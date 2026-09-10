import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()
import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import Button, DataTable, Input, Select, Static
from gridly.app import GridlyApp
from gridly.coltypes import OPTION_COLORS, ColumnType
from gridly.screens import ColumnScreen, OptionRow, PickScreen
from gridly.store import Sheet

path = pathlib.Path(tempfile.mkdtemp()) / "o.gridly"

def rows(app):
    return list(app.screen.query(OptionRow))

def fill(row, name=None, color=None):
    if name is not None:
        row.query_one(".option-name", Input).value = name
    if color is not None:
        row.query_one(".option-color", Select).value = color

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 40)) as pilot:
        t = app.query_one("#grid", DataTable)

        # --- a new dropdown starts with one empty row
        await pilot.press("c"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        await pilot.press(*"Stage")
        app.screen.query_one("#type", Select).value = ColumnType.SELECT.value
        await pilot.pause()
        print("rows to start :", len(rows(app)))
        assert len(rows(app)) == 1

        # --- add more rows with the button
        for _ in range(2):
            app.screen.query_one("#add-option", Button).press(); await pilot.pause()
        print("after adding  :", len(rows(app)))
        assert len(rows(app)) == 3

        # --- name them, pick a colour for one, leave the others to the palette
        fill(rows(app)[0], "Backlog")
        fill(rows(app)[1], "In progress", "purple")
        fill(rows(app)[2], "Done")
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        column = [c for c in app.sheet.columns() if c.name == "Stage"][0]
        print("saved         :", column.options)
        print("colours       :", column.colors)
        assert column.options == ["Backlog", "In progress", "Done"]
        assert column.colors["In progress"] == "purple", column.colors
        assert column.colors["Backlog"] in OPTION_COLORS

        # --- reopening shows a row per option with its colour selected
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        shown = [
            (r.query_one(".option-name", Input).value,
             r.query_one(".option-color", Select).value)
            for r in rows(app)
        ]
        print("reopened      :", shown)
        assert shown == [("Backlog", column.colors["Backlog"]),
                         ("In progress", "purple"),
                         ("Done", column.colors["Done"])]

        # --- a focused row stays one line: a border here would hide the text
        field = rows(app)[0].query_one(".option-name", Input)
        field.focus(); await pilot.pause()
        print("focused row   :", field.size.height, "line, border:", bool(field.styles.border.top[0]))
        assert field.size.height == 1, "a focused option must not grow a border"
        assert field.styles.background.a > 0, "focus needs to be visible somehow"

        # --- the ✕ drops a row
        rows(app)[1].query_one(".option-remove", Button).press()
        await pilot.pause()
        print("after remove  :", len(rows(app)))
        assert len(rows(app)) == 2
        await pilot.press("ctrl+s"); await pilot.pause()
        column = [c for c in app.sheet.columns() if c.name == "Stage"][0]
        print("saved         :", column.options)
        assert column.options == ["Backlog", "Done"]

        # --- a blank row is simply dropped, not saved as an empty option
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#add-option", Button).press(); await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        column = [c for c in app.sheet.columns() if c.name == "Stage"][0]
        print("blank ignored :", column.options)
        assert column.options == ["Backlog", "Done"]

        # --- duplicates and an empty list are still refused
        await pilot.press("e"); await pilot.pause()
        fill(rows(app)[1], "backlog")
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        print("duplicates    :", app.screen.query_one("#error", Static).content)
        for row in rows(app):
            fill(row, "")
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        print("empty list    :", app.screen.query_one("#error", Static).content)
        await pilot.press("escape"); await pilot.pause()

        # --- the options field only shows for dropdowns
        await pilot.press("c"); await pilot.pause()
        print("hidden for text:", not app.screen.query_one("#options").display)
        assert not app.screen.query_one("#options").display
        assert not app.screen.query_one("#add-option").display
        await pilot.press("escape"); await pilot.pause()

        # --- and the cell picker still works, coloured
        await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen, PickScreen)
        await pilot.press("down", "enter"); await pilot.pause()
        col = [c for c in app.sheet.columns() if c.name == "Stage"][0]
        print("picked        :", repr(app.sheet.rows()[0].values.get(col.id)))
        assert app.sheet.rows()[0].values.get(col.id) == "Backlog"
    print("ALL OPTION TESTS DONE")

def test_options():
    asyncio.run(main())
