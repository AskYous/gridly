import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, datetime, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Select, Static, TextArea
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import RowFormScreen
from gridly.store import Sheet

path = pathlib.Path(tempfile.mkdtemp()) / "f.gridly"
s = Sheet(path)
name, done = s.columns()
pr  = s.add_column("Priority", ColumnType.SELECT, ["Low", "High"])
qty = s.add_column("Qty", ColumnType.NUMBER)
due = s.add_column("Due", ColumnType.DATE)
r1 = s.rows()[0].id
s.set_cell(r1, name.id, "Milk"); s.set_cell(r1, done.id, True)
s.set_cell(r1, pr.id, "High");   s.set_cell(r1, qty.id, 3)
s.set_cell(r1, due.id, datetime.date(2026, 9, 9))
r2 = s.add_row()
s.close()

def vals(app, row=0):
    return {c.name: app.sheet.rows()[row].values.get(c.id) for c in app.sheet.columns()}

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 34)) as pilot:
        t = app.query_one("#grid", DataTable)
        await pilot.press("f"); await pilot.pause()
        form = app.screen
        assert isinstance(form, RowFormScreen), form
        print("title:", form.query_one(".dialog-title").content)

        # fields are pre-filled from the row
        print("prefill text  :", form.query_one(f"#field-{name.id}", TextArea).text)
        print("prefill bool  :", form.query_one(f"#field-{done.id}", Select).value)
        print("prefill select:", form.query_one(f"#field-{pr.id}", Select).value)
        print("prefill number:", form.query_one(f"#field-{qty.id}", Input).value)
        print("prefill date  :", form.query_one(f"#field-{due.id}", Input).value)

        # a bad number blocks the save and names the offending column
        form.query_one(f"#field-{qty.id}", Input).value = "abc"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, RowFormScreen), "should stay open"
        print("blocked:", form.query_one("#error", Static).content)
        assert app.focused.id == f"field-{qty.id}", "should focus the bad field"

        # fix it, change every type, and save
        form.query_one(f"#field-{qty.id}", Input).value = "7.5"
        form.query_one(f"#field-{name.id}", TextArea).text = "Oat milk"
        form.query_one(f"#field-{due.id}", Input).value = "today"
        form.query_one(f"#field-{done.id}", Select).value = "no"
        form.query_one(f"#field-{pr.id}", Select).value = "Low"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "form should close"
        print("saved:", vals(app))

        # blanking a Select writes an undefined cell
        await pilot.press("f"); await pilot.pause()
        app.screen.query_one(f"#field-{done.id}", Select).value = Select.NULL
        app.screen.query_one(f"#field-{pr.id}", Select).value = Select.NULL
        app.screen.query_one(f"#field-{due.id}", Input).value = ""
        await pilot.press("ctrl+s"); await pilot.pause()
        print("cleared:", vals(app))

        # escape discards edits
        await pilot.press("f"); await pilot.pause()
        app.screen.query_one(f"#field-{name.id}", TextArea).text = "THROWN AWAY"
        await pilot.press("escape"); await pilot.pause()
        print("after escape:", vals(app)["Name"])

        # an empty row round-trips, and enter saves too
        t.cursor_coordinate = Coordinate(1, 0); await pilot.pause()
        await pilot.press("f"); await pilot.pause()
        print("empty row title:", app.screen.query_one(".dialog-title").content)
        app.screen.query_one(f"#field-{name.id}", TextArea).focus()
        await pilot.press(*"Bread"); await pilot.press("ctrl+s"); await pilot.pause()
        print("row 2 saved:", vals(app, 1))

    print("on disk:", {c.name: Sheet(path).rows()[0].values.get(c.id) for c in Sheet(path).columns()})
    print("ALL FORM TESTS DONE")

def test_form():
    asyncio.run(main())
