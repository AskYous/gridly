import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.store import Sheet

path = pathlib.Path(tempfile.mkdtemp()) / "b.gridly"

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(90, 20)) as pilot:
        t = app.query_one("#grid", DataTable)
        done = app.sheet.columns()[1]                 # the seeded boolean column
        t.cursor_coordinate = Coordinate(0, 1); await pilot.pause()
        for label, keys in [("start", []), ("enter", ["enter"]),
                            ("backspace", ["backspace"]), ("enter", ["enter"])]:
            for k in keys: await pilot.press(k)
            await pilot.pause()
            print(f"{label:>10} -> {app.sheet.rows()[0].values.get(done.id)!r}")
    print("on-disk after quit:", Sheet(path).rows()[0].values.get(done.id))

def test_bool_clear():
    asyncio.run(main())
