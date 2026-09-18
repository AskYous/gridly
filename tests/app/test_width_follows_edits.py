"""A column is only as wide as what is in it, so an edit has to be able to move it.

It used to take pressing w all the way round the cycle and back before a new
value was allowed to widen its column — the grid redrew on a setting change and
on nothing else.
"""

import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()
import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.appearance import COLUMN_CAPS
from gridly.coltypes import ColumnType
from gridly.store import Sheet

path = pathlib.Path(tempfile.mkdtemp()) / "e.gridly"
s = Sheet(path)
name, done = s.columns()
note = s.add_column("Note", ColumnType.TEXT)
r = s.rows()[0].id
s.set_cell(r, name.id, "Ship it"); s.set_cell(r, note.id, "ok")
s.close()

NOTE = Coordinate(0, 2)


def width_of(app, heading):
    t = app.query_one("#grid", DataTable)
    return {str(c.label).split("  ")[0]: c.width for c in t.ordered_columns}[heading]


async def at(app, pilot, mode):
    while app.appearance.column_width != mode:
        await pilot.press("w"); await pilot.pause()
    await pilot.pause()


async def type_into_note(app, pilot, text):
    await pilot.press("enter"); await pilot.pause()   # open the cell editor
    app.screen.query_one("#value").text = text
    await pilot.press("ctrl+s"); await pilot.pause(); await pilot.pause()


async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(120, 24)) as pilot:
        t = app.query_one("#grid", DataTable)
        t.cursor_coordinate = NOTE; await pilot.pause()

        # --- a capped column grows towards its cap as soon as the value lands
        await at(app, pilot, "large")
        before = width_of(app, "Note")
        print("large, short :", before)
        await type_into_note(app, pilot, "a much longer note than before")
        after = width_of(app, "Note")
        print("after typing :", after, "(no w pressed)")
        assert after > before, (before, after)
        assert after == len("a much longer note than before"), after

        # --- and shrinks back when the long value goes away again
        await type_into_note(app, pilot, "ok")
        print("back to short:", width_of(app, "Note"))
        assert width_of(app, "Note") == before, width_of(app, "Note")

        # --- the cap is still a cap
        await type_into_note(app, pilot, "x" * 80)
        print("past the cap :", width_of(app, "Note"))
        assert width_of(app, "Note") == COLUMN_CAPS["large"]
        await type_into_note(app, pilot, "ok")

        # --- fit shares the viewport out again too
        await at(app, pilot, "fit")
        before = width_of(app, "Note")
        print("fit, short   :", before)
        await type_into_note(app, pilot, "a much longer note than before")
        print("fit, longer  :", width_of(app, "Note"))
        assert width_of(app, "Note") > before

        # --- clearing a cell counts as a change as much as filling one does
        await at(app, pilot, "large")
        wide = width_of(app, "Note")
        await pilot.press("backspace"); await pilot.pause(); await pilot.pause()
        print("after delete :", wide, "->", width_of(app, "Note"))
        assert width_of(app, "Note") < wide
    print("ALL WIDTH-FOLLOWS-EDITS TESTS DONE")


def test_width_follows_edits():
    asyncio.run(main())
