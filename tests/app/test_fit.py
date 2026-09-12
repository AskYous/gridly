import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()
import asyncio, pathlib, tempfile
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.view import MIN_FIT_WIDTH, fair_cap
from gridly.coltypes import ColumnType
from gridly.store import Sheet

# --- the allocator on its own
print("all fit      :", fair_cap([3, 4, 5], 30, 6), "(no squeeze needed)")
print("squeeze wide :", fair_cap([3, 4, 40], 30, 6), "(narrow ones paid in full)")
print("very tight   :", fair_cap([40, 40, 40], 9, 6), "(floor kicks in)")
assert fair_cap([3, 4, 40], 30, 6) == 23, fair_cap([3, 4, 40], 30, 6)
assert fair_cap([40, 40, 40], 9, 6) == 6

LONG = "Confirm with Waseem that change-primary-number will be fixed in the OCP side"
path = pathlib.Path(tempfile.mkdtemp()) / "f.gridly"
s = Sheet(path)
name, done = s.columns()
note = s.add_column("Note", ColumnType.TEXT)
status = s.add_column("Status", ColumnType.SELECT, ["New", "Done"])
r = s.rows()[0].id
s.set_cell(r, name.id, "Ship it"); s.set_cell(r, done.id, True)
s.set_cell(r, note.id, LONG); s.set_cell(r, status.id, "New")
s.add_row(); s.close()

def spread(app):
    t = app.query_one("#grid", DataTable)
    pad = 2 * t.cell_padding
    used = sum(c.width + pad for c in t.ordered_columns) + t._row_label_column_width
    return used, t.content_size.width, {str(c.label).split("  ")[0]: c.width for c in t.ordered_columns}

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(80, 20)) as pilot:
        while app.view.column_width != "fit":
            await pilot.press("w"); await pilot.pause()
        await pilot.pause()
        used, available, widths = spread(app)
        print("at 80 wide   :", widths, "-> uses", used, "of", available)
        assert used <= available, (used, available)
        # a narrow column is paid in full (its header sets the floor) and the
        # wide one absorbs the squeeze
        assert widths["Done"] == len("Done  y/n"), widths
        assert widths["Status"] == len("Status  list"), widths
        assert widths["Note"] < len(LONG), widths

        # --- narrower viewport, narrower columns, still no overflow
        app.query_one("#grid", DataTable).styles.width = None
        await pilot.resize_terminal(60, 20); await pilot.pause(); await pilot.pause()
        used, available, widths = spread(app)
        print("at 60 wide   :", widths, "-> uses", used, "of", available)
        assert used <= available, (used, available)

        # --- wider viewport gives the room back
        await pilot.resize_terminal(140, 20); await pilot.pause(); await pilot.pause()
        used, available, widths = spread(app)
        print("at 140 wide  :", widths, "-> uses", used, "of", available)
        assert used <= available
        assert widths["Note"] == len(LONG), "with room to spare, nothing is squeezed"

        # --- a hopeless viewport falls back to the floor rather than vanishing
        await pilot.resize_terminal(24, 20); await pilot.pause(); await pilot.pause()
        _, _, widths = spread(app)
        print("at 24 wide   :", widths)
        assert min(widths.values()) >= min(MIN_FIT_WIDTH, 6), widths

        # --- fit is remembered, and works in the flipped view
        await pilot.resize_terminal(90, 20); await pilot.pause(); await pilot.pause()
        await pilot.press("v"); await pilot.pause()
        used, available, widths = spread(app)
        print("flipped      :", widths, "-> uses", used, "of", available)
        assert used <= available
        await pilot.press("v"); await pilot.pause()

    app2 = GridlyApp(path)
    async with app2.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        print("reopened     :", app2.view.column_width)
        assert app2.view.column_width == "fit"
        used, available, _ = spread(app2)
        assert used <= available, (used, available)
    print("ALL FIT TESTS DONE")

def test_fit():
    asyncio.run(main())
