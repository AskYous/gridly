"""A row's comments, at the level the sheet keeps them."""

import sqlite3
from datetime import datetime

import pytest

from gridly.coltypes import ColumnType
from gridly.store import Sheet

T = ColumnType
MORNING = datetime(2026, 9, 20, 9, 12, 30)
AFTERNOON = datetime(2026, 9, 21, 14, 5, 0)


@pytest.fixture
def sheet(tmp_path):
    sheet = Sheet(tmp_path / "s.gridly")
    sheet.add_row()           # two, so one row's comments can be told apart
    sheet._undo.clear()
    yield sheet
    sheet.close()


def first(sheet):
    return sheet.rows()[0].id


def bodies(sheet, row_id):
    return [comment.body for comment in sheet.comments(row_id)]


def test_a_row_starts_with_none(sheet):
    assert sheet.comments(first(sheet)) == []
    assert sheet.rows()[0].comment_count == 0


def test_newest_comes_first(sheet):
    row = first(sheet)
    sheet.add_comment(row, "older", now=MORNING)
    sheet.add_comment(row, "newer", now=AFTERNOON)
    assert bodies(sheet, row) == ["newer", "older"]


def test_two_in_the_same_second_keep_the_order_they_were_written(sheet):
    row = first(sheet)
    sheet.add_comment(row, "first", now=MORNING)
    sheet.add_comment(row, "second", now=MORNING)
    assert bodies(sheet, row) == ["second", "first"]


def test_it_is_stamped_with_when_it_was_written(sheet):
    row = first(sheet)
    sheet.add_comment(row, "hello", now=MORNING)
    (comment,) = sheet.comments(row)
    assert comment.created == "2026-09-20 09:12:30"
    assert comment.edited == ""


def test_it_keeps_its_lines_but_not_the_blank_ones_around_them(sheet):
    row = first(sheet)
    sheet.add_comment(row, "\n  Called the vendor.\nFix lands Thursday.\n\n")
    assert bodies(sheet, row) == ["Called the vendor.\nFix lands Thursday."]


@pytest.mark.parametrize("body", ["", "   ", "\n\n"])
def test_an_empty_comment_is_refused_and_leaves_nothing_to_undo(sheet, body):
    with pytest.raises(ValueError):
        sheet.add_comment(first(sheet), body)
    assert sheet.undoable is None


def test_each_row_has_its_own(sheet):
    one, two = [row.id for row in sheet.rows()]
    sheet.add_comment(one, "about one")
    sheet.add_comment(two, "about two")
    sheet.add_comment(two, "more about two")
    assert bodies(sheet, one) == ["about one"]
    assert [row.comment_count for row in sheet.rows()] == [1, 2]


def test_rewording_keeps_when_it_was_written_and_says_it_was_edited(sheet):
    row = first(sheet)
    comment_id = sheet.add_comment(row, "draft", now=MORNING)
    sheet.edit_comment(comment_id, "final", now=AFTERNOON)
    (comment,) = sheet.comments(row)
    assert comment.body == "final"
    assert comment.created == "2026-09-20 09:12:30"
    assert comment.edited == "2026-09-21 14:05:00"


def test_rewording_to_the_same_words_is_not_an_edit(sheet):
    row = first(sheet)
    comment_id = sheet.add_comment(row, "same", now=MORNING)
    sheet._undo.clear()
    sheet.edit_comment(comment_id, "  same\n", now=AFTERNOON)
    assert sheet.comments(row)[0].edited == ""
    assert sheet.undoable is None


def test_rewording_to_nothing_is_refused(sheet):
    comment_id = sheet.add_comment(first(sheet), "keep me")
    with pytest.raises(ValueError):
        sheet.edit_comment(comment_id, "  ")
    assert bodies(sheet, first(sheet)) == ["keep me"]


def test_rewording_one_that_is_not_there(sheet):
    with pytest.raises(KeyError):
        sheet.edit_comment(999, "anything")


def test_deleting_one_leaves_the_rest(sheet):
    row = first(sheet)
    keep = sheet.add_comment(row, "keep", now=MORNING)
    drop = sheet.add_comment(row, "drop", now=AFTERNOON)
    sheet.delete_comment(drop)
    assert [c.id for c in sheet.comments(row)] == [keep]


def test_a_removed_comment_can_be_put_back_as_it_was(sheet):
    row = first(sheet)
    sheet.add_comment(row, "older", now=MORNING)
    middle = sheet.add_comment(row, "middle", now=AFTERNOON)
    sheet.edit_comment(middle, "middle, reworded", now=AFTERNOON)
    sheet.add_comment(row, "newest", now=datetime(2026, 9, 22, 8, 0))
    before = sheet.comments(row)
    sheet.delete_comment(middle)
    sheet.restore_comment(before[1])
    assert sheet.comments(row) == before
    assert sheet.undo() == "restore comment"
    assert bodies(sheet, row) == ["newest", "older"]


def test_deleting_the_row_takes_its_comments(sheet):
    one, two = [row.id for row in sheet.rows()]
    sheet.add_comment(one, "goes")
    sheet.add_comment(two, "stays")
    sheet.delete_row(one)
    left = sheet.db.execute("SELECT body FROM comments").fetchall()
    assert [r["body"] for r in left] == ["stays"]


def test_duplicating_a_row_does_not_copy_its_log(sheet):
    row = first(sheet)
    sheet.add_comment(row, "about the original")
    copy = sheet.duplicate_row(row)
    assert sheet.comments(copy) == []
    assert bodies(sheet, row) == ["about the original"]


@pytest.mark.parametrize(
    "label, change",
    [
        ("add comment", lambda s, c: s.add_comment(first(s), "another")),
        ("edit comment", lambda s, c: s.edit_comment(c, "reworded")),
        ("delete comment", lambda s, c: s.delete_comment(c)),
        ("delete row", lambda s, c: s.delete_row(first(s))),
    ],
)
def test_every_change_to_a_comment_can_be_taken_back(sheet, label, change):
    comment_id = sheet.add_comment(first(sheet), "original", now=MORNING)
    sheet._undo.clear()
    before = sheet.comments(first(sheet))
    change(sheet, comment_id)
    assert sheet.undo() == label
    assert sheet.comments(first(sheet)) == before
    sheet.redo()
    assert sheet.comments(first(sheet)) != before


def test_they_are_still_there_after_reopening(tmp_path):
    path = tmp_path / "s.gridly"
    sheet = Sheet(path)
    sheet.add_comment(sheet.rows()[0].id, "written down", now=MORNING)
    sheet.close()
    again = Sheet(path)
    assert bodies(again, again.rows()[0].id) == ["written down"]
    again.close()


def test_a_sheet_from_before_comments_picks_them_up(tmp_path):
    """A file written before the comments table existed opens and takes them."""
    path = tmp_path / "old.gridly"
    Sheet(path).close()
    db = sqlite3.connect(path)
    db.execute("DROP TABLE comments")
    db.commit()
    db.close()

    sheet = Sheet(path)
    row = sheet.rows()[0].id
    assert sheet.comments(row) == []
    sheet.add_comment(row, "first word")
    assert bodies(sheet, row) == ["first word"]
    sheet.close()
