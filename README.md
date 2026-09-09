# Gridly

<img width="1326" height="791" alt="image" src="https://github.com/user-attachments/assets/636d107b-7d50-40cb-9138-be8beddf5fad" />

A terminal spreadsheet with typed columns. Every change is written straight to a
SQLite file — there is no save step and nothing to lose on a crash.

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
ln -sf "$PWD/.venv/bin/gridly" ~/.local/bin/gridly   # or any dir on your PATH
```

The console script has the venv's python baked into its shebang, so the symlink
works from anywhere without activating anything. It points back at this
checkout, so keep the folder where it is.

## Run

```sh
gridly                   # opens ./sheet.gridly in the current directory
gridly ~/budget.gridly
```

`gridly.sh` in this folder does the same thing without installing anything.

## Column types

| Type     | Accepts                                   |
| -------- | ----------------------------------------- |
| Text     | anything                                  |
| Number   | `42`, `3.14`, `1,200`                     |
| Boolean  | `yes/no`, `y/n`, `true/false`, `1/0`      |
| Date     | `2026-09-07`, `07/09/2026`, `today`       |
| Dropdown | one of the options you define on the column, one per line |

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
| `v`         | flip the view: records across, not down       |
| `s`         | row size: small or large                      |
| `backspace` | clear the cell                                |
| `a`         | add a row at the bottom                       |
| `i`         | insert a row below the cursor                 |
| `d`         | delete the current row (no prompt if it's empty) |
| `c`         | add a column                                  |
| `e`         | edit the current column (name, type, options) |
| `x`         | delete the current column                     |
| `[` / `]`   | move the current column left / right          |
| shift+arrows| select a block of cells                       |
| `esc`       | drop the selection                            |
| `y`         | copy the selection, or just this cell         |
| `Y`         | copy the whole row, tab separated             |
| `E`         | export the sheet to a CSV file                |
| `cmd/ctrl+v`| paste cells copied from a spreadsheet         |
| `t`         | change the colour theme                       |
| `?`         | help                                          |
| `q`         | quit                                          |

## Themes

A fresh install opens in `rose-pine`. `t` (or `ctrl+p` → "theme") opens
Textual's theme search; whatever you pick is written to
`~/.config/gridly/config.json` and applied on the next launch. A
config naming a theme that no longer exists, or one that won't parse, falls
back to the default rather than failing to start.

Gridly paints its own colours rather than borrowing your terminal's — pick
`ansi-dark` or `ansi-light` if you would rather it used your terminal palette.

## Dropdown options

A dropdown's options are entered one per line, not comma separated, so a long
list is readable and an option can contain a comma itself. Blank lines are
ignored, options are trimmed, and two that differ only in case are refused.
`ctrl+s` saves the column, since `enter` is busy starting the next option.

## Multi-line text

A text column holds newlines. A row shows as many of them as its height allows
and squeezes the rest onto its last line, marking each break it swallows with a
dim `⏎` — so a small row still shows the whole value, and the value itself is
untouched either way. Open the cell with `enter`, or the row with `f`, and you
get a real text box with the lines laid out properly: `enter` starts a new
line, `ctrl+s` saves, `esc` throws the edit away. Number and date columns keep
their one-line input, where `enter` still saves.

## Exporting to CSV

`E` writes the whole sheet out as a CSV: a header row of column names, then one
line per record, with values exactly as the grid shows them — `yes`/`no` for a
boolean, `2026-09-08` for a date. It suggests the sheet's own name with a `.csv`
suffix, and asks before overwriting a file that is already there.

The file is UTF-8 with a byte order mark, which is what Excel needs to read
non-ASCII text without garbling it and which Sheets, pandas and everything else
accept happily.

Unlike copying, export ignores the flipped view. The clipboard is for grabbing
what you can see; a CSV is data going to another tool, and every one of those
tools expects a header row with records underneath.

## Flipping the view

A sheet with many columns and few rows means scrolling sideways to read one
record. `v` turns the grid on its side: column names run down the left and each
record becomes a column. It is only a way of drawing the sheet — the file is
untouched, `v` puts it back, and every launch starts the normal way round.

Nothing else changes meaning. `d` still deletes the record under the cursor
even though that record is now a column on screen, `c` still adds a column even
though it appears as a new row, and the status line says `flipped` so you know
which way you are looking.

Copying and pasting follow what is on screen. Flipped, `Y` copies a record as a
column of lines rather than one line, and a pasted block still spills right and
down the screen — so a block copied from the flipped view pastes back exactly
as it looked. The one asymmetry is inherent: records are the axis that can
grow, so pasting past the last record adds records, while a block that runs
past the last column is still clipped rather than inventing columns.

## Row size

`s` swaps between two row heights, small and large. Like flipping, it only
changes the drawing: nothing is written to the sheet, and the height is
remembered in the config so the next launch opens the way you left it.

Small is one line per row, which is the tightest the grid goes. Large is three,
which gives a multi-line text value room to show its later lines instead of
folding them onto the first, and sits every value in the middle of its row.

## Copying out

Hold shift and use the arrows to grow a block out from the cursor; the cells
highlight and the status line counts them. Any plain cursor move or `esc`
drops it. With a block selected `y` copies the whole thing, tab separated, so
it lands in Sheets as cells and pastes back into Gridly unchanged.

With nothing selected, `y` copies the cell under the cursor as plain text — the value itself, so it
lands in another app exactly as it reads on screen. `Y` copies the whole row
tab separated and quoted the way a spreadsheet writes it, so it pastes into
Sheets as a row of cells and back into Gridly unchanged.

Both go to the clipboard twice over: through OSC 52, which is what works when
you are on the other end of an ssh session, and through `pbcopy` (or `wl-copy`,
`xclip`, `xsel`) when Gridly is running on the same machine as the clipboard.
macOS Terminal ignores OSC 52, so the second route is what makes `y` work there.

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
`tab` between them, `ctrl+s` to save, `esc` to throw the edits away. (`enter`
saves too, except in a text field, where it starts a new line.) Nothing is
written until you save, and a bad value keeps the form open with the offending
field focused.

## File format

One SQLite database per sheet: `columns` (name, type, options, position),
`rows` (position), and `cells` (row_id, column_id, value). Open it with any
SQLite tool.
