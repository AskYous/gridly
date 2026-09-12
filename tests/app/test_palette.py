import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual.command import CommandPalette
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import ColumnScreen, ConfirmScreen, RowFormScreen
from gridly.store import Sheet

# --- every binding must be reachable from the palette, or explicitly elsewhere
actions = {b.action for b in GridlyApp.BINDINGS}
covered = {action for action, *_ in GridlyApp.PALETTE} | GridlyApp.PALETTE_ELSEWHERE
missing = actions - covered
extra = {a for a, *_ in GridlyApp.PALETTE} - actions
print("bindings         :", len(actions))
print("in the palette   :", len(GridlyApp.PALETTE))
print("uncovered        :", missing or "none")
print("palette-only     :", extra or "none")
assert not missing, missing
assert not extra, extra

path = pathlib.Path(tempfile.mkdtemp()) / "p.gridly"
s = Sheet(path)
name, done = s.columns()
qty = s.add_column("Qty", ColumnType.NUMBER)
r = s.rows()[0].id
s.set_cell(r, name.id, "Milk"); s.set_cell(r, done.id, True); s.set_cell(r, qty.id, 3)
s.add_row(); s.close()

async def run(app, pilot, query):
    """Open the palette, search, and hit the first result."""
    await pilot.press("ctrl+p"); await pilot.pause()
    assert isinstance(app.screen, CommandPalette), app.screen
    await pilot.press(*query)
    for _ in range(6):
        await pilot.pause()
    await pilot.press("down", "enter")
    for _ in range(6):
        await pilot.pause()

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(100, 30)) as pilot:
        t = app.query_one("#grid", DataTable)
        names = lambda: [c.name for c in app.sheet.columns()]

        # --- the commands are listed
        commands = list(app.get_system_commands(app.screen))
        titles = [c.title for c in commands]
        print("sample titles    :", [x for x in titles if "column" in x.lower()])

        # --- reordering from the palette, which is what prompted this
        print("before           :", names())
        t.cursor_coordinate = Coordinate(0, 2); await pilot.pause()
        await run(app, pilot, "Move column left")
        print("after palette    :", names())
        assert names() == ["Name", "Qty", "Done"], names()

        # --- one that opens a dialog: the palette must be out of the way first
        await run(app, pilot, "Edit column")
        print("dialog on top    :", type(app.screen).__name__)
        assert isinstance(app.screen, ColumnScreen), app.screen
        await pilot.press("escape"); await pilot.pause()

        # --- one that adds data
        rows_before = len(app.sheet.rows())
        await run(app, pilot, "Add row")
        print("rows             :", rows_before, "->", len(app.sheet.rows()))
        assert len(app.sheet.rows()) == rows_before + 1

        # --- one that changes the data, taken back with undo
        t.cursor_coordinate = Coordinate(0, 0); await pilot.pause()
        before = len(app.sheet.rows())
        await run(app, pilot, "Delete row")
        print("deleted          :", before, "->", len(app.sheet.rows()))
        assert len(app.sheet.rows()) == before - 1
        await run(app, pilot, "Undo")
        print("undone           :", len(app.sheet.rows()), "rows")
        assert len(app.sheet.rows()) == before

        # --- one that copies
        await run(app, pilot, "Copy cell")
        print("clipboard        :", repr(app._clipboard))

        # --- and the row form
        await run(app, pilot, "Edit row as a form")
        print("form             :", type(app.screen).__name__)
        assert isinstance(app.screen, RowFormScreen)
        await pilot.press("escape"); await pilot.pause()
    print("ALL PALETTE TESTS DONE")

def test_palette():
    asyncio.run(main())
