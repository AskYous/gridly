"""Gridly — a terminal spreadsheet with typed columns."""

from __future__ import annotations

import sys
from dataclasses import replace
from functools import partial
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.message import Message
from textual.screen import Screen
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Header, Static

from . import config
from .coltypes import ColumnType, ValidationError, color_style, display, parse
from .screens import (
    CellEditScreen,
    ColumnScreen,
    ConfirmScreen,
    ExportScreen,
    HelpScreen,
    PickScreen,
    RowFormScreen,
    SettingsScreen,
)
from .clipboard import format_block, parse_block, to_system_clipboard
from .csvfile import write_csv
from .picker import choose_sheet
from .store import Column, Row, Sheet
from .appearance import (
    COLUMN_WIDTHS,
    OVERFLOWS,
    ROW_SIZES,
    Appearance,
    centred,
    field_label,
    lines_needed,
    widest,
)

DEFAULT_FILE = "sheet.gridly"

# What a first run opens with, before anyone has pressed t.
DEFAULT_THEME = "rose-pine"

class Grid(DataTable):
    """A DataTable that says when its own width changed.

    The app's resize event arrives before the table has been laid out again, so
    reading the table's width there gives the size it is about to stop being.
    """

    class Resized(Message):
        pass

    def on_resize(self, event: events.Resize) -> None:
        self.post_message(self.Resized())


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
        Binding("s", "toggle_row_size", "Size", show=False),
        Binding("w", "cycle_column_width", "Width", show=False),
        Binding("W", "toggle_overflow", "Wrap", show=False),
        Binding("u", "undo", "Undo", show=False),
        Binding("U", "redo", "Redo", show=False),
        Binding("y", "copy_cell", "Copy", show=False),
        Binding("Y", "copy_row", "Copy row", show=False),
        Binding("E", "export", "Export", show=False),
        Binding("backspace", "clear_cell", "Clear", show=False),
        Binding("a", "add_row", "+Row"),
        Binding("i", "insert_row", "Insert row", show=False),
        Binding("D", "duplicate_row", "Duplicate row", show=False),
        Binding("d", "delete_row", "-Row", show=False),
        Binding("c", "add_column", "+Col"),
        Binding("e", "edit_column", "Edit col", show=False),
        Binding("x", "delete_column", "-Col", show=False),
        Binding("left_square_bracket", "move_column(-1)", "Move col left", show=False),
        Binding("right_square_bracket", "move_column(1)", "Move col right", show=False),
        Binding("comma", "settings", "Settings", key_display=","),
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
        ("duplicate_row", "Duplicate row", "Copy this row into a new one below it", True),
        ("delete_row", "Delete row", "Remove the row under the cursor", True),
        ("add_column", "Add column", "Define a new column and its type", True),
        ("edit_column", "Edit column", "Rename, retype or relist the current column", True),
        ("delete_column", "Delete column", "Remove the column and every value in it", True),
        ("move_column(-1)", "Move column left", "Swap it with the column before it", True),
        ("move_column(1)", "Move column right", "Swap it with the column after it", True),
        ("copy_cell", "Copy cell or selection", "To the clipboard, tab separated", True),
        ("copy_row", "Copy row", "The whole record, tab separated", True),
        ("export", "Export to CSV", "Write the sheet out as a file", True),
        ("undo", "Undo", "Take back the last change", True),
        ("redo", "Redo", "Put back what undo took away", True),
        ("toggle_row_size", "Toggle row height", "Between one line and three", True),
        ("settings", "Settings", "Width, wrapping, row height and theme", True),
        ("cycle_column_width", "Cycle column width", "Large, fit to the screen, small, or uncapped", True),
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
        self.appearance = Appearance.load()
        # A keyboard selection: where it started and which cells it covers now.
        # Cursor moves we made ourselves are counted, because the CellHighlighted
        # they raise arrives later — anything left over is the user moving away,
        # which drops the selection.
        self._cycle_timer: Timer | None = None
        self._anchor: Coordinate | None = None
        self._selected: set[Coordinate] = set()
        self._extending = 0
        # How many lines each row is given. Also only a way of looking at the
        # sheet, but a taller row has room to show more of a multi-line value.

    # ------------------------------------------------------------------ setup

    def compose(self) -> ComposeResult:
        yield Header()
        yield Grid(id="grid", cursor_type="cell", zebra_stripes=True)
        yield Static("", id="status")
        yield Footer(compact=True)

    def on_mount(self) -> None:
        saved = config.load()
        theme = saved.get("theme")
        self.theme = theme if theme in self.available_themes else DEFAULT_THEME
        self._theme_loaded = True
        config.remember(self.sheet.path)
        table = self.query_one("#grid", DataTable)
        table.show_row_labels = True
        table.focus()
        self.reload()
        if self.appearance.column_width == "fit":
            # The table has no size until it has been laid out once.
            self.call_after_refresh(self.reload)

    @on(Grid.Resized)
    def grid_resized(self) -> None:
        """A fitted table is sized against the viewport, so it follows it."""
        if self.appearance.column_width == "fit" and self._columns:
            self.reload()

    def watch_theme(self, theme: str) -> None:
        """Remember whatever theme was picked, wherever it was picked from."""
        if self._theme_loaded:
            config.save(theme=theme)

    @property
    def table(self) -> DataTable:
        return self.query_one("#grid", DataTable)


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

        drawn = {
            column.id: [
                self.appearance.cell(column, row.values.get(column.id))
                for row in self._rows
            ]
            for column in self._columns
        }
        labels = [field_label(column) for column in self._columns]
        widths = self.appearance.widths(
            labels,
            [drawn[column.id] for column in self._columns],
            len(str(len(self._rows))),
            *self._room(),
        )
        for label, column, width in zip(labels, self._columns, widths):
            table.add_column(label, key=str(column.id), width=width)
        for number, row in enumerate(self._rows, start=1):
            cells = [drawn[column.id][number - 1] for column in self._columns]
            height = self.appearance.row_height(cells, widths)
            cells = self.appearance.centre(cells, widths, height)
            table.add_row(
                *cells,
                height=height,
                key=str(row.id),
                label=centred(Text(str(number), "dim"), height),
            )

        if self._rows and self._columns:
            record, field = previous.row, previous.column
            table.cursor_coordinate = Coordinate(
                min(record, len(self._rows) - 1), min(field, len(self._columns) - 1)
            )
        self._update_status()

    def _room(self) -> tuple[int, int]:
        """How much width there is to share out, and what each column costs."""
        table = self.table
        return table.content_size.width or table.size.width, 2 * table.cell_padding

    def _update_status(self) -> None:
        if self._cycle_timer is not None:
            return  # a cycle is on show; it puts the status back when it ends
        columns, rows = self.sheet.counts()
        column = self.current_column()
        shape = f"{rows} {_plural(rows, 'row')} × {columns} {_plural(columns, 'column')}"
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
        line = Text.from_markup(f"[dim]{self.sheet.path.name}  ·  {shape}{detail}[/]")
        if column is not None and column.type is ColumnType.SELECT:
            line.append(" (", "dim")
            for index, option in enumerate(column.options):
                if index:
                    line.append(", ", "dim")
                line.append(option, color_style(column.color(option)) or "dim")
            if not column.options:
                line.append("no options", "dim")
            line.append(")", "dim")
        line.append("  ·  ? for help", "dim")
        self.query_one("#status", Static).update(line)

    def _show_cycle(self, title: str, options: tuple[str, ...], current: str) -> None:
        """Put the whole cycle on screen so it is clear what the key steps through."""
        strip = Text.assemble((f"{title}  ", "dim"))
        for option in options:
            if option == current:
                strip.append(f" {option} ", "reverse bold")
            else:
                strip.append(f" {option} ", "dim")
        if self._cycle_timer is not None:
            self._cycle_timer.stop()
        self.query_one("#status", Static).update(strip)
        self._cycle_timer = self.set_timer(3, self._end_cycle)

    def _end_cycle(self) -> None:
        self._cycle_timer = None
        self._update_status()

    # -------------------------------------------------------------- selection

    def current_column(self) -> Column | None:
        field = self.table.cursor_coordinate.column
        return self._columns[field] if 0 <= field < len(self._columns) else None

    def current_row(self) -> Row | None:
        record = self.table.cursor_coordinate.row
        return self._rows[record] if 0 <= record < len(self._rows) else None

    def _cell_at(self, coordinate: Coordinate) -> tuple[Row | None, Column | None]:
        record, field = coordinate.row, coordinate.column
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
        text = self.appearance.cell(column, row.values.get(column.id))
        if self.appearance.wrapping:
            table = self.table
            text = centred(
                text,
                table.ordered_rows[coordinate.row].height,
                lines_needed(text, table.ordered_columns[coordinate.column].width),
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

    def action_settings(self) -> None:
        """Every view setting in one place, rather than four keys to remember."""

        def done(chosen: tuple[Appearance, str] | None) -> None:
            if chosen is None:
                return
            view, theme = chosen
            self.appearance = view
            self.appearance.save()
            self.theme = theme
            self.reload()
            self.notify("Settings saved.")

        self.push_screen(
            SettingsScreen(
                replace(self.appearance), self.theme, sorted(self.available_themes),
                DEFAULT_THEME,
            ),
            done,
        )


    def action_cycle_column_width(self) -> None:
        """Small, large, or let columns take whatever they need."""
        self.appearance.cycle_column_width()
        self.reload()
        self._show_cycle("column width", COLUMN_WIDTHS, self.appearance.column_width)

    def action_toggle_overflow(self) -> None:
        """Wrap a too-long value over the row, or cut it with an ellipsis."""
        self.appearance.cycle_overflow()
        self.reload()
        self._show_cycle("long values", OVERFLOWS, self.appearance.overflow)
        if not self.appearance.capped:
            self.notify(
                f"Long values {self.appearance.overflow} — but nothing is capped, so press w first.",
                severity="warning",
            )

    def action_toggle_row_size(self) -> None:
        """Swap the row height for the other one."""
        self.appearance.cycle_row_size()
        self.reload()
        self._show_cycle("row height", tuple(ROW_SIZES), self.appearance.row_size)
        if self.appearance.wrapping:
            self.notify(
                "Wrapping is on, so rows grow to fit whatever they hold."
                " Press W for a fixed height.",
                severity="warning",
            )

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
        if self.appearance.wrapping:
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
            with self.sheet.change(f"edit row {number}"):
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
        self._copy(format_block([values]), f"row {self._rows.index(row) + 1}")

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

        at = self.table.cursor_coordinate
        record_start, field_start = at.row, at.column
        record_span = len(block)
        field_span = max(len(line) for line in block)
        columns = self._columns[field_start : field_start + field_span]
        clipped = field_span - len(columns)
        new_rows = max(0, record_start + record_span - len(self._rows))

        def cell(record_offset: int, field_offset: int) -> str:
            line = block[record_offset]
            return line[field_offset] if field_offset < len(line) else ""

        plan = [
            (record_start + record_offset, column, cell(record_offset, field_offset))
            for record_offset in range(record_span)
            for field_offset, column in enumerate(columns)
        ]

        shape = (
            f"{record_span} {_plural(record_span, 'row')}"
            f" × {len(columns)} {_plural(len(columns), 'column')}"
        )
        self._apply_paste(plan, shape, new_rows, clipped)

    def _apply_paste(self, plan, shape: str, new_rows: int, clipped: int) -> None:
        skipped = 0
        with self.sheet.change(f"paste {shape}"):
            for _ in range(new_rows):
                self.sheet.add_row()
            rows = self.sheet.rows()
            for record_index, column, raw in plan:
                try:
                    value = parse(column.type, raw, column.options)
                except ValidationError:
                    skipped += 1
                    continue
                self.sheet.set_cell(rows[record_index].id, column.id, value)

        self.reload()
        parts = [f"Pasted {shape}, u to undo"]
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
        field = self.table.cursor_coordinate.column
        self.reload(Coordinate(len(self._rows), field))

    def action_insert_row(self) -> None:
        if not self._columns:
            self.notify("Add a column first (c).", severity="warning")
            return
        row = self.current_row()
        at = self.table.cursor_coordinate
        record, field = at.row, at.column
        self.sheet.add_row(after_position=row.position if row else None)
        self.reload(Coordinate(record + 1, field))

    def action_undo(self) -> None:
        label = self.sheet.undo()
        if label is None:
            self.notify("Nothing to undo.", severity="warning")
            return
        self.reload()
        self.notify(f"Undid {label}. U puts it back.")

    def action_redo(self) -> None:
        label = self.sheet.redo()
        if label is None:
            self.notify("Nothing to redo.", severity="warning")
            return
        self.reload()
        self.notify(f"Redid {label}.")

    def action_duplicate_row(self) -> None:
        """Copy the row under the cursor and land on the copy."""
        row = self.current_row()
        if row is None:
            self.notify("Nothing to duplicate yet.", severity="warning")
            return
        number = self._rows.index(row) + 1
        at = self.table.cursor_coordinate
        record, field = at.row, at.column
        self.sheet.duplicate_row(row.id)
        self.reload(Coordinate(record + 1, field))
        self.notify(f"Row {number} copied to row {number + 1}.")

    def action_delete_row(self) -> None:
        row = self.current_row()
        if row is None:
            return
        number = self._rows.index(row) + 1
        self.sheet.delete_row(row.id)
        self.reload()
        self.notify(f"Deleted row {number}. u to undo.")

    # ---------------------------------------------------------------- columns

    def action_add_column(self) -> None:
        def done(result: tuple[str, ColumnType, list[str], dict[str, str]] | None) -> None:
            if result is None:
                return
            name, coltype, options, colors = result
            record = self.table.cursor_coordinate.row
            self.sheet.add_column(name, coltype, options, colors)
            self.reload(Coordinate(record, len(self._columns)))
            self.notify(f"Added column {name!r} ({coltype.label}).")

        self.push_screen(ColumnScreen(), done)

    def action_edit_column(self) -> None:
        column = self.current_column()
        if column is None:
            self.notify("No column here.", severity="warning")
            return

        def done(result: tuple[str, ColumnType, list[str], dict[str, str]] | None) -> None:
            if result is None:
                return
            name, coltype, options, colors = result
            dropped = self.sheet.update_column(
                column.id, name, coltype, options, colors
            )
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

        self.sheet.delete_column(column.id)
        self.reload()
        self.notify(f"Deleted column {column.name!r}. u to undo.")

    def action_move_column(self, offset: int) -> None:
        column = self.current_column()
        if column is None:
            return
        at = self.table.cursor_coordinate
        record, field = at.row, at.column
        if self.sheet.move_column(column.id, offset):
            self.reload(Coordinate(record, field + offset))

    # ------------------------------------------------------------------ misc

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def on_unmount(self) -> None:
        self.sheet.close()

def _plural(count: int, word: str) -> str:
    return word if count == 1 else word + "s"


def _short_path(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)

def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print(
            f"usage: gridly [FILE]\n\n"
            f"Opens FILE, creating it if needed. With no FILE, offers the sheets you\n"
            f"had open lately, or ./{DEFAULT_FILE} if there are none yet."
        )
        return 0

    if args:
        path: str | None = args[0]
    elif config.recent():
        path = choose_sheet(DEFAULT_FILE)
        if path is None:
            return 0
    else:
        path = DEFAULT_FILE  # nothing to choose between yet

    GridlyApp(path).run()
    return 0
