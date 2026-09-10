"""SQLite-backed sheet storage. Every mutation is committed immediately."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .coltypes import OPTION_COLORS, ColumnType, decode, display, encode, parse

SCHEMA_VERSION = "1"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS columns (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    type     TEXT NOT NULL,
    options  TEXT NOT NULL DEFAULT '[]',
    colors   TEXT NOT NULL DEFAULT '{}',
    position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rows (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cells (
    row_id    INTEGER NOT NULL REFERENCES rows(id) ON DELETE CASCADE,
    column_id INTEGER NOT NULL REFERENCES columns(id) ON DELETE CASCADE,
    value     TEXT,
    PRIMARY KEY (row_id, column_id)
);
"""


@dataclass
class Column:
    id: int
    name: str
    type: ColumnType
    options: list[str] = field(default_factory=list)
    colors: dict[str, str] = field(default_factory=dict)
    position: int = 0

    def color(self, option: str | None) -> str | None:
        """The colour a dropdown option is shown in.

        A column that has never been given colours — one written before they
        existed — still gets them, taken from the palette in option order, so
        an old sheet looks the same as a new one without being rewritten.
        """
        if option is None:
            return None
        stored = self.colors.get(option)
        if stored in OPTION_COLORS:
            return stored
        if option in self.options:
            names = tuple(OPTION_COLORS)
            return names[self.options.index(option) % len(names)]
        return None


@dataclass
class Row:
    id: int
    position: int
    values: dict[int, Any] = field(default_factory=dict)


class Sheet:
    """A single table of data living in one SQLite file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists()
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(_SCHEMA)
        self._migrate()
        self.db.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        self.db.commit()
        if is_new or not self.columns():
            self._seed()

    def _migrate(self) -> None:
        """Bring a sheet written by an older version up to date."""
        present = {
            row["name"] for row in self.db.execute("PRAGMA table_info(columns)")
        }
        if "colors" not in present:
            self.db.execute(
                "ALTER TABLE columns ADD COLUMN colors TEXT NOT NULL DEFAULT '{}'"
            )
            self.db.commit()

    def close(self) -> None:
        self.db.close()

    def _seed(self) -> None:
        """Give a brand new file something to type into."""
        self.add_column("Name", ColumnType.TEXT)
        self.add_column("Done", ColumnType.BOOLEAN)
        self.add_row()

    # ------------------------------------------------------------------ reads

    def columns(self) -> list[Column]:
        rows = self.db.execute(
            "SELECT id, name, type, options, colors, position FROM columns "
            "ORDER BY position, id"
        ).fetchall()
        return [
            Column(
                id=r["id"],
                name=r["name"],
                type=ColumnType(r["type"]),
                options=json.loads(r["options"]),
                colors=json.loads(r["colors"] or "{}"),
                position=r["position"],
            )
            for r in rows
        ]

    def column(self, column_id: int) -> Column | None:
        for col in self.columns():
            if col.id == column_id:
                return col
        return None

    def rows(self) -> list[Row]:
        by_type = {c.id: c.type for c in self.columns()}
        result = [
            Row(id=r["id"], position=r["position"])
            for r in self.db.execute(
                "SELECT id, position FROM rows ORDER BY position, id"
            )
        ]
        index = {row.id: row for row in result}
        for cell in self.db.execute("SELECT row_id, column_id, value FROM cells"):
            row = index.get(cell["row_id"])
            coltype = by_type.get(cell["column_id"])
            if row is not None and coltype is not None:
                row.values[cell["column_id"]] = decode(coltype, cell["value"])
        return result

    def counts(self) -> tuple[int, int]:
        cols = self.db.execute("SELECT COUNT(*) AS n FROM columns").fetchone()["n"]
        rows = self.db.execute("SELECT COUNT(*) AS n FROM rows").fetchone()["n"]
        return cols, rows

    # -------------------------------------------------------------- mutations

    def add_column(
        self,
        name: str,
        coltype: ColumnType,
        options: list[str] | None = None,
        colors: dict[str, str] | None = None,
    ) -> Column:
        position = self.db.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM columns"
        ).fetchone()["p"]
        cursor = self.db.execute(
            "INSERT INTO columns (name, type, options, colors, position) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                name,
                coltype.value,
                json.dumps(options or []),
                json.dumps(colors or {}),
                position,
            ),
        )
        self.db.commit()
        return Column(
            cursor.lastrowid, name, coltype, options or [], colors or {}, position
        )

    def update_column(
        self,
        column_id: int,
        name: str,
        coltype: ColumnType,
        options: list[str] | None = None,
        colors: dict[str, str] | None = None,
    ) -> int:
        """Rename / retype a column. Returns how many cells were dropped in the process."""
        old = self.column(column_id)
        if old is None:
            raise KeyError(column_id)
        options = options or []
        dropped = 0

        if old.type is not coltype or (
            coltype is ColumnType.SELECT and options != old.options
        ):
            cells = self.db.execute(
                "SELECT row_id, value FROM cells WHERE column_id = ?", (column_id,)
            ).fetchall()
            for cell in cells:
                value = decode(old.type, cell["value"])
                if value is None:
                    continue
                try:
                    converted = parse(coltype, display(old.type, value), options)
                except Exception:
                    converted = None
                if converted is None:
                    dropped += 1
                self.db.execute(
                    "UPDATE cells SET value = ? WHERE row_id = ? AND column_id = ?",
                    (encode(coltype, converted), cell["row_id"], column_id),
                )

        self.db.execute(
            "UPDATE columns SET name = ?, type = ?, options = ?, colors = ? "
            "WHERE id = ?",
            (
                name,
                coltype.value,
                json.dumps(options),
                json.dumps(colors or {}),
                column_id,
            ),
        )
        self.db.commit()
        return dropped

    def delete_column(self, column_id: int) -> None:
        self.db.execute("DELETE FROM cells WHERE column_id = ?", (column_id,))
        self.db.execute("DELETE FROM columns WHERE id = ?", (column_id,))
        self.db.commit()
        self._renumber("columns")

    def move_column(self, column_id: int, offset: int) -> bool:
        cols = self.columns()
        index = next((i for i, c in enumerate(cols) if c.id == column_id), None)
        if index is None:
            return False
        target = index + offset
        if not 0 <= target < len(cols):
            return False
        cols[index], cols[target] = cols[target], cols[index]
        for position, col in enumerate(cols):
            self.db.execute(
                "UPDATE columns SET position = ? WHERE id = ?", (position, col.id)
            )
        self.db.commit()
        return True

    def add_row(self, after_position: int | None = None) -> int:
        if after_position is None:
            position = self.db.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM rows"
            ).fetchone()["p"]
        else:
            position = after_position + 1
            self.db.execute(
                "UPDATE rows SET position = position + 1 WHERE position >= ?",
                (position,),
            )
        cursor = self.db.execute("INSERT INTO rows (position) VALUES (?)", (position,))
        self.db.commit()
        return cursor.lastrowid

    def duplicate_row(self, row_id: int) -> int:
        """Copy a row's values into a new row directly below it."""
        row = next((r for r in self.rows() if r.id == row_id), None)
        if row is None:
            raise KeyError(row_id)
        copy_id = self.add_row(after_position=row.position)
        # Copying the stored text rather than the decoded values keeps every
        # type exactly as it was, junk in a retyped column included.
        self.db.execute(
            "INSERT INTO cells (row_id, column_id, value) "
            "SELECT ?, column_id, value FROM cells WHERE row_id = ?",
            (copy_id, row_id),
        )
        self.db.commit()
        return copy_id

    def delete_row(self, row_id: int) -> None:
        self.db.execute("DELETE FROM cells WHERE row_id = ?", (row_id,))
        self.db.execute("DELETE FROM rows WHERE id = ?", (row_id,))
        self.db.commit()
        self._renumber("rows")

    def set_cell(self, row_id: int, column_id: int, value: Any) -> None:
        col = self.column(column_id)
        if col is None:
            raise KeyError(column_id)
        self.db.execute(
            "INSERT INTO cells (row_id, column_id, value) VALUES (?, ?, ?) "
            "ON CONFLICT(row_id, column_id) DO UPDATE SET value = excluded.value",
            (row_id, column_id, encode(col.type, value)),
        )
        self.db.commit()

    def _renumber(self, table: str) -> None:
        ids = [
            r["id"]
            for r in self.db.execute(f"SELECT id FROM {table} ORDER BY position, id")
        ]
        for position, row_id in enumerate(ids):
            self.db.execute(
                f"UPDATE {table} SET position = ? WHERE id = ?", (position, row_id)
            )
        self.db.commit()
