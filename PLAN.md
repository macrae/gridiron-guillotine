# Gridiron Guillotine 2026 — Agentic Draft Platform

_Plan of record. Generated 2026-08-17 from a five-agent codebase audit + 2026 strategy research._

---

## Context

You draft in **two 12-team full-PPR Yahoo snake leagues in roughly two weeks**. The goal is to turn `gridiron-guillotine` into an agentic draft platform: Pi-harnessed agents for data acquisition, analysis, modeling, scouting and coaching, feeding a **deterministic real-time engine** that surfaces live VORP/VONA recommendations against the actual Yahoo draft room.

A five-agent audit found the current system does not do what its docs claim. This is not cosmetic: the projection pipeline silently produces nothing, the "pre-computed strategy" is a no-op, and the Yahoo integration has never once read a draft board. The **data and valuation layers need a rebuild, not a patch** — which you've approved.

The ideas underneath are sound and align with 2026 market consensus. A focused two-week build delivers a genuinely strong draft-day tool.

**Locked decisions:** full rebuild of data/valuation · both drafts late Aug (~14 days) · Yahoo standard full-PPR roster · rotate credentials, purge history, repo stays public.

---

# Part 1 — Inventory: what exists and what it actually does

## 1.1 Shape of the repo

| Area | Size | Verdict |
|---|---|---|
| `gridiron_guillotine/` | ~40 modules, 11.9k LOC | Core loop runs; data + valuation layers broken |
| `data/` | 541 tracked files, 254 weekly CSVs | Mislabeled by one season; stops at NFL 2024 |
| Root loose scripts | ~25 untracked Yahoo scrapers | Archaeology of 5 failed attempts |
| `deprecated/` | 24 modules | **Contains the scripts that actually generated the shipped data** |
| `tests/` | 5 unit + 11 "integration" | 0 runnable (pytest not installed); 3 of 5 have no assertions |
| Git | 7 commits, 2025-07-28 → 2025-08-01 | +770/−1540 uncommitted on top |

Version drift: `pyproject.toml` 2.1.0 · `README.md` 2.2 · `CLAUDE.md` 2.3.

## 1.2 🔴 SECURITY — do this first

**`nbs/oauth2.json` holds live Yahoo OAuth credentials, committed to a PUBLIC GitHub repo** (`github.com/macrae/gridiron-guillotine`, `isPrivate: false`), in commits `de04674` and `992e186`, public since **2025-07-28**. Populated `consumer_key` (96 chars), `consumer_secret` (40), `access_token` (980), `refresh_token` (65) — no placeholders. `.gitignore` does not exclude it.

Treat the existing secret as compromised.

## 1.3 What genuinely works — keep this

- `live/mock_draft.py` (802 lines) — interactive mock draft, **the only live module with correct API usage**. Its interaction design (top-10 + rationale, search, position/team filters) is worth preserving wholesale.
- `news/` (~1,400 lines) — ESPN's `site.api.espn.com/.../nfl/news` path is real and unauthenticated. Aggregator has sane threading, caching, dedup. (NFL.com and RotoWire sub-sources are guesswork stubs.)
- `api/yahoo.py` `setup_client`/`authenticate` + the `oauth2.json` flow.
- `yahoo_mock_monitor.py:158-185` `_extract_draft_id` — correctly handles 4 Yahoo URL shapes.
- `connect_to_yahoo.py:20-58` — Chrome remote-debugging launch + `localhost:9222/json` verification. **The only architecturally sound browser code in the repo** (needs its `pkill` and `/tmp` removed).
- `core/tiers.py` and `core/strategy.py` phase machinery — conceptually right, miscalibrated.

## 1.4 🔴 The data layer, broken five independent ways

**a) Season labels are off by one.** Commit `8d79f40` renamed every CSV `YYYY` → `YYYY+1`, stashing originals in `data/backup_before_nfl_naming/`. Verified byte-identical: `backup/defense_2024_1.csv == data/defense_2025_1.csv`. Content confirms — `data/offense_2025_1.csv:2` is Baker Mayfield WAS@TB 289/4 = **NFL 2024 Week 1**.

- **File label `YYYY` = NFL season `YYYY−1`.** Newest football on disk is **NFL 2024**.
- `game_count_YYYY` columns use the *true* season. Two conventions, disagreeing, undocumented.
- Everything named "2026" is really 2025. **NFL 2025 was never scraped.** The tool is two seasons stale.

**b) The multi-year weighted projection never runs.** `data/loaders.py:110` builds a join key with a regex yielding `''` for essentially every row of `weighted_projections_2026.csv` (values look like `"Cole KmetC. Kmet"`). **0 of 1177 rows match.** What you believe is a 65/25/10 three-year weighted projection is a raw per-game mean from `deprecated/aggregate_scored_data.py:86`. Had the join worked it would inject a season total into a per-game column — a 16× unit error.

**c) Player identity is a `"Last, First"` string.** No IDs, despite `player_ids.json` holding 1,379. Consequences: the weighted join fails; PPR bonuses match on **last name only** (`strategy.py:361,366` — `"Jones"` hits Zay/Mac/Aaron/Julio); **461 players silently dropped** for missing `pos` (`loaders.py:184`); Marvin Harrison Jr. absent entirely.

**d) Advanced metrics are decorative.** `target_share`, `air_yards_share`, `red_zone_*`, `goal_line_carries`, `air_yards_per_target` are **never populated** — `loaders.py:213-216` zeroes them. WOPR ≡ 0; `expected_points` ≡ `projected_points`. The only live signal is a ±15% multiplier keyed off a hardcoded 2024 city-name list (`config.py:74-83`) that doesn't match the DB's abbreviation-encoded `team` column. The README's "0.746 R²" is decorative.

**e) Units and season length are inconsistent.** Per-game and season totals share columns. Season length is assumed **16** (`weighted_calculator.py:267`), **17** (`loaders.py:313`), 17 weeks scraped (`base.py:82`) — **week 18 never scraped since 2021**, though the NFL has played 18 since 2021.

**Additionally, the raw CSVs are unrepairable at the source:** `offense_*.csv` has **no position and no team column at all** (header is `Player,Game,Pts*,Passing_Att,…`) and `Player` is a mangled concatenation (`Baker MayfieldB. Mayfield`). The 461 dropped rows aren't a filter bug — the source never had position. `weighted_projections_2026.csv` labels Ricky Pearsall a TE, and `_infer_position` produces **381 TE vs 172 WR**. These files are strictly dominated by nflverse, which has the same games correctly labeled with IDs, positions, and 18 weeks.

## 1.5 🔴 The valuation layer

- **VBD implemented five times**: `strategy.calculate_vbd:170` · `processors.VBDCalculator:78` (unused) · `precompute._calculate_vbd:176` (hardcoded absolute baselines QB 21.0 / RB 12.9 / WR 14.8 / TE 9.5) · `_calculate_adjusted_value:196` and `_direct_player_adjustment:281` (both unreachable).
- `replacement_levels` sets **DB/DT/OT to 0** (`config.py:103-106`) — which is why **"A.J. Green (DB)" ranks #2 overall by VBD** in the shipped database.
- **`precompute` is a no-op.** `precompute.py:25` passes a `Config` where `draft_position: int` is expected; `:264-267` calls `get_round_strategy` with kwargs that don't exist → `TypeError` → caught → falls back to raw projection. Verified: **all 12 per-draft-position scores in `enhanced_players.db` are identical.**
- **The strategy never tracks its own roster.** `simulate_pick` (`strategy.py:575-598`) updates `drafted_players` but never `team_rosters`, so `get_my_roster()` always returns `{}`. Roster-need boosts are permanently 1.5, positional caps never fire, the QB ladder always sees zero QBs. **The entire roster-need half of the strategy is inert.**
- Floor/ceiling is a flat ±20% for everyone (`models.py:63-66`). No variance model exists.

## 1.6 🔴 Runtime bugs breaking advertised commands

| Bug | Location | Effect |
|---|---|---|
| `logger` used, never imported | `database.py:552` | `get_top_players` raises `NameError` |
| 6 binds for 5 placeholders | `database.py:578-583` | `gridiron db draft` raises `ProgrammingError`, masked by generic `except` |
| 3 methods **defined twice** | `database.py` 364/392/409 shadowed by 504/556/575 | Later, buggier definitions win |
| `LeagueSettings(league_name=, num_teams=…)` kwargs don't exist | `live/monitor.py:71-85`, `simulator.py:74-79` | `gridiron live` + `DraftSimulator` 100% broken |
| `save_data` signature clash | `scrapers/base.py:52` vs 4 subclasses | `gridiron data update` can't write any file |
| `--ppr` is `is_flag=True, default=True` | `cli/main.py:50` | **PPR can never be turned off**; half-PPR unrepresentable |
| `\\n` in non-raw f-strings | 65× across `cli/*.py` | Users see literal `\n` |
| `game_count_2020` omitted | `loaders.py:228` | 7 veterans (incl. **Frank Gore**) flagged rookies, points ÷17 |

`README.md` documents a Streamlit dashboard and six CLI flags that don't exist; `web/` was deleted in the working tree.

## 1.7 🔴 The Yahoo integration has never read a draft board

The captured `yahoo_debug_page.html` is **Yahoo's sign-in wall** — its only text is *"Please sign in to your Yahoo account to draft."* That one artifact explains every failure.

- The draft room is a client-rendered React SPA (`DraftClientBootstrap`). **Zero `data-testid` attributes.** Class names are CSS-in-JS hashes that change per deploy. The class `_ys_1dbz5fh`, hardcoded in **8 files** as "the players element", **appears nowhere in the captured DOM.** It was guessed.
- **Zero websocket URLs or API endpoints appear in the captured HTML** — the pick feed is established at runtime by the JS bundle. Its shape genuinely cannot be known from anything in the repo; it must be observed live.
- `yahoo_mock_monitor.py` queries ~25 broad selectors including bare `span`/`div`/`li`, then treats **`len(matching_elements)` as the pick count**. "Dedup" is a positional array slice, so any DOM reflow re-emits every pick. Name matching is exact `==` between Yahoo's *"Christian McCaffrey"* and the DB's *"McCaffrey, Christian"* — it could never match even if scraping worked.
- `connect_to_mock_draft` returns `True` and prints "✅ Connected successfully!" from the login page.
- Five approaches tried and abandoned: `requests` → headless Selenium → manual-login-then-ENTER → profile reuse → DevTools bookmarklet.

**How commercial tools actually do it:** FantasyPros Draft Wizard, DraftSharks War Room and DraftKick all ship **browser extensions**. DraftKick's public writeup says extensions read picks from the draft room's **chat log** (primary) with the **Draft Results tab** as fallback — precisely because SPA state is off-DOM.

---

# Part 2 — 2026 strategy research vs. what the code assumes

Your Hero-RB thesis is **directionally right for 2026**. Its calibration is a 2024 snapshot.

**Consensus as of Aug 2026:**
- **RB-heavy market.** Underdog ADP has **12 of the first 18 picks as RBs**. 4for4 BBM VI: RB in Rd 1 → ~24% advance vs ~12% Zero-RB; RB-RB Rds 1-2 → ~30% vs ~8%. **Zero-RB is out of favor.**
- 15 of the top-25 non-QB PPR scorers in 2025 were RBs. Goal-line run rate rose 48.8% (2021) → 51.5% (2025).
- **QB: late-round QB is back** (Rd 8+); Allen alone in tier 1 (~ADP 19). Yahoo's own ADP study finds QBs systematically overpriced.
- **TE: elite or punt** — Bowers/McBride tier 1, Loveland TE3, then wait to Rd 8+.
- **Weak rookie class for redraft** — only Jeremiyah Love (RB, ARI) has a top-24 ADP; 7 rookies in the top-120.
- **The RB dead zone (RB15-25) is undervalued this year** — a real, findable edge.
- Yahoo's *default* is 0.5 PPR but **your leagues are full PPR**, which raises WR and pass-catching-RB value above any half-PPR-sourced ranking.

**What the code gets wrong:** `elite_hero_rbs` lists Kamara, Derrick Henry, Jonathan Taylor. `position_targets` names Amari Cooper, Tony Pollard, Raheem Mostert. `ppr_pass_catchers` still boosts Ekeler and penalizes Nick Chubb. The 2026 board top (Gibbs, Bijan, Chase, Nacua, JSN, CMC, ARSB, J. Taylor) is largely absent or misvalued. **Every hardcoded name list becomes data.**

**Methodology upgrades adopted:** distinct VOLS/VORP/VONA baselines · **pick-EV** from ADP mean *and standard deviation* (highest-leverage addition for snake drafts) · Gaussian-mixture tier clustering · real Gamma-fit quantiles instead of ±20% · offline Monte Carlo for reach charts.

## 2.1 Data sources — verified live this week

| Source | What it gives | Access |
|---|---|---|
| **`nflreadpy`** | 2021-2025 weekly stats, pbp, rosters, depth charts, injuries, snaps | Free, no key. **Requires Python ≥3.10** |
| **`load_ff_playerids()`** | **The identity crosswalk** — gsis/sleeper/**yahoo**/espn/fantasypros/pfr/mfl | Free |
| **`load_ff_rankings("draft")`** | Live FantasyPros ECR **with `sd`** and `yahoo_id`; verified `scrape_date 2026-08-14` | Free |
| **FantasyPros projections** | Full-season **stat lines** (ATT/YDS/TDS/REC/FL), `?week=draft&scoring=PPR` | **No API key needed** |
| **FFCalculator ADP** | `adp, stdev, high, low, times_drafted, bye`; 2026 live: 6,665 drafts, 12-team PPR | Free, daily |
| **`load_ff_opportunity()`** | Prebuilt expected fantasy points from pbp | Free |
| Yahoo `draft_analysis` | `average_pick`, `percent_drafted` — the pool you actually draft against | OAuth, ~1000/hr, optional |

**Correction to earlier research: Sleeper has no documented projections or ADP endpoint.** Do not build on it.

**Why FantasyPros stat lines are decisive:** they give raw stats, not points. You compute FPTS yourself under full PPR — which structurally eliminates the entire "sourced from half-PPR rankings" bug class and makes the model scoring-agnostic for any future league.

---

# Part 3 — Target architecture

## 3.1 The organizing principle

> **Agents are never in the critical path. During a draft, only deterministic numpy code runs.**

Three tiers, by latency budget:

| Tier | When | Latency | Contains | LLM? |
|---|---|---|---|---|
| **0 — Live engine** | During draft | **<100ms p99** | Feed → identity → state → VORP/VONA/tiers/survival → SSE → dashboard | **Never** |
| **1 — Async annotation** | Between picks | 15-20s, hard deadline | News classification, second-opinion notes. Renders as a chip; **never auto-applied**, never blocks | Yes, killable |
| **2 — Pre-draft batch** | Days before | Minutes | Scouting, projection modeling, adjustments, data acquisition | Yes |

This is what satisfies both "agentic platform" and "draft happens fast." **CI test enforces it:** replay a full 180-pick draft with the entire `pi/` tree deleted and assert identical recommendations. If the engine can't run without agents, the architecture is wrong.

## 3.2 Topology

```
┌──────────────── one laptop, one user ─────────────────────────────┐
│  Chrome (dedicated profile, port 9222) ──CDP──┐                   │
│    └ Yahoo draft room (real login)            │                   │
│                                                ▼                  │
│  ┌──────── ggd serve (Python 3.12, uvicorn :8000) ────────────┐   │
│  │ feed/    supervisor + ws│xhr│dom│manual ingest             │   │
│  │ ids/     resolver (yahoo_id → player_uid)                  │   │
│  │ draft/   state + engine (numpy: VORP/VONA/tiers/survival)  │   │
│  │ adjust/  bounded adjustments + newswatch                   │   │
│  │ server/  SSE + REST + dashboard                            │   │
│  └────┬──────────────────────────────▲───────────────────────┘   │
│       │ SSE                          │ HTTP POST (localhost)      │
│       ▼                              │                            │
│  Browser dashboard          ┌────────┴─────────────────┐          │
│  (Jinja shell + vanilla JS) │ Pi supervisor (Node 22.19)│         │
│                             │ extensions/skills/agents  │          │
│                             └──────────────────────────┘          │
└───────────────────────────────────────────────────────────────────┘
```

**Language split.** Python owns everything live — the model core is already Python, and colocating the CDP listener with the engine removes an IPC hop from the latency budget. **There is no draft-day dependency on Node existing.** TypeScript (Pi) owns agents only.

**Pi ↔ Python.** Two mechanisms, split by state vs. compute:

| Need | Mechanism |
|---|---|
| Anything touching live draft state | Pi custom tool → `fetch("http://127.0.0.1:8000/…")`, 3s timeout. Single writer, server-side validation/clamping |
| Batch compute (rebuild, backtest, refresh) | Pi tool → `pi.exec("uv", ["run","ggd",…], {timeout})`, JSON on stdout |

No message bus, no queue, no second database.

## 3.3 Module layout

```
gridiron/                        # new package; `gridiron_guillotine/` deleted at end of Phase 1
  identity/  normalize.py  match.py  aliases.yaml  overrides.yaml
  ingest/    conventions.py  nflverse.py  adp_ffc.py  adp_yahoo.py  proj_fantasypros.py
  model/     scoring.py  games.py  variance.py  project.py  opportunity.py
  value/     vbd.py  dynamic.py  pickev.py  tiers.py  board.py
  draft/     state.py  ingest.py  engine.py  reconcile.py  events.py
  feed/      cdp.py  sniff.py  spec.py  supervisor.py  parsers/{ws,xhr,dom,manual}.py
  adjust/    models.py  rubric.py  apply.py  newswatch.py
  news/      (ported from gridiron_guillotine/news/, re-keyed on player_id)
  server/    app.py  sse.py  routes_*.py  templates/  static/
  cli/       main.py  build.py  serve.py  sniff.py  doctor.py  replay.py  adj.py
leagues/     main.yaml  second.yaml
config/      yahoo_feed.yaml  rubric.yaml
pi/          extensions/  skills/  agents/  jobs/  lib/
data/        raw/{source}/{asof}/*.parquet   gg.duckdb   draft.sqlite    # all gitignored
recordings/  (gitignored)
attic/       (dead root scripts, pending deletion)
```

**Storage split, deliberately:** **DuckDB** (`gg.duckdb`) for the analytical build — reads the raw parquet snapshots natively, so the build is SQL over immutable files with almost no glue. **SQLite** (`draft.sqlite`) for live mutable draft state — row-level upserts with a unique constraint. Live reads touch neither; the engine loads numpy arrays once at startup.

## 3.4 Identity layer — build first, everything joins through it

`nflreadpy.load_ff_playerids()` gives the crosswalk free, **including `yahoo_id`**. That is the single highest-leverage fix in the project: if the Yahoo feed carries `nfl.p.<id>`, name matching is deleted from the live path entirely.

```python
# gridiron/identity/match.py
@dataclass(frozen=True)
class Resolution:
    player_uid: str | None
    confidence: float
    method: Literal["yahoo_id","override","exact","merge","initial","fuzzy","none"]
```

Cascade — each stage runs only if the prior found nothing:
1. **Source ID** (`yahoo_id`/`sleeper_id`/`fantasypros_id`) → 1.0
2. **Override** — `identity/overrides.yaml`, hand-maintained, in git
3. Exact `name_norm` + position → 0.97
4. Last name + first initial + pos + team → 0.93
5. **Blocked fuzzy** — `rapidfuzz.token_set_ratio ≥ 88` within (pos, team) → 0.85; accept only if the **margin over runner-up ≥ 0.05**

That margin requirement is what kills the `"Jones"` collision at `strategy.py:361`. **Never match on last name alone.**

**Below 0.80 confidence, never drop the pick.** Insert as `UNRESOLVED` — it still consumes the slot and advances the board, and renders as a red chip with a one-click resolve dropdown. *A wrong pick count is catastrophic; an unidentified pick is a 3-second annoyance.*

Test fixture (written day 2): Amon-Ra St. Brown · Marvin Harrison Jr. vs Sr. · Brian Thomas Jr. · Kenneth Walker III · D'Andre Swift · Ja'Marr Chase · Deebo Samuel Sr. · Michael Pittman Jr. · DJ Moore vs D.J. Moore · Michael Thomas ×2 · Josh Allen QB/LB · every `Jones` · every DST variant.

## 3.5 Conventions — the anti-off-by-one module

```python
# gridiron/ingest/conventions.py
CURRENT_SEASON: Final = 2026        # season year = year the season STARTS
HISTORY_SEASONS: Final = (2021,2022,2023,2024,2025)
REG_WEEKS: Final = 18               # 18 since 2021 — the 17-week assumption IS the bug

def assert_season_frame(df, expect): ...   # max(week)==18; n_games ∈ [270,274]; anchors hold
def assert_units(df): ...                  # bans bare 'points'; _ppg median ∈[0,30]; _season ∈[0,450]
```

**`tests/fixtures/season_anchors.yaml`** — hardcoded verified facts per season (2024 Saquon Barkley rush_yards == 2005; 2023 CMC total TDs == 21). **This is the single test that would have caught the off-by-one**, and it fails on the first build if labels ever shift again.

**Naming rule, enforced by test: no column may be named `projected_points`.** Every points column carries `_ppg`, `_season`, or `_wk`, and `abs(proj_ppg * proj_games − proj_pts_season) < 1e-6` is asserted.

## 3.6 Projection model — hybrid, anchored on consensus

**FantasyPros season stat lines as the anchor, rescored under your own `ScoringRules`**; your own games-played model; your own variance model producing real quantiles. Opportunity model built last, used only as a bounded adjustment and a disagreement detector.

Rationale: with two weeks, an opportunity model that beats consensus is a multi-month project you cannot validate. In a 12-team home league the edge isn't the point estimate — it's replacement level done right, pick-EV against ADP, tiers, and live dynamic VORP. All four are currently absent or broken. **Spend the week there.**

```python
@dataclass(frozen=True)
class PlayerProjection:
    player_uid: str
    proj_pts_season: float   # mean, YOUR scoring
    proj_games: float        # expected games played
    proj_ppg: float
    ppg_sd: float
    p15_season: float        # FLOOR: exceeded 85% of the time (4for4 convention)
    p50_season: float
    p85_season: float        # CEILING: exceeded 15% of the time
    p_pos_top5: float
    source_blend: dict[str, float]
```

1. `score_stat_line(stats, rules) -> float` — **one pure function, the only place points are ever computed**, used for weekly history *and* projections.
2. **Anchor:** FP stat line → `anchor_pts_season`.
3. **Games:** `E[G] = 17 × p_avail`, `p_avail` from a Beta-Binomial (3-yr games-played rate shrunk toward position mean, k≈1.5 seasons), adjusted by current injury designation and age curve.
4. **Variance:** per-game sd from 3 seasons of weekly nflverse stats **scored under your rules**, shrunk to a position+role prior (k = 12 games).
5. **Distribution:** fit a **Gamma**, not Normal — season totals are right-skewed and bounded at 0. Compound games risk: `Var(total) = E[G]·sd_g² + Var(G)·ppg²`. `p15/p50/p85` become actual quantiles, replacing `models.py:63-66`.
6. **Opportunity model (cuttable):** ridge on next-season PPG from `load_ff_opportunity` features, trained 2021→22 … 2024→25. Applied as `clip(own/anchor, 0.92, 1.08)`; **raw disagreement is logged and surfaced** — divergence >1.5sd from consensus is genuinely actionable at the table.
7. **K and DST:** take FP wholesale. But **assert ≥32 DST and ≥32 K rows exist** — that's the fix for "0 DEF in the pool while strategy forces DEF in round 14."

## 3.7 League config as data

`leagues/main.yaml` and `leagues/second.yaml`, both in git:

```yaml
name: "Main 12-team full PPR"
teams: 12
rounds: 15
draft_type: snake
my_slot: null            # fill when known
platform: yahoo
roster: {QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DST: 1, BN: 6, IR: 1,
         flex_eligible: [RB, WR, TE]}
scoring:
  reception: 1.0         # FULL PPR — an explicit float, never a boolean
  rec_yd: 0.1
  rec_td: 6.0
  rush_yd: 0.1
  rush_td: 6.0
  pass_yd: 0.04
  pass_td: 4.0
  interception: -1.0
  fumble_lost: -2.0
  two_pt: 2.0
```

Pydantic v2 models. **No `ppr: bool` anywhere, no `Config.default_*`.** `--league PATH` is required with no default; overrides via `--set scoring.reception=0.5`, never a flag. A `float` field in YAML has no unsettable state — that kills the `--ppr is_flag default=True` bug class at the type level.

## 3.8 Valuation — one VBD, derived from settings

```python
def starter_demand(ls) -> dict[str, float]        # teams × slots, FLEX split RB .40 / WR .50 / TE .10
def replacement_index(ls, method, board=None) -> dict[str, int]
def compute_vbd(proj, ls, method="VORP", drafted=frozenset()) -> pl.DataFrame
```

For your Yahoo-standard 12-team (QB/2RB/2WR/TE/FLEX/K/DST), VOLS baselines land at roughly **QB12 · RB29 · WR30 · TE13 · K12 · DST12**. Baselines are **derived from `LeagueSettings`, never hardcoded**, and positions hard-filter to `{QB,RB,WR,TE,K,DST}` before valuation — DB/DT/OT cannot enter, which is exactly what let "A.J. Green (DB)" rank #2.

This one function replaces all five current implementations.

**Dynamic VORP + pick-EV** (`value/dynamic.py`, `pickev.py`):

```python
class Board:                       # numpy, loaded once, sorted desc within position
    pts, pos_idx, adp, adp_sd, tier, taken: np.ndarray
    def mark_taken(uid) / undo() / recompute(my_pick, my_next_pick) -> DataFrame

def p_available(adp, adp_sd, pick, n_taken_ahead)   # 1 − Φ((pick_eff − adp)/sd), sd floored at 3.0
def value_over_next_available(board, pos, my_next_pick)
def cost_of_waiting(board, my_pick, my_next_pick)   # vbd − E[vbd of best remaining at my next turn]
```

Recommendations rank on `vbd + λ · cost_of_waiting`, λ≈0.5, exposed in league YAML. Baselines recompute by taking the k-th *remaining* element per position via cumulative counts on the `taken` mask — O(N), **~3-5ms measured for a full recompute**, 20× under budget.

**VONA and survival must not Monte-Carlo in the hot path.** Precompute ADP availability curves pre-draft; at runtime apply a vectorized update from observed picks plus a positional-run detector (4 of last 6 picks were RB → shift RB curves left). Real MC runs offline for reach charts.

**VONA, not raw VORP, drives the recommendation ranking.** VORP tells you who's good; VONA tells you who you *lose* by waiting — that's the actual snake-draft decision.

## 3.9 Tiers

`sklearn.mixture.GaussianMixture` on projected points (2-D with `ppg_sd`), k by BIC over 2..10, components ordered by mean, `tier_confidence` = posterior probability. Boris Chen's method applied to points rather than ECR — better, because points are the units the valuation lives in; seed initial means from ECR ordering. Fit at build time; live only needs `players_remaining_in_tier`, a masked count.

Deletes `tiers.py:59-66` hand-tuned thresholds. **Urgency survives as a read-only display signal, never as a value multiplier.**

---

# Part 4 — The live draft loop

## 4.1 Chrome / CDP attach

A separate `--user-data-dir` gives a separate Chrome instance that **coexists with your main browser**. Never `pkill` (which `connect_to_yahoo.py:24` does), never `/tmp` (which gets swept and takes the Yahoo login with it).

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir=$HOME/.gg/chrome-draft-profile \
  --no-first-run --no-default-browser-check \
  --disable-background-timer-throttling \
  --disable-backgrounding-occluded-windows --disable-renderer-backgrounding
```

The `--disable-*background*` flags matter: tab away mid-draft and Chrome throttles timers, slowing the draft client's own polling.

**No anti-detection hacks.** Attaching to a real Chrome with a real profile, real GPU and a real login already looks human; injecting `navigator.webdriver` overrides makes you *more* fingerprintable. The rule that keeps you safe is behavioral: **observe only, never drive the page.**

Verification ladder — each a distinct dashboard state, never a boolean: port up → draft tab found → draft client mounted → **feed live**.

## 4.2 Network interception (primary)

**Observe, never intercept.** Use CDP `Network`, not `Fetch`. `Fetch.requestPaused` requires resuming every request — a bug or slow handler stalls the draft client and costs you a pick. There's no upside; you only need to read.

- `Network.webSocketFrameReceived` — payload arrives **inline**, zero extra round-trip. The fast path.
- `Network.responseReceived` + `getResponseBody(requestId)` — one ~2-5ms local round-trip. Acceptable.
- `Network.loadingFailed` / `webSocketClosed` → immediate health demotion signal.

Handlers parse into a `RawPick` and push to an `asyncio.Queue`; all engine work happens on the consumer side.

## 4.3 Feed discovery — a scheduled task, not a formality

The pick feed's shape **cannot be known from anything in the repo** (zero endpoints appear in the captured HTML). It must be observed live, so it gets real tooling, and its output is **data, not code**.

**`ggd sniff record`** — attach, `Network.enable`, record every event to JSONL with headers redacted. Join a Yahoo mock (`/f1/mock_lobby`), run ≥4 rounds. Autodrafting bots are ideal: picks every few seconds is exactly the stress case. Press a hotkey at 5+ visible picks to write wall-clock anchors into the same file.

**`ggd sniff analyze --emit config/yahoo_feed.yaml`** — scores each stream on temporal correlation with anchors, player-name density, monotone-ascending integer fields (that's `overall_pick`), and ID shape (`nfl.p.\d+` — the thing you actually want). Emits a spec the runtime parser is driven by:

```yaml
transport: ws
url_pattern: "wss://.*\\.yahoo\\.com/.*"
picks_path: "payload.picks"
fields: {overall: pick_num, round: round, team_key: team_key,
         yahoo_player_id: player_key, observed_name: player.name.full}
verified_against: recordings/mock_20260821_1400.jsonl
```

**Why this shape matters:** after a Yahoo deploy you re-run `sniff` and regenerate YAML — no code change, no redeploy. A skill documents the procedure so it can be redone under time pressure on draft morning.

Two outcomes to plan for: if the feed carries `nfl.p.<id>`, this entire risk class evaporates. If it's protobuf/opaque, you fall to L2 — **and you know that on day 5, not day 14.**

**`ggd sniff record` and `ggd replay` are built as a matched pair.** Every rehearsal replays offline through the whole pipeline, so every bug found becomes a regression test at zero extra cost. Best-value tooling in the plan.

## 4.4 Fallback ladder — one interface, four implementations

| L | Source | Latency | Notes |
|---|---|---|---|
| 0 | `WsFeed` | ~10ms | Spec-driven. Preferred. |
| 1 | `XhrFeed` | ~50ms | Same engine, `transport: xhr` |
| 2 | `DomText` | 300-800ms | `Runtime.evaluate` → `innerText`. **Text anchors only, never CSS classes** — regex `Round\s+(\d+)`, `Pick\s+(\d+)`, and chat/log lines. Immune to `_ys_*` hash churn |
| 3 | `Manual` | human speed | **Always running, always accepting** |

**OCR is cut.** ~2 days to build a mode slower and less accurate than a human typing three characters. `Page.captureScreenshot` stays as a *debug artifact* written on every degradation event. Spend those two days making manual entry excellent.

**Supervisor.** An independent 3s heartbeat reads only the current-pick indicator text — this is the **truth oracle**, running regardless of active mode. If the active source produces no pick for 2.5× the observed median interval *while the oracle shows the counter advancing* → demote, log, flash the badge. **Promotion is manual only** (auto-promotion risks flapping between disagreeing sources).

The dashboard shows a persistent badge — **● WS** / **● XHR** / **● DOM** / **● MANUAL** / **● BLIND**. It is never absent and never silently wrong. On BLIND, manual input auto-focuses.

## 4.5 Idempotent dedup and reconciliation

Replaces the positional-slice logic (`yahoo_mock_monitor.py:442-476, 573-585`) with database-enforced identity:

```sql
CREATE TABLE picks (
  draft_id TEXT, overall INTEGER, round INTEGER, slot INTEGER, team_key TEXT,
  player_uid TEXT, observed_name TEXT, source TEXT, confidence REAL,
  observed_at REAL, state_version INTEGER,
  PRIMARY KEY (draft_id, overall));
CREATE UNIQUE INDEX picks_player ON picks(draft_id, player_uid) WHERE player_uid IS NOT NULL;
```

Ingest is `INSERT … ON CONFLICT(draft_id, overall) DO UPDATE … WHERE excluded.confidence > picks.confidence`. **An SSE event fires only when a row actually changed.** Re-feeding the same board 100× is a no-op — that property is what makes L2 (which re-reads the whole DOM every poll) safe to use at all.

Conflict trust order: `human > ws > xhr > dom > manual-typeahead`.

**Reconciliation:** every 10s and after every mode change, `snapshot()` the best source, diff, apply missing rows, log `recon: +N applied, M conflicts`. Self-healing is what lets you sleep through a 20-second websocket blip.

## 4.6 Manual entry — the floor, built day 3

Not an afterthought. Built **third, before any CDP work**, so from day 3 onward you *have* a system that works on draft day.

- Input focused by default; global keydown refocuses it.
- Type-ahead over available players ranked by value, matching prefix of last name, first name, and initials (`arsb` → Amon-Ra St. Brown). Client-side over ~600 rows, sub-millisecond.
- `Enter` assigns the top match to **the team currently on the clock** (the engine knows the snake order). Two keystrokes: `bij` `Enter`.
- `↓`/`Tab` for other matches · `Cmd+Z` undo · `Space` = "a pick happened, I don't know who" → inserts `UNKNOWN`, still advances the clock.
- **Acceptance test: 180 picks in under 6 minutes of typing.** Timed with a stopwatch on day 3.

## 4.7 Latency budget

| Stage | Budget |
|---|---|
| CDP frame → `RawPick` | 5ms |
| resolve + upsert + dedup | 5ms |
| engine recompute (VORP/VONA/tiers/survival) | 30ms |
| SSE diff serialize + push | 10ms |
| browser DOM patch | 20ms |
| **total** | **70ms p50; CI asserts p99 < 100ms** |

Preallocated numpy arrays, positions as int codes, **no pandas in the hot path**, `np.argpartition` for baselines, erf approximation over `scipy.stats.norm.sf`.

---

# Part 5 — Pi agent harness

## 5.1 Opinion: 80% of what reads as "agents" should be deterministic code

An agent is justified only where input is unstructured language and output is a judgment. Everything else is a tool.

| Your ask | Verdict | Form |
|---|---|---|
| data acquisition | tool + skill | `ggd ingest <source>` does the work; skill says which command and how to validate |
| data analyst | skill + `gg_query` | Model writes SQL against a read-only view. It does not write pandas |
| data scientist | subagent, **pre-draft only** | `projection-modeler.md`, opus, thinking=high. Frozen at D9 |
| front-end developer | subagent, **pre-draft only** | `dashboard-dev.md`. Frozen at D9 |
| browser agent | **not an agent** | `ggd sniff` is deterministic. **No LLM touches a browser during a draft** |
| preseason | cron/batch | `ggd preseason refresh` nightly + interpretation skill |
| scout | subagent + skill | `player-scout.md` emits *structured* notes to the adjustment schema |
| coaching / recommendation | hybrid | Deterministic engine ranks. Optional 15s LLM second opinion may **annotate only, never reorder** |
| real-time VORP | **pure code, no LLM ever** | Non-negotiable |

## 5.2 Layout

```
pi/
  package.json          # "@earendil-works/pi-coding-agent": "0.84.2"  — exact, no caret
  package-lock.json     # committed
  extensions/ gg-tools.ts  gg-guardrails.ts
  skills/     draft-data-acquisition/  fantasy-data-analyst/  scouting-note/
              news-impact-adjustment/  yahoo-draft-feed-discovery/  draft-day-runbook/
  agents/     projection-modeler.md  player-scout.md  dashboard-dev.md
  lib/        run_agent.ts  schemas.ts
  jobs/       pre_draft_scout.ts  news_watch_classify.ts  second_opinion.ts
```

Tools: `gg_query(sql, limit)` (read-only view, 5s statement timeout) · `gg_player(ref)` · `gg_board(top_n, position)` · `gg_annotate(...)` · `gg_run(cmd, args, timeout_ms)` (whitelisted `ggd` subcommands only) · `gg_submit(payload)` (structured output, `terminate: true`).

**The clamp lives on the server, not in the prompt.** A model told "cap at ±8%" will eventually propose 40%. `/annotations` clamps, stores both requested and applied deltas, and **the dashboard shows when a proposal was clamped** — itself a useful signal the agent is off the rails.

Skill descriptions are written as **trigger conditions, not summaries** — under progressive disclosure only the `description` sits in the system prompt, so that string is what makes the model reach for the right skill under pressure.

**Guardrails extension:** `tool_call` blocks `git push|rm -rf|pip install|ggd model` during the draft window · `before_agent_start` injects compact live state so agents don't burn a call orienting · `agent_end` accumulates cost/cache into a ledger shown on the dashboard.

## 5.3 Qualitative → quantitative bridge

Adjustments are a table with mandatory provenance (`sources` JSON with URL + outlet + published_at, `rationale`, `author`, `status`, `expires_at`), storing both `delta_pct` and `applied_delta_pct`.

**Magnitude rubric** (`config/rubric.yaml`, enforced in code, documented in the skill):

| Signal | Bound |
|---|---|
| Out for season / IR | `availability` → 0 (a flag, **not** a percentage) |
| Confirmed multi-week injury | `availability` = (17−games_missed)/17 |
| Practice-report soft signal | −5% |
| Confirmed role change (named starter, lead back) | +8% … +15% |
| Beat-reporter buzz, single source | ±3% |
| Multi-source consensus (≥3 outlets) | ±6% |
| Industry/influencer divergence vs. your model | ±4% |
| Qualitative scouting note | ±5% |

**Two hard invariants in code:**
1. **Per-player stacking cap ±20%.**
2. **Per-position mean-zero normalization.** After stacking, subtract the position's mean adjustment. Otherwise every optimistic camp report inflates all WRs — which silently moves the replacement baseline and corrupts VORP for the entire position. *This is the failure mode people don't anticipate.*

Injury routes through `availability` rather than `delta_pct` deliberately: it's multiplicative on expected games, interacts differently with floor/ceiling, and shouldn't be capped at 20%.

**Approval:** anything `|delta| > 5%` stays `proposed` until you click Approve. Under 5% auto-activates. `ggd adj diff` shows what changed since the last snapshot, so a nightly batch can't quietly rewrite your board overnight.

**Breaking news during a draft — two tiers, and the fast one has no LLM:**
- **Tier 1, deterministic `newswatch`:** polls RSS/JSON every 60s, matches headlines against **still-available top-150 players only** (that filter is what keeps it fast and relevant), pushes an annotation SSE with raw headline + outlet + timestamp. **Latency: seconds.**
- **Tier 2, optional LLM garnish:** one-shot `pi -p --mode json`, **20s deadline**, classifies against the rubric. Returns in time → the chip gains a suggested delta and an Apply button. Times out → you still have the headline, which is 90% of the value.

**Non-negotiable: agent-proposed deltas are never auto-applied during a live draft.** They render as chips; a human clicks. This structurally eliminates "the agent hallucinated and I drafted the wrong guy."

## 5.4 Determinism policy

Every agent call goes through one wrapper, `pi/lib/run_agent.ts`:

1. **Structured output or failure.** Terminate via `gg_submit`; free-text output is discarded, not parsed.
2. **Fresh context** (`--no-session`) for all scheduled tasks.
3. **Two-stage timeout.** `AbortController` at `budgetMs` **plus** a hard `setTimeout` at `budgetMs + 2000` that SIGKILLs. Pi's custom tools get an `AbortSignal` but **no automatic timeout** — an abort that a hung HTTP call ignores needs the kill.
4. **Retries: 0 during a draft.** Pre-draft: 1 at half budget.
5. **Timeout never raises into the live path** — returns `{status:"timeout"}`, UI shows "engine only."
6. **Live window uses subprocess** (`pi -p --mode json --no-session --thinking low`), not the SDK: SIGKILL is a guarantee, in-process abort is a request. Pre-draft uses the SDK for `steer()`/`fork()`.

**Kill switch:** `POST /control/agents {enabled:false}` → grey **AGENTS OFF** pill; supervisor polls every 2s and aborts in flight. Plus `GG_NO_AGENTS=1` and a `pkill -f pi-coding-agent` line printed on the runbook card.

**Draft-day freeze at T-48h.** Tag `draft-day`. Pi is pre-1.0 with weekly breaking releases — pin `0.84.2` exactly, commit the lockfile, don't touch it after D9.

---

# Part 6 — Build order (Aug 17 → Aug 31)

## The minimum viable draft-day path

**ID spine → pick ingestion → manual entry → engine → dashboard.** No CDP, no Pi, no agents, no news. **Done by D6.** If everything else fails you type picks and still have the best board in your league.

| Day | Work | Deliverable / gate |
|---|---|---|
| **D0** Aug 17 | 🔴 Rotate Yahoo creds. `git rm --cached nbs/oauth2.json`, `.gitignore`, history purge + force-push. `uv` + Python 3.12; Node → 22.19+. Move ~20 root scripts to `attic/`. Deletion commit. | Repo clean, secret dead |
| **D1** | `gridiron/` skeleton. `ggd serve`: `/state`, `/events` SSE, static page. Dedicated Chrome profile + manual Yahoo login. `--draft-id`/`--port` from the start | Page updates when you `curl` a fake pick |
| **D2** | **Identity spine** from `load_ff_playerids()` + resolver + nasty-name fixture. `conventions.py` + `season_anchors.yaml`. `picks` table + idempotent ingest. **Freeze the `projections` view interface** | Replay 180 fake picks in <2s, zero dupes |
| **D3** | **Manual entry end-to-end** — type-ahead, keyboard, undo, on-clock inference | **180 picks typed in <6 min, timed** |
| **D4-D5** | `ggd sniff record` + `analyze` + `replay`. Record 2-3 real Yahoo mocks. Emit `yahoo_feed.yaml` + spec-driven parser | A working L0/L1 feed **or a documented "it's opaque" verdict** |
| **D6** | Ingest (nflverse/FP/FFC) → DuckDB → `gg build`. Scoring, games, variance, Gamma quantiles. VBD/dynamic/pick-EV/tiers on numpy | `gg build --offline` reproducible; p99 recompute <60ms |
| **D7** | **Dress rehearsal 1** — real Yahoo mock, network mode, full logging | Latency histogram + breakage list |
| **D8** | Fix D7. L2 DOM-text + supervisor + degradation badges | Demotion works and is visible |
| **D9** | Pi: pin 0.84.2, both extensions, 6 skills, 3 subagent defs. Pre-draft batch. **Freeze Pi** | Scouting notes + adjustments in the DB |
| **D10** | Qual→quant bridge, rubric enforcement, approval UI, `newswatch`. Both league YAMLs | `ggd adj list --active` reads sensibly |
| **D11** | **Dress rehearsal 2** — full stack, both leagues, agents on | Clean end-to-end run |
| **D12** | **Chaos day** — kill the websocket mid-draft, kill Chrome, drop wifi, flip agents off, force manual | Every fault degrades visibly and recovers |
| **D13** | Freeze. Print the one-page runbook card. Final data refresh. Offline Monte Carlo reach chart | Tag `draft-day` |
| **D14** | Buffer | — |

**Cut order if behind:** opportunity model → Monte Carlo → news re-key → LLM second opinion → **Yahoo live feed** (fall back to typing, which is 2 seconds a pick and fully reliable).

## What gets deleted

| Path | Why |
|---|---|
| `data/scrapers/` (all 5) | `save_data` signature clash; footballdb superseded by nflverse |
| `data/{loaders,weighted_calculator,processors,precompute,validators,database}.py` | Every one has a verified defect |
| `core/{config,metrics,tiers,strategy}.py` | Hardcoded name lists, fabricated metrics, unfalsifiable multiplier stack |
| All 254 weekly CSVs + `scored_data*.csv` + `weighted_projections_2026.csv` + `rookie_rankings_*.csv` + `players_[A-Z].csv` + `player_ids.json` | Mislabeled seasons, **no position/team columns at source**, fabricated players |
| `data/backup_before_nfl_naming/`, `data/enhanced_players.db` | Byte-identical duplicate; DB unreproducible |
| ~20 root scripts, 3 `.js`, 4 how-to `.md`, `yahoo_debug_screenshot.png` (4.5MB) | Selenium duplicates of one disproven job |
| `deprecated/`, `tests/integration/` | Dead code; "integration tests" are demo scripts with no assertions |

**Salvaged before deletion:** `connect_to_yahoo.py:20-58` (minus `pkill`, minus `/tmp`) · `yahoo_mock_monitor.py:158-185` · `news/` (re-keyed on `player_uid`) · `api/yahoo.py` auth · `mock_draft.py` interaction UX · `cli/main.py` click-group shape.

## Two leagues

Yahoo blocks one account in two draft rooms simultaneously. **Confirm both draft times immediately.** If they overlap: two Chrome profiles (9222/9223), two engine instances (8000/8001), keyed by `draft_id`. `--draft-id`/`--port` land on **D1** so this is free rather than a D13 emergency.

---

# Part 7 — Verification

**Build gates** (`gg build` exits non-zero on failure):
1. **Season anchors** — golden facts per season. *The one test that catches the off-by-one.*
2. **Week coverage** — `max(week) == 18` for every season ≥2021; `n_games ∈ [270,274]`.
3. **Units** — no bare `points` column exists; `_ppg` medians ∈[0,30]; `_season` ∈[0,450]; `proj_ppg × proj_games == proj_pts_season`.
4. **Identity** — ≥99.5% of FFC top-200 and ≥98% of FP projections resolved; 100% DST; the nasty-name fixture.
5. **Scoring** — property test: `score(reception=1.0) − score(reception=0.5) == 0.5 × receptions`. Golden: our PPR total reproduces FP's published FPTS for the top-20 RBs within 0.5.
6. **VBD monotonicity** — within position, Spearman(proj, vbd) == 1.0 exactly; `vbd == 0` at baseline rank; positions ⊆ `{QB,RB,WR,TE,K,DST}`.
7. **Dynamic VORP** — over a simulated full draft, each player's VBD is monotone non-decreasing as players ahead come off the board.
8. **Reproducibility** — `gg build --offline` twice → identical per-table sha256; DB row count == loader row count (*the 728-vs-716 bug*).
9. **Coverage floors** — ≥32 DST, ≥32 K, ≥250 RB/WR rows.

**Live gates:**
10. **Perf** — p99 of `mark_taken(); recompute()` over a 180-pick replay **< 100ms** (expect ~4ms).
11. **Agent independence** — replay a full draft with `pi/` deleted; recommendations must be byte-identical.
12. **Idempotency** — replay the same recording 100× → zero duplicate picks, zero spurious SSE events.
13. **Manual-entry speed** — 180 picks in <6 minutes, timed by hand.

**End-to-end:** `ggd doctor` preflight (creds valid, Chrome attached, feed spec matches, DB fresh, both league configs load) · two full dress rehearsals against real Yahoo mock drafts · one chaos day where every failure mode is induced deliberately.

---

# Part 8 — Risks

| # | Risk | Likelihood | Mitigation | Known by |
|---|---|---|---|---|
| 1 | **Burn 10 days on CDP and have nothing on draft day** | **The real one** | Manual path complete **D3**, before any CDP work. Every later day is pure upside | **D3** |
| 2 | Pick feed is opaque (protobuf/encrypted/absent) | Moderate | L2 DOM-text + manual, both already built | D5 |
| 3 | Yahoo front-end deploy between rehearsal and draft | Moderate | Feed spec is YAML data — re-run `sniff` draft morning. L2 uses text anchors, not `_ys_*` classes | draft morning |
| 4 | Data rebuild lands late / schema churns | High | **Freeze the `projections` view on D2**; back it with the existing DB until the rebuild lands. Never blocked | D2 |
| 5 | Python 3.9 blocks `nflreadpy` | **Confirmed** | `uv` + Python 3.12 (no standalone 3.10+ exists on this machine; only conda `py310`/`py314`) | D0 |
| 6 | Node 22.18.0 < Pi's 22.19 requirement | **Confirmed** | nvm install 22.19+ | D0 |
| 7 | CDP attach fails day-of (Chrome auto-update, port busy) | Low-moderate | `ggd doctor` at T-60min; manual mode needs no browser at all | T-60min |
| 8 | Pi pre-1.0 breaking change | Moderate | Exact pin, committed lockfile, no upgrades after D9. Agents non-critical by construction | D9 |
| 9 | Name resolution picks the wrong player | Low with `yahoo_id` | Confidence thresholds + margin rule; `UNRESOLVED` chips; never silently guess below 0.80 | D2 |
| 10 | Agent proposes a wild adjustment | Moderate | Server-side clamp + per-position normalization + approval above ±5% + never auto-apply live | D10 |
| 11 | FantasyPros HTML layout changes | Moderate | Snapshot raw HTML, parser test against saved fixture, fall back to `load_ff_rankings` ECR + isotonic ECR→points map | continuous |

---

# Open items (non-blocking)

- **Both draft dates and times** — needed now; determines whether the two-instance path is required.
- **Your draft slot in each league** — for the offline reach chart and `my_slot`. Fine to fill in on draft day.
- **Both Yahoo league keys** — lets `ggd` pull exact settings and Yahoo-specific ADP rather than assuming.
