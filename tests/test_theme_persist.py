import os, tempfile, pathlib, asyncio
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp()   # leave the real config alone
from gridly import config
from gridly.app import DEFAULT_THEME, GridlyApp

path = pathlib.Path(tempfile.mkdtemp()) / "t.gridly"

async def main():
    app = GridlyApp(path)
    async with app.run_test(size=(90, 24)) as pilot:
        print("starts at :", app.theme, "| config:", config.load())
        assert "theme" not in config.load(), "no theme saved until one is picked"
        app.theme = "gruvbox"          # what the command palette does on select
        await pilot.pause()
        print("after pick:", app.theme, "| theme in config:", config.load().get("theme"))

    app2 = GridlyApp(path)
    async with app2.run_test(size=(90, 24)) as pilot:
        print("relaunch  :", app2.theme)
        assert app2.theme == "gruvbox"
        app2.theme = "nord"            # changing again overwrites
        await pilot.pause()

    app3 = GridlyApp(path)
    async with app3.run_test(size=(90, 24)) as pilot:
        print("relaunch  :", app3.theme)
        assert app3.theme == "nord"

    config.CONFIG_PATH.write_text('{"theme": "no-such-theme"}')
    app4 = GridlyApp(path)
    async with app4.run_test(size=(90, 24)) as pilot:
        print("unknown   :", app4.theme)
        assert app4.theme == DEFAULT_THEME

    config.CONFIG_PATH.write_text("not json{{")
    app5 = GridlyApp(path)
    async with app5.run_test(size=(90, 24)) as pilot:
        print("corrupt   :", app5.theme)
        assert app5.theme == DEFAULT_THEME

    config.CONFIG_PATH.parent.chmod(0o500)   # unwritable config dir must not crash
    try:
        app6 = GridlyApp(path)
        async with app6.run_test(size=(90, 24)) as pilot:
            app6.theme = "dracula"
            await pilot.pause()
            print("read-only :", app6.theme, "(no crash)")
    finally:
        config.CONFIG_PATH.parent.chmod(0o700)
    print("ALL THEME PERSISTENCE TESTS DONE")

def test_theme_persist():
    asyncio.run(main())
