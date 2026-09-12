import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual import events
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Static, TextArea
from gridly.app import GridlyApp
from gridly.appearance import fit
from gridly.coltypes import ColumnType
from gridly.screens import CellEditScreen, RowFormScreen
from gridly.store import Sheet

print("1-line row :", repr(fit("first\nsecond\nthird", 1).plain))
print("3-line row :", repr(fit("first\nsecond\nthird", 3).plain))
print("tabs flat  :", repr(fit("a\tb", 1).plain))

path = pathlib.Path(tempfile.mkdtemp()) / "ml.gridly"
s = Sheet(path); s.add_column("Qty", ColumnType.NUMBER); s.close()

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 34)) as pilot:
        t = app.query_one("#grid", DataTable)
        note, done, qty = app.sheet.columns()

        # paste a multi-line cell the way Sheets writes it
        app.post_message(events.Paste('"line one\nline two"\tTRUE\t5\n'))
        await pilot.pause(); await pilot.pause()
        stored = app.sheet.rows()[0].values[note.id]
        print("stored     :", repr(stored))
        print("grid shows :", repr(t.get_cell_at(Coordinate(0, 0)).plain))
        assert stored == "line one\nline two"

        # the cell editor is a TextArea holding BOTH lines
        await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen, CellEditScreen)
        editor = app.screen.query_one("#value")
        assert isinstance(editor, TextArea), type(editor)
        print("editor text:", repr(editor.text))
        print("help says  :", app.screen.query_one(".dialog-help").content)

        # the cursor starts at the end, so enter adds a line rather than saving
        print("cursor at  :", editor.cursor_location, "of", editor.document.end)
        assert editor.cursor_location == editor.document.end
        await pilot.press("enter"); await pilot.press(*"three")
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after edit :", repr(app.sheet.rows()[0].values[note.id]))
        assert app.sheet.rows()[0].values[note.id] == "line one\nline two\nthree"

        # a number column still gets a one-line Input that enter saves
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen.query_one("#value"), Input)
        print("number help:", app.screen.query_one(".dialog-help").content)
        await pilot.press("backspace", *"42", "enter"); await pilot.pause()
        print("number now :", app.sheet.rows()[0].values[qty.id])

        # the form shows a TextArea for text and keeps every line
        await pilot.press("f"); await pilot.pause()
        form = app.screen
        assert isinstance(form, RowFormScreen)
        field = form.query_one(f"#field-{note.id}")
        assert isinstance(field, TextArea), type(field)
        print("form field :", repr(field.text))
        field.text = "alpha\nbeta\ngamma"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("form saved :", repr(app.sheet.rows()[0].values[note.id]))
        assert app.sheet.rows()[0].values[note.id] == "alpha\nbeta\ngamma"
        print("grid shows :", repr(t.get_cell_at(Coordinate(0, 0)).plain))
    print("ALL MULTILINE TESTS DONE")

def test_multiline():
    asyncio.run(main())
