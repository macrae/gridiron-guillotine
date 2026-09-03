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
    """Every fixture player has bye 7, so my first pick makes the rest clash."""
    assert not any(r["bye_clash"] for r in session.state()["recs"])
    session.store.append(1, overall=3)            # overall 3 is my slot
    assert any(r["bye_clash"] for r in session.state()["recs"])


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
