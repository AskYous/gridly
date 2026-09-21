import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Select
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import CommentBox, CommentView, RowFormScreen
from gridly.store import Sheet

path = pathlib.Path(tempfile.mkdtemp()) / "c.gridly"
s = Sheet(path)
for seeded in s.columns():
    s.delete_column(seeded.id)
task = s.add_column("Task", ColumnType.TEXT)
status = s.add_column("Status", ColumnType.SELECT, ["New", "Doing", "Done"])
r1 = s.rows()[0].id
s.set_cell(r1, task.id, "Fix login")
for n in range(2, 11):          # ten rows, so the numbers run to two digits
    s.set_cell(s.add_row(), task.id, f"Task {n}")
s.close()

def log(app, row=0):
    return [c.body for c in app.sheet.comments(app.sheet.rows()[row].id)]

def label(app, row):
    t = app.query_one("#grid", DataTable)
    return t.rows[t.ordered_rows[row].key].label.plain

def views(app):
    return list(app.screen.query(CommentView))

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 40)) as pilot:
        t = app.query_one("#grid", DataTable)

        # --- a row with nothing said about it shows only its number
        print("label before   :", repr(label(app, 0)))
        assert label(app, 0) == "1"

        # --- C opens the row with the cursor in a new comment
        await pilot.press("C"); await pilot.pause()
        assert isinstance(app.screen, RowFormScreen), app.screen
        form = app.screen
        assert app.focused.id == "new-comment", app.focused

        # --- ctrl+s there posts it and stays, ready for another
        await pilot.press(*"Repro'd on staging")
        await pilot.press("ctrl+s"); await pilot.pause()
        assert app.screen is form, "posting a comment keeps the form open"
        print("log            :", log(app))
        assert log(app) == ["Repro'd on staging"], "written straight away"
        box = form.query_one("#new-comment", CommentBox)
        assert box.text == "" and app.focused is box
        assert [v.comment.body for v in views(app)] == ["Repro'd on staging"]
        print("heading        :", form.query_one("#comments-heading").content)
        assert "1 ·" in str(form.query_one("#comments-heading").content)

        # --- a second one lands above the first
        await pilot.press(*"Called the vendor")
        await pilot.press("ctrl+s"); await pilot.pause()
        assert [v.comment.body for v in views(app)] == log(app) == [
            "Called the vendor", "Repro'd on staging",
        ]

        # --- ctrl+s on an empty box posts nothing
        await pilot.press("ctrl+s"); await pilot.pause()
        assert app.screen is form and len(log(app)) == 2

        # --- esc leaves, and what was posted stays posted
        await pilot.press("escape"); await pilot.pause()
        assert app.screen is app.screen_stack[0]
        print("label after    :", repr(label(app, 0)))
        assert label(app, 0) == "≡2  1", "the number against the right, as row 10's is"
        assert label(app, 9) == "   10", "no count, but its number where the rest are"

        # --- saving the row takes what is still in the box with it, as one change
        await pilot.press("f"); await pilot.pause()
        assert app.focused.id == f"field-{task.id}", "f still starts on the fields"
        app.screen.query_one(f"#field-{status.id}", Select).value = "Doing"
        app.screen.query_one("#new-comment", CommentBox).text = "Moved to Doing"
        await pilot.press("ctrl+s"); await pilot.pause()
        assert app.screen is app.screen_stack[0], "saving the row still closes"
        row = app.sheet.rows()[0]
        print("with a field   :", row.values.get(status.id), log(app))
        assert row.values.get(status.id) == "Doing"
        assert log(app)[0] == "Moved to Doing"
        await pilot.press("u"); await pilot.pause()
        row = app.sheet.rows()[0]
        print("after undo     :", row.values.get(status.id), log(app))
        assert row.values.get(status.id) is None and len(log(app)) == 2
        await pilot.press("U"); await pilot.pause()
        assert log(app) == ["Moved to Doing", "Called the vendor", "Repro'd on staging"]

        # --- backspace on a comment removes it there and then
        await pilot.press("f"); await pilot.pause()
        form = app.screen
        views(app)[1].focus(); await pilot.pause()
        gone = views(app)[1].comment
        await pilot.press("backspace"); await pilot.pause()
        assert views(app)[1].removed
        print("removed        :", log(app))
        assert log(app) == ["Moved to Doing", "Repro'd on staging"]
        assert "2 ·" in str(form.query_one("#comments-heading").content)

        # --- and again puts it back, as it was
        await pilot.press("backspace"); await pilot.pause()
        assert not views(app)[1].removed
        assert app.sheet.comments(row.id)[1] == gone

        # --- enter opens one; esc there keeps the wording and not the form
        views(app)[0].focus(); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        editor = views(app)[0].editor
        assert editor is not None and app.focused is editor
        assert editor.text == "Moved to Doing"
        await pilot.press(*" THROWN AWAY")
        await pilot.press("escape"); await pilot.pause()
        assert app.screen is form, "esc in a comment only closes the comment"
        assert views(app)[0].editor is None and app.focused is views(app)[0]
        assert log(app)[0] == "Moved to Doing"

        # --- ctrl+s there rewords it straight away, and stays
        await pilot.press("enter"); await pilot.pause()
        await pilot.press(*" after standup")
        await pilot.press("ctrl+s"); await pilot.pause()
        assert app.screen is form
        latest = app.sheet.comments(row.id)[0]
        print("reworded       :", latest.body, "| edited:", bool(latest.edited))
        assert latest.body == "Moved to Doing after standup" and latest.edited
        heading = views(app)[0].query_one(".comment-when").content
        assert "edited" in str(heading), heading
        assert app.focused is views(app)[0]

        # --- emptied out and posted, it goes
        views(app)[2].focus(); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        views(app)[2].editor.text = ""
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after emptying :", log(app))
        assert log(app) == ["Moved to Doing after standup", "Called the vendor"]
        assert views(app)[2].removed

        # --- esc on a comment that is not open closes the form
        await pilot.press("escape"); await pilot.pause()
        assert app.screen is app.screen_stack[0]
        assert label(app, 0) == "≡2  1"

        # --- a comment left open when the row is saved is saved with it
        await pilot.press("f"); await pilot.pause()
        views(app)[1].focus(); await pilot.pause()
        await pilot.press("enter"); await pilot.pause()
        await pilot.press(*" twice")
        app.screen.query_one(f"#field-{task.id}").focus(); await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        assert app.screen is app.screen_stack[0]
        print("left open      :", log(app))
        assert log(app) == ["Moved to Doing after standup", "Called the vendor twice"]

        # --- another row keeps a log of its own
        t.cursor_coordinate = Coordinate(9, 0); await pilot.pause()
        await pilot.press("C"); await pilot.pause()
        print("row 10 heading :", app.screen.query_one("#comments-heading").content)
        await pilot.press(*"Only here")
        await pilot.press("ctrl+s", "escape"); await pilot.pause()
        assert log(app, 9) == ["Only here"] and len(log(app, 0)) == 2
        assert label(app, 9) == "≡1 10"

    reopened = Sheet(path)
    print("on disk        :", [c.body for c in reopened.comments(reopened.rows()[9].id)])
    assert [c.body for c in reopened.comments(reopened.rows()[9].id)] == ["Only here"]
    reopened.close()
    print("ALL COMMENT TESTS DONE")

def test_comments():
    asyncio.run(main())
