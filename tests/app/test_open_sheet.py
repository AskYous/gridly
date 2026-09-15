import asyncio, os, pathlib, tempfile
from textual.widgets import DataTable, Input
from gridly import config
from gridly.app import GridlyApp
from gridly.picker import PickerScreen
from gridly.store import Sheet

def make(folder, name, value):
    path = folder / name
    sheet = Sheet(path)
    sheet.set_cell(sheet.rows()[0].id, sheet.columns()[0].id, value)
    sheet.close()
    return path.resolve()

def showing(app):
    t = app.query_one("#grid", DataTable)
    return t.get_cell_at(t.cursor_coordinate).plain

async def main():
    os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
    home = pathlib.Path(tempfile.mkdtemp())
    alpha = make(home, "alpha.gridly", "in alpha")
    beta = make(home, "beta.gridly", "in beta")
    config.remember(alpha)
    config.remember(beta)

    app = GridlyApp(alpha)
    async with app.run_test(size=(90, 24)) as pilot:
        print("started in   :", app.sheet.path.name, "|", showing(app))
        assert showing(app) == "in alpha"

        # --- o brings the picker back without leaving the app
        await pilot.press("o"); await pilot.pause()
        assert isinstance(app.screen, PickerScreen), app.screen
        print("picker up    : yes")

        # --- changing your mind leaves you where you were
        await pilot.press("escape"); await pilot.pause()
        print("after escape :", app.sheet.path.name)
        assert app.sheet.path == alpha and app.is_running
        assert showing(app) == "in alpha"

        # --- choosing another one switches to it
        await pilot.press("o"); await pilot.pause()
        app.screen.query_one("#path", Input).value = str(beta)
        app.screen.query_one("#path", Input).focus()
        await pilot.press("enter"); await pilot.pause()
        print("switched to  :", app.sheet.path.name, "|", showing(app))
        assert app.sheet.path == beta
        assert showing(app) == "in beta"
        assert app.title == "Gridly" and beta.name in app.sub_title

        # --- and the new sheet is live, not a picture of one
        await pilot.press("a"); await pilot.pause()
        assert len(app.sheet.rows()) == 2
        print("editable     : yes")

        # --- undo belongs to the sheet, so it does not reach across
        assert app.sheet.undoable is not None
        await pilot.press("o"); await pilot.pause()
        app.screen.query_one("#path", Input).value = str(alpha)
        app.screen.query_one("#path", Input).focus()
        await pilot.press("enter"); await pilot.pause()
        print("back in      :", app.sheet.path.name, "| undo:", app.sheet.undoable)
        assert app.sheet.path == alpha
        assert app.sheet.undoable is None, "the other sheet's history is not here"

        # --- choosing the sheet already open changes nothing
        await pilot.press("o"); await pilot.pause()
        app.screen.query_one("#path", Input).value = str(alpha)
        app.screen.query_one("#path", Input).focus()
        await pilot.press("enter"); await pilot.pause()
        print("same sheet   :", app.sheet.path.name, "|", showing(app))
        assert app.sheet.path == alpha and showing(app) == "in alpha"

        # --- the recent list reflects what has been opened
        print("recent       :", [p.name for p in config.recent()][:3])
        assert config.recent()[0] == alpha
    print("ALL OPEN TESTS DONE")

def test_open_sheet():
    asyncio.run(main())
