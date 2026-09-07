# Gridly

A terminal spreadsheet with typed columns. Every change is written straight to a
SQLite file — there is no save step and nothing to lose on a crash.

## Run

```sh
./gridly.sh              # opens ./sheet.gridly, creating it if needed
./gridly.sh budget.gridly
```

## Column types

| Type     | Accepts                                   |
| -------- | ----------------------------------------- |
| Text     | anything                                  |
| Number   | `42`, `3.14`, `1,200`                     |
| Boolean  | `yes/no`, `y/n`, `true/false`, `1/0`      |
| Date     | `2026-09-07`, `07/09/2026`, `today`       |
| Dropdown | one of the options you define on the column |

Bad input is refused with a message instead of being stored. Changing a
column's type converts the existing values where it can and clears the cells
where it can't, telling you how many it dropped.

## Keys

| Key         | Does                                          |
| ----------- | --------------------------------------------- |
| arrows      | move around the grid                          |
| `enter`     | edit the cell (a boolean cell just toggles)   |
| `ctrl+s`    | save a text cell (`enter` adds a line there)  |
| `space`     | same as `enter`                               |
| `f`         | open the whole row as a form                  |
| `backspace` | clear the cell                                |
| `a`         | add a row at the bottom                       |
| `i`         | insert a row below the cursor                 |
| `d`         | delete the current row                        |
| `c`         | add a column                                  |
| `e`         | edit the current column (name, type, options) |
| `x`         | delete the current column                     |
| `[` / `]`   | move the current column left / right          |
| `cmd/ctrl+v`| paste cells copied from a spreadsheet         |
| `t`         | change the colour theme                       |
| `?`         | help                                          |
| `q`         | quit                                          |

## Multi-line text

A text column holds newlines. Since a grid row is one line tall, the grid
collapses them onto that line and marks each break with a dim `⏎` — the value
itself is untouched. Open the cell with `enter`, or the row with `f`, and you
get a real text box with the lines laid out properly: `enter` starts a new
line, `ctrl+s` saves, `esc` throws the edit away. Number and date columns keep
their one-line input, where `enter` still saves.

## Pasting from a spreadsheet

Copy a range in Google Sheets, Excel or Numbers and paste it straight into the
grid. The block lands with its top-left cell at the cursor and spills right and
down from there, adding rows at the bottom when it needs more than the sheet
has. Cells are read through the target column's type, so `TRUE` lands in a
boolean column and `1,200` in a number one; blank cells clear their target.
A cell containing newlines arrives quoted and is stored whole, newlines and all.

Two things it deliberately does not do: it never invents columns, so a block
wider than the sheet is clipped and the notification tells you by how much, and
it asks before replacing cells that already have values, since there is no undo.
Values that don't fit their column's type are left alone and counted in the
same notification.

## Row form

Grid editing gets cramped once a sheet has more than a handful of columns.
`f` opens the row under the cursor as a form — one labelled field per column,
`tab` between them, `ctrl+s` or `enter` to save, `esc` to throw the edits away.
Nothing is written until you save, and a bad value keeps the form open with the
offending field focused.

## File format

One SQLite database per sheet: `columns` (name, type, options, position),
`rows` (position), and `cells` (row_id, column_id, value). Open it with any
SQLite tool.

## Install

```sh
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/gridly
```
