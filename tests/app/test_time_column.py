import asyncio, datetime, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import ColumnScreen
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "t.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    s.add_column("Task", ColumnType.TEXT)
    s.add_row()
    s.close()
    return path

def shown(app, row=0, col=1):
    t = app.query_one("#grid", DataTable)
    return t.get_cell_at(Coordinate(row, col)).plain

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 40)) as pilot:
        t = app.query_one("#grid", DataTable)

        # --- a time column, hours and minutes by default
        await pilot.press("c"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        await pilot.press(*"Start")
        app.screen.query_one("#type", Select).value = ColumnType.TIME.value
        await pilot.pause()
        assert app.screen.query_one("#format").display, "the precision should show"
        assert not app.screen.query_one("#options").display, "times have no options"
        await pilot.press("ctrl+s"); await pilot.pause()
        column = app.sheet.columns()[1]
        print("column       :", column.name, column.type.value, repr(column.format))
        assert column.type is ColumnType.TIME and column.format == ""

        # --- typing a time, in any of the ways people write one
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        for typed, expect in [("9:30", "09:30"), ("9:30 pm", "21:30"), ("7", "07:00")]:
            await pilot.press("enter"); await pilot.pause()
            field = app.screen.query_one("#value", Input)
            field.value = typed
            await pilot.press("enter"); await pilot.pause()
            print(f"  typed {typed!r:9} -> {shown(app)}")
            assert shown(app) == expect

        # --- seconds are dropped while the column does not show them
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", Input).value = "9:30:45"
        await pilot.press("enter"); await pilot.pause()
        print("  9:30:45 at minutes ->", shown(app))
        assert shown(app) == "09:30"
        assert app.sheet.rows()[0].values[app.sheet.columns()[1].id].second == 0

        # --- turning seconds on
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#format", Select).value = "seconds"
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("  after switch       ->", shown(app))
        assert shown(app) == "09:30:00"
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", Input).value = "9:30:45"
        await pilot.press("enter"); await pilot.pause()
        print("  9:30:45 at seconds ->", shown(app))
        assert shown(app) == "09:30:45"

        # --- a time that is not a time is refused, and the cell is left alone
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", Input).value = "half nine"
        await pilot.press("enter"); await pilot.pause()
        assert app.screen is not app.screen_stack[0], "the editor should stay open"
        await pilot.press("escape"); await pilot.pause()
        assert shown(app) == "09:30:45"
        print("  nonsense refused")

        # --- searching finds it by what is on screen
        await pilot.press("slash"); await pilot.press(*"09:30"); await pilot.pause()
        print("  search matches     :", len(app._matches))
        assert app._matches == [Coordinate(0, 1)]
        await pilot.press("escape"); await pilot.pause()

        # --- and it survives a reopen
        kept = app.sheet.rows()[0].values[app.sheet.columns()[1].id]
    again = Sheet(app.sheet.path)
    column = again.columns()[1]
    print("on disk      :", again.rows()[0].values[column.id], "| format:", column.format)
    assert again.rows()[0].values[column.id] == kept == datetime.time(9, 30, 45)
    assert column.format == "seconds"
    print("ALL TIME COLUMN TESTS DONE")

def test_time_column():
    asyncio.run(main())
