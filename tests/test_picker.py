import os as _os, tempfile as _tf; _os.environ["XDG_CONFIG_HOME"] = _tf.mkdtemp()
import asyncio, pathlib, tempfile
from textual.widgets import Input, OptionList
from gridly import config
from gridly.picker import PickerApp, _entry, _folder
from gridly.store import Sheet

home = pathlib.Path(tempfile.mkdtemp())
made = []
for name in ("alpha", "beta", "gamma"):
    p = home / f"{name}.gridly"
    Sheet(p).close()
    made.append(p.resolve())

# --- the recent list itself
print("empty at first :", config.recent())
for p in made:
    config.remember(p)
print("newest first   :", [p.name for p in config.recent()])
assert [p.name for p in config.recent()] == ["gamma.gridly", "beta.gridly", "alpha.gridly"]

config.remember(made[2])                      # touching one moves it up, no duplicate
print("after re-open  :", [p.name for p in config.recent()])
assert [p.name for p in config.recent()] == ["gamma.gridly", "beta.gridly", "alpha.gridly"]
config.remember(made[0])
assert [p.name for p in config.recent()][0] == "alpha.gridly"

made[1].unlink()                              # a sheet that has gone is skipped
print("after deleting :", [p.name for p in config.recent()])
assert "beta.gridly" not in [p.name for p in config.recent()]

for i in range(20):                           # the list is capped
    extra = home / f"extra{i}.gridly"
    Sheet(extra).close()
    config.remember(extra)
print("capped at      :", len(config.recent()), "of", config.RECENT_LIMIT)
assert len(config.recent()) == config.RECENT_LIMIT

# --- long paths stay on one line
deep = pathlib.Path("/a/very/long/directory/name/that/keeps/going/and/going/onwards")
line = _entry(deep / "notes.gridly")
print("entry          :", repr(line.plain))
assert len(line.plain) <= 64 and "\n" not in line.plain

async def main():
    sheets = config.recent()

    # --- enter on the list opens that sheet
    app = PickerApp(sheets, "fallback.gridly")
    async with app.run_test(size=(90, 20)) as pilot:
        options = app.query_one("#recent", OptionList)
        print("listed         :", options.option_count, "sheets | focus:", type(app.focused).__name__)
        assert options.option_count == len(sheets)
        await pilot.press("down", "enter"); await pilot.pause()
    print("chose          :", pathlib.Path(app.return_value).name)
    assert app.return_value == str(sheets[1])

    # --- a typed path wins over the list
    app = PickerApp(sheets, "fallback.gridly")
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.press("tab"); await pilot.pause()
        app.query_one("#path", Input).value = "/tmp/typed.gridly"
        await pilot.press("enter"); await pilot.pause()
    print("typed          :", app.return_value)
    assert app.return_value == "/tmp/typed.gridly"

    # --- escape means "never mind"
    app = PickerApp(sheets, "fallback.gridly")
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.press("escape"); await pilot.pause()
    print("escaped        :", app.return_value)
    assert app.return_value is None

    # --- with nothing recent, the typing field takes focus
    app = PickerApp([], "fallback.gridly")
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        print("no recents     : focus is", type(app.focused).__name__)
        assert isinstance(app.focused, Input)
        await pilot.press("enter"); await pilot.pause()
    assert app.return_value == "fallback.gridly"
    print("ALL PICKER TESTS DONE")

def test_picker():
    asyncio.run(main())
