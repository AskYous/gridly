"""Taking changes back, at the level the sheet works at."""

import pytest

from gridly.coltypes import ColumnType
from gridly.store import UNDO_LIMIT, Sheet

T = ColumnType


@pytest.fixture
def sheet(tmp_path):
    sheet = Sheet(tmp_path / "s.gridly")
    for seeded in sheet.columns():
        sheet.delete_column(seeded.id)
    sheet.add_column("Name", T.TEXT)
    sheet.add_column("Qty", T.NUMBER)
    sheet.add_row()
    sheet._undo.clear()
    yield sheet
    sheet.close()


def snapshot(sheet):
    columns = sheet.columns()
    return [c.name for c in columns], [
        [r.values.get(c.id) for c in columns] for r in sheet.rows()
    ]


def test_a_new_sheet_has_nothing_to_undo(tmp_path):
    assert Sheet(tmp_path / "new.gridly").undoable is None


@pytest.mark.parametrize(
    "label, change",
    [
        ("edit cell", lambda s: s.set_cell(s.rows()[0].id, s.columns()[0].id, "x")),
        ("add row", lambda s: s.add_row()),
        ("delete row", lambda s: s.delete_row(s.rows()[0].id)),
        ("duplicate row", lambda s: s.duplicate_row(s.rows()[0].id)),
        ("add column", lambda s: s.add_column("New", T.TEXT)),
        ("delete column", lambda s: s.delete_column(s.columns()[0].id)),
        ("move column", lambda s: s.move_column(s.columns()[1].id, -1)),
        ("edit column", lambda s: s.update_column(
            s.columns()[0].id, "Renamed", T.TEXT)),
    ],
)
def test_every_change_can_be_taken_back(sheet, label, change):
    before = snapshot(sheet)
    change(sheet)
    assert snapshot(sheet) != before, "the change did nothing to undo"
    # column labels carry the column's name, so the notification can say it
    assert (sheet.undo() or "").startswith(label)
    assert snapshot(sheet) == before


def test_redo_puts_it_back(sheet):
    sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, "x")
    after = snapshot(sheet)
    sheet.undo()
    assert sheet.redo() == "edit cell"
    assert snapshot(sheet) == after


def test_undoing_twice_goes_back_twice(sheet):
    row, column = sheet.rows()[0].id, sheet.columns()[0].id
    sheet.set_cell(row, column, "one")
    sheet.set_cell(row, column, "two")
    sheet.undo()
    assert sheet.rows()[0].values[column] == "one"
    sheet.undo()
    assert sheet.rows()[0].values.get(column) is None


def test_a_group_of_edits_is_taken_back_together(sheet):
    before = snapshot(sheet)
    with sheet.change("paste"):
        sheet.add_row()
        sheet.add_row()
        sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, "x")
    assert sheet.undo() == "paste"
    assert snapshot(sheet) == before


def test_a_new_change_means_there_is_nothing_to_redo(sheet):
    sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, "one")
    sheet.undo()
    assert sheet.redoable is not None
    sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, "two")
    assert sheet.redoable is None


def test_undoing_with_nothing_to_undo_is_not_an_error(sheet):
    assert sheet.undo() is None
    assert sheet.redo() is None


def test_only_so_many_changes_are_kept(sheet):
    row, column = sheet.rows()[0].id, sheet.columns()[0].id
    for n in range(UNDO_LIMIT + 10):
        sheet.set_cell(row, column, f"value {n}")
    assert len(sheet._undo) == UNDO_LIMIT


def test_what_was_undone_is_on_disk_too(tmp_path):
    path = tmp_path / "s.gridly"
    sheet = Sheet(path)
    column = sheet.columns()[0].id
    row = sheet.rows()[0].id
    sheet.set_cell(row, column, "typed")
    sheet.undo()
    sheet.close()
    assert Sheet(path).rows()[0].values.get(column) is None
