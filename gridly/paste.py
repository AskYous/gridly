"""Reading a block of cells out of clipboard text."""

from __future__ import annotations

import csv
import io


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
