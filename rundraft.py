#!/usr/bin/env python3
"""Launch the live draft board.

    ./rundraft.py --league main   --slot 3  --port 8100 --accent "#c0392b"
    ./rundraft.py --league second --slot 7  --port 8101 --accent "#1f6feb"

Two leagues run as two independent processes with separate SQLite files. If one
crashes the other is untouched -- which is the real reason for processes rather
than one server holding two drafts.

The accent colour paints the header band. The failure mode worth designing
against is human: typing a pick into the wrong browser tab.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from gridiron.live.server import build_session, serve


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live draft board.")
    ap.add_argument("--league", default="main", help="league name; keys the SQLite file")
    ap.add_argument("--slot", type=int, required=True, help="your draft slot (1-N)")
    ap.add_argument("--teams", type=int, default=12)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--port", type=int, default=8100)
    ap.add_argument("--accent", default="#c0392b", help="header band colour")
    ap.add_argument("--pool", type=Path,
                    default=Path("data/2026/player_pool_latest.csv"))
    ap.add_argument("--reset", action="store_true", help="clear recorded picks first")
    args = ap.parse_args(argv)

    if not args.pool.exists():
        print(f"no player pool at {args.pool}\n"
              f"build one with:  python -m gridiron.live.espn", file=sys.stderr)
        return 1
    if not 1 <= args.slot <= args.teams:
        print(f"--slot must be 1..{args.teams}", file=sys.stderr)
        return 1

    session = build_session(
        league=args.league,
        pool_csv=args.pool,
        db_path=Path(f"data/2026/draft_{args.league}.sqlite"),
        my_slot=args.slot,
        teams=args.teams,
        rounds=args.rounds,
        accent=args.accent,
    )
    if args.reset:
        session.store.reset()
    serve(session, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
