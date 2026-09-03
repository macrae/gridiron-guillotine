"""League scoring, applied to raw component projections.

ESPN's `appliedTotal` is ITS scoring: full PPR, 4-point passing TDs. That
matches some leagues and not others, and a passing-TD difference alone moves a
quarterback by 40-65 points -- far more than any modelling refinement elsewhere
in this codebase.

So projections are rebuilt from the component sidecar (`raw_stats_latest.csv`)
under each league's actual rules. Rebuilding at 4-point passing TDs reproduces
ESPN's own number within ~1.5 points, which is the check that says the
components can be trusted; the residual is sacks, 2-point conversions and
return TDs, which ESPN includes and the sidecar does not.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

#: Games in a season. Season projections already price in expected missed time,
#: so dividing by 17 gives yards per SCHEDULED game. For a player projected to
#: miss games this understates his per-game rate, which makes the bonus estimate
#: conservative for injury-prone players -- the safe direction to be wrong.
GAMES = 17

#: Coefficient of variation of single-game yardage, by position. Passing yardage
#: is far steadier week to week than rushing or receiving, so one shared CV would
#: badly misprice the 350/450 passing bonuses against the 100/150 rushing and
#: receiving ones.
CV_BY_POS = {"QB": 0.30, "RB": 0.55, "WR": 0.65, "TE": 0.70}
CV_DEFAULT = 0.60


@dataclass
class ScoringRules:
    """Per-league scoring. Only the fields that actually differ between
    real leagues -- this is not a general fantasy scoring engine."""

    name: str = "yahoo_default"
    pass_yds_per_pt: float = 25.0
    pass_td: float = 4.0
    interception: float = -1.0
    rush_yds_per_pt: float = 10.0
    rush_td: float = 6.0
    reception: float = 1.0            # full PPR
    rec_yds_per_pt: float = 10.0
    rec_td: float = 6.0
    fumble_lost: float = -2.0
    #: Per-GAME yardage bonuses, e.g. {350: 5.0, 450: 5.0}. Estimating their
    #: value needs a game-level distribution, which the season totals do not
    #: carry -- see `bonus_note`. Recorded here so the rules stay honest about
    #: what the league actually pays, even when the estimate is off.
    pass_bonus: dict[int, float] = field(default_factory=dict)
    rush_bonus: dict[int, float] = field(default_factory=dict)
    rec_bonus: dict[int, float] = field(default_factory=dict)

    @property
    def has_bonuses(self) -> bool:
        return bool(self.pass_bonus or self.rush_bonus or self.rec_bonus)


#: 12-team, QB/WR/WR/RB/RB/TE/FLEX/K/DEF + 5 BN. Six-point passing TDs and
#: per-game yardage bonuses -- the highest-ceiling scoring of the two.
TWO_MINUTE_DRILL = ScoringRules(
    name="2MinuteDrill",
    pass_td=6.0,
    pass_bonus={350: 5.0, 450: 5.0},
    rush_bonus={100: 5.0, 150: 5.0},
    rec_bonus={100: 5.0, 150: 5.0},
)

#: 10-team, QB/WR/WR/WR/RB/RB/TE/FLEX/K/DEF + 6 BN. Standard scoring; matches
#: ESPN's own assumptions, so its projections need no adjustment.
FIRST_DOWN = ScoringRules(name="FirstDown", pass_td=4.0)

PRESETS = {r.name: r for r in (TWO_MINUTE_DRILL, FIRST_DOWN, ScoringRules())}


def _f(row: dict, key: str) -> float:
    return float(row.get(key) or 0.0)


def _lower_regularized(s: float, z: float) -> float:
    """Regularized lower incomplete gamma P(s, z). Stdlib only."""
    if z <= 0:
        return 0.0
    if z < s + 1:                      # series expansion
        term = 1.0 / s
        total = term
        for n in range(1, 400):
            term *= z / (s + n)
            total += term
            if abs(term) < abs(total) * 1e-12:
                break
        return total * math.exp(-z + s * math.log(z) - math.lgamma(s))
    tiny = 1e-300                      # continued fraction for the upper tail
    b = z + 1 - s
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 400):
        an = -i * (i - s)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-12:
            break
    return 1.0 - math.exp(-z + s * math.log(z) - math.lgamma(s)) * h


def p_game_at_least(mean_per_game: float, threshold: float, cv: float) -> float:
    """P(a single game clears `threshold` yards).

    Gamma is the right shape for per-game yardage: non-negative and
    right-skewed. Season totals cannot recover the true game-by-game
    distribution, so this is an estimate -- but the ORDERING it produces is
    stable across any plausible CV, even though the level is not.
    """
    if mean_per_game <= 0 or threshold <= 0:
        return 0.0
    shape = 1.0 / (cv * cv)
    scale = mean_per_game / shape
    return 1.0 - _lower_regularized(shape, threshold / scale)


def expected_bonus(row: dict, pos: str, rules: ScoringRules) -> float:
    """Expected season points from per-game yardage bonuses.

    Rushing and receiving yards share a threshold, so they are summed before
    the probability is taken -- a back with 60 rushing and 45 receiving yards
    has a real shot at 100 combined, and scoring them separately would miss it
    entirely. That is also why these bonuses tilt toward running backs.
    """
    if not rules.has_bonuses:
        return 0.0
    cv = CV_BY_POS.get(pos, CV_DEFAULT)
    total = 0.0
    if rules.pass_bonus:
        ypg = _f(row, "pass_yds") / GAMES
        for thresh, pts in rules.pass_bonus.items():
            total += GAMES * pts * p_game_at_least(ypg, thresh, CV_BY_POS["QB"])
    scrimmage = rules.rush_bonus or rules.rec_bonus
    if scrimmage:
        ypg = (_f(row, "rush_yds") + _f(row, "rec_yds")) / GAMES
        for thresh, pts in scrimmage.items():
            total += GAMES * pts * p_game_at_least(ypg, thresh, cv)
    return total


def score_components(row: dict, rules: ScoringRules) -> float:
    """Season projected points under `rules`, excluding per-game bonuses."""
    return (
        _f(row, "pass_yds") / rules.pass_yds_per_pt
        + rules.pass_td * _f(row, "pass_td")
        + rules.interception * _f(row, "interceptions")
        + _f(row, "rush_yds") / rules.rush_yds_per_pt
        + rules.rush_td * _f(row, "rush_td")
        + rules.reception * _f(row, "receptions")
        + _f(row, "rec_yds") / rules.rec_yds_per_pt
        + rules.rec_td * _f(row, "rec_td")
        + rules.fumble_lost * _f(row, "fumbles_lost")
    )


def load_components(path: Path) -> dict[int, dict]:
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return {int(r["player_id"]): r for r in csv.DictReader(fh)}


def rescore_pool(pool_csv: Path, raw_csv: Path, rules: ScoringRules,
                 out_csv: Path) -> tuple[Path, int, int]:
    """Rewrite a pool CSV with `proj_points` recomputed under `rules`.

    Players with no component row (kickers and defenses -- ESPN does not expose
    their components) keep ESPN's number. That is correct for K/DST here: both
    leagues use close-to-default kicking and DST scoring, and neither position
    is where drafts are won.

    Returns (path, rescored_count, kept_count).
    """
    comps = load_components(raw_csv)
    rescored = kept = 0
    with Path(pool_csv).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fields = reader.fieldnames or []
        rows = list(reader)

    for row in rows:
        comp = comps.get(int(row["player_id"]))
        if comp is None or row["pos"] in ("K", "DST"):
            kept += 1
            continue
        pts = score_components(comp, rules)
        pts += expected_bonus(comp, row["pos"], rules)
        row["proj_points"] = f"{pts:.2f}"
        rescored += 1

    # Re-rank on the new numbers; the board's ordering is scoring-dependent.
    rows.sort(key=lambda r: -float(r["proj_points"]))
    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return out, rescored, kept


def bonus_note(rules: ScoringRules) -> str:
    """What the bonus estimate is, and how much to trust it."""
    if not rules.has_bonuses:
        return ""
    return (
        f"{rules.name} pays per-game yardage bonuses "
        f"(pass {rules.pass_bonus}, scrimmage {rules.rush_bonus or rules.rec_bonus}). "
        "These ARE included, as a gamma estimate over per-game yardage -- season "
        "totals cannot recover the true distribution, so the level is uncertain "
        "even though the ordering is stable. They favour high-volume backs, who "
        "reach the shared rushing+receiving threshold most often."
    )
