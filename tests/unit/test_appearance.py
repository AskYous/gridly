"""The measurements behind how the grid is drawn."""

import datetime

import pytest
from rich.text import Text

from gridly.coltypes import ColumnType
from gridly.store import Column
from gridly.appearance import (
    CENTRED,
    COLUMN_CAPS,
    COLUMN_WIDTHS,
    MAX_WRAP_LINES,
    MIN_FIT_WIDTH,
    OVERFLOWS,
    PADDING,
    Appearance,
    centred,
    fair_cap,
    fit,
    lines_needed,
    render,
    stretched,
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


# --------------------------------------------------------------- placing

@pytest.mark.parametrize(
    "height, expected_blank_lines", [(1, 0), (2, 0), (3, 1), (4, 1), (5, 2), (11, 5)]
)
def test_a_one_line_value_sits_in_the_middle(height, expected_blank_lines):
    out = centred(Text("x"), height).plain
    assert len(out) - len(out.lstrip("\n")) == expected_blank_lines


def test_a_value_as_tall_as_its_row_is_not_pushed_down():
    assert centred(Text("a\nb\nc"), 3).plain == "a\nb\nc"


def test_centring_can_be_told_how_tall_the_value_really_is():
    """Once wrapped, a value takes more lines than its newlines suggest."""
    assert centred(Text("x"), 5, lines=3).plain == "\nx"


def test_centring_keeps_how_the_value_is_laid_out_across_its_column():
    assert centred(Text("✓", justify="center"), 5).justify == "center"


def test_a_short_value_is_not_stranded_at_the_top_of_a_tall_row():
    """Nine lines in one cell and a word in the next: the word goes in the middle."""
    appearance = Appearance(padded=True, overflow="wrap", column_width="small")
    cells = [Text("t\n" * 8 + "t"), Text("Sunday")]
    widths = [16, 16]
    height = appearance.row_height(cells, widths)
    placed = appearance.place(cells, widths, height)
    above = len(placed[1].plain) - len(placed[1].plain.lstrip("\n"))
    assert height == 11
    assert above == (height - 1) // 2, above


def test_values_of_the_same_height_line_up_with_each_other():
    appearance = Appearance(overflow="wrap", column_width="small")
    cells = [Text("a" * 40), Text("b" * 40), Text("c")]
    widths = [16, 16, 16]
    height = appearance.row_height(cells, widths)
    placed = appearance.place(cells, widths, height)
    starts = [len(c.plain) - len(c.plain.lstrip("\n")) for c in placed]
    assert starts[0] == starts[1]


def test_a_padded_row_is_taller_than_what_it_holds_by_the_padding():
    appearance = Appearance(padded=True, overflow="wrap", column_width="small")
    assert appearance.row_height([Text("a" * 45)], [16]) == 3 + 2 * PADDING


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


def test_spare_room_is_shared_out_evenly():
    assert stretched([3, 4, 5], 30) == [9, 10, 11]


def test_what_does_not_divide_goes_to_the_first_columns():
    assert stretched([3, 4, 5], 32) == [10, 11, 11]


def test_nothing_to_stretch():
    assert stretched([], 30) == []


# -------------------------------------------------------------- the settings

def test_the_defaults_are_all_real_choices():
    view = Appearance()
    assert view.column_width in COLUMN_WIDTHS
    assert view.overflow in OVERFLOWS
    assert isinstance(view.padded, bool)


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
    config.write_text('{"column_width": "enormous", "padded": 7, "overflow": null}')
    assert Appearance.load() == Appearance()




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
    view = Appearance(padded=True, overflow="ellipsis")
    assert view.row_height([Text(LONG)], [10]) == 1 + 2 * PADDING


def test_a_wrapping_row_is_as_tall_as_its_tallest_value():
    view = Appearance(overflow="wrap", column_width="small")
    assert view.row_height([Text("short"), Text("a" * 40)], [10, 10]) == 4


def test_no_value_gets_to_own_the_whole_screen():
    view = Appearance(overflow="wrap", column_width="small")
    assert view.row_height([Text("a" * 5000)], [10]) == MAX_WRAP_LINES


@pytest.mark.parametrize("width", [w for w in COLUMN_WIDTHS if w != "fit"])
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


def test_fitting_fills_a_screen_wider_than_the_table():
    view = Appearance(column_width="fit")
    labels = [Text("Done"), Text("Note")]
    cells = [[Text("yes")], [Text("short")]]
    available, gutters, row_label = 80, 2, 2
    widths = view.widths(labels, cells, row_label, available, gutters)
    spent = sum(w + gutters for w in widths) + row_label + gutters
    assert spent == available, (widths, spent)
    assert widths[0] > len("Done") and widths[1] > len("short"), widths


def test_fitting_with_no_room_yet_falls_back_to_what_values_need():
    """The table has no width until it has been laid out once."""
    view = Appearance(column_width="fit")
    assert view.widths([Text("A")], [[Text("abc")]], 0, 0, 2) == [3]


# ------------------------------------------------------- horizontal placing

def test_a_tick_sits_in_the_middle_of_its_column():
    """A boolean is one character in a column as wide as its heading."""
    for value in (True, False):
        assert render(column(ColumnType.BOOLEAN), value, 1).justify == "center"


@pytest.mark.parametrize(
    "coltype, value",
    [
        (ColumnType.BOOLEAN, True),
        (ColumnType.DATE, datetime.date(2026, 9, 13)),
        (ColumnType.TIME, datetime.time(9, 30)),
        (ColumnType.SELECT, "Low"),
    ],
)
def test_short_and_even_values_go_down_the_middle(coltype, value):
    assert render(column(coltype, options=["Low"]), value, 1).justify == "center"


@pytest.mark.parametrize(
    "coltype, value",
    [(ColumnType.TEXT, "x"), (ColumnType.TEXT, "a\nb"), (ColumnType.NUMBER, 1)],
)
def test_text_and_numbers_stay_against_the_left_edge(coltype, value):
    """Prose and figures are read down their left edge, not from the middle."""
    assert render(column(coltype), value, 1).justify is None


@pytest.mark.parametrize("coltype", list(ColumnType))
def test_an_empty_cell_is_placed_like_the_rest_of_its_column(coltype):
    expected = "center" if coltype in CENTRED else None
    assert render(column(coltype), None, 1).justify == expected


@pytest.mark.parametrize("coltype", list(ColumnType))
def test_turning_centring_off_puts_everything_against_the_left(coltype):
    appearance = Appearance(centred=False)
    assert appearance.cell(column(coltype, options=["Low"]), None).justify is None


@pytest.mark.parametrize("coltype", list(ColumnType))
def test_it_is_on_unless_it_is_turned_off(coltype):
    appearance = Appearance()
    expected = "center" if coltype in CENTRED else None
    assert appearance.cell(column(coltype, options=["Low"]), None).justify == expected


def test_the_choice_is_remembered(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    Appearance(centred=False).save()
    assert Appearance.load().centred is False


def test_centring_a_row_keeps_how_the_value_is_placed_across_it():
    cell = render(column(ColumnType.BOOLEAN), True, 1)
    assert centred(cell, 5).justify == "center"


def test_a_drawn_boolean_cell_is_still_centred():
    """Through Appearance.cell, which is what the grid actually gets."""
    cell = Appearance(padded=True).cell(column(ColumnType.BOOLEAN), True)
    assert cell.justify == "center"
