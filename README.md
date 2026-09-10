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
gridly                   # offers the sheets you had open lately
gridly ~/budget.gridly   # or open one straight away
```

With no file named, Gridly lists the sheets you have opened before — newest
first, with where they live and when they were last touched — so a sheet in
some deep folder is two keystrokes away rather than a `cd`. Sheets that have
since been deleted are dropped from the list. There is a field underneath for
typing any other path, and `esc` quits without opening anything. The very first
run has nothing to list, so it just opens `./sheet.gridly` as before.

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
| `w`         | column width: large, fit, small, unlimited    |
| `W`         | long values wrap, or end in an ellipsis       |
| `v`         | flip the view: records across, not down       |
| `s`         | row size: small or large                      |
| `backspace` | clear the cell                                |
| `a`         | add a row at the bottom                       |
| `i`         | insert a row below the cursor                 |
| `D`         | duplicate the row below itself                |
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
| `ctrl+p`    | command palette — every command, searchable   |
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

## Finding things

The footer keeps only the way in — edit, add a row, add a column — plus the two
routes to everything else: `?` for the grouped key list and `ctrl+p` for the
command palette. Every other key is one of those two away.

`ctrl+p` opens the command palette. Everything the app can do is in there by
name, with a sentence saying what it means — including the things whose keys
are easy to miss, like moving a column left or right. A test asserts every
key binding has a palette entry, so the two cannot drift apart.

## Dropdown options

`c` and `e` open a full-screen form — the same shape as the row form — rather
than a dialog, because a name, a type and a list of options with their colours
stopped fitting in one. A dropdown's options are rows: a field for the name and
a dropdown for the colour it is shown in. `+ add option` adds a row,
`✕` drops one, and a row left blank is ignored. Two options that differ only in
case are refused, and so is an empty list.

```
  Options
   Low                       ███ green    ▼   ✕
   Medium                    ███ yellow   ▼   ✕
   High                      ███ red      ▼   ✕

    + add option
```

Leave a colour unset and one is taken from the palette in the order the options
are listed, so a Low/Medium/High column reads green, yellow, red without you
choosing anything. The nine colours are `green`, `yellow`, `red`, `blue`,
`purple`, `teal`, `orange`, `pink` and `grey`, each shown as a block of itself
in the dropdown. They are spelled out rather than borrowed from the terminal's
own palette, which maps several names onto the same colour depending on the
theme.

Colours show in the grid, in the picker you get when editing a cell, and in the
status line. Sheets made before colours existed pick them up from the palette
without being rewritten.

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

## Column width

One long value used to stretch its column across the screen and push the rest
out of sight. Gridly opens in **fit**, and `w` cycles between large (36
characters), fit, small (16) and unlimited. Pressing it shows the whole cycle
along the status line with the current setting marked, for a few seconds:

```
column width   large   fit  [ small ]  unlimited
```

`W` and `s` do the same for their own cycles. These are caps, not widths: a column narrower than the cap keeps its
own size, so a yes/no column stays three wide however the cap is set.

Fit has no fixed number — it shares the screen out between the columns so
the whole table is visible across, with no sideways scrolling. Narrow columns
are paid in full and what is left over goes to the wide ones, so the squeeze
falls on whichever column is hogging the room. A fitted table follows the
window: resize the terminal and the columns are shared out again. Nothing goes
below six characters, so on a very narrow window the table gives up and
scrolls rather than reducing every column to nothing.

`W` decides what a capped column does with a value too long for it — end it in
an ellipsis, or wrap it. Wrapping grows each row to fit its tallest value, up
to twelve lines, so a row of short values stays one line high and only the long
one takes the space. `s` sets the row height for the ellipsis side, where every
row is the same height whatever is in it:

```
 Task       Done  Note                                  Qty
 Ship it    ✓     This is a very long note that would…  4
 Short one  ✗     brief                                 12
```

Both settings are remembered in `~/.config/gridly/config.json` along with the
theme and row height.

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
