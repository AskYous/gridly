"""Reading and writing clock times."""

import datetime

import pytest

from gridly.coltypes import (
    TIME_FORMATS,
    ColumnType,
    ValidationError,
    decode,
    display,
    encode,
    parse,
)

T = ColumnType.TIME


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("9:30", (9, 30)),
        ("09:30", (9, 30)),
        ("14:5", (14, 5)),
        ("23:59", (23, 59)),
        ("00:00", (0, 0)),
        ("7", (7, 0)),
        ("9:30 pm", (21, 30)),
        ("9:30pm", (21, 30)),
        ("9:30 PM", (21, 30)),
        ("9:30 p.m.", (21, 30)),
        ("12:00 am", (0, 0)),
        ("12 am", (0, 0)),
        ("12:30 pm", (12, 30)),
        ("12 pm", (12, 0)),
        ("  9:30  ", (9, 30)),
    ],
)
def test_times_it_accepts(typed, expected):
    assert parse(T, typed) == datetime.time(*expected)


def test_seconds_are_read_when_the_column_keeps_them():
    assert parse(T, "9:30:15", fmt="seconds") == datetime.time(9, 30, 15)


def test_seconds_are_dropped_when_the_column_does_not_show_them():
    """What is stored is what is on screen, so nothing hides in the file."""
    assert parse(T, "9:30:15") == datetime.time(9, 30)


@pytest.mark.parametrize(
    "typed",
    ["25:00", "9:60", "9:30:60", "abc", "13 pm", "0 pm", "-1:00", "9:30:15:20",
     "9:", ":30", "half nine", "9;30"],
)
def test_times_it_refuses(typed):
    with pytest.raises(ValidationError):
        parse(T, typed)


def test_nothing_typed_is_no_time():
    assert parse(T, "") is None
    assert parse(T, "   ") is None


@pytest.mark.parametrize("fmt", list(TIME_FORMATS))
def test_a_time_survives_the_round_trip_to_storage(fmt):
    value = parse(T, "9:30:15", fmt=fmt)
    assert decode(T, encode(T, value)) == value


@pytest.mark.parametrize(
    "fmt, shown", [("", "09:30"), ("seconds", "09:30:15")]
)
def test_how_a_time_is_written(fmt, shown):
    assert display(T, datetime.time(9, 30, 15), fmt) == shown


def test_a_time_is_always_written_on_the_clock_however_it_was_typed():
    """Typed as pm, shown on a twenty-four hour clock, which sorts and reads."""
    assert display(T, parse(T, "9:30 pm")) == "21:30"


@pytest.mark.parametrize("fmt", list(TIME_FORMATS))
def test_what_is_shown_can_be_typed_back_in(fmt):
    value = parse(T, "21:30:45", fmt=fmt)
    assert parse(T, display(T, value, fmt), fmt=fmt) == value
