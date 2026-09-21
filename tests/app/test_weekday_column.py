import asyncio, datetime, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.formulas import Formula
from gridly.screens import ColumnScreen
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "w.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    day = s.add_column("Day", ColumnType.DATE)
    s.set_cell(s.rows()[0].id, day.id, datetime.date(2026, 9, 21))   # a Monday
    s.close()
    return path

def shown(app, row=0, col=1):
    return app.query_one("#grid", DataTable).get_cell_at(Coordinate(row, col)).plain

def wordings(app):
    return [key for _, key in app.screen.query_one("#shows", Select)._options if key is not Select.NULL]

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(110, 40)) as pilot:
        t = app.query_one("#grid", DataTable)
        day = app.sheet.columns()[0]

        # --- the form offers it beside the month, and asks the same two things
        await pilot.press("c"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        await pilot.press(*"Weekday")
        app.screen.query_one("#function", Select).value = "weekday"
        await pilot.pause()
        assert app.screen.query_one("#source").display, "it should ask which date"
        assert app.screen.query_one("#shows").display, "and how to write the day"
        print("wordings     :", wordings(app))
        assert wordings(app) == ["name", "short"], "a weekday has no number"

        # --- switching to a month offers the month's wordings, and back again
        app.screen.query_one("#function", Select).value = "month"; await pilot.pause()
        assert wordings(app) == ["name", "short", "number", "year"]
        app.screen.query_one("#shows", Select).value = "number"; await pilot.pause()
        app.screen.query_one("#function", Select).value = "weekday"; await pilot.pause()
        assert wordings(app) == ["name", "short"]
        print("after number :", app.screen.query_one("#shows", Select).value)
        assert app.screen.query_one("#shows", Select).value == "name", "no number to keep"

        app.screen.query_one("#source", Select).value = day.id
        await pilot.press("ctrl+s"); await pilot.pause()
        column = app.sheet.columns()[1]
        print("column       :", column.name, "|", column.computed)
        assert column.computed == Formula("weekday", day.id, "name")
        print("row 1        :", shown(app))
        assert shown(app) == "Monday"

        # --- the status line says what works it out
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        status = str(app.query_one("#status").content)
        print("status       :", status)
        assert "the weekday of Day" in status

        # --- changing the date changes the day
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", Input).value = "2026-09-27"
        await pilot.press("enter"); await pilot.pause()
        print("after 09-27  :", shown(app))
        assert shown(app) == "Sunday"

        # --- a number column will not take it, and says so
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        assert app.screen.query_one("#shows", Select).value == "name", "opens as it was"
        app.screen.query_one("#type", Select).value = ColumnType.NUMBER.value
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen), "the form should have stayed up"
        error = str(app.screen.query_one("#error").content)
        print("as a number  :", error)
        assert "weekday" in error

        # --- a dropdown lists the seven days itself, short if asked
        app.screen.query_one("#type", Select).value = ColumnType.SELECT.value
        app.screen.query_one("#shows", Select).value = "short"
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        column = app.sheet.columns()[1]
        print("dropdown     :", column.options, "|", shown(app))
        assert column.options == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        assert shown(app) == "Sun"

        # --- with no date column, there is nothing to take a weekday from
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("x"); await pilot.pause()
        await pilot.press("c"); await pilot.pause()
        await pilot.press(*"Weekday")
        app.screen.query_one("#function", Select).value = "weekday"
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        error = str(app.screen.query_one("#error").content)
        print("no dates     :", error)
        assert "take a weekday from" in error
        await pilot.press("escape"); await pilot.pause()
    print("ALL WEEKDAY COLUMN TESTS DONE")

def test_weekday_column():
    asyncio.run(main())
