"""Gridly — a terminal spreadsheet with typed columns."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Static

from .coltypes import ColumnType, display
from .screens import CellEditScreen, ColumnScreen, ConfirmScreen, HelpScreen, PickScreen
from .store import Column, Row, Sheet

DEFAULT_FILE = "sheet.gridly"


class GridlyApp(App[None]):
    CSS_PATH = "app.tcss"
    TITLE = "Gridly"

    BINDINGS = [
        Binding("space", "edit_cell", "Edit"),
        Binding("backspace", "clear_cell", "Clear"),
        Binding("a", "add_row", "+Row"),
        Binding("i", "insert_row", "Insert row", show=False),
        Binding("d", "delete_row", "-Row"),
        Binding("c", "add_column", "+Col"),
        Binding("e", "edit_column", "Edit col"),
        Binding("x", "delete_column", "-Col"),
        Binding("left_square_bracket", "move_column(-1)", "Move col left", show=False),
        Binding("right_square_bracket", "move_column(1)", "Move col right", show=False),
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
        table = self.query_one("#grid", DataTable)
        table.show_row_labels = True
        table.focus()
        self.reload()

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
    return Text(display(column.type, value))


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("-h", "--help"):
        print(f"usage: gridly [FILE]\n\nOpens FILE (default: ./{DEFAULT_FILE}), creating it if needed.")
        return 0
    GridlyApp(args[0] if args else DEFAULT_FILE).run()
    return 0
