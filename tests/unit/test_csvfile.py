"""Writing a sheet out for other tools to read."""

import csv
import datetime

from gridly.coltypes import ColumnType
from gridly.store import Column, Row
from gridly.csvfile import write_csv

T = ColumnType


def sheet():
    columns = [
        Column(1, "Task", T.TEXT),
        Column(2, "Done", T.BOOLEAN),
        Column(3, "Qty", T.NUMBER),
        Column(4, "Due", T.DATE),
        Column(5, "Stage", T.SELECT, ["New"], {"New": "green"}),
    ]
    rows = [
        Row(1, 0, {1: 'Milk, "the good kind"', 2: True, 3: 7.5,
                   4: datetime.date(2026, 9, 12), 5: "New"}),
        Row(2, 1, {1: "two\nlines and عربي", 2: False}),
    ]
    return columns, rows


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def test_a_header_row_then_one_line_per_record(tmp_path):
    columns, rows = sheet()
    out = write_csv(tmp_path / "out.csv", columns, rows)
    assert read(out) == [
        ["Task", "Done", "Qty", "Due", "Stage"],
        ['Milk, "the good kind"', "yes", "7.5", "2026-09-12", "New"],
        ["two\nlines and عربي", "no", "", "", ""],
    ]


def test_excel_needs_the_byte_order_mark_to_read_non_ascii(tmp_path):
    columns, rows = sheet()
    out = write_csv(tmp_path / "out.csv", columns, rows)
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")


def test_a_sheet_with_no_rows_still_writes_its_header(tmp_path):
    columns, _ = sheet()
    out = write_csv(tmp_path / "empty.csv", columns, [])
    assert read(out) == [["Task", "Done", "Qty", "Due", "Stage"]]


def test_the_file_is_replaced_rather_than_appended_to(tmp_path):
    columns, rows = sheet()
    target = tmp_path / "out.csv"
    write_csv(target, columns, rows)
    write_csv(target, columns, rows)
    assert len(read(target)) == 3
