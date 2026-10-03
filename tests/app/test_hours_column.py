import asyncio, datetime, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.formulas import Formula
from gridly.screens import ColumnScreen
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "h.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    start = s.add_column("Start", ColumnType.TIME)
    end = s.add_column("End", ColumnType.TIME)
    s.add_column("Pay", ColumnType.NUMBER, formula=Formula("sum", expr="Hours * 10").encode())
    row = s.rows()[0].id
    s.set_cell(row, start.id, datetime.time(16, 0))
    s.set_cell(row, end.id, datetime.time(17, 30))
    s.close()
    return path

def shown(app, row=0, col=3):
    return app.query_one("#grid", DataTable).get_cell_at(Coordinate(row, col)).plain

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(110, 40)) as pilot:
        t = app.query_one("#grid", DataTable)
        start, end = app.sheet.columns()[:2]

        # --- picking hours turns the column into a number, and guesses the times
        await pilot.press("c"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        assert not app.screen.query_one("#start").display, "only asked for hours"
        await pilot.press(*"Hours")
        app.screen.query_one("#function", Select).value = "hours"
        await pilot.pause()
        assert app.screen.query_one("#type", Select).value == ColumnType.NUMBER.value
        assert app.screen.query_one("#start").display
        assert app.screen.query_one("#start", Select).value == start.id
        assert app.screen.query_one("#end", Select).value == end.id
        assert not app.screen.query_one("#source").display, "no date to ask about"

        # --- the same time twice is refused
        app.screen.query_one("#end", Select).value = start.id; await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        assert "different" in str(app.screen.query_one("#error").content)

        app.screen.query_one("#end", Select).value = end.id; await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        column = app.sheet.columns()[3]
        assert column.computed == Formula("hours", start.id, until=end.id)
        print("hours        :", shown(app))
        assert shown(app) == "1.5"
        assert shown(app, col=2) == "15", "a sum reads the hours"

        # --- the status line says what works it out
        t.cursor_coordinate = Coordinate(0, 3); await pilot.pause()
        status = str(app.query_one("#status").content)
        print("status       :", status)
        assert "the hours from Start to End" in status

        # --- changing a time changes the hours
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", Input).value = "20:00"
        await pilot.press("enter"); await pilot.pause()
        print("to 20:00     :", shown(app))
        assert shown(app) == "4"

        # --- reopening the form shows the times it was given
        t.cursor_coordinate = Coordinate(0, 3); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        assert app.screen.query_one("#start", Select).value == start.id
        assert app.screen.query_one("#end", Select).value == end.id
        await pilot.press("escape"); await pilot.pause()
    print("ALL HOURS COLUMN TESTS DONE")

def test_hours_column():
    asyncio.run(main())
