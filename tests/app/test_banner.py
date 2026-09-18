"""The name across the top of the picker, and when it stands down."""

import asyncio, pathlib, tempfile
from rich.cells import cell_len
from textual.widgets import OptionList, Static
from gridly import config
from gridly.app import GridlyApp
from gridly.picker import BANNER, BANNER_ROOM, LIST_FLOOR
from gridly.store import Sheet


def recent():
    folder = pathlib.Path(tempfile.mkdtemp())
    for name in ("overtime.gridly", "tasks.gridly"):
        sheet = Sheet(folder / name)
        sheet.close()
        config.remember(folder / name)


async def look(size):
    """What the picker's banner does at this terminal size."""
    app = GridlyApp(None)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        await pilot.pause()
        banner = app.screen.query_one("#banner", Static)
        tagline = app.screen.query_one("#tagline", Static)
        if not banner.display:
            return None
        lines = banner.content.plain.split("\n")
        # Where it actually lands on the screen, not just what it holds.
        painted = [banner.render_line(y).text for y in range(banner.region.height)]
        drawn = [line for line in painted if line.strip()]
        return {
            "lines": lines,
            "art": max(cell_len(line) for line in lines),
            "box": banner.region.width,
            "left": min(len(line) - len(line.lstrip()) for line in drawn),
            "right": banner.region.width - max(len(line.rstrip()) for line in drawn),
            "tagline": str(tagline.content),
            "tagline_shown": tagline.display,
        }


async def main():
    recent()

    # --- it is drawn whole, and sits inside its box without wrapping
    wide = await look((100, 34))
    print("at 100x34    :", wide["art"], "wide ·", len(wide["lines"]), "rows · box", wide["box"])
    assert wide["lines"] == list(BANNER), "the letters should be drawn as written"
    assert wide["art"] <= wide["box"], "it should not wrap"

    # --- and it sits down the middle, not against the left edge
    print("gaps         :", wide["left"], "left,", wide["right"], "right")
    assert wide["left"] > 0 and abs(wide["left"] - wide["right"]) <= 1, (
        "the banner should be centred"
    )
    assert wide["tagline_shown"] and "spreadsheet" in wide["tagline"]
    assert cell_len(wide["tagline"]) <= wide["box"]

    # --- the letters are the theme's colour, their shadow a shade behind
    app = GridlyApp(None)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause(); await pilot.pause()
        drawn = app.screen.query_one("#banner", Static).content
        plain = drawn.plain
        faces = {span.style for span in drawn.spans if plain[span.start] == "█"}
        edges = {span.style for span in drawn.spans if plain[span.start] in "╗═╝║╔╚"}
        print("letters      :", len(faces), "style ·", len(edges), "for the shadow")
        assert len(faces) == 1 and len(edges) == 1, "one colour each"
        assert faces != edges, "the shadow should not be the same as the letters"

    # --- just wide enough, and just too narrow
    just = await look((BANNER_ROOM[0], 34))
    print(f"at {BANNER_ROOM[0]}x34     :", just["art"], "wide · box", just["box"])
    assert just is not None and just["art"] <= just["box"]
    assert abs(just["left"] - just["right"]) <= 1, "centred at every width it shows at"
    assert cell_len(just["tagline"]) <= just["box"], "the tagline should fit too"
    assert await look((BANNER_ROOM[0] - 1, 34)) is None, "too narrow: it should go"

    # --- and a short terminal keeps the room for the list of sheets
    assert await look((100, BANNER_ROOM[1] - 1)) is None, "too short: it should go"
    print("short screen : stands down, as it should")

    # --- wherever it does show, the list is still worth reading. This is the
    #     rule the height threshold exists to keep, so it is checked rather
    #     than the number that happens to satisfy it today.
    for height in range(BANNER_ROOM[1], BANNER_ROOM[1] + 8):
        app = GridlyApp(None)
        async with app.run_test(size=(100, height)) as pilot:
            await pilot.pause(); await pilot.pause()
            rows = app.screen.query_one("#recent", OptionList).region.height
            if height == BANNER_ROOM[1]:
                print("at the floor :", rows, "rows of sheets still showing")
            assert app.screen.query_one("#banner", Static).display
            assert rows >= LIST_FLOOR, (
                f"at {height} rows the banner leaves only {rows} for the list"
            )

    # --- the picker still works with it there
    app = GridlyApp(None)
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause(); await pilot.pause()
        options = app.screen.query_one("#recent")
        assert options.option_count >= 2, "the sheets are still listed"
        await pilot.press("down", "enter"); await pilot.pause()
        print("opened       :", app.sheet.path.name)
        assert app.sheet is not None
    print("ALL BANNER TESTS DONE")


def test_banner():
    asyncio.run(main())
