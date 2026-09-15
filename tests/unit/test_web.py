"""Working out what to serve, and saying why when it cannot."""

import errno
import sys

import pytest

from gridly import web


class FakeServer:
    """Stands in for textual-serve, remembering how it was asked to run."""

    last: "FakeServer | None" = None
    raises: Exception | None = None

    def __init__(self, command, host, port, title):
        self.command, self.host, self.port, self.title = command, host, port, title
        FakeServer.last = self

    def serve(self):
        if FakeServer.raises is not None:
            raise FakeServer.raises


@pytest.fixture(autouse=True)
def fake_server(monkeypatch):
    FakeServer.last = None
    FakeServer.raises = None
    module = type(sys)("textual_serve.server")
    module.Server = FakeServer
    monkeypatch.setitem(sys.modules, "textual_serve", type(sys)("textual_serve"))
    monkeypatch.setitem(sys.modules, "textual_serve.server", module)
    return FakeServer


def test_help_says_how_and_serves_nothing(capsys):
    assert web.main(["--help"]) == 0
    assert "usage: gridly-web" in capsys.readouterr().out
    assert FakeServer.last is None


def test_it_listens_on_this_machine_only_by_default():
    web.main([])
    assert FakeServer.last.host == "127.0.0.1"
    assert FakeServer.last.port == 8000


def test_host_and_port_can_be_given():
    web.main(["--host", "0.0.0.0", "--port", "9001"])
    assert (FakeServer.last.host, FakeServer.last.port) == ("0.0.0.0", 9001)


def test_with_no_file_the_app_is_left_to_ask(tmp_path, monkeypatch):
    """Passing a path here would rob a browser session of the picker."""
    monkeypatch.chdir(tmp_path)
    web.main([])
    assert FakeServer.last.command.endswith("-m gridly")
    assert FakeServer.last.title == "Gridly"


def test_a_named_sheet_is_resolved_before_it_is_handed_over(tmp_path, monkeypatch):
    """A session starts elsewhere, so a relative path would find the wrong file."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "budget.gridly").touch()
    web.main(["budget.gridly"])
    assert str(tmp_path.resolve() / "budget.gridly") in FakeServer.last.command
    assert FakeServer.last.title == "Gridly — budget.gridly"


def test_a_path_with_a_space_in_it_survives(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    awkward = tmp_path / "my sheets.gridly"
    awkward.touch()
    web.main([str(awkward)])
    assert "'" in FakeServer.last.command or '"' in FakeServer.last.command


def test_naming_a_sheet_that_is_not_there_says_so(tmp_path, capsys):
    web.main([str(tmp_path / "nope.gridly")])
    assert "will be created empty" in capsys.readouterr().out


def test_a_busy_port_is_one_line_not_a_traceback(capsys):
    FakeServer.raises = OSError(errno.EADDRINUSE, "address already in use")
    assert web.main(["--port", "8000"]) == 1
    printed = capsys.readouterr().out
    assert "already busy" in printed and "--port 8001" in printed


def test_any_other_failure_is_not_swallowed():
    FakeServer.raises = OSError(errno.EACCES, "permission denied")
    with pytest.raises(OSError):
        web.main([])


def test_ctrl_c_is_a_clean_way_to_stop():
    FakeServer.raises = KeyboardInterrupt()
    assert web.main([]) == 0


def test_without_textual_serve_it_says_what_to_install(monkeypatch, capsys):
    """Serving is an extra, so its absence is a sentence, not a stack trace."""
    monkeypatch.setitem(sys.modules, "textual_serve.server", None)
    assert web.main([]) == 1
    assert "pip install" in capsys.readouterr().out
