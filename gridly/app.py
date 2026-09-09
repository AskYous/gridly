"""Gridly — a terminal spreadsheet with typed columns."""

from __future__ import annotations

import sys
from functools import partial
from math import ceil
from pathlib import Path
from typing import Any

from rich.cells import cell_len
from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static

from . import config
from .coltypes import ColumnType, ValidationError, display, parse
from .screens import (
    CellEditScreen,
    ColumnScreen,
    ConfirmScreen,
    ExportScreen,
    HelpScreen,
    PickScreen,
    RowFormScreen,
)
from .clipboard import format_block, parse_block, to_system_clipboard
from .csvfile import write_csv
from .store import Column, Row, Sheet

DEFAULT_FILE = "sheet.gridly"

# What a first run opens with, before anyone has pressed t.
DEFAULT_THEME = "rose-pine"

# How many lines a row gets on screen. Both are odd heights, so a single-line
# value has as many blank lines above it as below.
ROW_SIZES = {"small": 1, "large": 3}
DEFAULT_ROW_SIZE = "small"

# How wide a column may get. These are caps, not widths: a column narrower than
# its cap keeps its own size, so a yes/no column never gets padded out.
COLUMN_WIDTHS = {"small": 16, "large": 36, "unlimited": None}
DEFAULT_COLUMN_WIDTH = "large"

# What a capped column does with a value too long for it. Wrapping grows the
# row to fit, so row_size only applies to the ellipsis side.
OVERFLOWS = ("ellipsis", "wrap")
DEFAULT_OVERFLOW = "ellipsis"

# However much a wrapped row wants, it does not get to own the whole screen.
MAX_WRAP_LINES = 12


class GridlyApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "Gridly"

    # Set once the saved theme has been read, so the watcher below doesn't
    # write the default theme over it on the way up.
    _theme_loaded = False

    BINDINGS = [
        Binding("space", "edit_cell", "Edit"),
        Binding("f", "edit_row", "Form", show=False),
        Binding("shift+right", "extend(0, 1)", "Select", key_display="shift+→", show=False),
        Binding("shift+left", "extend(0, -1)", "Select left", show=False),
        Binding("shift+up", "extend(-1, 0)", "Select up", show=False),
        Binding("shift+down", "extend(1, 0)", "Select down", show=False),
        Binding("escape", "clear_selection", "Drop selection", show=False),
        Binding("v", "flip", "Flip", show=False),
        Binding("s", "toggle_row_size", "Size", show=False),
        Binding("w", "cycle_column_width", "Width", show=False),
        Binding("W", "toggle_overflow", "Wrap", show=False),
        Binding("y", "copy_cell", "Copy", show=False),
        Binding("Y", "copy_row", "Copy row", show=False),
        Binding("E", "export", "Export", show=False),
        Binding("backspace", "clear_cell", "Clear", show=False),
        Binding("a", "add_row", "+Row"),
        Binding("i", "insert_row", "Insert row", show=False),
        Binding("d", "delete_row", "-Row", show=False),
        Binding("c", "add_column", "+Col"),
        Binding("e", "edit_column", "Edit col", show=False),
        Binding("x", "delete_column", "-Col", show=False),
        Binding("left_square_bracket", "move_column(-1)", "Move col left", show=False),
        Binding("right_square_bracket", "move_column(1)", "Move col right", show=False),
        Binding("t", "change_theme", "Theme", show=False),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("q", "quit", "Quit"),
    ]

    # Everything the app can do, spelled out for the command palette. Keeping
    # it beside the bindings is what stops the two drifting apart; the titles
    # are longer than the footer's because there is room to say what they mean.
    PALETTE: list[tuple[str, str, str, bool]] = [
        ("edit_cell", "Edit cell", "Open the cell under the cursor", True),
        ("edit_row", "Edit row as a form", "One field per column, on its own screen", True),
        ("clear_cell", "Clear cell", "Leave the cell with no value at all", True),
        ("add_row", "Add row", "Append an empty row at the bottom", True),
        ("insert_row", "Insert row below", "Add an empty row under the cursor", True),
        ("delete_row", "Delete row", "Remove the row under the cursor", True),
        ("add_column", "Add column", "Define a new column and its type", True),
        ("edit_column", "Edit column", "Rename, retype or relist the current column", True),
        ("delete_column", "Delete column", "Remove the column and every value in it", True),
        ("move_column(-1)", "Move column left", "Swap it with the column before it", True),
        ("move_column(1)", "Move column right", "Swap it with the column after it", True),
        ("copy_cell", "Copy cell or selection", "To the clipboard, tab separated", True),
        ("copy_row", "Copy row", "The whole record, tab separated", True),
        ("export", "Export to CSV", "Write the sheet out as a file", True),
        ("flip", "Flip the view", "Draw records across the screen instead of down", True),
        ("toggle_row_size", "Toggle row height", "Between one line and three", True),
        ("cycle_column_width", "Cycle column width", "Cap columns small, large, or not at all", True),
        ("toggle_overflow", "Toggle wrapping", "A long value wraps over the row, or ends in an ellipsis", True),
        ("help", "Show Gridly's keys", "The keyboard reference", True),
        ("extend(0, 1)", "Select one cell right", "Grow the selection", False),
        ("extend(0, -1)", "Select one cell left", "Grow the selection", False),
        ("extend(-1, 0)", "Select one cell up", "Grow the selection", False),
        ("extend(1, 0)", "Select one cell down", "Grow the selection", False),
        ("clear_selection", "Drop the selection", "Back to a single cell", False),
    ]
    # Textual's own system commands already cover these two.
    PALETTE_ELSEWHERE = {"change_theme", "quit"}

    def get_system_commands(self, screen: Screen):
        yield from super().get_system_commands(screen)
        for action, title, description, discover in self.PALETTE:
            yield SystemCommand(
                title, description, partial(self.run_action, action), discover
            )

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.sheet = Sheet(path)
        self.sub_title = _short_path(self.sheet.path)
        self._columns: list[Column] = []
        self._rows: list[Row] = []
        # Draw records down the screen (normal) or across it (flipped). This is
        # only ever a way of looking at the sheet — the data is the same either way.
        self.flipped = False
        # A keyboard selection: where it started and which cells it covers now.
        # Cursor moves we made ourselves are counted, because the CellHighlighted
        # they raise arrives later — anything left over is the user moving away,
        # which drops the selection.
        self._anchor: Coordinate | None = None
        self._selected: set[Coordinate] = set()
        self._extending = 0
        # How many lines each row is given. Also only a way of looking at the
        # sheet, but a taller row has room to show more of a multi-line value.
        self.row_size = DEFAULT_ROW_SIZE
        self.column_width = DEFAULT_COLUMN_WIDTH
        self.overflow = DEFAULT_OVERFLOW

    # ------------------------------------------------------------------ setup

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="grid", cursor_type="cell", zebra_stripes=True)
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        saved = config.load()
        theme = saved.get("theme")
        self.theme = theme if theme in self.available_themes else DEFAULT_THEME
        self._theme_loaded = True
        if saved.get("row_size") in ROW_SIZES:
            self.row_size = saved["row_size"]
        if saved.get("column_width") in COLUMN_WIDTHS:
            self.column_width = saved["column_width"]
        if saved.get("overflow") in OVERFLOWS:
            self.overflow = saved["overflow"]
        table = self.query_one("#grid", DataTable)
        table.show_row_labels = True
        table.focus()
        self.reload()

    def watch_theme(self, theme: str) -> None:
        """Remember whatever theme was picked, wherever it was picked from."""
        if self._theme_loaded:
            config.save(theme=theme)

    @property
    def table(self) -> DataTable:
        return self.query_one("#grid", DataTable)

    # ------------------------------------------------------- grid <-> data

    def _coordinate(self, record: int, field: int) -> Coordinate:
        """Where a given record and column sit on screen."""
        return Coordinate(field, record) if self.flipped else Coordinate(record, field)

    def _indices(self, coordinate: Coordinate | None = None) -> tuple[int, int]:
        """The record and column a screen position points at."""
        at = self.table.cursor_coordinate if coordinate is None else coordinate
        return (at.column, at.row) if self.flipped else (at.row, at.column)

    # ---------------------------------------------------------------- drawing

    def reload(self, cursor: Coordinate | None = None) -> None:
        """Redraw the whole grid from the database."""
        table = self.table
        previous = cursor or table.cursor_coordinate
        self._anchor = None
        self._selected = set()
        table.clear(columns=True)

        self._columns = self.sheet.columns()
        self._rows = self.sheet.rows()

        if self.flipped:
            # A grid column is a record: size it from that record's own values.
            drawn = {
                row.id: [
                    self._cell(column, row.values.get(column.id))
                    for column in self._columns
                ]
                for row in self._rows
            }
            widths = []
            for number, row in enumerate(self._rows, start=1):
                label = Text(str(number), "dim")
                width = self._column_width(label, drawn[row.id])
                widths.append(width)
                table.add_column(label, key=str(row.id), width=width)
            for index, column in enumerate(self._columns):
                cells = [drawn[row.id][index] for row in self._rows]
                height = self._row_height(cells, widths)
                cells = self._centre(cells, widths, height)
                table.add_row(
                    *cells,
                    height=height,
                    key=str(column.id),
                    label=_centred(_field_label(column), height),
                )
        else:
            drawn = {
                column.id: [
                    self._cell(column, row.values.get(column.id)) for row in self._rows
                ]
                for column in self._columns
            }
            widths = []
            for column in self._columns:
                label = _field_label(column)
                width = self._column_width(label, drawn[column.id])
                widths.append(width)
                table.add_column(label, key=str(column.id), width=width)
            for number, row in enumerate(self._rows, start=1):
                cells = [drawn[column.id][number - 1] for column in self._columns]
                height = self._row_height(cells, widths)
                cells = self._centre(cells, widths, height)
                table.add_row(
                    *cells,
                    height=height,
                    key=str(row.id),
                    label=_centred(Text(str(number), "dim"), height),
                )

        if self._rows and self._columns:
            record, field = self._indices(previous)
            table.cursor_coordinate = self._coordinate(
                min(record, len(self._rows) - 1), min(field, len(self._columns) - 1)
            )
        self._update_status()

    def _wrapping(self) -> bool:
        """Wrapping needs a cap to wrap against, so both settings have to agree."""
        return self.overflow == "wrap" and COLUMN_WIDTHS[self.column_width] is not None

    def _cell(self, column: Column, value: Any) -> Text:
        """A value drawn for the row height that is in force."""
        if self._wrapping():
            # The row will be grown to fit this, so nothing is squeezed or cut.
            return _render(column, value, MAX_WRAP_LINES)
        height = ROW_SIZES[self.row_size]
        cell = _centred(_render(column, value, height), height)
        if COLUMN_WIDTHS[self.column_width] is not None:
            cell.no_wrap = True
            cell.overflow = "ellipsis"
        return cell

    def _row_height(self, cells: list[Text], widths: list[int | None]) -> int:
        """How many lines a row needs once its values have wrapped."""
        if not self._wrapping():
            return ROW_SIZES[self.row_size]
        needed = max(
            (_lines_needed(cell, width) for cell, width in zip(cells, widths)),
            default=1,
        )
        return min(max(1, needed), MAX_WRAP_LINES)

    def _centre(
        self, cells: list[Text], widths: list[int | None], height: int
    ) -> list[Text]:
        """Sit each value in the middle of the row its tallest neighbour set."""
        if not self._wrapping():
            return cells  # _cell has already centred these against a fixed height
        return [
            _centred(cell, height, _lines_needed(cell, width))
            for cell, width in zip(cells, widths)
        ]

    def _column_width(self, label: Text, cells: list[Text]) -> int | None:
        """A cap, not a width: a column narrower than the cap keeps its own size."""
        cap = COLUMN_WIDTHS[self.column_width]
        if cap is None:
            return None
        natural = max([_widest(label)] + [_widest(cell) for cell in cells])
        return max(1, min(natural, cap))

    def _update_status(self) -> None:
        columns, rows = self.sheet.counts()
        column = self.current_column()
        shape = f"{rows} {_plural(rows, 'row')} × {columns} {_plural(columns, 'column')}"
        if self.flipped:
            shape += ", flipped"
        detail = ""
        region = self._selection_region()
        if region is not None:
            start, end = region
            detail += (
                f"  ·  {end.row - start.row + 1} × {end.column - start.column + 1}"
                " selected"
            )
        if column is not None:
            detail += f"  ·  {column.name}: {column.type.label}"
            if column.type is ColumnType.SELECT:
                detail += f" ({', '.join(column.options) or 'no options'})"
        self.query_one("#status", Static).update(
            Text.from_markup(
                f"[dim]{self.sheet.path.name}  ·  {shape}{detail}  ·  ? for help[/]"
            )
        )

    # -------------------------------------------------------------- selection

    def current_column(self) -> Column | None:
        _, field = self._indices()
        return self._columns[field] if 0 <= field < len(self._columns) else None

    def current_row(self) -> Row | None:
        record, _ = self._indices()
        return self._rows[record] if 0 <= record < len(self._rows) else None

    def _cell_at(self, coordinate: Coordinate) -> tuple[Row | None, Column | None]:
        record, field = self._indices(coordinate)
        row = self._rows[record] if 0 <= record < len(self._rows) else None
        column = self._columns[field] if 0 <= field < len(self._columns) else None
        return row, column

    # ------------------------------------------------------------- selection

    def _selection_region(self) -> tuple[Coordinate, Coordinate] | None:
        """The corners of the selected block, or None when it is a single cell."""
        if self._anchor is None:
            return None
        at = self.table.cursor_coordinate
        top, bottom = sorted((self._anchor.row, at.row))
        left, right = sorted((self._anchor.column, at.column))
        if (top, left) == (bottom, right):
            return None
        return Coordinate(top, left), Coordinate(bottom, right)

    def _selected_cells(self) -> set[Coordinate]:
        region = self._selection_region()
        if region is None:
            return set()
        start, end = region
        return {
            Coordinate(row, column)
            for row in range(start.row, end.row + 1)
            for column in range(start.column, end.column + 1)
        }

    def _refresh_selection(self) -> None:
        wanted = self._selected_cells()
        for coordinate in self._selected ^ wanted:  # only what changed
            self._repaint(coordinate, coordinate in wanted)
        self._selected = wanted
        self._update_status()

    def _repaint(self, coordinate: Coordinate, selected: bool) -> None:
        row, column = self._cell_at(coordinate)
        if row is None or column is None:
            return
        text = self._cell(column, row.values.get(column.id))
        if self._wrapping():
            table = self.table
            text = _centred(
                text,
                table.ordered_rows[coordinate.row].height,
                _lines_needed(text, table.ordered_columns[coordinate.column].width),
            )
        if selected:
            text = text.copy()
            text.stylize(f"on {self.theme_variables.get('primary-darken-2', 'blue')}")
        self.table.update_cell_at(coordinate, text)

    def action_extend(self, down: int, across: int) -> None:
        """Grow the selection with shift+arrows, anchored where it started."""
        table = self.table
        if not table.rows or not table.columns:
            return
        before = table.cursor_coordinate
        if self._anchor is None:
            self._anchor = before
        target = Coordinate(
            max(0, min(before.row + down, len(table.rows) - 1)),
            max(0, min(before.column + across, len(table.columns) - 1)),
        )
        if target != before:
            self._extending += 1
            table.cursor_coordinate = target
        self._refresh_selection()

    def action_clear_selection(self) -> None:
        self._clear_selection()

    def _clear_selection(self) -> None:
        self._anchor = None
        self._extending = 0
        for coordinate in self._selected:
            self._repaint(coordinate, False)
        self._selected = set()

    def action_flip(self) -> None:
        """Swap which way the sheet is drawn, keeping the cursor on the same cell."""
        record, field = self._indices()
        self.flipped = not self.flipped
        self.reload(self._coordinate(record, field))
        self.notify(
            "Records run across the screen." if self.flipped else "Back to normal."
        )

    def action_cycle_column_width(self) -> None:
        """Small, large, or let columns take whatever they need."""
        widths = list(COLUMN_WIDTHS)
        self.column_width = widths[
            (widths.index(self.column_width) + 1) % len(widths)
        ]
        config.save(column_width=self.column_width)
        self.reload()
        cap = COLUMN_WIDTHS[self.column_width]
        self.notify(
            "Columns take the width they need."
            if cap is None
            else f"Columns stop at {cap} characters ({self.column_width})."
        )

    def action_toggle_overflow(self) -> None:
        """Wrap a too-long value over the row, or cut it with an ellipsis."""
        self.overflow = OVERFLOWS[(OVERFLOWS.index(self.overflow) + 1) % len(OVERFLOWS)]
        config.save(overflow=self.overflow)
        self.reload()
        if COLUMN_WIDTHS[self.column_width] is None:
            self.notify(
                f"Long values {self.overflow} — but nothing is capped, so press w first.",
                severity="warning",
            )
        elif self.overflow == "wrap":
            self.notify("Long values wrap, and rows grow to fit them.")
        else:
            self.notify(f"Long values end in an ellipsis. Rows are {self.row_size}.")

    def action_toggle_row_size(self) -> None:
        """Swap the row height for the other one."""
        sizes = list(ROW_SIZES)
        self.row_size = sizes[(sizes.index(self.row_size) + 1) % len(sizes)]
        config.save(row_size=self.row_size)
        self.reload()
        if self._wrapping():
            self.notify(
                f"Rows are {self.row_size} — but wrapping is on, so they grow to fit."
                " Press W for ellipsis.",
                severity="warning",
            )
        else:
            self.notify(f"Rows are {self.row_size} now.")

    @on(DataTable.CellHighlighted)
    def cell_highlighted(self) -> None:
        if self._extending:
            self._extending -= 1
        else:
            self._clear_selection()
        self._update_status()

    # ----------------------------------------------------------- cell editing

    @on(DataTable.CellSelected)
    def cell_selected(self) -> None:
        self.action_edit_cell()

    def action_edit_cell(self) -> None:
        column, row = self.current_column(), self.current_row()
        if column is None or row is None:
            self.notify("Nothing to edit yet.", severity="warning")
            return
        value = row.values.get(column.id)

        if column.type is ColumnType.BOOLEAN:
            self._write(row, column, not bool(value))
            return

        def done(result: tuple[bool, Any] | None) -> None:
            if result and result[0]:
                self._write(row, column, result[1])

        screen = (
            PickScreen(column, value)
            if column.type is ColumnType.SELECT
            else CellEditScreen(column, value)
        )
        self.push_screen(screen, done)

    def action_clear_cell(self) -> None:
        column, row = self.current_column(), self.current_row()
        if column is None or row is None:
            return
        self._write(row, column, None)

    def _write(self, row: Row, column: Column, value: Any) -> None:
        self.sheet.set_cell(row.id, column.id, value)
        row.values[column.id] = value
        if self._wrapping():
            # The value may need a different number of lines than the row has,
            # and only a redraw can change that. Nothing structural moved, so
            # the selection is put back afterwards.
            anchor = self._anchor
            self.reload()
            if anchor is not None:
                # Redrawing moves the cursor, and the message that raises
                # clears the selection — so put it back behind that message.
                def restore(anchor: Coordinate = anchor) -> None:
                    self._anchor = anchor
                    self._refresh_selection()

                self.call_after_refresh(restore)
        else:
            # Repaint rather than redraw, so a selection keeps its highlight.
            at = self.table.cursor_coordinate
            self._repaint(at, at in self._selected)
        self._update_status()

    def action_edit_row(self) -> None:
        row = self.current_row()
        if row is None or not self._columns:
            self.notify("Nothing to edit yet.", severity="warning")
            return
        number = self._rows.index(row) + 1

        def done(values: dict[int, Any] | None) -> None:
            if values is None:
                return
            changed = [
                (column_id, value)
                for column_id, value in values.items()
                if value != row.values.get(column_id)
            ]
            for column_id, value in changed:
                self.sheet.set_cell(row.id, column_id, value)
            self.reload()
            self.notify(
                f"Saved row {number}." if changed else f"Row {number} unchanged."
            )

        self.push_screen(RowFormScreen(self._columns, row, number, len(self._rows)), done)

    # ------------------------------------------------------------------ copy

    def action_copy_cell(self) -> None:
        """Copy the selected block, or just the cell when nothing is selected."""
        region = self._selection_region()
        if region is not None:
            start, end = region
            block = [
                [self._text_at(Coordinate(row, column))
                 for column in range(start.column, end.column + 1)]
                for row in range(start.row, end.row + 1)
            ]
            down = end.row - start.row + 1
            across = end.column - start.column + 1
            self._copy(format_block(block), f"{down} × {across} cells")
            return

        column, row = self.current_column(), self.current_row()
        if column is None or row is None:
            return
        value = row.values.get(column.id)
        self._copy(display(column.type, value), f"{column.name} cell")

    def _text_at(self, coordinate: Coordinate) -> str:
        row, column = self._cell_at(coordinate)
        if row is None or column is None:
            return ""
        return display(column.type, row.values.get(column.id))

    def action_copy_row(self) -> None:
        """Put the whole row on the clipboard as a spreadsheet would write it."""
        row = self.current_row()
        if row is None or not self._columns:
            return
        values = [display(c.type, row.values.get(c.id)) for c in self._columns]
        # Copy the shape that is on screen: a record reads down the screen when
        # the view is flipped, and paste reads it back the same way.
        block = [[value] for value in values] if self.flipped else [values]
        self._copy(format_block(block), f"row {self._rows.index(row) + 1}")

    def _copy(self, text: str, what: str) -> None:
        self.copy_to_clipboard(text)  # OSC 52 — the one that works over ssh
        to_system_clipboard(text)  # and pbcopy and friends, for terminals that ignore it
        if text.strip():
            self.notify(f"Copied {what}.")
        else:
            self.notify(f"Nothing to copy — {what} is empty.", severity="warning")

    # ---------------------------------------------------------------- export

    def action_export(self) -> None:
        """Write the sheet out as a CSV, whichever way it happens to be drawn."""
        if not self._columns:
            self.notify("Nothing to export yet.", severity="warning")
            return

        def chosen(path: str | None) -> None:
            if path is None:
                return
            target = Path(path).expanduser()
            if target.exists():
                self.push_screen(
                    ConfirmScreen(f"{target.name} already exists. Overwrite it?", confirm="Overwrite"),
                    lambda confirmed: self._export(target) if confirmed else None,
                )
            else:
                self._export(target)

        self.push_screen(ExportScreen(str(self.sheet.path.with_suffix(".csv"))), chosen)

    def _export(self, target: Path) -> None:
        try:
            written = write_csv(target, self._columns, self._rows)
        except OSError as error:
            self.notify(f"Could not write it: {error}", severity="error")
            return
        rows = len(self._rows)
        self.notify(
            f"Exported {rows} {_plural(rows, 'row')} to {_short_path(written)}."
        )

    # ----------------------------------------------------------------- paste

    def on_paste(self, event: events.Paste) -> None:
        """Drop a block of cells copied from a spreadsheet in at the cursor."""
        if self.screen is not self.screen_stack[0]:
            return
        block = parse_block(event.text)
        if not block:
            return
        event.stop()
        if not self._columns:
            self.notify("Add a column first (c).", severity="warning")
            return

        record_start, field_start = self._indices()
        across = max(len(line) for line in block)
        # A block always spills right and down the screen, so which of its axes
        # is records and which is columns depends on which way the grid is drawn.
        record_span, field_span = (
            (across, len(block)) if self.flipped else (len(block), across)
        )
        columns = self._columns[field_start : field_start + field_span]
        clipped = field_span - len(columns)
        new_rows = max(0, record_start + record_span - len(self._rows))

        def cell(record_offset: int, field_offset: int) -> str:
            line = block[field_offset if self.flipped else record_offset]
            index = record_offset if self.flipped else field_offset
            return line[index] if index < len(line) else ""

        plan = [
            (record_start + record_offset, column, cell(record_offset, field_offset))
            for record_offset in range(record_span)
            for field_offset, column in enumerate(columns)
        ]

        overwrites = 0
        for record_index, column, raw in plan:
            if record_index >= len(self._rows):
                continue
            try:
                value = parse(column.type, raw, column.options)
            except ValidationError:
                continue
            current = self._rows[record_index].values.get(column.id)
            if current is not None and value != current:
                overwrites += 1

        shape = (
            f"{record_span} {_plural(record_span, 'row')}"
            f" × {len(columns)} {_plural(len(columns), 'column')}"
        )

        def apply(confirmed: bool | None = True) -> None:
            if confirmed:
                self._apply_paste(plan, shape, new_rows, clipped)

        if overwrites:
            self.push_screen(
                ConfirmScreen(
                    f"Paste {shape} here? It replaces {overwrites} filled "
                    f"{_plural(overwrites, 'cell')}.",
                    confirm="Paste",
                ),
                apply,
            )
        else:
            apply()

    def _apply_paste(self, plan, shape: str, new_rows: int, clipped: int) -> None:
        for _ in range(new_rows):
            self.sheet.add_row()
        rows = self.sheet.rows()

        skipped = 0
        for record_index, column, raw in plan:
            try:
                value = parse(column.type, raw, column.options)
            except ValidationError:
                skipped += 1
                continue
            self.sheet.set_cell(rows[record_index].id, column.id, value)

        self.reload()
        parts = [f"Pasted {shape}"]
        if new_rows:
            parts.append(f"{new_rows} {_plural(new_rows, 'row')} added")
        if skipped:
            parts.append(
                f"{skipped} {_plural(skipped, 'value')} did not fit the column type"
            )
        if clipped:
            parts.append(f"{clipped} {_plural(clipped, 'column')} ran off the end")
        self.notify(
            " · ".join(parts), severity="warning" if skipped or clipped else "information"
        )

    # ------------------------------------------------------------------- rows

    def action_add_row(self) -> None:
        if not self._columns:
            self.notify("Add a column first (c).", severity="warning")
            return
        self.sheet.add_row()
        _, field = self._indices()
        self.reload(self._coordinate(len(self._rows), field))

    def action_insert_row(self) -> None:
        if not self._columns:
            self.notify("Add a column first (c).", severity="warning")
            return
        row = self.current_row()
        record, field = self._indices()
        self.sheet.add_row(after_position=row.position if row else None)
        self.reload(self._coordinate(record + 1, field))

    def action_delete_row(self) -> None:
        row = self.current_row()
        if row is None:
            return
        number = self._rows.index(row) + 1

        def done(confirmed: bool | None) -> None:
            if confirmed:
                self.sheet.delete_row(row.id)
                self.reload()
                self.notify(f"Deleted row {number}.")

        # There is nothing to lose in an empty row, so don't ask about it.
        if all(value is None for value in row.values.values()):
            done(True)
            return
        self.push_screen(ConfirmScreen(f"Delete row {number}?"), done)

    # ---------------------------------------------------------------- columns

    def action_add_column(self) -> None:
        def done(result: tuple[str, ColumnType, list[str]] | None) -> None:
            if result is None:
                return
            name, coltype, options = result
            record, _ = self._indices()
            self.sheet.add_column(name, coltype, options)
            self.reload(self._coordinate(record, len(self._columns)))
            self.notify(f"Added column {name!r} ({coltype.label}).")

        self.push_screen(ColumnScreen(), done)

    def action_edit_column(self) -> None:
        column = self.current_column()
        if column is None:
            self.notify("No column here.", severity="warning")
            return

        def done(result: tuple[str, ColumnType, list[str]] | None) -> None:
            if result is None:
                return
            name, coltype, options = result
            dropped = self.sheet.update_column(column.id, name, coltype, options)
            self.reload()
            if dropped:
                self.notify(
                    f"{dropped} value(s) did not fit {coltype.label} and were cleared.",
                    severity="warning",
                )
            else:
                self.notify(f"Updated column {name!r}.")

        self.push_screen(ColumnScreen(column), done)

    def action_delete_column(self) -> None:
        column = self.current_column()
        if column is None:
            return

        def done(confirmed: bool | None) -> None:
            if confirmed:
                self.sheet.delete_column(column.id)
                self.reload()
                self.notify(f"Deleted column {column.name!r}.")

        self.push_screen(
            ConfirmScreen(f"Delete column {column.name!r} and all its values?"), done
        )

    def action_move_column(self, offset: int) -> None:
        column = self.current_column()
        if column is None:
            return
        record, field = self._indices()
        if self.sheet.move_column(column.id, offset):
            self.reload(self._coordinate(record, field + offset))

    # ------------------------------------------------------------------ misc

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def on_unmount(self) -> None:
        self.sheet.close()


def _field_label(column: Column) -> Text:
    return Text.assemble((column.name, "bold"), (f"  {column.type.tag}", "dim"))


def _widest(text: Text) -> int:
    """How many columns the longest line of a value needs."""
    return max((cell_len(line) for line in text.plain.split("\n")), default=0)


def _plural(count: int, word: str) -> str:
    return word if count == 1 else word + "s"


def _short_path(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _fit(text: str, lines: int) -> Text:
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


def _lines_needed(cell: Text, width: int | None) -> int:
    """How many screen lines a value takes once it has wrapped to `width`."""
    return sum(
        max(1, ceil(cell_len(line) / max(1, width or 1)))
        for line in cell.plain.split("\n")
    )


def _centred(cell: Text, height: int, lines: int | None = None) -> Text:
    """Sit a value in the middle of its row rather than at the top of it."""
    occupied = cell.plain.count("\n") + 1 if lines is None else lines
    above = (height - occupied) // 2
    return Text("\n" * above) + cell if above > 0 else cell


def _render(column: Column, value: Any, lines: int) -> Text:
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
        return Text(display(column.type, value), "yellow")
    return _fit(display(column.type, value), lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print(f"usage: gridly [FILE]\n\nOpens FILE (default: ./{DEFAULT_FILE}), creating it if needed.")
        return 0
    GridlyApp(args[0] if args else DEFAULT_FILE).run()
    return 0
