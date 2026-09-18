import asyncio, os, pathlib, tempfile
from textual.containers import Vertical
from textual.widgets import DataTable, Input, OptionList
from gridly import config
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.picker import PickerScreen
from gridly.store import Sheet

def make(folder, name, value=None):
    path = folder / name
    sheet = Sheet(path)
    if value:
        sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, value)
    sheet.close()
    return path.resolve()

async def main():
    # A config of its own: this test counts what is in the recent list, and
    # every other test that opens a sheet adds to the shared one.
    os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
    home = pathlib.Path(tempfile.mkdtemp())
    first = make(home, "alpha.gridly", "in alpha")
    second = make(home, "beta.gridly", "in beta")
    config.remember(first)
    config.remember(second)          # newest first: beta, alpha

    # --- with nothing named, the app asks which sheet
    app = GridlyApp()
    async with app.run_test(size=(90, 24)) as pilot:
        assert isinstance(app.screen, PickerScreen), app.screen
        options = app.screen.query_one("#recent", OptionList)
        print("offered      :", options.option_count, "sheets")
        assert options.option_count == 2

        # --- it sits in the middle, not shoved against the left edge
        box = app.screen.query_one(".picker", Vertical).region
        left, right = box.x, app.screen.size.width - box.right
        print("gaps         :", left, "left,", right, "right")
        assert left > 0 and abs(left - right) <= 1, (left, right)

        # --- choosing one opens it, and the app carries on running
        await pilot.press("down", "enter"); await pilot.pause()
        print("opened       :", app.sheet.path.name)
        assert app.sheet.path == first
        assert app.screen is app.screen_stack[0], "the picker should be gone"
        assert app.is_running, "choosing a sheet must not end the session"

        # --- and the sheet is really there to work in
        t = app.query_one("#grid", DataTable)
        print("shows        :", t.get_cell_at(t.cursor_coordinate).plain)
        assert t.get_cell_at(t.cursor_coordinate).plain == "in alpha"
        await pilot.press("a"); await pilot.pause()
        assert len(app.sheet.rows()) == 2, "the grid should take keys afterwards"

    # --- typing a path works the same way
    app = GridlyApp()
    async with app.run_test(size=(90, 24)) as pilot:
        # Focused outright rather than tabbed to: how many stops there are
        # between here and there is the filter's business, not this test's.
        app.screen.query_one("#path", Input).focus(); await pilot.pause()
        app.screen.query_one("#path", Input).value = str(second)
        await pilot.press("enter"); await pilot.pause()
        print("typed        :", app.sheet.path.name)
        assert app.sheet.path == second and app.is_running

    # --- a path that is not there yet is created
    fresh = home / "made-up.gridly"
    app = GridlyApp()
    async with app.run_test(size=(90, 24)) as pilot:
        # Focused outright rather than tabbed to: how many stops there are
        # between here and there is the filter's business, not this test's.
        app.screen.query_one("#path", Input).focus(); await pilot.pause()
        app.screen.query_one("#path", Input).value = str(fresh)
        await pilot.press("enter"); await pilot.pause()
        assert app.sheet.path == fresh.resolve() and fresh.exists()
        print("created      :", fresh.name)

    # --- escaping means opening nothing at all
    app = GridlyApp()
    async with app.run_test(size=(90, 24)) as pilot:
        await pilot.press("escape"); await pilot.pause()
    print("escaped      : sheet is", app.sheet)
    assert app.sheet is None

    # --- and naming a sheet skips the asking
    app = GridlyApp(second)
    async with app.run_test(size=(90, 24)) as pilot:
        assert app.screen is app.screen_stack[0]
        assert app.sheet.path == second
        print("named        :", app.sheet.path.name, "— no picker")

    print("ALL PICKER TESTS DONE")

def test_picker():
    asyncio.run(main())
