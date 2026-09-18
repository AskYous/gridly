"""Working a value out from another column, rather than typing it in."""

import datetime

import pytest

from gridly.coltypes import ColumnType
from gridly.formulas import (
    MONTH_WORDINGS,
    Formula,
    month_text,
    options_for,
    read_sum,
    reading_order,
    refusal,
    sources_among,
    unreadable,
    value_of,
)
from gridly.store import Column

T = ColumnType
SEPTEMBER = datetime.date(2026, 9, 17)


@pytest.mark.parametrize(
    "shows, written",
    [("name", "September"), ("short", "Sep"), ("number", "9"), ("year", "2026-09")],
)
def test_the_ways_a_month_can_be_written(shows, written):
    assert value_of(Formula("month", 1, shows), T.DATE, SEPTEMBER) == written


def test_every_wording_has_the_example_the_form_shows():
    """The form offers an example of each; it should be what the sum produces."""
    for shows, example in MONTH_WORDINGS.items():
        assert value_of(Formula("month", 1, shows), T.DATE, SEPTEMBER) == example


def test_nothing_to_work_out_is_an_empty_answer():
    assert value_of(Formula("month", 1), T.DATE, None) == ""


def test_a_source_that_is_no_longer_a_date_works_nothing_out():
    """Retyping the column underneath empties the month rather than guessing."""
    assert value_of(Formula("month", 1), T.TEXT, "September") == ""


def test_a_formula_survives_the_round_trip_to_storage():
    spec = Formula("month", 7, "short")
    assert Formula.decode(spec.encode()) == spec


@pytest.mark.parametrize(
    "stored", ["", None, "not json", "{}", '{"fn": "median", "source": 1}', "[]"]
)
def test_junk_decodes_to_no_formula_at_all(stored):
    assert Formula.decode(stored) is None


def test_an_unknown_wording_falls_back_rather_than_failing():
    spec = Formula.decode('{"fn": "month", "source": 2, "shows": "runes"}')
    assert spec == Formula("month", 2, "name")


def test_a_dropdown_of_months_lists_twelve_of_them():
    assert options_for(Formula("month", 1)) == [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    assert options_for(Formula("month", 1, "number")) == [str(m) for m in range(1, 13)]


@pytest.mark.parametrize(
    "coltype, shows",
    [(T.TEXT, "name"), (T.TEXT, "year"), (T.NUMBER, "number"), (T.SELECT, "short")],
)
def test_types_a_month_fits_in(coltype, shows):
    assert refusal(Formula("month", 1, shows), coltype) is None


@pytest.mark.parametrize(
    "coltype, shows",
    [
        (T.NUMBER, "name"),   # "September" is not a number
        (T.SELECT, "year"),   # a year and month never stops adding options
        (T.DATE, "name"),
        (T.TIME, "number"),
        (T.BOOLEAN, "name"),
    ],
)
def test_types_a_month_does_not_fit_in(coltype, shows):
    assert refusal(Formula("month", 1, shows), coltype)


def test_month_text_counts_from_one():
    assert month_text(1, "name") == "January"
    assert month_text(12, "name") == "December"


def test_only_a_date_column_can_be_read_from():
    """Not a computed one either, so a formula can never chase its own tail."""
    columns = [
        Column(1, "Day", T.DATE),
        Column(2, "Hours", T.NUMBER),
        Column(3, "Signed", T.DATE, formula=Formula("month", 1).encode()),
        Column(4, "Paid", T.DATE),
    ]
    assert [c.name for c in sources_among(columns)] == ["Day", "Paid"]
    assert [c.name for c in sources_among(columns, exclude=1)] == ["Paid"]


@pytest.mark.parametrize("coltype", [T.NUMBER, T.TEXT])
def test_types_a_sum_fits_in(coltype):
    assert refusal(Formula("sum", expr="Hours * 2"), coltype) is None


@pytest.mark.parametrize("coltype", [T.DATE, T.TIME, T.BOOLEAN, T.SELECT])
def test_types_a_sum_does_not_fit_in(coltype):
    assert refusal(Formula("sum", expr="Hours * 2"), coltype)


def test_a_sum_with_nothing_in_it_is_no_formula_at_all():
    assert Formula.decode('{"fn": "sum", "expr": "   "}') is None
    assert Formula.decode('{"fn": "sum"}') is None


def test_a_sum_survives_the_round_trip_to_storage():
    spec = Formula("sum", expr="Hours * 55 + 10")
    assert Formula.decode(spec.encode()) == spec


def test_a_sum_that_names_one_of_two_columns_sharing_a_name_is_refused():
    """It cannot say which of them it meant, so it is not allowed to guess."""
    columns = [
        Column(1, "Hours", T.NUMBER),
        Column(2, "Hours", T.NUMBER),
        Column(3, "Rate", T.NUMBER),
    ]
    tree = read_sum("Hours * Rate", columns)
    assert "Two columns" in unreadable(tree, columns)
    assert unreadable(read_sum("Rate * 2", columns), columns) is None


def test_a_sum_reads_a_column_that_is_itself_worked_out():
    columns = [
        Column(1, "Hours", T.NUMBER),
        Column(2, "Pay", T.NUMBER, formula=Formula("sum", expr="Hours * 55").encode()),
    ]
    assert unreadable(read_sum("Pay * 0.15", columns), columns) is None


def test_reading_order_puts_each_column_behind_what_it_reads():
    columns = [
        Column(1, "Hours", T.NUMBER),
        Column(2, "Net", T.NUMBER, formula=Formula("sum", expr="Pay - Tax").encode()),
        Column(3, "Tax", T.NUMBER, formula=Formula("sum", expr="Pay * 0.15").encode()),
        Column(4, "Pay", T.NUMBER, formula=Formula("sum", expr="Hours * 55").encode()),
    ]
    sums = {c.id: read_sum(c.computed.expr, columns) for c in columns[1:]}
    assert [c.name for c in reading_order(columns, sums)] == ["Pay", "Tax", "Net"]


def test_a_ring_of_columns_never_comes_up_at_all():
    columns = [
        Column(1, "Here", T.NUMBER, formula=Formula("sum", expr="There + 1").encode()),
        Column(2, "There", T.NUMBER, formula=Formula("sum", expr="Here + 1").encode()),
        Column(3, "Fine", T.NUMBER, formula=Formula("sum", expr="2 + 2").encode()),
    ]
    sums = {c.id: read_sum(c.computed.expr, columns) for c in columns}
    assert [c.name for c in reading_order(columns, sums)] == ["Fine"]
