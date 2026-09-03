"""The selector function.

Pure: takes the pool, who has been drafted, my roster, league config, and the
current pick -- returns ranked recommendations. No I/O, no globals, no network.
Because it is a pure function of the pick list, undo is free: drop a pick and
recompute. Nothing incremental to unwind.

Full recompute over ~500 players is ~1-3ms, so it is affordable on every
keystroke.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import snake, vona as vona_mod
from .pool import Player, PlayerPool
from .reasons import pick_reason, slot_role
from .vorp import LeagueConfig, roster_counts, unfilled_mandatory

# Weight on urgency. 0 == pure VORP (best available), 1 == pure VONA.
#
# 0.2, and that number is measured, not chosen. Simulating ~100 paired drafts
# per setting -- identical seed and seat, so draft luck cancels -- and scoring
# the resulting STARTING lineup:
#
#   room type                       l=0.2    l=0.6    l=1.0
#   opponents follow ADP exactly    +15.1    -13.2    -60.5
#   ordinary noise (sigma 8)         +7.2    -20.5    -36.7
#   noise scaled to ADP              -0.7    -28.9    -56.8
#   10-team league                   +0.2     -6.2    -33.3
#   chaotic room (sigma 25)          -4.3    -12.6    -28.7
#
# Two things follow, and the second is the uncomfortable one.
#
# First, the old default of 0.6 was wrong in EVERY room tested, including the
# one where survival is perfectly predictable. It was a guess, and it cost
# 6-29 points of starting lineup.
#
# Second, VONA is worth far less than this codebase originally assumed. Its
# entire value is a bet on predicting who will be gone, and that depends on
# other people's picks -- so it pays well in a chalk room (+15) and costs in a
# chaotic one (-4). 0.2 is chosen for that asymmetry: bounded downside, real
# upside, never the dominant term.
#
# VONA remains the right thing to SHOW. Knowing a player is 8% to survive is
# useful to a human deciding between two names. It is just a poor thing to
# optimise hard against.
DEFAULT_URGENCY = 0.2

# Kickers and defenses are excluded outright until the draft is nearly over.
# One rule, and it prevents the most common catastrophic draft blunder.
LATE_ONLY = ("K", "DST")
LATE_ONLY_WITHIN = 2


@dataclass
class Recommendation:
    player: Player
    vorp: float
    vona: float
    score: float
    survival_at_next: float
    cliff: float
    reason: str


#: Positions that can also fill the FLEX slot. A surplus RB/WR/TE can still
#: enter the starting lineup; a surplus QB/K/DST cannot.
FLEX_ELIGIBLE = ("RB", "WR", "TE")

#: Weight for a player who cannot reach the starting lineup at all. Not zero --
#: a backup covers a bye week and an injury -- but nowhere near a starter.
BENCH_ONLY = 0.25

#: Flex-eligible depth once the flex seat is taken. Higher than BENCH_ONLY
#: because an RB/WR/TE bench piece is the one most likely to be promoted: byes,
#: injuries and in-season breakouts all happen at these positions.
#: Measured -- see _need_multiplier. The starting-lineup curve is flat below
#: 0.55, so this is the least aggressive value that captures the whole gain.
BENCH_DEPTH = 0.55
BENCH_DEEP = 0.35


def _need_multiplier(pos: str, roster: list[Player], league: LeagueConfig) -> float:
    """How much a player at this position is worth given what I already have.

    VORP and VONA have no concept of a bench: both value a player as though he
    starts every week. This is the only place that correction lives.

        1.0          fills an empty starter slot, or an open FLEX seat
        BENCH_DEPTH  flex-eligible depth once the flex seat is taken
        BENCH_DEEP   depth beyond that
        BENCH_ONLY   surplus QB/K/DST -- cannot reach the lineup at all

    BENCH_DEPTH = 0.55 is measured, not guessed: sweeping it across all twelve
    draft slots and scoring the resulting STARTING lineup (bench points never
    score) gains ~5.6 points versus no discount, and the curve is flat below
    0.55 -- discounting harder changes no decisions.

    The BENCH_ONLY tier matters more than it looks. Replacement level is static,
    computed once against the full pool, so by the late rounds every remaining
    player scores below it and VORP goes uniformly negative. At that point a
    backup QB is the only positive number on the board and wins the pick -- even
    though in a one-QB league he can never enter the lineup and is worth roughly
    nothing. Without this tier the engine spends round 9 on a second quarterback.
    """
    counts = roster_counts(roster)
    have = counts.get(pos, 0)
    cap = league.max_at_pos.get(pos, 99)
    starters = league.starters.get(pos, 0)

    if have >= cap:
        return 0.0  # hard cap -- filtered before this is used
    if have < starters:
        return 1.0

    # Starters at this position are covered. Can another one still reach the
    # lineup through FLEX?
    if pos in FLEX_ELIGIBLE:
        # The flex is ONE shared slot, not one per position. Counting it
        # per-position let a 3rd RB, a 3rd WR and a 2nd TE each claim full
        # starter credit for the same seat -- so the engine would spend a middle
        # round on bench depth while a real starting slot sat empty, then fill
        # that slot from scraps twenty picks later.
        flex_used = sum(
            max(0, counts.get(q, 0) - league.starters.get(q, 0)) for q in FLEX_ELIGIBLE
        )
        if flex_used < league.flex_count:
            return 1.0      # a genuinely open flex seat
        return BENCH_DEPTH if have < max(1, cap - 1) else BENCH_DEEP
    return BENCH_ONLY       # QB/K/DST surplus is bench-only


def _apply_need(base: float, mult: float) -> float:
    """Make a score LESS attractive by `mult`, in both directions.

    Not "scale toward zero": for a positive score this is `base * mult`, but for
    a NEGATIVE score it moves further from zero, not closer. That asymmetry is
    the point. Plain multiplication would make a negative score larger (less
    bad) and so promote positions you have already filled -- exactly backwards.
    Late in a draft every score is negative, which is when it matters most.
    """
    return base - (1.0 - mult) * abs(base)


def recommend(
    pool: PlayerPool,
    drafted_ids: set[int],
    my_roster: list[Player],
    league: LeagueConfig,
    current_pick: int,
    top_n: int = 3,
    urgency: float = DEFAULT_URGENCY,
    adp_offset: float = 0.0,
    drafted_order: list[tuple[Player, int]] | None = None,
) -> list[Recommendation]:
    """Rank available players for the pick at `current_pick`.

    `drafted_order` is [(player, overall_pick)] for what has already gone. When
    supplied, the room's own drift from national ADP is measured and folded into
    the survival model: a league that reaches on running backs makes every
    player's ADP optimistic, and uncorrected VONA would then think help is
    closer than it is.
    """
    next_pick = snake.next_pick_after(
        current_pick, league.num_teams, league.my_slot, league.rounds
    )
    left = snake.picks_remaining(
        current_pick, league.num_teams, league.my_slot, league.rounds
    )
    round_num = snake.round_of(current_pick, league.num_teams)
    needs = unfilled_mandatory(my_roster, league)
    counts = roster_counts(my_roster)

    available = pool.available(drafted_ids)
    by_pos: dict[str, list[Player]] = {}
    for p in available:
        by_pos.setdefault(p.pos, []).append(p)
    for lst in by_pos.values():
        lst.sort(key=lambda p: -p.vorp)

    # --- Gating -----------------------------------------------------------
    allowed = set(by_pos)

    # 1. Hard positional caps.
    allowed = {
        pos for pos in allowed if counts.get(pos, 0) < league.max_at_pos.get(pos, 99)
    }

    # 2. K/DST only in the final rounds.
    if left > LATE_ONLY_WITHIN:
        allowed -= set(LATE_ONLY)

    # 3. Endgame guard: if I have exactly as many picks left as unfilled
    #    mandatory slots, every remaining pick must fill one. This is what stops
    #    a draft ending with no kicker.
    if needs and left <= sum(needs.values()):
        forced = set(needs) & allowed
        if forced:
            allowed = forced

    if not allowed:  # every position capped -- fall back to raw value
        allowed = set(by_pos)

    # --- Scoring ----------------------------------------------------------
    # National ADP is a market average, not this room. Measure how far this
    # draft has run ahead of or behind it, and evaluate survival at the shifted
    # position. Returns 0.0 until there is enough signal to be worth trusting.
    drift = vona_mod.adp_drift(drafted_order or [])
    shifted = next_pick - drift + adp_offset if next_pick is not None else None
    baseline: dict[str, float] = {}
    cliffs: dict[str, float] = {}
    for pos in allowed:
        cand = by_pos.get(pos, [])
        baseline[pos] = (
            vona_mod.expected_best_vorp(cand, shifted) if shifted is not None else 0.0
        )
        cliffs[pos] = vona_mod.position_cliff(cand, shifted)

    scored: list[Recommendation] = []
    # sorted(), not the set itself: `score` is rounded to one decimal, so near
    # ties are common, and a stable sort would then break them by whatever order
    # the set happened to iterate. Python randomises string hashing per process,
    # so that would make the board differ between runs on identical input.
    for pos in sorted(allowed):
        cand = by_pos.get(pos, [])
        mult = _need_multiplier(pos, my_roster, league)
        # Only the top few at each position can ever win; scoring the whole tail
        # is wasted work.
        for p in cand[: max(top_n + 5, 10)]:
            others = [q for q in cand if q.player_id != p.player_id]
            e_next = (
                vona_mod.expected_best_vorp(others, shifted)
                if shifted is not None
                else 0.0
            )
            v = p.vorp - e_next if shifted is not None else p.vorp
            base = p.vorp - urgency * e_next
            survival = (
                vona_mod.survival_prob(p.adp, shifted) if shifted is not None else 0.0
            )
            scored.append(
                Recommendation(
                    player=p,
                    vorp=round(p.vorp, 1),
                    vona=round(v, 1),
                    score=round(_apply_need(base, mult), 1),
                    survival_at_next=round(survival, 3),
                    cliff=round(cliffs.get(pos, 0.0), 1),
                    reason="",
                )
            )

    # Total order: score, then raw VORP, then player id. Every component is
    # needed -- score alone ties after rounding, and score+VORP can still tie
    # for genuinely equivalent players.
    scored.sort(key=lambda r: (-r.score, -r.vorp, r.player.player_id))
    top = scored[:top_n]
    for r in top:
        r.reason = pick_reason(
            role=slot_role(r.player, counts, league.starters, league.flex_count),
            player=r.player,
            vorp=r.vorp,
            vona=r.vona,
            survival=r.survival_at_next,
            round_num=round_num,
            pos_remaining=len(by_pos.get(r.player.pos, [])),
            cliff=r.cliff,
            needs=needs,
        )
    return top
