"""Injury and role risk from ESPN's league-wide injury report.

Far richer than the news headline feed: ~800 records carrying a status, the body
part, the specific diagnosis, an estimated return date, and a beat-writer note.
The notes are where the role risk lives -- "Love is still likely to split
carries with Tyler Allgeier" is exactly the thing a projection cannot tell you.

These records carry NO athlete id, unlike the news feed, so the join is by name
and position through gridiron.live.names. That is the join style this codebase
otherwise avoids, so it is instrumented: `unmatched_fantasy` reports every
QB/RB/WR/TE/K the report knows about and the pool does not. On the current feed
those are all genuinely absent from ESPN's top-700 (backups like AJ Dillon and
Cooper Rush), not matcher failures -- but a silent name join is exactly how you
end up trusting a roster that is quietly wrong.
"""

from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path

import requests

from . import names

FEED = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

FANTASY_POS = ("QB", "RB", "WR", "TE", "K")

#: Worst first. Drives ordering and the colour of the badge.
SEVERITY = {
    "Injured Reserve": 4,
    "Suspension": 4,
    "Out": 3,
    "Doubtful": 3,
    "Questionable": 2,
    "Day-To-Day": 1,
    "Active": 0,
}


def severity(status: str | None) -> int:
    return SEVERITY.get(status or "", 1)


def fetch(timeout: int = 40) -> dict:
    resp = requests.get(FEED, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _records(payload: dict) -> list[dict]:
    out = []
    for team in payload.get("injuries") or []:
        for r in team.get("injuries") or []:
            a = r.get("athlete") or {}
            det = r.get("details") or {}
            out.append({
                "name": (a.get("displayName") or "").strip(),
                "pos": (a.get("position") or {}).get("abbreviation"),
                "team": ((a.get("team") or {}).get("abbreviation")
                         or team.get("abbreviation") or ""),
                "status": r.get("status"),
                "type": det.get("type"),
                "detail": det.get("detail"),
                "return_date": det.get("returnDate"),
                "note": (r.get("shortComment") or "").strip(),
                "long_note": (r.get("longComment") or "").strip(),
            })
    return out


def weeks_out(return_date: str | None, today: date | None = None) -> int | None:
    """Whole weeks until the estimated return. None if unknown or in the past."""
    if not return_date:
        return None
    try:
        d = datetime.strptime(return_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    days = (d - (today or date.today())).days
    return max(0, round(days / 7)) if days > 0 else None


def build(out_path: Path, pool) -> tuple[Path, int, int, list[str]]:
    """Fetch, join to the pool, cache.

    Returns (path, matched, non_active, unmatched_fantasy_names).
    """
    recs = _records(fetch())
    rows = pool.as_rows()
    by_player: dict[int, dict] = {}
    unmatched: list[str] = []

    for r in recs:
        pos = r["pos"] if r["pos"] in FANTASY_POS else None
        hit = names.match(r["name"], rows, pos=pos, team=r["team"] or None)
        if hit is None:
            if r["pos"] in FANTASY_POS:
                unmatched.append(f"{r['name']} ({r['pos']} {r['team']})")
            continue
        pid = hit["player_id"]
        prior = by_player.get(pid)
        # One player can appear more than once; keep the worst.
        if prior is None or severity(r["status"]) > severity(prior["status"]):
            by_player[pid] = {
                "status": r["status"], "type": r["type"], "detail": r["detail"],
                "return_date": r["return_date"], "weeks_out": weeks_out(r["return_date"]),
                "note": r["note"], "long_note": r["long_note"],
                "severity": severity(r["status"]),
            }

    non_active = sum(1 for v in by_player.values() if v["severity"] > 0)
    payload = {"fetched_at": time.time(), "records": len(recs),
               "unmatched_fantasy": sorted(unmatched),
               "players": {str(k): v for k, v in by_player.items()}}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return out_path, len(by_player), non_active, sorted(unmatched)


def load(path: Path) -> dict[int, dict]:
    """Cached report. A missing or corrupt file loads empty -- risk data is a
    bonus and must never be able to stop a draft."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {int(k): v for k, v in (data.get("players") or {}).items()}


def age_hours(path: Path) -> float | None:
    p = Path(path)
    if not p.exists():
        return None
    try:
        return (time.time() - json.loads(p.read_text(encoding="utf-8"))["fetched_at"]) / 3600
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def main(argv: list[str] | None = None) -> int:
    import argparse
    from .pool import load_pool
    ap = argparse.ArgumentParser(description="Cache the ESPN injury report.")
    ap.add_argument("--pool", type=Path,
                    default=Path("data/2026/player_pool_latest.csv"))
    ap.add_argument("--out", type=Path, default=Path("data/2026/injuries.json"))
    args = ap.parse_args(argv)
    path, matched, non_active, unmatched = build(args.out, load_pool(args.pool))
    print(f"  {matched} players matched, {non_active} carrying an injury -> {path}")
    if unmatched:
        print(f"  {len(unmatched)} fantasy-position names not in the pool "
              f"(deep roster, not matcher failures): {', '.join(unmatched[:5])}"
              f"{' ...' if len(unmatched) > 5 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
