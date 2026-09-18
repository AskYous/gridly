"""SQLite-backed sheet storage. Every mutation is committed immediately."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from . import arithmetic
from .coltypes import (
    OPTION_COLORS,
    ColumnType,
    ValidationError,
    decode,
    display,
    encode,
    parse,
)
from .formulas import (
    Formula,
    read_sum,
    reading_order,
    reads_of,
    sum_text,
    value_of,
)

SCHEMA_VERSION = "1"

# How many changes can be taken back. Each one holds a copy of the sheet.
UNDO_LIMIT = 40

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
    unique_  INTEGER NOT NULL DEFAULT 0,
    format   TEXT NOT NULL DEFAULT '',
    formula  TEXT NOT NULL DEFAULT '',
    align    TEXT NOT NULL DEFAULT '',
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
    #: No two rows may hold the same value. Empty cells are not compared.
    unique: bool = False
    #: How the type writes itself, where it has a choice — see the type's own
    #: formats, such as TIME_FORMATS.
    format: str = ""
    #: An encoded Formula, for a column that is worked out rather than typed in.
    formula: str = ""
    #: Where the values sit across the column — left, center or right. Empty
    #: leaves it to the type, which is what every column did before this.
    align: str = ""
    position: int = 0

    @property
    def computed(self) -> Formula | None:
        """What works this column out, or nothing if it is typed in."""
        return Formula.decode(self.formula)

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
        self._undo: list[tuple[str, tuple]] = []
        self._redo: list[tuple[str, tuple]] = []
        self._pending: str | None = None
        self._migrate()
        self.db.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
            (SCHEMA_VERSION,),
        )
        self.db.commit()
        if is_new or not self.columns():
            self._seed()
        self._undo.clear()  # a brand new sheet has nothing to go back to

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
        if "unique_" not in present:
            self.db.execute(
                "ALTER TABLE columns ADD COLUMN unique_ INTEGER NOT NULL DEFAULT 0"
            )
            self.db.commit()
        if "format" not in present:
            self.db.execute(
                "ALTER TABLE columns ADD COLUMN format TEXT NOT NULL DEFAULT ''"
            )
            self.db.commit()
        if "formula" not in present:
            self.db.execute(
                "ALTER TABLE columns ADD COLUMN formula TEXT NOT NULL DEFAULT ''"
            )
            self.db.commit()
        if "align" not in present:
            self.db.execute(
                "ALTER TABLE columns ADD COLUMN align TEXT NOT NULL DEFAULT ''"
            )
            self.db.commit()

    def close(self) -> None:
        self.db.close()

    def _seed(self) -> None:
        """Give a brand new file something to type into."""
        self.add_column("Name", ColumnType.TEXT)
        self.add_column("Done", ColumnType.BOOLEAN)
        self.add_row()

    # ------------------------------------------------------------------ undo

    #: The tables a snapshot covers, in the order they can be put back.
    _TABLES = ("columns", "rows", "cells")

    def _capture(self) -> tuple:
        """Everything in the sheet, as plain rows.

        Every field of every table, rather than a list of names — a snapshot
        that names its columns is one more place to forget when a new one is
        added, and forgetting it means undo quietly drops the field.
        """
        return tuple(
            [tuple(r) for r in self.db.execute(f"SELECT * FROM {table}")]
            for table in self._TABLES
        )

    def _put_back(self, state: tuple) -> None:
        for table in reversed(self._TABLES):        # cells reference the rest
            self.db.execute(f"DELETE FROM {table}")
        for table, saved in zip(self._TABLES, state):
            if not saved:
                continue
            places = ", ".join("?" * len(saved[0]))
            self.db.executemany(f"INSERT INTO {table} VALUES ({places})", saved)
        self.db.commit()

    def _checkpoint(self, label: str) -> None:
        """Remember how things look before a change, unless one is under way."""
        if self._pending is not None:
            return
        self._undo.append((label, self._capture()))
        del self._undo[:-UNDO_LIMIT]
        self._redo.clear()

    @contextmanager
    def change(self, label: str):
        """Group a run of edits so they are taken back together."""
        self._checkpoint(label)
        outer, self._pending = self._pending, label
        try:
            yield
        finally:
            self._pending = outer

    @property
    def undoable(self) -> str | None:
        return self._undo[-1][0] if self._undo else None

    @property
    def redoable(self) -> str | None:
        return self._redo[-1][0] if self._redo else None

    def undo(self) -> str | None:
        """Take the last change back. Returns what it was, or None."""
        if not self._undo:
            return None
        label, state = self._undo.pop()
        self._redo.append((label, self._capture()))
        self._put_back(state)
        return label

    def redo(self) -> str | None:
        if not self._redo:
            return None
        label, state = self._redo.pop()
        self._undo.append((label, self._capture()))
        self._put_back(state)
        return label

    # ------------------------------------------------------------------ reads

    def columns(self) -> list[Column]:
        rows = self.db.execute(
            "SELECT id, name, type, options, colors, unique_, format, formula, "
            "align, position "
            "FROM columns "
            "ORDER BY position, id"
        ).fetchall()
        return [
            Column(
                id=r["id"],
                name=r["name"],
                type=ColumnType(r["type"]),
                options=json.loads(r["options"]),
                colors=json.loads(r["colors"] or "{}"),
                unique=bool(r["unique_"]),
                format=r["format"],
                formula=r["formula"],
                align=r["align"],
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
        columns = self.columns()
        by_type = {c.id: c.type for c in columns}
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
        self._work_out(columns, result)
        return result

    def _work_out(self, columns: list[Column], rows: list[Row]) -> None:
        """Fill in every computed column, from the columns they read.

        Done here, on the way out, rather than written into cells — so a month
        can never be left standing next to a date that has since moved. A source
        that has gone, or is no longer a date, leaves the column empty rather
        than complaining, and so does a value the column's own type refuses.

        Columns are worked out in the order they read each other, so a sum over
        a column that is itself a sum sees the answer rather than the blank it
        started as.
        """
        found = {column.id: column for column in columns}
        sums = {
            column.id: read_sum(column.computed.expr, columns)
            for column in columns
            if column.computed is not None and column.computed.fn == "sum"
        }
        # Every computed column starts empty, so one that never comes up — a
        # ring of them, or a sum that will not read — shows nothing at all.
        for column in columns:
            if column.computed is not None:
                for row in rows:
                    row.values[column.id] = None

        for column in reading_order(columns, sums):
            spec = column.computed
            source = found.get(spec.source)
            for row in rows:
                if spec.fn == "sum":
                    raw = sum_text(sums[column.id], columns, row.values)
                elif source is None:
                    raw = ""
                else:
                    raw = value_of(spec, source.type, row.values.get(source.id))
                try:
                    row.values[column.id] = parse(
                        column.type, raw, column.options, column.format
                    )
                except ValidationError:
                    row.values[column.id] = None

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
        unique: bool = False,
        fmt: str = "",
        formula: str = "",
        align: str = "",
    ) -> Column:
        self._checkpoint(f"add column {name!r}")
        position = self.db.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM columns"
        ).fetchone()["p"]
        cursor = self.db.execute(
            "INSERT INTO columns "
            "(name, type, options, colors, unique_, format, formula, align, "
            "position) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                coltype.value,
                json.dumps(options or []),
                json.dumps(colors or {}),
                int(unique),
                fmt,
                formula,
                align,
                position,
            ),
        )
        self.db.commit()
        return Column(
            cursor.lastrowid, name, coltype, options or [], colors or {},
            unique, fmt, formula, align, position,
        )

    def update_column(
        self,
        column_id: int,
        name: str,
        coltype: ColumnType,
        options: list[str] | None = None,
        colors: dict[str, str] | None = None,
        unique: bool = False,
        renames: dict[str, str] | None = None,
        fmt: str = "",
        formula: str = "",
        align: str = "",
    ) -> int:
        """Rename / retype a column. Returns how many cells were dropped in the process."""
        old = self.column(column_id)
        if old is None:
            raise KeyError(column_id)
        self._checkpoint(f"edit column {old.name!r}")
        options = options or []
        dropped = 0
        if name != old.name:
            self._follow_rename(old.name, name, column_id)

        # An option that was renamed takes its values with it. Without this,
        # every cell holding the old wording fails to match the new options and
        # is cleared — losing data for what was meant to be a wording change.
        if renames:
            for cell in self.db.execute(
                "SELECT row_id, value FROM cells WHERE column_id = ?", (column_id,)
            ).fetchall():
                if cell["value"] in renames:
                    self.db.execute(
                        "UPDATE cells SET value = ? WHERE row_id = ? AND column_id = ?",
                        (renames[cell["value"]], cell["row_id"], column_id),
                    )

        if formula:
            # A computed column keeps no cells: whatever was typed in here
            # before is gone rather than converted, since nothing would ever
            # show it again. Undo still has it.
            self.db.execute("DELETE FROM cells WHERE column_id = ?", (column_id,))
        elif old.type is not coltype or (
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
                    converted = parse(
                        coltype, display(old.type, value, old.format), options, fmt
                    )
                except Exception:
                    converted = None
                if converted is None:
                    dropped += 1
                self.db.execute(
                    "UPDATE cells SET value = ? WHERE row_id = ? AND column_id = ?",
                    (encode(coltype, converted), cell["row_id"], column_id),
                )

        self.db.execute(
            "UPDATE columns SET name = ?, type = ?, options = ?, colors = ?, "
            "unique_ = ?, format = ?, formula = ?, align = ? WHERE id = ?",
            (
                name,
                coltype.value,
                json.dumps(options),
                json.dumps(colors or {}),
                int(unique),
                fmt,
                formula,
                align,
                column_id,
            ),
        )
        self.db.commit()
        return dropped

    def _follow_rename(self, was: str, now: str, renamed: int) -> None:
        """Point every sum that reads a column at its new name.

        A sum names the columns it reads, so a rename would otherwise leave it
        naming something that is not there any more — for a change that was only
        ever about the wording.
        """
        columns = self.columns()
        names = [column.name for column in columns]
        for column in columns:
            spec = column.computed
            if column.id == renamed or spec is None or spec.fn != "sum":
                continue
            rewritten = arithmetic.rename(spec.expr, names, was, now)
            if rewritten != spec.expr:
                self.db.execute(
                    "UPDATE columns SET formula = ? WHERE id = ?",
                    (replace(spec, expr=rewritten).encode(), column.id),
                )

    def delete_column(self, column_id: int) -> list[str]:
        """Remove a column. Returns the computed columns it was feeding.

        Those are left standing as ordinary empty columns rather than quietly
        working nothing out, so what they lost is something you can see.
        """
        gone = self.column(column_id)
        self._checkpoint(f"delete column {gone.name!r}" if gone else "delete column")
        columns = self.columns()
        orphaned = [
            column
            for column in columns
            if column.computed is not None
            and column.id != column_id
            and column_id
            in reads_of(column, read_sum(column.computed.expr, columns), columns)
        ]
        for column in orphaned:
            self.db.execute(
                "UPDATE columns SET formula = '' WHERE id = ?", (column.id,)
            )
        self.db.execute("DELETE FROM cells WHERE column_id = ?", (column_id,))
        self.db.execute("DELETE FROM columns WHERE id = ?", (column_id,))
        self.db.commit()
        self._renumber("columns")
        return [column.name for column in orphaned]

    def move_column(self, column_id: int, offset: int) -> bool:
        self._checkpoint("move column")
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

    def move_row(self, row_id: int, offset: int) -> bool:
        """Swap a row with the one beside it. False if there is none."""
        self._checkpoint("move row")
        rows = self.rows()
        index = next((i for i, r in enumerate(rows) if r.id == row_id), None)
        if index is None:
            return False
        target = index + offset
        if not 0 <= target < len(rows):
            return False
        rows[index], rows[target] = rows[target], rows[index]
        for position, row in enumerate(rows):
            self.db.execute(
                "UPDATE rows SET position = ? WHERE id = ?", (position, row.id)
            )
        self.db.commit()
        return True

    def add_row(self, after_position: int | None = None) -> int:
        self._checkpoint("add row")
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

    # ---------------------------------------------------------- uniqueness

    def holder_of(self, column_id: int, value: Any, ignoring: int = 0) -> int | None:
        """Which row already has this value in this column, if any.

        An empty cell is not a value, so any number of rows may have one.
        Returns the row's number as shown in the grid, counting from one.
        """
        column = self.column(column_id)
        if column is None or not column.unique or value is None:
            return None
        for number, row in enumerate(self.rows(), start=1):
            if row.id != ignoring and row.values.get(column_id) == value:
                return number
        return None

    def repeats_in(self, column_id: int) -> list[Any]:
        """Values this column holds more than once — what stops it being unique."""
        seen: dict[Any, int] = {}
        for row in self.rows():
            value = row.values.get(column_id)
            if value is not None:
                seen[value] = seen.get(value, 0) + 1
        return [value for value, count in seen.items() if count > 1]

    def duplicate_row(self, row_id: int) -> int:
        """Copy a row's values into a new row directly below it."""
        with self.change("duplicate row"):
            return self._duplicate_row(row_id)

    def _duplicate_row(self, row_id: int) -> int:
        row = next((r for r in self.rows() if r.id == row_id), None)
        if row is None:
            raise KeyError(row_id)
        copy_id = self.add_row(after_position=row.position)
        # Copying the stored text rather than the decoded values keeps every
        # type exactly as it was, junk in a retyped column included. A column
        # that has to be unique is left empty instead — a copy of it would be
        # the one thing the column does not allow.
        unique = [c.id for c in self.columns() if c.unique]
        skip = ",".join("?" * len(unique))
        self.db.execute(
            "INSERT INTO cells (row_id, column_id, value) "
            "SELECT ?, column_id, value FROM cells WHERE row_id = ? "
            f"AND column_id NOT IN ({skip})",
            (copy_id, row_id, *unique),
        )
        self.db.commit()
        return copy_id

    def delete_row(self, row_id: int) -> None:
        self._checkpoint("delete row")
        self.db.execute("DELETE FROM cells WHERE row_id = ?", (row_id,))
        self.db.execute("DELETE FROM rows WHERE id = ?", (row_id,))
        self.db.commit()
        self._renumber("rows")

    def set_cell(self, row_id: int, column_id: int, value: Any) -> None:
        # Both refusals come before the checkpoint: a change that never
        # happened is not one to be able to take back.
        col = self.column(column_id)
        if col is None:
            raise KeyError(column_id)
        if col.computed is not None:
            raise ValueError(f"{col.name} is worked out, not typed in")
        self._checkpoint("edit cell")
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
