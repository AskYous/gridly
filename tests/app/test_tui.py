import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual.widgets import Button, DataTable, Input, Select, TextArea
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import CellEditScreen, ColumnScreen, ConfirmScreen, OptionRow, PickScreen
from gridly.store import Sheet

path = pathlib.Path(tempfile.mkdtemp()) / "demo.gridly"

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 28)) as pilot:
        t = app.query_one("#grid", DataTable)
        assert (len(t.columns), len(t.rows)) == (2, 1), (len(t.columns), len(t.rows))
        print("start:", len(t.columns), "cols", len(t.rows), "row")

        # --- edit a text cell via enter
        await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen, CellEditScreen), app.screen
        await pilot.press(*"Milk"); await pilot.press("ctrl+s"); await pilot.pause()  # text = TextArea
        print("after text edit:", app.sheet.rows()[0].values)

        # --- invalid input is rejected and the dialog stays open
        await pilot.press("right"); await pilot.press("enter"); await pilot.pause()
        print("bool toggled ->", list(app.sheet.rows()[0].values.values()))
        await pilot.press("enter"); await pilot.pause()
        print("bool toggled back ->", list(app.sheet.rows()[0].values.values()))

        # --- add a NUMBER column through the dialog
        await pilot.press("c"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        await pilot.press(*"Qty")
        app.screen.query_one("#type", Select).value = ColumnType.NUMBER.value
        await pilot.pause()
        assert not app.screen.query_one("#options").display, "options field should hide"
        await pilot.press("enter"); await pilot.pause()
        print("cols:", [(c.name, c.type.value) for c in app.sheet.columns()])

        # --- bad number is refused, good one sticks
        t.cursor_coordinate = t.cursor_coordinate.__class__(0, 2); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        await pilot.press(*"abc"); await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen, CellEditScreen), "dialog should stay open on bad input"
        print("rejected bad number, error:", app.screen.query_one("#error").content)
        for _ in range(3): await pilot.press("backspace")
        await pilot.press(*"12.5"); await pilot.press("enter"); await pilot.pause()
        print("number saved:", app.sheet.rows()[0].values)

        # --- dropdown column + picker
        await pilot.press("c"); await pilot.pause()
        await pilot.press(*"Priority")
        app.screen.query_one("#type", Select).value = ColumnType.SELECT.value
        await pilot.pause()
        assert app.screen.query_one("#options").display, "options field should show"
        rows = list(app.screen.query(OptionRow))
        rows[0].query_one(".option-name", Input).value = "Low"
        app.screen.query_one("#add-option", Button).press(); await pilot.pause()
        list(app.screen.query(OptionRow))[1].query_one(".option-name", Input).value = "High"
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        t.cursor_coordinate = t.cursor_coordinate.__class__(0, 3); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen, PickScreen), app.screen
        await pilot.press("down", "down", "enter"); await pilot.pause()
        print("picked:", app.sheet.rows()[0].values)

        # --- dropdown with no options is refused
        await pilot.press("c"); await pilot.pause()
        await pilot.press(*"Bad")
        app.screen.query_one("#type", Select).value = ColumnType.SELECT.value
        await pilot.pause(); await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen), "should refuse empty dropdown"
        print("refused empty dropdown:", app.screen.query_one("#error").content)
        await pilot.press("escape"); await pilot.pause()

        # --- rows
        await pilot.press("a"); await pilot.press("a"); await pilot.pause()
        print("rows after 'a' x2:", len(t.rows), "cursor:", t.cursor_coordinate)
        # an empty row goes without asking, so fill it to exercise the prompt
        app.sheet.set_cell(app.current_row().id, app.sheet.columns()[0].id, "keepme")
        app.reload()
        rows_before = len(app.sheet.rows())
        await pilot.press("d"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "delete no longer asks"
        assert len(app.sheet.rows()) == rows_before - 1
        print("rows after delete:", len(t.rows))

        # --- clear a cell
        t.cursor_coordinate = t.cursor_coordinate.__class__(0, 0); await pilot.pause()
        await pilot.press("backspace"); await pilot.pause()
        print("after clear:", app.sheet.rows()[0].values)

        # --- retype Qty number->text keeps the value
        t.cursor_coordinate = t.cursor_coordinate.__class__(0, 2); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        app.screen.query_one("#type", Select).value = ColumnType.TEXT.value
        await pilot.pause(); await pilot.press("enter"); await pilot.pause()
        print("after retype:", [(c.name, c.type.value) for c in app.sheet.columns()], app.sheet.rows()[0].values)

        # --- move + delete column
        await pilot.press("right"); await pilot.press("left_square_bracket"); await pilot.pause()
        print("after move:", [c.name for c in app.sheet.columns()], "cursor:", t.cursor_coordinate)
        await pilot.press("x"); await pilot.pause()
        await pilot.press("y"); await pilot.pause()
        print("after col delete:", [c.name for c in app.sheet.columns()])

        # --- help screen opens and closes
        await pilot.press("question_mark"); await pilot.pause()
        print("help open:", type(app.screen).__name__)
        await pilot.press("escape"); await pilot.pause()

        app.save_screenshot(str(pathlib.Path(tempfile.mkdtemp()) / "grid.svg"))

    # persistence across a fresh open
    reopened = Sheet(path)
    print("reopened:", [(c.name, c.type.value) for c in reopened.columns()],
          [r.values for r in reopened.rows()])
    print("ALL TUI TESTS DONE")

def test_tui():
    asyncio.run(main())
