"""A read-only sheet can be looked through but not changed, from any direction."""

import asyncio
import pathlib
import sqlite3
import tempfile

from textual import events
from textual.widgets import DataTable

from gridly import app as gridly_app
from gridly import config
from gridly.app import GridlyApp
from gridly.store import Sheet


def sheet_file() -> pathlib.Path:
    path = pathlib.Path(tempfile.mkdtemp()) / "look.gridly"
    sheet = Sheet(path)
    sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, "Milk")
    sheet.close()
    return path


def test_the_file_is_never_written(tmp_path):
    path = sheet_file()
    before = path.read_bytes()
    sheet = Sheet(path, read_only=True)
    sheet.add_row()  # lands in the copy in memory
    sheet.close()
    assert path.read_bytes() == before
    assert len(Sheet(path).rows()) == 1


def test_an_empty_sheet_is_shown_empty_not_seeded(tmp_path):
    path = tmp_path / "empty.gridly"
    sqlite3.connect(path).close()
    assert Sheet(path, read_only=True).columns() == []


def test_a_file_that_is_not_a_sheet_is_refused(tmp_path, capsys):
    junk = tmp_path / "junk.gridly"
    junk.write_text("not a database, just words " * 100)
    assert gridly_app.main([str(junk), "--read-only"]) == 1
    assert "Cannot read" in capsys.readouterr().out


def test_it_needs_a_file_to_show(capsys):
    assert gridly_app.main(["--read-only"]) == 1
    assert "needs a sheet" in capsys.readouterr().out


async def exercise(path: pathlib.Path) -> None:
    app = GridlyApp(path, read_only=True)
    async with app.run_test(size=(100, 30)) as pilot:
        table = app.query_one("#grid", DataTable)
        # Every key that would change something does nothing.
        for key in ["space", "enter", "a", "i", "D", "d", "c", "e", "x", "f",
                    "C", "backspace", "u", "U", "o", "E", "{", "]"]:
            await pilot.press(key)
            await pilot.pause()
            assert app.screen is app.screen_stack[0], f"{key} opened a screen"
        # A paste is dropped too.
        app.post_message(events.Paste("Bread\tyes"))
        await pilot.pause()
        assert [c.plain for c in table.get_row_at(0)][0] == "Milk"
        assert len(app.sheet.rows()) == 1

        # The palette does not offer them either.
        titles = {command.title for command in app.get_system_commands(app.screen)}
        assert "Find" in titles and "Copy row" in titles
        assert not titles & {"Edit cell", "Add row", "Delete column", "Undo",
                             "Open another sheet", "Export to CSV"}

        # Looking still works.
        await pilot.press("slash")
        for letter in "milk":
            await pilot.press(letter)
        await pilot.press("enter")
        await pilot.pause()
        assert len(app._matches) == 1
        assert "read-only" in app.sub_title


def test_nothing_in_the_app_changes_it():
    path = sheet_file()
    before = path.read_bytes()
    asyncio.run(exercise(path))
    assert path.read_bytes() == before


def test_it_is_not_added_to_the_recent_list():
    path = sheet_file()
    asyncio.run(exercise(path))
    assert path.resolve() not in config.recent()
