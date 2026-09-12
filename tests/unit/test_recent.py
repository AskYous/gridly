"""The list of sheets offered when the command line names no file."""

import pathlib

import pytest

from gridly import config
from gridly.picker import ENTRY_WIDTH, _age, _entry, _folder
from gridly.store import Sheet


@pytest.fixture(autouse=True)
def own_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))


def make(tmp_path, name):
    path = tmp_path / name
    Sheet(path).close()
    return path.resolve()


def test_nothing_has_been_opened_yet():
    assert config.recent() == []


def test_the_newest_is_first(tmp_path):
    for name in ("a.gridly", "b.gridly", "c.gridly"):
        config.remember(make(tmp_path, name))
    assert [p.name for p in config.recent()] == ["c.gridly", "b.gridly", "a.gridly"]


def test_opening_one_again_moves_it_up_rather_than_repeating_it(tmp_path):
    first = make(tmp_path, "a.gridly")
    config.remember(first)
    config.remember(make(tmp_path, "b.gridly"))
    config.remember(first)
    assert [p.name for p in config.recent()] == ["a.gridly", "b.gridly"]


def test_a_sheet_that_has_been_deleted_drops_out(tmp_path):
    gone = make(tmp_path, "gone.gridly")
    config.remember(gone)
    config.remember(make(tmp_path, "here.gridly"))
    gone.unlink()
    assert [p.name for p in config.recent()] == ["here.gridly"]


def test_the_list_does_not_grow_forever(tmp_path):
    for n in range(config.RECENT_LIMIT + 5):
        config.remember(make(tmp_path, f"s{n}.gridly"))
    assert len(config.recent()) == config.RECENT_LIMIT


def test_a_mangled_list_is_ignored_rather_than_fatal(tmp_path):
    config.save(recent="not a list")
    assert config.recent() == []
    config.save(recent=[1, 2, None])
    assert config.recent() == []


def test_an_entry_stays_on_one_line_however_long_the_path(tmp_path):
    deep = pathlib.Path("/" + "/".join(f"folder{n}" for n in range(20)))
    line = _entry(deep / "notes.gridly").plain
    assert "\n" not in line and len(line) <= ENTRY_WIDTH + 2


def test_an_entry_leads_with_the_name(tmp_path):
    assert _entry(make(tmp_path, "budget.gridly")).plain.startswith("budget.gridly")


def test_a_folder_keeps_its_tail_since_that_is_what_tells_them_apart():
    short = _folder(pathlib.Path("/a/b/notes.gridly"), 38)
    assert short == "/a/b"
    long = _folder(pathlib.Path("/" + "x" * 80 + "/deep/notes.gridly"), 20)
    assert long.startswith("…") and long.endswith("/deep") and len(long) == 20


def test_a_missing_file_has_no_age():
    assert _age(pathlib.Path("/does/not/exist.gridly")) == ""


def test_a_file_just_written_reads_as_such(tmp_path):
    assert _age(make(tmp_path, "now.gridly")) == "just now"
