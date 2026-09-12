"""Small dialogs: naming a file, saying yes, and the list of keys."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

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
