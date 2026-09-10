"""Column types: parsing, validation, storage encoding, and display."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any


class ValidationError(ValueError):
    """Raised when a raw value cannot be coerced into a column's type."""


class ColumnType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    SELECT = "select"

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def tag(self) -> str:
        """Short marker shown next to the column name in the header."""
        return _TAGS[self]

    @property
    def hint(self) -> str:
        return _HINTS[self]


_LABELS = {
    ColumnType.TEXT: "Text",
    ColumnType.NUMBER: "Number",
    ColumnType.BOOLEAN: "Boolean",
    ColumnType.DATE: "Date",
    ColumnType.SELECT: "Dropdown",
}

_TAGS = {
    ColumnType.TEXT: "abc",
    ColumnType.NUMBER: "123",
    ColumnType.BOOLEAN: "y/n",
    ColumnType.DATE: "cal",
    ColumnType.SELECT: "list",
}

_HINTS = {
    ColumnType.TEXT: "any text",
    ColumnType.NUMBER: "e.g. 42 or 3.14",
    ColumnType.BOOLEAN: "yes / no",
    ColumnType.DATE: "YYYY-MM-DD (or 'today')",
    ColumnType.SELECT: "one of the column's options",
}

_TRUE_WORDS = {"1", "true", "t", "yes", "y", "on", "✓"}
_FALSE_WORDS = {"0", "false", "f", "no", "n", "off", "✗"}

_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%b %d %Y")


def parse(coltype: ColumnType, raw: str, options: list[str] | None = None) -> Any:
    """Turn user-typed text into a stored value. Empty input means "no value"."""
    raw = raw.strip()
    if not raw:
        return None

    if coltype is ColumnType.TEXT:
        return raw

    if coltype is ColumnType.NUMBER:
        cleaned = raw.replace(",", "").replace("_", "")
        try:
            value = float(cleaned)
        except ValueError:
            raise ValidationError(f"{raw!r} is not a number") from None
        if value != value or value in (float("inf"), float("-inf")):
            raise ValidationError(f"{raw!r} is not a finite number")
        return int(value) if value.is_integer() else value

    if coltype is ColumnType.BOOLEAN:
        lowered = raw.lower()
        if lowered in _TRUE_WORDS:
            return True
        if lowered in _FALSE_WORDS:
            return False
        raise ValidationError(f"{raw!r} is not yes/no")

    if coltype is ColumnType.DATE:
        if raw.lower() == "today":
            return date.today()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        raise ValidationError(f"{raw!r} is not a date (try YYYY-MM-DD)")

    if coltype is ColumnType.SELECT:
        for option in options or []:
            if option.lower() == raw.lower():
                return option
        raise ValidationError(f"{raw!r} is not one of the options")

    raise ValidationError(f"unknown column type {coltype}")


def encode(coltype: ColumnType, value: Any) -> str | None:
    """Serialize a value for SQLite."""
    if value is None:
        return None
    if coltype is ColumnType.BOOLEAN:
        return "1" if value else "0"
    if coltype is ColumnType.DATE:
        return value.isoformat()
    if coltype is ColumnType.NUMBER:
        return repr(value)
    return str(value)


def decode(coltype: ColumnType, stored: str | None) -> Any:
    """Deserialize a value read back from SQLite. Junk decodes to None."""
    if stored is None:
        return None
    try:
        if coltype is ColumnType.BOOLEAN:
            return stored == "1"
        if coltype is ColumnType.DATE:
            return date.fromisoformat(stored)
        if coltype is ColumnType.NUMBER:
            value = float(stored)
            return int(value) if value.is_integer() else value
    except (ValueError, TypeError):
        return None
    return stored


def display(coltype: ColumnType, value: Any) -> str:
    """Plain-text rendering used in the grid and as the starting text when editing."""
    if value is None:
        return ""
    if coltype is ColumnType.BOOLEAN:
        return "yes" if value else "no"
    if coltype is ColumnType.DATE:
        return value.isoformat()
    if coltype is ColumnType.NUMBER:
        if isinstance(value, int):
            return str(value)
        return f"{value:g}"
    return str(value)


# Colours a dropdown option can be shown in. Handed out in this order when a
# column does not say, which puts a Low/Medium/High list at green/yellow/red.
OPTION_COLORS = (
    "green",
    "yellow",
    "red",
    "cyan",
    "magenta",
    "blue",
    "bright_green",
    "bright_yellow",
    "bright_red",
    "white",
)


def assign_colors(options: list[str], chosen: dict[str, str]) -> dict[str, str]:
    """Fill in a colour for every option the user did not pick one for."""
    colors: dict[str, str] = {}
    spare = [c for c in OPTION_COLORS if c not in chosen.values()]
    for index, option in enumerate(options):
        if option in chosen:
            colors[option] = chosen[option]
        elif spare:
            colors[option] = spare.pop(0)
        else:
            colors[option] = OPTION_COLORS[index % len(OPTION_COLORS)]
    return colors
