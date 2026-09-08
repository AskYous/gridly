"""Gridly — a terminal spreadsheet with typed columns."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Static

from . import config
from .coltypes import ColumnType, ValidationError, display, parse
from .screens import (
    CellEditScreen,
    ColumnScreen,
    ConfirmScreen,
    HelpScreen,
    PickScreen,
    RowFormScreen,
)
from .paste import parse_block
from .store import Column, Row, Sheet

DEFAULT_FILE = "sheet.gridly"


class GridlyApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "Gridly"

    # Set once the saved theme has been read, so the watcher below doesn't
    # write the default theme over it on the way up.
    _theme_loaded = False

    BINDINGS = [
        Binding("space", "edit_cell", "Edit"),
        Binding("f", "edit_row", "Form"),
        Binding("backspace", "clear_cell", "Clear"),
        Binding("a", "add_row", "+Row"),
        Binding("i", "insert_row", "Insert row", show=False),
        Binding("d", "delete_row", "-Row"),
        Binding("c", "add_column", "+Col"),
        Binding("e", "edit_column", "Edit col"),
        Binding("x", "delete_column", "-Col"),
        Binding("left_square_bracket", "move_column(-1)", "Move col left", show=False),
        Binding("right_square_bracket", "move_column(1)", "Move col right", show=False),
        Binding("t", "change_theme", "Theme"),
        Binding("question_mark", "help", "Help"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        self.sheet = Sheet(path)
        self.sub_title = _short_path(self.sheet.path)
        self._columns: list[Column] = []
        self._rows: list[Row] = []

    # ------------------------------------------------------------------ setup

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="grid", cursor_type="cell", zebra_stripes=True)
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        saved = config.load().get("theme")
        if saved in self.available_themes:
            self.theme = saved
        self._theme_loaded = True
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

    # ---------------------------------------------------------------- drawing

    def reload(self, cursor: Coordinate | None = None) -> None:
        """Redraw the whole grid from the database."""
        table = self.table
        previous = cursor or table.cursor_coordinate
        table.clear(columns=True)

        self._columns = self.sheet.columns()
        self._rows = self.sheet.rows()

        for column in self._columns:
            table.add_column(
                Text.assemble((column.name, "bold"), (f"  {column.type.tag}", "dim")),
                key=str(column.id),
            )
        for number, row in enumerate(self._rows, start=1):
            cells = [
                _render(column, row.values.get(column.id)) for column in self._columns
            ]
            table.add_row(*cells, key=str(row.id), label=Text(str(number), "dim"))

        if self._rows and self._columns:
            table.cursor_coordinate = Coordinate(
                min(previous.row, len(self._rows) - 1),
                min(previous.column, len(self._columns) - 1),
            )
        self._update_status()

    def _update_status(self) -> None:
        columns, rows = self.sheet.counts()
        column = self.current_column()
        shape = f"{rows} {_plural(rows, 'row')} × {columns} {_plural(columns, 'column')}"
        detail = ""
        if column is not None:
            detail = f"  ·  {column.name}: {column.type.label}"
            if column.type is ColumnType.SELECT:
                detail += f" ({', '.join(column.options) or 'no options'})"
        self.query_one("#status", Static).update(
            Text.from_markup(
                f"[dim]{self.sheet.path.name}  ·  {shape}{detail}  ·  ? for help[/]"
            )
        )

    # -------------------------------------------------------------- selection

    def current_column(self) -> Column | None:
        index = self.table.cursor_coordinate.column
        if 0 <= index < len(self._columns):
            return self._columns[index]
        return None

    def current_row(self) -> Row | None:
        index = self.table.cursor_coordinate.row
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    @on(DataTable.CellHighlighted)
    def cell_highlighted(self) -> None:
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
        self.table.update_cell_at(self.table.cursor_coordinate, _render(column, value))
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

        top, left = self.table.cursor_coordinate
        width = max(len(line) for line in block)
        columns = self._columns[left : left + width]
        clipped = width - len(columns)
        new_rows = max(0, top + len(block) - len(self._rows))

        overwrites = sum(
            1
            for target, value in self._paste_targets(block, columns, top)
            if target is not None and value != target
        )
        shape = f"{len(block)} × {len(columns)}"

        def apply(confirmed: bool | None = True) -> None:
            if confirmed:
                self._apply_paste(block, columns, top, new_rows, clipped)

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

    def _paste_targets(self, block, columns: list[Column], top: int):
        """Yield (existing value, pasted value) for cells that already have a row."""
        for offset, line in enumerate(block):
            index = top + offset
            if index >= len(self._rows):
                continue
            row = self._rows[index]
            for across, column in enumerate(columns):
                raw = line[across] if across < len(line) else ""
                try:
                    value = parse(column.type, raw, column.options)
                except ValidationError:
                    continue
                yield row.values.get(column.id), value

    def _apply_paste(self, block, columns: list[Column], top: int, new_rows: int, clipped: int) -> None:
        for _ in range(new_rows):
            self.sheet.add_row()
        rows = self.sheet.rows()

        written = skipped = 0
        for offset, line in enumerate(block):
            row = rows[top + offset]
            for across, column in enumerate(columns):
                raw = line[across] if across < len(line) else ""
                try:
                    value = parse(column.type, raw, column.options)
                except ValidationError:
                    skipped += 1
                    continue
                self.sheet.set_cell(row.id, column.id, value)
                written += 1

        self.reload(Coordinate(top, self.table.cursor_coordinate.column))
        parts = [f"Pasted {len(block)} × {len(columns)}"]
        if new_rows:
            parts.append(f"{new_rows} {_plural(new_rows, 'row')} added")
        if skipped:
            parts.append(f"{skipped} {_plural(skipped, 'value')} did not fit the column type")
        if clipped:
            parts.append(f"{clipped} {_plural(clipped, 'column')} ran off the end")
        self.notify(" · ".join(parts), severity="warning" if skipped or clipped else "information")

    # ------------------------------------------------------------------- rows

    def action_add_row(self) -> None:
        if not self._columns:
            self.notify("Add a column first (c).", severity="warning")
            return
        self.sheet.add_row()
        self.reload(Coordinate(len(self._rows), self.table.cursor_coordinate.column))

    def action_insert_row(self) -> None:
        if not self._columns:
            self.notify("Add a column first (c).", severity="warning")
            return
        row = self.current_row()
        self.sheet.add_row(after_position=row.position if row else None)
        self.reload(
            Coordinate(
                self.table.cursor_coordinate.row + 1, self.table.cursor_coordinate.column
            )
        )

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

        self.push_screen(ConfirmScreen(f"Delete row {number}?"), done)

    # ---------------------------------------------------------------- columns

    def action_add_column(self) -> None:
        def done(result: tuple[str, ColumnType, list[str]] | None) -> None:
            if result is None:
                return
            name, coltype, options = result
            self.sheet.add_column(name, coltype, options)
            self.reload(Coordinate(self.table.cursor_coordinate.row, len(self._columns)))
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
        if self.sheet.move_column(column.id, offset):
            self.reload(
                Coordinate(
                    self.table.cursor_coordinate.row,
                    self.table.cursor_coordinate.column + offset,
                )
            )

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


def _one_line(text: str) -> Text:
    """Squeeze a value onto the one line a grid row has, marking where it breaks."""
    parts = text.replace("\t", " ").split("\n")
    line = Text(parts[0])
    for part in parts[1:]:
        line.append(" ⏎ ", "dim")
        line.append(part)
    return line


def _render(column: Column, value: Any) -> Text:
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
    return _one_line(display(column.type, value))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print(f"usage: gridly [FILE]\n\nOpens FILE (default: ./{DEFAULT_FILE}), creating it if needed.")
        return 0
    GridlyApp(args[0] if args else DEFAULT_FILE).run()
    return 0
