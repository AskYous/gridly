"""Defining a column: its name, its type, and a dropdown's options."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from ..coltypes import (
    OPTION_COLORS,
    TIME_FORMATS,
    ColumnType,
    assign_colors,
    color_style,
)
from dataclasses import dataclass, field, replace as dataclass_replace

from .. import arithmetic
from ..appearance import ALIGNMENTS
from ..formulas import (
    FUNCTIONS,
    MONTH_WORDINGS,
    Formula,
    options_for,
    read_sum,
    reading_order,
    refusal,
    sources_among,
    unreadable,
)
from ..store import Column

#: What the "Value" dropdown calls a column nobody works out for you.
TYPED_IN = "typed"


def _swatch(color: str) -> Text:
    """A colour's name next to a block of it, for the colour dropdown."""
    return Text.assemble(("███ ", color_style(color)), (color, ""))

@dataclass
class ColumnSpec:
    """What the form says a column should be."""

    name: str
    type: ColumnType
    options: list[str] = field(default_factory=list)
    colors: dict[str, str] = field(default_factory=dict)
    unique: bool = False
    #: How the type writes itself, where it has a choice.
    format: str = ""
    #: An encoded Formula, where the column is worked out rather than typed in.
    formula: str = ""
    #: Where the values sit across the column. Empty leaves it to the type.
    align: str = ""
    #: Options that were reworded, old name to new, so the values can follow.
    renames: dict[str, str] = field(default_factory=dict)


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
    def was(self) -> str:
        """What this option was called when the form opened."""
        return self.option_name

    @property
    def option(self) -> tuple[str, str | None]:
        name = self.query_one(".option-name", Input).value.strip()
        picked = self.query_one(".option-color", Select).value
        return name, None if picked is Select.NULL else str(picked)

class ColumnScreen(ModalScreen[ColumnSpec | None]):
    """Create or edit a column definition."""

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=False),
        Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(
        self, column: Column | None = None, columns: list[Column] | None = None
    ) -> None:
        super().__init__()
        self.column = column
        #: Every column in the sheet, which is what a sum may name.
        self.all = list(columns or [])
        #: The ones a month can be taken from.
        self.sources = sources_among(self.all, exclude=column.id if column else 0)

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
                    yield Label(
                        "Time shows", classes="field-label", id="format-label"
                    )
                    yield Select(
                        [(about, key) for key, about in TIME_FORMATS.items()],
                        value=(column.format if column else "") or "",
                        allow_blank=False,
                        id="format",
                    )
                    spec = column.computed if column else None
                    yield Label("Value", classes="field-label")
                    yield Select(
                        [
                            ("Typed in", TYPED_IN),
                            *((about, fn) for fn, about in FUNCTIONS.items()),
                        ],
                        value=spec.fn if spec else TYPED_IN,
                        allow_blank=False,
                        id="function",
                    )
                    yield Label("Taken from", classes="field-label", id="source-label")
                    yield Select(
                        [(source.name, source.id) for source in self.sources],
                        value=(
                            spec.source
                            if spec and any(s.id == spec.source for s in self.sources)
                            else Select.NULL
                        ),
                        prompt="(choose a date column)",
                        id="source",
                    )
                    yield Label("Written as", classes="field-label", id="shows-label")
                    yield Select(
                        [
                            (f"{example}", key)
                            for key, example in MONTH_WORDINGS.items()
                        ],
                        value=spec.shows if spec else next(iter(MONTH_WORDINGS)),
                        allow_blank=False,
                        id="shows",
                    )
                    yield Label("Formula", classes="field-label", id="expr-label")
                    yield Input(
                        value=spec.expr if spec else "",
                        # An example of the shape, naming no column: the line
                        # underneath is where this sheet's own names belong.
                        placeholder="e.g. 8 * 2 + 5",
                        id="expr",
                    )
                    yield Static("", classes="dialog-help", id="expr-help")
                    yield Label("Options", classes="field-label", id="options-label")
                    with Vertical(id="options"):
                        for option in column.options if column else []:
                            yield OptionRow(option, column.color(option))
                    yield Button("+ add option", compact=True, id="add-option")
                    yield Label("Alignment", classes="field-label")
                    yield Select(
                        [(about, key) for key, about in ALIGNMENTS.items()],
                        value=(column.align if column else "") or "",
                        allow_blank=False,
                        id="align",
                    )
                    yield Static(
                        "Automatic puts dates, times, yes/no and dropdowns down "
                        "the middle, and text and numbers against the left.",
                        classes="dialog-help",
                        id="align-help",
                    )
                    yield Label("Rules", classes="field-label", id="rules-label")
                    yield Checkbox(
                        "Unique — no two rows may hold the same value",
                        value=column.unique if column else False,
                        id="unique",
                    )
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

    def _readable(self) -> str:
        """The columns a formula here may use, spelled out under the field."""
        mine = self.column.id if self.column else 0
        names = [
            c.name for c in self.all if c.type is ColumnType.NUMBER and c.id != mine
        ]
        if not names:
            return (
                "[dim]numbers, + - * / and brackets — "
                "this sheet has no number column to use yet[/]"
            )
        return (
            "[dim]numbers, + - * / and brackets · "
            f"columns you can use: {', '.join(names)}[/]"
        )

    def _selected_function(self) -> str:
        """The sum this column is worked out by, or nothing if it is typed in."""
        chosen = self.query_one("#function", Select).value
        return "" if chosen in (TYPED_IN, Select.NULL) else str(chosen)

    def _sync_options_field(self) -> None:
        """Only show what the chosen type and source actually have to say."""
        coltype = self._selected_type()
        computed = bool(self._selected_function())
        # A worked-out dropdown lists whatever the sum can produce, so its
        # options are not something to type in; nor is a rule about repeats,
        # which is about what people put in a column, not what it works out.
        is_dropdown = coltype is ColumnType.SELECT and not computed
        is_time = coltype is ColumnType.TIME and not computed
        is_month = self._selected_function() == "month"
        is_sum = self._selected_function() == "sum"
        self.query_one("#format-label", Label).display = is_time
        self.query_one("#format", Select).display = is_time
        self.query_one("#source-label", Label).display = is_month
        self.query_one("#source", Select).display = is_month
        self.query_one("#shows-label", Label).display = is_month
        self.query_one("#shows", Select).display = is_month
        self.query_one("#expr-label", Label).display = is_sum
        self.query_one("#expr", Input).display = is_sum
        self.query_one("#expr-help", Static).display = is_sum
        if is_sum:
            self.query_one("#expr-help", Static).update(self._readable())
        self.query_one("#options-label", Label).display = is_dropdown
        self.query_one("#options", Vertical).display = is_dropdown
        self.query_one("#add-option", Button).display = is_dropdown
        self.query_one("#rules-label", Label).display = not computed
        self.query_one("#unique", Checkbox).display = not computed
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
    @on(Select.Changed, "#function")
    def type_changed(self) -> None:
        self._sync_options_field()

    @on(Input.Submitted)
    def action_save(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        coltype = self._selected_type()
        options: list[str] = []
        chosen: dict[str, str] = {}
        renames: dict[str, str] = {}
        for row in self.query(OptionRow):
            label, color = row.option
            if not label:
                continue  # a row left blank is a row you meant to drop
            options.append(label)
            if color:
                chosen[label] = color
            if row.was and row.was != label:
                renames[row.was] = label

        if not name:
            return self._error("Give the column a name")

        spec: Formula | None = None
        if function := self._selected_function():
            if function == "sum":
                spec = Formula("sum", expr=self.query_one("#expr", Input).value.strip())
                try:
                    tree = arithmetic.parse(spec.expr, [c.name for c in self.all])
                except arithmetic.FormulaError as error:
                    return self._error(str(error))
                if complaint := unreadable(tree, self.all):
                    return self._error(complaint)
                if self._loops(spec):
                    return self._error(
                        f"{name} would be worked out from itself, round in a circle"
                    )
            else:
                if not self.sources:
                    return self._error(
                        "There is no date column to take a month from — add one first"
                    )
                source = self.query_one("#source", Select).value
                if source is Select.NULL:
                    return self._error("Say which column the value is taken from")
                spec = Formula(
                    function,
                    int(source),
                    str(self.query_one("#shows", Select).value),
                )
            if complaint := refusal(spec, coltype):
                return self._error(complaint)
            # A worked-out dropdown holds exactly what the sum can produce,
            # so its options come from the sum rather than from the form.
            options = (
                options_for(spec)
                if coltype is ColumnType.SELECT and spec.fn == "month"
                else []
            )
            chosen, renames = {}, {}

        if coltype is ColumnType.SELECT and not options:
            return self._error("A dropdown needs at least one option")
        if len(set(o.lower() for o in options)) != len(options):
            return self._error("Options must be unique")
        self.dismiss(
            ColumnSpec(
                name=name,
                type=coltype,
                options=options,
                colors=assign_colors(options, chosen),
                unique=self.query_one("#unique", Checkbox).value and spec is None,
                format=str(self.query_one("#format", Select).value or ""),
                formula=spec.encode() if spec else "",
                align=str(self.query_one("#align", Select).value or ""),
                renames=renames,
            )
        )

    def _loops(self, spec: Formula) -> bool:
        """Would this sum end up reading itself, however long the chain?

        Only an existing column can: a new one is not there to be read yet.
        """
        if self.column is None:
            return False
        proposed = [
            dataclass_replace(c, formula=spec.encode()) if c.id == self.column.id else c
            for c in self.all
        ]
        sums = {
            c.id: read_sum(c.computed.expr, proposed)
            for c in proposed
            if c.computed is not None and c.computed.fn == "sum"
        }
        return self.column.id not in {c.id for c in reading_order(proposed, sums)}

    def _error(self, message: str) -> None:
        self.query_one("#error", Static).update(f"[red]{message}[/]")

    def action_cancel(self) -> None:
        self.dismiss(None)
