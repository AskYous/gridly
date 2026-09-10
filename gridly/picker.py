"""Choosing which sheet to open, when the command line did not say."""

from __future__ import annotations

import time
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Input, Label, OptionList, Static

from . import config

NEW_SHEET = "new"


def _age(path: Path) -> str:
    """How long ago the sheet was last written, in round numbers."""
    try:
        seconds = time.time() - path.stat().st_mtime
    except OSError:
        return ""
    for length, name in ((86400, "day"), (3600, "hour"), (60, "minute")):
        if seconds >= length:
            count = int(seconds // length)
            return f"{count} {name}{'s' if count != 1 else ''} ago"
    return "just now"


def _folder(path: Path, limit: int = 38) -> str:
    """The sheet's folder, short enough to sit on one line beside its name."""
    try:
        text = "~/" + str(path.parent.relative_to(Path.home()))
    except ValueError:
        text = str(path.parent)
    return text if len(text) <= limit else "…" + text[-(limit - 1) :]


# The list is this wide inside its border and padding; entries are trimmed to
# it so each sheet keeps to a single row however long its path is.
ENTRY_WIDTH = 62


def _entry(sheet: Path) -> Text:
    """One sheet on one line: what it is called, when it was last touched, where."""
    age = _age(sheet)
    when = f"  ·  {age}" if age else ""
    room = ENTRY_WIDTH - len(sheet.name) - len(when) - 2
    folder = _folder(sheet, room) if room >= 10 else ""
    return Text.assemble(
        (sheet.name, "bold"),
        (when, "dim"),
        (f"  {folder}" if folder else "", "dim"),
    )


class PickerApp(App[str | None]):
    """A list of the sheets you had open lately, plus somewhere to type a path."""

    CSS_PATH = "app.tcss"
    TITLE = "Gridly"
    SUB_TITLE = "open a sheet"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        Binding("ctrl+c", "cancel", "Cancel", show=False),
    ]

    def __init__(self, sheets: list[Path], suggestion: str) -> None:
        super().__init__()
        self.sheets = sheets
        self.suggestion = suggestion

    def compose(self) -> ComposeResult:
        with Vertical(classes="picker"):
            yield Label("Recent sheets")
            options = OptionList(id="recent")
            yield options
            yield Label("Or type a path — a new sheet if it isn't there yet", classes="field-label")
            yield Input(value=self.suggestion, id="path")
            yield Static(
                "[dim]enter open · tab switch · esc quit[/]", classes="dialog-help"
            )

    def on_mount(self) -> None:
        options = self.query_one("#recent", OptionList)
        for sheet in self.sheets:
            options.add_option(_entry(sheet))
        if self.sheets:
            options.highlighted = 0
            options.focus()
        else:
            self.query_one("#path", Input).focus()

    @on(OptionList.OptionSelected)
    def open_recent(self, event: OptionList.OptionSelected) -> None:
        self.exit(str(self.sheets[event.option_index]))

    @on(Input.Submitted)
    def open_typed(self) -> None:
        typed = self.query_one("#path", Input).value.strip()
        if typed:
            self.exit(typed)

    def action_cancel(self) -> None:
        self.exit(None)


def choose_sheet(suggestion: str) -> str | None:
    """Ask which sheet to open. None means the user changed their mind."""
    return PickerApp(config.recent(), suggestion).run(inline=False)
