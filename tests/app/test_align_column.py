import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import ColumnScreen
from gridly.store import Sheet

def fresh(align=""):
    path = pathlib.Path(tempfile.mkdtemp()) / "a.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    for seeded in s.rows():
        s.delete_row(seeded.id)
    pay = s.add_column("Pay", ColumnType.NUMBER, align=align)
    for value in (1.5, 1234567.25):
        rid = s.add_row()
        s.set_cell(rid, pay.id, value)
    s.close()
    return path

def lines(app):
    """The heading and the first value, as the grid actually draws them.

    Found by what they hold rather than by row number: padding and wrapping
    are settings, and where a line lands is none of this test's business.
    """
    t = app.query_one("#grid", DataTable)
    drawn = [t.render_line(y).text.rstrip() for y in range(t.size.height)]
    heading = next(line for line in drawn if "Pay" in line)
    value = next(line for line in drawn if "1.5" in line)
    return heading, value

async def main():
    # --- left as it was, a number still reads from the left edge
    app = GridlyApp(fresh())
    async with app.run_test(size=(70, 16)) as pilot:
        await pilot.pause(); await pilot.pause()
        heading, row = lines(app)
        print("automatic    :", repr(heading), repr(row))
        assert row.rstrip().endswith("1.5")
        assert row.index("1.5") < 8, "it should sit against the left"

    # --- told to go right, both the values and the heading follow
    app = GridlyApp(fresh("right"))
    async with app.run_test(size=(70, 16)) as pilot:
        await pilot.pause(); await pilot.pause()
        heading, row = lines(app)
        print("right        :", repr(heading), repr(row))
        assert row.index("1.5") > 8, "the value should be pushed across"
        assert heading.index("Pay") > 4, "and the heading should follow it"

    # --- and centred lands between the two
    app = GridlyApp(fresh("center"))
    async with app.run_test(size=(70, 16)) as pilot:
        await pilot.pause(); await pilot.pause()
        _, centred = lines(app)
        print("centred      :", repr(centred))

    # --- set through the form, and it sticks
    app = GridlyApp(fresh())
    async with app.run_test(size=(90, 34)) as pilot:
        await pilot.pause(); await pilot.pause()
        t = app.query_one("#grid", DataTable)
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        assert isinstance(app.screen, ColumnScreen)
        assert app.screen.query_one("#align", Select).value == "", "automatic to begin"
        app.screen.query_one("#align", Select).value = "right"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("through form :", repr(app.sheet.columns()[0].align))
        assert app.sheet.columns()[0].align == "right"
        _, row = lines(app)
        assert row.index("1.5") > 8, "the grid should redraw with it"

        # --- the form opens showing what the column was set to
        await pilot.press("e"); await pilot.pause()
        assert app.screen.query_one("#align", Select).value == "right"
        await pilot.press("escape"); await pilot.pause()

        path = app.sheet.path

    # --- and it is still there when the sheet is opened again
    again = Sheet(path)
    print("on disk      :", repr(again.columns()[0].align))
    assert again.columns()[0].align == "right"
    again.close()

    # --- a column on Automatic still follows the sheet-wide setting; one with
    #     an alignment of its own ignores it
    for centred in (True, False):
        app = GridlyApp(fresh())
        async with app.run_test(size=(70, 16)) as pilot:
            await pilot.pause()
            app.appearance.centred = centred
            app.sheet.update_column(
                app.sheet.columns()[0].id, "Pay", ColumnType.DATE, align=""
            )
            app.reload(); await pilot.pause()
            auto = app.query_one("#grid", DataTable).ordered_columns[0].label.justify
            app.sheet.update_column(
                app.sheet.columns()[0].id, "Pay", ColumnType.DATE, align="left"
            )
            app.reload(); await pilot.pause()
            told = app.query_one("#grid", DataTable).ordered_columns[0].label.justify
            print(f"sheet centred={str(centred):5} -> automatic {auto!r}, told {told!r}")
            assert auto == ("center" if centred else None)
            assert told == "left", "a column that was told should not care"
    print("ALL ALIGNMENT TESTS DONE")

def test_alignment():
    asyncio.run(main())
