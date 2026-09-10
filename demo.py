"""Build demo.gridly — the sheet the screenshot in the README is taken from.

    python demo.py [PATH]

Rewrites the file from scratch each time, so the picture can be retaken after
the app changes.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from gridly.coltypes import ColumnType as T
from gridly.store import Sheet

COLUMNS = [
    ("Task", T.TEXT, {}),
    ("Status", T.SELECT, {"New": "blue", "Doing": "yellow", "Blocked": "red", "Done": "green"}),
    ("Priority", T.SELECT, {"Low": "grey", "Medium": "orange", "High": "red"}),
    ("Owner", T.SELECT, {"Yousef": "purple", "Waseem": "teal", "Khan": "pink"}),
    ("Hours", T.NUMBER, {}),
    ("Due", T.DATE, {}),
    ("Shipped", T.BOOLEAN, {}),
    ("Notes", T.TEXT, {}),
]

ROWS = [
    ("Wire up the EBU SDK", "Doing", "High", "Waseem", 6, "2026-09-14", False,
     "Waiting on sandbox creds"),
    ("Login & registration", "Blocked", "High", "Yousef", 12, "2026-09-11", False,
     "OCP 500s on primary swap"),
    ("In-app notifications", "New", "Medium", "Khan", 4, "2026-09-21", False, ""),
    ("Migrate the billing table", "Done", "Medium", "Yousef", 8, "2026-09-02", True,
     "Clean on the second attempt"),
    ("Write the release notes", "New", "Low", "Khan", 1.5, "2026-09-25", False, ""),
    ("Retire the v3 endpoints", "Doing", "Low", "Waseem", 3, "2026-10-01", False,
     "Two consumers left to move"),
    ("Fix the dropdown colours", "Done", "High", "Yousef", 2, "2026-09-09", True, ""),
]


def build(path: Path) -> Path:
    path = Path(path).expanduser()
    path.unlink(missing_ok=True)
    sheet = Sheet(path)
    for seeded in sheet.columns():          # drop what a new sheet starts with
        sheet.delete_column(seeded.id)

    columns = [
        sheet.add_column(name, coltype, list(colors), colors)
        for name, coltype, colors in COLUMNS
    ]
    existing = sheet.rows()
    for index, values in enumerate(ROWS):
        row_id = existing[0].id if index == 0 and existing else sheet.add_row()
        for column, value in zip(columns, values):
            if value == "" or value is None:
                continue
            if column.type is T.DATE:
                value = date.fromisoformat(value)
            sheet.set_cell(row_id, column.id, value)
    sheet.close()
    return path.resolve()


if __name__ == "__main__":
    target = build(sys.argv[1] if len(sys.argv) > 1 else "demo.gridly")
    print(f"wrote {target}\n\nopen it with:  gridly {target}")
