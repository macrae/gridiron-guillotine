"""Snake draft pick arithmetic. Pure, no dependencies.

Implement pick *numbers* and let the gaps fall out, rather than coding the gap
formulas directly -- fewer places to get an off-by-one, and the resulting gaps
self-check against the known identities:

    odd round  -> even round gap = 2(N - p) + 1
    even round -> odd round gap  = 2p - 1

For N=12, p=3: picks 3, 22, 27, 46, 51 ... waits 19, 5, 19, 5.

The existing implementation at yahoo_mock_monitor.py:878 computes
`user_pick_in_round - current_pick_in_round` within a single round, which goes
NEGATIVE once your slot has passed. That value is the sole input to VONA, so the
sign error would silently invert the urgency signal. Fixed here by computing
against the full pick list.
"""

from __future__ import annotations


def overall_of(round_num: int, slot: int, num_teams: int) -> int:
    """Overall pick number (1-indexed) for `slot` in `round_num`."""
    if round_num < 1 or slot < 1 or slot > num_teams:
        raise ValueError(f"bad round={round_num} slot={slot} teams={num_teams}")
    offset = slot if round_num % 2 == 1 else num_teams - slot + 1
    return (round_num - 1) * num_teams + offset


def round_of(overall: int, num_teams: int) -> int:
    """Round containing `overall` (1-indexed)."""
    return (overall - 1) // num_teams + 1


def slot_on_clock(overall: int, num_teams: int) -> int:
    """Which team slot owns `overall`. Reverses on even rounds."""
    rnd = round_of(overall, num_teams)
    idx = (overall - 1) % num_teams + 1
    return idx if rnd % 2 == 1 else num_teams - idx + 1


def my_pick_numbers(num_teams: int, slot: int, rounds: int) -> list[int]:
    """Every overall pick number belonging to `slot`."""
    return [overall_of(r, slot, num_teams) for r in range(1, rounds + 1)]


def next_pick_at_or_after(
    overall: int, num_teams: int, slot: int, rounds: int
) -> int | None:
    """My next pick at or after `overall`. None once my picks are exhausted."""
    for p in my_pick_numbers(num_teams, slot, rounds):
        if p >= overall:
            return p
    return None


def next_pick_after(overall: int, num_teams: int, slot: int, rounds: int) -> int | None:
    """My next pick strictly after `overall`. None if that was my last."""
    for p in my_pick_numbers(num_teams, slot, rounds):
        if p > overall:
            return p
    return None


def picks_until_next_turn(
    overall: int, num_teams: int, slot: int, rounds: int
) -> int | None:
    """How many picks elapse before my next turn. 0 means I am on the clock.

    Never negative -- that is the bug in the original implementation.
    """
    nxt = next_pick_at_or_after(overall, num_teams, slot, rounds)
    if nxt is None:
        return None
    return nxt - overall


def picks_remaining(overall: int, num_teams: int, slot: int, rounds: int) -> int:
    """How many picks I still have, counting one at `overall` if it is mine."""
    return sum(1 for p in my_pick_numbers(num_teams, slot, rounds) if p >= overall)


def label(overall: int, num_teams: int) -> str:
    """'2.07 (#19)' -- the round.pick form people actually speak."""
    rnd = round_of(overall, num_teams)
    in_round = (overall - 1) % num_teams + 1
    return f"{rnd}.{in_round:02d} (#{overall})"
