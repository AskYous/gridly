"""Defining a column: its name, its type, and a dropdown's options."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from ..coltypes import OPTION_COLORS, ColumnType, assign_colors, color_style
from ..store import Column


def _swatch(color: str) -> Text:
    """A colour's name next to a block of it, for the colour dropdown."""
    return Text.assemble(("███ ", color_style(color)), (color, ""))

class OptionRow(Horizontal):
    """One dropdown option: what it is called and what colour it is shown in."""

    def __init__(self, name: str = "", color: str | None = None) -> None:
        super().__init__(classes="option-row")
        self.option_name = name
        self.option_color = color

    def compose(self) -> ComposeResult:
        yield Input(
            value=self.option_name,
            placeholder="option",
            compact=True,
            classes="option-name",
        )
        yield Select(
            [(_swatch(color), color) for color in OPTION_COLORS],
            value=(
                self.option_color
                if self.option_color in OPTION_COLORS
                else Select.NULL
            ),
            prompt="colour",
            compact=True,
            classes="option-color",
        )
        yield Button("✕", compact=True, classes="option-remove")

    @property
    def option(self) -> tuple[str, str | None]:
        name = self.query_one(".option-name", Input).value.strip()
        picked = self.query_one(".option-color", Select).value
        return name, None if picked is Select.NULL else str(picked)

class ColumnScreen(
    ModalScreen[tuple[str, ColumnType, list[str], dict[str, str]] | None]
):
    """Create or edit a column definition."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, column: Column | None = None) -> None:
        super().__init__()
        self.column = column

    def compose(self) -> ComposeResult:
        column = self.column
        # A full screen, laid out like the row form: the fields grew past what
        # a modal could hold without scrolling inside a scroll.
        with Vertical(classes="form"):
            with Vertical(classes="form-inner"):
                yield Label(
                    "Edit column" if column else "New column",
                    classes="dialog-title",
                )
                with VerticalScroll(classes="form-fields"):
                    yield Label("Name", classes="field-label")
                    yield Input(value=column.name if column else "", id="name")
                    yield Label("Type", classes="field-label")
                    yield Select(
                        [(t.label, t.value) for t in ColumnType],
                        value=(column.type if column else ColumnType.TEXT).value,
                        allow_blank=False,
                        id="type",
                    )
                    yield Label("Options", classes="field-label", id="options-label")
                    with Vertical(id="options"):
                        for option in column.options if column else []:
                            yield OptionRow(option, column.color(option))
                    yield Button("+ add option", compact=True, id="add-option")
                yield Static("", id="error", classes="error")
                yield Static(
                    "[dim]tab move · ctrl+s save · esc cancel[/]",
                    classes="dialog-help",
                )

    def on_mount(self) -> None:
        self.query_one("#name", Input).focus()
        self._sync_options_field()

    def _selected_type(self) -> ColumnType:
        return ColumnType(self.query_one("#type", Select).value)

    def _sync_options_field(self) -> None:
        is_dropdown = self._selected_type() is ColumnType.SELECT
        self.query_one("#options-label", Label).display = is_dropdown
        self.query_one("#options", Vertical).display = is_dropdown
        self.query_one("#add-option", Button).display = is_dropdown
        if is_dropdown and not self.query(OptionRow):
            self.query_one("#options", Vertical).mount(OptionRow())

    @on(Button.Pressed, "#add-option")
    async def add_option(self) -> None:
        row = OptionRow()
        # Await the mount: the row has no children to focus until it is done.
        await self.query_one("#options", Vertical).mount(row)
        row.query_one(".option-name", Input).focus()
        row.scroll_visible()

    @on(Button.Pressed, ".option-remove")
    def remove_option(self, event: Button.Pressed) -> None:
        event.stop()
        row = event.button.parent
        if isinstance(row, OptionRow):
            row.remove()

    @on(Select.Changed, "#type")
    def type_changed(self) -> None:
        self._sync_options_field()

    @on(Input.Submitted)
    def action_save(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        coltype = self._selected_type()
        options: list[str] = []
        chosen: dict[str, str] = {}
        for row in self.query(OptionRow):
            label, color = row.option
            if not label:
                continue  # a row left blank is a row you meant to drop
            options.append(label)
            if color:
                chosen[label] = color

        if not name:
            return self._error("Give the column a name")
        if coltype is ColumnType.SELECT and not options:
            return self._error("A dropdown needs at least one option")
        if len(set(o.lower() for o in options)) != len(options):
            return self._error("Options must be unique")
        self.dismiss((name, coltype, options, assign_colors(options, chosen)))

    def _error(self, message: str) -> None:
        self.query_one("#error", Static).update(f"[red]{message}[/]")

    def action_cancel(self) -> None:
        self.dismiss(None)
