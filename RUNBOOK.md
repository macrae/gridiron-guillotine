# Draft day runbook

One page. Keep it open in a second tab.

---

## T-60 minutes

```bash
cd ~/gridiron-guillotine

# 1. Refresh the board — pool, news AND the injury report
.venv/bin/python -m gridiron.live.espn

# 2. Build the research dossiers (~1 min, once per league, do this the night before)
.venv/bin/python -m gridiron.live.dossier --league 2MinuteDrill
.venv/bin/python -m gridiron.live.dossier --league FirstDown --out data/2026/dossier.json

# 2. Launch. Slot can be wrong here -- you can fix it from the page.
.venv/bin/python rundraft.py --league main --slot 3 --port 8100 --accent "#c0392b"
```

Read the two lines it prints. They are the whole pre-flight:

```
  12-team, 15 rounds, slot 3 | QB1 RB2 WR2 TE1 K1 DST1 FLEX1 | 6 bench
  main: http://127.0.0.1:8100   slot 3/12   542 players
```

If the lineup line does not match your league, stop and fix it before the first
pick — a wrong roster shape silently miscalibrates every ranking.

**Both leagues** (two processes, never one):

```bash
.venv/bin/python rundraft.py --league 2MinuteDrill --slot N --port 8100 \
    --accent "#c0392b" --peer FirstDown:8101

.venv/bin/python rundraft.py --league FirstDown --slot N --port 8101 \
    --accent "#1f6feb" --peer 2MinuteDrill:8100
```

Red band = 2MinuteDrill (Sun 9:30pm), blue = FirstDown (Mon 11:00pm). The tab
title carries the league and the pick, and a header link switches between them
in one click. The failure mode this guards against is human: typing into the
wrong tab.

The link is navigation only -- the two processes share nothing, so one dying
cannot touch the other, and switching loses nothing because all state is on the
server.

---

## When your slot is assigned

Type into the box: `/slot 7` — recalculates instantly, no restart.

---

## Hovering a player

Hover any row in the **right column** -- board, next up, or by position -- for a
card answering "can I start him": the traffic-light verdict in words and colour,
a plain-language starting outlook, the injury report entry, the scouting note,
and the season outlook.

The ranking list in the left column has no hover card, by design: it is the
primary reading surface and you scan down it with the cursor. The card also
cannot spill into that column even when it opens leftward from the far right.

Fetched per player on demand and cached, so it costs one ~1KB request the first
time you hover someone and nothing after. The card never intercepts a click, so
hovering and then clicking to mark a player gone works normally.

Note the green wording: "silence in the feeds, not a medical clearance". A green
lamp on a player whose outlook mentions missing eight games last season is the
lamp working correctly -- it reports current flags, not career risk. Read the
outlook.

## The urgency dial

`score = VORP - urgency x e_next`, where `e_next` is the expected VORP of the
best player still there at your next pick. 0 is pure best-available; 1 is pure
value-over-next-available.

**Leave it at 0.2.** Measured across every seat in both leagues, paired seeds:

| urgency | FirstDown | 2MinuteDrill |
|---|---|---|
| 0.0 | -0.9 | -4.9 |
| 0.1 | -1.1 | -3.2 |
| **0.2** | **best** | **best** |
| 0.3 | -0.7 | -1.2 |
| 0.5 | -4.7 | -11.4 |
| 0.8 | -17.2 | -39.1 |
| 1.0 | -31.5 | -43.7 |

Three things fall out of this:

  * **0 to 0.3 is a flat band.** Anywhere in it is fine; the differences are
    within a couple of points.
  * **The error is one-directional.** Too low costs 1-5 points. Too high costs
    17-44. If you are unsure, sit low.
  * **Do not schedule it.** Ramping it up after round 3 tied with leaving it
    alone; ramping it down was 7-13 points worse. There is no round at which the
    dial wants to move.

Urgency is worth slightly more against a disciplined room, because e_next is
computed from ADP and a room that ignores ADP makes that estimate wrong:

| room | urg 0.0 | urg 0.2 | urg 0.5 |
|---|---|---|---|
| chalk | 2332.9 | **2342.7** | 2324.5 |
| normal | 2357.2 | **2362.7** | 2351.7 |
| chaotic | **2436.1** | 2435.6 | 2432.0 |

In a wild room 0.0 does edge ahead -- by half a point, which is nothing. The
honest reading is that 0.2 is never wrong, so there is no live situation worth
reaching for the slider mid-draft.

## Research page

`http://127.0.0.1:8100/research` — or the **research** link in the header.

A separate reading view, one dossier per player: scouting note, season outlook,
per-player news, prior-season stats, injury report, VORP/ADP. Filter by
position or name, sort by VORP / ADP / injury severity / value-vs-ADP, and
toggle "risk only" to see just the hurt.

It is deliberately separate from the board and does not poll, so it cannot
interfere with a live draft. Read it the night before.

---

## During the draft

**Two separate acts.** Marking a player *gone* says nothing about who took him —
you do not need to track that, and the recommendations do not care. Claiming a
player for your own roster is a second, explicit act.

| | |
|---|---|
| type 2-3 letters, `Enter` | **GONE** — somebody drafted them |
| `+name` then `Enter`, or `shift-Enter` | **MINE** — you drafted them |
| `↓` `↑` | move through matches |
| `Esc` | clear the box |
| `Space` on an empty box | a pick happened, you missed who — clock still advances |
| `⌘Z` / `⌘⇧Z` | undo / redo — or the ↶ ↷ buttons in the header |
| **reset** (footer) | clear every pick and start over; click twice to confirm |
| **by position** tab, click a row | GONE. Shift-click = MINE |
| **mine** tab, click a row | un-claim |
| click any row in **gone** | retype it; later picks are untouched |
| **draft grid** tab, click a cell | correct or **remove** that pick |
| `x` on a history row | same remove, without leaving the list |

**Removing frees the player and leaves the slot empty** — he goes straight back
into search and the position counts, the slot turns red, and nothing else
renumbers. Click the red cell (or the red log row) to fill it. This is the fast
repair when you recorded the wrong name and do not yet know the right one.

The **by position** tab is the fast path when the room is moving quicker than you
can type: pick the position chip, then click straight down the list. Rows you
mark stay in place struck through, so nothing shifts under your cursor.

`cmc` → McCaffrey · `arsb` → Amon-Ra St. Brown · `jsn` → Smith-Njigba.
Mean is 2.2 keystrokes; 95% of picks resolve in 3 or fewer.

Commands: `/u` undo · `/j 47` next entry is pick #47 · `/t 9` show team 9 ·
`/d 33` delete pick 33 and shift back · `/l 0.8` urgency · `/h` help.

---

## Reading the board

- **score** is the sort key: `VORP − 0.6 × what you lose by waiting`.
- **VONA** is the decision: value that evaporates before your next turn.
- The **snake strip** under the clock is the current round: green taken, amber
  on the clock, red missing, your seat outlined, and how many picks to your turn.
  The **draft grid** tab is the same thing for the whole draft.
- The strip above the tabs is how many are **left** at each position; amber
  means fewer remain than picks before your next turn.
- **best available at each** explains the top pick. When TE shows `cliff 21.3`
  and RB shows `cliff 2.2`, a lesser tight end outranking better backs is the
  engine working, not a glitch.
- A **dashed rule** in the list is a tier break — everything below it is a step
  down.
- The **dot before each name** is the research verdict. Hover it for the reason.
  · **green** nothing flagged in any feed — NOT a clean bill of health, the
    feeds do not cover everyone equally
  · **amber** a one-to-two game question, or a role/committee risk
  · **red** multi-week absence, or one with no stated return
- `BYE 13` amber chip = clashes with someone already on your roster.
- An injury chip (`GROIN ~1wk`, `KNEE ~5wk`) means the ESPN injury report has
  something. Hover it for the beat-writer note — that is where role risk lives
  ("likely to split carries", "off to the side at practice"). The **risk** tab
  lists every hurt player still available, worst first.
- Late rounds compress toward zero. That is true, not broken: those players
  really are near replacement.

---

## When something breaks

| Symptom | Do this |
|---|---|
| Page frozen, dot is red | The server died. Restart the same command — picks are in SQLite, recovery is under 2s and the page repaints itself. |
| Browser dies entirely | `.venv/bin/python -m gridiron.live.term --league main --slot 3` — same database, same recommendations, continue at the exact pick. |
| Laptop slept | Nothing. The page fetches on wake and repaints. |
| Out of sync with the room | `/j <pick number>` to re-anchor. |
| Red **missing** rows | You recorded a pick out of order. Click each one and fill it — until you do, those players are still counted as available. |
| Everything is wrong | The **reset** button in the footer, or `--reset` on relaunch. Reset is itself undoable. |

**Verified**: server killed mid-draft and restarted with picks, clock and roster
intact; terminal and web driving the same database concurrently; two leagues on
two ports with no cross-contamination.

---

## Do not

- Rebuild the pool mid-draft. `player_pool_latest.csv` is read once at launch.
- Run two servers on the same `--league`. They share a SQLite file and will
  fight over the clock.
- Trust a blind `Enter` on an ambiguous name — the box tells you what it will
  commit. `brown` and `smith` deliberately refuse until you pick with `↓`.

---

# In-season weekly runbook

The draft-day sections below are historical. This is the loop the season actually runs on.
`NOTES.md` is the source of truth for rosters, FAAB, waiver priority and pending moves.

## Monday — post-mortem and damage report

```bash
.venv/bin/python -m gridiron.live.espn --season 2026 --out data/2026   # pool + raw_stats + news + injuries
```

Then: read the box scores for both leagues, record **bench points left behind** (the metric that graded
the Golden and Andrews mistakes), and check every rostered player's injury record. The fetch above
rewrites `news.json` and `injuries.json`; `injuries.weeks_out()` gives return dates, which is how
Achane's season-ending ACL surfaced within minutes of the refresh.

## Tuesday — wire scan and claims

Waivers process **Wednesday** in both leagues, so claims go in Tuesday night.
Pull available players by Week N projection AND by rest-of-season, per position, for both leagues.
Bid sizing: breakout skill players cost $20+; contingent/backup-dependent roles $6–9. We lose every
FAAB tie in 2MinuteDrill (12th of 12 on the rolling list), so never bid a round number.
In First Down, waiver priority #1 is spent only on a starter's permanent replacement.

## Wednesday — claims land, injury pressers

Most coaches give their first real practice report Wednesday. If a claim hinged on someone else's
status, that news usually arrives *after* waivers run — so do not spend a claim on a coin flip.

## Thursday — the Thursday rule

Anyone playing Thursday night locks at kickoff. **Judge him on merit before then. Never hold a
Thursday player as a contingency for a Friday injury decision.** This rule exists because Golden
scored 21–26 on the bench in Week 3 while we waited on a Friday designation.

## Friday — designations

Official game statuses post Friday. Resolve every questionable starter, then set both lineups.

## Sunday — inactives

Inactives post ~90 minutes before each kickoff. Check before the 1pm window, and remember late-window
and Sunday-night players are still swappable after the early games.

## Standing lineup rules

- Do not bench a stable high-floor starter to chase a game stack worth ~0.5 projected points.
- Projections are a mean. Argue from role, target share, snap share and scoring rules.
- Defense is not an optimization we spend on; the Steelers stay.
