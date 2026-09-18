import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.formulas import Formula
from gridly.screens import ColumnScreen
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "p.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    s.add_column("Note", ColumnType.TEXT)
    hours = s.add_column("Hours", ColumnType.NUMBER)
    for i, worked in enumerate([1.5, 8]):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, hours.id, worked)
    s.close()
    return path

def shown(app, row=0, col=2):
    return app.query_one("#grid", DataTable).get_cell_at(Coordinate(row, col)).plain

async def build(app, pilot, name, expr, coltype=None):
    """Add a column worked out by a sum, through the form."""
    await pilot.press("c"); await pilot.pause()
    await pilot.press(*name)
    if coltype is not None:
        app.screen.query_one("#type", Select).value = coltype.value
    app.screen.query_one("#function", Select).value = "sum"
    await pilot.pause()
    app.screen.query_one("#expr", Input).value = expr
    await pilot.press("ctrl+s"); await pilot.pause()

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(120, 40)) as pilot:
        t = app.query_one("#grid", DataTable)

        # --- the form asks for a sum, and says what it may read
        await pilot.press("c"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        await pilot.press(*"Pay")
        app.screen.query_one("#function", Select).value = "sum"
        await pilot.pause()
        assert app.screen.query_one("#expr").display, "it should ask for the sum"
        assert not app.screen.query_one("#source").display, "that is the month's field"
        print("reads        :", app.screen.query_one("#expr-help").content)
        assert "Hours" in str(app.screen.query_one("#expr-help").content)

        # --- a sum naming a column that is not there is refused
        app.screen.query_one("#expr", Input).value = "Hrs * 55"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen), "the form should have stayed up"
        print("unknown name :", app.screen.query_one("#error").content)

        # --- and so is one that reads something that is not a number
        app.screen.query_one("#expr", Input).value = "Note * 2"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        print("not a number :", app.screen.query_one("#error").content)

        # --- a rate, at last
        app.screen.query_one("#expr", Input).value = "Hours * 55"
        app.screen.query_one("#type", Select).value = ColumnType.NUMBER.value
        await pilot.press("ctrl+s"); await pilot.pause()
        pay = app.sheet.columns()[2]
        print("column       :", pay.name, "|", pay.computed.expr)
        assert pay.computed == Formula("sum", expr="Hours * 55")
        print("rows         :", shown(app, 0), shown(app, 1))
        assert (shown(app, 0), shown(app, 1)) == ("82.5", "440")

        # --- changing the hours changes the pay, with nothing else pressed
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", Input).value = "4"
        await pilot.press("enter"); await pilot.pause()
        print("after 4 hours:", shown(app, 0))
        assert shown(app, 0) == "220"

        # --- a sum over the sum, worked out after it whatever the order
        await build(app, pilot, "Tax", "Pay * 0.15", ColumnType.NUMBER)
        print("tax          :", shown(app, 0, 3), shown(app, 1, 3))
        assert (shown(app, 0, 3), shown(app, 1, 3)) == ("33", "66")

        # --- a sum that would read itself round a circle is refused
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#expr", Input).value = "Tax * 2"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen), "the form should have stayed up"
        print("a circle     :", app.screen.query_one("#error").content)
        await pilot.press("escape"); await pilot.pause()
        assert shown(app, 0) == "220", "and the sum it had is untouched"

        # --- typing into one is refused, and says what to change instead
        await pilot.press("enter"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "no editor should have opened"
        await pilot.press("backspace"); await pilot.pause()
        assert shown(app, 0) == "220"
        print("status       :", app.query_one("#status").content.plain[-46:])

        # --- renaming what a sum reads takes the sum along
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#name", Input).value = "Worked"
        await pilot.press("ctrl+s"); await pilot.pause()
        moved = app.sheet.columns()[2]
        print("after rename :", moved.computed.expr, "|", shown(app, 0))
        assert moved.computed.expr == "Worked * 55" and shown(app, 0) == "220"

        # --- and deleting it leaves the sums standing, empty, with a word said
        await pilot.press("x"); await pilot.pause()
        left = [c.name for c in app.sheet.columns()]
        print("columns now  :", left)
        assert [c.computed for c in app.sheet.columns() if c.name == "Pay"] == [None]
    print("ALL SUM COLUMN TESTS DONE")

def test_sum_column():
    asyncio.run(main())
