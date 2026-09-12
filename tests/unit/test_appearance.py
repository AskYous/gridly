"""The measurements behind how the grid is drawn."""

import os
import tempfile

import pytest
from rich.text import Text

from gridly.coltypes import ColumnType
from gridly.store import Column
from gridly.appearance import (
    COLUMN_CAPS,
    COLUMN_WIDTHS,
    MAX_WRAP_LINES,
    MIN_FIT_WIDTH,
    OVERFLOWS,
    ROW_SIZES,
    Appearance,
    centred,
    fair_cap,
    fit,
    lines_needed,
    widest,
)

LONG = "a value far too long to sit in one narrow column"


def column(coltype=ColumnType.TEXT, **kwargs):
    return Column(id=1, name="Col", type=coltype, **kwargs)


# --------------------------------------------------------------- measuring

@pytest.mark.parametrize(
    "text, expected",
    [("abc", 3), ("", 0), ("one\nlonger line", 11), ("héllo", 5), ("日本", 4)],
)
def test_widest_is_the_longest_line(text, expected):
    assert widest(Text(text)) == expected


@pytest.mark.parametrize(
    "text, width, expected",
    [
        ("abcdefghij", 10, 1),
        ("abcdefghij", 5, 2),
        ("abcdefghij", 3, 4),
        ("two\nlines", 10, 2),
        ("", 10, 1),
        ("abc", None, 3),
    ],
)
def test_lines_needed_counts_what_wrapping_will_produce(text, width, expected):
    assert lines_needed(Text(text), width) == expected


def test_lines_needed_survives_a_zero_width():
    assert lines_needed(Text("abc"), 0) >= 1


# ------------------------------------------------------------------ fitting

def test_a_value_fits_on_one_line_by_marking_its_breaks():
    assert fit("first\nsecond\nthird", 1).plain == "first ⏎ second ⏎ third"


def test_a_taller_row_uses_its_lines_and_squeezes_only_the_rest():
    assert fit("a\nb\nc\nd", 3).plain == "a\nb\nc ⏎ d"


def test_a_value_that_fits_is_left_alone():
    assert fit("a\nb", 3).plain == "a\nb"


def test_tabs_would_break_the_columns_so_they_become_spaces():
    assert "\t" not in fit("a\tb", 1).plain


# ---------------------------------------------------------------- centring

@pytest.mark.parametrize(
    "height, expected_blank_lines",
    [(1, 0), (2, 0), (3, 1), (4, 1), (5, 2)],
)
def test_a_one_line_value_sits_in_the_middle(height, expected_blank_lines):
    out = centred(Text("x"), height).plain
    assert len(out) - len(out.lstrip("\n")) == expected_blank_lines


def test_a_value_as_tall_as_its_row_is_not_pushed_down():
    assert centred(Text("a\nb\nc"), 3).plain == "a\nb\nc"


def test_centring_can_be_told_how_tall_the_value_really_is():
    """Once wrapped, a value takes more lines than its newlines suggest."""
    assert centred(Text("x"), 5, lines=3).plain == "\nx"


# ------------------------------------------------------------ sharing width

def test_nothing_is_squeezed_when_everything_fits():
    assert fair_cap([3, 4, 5], 30, MIN_FIT_WIDTH) == 5


def test_the_wide_column_pays_for_the_squeeze():
    assert fair_cap([3, 4, 40], 30, MIN_FIT_WIDTH) == 23


def test_two_wide_columns_share_what_is_left():
    assert fair_cap([2, 40, 40], 30, MIN_FIT_WIDTH) == 14


def test_a_hopeless_budget_stops_at_the_floor():
    assert fair_cap([40, 40, 40], 3, MIN_FIT_WIDTH) == MIN_FIT_WIDTH


def test_no_columns_at_all():
    assert fair_cap([], 30, MIN_FIT_WIDTH) == MIN_FIT_WIDTH


# -------------------------------------------------------------- the settings

def test_the_defaults_are_all_real_choices():
    view = Appearance()
    assert view.column_width in COLUMN_WIDTHS
    assert view.overflow in OVERFLOWS
    assert view.row_size in ROW_SIZES


def test_cycling_comes_back_round(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    view = Appearance()
    for _ in COLUMN_WIDTHS:
        view.cycle_column_width()
    assert view.column_width == Appearance().column_width


def test_a_setting_is_written_when_it_changes(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    view = Appearance()
    view.cycle_overflow()
    assert Appearance.load().overflow == view.overflow


def test_unreadable_settings_fall_back_to_the_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    config = tmp_path / "gridly" / "config.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"column_width": "enormous", "row_size": 7, "overflow": null}')
    assert Appearance.load() == Appearance()


def test_which_way_round_the_grid_runs_is_not_remembered(tmp_path, monkeypatch):
    """It is a quick look at a wide sheet, not a preference."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    view = Appearance(flipped=True)
    view.save()
    assert Appearance.load().flipped is False


# --------------------------------------------------------------- drawing

def test_wrapping_needs_something_to_wrap_against():
    assert Appearance(overflow="wrap", column_width="unlimited").wrapping is False
    assert Appearance(overflow="wrap", column_width="fit").wrapping is True
    assert Appearance(overflow="ellipsis", column_width="small").wrapping is False


def test_a_capped_cell_is_cut_rather_than_wrapped():
    cell = Appearance(column_width="small", overflow="ellipsis").cell(column(), LONG)
    assert cell.no_wrap and cell.overflow == "ellipsis"


def test_a_wrapping_cell_is_left_whole_for_the_row_to_grow_around():
    cell = Appearance(column_width="small", overflow="wrap").cell(column(), LONG)
    assert not cell.no_wrap


def test_a_fixed_row_is_always_the_same_height():
    view = Appearance(row_size="large", overflow="ellipsis")
    assert view.row_height([Text(LONG)], [10]) == ROW_SIZES["large"]


def test_a_wrapping_row_is_as_tall_as_its_tallest_value():
    view = Appearance(row_size="small", overflow="wrap", column_width="small")
    assert view.row_height([Text("short"), Text("a" * 40)], [10, 10]) == 4


def test_no_value_gets_to_own_the_whole_screen():
    view = Appearance(overflow="wrap", column_width="small")
    assert view.row_height([Text("a" * 5000)], [10]) == MAX_WRAP_LINES


@pytest.mark.parametrize("width", list(COLUMN_WIDTHS))
def test_a_narrow_column_is_never_padded_out(width):
    view = Appearance(column_width=width)
    widths = view.widths([Text("Done")], [[Text("yes")]], 3, 200, 2)
    assert widths[0] in (None, 4), widths


def test_a_cap_is_a_maximum():
    view = Appearance(column_width="small")
    widths = view.widths([Text("Note")], [[Text(LONG)]], 3, 200, 2)
    assert widths == [COLUMN_CAPS["small"]]


def test_uncapped_columns_are_left_for_the_table_to_size():
    view = Appearance(column_width="unlimited")
    assert view.widths([Text("Note")], [[Text(LONG)]], 3, 200, 2) == [None]


def test_fitting_never_spends_more_room_than_there_is():
    view = Appearance(column_width="fit")
    labels = [Text("A"), Text("B"), Text("C")]
    cells = [[Text(LONG)], [Text("x")], [Text(LONG)]]
    available, gutters, row_label = 40, 2, 2
    widths = view.widths(labels, cells, row_label, available, gutters)
    spent = sum(w + gutters for w in widths) + row_label + gutters
    assert spent <= available, (widths, spent)


def test_fitting_with_no_room_yet_falls_back_to_what_values_need():
    """The table has no width until it has been laid out once."""
    view = Appearance(column_width="fit")
    assert view.widths([Text("A")], [[Text("abc")]], 0, 0, 2) == [3]
