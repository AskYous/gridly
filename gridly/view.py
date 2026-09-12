"""How the sheet is drawn, and the settings that decide it.

Column width, row height, wrapping and which way round the grid runs all feed
into the same few measurements, so they live together rather than being spread
between the app and a pile of loose helpers.
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

# How many lines a row gets on screen. Both are odd heights, so a single-line
# value has as many blank lines above it as below.
ROW_SIZES = {"small": 1, "large": 3}
DEFAULT_ROW_SIZE = "small"

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
# row to fit, so row_size only applies to the ellipsis side.
OVERFLOWS = ("ellipsis", "wrap")
DEFAULT_OVERFLOW = "ellipsis"

# However much a wrapped row wants, it does not get to own the whole screen.
MAX_WRAP_LINES = 12


@dataclass
class View:
    """A way of looking at a sheet. Never changes what is in it."""

    #: Records down the screen (normal) or across it.
    flipped: bool = False
    row_size: str = DEFAULT_ROW_SIZE
    column_width: str = DEFAULT_COLUMN_WIDTH
    overflow: str = DEFAULT_OVERFLOW

    @classmethod
    def load(cls) -> View:
        """The settings from last time, ignoring anything unrecognisable.

        `flipped` is deliberately not among them: it is a quick look at a wide
        sheet, not a preference.
        """
        saved = config.load()
        view = cls()
        if saved.get("row_size") in ROW_SIZES:
            view.row_size = saved["row_size"]
        if saved.get("column_width") in COLUMN_WIDTHS:
            view.column_width = saved["column_width"]
        if saved.get("overflow") in OVERFLOWS:
            view.overflow = saved["overflow"]
        return view

    def save(self) -> None:
        """Write the settings that outlive the session."""
        config.save(
            row_size=self.row_size,
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

    def cycle_row_size(self) -> None:
        self.row_size = _next(tuple(ROW_SIZES), self.row_size)
        config.save(row_size=self.row_size)

    # -------------------------------------------------------------- drawing

    @property
    def capped(self) -> bool:
        """Is anything holding the columns back?"""
        return self.column_width != "unlimited"

    @property
    def wrapping(self) -> bool:
        """Wrapping needs a cap to wrap against, so both settings have to agree."""
        return self.overflow == "wrap" and self.capped

    def cell(self, column: Column, value: Any) -> Text:
        """A value drawn for the row height that is in force."""
        if self.wrapping:
            # The row will be grown to fit this, so nothing is squeezed or cut.
            return render(column, value, MAX_WRAP_LINES)
        height = ROW_SIZES[self.row_size]
        drawn = centred(render(column, value, height), height)
        if self.capped:
            drawn.no_wrap = True
            drawn.overflow = "ellipsis"
        return drawn

    def row_height(self, cells: list[Text], widths: list[int | None]) -> int:
        """How many lines a row needs once its values have wrapped."""
        if not self.wrapping:
            return ROW_SIZES[self.row_size]
        needed = max(
            (lines_needed(cell, width) for cell, width in zip(cells, widths)),
            default=1,
        )
        return min(max(1, needed), MAX_WRAP_LINES)

    def centre(
        self, cells: list[Text], widths: list[int | None], height: int
    ) -> list[Text]:
        """Sit each value in the middle of the row its tallest neighbour set."""
        if not self.wrapping:
            return cells  # cell() has already centred these against a fixed height
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


def field_label(column: Column) -> Text:
    return Text.assemble((column.name, "bold"), (f"  {column.type.tag}", "dim"))


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
    """Sit a value in the middle of its row rather than at the top of it."""
    occupied = cell.plain.count("\n") + 1 if lines is None else lines
    above = (height - occupied) // 2
    return Text("\n" * above) + cell if above > 0 else cell


def render(column: Column, value: Any, lines: int) -> Text:
    """How a value looks inside the grid."""
    if value is None:
        return Text("·", "dim")
    if column.type is ColumnType.BOOLEAN:
        return Text("✓", "green") if value else Text("✗", "red dim")
    if column.type is ColumnType.NUMBER:
        return Text(display(column.type, value), "cyan")
    if column.type is ColumnType.DATE:
        return Text(display(column.type, value), "magenta")
    if column.type is ColumnType.SELECT:
        return Text(display(column.type, value), color_style(column.color(value)))
    return fit(display(column.type, value), lines)
