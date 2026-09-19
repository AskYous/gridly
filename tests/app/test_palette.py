import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()  # keep the real config out of it
import asyncio, pathlib, tempfile
from textual.command import CommandPalette
from rich.cells import cell_len
from textual.content import Content
from textual.coordinate import Coordinate
from textual.widgets import DataTable
from gridly.app import GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import ColumnScreen, ConfirmScreen, RowFormScreen
from gridly.store import Sheet

# --- every binding must be reachable from the palette, or explicitly elsewhere.
# The other way round is allowed: a command not worth a key of its own still
# belongs in the palette.
actions = {b.action for b in GridlyApp.BINDINGS}
listed = {action for action, *_ in GridlyApp.PALETTE}
missing = actions - listed - GridlyApp.PALETTE_ELSEWHERE
print("bindings         :", len(actions))
print("in the palette   :", len(GridlyApp.PALETTE))
print("bindings missing from the palette:", missing or "none")
print("palette-only commands            :", listed - actions or "none")
assert not missing, missing

# every palette entry has to name something the app can actually do
assert all(
    hasattr(GridlyApp, "action_" + action.split("(")[0]) for action in listed
), [a for a in listed if not hasattr(GridlyApp, "action_" + a.split("(")[0])]

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

        # --- every command says which key does the same thing, so the palette
        #     teaches its own way out
        ours = {title: c.help for title, c in zip(titles, commands)}
        keys = app.keys_by_action()
        checked = 0
        for action, title, description, _ in app.PALETTE:
            line = ours[title]
            assert description in line, (title, line)
            key = keys.get(action)
            if key is None:
                continue  # a palette-only command has no key to show
            # Checked on what is rendered, not the markup: the `[` key has to
            # be escaped there, so the markup does not read back literally.
            shown = Content.from_markup(line).plain
            assert key in shown, (title, key, shown)
            checked += 1
        print("keys shown       :", checked, "of", len(app.PALETTE), "commands")
        assert checked >= len(app.PALETTE) - 1, "only Toggle centring lacks a key"

        # --- the description sits against the left of the row and the key is
        #     pushed to the far right of it, the way a menu sets out its
        #     shortcuts. Measured on the rendered text, which is what the
        #     palette shows — the markup around the key is not on screen and
        #     must not be counted.
        edges = set()
        for action, title, description, _ in app.PALETTE:
            shown = Content.from_markup(ours[title]).plain
            assert shown.startswith(description), (title, shown)
            key = keys.get(action)
            if key is not None:
                assert shown.endswith(key), (title, key, shown)
                # Nothing but space between the two: the gap is padding.
                assert not shown[len(description) : -len(key)].strip(), shown
                edges.add(cell_len(shown))
        print("keys all end at  :", edges, f"(screen {app.size.width})")
        assert len(edges) == 1, edges

        # --- and no row is pushed wide enough to wrap onto a second line
        widest = max(cell_len(Content.from_markup(h).plain) for h in ours.values())
        print("widest row       :", widest, "of", app.size.width - 6, "usable")
        assert widest <= app.size.width - 6, (widest, app.size.width)

        # --- the key is written the way the footer writes it, not the way the
        #     binding spells it
        wrote = lambda title: Content.from_markup(ours[title]).plain.rstrip()
        assert wrote("Select one cell right").endswith("shift+→")
        assert wrote("Settings").endswith(",")
        assert wrote("Find").endswith("/")
        # A binding listing several keys shows the first, as the footer does.
        assert wrote("Move row up").endswith("{")
        # And a bracket key survives being put through markup.
        assert wrote("Move column left").endswith("["), wrote("Move column left")
        assert wrote("Move column right").endswith("]")
        print("written as       :", repr(ours["Select one cell right"]))
        print("bracket key      :", repr(wrote("Move column left")[-30:]))

        # --- a description with a bracket in it would be read as markup and
        #     swallowed, so none may have one
        loose = [t for _, t, d, _ in app.PALETTE if "[" in d or "]" in d]
        assert not loose, loose

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
    # --- the right edge follows the terminal, so the keys stay against it
    #     whatever size the window is, and still nothing wraps
    for width in (70, 80, 120, 200):
        app = GridlyApp(path)
        async with app.run_test(size=(width, 30)) as pilot:
            await pilot.pause()
            keys = app.keys_by_action()
            lines = {c.title: c.help for c in app.get_system_commands(app.screen)}
            edges = {
                cell_len(Content.from_markup(lines[title]).plain)
                for action, title, _, _ in app.PALETTE
                if keys.get(action) is not None
            }
            widest = max(
                cell_len(Content.from_markup(h).plain) for h in lines.values()
            )
            print(f"  at {width:>3} columns: keys end at {edges}, widest row {widest}")
            assert len(edges) == 1, (width, edges)
            assert widest <= width - 6, (width, widest)
            assert edges.pop() == width - 7, "right against the edge, less a column of air"
    print("ALL PALETTE TESTS DONE")

def test_palette():
    asyncio.run(main())
