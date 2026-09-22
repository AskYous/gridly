import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()
import asyncio, pathlib, tempfile
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.appearance import MIN_FIT_WIDTH, fair_cap
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
    return used, t.scrollable_content_region.width, {str(c.label).split("  ")[0]: c.width for c in t.ordered_columns}

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(80, 20)) as pilot:
        while app.appearance.column_width != "fit":
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
        assert widths["Note"] >= len(LONG), "with room to spare, nothing is squeezed"
        assert used == available, "with room to spare, the table fills the screen"

        # --- a hopeless viewport falls back to the floor rather than vanishing
        await pilot.resize_terminal(24, 20); await pilot.pause(); await pilot.pause()
        _, _, widths = spread(app)
        print("at 24 wide   :", widths)
        assert min(widths.values()) >= min(MIN_FIT_WIDTH, 6), widths


    app2 = GridlyApp(path)
    async with app2.run_test(size=(80, 20)) as pilot:
        await pilot.pause()
        print("reopened     :", app2.appearance.column_width)
        assert app2.appearance.column_width == "fit"
        used, available, _ = spread(app2)
        assert used <= available, (used, available)

    # --- a sheet too tall for the screen: the columns fill the room beside
    # the scrollbar, and give it back when the scrollbar goes
    tall = Sheet(path)
    for _ in range(30):
        tall.add_row()
    tall.close()
    app3 = GridlyApp(path)
    async with app3.run_test(size=(80, 20)) as pilot:
        await pilot.pause(); await pilot.pause()
        t = app3.query_one("#grid", DataTable)
        used, available, _ = spread(app3)
        print("tall, 80x20  :", "uses", used, "of", available, "beside the scrollbar")
        assert t.show_vertical_scrollbar
        assert used == available < t.content_size.width, (used, available)
        assert t.max_scroll_x == 0, "nothing hides under the scrollbar"

        await pilot.resize_terminal(80, 50); await pilot.pause(); await pilot.pause()
        used, available, _ = spread(app3)
        print("tall, 80x50  :", "uses", used, "of", available)
        assert not t.show_vertical_scrollbar
        assert used == available == t.content_size.width, (used, available)
    print("ALL FIT TESTS DONE")

def test_fit():
    asyncio.run(main())
