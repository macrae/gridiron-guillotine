# Draft day runbook

One page. Keep it open in a second tab.

---

## T-60 minutes

```bash
cd ~/gridiron-guillotine

# 1. Refresh the board (injuries and ADP move all week)
.venv/bin/python -m gridiron.live.espn

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
- `BYE 13` amber chip = clashes with someone already on your roster.
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
