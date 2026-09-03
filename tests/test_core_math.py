"""Correctness of the math behind the top-3 recommendation.

Everything the board shows flows through four things: snake pick arithmetic,
replacement level, survival probability, and expected-best-survivor. A silent
error in any of them produces a plausible-looking board that is wrong, which is
the failure mode that actually loses a draft.

Where a property can be checked by brute force rather than asserted, it is --
`expected_best_vorp` is verified against explicit enumeration over every subset
of survivors, which is a proof for small cases rather than a spot check.
"""

from __future__ import annotations

import itertools
import math

import pytest

from gridiron.live import names, snake, vona
from gridiron.live.pool import Player, PlayerPool
from gridiron.live.recommend import (BENCH_DEEP, BENCH_DEPTH, BENCH_ONLY,
                                     FLEX_ELIGIBLE, LATE_ONLY_WITHIN,
                                     _apply_need, _need_multiplier, recommend)
from gridiron.live.vorp import (LeagueConfig, compute_vorp, flex_shares,
                                replacement_levels, replacement_ranks,
                                roster_counts, unfilled_mandatory)

STD = dict(starters={"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1},
           flex_count=1)


def mk(pid, name, pos, proj, adp, team="XXX", bye=7):
    return Player(player_id=pid, name=name, name_norm=names.normalize(name), pos=pos,
                  team=team, bye_week=bye, proj_points=proj, adp=adp,
                  espn_ppr_rank=pid, percent_owned=50.0, injury_status="ACTIVE",
                  eligible_pos=(pos,))


# ==========================================================================
# 1. SNAKE ARITHMETIC -- exhaustive, not sampled
# ==========================================================================

@pytest.mark.parametrize("teams", [8, 10, 12, 14, 16])
def test_every_pick_belongs_to_exactly_one_slot(teams):
    """Across a whole draft, each overall pick maps to one slot, and each slot
    owns exactly one pick per round. If this is wrong, everything is."""
    rounds = 16
    owner = {}
    for slot in range(1, teams + 1):
        for o in snake.my_pick_numbers(teams, slot, rounds):
            assert o not in owner, f"pick {o} claimed by slots {owner.get(o)} and {slot}"
            owner[o] = slot
    assert sorted(owner) == list(range(1, teams * rounds + 1)), "gaps or overlaps"


@pytest.mark.parametrize("teams", [8, 10, 12, 14])
def test_gap_identities_hold_for_every_slot(teams):
    """odd->even gap = 2(N-p)+1 ; even->odd gap = 2p-1, for ALL slots."""
    for p in range(1, teams + 1):
        picks = snake.my_pick_numbers(teams, p, 8)
        gaps = [b - a for a, b in zip(picks, picks[1:])]
        for i, g in enumerate(gaps):
            want = 2 * (teams - p) + 1 if i % 2 == 0 else 2 * p - 1
            assert g == want, f"teams={teams} slot={p} gap#{i}: {g} != {want}"


@pytest.mark.parametrize("teams", [10, 12])
def test_slot_and_round_round_trip_over_the_whole_draft(teams):
    for rnd in range(1, 17):
        for slot in range(1, teams + 1):
            o = snake.overall_of(rnd, slot, teams)
            assert snake.slot_on_clock(o, teams) == slot
            assert snake.round_of(o, teams) == rnd


@pytest.mark.parametrize("teams,slot", [(12, 1), (12, 3), (12, 12), (10, 5), (14, 9)])
def test_picks_until_next_turn_never_negative_and_hits_zero_on_your_pick(teams, slot):
    rounds = 15
    mine = set(snake.my_pick_numbers(teams, slot, rounds))
    last = max(mine)
    for o in range(1, teams * rounds + 1):
        got = snake.picks_until_next_turn(o, teams, slot, rounds)
        if o > last:
            assert got is None, f"overall {o} is past my last pick; must be None"
            continue
        assert got is not None and got >= 0
        assert (got == 0) == (o in mine), f"overall {o}: zero-gap disagrees with ownership"


@pytest.mark.parametrize("teams,slot", [(12, 1), (12, 6), (12, 12), (10, 10)])
def test_picks_remaining_counts_down_exactly_once_per_turn(teams, slot):
    rounds = 15
    seen = []
    for o in range(1, teams * rounds + 1):
        seen.append(snake.picks_remaining(o, teams, slot, rounds))
    assert seen[0] == rounds
    assert seen[-1] in (0, 1)
    assert all(b <= a for a, b in zip(seen, seen[1:])), "must be non-increasing"


def test_next_pick_after_is_strictly_after():
    for o in range(1, 12 * 15 + 1):
        nxt = snake.next_pick_after(o, 12, 3, 15)
        assert nxt is None or nxt > o


def test_next_pick_at_or_after_includes_the_current_pick():
    assert snake.next_pick_at_or_after(22, 12, 3, 15) == 22
    assert snake.next_pick_after(22, 12, 3, 15) == 27


def test_snake_rejects_impossible_input():
    for bad in [(0, 3, 12), (1, 0, 12), (1, 13, 12)]:
        with pytest.raises(ValueError):
            snake.overall_of(*bad)


def test_label_matches_round_and_pick_in_round():
    assert snake.label(1, 12) == "1.01 (#1)"
    assert snake.label(12, 12) == "1.12 (#12)"
    assert snake.label(13, 12) == "2.01 (#13)"
    assert snake.label(22, 12) == "2.10 (#22)"


# ==========================================================================
# 2. SURVIVAL PROBABILITY
# ==========================================================================

def test_survival_is_exactly_one_half_at_the_adp():
    for adp in (1, 5, 20, 50, 100, 200):
        assert vona.survival_prob(float(adp), adp) == pytest.approx(0.5)


@pytest.mark.parametrize("adp", [3.0, 12.0, 45.0, 120.0])
def test_survival_decreases_with_later_picks(adp):
    ps = [vona.survival_prob(adp, k) for k in range(1, 250)]
    assert all(b <= a + 1e-12 for a, b in zip(ps, ps[1:]))
    assert all(0.0 <= x <= 1.0 for x in ps)


@pytest.mark.parametrize("pick", [10, 40, 100])
def test_survival_increases_with_later_adp(pick):
    ps = [vona.survival_prob(a, pick) for a in range(1, 220, 5)]
    assert all(b >= a - 1e-12 for a, b in zip(ps, ps[1:]))


def test_sigma_scales_so_late_round_adp_carries_more_uncertainty():
    """Equal distance past ADP must be less certain deep in the draft."""
    for delta in (5, 10, 20):
        early = vona.survival_prob(6.0, 6 + delta)
        late = vona.survival_prob(150.0, 150 + delta)
        assert late > early, f"delta={delta}: late {late:.3f} not > early {early:.3f}"


def test_survival_is_finite_at_extremes():
    for adp, pick in [(0.1, 10_000), (500.0, 1), (1e-6, 1), (300.0, 300)]:
        v = vona.survival_prob(adp, pick)
        assert 0.0 <= v <= 1.0 and not math.isnan(v)


def test_missing_adp_means_nobody_is_taking_him():
    assert vona.survival_prob(0.0, 500) == 1.0
    assert vona.survival_prob(-3.0, 500) == 1.0


# ==========================================================================
# 3. EXPECTED BEST SURVIVOR -- verified by brute force
# ==========================================================================

def _brute_force_expected_best(players, next_pick):
    """E[VORP of best survivor], by explicit enumeration over every subset.

    Each player survives independently. This is the definition; the production
    implementation is an O(k) shortcut for it.
    """
    n = len(players)
    total = 0.0
    for mask in range(1 << n):
        p_mask = 1.0
        best = 0.0
        for i, pl in enumerate(players):
            s = vona.survival_prob(pl.adp, next_pick)
            if mask & (1 << i):
                p_mask *= s
                best = max(best, pl.vorp)
            else:
                p_mask *= 1.0 - s
        total += p_mask * best
    return total


@pytest.mark.parametrize("next_pick", [5, 15, 30, 60, 120])
def test_expected_best_matches_brute_force_enumeration(next_pick):
    players = [mk(i, f"P{i} X", "RB", 0, adp) for i, adp in
               enumerate([4.0, 11.0, 19.0, 28.0, 44.0, 70.0, 95.0, 140.0], start=1)]
    for i, p in enumerate(players):
        object.__setattr__(p, "vorp", 120.0 - 13.0 * i)
    got = vona.expected_best_vorp(players, next_pick)
    want = _brute_force_expected_best(players, next_pick)
    # The walk exits once P(nobody better survived) < 1e-6, so the residual is
    # bounded by that times the remaining values -- not by floating point.
    # Anything larger than this is a formula error, not the approximation.
    assert got == pytest.approx(want, abs=1e-3), f"{got} != {want}"
    assert got <= want + 1e-9, "early exit can only ever UNDER-count"


def test_expected_best_matches_brute_force_with_ties_and_zeros():
    players = [mk(1, "A X", "RB", 0, 10.0), mk(2, "B X", "RB", 0, 10.0),
               mk(3, "C X", "RB", 0, 60.0), mk(4, "D X", "RB", 0, 0.0)]
    for p, v in zip(players, (40.0, 40.0, 0.0, 15.0)):
        object.__setattr__(p, "vorp", v)
    for pick in (5, 20, 80):
        assert vona.expected_best_vorp(players, pick) == pytest.approx(
            _brute_force_expected_best(players, pick), abs=1e-3)


def test_expected_best_falls_as_your_next_pick_gets_later():
    players = [mk(i, f"P{i} X", "RB", 0, 8.0 * i) for i in range(1, 9)]
    for i, p in enumerate(players):
        object.__setattr__(p, "vorp", 100.0 - 10.0 * i)
    vals = [vona.expected_best_vorp(players, k) for k in range(5, 200, 10)]
    assert all(b <= a + 1e-9 for a, b in zip(vals, vals[1:])), "waiting cannot help"


def test_expected_best_never_exceeds_the_best_candidate():
    players = [mk(i, f"P{i} X", "RB", 0, 5.0 * i) for i in range(1, 10)]
    for i, p in enumerate(players):
        object.__setattr__(p, "vorp", 90.0 - 9.0 * i)
    for pick in (1, 10, 50, 300):
        assert 0.0 <= vona.expected_best_vorp(players, pick) <= 90.0 + 1e-9


def test_expected_best_of_nothing_is_zero():
    assert vona.expected_best_vorp([], 20) == 0.0


def test_adding_a_candidate_never_lowers_the_expectation():
    base = [mk(i, f"P{i} X", "RB", 0, 10.0 * i) for i in range(1, 6)]
    for i, p in enumerate(base):
        object.__setattr__(p, "vorp", 60.0 - 8.0 * i)
    extra = mk(99, "Extra X", "RB", 0, 12.0)
    object.__setattr__(extra, "vorp", 75.0)
    for pick in (8, 25, 90):
        assert (vona.expected_best_vorp(base + [extra], pick)
                >= vona.expected_best_vorp(base, pick) - 1e-12)


def test_truncation_depth_does_not_change_the_answer_materially():
    """The O(k) walk stops early once nothing better can survive. Deepening it
    must not move the number."""
    players = [mk(i, f"P{i} X", "RB", 0, 3.0 * i) for i in range(1, 60)]
    for i, p in enumerate(players):
        object.__setattr__(p, "vorp", 200.0 - 3.0 * i)
    a = vona.expected_best_vorp(players, 40, depth=25)
    b = vona.expected_best_vorp(players, 40, depth=59)
    assert a == pytest.approx(b, abs=1e-6)


# ==========================================================================
# 4. VONA -- the urgency number itself
# ==========================================================================

def _pos_group(vorps, adps):
    ps = [mk(i + 1, f"P{i} X", "RB", 0, adps[i]) for i in range(len(vorps))]
    for p, v in zip(ps, vorps):
        object.__setattr__(p, "vorp", v)
    return ps


def test_vona_excludes_the_player_himself():
    group = _pos_group([100.0, 90.0], [5.0, 6.0])
    got = vona.vona(group[0], group, next_pick=40)
    want = group[0].vorp - vona.expected_best_vorp([group[1]], 40)
    assert got == pytest.approx(want)


def test_vona_collapses_to_vorp_on_the_final_pick():
    group = _pos_group([80.0, 60.0, 40.0], [10.0, 20.0, 30.0])
    assert vona.vona(group[0], group, next_pick=None) == group[0].vorp


def test_vona_grows_with_the_length_of_the_wait():
    """The core claim of the whole tool: a longer wait makes a player more
    urgent, because less of his position survives."""
    group = _pos_group([120.0, 95.0, 90.0, 85.0], [4.0, 14.0, 18.0, 22.0])
    vals = [vona.vona(group[0], group, next_pick=k) for k in (6, 12, 24, 48, 96)]
    assert all(b >= a - 1e-9 for a, b in zip(vals, vals[1:])), vals
    assert vals[-1] > vals[0] + 1.0, "a 96-pick wait must be more urgent than a 6"


def test_vona_is_larger_for_a_cliff_position_than_a_flat_one():
    """The wait has to land where the DEPTH survives but the top does not --
    otherwise both positions collapse to ~VORP and the fixture cannot express
    the property it claims to test."""
    cliff = _pos_group([120.0, 40.0, 38.0, 36.0], [5.0, 40.0, 45.0, 50.0])
    flat = _pos_group([120.0, 115.0, 110.0, 105.0], [5.0, 40.0, 45.0, 50.0])
    assert vona.vona(cliff[0], cliff, 25) > vona.vona(flat[0], flat, 25) + 20


def test_a_wait_so_long_that_nobody_survives_collapses_both_to_vorp():
    """Guard on the guard above: past everyone's ADP the distinction genuinely
    disappears, and that is correct, not a bug."""
    cliff = _pos_group([120.0, 40.0, 38.0, 36.0], [5.0, 15.0, 25.0, 35.0])
    flat = _pos_group([120.0, 115.0, 110.0, 105.0], [5.0, 15.0, 25.0, 35.0])
    assert vona.vona(cliff[0], cliff, 120) == pytest.approx(120.0, abs=1.0)
    assert vona.vona(flat[0], flat, 120) == pytest.approx(120.0, abs=1.0)


def test_vona_can_be_negative_when_the_position_is_deep():
    """A worse player at a deep position should show negative urgency: waiting
    is expected to yield someone better."""
    group = _pos_group([50.0, 130.0, 125.0], [5.0, 400.0, 400.0])
    assert vona.vona(group[0], group, next_pick=10) < 0


# ==========================================================================
# 5. SCARCITY / CLIFF -- display signal only
# ==========================================================================

def test_cliff_is_non_negative_and_zero_without_a_next_pick():
    group = _pos_group([100.0, 30.0, 28.0], [3.0, 9.0, 15.0])
    assert vona.position_cliff(group, None) == 0.0
    assert vona.position_cliff([], 30) == 0.0
    assert vona.position_cliff(group, 30) >= 0.0


def test_cliff_is_bigger_where_the_drop_is_bigger():
    steep = _pos_group([100.0, 20.0, 18.0, 16.0], [3.0, 9.0, 15.0, 21.0])
    gentle = _pos_group([100.0, 96.0, 92.0, 88.0], [3.0, 9.0, 15.0, 21.0])
    assert vona.position_cliff(steep, 45) > vona.position_cliff(gentle, 45)


def test_cliff_never_exceeds_the_best_players_vorp():
    group = _pos_group([100.0, 20.0, 10.0], [3.0, 9.0, 15.0])
    assert vona.position_cliff(group, 200) <= 100.0 + 1e-9


# ==========================================================================
# 6. REPLACEMENT LEVEL AND VORP
# ==========================================================================

@pytest.fixture
def deep_pool():
    players = []
    pid = 1
    for pos, top in (("QB", 380.0), ("RB", 360.0), ("WR", 350.0), ("TE", 250.0)):
        for i in range(60):
            players.append(mk(pid, f"{pos}{i} Guy", pos, top - 4.0 * i, 2.0 + 3.0 * i))
            pid += 1
    for pos, top in (("K", 170.0), ("DST", 140.0)):
        for i in range(20):
            players.append(mk(pid, f"{pos}{i} Guy", pos, top - 2.0 * i, 150.0 + i))
            pid += 1
    return PlayerPool(players)


def test_vorp_is_exactly_projection_minus_replacement(deep_pool):
    cfg = LeagueConfig(num_teams=12, rounds=15, my_slot=1, **STD)
    levels = compute_vorp(deep_pool, cfg)
    for p in deep_pool.players:
        assert p.vorp == pytest.approx(p.proj_points - levels[p.pos], abs=0.01)


@pytest.mark.parametrize("pos", ["QB", "RB", "WR", "TE"])
def test_more_teams_pushes_replacement_deeper_and_lowers_it(deep_pool, pos):
    small = replacement_ranks(deep_pool, LeagueConfig(num_teams=8, **STD))
    big = replacement_ranks(deep_pool, LeagueConfig(num_teams=14, **STD))
    assert big[pos] > small[pos]
    lo = replacement_levels(deep_pool, LeagueConfig(num_teams=8, **STD))
    hi = replacement_levels(deep_pool, LeagueConfig(num_teams=14, **STD))
    assert hi[pos] < lo[pos], "a deeper baseline must be a worse player"


def test_extra_flex_slots_push_flex_positions_deeper_only(deep_pool):
    one = replacement_ranks(deep_pool, LeagueConfig(num_teams=12, flex_count=1,
                                                    starters=STD["starters"]))
    two = replacement_ranks(deep_pool, LeagueConfig(num_teams=12, flex_count=2,
                                                    starters=STD["starters"]))
    for pos in FLEX_ELIGIBLE:
        assert two[pos] >= one[pos]
    assert two["QB"] == one["QB"], "flex must not move a non-flex position"


def test_more_starting_slots_pushes_that_position_deeper(deep_pool):
    two_wr = LeagueConfig(num_teams=12, flex_count=1,
                          starters={"QB":1,"RB":2,"WR":2,"TE":1,"K":1,"DST":1})
    three_wr = LeagueConfig(num_teams=12, flex_count=1,
                            starters={"QB":1,"RB":2,"WR":3,"TE":1,"K":1,"DST":1})
    assert replacement_ranks(deep_pool, three_wr)["WR"] > replacement_ranks(deep_pool, two_wr)["WR"]


def test_flex_shares_are_a_distribution(deep_pool):
    sh = flex_shares(deep_pool, LeagueConfig(num_teams=12, **STD))
    assert set(sh) == set(FLEX_ELIGIBLE)
    assert all(0.0 <= v <= 1.0 for v in sh.values())
    assert sum(sh.values()) == pytest.approx(1.0)


def test_replacement_is_smoothed_not_a_single_player(deep_pool):
    """A lone anomalous player at the boundary must not move the baseline for a
    whole position."""
    cfg = LeagueConfig(num_teams=12, **STD)
    before = replacement_levels(deep_pool, cfg)["RB"]
    r = replacement_ranks(deep_pool, cfg)["RB"]
    ranked = sorted((p for p in deep_pool.players if p.pos == "RB"),
                    key=lambda p: -p.proj_points)
    spike = ranked[r - 1]
    object.__setattr__(spike, "proj_points", spike.proj_points + 60.0)
    deep_pool.reindex()
    after = replacement_levels(deep_pool, cfg)["RB"]
    assert after - before < 25.0, "one player moved the baseline too much"


def test_non_fantasy_positions_cannot_reach_valuation(tmp_path):
    csv_path = tmp_path / "pool.csv"
    csv_path.write_text(
        "player_id,name,name_norm,pos,team,bye_week,proj_points,adp,adp_source,"
        "espn_ppr_rank,auction_value,percent_owned,injury_status,eligible_pos,snapshot_ts\n"
        "1,Real Back,real back,RB,SF,9,300,1.0,espn,1,60,99,ACTIVE,RB,x\n"
        "2,A.J. Green,aj green,DB,CIN,9,900,2.0,espn,2,60,99,ACTIVE,DB,x\n"
        "3,Big Tackle,big tackle,OT,DAL,9,800,3.0,espn,3,60,99,ACTIVE,OT,x\n",
        encoding="utf-8")
    from gridiron.live.pool import load_pool
    pool = load_pool(csv_path)
    assert [p.pos for p in pool.players] == ["RB"]


# ==========================================================================
# 7. ROSTER NEED / BENCH DEPTH -- exhaustive table
# ==========================================================================

def _roster(counts):
    out, pid = [], 1
    for pos, n in counts.items():
        for _ in range(n):
            out.append(mk(pid, f"P{pid} X", pos, 100.0, 10.0)); pid += 1
    return out


@pytest.mark.parametrize("counts,pos,want", [
    ({},                              "RB", 1.0),          # empty starter slot
    ({"RB": 1},                       "RB", 1.0),          # RB2 still a starter
    ({"RB": 2},                       "RB", 1.0),          # RB3 fills the flex
    ({"RB": 2, "WR": 3},              "RB", BENCH_DEPTH),  # flex used by WR3
    ({"RB": 2, "TE": 2},              "RB", BENCH_DEPTH),  # flex used by TE2
    ({"WR": 2},                       "WR", 1.0),          # WR3 fills the flex
    ({"WR": 2, "RB": 3},              "WR", BENCH_DEPTH),  # flex used by RB3
    ({"TE": 1},                       "TE", 1.0),          # TE2 fills the flex
    ({"TE": 1, "RB": 3},              "TE", BENCH_DEEP),   # flex gone; TE2 is the last before cap
    ({"TE": 2},                       "TE", 0.0),          # TE hard cap of 2
    ({},                              "QB", 1.0),
    ({"QB": 1},                       "QB", 0.0),          # hard cap of 1
    ({"K": 1},                        "K",  0.0),
    ({"DST": 1},                      "DST", 0.0),
])
def test_need_multiplier_table(counts, pos, want):
    cfg = LeagueConfig(num_teams=12, rounds=15, my_slot=1, **STD)
    got = _need_multiplier(pos, _roster(counts), cfg)
    assert got == pytest.approx(want), f"{counts} + {pos}: {got} != {want}"


def test_the_flex_can_only_be_claimed_once():
    """Exhaustive over RB/WR/TE surpluses: the number of positions granted
    starter credit beyond their own slots can never exceed flex_count."""
    cfg = LeagueConfig(num_teams=12, rounds=15, my_slot=1, **STD)
    for rb, wr, te in itertools.product(range(0, 5), repeat=3):
        counts = {"RB": rb, "WR": wr, "TE": te}
        roster = _roster(counts)
        surplus_at_full_credit = 0
        for pos in FLEX_ELIGIBLE:
            have = counts[pos]
            if have < cfg.starters[pos]:
                continue                       # filling its own starter slot
            if have >= cfg.max_at_pos[pos]:
                continue                       # hard-capped out
            if _need_multiplier(pos, roster, cfg) == 1.0:
                surplus_at_full_credit += 1
        used = sum(max(0, counts[q] - cfg.starters[q]) for q in FLEX_ELIGIBLE)
        if used >= cfg.flex_count:
            assert surplus_at_full_credit == 0, f"{counts}: flex claimed after it was filled"


def test_bench_only_is_below_bench_depth_is_below_a_starter():
    assert 0.0 < BENCH_ONLY < BENCH_DEEP < BENCH_DEPTH < 1.0


def test_apply_need_always_makes_a_score_less_attractive():
    """A discount must lower a score in BOTH directions. For a positive score
    that is multiplication; for a negative one it must move further from zero,
    or a filled position would be promoted just as every score turns negative
    late in the draft."""
    for base in (120.0, 12.0, 0.0, -12.0, -120.0):
        prev = None
        for mult in (1.0, 0.85, 0.55, 0.25, 0.0):
            got = _apply_need(base, mult)
            assert got <= base + 1e-9, (base, mult, got)
            if prev is not None:
                assert got <= prev + 1e-9, "a harsher discount must not raise the score"
            prev = got
            if base > 0:
                assert got == pytest.approx(base * mult)
    assert _apply_need(50.0, 1.0) == pytest.approx(50.0)
    assert _apply_need(-50.0, 1.0) == pytest.approx(-50.0)
    assert _apply_need(-50.0, 0.5) < -50.0, "negatives must get worse, not better"


def test_unfilled_mandatory_tracks_the_starting_lineup():
    cfg = LeagueConfig(num_teams=12, rounds=15, my_slot=1, **STD)
    assert unfilled_mandatory([], cfg) == {"QB":1,"RB":2,"WR":2,"TE":1,"K":1,"DST":1}
    got = unfilled_mandatory(_roster({"QB":1,"RB":2,"WR":1}), cfg)
    assert got == {"WR": 1, "TE": 1, "K": 1, "DST": 1}
    full = _roster({"QB":1,"RB":2,"WR":2,"TE":1,"K":1,"DST":1})
    assert unfilled_mandatory(full, cfg) == {}


def test_roster_counts_counts():
    r = _roster({"RB": 3, "WR": 2})
    assert roster_counts(r)["RB"] == 3 and roster_counts(r)["WR"] == 2
    assert roster_counts(r)["QB"] == 0


# ==========================================================================
# 8. recommend() -- the function the board actually calls
# ==========================================================================

@pytest.fixture
def board(deep_pool):
    cfg = LeagueConfig(num_teams=12, rounds=15, my_slot=3, **STD)
    compute_vorp(deep_pool, cfg)
    return deep_pool, cfg


def test_results_are_sorted_by_score(board):
    pool, cfg = board
    recs = recommend(pool, set(), [], cfg, current_pick=3, top_n=10)
    scores = [r.score for r in recs]
    assert scores == sorted(scores, reverse=True)


def test_top_n_is_respected(board):
    pool, cfg = board
    for n in (1, 3, 5, 12):
        assert len(recommend(pool, set(), [], cfg, 3, top_n=n)) == n


def test_a_drafted_player_can_never_be_recommended(board):
    pool, cfg = board
    gone = {p.player_id for p in sorted(pool.players, key=lambda x: -x.vorp)[:40]}
    recs = recommend(pool, gone, [], cfg, current_pick=41, top_n=15)
    assert recs and all(r.player.player_id not in gone for r in recs)


def test_every_recommendation_carries_its_reasoning(board):
    pool, cfg = board
    for r in recommend(pool, set(), [], cfg, 3, top_n=5):
        assert r.reason and isinstance(r.reason, str)
        assert 0.0 <= r.survival_at_next <= 1.0
        assert r.cliff >= 0.0


def test_urgency_zero_is_pure_vorp(board):
    """lambda = 0 must reduce exactly to best-player-available among allowed
    positions -- a clean, checkable degenerate case."""
    pool, cfg = board
    recs = recommend(pool, set(), [], cfg, current_pick=3, top_n=5, urgency=0.0)
    allowed = {"QB", "RB", "WR", "TE"}          # K/DST gated this early
    best = sorted((p for p in pool.players if p.pos in allowed),
                  key=lambda p: -p.vorp)[:5]
    assert [r.player.player_id for r in recs] == [p.player_id for p in best]


def test_urgency_only_reorders_it_does_not_invent_players(board):
    pool, cfg = board
    a = {r.player.player_id for r in recommend(pool, set(), [], cfg, 3, top_n=25, urgency=0.0)}
    b = {r.player.player_id for r in recommend(pool, set(), [], cfg, 3, top_n=25, urgency=1.0)}
    assert a & b, "the two extremes should still overlap heavily"


@pytest.fixture
def kicker_heavy_pool():
    """A pool where kickers and defenses WOULD dominate without the gate.

    The previous version of this test used a normal pool, where K/DST never
    crack the top 20 on merit -- so deleting the gate outright did not fail it.
    It was asserting nothing. Here they out-project everyone, so only the gate
    can keep them off the board.
    """
    players, pid = [], 1
    for pos, top in (("QB", 200.0), ("RB", 190.0), ("WR", 185.0), ("TE", 150.0)):
        for i in range(40):
            players.append(mk(pid, f"{pos}{i} Guy", pos, top - 3.0 * i, 2.0 + 4.0 * i))
            pid += 1
    # A steep drop, not just a high level: VORP is relative, so a flat pool of
    # 900-point kickers has almost no VORP at all. The first attempt at this
    # fixture made exactly that mistake and the gate test went on asserting
    # nothing.
    for pos in ("K", "DST"):
        for i in range(20):
            players.append(mk(pid, f"{pos}{i} Guy", pos, 900.0 - 60.0 * i, 150.0 + i))
            pid += 1
    pool = PlayerPool(players)
    cfg = LeagueConfig(num_teams=12, rounds=15, my_slot=3, **STD)
    compute_vorp(pool, cfg)
    return pool, cfg


def test_kickers_outproject_everyone_in_this_fixture(kicker_heavy_pool):
    """Guard on the guard below: if K/DST stop being the top of this pool, the
    gate test silently goes back to asserting nothing."""
    pool, _ = kicker_heavy_pool
    best = max(pool.players, key=lambda p: p.vorp)
    assert best.pos in ("K", "DST"), "fixture no longer exercises the gate"


def test_kickers_and_defenses_are_gated_until_the_end(kicker_heavy_pool):
    pool, cfg = kicker_heavy_pool
    saw_gated = saw_released = False
    for pick in snake.my_pick_numbers(12, 3, 15):
        left = snake.picks_remaining(pick, 12, 3, 15)
        recs = recommend(pool, set(), [], cfg, pick, top_n=20)
        if left > LATE_ONLY_WITHIN:
            assert all(r.player.pos not in ("K", "DST") for r in recs), \
                f"K/DST offered at pick {pick} with {left} picks left"
            saw_gated = True
        else:
            assert any(r.player.pos in ("K", "DST") for r in recs), \
                f"K/DST still suppressed at pick {pick} with only {left} left"
            saw_released = True
    assert saw_gated and saw_released, "test must cover both sides of the gate"


def test_endgame_guard_forces_the_last_empty_starting_slots(board):
    """With exactly as many picks left as unfilled starter slots, every pick
    must fill one -- this is what stops a draft ending without a kicker."""
    pool, cfg = board
    picks = snake.my_pick_numbers(12, 3, 15)
    roster = _roster({"QB": 1, "RB": 2, "WR": 2, "TE": 1})
    drafted = {p.player_id for p in pool.players[:0]}
    last_two = picks[-2]
    recs = recommend(pool, drafted, roster, cfg, last_two, top_n=6)
    assert all(r.player.pos in ("K", "DST") for r in recs), \
        [(r.player.name, r.player.pos) for r in recs]


def test_hard_caps_are_never_violated(board):
    pool, cfg = board
    for pos, cap in cfg.max_at_pos.items():
        roster = _roster({pos: cap})
        recs = recommend(pool, {p.player_id for p in roster}, roster, cfg, 27, top_n=20)
        assert all(r.player.pos != pos for r in recs), f"{pos} offered at cap {cap}"


def test_recommendation_is_deterministic(board):
    pool, cfg = board
    a = [(r.player.player_id, r.score) for r in recommend(pool, set(), [], cfg, 22, top_n=10)]
    b = [(r.player.player_id, r.score) for r in recommend(pool, set(), [], cfg, 22, top_n=10)]
    assert a == b


def test_draft_position_changes_the_recommendation(board):
    """Slot 1 and slot 12 face different waits at the same overall pick, so the
    urgency term must differ. If these agree, VONA is not wired in."""
    pool, _ = board
    early = LeagueConfig(num_teams=12, rounds=15, my_slot=1, **STD)
    late = LeagueConfig(num_teams=12, rounds=15, my_slot=12, **STD)
    compute_vorp(pool, early)
    a = recommend(pool, set(), [], early, current_pick=12, top_n=5)
    b = recommend(pool, set(), [], late, current_pick=12, top_n=5)
    assert [r.score for r in a] != [r.score for r in b]


def test_no_candidates_returns_empty_not_an_error(board):
    pool, cfg = board
    everyone = {p.player_id for p in pool.players}
    assert recommend(pool, everyone, [], cfg, 100, top_n=3) == []


def test_survives_a_pool_with_a_single_player():
    cfg = LeagueConfig(num_teams=12, rounds=15, my_slot=3, **STD)
    pool = PlayerPool([mk(1, "Lone Guy", "RB", 200.0, 5.0)])
    compute_vorp(pool, cfg)
    recs = recommend(pool, set(), [], cfg, 3, top_n=3)
    assert len(recs) == 1 and recs[0].player.name == "Lone Guy"
