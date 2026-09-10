"""Modal dialogs: editing a cell, defining a column, confirming a deletion."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Select, Static, TextArea

from .coltypes import (
    OPTION_COLORS,
    ColumnType,
    ValidationError,
    assign_colors,
    color_style,
    display,
    parse,
)
from .store import Column, Row

CLEAR_OPTION = "— clear —"


def _palette() -> Text:
    """The colours you can ask for, each written in itself."""
    swatches = Text("colours: ", "dim")
    for index, color in enumerate(OPTION_COLORS):
        if index:
            swatches.append("  ", "dim")
        swatches.append(color, color_style(color))
    return swatches


def _option_lines(column: Column | None) -> str:
    """A dropdown's options as text, each with the colour it is shown in."""
    if column is None:
        return ""
    return "\n".join(
        f"{option} = {column.color(option)}" for option in column.options
    )


def build_editor(column: Column, value: Any, field_id: str):
    """The right widget for a column's type, pre-filled with `value`."""
    if column.type is ColumnType.BOOLEAN:
        return Select(
            [("Yes", "yes"), ("No", "no")],
            value="yes" if value else "no" if value is not None else Select.NULL,
            prompt="(not set)",
            id=field_id,
        )
    if column.type is ColumnType.SELECT:
        return Select(
            [(option, option) for option in column.options],
            value=value if value in column.options else Select.NULL,
            prompt="(not set)",
            id=field_id,
        )
    if column.type is ColumnType.TEXT:
        # Text may contain newlines — a single-line Input would hide all but the first.
        return TextArea(display(column.type, value), soft_wrap=True, id=field_id)
    return Input(
        value=display(column.type, value), placeholder=column.type.hint, id=field_id
    )


def read_editor(field) -> str:
    """The raw text a `build_editor` widget is holding."""
    return field.text if isinstance(field, TextArea) else field.value


class CellEditScreen(ModalScreen[tuple[bool, Any]]):
    """Editor for text, number and date cells."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, column: Column, value: Any) -> None:
        super().__init__()
        self.column = column
        self.value = value
        # Text can hold newlines, so it needs an editor that can show them.
        self.multiline = column.type is ColumnType.TEXT

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(f"{self.column.name}  [dim]{self.column.type.label}[/]")
            yield build_editor(self.column, self.value, "value")
            yield Static("", id="error", classes="error")
            save_key = "ctrl+s" if self.multiline else "enter"
            yield Static(
                f"[dim]{save_key} save · esc cancel · empty clears the cell[/]",
                classes="dialog-help",
            )

    def on_mount(self) -> None:
        editor = self.query_one("#value")
        editor.focus()
        # Start where you would carry on typing, not in front of what is there.
        if isinstance(editor, Input):
            editor.cursor_position = len(editor.value)
        elif isinstance(editor, TextArea):
            editor.move_cursor(editor.document.end)

    @on(Input.Submitted)
    def action_save(self) -> None:
        try:
            parsed = parse(self.column.type, read_editor(self.query_one("#value")), self.column.options)
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
            yield OptionList(
                Text(CLEAR_OPTION, "dim"),
                *(
                    Text(option, color_style(self.column.color(option)))
                    for option in self.column.options
                ),
                id="options",
            )
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


class RowFormScreen(ModalScreen[dict[int, Any] | None]):
    """One row, one field per column — for when the grid is too cramped to think in."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, columns: list[Column], row: Row, number: int, total: int) -> None:
        super().__init__()
        self.columns = columns
        self.row = row
        self.number = number
        self.total = total

    def compose(self) -> ComposeResult:
        with Vertical(classes="form"):
            with Vertical(classes="form-inner"):
                yield Label(
                    f"Row {self.number} of {self.total}", classes="dialog-title"
                )
                with VerticalScroll(classes="form-fields"):
                    for column in self.columns:
                        yield Label(
                            f"{column.name}  [dim]{column.type.label}[/]",
                            classes="field-label",
                        )
                        yield self._field(column)
                yield Static("", id="error", classes="error")
                yield Static(
                    "[dim]tab move · ctrl+s save · esc cancel[/]",
                    classes="dialog-help",
                )

    def _field(self, column: Column):
        return build_editor(
            column, self.row.values.get(column.id), f"field-{column.id}"
        )

    def on_mount(self) -> None:
        if self.columns:
            self.query_one(f"#field-{self.columns[0].id}").focus()

    @on(Input.Submitted)
    def action_save(self) -> None:
        values: dict[int, Any] = {}
        for column in self.columns:
            field = self.query_one(f"#field-{column.id}")
            if isinstance(field, Select):
                chosen = None if field.value is Select.NULL else field.value
                if column.type is ColumnType.BOOLEAN:
                    values[column.id] = None if chosen is None else chosen == "yes"
                else:
                    values[column.id] = chosen
                continue
            try:
                values[column.id] = parse(
                    column.type, read_editor(field), column.options
                )
            except ValidationError as error:
                self.query_one("#error", Static).update(f"[red]{column.name}: {error}[/]")
                field.focus()
                return
        self.dismiss(values)

    def action_cancel(self) -> None:
        self.dismiss(None)


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
        with Vertical(classes="dialog dialog--wide"):
            yield Label(
                "Edit column" if column else "New column", classes="dialog-title"
            )
            # The fields scroll so the buttons and any error stay in view on a
            # short terminal.
            with VerticalScroll(classes="dialog-fields"):
                yield Label("Name", classes="field-label")
                yield Input(value=column.name if column else "", id="name")
                yield Label("Type", classes="field-label")
                yield Select(
                    [(t.label, t.value) for t in ColumnType],
                    value=(column.type if column else ColumnType.TEXT).value,
                    allow_blank=False,
                    id="type",
                )
                yield Label(
                    "Options, one per line — name = colour",
                    classes="field-label",
                    id="options-label",
                )
                yield TextArea(
                    _option_lines(column), soft_wrap=False, id="options"
                )
                yield Static(_palette(), id="palette", classes="palette")
            yield Static("", id="error", classes="error")
            yield Static("[dim]ctrl+s save · esc cancel[/]", classes="dialog-help")
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
        self.query_one("#options", TextArea).display = is_dropdown
        self.query_one("#palette", Static).display = is_dropdown

    @on(Select.Changed, "#type")
    def type_changed(self) -> None:
        self._sync_options_field()

    @on(Input.Submitted)
    @on(Button.Pressed, "#save")
    def action_save(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        coltype = self._selected_type()
        options: list[str] = []
        chosen: dict[str, str] = {}
        for line in self.query_one("#options", TextArea).text.splitlines():
            # A colour is one word after the last "=", so an option may contain
            # an "=" itself as long as what follows it is not a bare word.
            head, sep, tail = line.rpartition("=")
            color = tail.strip().lower()
            if sep and color and " " not in color:
                if color not in OPTION_COLORS:
                    return self._error(
                        f"{color!r} is not a colour. Try: "
                        ', '.join(OPTION_COLORS)
                    )
                label = head.strip()
            else:
                label, color = line.strip(), ""
            if not label:
                continue
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

    @on(Button.Pressed, "#cancel")
    def action_cancel(self) -> None:
        self.dismiss(None)


class ExportScreen(ModalScreen[str | None]):
    """Ask where to write the CSV."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", show=False)]

    def __init__(self, suggestion: str) -> None:
        super().__init__()
        self.suggestion = suggestion

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dialog--wide"):
            yield Label("Export to CSV")
            yield Label("File", classes="field-label")
            yield Input(value=self.suggestion, id="path")
            yield Static("", id="error", classes="error")
            yield Static("[dim]enter write · esc cancel[/]", classes="dialog-help")

    def on_mount(self) -> None:
        path_input = self.query_one("#path", Input)
        path_input.focus()
        path_input.cursor_position = len(path_input.value)

    @on(Input.Submitted)
    def save(self) -> None:
        path = self.query_one("#path", Input).value.strip()
        if not path:
            self.query_one("#error", Static).update("[red]Give the file a name[/]")
            return
        self.dismiss(path)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Yes/no prompt."""

    BINDINGS = [
        Binding("escape,n", "no", "No", show=False),
        Binding("y", "yes", "Yes", show=False),
    ]

    def __init__(self, message: str, confirm: str = "Delete") -> None:
        super().__init__()
        self.message = message
        self.confirm = confirm

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self.message)
            yield Static("[dim]y confirm · n or esc cancel[/]", classes="dialog-help")
            with Horizontal(classes="buttons"):
                yield Button(self.confirm, variant="error", id="yes")
                yield Button("Cancel", id="no")

    @on(Button.Pressed, "#yes")
    def action_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def action_no(self) -> None:
        self.dismiss(False)


class HelpScreen(ModalScreen[None]):
    """Keyboard reference."""

    BINDINGS = [Binding("escape,question_mark,q", "close", "Close", show=False)]

    # Grouped, and kept short enough to sit on one line beside the key.
    KEYS = [
        ("Moving and editing", [
            ("arrows", "Move around the grid"),
            ("enter / space", "Edit the cell, or toggle a yes/no"),
            ("ctrl+s", "Save a text cell (enter adds a line)"),
            ("backspace", "Clear the cell"),
            ("f", "Edit the whole row as a form"),
        ]),
        ("Rows and columns", [
            ("a / i", "Add a row at the bottom / below"),
            ("D", "Duplicate the row"),
            ("d", "Delete the row"),
            ("c / e / x", "Add / edit / delete a column"),
            ("[ / ]", "Move the column left / right"),
        ]),
        ("Clipboard", [
            ("shift+arrows", "Select a block of cells"),
            ("esc", "Drop the selection"),
            ("y / Y", "Copy the cell or block / the row"),
            ("cmd+v", "Paste cells from a spreadsheet"),
            ("E", "Export the sheet to CSV"),
        ]),
        ("How it looks", [
            ("w", "Width: large, fit, small, uncapped"),
            ("W", "Wrap long values, or cut with …"),
            ("s", "Row height: one line or three"),
            ("v", "Flip: records across, not down"),
            ("t", "Change the colour theme"),
        ]),
        ("Finding things", [
            ("ctrl+p", "Every command, searchable by name"),
            ("? / q", "This help / quit"),
        ]),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog dialog--wide"):
            yield Label("Keys")
            with VerticalScroll(classes="dialog-fields"):
                for heading, rows in self.KEYS:
                    yield Static(f"[b]{heading}[/]", classes="help-heading")
                    for key, description in rows:
                        yield Static(f"  [b]{key:<14}[/][dim]{description}[/]")
            yield Static(
                "[dim]↑↓ scroll · esc close · every change is saved as you make it[/]",
                classes="dialog-help",
            )

    def action_close(self) -> None:
        self.dismiss(None)
