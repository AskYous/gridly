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
from .view import (
    COLUMN_WIDTHS,
    DEFAULT_COLUMN_WIDTH,
    DEFAULT_OVERFLOW,
    DEFAULT_ROW_SIZE,
    OVERFLOWS,
    ROW_SIZES,
    View,
)

CLEAR_OPTION = "— clear —"


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


#: Every setting, with something readable to say about each choice.
SETTINGS = [
    (
        "column_width",
        "Column width",
        "How wide a column is allowed to get.",
        [
            ("fit — share the screen so the whole table fits across", "fit"),
            ("large — stop at 36 characters", "large"),
            ("small — stop at 16 characters", "small"),
            ("unlimited — as wide as the longest value", "unlimited"),
        ],
    ),
    (
        "overflow",
        "Long values",
        "What happens to a value too long for its column.",
        [
            ("ellipsis — cut it off with a …", "ellipsis"),
            ("wrap — wrap it, growing the row to fit", "wrap"),
        ],
    ),
    (
        "row_size",
        "Row height",
        "How tall a row is. Ignored while values wrap, since they set their own.",
        [
            ("small — one line", "small"),
            ("large — three lines", "large"),
        ],
    ),
    (
        "flipped",
        "Layout",
        "Which way round the grid runs. Not remembered between runs.",
        [
            ("normal — a row per record", False),
            ("flipped — a column per record", True),
        ],
    ),
]


class SettingsScreen(ModalScreen[tuple[View, str] | None]):
    """Everything the view keys do, in one place, with a way back to the defaults."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self, view: View, theme: str, themes: list[str], default_theme: str):
        super().__init__()
        self.view = view
        self.theme_was = theme
        self.themes = themes
        self.default_theme = default_theme

    def compose(self) -> ComposeResult:
        with Vertical(classes="form"):
            with Vertical(classes="form-inner"):
                yield Label("Settings", classes="dialog-title")
                with VerticalScroll(classes="form-fields"):
                    for key, title, about, choices in SETTINGS:
                        yield Label(title, classes="field-label")
                        yield Static(f"[dim]{about}[/]", classes="setting-about")
                        yield Select(
                            choices,
                            value=getattr(self.view, key),
                            allow_blank=False,
                            id=f"set-{key}",
                        )
                    yield Label("Theme", classes="field-label")
                    yield Static(
                        "[dim]Changes as you pick, so you can see it.[/]",
                        classes="setting-about",
                    )
                    yield Select(
                        [(name, name) for name in self.themes],
                        value=self.theme_was,
                        allow_blank=False,
                        id="set-theme",
                    )
                    yield Button(
                        "Reset everything to defaults", compact=True, id="reset"
                    )
                yield Static(
                    "[dim]tab move · ctrl+s save · esc cancel[/]",
                    classes="dialog-help",
                )

    @on(Select.Changed, "#set-theme")
    def preview_theme(self, event: Select.Changed) -> None:
        self.app.theme = str(event.value)

    @on(Button.Pressed, "#reset")
    def reset(self) -> None:
        fresh = View()
        for key, *_ in SETTINGS:
            self.query_one(f"#set-{key}", Select).value = getattr(fresh, key)
        self.query_one("#set-theme", Select).value = self.default_theme

    def action_save(self) -> None:
        chosen = View(
            **{key: self.query_one(f"#set-{key}", Select).value for key, *_ in SETTINGS}
        )
        self.dismiss((chosen, str(self.query_one("#set-theme", Select).value)))

    def action_cancel(self) -> None:
        self.app.theme = self.theme_was  # undo the preview
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
            ("u / U", "Undo / redo the last change"),
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
            (",", "Settings: all of the above in one page"),
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
