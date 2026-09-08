"""Moving blocks of cells to and from the clipboard."""

from __future__ import annotations

import csv
import io
import shutil
import subprocess


def parse_block(text: str) -> list[list[str]]:
    """Split clipboard text into rows of cells.

    Sheets, Excel and Numbers all put tab-separated text on the clipboard, with
    any cell containing a tab, newline or quote wrapped in double quotes — which
    is exactly what :mod:`csv` reads with a tab delimiter.
    """
    if not text:
        return []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    block = [row for row in csv.reader(io.StringIO(text), delimiter="\t")]
    if block and block[-1] in ([""], []):
        block.pop()  # the trailing newline of a copied range is not another row
    return block


def format_block(block: list[list[str]]) -> str:
    """Render rows of cells as the tab-separated text a spreadsheet expects."""
    out = io.StringIO()
    csv.writer(out, delimiter="\t", lineterminator="\n").writerows(block)
    return out.getvalue()


# Textual copies with OSC 52, which macOS Terminal ignores. When we are on the
# same machine as the clipboard, hand the text to the system tool as well.
_CLIPBOARD_COMMANDS = (
    ["pbcopy"],
    ["wl-copy"],
    ["xclip", "-selection", "clipboard"],
    ["xsel", "--clipboard", "--input"],
)


def to_system_clipboard(text: str) -> bool:
    """Best-effort copy through a local clipboard tool. False if none worked."""
    for command in _CLIPBOARD_COMMANDS:
        if shutil.which(command[0]) is None:
            continue
        try:
            subprocess.run(command, input=text.encode(), check=True, timeout=5)
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False
