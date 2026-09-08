"""Writing a sheet out as a CSV file."""

from __future__ import annotations

from pathlib import Path

import csv

from .coltypes import display
from .store import Column, Row


def write_csv(path: str | Path, columns: list[Column], rows: list[Row]) -> Path:
    """Write a header row of column names followed by one line per record.

    Values are written the way the grid shows them, so a boolean reads `yes`
    or `no` and a date `2026-09-08`. The file is utf-8 with a BOM, which is
    what Excel needs to read non-ASCII text correctly and which Sheets, pandas
    and the like all accept.
    """
    path = Path(path).expanduser()
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([column.name for column in columns])
        for row in rows:
            writer.writerow(
                [display(column.type, row.values.get(column.id)) for column in columns]
            )
    return path
