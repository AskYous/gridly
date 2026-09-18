"""Choosing which sheet to open, when the command line did not say.

A screen rather than an app of its own: two apps in one process means the
first one finishing ends a browser session, which is not what choosing a
sheet should do.
"""

from __future__ import annotations

import time
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static

from . import config
from .matching import Search

NEW_SHEET = "new"

# The name in block capitals, drawn rather than generated so it needs no font
# and no dependency. The full blocks are the letters; the light lines around
# them are the shadow, which is drawn a shade behind.
BANNER = (
    " ██████╗ ██████╗ ██╗██████╗ ██╗     ██╗   ██╗",
    "██╔════╝ ██╔══██╗██║██╔══██╗██║     ╚██╗ ██╔╝",
    "██║  ███╗██████╔╝██║██║  ██║██║      ╚████╔╝ ",
    "██║   ██║██╔══██╗██║██║  ██║██║       ╚██╔╝  ",
    "╚██████╔╝██║  ██║██║██████╔╝███████╗   ██║   ",
    " ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝ ╚══════╝   ╚═╝   ",
)

#: How wide and how tall a screen has to be before the banner is worth the
#: room. Under either, it goes: the list of sheets is what the screen is for,
#: and the banner costs it nine rows — at 28 the list still holds six sheets,
#: which is about where showing off stops being worth the space.
BANNER_ROOM = (50, 28)

#: What the list is never squeezed below while the banner is up.
LIST_FLOOR = 6


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


class PickerScreen(ModalScreen[str | None]):
    """A list of the sheets you had open lately, plus somewhere to type a path."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=False),
        # The list takes these itself when it has the focus; they only reach
        # here from the filter, where an Input leaves them alone.
        Binding("down", "step(1)", "Next", show=False),
        Binding("up", "step(-1)", "Previous", show=False),
    ]

    def __init__(self, sheets: list[Path], suggestion: str) -> None:
        super().__init__()
        self.sheets = sheets
        self.suggestion = suggestion
        #: The sheets the list is showing, which the filter narrows. What is
        #: picked is read from here rather than from `sheets`, since the two
        #: stop matching the moment anything is typed.
        self.shown: list[Path] = list(sheets)

    def compose(self) -> ComposeResult:
        with Vertical(classes="picker"):
            yield Static(id="banner")
            yield Static("a terminal spreadsheet · saved as you type", id="tagline")
            yield Label("Recent sheets", id="recent-label")
            yield Input(placeholder="filter…", id="filter", compact=True)
            yield OptionList(id="recent")
            yield Label(
                "Or type a path — a new sheet if it isn't there yet",
                classes="field-label",
            )
            yield Input(value=self.suggestion, id="path")
            yield Static(
                "[dim]type to filter · ↑↓ move · enter open · tab switch · esc clear[/]",
                classes="dialog-help",
            )

    def on_mount(self) -> None:
        self._draw_banner()
        self._narrow("")
        if self.sheets:
            # The filter takes the keys first, so a sheet can be found by
            # typing its name straight away, as the command palette is found.
            self.query_one("#filter", Input).focus()
        else:
            self.query_one("#filter", Input).display = False
            self.query_one("#path", Input).focus()

    def on_resize(self) -> None:
        self._draw_banner()

    def _draw_banner(self) -> None:
        """Put the name up, if this screen has the room to carry it."""
        wide, tall = BANNER_ROOM
        room = self.size.width >= wide and self.size.height >= tall
        banner = self.query_one("#banner", Static)
        banner.display = room
        self.query_one("#tagline", Static).display = room
        if room:
            banner.update(self._lettering())

    def _lettering(self) -> Text:
        """The banner, its letters in the theme's own colour, shadow behind."""
        face = self.app.theme_variables.get("primary", "blue")
        shadow = self.app.theme_variables.get("primary-darken-2", face)
        drawn = Text(no_wrap=True)
        for index, line in enumerate(BANNER):
            if index:
                drawn.append("\n")
            for char in line:
                drawn.append(char, face if char == "█" else shadow)
        return drawn

    # ------------------------------------------------------------- filtering

    @on(Input.Changed, "#filter")
    def filtering(self, event: Input.Changed) -> None:
        self._narrow(event.value)

    def _narrow(self, query: str) -> None:
        """Show the sheets this query finds, the best match first.

        A query need only be the letters of a name, in order — `ovt` finds
        `overtime.gridly`. See `matching`, which hands this to the command
        palette's own matcher where there is one.
        """
        query = query.strip()
        options = self.query_one("#recent", OptionList)
        options.clear_options()
        if not query:
            self.shown = list(self.sheets)
            entries = [_entry(sheet) for sheet in self.sheets]
        else:
            # Matched against the sheet's name alone, not the whole line: a
            # folder is long enough that a letter or two of a query turns up
            # somewhere in every one of them, which is no filter at all.
            search = Search(query)
            found = []
            for sheet in self.sheets:
                score = search.score(sheet.name)
                if score:
                    found.append((score, sheet, _entry(sheet)))
            found.sort(key=lambda row: -row[0])
            self.shown = [sheet for _, sheet, _ in found]
            entries = [
                self._lit(search, entry, sheet.name) for _, sheet, entry in found
            ]
        for entry in entries:
            options.add_option(entry)
        if self.shown:
            options.highlighted = 0
        self._count(query)

    def _lit(self, search: Search, entry: Text, name: str) -> Text:
        """The same line, with the letters the query found picked out.

        The name sits at the front of the line, so an offset into the name on
        its own lands on the same letter here.
        """
        lit = entry.copy()
        style = self.app.theme_variables.get("accent", "yellow")
        for place in search.marks(name):
            lit.stylize(f"bold {style}", place, place + 1)
        return lit

    def _count(self, query: str) -> None:
        """Say how much of the list is left, once it is not all of it."""
        label = self.query_one("#recent-label", Label)
        if not query:
            label.update("Recent sheets")
        elif not self.shown:
            label.update(f"Recent sheets — none match {query!r}")
        else:
            label.update(f"Recent sheets — {len(self.shown)} of {len(self.sheets)}")

    def action_step(self, by: int) -> None:
        """Move the highlight from the filter, where the arrows do nothing."""
        if self.focused is not self.query_one("#filter", Input):
            return
        options = self.query_one("#recent", OptionList)
        if options.option_count:
            here = options.highlighted or 0
            options.highlighted = max(0, min(here + by, options.option_count - 1))

    @on(Input.Submitted, "#filter")
    def open_highlighted(self) -> None:
        options = self.query_one("#recent", OptionList)
        if self.shown:
            self.dismiss(str(self.shown[options.highlighted or 0]))

    # ---------------------------------------------------------------- opening

    @on(OptionList.OptionSelected)
    def open_recent(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(self.shown[event.option_index]))

    @on(Input.Submitted, "#path")
    def open_typed(self) -> None:
        typed = self.query_one("#path", Input).value.strip()
        if typed:
            self.dismiss(typed)

    def action_cancel(self) -> None:
        """Drop the filter first, and only then give up on opening anything."""
        field = self.query_one("#filter", Input)
        if field.value:
            field.value = ""
            field.focus()
            return
        self.dismiss(None)
