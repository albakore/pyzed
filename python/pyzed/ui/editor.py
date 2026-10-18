"""A themed code editor (gutter, git markers, syntax colors) and a terminal view."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .. import _core
from ..theme import Theme
from .base import _theme

_EXT_TOKENS = {"py": "py", "rs": "rs", "js": "js", "ts": "ts", "tsx": "tsx", "jsx": "js", "md": "md", "toml": "toml",
               "json": "json", "yaml": "yaml", "yml": "yaml", "html": "html", "css": "css", "sh": "sh", "go": "go",
               "c": "c", "h": "c", "cpp": "cpp", "rb": "rb", "java": "java", "sql": "sql", "lua": "lua"}


def language_token(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else "txt"
    return _EXT_TOKENS.get(ext, ext)


def editor(
    id: str,  # noqa: A002
    text: str = "",
    *,
    language: Optional[str] = None,
    path: Optional[str] = None,
    on_change: Any = None,
    on_cursor: Any = None,
    markers: Optional[Dict[int, str]] = None,
    font_size: Optional[float] = None,
    line_height: Optional[float] = None,
    gutter: bool = True,
    wrap: bool = False,
    placeholder: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A Zed-styled code editor.

    ``id`` keys the editor's internal buffer (text, cursor, undo): reuse it to keep state across
    renders and use a new one (e.g. the file path) for a different buffer. ``text`` is only the
    initial content; use ``Command.set_editor_text`` to replace it later.

    ``markers`` maps 1-based line numbers to git statuses ("created", "modified", "deleted").
    ``on_change(text)`` and ``on_cursor(line, column)`` may return messages.
    """
    t = _theme(theme)
    size = font_size or t.buffer_font_size
    status_colors = {"created": t.created, "modified": t.modified, "deleted": t.deleted}
    return _core.code_editor(
        id,
        text,
        language=language or (language_token(path) if path else "txt"),
        size=size,
        line_height=line_height or round(size * 1.6),
        syntax=t.syntax_scopes(),
        bg=t.editor,
        color=t.editor_text,
        selection_color=t.selection,
        placeholder=placeholder,
        placeholder_color=t.text_placeholder,
        gutter=gutter,
        gutter_color=t.line_number,
        gutter_active_color=t.line_number_active,
        markers={line: status_colors.get(s, s) for line, s in (markers or {}).items()},
        wrap=wrap,
        on_change=on_change,
        on_cursor=on_cursor,
    )


Segment = Tuple[str, Optional[str]]
Line = Union[str, Sequence[Segment]]

_SGR = re.compile(r"\x1b\[([0-9;]*)m")
_ANSI_NAMES = {30: "black", 31: "red", 32: "green", 33: "yellow", 34: "blue", 35: "magenta", 36: "cyan", 37: "white",
               90: "bright_black", 91: "red", 92: "green", 93: "yellow", 94: "blue", 95: "magenta", 96: "cyan", 97: "white"}


def ansi(text: str) -> List[List[Segment]]:
    """Parses text with ANSI color escapes into lines of ``(text, ansi_color_name)`` segments."""
    lines: List[List[Segment]] = []
    color: Optional[str] = None
    for raw in text.split("\n"):
        segments: List[Segment] = []
        pos = 0
        for match in _SGR.finditer(raw):
            if match.start() > pos:
                segments.append((raw[pos:match.start()], color))
            for code in (int(c) for c in (match.group(1) or "0").split(";") if c):
                if code == 0 or code == 39:
                    color = None
                elif code == 2:
                    color = "dim"
                elif code in _ANSI_NAMES:
                    color = _ANSI_NAMES[code]
            pos = match.end()
        if pos < len(raw):
            segments.append((raw[pos:], color))
        lines.append(segments)
    return lines


def terminal(
    lines: Union[str, Sequence[Line]],
    *,
    font_size: float = 13,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A read-only terminal view. ``lines`` may be a string with ANSI colors or a list of segment lists."""
    t = _theme(theme)
    if isinstance(lines, str):
        lines = ansi(lines)
    rows = []
    for line in lines:
        if isinstance(line, str):
            line = [(line, None)]
        if not line:
            rows.append(_core.space(height=round(font_size * 1.5)))
            continue
        rows.append(
            _core.row(
                [
                    _core.text(seg, size=font_size, font="mono", line_height=1.5, wrap=False,
                               color=(t.ansi[color] if color in t.ansi else t.color(color)) if color else t.text)
                    for seg, color in line
                ]
            )
        )
    return _core.container(
        _core.scrollable(_core.column(rows, width="fill"), id=id, anchor_bottom=True, height="fill",
                         scroller=t.scrollbar, scroller_hover=t.scrollbar_hover, scrollbar_width=6),
        padding=(6, 12),
        width="fill",
        height="fill",
        bg=t.terminal,
    )
