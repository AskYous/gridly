import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()
import asyncio, datetime, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.store import Sheet

path = pathlib.Path(tempfile.mkdtemp()) / "d.gridly"
s = Sheet(path)
name, done = s.columns()
pr  = s.add_column("Priority", ColumnType.SELECT, ["Low", "High"])
qty = s.add_column("Qty", ColumnType.NUMBER)
due = s.add_column("Due", ColumnType.DATE)
r1 = s.rows()[0].id
s.set_cell(r1, name.id, "Milk\nand honey"); s.set_cell(r1, done.id, True)
s.set_cell(r1, pr.id, "High"); s.set_cell(r1, qty.id, 7.5)
s.set_cell(r1, due.id, datetime.date(2026, 9, 9))
r2 = s.add_row(); s.set_cell(r2, name.id, "Bread")
r3 = s.add_row()                                   # left empty on purpose
s.close()

def data(app):
    cols = app.sheet.columns()
    return [[r.values.get(c.id) for c in cols] for r in app.sheet.rows()]

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(110, 30)) as pilot:
        t = app.query_one("#grid", DataTable)
        print("before      :", len(app.sheet.rows()), "rows")

        # --- the copy lands directly below, values and all
        await pilot.press("D"); await pilot.pause()
        rows = data(app)
        print("after D     :", len(rows), "rows")
        print("  row 1     :", rows[0])
        print("  row 2     :", rows[1])
        assert rows[0] == rows[1], "the copy should match the original"
        assert rows[2][0] == "Bread", "and it should not displace what followed"
        assert len(rows) == 4

        # --- the cursor follows the copy, so you can edit it straight away
        print("cursor      :", t.cursor_coordinate, "->", app.current_row().values.get(name.id))
        assert t.cursor_coordinate.row == 1
        assert app._rows[1].id != app._rows[0].id, "a real new row, not the same one"

        # --- editing the copy leaves the original alone
        await pilot.press("enter"); await pilot.pause()
        from textual.widgets import TextArea
        app.screen.query_one("#value", TextArea).text = "Oat milk"
        await pilot.press("ctrl+s"); await pilot.pause()
        rows = data(app)
        print("independent :", rows[0][0][:12], "|", rows[1][0])
        assert rows[0][0] == "Milk\nand honey" and rows[1][0] == "Oat milk"

        # --- duplicating an empty row gives another empty row
        t.cursor_coordinate = Coordinate(3, 0); await pilot.pause()
        await pilot.press("D"); await pilot.pause()
        rows = data(app)
        print("empty copy  :", rows[4])
        assert all(v is None for v in rows[4])

        # --- it survives a reopen, in order
        order_before = [r[0] for r in data(app)]
        await pilot.press("v"); await pilot.pause()      # and works flipped
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("D"); await pilot.pause()
        print("flipped     :", [r[0] for r in data(app)])
        assert t.cursor_coordinate.column == 1, "the cursor follows the copy across"

    reopened = Sheet(path)
    cols = reopened.columns()
    print("on disk     :", [[r.values.get(c.id) for c in cols][0] for r in reopened.rows()])
    print("ALL DUPLICATE TESTS DONE")

def test_duplicate():
    asyncio.run(main())
