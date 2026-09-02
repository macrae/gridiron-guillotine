"""Fetch the 2026 player pool (projections + ADP) from ESPN's public endpoint.

One unauthenticated GET returns the whole board. No auth, no pagination, no
scraping. `leaguedefaults/3` is full PPR with 4-point passing TDs -- both
verified empirically by reconstructing player points from raw components.

UNITS TRAP: a player's `stats` list holds both per-week and season blocks with
the same `appliedTotal` field name, 17x apart. The season block is identified by
id "10<season>" (statSourceId=1, statSplitTypeId=0). We pin that id exactly and
fail loudly if it is missing -- mixing these is the defect class that broke the
previous pipeline.

Stdlib + requests only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from .names import normalize

BASE = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons"

POSITION_MAP = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DST"}
SLOT_MAP = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 16: "DST", 17: "K"}
FANTASY_POSITIONS = {"QB", "RB", "WR", "TE", "K", "DST"}

# Raw component stats, kept as a rescoring escape hatch. If a league turns out
# to be 6-pt passing TDs or half-PPR, recompute from these instead of refetching.
COMPONENT_STATS = {
    "3": "pass_yds",
    "4": "pass_td",
    "20": "interceptions",
    "23": "rush_att",
    "24": "rush_yds",
    "25": "rush_td",
    "42": "rec_yds",
    "43": "rec_td",
    "53": "receptions",
    "58": "targets",
    "72": "fumbles_lost",
}

POOL_FIELDS = [
    "player_id", "name", "name_norm", "pos", "team", "bye_week",
    "proj_points", "adp", "adp_source", "espn_ppr_rank", "auction_value",
    "percent_owned", "injury_status", "eligible_pos", "snapshot_ts",
]


class DataGateError(Exception):
    """A verification gate failed. Stop -- do not build on this data."""


def fetch_players(season: int = 2026, limit: int = 700, timeout: int = 45) -> list[dict]:
    """Single GET for the whole player pool."""
    filt = {
        "players": {
            "limit": limit,
            "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": "PPR"},
        }
    }
    resp = requests.get(
        f"{BASE}/{season}/segments/0/leaguedefaults/3",
        params={"view": "kona_player_info"},
        headers={"x-fantasy-filter": json.dumps(filt)},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json().get("players", [])


def fetch_pro_teams(season: int = 2026, timeout: int = 30) -> dict[int, dict]:
    """proTeamId -> {abbrev, bye_week}."""
    resp = requests.get(
        f"{BASE}/{season}",
        params={"view": "proTeamSchedules_wl"},
        timeout=timeout,
    )
    resp.raise_for_status()
    teams = resp.json().get("settings", {}).get("proTeams", [])
    return {
        t["id"]: {"abbrev": t.get("abbrev", "FA"), "bye_week": t.get("byeWeek", 0)}
        for t in teams
    }


def season_stat_block(player: dict, season: int) -> dict | None:
    """The season-total projection block, pinned by id. None if absent."""
    target = f"10{season}"
    for s in player.get("stats", []):
        if s.get("id") == target:
            return s
    return None


def extract(entry: dict, pro_teams: dict[int, dict], season: int, ts: str) -> tuple[dict, dict] | None:
    """(pool_row, component_row) for one player, or None if unusable."""
    p = entry.get("player") or {}
    pos = POSITION_MAP.get(p.get("defaultPositionId"))
    if pos not in FANTASY_POSITIONS:
        return None

    block = season_stat_block(p, season)
    if block is None or block.get("appliedTotal") is None:
        return None

    team = pro_teams.get(p.get("proTeamId"), {"abbrev": "FA", "bye_week": 0})
    own = p.get("ownership") or {}
    ranks = (p.get("draftRanksByRankType") or {}).get("PPR") or {}
    eligible = sorted(
        {SLOT_MAP[s] for s in p.get("eligibleSlots", []) if s in SLOT_MAP}
    )
    name = p.get("fullName") or ""

    pool_row = {
        "player_id": p.get("id"),
        "name": name,
        "name_norm": normalize(name),
        "pos": pos,
        "team": team["abbrev"],
        "bye_week": team["bye_week"],
        "proj_points": round(float(block["appliedTotal"]), 2),
        "adp": round(float(own.get("averageDraftPosition") or 0.0), 2),
        "adp_source": "espn",
        "espn_ppr_rank": ranks.get("rank", 0),
        "auction_value": round(float(own.get("auctionValueAverage") or 0.0), 2),
        "percent_owned": round(float(own.get("percentOwned") or 0.0), 2),
        "injury_status": p.get("injuryStatus") or "ACTIVE",
        "eligible_pos": "|".join(eligible) or pos,
        "snapshot_ts": ts,
    }

    raw = block.get("stats") or {}
    comp_row = {"player_id": p.get("id"), "name": name}
    for stat_id, label in COMPONENT_STATS.items():
        comp_row[label] = round(float(raw.get(stat_id, 0.0) or 0.0), 2)
    return pool_row, comp_row


def check_gates(
    raw_count: int, rows: list[dict], min_players: int = 600, min_draftable: int = 400
) -> list[str]:
    """The four pre-build assertions. Returns a list of failures (empty == pass).

    Note on zero-projection players: ESPN legitimately projects 0 for players on
    IR, suspended, or buried on a depth chart. They are kept in the CSV so that
    the name matcher can still resolve them if someone reaches on one -- an
    unmatchable pick is a louder problem than an unrecommendable player. The
    engine excludes them from candidates via proj_points > 0, so the gate that
    matters is how many *draftable* players survive, not what share project > 0.
    """
    failures = []

    if raw_count < min_players:
        failures.append(f"only {raw_count} players returned (want >={min_players})")

    if not rows:
        failures.append("no usable rows extracted")
        return failures

    draftable = sum(1 for r in rows if r["proj_points"] > 0)
    if draftable < min_draftable:
        failures.append(
            f"only {draftable} draftable players (proj>0), want >={min_draftable}"
        )

    with_adp = sum(1 for r in rows if r["adp"] > 0)
    if with_adp / len(rows) < 0.95:
        failures.append(
            f"only {with_adp}/{len(rows)} ({with_adp/len(rows):.0%}) have an ADP"
        )

    rbs = sorted((r for r in rows if r["pos"] == "RB"), key=lambda r: -r["proj_points"])
    if not rbs:
        failures.append("no RBs in pool")
    elif not (280 <= rbs[0]["proj_points"] <= 400):
        failures.append(
            f"RB1 {rbs[0]['name']} projects {rbs[0]['proj_points']} "
            f"-- outside 280-400, suspect wrong season or wrong units"
        )
    return failures


def build(out_dir: Path, season: int = 2026, limit: int = 700) -> tuple[Path, Path]:
    """Fetch, verify, and write the pool CSV plus the component sidecar."""
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"fetching ESPN season {season} (limit {limit}) ...")
    raw = fetch_players(season, limit)
    pro_teams = fetch_pro_teams(season)
    print(f"  {len(raw)} players, {len(pro_teams)} pro teams")

    extracted = [extract(e, pro_teams, season, ts) for e in raw]
    pairs = [x for x in extracted if x is not None]
    rows = [a for a, _ in pairs]
    comps = [b for _, b in pairs]

    failures = check_gates(len(raw), rows)
    if failures:
        for f in failures:
            print(f"  GATE FAIL: {f}", file=sys.stderr)
        raise DataGateError(f"{len(failures)} gate(s) failed -- refusing to write")
    zero = sum(1 for r in rows if r["proj_points"] <= 0)
    print(
        f"  gates passed: {len(rows)} fantasy-position players "
        f"({len(rows) - zero} draftable, {zero} projected 0 -- IR/OUT/depth, kept for name matching)"
    )

    rows.sort(key=lambda r: -r["proj_points"])

    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    pool_path = out_dir / f"player_pool_{stamp}.csv"
    comp_path = out_dir / f"raw_stats_{stamp}.csv"

    with pool_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=POOL_FIELDS)
        w.writeheader()
        w.writerows(rows)
    with comp_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["player_id", "name", *COMPONENT_STATS.values()])
        w.writeheader()
        w.writerows(comps)

    # Stable paths the rest of the tooling reads. Snapshots are never
    # overwritten -- you will want to diff them on Friday night.
    for src, dst in ((pool_path, "player_pool_latest.csv"), (comp_path, "raw_stats_latest.csv")):
        (out_dir / dst).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    print(f"  wrote {pool_path}")
    print(f"  wrote {comp_path}")
    return pool_path, comp_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the 2026 player pool from ESPN.")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--limit", type=int, default=700)
    ap.add_argument("--out", type=Path, default=Path("data/2026"))
    args = ap.parse_args(argv)
    try:
        build(args.out, args.season, args.limit)
    except DataGateError as e:
        print(f"\nABORTED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
