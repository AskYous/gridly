import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
import gridly.app as appmod
from textual import events
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Static
from gridly.app import GridlyApp
from gridly.clipboard import parse_block
from gridly.coltypes import ColumnType
from gridly.store import Sheet


def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "s.gridly"
    s = Sheet(path)
    name, done = s.columns()
    qty = s.add_column("Qty", ColumnType.NUMBER)
    for i, (n, d, q) in enumerate([("Milk", True, 3), ("Bread", False, 1), ("Eggs", True, 12)]):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, name.id, n); s.set_cell(rid, done.id, d); s.set_cell(rid, qty.id, q)
    s.close()
    return path

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 30)) as pilot:
        t = app.query_one("#grid", DataTable)
        status = app.query_one("#status", Static)

        # --- nothing selected to start; y copies one cell
        await pilot.press("y"); await pilot.pause()
        print("bare y     :", repr(app._clipboard))
        assert app._clipboard == "Milk"

        # --- shift+arrows build a block, one press at a time or several
        await pilot.press("shift+down", "shift+right"); await pilot.pause()
        print("selected   :", len(app._selected), "cells |", status.content.plain)
        assert "2 × 2 selected" in status.content.plain, status.content.plain
        assert app._selected == {Coordinate(r, c) for r in (0, 1) for c in (0, 1)}

        cell = t.get_cell_at(Coordinate(0, 0))
        print("highlight  :", {str(span.style) for span in cell.spans})
        assert cell.spans, "selected cells should be painted"
        await pilot.press("y"); await pilot.pause()
        print("y on block :", repr(app._clipboard))
        assert parse_block(app._clipboard) == [["Milk", "yes"], ["Bread", "no"]]

        # --- shrinking back to one cell stops being a selection
        await pilot.press("shift+up", "shift+left"); await pilot.pause()
        print("shrunk     :", app._selected, "| region:", app._selection_region())
        await pilot.press("y"); await pilot.pause()
        assert app._clipboard == "Milk", "back to a single cell"

        # --- extending backwards from an anchor works too
        t.cursor_coordinate = Coordinate(2, 2); await pilot.pause()
        await pilot.press("shift+up", "shift+left"); await pilot.pause()
        await pilot.press("y"); await pilot.pause()
        print("backwards  :", parse_block(app._clipboard))
        assert parse_block(app._clipboard) == [["no", "1"], ["yes", "12"]]

        # --- a plain arrow drops the selection
        await pilot.press("up"); await pilot.pause()
        print("after arrow:", app._selected, app._anchor)
        assert not app._selected and app._anchor is None

        # --- escape drops it too
        await pilot.press("shift+left"); await pilot.pause()
        assert app._selected
        await pilot.press("escape"); await pilot.pause()
        print("after esc  :", app._selected, app._anchor)
        assert not app._selected and app._anchor is None

        # --- it stops at the edges instead of running off
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("shift+up", "shift+left", "shift+up"); await pilot.pause()
        print("at corner  :", t.cursor_coordinate, "| selected:", len(app._selected))
        assert t.cursor_coordinate == Coordinate(0, 0)
        await pilot.press("escape"); await pilot.pause()

        # --- editing a cell inside the selection keeps the block intact
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("shift+down"); await pilot.pause()
        held = set(app._selected)
        await pilot.press("enter"); await pilot.pause()
        await pilot.press("backspace", *"55", "enter"); await pilot.pause()
        print("wrapping   :", app.view.wrapping, "| width:", app.view.column_width, "| overflow:", app.view.overflow)
        print("held       :", sorted(held), "now:", sorted(app._selected))
        print("after edit :", len(app._selected), "still selected")
        assert app._selected == held
        # and the edited cell is still *painted* as selected, not just tracked
        edited = t.get_cell_at(t.cursor_coordinate)
        print("           :", {str(sp.style) for sp in edited.spans} or "NOT PAINTED")
        assert edited.spans, "editing must not wipe the selection highlight"

        # --- selection follows the flipped view, and flipping drops it
        await pilot.press("escape"); await pilot.pause()
        await pilot.press("v"); await pilot.pause()
        assert not app._selected, "flipping starts fresh"
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("shift+right", "shift+down"); await pilot.pause()
        await pilot.press("y"); await pilot.pause()
        print("flipped y  :", parse_block(app._clipboard))
        assert parse_block(app._clipboard) == [["Milk", "Bread"], ["yes", "no"]]

        # --- and what it copies pastes back unchanged
        before = [[r.values.get(c.id) for c in app.sheet.columns()] for r in app.sheet.rows()]
        app.post_message(events.Paste(app._clipboard))
        await pilot.pause(); await pilot.pause()
        if app.screen is not app.screen_stack[0]:
            await pilot.press("y"); await pilot.pause()
        after = [[r.values.get(c.id) for c in app.sheet.columns()] for r in app.sheet.rows()]
        print("round trip :", before == after)
        assert before == after
    print("ALL SELECTION TESTS DONE")

def test_select():
    asyncio.run(main())
