"""A small arithmetic language: the sums a column can be worked out by.

Numbers, the names of other columns, `+ - * /` and brackets. Nothing else —
no calls, no attributes, no names it was not handed. It is read by hand rather
than by `eval`, so a sum typed into a sheet can only ever do arithmetic.
"""

from __future__ import annotations

from typing import Any

#: What `+ - * /` do, given two numbers. Division that cannot be done is None.
_OPERATORS = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: None if b == 0 else a / b,
}

#: Beyond this many decimal places is float noise, not arithmetic.
PLACES = 10


class FormulaError(ValueError):
    """Raised when a sum cannot be read, with something to show the writer."""


def _match_name(text: str, at: int, names: list[str]) -> str | None:
    """The longest column name written at this point, if one is.

    Longest first, so a sheet with both `Hours` and `Hours worked` reads the
    longer one where it is written rather than stopping halfway through it.
    """
    ahead = text[at:].lower()
    found = [n for n in names if ahead.startswith(n.lower())]
    return max(found, key=len) if found else None


def tokenize(text: str, names: list[str]) -> list[tuple[str, Any]]:
    """Break a sum into numbers, column names and operators."""
    tokens: list[tuple[str, Any]] = []
    at = 0
    while at < len(text):
        char = text[at]
        if char.isspace():
            at += 1
            continue
        if char in _OPERATORS or char in "()":
            tokens.append((char, char))
            at += 1
            continue
        if char.isdigit() or (char == "." and text[at + 1 : at + 2].isdigit()):
            end = at
            while end < len(text) and (text[end].isdigit() or text[end] in ".,"):
                end += 1
            raw = text[at:end].replace(",", "")
            try:
                tokens.append(("number", float(raw)))
            except ValueError:
                raise FormulaError(f"{text[at:end]!r} is not a number") from None
            at = end
            continue
        name = _match_name(text, at, names)
        if name is not None:
            tokens.append(("column", name))
            at += len(name)
            continue
        # Not a name this sheet has: say which word, rather than which letter.
        end = at
        while end < len(text) and not text[end].isspace() and text[end] not in "()+-*/":
            end += 1
        word = text[at:end] or char
        raise FormulaError(f"No column is called {word!r}")
    return tokens


class _Reader:
    """Reads the tokens once, left to right, deepest sum first."""

    def __init__(self, tokens: list[tuple[str, Any]]) -> None:
        self.tokens = tokens
        self.at = 0

    def peek(self) -> str | None:
        return self.tokens[self.at][0] if self.at < len(self.tokens) else None

    def take(self) -> tuple[str, Any]:
        token = self.tokens[self.at]
        self.at += 1
        return token

    def sum_(self):
        node = self.product()
        while self.peek() in ("+", "-"):
            operator, _ = self.take()
            node = (operator, node, self.product())
        return node

    def product(self):
        node = self.signed()
        while self.peek() in ("*", "/"):
            operator, _ = self.take()
            node = (operator, node, self.signed())
        return node

    def signed(self):
        if self.peek() == "-":
            self.take()
            return ("neg", self.signed())
        if self.peek() == "+":
            self.take()
        return self.value()

    def value(self):
        kind = self.peek()
        if kind is None:
            raise FormulaError("The formula stops early — something is missing from it")
        if kind == "(":
            self.take()
            inside = self.sum_()
            if self.peek() != ")":
                raise FormulaError("A bracket is opened and never closed")
            self.take()
            return inside
        if kind == ")":
            raise FormulaError("There is a closing bracket with nothing to close")
        if kind in _OPERATORS:
            raise FormulaError(f"{kind!r} has nothing in front of it")
        _, value = self.take()
        return (kind, value)


def parse(text: str, names: list[str]):
    """Read a sum into something that can be worked out. Raises FormulaError."""
    if not text.strip():
        raise FormulaError("Write the formula this column is calculated by")
    reader = _Reader(tokenize(text, names))
    tree = reader.sum_()
    if reader.at < len(reader.tokens):
        kind, value = reader.tokens[reader.at]
        if kind == ")":
            raise FormulaError("There is a closing bracket with nothing to close")
        shown = f"{value:g}" if kind == "number" else str(value)
        raise FormulaError(f"{shown!r} has nothing to join it to the rest")
    return tree


def columns_in(tree) -> list[str]:
    """Every column a sum reads, in the order it reads them, without repeats."""
    kind = tree[0]
    if kind == "column":
        return [tree[1]]
    if kind == "number":
        return []
    found = columns_in(tree[1])
    if kind != "neg":
        found += [c for c in columns_in(tree[2]) if c not in found]
    return found


def _work(tree, values: dict[str, float]) -> float | None:
    kind = tree[0]
    if kind == "number":
        return tree[1]
    if kind == "column":
        return values.get(tree[1], 0.0)
    if kind == "neg":
        inner = _work(tree[1], values)
        return None if inner is None else -inner
    left, right = _work(tree[1], values), _work(tree[2], values)
    if left is None or right is None:
        return None
    return _OPERATORS[kind](left, right)


def evaluate(tree, values: dict[str, Any]) -> float | None:
    """Work a sum out for one row. Nothing to go on is no answer at all.

    A row nobody has filled in yet stays empty rather than reading as zero; in
    a row that has been started, a column still blank counts as nothing. That
    is what keeps a rate column from paying out on every empty row.
    """
    reads = columns_in(tree)
    if reads and all(values.get(name) is None for name in reads):
        return None
    numbers = {
        name: float(values[name])
        for name in reads
        if isinstance(values.get(name), (int, float))
        and not isinstance(values.get(name), bool)
    }
    answer = _work(tree, numbers)
    if answer is None or answer != answer or answer in (float("inf"), float("-inf")):
        return None
    answer = round(answer, PLACES)
    return answer + 0.0  # -0.0 is a number nobody means


def rename(text: str, names: list[str], was: str, now: str) -> str:
    """The same sum, with one of the columns it reads called something else.

    The sum is read into its pieces and written back out, so a name is replaced
    where it is meant and nowhere else — not inside a longer name that contains
    it, and not inside a number. Spacing is tidied on the way, which is the one
    thing that changes about a sum nobody has touched.
    """
    try:
        tokens = tokenize(text, names)
    except FormulaError:
        return text  # it does not read as it is; renaming will not help
    if not any(kind == "column" and value == was for kind, value in tokens):
        return text
    pieces = [
        f"{value:g}"
        if kind == "number"
        else (now if kind == "column" and value == was else str(value))
        for kind, value in tokens
    ]
    return " ".join(pieces).replace("( ", "(").replace(" )", ")")
