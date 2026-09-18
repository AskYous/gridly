"""Where a column's values sit across it."""

import pytest

from gridly.appearance import ALIGNMENTS, CENTRED, DEFAULT_CENTRED, render, sits
from gridly.coltypes import ColumnType
from gridly.store import Column

T = ColumnType


def column(coltype=T.TEXT, align=""):
    return Column(1, "Thing", coltype, align=align)


@pytest.mark.parametrize("align", ["left", "center", "right"])
@pytest.mark.parametrize("coltype", list(T))
def test_a_column_that_has_been_told_sits_where_it_was_told(align, coltype):
    """Whatever its type, and whichever way the sheet-wide setting is set."""
    assert sits(column(coltype, align), middle=True) == align
    assert sits(column(coltype, align), middle=False) == align


@pytest.mark.parametrize("coltype", CENTRED)
def test_automatic_still_centres_the_types_that_suit_it(coltype):
    assert sits(column(coltype), middle=True) == "center"
    assert sits(column(coltype), middle=False) is None


@pytest.mark.parametrize("coltype", [T.TEXT, T.NUMBER])
def test_automatic_still_leaves_text_and_numbers_where_they_were(coltype):
    assert sits(column(coltype), middle=True) is None
    assert sits(column(coltype), middle=False) is None


def test_an_alignment_nobody_recognises_falls_back_to_automatic():
    """A file edited by hand should not be able to break the drawing."""
    assert sits(column(T.NUMBER, "sideways"), middle=True) is None
    assert sits(column(T.DATE, "sideways"), middle=True) == "center"


def test_the_form_offers_exactly_what_the_drawing_understands():
    assert set(ALIGNMENTS) == {"", "left", "center", "right"}
    for key in ALIGNMENTS:
        if key:
            assert sits(column(T.TEXT, key)) == key


@pytest.mark.parametrize(
    "coltype, value",
    [
        (T.TEXT, "hello"),
        (T.NUMBER, 42),
        (T.BOOLEAN, True),
        (T.SELECT, "New"),
    ],
)
def test_every_type_of_value_is_drawn_where_the_column_says(coltype, value):
    """Numbers and text included, which never moved before there was a say."""
    for align in ("left", "center", "right"):
        col = Column(1, "Thing", coltype, options=["New"], align=align)
        assert render(col, value, 1).justify == align


def test_an_empty_cell_goes_where_its_column_goes_too():
    assert render(column(T.NUMBER, "right"), None, 1).justify == "right"


def test_the_default_is_what_the_sheet_did_before_any_of_this():
    assert DEFAULT_CENTRED is True
    assert sits(column(T.DATE)) == "center"
    assert sits(column(T.TEXT)) is None
