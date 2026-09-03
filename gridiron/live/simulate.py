"""Draft simulation, for measuring whether the engine is actually any good.

The metric is projected points of the best legal STARTING lineup. Bench points
never score, so a strategy that hoards depth must not be rewarded for it.

Opponents are ADP-followers with noise and a soft positional need, which is a
fair model of both Yahoo's autodraft bots and a room of ordinary humans. The
noise is what makes repeated runs informative: without it every draft is
identical and one run per seat tells you everything.

Nothing here is imported by the live path.
"""

from __future__ import annotations

import random
import statistics
from dataclasses import dataclass

from . import snake
from .pool import Player, PlayerPool
from .recommend import DEFAULT_URGENCY, recommend
from .vorp import LeagueConfig, roster_counts

FLEX_ELIGIBLE = ("RB", "WR", "TE")


# ----------------------------------------------------------------- scoring

def starting_points(roster: list[Player], cfg: LeagueConfig) -> float:
    """Points from the best legal starting lineup. Bench contributes zero."""
    by: dict[str, list[Player]] = {}
    for p in roster:
        by.setdefault(p.pos, []).append(p)
    for lst in by.values():
        lst.sort(key=lambda p: -p.proj_points)

    used: list[Player] = []
    total = 0.0
    for pos, n in cfg.starters.items():
        take = by.get(pos, [])[:n]
        total += sum(p.proj_points for p in take)
        used.extend(take)
    rest = sorted((p for p in roster if p not in used and p.pos in FLEX_ELIGIBLE),
                  key=lambda p: -p.proj_points)
    return total + sum(p.proj_points for p in rest[:cfg.flex_count])


def unfilled_starters(roster: list[Player], cfg: LeagueConfig) -> int:
    """How many starting seats this roster cannot fill. A strategy that leaves
    holes is broken regardless of how many points it accumulated."""
    counts = roster_counts(roster)
    missing = sum(max(0, n - counts.get(pos, 0)) for pos, n in cfg.starters.items())
    surplus = sum(max(0, counts.get(q, 0) - cfg.starters.get(q, 0))
                  for q in FLEX_ELIGIBLE)
    return missing + max(0, cfg.flex_count - surplus)


# --------------------------------------------------------------- drafters

@dataclass
class Ctx:
    pool: PlayerPool
    drafted: set[int]
    roster: list[Player]
    cfg: LeagueConfig
    overall: int
    order: list[tuple[Player, int]]
    rng: random.Random


def _available(ctx: Ctx) -> list[Player]:
    return ctx.pool.available(ctx.drafted)


def _needs_position(ctx: Ctx, p: Player) -> bool:
    """Would this player fill a starting seat?"""
    counts = roster_counts(ctx.roster)
    if counts.get(p.pos, 0) < ctx.cfg.starters.get(p.pos, 0):
        return True
    if p.pos in FLEX_ELIGIBLE:
        used = sum(max(0, counts.get(q, 0) - ctx.cfg.starters.get(q, 0))
                   for q in FLEX_ELIGIBLE)
        return used < ctx.cfg.flex_count
    return False


def adp_bot(noise: float = 8.0):
    """ADP order, jittered, with a soft pull toward unfilled starting seats and
    a hard block on drafting K/DST early or a second QB. This is roughly how a
    Yahoo autodraft bot and an average human both behave."""
    def pick(ctx: Ctx) -> Player | None:
        avail = [p for p in _available(ctx) if p.adp > 0]
        if not avail:
            return None
        left = snake.picks_remaining(ctx.overall, ctx.cfg.num_teams,
                                     snake.slot_on_clock(ctx.overall, ctx.cfg.num_teams),
                                     ctx.cfg.rounds)
        counts = roster_counts(ctx.roster)
        best, best_key = None, None
        for p in avail:
            if p.pos in ("K", "DST") and left > 2:
                continue
            if counts.get(p.pos, 0) >= ctx.cfg.max_at_pos.get(p.pos, 99):
                continue
            key = p.adp + ctx.rng.gauss(0.0, noise)
            if _needs_position(ctx, p):
                key -= 6.0                     # mild need bias
            if best_key is None or key < best_key:
                best, best_key = p, key
        return best or avail[0]
    return pick


def engine(urgency: float = DEFAULT_URGENCY, use_drift: bool = True):
    """The real thing."""
    def pick(ctx: Ctx) -> Player | None:
        recs = recommend(ctx.pool, ctx.drafted, ctx.roster, ctx.cfg, ctx.overall,
                         top_n=1, urgency=urgency,
                         drafted_order=ctx.order if use_drift else None)
        return recs[0].player if recs else None
    return pick


def best_vorp():
    """Pure best-player-available by VORP, with the same roster gating. This is
    the honest control: it isolates what VONA adds, since everything else is
    shared with the engine."""
    return engine(urgency=0.0)


def best_projection():
    """Highest raw projection, ignoring replacement level entirely -- what a
    magazine top-200 list gives you."""
    def pick(ctx: Ctx) -> Player | None:
        counts = roster_counts(ctx.roster)
        left = snake.picks_remaining(ctx.overall, ctx.cfg.num_teams,
                                     snake.slot_on_clock(ctx.overall, ctx.cfg.num_teams),
                                     ctx.cfg.rounds)
        cand = [p for p in _available(ctx)
                if counts.get(p.pos, 0) < ctx.cfg.max_at_pos.get(p.pos, 99)
                and not (p.pos in ("K", "DST") and left > 2)]
        return max(cand, key=lambda p: p.proj_points) if cand else None
    return pick


def adp_follower():
    """Draft strictly by ADP -- the 'just take who the site says' strategy."""
    return adp_bot(noise=0.0)


# ------------------------------------------------------------------ engine

def run_draft(strategies: dict[int, object], cfg: LeagueConfig, pool: PlayerPool,
              seed: int) -> dict[int, list[Player]]:
    """One full draft. `strategies` maps slot -> drafter; missing slots get a bot."""
    rng = random.Random(seed)
    default = adp_bot()
    rosters: dict[int, list[Player]] = {s: [] for s in range(1, cfg.num_teams + 1)}
    drafted: set[int] = set()
    order: list[tuple[Player, int]] = []

    for overall in range(1, cfg.num_teams * cfg.rounds + 1):
        slot = snake.slot_on_clock(overall, cfg.num_teams)
        seat_cfg = LeagueConfig(
            num_teams=cfg.num_teams, rounds=cfg.rounds, my_slot=slot,
            starters=dict(cfg.starters), flex_count=cfg.flex_count,
            max_at_pos=dict(cfg.max_at_pos))
        ctx = Ctx(pool, drafted, rosters[slot], seat_cfg, overall, order, rng)
        pick = (strategies.get(slot) or default)(ctx)
        if pick is None:
            break
        rosters[slot].append(pick)
        drafted.add(pick.player_id)
        order.append((pick, overall))
    return rosters


def head_to_head(cfg: LeagueConfig, pool: PlayerPool, contenders: dict[str, object],
                 seeds: range) -> dict:
    """Every contender drafts from every seat, against bots, across seeds.

    Rotating seats matters: draft position is worth more than any strategy, so
    comparing two strategies at fixed different seats would measure the seat.
    """
    results: dict[str, list[float]] = {k: [] for k in contenders}
    holes: dict[str, int] = {k: 0 for k in contenders}
    for name, strat in contenders.items():
        for seed in seeds:
            for slot in range(1, cfg.num_teams + 1):
                rosters = run_draft({slot: strat}, cfg, pool, seed * 100 + slot)
                seat_cfg = LeagueConfig(
                    num_teams=cfg.num_teams, rounds=cfg.rounds, my_slot=slot,
                    starters=dict(cfg.starters), flex_count=cfg.flex_count,
                    max_at_pos=dict(cfg.max_at_pos))
                results[name].append(starting_points(rosters[slot], seat_cfg))
                holes[name] += unfilled_starters(rosters[slot], seat_cfg)
    return {
        name: {
            "mean": statistics.mean(v),
            "stdev": statistics.pstdev(v),
            "min": min(v),
            "max": max(v),
            "n": len(v),
            "unfilled_seats": holes[name],
        }
        for name, v in results.items()
    }


def one_room(cfg: LeagueConfig, pool: PlayerPool, assignment: dict[int, tuple[str, object]],
             seed: int) -> list[tuple[str, int, float]]:
    """All strategies in the SAME draft, competing for the same players."""
    rosters = run_draft({s: fn for s, (_, fn) in assignment.items()}, cfg, pool, seed)
    out = []
    for slot, (name, _) in assignment.items():
        seat_cfg = LeagueConfig(
            num_teams=cfg.num_teams, rounds=cfg.rounds, my_slot=slot,
            starters=dict(cfg.starters), flex_count=cfg.flex_count,
            max_at_pos=dict(cfg.max_at_pos))
        out.append((name, slot, starting_points(rosters[slot], seat_cfg)))
    return out
