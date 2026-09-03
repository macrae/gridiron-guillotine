"""One-line rationale for a recommendation.

Vocabulary adapted from mock_draft.py:432 `_generate_pick_reason`, which is the
one genuinely good piece of the old live module: it is what makes output read as
advice rather than a sorted column. Copied and de-classed rather than imported --
the original pulls in the pandas-importing strategy package, and its Hero-RB
phase lookup is replaced here by a pure function over the round number.

Pure. No I/O, no state.
"""

from __future__ import annotations

from .pool import Player


def draft_phase(round_num: int) -> str:
    """Coarse phase label. Descriptive only -- it never moves a score."""
    if round_num <= 2:
        return "anchor"
    if round_num <= 6:
        return "core"
    if round_num <= 10:
        return "depth"
    return "endgame"


def slot_role(player: Player, counts: dict[str, int], starters: dict[str, int],
              flex_count: int) -> str:
    """Which lineup seat this player would actually occupy.

    The engine already prices this in via _need_multiplier, but silently. Saying
    it out loud is what lets you sanity-check a recommendation in one glance --
    "3rd RB" reads very differently depending on whether the flex is open.
    """
    have = counts.get(player.pos, 0)
    if have < starters.get(player.pos, 0):
        return f"starts {player.pos}{have + 1}"
    if player.pos in ("RB", "WR", "TE"):
        used = sum(max(0, counts.get(q, 0) - starters.get(q, 0))
                   for q in ("RB", "WR", "TE"))
        if used < flex_count:
            return "starts FLEX"
    return "bench"


def pick_reason(
    player: Player,
    vorp: float,
    vona: float,
    survival: float,
    round_num: int,
    pos_remaining: int,
    cliff: float,
    needs: dict[str, int],
    role: str | None = None,
) -> str:
    """Short pipe-joined rationale. Ordered most-decisive first."""
    tags: list[str] = []
    if role:
        tags.append(role)

    # Why he is urgent -- the number that actually drives the pick.
    if survival < 0.15:
        tags.append(f"gone by your next pick ({survival:.0%})")
    elif survival < 0.45:
        tags.append(f"coin-flip to last ({survival:.0%})")
    elif survival > 0.85 and vona < 5:
        tags.append(f"likely still there ({survival:.0%})")

    if cliff >= 25:
        tags.append(f"{player.pos} cliff: -{cliff:.0f} VORP if you wait")
    elif cliff >= 12:
        tags.append(f"{player.pos} thinning")

    # Why he is valuable.
    if vorp >= 100:
        tags.append("elite value")
    elif vorp >= 50:
        tags.append("strong value")
    elif vorp <= 0:
        tags.append("replacement level")

    if pos_remaining <= 5:
        tags.append(f"only {pos_remaining} {player.pos} left")

    if player.is_injured():
        tags.append(player.injury_status.replace("_", " ").lower())

    if not tags:
        tags.append(f"best available {player.pos} ({draft_phase(round_num)})")
    return " · ".join(tags)
