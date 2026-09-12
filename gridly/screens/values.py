"""Editing values: one cell, one dropdown choice, or a whole row."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Select, Static, TextArea

from ..coltypes import ColumnType, ValidationError, color_style, display, parse
from ..store import Column, Row

CLEAR_OPTION = "— clear —"


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
