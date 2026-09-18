"""Finding a name by its letters, in order — `ovt` finds `overtime.gridly`.

Textual's command palette has a matcher of its own, and using it means the
picker ranks names the same way the palette ranks commands. It lives in a
corner of Textual that is not promised to stay put, though, and this project
asks only for `textual>=1.0` — so when it is not there, the same job is done
here instead, and the filter goes on working rather than the picker failing
to import.
"""

from __future__ import annotations

try:  # the command palette's own, when the installed Textual has it
    from textual.fuzzy import Matcher as _Palette
except ImportError:  # pragma: no cover — depends on the Textual installed
    _Palette = None


def letters_in(query: str, candidate: str) -> list[int]:
    """Where each letter of the query sits in the candidate, earliest first.

    Empty if they are not all there, in order — which is what "no match" is.
    """
    lowered = candidate.lower()
    found: list[int] = []
    at = 0
    for letter in query.lower():
        place = lowered.find(letter, at)
        if place < 0:
            return []
        found.append(place)
        at = place + 1
    return found


def rank(query: str, candidate: str) -> float:
    """How well a query fits a name, or zero if it does not fit at all.

    A letter at the start of the name, or of a word inside it, counts for more
    than one in the middle of nowhere — and a letter following straight on from
    the one before counts for more again. Running on is worth more than starting
    a word, so a name holding the query whole beats one where the same letters
    happen to begin three words: `ove` is more of `overtime` than of `o-v-e-r`.
    """
    found = letters_in(query, candidate)
    if not found:
        return 0.0
    total = 1.0
    for index, place in enumerate(found):
        total += 1.0
        if place == 0 or not candidate[place - 1].isalnum():
            total += 1.5
        if index and place == found[index - 1] + 1:
            total += 3.0
    return total


class Search:
    """One query, ready to be tried against many names."""

    def __init__(self, query: str, palette: bool = True) -> None:
        self.query = query.strip()
        #: None when matching is done here rather than by Textual.
        self.palette = _Palette(self.query) if palette and _Palette else None

    def score(self, candidate: str) -> float:
        """Above zero if the query finds this name; higher is a better fit."""
        if not self.query:
            return 0.0
        if self.palette is not None:
            return float(self.palette.match(candidate))
        return rank(self.query, candidate)

    def marks(self, candidate: str) -> list[int]:
        """Which letters of the name the query found, to pick them out."""
        if not self.score(candidate):
            return []
        if self.palette is not None:
            return [
                place
                for span in self.palette.highlight(candidate).spans
                for place in range(span.start, span.end)
            ]
        return letters_in(self.query, candidate)
