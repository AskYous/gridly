"""Modal dialogs: editing a cell, defining a column, confirming a deletion."""

from __future__ import annotations

from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static

from .coltypes import ColumnType, ValidationError, display, parse
from .store import Column

CLEAR_OPTION = "— clear —"


class CellEditScreen(ModalScreen[tuple[bool, Any]]):
    """Free-text editor for text, number and date cells."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, column: Column, value: Any) -> None:
        super().__init__()
        self.column = column
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(f"{self.column.name}  [dim]{self.column.type.label}[/]")
            yield Input(
                value=display(self.column.type, self.value),
                placeholder=self.column.type.hint,
                id="value",
            )
            yield Static("", id="error", classes="error")
            yield Static(
                "[dim]enter save · esc cancel · empty clears the cell[/]",
                classes="dialog-help",
            )

    def on_mount(self) -> None:
        value_input = self.query_one("#value", Input)
        value_input.focus()
        value_input.cursor_position = len(value_input.value)

    @on(Input.Submitted)
    def save(self) -> None:
        raw = self.query_one("#value", Input).value
        try:
            parsed = parse(self.column.type, raw, self.column.options)
        except ValidationError as error:
            self.query_one("#error", Static).update(f"[red]{error}[/]")
            return
        self.dismiss((True, parsed))

    def action_cancel(self) -> None:
        self.dismiss((False, None))


class PickScreen(ModalScreen[tuple[bool, Any]]):
    """Option picker for dropdown cells."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, column: Column, value: Any) -> None:
        super().__init__()
        self.column = column
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(f"{self.column.name}  [dim]Dropdown[/]")
            yield OptionList(CLEAR_OPTION, *self.column.options, id="options")
            yield Static("[dim]enter pick · esc cancel[/]", classes="dialog-help")

    def on_mount(self) -> None:
        options = self.query_one("#options", OptionList)
        options.focus()
        if self.value in self.column.options:
            options.highlighted = self.column.options.index(self.value) + 1

    @on(OptionList.OptionSelected)
    def pick(self, event: OptionList.OptionSelected) -> None:
        if event.option_index == 0:
            self.dismiss((True, None))
        else:
            self.dismiss((True, self.column.options[event.option_index - 1]))

    def action_cancel(self) -> None:
        self.dismiss((False, None))


class ColumnScreen(ModalScreen[tuple[str, ColumnType, list[str]] | None]):
    """Create or edit a column definition."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, column: Column | None = None) -> None:
        super().__init__()
        self.column = column

    def compose(self) -> ComposeResult:
        column = self.column
        with Vertical(classes="dialog dialog--wide"):
            yield Label(
                "Edit column" if column else "New column", classes="dialog-title"
            )
            yield Label("Name", classes="field-label")
            yield Input(value=column.name if column else "", id="name")
            yield Label("Type", classes="field-label")
            yield Select(
                [(t.label, t.value) for t in ColumnType],
                value=(column.type if column else ColumnType.TEXT).value,
                allow_blank=False,
                id="type",
            )
            yield Label("Options (comma separated)", classes="field-label", id="options-label")
            yield Input(
                value=", ".join(column.options) if column else "",
                placeholder="Low, Medium, High",
                id="options",
            )
            yield Static("", id="error", classes="error")
            with Horizontal(classes="buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#name", Input).focus()
        self._sync_options_field()

    def _selected_type(self) -> ColumnType:
        return ColumnType(self.query_one("#type", Select).value)

    def _sync_options_field(self) -> None:
        is_dropdown = self._selected_type() is ColumnType.SELECT
        self.query_one("#options-label", Label).display = is_dropdown
        self.query_one("#options", Input).display = is_dropdown

    @on(Select.Changed, "#type")
    def type_changed(self) -> None:
        self._sync_options_field()

    @on(Input.Submitted)
    @on(Button.Pressed, "#save")
    def save(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        coltype = self._selected_type()
        options = [
            part.strip()
            for part in self.query_one("#options", Input).value.split(",")
            if part.strip()
        ]
        if not name:
            return self._error("Give the column a name")
        if coltype is ColumnType.SELECT and not options:
            return self._error("A dropdown needs at least one option")
        if len(set(o.lower() for o in options)) != len(options):
            return self._error("Options must be unique")
        self.dismiss((name, coltype, options))

    def _error(self, message: str) -> None:
        self.query_one("#error", Static).update(f"[red]{message}[/]")

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Yes/no prompt."""

    BINDINGS = [
        Binding("escape,n", "no", "No", show=False),
        Binding("y", "yes", "Yes", show=False),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.message)
            yield Static("[dim]y confirm · n or esc cancel[/]", classes="dialog-help")
            with Horizontal(classes="buttons"):
                yield Button("Delete", variant="error", id="yes")
                yield Button("Cancel", id="no")

    @on(Button.Pressed, "#yes")
    def action_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def action_no(self) -> None:
        self.dismiss(False)


class ThemeScreen(ModalScreen[str | None]):
    """Theme picker that applies each theme as you move through the list."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self) -> None:
        super().__init__()
        self.original = ""

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Theme")
            yield OptionList(*sorted(self.app.available_themes), id="themes")
            yield Static(
                "[dim]↑↓ preview · enter keep · esc revert[/]", classes="dialog-help"
            )

    def on_mount(self) -> None:
        self.original = self.app.theme
        themes = self.query_one("#themes", OptionList)
        themes.focus()
        names = sorted(self.app.available_themes)
        if self.original in names:
            themes.highlighted = names.index(self.original)

    @on(OptionList.OptionHighlighted)
    def preview(self, event: OptionList.OptionHighlighted) -> None:
        self.app.theme = str(event.option.prompt)

    @on(OptionList.OptionSelected)
    def keep(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(str(event.option.prompt))

    def action_cancel(self) -> None:
        self.app.theme = self.original
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    """Keyboard reference."""

    BINDINGS = [Binding("escape,question_mark,q", "close", "Close", show=False)]

    KEYS = [
        ("arrows", "Move around the grid"),
        ("enter", "Edit the current cell (toggles a yes/no cell)"),
        ("space", "Same as enter"),
        ("backspace", "Clear the current cell"),
        ("a", "Add a row at the bottom"),
        ("i", "Insert a row below the cursor"),
        ("d", "Delete the current row"),
        ("c", "Add a column"),
        ("e", "Edit the current column (name, type, options)"),
        ("x", "Delete the current column"),
        ("[ / ]", "Move the current column left / right"),
        ("t", "Change the colour theme"),
        ("?", "This help"),
        ("q", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dialog--wide"):
            yield Label("Keys")
            for key, description in self.KEYS:
                yield Static(f"  [b]{key:<10}[/] [dim]{description}[/]")
            yield Static("", classes="dialog-help")
            yield Static(
                "[dim]Every change is written to the file straight away.[/]",
                classes="dialog-help",
            )

    def action_close(self) -> None:
        self.dismiss(None)
