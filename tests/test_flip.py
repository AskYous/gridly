import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
import gridly.app as appmod
from textual import events
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.clipboard import parse_block
from gridly.coltypes import ColumnType
from gridly.screens import ConfirmScreen, RowFormScreen
from gridly.store import Sheet


def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "v.gridly"
    s = Sheet(path)
    name, done = s.columns()
    qty = s.add_column("Qty", ColumnType.NUMBER)
    r1 = s.rows()[0].id
    s.set_cell(r1, name.id, "Milk"); s.set_cell(r1, done.id, True); s.set_cell(r1, qty.id, 3)
    r2 = s.add_row()
    s.set_cell(r2, name.id, "Bread"); s.set_cell(r2, done.id, False); s.set_cell(r2, qty.id, 1)
    s.close()
    return path

def data(app):
    cols = app.sheet.columns()
    return [[r.values.get(c.id) for c in cols] for r in app.sheet.rows()]

def screen(t):
    return [[t.get_cell_at(Coordinate(r, c)).plain for c in range(len(t.columns))]
            for r in range(len(t.rows))]

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 30)) as pilot:
        t = app.query_one("#grid", DataTable)
        print("normal  :", screen(t))
        before = data(app)

        # --- flipping transposes the drawing and touches nothing else
        t.cursor_coordinate = Coordinate(1, 2)      # Bread / Qty
        await pilot.pause()
        await pilot.press("v"); await pilot.pause()
        print("flipped :", screen(t))
        assert app.view.flipped and data(app) == before, "flipping is not a data change"
        assert screen(t) == [list(col) for col in zip(*[["Milk","✓","3"],["Bread","✗","1"]])]

        # --- the cursor stays on the same cell through the flip
        print("cursor  :", t.cursor_coordinate, "->",
              app.current_row().values[app.current_column().id])
        assert (app.current_column().name, app.current_row().values[app.current_column().id]) == ("Qty", 1)

        # --- editing through the flipped view writes the cell you are looking at
        await pilot.press("enter"); await pilot.pause()
        await pilot.press("backspace", *"99", "enter"); await pilot.pause()
        print("edited  :", data(app))
        assert data(app)[1][2] == 99

        # --- a boolean toggles, backspace clears, in the flipped view
        t.cursor_coordinate = Coordinate(1, 0); await pilot.pause()   # Done / Milk
        await pilot.press("enter"); await pilot.pause()
        assert data(app)[0][1] is False
        await pilot.press("backspace"); await pilot.pause()
        assert data(app)[0][1] is None
        print("toggle+clear ok:", data(app)[0])

        # --- y / Y still mean cell and record
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()   # Name / Bread
        await pilot.press("y"); await pilot.pause()
        print("y       :", repr(app._clipboard))
        assert app._clipboard == "Bread"
        await pilot.press("Y"); await pilot.pause()
        print("Y       :", repr(app._clipboard))
        # flipped, a record reads down the screen, so Y copies it as a column
        assert parse_block(app._clipboard) == [["Bread"], ["no"], ["99"]]

        # --- 'a' adds a record: a new grid COLUMN when flipped
        wide = len(t.columns)
        await pilot.press("a"); await pilot.pause()
        print("after a :", len(t.columns), "grid columns (was", wide, ") rows:", len(app.sheet.rows()))
        assert len(t.columns) == wide + 1 and len(t.rows) == 3

        # --- 'c' adds a column: a new grid ROW when flipped
        tall = len(t.rows)
        await pilot.press("c"); await pilot.pause()
        await pilot.press(*"Notes"); await pilot.press("enter"); await pilot.pause()
        print("after c :", len(t.rows), "grid rows (was", tall, ")")
        assert len(t.rows) == tall + 1
        print("cursor on new column:", app.current_column().name)

        # --- 'd' deletes the record under the cursor
        app.sheet.set_cell(app.current_row().id, app.sheet.columns()[0].id, "keepme")
        app.reload()
        rows_before = len(app.sheet.rows())
        await pilot.press("d"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "delete no longer asks"
        assert len(app.sheet.rows()) == rows_before - 1
        print("after d :", len(app.sheet.rows()), "records")

        # --- the form opens the record under the cursor
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("f"); await pilot.pause()
        assert isinstance(app.screen, RowFormScreen)
        print("form    :", app.screen.query_one(".dialog-title").content)
        await pilot.press("escape"); await pilot.pause()

        # --- flipping back restores the original drawing
        await pilot.press("v"); await pilot.pause()
        assert not app.view.flipped
        print("back    :", screen(t))
    print("--- paste in the flipped view ---")

    app2 = GridlyApp(fresh())
    async with app2.run_test(size=(100, 30)) as pilot:
        t = app2.query_one("#grid", DataTable)
        await pilot.press("v"); await pilot.pause()
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        # two screen rows (Name, Done) x three screen columns -> 3 records, 2 columns
        app2.post_message(events.Paste("Oat\tRye\tSpelt\nTRUE\tFALSE\tTRUE\n"))
        await pilot.pause(); await pilot.pause()
        if isinstance(app2.screen, ConfirmScreen):
            print("confirm :", app2.screen.message)
            await pilot.press("y"); await pilot.pause()
        print("pasted  :", data(app2))
        assert data(app2) == [["Oat", True, 3], ["Rye", False, 1], ["Spelt", True, None]]

        # --- what Y copies pastes back unchanged, in the flipped view too
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        snapshot = data(app2)
        await pilot.press("Y"); await pilot.pause()
        print("Y row   :", repr(app2._clipboard))
        app2.post_message(events.Paste(app2._clipboard))
        await pilot.pause(); await pilot.pause()
        if isinstance(app2.screen, ConfirmScreen): await pilot.press("y"); await pilot.pause()
        print("round trip is a no-op:", data(app2) == snapshot)
        assert data(app2) == snapshot

        # --- a block taller than the sheet has columns gets clipped, never invents one
        columns_before = [c.name for c in app2.sheet.columns()]
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        app2.post_message(events.Paste("a\nb\nc\nd\ne\n"))
        await pilot.pause(); await pilot.pause()
        if isinstance(app2.screen, ConfirmScreen): await pilot.press("y"); await pilot.pause()
        print("columns unchanged:", [c.name for c in app2.sheet.columns()] == columns_before)
        assert [c.name for c in app2.sheet.columns()] == columns_before
    print("ALL FLIP TESTS DONE")

def test_flip():
    asyncio.run(main())
