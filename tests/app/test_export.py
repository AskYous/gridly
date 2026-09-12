import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, csv, datetime, pathlib, tempfile
from textual.widgets import Input, Static
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import ConfirmScreen, ExportScreen
from gridly.store import Sheet

out = pathlib.Path(tempfile.mkdtemp()).resolve()
path = out / "sheet.gridly"
s = Sheet(path)
name, done = s.columns()
pr  = s.add_column("Priority", ColumnType.SELECT, ["Low", "High"])
qty = s.add_column("Qty", ColumnType.NUMBER)
due = s.add_column("Due", ColumnType.DATE)
r1 = s.rows()[0].id
s.set_cell(r1, name.id, 'Milk, "the good kind"')
s.set_cell(r1, done.id, True); s.set_cell(r1, pr.id, "High")
s.set_cell(r1, qty.id, 7.5);   s.set_cell(r1, due.id, datetime.date(2026, 9, 9))
r2 = s.add_row()
s.set_cell(r2, name.id, "two\nlines and عربي")
s.set_cell(r2, done.id, False)
s.close()

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("E"); await pilot.pause()
        assert isinstance(app.screen, ExportScreen)
        suggested = app.screen.query_one("#path", Input).value
        print("suggests   :", pathlib.Path(suggested).name)
        assert suggested == str(out / "sheet.csv")
        await pilot.press("enter"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "should close after writing"

        target = out / "sheet.csv"
        raw = target.read_bytes()
        print("BOM for excel:", raw[:3] == b"\xef\xbb\xbf")
        with target.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        for row in rows:
            print("  ", row)
        assert rows[0] == ["Name", "Done", "Priority", "Qty", "Due"]
        assert rows[1] == ['Milk, "the good kind"', "yes", "High", "7.5", "2026-09-09"]
        assert rows[2] == ["two\nlines and عربي", "no", "", "", ""]

        # --- exporting again asks before overwriting; cancel leaves the file alone
        before = target.read_bytes()
        target.write_bytes(b"sentinel")
        await pilot.press("E"); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen, ConfirmScreen), app.screen
        print("confirm    :", app.screen.message)
        await pilot.press("n"); await pilot.pause()
        print("cancel kept the file:", target.read_bytes() == b"sentinel")
        assert target.read_bytes() == b"sentinel"

        # --- ...and confirming rewrites it
        await pilot.press("E"); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        await pilot.press("y"); await pilot.pause()
        print("overwrote  :", target.read_bytes() == before)
        assert target.read_bytes() == before


        # --- an empty name is refused, a bad directory reports instead of crashing
        await pilot.press("E"); await pilot.pause()
        app.screen.query_one("#path", Input).value = "   "
        await pilot.press("enter"); await pilot.pause()
        assert isinstance(app.screen, ExportScreen), "should stay open"
        print("empty name :", app.screen.query_one("#error", Static).content)
        app.screen.query_one("#path", Input).value = str(out / "no" / "such" / "dir.csv")
        await pilot.press("enter"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "closes, reports via a notification"
        print("bad dir did not crash the app")

        # --- ~ is expanded rather than making a folder called ~
        await pilot.press("E"); await pilot.pause()
        print("tilde ok   :", isinstance(app.screen, ExportScreen))
        await pilot.press("escape"); await pilot.pause()
    print("ALL EXPORT TESTS DONE")

def test_export():
    asyncio.run(main())
