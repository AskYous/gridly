import os, tempfile, pathlib, asyncio
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()
from textual.widgets import DataTable
from gridly import config
from gridly.app import GridlyApp
from gridly.appearance import COLUMN_CAPS
from gridly.coltypes import ColumnType
from gridly.store import Sheet

LONG = "This is a very long note that would otherwise stretch right across the screen"
path = pathlib.Path(tempfile.mkdtemp()) / "w.gridly"
s = Sheet(path)
name, done = s.columns()
note = s.add_column("Note", ColumnType.TEXT)
r = s.rows()[0].id
s.set_cell(r, name.id, "Ship it"); s.set_cell(r, done.id, True); s.set_cell(r, note.id, LONG)
s.close()

def widths(app):
    t = app.query_one("#grid", DataTable)
    return {str(c.label): c.width for c in t.ordered_columns}

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(120, 24)) as pilot:
        print("default mode :", app.appearance.column_width, "/", app.appearance.overflow)
        assert app.appearance.column_width == "fit", "fit is the default now"
        while app.appearance.column_width != "large":       # this test is about the fixed caps
            await pilot.press("w"); await pilot.pause()
        print("widths       :", widths(app))
        w = widths(app)
        assert w["Note  abc"] == COLUMN_CAPS["large"], w
        # a narrow column is never padded out to the cap
        assert w["Done  y/n"] < 10, w

        while app.appearance.column_width != "unlimited":
            await pilot.press("w"); await pilot.pause()
        print("now          :", app.appearance.column_width, widths(app))
        # uncapped columns are left to size themselves, which DataTable does lazily
        note = [c for c in app.query_one("#grid", DataTable).ordered_columns
                if str(c.label).startswith("Note")][0]
        print("             : auto_width =", note.auto_width)
        assert note.auto_width, "uncapped columns should size themselves"

        while app.appearance.column_width != "small":
            await pilot.press("w"); await pilot.pause()
        print("now          :", app.appearance.column_width, widths(app))
        assert widths(app)["Note  abc"] == COLUMN_CAPS["small"]

        # ellipsis vs wrap changes how the cell is drawn, not the width
        t = app.query_one("#grid", DataTable)
        cell = t.get_cell_at(t.cursor_coordinate.__class__(0, 2))
        print("ellipsis mode: no_wrap =", cell.no_wrap, "overflow =", cell.overflow)
        assert cell.no_wrap and cell.overflow == "ellipsis"
        await pilot.press("W"); await pilot.pause()
        cell = t.get_cell_at(t.cursor_coordinate.__class__(0, 2))
        print("wrap mode    : no_wrap =", cell.no_wrap, "overflow =", cell.overflow)
        assert not cell.no_wrap
        assert widths(app)["Note  abc"] == COLUMN_CAPS["small"], "width is unchanged"

        # uncapped never truncates, whatever the overflow setting says
        while app.appearance.column_width != "unlimited":
            await pilot.press("w"); await pilot.pause()
        cell = t.get_cell_at(t.cursor_coordinate.__class__(0, 2))
        print("uncapped     : no_wrap =", cell.no_wrap)
        assert not cell.no_wrap

        while app.appearance.column_width != "small":
            await pilot.press("w"); await pilot.pause()
        assert all(c.width <= COLUMN_CAPS["small"] for c in t.ordered_columns)
        print("saved        :", config.load())

    app2 = GridlyApp(path)
    async with app2.run_test(size=(120, 24)) as pilot:
        print("reopened     :", app2.appearance.column_width, "/", app2.appearance.overflow)
        assert (app2.appearance.column_width, app2.appearance.overflow) == ("small", "wrap")

    config.path().write_text('{"column_width": "enormous", "overflow": "nope"}')
    app3 = GridlyApp(path)
    async with app3.run_test(size=(120, 24)) as pilot:
        print("junk config  :", app3.appearance.column_width, "/", app3.appearance.overflow)
        assert app3.appearance.column_width == "fit" and app3.appearance.overflow == "ellipsis"
    print("ALL WIDTH TESTS DONE")

def test_width():
    asyncio.run(main())
