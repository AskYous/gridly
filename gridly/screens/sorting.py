"""Choosing how the rows are sorted: a column, then another for ties."""

from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Static

from ..sorting import DIRECTIONS, MAX_LEVELS, Level
from ..store import Column

#: What each level is headed, most important first.
HEADINGS = ("Sort by", "then by", "then by")


class SortScreen(ModalScreen[list[Level] | None]):
    """A column to sort by, and up to two more to break ties.

    A level only appears once the one before it has a column, so the form is
    as long as the sort and no longer. Nothing chosen at all turns sorting off.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, columns: list[Column], levels: list[Level], here: Column | None):
        super().__init__()
        self.columns = columns
        self.found = {column.id: column for column in columns}
        # With no sort yet, the column the cursor is in is the likely one.
        if not levels and here is not None:
            levels = [Level(here.id)]
        self.levels = levels

    def compose(self) -> ComposeResult:
        with Vertical(classes="form"):
            with Vertical(classes="form-inner"):
                yield Label("Sort", classes="dialog-title")
                with VerticalScroll(classes="form-fields"):
                    yield Static(
                        "[dim]Only changes how the rows are shown — turn it off "
                        "and they are back as they were. A row you add or change "
                        "stays where it is, marked ↕, until you press r.[/]",
                        classes="setting-about",
                    )
                    for index in range(MAX_LEVELS):
                        level = self.levels[index] if index < len(self.levels) else None
                        yield Label(
                            HEADINGS[index], classes="field-label", id=f"heading-{index}"
                        )
                        yield Select(
                            [(column.name, column.id) for column in self.columns],
                            value=level.column_id if level else Select.NULL,
                            prompt="nothing",
                            id=f"column-{index}",
                        )
                        yield Select(
                            self._directions(level.column_id if level else None),
                            value=level.descending if level else False,
                            allow_blank=False,
                            id=f"direction-{index}",
                        )
                    yield Button("Turn sorting off", compact=True, id="off")
                yield Static(
                    "[dim]tab move · ctrl+s sort · esc cancel[/]",
                    classes="dialog-help",
                )

    def on_mount(self) -> None:
        self._sync()

    def _directions(self, column_id: int | None) -> list[tuple[str, bool]]:
        column = self.found.get(column_id) if column_id is not None else None
        up, down = DIRECTIONS[column.type] if column else ("ascending", "descending")
        return [(up, False), (down, True)]

    def _chosen(self, index: int) -> int | None:
        value = self.query_one(f"#column-{index}", Select).value
        return value if isinstance(value, int) else None

    def _sync(self) -> None:
        """Show each level only once the one above it has a column."""
        shown = True
        for index in range(MAX_LEVELS):
            chosen = self._chosen(index)
            for part in ("heading", "column"):
                self.query_one(f"#{part}-{index}").display = shown
            self.query_one(f"#direction-{index}").display = shown and chosen is not None
            shown = shown and chosen is not None

    @on(Select.Changed)
    def changed(self, event: Select.Changed) -> None:
        name = event.select.id or ""
        if name.startswith("column-"):
            # The words for each way round depend on the column's type.
            direction = self.query_one(f"#direction-{name[7:]}", Select)
            kept = direction.value
            direction.set_options(self._directions(self._chosen(int(name[7:]))))
            direction.value = kept
        self._sync()

    @on(Button.Pressed, "#off")
    def off(self) -> None:
        self.dismiss([])

    def action_save(self) -> None:
        levels: list[Level] = []
        for index in range(MAX_LEVELS):
            chosen = self._chosen(index)
            if chosen is None:
                break  # a gap ends the sort, the same as the form hides past it
            if any(level.column_id == chosen for level in levels):
                continue  # a second time by the same column changes nothing
            descending = self.query_one(f"#direction-{index}", Select).value is True
            levels.append(Level(chosen, descending))
        self.dismiss(levels)

    def action_cancel(self) -> None:
        self.dismiss(None)
