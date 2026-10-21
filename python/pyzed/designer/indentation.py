"""Tabs or spaces: the indentation of a text, and converting it from one to the other.

``detect`` tells what a file indents with, ``convert`` rewrites the leading whitespace of each
line with tabs or spaces (the code editor's "Convert indentation to tabs" and the setting that
does it on save), and ``keeps_indentation`` makes the code generators follow the file they
edit: they write four spaces, so their output becomes tabs in a file indented with tabs (Python
refuses a block that mixes them).
"""

from __future__ import annotations

import functools
import io
import tokenize
from typing import Any, Callable, Optional, Set, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

#: Spaces per level of the code the designer writes (``code.stub``, ``scene_code.INDENT``).
GENERATED = 4


def detect(text: str) -> Optional[str]:
    """What ``text`` indents with: ``"\\t"``, a run of spaces (the smallest step seen) or ``None`` when no
    line is indented."""
    tabs = spaces = 0
    step = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        if line[0] == "\t":
            tabs += 1
        elif line[0] == " ":
            spaces += 1
            width = len(line) - len(line.lstrip(" "))
            step = width if not step else min(step, width)
    if not tabs and not spaces:
        return None
    return "\t" if tabs > spaces else " " * (step or GENERATED)


def _string_lines(text: str) -> Set[int]:
    """The 0-based lines that begin inside a multi-line string of Python ``text`` (their whitespace is the
    string's own); empty when ``text`` does not tokenize."""
    inside: Set[int] = set()
    starts = []  # where the f-strings (t-strings) being read began
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            name = tokenize.tok_name.get(token.type, "")
            if name.endswith("STRING_START"):
                starts.append(token.start[0])
            elif name.endswith("STRING_END") and starts:
                inside.update(range(starts.pop(), token.end[0]))
            elif token.type == tokenize.STRING:
                inside.update(range(token.start[0], token.end[0]))  # the rows after the first one, 0-based
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return set()
    return inside


def width(lead: str, size: int) -> int:
    """The columns ``lead`` (spaces and tabs) takes with a tab stop every ``size`` columns."""
    col = 0
    for ch in lead:
        col = (col // size + 1) * size if ch == "\t" else col + 1
    return col


def convert(text: str, tabs: bool, size: int = 4, *, python: bool = True) -> str:
    """Rewrites the leading whitespace of every line of ``text`` with tabs (``tabs``) or spaces, a tab being
    ``size`` columns. Columns left over from a tab stop stay as spaces. With ``python``, lines that start
    inside a multi-line string are left alone."""
    size = max(int(size), 1)
    skip = _string_lines(text) if python else set()
    out = []
    for i, line in enumerate(text.splitlines(keepends=True)):
        body = line.lstrip(" \t")
        lead = line[: len(line) - len(body)]
        if not lead or i in skip or not body.strip("\r\n"):
            out.append(line)
            continue
        cols = width(lead, size)
        new = "\t" * (cols // size) + " " * (cols % size) if tabs else " " * cols
        out.append(new + body)
    return "".join(out)


def to_tabs(text: str, size: int = 4, *, python: bool = True) -> str:
    """``convert(text, True, size)``."""
    return convert(text, True, size, python=python)


def to_spaces(text: str, size: int = 4, *, python: bool = True) -> str:
    """``convert(text, False, size)``."""
    return convert(text, False, size, python=python)


def follow(before: str, after: str) -> str:
    """``after`` (``before`` with generated code added) indented like ``before``: tabs when ``before`` uses
    them, else the tabs in ``after`` become spaces."""
    unit = detect(before)
    if unit == "\t":
        return to_tabs(after, GENERATED)
    if "\t" in after and any(line.startswith("\t") for line in after.splitlines()):
        return to_spaces(after, len(unit) if unit else GENERATED)
    return after


def keeps_indentation(fn: F) -> F:
    """Makes a code generator ``fn(source, ...)`` (returning the new source, or ``(source, flag)``) indent
    what it writes like ``source``."""

    @functools.wraps(fn)
    def wrapper(source: str, *args: Any, **kwargs: Any) -> Any:
        result = fn(source, *args, **kwargs)
        if isinstance(result, tuple):
            return (follow(source, result[0]), *result[1:])
        return follow(source, result)

    return wrapper  # type: ignore[return-value]
