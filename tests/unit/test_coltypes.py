"""Turning what someone typed into a stored value, and back again."""

import datetime

import pytest

from gridly.coltypes import (
    OPTION_COLORS,
    ColumnType,
    ValidationError,
    assign_colors,
    color_style,
    decode,
    display,
    encode,
    parse,
)

T = ColumnType


@pytest.mark.parametrize(
    "coltype, typed, expected",
    [
        (T.TEXT, "hello", "hello"),
        (T.TEXT, "  padded  ", "padded"),
        (T.TEXT, "two\nlines", "two\nlines"),
        (T.NUMBER, "42", 42),
        (T.NUMBER, "3.5", 3.5),
        (T.NUMBER, "1,200", 1200),
        (T.NUMBER, "1_000", 1000),
        (T.NUMBER, "-7", -7),
        (T.NUMBER, "42.0", 42),
        (T.BOOLEAN, "yes", True),
        (T.BOOLEAN, "Y", True),
        (T.BOOLEAN, "TRUE", True),
        (T.BOOLEAN, "1", True),
        (T.BOOLEAN, "no", False),
        (T.BOOLEAN, "off", False),
        (T.DATE, "2026-09-12", datetime.date(2026, 9, 12)),
        (T.DATE, "2026/09/12", datetime.date(2026, 9, 12)),
        (T.DATE, "12/09/2026", datetime.date(2026, 9, 12)),
        (T.DATE, "12 Sep 2026", datetime.date(2026, 9, 12)),
    ],
)
def test_parse_accepts(coltype, typed, expected):
    assert parse(coltype, typed, []) == expected


@pytest.mark.parametrize("coltype", list(T))
def test_nothing_typed_means_no_value(coltype):
    assert parse(coltype, "", ["Low"]) is None
    assert parse(coltype, "   ", ["Low"]) is None


@pytest.mark.parametrize(
    "coltype, typed",
    [
        (T.NUMBER, "abc"),
        (T.NUMBER, "12 34"),
        (T.NUMBER, "inf"),
        (T.NUMBER, "nan"),
        (T.BOOLEAN, "maybe"),
        (T.DATE, "the 12th"),
        (T.DATE, "2026-13-45"),
        (T.SELECT, "Mid"),
    ],
)
def test_parse_refuses(coltype, typed):
    with pytest.raises(ValidationError):
        parse(coltype, typed, ["Low", "High"])


def test_a_dropdown_matches_regardless_of_case_but_stores_the_option():
    assert parse(T.SELECT, "low", ["Low", "High"]) == "Low"


def test_today():
    assert parse(T.DATE, "today", []) == datetime.date.today()


@pytest.mark.parametrize(
    "coltype, value",
    [
        (T.TEXT, "hello"),
        (T.TEXT, "two\nlines"),
        (T.NUMBER, 42),
        (T.NUMBER, -3.5),
        (T.BOOLEAN, True),
        (T.BOOLEAN, False),
        (T.DATE, datetime.date(2026, 9, 12)),
        (T.SELECT, "Low"),
    ],
)
def test_a_value_survives_the_round_trip_to_storage(coltype, value):
    assert decode(coltype, encode(coltype, value)) == value


@pytest.mark.parametrize("coltype", list(T))
def test_no_value_survives_too(coltype):
    assert encode(coltype, None) is None
    assert decode(coltype, None) is None


@pytest.mark.parametrize(
    "coltype, stored", [(T.NUMBER, "abc"), (T.DATE, "not-a-date"), (T.DATE, "")]
)
def test_junk_in_the_file_reads_as_no_value(coltype, stored):
    """A column retyped by hand can leave values the new type cannot read."""
    assert decode(coltype, stored) is None


@pytest.mark.parametrize(
    "coltype, value, shown",
    [
        (T.BOOLEAN, True, "yes"),
        (T.BOOLEAN, False, "no"),
        (T.NUMBER, 42, "42"),
        (T.NUMBER, 1.5, "1.5"),
        (T.DATE, datetime.date(2026, 9, 12), "2026-09-12"),
        (T.TEXT, "hello", "hello"),
    ],
)
def test_display(coltype, value, shown):
    assert display(coltype, value) == shown


def test_what_is_displayed_can_be_typed_back_in():
    for coltype, value in [
        (T.NUMBER, 1.5),
        (T.BOOLEAN, False),
        (T.DATE, datetime.date(2026, 9, 12)),
        (T.TEXT, "hello"),
    ]:
        assert parse(coltype, display(coltype, value), []) == value


# ----------------------------------------------------------------- colours

def test_colours_are_handed_out_in_order():
    assert assign_colors(["Low", "Medium", "High"], {}) == {
        "Low": "green",
        "Medium": "yellow",
        "High": "red",
    }


def test_a_chosen_colour_is_kept_and_not_handed_to_anyone_else():
    colors = assign_colors(["Low", "Medium", "High"], {"Low": "red"})
    assert colors["Low"] == "red"
    assert "red" not in [colors["Medium"], colors["High"]]


def test_more_options_than_colours_starts_over_rather_than_failing():
    options = [f"option {n}" for n in range(len(OPTION_COLORS) + 3)]
    colors = assign_colors(options, {})
    assert len(colors) == len(options)
    assert set(colors.values()) <= set(OPTION_COLORS)


def test_every_colour_is_different_from_every_other():
    assert len(set(OPTION_COLORS.values())) == len(OPTION_COLORS)


def test_an_unknown_colour_name_draws_as_nothing_rather_than_crashing():
    assert color_style("chartreuse") == ""
    assert color_style(None) == ""
    assert color_style("green") == OPTION_COLORS["green"]
