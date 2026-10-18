"""Every seat in a league, solved ahead of the draft-order reveal.

FirstDown releases the order 30 minutes before the draft, so there is no time
to think. This precomputes the answer for all N seats: pick numbers, what the
engine does with the first three, and which early moves are measurably wrong.
"""
import sys, statistics, collections
from pathlib import Path
from gridiron.live.league import load_config
from gridiron.live.pool import load_pool
from gridiron.live.vorp import compute_vorp, LeagueConfig
from gridiron.live.simulate import run_draft, starting_points, engine, _available
from gridiron.live import snake

LEAGUE = sys.argv[1] if len(sys.argv) > 1 else "FirstDown"
BEHAV, PEN = range(120), range(60)

cfg = load_config(Path(f"data/2026/league_{LEAGUE}.json"))
pool = load_pool(Path(f"data/2026/pool_{LEAGUE}.csv"))
compute_vorp(pool, cfg)
N = cfg.num_teams
base = engine()

def seat_cfg(slot):
    return LeagueConfig(num_teams=N, rounds=cfg.rounds, my_slot=slot,
                        starters=dict(cfg.starters), flex_count=cfg.flex_count,
                        max_at_pos=dict(cfg.max_at_pos))

def forcing(plan):
    def pick(ctx):
        want = plan.get(ctx.overall)
        if want:
            c = [p for p in _available(ctx) if p.pos == want and p.proj_points > 0]
            if c:
                return max(c, key=lambda p: p.vorp)
        return base(ctx)
    return pick

out = []
out.append(f"# {LEAGUE} — every seat, decided in advance\n")
out.append(f"{N} teams · {cfg.rounds} rounds · starters "
           + ", ".join(f"{n}{p}" for p, n in cfg.starters.items())
           + f" · {cfg.flex_count} flex\n")
out.append("Draft order is released 30 minutes before the draft. Find your row, "
           "type `/slot N` into the board, and draft.\n")

rows = []
for slot in range(1, N + 1):
    picks = [snake.overall_of(r, slot, N) for r in range(1, 7)]
    first3 = picks[:3]
    pts, posmix, names = [], collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for sd in BEHAV:
        r = run_draft({slot: engine()}, cfg, pool, sd)
        pts.append(starting_points(r[slot], seat_cfg(slot)))
        for i in range(3):
            p = r[slot][i]
            posmix[i][p.pos] += 1
            names[i][p.name] += 1
    # penalties for the classic early mistakes
    pen = {}
    baseline = [starting_points(run_draft({slot: engine()}, cfg, pool, sd)[slot], seat_cfg(slot))
                for sd in PEN]
    for label, plan in {
        "QB early":   {first3[1]: "QB"},
        "TE early":   {first3[1]: "TE"},
        "WR+WR":      {first3[1]: "WR", first3[2]: "WR"},
        "RB+RB":      {first3[1]: "RB", first3[2]: "RB"},
    }.items():
        a = [starting_points(run_draft({slot: forcing(plan)}, cfg, pool, sd)[slot], seat_cfg(slot))
             for sd in PEN]
        d = [x - y for x, y in zip(a, baseline)]
        pen[label] = (statistics.mean(d), 2 * statistics.pstdev(d) / len(d) ** 0.5)
    rows.append((slot, picks, pts, posmix, names, pen))
    print(f"  seat {slot}/{N} done", flush=True)

bestmean = max(statistics.mean(r[2]) for r in rows)
out.append("\n## Seat summary\n")
out.append("| seat | your picks | waits | value | pick 1 | picks 2–3 |")
out.append("|---|---|---|---|---|---|")
for slot, picks, pts, posmix, names, pen in rows:
    waits = "+".join(str(picks[i+1]-picks[i]-1) for i in range(2))
    m = statistics.mean(pts)
    p1 = names[0].most_common(1)[0]
    p1s = f"{p1[0]} ({100*p1[1]/len(BEHAV):.0f}%)"
    mix = lambda i: " ".join(f"{k}{100*v/len(BEHAV):.0f}" for k, v in posmix[i].most_common(2))
    out.append(f"| **{slot}** | {', '.join(map(str,picks[:4]))} | {waits} | "
               f"{m:.0f} ({m-bestmean:+.0f}) | {p1s} | {mix(1)} / {mix(2)} |")

out.append("\n## What is measurably wrong, by seat\n")
out.append("Points vs letting the engine choose, over 80 paired drafts. "
           "Bold = beyond 2 standard errors, i.e. real.\n")
out.append("| seat | QB early | TE early | WR+WR | RB+RB |")
out.append("|---|---|---|---|---|")
for slot, picks, pts, posmix, names, pen in rows:
    cells = []
    for k in ("QB early", "TE early", "WR+WR", "RB+RB"):
        d, se = pen[k]
        cells.append(f"**{d:+.0f}**" if abs(d) > se else f"{d:+.0f}")
    out.append(f"| **{slot}** | " + " | ".join(cells) + " |")

Path(f"SEATS_{LEAGUE}.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"\nwrote SEATS_{LEAGUE}.md")
