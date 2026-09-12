"""Build demo.gridly — the sheet the screenshot in the README is taken from.

    python demo.py [PATH] [--rows N]

Rewrites the file from scratch each time, so the picture can be retaken after
the app changes. Ask for more rows than there are written out below and the
rest are made up, which is the quick way to a sheet big enough to see how the
app behaves when it is carrying something.
"""

from __future__ import annotations

import argparse
import itertools
from datetime import date, timedelta
from pathlib import Path

from gridly.coltypes import ColumnType as T
from gridly.store import Sheet

COLUMNS = [
    ("Task", T.TEXT, {}),
    ("Status", T.SELECT, {"New": "blue", "Doing": "yellow", "Blocked": "red", "Done": "green"}),
    ("Priority", T.SELECT, {"Low": "grey", "Medium": "orange", "High": "red"}),
    ("Owner", T.SELECT, {"Yousef": "purple", "Waseem": "teal", "Khan": "pink",
                         "Sultan": "blue", "Noura": "orange"}),
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
    ("Rate limit the search API", "Doing", "High", "Sultan", 5, "2026-09-15", False,
     "Redis counter, 100/min"),
    ("Arabic number formatting", "Blocked", "Medium", "Noura", 3, "2026-09-16", False,
     "Needs a ruling from design"),
    ("Cache the account summary", "New", "Medium", "Sultan", 4, "2026-09-23", False, ""),
    ("Drop the legacy session store", "Done", "Low", "Waseem", 6, "2026-08-28", True,
     "No traffic for three weeks"),
    ("Onboarding empty states", "Doing", "Medium", "Noura", 7, "2026-09-18", False,
     "Four screens still unwritten"),
    ("Sentry release tagging", "Done", "Low", "Khan", 1, "2026-09-04", True, ""),
    ("Split the payments module", "New", "High", "Yousef", 16, "2026-10-06", False,
     "Blocked behind the billing migration"),
    ("Prepaid top-up receipts", "Doing", "High", "Sultan", 9, "2026-09-17", False, ""),
    ("Dark mode audit", "New", "Low", "Noura", 5, "2026-10-02", False,
     "Contrast fails on three screens"),
    ("Retry failed webhooks", "Done", "Medium", "Waseem", 4, "2026-09-01", True,
     "Exponential backoff, five tries"),
    ("Device trust prompts", "Blocked", "High", "Yousef", 8, "2026-09-12", False,
     "Legal has not signed off"),
    ("Trim the bundle by 200kb", "Doing", "Medium", "Khan", 6, "2026-09-19", False, ""),
    ("Localise the error catalogue", "New", "Medium", "Noura", 10, "2026-09-30", False,
     "482 strings, 3 languages"),
    ("Postpaid invoice PDF", "Done", "High", "Sultan", 11, "2026-08-25", True, ""),
    ("Deprecate SMS OTP", "New", "Low", "Waseem", 2, "2026-10-09", False,
     "After the push migration lands"),
    ("Contact sync back-off", "Doing", "Low", "Khan", 3, "2026-09-22", False, ""),
    ("Roaming bundle screen", "Blocked", "Medium", "Noura", 7, "2026-09-13", False,
     "Waiting on the pricing feed"),
    ("Audit log retention", "Done", "Medium", "Yousef", 5, "2026-09-06", True,
     "Ninety days, then cold storage"),
    ("Push token cleanup job", "New", "Low", "Sultan", 2, "2026-10-04", False, ""),
    ("Two-factor recovery codes", "Doing", "High", "Waseem", 8, "2026-09-20", False,
     "Ten codes, single use"),
    ("Refresh the API docs", "New", "Low", "Khan", 4, "2026-10-12", False, ""),
    ("eSIM activation flow", "Blocked", "High", "Noura", 14, "2026-09-24", False,
     "Carrier sandbox is down"),
    ("Remove the beta banner", "Done", "Low", "Yousef", 0.5, "2026-09-08", True, ""),
]


VERBS = ["Fix", "Ship", "Audit", "Migrate", "Retire", "Cache", "Localise",
         "Rewrite", "Profile", "Document", "Split", "Trim", "Harden", "Rename"]
NOUNS = ["the search index", "the billing job", "the session store", "the API docs",
         "the retry queue", "the onboarding flow", "the export path", "the token cache",
         "the webhook handler", "the settings page", "the audit log", "the SMS gateway"]


def invented(number: int) -> tuple:
    """A plausible row, for when more are wanted than are written out above."""
    verb = VERBS[number % len(VERBS)]
    noun = NOUNS[(number // len(VERBS)) % len(NOUNS)]
    statuses = list(COLUMNS[1][2])
    priorities = list(COLUMNS[2][2])
    owners = list(COLUMNS[3][2])
    status = statuses[number % len(statuses)]
    return (
        f"{verb} {noun} ({number})",
        status,
        priorities[number % len(priorities)],
        owners[number % len(owners)],
        round((number % 16) + 0.5, 1),
        (date(2026, 9, 1) + timedelta(days=number % 90)).isoformat(),
        status == "Done",
        f"Note {number}" if number % 3 else "",
    )


def build(path: Path, rows: int) -> Path:
    path = Path(path).expanduser()
    path.unlink(missing_ok=True)
    sheet = Sheet(path)
    for seeded in sheet.columns():          # drop what a new sheet starts with
        sheet.delete_column(seeded.id)

    columns = [
        sheet.add_column(name, coltype, list(colors), colors)
        for name, coltype, colors in COLUMNS
    ]
    wanted = itertools.chain(ROWS, (invented(n) for n in itertools.count()))

    existing = sheet.rows()
    with sheet.change("build"):             # one undo step, not thousands
        for index, values in zip(range(rows), wanted):
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default="demo.gridly")
    parser.add_argument(
        "--rows", type=int, default=len(ROWS),
        help=f"how many rows to write (default {len(ROWS)}, the ones in the picture)",
    )
    args = parser.parse_args()
    target = build(args.path, args.rows)
    print(f"wrote {target} with {args.rows} rows\n\nopen it with:  gridly {target}")
