import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, datetime, pathlib, tempfile
import gridly.app as appmod
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.clipboard import parse_block
from gridly.coltypes import ColumnType
from gridly.store import Sheet


path = pathlib.Path(tempfile.mkdtemp()) / "c.gridly"
s = Sheet(path)
name, done = s.columns()
pr  = s.add_column("Priority", ColumnType.SELECT, ["Low", "High"])
qty = s.add_column("Qty", ColumnType.NUMBER)
due = s.add_column("Due", ColumnType.DATE)
r1 = s.rows()[0].id
s.set_cell(r1, name.id, "Milk\tand\thoney")
s.set_cell(r1, done.id, True); s.set_cell(r1, pr.id, "High")
s.set_cell(r1, qty.id, 7.5);   s.set_cell(r1, due.id, datetime.date(2026, 9, 9))
r2 = s.add_row()
s.set_cell(r2, name.id, "two\nlines")
s.close()

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 30)) as pilot:
        t = app.query_one("#grid", DataTable)

        for col, label in enumerate(["text", "boolean", "dropdown", "number", "date"]):
            t.cursor_coordinate = Coordinate(0, col); await pilot.pause()
            await pilot.press("y"); await pilot.pause()
            print(f"y on {label:<9}:", repr(app._clipboard), "| same to the system clipboard:", appmod.last_system_clipboard == app._clipboard)

        # a cell's own text is copied raw, not quoted
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("y"); await pilot.pause()
        assert app._clipboard == "Milk\tand\thoney", "y should copy the value itself"

        # an empty cell copies nothing and says so
        t.cursor_coordinate = Coordinate(1, 3); await pilot.pause()
        await pilot.press("y"); await pilot.pause()
        print("y on empty   :", repr(app._clipboard))

        # Y copies the row as spreadsheet-shaped TSV that survives a round trip
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("Y"); await pilot.pause()
        row = app._clipboard
        print("Y on row 1   :", repr(row))
        assert parse_block(row) == [["Milk\tand\thoney", "yes", "High", "7.5", "2026-09-09"]]

        # ...including a row holding a multi-line cell
        t.cursor_coordinate = Coordinate(1, 0); await pilot.pause()
        await pilot.press("Y"); await pilot.pause()
        print("Y on row 2   :", repr(app._clipboard))
        assert parse_block(app._clipboard) == [["two\nlines", "", "", "", ""]]

        # what Y copies is exactly what paste puts back
        before = [[r.values.get(c.id) for c in app.sheet.columns()] for r in app.sheet.rows()]
        from textual import events
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("Y"); await pilot.pause()
        app.post_message(events.Paste(app._clipboard))
        await pilot.pause(); await pilot.pause()
        if app.screen is not app.screen_stack[0]:
            await pilot.press("y"); await pilot.pause()   # confirm the overwrite
        after = [[r.values.get(c.id) for c in app.sheet.columns()] for r in app.sheet.rows()]
        print("copy->paste is a no-op:", before == after)
        assert before == after
    print("ALL COPY TESTS DONE")

def test_copy():
    asyncio.run(main())
