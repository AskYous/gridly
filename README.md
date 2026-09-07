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
| `space`     | same as `enter`                               |
| `backspace` | clear the cell                                |
| `a`         | add a row at the bottom                       |
| `i`         | insert a row below the cursor                 |
| `d`         | delete the current row                        |
| `c`         | add a column                                  |
| `e`         | edit the current column (name, type, options) |
| `x`         | delete the current column                     |
| `[` / `]`   | move the current column left / right          |
| `?`         | help                                          |
| `q`         | quit                                          |

## File format

One SQLite database per sheet: `columns` (name, type, options, position),
`rows` (position), and `cells` (row_id, column_id, value). Open it with any
SQLite tool.

## Install

```sh
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/gridly
```
