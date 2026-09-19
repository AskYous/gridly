# Gridly

[![tests](https://github.com/AskYous/gridly/actions/workflows/tests.yml/badge.svg)](https://github.com/AskYous/gridly/actions/workflows/tests.yml)

<img width="1141" height="794" alt="image" src="https://github.com/user-attachments/assets/a4f05501-15f3-4d92-933d-9ca2a58fd7ca" />

A terminal spreadsheet with typed columns. Every change is written straight to a
SQLite file — there is no save step and nothing to lose on a crash.

## In a browser

```sh
pip install -e ".[web]"
gridly-web                      # http://127.0.0.1:8000
gridly-web demo.gridly          # or open one straight away
```

With no file named, a browser session offers the sheets opened lately, the
same as running `gridly` with nothing after it.

Gridly is a Textual app, and Textual streams a terminal to the page, so this is
the same app rather than a second one — every key and every setting works as it
does in a terminal.

Each browser session starts a real Gridly process with this machine's file
access, so it listens on `127.0.0.1` only. `--host` widens that, and is worth
doing only on a network you trust.

## Tests

```sh
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

`tests/unit` is the logic on its own — parsing, storage round trips, the
width and height maths, undo, the clipboard format, the CSV writer. A hundred
and sixty of them, and they finish in under a second, so there is no reason not
to run them.

`tests/app` drives the real app through Textual's test harness: pressing keys,
reading what the grid ends up showing, checking what landed in the file. Twenty
of them, and they take about forty seconds between them.

```sh
.venv/bin/python -m pytest tests/unit   # while working
.venv/bin/python -m pytest              # before pushing
```

They share a process, so `tests/conftest.py` points the config and the
clipboard somewhere harmless before any of them run.

Both halves run on every push and pull request, against Python 3.10, 3.12 and
3.13, and the run fails if the tests stop reaching 93% of the code. Coverage
sits at 94%; the floor is there to catch a feature arriving without tests, not
to be chased upwards.

## The screenshot

`python demo.py` writes `demo.gridly`, the task list the picture above is taken
from — thirty rows across eight columns covering every type, with the dropdowns
coloured. About 142×36 shows the whole thing:

```sh
python demo.py && gridly demo.gridly
```

`--rows N` writes more than the thirty in the picture, making the rest up, for
when you want a sheet with something in it:

```sh
python demo.py big.gridly --rows 2000
```

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

`o` brings that list back at any point, to leave the sheet you are in for
another one without closing the app. `esc` there leaves you where you were.

With no file named, Gridly lists the sheets you have opened before — newest
first, with where they live and when they were last touched — so a sheet in
some deep folder is two keystrokes away rather than a `cd`. Sheets that have
since been deleted are dropped from the list. There is a field underneath for
typing any other path, and `esc` quits without opening anything. The very first
run has nothing to list, so it just opens `./sheet.gridly` as before.

The list takes the keys straight away, so you can find a sheet by typing at it:
`ovt` finds `overtime.gridly`, the same fuzzy matching the command palette does,
with the letters it found picked out and the closest match first. It is the
sheet's name that is matched, not the folder it sits in — folders are long
enough that a letter or two would otherwise turn up in every one of them. `↑↓`
move the highlight from the filter, `enter` opens what is highlighted, and `esc`
clears the filter before it gives up on the screen.

The name goes across the top in block capitals, in whatever theme is loaded. On
a screen too small to carry it — under 50 columns or 28 rows — it stands down,
since the list of sheets is what the screen is for.

`gridly.sh` in this folder does the same thing without installing anything.

## Column types

| Type     | Accepts                                   |
| -------- | ----------------------------------------- |
| Text     | anything                                  |
| Number   | `42`, `3.14`, `1,200`                     |
| Boolean  | `yes/no`, `y/n`, `true/false`, `1/0`      |
| Date     | `2026-09-07`, `07/09/2026`, `today`       |
| Time     | `9:30`, `14:05`, `9:30 pm`, `7`           |
| Dropdown | one of the options you define on the column, one per line |

Bad input is refused with a message instead of being stored. Changing a
column's type converts the existing values where it can and clears the cells
where it can't, telling you how many it dropped.

A column can also be calculated from the others rather than typed into — a
formula such as `Hours * 55`, or the month of a date. See *Columns that work
themselves out* below.

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
| `s`         | row size: small or large                      |
| `backspace` | clear the cell                                |
| `a`         | add a row at the bottom                       |
| `i`         | insert a row below the cursor                 |
| `D`         | duplicate the row below itself                |
| `u` / `U`   | undo / redo the last change                   |
| `d`         | delete the current row                        |
| `c`         | add a column                                  |
| `e`         | edit the current column (name, type, options, formula, alignment) |
| `x`         | delete the current column                     |
| `{` / `}`   | move the current row up / down (or alt+↑/↓)   |
| `[` / `]`   | move the current column left / right          |
| `o`         | open another sheet                            |
| `/`         | search every cell                             |
| `n` / `N`   | next / previous match                         |
| shift+arrows| select a block of cells                       |
| `esc`       | drop the selection                            |
| `y`         | copy the selection, or just this cell         |
| `Y`         | copy the whole row, tab separated             |
| `E`         | export the sheet to a CSV file                |
| `cmd/ctrl+v`| paste cells copied from a spreadsheet         |
| `,`         | settings: width, wrapping, padding, placing, theme |
| `t`         | change the colour theme                       |
| `ctrl+p`    | command palette — every command, with its key |
| `?`         | help                                          |
| `q`         | quit                                          |

## The command palette

`ctrl+p` lists everything the app can do, searchable by name — and each command
shows the key that does the same thing, in a column down the left:

```
Add row
a         Append an empty row at the bottom
Duplicate row
D         Copy this row into a new one below it
Select one cell right
shift+→   Grow the selection
```

So the palette is a way of finding a command once, rather than the way of
running it every time. The keys come from the bindings themselves, written the
way the footer writes them, so the two cannot drift apart — and a command with
no key of its own keeps the column and simply shows nothing there.

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

## Times

A time column takes `9:30`, `14:05`, `9:30 pm`, `9.30pm` or just `7`, and always
shows it on a twenty-four hour clock so the column reads and sorts straight.

Each time column says how precise it is: hours and minutes, or seconds as well.
A column that does not show seconds does not keep them either — type `9:30:45`
into one and it stores `09:30`, so what is in the file is what is on screen.
Switch the column to seconds later and the times you already have read as
`09:30:00`.

## Unique columns

A column can be told that no two rows may share a value — an id, an email, a
reference. Tick *Unique* in the column form and Gridly stops a repeat getting
in, wherever it comes from:

- typing one into a cell is refused and says which row already has it
- the row form refuses inline, so the rest of what you typed is not lost
- a paste drops the values that would repeat, keeps the rest, and counts them
- `D` duplicates the row but leaves its unique columns empty, since a copy of
  them is the one thing the column does not allow

Empty cells are not compared, so any number of rows may have nothing there.
Values are compared as they are stored, so `A1` and `a1` are two different
things. Turning the rule on is refused while the column still repeats itself,
and says which values to sort out first.

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

Rewording an option takes its values with it: change *Doing* to *In progress*
and every cell that said *Doing* now says *In progress*. Gridly knows which
option row was which, so renaming two at once — even swapping their names —
does the right thing. Removing an option is the one thing that clears cells,
and it says how many and that `u` puts them back.

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

## Columns that work themselves out

A column can take its values from another column instead of from you. In the
column form (`c` or `e`), *Value* offers two of those beside the usual *Typed
in*: **Calculated**, by a formula you write, and **Month of a date**.

Nothing is stored. A worked-out column is worked out every time the sheet is
read, so it can never be left standing beside a value that has since moved —
change what it reads and it changes with it, undo that and it goes back too. Its
header carries an `fx` beside the type, and the status line says what works it
out.

That also means there is nothing in it to type into: `enter` and `backspace` say
which column to change instead, the row form shows it greyed out, and a paste
that lands on it is counted and dropped rather than written.

### Calculated

Write the formula in the names of the other columns: `Hours * 55`, `Hours * 55 + Bonus`,
`(Hours - 8) * 1.5 * Rate`. Numbers, `+ - * /` and brackets, and nothing else —
it is read a piece at a time rather than handed to Python, so a formula in a
sheet can only ever do arithmetic. A formula reads number columns, including ones
that are themselves calculated, so `Pay = Hours * 55` and `Tax = Pay * 0.15` both
land; each column is worked out after the ones it reads, whatever order they sit
in. A formula that would end up reading itself round a circle is refused in the
form. Under the box, the form lists the columns of this sheet you can use.

A row nobody has filled in yet stays empty rather than reading as zero — which
is what stops a rate column paying out on every blank row. In a row that has
been started, a column still blank counts as nothing. Dividing by nothing leaves
the cell empty too.

Rename a column and the formulas that read it follow the new name. Delete it
and they stop, and say so.

### Month of a date

Pick the date column to read and how the month should be written.

| Written as | Looks like  |
| ---------- | ----------- |
| name       | `September` |
| short      | `Sep`       |
| number     | `9`         |
| year       | `2026-09`   |

### What a worked-out column may be

The column still has a type, and the answer has to fit it. A formula goes in a
number column, or a text one. A month has more to say: text takes any of the
four wordings. A number column takes the month only as a number. A dropdown
lists the twelve months itself — you do not type its options, and it will not
take `2026-09`, which never stops adding new ones. Anything else — a date, a
time, a yes/no — is refused in the form, with the reason.

Delete a column that something else is worked out from, and that column stops
working anything out and says so, rather than quietly emptying. Turn *Value*
back to *Typed in* and it becomes an ordinary empty column you own again.

## Where values sit in a column

Each column has an *Alignment* in its own form (`c` or `e`): **Left**,
**Centred**, **Right**, or **Automatic**, which is what it starts on. The
heading goes wherever the values go, so a column of right-aligned figures does
not read as two columns.

Right is the one worth reaching for: a column of money or hours lines its digits
up against each other, which is how figures are meant to be read.

On Automatic, booleans, dates, times and dropdowns go down the middle of their
column: they are all of a size and usually shorter than the heading above them,
so against the left edge they read as stranded. Text and numbers stay left,
where prose and figures are read from. *Where values sit by default* in the
settings page (`,`) turns that centring off across the sheet — for the columns
still on Automatic. A column given an alignment of its own keeps it either way.

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

## Undo

`u` takes back the last change and `U` puts it back, forty deep. Everything
that touches the sheet is covered: editing a cell, adding or deleting a row or
column, moving a column, retyping one and losing the values that no longer fit,
duplicating a row, saving the row form, and pasting.

A run of edits that happened together is taken back together — pasting a block
of thirty cells is one press of `u`, not thirty. Because of that, deleting a row
or a column and pasting over filled cells no longer stop to ask first: they
happen, and the notification tells you `u` will put them back.

The stack lives for as long as the app is open. Closing the sheet forgets it —
what is on disk is what you have.

## Settings

`w`, `W`, `s` and `t` each change one thing and are quick once you know
them. `,` opens all of them on one page instead, each with a line saying what
it does and what the choices mean, plus a button that puts everything back to
how it started. The theme changes as you move through the list so you can see
it; `esc` puts it back.

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
one takes the space.

`s` adds a blank line above and below every value, wrapped or not — the sheet
reads less like a wall. A value shorter than its row sits in the middle of it,
so a single word beside a cell nine lines tall is not left stranded at the top. It used to be a choice of two row heights, which did
nothing at all while values were wrapping, since they set their own height.

```
 Task       Done  Note                                  Qty
 Ship it    ✓     This is a very long note that would…  4
 Short one  ✗     brief                                 12
```

Both settings are remembered in `~/.config/gridly/config.json` along with the
theme and row height.


## Row size

`s` swaps between two row heights, small and large. It only
changes the drawing: nothing is written to the sheet, and the height is
remembered in the config so the next launch opens the way you left it.

Small is one line per row, which is the tightest the grid goes. Large is three,
which gives a multi-line text value room to show its later lines instead of
folding them onto the first, and sits every value in the middle of its row.

## Searching

`/` opens a bar at the bottom and looks as you type, across every column,
ignoring case. It matches what you can see rather than what is stored, so
`yes` finds a ticked box and `2026-09` finds a date. Every match lights up and
the status line counts them — `1 of 6 matches for 'waseem'`.

`enter` hands the grid back with the matches still lit, and `n` and `N` walk
through them, wrapping round at the ends. `esc` gives up and puts the cursor
back where it was before you started.

Matches follow the sheet: edit a cell or delete a row and the count and
highlights are worked out again.

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

One thing it deliberately does not do: it never invents columns, so a block
wider than the sheet is clipped and the notification tells you by how much.
Values that don't fit their column's type are left alone and counted in the
same notification, and the whole paste is a single `u` away from being undone.

## Row form

Grid editing gets cramped once a sheet has more than a handful of columns.
`f` opens the row under the cursor as a form — one labelled field per column,
`tab` between them, `ctrl+s` to save, `esc` to throw the edits away. (`enter`
saves too, except in a text field, where it starts a new line.) Nothing is
written until you save, and a bad value keeps the form open with the offending
field focused.

## File format

One SQLite database per sheet: `columns` (name, type, options, formula, align,
position), `rows` (position), and `cells` (row_id, column_id, value). Open it
with any SQLite tool. A column that works itself out keeps what works it out in
`formula` and holds no cells at all.
