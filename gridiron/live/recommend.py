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
from .reasons import pick_reason
from .vorp import LeagueConfig, roster_counts, unfilled_mandatory

# Default weight on urgency. 0 == pure VORP (best available), 1 == pure VONA.
# 0.6 keeps raw value in charge while letting scarcity break ties: pure VONA
# will happily hand you a mediocre TE over an elite WR purely because the TE
# cliff is nearer.
DEFAULT_URGENCY = 0.6

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


def _need_multiplier(pos: str, roster: list[Player], league: LeagueConfig) -> float:
    """How much a player at this position is worth given what I already have.

    1.0 fills an empty starter slot · 0.85 useful depth · BENCH_ONLY otherwise.

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

    # Starters are covered. Can another one still reach the lineup?
    if pos in FLEX_ELIGIBLE:
        flex_room = starters + league.flex_count
        if have < flex_room:
            return 1.0      # still fills the flex slot
        return 0.85 if have < max(1, cap - 1) else 0.60
    return BENCH_ONLY       # QB/K/DST surplus is bench-only


def _apply_need(base: float, mult: float) -> float:
    """Scale a score toward zero by `mult`, correct for negative scores too.

    Plain multiplication would make a negative score *larger* (less bad), which
    would promote positions you have already filled.
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
) -> list[Recommendation]:
    """Rank available players for the pick at `current_pick`."""
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
    shifted = next_pick + adp_offset if next_pick is not None else None
    baseline: dict[str, float] = {}
    cliffs: dict[str, float] = {}
    for pos in allowed:
        cand = by_pos.get(pos, [])
        baseline[pos] = (
            vona_mod.expected_best_vorp(cand, shifted) if shifted is not None else 0.0
        )
        cliffs[pos] = vona_mod.position_cliff(cand, shifted)

    scored: list[Recommendation] = []
    for pos in allowed:
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

    scored.sort(key=lambda r: -r.score)
    top = scored[:top_n]
    for r in top:
        r.reason = pick_reason(
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
