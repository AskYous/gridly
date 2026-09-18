import asyncio, csv, datetime, pathlib, tempfile
import gridly.app as appmod
from textual import events
from textual.coordinate import Coordinate
from textual.widgets import Checkbox, DataTable, Input, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.formulas import Formula
from gridly.screens import ColumnScreen, RowFormScreen
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "c.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    day = s.add_column("Day", ColumnType.DATE)
    s.add_column("Hours", ColumnType.NUMBER)
    s.set_cell(s.rows()[0].id, day.id, datetime.date(2026, 9, 17))
    s.close()
    return path

def shown(app, row=0, col=2):
    return app.query_one("#grid", DataTable).get_cell_at(Coordinate(row, col)).plain

def heading(app, col=2):
    return app.query_one("#grid", DataTable).ordered_columns[col].label.plain

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(110, 40)) as pilot:
        t = app.query_one("#grid", DataTable)

        # --- a column worked out from another one, built through the form
        await pilot.press("c"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        await pilot.press(*"Month")
        assert not app.screen.query_one("#source").display, "typed in by default"
        app.screen.query_one("#function", Select).value = "month"
        await pilot.pause()
        assert app.screen.query_one("#source").display, "it should ask where from"
        assert app.screen.query_one("#shows").display, "and how to write it"
        assert not app.screen.query_one("#unique").display, "repeats are not its business"

        # --- it will not be built without being told what to read
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen), "the form should have stayed up"
        print("no source    :", app.screen.query_one("#error").content)

        source = app.sheet.columns()[0]
        app.screen.query_one("#source", Select).value = source.id
        await pilot.press("ctrl+s"); await pilot.pause()
        column = app.sheet.columns()[2]
        print("column       :", column.name, "| formula:", column.formula)
        assert column.computed == Formula("month", source.id, "name")

        # --- and it has already worked the first row out
        print("row 1        :", shown(app), "| heading:", heading(app))
        assert shown(app) == "September"
        assert "fx" in heading(app), "the header should say it is worked out"

        # --- changing the date changes the month, with nothing else pressed
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", Input).value = "2026-12-01"
        await pilot.press("enter"); await pilot.pause()
        print("after 12-01  :", shown(app))
        assert shown(app) == "December"

        # --- typing into it is refused, and it is left alone
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "no editor should have opened"
        await pilot.press("backspace"); await pilot.pause()
        print("after typing :", shown(app))
        assert shown(app) == "December"

        # --- the row form shows it, but will not take anything for it
        await pilot.press("f"); await pilot.pause()
        assert isinstance(app.screen, RowFormScreen)
        field = app.screen.query_one(f"#field-{app.sheet.columns()[2].id}", Input)
        print("in the form  :", repr(field.value), "| disabled:", field.disabled)
        assert field.value == "December" and field.disabled
        await pilot.press("escape"); await pilot.pause()

        # --- a pasted block does not land on it
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        app.post_message(events.Paste("2025-01-03\t4\tMarch"))
        await pilot.pause()
        print("after paste  :", [shown(app, 0, c) for c in range(3)])
        assert [shown(app, 0, c) for c in range(3)] == ["2025-01-03", "4", "January"]

        # --- searching and copying read what is on screen
        await pilot.press("slash"); await pilot.press(*"January"); await pilot.pause()
        print("matches      :", app._matches)
        assert Coordinate(0, 2) in app._matches
        await pilot.press("escape"); await pilot.pause()
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("y"); await pilot.pause()
        print("copied       :", repr(appmod.last_system_clipboard))
        assert appmod.last_system_clipboard == "January"

        # --- and so does the CSV
        out = pathlib.Path(tempfile.mkdtemp()) / "out.csv"
        app._export(out)
        with out.open(encoding="utf-8-sig", newline="") as handle:
            written = list(csv.reader(handle))
        print("csv          :", written)
        assert written == [["Day", "Hours", "Month"], ["2025-01-03", "4", "January"]]

        # --- a wording the column's type cannot hold is refused, and said plainly
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#type", Select).value = ColumnType.NUMBER.value
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen), "the form should have stayed up"
        print("wrong type   :", app.screen.query_one("#error").content)

        # --- a number column takes the month as a number, though
        app.screen.query_one("#shows", Select).value = "number"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("as a number  :", shown(app))
        assert shown(app) == "1"

        # --- editing it back to an ordinary column hands it over to be typed in
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#function", Select).value = "typed"
        await pilot.pause()
        assert app.screen.query_one("#unique").display, "rules are its business again"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after undoing:", repr(shown(app)), "| formula:", repr(app.sheet.columns()[2].formula))
        assert shown(app) == "·" and app.sheet.columns()[2].formula == ""

        # --- and with no date column left, there is nothing to work a month out of
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("x"); await pilot.pause()
        await pilot.press("c"); await pilot.pause()
        await pilot.press(*"Month")
        app.screen.query_one("#function", Select).value = "month"
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen), "the form should have stayed up"
        print("no dates     :", app.screen.query_one("#error").content)
        await pilot.press("escape"); await pilot.pause()

        path = app.sheet.path

    # --- what is in the file is the date, never a copy of the month
    again = Sheet(path)
    kept = {c.id: c.name for c in again.columns()}
    stored = again.db.execute("SELECT column_id, value FROM cells").fetchall()
    print("on disk      :", [(kept[c["column_id"]], c["value"]) for c in stored])
    assert all(kept[c["column_id"]] != "Month" for c in stored)
    print("ALL COMPUTED COLUMN TESTS DONE")

def test_computed_column():
    asyncio.run(main())
