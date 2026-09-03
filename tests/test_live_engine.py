"""Verification gates for the 2026 live draft engine.

Deliberately small. Under a three-day clock these are the assertions whose
silent failure would actually lose a draft; everything else is eyeballed.
"""

from __future__ import annotations

import math

import pytest

from gridiron.live import names, snake, vona
from gridiron.live.pool import Player, PlayerPool
from gridiron.live.recommend import recommend
from gridiron.live.vorp import LeagueConfig, compute_vorp, replacement_ranks


# --------------------------------------------------------------------------
# 1. Snake math -- the hand-computed table from the plan
# --------------------------------------------------------------------------

def test_snake_pick_numbers_slot3_of_12():
    """Slot 3 of 12 picks at 3, 22, 27, 46, 51."""
    assert snake.my_pick_numbers(12, 3, 5) == [3, 22, 27, 46, 51]


def test_snake_gaps_alternate_19_5():
    """Waits alternate 2(N-p)+1 = 19 and 2p-1 = 5."""
    picks = snake.my_pick_numbers(12, 3, 5)
    gaps = [b - a for a, b in zip(picks, picks[1:])]
    assert gaps == [19, 5, 19, 5]


def test_snake_endpoints():
    """Slot 1 and slot N are the extreme cases."""
    assert snake.my_pick_numbers(12, 1, 3) == [1, 24, 25]
    assert snake.my_pick_numbers(12, 12, 3) == [12, 13, 36]


def test_slot_on_clock_reverses_on_even_rounds():
    assert snake.slot_on_clock(1, 12) == 1
    assert snake.slot_on_clock(12, 12) == 12
    assert snake.slot_on_clock(13, 12) == 12   # round 2 starts at the far end
    assert snake.slot_on_clock(24, 12) == 1
    assert snake.slot_on_clock(25, 12) == 1    # round 3 snaps back


def test_round_of():
    assert snake.round_of(1, 12) == 1
    assert snake.round_of(12, 12) == 1
    assert snake.round_of(13, 12) == 2


def test_picks_until_next_turn_never_negative():
    """The original implementation went negative once your slot passed."""
    for overall in range(1, 12 * 15 + 1):
        got = snake.picks_until_next_turn(overall, 12, 3, 15)
        assert got is None or got >= 0, f"negative at overall={overall}"


def test_picks_until_next_turn_is_zero_on_your_pick():
    assert snake.picks_until_next_turn(22, 12, 3, 15) == 0


def test_overall_of_roundtrips_with_slot_on_clock():
    for rnd in range(1, 16):
        for slot in range(1, 13):
            o = snake.overall_of(rnd, slot, 12)
            assert snake.slot_on_clock(o, 12) == slot
            assert snake.round_of(o, 12) == rnd


# --------------------------------------------------------------------------
# 2. Survival probability
# --------------------------------------------------------------------------

def test_survival_is_exactly_half_at_adp():
    """adp == pick_number is a coin flip. The anchor of the whole model."""
    assert vona.survival_prob(30.0, 30) == pytest.approx(0.5)


def test_survival_monotonic_and_bounded():
    probs = [vona.survival_prob(50.0, pick) for pick in range(1, 120)]
    assert all(b <= a for a, b in zip(probs, probs[1:])), "must be non-increasing"
    assert all(0.0 <= p <= 1.0 for p in probs)


def test_survival_sigma_scales_with_adp():
    """An ADP-5 player is a near-certainty; an ADP-150 player is a coin toss."""
    early = vona.survival_prob(5.0, 12)     # 7 picks past his ADP
    late = vona.survival_prob(150.0, 157)   # also 7 picks past
    assert early < late, "late-round ADP must carry more uncertainty"


def test_survival_no_adp_means_always_available():
    assert vona.survival_prob(0.0, 200) == 1.0


def test_survival_does_not_overflow():
    assert vona.survival_prob(1.0, 10_000) == pytest.approx(0.0, abs=1e-9)
    assert not math.isnan(vona.survival_prob(500.0, 1))


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

def _mk(pid, name, pos, proj, adp, team="XXX"):
    return Player(
        player_id=pid, name=name, name_norm=names.normalize(name), pos=pos,
        team=team, bye_week=7, proj_points=proj, adp=adp, espn_ppr_rank=pid,
        percent_owned=50.0, injury_status="ACTIVE", eligible_pos=(pos,),
    )


@pytest.fixture
def pool():
    """A small pool with a deliberate structure: RB has a cliff after two elite
    backs; WR is deep and flat. That is the situation VONA has to detect."""
    players = []
    pid = 1
    # RB: two elite, then a cliff.
    for i, proj in enumerate([300.0, 290.0, 200.0, 198.0, 196.0, 194.0, 192.0, 190.0]):
        players.append(_mk(pid, f"Rb{i} Back", "RB", proj, 3.0 + i * 8)); pid += 1
    # WR: deep and flat, no cliff.
    for i, proj in enumerate([280.0, 276.0, 272.0, 268.0, 264.0, 260.0, 256.0, 252.0]):
        players.append(_mk(pid, f"Wr{i} Catcher", "WR", proj, 5.0 + i * 8)); pid += 1
    for i, proj in enumerate([310.0, 300.0, 290.0, 285.0]):
        players.append(_mk(pid, f"Qb{i} Passer", "QB", proj, 40.0 + i * 20)); pid += 1
    for i, proj in enumerate([200.0, 150.0, 145.0, 140.0]):
        players.append(_mk(pid, f"Te{i} End", "TE", proj, 50.0 + i * 25)); pid += 1
    for i in range(3):
        players.append(_mk(pid, f"Kk{i} Boot", "K", 140.0 - i, 170.0)); pid += 1
        players.append(_mk(pid + 100, f"Dd{i} D/ST", "DST", 120.0 - i, 175.0)); pid += 1
    p = PlayerPool(players)
    compute_vorp(p, LeagueConfig(num_teams=12, rounds=15, my_slot=3))
    return p


# --------------------------------------------------------------------------
# 3. Position filter and replacement level
# --------------------------------------------------------------------------

def test_replacement_ranks_derive_from_roster_shape():
    """Not read from a constant -- changing team count must move the ranks."""
    from gridiron.live.pool import PlayerPool as PP
    players = [_mk(i, f"P{i} X", "RB", 300.0 - i, i + 1) for i in range(1, 60)]
    p = PP(players)
    r10 = replacement_ranks(p, LeagueConfig(num_teams=10))
    r14 = replacement_ranks(p, LeagueConfig(num_teams=14))
    assert r14["RB"] > r10["RB"], "more teams must push replacement deeper"


def test_no_non_fantasy_position_can_be_recommended(pool):
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    recs = recommend(pool, set(), [], league, current_pick=3, top_n=10)
    assert recs
    assert all(r.player.pos in ("QB", "RB", "WR", "TE", "K", "DST") for r in recs)


def test_load_pool_hard_filters_non_fantasy(tmp_path):
    """A DB/DT/OT row in the CSV must never reach the pool -- this is the
    'A.J. Green ranks #2' bug, made unexpressible."""
    csv_path = tmp_path / "pool.csv"
    csv_path.write_text(
        "player_id,name,name_norm,pos,team,bye_week,proj_points,adp,adp_source,"
        "espn_ppr_rank,auction_value,percent_owned,injury_status,eligible_pos,snapshot_ts\n"
        "1,Real Back,real back,RB,SF,9,300,1.0,espn,1,60,99,ACTIVE,RB,x\n"
        "2,A.J. Green,aj green,DB,CIN,9,400,2.0,espn,2,60,99,ACTIVE,DB,x\n",
        encoding="utf-8",
    )
    from gridiron.live.pool import load_pool
    p = load_pool(csv_path)
    assert [x.name for x in p.players] == ["Real Back"]


# --------------------------------------------------------------------------
# 4. VONA direction -- the assertion that matters most
# --------------------------------------------------------------------------

def test_vona_larger_when_the_wait_is_longer(pool):
    """The same player at the same position must be more urgent with a 19-pick
    gap than a 5-pick gap. A regression here silently reverts the tool to a
    static cheat sheet."""
    rbs = pool.at_position("RB", set())
    target = rbs[0]
    long_wait = vona.vona(target, rbs, next_pick=22)   # 19 picks away
    short_wait = vona.vona(target, rbs, next_pick=8)   # 5 picks away
    assert long_wait > short_wait


def test_vona_collapses_to_vorp_on_last_pick(pool):
    rbs = pool.at_position("RB", set())
    assert vona.vona(rbs[0], rbs, next_pick=None) == rbs[0].vorp


@pytest.fixture
def flip_pool():
    """Constructed so the RIGHT PICK CHANGES with the length of the wait.

    WR1 is strictly the better player (305 vs 300), so on raw VORP he always
    wins. The difference is what survives behind each of them:

      RB depth  -- five 250-point backs, all with ADP under 20, so a long wait
                   wipes them out and leaves a cliff down to 150.
      WR depth  -- five 250-point receivers with ADP 60-100, who comfortably
                   survive any realistic wait.

    Short wait  -> both depths intact -> take the better player (WR).
    Long wait   -> RB depth is gone, WR depth is not -> take the scarce one (RB).

    If this test ever passes on VORP alone it has stopped testing anything.
    """
    players = []
    pid = 1
    players.append(_mk(pid, "Rb1 Elite", "RB", 300.0, 3.0)); pid += 1
    for i, adp in enumerate([10.0, 12.0, 14.0, 16.0, 18.0]):
        players.append(_mk(pid, f"Rb{i+2} Depth", "RB", 250.0 - i, adp)); pid += 1
    for i in range(6):  # the cliff floor
        players.append(_mk(pid, f"Rb{i+7} Scrub", "RB", 150.0 - i, 150.0 + i)); pid += 1

    players.append(_mk(pid, "Wr1 Elite", "WR", 305.0, 4.0)); pid += 1
    for i, adp in enumerate([60.0, 70.0, 80.0, 90.0, 100.0]):
        players.append(_mk(pid, f"Wr{i+2} Depth", "WR", 250.0 - i, adp)); pid += 1
    for i in range(6):
        players.append(_mk(pid, f"Wr{i+7} Scrub", "WR", 150.0 - i, 155.0 + i)); pid += 1

    p = PlayerPool(players)
    compute_vorp(p, LeagueConfig(num_teams=12, rounds=15, my_slot=3))
    return p


def test_wr_wins_when_the_wait_is_short(flip_pool):
    """5-pick wait: both position groups survive, so take the better player."""
    league = LeagueConfig(num_teams=12, rounds=12, my_slot=12)
    # Slot 12 picks at 12 and 13 -- a 1-pick turn, essentially no attrition.
    recs = recommend(flip_pool, set(), [], league, current_pick=12, top_n=1)
    assert recs[0].player.pos == "WR", [(r.player.name, r.score) for r in recs]


def test_rb_wins_when_the_wait_is_long(flip_pool):
    """19-pick wait: RB depth is drafted away, WR depth is not. Take the cliff."""
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    recs = recommend(flip_pool, set(), [], league, current_pick=3, top_n=1)
    assert recs[0].player.pos == "RB", [(r.player.name, r.score) for r in recs]


def test_the_flip_is_caused_by_the_gap_not_by_vorp(flip_pool):
    """Guard the guard: WR1 must out-VORP RB1, so any preference for RB is
    attributable to timing alone."""
    wr1 = flip_pool.at_position("WR", set())[0]
    rb1 = flip_pool.at_position("RB", set())[0]
    assert wr1.vorp > rb1.vorp


# --------------------------------------------------------------------------
# 5. Roster gating
# --------------------------------------------------------------------------

def test_kickers_and_defenses_are_suppressed_early(pool):
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    recs = recommend(pool, set(), [], league, current_pick=3, top_n=12)
    assert all(r.player.pos not in ("K", "DST") for r in recs)


def test_kickers_appear_at_the_very_end(pool):
    """With one pick left and every starter filled, K/DST become eligible."""
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    last = snake.my_pick_numbers(12, 3, 15)[-1]
    roster = [
        pool.at_position("QB", set())[0],
        *pool.at_position("RB", set())[:2],
        *pool.at_position("WR", set())[:2],
        pool.at_position("TE", set())[0],
    ]
    recs = recommend(pool, set(), roster, league, current_pick=last, top_n=5)
    assert any(r.player.pos in ("K", "DST") for r in recs)


def test_hard_cap_blocks_a_full_position(pool):
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    league.max_at_pos["QB"] = 1
    roster = [pool.at_position("QB", set())[0]]
    recs = recommend(pool, set(), roster, league, current_pick=27, top_n=12)
    assert all(r.player.pos != "QB" for r in recs)


def test_drafted_players_never_recommended(pool):
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    gone = {p.player_id for p in pool.at_position("RB", set())[:3]}
    recs = recommend(pool, gone, [], league, current_pick=22, top_n=10)
    assert all(r.player.player_id not in gone for r in recs)


# --------------------------------------------------------------------------
# 6. Name matching -- the integration risk
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Ja'Marr Chase", "jamarr chase"),
    ("Amon-Ra St. Brown", "amon ra st brown"),
    ("Kenneth Walker III", "kenneth walker"),
    ("Chase, Ja'Marr", "jamarr chase"),
    ("McCaffrey, Christian", "christian mccaffrey"),
    ("Marvin Harrison Jr.", "marvin harrison"),
    ("D'Andre Swift", "dandre swift"),
    ("  Puka   Nacua  ", "puka nacua"),
])
def test_normalize(raw, expected):
    assert names.normalize(raw) == expected


def test_initials_and_first_initial_last():
    assert names.initials("Amon-Ra St. Brown") == "arsb"
    assert names.first_initial_last("Christian McCaffrey") == "cmccaffrey"


def test_match_exact_and_fuzzy():
    rows = [
        {"player_id": 1, "name": "Ja'Marr Chase", "name_norm": "jamarr chase",
         "pos": "WR", "team": "CIN"},
        {"player_id": 2, "name": "Christian McCaffrey", "name_norm": "christian mccaffrey",
         "pos": "RB", "team": "SF"},
    ]
    assert names.match("Chase, Ja'Marr", rows)["player_id"] == 1
    assert names.match("JaMarr Chase", rows)["player_id"] == 1
    assert names.match("Christian McCaffery", rows)["player_id"] == 2   # misspelled
    assert names.match("Nobody Here", rows) is None


# --------------------------------------------------------------------------
# 7. Pick store -- undo, correct, and the anti-double-count constraints
# --------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    from gridiron.live.store import PickStore
    return PickStore(tmp_path / "d.sqlite", num_teams=12)


def test_append_assigns_snake_slots(store):
    a = store.append(101)
    b = store.append(102)
    assert (a.overall, a.slot) == (1, 1)
    assert (b.overall, b.slot) == (2, 2)
    for _ in range(10):
        store.append(None, observed_name="x")
    turn = store.append(999)          # overall 13 -> round 2 starts at slot 12
    assert (turn.overall, turn.round, turn.slot) == (13, 2, 12)


def test_one_player_cannot_occupy_two_picks(store):
    from gridiron.live.store import PickConflict
    store.append(101)
    with pytest.raises(PickConflict):
        store.append(101)


def test_undo_is_repeatable_to_empty(store):
    for pid in (101, 102, 103):
        store.append(pid)
    assert store.count() == 3
    while store.undo_last():
        pass
    assert store.count() == 0
    assert store.undo_last() is None


def test_undo_then_reenter_reuses_the_slot(store):
    store.append(101)
    store.append(102)
    store.undo_last()
    p = store.append(103)
    assert p.overall == 2
    assert store.drafted_ids() == {101, 103}


def test_correct_does_not_shift_later_picks(store):
    """Fixing pick 3 while sitting at pick 10 must not disturb 4-10."""
    for pid in range(101, 111):
        store.append(pid)
    before = {p.overall: p.player_id for p in store.snapshot() if p.overall != 3}
    store.correct(3, 999)
    after = {p.overall: p.player_id for p in store.snapshot() if p.overall != 3}
    assert before == after
    assert store.conn.execute(
        "SELECT player_id FROM picks WHERE overall=3").fetchone()["player_id"] == 999


def test_correct_rejects_a_player_already_taken(store):
    from gridiron.live.store import PickConflict
    store.append(101)
    store.append(102)
    with pytest.raises(PickConflict):
        store.correct(1, 102)


def test_delete_shift_pulls_everything_back(store):
    for pid in (101, 102, 103, 104):
        store.append(pid)
    store.delete_shift(2)
    assert [(p.overall, p.player_id) for p in store.snapshot()] == [
        (1, 101), (2, 103), (3, 104)]


def test_yahoo_outranks_manual_at_the_same_slot(store):
    store.append(101, overall=5, source="manual")
    store.append(202, overall=5, source="yahoo")
    row = store.conn.execute("SELECT * FROM picks WHERE overall=5").fetchone()
    assert row["player_id"] == 202 and row["source"] == "yahoo"


def test_manual_cannot_overwrite_yahoo(store):
    from gridiron.live.store import PickConflict
    store.append(202, overall=5, source="yahoo")
    with pytest.raises(PickConflict):
        store.append(101, overall=5, source="manual")


def test_state_survives_reopen(tmp_path):
    from gridiron.live.store import PickStore
    path = tmp_path / "d.sqlite"
    s1 = PickStore(path, num_teams=12)
    s1.append(101); s1.append(102)
    s1.close()
    s2 = PickStore(path, num_teams=12)
    assert s2.drafted_ids() == {101, 102}
    assert s2.next_overall() == 3


def test_next_overall_uses_max_not_count(store):
    """A gap left by an out-of-order Yahoo pick must not rewind the clock."""
    store.append(101, overall=1)
    store.append(102, overall=7)
    assert store.next_overall() == 8


# --------------------------------------------------------------------------
# 8. Type-ahead
# --------------------------------------------------------------------------

def _rows(*pairs):
    return [{"name": n, "rank": r} for n, r in pairs]


def test_search_shorthand_hits():
    rows = _rows(("Christian McCaffrey", 4), ("Chase McLaughlin", 300),
                 ("Amon-Ra St. Brown", 8), ("Jaxon Smith-Njigba", 7))
    assert names.search("cmc", rows)[0]["name"] == "Christian McCaffrey"
    assert names.search("arsb", rows)[0]["name"] == "Amon-Ra St. Brown"
    assert names.search("jsn", rows)[0]["name"] == "Jaxon Smith-Njigba"


def test_search_ranks_studs_above_nobodies():
    """A weak-tier match on a stud beats a strong-tier match on a scrub."""
    rows = _rows(("Ja'Marr Chase", 5), ("Chase Brown", 40), ("Chase McLaughlin", 300))
    assert names.search("chase", rows)[0]["name"] == "Ja'Marr Chase"


def test_is_decisive_accepts_clear_winners_and_asks_otherwise():
    clear = names.search("cmc", _rows(("Christian McCaffrey", 4), ("Chase McLaughlin", 300)))
    assert names.is_decisive(clear)
    close = names.search("brown", _rows(("Chase Brown", 40), ("A.J. Brown", 45)))
    assert not names.is_decisive(close)


# --------------------------------------------------------------------------
# 9. Bench-only positions -- the round-9 backup-QB trap
# --------------------------------------------------------------------------

def test_surplus_qb_is_bench_only(pool):
    """A second QB in a one-QB league cannot enter the lineup, so he must be
    weighted far below a player who can.

    This is not hypothetical: replacement level is static, so by the late rounds
    every remaining player scores below it and VORP goes uniformly negative. A
    backup QB is then the only positive number on the board and wins the pick.
    A 180-pick replay spent round 9 on a second quarterback before this rule.
    """
    from gridiron.live.recommend import BENCH_ONLY, _need_multiplier
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    qb = pool.at_position("QB", set())[0]
    assert _need_multiplier("QB", [qb], league) == BENCH_ONLY


def test_flex_eligible_surplus_still_counts_as_a_starter(pool):
    """A third RB/WR or second TE fills the FLEX slot, so it is NOT bench-only."""
    from gridiron.live.recommend import _need_multiplier
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)   # RB2 WR2 TE1 + 1 flex
    rbs = pool.at_position("RB", set())[:3]
    tes = pool.at_position("TE", set())[:1]
    assert _need_multiplier("RB", rbs[:2], league) == 1.0   # 3rd RB fills flex
    assert _need_multiplier("TE", tes, league) == 1.0       # 2nd TE fills flex
    assert _need_multiplier("RB", rbs[:3], league) < 1.0    # 4th RB is depth


def test_startable_player_beats_a_backup_qb_when_both_are_replacement_level(pool):
    """The concrete regression: with a QB already rostered, a flex-eligible
    player must outrank a surplus QB of comparable raw value."""
    league = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    roster = [pool.at_position("QB", set())[0], *pool.at_position("RB", set())[:2],
              *pool.at_position("WR", set())[:2]]
    drafted = {p.player_id for p in roster}
    recs = recommend(pool, drafted, roster, league, current_pick=99, top_n=1)
    assert recs[0].player.pos != "QB", (
        f"took a backup QB over startable depth: {recs[0].player.name}")
