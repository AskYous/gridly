"""The settings page: every way of looking at a sheet, in one place."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Select, Static

from ..view import View


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
