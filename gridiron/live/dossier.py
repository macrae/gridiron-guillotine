"""Per-player research dossiers from ESPN's athlete overview endpoint.

One request per player returns far more than the league-wide feeds do:

  rotowire            a beat-writer note -- practice reports, camp performance,
                      depth-chart movement. The scouting layer.
  fantasy.projection  a written analyst outlook for the season ahead.
  news                ~13 articles about THAT player, versus 50 for the league.
  statistics          prior season and career production.

The cost is one HTTP request per player and roughly 240 KB of response, so this
is deliberately a pre-draft build over the top N by value, not something the
live board does. The draft never waits on it: a missing dossier file simply
means the research page is empty, and every failure is per-player and skipped.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

OVERVIEW = ("https://site.api.espn.com/apis/common/v3/sports/football/nfl"
            "/athletes/{pid}/overview")

#: How many players to pull, by VORP. A 12-team 14-round draft is 168 picks, so
#: this comfortably covers everyone who will actually be taken.
DEFAULT_DEPTH = 190


def _clip(text: str | None, limit: int) -> str:
    t = (text or "").strip()
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def fetch_one(player_id: int, timeout: int = 20) -> dict | None:
    """The interesting parts of one athlete overview, or None on any failure."""
    try:
        r = requests.get(OVERVIEW.format(pid=player_id), timeout=timeout)
        if r.status_code != 200:
            return None
        d = r.json()
    except (requests.RequestException, ValueError):
        return None

    rw = d.get("rotowire") or {}
    fz = d.get("fantasy") or {}
    news = []
    for n in (d.get("news") or [])[:8]:
        news.append({
            "headline": _clip(n.get("headline"), 160),
            "published": (n.get("published") or "")[:10],
            "link": ((n.get("links") or {}).get("web") or {}).get("href", ""),
        })

    stats = {}
    st = d.get("statistics") or {}
    labels = st.get("labels") or st.get("names") or []
    for split in st.get("splits") or []:
        name = split.get("displayName")
        if name in ("Regular Season", "Career") and split.get("stats"):
            stats[name] = dict(zip(labels, split["stats"]))

    return {
        "scouting": {
            "headline": _clip(rw.get("headline"), 400),
            "story": _clip(rw.get("story"), 1600),
            "published": (rw.get("published") or "")[:10],
        } if rw.get("headline") else None,
        "outlook": _clip(fz.get("projection"), 1400) or None,
        "draft_rank": fz.get("draftRank"),
        "position_rank": fz.get("positionRank"),
        "percent_owned": fz.get("percentOwned"),
        "news": news,
        "stats": stats,
    }


def build(out_path: Path, pool, depth: int = DEFAULT_DEPTH,
          pause: float = 0.12, progress=None) -> tuple[Path, int, int]:
    """Fetch dossiers for the top `depth` players by VORP.

    Returns (path, fetched, failed). A per-player failure is skipped, never
    fatal -- partial research is far better than none an hour before a draft.
    """
    # D/ST are team entries, not athletes -- ESPN has no overview for them, so
    # requesting one is a guaranteed miss that would read as a failure.
    ranked = sorted((p for p in pool.players if p.draftable),
                    key=lambda p: -p.vorp)[:depth]
    targets = [p for p in ranked if p.pos != "DST"]
    out: dict[str, dict] = {}
    failed = 0
    for i, p in enumerate(targets, 1):
        rec = fetch_one(p.player_id)
        if rec is None:
            failed += 1
        else:
            out[str(p.player_id)] = rec
        if progress and (i % 25 == 0 or i == len(targets)):
            progress(i, len(targets), failed)
        time.sleep(pause)          # be a good citizen against a free endpoint

    payload = {"fetched_at": time.time(), "depth": depth,
               "failed": failed, "skipped_dst": len(ranked) - len(targets),
               "players": out}
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload), encoding="utf-8")
    return out_path, len(out), failed


def load(path: Path) -> dict[int, dict]:
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
    from .league import load_config
    from .pool import load_pool
    from .vorp import compute_vorp
    ap = argparse.ArgumentParser(description="Build per-player research dossiers.")
    ap.add_argument("--league", default="2MinuteDrill")
    ap.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    ap.add_argument("--out", type=Path, default=Path("data/2026/dossier.json"))
    args = ap.parse_args(argv)

    cfg = load_config(Path(f"data/2026/league_{args.league}.json"))
    pool = load_pool(Path(f"data/2026/pool_{args.league}.csv"))
    compute_vorp(pool, cfg)

    def show(done: int, total: int, failed: int) -> None:
        print(f"  {done}/{total} ({failed} failed)", flush=True)

    print(f"fetching {args.depth} dossiers (~1 request each) ...", flush=True)
    path, got, failed = build(args.out, pool, args.depth, progress=show)
    print(f"  wrote {got} dossiers ({failed} failed) -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
