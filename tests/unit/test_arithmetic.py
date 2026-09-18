"""The small arithmetic a column can be worked out by."""

import pytest

from gridly.arithmetic import (
    FormulaError,
    columns_in,
    evaluate,
    parse,
    rename,
    tokenize,
)

NAMES = ["Hours", "Hours worked", "Rate", "Bonus"]


def work(text, **values):
    return evaluate(parse(text, NAMES), values)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hours * 55", 165),
        ("Hours*55", 165),
        ("  Hours   *   55  ", 165),
        ("Hours + 1", 4),
        ("Hours - 1", 2),
        ("Hours / 2", 1.5),
        ("55", 55),
        ("1.5", 1.5),
        (".5", 0.5),
        ("1,200", 1200),
        ("-Hours", -3),
        ("+Hours", 3),
        ("--Hours", 3),
        ("(Hours)", 3),
    ],
)
def test_sums_it_works_out(text, expected):
    assert work(text, Hours=3) == expected


def test_multiplication_happens_before_addition():
    assert work("1 + Hours * 2", Hours=3) == 7
    assert work("(1 + Hours) * 2", Hours=3) == 8


def test_it_reads_left_to_right_where_that_matters():
    assert work("100 - Hours - 1", Hours=3) == 96
    assert work("100 / Hours / 2", Hours=5) == 10


def test_the_longest_column_name_wins():
    """A sheet with Hours and Hours worked reads the one that is written."""
    assert columns_in(parse("Hours worked * 2", NAMES)) == ["Hours worked"]
    assert columns_in(parse("Hours * 2", NAMES)) == ["Hours"]


def test_a_name_is_read_whatever_case_it_is_typed_in():
    assert columns_in(parse("hours * 2", NAMES)) == ["Hours"]


def test_what_a_sum_reads_is_listed_once_in_the_order_it_reads_them():
    assert columns_in(parse("Rate * Hours + Rate", NAMES)) == ["Rate", "Hours"]


@pytest.mark.parametrize(
    "text",
    [
        "Hrs * 2",        # no such column
        "Hours *",        # nothing after the operator
        "* 3",            # nothing before it
        "(Hours",         # bracket never closed
        "Hours) * 2",     # bracket closing nothing
        "Hours 3",        # two values with nothing joining them
        "",               # nothing at all
        "   ",
        "Hours & 2",      # not arithmetic
    ],
)
def test_sums_it_refuses(text):
    with pytest.raises(FormulaError):
        parse(text, NAMES)


def test_what_it_refuses_says_which_word_it_did_not_know():
    with pytest.raises(FormulaError, match="Hrs"):
        parse("Hrs * 2", NAMES)


def test_dividing_by_nothing_is_no_answer_rather_than_a_crash():
    assert work("Hours / 0", Hours=3) is None
    assert work("Hours / (Rate - Rate)", Hours=3, Rate=2) is None


def test_a_row_nobody_has_filled_in_stays_empty():
    """Rather than reading as zero and paying out on every blank row."""
    assert work("Hours * 55", Hours=None) is None
    assert work("Hours + Bonus", Hours=None, Bonus=None) is None


def test_a_blank_beside_a_value_counts_as_nothing():
    assert work("Hours + Bonus", Hours=3, Bonus=None) == 3


def test_a_sum_of_only_numbers_needs_no_row_at_all():
    assert work("2 + 2") == 4


def test_float_noise_is_rounded_away():
    assert work("Hours * 1.15", Hours=0.1) == 0.115
    assert work("0.1 + 0.2") == 0.3


def test_a_value_that_is_not_a_number_counts_as_nothing():
    assert work("Hours + Bonus", Hours=3, Bonus="later") == 3


def test_nothing_but_arithmetic_gets_through_the_tokenizer():
    """No calls, no attributes, no names the sheet did not hand it."""
    for attempt in ["__import__", "Hours.real", "open('x')", "1 if 1 else 2"]:
        with pytest.raises(FormulaError):
            parse(attempt, NAMES)


def test_tokenize_gives_back_the_columns_it_recognised():
    kinds = [kind for kind, _ in tokenize("Hours * 55", NAMES)]
    assert kinds == ["column", "*", "number"]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Hours*55", "Worked * 55"),
        ("(Hours - 8) * Rate", "(Worked - 8) * Rate"),
        ("Hours worked + Hours", "Hours worked + Worked"),
        ("Rate * 2", "Rate * 2"),
    ],
)
def test_renaming_a_column_moves_the_sums_that_read_it(text, expected):
    assert rename(text, NAMES, "Hours", "Worked") == expected


def test_a_sum_that_does_not_read_is_left_exactly_as_it_was():
    assert rename("Hrs * 2", NAMES, "Hours", "Worked") == "Hrs * 2"
