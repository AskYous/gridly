import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.screens import RowFormScreen, HelpScreen

path = pathlib.Path(tempfile.mkdtemp()) / "m.gridly"

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 28)) as pilot:
        t = app.query_one("#grid", DataTable)
        before = len(t.rows)
        app.sheet.set_cell(app.current_row().id, app.sheet.columns()[0].id, "keepme")
        app.reload()
        await pilot.press("f"); await pilot.pause()
        assert isinstance(app.screen, RowFormScreen)
        await pilot.press("a", "c", "x"); await pilot.pause()
        print("row form still up:", isinstance(app.screen, RowFormScreen),
              "| rows unchanged:", len(t.rows) == before,
              "| cols unchanged:", len(t.columns) == 2)
        await pilot.press("escape"); await pilot.pause()

        await pilot.press("question_mark"); await pilot.pause()
        await pilot.press("a", "c"); await pilot.pause()
        print("help still up:", isinstance(app.screen, HelpScreen),
              "| rows unchanged:", len(t.rows) == before,
              "| cols unchanged:", len(t.columns) == 2)
        await pilot.press("escape"); await pilot.pause()
        print("back on grid:", app.screen is app.screen_stack[0])
def test_modal_block():
    asyncio.run(main())
