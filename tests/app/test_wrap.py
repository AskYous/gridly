import os, tempfile, pathlib, asyncio
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
from textual.coordinate import Coordinate
from textual.widgets import DataTable, TextArea
from gridly.app import GridlyApp
from gridly.appearance import COLUMN_CAPS, MAX_WRAP_LINES, ROW_SIZES
from gridly.coltypes import ColumnType
from gridly.store import Sheet

LONG = "This is a very long note that would otherwise stretch the column right across the screen and hide everything else"
HUGE = "word " * 400

path = pathlib.Path(tempfile.mkdtemp()) / "wr.gridly"
s = Sheet(path)
name, done = s.columns()
note = s.add_column("Note", ColumnType.TEXT)
r1 = s.rows()[0].id
s.set_cell(r1, name.id, "Ship it"); s.set_cell(r1, note.id, LONG)
r2 = s.add_row(); s.set_cell(r2, name.id, "Short"); s.set_cell(r2, note.id, "brief")
s.close()

def heights(app):
    return [r.height for r in app.query_one("#grid", DataTable).ordered_rows]

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(120, 30)) as pilot:
        t = app.query_one("#grid", DataTable)
        print("ellipsis, small rows :", heights(app), "| wrapping:", app.appearance.wrapping)
        assert heights(app) == [1, 1]

        # --- W alone grows the row; row_size is untouched
        await pilot.press("W"); await pilot.pause()
        print("wrap, row_size still :", app.appearance.row_size, "->", heights(app))
        assert app.appearance.row_size == "small", "wrapping should not need the row-size toggle"
        assert heights(app)[0] > 1, "the long row should have grown"
        assert heights(app)[1] == 1, "a short row stays one line"

        # --- the height matches what the value actually needs at that width
        width = [c.width for c in t.ordered_columns][2]
        expected = -(-len(LONG) // width)      # ceil
        print("width", width, "-> expected", expected, "got", heights(app)[0])
        assert heights(app)[0] == expected

        # --- narrower cap, taller row
        tall_before = heights(app)[0]
        while app.appearance.column_width != "small":
            await pilot.press("w"); await pilot.pause()
        print("small cap            :", app.appearance.column_width, heights(app))
        assert heights(app)[0] > tall_before

        # --- uncapped means nothing to wrap against, so back to flat rows
        while app.appearance.column_width != "unlimited":
            await pilot.press("w"); await pilot.pause()
        print("unlimited            :", app.appearance.column_width, heights(app), "| wrapping:", app.appearance.wrapping)
        assert not app.appearance.wrapping and heights(app) == [1, 1]

        # --- back to a cap, then check one value cannot own the screen
        while app.appearance.column_width != "small":
            await pilot.press("w"); await pilot.pause()
        app.sheet.set_cell(r1, note.id, HUGE)
        app.reload(); await pilot.pause()
        print("a huge value         :", heights(app), "capped at", MAX_WRAP_LINES)
        assert heights(app)[0] == MAX_WRAP_LINES
        app.sheet.set_cell(r1, note.id, LONG); app.reload(); await pilot.pause()

        # --- editing re-measures the row
        t.cursor_coordinate = Coordinate(1, 2); await pilot.pause()
        before = heights(app)[1]
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", TextArea).text = "padded out until it needs more than one line to show" * 2
        await pilot.press("ctrl+s"); await pilot.pause()
        print("stored               :", repr(app.sheet.rows()[1].values.get(note.id))[:40])
        print("after editing row 2  :", before, "->", heights(app)[1])
        assert heights(app)[1] > before

        # --- short values sit in the middle of a grown row, not at the top
        while app.appearance.column_width != "small":           # small cap -> a tall row
            await pilot.press("w"); await pilot.pause()
        height = heights(app)[0]
        short = t.get_cell_at(Coordinate(0, 0))       # "Ship it", one line
        above = len(short.plain) - len(short.plain.lstrip("\n"))
        print("row is", height, "tall; short value starts on line", above + 1)
        assert height >= 4, height
        assert above == (height - 1) // 2, (above, height)
        # the tall value that set the height keeps its first line
        tall = t.get_cell_at(Coordinate(0, 2))
        assert not tall.plain.startswith("\n"), "the tallest value should not be pushed down"
        while app.appearance.column_width != "large":
            await pilot.press("w"); await pilot.pause()

        # --- a selection survives the redraw that re-heights the row
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        await pilot.press("shift+down"); await pilot.pause()
        held = set(app._selected)
        assert held, "expected a selection to test with"
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("shift+down"); await pilot.pause()
        held = set(app._selected)
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", TextArea).text = "now a good deal longer than it was before, so the row must grow"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("selection after edit :", len(app._selected), "of", len(held))
        assert app._selected == held, "re-heighting must not drop the selection"
        painted = t.get_cell_at(t.cursor_coordinate)
        assert painted.spans, "and it should still be painted"
        await pilot.press("escape"); await pilot.pause()


        # --- turning wrapping off puts row_size back in charge
        await pilot.press("W"); await pilot.pause()
        print("ellipsis again       :", heights(app))
        assert heights(app) == [ROW_SIZES[app.appearance.row_size]] * 2
        await pilot.press("s"); await pilot.pause()
        print("s with ellipsis      :", app.appearance.row_size, heights(app))
        assert heights(app) == [ROW_SIZES["large"]] * 2
    print("ALL WRAP TESTS DONE")

def test_wrap():
    asyncio.run(main())
