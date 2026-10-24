"""A themed code editor (gutter, git markers, syntax colors) and a terminal view."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

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

#: The editor's default keys for each action (Zed's names and keys; Ctrl is Cmd on macOS).
DEFAULT_KEYS: Dict[str, Tuple[str, ...]] = {
    "undo": ("ctrl-z",),
    "redo": ("ctrl-y", "ctrl-shift-z"),
    "copy": ("ctrl-c",),
    "cut": ("ctrl-x",),
    "select_next": ("ctrl-d", "ctrl-shift-down"),
    "select_previous": ("ctrl-shift-up",),
    "select_all_matches": ("ctrl-shift-l", "ctrl-f2"),
    "add_selection_above": ("ctrl-alt-up",),
    "add_selection_below": ("ctrl-alt-down",),
    "split_selection_into_lines": ("alt-shift-i",),
    "undo_selection": ("ctrl-u",),
    "cancel": ("escape",),
    "select_line": ("ctrl-l",),
    "move_line_up": ("alt-up",),
    "move_line_down": ("alt-down",),
    "duplicate_line_up": ("alt-shift-up", "ctrl-alt-shift-up"),
    "duplicate_line_down": ("alt-shift-down", "ctrl-alt-shift-down"),
    "duplicate_selection": ("ctrl-shift-d",),
    "delete_line": ("ctrl-shift-k",),
    "join_lines": ("ctrl-shift-j",),
    "newline_below": ("ctrl-enter",),
    "newline_above": ("ctrl-shift-enter",),
    "indent": ("ctrl-]",),
    "outdent": ("ctrl-[", "shift-tab"),
    "toggle_comments": ("ctrl-/", "ctrl-k ctrl-c"),
    "move_to_enclosing_bracket": ("ctrl-m",),
    "delete_to_previous_word_start": ("ctrl-backspace",),
    "delete_to_next_word_end": ("ctrl-delete",),
    "move_to_beginning_of_line": ("home",),
    "select_to_beginning_of_line": ("shift-home",),
    "line_up": ("ctrl-up",),
    "line_down": ("ctrl-down",),
    "fold": ("ctrl-shift-[", "ctrl-k ctrl-["),
    "unfold_lines": ("ctrl-shift-]", "ctrl-k ctrl-]"),
    "toggle_fold": ("ctrl-k ctrl-l",),
    "fold_all": ("ctrl-k ctrl-0",),
    "unfold_all": ("ctrl-k ctrl-j",),
    "convert_to_upper_case": (),
    "convert_to_lower_case": (),
    "sort_lines_case_sensitive": (),
}

_MODIFIERS = {"ctrl": "ctrl", "control": "ctrl", "cmd": "ctrl", "super": "ctrl", "win": "ctrl", "secondary": "ctrl",
              "alt": "alt", "option": "alt", "opt": "alt", "shift": "shift"}
_KEY_ALIASES = {"esc": "escape", "return": "enter", "del": "delete", "pgup": "pageup", "pgdown": "pagedown"}
_NAMED_KEYS = {"up", "down", "left", "right", "enter", "tab", "escape", "pageup", "pagedown", "home", "end",
               "backspace", "delete", "space", "insert", *(f"f{n}" for n in range(1, 13))}


def _keystroke(text: str) -> Optional[str]:
    rest = text.strip().lower()
    mods = set()
    while True:
        cut = min((i for i in (rest.find("-"), rest.find("+")) if i >= 0), default=-1)
        if cut < 0 or cut == len(rest) - 1:
            break
        modifier = _MODIFIERS.get(rest[:cut])
        if modifier is None:
            return None
        mods.add(modifier)
        rest = rest[cut + 1:]
    key = _KEY_ALIASES.get(rest, rest)
    if len(key) != 1 and key not in _NAMED_KEYS:
        return None
    return "-".join([m for m in ("ctrl", "alt", "shift") if m in mods] + [key])


def parse_keys(text: str) -> Optional[str]:
    """Normalizes a Zed-style binding (``"Ctrl+Shift+K"`` -> ``"ctrl-shift-k"``, ``"ctrl-k ctrl-c"``), or
    ``None`` when it is not one the editor understands (chords must start with Ctrl+K)."""
    strokes = [_keystroke(part) for part in text.split()]
    if not strokes or len(strokes) > 2 or None in strokes:
        return None
    if len(strokes) == 2 and strokes[0] != "ctrl-k":
        return None
    return " ".join(strokes)  # type: ignore[arg-type]


def keymap_for(overrides: Mapping[str, str]) -> Dict[str, Optional[str]]:
    """Turns per-action overrides (``{"delete_line": "ctrl-shift-d"}``, ``""`` for no key, several keys
    separated by commas) into an ``editor(keymap=...)``: each overridden action loses its default keys."""
    keymap: Dict[str, Optional[str]] = {}
    for action, keys in overrides.items():
        for key in DEFAULT_KEYS.get(action, ()):
            keymap.setdefault(key, None)
    for action, keys in overrides.items():
        for key in (k.strip() for k in keys.split(",")):
            normalized = parse_keys(key) if key else None
            if normalized:
                keymap[normalized] = action
    return keymap


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
    hard_tabs: bool = False,
    backspace_unindent: bool = True,
    repeat_delay: Optional[float] = None,
    repeat_rate: Optional[float] = None,
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
    on_paste: Any = None,
    highlights: Optional[Sequence[Tuple[int, int, int, int]]] = None,
    match_brackets: bool = True,
    selection_highlight: bool = True,
    font: Optional[str] = None,
    keymap: Optional[Mapping[str, Optional[str]]] = None,
    scrollbar: bool = True,
    readonly: bool = False,
    on_hover: Any = None,
    hover_delay: float = 500,
    sticky_scroll: int = 0,
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
    ``:``) and Backspace removes a whole level (``backspace_unindent=False``: one space); tabs are
    drawn ``tab_size`` columns wide. ``hard_tabs=True`` indents with tab characters instead.
    ``repeat_delay`` (milliseconds) and ``repeat_rate`` (deletions per second) slow down Backspace
    and Delete held down: repeats start after the delay and come at most that often (they can't
    beat the system's own key repeat). Keys in ``capture_keys`` (``"up"``, ``"down"``,
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

    ``keymap`` changes the keys, like Zed's keymap: it maps a binding (``"ctrl-shift-d"``, ``"alt-up"``,
    ``"ctrl-k ctrl-u"``) to an action name (see ``DEFAULT_KEYS``), or to ``None`` to take a default key
    away; ``keymap_for`` builds one from per-action overrides. ``scrollbar=False`` hides the scrollbars.
``readonly=True`` lets the text be selected and copied (mouse, Shift+arrows, Ctrl+A, Ctrl+C) but not changed:
a log, a traceback or generated code to look at.

    IDE features, for an app that talks to a language server:

    - ``on_hover(info)`` is called when the mouse rests on a word for ``hover_delay`` milliseconds, with
      its ``line``, ``column``, ``start`` and ``end`` (1-based byte columns) and where it is drawn (``x``,
      ``y`` and ``height``, relative to the editor) to place a popup; and with ``None`` when the mouse
      leaves the word (after a moment, so it can reach the popup), types, clicks or scrolls.
    - Ctrl+click (Cmd+click) moves the cursor and calls ``on_action("go_to_definition")``.
    - ``sticky_scroll=5`` pins up to five headers of the blocks around the first visible line (the
      ``class`` and ``def`` you are scrolling through) to the top; a click on one jumps to it.

    ``font`` is the typeface (``"mono"`` by default; ``"sans"`` makes a multi-line text box, like a
    chat message box). Shift+Enter always breaks the line, even with ``"enter"`` in ``capture_keys``.

    Events:
        ``on_change(text)``: Callable that receives the new value.
        ``on_cursor(line, column)``: Callable that receives ``(line, column)``.
        ``on_scroll(info)``: Called on scroll.
        ``on_zoom(step)``: Callable that receives ``1``, ``-1`` or ``0`` for Ctrl+= / Ctrl+- / Ctrl+0 and
            Ctrl+wheel.
        ``on_action(name)``: Callable that receives the name of each editor action that runs (``"undo"``,
            ``"select_next"``…), e.g. to count them.
        ``on_paste()``: Called after Ctrl+V (Cmd+V, Shift+Insert) pastes the clipboard's text, if it holds any;
            a chat box reads an image from the clipboard with ``Command.paste_image``.
        ``on_hover(info)``: Callable that receives the word the mouse rests on (a dict), or ``None``.
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
        hard_tabs=hard_tabs,
        backspace_unindent=backspace_unindent,
        repeat_delay=repeat_delay,
        repeat_rate=repeat_rate,
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
        on_paste=on_paste,
        highlights=[tuple(h) for h in highlights or ()],
        highlight_color=t.search_match,
        match_brackets=match_brackets,
        selection_highlight=selection_highlight,
        keymap=dict(keymap) if keymap else None,
        scrollbar=scrollbar,
        readonly=readonly,
        on_hover=on_hover,
        hover_delay=hover_delay,
        sticky_scroll=sticky_scroll,
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
