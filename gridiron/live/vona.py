"""VONA -- Value Over Next Available.

VORP asks "how much better is this player than a replacement starter?" It is
static: the same number whether you pick next or in an hour.

VONA asks "how much value at this position evaporates if I don't take him now?"
That depends entirely on how many picks elapse before your next turn, which in a
snake draft alternates between long and short. For slot 3 of 12 the waits go
19, 5, 19, 5 -- the 19 is where the cliff bites.

VONA is the number that makes this tool better than a printed cheat sheet, and
it is the reason ADP is a hard requirement: rank tells you who is good, ADP tells
you who will still be there.
"""

from __future__ import annotations

import math

from .pool import Player

# Beyond ~25 candidates the survival product has decayed to nothing.
CANDIDATE_DEPTH = 25


def survival_prob(
    adp: float, pick_number: int, sigma_floor: float = 3.0, sigma_frac: float = 0.15
) -> float:
    """P(a player with this ADP is still on the board at `pick_number`).

    Logistic rather than a hard ADP cutoff, so there is no cliff artifact.

    - adp == pick_number  -> exactly 0.50. A coin flip at your next turn.
    - adp >> pick_number  -> ~1.0 (nobody takes him before you).
    - adp << pick_number  -> ~0.0 (long gone).

    sigma scales with ADP: an ADP-5 player gets sigma=3 because the market is
    near-certain about him, while an ADP-150 player gets sigma=22.5 because the
    late rounds are chaos. One max() buys the right shape across the whole board.
    """
    if adp <= 0:  # no ADP signal: assume undrafted filler, always available
        return 1.0
    sigma = max(sigma_floor, sigma_frac * adp)
    # Clamp the exponent so a huge gap cannot overflow.
    z = max(-60.0, min(60.0, (pick_number - adp) / sigma))
    return 1.0 / (1.0 + math.exp(z))


def expected_best_vorp(
    candidates: list[Player], next_pick: int, depth: int = CANDIDATE_DEPTH
) -> float:
    """E[VORP of the best survivor at `next_pick`] over position-sorted candidates.

    Exact under independence -- walk down by value, accumulating
    value x P(available) x P(nobody better survived).
    """
    ev = 0.0
    none_better = 1.0
    for p in sorted(candidates, key=lambda x: -x.vorp)[:depth]:
        s = survival_prob(p.adp, next_pick)
        ev += p.vorp * s * none_better
        none_better *= 1.0 - s
        if none_better < 1e-6:
            break
    return ev


def vona(
    player: Player, same_position: list[Player], next_pick: int | None
) -> float:
    """VORP lost by waiting on this position until `next_pick`.

    `same_position` must be the AVAILABLE players at the position, including
    `player` (excluded here). If `next_pick` is None this is the last pick and
    there is nothing to wait for, so VONA collapses to VORP.
    """
    if next_pick is None:
        return player.vorp
    others = [p for p in same_position if p.player_id != player.player_id]
    return player.vorp - expected_best_vorp(others, next_pick)


def position_cliff(
    candidates: list[Player], next_pick: int | None, top_n: int = 8
) -> float:
    """Expected VORP drop at this position between now and the next turn.

    A read-only urgency signal for display. It must never multiply a player's
    value -- the previous codebase's habit of folding scarcity into the score is
    what made its rankings unfalsifiable.
    """
    if not candidates or next_pick is None:
        return 0.0
    ranked = sorted(candidates, key=lambda p: -p.vorp)[:top_n]
    return max(0.0, ranked[0].vorp - expected_best_vorp(ranked, next_pick))


def adp_drift(drafted: list[tuple[Player, int]]) -> float:
    """Median (actual pick - ADP) so far. Positive means the room is reaching.

    Applied as an offset to ADP when evaluating survival, this catches a league
    that drafts RBs earlier than the national market. Returns 0.0 until there is
    enough signal to be worth trusting.
    """
    deltas = sorted(actual - p.adp for p, actual in drafted if p.adp > 0)
    if len(deltas) < 8:
        return 0.0
    mid = len(deltas) // 2
    if len(deltas) % 2:
        return deltas[mid]
    return (deltas[mid - 1] + deltas[mid]) / 2.0
