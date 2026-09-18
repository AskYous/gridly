"""A column that works itself out, seen from the database side."""

import datetime
import pathlib
import tempfile

import pytest

from gridly.coltypes import ColumnType
from gridly.formulas import MONTH_NAMES, Formula
from gridly.store import Sheet

T = ColumnType


def sheet():
    """A Day / Hours sheet with nothing seeded and nothing in it yet."""
    path = pathlib.Path(tempfile.mkdtemp()) / "t.gridly"
    kept = Sheet(path)
    for seeded in kept.columns():
        kept.delete_column(seeded.id)
    for seeded in kept.rows():
        kept.delete_row(seeded.id)
    day = kept.add_column("Day", T.DATE)
    hours = kept.add_column("Hours", T.NUMBER)
    return kept, day, hours


def month_column(kept, day, coltype=T.TEXT, shows="name", options=None):
    return kept.add_column(
        "Month",
        coltype,
        options or [],
        formula=Formula("month", day.id, shows).encode(),
    )


def values(kept, column):
    return [row.values.get(column.id) for row in kept.rows()]


def test_a_month_is_worked_out_from_the_date_beside_it():
    kept, day, _ = sheet()
    month = month_column(kept, day)
    first, second = kept.add_row(), kept.add_row()
    kept.set_cell(first, day.id, datetime.date(2026, 9, 17))
    kept.set_cell(second, day.id, datetime.date(2025, 1, 3))
    assert values(kept, month) == ["September", "January"]


def test_it_follows_the_column_it_reads():
    """The whole point: no stored copy, so nothing to fall behind."""
    kept, day, _ = sheet()
    month = month_column(kept, day)
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))
    assert values(kept, month) == ["September"]
    kept.set_cell(row, day.id, datetime.date(2026, 12, 1))
    assert values(kept, month) == ["December"]
    kept.set_cell(row, day.id, None)
    assert values(kept, month) == [None]


def test_undoing_the_date_takes_the_month_with_it():
    kept, day, _ = sheet()
    month = month_column(kept, day)
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))
    kept.set_cell(row, day.id, datetime.date(2026, 12, 1))
    assert values(kept, month) == ["December"]
    kept.undo()
    assert values(kept, month) == ["September"]


def test_the_column_takes_its_value_in_its_own_type():
    kept, day, _ = sheet()
    number = kept.add_column(
        "No.", T.NUMBER, formula=Formula("month", day.id, "number").encode()
    )
    pick = kept.add_column(
        "Pick", T.SELECT, list(MONTH_NAMES),
        formula=Formula("month", day.id, "name").encode(),
    )
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))
    assert values(kept, number) == [9]
    assert values(kept, pick) == ["September"]


def test_a_value_the_column_type_refuses_leaves_the_cell_empty():
    """Rather than raising out of a plain read of the sheet."""
    kept, day, _ = sheet()
    wrong = kept.add_column(
        "Month", T.NUMBER, formula=Formula("month", day.id, "name").encode()
    )
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))
    assert values(kept, wrong) == [None]


def test_typing_into_one_is_refused():
    kept, day, _ = sheet()
    month = month_column(kept, day)
    row = kept.add_row()
    with pytest.raises(ValueError):
        kept.set_cell(row, month.id, "Nope")


def test_a_refused_write_is_not_something_to_undo():
    kept, day, _ = sheet()
    month = month_column(kept, day)
    row = kept.add_row()
    was = kept.undoable
    with pytest.raises(ValueError):
        kept.set_cell(row, month.id, "Nope")
    assert kept.undoable == was


def test_it_survives_being_closed_and_opened_again():
    kept, day, _ = sheet()
    month = month_column(kept, day, shows="short")
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))
    path = kept.path
    kept.close()

    again = Sheet(path)
    column = [c for c in again.columns() if c.name == "Month"][0]
    assert column.computed == Formula("month", day.id, "short")
    assert values(again, column) == ["Sep"]


def test_making_a_column_computed_clears_what_was_typed_into_it():
    """Nothing would ever show those again, and undo still has them."""
    kept, day, _ = sheet()
    month = kept.add_column("Month", T.TEXT)
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))
    kept.set_cell(row, month.id, "typed by hand")

    dropped = kept.update_column(
        month.id, "Month", T.TEXT, formula=Formula("month", day.id).encode()
    )
    assert dropped == 0, "converting nothing is not a loss to report"
    assert values(kept, month) == ["September"]
    kept.undo()
    assert values(kept, month) == ["typed by hand"]


def test_taking_the_formula_off_leaves_an_ordinary_empty_column():
    kept, day, _ = sheet()
    month = month_column(kept, day)
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))
    kept.update_column(month.id, "Month", T.TEXT)
    assert values(kept, month) == [None]
    kept.set_cell(row, month.id, "mine now")
    assert values(kept, month) == ["mine now"]


def test_deleting_the_source_says_which_columns_it_leaves_with_nothing():
    kept, day, _ = sheet()
    month = month_column(kept, day)
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))

    assert kept.delete_column(day.id) == ["Month"]
    left = [c for c in kept.columns() if c.name == "Month"][0]
    assert left.computed is None, "it stops working nothing out"
    assert values(kept, left) == [None]


def test_a_duplicated_row_works_its_month_out_afresh():
    kept, day, _ = sheet()
    month = month_column(kept, day)
    row = kept.add_row()
    kept.set_cell(row, day.id, datetime.date(2026, 9, 17))
    copy = kept.duplicate_row(row)
    assert values(kept, month) == ["September", "September"]
    kept.set_cell(copy, day.id, datetime.date(2026, 3, 1))
    assert values(kept, month) == ["September", "March"]


# ---------------------------------------------------------------------- sums


def sum_column(kept, name, expr, coltype=T.NUMBER):
    return kept.add_column(name, coltype, formula=Formula("sum", expr=expr).encode())


def test_a_column_is_worked_out_by_a_sum_over_another():
    kept, _, hours = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55")
    first, second = kept.add_row(), kept.add_row()
    kept.set_cell(first, hours.id, 1.5)
    kept.set_cell(second, hours.id, 8)
    assert values(kept, pay) == [82.5, 440]


def test_a_sum_follows_the_column_it_reads():
    kept, _, hours = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55")
    row = kept.add_row()
    kept.set_cell(row, hours.id, 2)
    assert values(kept, pay) == [110]
    kept.set_cell(row, hours.id, 3)
    assert values(kept, pay) == [165]


def test_changing_the_sum_changes_every_row():
    kept, _, hours = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55")
    row = kept.add_row()
    kept.set_cell(row, hours.id, 2)
    kept.update_column(
        pay.id, "Pay", T.NUMBER, formula=Formula("sum", expr="Hours * 70").encode()
    )
    assert values(kept, pay) == [140]


def test_a_sum_over_a_sum_is_worked_out_in_the_right_order():
    """However the columns happen to sit, each one comes after what it reads."""
    kept, _, hours = sheet()
    net = sum_column(kept, "Net", "Pay - Tax")     # written before either exists
    tax = sum_column(kept, "Tax", "Pay * 0.15")
    pay = sum_column(kept, "Pay", "Hours * 100")
    row = kept.add_row()
    kept.set_cell(row, hours.id, 2)
    assert values(kept, pay) == [200]
    assert values(kept, tax) == [30]
    assert values(kept, net) == [170]


def test_columns_that_read_each_other_in_a_ring_stay_empty():
    """There is no order that works them out, so neither gets an answer."""
    kept, _, hours = sheet()
    here = sum_column(kept, "Here", "Hours + 1")
    there = sum_column(kept, "There", "Here + 1")
    kept.update_column(
        here.id, "Here", T.NUMBER, formula=Formula("sum", expr="There + 1").encode()
    )
    row = kept.add_row()
    kept.set_cell(row, hours.id, 2)
    assert values(kept, here) == [None]
    assert values(kept, there) == [None]


def test_a_row_nobody_has_filled_in_yet_stays_empty():
    kept, _, _ = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55")
    kept.add_row()
    assert values(kept, pay) == [None]


def test_a_sum_can_be_written_into_a_text_column_too():
    kept, _, hours = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55", coltype=T.TEXT)
    row = kept.add_row()
    kept.set_cell(row, hours.id, 2)
    assert values(kept, pay) == ["110"]


def test_renaming_a_column_takes_the_sums_that_read_it_along():
    kept, _, hours = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55")
    row = kept.add_row()
    kept.set_cell(row, hours.id, 2)
    kept.update_column(hours.id, "Worked", T.NUMBER)
    moved = [c for c in kept.columns() if c.name == "Pay"][0]
    assert moved.computed.expr == "Worked * 55"
    assert values(kept, moved) == [110]


def test_a_sum_is_not_rewritten_by_a_rename_it_does_not_read():
    kept, day, hours = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55")
    kept.update_column(day.id, "Date", T.DATE)
    assert [c for c in kept.columns() if c.name == "Pay"][0].computed.expr == "Hours * 55"


def test_deleting_what_a_sum_reads_says_so_and_stops_it():
    kept, _, hours = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55")
    assert kept.delete_column(hours.id) == ["Pay"]
    left = [c for c in kept.columns() if c.name == "Pay"][0]
    assert left.computed is None


def test_a_sum_that_no_longer_reads_leaves_its_column_empty():
    """A file edited by hand, say — it shows nothing rather than failing."""
    kept, _, hours = sheet()
    pay = kept.add_column(
        "Pay", T.NUMBER, formula='{"fn": "sum", "expr": "Nonsense * 2"}'
    )
    row = kept.add_row()
    kept.set_cell(row, hours.id, 2)
    assert values(kept, pay) == [None]


def test_a_sum_survives_being_closed_and_opened_again():
    kept, _, hours = sheet()
    sum_column(kept, "Pay", "Hours * 55")
    row = kept.add_row()
    kept.set_cell(row, hours.id, 2)
    path = kept.path
    kept.close()

    again = Sheet(path)
    column = [c for c in again.columns() if c.name == "Pay"][0]
    assert column.computed == Formula("sum", expr="Hours * 55")
    assert values(again, column) == [110]


def test_typing_into_a_sum_column_is_refused():
    kept, _, _ = sheet()
    pay = sum_column(kept, "Pay", "Hours * 55")
    row = kept.add_row()
    with pytest.raises(ValueError):
        kept.set_cell(row, pay.id, 999)
