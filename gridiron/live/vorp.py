"""Replacement levels and VORP.

Replacement level is DERIVED from league roster shape, never hardcoded. The
previous codebase had five VBD implementations sharing one disqualifying defect:
a `0` replacement level for non-fantasy positions, which in every case made
DB/DT/OT *maximally* advantaged rather than excluded -- the actual mechanism
behind "A.J. Green (DB) ranks #2 overall". Here the position filter runs before
valuation, in pool.load_pool(), so that bug is not expressible.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .pool import Player, PlayerPool

FLEX_ELIGIBLE = ("RB", "WR", "TE")


@dataclass
class LeagueConfig:
    """Everything the engine needs about a league. Yahoo-hydrated or hand-typed."""

    num_teams: int = 12
    rounds: int = 15
    my_slot: int = 1
    # Dedicated starter slots per position.
    starters: dict[str, int] = field(
        default_factory=lambda: {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
    )
    flex_count: int = 1
    # Hard roster caps -- a position at cap is dropped from candidates entirely.
    #
    # QB is capped at 1 deliberately: in a one-QB league a backup can never enter
    # the lineup, and a hard cap makes drafting one structurally impossible
    # rather than merely unlikely. TE stays at 2 because a second TE is genuinely
    # startable -- it fills the FLEX slot.
    #
    # Raise QB for a superflex or 2-QB league; the bench-only weighting in
    # recommend._need_multiplier then takes over from the hard cap.
    max_at_pos: dict[str, int] = field(
        default_factory=lambda: {"QB": 1, "RB": 6, "WR": 7, "TE": 2, "K": 1, "DST": 1}
    )

    @property
    def total_picks(self) -> int:
        return self.num_teams * self.rounds

    def mandatory_slots(self) -> dict[str, int]:
        """Starter slots that must be filled, flex counted separately."""
        return dict(self.starters)


def flex_shares(pool: PlayerPool, league: LeagueConfig) -> dict[str, float]:
    """Infer how flex slots split across RB/WR/TE from the data itself.

    Take the top N x (dedicated RB/WR/TE starters + flex) players across those
    positions by projection. Whatever each position contributes *beyond* its
    dedicated starters is what flex absorbs. Self-calibrating -- no magic
    constants, and it tracks the actual shape of this season's pool.
    """
    if league.flex_count <= 0:
        return {p: 0.0 for p in FLEX_ELIGIBLE}

    dedicated = {p: league.num_teams * league.starters.get(p, 0) for p in FLEX_ELIGIBLE}
    n_flex = league.num_teams * league.flex_count
    take = sum(dedicated.values()) + n_flex

    candidates = [p for p in pool.players if p.pos in FLEX_ELIGIBLE and p.draftable]
    candidates.sort(key=lambda p: -p.proj_points)
    top = candidates[:take]

    excess = {}
    for pos in FLEX_ELIGIBLE:
        observed = sum(1 for p in top if p.pos == pos)
        excess[pos] = max(0, observed - dedicated[pos])

    total = sum(excess.values())
    if total <= 0:  # degenerate; fall back to an even split
        return {p: 1.0 / len(FLEX_ELIGIBLE) for p in FLEX_ELIGIBLE}
    return {pos: excess[pos] / total for pos in FLEX_ELIGIBLE}


def replacement_ranks(pool: PlayerPool, league: LeagueConfig) -> dict[str, int]:
    """Positional rank at which a player becomes replacement-level."""
    shares = flex_shares(pool, league)
    ranks: dict[str, int] = {}
    for pos, n_start in league.starters.items():
        share = shares.get(pos, 0.0)
        ranks[pos] = max(1, round(league.num_teams * (n_start + share * league.flex_count)))
    return ranks


def replacement_levels(pool: PlayerPool, league: LeagueConfig) -> dict[str, float]:
    """Projected points of a replacement-level starter, per position.

    Smoothed over ranks R, R+1, R+2 so a single anomalous player cannot move the
    baseline for a whole position.
    """
    ranks = replacement_ranks(pool, league)
    levels: dict[str, float] = {}
    for pos, r in ranks.items():
        ranked = sorted(
            (p for p in pool.players if p.pos == pos and p.draftable),
            key=lambda p: -p.proj_points,
        )
        if not ranked:
            levels[pos] = 0.0
            continue
        window = ranked[r - 1 : r + 2] or ranked[-1:]
        levels[pos] = sum(p.proj_points for p in window) / len(window)
    return levels


def compute_vorp(pool: PlayerPool, league: LeagueConfig) -> dict[str, float]:
    """Attach VORP to every player in `pool` (in place). Returns the baselines used."""
    levels = replacement_levels(pool, league)
    pool.players = [
        replace(p, vorp=round(p.proj_points - levels.get(p.pos, 0.0), 2))
        for p in pool.players
    ]
    pool.reindex()
    return levels


def roster_counts(roster: list[Player]) -> dict[str, int]:
    counts = {pos: 0 for pos in ("QB", "RB", "WR", "TE", "K", "DST")}
    for p in roster:
        counts[p.pos] = counts.get(p.pos, 0) + 1
    return counts


def unfilled_mandatory(roster: list[Player], league: LeagueConfig) -> dict[str, int]:
    """Starter slots still empty, ignoring flex."""
    counts = roster_counts(roster)
    return {
        pos: max(0, need - counts.get(pos, 0))
        for pos, need in league.mandatory_slots().items()
        if max(0, need - counts.get(pos, 0)) > 0
    }
