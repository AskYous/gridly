import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import OptionRow
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "c.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    status = s.add_column("Status", ColumnType.TEXT)
    wide = s.add_column("Wide", ColumnType.TEXT)
    for i, value in enumerate(["Open", "Closed", "Open", "Pending", "Closed"]):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, status.id, value)
    for i in range(25):
        s.set_cell(s.add_row(), wide.id, f"v{i}")
    s.close()
    return path

def rows(app):
    return list(app.screen.query(OptionRow))

def names(app):
    return [r.query_one(".option-name", Input).value for r in rows(app)]

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 40)) as pilot:
        t = app.query_one("#grid", DataTable)

        # --- switching a text column to dropdown offers its own values
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#type", Select).value = ColumnType.SELECT.value
        await pilot.pause()
        print("seeded rows :", names(app))
        assert names(app) == ["Open", "Closed", "Pending"]

        await pilot.press("ctrl+s"); await pilot.pause()
        column = [c for c in app.sheet.columns() if c.name == "Status"][0]
        print("saved       :", column.options)
        assert column.options == ["Open", "Closed", "Pending"]
        # the values themselves survived the conversion untouched
        assert [r.values.get(column.id) for r in app.sheet.rows()[:5]] == [
            "Open", "Closed", "Open", "Pending", "Closed",
        ]

        # --- reopening and toggling away and back leaves it alone, not doubled
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#type", Select).value = ColumnType.TEXT.value
        await pilot.pause()
        app.screen.query_one("#type", Select).value = ColumnType.SELECT.value
        await pilot.pause()
        print("after toggle:", names(app))
        assert names(app) == ["Open", "Closed", "Pending"]
        await pilot.press("escape"); await pilot.pause()

        # --- too many distinct values to seed: falls back to one blank row
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#type", Select).value = ColumnType.SELECT.value
        await pilot.pause()
        print("over cap    :", names(app))
        assert names(app) == [""]
    print("ALL CONVERT-TO-DROPDOWN TESTS DONE")

def test_convert_to_dropdown():
    asyncio.run(main())
