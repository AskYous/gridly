"""Putting rows in order by what they hold.

A sort is a way of looking at the sheet, like its width or its theme: it never
moves a row in the file, so turning it off puts every row back where it was.
It is a list of columns, most important first — sort by the first, and where
two rows hold the same there, by the second, and so on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coltypes import ColumnType
from .store import Column, Row

#: How many columns a sort may go by. Past three, the rows that still tie are
#: few enough to read.
MAX_LEVELS = 3


@dataclass(frozen=True)
class Level:
    """One column the rows are sorted by, and which way round."""

    column_id: int
    descending: bool = False


#: What each way round is called, by the type it is sorting — "A → Z" means
#: nothing to a date.
DIRECTIONS = {
    ColumnType.TEXT: ("A → Z", "Z → A"),
    ColumnType.NUMBER: ("smallest first", "largest first"),
    ColumnType.DATE: ("oldest first", "newest first"),
    ColumnType.TIME: ("earliest first", "latest first"),
    ColumnType.BOOLEAN: ("no first", "yes first"),
    ColumnType.SELECT: ("in the dropdown's order", "the dropdown's order reversed"),
}


def encode(levels: list[Level]) -> str:
    """A sort as the sheet keeps it: a line of text in its meta table."""
    return ",".join(
        f"{'-' if level.descending else ''}{level.column_id}" for level in levels
    )


def decode(text: str, columns: list[Column]) -> list[Level]:
    """A sort read back from the sheet.

    A column that has since been deleted is left out, rather than the sort
    being thrown away for the columns that are still there.
    """
    present = {column.id for column in columns}
    levels = []
    for part in text.split(","):
        part = part.strip()
        descending = part.startswith("-")
        try:
            column_id = int(part.lstrip("-"))
        except ValueError:
            continue
        if column_id in present and all(l.column_id != column_id for l in levels):
            levels.append(Level(column_id, descending))
    return levels[:MAX_LEVELS]


def key(column: Column, value: Any) -> Any:
    """What a value is compared by. Never called with an empty one."""
    if column.type is ColumnType.TEXT:
        return str(value).casefold()
    if column.type is ColumnType.SELECT:
        # The order the options were listed in is the order they mean — Low,
        # Medium, High — which the alphabet would scramble. One no longer on
        # the list goes after the rest.
        if value in column.options:
            return (0, column.options.index(value), "")
        return (1, 0, str(value).casefold())
    return value


def sort_rows(rows: list[Row], columns: list[Column], levels: list[Level]) -> list[Row]:
    """The rows in the order the sort asks for.

    Rows that tie on every level keep the order they have in the file, and an
    empty cell goes last whichever way round the column is sorted — a gap at
    the top of the sheet reads as nothing being there.
    """
    found = {column.id: column for column in columns}
    ordered = list(rows)
    # Least important first: each pass is stable, so it keeps the order the
    # passes before it made among the rows it cannot tell apart.
    for level in reversed(levels):
        column = found.get(level.column_id)
        if column is None:
            continue
        held = [row for row in ordered if row.values.get(column.id) is not None]
        empty = [row for row in ordered if row.values.get(column.id) is None]
        held.sort(
            key=lambda row: key(column, row.values[column.id]),
            reverse=level.descending,
        )
        ordered = held + empty
    return ordered


def out_of_order(upper: Row, lower: Row, columns: list[Column], levels: list[Level]) -> bool:
    """Would the sort put `lower` above `upper`, where they are the other way?"""
    found = {column.id: column for column in columns}
    for level in levels:
        column = found.get(level.column_id)
        if column is None:
            continue
        x, y = upper.values.get(column.id), lower.values.get(column.id)
        if x is None and y is None:
            continue
        if x is None:
            return True
        if y is None:
            return False
        kx, ky = key(column, x), key(column, y)
        if kx == ky:
            continue
        return (kx < ky) if level.descending else (kx > ky)
    return False
