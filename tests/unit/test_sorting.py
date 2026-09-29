"""Putting rows in order, and keeping the sort in the sheet."""

import datetime, pathlib, tempfile

from gridly.coltypes import ColumnType
from gridly.sorting import Level, decode, encode, out_of_order, sort_rows
from gridly.store import Column, Row, Sheet

NAME = Column(1, "Name", ColumnType.TEXT)
QTY = Column(2, "Qty", ColumnType.NUMBER)
PRIO = Column(3, "Priority", ColumnType.SELECT, ["Low", "Medium", "High"])
DUE = Column(4, "Due", ColumnType.DATE)
COLUMNS = [NAME, QTY, PRIO, DUE]


def rows(*values):
    return [
        Row(id=index, position=index, values=dict(zip((1, 2, 3, 4), row)))
        for index, row in enumerate(values, start=1)
    ]


def names(ordered):
    return [row.values[1] for row in ordered]


def test_one_column_either_way():
    data = rows(("pear", 3), ("Apple", 1), ("fig", 2))
    assert names(sort_rows(data, COLUMNS, [Level(1)])) == ["Apple", "fig", "pear"]
    assert names(sort_rows(data, COLUMNS, [Level(2, True)])) == ["pear", "fig", "Apple"]


def test_ties_go_to_the_next_column_then_the_file():
    data = rows(("b", 1), ("a", 2), ("c", 1), ("d", 2))
    by_qty = sort_rows(data, COLUMNS, [Level(2)])
    assert names(by_qty) == ["b", "c", "a", "d"]  # file order within a tie
    then_name_down = sort_rows(data, COLUMNS, [Level(2), Level(1, True)])
    assert names(then_name_down) == ["c", "b", "d", "a"]


def test_empty_goes_last_both_ways():
    data = rows(("a", None), ("b", 5), ("c", 1))
    assert names(sort_rows(data, COLUMNS, [Level(2)])) == ["c", "b", "a"]
    assert names(sort_rows(data, COLUMNS, [Level(2, True)])) == ["b", "c", "a"]


def test_dropdown_follows_its_own_order():
    data = rows(("a", 0, "High"), ("b", 0, "Low"), ("c", 0, "Gone"), ("d", 0, "Medium"))
    assert names(sort_rows(data, COLUMNS, [Level(3)])) == ["b", "d", "a", "c"]


def test_dates():
    day = datetime.date
    data = rows(("a", 0, None, day(2026, 3, 1)), ("b", 0, None, day(2025, 1, 1)))
    assert names(sort_rows(data, COLUMNS, [Level(4, True)])) == ["a", "b"]


def test_out_of_order():
    low, high = rows(("a", 1), ("b", 9))
    assert not out_of_order(low, high, COLUMNS, [Level(2)])
    assert out_of_order(high, low, COLUMNS, [Level(2)])
    assert out_of_order(low, high, COLUMNS, [Level(2, True)])
    empty, full = rows(("a", None), ("b", 1))
    assert out_of_order(empty, full, COLUMNS, [Level(2)])
    same, other = rows(("a", 1), ("a", 1))
    assert not out_of_order(same, other, COLUMNS, [Level(2)])


def test_encoding_round_trip_and_gone_columns():
    levels = [Level(2, True), Level(1)]
    assert encode(levels) == "-2,1"
    assert decode(encode(levels), COLUMNS) == levels
    assert decode("-9,1,junk,1", COLUMNS) == [Level(1)]
    assert decode("", COLUMNS) == []


def test_sheet_keeps_its_sort_out_of_undo():
    path = pathlib.Path(tempfile.mkdtemp()) / "s.gridly"
    sheet = Sheet(path)
    assert sheet.sort_text() == ""
    sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, "x")
    sheet.set_sort_text("-1")
    sheet.undo()
    assert sheet.sort_text() == "-1"
    sheet.close()
    assert Sheet(path).sort_text() == "-1"
