"""Columns whose values are worked out rather than typed.

A computed column holds no cells of its own. Its values are worked out on the
way out of the database, every time the sheet is read, from a column it names.
That is what keeps it honest: there is no stored copy to fall behind the column
it reads, so changing a date changes the month beside it at once, and undoing
that change takes the month back with it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from . import arithmetic
from .coltypes import ColumnType, display

#: What a column can be told to work out, and how the form offers it. The
#: keys are what a sheet stores; the words are what the form shows.
FUNCTIONS = {"sum": "Calculated", "month": "Month of a date"}

#: The types a sum can be written into — whatever can hold a number.
SUM_TYPES = (ColumnType.NUMBER, ColumnType.TEXT)

#: The ways a month can be written, and September 2026 written each way.
MONTH_WORDINGS = {
    "name": "September",
    "short": "Sep",
    "number": "9",
    "year": "2026-09",
}
DEFAULT_WORDING = "name"

# Spelled out rather than taken from strftime, which answers in whatever
# language the machine happens to be set to — a sheet should read the same
# wherever it is opened.
MONTH_NAMES = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

#: The types a month can be written into. The rest are refused by `refusal`.
MONTH_TYPES = (ColumnType.TEXT, ColumnType.NUMBER, ColumnType.SELECT)


@dataclass(frozen=True)
class Formula:
    """What a computed column works out: which sum, from where, written how."""

    fn: str
    #: The id of the column a month is read from. Unused by a sum.
    source: int = 0
    shows: str = DEFAULT_WORDING
    #: The arithmetic a sum is worked out by, written in column names.
    expr: str = ""

    def encode(self) -> str:
        """How a formula is kept in the column's row. Empty means none."""
        return json.dumps(
            {
                "fn": self.fn,
                "source": self.source,
                "shows": self.shows,
                "expr": self.expr,
            }
        )

    @classmethod
    def decode(cls, stored: str | None) -> Formula | None:
        """Read one back. Anything unrecognisable is no formula at all."""
        if not stored:
            return None
        try:
            spec = json.loads(stored)
            fn = spec["fn"]
            source = int(spec.get("source", 0))
            expr = str(spec.get("expr", ""))
        except (ValueError, TypeError, KeyError, AttributeError):
            return None
        if fn not in FUNCTIONS or (fn == "sum" and not expr.strip()):
            return None
        shows = spec.get("shows", DEFAULT_WORDING)
        return cls(
            fn, source, shows if shows in MONTH_WORDINGS else DEFAULT_WORDING, expr
        )


def month_text(month: int, shows: str, year: int = 0) -> str:
    """One month, written the way a column asks for it."""
    if shows == "number":
        return str(month)
    if shows == "short":
        return MONTH_NAMES[month - 1][:3]
    if shows == "year":
        return f"{year:04d}-{month:02d}"
    return MONTH_NAMES[month - 1]


def value_of(spec: Formula, source_type: ColumnType, source_value) -> str:
    """What a formula works out for one row, as text for the column to read.

    Nothing to go on — an empty source cell, or a source that is no longer a
    date — is an empty answer, which lands as an empty cell rather than an error.
    """
    if source_type is not ColumnType.DATE or not isinstance(source_value, date):
        return ""
    if spec.fn == "month":
        return month_text(source_value.month, spec.shows, source_value.year)
    return ""


def options_for(spec: Formula) -> list[str]:
    """Every value the formula can produce, for a dropdown to list.

    Only asked for where the answers are countable — `refusal` turns away the
    wordings that are not, such as a year and month together.
    """
    return [month_text(month, spec.shows, 0) for month in range(1, 13)]


def refusal(spec: Formula, coltype: ColumnType) -> str | None:
    """Why a column of this type cannot hold this formula, if it cannot."""
    if spec.fn == "sum":
        if coltype in SUM_TYPES:
            return None
        return f"A formula cannot go in a {coltype.label.lower()} column"
    if coltype is ColumnType.TEXT:
        return None
    if coltype is ColumnType.NUMBER:
        if spec.shows != "number":
            return (
                "A number column can only show a month as a number — "
                f"not as {MONTH_WORDINGS[spec.shows]!r}"
            )
        return None
    if coltype is ColumnType.SELECT:
        if spec.shows == "year":
            return "A dropdown cannot hold a year and month — there is no end to them"
        return None
    return f"A month cannot go in a {coltype.label.lower()} column"


def sources_among(columns, exclude: int = 0) -> list:
    """The columns a month can be taken from: dates that are not worked out."""
    return [
        column
        for column in columns
        if column.type is ColumnType.DATE
        and column.id != exclude
        and column.computed is None
    ]


# --------------------------------------------------------------------- sums


def read_sum(expr: str, columns) -> object | None:
    """A sum parsed against this sheet's columns, or None if it will not read."""
    try:
        return arithmetic.parse(expr, [column.name for column in columns])
    except arithmetic.FormulaError:
        return None


def sum_text(tree, columns, values: dict) -> str:
    """What a sum works out for one row, written as a number for the column."""
    if tree is None:
        return ""
    by_name = {column.name: column for column in columns}
    reads = {
        name: values.get(by_name[name].id)
        for name in arithmetic.columns_in(tree)
        if name in by_name
    }
    answer = arithmetic.evaluate(tree, reads)
    if answer is None:
        return ""
    whole = int(answer) if float(answer).is_integer() else answer
    return display(ColumnType.NUMBER, whole)


def unreadable(tree, columns) -> str | None:
    """Why a sum cannot read the columns it names, if it cannot.

    A sum reads numbers. Two columns sharing a name is turned away here too:
    a sum that names one of them cannot say which it meant.
    """
    by_name: dict[str, list] = {}
    for column in columns:
        by_name.setdefault(column.name.lower(), []).append(column)
    for name in arithmetic.columns_in(tree):
        found = by_name.get(name.lower(), [])
        if not found:
            return f"No column is called {name!r}"
        if len(found) > 1:
            return f"Two columns are called {name!r} — rename one of them"
        if found[0].type is not ColumnType.NUMBER:
            return (
                f"A formula reads numbers — {found[0].name} is "
                f"a {found[0].type.label.lower()} column"
            )
    return None


def reads_of(column, tree, columns) -> list[int]:
    """The ids of the columns a computed column reads."""
    spec = column.computed
    if spec is None:
        return []
    if spec.fn != "sum":
        return [spec.source]
    if tree is None:
        return []
    by_name = {c.name.lower(): c.id for c in columns}
    return [
        by_name[name.lower()]
        for name in arithmetic.columns_in(tree)
        if name.lower() in by_name
    ]


def reading_order(columns, sums: dict) -> list:
    """The computed columns, each behind the ones it reads.

    A column caught in a ring of columns reading each other never comes up:
    there is no order that would work it out, so it is left out and stays
    empty rather than showing whichever answer the column order happened to
    produce. `sums` maps a column's id to its parsed sum, where it has one.
    """
    computed = {c.id: c for c in columns if c.computed is not None}
    needs = {
        cid: {
            read
            for read in reads_of(column, sums.get(cid), columns)
            if read in computed
        }
        for cid, column in computed.items()
    }
    ordered: list = []
    done: set[int] = set()
    while True:
        ready = [cid for cid in computed if cid not in done and needs[cid] <= done]
        if not ready:
            return ordered
        ordered += [computed[cid] for cid in ready]
        done |= set(ready)
