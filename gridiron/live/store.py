"""Durable draft state.

The schema is the safety mechanism. Picks are keyed on `overall` as PRIMARY KEY
and carry a partial UNIQUE index on `uid`, so:

  - two players cannot occupy one pick slot, and
  - one player cannot occupy two pick slots.

That makes double-counting structurally impossible rather than something the
reconciliation code has to be careful about. Manual entry and Yahoo polling can
both run flat out; the worst case is a detected conflict, never silent
corruption.

Every mutation commits before the caller is told it succeeded, and also appends
to a JSONL audit log -- the recovery path if the database ever looks wrong
mid-draft.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

# Higher confidence wins a conflict at the same pick slot.
CONFIDENCE = {"yahoo": 100, "manual": 50, "unknown": 10}

SCHEMA = """
CREATE TABLE IF NOT EXISTS picks (
    overall       INTEGER PRIMARY KEY,
    round         INTEGER NOT NULL,
    slot          INTEGER NOT NULL,
    player_id     INTEGER,
    observed_name TEXT,
    source        TEXT NOT NULL DEFAULT 'manual',
    confidence    INTEGER NOT NULL DEFAULT 50,
    observed_at   REAL NOT NULL,
    -- Explicit, NOT derived from `slot`. In a fast draft you cannot reliably
    -- track which team took which player, and inferring ownership from snake
    -- position means one missed pick silently reassigns your whole roster.
    -- Marking a player gone and marking a player yours are separate acts.
    mine          INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS picks_player
    ON picks(player_id) WHERE player_id IS NOT NULL;
"""


@dataclass(frozen=True)
class Pick:
    overall: int
    round: int
    slot: int
    player_id: int | None
    observed_name: str | None
    source: str
    confidence: int
    observed_at: float
    mine: bool = False


class PickConflict(Exception):
    """A pick collided with an existing one. Surface it -- never swallow."""


class PickStore:
    def __init__(self, db_path: Path, num_teams: int, log_path: Path | None = None):
        self.db_path = Path(db_path)
        self.num_teams = num_teams
        self.log_path = log_path or self.db_path.with_suffix(".log.jsonl")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._undo: list[tuple[str, list[tuple]]] = []
        self._redo: list[tuple[str, list[tuple]]] = []
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    # -- undo / redo -------------------------------------------------------
    #
    # Snapshot the whole picks table before every mutation rather than tracking
    # inverse operations. A draft is at most ~180 rows, so a snapshot is cheap,
    # and it is correct by construction for EVERY operation -- append, remove,
    # correct, claim, release, skip -- including ones whose inverse is awkward
    # to express. Inverse-op tracking is where undo implementations get subtly
    # wrong, and this is not the week to find that out.

    UNDO_DEPTH = 60

    def _columns(self) -> list[str]:
        return [r["name"] for r in self.conn.execute("PRAGMA table_info(picks)")]

    def _dump(self) -> list[tuple]:
        return [tuple(r) for r in self.conn.execute(
            "SELECT * FROM picks ORDER BY overall").fetchall()]

    def _load(self, rows: list[tuple]) -> None:
        cols = self._columns()
        ph = ",".join("?" * len(cols))
        with self.conn:
            self.conn.execute("DELETE FROM picks")
            if rows:
                self.conn.executemany(
                    f"INSERT INTO picks({','.join(cols)}) VALUES({ph})", rows)

    def checkpoint(self, label: str) -> None:
        """Record the state BEFORE a mutation. Clears the redo branch, because
        acting after an undo makes the old forward history unreachable."""
        self._undo.append((label, self._dump()))
        del self._undo[:-self.UNDO_DEPTH]
        self._redo.clear()

    def undo(self) -> str | None:
        """Step back one operation. Returns its label, or None if nothing to undo."""
        if not self._undo:
            return None
        label, rows = self._undo.pop()
        self._redo.append((label, self._dump()))
        self._load(rows)
        self._log("undo", label=label)
        return label

    def redo(self) -> str | None:
        if not self._redo:
            return None
        label, rows = self._redo.pop()
        self._undo.append((label, self._dump()))
        self._load(rows)
        self._log("redo", label=label)
        return label

    @property
    def undo_label(self) -> str | None:
        return self._undo[-1][0] if self._undo else None

    @property
    def redo_label(self) -> str | None:
        return self._redo[-1][0] if self._redo else None

    def _migrate(self) -> None:
        """Add columns to a database created by an earlier version."""
        cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(picks)")}
        if "mine" not in cols:
            self.conn.execute(
                "ALTER TABLE picks ADD COLUMN mine INTEGER NOT NULL DEFAULT 0")

    # -- internals ---------------------------------------------------------

    def _log(self, op: str, **fields) -> None:
        rec = {"op": op, "ts": time.time(), **fields}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    def _row_to_pick(self, r: sqlite3.Row) -> Pick:
        return Pick(
            overall=r["overall"], round=r["round"], slot=r["slot"],
            player_id=r["player_id"], observed_name=r["observed_name"],
            source=r["source"], confidence=r["confidence"], observed_at=r["observed_at"],
            mine=bool(r["mine"]),
        )

    # -- reads -------------------------------------------------------------

    def snapshot(self) -> list[Pick]:
        rows = self.conn.execute("SELECT * FROM picks ORDER BY overall").fetchall()
        return [self._row_to_pick(r) for r in rows]

    def drafted_ids(self) -> set[int]:
        rows = self.conn.execute(
            "SELECT player_id FROM picks WHERE player_id IS NOT NULL"
        ).fetchall()
        return {r["player_id"] for r in rows}

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) AS n FROM picks").fetchone()["n"]

    def next_overall(self) -> int:
        """The next unfilled pick slot -- the team on the clock.

        Uses max+1 rather than count+1 so a gap (a pick recorded out of order by
        the Yahoo poller) does not silently rewind the clock.
        """
        row = self.conn.execute("SELECT MAX(overall) AS m FROM picks").fetchone()
        return (row["m"] or 0) + 1

    def picks_for_slot(self, slot: int) -> list[Pick]:
        rows = self.conn.execute(
            "SELECT * FROM picks WHERE slot = ? ORDER BY overall", (slot,)
        ).fetchall()
        return [self._row_to_pick(r) for r in rows]

    # -- mutations ---------------------------------------------------------

    def my_players(self) -> list[int]:
        rows = self.conn.execute(
            "SELECT player_id FROM picks WHERE mine = 1 AND player_id IS NOT NULL"
            " ORDER BY overall").fetchall()
        return [r["player_id"] for r in rows]

    def set_mine(self, overall: int, mine: bool = True) -> None:
        """Flag or unflag a recorded pick as yours, after the fact."""
        with self.conn:
            self.conn.execute("UPDATE picks SET mine = ? WHERE overall = ?",
                              (1 if mine else 0, overall))
        self._log("set_mine", overall=overall, mine=mine)

    def append(
        self,
        player_id: int | None,
        overall: int | None = None,
        source: str = "manual",
        observed_name: str | None = None,
        mine: bool = False,
    ) -> Pick:
        """Record a player as gone. `mine=True` also claims them for your roster.

        `overall` defaults to the next open slot -- it is a running count, not an
        assertion about which team picked.
        """
        from . import snake

        overall = overall or self.next_overall()
        rnd = snake.round_of(overall, self.num_teams)
        slot = snake.slot_on_clock(overall, self.num_teams)
        conf = CONFIDENCE.get(source, 50)
        now = time.time()

        if player_id is not None:
            existing = self.conn.execute(
                "SELECT overall FROM picks WHERE player_id = ?", (player_id,)
            ).fetchone()
            if existing and existing["overall"] != overall:
                raise PickConflict(
                    f"player {player_id} is already recorded at pick {existing['overall']}"
                )

        prior = self.conn.execute(
            "SELECT * FROM picks WHERE overall = ?", (overall,)
        ).fetchone()
        if prior is not None and prior["confidence"] > conf:
            raise PickConflict(
                f"pick {overall} already held by a higher-confidence source "
                f"({prior['source']})"
            )

        with self.conn:
            self.conn.execute(
                "INSERT INTO picks(overall, round, slot, player_id, observed_name,"
                " source, confidence, observed_at, mine) VALUES(?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(overall) DO UPDATE SET"
                "  player_id=excluded.player_id, observed_name=excluded.observed_name,"
                "  source=excluded.source, confidence=excluded.confidence,"
                "  observed_at=excluded.observed_at, mine=excluded.mine",
                (overall, rnd, slot, player_id, observed_name, source, conf, now,
                 1 if mine else 0),
            )
        self._log("append", overall=overall, player_id=player_id, source=source,
                  observed_name=observed_name, mine=mine)
        return Pick(overall, rnd, slot, player_id, observed_name, source, conf, now, mine)

    def undo_last(self) -> Pick | None:
        row = self.conn.execute(
            "SELECT * FROM picks ORDER BY overall DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        pick = self._row_to_pick(row)
        with self.conn:
            self.conn.execute("DELETE FROM picks WHERE overall = ?", (pick.overall,))
        self._log("undo", overall=pick.overall, player_id=pick.player_id)
        return pick

    def correct(self, overall: int, player_id: int) -> Pick:
        """Fix one recorded pick without disturbing anything after it.

        The important edit: realising at pick 40 that pick 33 was wrong must not
        cost seven undos. Overall numbers never renumber, so nothing downstream
        shifts.
        """
        row = self.conn.execute(
            "SELECT * FROM picks WHERE overall = ?", (overall,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no pick recorded at {overall}")
        clash = self.conn.execute(
            "SELECT overall FROM picks WHERE player_id = ? AND overall != ?",
            (player_id, overall),
        ).fetchone()
        if clash:
            raise PickConflict(
                f"player {player_id} is already recorded at pick {clash['overall']}"
            )
        with self.conn:
            self.conn.execute(
                "UPDATE picks SET player_id = ?, observed_name = NULL WHERE overall = ?",
                (player_id, overall),
            )
        self._log("correct", overall=overall, player_id=player_id,
                  was=row["player_id"])
        return self._row_to_pick(
            self.conn.execute("SELECT * FROM picks WHERE overall = ?", (overall,)).fetchone()
        )

    def remove(self, overall: int) -> Pick | None:
        """Delete one pick, leaving its slot EMPTY. Returns what was removed.

        Distinct from delete_shift, which renumbers everything after it. A
        misclick means the wrong player sits in a slot that genuinely happened,
        so the slot must stay: gaps() then surfaces it as refillable and every
        other pick keeps its position. Renumbering mid-draft would be far worse
        than the mistake being fixed.
        """
        row = self.conn.execute(
            "SELECT * FROM picks WHERE overall = ?", (overall,)
        ).fetchone()
        if row is None:
            return None
        pick = self._row_to_pick(row)
        with self.conn:
            self.conn.execute("DELETE FROM picks WHERE overall = ?", (overall,))
        self._log("remove", overall=overall, player_id=pick.player_id)
        return pick

    def delete_shift(self, overall: int) -> None:
        """Remove a pick that never happened, pulling everything after it back."""
        from . import snake

        with self.conn:
            self.conn.execute("DELETE FROM picks WHERE overall = ?", (overall,))
            later = self.conn.execute(
                "SELECT * FROM picks WHERE overall > ? ORDER BY overall", (overall,)
            ).fetchall()
            for r in later:
                new = r["overall"] - 1
                self.conn.execute(
                    "UPDATE picks SET overall = ?, round = ?, slot = ? WHERE overall = ?",
                    (new, snake.round_of(new, self.num_teams),
                     snake.slot_on_clock(new, self.num_teams), r["overall"]),
                )
        self._log("delete_shift", overall=overall)

    def reset(self) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM picks")
        self._log("reset")

    def close(self) -> None:
        self.conn.close()
