import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType, assign_colors
from gridly.screens import OptionRow
from gridly.store import Sheet

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "r.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    task = s.add_column("Task", ColumnType.TEXT)
    opts = ["Doing", "Blocked", "Done"]
    status = s.add_column("Status", ColumnType.SELECT, opts, assign_colors(opts, {}))
    for i, (t, st) in enumerate(
        [("one", "Doing"), ("two", "Doing"), ("three", "Blocked"), ("four", "Done")]
    ):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, task.id, t); s.set_cell(rid, status.id, st)
    s.close()
    return path

def statuses(app):
    status = app.sheet.columns()[1]
    return [r.values.get(status.id) for r in app.sheet.rows()]

def rows_of(app):
    return list(app.screen.query(OptionRow))

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 40)) as pilot:
        t = app.query_one("#grid", DataTable)
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        print("before       :", statuses(app))

        # --- rewording an option takes its values with it
        await pilot.press("e"); await pilot.pause()
        rows_of(app)[0].query_one(".option-name", Input).value = "In progress"
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after reword :", statuses(app))
        assert statuses(app) == ["In progress", "In progress", "Blocked", "Done"]
        assert app.sheet.columns()[1].options == ["In progress", "Blocked", "Done"]

        # --- the colour goes with the new wording
        colors = app.sheet.columns()[1].colors
        print("colours      :", colors)
        assert "In progress" in colors and "Doing" not in colors

        # --- rewording two at once, including a swap of their names
        await pilot.press("e"); await pilot.pause()
        rows_of(app)[0].query_one(".option-name", Input).value = "Blocked"
        rows_of(app)[1].query_one(".option-name", Input).value = "In progress"
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after swap   :", statuses(app))
        assert statuses(app) == ["Blocked", "Blocked", "In progress", "Done"]

        # --- deleting an option still clears its cells, and says so
        await pilot.press("e"); await pilot.pause()
        rows_of(app)[0].query_one(".option-name", Input).value = ""
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after delete :", statuses(app))
        assert statuses(app) == [None, None, "In progress", "Done"]

        # --- and that is undoable
        await pilot.press("u"); await pilot.pause()
        print("undone       :", statuses(app))
        assert statuses(app) == ["Blocked", "Blocked", "In progress", "Done"]

        # --- renaming the column itself leaves the values alone
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#name", Input).value = "Stage"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("column named :", app.sheet.columns()[1].name, statuses(app))
        assert app.sheet.columns()[1].name == "Stage"
        assert statuses(app) == ["Blocked", "Blocked", "In progress", "Done"]

        # --- a new option added alongside a reword does not confuse it
        await pilot.press("e"); await pilot.pause()
        rows_of(app)[0].query_one(".option-name", Input).value = "Underway"
        app.screen.query_one("#add-option").press(); await pilot.pause()
        rows_of(app)[-1].query_one(".option-name", Input).value = "Parked"
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("reword + add :", statuses(app), app.sheet.columns()[1].options)
        assert statuses(app) == ["Underway", "Underway", "In progress", "Done"]
        assert "Parked" in app.sheet.columns()[1].options
    print("ALL RENAME TESTS DONE")

def test_rename_option():
    asyncio.run(main())
