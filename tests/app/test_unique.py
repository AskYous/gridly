import asyncio, pathlib, tempfile
from textual import events
from textual.coordinate import Coordinate
from textual.widgets import Checkbox, DataTable, Input, Select, Static, TextArea
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import ColumnScreen, RowFormScreen
from gridly.store import Sheet

def fresh(unique=True):
    path = pathlib.Path(tempfile.mkdtemp()) / "u.gridly"
    s = Sheet(path)
    for seeded in s.columns():
        s.delete_column(seeded.id)
    ident = s.add_column("Id", ColumnType.TEXT, unique=unique)
    note = s.add_column("Note", ColumnType.TEXT)
    for i, (a, b) in enumerate([("A1", "first"), ("A2", "second")]):
        rid = s.rows()[0].id if i == 0 else s.add_row()
        s.set_cell(rid, ident.id, a); s.set_cell(rid, note.id, b)
    s.close()
    return path

def data(app):
    cols = app.sheet.columns()
    return [[r.values.get(c.id) for c in cols] for r in app.sheet.rows()]

async def main():
    app = GridlyApp(fresh())
    async with app.run_test(size=(100, 30)) as pilot:
        t = app.query_one("#grid", DataTable)

        # --- typing a value another row already has is refused
        t.cursor_coordinate = Coordinate(1, 0); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", TextArea).text = "A1"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after clash  :", data(app))
        assert data(app)[1][0] == "A2", "the clash should not have been written"

        # --- the same value in its own row is fine
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", TextArea).text = "A2"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert data(app)[1][0] == "A2"
        print("own value ok : yes")

        # --- and a value nobody has is fine
        await pilot.press("enter"); await pilot.pause()
        app.screen.query_one("#value", TextArea).text = "A3"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert data(app)[1][0] == "A3"

        # --- empty cells never clash with each other
        await pilot.press("backspace"); await pilot.pause()
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("backspace"); await pilot.pause()
        print("two empties  :", data(app))
        assert data(app)[0][0] is None and data(app)[1][0] is None
        await pilot.press("u"); await pilot.press("u"); await pilot.pause()

        # --- the row form refuses inline rather than losing the edits
        t.cursor_coordinate = Coordinate(1, 0); await pilot.pause()
        await pilot.press("f"); await pilot.pause()
        cols = app.sheet.columns()
        app.screen.query_one(f"#field-{cols[0].id}", TextArea).text = "A1"
        app.screen.query_one(f"#field-{cols[1].id}", TextArea).text = "kept"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert isinstance(app.screen, RowFormScreen), "the form should stay open"
        print("form says    :", app.screen.query_one("#error", Static).content)
        assert app.screen.query_one(f"#field-{cols[1].id}", TextArea).text == "kept"
        app.screen.query_one(f"#field-{cols[0].id}", TextArea).text = "A9"
        await pilot.press("ctrl+s"); await pilot.pause()
        print("form saved   :", data(app)[1])
        assert data(app)[1] == ["A9", "kept"]

        # --- duplicating leaves the unique column empty
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("D"); await pilot.pause()
        print("duplicated   :", data(app))
        assert data(app)[1] == [None, "first"], data(app)

        # --- pasting a row's own value back is not a clash; a repeat is dropped
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        app.post_message(events.Paste("A1\tfrom paste\nA1\talso new\n"))
        await pilot.pause(); await pilot.pause()
        print("after paste  :", data(app))
        assert data(app)[0] == ["A1", "from paste"], "a row's own value is fine"
        assert data(app)[1][0] is None, "the second A1 should have been dropped"
        assert data(app)[1][1] == "also new", "the rest of the row still lands"

        # --- a block that repeats itself is caught too
        app2 = GridlyApp(fresh())
        async with app2.run_test(size=(100, 30)) as pilot2:
            app2.query_one("#grid", DataTable).cursor_coordinate = Coordinate(0, 0)
            await pilot2.pause()
            app2.post_message(events.Paste("Z1\tone\nZ1\ttwo\n"))
            await pilot2.pause(); await pilot2.pause()
            print("self-repeat  :", data(app2))
            # the first Z1 lands; the second is dropped, leaving what was there
            assert data(app2)[0] == ["Z1", "one"]
            assert data(app2)[1] == ["A2", "two"]

    # --- turning the rule on when the column already repeats is refused
    app3 = GridlyApp(fresh(unique=False))
    async with app3.run_test(size=(100, 30)) as pilot:
        t = app3.query_one("#grid", DataTable)
        ident = app3.sheet.columns()[0]
        app3.sheet.set_cell(app3.sheet.rows()[1].id, ident.id, "A1")
        app3.reload(); await pilot.pause()
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        app3.screen.query_one("#unique", Checkbox).value = True
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("refused      :", app3.sheet.columns()[0].unique)
        assert app3.sheet.columns()[0].unique is False

        # --- once the repeat is gone it can be turned on
        app3.sheet.set_cell(app3.sheet.rows()[1].id, ident.id, "A2")
        app3.reload(); await pilot.pause()
        await pilot.press("e"); await pilot.pause()
        app3.screen.query_one("#unique", Checkbox).value = True
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("now unique   :", app3.sheet.columns()[0].unique)
        assert app3.sheet.columns()[0].unique is True
    print("ALL UNIQUE TESTS DONE")

def test_unique():
    asyncio.run(main())
