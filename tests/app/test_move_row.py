import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "m.gridly"
    s = Sheet(path)
    name = s.columns()[0]
    for i, value in enumerate(["one", "two", "three"]):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, name.id, value)
    s.close()
    return path

def order(app):
    first = app.sheet.columns()[0].id
    return [r.values.get(first) for r in app.sheet.rows()]

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(90, 20)) as pilot:
        t = app.query_one("#grid", DataTable)
        print("start        :", order(app))

        # --- down, and the cursor goes with it
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("right_curly_bracket"); await pilot.pause()
        print("after down   :", order(app), "cursor:", t.cursor_coordinate.row)
        assert order(app) == ["two", "one", "three"]
        assert t.cursor_coordinate.row == 1, "the cursor should follow the row"

        # --- and back up
        await pilot.press("left_curly_bracket"); await pilot.pause()
        print("after up     :", order(app))
        assert order(app) == ["one", "two", "three"]

        # --- it stops at the ends rather than wrapping or failing
        await pilot.press("left_curly_bracket"); await pilot.pause()
        print("at the top   :", order(app), "cursor:", t.cursor_coordinate.row)
        assert order(app) == ["one", "two", "three"]
        assert t.cursor_coordinate.row == 0
        t.cursor_coordinate = Coordinate(2, 0); await pilot.pause()
        await pilot.press("right_curly_bracket"); await pilot.pause()
        assert order(app) == ["one", "two", "three"]
        assert t.cursor_coordinate.row == 2

        # --- alt+arrows do the same, for anyone who reaches for those
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("alt+down"); await pilot.pause()
        assert order(app) == ["two", "one", "three"]
        await pilot.press("alt+up"); await pilot.pause()
        assert order(app) == ["one", "two", "three"]
        print("alt works    : yes")

        # --- a move can be taken back
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("right_curly_bracket"); await pilot.pause()
        assert order(app) == ["two", "one", "three"]
        await pilot.press("u"); await pilot.pause()
        print("undone       :", order(app))
        assert order(app) == ["one", "two", "three"]

        # --- the new order is what is on disk
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("right_curly_bracket"); await pilot.pause()
        assert order(app) == ["two", "one", "three"]
    reopened = Sheet(app.sheet.path)
    first = reopened.columns()[0].id
    print("on disk      :", [r.values.get(first) for r in reopened.rows()])
    assert [r.values.get(first) for r in reopened.rows()] == ["two", "one", "three"]
    print("ALL MOVE ROW TESTS DONE")

def test_move_row():
    asyncio.run(main())
