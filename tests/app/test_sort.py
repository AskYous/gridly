"""Sorting the grid: a view of the rows that never reorders the file."""

import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.store import Sheet


def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "s.gridly"
    s = Sheet(path)
    name = s.columns()[0]
    qty = s.add_column("Qty", ColumnType.NUMBER)
    for i, (value, n) in enumerate([("pear", 3), ("apple", 1), ("fig", 2)]):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, name.id, value)
        s.set_cell(rid, qty.id, n)
    s.close()
    return path


def shown(app):
    first = app._columns[0].id
    return [r.values.get(first) for r in app._rows]


def filed(app):
    first = app.sheet.columns()[0].id
    return [r.values.get(first) for r in app.sheet.rows()]


async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(120, 24)) as pilot:
        t = app.query_one("#grid", DataTable)
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()

        # --- S opens the form on the cursor's column; ctrl+s sorts by it
        await pilot.press("S"); await pilot.pause()
        assert app.screen.query_one("#column-0", Select).value == app._columns[0].id
        await pilot.press("ctrl+s"); await pilot.pause()
        print("sorted       :", shown(app))
        assert shown(app) == ["apple", "fig", "pear"]
        assert filed(app) == ["pear", "apple", "fig"], "the file keeps its order"
        # the heading says so, and no other heading does
        assert str(t.ordered_columns[0].label).endswith(" ↑")
        assert "↑" not in str(t.ordered_columns[1].label)

        # --- a new row stays at the bottom, and is not marked while it fits
        await pilot.press("a"); await pilot.pause()
        new = app._rows[-1]
        assert shown(app)[-1] is None
        # an empty cell sorts last anyway, so it is where it belongs
        assert not app._misplaced

        # --- typing into it leaves it put, marked ↕
        app._write(new, app._columns[0], "banana"); await pilot.pause()
        print("after edit   :", shown(app), "misplaced:", app._misplaced)
        assert shown(app) == ["apple", "fig", "pear", "banana"]
        assert app._misplaced == {new.id}
        assert "↕" in str(t.ordered_rows[3].label)

        # --- r puts it in place, and the cursor follows the row
        t.cursor_coordinate = Coordinate(3, 0); await pilot.pause()
        await pilot.press("r"); await pilot.pause()
        print("re-sorted    :", shown(app))
        assert shown(app) == ["apple", "banana", "fig", "pear"]
        assert not app._misplaced
        assert app._rows[t.cursor_coordinate.row].id == new.id

        # --- rows cannot be moved by hand while sorted
        await pilot.press("right_curly_bracket"); await pilot.pause()
        assert shown(app) == ["apple", "banana", "fig", "pear"]

        # --- descending flips it, and an empty cell still goes last
        qty = next(c for c in app._columns if c.name == "Qty")
        app.sheet.set_sort_text(f"-{qty.id}")
        app._resort(); await pilot.pause()
        print("by qty desc  :", shown(app))
        qty_at = app._columns.index(qty)
        assert str(t.ordered_columns[qty_at].label).endswith(" ↓")
        assert "↑" not in str(t.ordered_columns[0].label)
        assert shown(app) == ["pear", "fig", "apple", "banana"]  # banana has no qty

        # --- the sort is kept in the sheet, for next time
        reopened = Sheet(app.sheet.path)
        assert reopened.sort_text() == f"-{qty.id}"
        reopened.close()

        # --- turning it off puts the file's order back
        await pilot.press("S"); await pilot.pause()
        await pilot.click("#off"); await pilot.pause()
        print("off          :", shown(app))
        assert shown(app) == filed(app)
        assert not app._levels
        assert not any("↑" in str(c.label) or "↓" in str(c.label) for c in t.ordered_columns)
    print("ALL SORT TESTS DONE")


def test_sort():
    asyncio.run(main())
