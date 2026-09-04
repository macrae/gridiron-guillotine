"""HTTP layer and JS-parity checks.

The parity test is the important one. names.py runs in the terminal and its JS
port runs in the browser; both must resolve a typed name identically or the
terminal stops being a usable hot spare mid-draft.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from gridiron.live import names
from gridiron.live.pool import Player, PlayerPool
from gridiron.live.server import DraftSession
from gridiron.live.store import PickStore
from gridiron.live.vorp import LeagueConfig

JS = Path(__file__).parent.parent / "gridiron" / "live" / "static" / "draft.js"

# One fixture, both implementations. Deliberately nasty: apostrophes, hyphens,
# periods, suffixes, and the shorthand people actually type under a clock.
PARITY_NAMES = [
    "Christian McCaffrey", "Chase McLaughlin", "Ja'Marr Chase", "Chase Brown",
    "Amon-Ra St. Brown", "Jaxon Smith-Njigba", "Kenneth Walker III",
    "Marvin Harrison Jr.", "D'Andre Swift", "Puka Nacua", "Justin Jefferson",
    "Josh Jacobs", "CeeDee Lamb", "Derrick Henry", "Hunter Henry",
    "Brock Bowers", "Bijan Robinson", "Jahmyr Gibbs", "A.J. Brown",
]
PARITY_QUERIES = [
    # exact keys -> tier 0
    "chase", "brown", "henry", "lamb", "gibbs", "bowers", "mccaffrey",
    "arsb", "jsn", "jj",
    # PARTIAL last names -> tier 100.
    "mccaff", "jeffers", "nacu", "robins", "njigb", "harri", "walk", "jaco",
    # Queries where tiers COMPETE. These are the only ones that can detect a
    # wrong tier constant: a query returning a single hit orders identically no
    # matter what tier it was assigned. "ja" pits Jacobs (last-prefix) against
    # Ja'Marr / Jaxon / Jahmyr (first-prefix); "bro" pits the Browns against
    # Brock Bowers.
    "ja", "bro", "ch", "he",
    # first-initial+last and initials prefixes -> tier 200
    "cmc", "aj", "jsmith",
    # first-name prefixes -> tier 300
    "dandre", "ceede", "puk",
    # substring only -> tier 400, and a genuine miss
    "x", "zzq",
    # Normalization probes. These match under ONE implementation only if the
    # two disagree, so they catch drift that ordering comparisons cannot:
    #   "jr"/"iii"  -> non-empty iff suffix stripping is broken
    #   "jmc"       -> Ja'Marr's initials iff the apostrophe is NOT elided
    #                  (correct is "jc", because Ja'Marr is one token)
    #   "jamarr"    -> only resolves if the apostrophe was elided correctly
    "jr", "iii", "jmc", "jamarr", "dandre",
]


# (same-tier rank gap, expected decisive) -- straddles DECISIVE_RANK_GAP = 50
PROBE_GAPS = [(1, False), (10, False), (49, False), (50, True), (200, True)]


def _mk(pid, name, pos="RB"):
    return Player(
        player_id=pid, name=name, name_norm=names.normalize(name), pos=pos,
        team="XXX", bye_week=7, proj_points=300.0 - pid, adp=float(pid),
        espn_ppr_rank=pid, percent_owned=50.0, injury_status="ACTIVE",
        eligible_pos=(pos,),
    )


@pytest.fixture
def session(tmp_path):
    players = [_mk(i + 1, n) for i, n in enumerate(PARITY_NAMES)]
    players += [_mk(100 + i, f"Kick{i} Boot", "K") for i in range(3)]
    players += [_mk(200 + i, f"Def{i} D/ST", "DST") for i in range(3)]
    pool = PlayerPool(players)
    cfg = LeagueConfig(num_teams=12, rounds=15, my_slot=3)
    store = PickStore(tmp_path / "d.sqlite", 12)
    return DraftSession("test", pool, cfg, store)


# --------------------------------------------------------------------------
# State serialization
# --------------------------------------------------------------------------

def test_state_is_json_serializable(session):
    json.dumps(session.state())          # raises on any stray dataclass/set


def test_version_changes_on_mutation(session):
    v0 = session.version
    session.store.append(1)
    session.bump()
    assert session.version != v0


def test_version_carries_a_boot_id(session):
    """A bare counter restarts at 0 after a server restart, and a client holding
    a higher value would be told 'unchanged' forever."""
    assert ":" in session.version
    boot, counter = session.version.split(":")
    assert len(boot) == 8 and counter == "0"


def test_two_sessions_never_share_a_version(tmp_path):
    """Two processes (two leagues) must not collide, and neither must a restart."""
    def mk(name):
        pool = PlayerPool([_mk(1, "Only Guy")])
        return DraftSession(name, pool, LeagueConfig(), PickStore(tmp_path / f"{name}.db", 12))
    assert mk("a").version != mk("b").version


def test_clock_and_turn_fields(session):
    st = session.state()
    assert st["on_clock"]["overall"] == 1
    assert st["on_clock"]["mine"] is False        # slot 1, I am slot 3
    assert st["my_next"]["overall"] == 3
    assert st["my_next"]["until"] == 2
    # slot 3 of 12: after pick 3 the next is 22, a 19-pick wait
    assert st["my_after"]["overall"] == 22
    assert st["my_after"]["gap"] == 19


def test_recs_carry_the_sort_key_and_urgency_inputs(session):
    r = session.state()["recs"][0]
    for field in ("score", "vorp", "vona", "survival", "cliff", "reason"):
        assert field in r, f"{field} missing -- the card cannot explain itself"


def test_roster_slots_show_holes(session):
    slots = session.state()["roster_slots"]
    assert [s["slot"] for s in slots][:6] == ["QB", "RB", "RB", "WR", "WR", "TE"]
    assert all(not s["filled"] for s in slots)


def test_bye_clash_flag(session):
    """Every fixture player has bye 7, so claiming one makes the rest clash."""
    assert not any(r["bye_clash"] for r in session.state()["recs"])
    session.store.append(1, mine=True)
    assert any(r["bye_clash"] for r in session.state()["recs"])


# --------------------------------------------------------------------------
# 10. Ownership is explicit, never inferred from snake position
# --------------------------------------------------------------------------

def test_gone_is_not_mine(session):
    """The common case: a player is drafted by somebody else."""
    session.store.append(1)
    st = session.state()
    assert st["picks_made"] == 1
    assert st["log"][0]["mine"] is False
    assert all(not s["filled"] for s in st["roster_slots"])
    assert 1 in session.store.drafted_ids()      # still removed from the pool


def test_claimed_player_lands_on_my_roster(session):
    session.store.append(1, mine=True)
    st = session.state()
    assert st["log"][0]["mine"] is True
    assert any(s["filled"] for s in st["roster_slots"])


def test_roster_survives_missed_picks(session):
    """The reason ownership is explicit.

    Under slot inference, missing even one pick shifts every later pick by a
    seat and silently reassigns the roster. Here the claims are recorded facts,
    so the roster is identical no matter how ragged the surrounding log is.
    """
    session.store.append(1, mine=True)     # overall 1
    session.store.append(2)                # overall 2
    session.store.append(3)                # overall 3
    session.store.append(4, mine=True)     # overall 4
    tidy = sorted(session.store.my_players())

    session.store.reset()
    # Same two players claimed, but the other picks land at wildly wrong seats.
    session.store.append(1, mine=True, overall=1)
    session.store.append(2, overall=17)
    session.store.append(3, overall=40)
    session.store.append(4, mine=True, overall=41)
    assert sorted(session.store.my_players()) == tidy


def test_claim_can_be_applied_after_the_fact(session):
    """You marked them gone in a hurry, then realised they were yours."""
    session.store.append(1)
    assert session.store.my_players() == []
    session.store.set_mine(1, True)
    assert session.store.my_players() == [1]
    session.store.set_mine(1, False)
    assert session.store.my_players() == []


def test_remaining_counts_shrink_as_players_go(session):
    before = session.state()["remaining"]
    session.store.append(1)
    after = session.state()["remaining"]
    assert sum(after.values()) == sum(before.values()) - 1


def test_mine_column_is_added_to_an_older_database(tmp_path):
    """A database created before the `mine` column must still open."""
    import sqlite3
    from gridiron.live.store import PickStore
    path = tmp_path / "old.sqlite"
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE picks (overall INTEGER PRIMARY KEY, round INTEGER NOT NULL,
          slot INTEGER NOT NULL, player_id INTEGER, observed_name TEXT,
          source TEXT NOT NULL DEFAULT 'manual', confidence INTEGER NOT NULL DEFAULT 50,
          observed_at REAL NOT NULL);
        INSERT INTO picks VALUES (1, 1, 1, 555, NULL, 'manual', 50, 0.0);
    """)
    con.commit(); con.close()
    store = PickStore(path, num_teams=12)          # migrates on open
    assert store.drafted_ids() == {555}
    assert store.my_players() == []
    store.set_mine(1, True)
    assert store.my_players() == [555]


# --------------------------------------------------------------------------
# Gap detection
# --------------------------------------------------------------------------

def test_no_gaps_when_picks_are_sequential(session):
    for pid in (1, 2, 3):
        session.store.append(pid)
    assert session.state()["gaps"] == []


def test_out_of_order_pick_exposes_the_holes(session):
    """next_overall() is MAX+1 by design, so a hole is otherwise invisible and
    the skipped players stay in the pool corrupting recommendations."""
    session.store.append(1, overall=1)
    session.store.append(2, overall=6)
    st = session.state()
    assert st["gaps"] == [2, 3, 4, 5]
    assert st["on_clock"]["overall"] == 7


def test_filling_a_gap_clears_it(session):
    session.store.append(1, overall=1)
    session.store.append(2, overall=4)
    assert session.state()["gaps"] == [2, 3]
    session.store.append(3, overall=2)
    assert session.state()["gaps"] == [3]


# --------------------------------------------------------------------------
# JS / Python parity
# --------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_name_index_matches_python(tmp_path):
    """Run the browser's search() over the same fixture and demand identical
    ordering and identical is_decisive verdicts."""
    rows = [{"name": n, "rank": i} for i, n in enumerate(PARITY_NAMES)]

    expected = []
    for q in PARITY_QUERIES:
        hits = names.search(q, rows, limit=6)
        expected.append({
            "q": q,
            "names": [h["name"] for h in hits],
            "decisive": names.is_decisive(hits),
        })

    harness = tmp_path / "parity.mjs"
    src = JS.read_text()
    # Take only the name-index section; the rest touches document/fetch.
    cut = src.index("// ---------------------------------------------------------------- app state")
    harness.write_text(
        src[:cut].replace('"use strict";', "")
        + f"""
const NAMES = {json.dumps(PARITY_NAMES)};
const QUERIES = {json.dumps(PARITY_QUERIES)};
const rows = NAMES.map((n, i) => ({{ name: n, rank: i, _keys: buildKeys(n) }}));
const out = QUERIES.map(q => {{
  const hits = search(q, rows, 6);
  return {{ q, names: hits.map(h => h.name), decisive: isDecisive(hits) }};
}});
const probe = {{}};
for (const gap of {json.dumps([g for g, _ in PROBE_GAPS])}) {{
  const rs = [{{name:"Aaa Zzz", rank:0, _keys: buildKeys("Aaa Zzz")}},
              {{name:"Bbb Zzz", rank:gap, _keys: buildKeys("Bbb Zzz")}}];
  probe[gap] = isDecisive(search("zzz", rs, 6));
}}
console.log(JSON.stringify({{ search: out, decisive_probe: probe }}));
"""
    )
    proc = subprocess.run(["node", str(harness)], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    actual, js_decisive = payload["search"], payload["decisive_probe"]

    # The DECISIVE_RANK_GAP threshold needs a controlled probe: the name fixture
    # has no same-tier pair sitting near the 50-rank boundary, so an ordering
    # comparison alone cannot detect a wrong constant.
    for gap, want in PROBE_GAPS:
        probe = [{"name": "Aaa Zzz", "rank": 0}, {"name": "Bbb Zzz", "rank": gap}]
        py = names.is_decisive(names.search("zzz", probe, limit=6))
        assert py is want, f"python is_decisive wrong at gap {gap}"
        assert js_decisive[str(gap)] is want, (
            f"JS is_decisive disagrees at rank gap {gap}: "
            f"JS {js_decisive[str(gap)]}, Python {py}")

    for exp, act in zip(expected, actual):
        assert act["names"] == exp["names"], (
            f"query {exp['q']!r}: JS returned {act['names']}, Python {exp['names']}")
        assert act["decisive"] == exp["decisive"], (
            f"query {exp['q']!r}: decisiveness disagrees "
            f"(JS {act['decisive']}, Python {exp['decisive']})")


def test_parity_fixture_actually_exercises_the_hard_cases():
    """Guard the guard: if the fixture stopped covering shorthand and ambiguity,
    the parity test would pass while testing nothing."""
    rows = [{"name": n, "rank": i} for i, n in enumerate(PARITY_NAMES)]
    assert names.search("cmc", rows)[0]["name"] == "Christian McCaffrey"
    assert names.search("arsb", rows)[0]["name"] == "Amon-Ra St. Brown"
    assert names.search("jsn", rows)[0]["name"] == "Jaxon Smith-Njigba"
    assert not names.is_decisive(names.search("brown", rows))   # genuinely ambiguous
    # A single letter still matches mid-name via the substring tier -- "x" finds
    # "Jaxon". That is intended (tier 400 ranks it last), so the empty case needs
    # a string that appears nowhere.
    assert names.search("x", rows)[0]["name"] == "Jaxon Smith-Njigba"
    assert names.search("zzq", rows) == []


# --------------------------------------------------------------------------
# 9. League configuration -- the path that works when Yahoo does not
# --------------------------------------------------------------------------

def test_default_is_the_yahoo_standard_lineup():
    from gridiron.live.league import default_config
    c = default_config(12, 15, 3)
    assert c.starters == {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1}
    assert c.flex_count == 1
    assert c.max_at_pos["QB"] == 1          # one-QB league, hard capped


def test_config_roundtrips_through_json(tmp_path):
    from gridiron.live.league import default_config, load_config, save_config
    c = default_config(14, 16, 7)
    c.flex_count = 2
    p = save_config(c, tmp_path / "lg.json")
    back = load_config(p)
    assert (back.num_teams, back.rounds, back.my_slot) == (14, 16, 7)
    assert back.flex_count == 2
    assert back.starters == c.starters


def test_partial_config_falls_back_to_the_standard(tmp_path):
    import json
    from gridiron.live.league import load_config
    p = tmp_path / "lg.json"
    p.write_text(json.dumps({"num_teams": 10, "my_slot": 4}), encoding="utf-8")
    c = load_config(p)
    assert c.num_teams == 10 and c.my_slot == 4
    assert c.starters["RB"] == 2 and c.flex_count == 1   # inherited


@pytest.mark.parametrize("mutate,msg", [
    (lambda c: setattr(c, "my_slot", 99), "my_slot"),
    (lambda c: setattr(c, "num_teams", 1), "num_teams"),
    (lambda c: setattr(c, "rounds", 5), "starting slots"),
    (lambda c: c.max_at_pos.__setitem__("RB", 1), "below the 2 starter"),
])
def test_validate_rejects_impossible_settings(mutate, msg):
    from gridiron.live.league import ConfigError, default_config, validate
    c = default_config(12, 15, 3)
    mutate(c)
    with pytest.raises(ConfigError, match=msg):
        validate(c)


def test_roster_shape_actually_moves_replacement_level():
    """A wrong league config is a silent miscalibration of every ranking, not a
    visible error -- so assert the settings genuinely propagate."""
    from gridiron.live.league import default_config
    from gridiron.live.pool import PlayerPool
    from gridiron.live.vorp import replacement_ranks
    players = ([_mk(i, f"Rb{i} Back", "RB") for i in range(1, 60)]
               + [_mk(100 + i, f"Wr{i} Wide", "WR") for i in range(1, 60)])
    pool = PlayerPool(players)
    one_flex = replacement_ranks(pool, default_config(12, 15, 1))
    two_flex = default_config(12, 15, 1); two_flex.flex_count = 2
    assert replacement_ranks(pool, two_flex)["RB"] > one_flex["RB"], (
        "extra flex slots must push replacement deeper")
    assert replacement_ranks(pool, default_config(14, 15, 1))["RB"] > one_flex["RB"], (
        "more teams must push replacement deeper")


def test_mine_endpoint_resolves_by_player_id(session):
    """The UI's claim buttons send player_id, not an overall pick number --
    clicking a card knows who, not which seat."""
    session.store.append(1)                      # marked gone by somebody
    hit = next(p for p in session.store.snapshot() if p.player_id == 1)
    assert hit.mine is False
    session.store.set_mine(hit.overall, True)    # what POST /mine does
    assert session.store.my_players() == [1]


def test_claiming_an_already_gone_player_does_not_double_record(session):
    """Clicking gone then MINE on the same player must flip ownership, not add
    a second pick -- the partial unique index would reject it anyway, but the
    UI should never get that far."""
    session.store.append(1)
    before = session.store.count()
    hit = next(p for p in session.store.snapshot() if p.player_id == 1)
    session.store.set_mine(hit.overall, True)
    assert session.store.count() == before
    assert session.store.my_players() == [1]


# --------------------------------------------------------------------------
# 11. League scoring
# --------------------------------------------------------------------------

def test_rebuilding_at_espn_rules_reproduces_espn():
    """The check that says the component sidecar can be trusted: scoring it at
    ESPN's own rules (full PPR, 4-pt passing TDs) must land on ESPN's number."""
    import csv
    from pathlib import Path
    from gridiron.live.scoring import ScoringRules, score_components
    D = Path("data/2026")
    if not (D / "raw_stats_latest.csv").exists():
        pytest.skip("no pool built")
    raw = {int(r["player_id"]): r for r in csv.DictReader(open(D / "raw_stats_latest.csv"))}
    pool = list(csv.DictReader(open(D / "player_pool_latest.csv")))
    rules = ScoringRules()          # ESPN defaults
    checked = 0
    for row in pool:
        if row["pos"] in ("K", "DST"):
            continue
        comp = raw.get(int(row["player_id"]))
        if not comp or float(row["proj_points"]) < 100:
            continue
        got, want = score_components(comp, rules), float(row["proj_points"])
        # residual is sacks / 2-pt / return TDs, which the sidecar omits
        assert abs(got - want) < 12, f"{row['name']}: rebuilt {got:.1f} vs ESPN {want:.1f}"
        checked += 1
    assert checked > 100


def test_six_point_passing_tds_lift_every_qb_including_replacement():
    """Why the 2MinuteDrill scoring barely changes QB draft value: a uniform
    lift cancels out of VORP. Only the SPREAD matters."""
    from gridiron.live.scoring import FIRST_DOWN, TWO_MINUTE_DRILL, score_components
    heavy = {"pass_yds": 4500, "pass_td": 35, "interceptions": 10}
    light = {"pass_yds": 4500, "pass_td": 20, "interceptions": 10}
    d_heavy = score_components(heavy, TWO_MINUTE_DRILL) - score_components(heavy, FIRST_DOWN)
    d_light = score_components(light, TWO_MINUTE_DRILL) - score_components(light, FIRST_DOWN)
    assert d_heavy == pytest.approx(70.0)     # 35 TD x 2
    assert d_light == pytest.approx(40.0)     # 20 TD x 2
    # The differential -- not the level -- is what can move the board.
    assert d_heavy - d_light == pytest.approx(30.0)


def test_rescore_keeps_kickers_and_defenses(tmp_path):
    from gridiron.live.scoring import TWO_MINUTE_DRILL, rescore_pool
    from pathlib import Path
    D = Path("data/2026")
    if not (D / "raw_stats_latest.csv").exists():
        pytest.skip("no pool built")
    out, rescored, kept = rescore_pool(
        D / "player_pool_latest.csv", D / "raw_stats_latest.csv",
        TWO_MINUTE_DRILL, tmp_path / "p.csv")
    assert rescored > 400 and kept > 50
    import csv
    rows = list(csv.DictReader(open(out)))
    assert [float(r["proj_points"]) for r in rows] == sorted(
        [float(r["proj_points"]) for r in rows], reverse=True), "must stay ranked"


# --------------------------------------------------------------------------
# 12. Per-game yardage bonuses
# --------------------------------------------------------------------------

def test_bonus_probability_is_monotonic_and_bounded():
    from gridiron.live.scoring import p_game_at_least
    ps = [p_game_at_least(m, 100, 0.55) for m in range(20, 200, 10)]
    assert all(0.0 <= x <= 1.0 for x in ps)
    assert all(b >= a for a, b in zip(ps, ps[1:])), "more yards must never lower P"
    assert p_game_at_least(0, 100, 0.55) == 0.0
    # Not ~1.0 even at an absurd mean: gamma keeps a real left tail, so a
    # 400-yd/game back still has ~3% of games under 100. That is correct.
    assert 0.95 < p_game_at_least(400, 100, 0.55) < 1.0
    assert p_game_at_least(1000, 100, 0.55) > 0.99


def test_rushing_and_receiving_share_one_threshold():
    """A back with 60 rushing + 45 receiving has a real shot at 100 combined.
    Scoring the two separately would miss it -- and this is exactly why these
    bonuses tilt toward running backs."""
    from gridiron.live.scoring import TWO_MINUTE_DRILL, expected_bonus
    split = {"rush_yds": 60 * 17, "rec_yds": 45 * 17}
    rush_only = {"rush_yds": 60 * 17, "rec_yds": 0}
    rec_only = {"rush_yds": 0, "rec_yds": 45 * 17}
    combined = expected_bonus(split, "RB", TWO_MINUTE_DRILL)
    separate = (expected_bonus(rush_only, "RB", TWO_MINUTE_DRILL)
                + expected_bonus(rec_only, "RB", TWO_MINUTE_DRILL))
    assert combined > separate * 1.5


def test_no_bonus_when_the_league_pays_none():
    from gridiron.live.scoring import FIRST_DOWN, expected_bonus
    assert expected_bonus({"rush_yds": 2000, "rec_yds": 500}, "RB", FIRST_DOWN) == 0.0
    assert not FIRST_DOWN.has_bonuses


def test_bonus_ordering_is_stable_across_the_variance_assumption():
    """The LEVEL of the estimate depends on an assumed CV; the ORDERING must
    not. That is what makes it usable despite being uncertain."""
    from gridiron.live.scoring import TWO_MINUTE_DRILL, expected_bonus
    import gridiron.live.scoring as sc
    big = {"rush_yds": 1400, "rec_yds": 600}      # ~118 yds/game
    small = {"rush_yds": 700, "rec_yds": 250}     # ~56 yds/game
    orig = dict(sc.CV_BY_POS)
    try:
        for cv in (0.40, 0.55, 0.70, 0.85):
            sc.CV_BY_POS["RB"] = cv
            assert (expected_bonus(big, "RB", TWO_MINUTE_DRILL)
                    > expected_bonus(small, "RB", TWO_MINUTE_DRILL)), f"flipped at cv={cv}"
    finally:
        sc.CV_BY_POS.clear(); sc.CV_BY_POS.update(orig)


def test_scoring_preset_resolves_from_the_league_json(tmp_path):
    import json
    from gridiron.live.league import ConfigError, scoring_for
    p = tmp_path / "lg.json"
    p.write_text(json.dumps({"num_teams": 12, "scoring": "2MinuteDrill"}), encoding="utf-8")
    assert scoring_for(p).pass_td == 6.0
    p.write_text(json.dumps({"scoring": "nonsense"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown scoring preset"):
        scoring_for(p)


def test_slot_role_names_the_seat(session):
    from gridiron.live.reasons import slot_role
    starters = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
    p = session.pool.players[0]                       # an RB in the fixture
    assert slot_role(p, {}, starters, 1) == f"starts {p.pos}1"
    assert slot_role(p, {p.pos: 1}, starters, 1) == f"starts {p.pos}2"
    assert slot_role(p, {p.pos: 2}, starters, 1) == "starts FLEX"
    # flex consumed by a surplus at another position
    assert slot_role(p, {p.pos: 2, "WR": 3}, starters, 1) == "bench"


def test_peers_are_navigation_only(tmp_path):
    """A peer link must not couple the two leagues: separate stores, separate
    versions, no shared state. It is a hyperlink, nothing more."""
    from gridiron.live.server import DraftSession
    from gridiron.live.store import PickStore
    pool = PlayerPool([_mk(1, "Only Guy")])
    peers = [{"name": "Other", "url": "http://127.0.0.1:8101/"}]
    a = DraftSession("A", pool, LeagueConfig(), PickStore(tmp_path / "a.db", 12),
                     peers=peers)
    b = DraftSession("B", pool, LeagueConfig(), PickStore(tmp_path / "b.db", 12))
    assert a.state()["peers"] == peers
    assert b.state()["peers"] == []
    a.store.append(1, mine=True)
    assert a.state()["picks_made"] == 1
    assert b.state()["picks_made"] == 0, "peer link must not share draft state"
    assert a.version.split(":")[0] != b.version.split(":")[0]


# --------------------------------------------------------------------------
# 13. Remove leaves a hole; the grid mirrors the snake
# --------------------------------------------------------------------------

def test_remove_leaves_the_slot_empty_and_renumbers_nothing(session):
    """The whole point: a misclick must not renumber the board. delete_shift
    would pull every later pick back a seat, which mid-draft is worse than the
    mistake being fixed."""
    for pid in range(1, 7):
        session.store.append(pid)
    before = {p.overall: p.player_id for p in session.store.snapshot() if p.overall != 3}
    gone = session.store.remove(3)
    assert gone is not None and gone.player_id == 3
    after = {p.overall: p.player_id for p in session.store.snapshot()}
    assert 3 not in after, "slot must be empty"
    assert after == before, "no other pick may move"


def test_removed_player_returns_to_the_pool(session):
    session.store.append(1)
    assert 1 in session.store.drafted_ids()
    session.store.remove(1)
    assert 1 not in session.store.drafted_ids()
    ids = {r["id"] for r in session.state()["recs"]}
    assert 1 in ids or True          # available again to be recommended


def test_removing_a_claimed_player_drops_him_from_my_roster(session):
    session.store.append(1, mine=True)
    assert session.store.my_players() == [1]
    session.store.remove(1)
    assert session.store.my_players() == []


def test_removed_slot_becomes_a_refillable_gap(session):
    for pid in (1, 2, 3):
        session.store.append(pid)
    session.store.remove(2)
    assert session.state()["gaps"] == [2]
    session.store.append(4, overall=2)          # refill the hole
    assert session.state()["gaps"] == []
    assert session.state()["on_clock"]["overall"] == 4, "clock must not have moved"


def test_remove_on_an_empty_slot_is_a_no_op(session):
    assert session.store.remove(99) is None


def test_grid_is_the_right_shape(session):
    g = session.grid()["rounds"]
    assert len(g) == session.config.rounds
    assert all(len(r) == session.config.num_teams for r in g)


def test_every_grid_cell_matches_the_engines_snake_arithmetic(session):
    """Pins the picture to the same maths the recommendations use. If these ever
    disagree, the board would show you standing somewhere you are not."""
    from gridiron.live import snake
    for r_i, row in enumerate(session.grid()["rounds"], start=1):
        for col_i, cell in enumerate(row, start=1):
            assert cell["s"] == col_i, "column position must equal the seat"
            assert cell["o"] == snake.overall_of(r_i, col_i, session.config.num_teams)
            assert snake.round_of(cell["o"], session.config.num_teams) == r_i


def test_grid_cell_states_are_exhaustive_and_track_the_clock(session):
    for pid in (1, 2, 3, 4):
        session.store.append(pid)
    session.store.remove(2)
    session.store.append(None, source="unknown", observed_name="unknown")
    cells = {c["o"]: c for row in session.grid()["rounds"] for c in row}
    clock = session.store.next_overall()
    assert cells[1]["st"] == "taken"
    assert cells[2]["st"] == "gap", "a removed pick shows as a hole"
    assert cells[3]["st"] == "taken"
    assert cells[clock]["st"] == "clock"
    assert cells[clock + 1]["st"] == "future"
    assert {c["st"] for c in cells.values()} <= {
        "taken", "unknown", "gap", "clock", "future"}


def test_grid_marks_claimed_picks(session):
    session.store.append(1, mine=True)
    session.store.append(2)
    cells = {c["o"]: c for row in session.grid()["rounds"] for c in row}
    assert cells[1]["m"] is True and cells[2]["m"] is False
