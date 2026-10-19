"""A themed code editor (gutter, git markers, syntax colors) and a terminal view."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .. import _core
from ..theme import Theme, alpha
from .base import _theme

_EXT_TOKENS = {"py": "py", "rs": "rs", "js": "js", "ts": "ts", "tsx": "tsx", "jsx": "js", "md": "md", "toml": "toml",
               "json": "json", "yaml": "yaml", "yml": "yaml", "html": "html", "css": "css", "sh": "sh", "go": "go",
               "c": "c", "h": "c", "cpp": "cpp", "rb": "rb", "java": "java", "sql": "sql", "lua": "lua"}


#: Default width of the editor's minimap, in pixels.
MINIMAP_WIDTH = 100.0
#: Shapes accepted by ``editor(cursor_shape=...)``.
CURSOR_SHAPES = ("bar", "block", "underline", "hollow")


def language_token(path: str) -> str:
    """The highlighter token for a file path, from its extension (``"main.rs"`` -> ``"rs"``)."""
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
    active_line: bool = True,
    height: Any = "fill",
    placeholder: Optional[str] = None,
    annotations: Optional[Dict[int, Union[str, Tuple[str, str]]]] = None,
    show_whitespace: bool = False,
    tab_size: Optional[int] = None,
    capture_keys: Sequence[str] = (),
    on_scroll: Any = None,
    auto_close: bool = True,
    folding: bool = True,
    minimap: Union[bool, float] = False,
    cursor_shape: str = "bar",
    cursor_blink: bool = True,
    cursor_width: float = 2.0,
    cursor_color: Optional[str] = None,
    on_zoom: Any = None,
    on_action: Any = None,
    highlights: Optional[Sequence[Tuple[int, int, int, int]]] = None,
    match_brackets: bool = True,
    selection_highlight: bool = True,
    font: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A Zed-styled code editor.

    ``id`` keys the editor's internal buffer (text, cursor, undo): reuse it to keep state across
    renders and use a new one (e.g. the file path) for a different buffer. ``text`` is only the
    initial content; use ``Command.set_editor_text`` to replace it later.

    ``markers`` maps 1-based line numbers to git statuses ("created", "modified", "deleted").
    ``on_change(text)`` and ``on_cursor(line, column)`` may return messages.

    Like Zed, long lines scroll horizontally while the line numbers stay put; with
    ``wrap=True`` they wrap at the editor's width instead, and the gutter numbers only the
    first row of each wrapped line. ``active_line`` highlights the line with the cursor.
    The view follows the cursor (arrows, PageUp/PageDown, ``Command.set_editor_cursor``).

    ``height`` is ``"fill"`` by default; inside a vertical ``scrollable`` use a number or
    ``"shrink"`` (tall enough for every line).

    ``annotations`` maps 1-based lines to virtual text drawn after the line's last character
    (``"2 references"`` or ``("undefined name", "#e06c75")``), as used for code lens and
    inline diagnostics. ``show_whitespace`` draws spaces as ``·`` and tabs as ``→``.
    With ``tab_size``, Tab inserts spaces, Enter keeps the indentation (one level more after
    ``:``) and Backspace removes a whole level. Keys in ``capture_keys`` (``"up"``, ``"down"``,
    ``"enter"``, ``"tab"``, ``"escape"``...) are left to the app's ``on_key``, e.g. while a
    completion list is open. ``on_scroll(info)`` gets the scroll offset (``info["x"]``, ``info["y"]``).

    Like Zed:

    - ``auto_close`` inserts the closing bracket or quote as you type the opening one, wraps a
      selection in it, steps over a closer that is already there, deletes an empty pair with
      Backspace and opens an indented line when Enter is pressed between brackets.
    - ``folding`` shows chevrons in the gutter (on hover, and always on folded lines) that fold
      a block by indentation; a folded line ends in ``⋯`` (click it to unfold). Ctrl+Shift+[
      folds the block around the cursor and Ctrl+Shift+] unfolds it; ``Command.fold_all(id)``
      folds everything. Callbacks, markers and annotations keep using real line numbers.
    - ``minimap=True`` (or a width in pixels) adds a minimap on the right; click or drag it to scroll.
    - ``cursor_shape`` is ``"bar"``, ``"block"``, ``"underline"`` or ``"hollow"``; ``cursor_blink``,
      ``cursor_width`` (of the bar) and ``cursor_color`` (the theme's player color by default).
    - ``on_zoom(step)`` is called with ``1``, ``-1`` or ``0`` (reset) for Ctrl+= / Ctrl+- / Ctrl+0
      and Ctrl+mouse wheel; change ``font_size`` in response.
    - Multiple cursors: Alt+click adds (or removes) a cursor, Alt+Shift+Up/Down adds one above or
      below, Ctrl+D selects the next match of the selection (the word under the cursor first),
      Ctrl+Shift+L selects every match and Escape goes back to one cursor. Typing, deleting,
      pasting (one line per cursor when the counts match) and moving apply to every cursor.
    - Undo and redo (Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z), with consecutive typing undone at once.
    - Zed's editing keys: Alt+Up/Down move lines, Ctrl+Alt+Shift+Up/Down duplicate them,
      Ctrl+Shift+K deletes them, Ctrl+/ toggles comments, Ctrl+] / Ctrl+[ indent and outdent,
      Ctrl+L selects the line, Ctrl+Shift+J joins lines, Ctrl+Enter / Ctrl+Shift+Enter open a line
      below or above, Ctrl+M jumps to the matching bracket and Ctrl+K chords fold (Ctrl+K Ctrl+0
      folds everything, Ctrl+K Ctrl+J unfolds it). ``on_action(name)`` is called after each of them
      with Zed's action name (``"select_next"``, ``"move_line_up"``...); ``Command.editor_action(id,
      name)`` runs one and ``Command.editor_actions()`` lists them.
    - ``highlights`` paints ranges behind the text, as 1-based ``(line, column, end_line,
      end_column)`` with exclusive ends (search results). ``match_brackets`` outlines the bracket
      that matches the one next to the cursor and ``selection_highlight`` the other occurrences of
      the selected text.

    ``font`` is the typeface (``"mono"`` by default; ``"sans"`` makes a multi-line text box, like a
    chat message box). Shift+Enter always breaks the line, even with ``"enter"`` in ``capture_keys``.
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
        font=font,
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
        active_line=t.active_line if active_line else None,
        scrollbar_color=t.scrollbar,
        height=height,
        annotations=annotations,
        whitespace=alpha(t.line_number, 0.8) if show_whitespace else None,
        tab_size=tab_size,
        capture_keys=list(capture_keys),
        on_scroll=on_scroll,
        auto_close=auto_close,
        folding=folding,
        minimap=(MINIMAP_WIDTH if minimap is True else float(minimap)) if minimap else None,
        minimap_thumb=t.scrollbar_hover,
        cursor_shape=cursor_shape,
        cursor_blink=cursor_blink,
        cursor_width=cursor_width,
        cursor_color=cursor_color or (t.players[0] if t.players else t.accent),
        on_zoom=on_zoom,
        on_action=on_action,
        highlights=[tuple(h) for h in highlights or ()],
        highlight_color=t.search_match,
        match_brackets=match_brackets,
        selection_highlight=selection_highlight,
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
