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
from dataclasses import dataclass, field
from pathlib import Path


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
        row["proj_points"] = f"{score_components(comp, rules):.2f}"
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
    """Why bonuses are recorded but not scored."""
    if not rules.has_bonuses:
        return ""
    return (
        f"{rules.name} pays per-game yardage bonuses "
        f"(pass {rules.pass_bonus}, rush {rules.rush_bonus}, rec {rules.rec_bonus}). "
        "These are NOT in the projections: they depend on the game-by-game "
        "distribution, and season totals cannot recover it. They reward "
        "high-ceiling players, so treat boom/bust profiles as slightly "
        "undervalued on this board."
    )
