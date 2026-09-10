import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual import events
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.clipboard import parse_block
from gridly.screens import CellEditScreen
from gridly.store import Sheet

# --- the parser on its own
print("sheets block :", parse_block("Milk\tTRUE\t3\nBread\tFALSE\t1\n"))
print("one cell     :", parse_block("hello"))
print("quoted cell  :", parse_block('a\t"has\ttab"\tb\n'))
print("blank cells  :", parse_block("a\t\tc\n"))
print("empty        :", parse_block(""), parse_block("\n"))

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "p.gridly"
    s = Sheet(path)
    name, done = s.columns()
    s.add_column("Qty", ColumnType.NUMBER)
    s.close()
    return path

def grid(app):
    cols = app.sheet.columns()
    return [[r.values.get(c.id) for c in cols] for r in app.sheet.rows()]

async def main():
    # --- pastes into empty space, growing rows, no confirmation
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 30)) as pilot:
        t = app.query_one("#grid", DataTable)
        assert len(t.rows) == 1
        app.post_message(events.Paste("Milk\tTRUE\t3\nBread\tFALSE\t1.5\nEggs\tTRUE\t12\n"))
        await pilot.pause(); await pilot.pause()
        assert app.screen is app.screen_stack[0], "no confirm needed for empty cells"
        print("grew to:", len(t.rows), "rows ->", grid(app))

        # --- pasting over filled cells just happens, and u takes it back
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        before = grid(app)
        app.post_message(events.Paste("Oat\tFALSE\t9\n"))
        await pilot.pause(); await pilot.pause()
        assert app.screen is app.screen_stack[0], "paste no longer asks"
        print("after paste:", grid(app)[0])
        await pilot.press("u"); await pilot.pause()
        print("after undo :", grid(app)[0])
        assert grid(app) == before
        app.post_message(events.Paste("Oat\tFALSE\t9\n"))
        await pilot.pause(); await pilot.pause()
        print("re-pasted  :", grid(app)[0])

        # --- anchored at the cursor, spilling right and down
        t.cursor_coordinate = Coordinate(1, 1); await pilot.pause()
        app.post_message(events.Paste("TRUE\t99\nFALSE\t100\n"))
        await pilot.pause(); await pilot.pause()
        print("anchored paste:", grid(app))

        # --- a single cell lands in one cell
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        app.post_message(events.Paste("Just one"))
        await pilot.pause(); await pilot.pause()
        print("single cell:", grid(app)[0])

    # --- too wide, and values that don't fit the column type
    app2 = GridlyApp(fresh())
    async with app2.run_test(size=(100, 30)) as pilot:
        t = app2.query_one("#grid", DataTable)
        app2.post_message(events.Paste("A\tTRUE\t1\tEXTRA\tMORE\nB\tnope\tnotanumber\tX\tY\n"))
        await pilot.pause(); await pilot.pause()
        print("clipped + skipped:", grid(app2))
        print("columns untouched:", [c.name for c in app2.sheet.columns()])

        # --- blank pasted cells clear their target
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        app2.post_message(events.Paste("\t\t\n"))
        await pilot.pause(); await pilot.pause()
        print("blanks cleared:", grid(app2)[0])

        # --- paste inside a cell editor goes into the input, not the grid
        await pilot.press("enter"); await pilot.pause()
        assert isinstance(app2.screen, CellEditScreen)
        before = grid(app2)
        app2.post_message(events.Paste("typed\nover two lines"))
        await pilot.pause(); await pilot.pause()
        assert isinstance(app2.screen, CellEditScreen), "editor should keep focus"
        from textual.widgets import TextArea
        got = app2.screen.query_one("#value", TextArea).text
        print("editor got:", repr(got), "| grid unchanged:", grid(app2) == before)
        assert got == "typed\nover two lines", "the editor should keep every line"
        await pilot.press("escape"); await pilot.pause()
    print("ALL PASTE TESTS DONE")

def test_paste():
    asyncio.run(main())
