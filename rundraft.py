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
import functools
import sys
from pathlib import Path

from gridiron.live.league import (ConfigError, default_config, describe,
                                  load_config, save_config, scoring_for)
from gridiron.live.scoring import bonus_note, rescore_pool
from gridiron.live.server import build_session, serve


# The launch banner is the pre-flight check -- unbuffered so it survives nohup,
# tee, and redirection to a log file.
print = functools.partial(__builtins__.print if not isinstance(__builtins__, dict)
                          else __builtins__["print"], flush=True)


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
    ap.add_argument("--config", type=Path,
                    help="league settings JSON (roster slots, flex, caps). "
                         "Defaults to data/2026/league_<name>.json if present.")
    ap.add_argument("--flex", type=int, help="FLEX slots (default 1)")
    ap.add_argument("--peer", action="append", default=[], metavar="NAME:PORT",
                    help="another league to offer a header link to, e.g. "
                         "FirstDown:8101. Repeatable. Navigation only -- the "
                         "processes stay independent.")
    ap.add_argument("--write-config", action="store_true",
                    help="write the resolved settings to the league JSON and exit")
    args = ap.parse_args(argv)

    if not args.pool.exists():
        print(f"no player pool at {args.pool}\n"
              f"build one with:  python -m gridiron.live.espn", file=sys.stderr)
        return 1
    if not 1 <= args.slot <= args.teams:
        print(f"--slot must be 1..{args.teams}", file=sys.stderr)
        return 1

    # League settings: explicit --config, else a per-league file if one exists,
    # else the Yahoo standard lineup adjusted by flags.
    cfg_path = args.config or Path(f"data/2026/league_{args.league}.json")
    try:
        if cfg_path.exists():
            cfg = load_config(cfg_path)
            cfg.my_slot = args.slot
            if args.teams != 12:
                cfg.num_teams = args.teams
            if args.rounds != 15:
                cfg.rounds = args.rounds
            print(f"  settings from {cfg_path}")
        else:
            cfg = default_config(args.teams, args.rounds, args.slot)
        if args.flex is not None:
            cfg.flex_count = args.flex
        from gridiron.live.league import validate
        validate(cfg)
    except ConfigError as e:
        print(f"league settings invalid: {e}", file=sys.stderr)
        return 1

    if args.write_config:
        out = save_config(cfg, cfg_path)
        print(f"wrote {out}\n  {describe(cfg)}")
        return 0

    # Each league scores differently, so each gets its own board. ESPN's
    # numbers are ITS scoring; using them unchanged silently misprices any
    # league that does not match.
    rules = scoring_for(cfg_path)
    pool_path = args.pool
    raw_path = args.pool.parent / "raw_stats_latest.csv"
    if rules.name != "yahoo_default" and raw_path.exists():
        pool_path, n, kept = rescore_pool(
            args.pool, raw_path, rules, args.pool.parent / f"pool_{args.league}.csv")
        print(f"  scoring: {rules.name}  (rescored {n}, kept ESPN for {kept} K/DST)")
        note = bonus_note(rules)
        if note:
            print(f"  {note}")

    peers = []
    for spec in args.peer:
        name, _, port = spec.partition(":")
        if not name or not port.isdigit():
            print(f"--peer must look like NAME:PORT, got {spec!r}", file=sys.stderr)
            return 1
        peers.append({"name": name, "url": f"http://127.0.0.1:{port}/"})
    if peers:
        print("  peers: " + ", ".join(f"{p['name']} -> {p['url']}" for p in peers))

    print(f"  {describe(cfg)}")
    session = build_session(
        league=args.league,
        pool_csv=pool_path,
        db_path=Path(f"data/2026/draft_{args.league}.sqlite"),
        config=cfg,
        accent=args.accent,
        peers=peers,
    )
    if args.reset:
        session.store.reset()
    serve(session, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
