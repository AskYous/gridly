import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()
import asyncio, pathlib, tempfile
from textual import events
from textual.coordinate import Coordinate
from textual.widgets import DataTable, TextArea
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "u.gridly"
    s = Sheet(path)
    name, done = s.columns()
    qty = s.add_column("Qty", ColumnType.NUMBER)
    for i, (n, d, q) in enumerate([("Milk", True, 3), ("Bread", False, 1)]):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, name.id, n); s.set_cell(rid, done.id, d); s.set_cell(rid, qty.id, q)
    s.close()
    return path

def data(app):
    cols = app.sheet.columns()
    return [[r.values.get(c.id) for c in cols] for r in app.sheet.rows()]

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 30)) as pilot:
        t = app.query_one("#grid", DataTable)
        start = data(app)
        print("start        :", start)

        # --- deleting a row no longer asks, and comes back
        await pilot.press("d"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "delete should not stop to ask"
        print("after d      :", len(data(app)), "rows")
        assert len(data(app)) == 1
        await pilot.press("u"); await pilot.pause()
        print("after u      :", data(app))
        assert data(app) == start

        # --- so does deleting a column
        await pilot.press("x"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "delete column should not ask either"
        print("after x      :", [c.name for c in app.sheet.columns()])
        assert len(app.sheet.columns()) == 2
        await pilot.press("u"); await pilot.pause()
        assert [c.name for c in app.sheet.columns()] == ["Name", "Done", "Qty"]
        print("column back  :", [c.name for c in app.sheet.columns()])

        # --- a cell edit
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("enter"); await pilot.press("backspace", *"99", "enter")
        await pilot.pause()
        assert data(app)[0][2] == 99
        await pilot.press("u"); await pilot.pause()
        print("cell undone  :", data(app)[0])
        assert data(app) == start

        # --- redo puts it back
        await pilot.press("U"); await pilot.pause()
        print("redone       :", data(app)[0])
        assert data(app)[0][2] == 99
        await pilot.press("u"); await pilot.pause()

        # --- a whole paste is one step, and no longer asks before overwriting
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        app.post_message(events.Paste("Oat\tFALSE\t7\nRye\tTRUE\t8\nSpelt\tFALSE\t9\n"))
        await pilot.pause(); await pilot.pause()
        assert app.screen is app.screen_stack[0], "paste should not stop to ask"
        print("after paste  :", data(app))
        assert len(data(app)) == 3
        await pilot.press("u"); await pilot.pause()
        print("paste undone :", data(app))
        assert data(app) == start, "one press should take back the whole block"

        # --- the row form is one step too
        await pilot.press("f"); await pilot.pause()
        cols = app.sheet.columns()
        app.screen.query_one(f"#field-{cols[0].id}", TextArea).text = "Oat milk"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert data(app)[0][0] == "Oat milk"
        await pilot.press("u"); await pilot.pause()
        print("form undone  :", data(app)[0])
        assert data(app) == start

        # --- duplicating is one step
        await pilot.press("D"); await pilot.pause()
        assert len(data(app)) == 3
        await pilot.press("u"); await pilot.pause()
        assert data(app) == start
        print("duplicate undone")

        # --- retyping a column, which drops values, is recoverable
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        from textual.widgets import Select
        app.screen.query_one("#type", Select).value = ColumnType.NUMBER.value
        await pilot.pause(); await pilot.press("ctrl+s"); await pilot.pause()
        print("retyped      :", data(app))
        assert data(app)[0][0] is None, "Milk does not survive being a number"
        await pilot.press("u"); await pilot.pause()
        print("retype undone:", data(app))
        assert data(app) == start

        # --- nothing left to undo says so
        while app.sheet.undoable:
            await pilot.press("u"); await pilot.pause()
        await pilot.press("u"); await pilot.pause()
        print("empty stack  : still", len(data(app)), "rows, app alive")

    print("ALL UNDO TESTS DONE")

def test_undo():
    asyncio.run(main())
