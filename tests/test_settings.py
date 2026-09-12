import asyncio, pathlib, tempfile
from textual.widgets import Button, Select
from gridly.app import DEFAULT_THEME, GridlyApp
from gridly.coltypes import ColumnType
from gridly.screens import SettingsScreen
from gridly.store import Sheet
from gridly.view import View

def fresh():
    path = pathlib.Path(tempfile.mkdtemp()) / "s.gridly"
    s = Sheet(path)
    s.add_column("Note", ColumnType.TEXT)
    r = s.rows()[0].id
    s.set_cell(r, s.columns()[0].id, "Milk")
    s.close()
    return path

def pick(app, key, value):
    app.screen.query_one(f"#set-{key}", Select).value = value

async def main():
    path = fresh()
    app = GridlyApp(path)
    async with app.run_test(size=(100, 40)) as pilot:
        print("defaults     :", app.view)

        # --- every view setting is on the page
        await pilot.press("comma"); await pilot.pause()
        assert isinstance(app.screen, SettingsScreen), app.screen
        for key in ("column_width", "overflow", "row_size", "flipped"):
            assert app.screen.query_one(f"#set-{key}", Select).value == getattr(app.view, key)
        print("page shows   : column width, long values, row height, layout, theme")

        # --- changing them and saving takes effect
        pick(app, "column_width", "small")
        pick(app, "overflow", "wrap")
        pick(app, "row_size", "large")
        pick(app, "flipped", True)
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after save   :", app.view)
        assert (app.view.column_width, app.view.overflow) == ("small", "wrap")
        assert app.view.row_size == "large" and app.view.flipped is True
        assert app.screen is app.screen_stack[0]

        # --- escape leaves everything as it was
        was = View(**vars(app.view))
        await pilot.press("comma"); await pilot.pause()
        pick(app, "column_width", "unlimited")
        await pilot.pause()
        await pilot.press("escape"); await pilot.pause()
        print("after escape :", app.view)
        assert app.view == was

        # --- the theme changes as you pick it, and comes back if you cancel
        started_as = app.theme
        await pilot.press("comma"); await pilot.pause()
        other = next(t for t in sorted(app.available_themes) if t != started_as)
        app.screen.query_one("#set-theme", Select).value = other
        await pilot.pause()
        print("previewing   :", app.theme)
        assert app.theme == other, "the theme should change while you look at it"
        await pilot.press("escape"); await pilot.pause()
        print("cancelled    :", app.theme)
        assert app.theme == started_as

        # --- ...and sticks if you save
        await pilot.press("comma"); await pilot.pause()
        app.screen.query_one("#set-theme", Select).value = other
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        assert app.theme == other
        print("theme saved  :", app.theme)

        # --- reset puts everything back
        await pilot.press("comma"); await pilot.pause()
        app.screen.query_one("#reset", Button).press()
        await pilot.pause()
        await pilot.press("ctrl+s"); await pilot.pause()
        print("after reset  :", app.view, "| theme:", app.theme)
        assert app.view == View()
        assert app.theme == DEFAULT_THEME

    # --- and what was saved is there next time
    app2 = GridlyApp(path)
    async with app2.run_test(size=(100, 40)) as pilot:
        print("reopened     :", app2.view, "| theme:", app2.theme)
        assert app2.view == View() and app2.theme == DEFAULT_THEME

def test_settings():
    asyncio.run(main())
