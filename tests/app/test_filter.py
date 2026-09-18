"""Finding a sheet by typing at the picker."""

import asyncio, pathlib, tempfile
from textual.widgets import Input, Label, OptionList
from gridly import config
from gridly.app import GridlyApp
from gridly.store import Sheet

SHEETS = [
    "overtime.gridly",
    "tasks.gridly",
    "users.gridly",
    "logins.gridly",
    "mystc4-ebu-screens.gridly",
]


def recent(names=SHEETS):
    """A folder of sheets, and a config that remembers only those."""
    folder = pathlib.Path(tempfile.mkdtemp())
    config.save(recent=[])
    for name in names:
        sheet = Sheet(folder / name)
        sheet.close()
        config.remember(folder / name)
    return folder


def listed(app):
    return [path.name for path in app.screen.shown]


def label(app):
    return str(app.screen.query_one("#recent-label", Label).content)


async def type_in(app, pilot, query):
    app.screen.query_one("#filter", Input).value = query
    await pilot.pause()


async def main():
    recent()
    app = GridlyApp(None)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause(); await pilot.pause()
        screen = app.screen

        # --- the filter takes the keys, so you can just start typing
        print("focused      :", screen.focused.id)
        assert screen.focused.id == "filter"
        assert screen.query_one("#recent", OptionList).option_count == len(SHEETS)

        # --- the letters of a name, in order, are enough to find it
        await type_in(app, pilot, "ovt")
        print("  'ovt'      ->", listed(app))
        assert listed(app) == ["overtime.gridly"]

        await type_in(app, pilot, "screens")
        print("  'screens'  ->", listed(app))
        assert listed(app) == ["mystc4-ebu-screens.gridly"]

        # --- it is the name that is matched, not the folder the sheet sits in
        await type_in(app, pilot, "tmp")
        print("  'tmp'      ->", listed(app), "(the folder is a temp dir)")
        assert listed(app) == [], "a folder should not drag every sheet in"

        # --- and the closest match comes first
        await type_in(app, pilot, "us")
        print("  'us'       ->", listed(app))
        assert listed(app)[0] == "users.gridly"

        # --- the label counts what is left, and says when nothing is
        print("count        :", label(app))
        assert "2 of 5" in label(app)
        await type_in(app, pilot, "zzz")
        print("no matches   :", label(app))
        assert "none match" in label(app) and listed(app) == []
        await type_in(app, pilot, "")
        assert label(app) == "Recent sheets" and len(listed(app)) == len(SHEETS)

        # --- the letters that matched are picked out in the row
        await type_in(app, pilot, "ovt")
        row = screen.query_one("#recent", OptionList).get_option_at_index(0).prompt
        # The name carries one bold span of its own; the matched letters are
        # marked one at a time on top of it.
        lit = "".join(row.plain[s.start : s.end] for s in row.spans if s.end - s.start == 1)
        print("highlighted  :", repr(lit), "in", repr(row.plain[:15]))
        assert lit == "ovt", "the letters the query found should be the ones lit"

        # --- arrows work from the filter, where an Input would ignore them
        await type_in(app, pilot, "s")
        options = screen.query_one("#recent", OptionList)
        assert options.highlighted == 0
        await pilot.press("down"); await pilot.pause()
        print("after down   :", options.highlighted, listed(app)[options.highlighted])
        assert options.highlighted == 1
        await pilot.press("up", "up"); await pilot.pause()
        assert options.highlighted == 0, "and it stops at the top"

        # --- escape drops the filter before it gives up on the screen
        await pilot.press("escape"); await pilot.pause()
        print("after escape :", repr(screen.query_one("#filter", Input).value))
        assert screen.query_one("#filter", Input).value == ""
        assert app.sheet is None, "the picker should still be up"

        # --- enter opens what is highlighted, and only that
        await type_in(app, pilot, "log")
        screen.query_one("#filter", Input).focus()
        await pilot.press("enter"); await pilot.pause()
        print("opened       :", app.sheet.path.name)
        assert app.sheet.path.name == "logins.gridly"

    # --- picking from a filtered list opens the row you picked, not the
    #     one that used to sit at that place in the full list
    recent()
    app = GridlyApp(None)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause(); await pilot.pause()
        await type_in(app, pilot, "us")
        options = app.screen.query_one("#recent", OptionList)
        options.focus()
        await pilot.press("down", "enter"); await pilot.pause()
        print("second row   :", app.sheet.path.name)
        assert app.sheet.path.name == "mystc4-ebu-screens.gridly"

    # --- the path box still opens what is typed into it
    folder = recent()
    app = GridlyApp(None)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause(); await pilot.pause()
        field = app.screen.query_one("#path", Input)
        field.focus()
        field.value = str(folder / "brand-new.gridly")
        await pilot.press("enter"); await pilot.pause()
        print("typed path   :", app.sheet.path.name)
        assert app.sheet.path.name == "brand-new.gridly"

    # --- with nothing to filter, the box stays out of the way
    config.save(recent=[])
    app = GridlyApp(None)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause(); await pilot.pause()
        shown = app.screen.query_one("#filter", Input).display
        print("no sheets    : filter shown:", shown, "| focus:", app.screen.focused.id)
        assert not shown and app.screen.focused.id == "path"
    print("ALL FILTER TESTS DONE")


def test_filter():
    asyncio.run(main())
