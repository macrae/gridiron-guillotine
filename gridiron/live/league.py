"""League configuration, from a file or from flags.

Yahoo was only ever the convenient way to discover these numbers. It is not the
only way, and it must never be the blocking way -- a league whose settings live
in a JSON file works identically to one hydrated from the API, and works when
the API does not.

Roster shape matters more than it looks: replacement level is derived from it
(vorp.replacement_ranks), so a league with two flex slots or no kicker produces
genuinely different rankings. Getting this wrong is a silent miscalibration, not
an error.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .vorp import LeagueConfig

#: Yahoo's default full-PPR lineup: QB, RB, RB, WR, WR, TE, W/R/T, K, DEF + 6 BN.
YAHOO_STANDARD = {
    "starters": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DST": 1},
    "flex_count": 1,
    "max_at_pos": {"QB": 1, "RB": 6, "WR": 7, "TE": 2, "K": 1, "DST": 1},
}


def default_config(num_teams: int = 12, rounds: int = 15, my_slot: int = 1) -> LeagueConfig:
    return LeagueConfig(
        num_teams=num_teams, rounds=rounds, my_slot=my_slot,
        starters=dict(YAHOO_STANDARD["starters"]),
        flex_count=YAHOO_STANDARD["flex_count"],
        max_at_pos=dict(YAHOO_STANDARD["max_at_pos"]),
    )


def load_config(path: Path) -> LeagueConfig:
    """Read a league JSON. Unspecified keys fall back to the Yahoo standard."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cfg = default_config(
        num_teams=int(raw.get("num_teams", 12)),
        rounds=int(raw.get("rounds", 15)),
        my_slot=int(raw.get("my_slot", 1)),
    )
    if "starters" in raw:
        cfg.starters = {k: int(v) for k, v in raw["starters"].items()}
    if "flex_count" in raw:
        cfg.flex_count = int(raw["flex_count"])
    if "max_at_pos" in raw:
        cfg.max_at_pos = {k: int(v) for k, v in raw["max_at_pos"].items()}
    validate(cfg)
    return cfg


def save_config(cfg: LeagueConfig, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


class ConfigError(ValueError):
    """The league settings are internally inconsistent. Fail loudly."""


def validate(cfg: LeagueConfig) -> None:
    """Catch settings that would silently miscalibrate replacement level."""
    if not 2 <= cfg.num_teams <= 32:
        raise ConfigError(f"num_teams {cfg.num_teams} out of range")
    if not 1 <= cfg.my_slot <= cfg.num_teams:
        raise ConfigError(f"my_slot {cfg.my_slot} not in 1..{cfg.num_teams}")
    if cfg.rounds < 1:
        raise ConfigError("rounds must be >= 1")

    starting = sum(cfg.starters.values()) + cfg.flex_count
    if starting > cfg.rounds:
        raise ConfigError(
            f"{starting} starting slots but only {cfg.rounds} rounds -- "
            "the draft cannot fill the lineup")
    for pos, n in cfg.starters.items():
        cap = cfg.max_at_pos.get(pos, 0)
        if cap < n:
            raise ConfigError(
                f"{pos}: cap {cap} is below the {n} starter slot(s) -- "
                "the lineup could never be filled")


def describe(cfg: LeagueConfig) -> str:
    """One line, so a miscalibrated league is visible at launch."""
    lineup = " ".join(
        f"{p}{n}" for p, n in cfg.starters.items() if n
    ) + (f" FLEX{cfg.flex_count}" if cfg.flex_count else "")
    bench = cfg.rounds - sum(cfg.starters.values()) - cfg.flex_count
    return (f"{cfg.num_teams}-team, {cfg.rounds} rounds, slot {cfg.my_slot} | "
            f"{lineup} | {bench} bench")
