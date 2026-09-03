"""Terminal draft assistant -- the floor.

Deliberately the least sophisticated thing that wins the draft. No server, no
browser, no network once the pool CSV exists. It reads and writes the same
SQLite file as the web UI, so if the browser dies mid-draft you Ctrl-C, run this,
and continue at the exact pick. A real hot spare, not a theoretical one.

Bare text is always a player name. A leading '/' is always a command -- no
player name starts with one, so there is no ambiguity to resolve under a clock.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import names, snake
from .pool import load_pool
from .recommend import DEFAULT_URGENCY, recommend
from .store import PickConflict, PickStore
from .vorp import LeagueConfig, compute_vorp, roster_counts

BOLD, DIM, RED, GREEN, YELLOW, CYAN, RESET = (
    "\033[1m", "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[36m", "\033[0m",
)

HELP = """
  <name>        mark GONE -- someone drafted them  (e.g. 'cmc', 'arsb')
  +<name>       mark MINE -- I drafted them
  /u            undo the last pick
  /c <n> <name> correct pick n
  /j <n>        jump: next entry is overall pick n
  /s            skip -- a pick happened, player unknown
  /b [pos]      board: top 15, optionally by position
  /r            my roster
  /l <0-1>      set urgency weight (0 = pure VORP, 1 = pure VONA)
  /h            this help
  /q            quit
"""


def fmt_pick(overall: int, teams: int) -> str:
    return snake.label(overall, teams)


def show_state(store, pool, league, urgency):
    nxt = store.next_overall()
    total = league.total_picks
    if nxt > total:
        print(f"\n{GREEN}Draft complete.{RESET}")
        return False

    on_clock = snake.slot_on_clock(nxt, league.num_teams)
    mine = on_clock == league.my_slot
    until = snake.picks_until_next_turn(nxt, league.num_teams, league.my_slot, league.rounds)
    my_next = snake.next_pick_at_or_after(nxt, league.num_teams, league.my_slot, league.rounds)

    bar = GREEN if mine else DIM
    print(f"\n{bar}{'='*76}{RESET}")
    head = f"{fmt_pick(nxt, league.num_teams)}  slot {on_clock}"
    if mine:
        print(f"{GREEN}{BOLD}>>> YOUR PICK   {head}{RESET}")
    else:
        after = snake.next_pick_after(my_next, league.num_teams, league.my_slot, league.rounds)
        turn = f"  then {fmt_pick(after, league.num_teams)}" if after else ""
        print(f"{DIM}on the clock: {head}{RESET}   "
              f"your next: {BOLD}{fmt_pick(my_next, league.num_teams)}{RESET} "
              f"({until} away){turn}")
    print(f"{bar}{'='*76}{RESET}")

    drafted = store.drafted_ids()
    roster = [pool.by_id[pid] for pid in store.my_players() if pid in pool.by_id]
    recs = recommend(pool, drafted, roster, league, nxt, top_n=5, urgency=urgency)
    if not recs:
        print("  (no candidates)")
        return True

    for i, r in enumerate(recs, 1):
        p = r.player
        flag = f" {RED}{p.injury_status}{RESET}" if p.is_injured() else ""
        star = f"{BOLD}" if i == 1 and mine else ""
        # `score` is the sort key and must be visible: without it, a player with
        # higher VORP ranking below one with lower VORP looks like a bug.
        print(f"  {star}{i}. {p.name:<24}{RESET} {CYAN}{p.pos:<4}{RESET}{p.team:<4} "
              f"{BOLD}score {r.score:6.1f}{RESET}  {DIM}={RESET} VORP {r.vorp:6.1f} "
              f"- {urgency:g}x wait  {DIM}|{RESET} VONA {r.vona:6.1f}  "
              f"bye {p.bye_week:>2}{flag}")
        print(f"     {DIM}{r.reason}{RESET}")

    counts = roster_counts(roster)
    have = " ".join(f"{k}{v}" for k, v in counts.items() if v)
    print(f"\n  {DIM}roster: {have or '(empty)'}   "
          f"picks left: {snake.picks_remaining(nxt, league.num_teams, league.my_slot, league.rounds)}"
          f"   urgency {urgency}{RESET}")
    return True


def resolve(query: str, pool, drafted: set[int]):
    """Return one player or None, prompting if the query is ambiguous."""
    rows = [
        {"name": p.name, "rank": i, "pid": p.player_id, "pos": p.pos, "team": p.team}
        for i, p in enumerate(pool.players)
        if p.player_id not in drafted
    ]
    hits = names.search(query, rows, limit=6)
    if not hits:
        print(f"  {RED}no match for {query!r}{RESET}")
        return None
    if names.is_decisive(hits):
        return pool.by_id[hits[0]["pid"]]
    exact = [h for h in hits if names.normalize(h["name"]) == names.normalize(query)]
    if len(exact) == 1:
        return pool.by_id[exact[0]["pid"]]
    for i, h in enumerate(hits, 1):
        print(f"    {i}. {h['name']:<24} {h['pos']:<4}{h['team']}")
    sel = input("  which? [1] ").strip() or "1"
    if not sel.isdigit() or not (1 <= int(sel) <= len(hits)):
        return None
    return pool.by_id[hits[int(sel) - 1]["pid"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Terminal draft assistant.")
    ap.add_argument("--league", default="main")
    ap.add_argument("--pool", type=Path, default=Path("data/2026/player_pool_latest.csv"))
    ap.add_argument("--slot", type=int, required=True, help="your draft slot (1-N)")
    ap.add_argument("--teams", type=int, default=12)
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--urgency", type=float, default=DEFAULT_URGENCY)
    ap.add_argument("--reset", action="store_true", help="clear recorded picks first")
    args = ap.parse_args(argv)

    if not args.pool.exists():
        print(f"no pool at {args.pool} -- run: python -m gridiron.live.espn", file=sys.stderr)
        return 1

    league = LeagueConfig(num_teams=args.teams, rounds=args.rounds, my_slot=args.slot)
    pool = load_pool(args.pool)
    levels = compute_vorp(pool, league)
    store = PickStore(Path(f"data/2026/draft_{args.league}.sqlite"), args.teams)
    if args.reset:
        store.reset()

    urgency = args.urgency
    override: int | None = None

    print(f"{BOLD}{args.league}{RESET}  {args.teams}-team, {args.rounds} rounds, "
          f"slot {args.slot}   pool={len(pool.players)}")
    print("  replacement: " + "  ".join(f"{k} {v:.0f}" for k, v in sorted(levels.items())))
    print(f"{DIM}/h for help{RESET}")

    while True:
        if not show_state(store, pool, league, urgency):
            break
        try:
            raw = input(f"\n{BOLD}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not raw:
            continue

        if raw.startswith("/"):
            parts = raw[1:].split()
            cmd = parts[0].lower() if parts else ""
            rest = parts[1:]
            if cmd in ("q", "quit"):
                break
            elif cmd in ("h", "help"):
                print(HELP)
            elif cmd == "u":
                p = store.undo_last()
                if p:
                    who = pool.by_id.get(p.player_id)
                    print(f"  {YELLOW}undid {fmt_pick(p.overall, args.teams)} "
                          f"{who.name if who else p.observed_name}{RESET}")
                else:
                    print(f"  {DIM}nothing to undo{RESET}")
            elif cmd == "s":
                p = store.append(None, overall=override, source="unknown",
                                 observed_name="UNKNOWN")
                override = None
                print(f"  {YELLOW}recorded unknown at {fmt_pick(p.overall, args.teams)}{RESET}")
            elif cmd == "j" and rest:
                override = int(rest[0])
                print(f"  next entry -> {fmt_pick(override, args.teams)}")
            elif cmd == "l" and rest:
                urgency = max(0.0, min(1.0, float(rest[0])))
            elif cmd == "c" and len(rest) >= 2:
                target = int(rest[0])
                who = resolve(" ".join(rest[1:]), pool, store.drafted_ids())
                if who:
                    try:
                        store.correct(target, who.player_id)
                        print(f"  {GREEN}pick {target} -> {who.name}{RESET}")
                    except (KeyError, PickConflict) as e:
                        print(f"  {RED}{e}{RESET}")
            elif cmd == "r":
                mine = [pool.by_id[pid] for pid in store.my_players()
                        if pid in pool.by_id]
                for p in mine:
                    print(f"    {p.pos:<4} {p.name:<24} {p.team}  bye {p.bye_week}")
                if not mine:
                    print(f"    {DIM}(empty){RESET}")
            elif cmd == "b":
                pos = rest[0].upper() if rest else None
                drafted = store.drafted_ids()
                cand = (pool.at_position(pos, drafted) if pos
                        else sorted(pool.available(drafted), key=lambda p: -p.vorp))
                for i, p in enumerate(cand[:15], 1):
                    print(f"    {i:2}. {p.name:<24} {p.pos:<4}{p.team:<4} "
                          f"VORP {p.vorp:6.1f}  adp {p.adp:6.1f}")
            else:
                print(f"  {DIM}unknown command -- /h for help{RESET}")
            continue

        claim = raw.startswith("+")
        who = resolve(raw[1:] if claim else raw, pool, store.drafted_ids())
        if who is None:
            continue
        try:
            p = store.append(who.player_id, overall=override, mine=claim)
            override = None
            mine = f" {GREEN}<- YOURS{RESET}" if p.mine else ""
            print(f"  {GREEN}{fmt_pick(p.overall, args.teams)}  {who.name} "
                  f"({who.pos} {who.team}){mine}{RESET}")
        except PickConflict as e:
            print(f"  {RED}{e}{RESET}")

    store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
