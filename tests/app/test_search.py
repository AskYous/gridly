import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Static
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "f.gridly"
    s = Sheet(path)
    name, done = s.columns()
    note = s.add_column("Note", ColumnType.TEXT)
    rows = [("Milk", True, "buy oat milk"), ("Bread", False, "sourdough"),
            ("Eggs", True, "half dozen"), ("Oat milk", False, "")]
    for i, (n, d, x) in enumerate(rows):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, name.id, n); s.set_cell(rid, done.id, d)
        if x: s.set_cell(rid, note.id, x)
    s.close()
    return path

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 24)) as pilot:
        t = app.query_one("#grid", DataTable)
        bar = app.query_one("#search", Input)
        status = app.query_one("#status", Static)

        # --- the bar is out of the way until asked for
        assert not bar.display
        await pilot.press("slash"); await pilot.pause()
        assert bar.display and app.focused is bar
        print("bar opens    : yes")

        # --- it finds as you type, across every column
        await pilot.press(*"milk"); await pilot.pause()
        print("matches      :", app._matches)
        assert app._matches == [
            Coordinate(0, 0),   # Milk
            Coordinate(0, 2),   # buy oat milk
            Coordinate(3, 0),   # Oat milk
        ]
        print("status says  :", status.content.plain.split("  ·  ")[-2])
        assert "3 matches" in status.content.plain

        # --- and lands on the first one
        assert t.cursor_coordinate == Coordinate(0, 0)

        # --- matching ignores case and reads the value, not the raw text
        bar.value = "YES"; await pilot.pause()
        print("booleans     :", app._matches)
        assert app._matches == [Coordinate(0, 1), Coordinate(2, 1)]

        # --- enter hands the grid back but keeps the matches lit
        bar.value = "milk"; await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert not bar.display and app.focused is t
        assert len(app._matches) == 3
        cell = t.get_cell_at(Coordinate(3, 0))
        print("still lit    :", bool(cell.spans))
        assert cell.spans, "a match should stay highlighted"

        # --- n and N walk through them, round and round
        seen = [t.cursor_coordinate]
        for _ in range(3):
            await pilot.press("n"); await pilot.pause()
            seen.append(t.cursor_coordinate)
        print("n walks      :", seen)
        assert seen == [Coordinate(0, 0), Coordinate(0, 2), Coordinate(3, 0), Coordinate(0, 0)]
        await pilot.press("N"); await pilot.pause()
        assert t.cursor_coordinate == Coordinate(3, 0)

        # --- escape puts the cursor back and clears the highlight
        t.cursor_coordinate = Coordinate(2, 1); await pilot.pause()
        await pilot.press("slash"); await pilot.press(*"bread"); await pilot.pause()
        assert t.cursor_coordinate == Coordinate(1, 0)
        await pilot.press("escape"); await pilot.pause()
        print("escaped to   :", t.cursor_coordinate, "| matches:", app._matches)
        assert t.cursor_coordinate == Coordinate(2, 1)
        assert app._matches == []
        assert not t.get_cell_at(Coordinate(1, 0)).spans

        # --- something that is not there says so rather than moving
        await pilot.press("slash"); await pilot.press(*"zzz"); await pilot.pause()
        assert app._matches == []
        await pilot.press("enter"); await pilot.pause()
        print("nothing found: cursor stayed at", t.cursor_coordinate)

        # --- stepping with nothing searched for is not an error
        await pilot.press("n"); await pilot.pause()
        await pilot.press("N"); await pilot.pause()

        # --- what is found follows an edit
        await pilot.press("slash"); await pilot.press(*"eggs"); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert app._matches == [Coordinate(2, 0)]
        await pilot.press("enter"); await pilot.pause()
        from textual.widgets import TextArea
        app.screen.query_one("#value", TextArea).text = "Duck eggs"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after editing:", app._matches)
        assert app._matches == [Coordinate(2, 0)], "still a match, rewritten"

        # --- and after a row goes
        await pilot.press("d"); await pilot.pause()
        print("after delete :", app._matches)
        assert app._matches == []
    print("ALL SEARCH TESTS DONE")

def test_search():
    asyncio.run(main())
