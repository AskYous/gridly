"""How the sheet is drawn, and the settings that decide it.

Column width, row height, wrapping and which way round the grid runs all feed
into the same few measurements, so they live together rather than being spread
between the app and a pile of loose helpers.

None of this decides *which* records are shown or in what order — that is what
a view is, and it is a separate thing.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any

from rich.cells import cell_len
from rich.text import Text

from . import config
from .coltypes import ColumnType, color_style, display
from .store import Column

# A padded row gets this many blank lines above its value, and as many below.
PADDING = 1
DEFAULT_PADDED = False

# Whether the types that suit it sit down the middle of their column.
DEFAULT_CENTRED = True

# How wide a column may get, in the order w cycles them. These are caps, not
# widths: a column narrower than its cap keeps its own size, so a yes/no column
# never gets padded out. "fit" has no fixed cap — it shares the viewport out
# between the columns so the whole table fits across.
COLUMN_WIDTHS = ("large", "fit", "small", "unlimited")
COLUMN_CAPS = {"large": 36, "small": 16, "fit": None, "unlimited": None}
DEFAULT_COLUMN_WIDTH = "fit"

# However tight the fit, a column stays readable rather than disappearing.
MIN_FIT_WIDTH = 6

# What a capped column does with a value too long for it. Wrapping grows the
# row to fit whatever it holds; padding is added on top either way.
OVERFLOWS = ("ellipsis", "wrap")
DEFAULT_OVERFLOW = "ellipsis"

# However much a wrapped row wants, it does not get to own the whole screen.
MAX_WRAP_LINES = 12


@dataclass
class Appearance:
    """How a sheet looks. Never changes what is in it, or which of it is shown."""

    #: A blank line above and below each value, whatever height it needs.
    padded: bool = DEFAULT_PADDED
    #: Booleans, dates, times and dropdowns go down the middle of their column.
    #: Text and numbers are read from their left edge and never move.
    centred: bool = DEFAULT_CENTRED
    column_width: str = DEFAULT_COLUMN_WIDTH
    overflow: str = DEFAULT_OVERFLOW

    @classmethod
    def load(cls) -> Appearance:
        """The settings from last time, ignoring anything unrecognisable."""
        saved = config.load()
        appearance = cls()
        if isinstance(saved.get("padded"), bool):
            appearance.padded = saved["padded"]
        elif saved.get("row_size") in ("small", "large"):
            appearance.padded = saved["row_size"] == "large"  # what it used to be
        if isinstance(saved.get("centred"), bool):
            appearance.centred = saved["centred"]
        if saved.get("column_width") in COLUMN_WIDTHS:
            appearance.column_width = saved["column_width"]
        if saved.get("overflow") in OVERFLOWS:
            appearance.overflow = saved["overflow"]
        return appearance

    def save(self) -> None:
        """Write the settings that outlive the session."""
        config.save(
            padded=self.padded,
            centred=self.centred,
            column_width=self.column_width,
            overflow=self.overflow,
        )

    # ------------------------------------------------------------- switching

    def cycle_column_width(self) -> None:
        self.column_width = _next(COLUMN_WIDTHS, self.column_width)
        config.save(column_width=self.column_width)

    def cycle_overflow(self) -> None:
        self.overflow = _next(OVERFLOWS, self.overflow)
        config.save(overflow=self.overflow)

    def toggle_padding(self) -> None:
        self.padded = not self.padded
        config.save(padded=self.padded)

    # -------------------------------------------------------------- drawing

    @property
    def capped(self) -> bool:
        """Is anything holding the columns back?"""
        return self.column_width != "unlimited"

    @property
    def wrapping(self) -> bool:
        """Wrapping needs a cap to wrap against, so both settings have to agree."""
        return self.overflow == "wrap" and self.capped

    @property
    def spare(self) -> int:
        """Blank lines a padded row adds, above and below together."""
        return 2 * PADDING if self.padded else 0

    def cell(self, column: Column, value: Any) -> Text:
        """A value drawn for the row height that is in force."""
        if self.wrapping:
            # The row will be grown to fit this, so nothing is squeezed or cut.
            return render(column, value, MAX_WRAP_LINES, self.centred)
        height = 1 + self.spare
        drawn = centred(render(column, value, height, self.centred), height)
        if self.capped:
            drawn.no_wrap = True
            drawn.overflow = "ellipsis"
        return drawn

    def row_height(self, cells: list[Text], widths: list[int | None]) -> int:
        """How many lines a row needs, padding included."""
        if not self.wrapping:
            return 1 + self.spare
        needed = max(
            (lines_needed(cell, width) for cell, width in zip(cells, widths)),
            default=1,
        )
        return min(max(1, needed), MAX_WRAP_LINES) + self.spare

    def place(
        self, cells: list[Text], widths: list[int | None], height: int
    ) -> list[Text]:
        """Sit every value in the middle of the row its tallest neighbour set.

        A short value stranded at the top of a row nine lines tall reads as a
        mistake, so each one is centred against the whole row, padding included.
        """
        if not self.wrapping:
            return cells  # cell() has already centred these
        return [
            centred(cell, height, lines_needed(cell, width))
            for cell, width in zip(cells, widths)
        ]

    def widths(
        self,
        labels: list[Text],
        columns: list[list[Text]],
        row_label: int,
        available: int,
        gutters: int,
    ) -> list[int | None]:
        """How wide each column gets. A cap never pads a narrow column out."""
        naturals = [
            max([widest(label)] + [widest(cell) for cell in cells] + [1])
            for label, cells in zip(labels, columns)
        ]
        if self.column_width == "unlimited":
            return [None] * len(naturals)
        if self.column_width != "fit":
            cap = COLUMN_CAPS[self.column_width]
            return [min(natural, cap) for natural in naturals]

        # Everything the table spends besides the columns themselves.
        budget = available - (row_label + gutters) - gutters * len(naturals)
        if available <= 0 or budget <= 0 or sum(naturals) <= budget:
            return naturals
        cap = fair_cap(naturals, budget, MIN_FIT_WIDTH)
        return [min(natural, cap) for natural in naturals]


def _next(options: tuple[str, ...], current: str) -> str:
    return options[(options.index(current) + 1) % len(options)]


def field_label(column: Column, middle: bool = DEFAULT_CENTRED) -> Text:
    # A worked-out column says so beside its type, since nothing else in the
    # grid distinguishes a value nobody typed from one somebody did.
    tag = column.type.tag + (" fx" if column.computed is not None else "")
    label = Text.assemble((column.name, "bold"), (f"  {tag}", "dim"))
    # A heading against the left of a column of right-aligned figures reads as
    # a different column, so it goes wherever the values go.
    label.justify = sits(column, middle)
    return label


def fair_cap(naturals: list[int], budget: int, minimum: int) -> int:
    """The widest every column may be so that together they fit the budget.

    Narrow columns are paid in full and the room they leave is shared out among
    the wide ones, so squeezing costs the columns that are hogging the screen.
    """
    remaining = budget
    for index, width in enumerate(sorted(naturals)):
        left = len(naturals) - index
        if width * left <= remaining:
            remaining -= width
        else:
            return max(minimum, remaining // left)
    return max(naturals, default=minimum)


def widest(text: Text) -> int:
    """How many columns the longest line of a value needs."""
    return max((cell_len(line) for line in text.plain.split("\n")), default=0)


def fit(text: str, lines: int) -> Text:
    """Lay a value out over the lines its row has.

    Whatever is left over is squeezed onto the last of them, every break it
    swallows marked with a dim ⏎, so even a one-line row shows the whole value.
    """
    parts = text.replace("\t", " ").split("\n")
    head, tail = parts[: lines - 1], parts[lines - 1 :]
    fitted = Text("\n".join(head))
    if not tail:
        return fitted
    if head:
        fitted.append("\n")
    fitted.append(tail[0])
    for part in tail[1:]:
        fitted.append(" ⏎ ", "dim")
        fitted.append(part)
    return fitted


def lines_needed(cell: Text, width: int | None) -> int:
    """How many screen lines a value takes once it has wrapped to `width`."""
    return sum(
        max(1, ceil(cell_len(line) / max(1, width or 1)))
        for line in cell.plain.split("\n")
    )


def centred(cell: Text, height: int, lines: int | None = None) -> Text:
    """Sit a value in the middle of the height it has been given."""
    occupied = cell.plain.count("\n") + 1 if lines is None else lines
    above = (height - occupied) // 2
    if above <= 0:
        return cell
    # Adding Texts together drops how the result should be justified, so it is
    # carried over by hand — otherwise a tick loses its centring in a tall row.
    padded = Text("\n" * above) + cell
    padded.justify = cell.justify
    return padded


#: Types whose values are shorter than their heading and all of a size, so
#: they read better down the middle of the column than against its left edge.
CENTRED = (ColumnType.BOOLEAN, ColumnType.DATE, ColumnType.TIME, ColumnType.SELECT)

#: Where a column's values may be told to sit, and what the form calls each.
#: The empty one leaves it to the type, which is what every column did before
#: a column could be told; the rest are Rich's own names for the same thing.
ALIGNMENTS = {
    "": "Automatic",
    "left": "Left",
    "center": "Centred",
    "right": "Right",
}


def sits(column: Column, middle: bool = DEFAULT_CENTRED) -> str | None:
    """Where this column's values sit across it.

    A column that has been told wins outright. One that has not falls back to
    what its type suits, which is the sheet-wide setting's business.
    """
    if column.align in ("left", "center", "right"):
        return column.align
    return "center" if middle and column.type in CENTRED else None


def render(
    column: Column, value: Any, lines: int, middle: bool = DEFAULT_CENTRED
) -> Text:
    """How a value looks inside the grid."""
    across = sits(column, middle)
    if value is None:
        return Text("·", "dim", justify=across)
    if column.type is ColumnType.BOOLEAN:
        return (
            Text("✓", "green", justify=across)
            if value
            else Text("✗", "red dim", justify=across)
        )
    if column.type is ColumnType.NUMBER:
        return Text(display(column.type, value), "cyan", justify=across)
    if column.type in (ColumnType.DATE, ColumnType.TIME):
        return Text(display(column.type, value, column.format), "magenta", justify=across)
    if column.type is ColumnType.SELECT:
        return Text(
            display(column.type, value), color_style(column.color(value)), justify=across
        )
    drawn = fit(display(column.type, value), lines)
    drawn.justify = across
    return drawn
