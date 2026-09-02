"""The player pool: CSV in, queryable immutable objects out.

Pure stdlib, no I/O beyond the one CSV read. Everything downstream (vorp, vona,
recommend) operates on these objects and never touches the network.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

FANTASY_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DST")


@dataclass(frozen=True)
class Player:
    player_id: int
    name: str
    name_norm: str
    pos: str
    team: str
    bye_week: int
    proj_points: float
    adp: float
    espn_ppr_rank: int
    percent_owned: float
    injury_status: str
    eligible_pos: tuple[str, ...]
    # Filled in by vorp.compute_vorp once league settings are known.
    vorp: float = 0.0

    @property
    def draftable(self) -> bool:
        """A player projected at 0 (IR, suspended, deep depth) is never a candidate.

        Such players stay in the pool so the name matcher can resolve them if a
        leaguemate reaches -- an unmatchable pick is a louder failure than an
        unrecommendable player.
        """
        return self.proj_points > 0

    def is_injured(self) -> bool:
        return self.injury_status not in ("ACTIVE", "")


@dataclass
class PlayerPool:
    players: list[Player]
    by_id: dict[int, Player] = field(default_factory=dict)
    by_norm: dict[str, Player] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.reindex()

    def reindex(self) -> None:
        self.by_id = {p.player_id: p for p in self.players}
        # First writer wins: the pool is projection-sorted, so a duplicated
        # normalized name resolves to the more valuable player.
        self.by_norm = {}
        for p in self.players:
            self.by_norm.setdefault(p.name_norm, p)

    def available(self, drafted_ids: set[int]) -> list[Player]:
        return [p for p in self.players if p.player_id not in drafted_ids and p.draftable]

    def at_position(self, pos: str, drafted_ids: set[int]) -> list[Player]:
        """Available players at `pos`, best first by VORP."""
        out = [
            p
            for p in self.players
            if p.pos == pos and p.player_id not in drafted_ids and p.draftable
        ]
        out.sort(key=lambda p: -p.vorp)
        return out

    def as_rows(self) -> list[dict]:
        """Dict view for names.match()."""
        return [
            {"player_id": p.player_id, "name": p.name, "name_norm": p.name_norm,
             "pos": p.pos, "team": p.team}
            for p in self.players
        ]


def load_pool(csv_path: Path) -> PlayerPool:
    """Read a player_pool CSV written by espn.build()."""
    players: list[Player] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pos = row["pos"]
            if pos not in FANTASY_POSITIONS:
                continue  # hard filter: non-fantasy positions never enter valuation
            players.append(
                Player(
                    player_id=int(row["player_id"]),
                    name=row["name"],
                    name_norm=row["name_norm"],
                    pos=pos,
                    team=row["team"],
                    bye_week=int(row["bye_week"] or 0),
                    proj_points=float(row["proj_points"] or 0.0),
                    adp=float(row["adp"] or 0.0),
                    espn_ppr_rank=int(row["espn_ppr_rank"] or 0),
                    percent_owned=float(row["percent_owned"] or 0.0),
                    injury_status=row["injury_status"] or "ACTIVE",
                    eligible_pos=tuple((row["eligible_pos"] or pos).split("|")),
                )
            )
    if not players:
        raise ValueError(f"no fantasy-position players loaded from {csv_path}")
    players.sort(key=lambda p: -p.proj_points)
    return PlayerPool(players)
