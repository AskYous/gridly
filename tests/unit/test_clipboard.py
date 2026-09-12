"""Reading and writing the tab-separated text spreadsheets put on the clipboard."""

import pytest

from gridly.clipboard import format_block, parse_block


@pytest.mark.parametrize(
    "text, expected",
    [
        ("a\tb\nc\td\n", [["a", "b"], ["c", "d"]]),
        ("a\tb\nc\td", [["a", "b"], ["c", "d"]]),          # no trailing newline
        ("one", [["one"]]),                                  # a single cell
        ("a\t\tc\n", [["a", "", "c"]]),                      # a blank in the middle
        ('a\t"has\ttab"\tb\n', [["a", "has\ttab", "b"]]),
        ('"two\nlines"\tx\n', [["two\nlines", "x"]]),
        ('"say ""hi"""\n', [['say "hi"']]),
        ("a\r\nb\r\n", [["a"], ["b"]]),                      # windows line endings
        ("a\rb\r", [["a"], ["b"]]),                          # old mac ones
        ("", []),
        ("\n", []),
        ("   ", [["   "]]),                                  # spaces are a value
    ],
)
def test_parse_block(text, expected):
    assert parse_block(text) == expected


@pytest.mark.parametrize(
    "block",
    [
        [["a", "b"], ["c", "d"]],
        [["only"]],
        [["has\ttab", "plain"]],
        [["two\nlines"]],
        [['quote"inside']],
        [["", "", ""]],
        [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"]],
        [["عربي", "日本語"]],
    ],
)
def test_what_is_copied_pastes_back_the_same(block):
    assert parse_block(format_block(block)) == block


def test_a_block_is_written_the_way_a_spreadsheet_expects():
    assert format_block([["a", "b"], ["c", "d"]]) == "a\tb\nc\td\n"


def test_only_the_cells_that_need_it_are_quoted():
    assert format_block([["plain", "has\ttab"]]) == 'plain\t"has\ttab"\n'
