"""The designer's code editor: event code with completion, diagnostics, code lens, search and settings.

``CodeAssist`` holds the editor's state (cursor, completion list, search, settings) and talks to the
language servers through ``CodeIntel``; ``code_panel`` and ``settings_dialog`` are its views.
The designer forwards the editor's callbacks and the keys pressed while it has focus.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha, themes
from . import intellisense as _intel
from . import settings as _settings
from . import telemetry as _telemetry
from .intellisense import CodeIntel, CompletionItem, Diagnostic
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Must match the editor's layout in ``src/editor.rs``.
PAD_Y = 4.0
PAD_LEFT = 4.0
MARKER_WIDTH = 3.0
#: Advance of one character of the editor font (IBM Plex Mono) per pixel of font size.
CHAR_WIDTH = 0.6

POPUP_ROWS = 9
ROW_HEIGHT = 24.0
#: Height of the list's padding and footer.
FOOTER = 34.0
LIST_WIDTH = 320.0
#: Width of the completion list's scrollbar.
SCROLLBAR = 4.0
DOC_WIDTH = 340.0
CAPTURED = ("up", "down", "enter", "tab", "escape", "pageup", "pagedown")
FIND_ID = "designer-code-find"
REPLACE_ID = "designer-code-replace"
GOTO_ID = "designer-code-goto"
#: Most matches the search highlights.
MAX_MATCHES = 5000

#: A match as 1-based ``(line, column, end_line, end_column)``, with byte columns like the editor's.
Range = Tuple[int, int, int, int]


@dataclass
class Search:
    """The find (and replace) bar, like Zed's buffer search."""

    query: str = ""
    replacement: str = ""
    case: bool = False
    word: bool = False
    regex: bool = False
    replacing: bool = False
    #: Index of the current match in ``matches``.
    index: int = 0
    matches: List[Range] = field(default_factory=list)
    #: The regular expression's error, if it does not compile.
    error: str = ""


@dataclass
class Completion:
    """An open completion list."""

    line: int
    #: 1-based column where the word being completed starts.
    start: int
    items: List[CompletionItem]
    shown: List[CompletionItem]
    index: int = 0
    #: True while waiting for the language server (``shown`` may already have local items).
    loading: bool = False
    #: The first row on screen; the wheel scrolls it, moving the selection brings it back into view.
    top: int = 0
    #: Keep the highlighted row in view (off after the wheel scrolls the list).
    follow: bool = True

    @property
    def selected(self) -> Optional[CompletionItem]:
        """The highlighted item of the filtered list, or ``None`` if the list is empty."""
        return self.shown[self.index] if 0 <= self.index < len(self.shown) else None


class CodeAssist:
    """Completion, diagnostics, code lens and preferences for the designer's code editor."""

    def __init__(self, designer: "Designer", *, servers: bool = True) -> None:
        self.d = designer
        self.settings = _settings.load()
        self.intel = CodeIntel(self.settings, dispatch=self._post, on_update=self._noop)
        self.servers = servers
        self.cursor: Tuple[int, int] = (1, 1)
        self.scroll: Tuple[float, float] = (0.0, 0.0)
        self.completion: Optional[Completion] = None
        self.problems_open = True
        self.search: Optional[Search] = None
        #: The "go to line" field's text while it is open.
        self.goto: Optional[str] = None
        self._typed = False
        self._text = ""

    # -- plumbing -------------------------------------------------------------
    @staticmethod
    def _post(fn: Any) -> None:
        try:
            _core.post(fn)
        except RuntimeError:  # no app running (tests, scripts): run it right away
            fn()

    @staticmethod
    def _noop() -> None:
        """Server updates arrive as posted messages, which re-render the designer by themselves."""

    @property
    def handler(self) -> Optional[str]:
        """The name of the handler being edited, or ``None`` when editing the whole file or nothing."""
        editing = self.d.editing
        if editing is None:
            return None
        return None if editing[0] == "*" else editing[0]

    def code_file(self) -> Path:
        """Returns the path of the document's code file (``<form name>.py`` in the working directory if
        unsaved)."""
        doc = self.d.doc
        if doc.code_path is not None:
            return doc.code_path
        return Path.cwd() / f"{doc.form.name}.py"

    # -- lifecycle --------------------------------------------------------------
    def opened(self) -> None:
        """The editor shows a new handler (or the whole file)."""
        self.completion = None
        self.cursor = (1, 1)
        self.scroll = (0.0, 0.0)
        if self.d.editing is None:
            return
        self._text = self.d.editing[1]
        if self.servers:
            self.intel.attach(self.code_file())
        self._sync()

    def closed(self) -> None:
        """The editor was closed: drops any open completion list."""
        self.completion = None

    def shutdown(self) -> None:
        """Stops the language servers (when the designer exits)."""
        self.intel.shutdown()

    def _sync(self) -> None:
        if self.d.editing is None:
            return
        self.intel.update(self.d.doc.code, self.handler, self.d.editing[1])
        self.intel.refresh_lenses(self.d.doc.form)

    # -- editor callbacks ---------------------------------------------------------
    def changed(self, text: str) -> None:
        """The text changed (called by the designer after storing it)."""
        self._typed = len(text) == len(self._text) + 1
        if len(text) < len(self._text) and self.completion is not None:
            self._typed = True  # deleting inside a word keeps the list open and refilters it
        self._text = text
        self.intel.update(self.d.doc.code, self.handler, text)
        if self.search is not None:
            self._find()

    def moved(self, line: int, column: int) -> Any:
        """The editor's cursor moved to ``line``, ``column`` (1-based).

        Refilters or closes the open completion list, and opens one after a typed character when autocomplete
        is on and the context calls for it. Returns ``None``.
        """
        self.cursor = (line, column)
        typed, self._typed = self._typed, False
        current = self._line(line)
        if self.completion is not None:
            c = self.completion
            word = _intel.word_before(current, column)
            if line != c.line or column < c.start or column - len(word) != c.start:
                self.completion = None
            else:
                self._refilter(word)
                return None
        if typed and self.settings.autocomplete and _intel.should_complete(current, column):
            self.open_completion()
        return None

    def scrolled(self, info: Dict[str, float]) -> None:
        """The editor scrolled; stores its ``x``/``y`` offsets in pixels (used to place the completion
        list)."""
        self.scroll = (float(info.get("x", 0.0)), float(info.get("y", 0.0)))

    def _line(self, line: int) -> str:
        lines = self._text.split("\n")
        return lines[line - 1] if 0 < line <= len(lines) else ""

    # -- completion ---------------------------------------------------------------
    def open_completion(self) -> None:
        """Opens the completion list for the word before the cursor.

        Designer completions (controls of the form) are shown right away; otherwise the list waits, marked
        ``loading``, for the language server. Closes it if there is nothing to show.
        """
        line, column = self.cursor
        current = self._line(line)
        word = _intel.word_before(current, column)
        start = column - len(word)
        local = _intel.designer_completions(self.d.doc.form, current, column)
        if local is not None:
            self.completion = Completion(line, start, local, _intel.filter_items(local, word))
            if not self.completion.shown:
                self.completion = None
            return
        self.completion = Completion(line, start, [], [], loading=True)
        if not self.intel.complete(line, column, self._received):
            self.completion = None

    def _received(self, items: List[CompletionItem]) -> None:
        c = self.completion
        if c is None:
            return
        c.items, c.loading = items, False
        line, column = self.cursor
        if line != c.line:
            self.completion = None
            return
        self._refilter(_intel.word_before(self._line(line), column))

    def _refilter(self, word: str) -> None:
        c = self.completion
        assert c is not None
        selected = c.selected
        c.shown = _intel.filter_items(c.items, word)
        if not c.shown and not c.loading:
            self.completion = None
            return
        c.index = c.shown.index(selected) if selected in c.shown else 0
        c.follow = True

    def move_selection(self, delta: int) -> None:
        """Moves the highlighted completion by ``delta`` rows: wrapping around for one step, clamped for
        larger (page) steps."""
        c = self.completion
        if c is None or not c.shown:
            return
        c.index = (c.index + delta) % len(c.shown) if abs(delta) == 1 else max(0, min(len(c.shown) - 1, c.index + delta))
        c.follow = True

    def scroll_completion(self, _x: float, y: float) -> None:
        """Scrolls the completion list by the mouse wheel (``y`` lines, positive up) without moving the
        highlighted row; the list keeps the rows in range when it is drawn."""
        c = self.completion
        if c is None:
            return
        c.top = max(0, c.top - round(y * 3))
        c.follow = False

    def select(self, index: int) -> Any:
        """Highlights completion ``index`` and accepts it (a click in the list); returns the editor
        commands."""
        if self.completion is not None:
            self.completion.index = index
            return self.accept()
        return None

    def accept(self) -> Any:
        """Inserts the highlighted completion (and any auto-import it brings) and closes the list.

        Returns the commands that set the editor's text and cursor, or ``None`` if nothing was highlighted.
        """
        c, self.completion = self.completion, None
        if c is None or c.selected is None or self.d.editing is None:
            return None
        line, column = self.cursor
        item = c.selected
        text, line, column = _intel.apply_completion(self._text, line, column, item)
        if item.additional_edits:
            text, line = self._apply_imports(item, text, line)
        self.d.set_code_buffer(text)
        self.cursor = (line, column)
        editor = self.d.editor_id
        return [_core.Command.set_editor_text(editor, text), _core.Command.set_editor_cursor(editor, line, column)]

    def _apply_imports(self, item: CompletionItem, text: str, line: int) -> Tuple[str, int]:
        """Adds an auto-import item's ``import``: to the module above the handler, or to the buffer."""
        offset = self.intel.offset
        if self.handler is None:
            added = _intel.apply_edits(text, item.additional_edits)
            return added, line + added.count("\n") - text.count("\n")
        above = [e for e in item.additional_edits if e["range"]["end"]["line"] < offset]
        inside = [e for e in item.additional_edits if e["range"]["start"]["line"] >= offset]
        if above:
            self.d.doc.set_code(_intel.apply_edits(self.d.doc.code, above))
        if inside:
            added = _intel.apply_edits(text, inside, offset)
            line += added.count("\n") - text.count("\n")
            text = added
        return text, line

    def close_completion(self) -> None:
        """Closes the completion list."""
        self.completion = None

    def on_key(self, combo: str) -> Any:
        """Keys pressed while the editor has focus; returns ``(handled, result)``."""
        if combo in ("ctrl-space", "ctrl- "):
            self.open_completion()
            return True, None
        panel = {
            "ctrl-f": lambda: self.open_search(),
            "ctrl-h": lambda: self.open_search(replacing=True),
            "ctrl-g": self.open_goto,
        }
        if combo in panel:
            return True, panel[combo]()
        if self.search is not None and combo in ("f3", "shift-f3", "shift-enter", "alt-enter", "escape"):
            if combo == "escape":
                return True, self.close_search()
            if combo == "alt-enter":
                return True, self.select_all_matches()
            return True, self.next_match(-1 if combo.startswith("shift") else 1)
        if self.goto is not None and combo == "escape":
            return True, self.close_goto()
        c = self.completion
        if c is None:
            return False, None
        actions = {
            "up": lambda: self.move_selection(-1),
            "down": lambda: self.move_selection(1),
            "pageup": lambda: self.move_selection(-POPUP_ROWS),
            "pagedown": lambda: self.move_selection(POPUP_ROWS),
            "enter": self.accept,
            "tab": self.accept,
            "escape": self.close_completion,
        }
        if combo in actions:
            return True, actions[combo]()
        return False, None

    @property
    def captured_keys(self) -> Tuple[str, ...]:
        """Keys the editor must hand to the designer instead of handling them: the list navigation keys while
        a completion list is shown, else none."""
        return CAPTURED if self.completion is not None and self.completion.shown else ()

    # -- diagnostics and lenses -----------------------------------------------------
    def diagnostics(self) -> List[Diagnostic]:
        """Returns the language servers' errors, warnings and information (hints left out) for the code."""
        return [d for d in self.intel.diagnostics() if d.severity <= 3]

    def annotations(self, t: Theme) -> Dict[int, Any]:
        """Returns the end-of-line annotations by line: code lens texts and, if enabled, the most severe
        diagnostic of each line as ``(text, color)`` in theme ``t``."""
        out: Dict[int, Any] = {}
        if self.settings.code_lens:
            out.update(self.intel.lens_annotations())
        if self.settings.inline_diagnostics:
            for diag in sorted(self.diagnostics(), key=lambda d: -d.severity):
                color = {1: t.error, 2: t.warning}.get(diag.severity, t.info)
                out[diag.line] = (f"● {diag.message}", alpha(color, 0.9))
        return out

    def go_to(self, diag: Diagnostic) -> Any:
        """Moves the cursor to diagnostic ``diag`` (a click in the problems list); returns the editor
        command."""
        self.cursor = (diag.line, diag.column)
        self.completion = None
        return _core.Command.set_editor_cursor(self.d.editor_id, diag.line, diag.column)

    def toggle_problems(self) -> None:
        """Shows or hides the problems list under the editor."""
        self.problems_open = not self.problems_open

    # -- settings -------------------------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        """Changes editor setting ``key`` to ``value``, saves the settings and applies them to the servers."""
        self.settings = replace(self.settings, **{key: value})
        _settings.save(self.settings)
        self.intel.apply_settings(self.settings)
        if key == "code_lens" and value:
            self.intel.refresh_lenses(self.d.doc.form)

    def setter(self, key: str) -> Any:
        """Returns a callback that sets editor setting ``key`` to the value it receives (for settings
        widgets)."""
        return lambda value: self.set(key, value)

    def zoom(self, step: float) -> None:
        """Ctrl+= / Ctrl+- / Ctrl+0 and Ctrl+wheel in the editor: one point bigger, smaller or back to default."""
        size = _settings.DEFAULT_FONT if step == 0 else self.settings.font_size + (1 if step > 0 else -1)
        size = min(max(size, _settings.MIN_FONT), _settings.MAX_FONT)
        if size != self.settings.font_size:
            self.set("font_size", size)

    def action_ran(self, name: str) -> None:
        """An editor action ran (``on_action``): counted by the telemetry when it is on."""
        _telemetry.get().count(f"editor.{name}")

    # -- search -----------------------------------------------------------------------
    def open_search(self, replacing: bool = False) -> Any:
        """Opens the find bar (``replacing`` also shows the replace field), seeded with the word under the
        cursor when it is empty; returns the command that focuses it."""
        if self.search is None:
            self.search = Search()
        s = self.search
        s.replacing = s.replacing or replacing
        if not s.query:
            line, column = self.cursor
            word = _word_at(self._line(line), _char_index(self._line(line), column))
            s.query = word
        self._find()
        _telemetry.get().count("editor.search" if not replacing else "editor.replace_open")
        # Selected, so typing replaces the seeded word (like Zed).
        return _core.Command.select_all(FIND_ID)

    def close_search(self) -> Any:
        """Closes the find bar and gives the keyboard back to the editor."""
        self.search = None
        return _core.Command.focus(self.d.editor_id)

    def set_query(self, query: str) -> Any:
        """The find field changed: searches again and selects the match nearest the cursor."""
        if self.search is None:
            return None
        self.search.query = query
        self._find(nearest=True)
        return self._select_current()

    def set_replacement(self, text: str) -> None:
        """The replace field changed."""
        if self.search is not None:
            self.search.replacement = text

    def toggle_option(self, name: str) -> Any:
        """Toggles a search option: ``"case"``, ``"word"``, ``"regex"`` or ``"replacing"``."""
        if self.search is None:
            return None
        setattr(self.search, name, not getattr(self.search, name))
        self._find(nearest=True)
        return None if name == "replacing" else self._select_current()

    def _find(self, nearest: bool = False) -> None:
        s = self.search
        if s is None:
            return
        s.matches, s.error = find_matches(self._text, s.query, case=s.case, word=s.word, regex=s.regex)
        if not s.matches:
            s.index = 0
        elif nearest:
            here = (self.cursor[0], self.cursor[1])
            s.index = next((i for i, m in enumerate(s.matches) if (m[2], m[3]) > here), 0)
        else:
            s.index = min(s.index, len(s.matches) - 1)

    def _select_current(self) -> Any:
        s = self.search
        if s is None or not s.matches:
            return None
        return _core.Command.select_editor_ranges(self.d.editor_id, [s.matches[s.index]])

    def next_match(self, step: int = 1) -> Any:
        """Selects the next (``step=1``) or previous (``-1``) match, wrapping around."""
        s = self.search
        if s is None or not s.matches:
            return None
        s.index = (s.index + step) % len(s.matches)
        return self._select_current()

    def select_all_matches(self) -> Any:
        """Puts a cursor on every match (Zed's Alt+Enter) and focuses the editor."""
        s = self.search
        if s is None or not s.matches:
            return None
        ordered = s.matches[s.index:] + s.matches[: s.index]
        _telemetry.get().count("editor.select_all_matches")
        return _core.Command.batch([_core.Command.select_editor_ranges(self.d.editor_id, ordered),
                                    _core.Command.focus(self.d.editor_id)])

    def _replacement(self, match: Range) -> str:
        s = self.search
        assert s is not None
        if not s.regex:
            return s.replacement
        text = _slice(self._text, match)
        pattern = _pattern(s.query, case=s.case, word=s.word, regex=True)
        found = pattern.fullmatch(text) if pattern else None
        try:
            return found.expand(s.replacement) if found else s.replacement
        except (re.error, IndexError):
            return s.replacement

    def replace_current(self) -> Any:
        """Replaces the current match and moves on to the next one."""
        s = self.search
        if s is None or not s.matches:
            return None
        match = s.matches[s.index]
        _telemetry.get().count("editor.replace")
        return _core.Command.replace_editor_ranges(self.d.editor_id, [(match, self._replacement(match))])

    def replace_all(self) -> Any:
        """Replaces every match, as one undo step."""
        s = self.search
        if s is None or not s.matches:
            return None
        _telemetry.get().count("editor.replace_all")
        return _core.Command.replace_editor_ranges(self.d.editor_id,
                                                   [(m, self._replacement(m)) for m in s.matches])

    # -- go to line -------------------------------------------------------------------
    def open_goto(self) -> Any:
        """Opens the "go to line" field (Ctrl+G); returns the command that focuses it."""
        self.goto = ""
        return _core.Command.focus(GOTO_ID)

    def set_goto(self, text: str) -> None:
        """The "go to line" field changed."""
        self.goto = text

    def close_goto(self) -> Any:
        """Closes the "go to line" field and gives the keyboard back to the editor."""
        self.goto = None
        return _core.Command.focus(self.d.editor_id)

    def submit_goto(self) -> Any:
        """Moves the cursor to the typed ``line`` or ``line:column`` and closes the field."""
        target = parse_goto(self.goto or "", self._text.count("\n") + 1)
        self.goto = None
        commands = [_core.Command.focus(self.d.editor_id)]
        if target is not None:
            line, column = target
            byte = len(self._line(line)[: column - 1].encode("utf-8")) + 1
            self.cursor = (line, byte)
            commands.insert(0, _core.Command.set_editor_cursor(self.d.editor_id, line, byte))
            _telemetry.get().count("editor.go_to_line")
        return _core.Command.batch(commands)

    def restart_servers(self) -> None:
        """Restarts the language servers, re-attaching them to the code file if the editor is open."""
        if self.servers and self.d.editing is not None:
            self.intel.attach(self.code_file())
        self.intel.restart()

    def format(self, source: str) -> str:
        """Returns ``source`` formatted with ruff when "format on apply" is on (unchanged otherwise or if
        formatting fails)."""
        if not self.settings.format_on_apply:
            return source
        formatted = _intel.format_code(source, self.intel.env)
        return formatted if formatted is not None else source

    def editor_theme(self, t: Theme) -> Theme:
        """Returns the theme chosen for the editor in its settings, or the designer's theme ``t``."""
        if self.settings.theme:
            try:
                return themes.get(self.settings.theme)
            except (KeyError, ValueError):
                return t
        return t


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------


def _pattern(query: str, *, case: bool, word: bool, regex: bool) -> Optional["re.Pattern[str]"]:
    body = query if regex else re.escape(query)
    if word:
        body = rf"\b(?:{body})\b"
    try:
        return re.compile(body, 0 if case else re.IGNORECASE)
    except re.error:
        return None


def find_matches(text: str, query: str, *, case: bool = False, word: bool = False,
                 regex: bool = False) -> Tuple[List[Range], str]:
    """Finds ``query`` in ``text``; returns the matches as 1-based ``(line, column, end_line, end_column)``
    ranges with byte columns (like the editor's) and exclusive ends, and the regular expression's error
    (``""`` if none). Empty matches are skipped."""
    if not query:
        return [], ""
    pattern = _pattern(query, case=case, word=word, regex=regex)
    if pattern is None:
        try:
            re.compile(query)
        except re.error as err:
            return [], str(err)
        return [], ""
    lines = text.split("\n")
    starts = [0]
    for line in lines[:-1]:
        starts.append(starts[-1] + len(line) + 1)

    def where(offset: int) -> Tuple[int, int]:
        index = bisect.bisect_right(starts, offset) - 1
        line = lines[index]
        return index + 1, len(line[: offset - starts[index]].encode("utf-8")) + 1

    out: List[Range] = []
    for m in pattern.finditer(text):
        if m.end() == m.start():
            continue
        out.append((*where(m.start()), *where(m.end())))
        if len(out) >= MAX_MATCHES:
            break
    return out, ""


def _slice(text: str, match: Range) -> str:
    lines = text.split("\n")
    (l1, c1, l2, c2) = match

    def offset(line: int, column: int) -> int:
        head = lines[line - 1].encode("utf-8")[: column - 1].decode("utf-8", "ignore")
        return sum(len(x) + 1 for x in lines[: line - 1]) + len(head)

    return text[offset(l1, c1):offset(l2, c2)]


def _char_index(line: str, column: int) -> int:
    """The character index of 1-based byte ``column`` in ``line``."""
    return len(line.encode("utf-8")[: column - 1].decode("utf-8", "ignore"))


def _word_at(line: str, index: int) -> str:
    start = index
    while start > 0 and (line[start - 1].isalnum() or line[start - 1] == "_"):
        start -= 1
    end = index
    while end < len(line) and (line[end].isalnum() or line[end] == "_"):
        end += 1
    return line[start:end]


def parse_goto(text: str, line_count: int) -> Optional[Tuple[int, int]]:
    """Parses "go to line" input: ``"12"`` or ``"12:5"`` (1-based, clamped to the text); ``None`` if it is
    not a number."""
    parts = text.strip().split(":")
    try:
        line = int(parts[0])
        column = int(parts[1]) if len(parts) > 1 and parts[1].strip() else 1
    except ValueError:
        return None
    return min(max(line, 1), max(line_count, 1)), max(column, 1)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------


def _kind_color(t: Theme, name: str) -> str:
    if name in t.ansi:
        return t.ansi[name]
    return t.color(name)


_ANSI_FOR = {"purple": "magenta", "orange": "red"}


def kind_badge(item: CompletionItem, t: Theme, size: float = 16) -> Any:
    """Returns the colored icon of a completion item's kind, ``size`` pixels square, with a small lock for
    private names."""
    icon, color = item.icon
    color = _kind_color(t, _ANSI_FOR.get(color, color))
    badge = _core.container(_icon(icon, size=size - 5, color=color), width=size, height=size, align_x="center",
                            align_y="center", radius=4, bg=alpha(color, 0.16))
    if not item.private:
        return badge
    lock = _core.container(_icon("lock", size=8, color=t.text_muted), width=10, height=10, align_x="center",
                           align_y="center", radius=5, bg=t.elevated)
    return _core.stack([badge, _core.pin(lock, x=size - 7, y=size - 7)], width=size + 3, height=size + 3)


def completion_popup(a: CodeAssist, t: Theme, visible_rows: int = POPUP_ROWS, max_height: float = 300) -> Any:
    """Builds the completion list (``visible_rows`` rows, scrolled with the wheel or to keep the highlighted
    one in view, with a scrollbar when there are more) and, beside it, the highlighted item's signature and
    documentation, at most ``max_height`` pixels tall."""
    c = a.completion
    assert c is not None
    visible_rows = max(1, visible_rows)
    last_top = max(len(c.shown) - visible_rows, 0)
    if c.follow:
        c.top = min(c.top, c.index)
        c.top = max(c.top, c.index - visible_rows + 1)
    c.top = min(max(c.top, 0), last_top)
    scrolls = len(c.shown) > visible_rows
    room = LIST_WIDTH - 2 * 4 - 2 - 2 * 8 - 16 - 8 - (SCROLLBAR + 2 if scrolls else 0)
    rows: List[Any] = []
    for i, item in enumerate(c.shown[c.top: c.top + visible_rows], start=c.top):
        selected = i == c.index
        label_color = t.text_muted if item.private or item.is_dunder else t.text
        label, detail = fit_row(item.label, " ".join(item.detail.split()), room)
        rows.append(_core.button(
            _core.container(_core.row([
                kind_badge(item, t),
                _core.text(label, size=13, font="mono", color=label_color, wrap=False),
                _core.space(width="fill"),
                _core.text(detail, size=11, color=t.text_muted, wrap=False) if detail else None,
            ], spacing=8, align="center"), width="fill", clip=True),
            lambda i=i: a.select(i), padding=(0, 8), height=ROW_HEIGHT, width="fill",
            bg=t.element_selected if selected else "transparent", hover_bg=t.element_hover, radius=4))
    if scrolls and rows:
        track = len(rows) * ROW_HEIGHT
        thumb = max(track * visible_rows / len(c.shown), 16.0)
        offset = (track - thumb) * c.top / last_top if last_top else 0.0
        bar = _core.stack([
            _core.container(_core.space(), width=SCROLLBAR, height=track, radius=SCROLLBAR / 2,
                            bg=alpha(t.text_muted, 0.08)),
            _core.pin(_core.container(_core.space(), width=SCROLLBAR, height=thumb, radius=SCROLLBAR / 2,
                                      bg=alpha(t.text_muted, 0.45)), x=0, y=offset),
        ], width=SCROLLBAR, height=track)
        body: Any = _core.row([_core.column(rows, spacing=0, width="fill"), bar], spacing=2)
    else:
        body = _core.column(rows, spacing=0, width="fill")
    body = _core.mouse_area(body, on_scroll=a.scroll_completion)
    if c.loading and not rows:
        rows.append(_core.container(ui.label(tr("Loading…"), size="sm", color="text_muted", theme=t), padding=(4, 8)))
    footer = _core.container(
        _core.row([ui.label(f"{c.index + 1}/{len(c.shown)}" if c.shown else "", size="xs", color="text_muted",
                            theme=t),
                   _core.space(width="fill"),
                   ui.label(tr("↵ insert  esc close"), size="xs", color="text_muted", theme=t)]),
        padding=(2, 8), width="fill")
    listing = _core.container(_core.column([body, footer], spacing=0), width=LIST_WIDTH, padding=4, clip=True,
                              bg=t.elevated, border_color=t.border, border_width=1, radius=6)
    item = c.selected
    if item is None or not (item.detail or item.documentation):
        return listing
    doc_parts = [
        _core.row([kind_badge(item, t, 18), _core.text(item.label, size=13, font="mono", color=t.text, width="fill"),
                   ui.badge(tr("private"), theme=t) if item.private else None], spacing=8, align="center"),
        _core.text(item.detail, size=12, font="mono", color=t.text_muted) if item.detail else None,
        ui.divider(theme=t) if item.documentation else None,
        _core.container(ui.markdown(_short_doc(item.documentation), size=12, theme=t),
                        max_height=max(max_height - 80, 40), clip=True) if item.documentation else None,
    ]
    docs = _core.container(_core.column(doc_parts, spacing=6), width=DOC_WIDTH, max_height=max_height, clip=True,
                           padding=10, bg=t.elevated,
                           border_color=t.border, border_width=1, radius=6)
    return _core.row([listing, docs], spacing=4)


def fit_row(label: str, detail: str, room: float) -> Tuple[str, str]:
    """Cuts a completion row's ``label`` (13 px mono) and ``detail`` (11 px) with "…" so both fit in
    ``room`` pixels; the label wins, and the detail is dropped when too little of it would show."""
    label_char, detail_char, gap = 13 * CHAR_WIDTH, 6.2, 12
    most = max(int(room // label_char), 4)
    if len(label) > most:
        return label[: most - 1] + "…", ""
    left = int((room - len(label) * label_char - gap) // detail_char)
    if left < 8 or not detail:
        return label, ""
    return label, _short(detail, left)


def _short_doc(text: str, limit: int = 1200) -> str:
    """The start of a docstring, cut at a paragraph break near ``limit``."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n\n", 0, limit)
    return text[: cut if cut > limit // 3 else limit].rstrip() + "\n\n…"


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _editor_area(a: CodeAssist, editor: Any, below: List[Any], size: float, line_count: int, gutter: bool) -> Any:
    """The editor, with the completion list pinned under (or above) the word being completed, and ``below`` it.

    The widget tree is the same with or without the list, so the editor keeps its focus.
    """
    t = a.d.theme_obj
    lh = round(size * 1.6)
    left = (MARKER_WIDTH + max(len(str(line_count)), 2) * size * 0.62 + 28) if gutter else 0.0
    char = size * CHAR_WIDTH
    below_height = sum(h for _, h in below)

    def place(width: float, height: float) -> Any:
        c = a.completion
        popup: Any = _core.space(width=0, height=0)
        x = y = 0.0
        if c is not None and (c.shown or c.loading):
            sx, sy = a.scroll
            visible = height - below_height
            x = left + PAD_LEFT + (c.start - 1) * char - sx - 30
            y = PAD_Y + c.line * lh - sy + 2
            # below the line if it fits, else on the side with more room, with as many rows as fit
            space_below, space_above = visible - y - 4, y - lh - 6
            wanted = min(len(c.shown), POPUP_ROWS) if c.shown else 1
            up = space_below < wanted * ROW_HEIGHT + FOOTER and space_above > space_below
            room = space_above if up else space_below
            rows = max(1, min(wanted, int((room - FOOTER) // ROW_HEIGHT)))
            if up:
                y = y - lh - 4 - (rows * ROW_HEIGHT + FOOTER)
            docs = c.selected is not None and bool(c.selected.detail or c.selected.documentation)
            x = max(4.0, min(x, width - LIST_WIDTH - (DOC_WIDTH + 4 if docs else 0) - 4))
            popup = completion_popup(a, t, rows, max(room, 80))
        area = _core.stack([editor, _core.pin(popup, x=x, y=y)], width="fill", height="fill")
        return _core.column([area, *(w for w, _ in below)], width="fill", height="fill")

    return _core.responsive(place)


def problems_list(a: CodeAssist, diags: List[Diagnostic], t: Theme) -> Tuple[Any, float]:
    """Builds the clickable list of diagnostics under the editor; returns ``(widget, height)`` in pixels."""
    icons = {1: ("circle-x", t.error), 2: ("triangle-alert", t.warning), 3: ("info", t.info)}
    rows = []
    for diag in diags:
        icon, color = icons.get(diag.severity, icons[3])
        source = " ".join(x for x in (diag.source, f"({diag.code})" if diag.code else "") if x)
        rows.append(_core.button(
            _core.row([_icon(icon, size=13, color=color),
                       _core.text(f"{diag.line}:{diag.column}", size=12, font="mono", color=t.text_muted, width=52),
                       _core.text(diag.message, size=12, color=t.text, wrap=False, width="fill"),
                       _core.text(source, size=11, color=t.text_muted, wrap=False)], spacing=8, align="center"),
            lambda diag=diag: a.go_to(diag), padding=(2, 12), width="fill", bg="transparent",
            hover_bg=t.element_hover))
    height = min(len(rows), 4) * 22 + 6
    return _core.container(_core.scrollable(_core.column(rows, width="fill"), scrollbar_width=4),
                           height=height, width="fill", padding=(3, 0), bg=t.panel), height


def code_panel(d: "Designer", t: Theme) -> Any:
    """Builds the code editor panel: header with the problems toggle and actions, the editor with its
    completion list, and the error line and problems list below it."""
    assert d.editing is not None
    a = d.assist
    s = a.settings
    handler, text = d.editing
    whole = handler == "*"
    path = d.doc.code_path.name if d.doc.code_path else f"{d.doc.form.name}.py"
    title = path if whole else f"{path} › {handler}()"
    diags = a.diagnostics()
    errors = sum(1 for x in diags if x.severity == 1)
    warnings = sum(1 for x in diags if x.severity == 2)
    problems = ui.button(f"{errors}  ·  {warnings}", a.toggle_problems, icon="circle-x" if errors else "circle-check",
                         variant="ghost", size="sm", selected=a.problems_open and bool(diags), theme=t)
    problems = ui.tooltip(problems, tr("Problems"), theme=t)
    header = ui.panel_header(title, icon="code", actions=[
        problems,
        ui.icon_button("sparkles", d.agent.open_inline, size="sm", tooltip=tr("Inline assist (Ctrl+Alt+I)"), theme=t),
        ui.icon_button("settings", d.open_editor_settings, size="sm", tooltip=tr("Editor settings"), theme=t),
        ui.button(tr("Whole file") if not whole else tr("This handler"), d.toggle_whole_file, variant="ghost", size="sm",
                  theme=t),
        ui.button(tr("Apply"), d.apply_code, icon="check", variant="tinted", size="sm", theme=t),
        ui.icon_button("x", d.close_code, size="sm", tooltip=tr("Close"), theme=t),
    ], theme=t)
    below: List[Tuple[Any, float]] = []
    if d.code_error:
        below.append((_core.container(ui.label(d.code_error, size="sm", color="error", mono=True, theme=t),
                                      padding=(4, 12), width="fill", height=26, bg=alpha(t.error, 0.1)), 26))
    if diags and a.problems_open:
        below.append(problems_list(a, diags, t))
    et = a.editor_theme(t)
    editor = ui.editor(
        d.editor_id, text, language="py", on_change=d.set_code_buffer, on_cursor=d.set_code_cursor,
        on_scroll=a.scrolled, font_size=s.font_size, gutter=s.line_numbers, wrap=s.wrap,
        active_line=s.highlight_line, show_whitespace=s.show_whitespace, tab_size=s.tab_size,
        annotations=a.annotations(et), capture_keys=a.captured_keys, auto_close=s.auto_close, folding=s.folding,
        minimap=s.minimap, cursor_shape=s.cursor_shape, cursor_blink=s.cursor_blink, on_zoom=a.zoom,
        on_action=a.action_ran, highlights=a.search.matches if a.search else None,
        match_brackets=s.match_brackets, selection_highlight=s.selection_highlight, theme=et)
    area = _editor_area(a, editor, below, s.font_size, text.count("\n") + 1, s.line_numbers)
    bars = []
    if a.search is not None:
        bars.append(search_bar(a, t))
    if a.goto is not None:
        bars.append(goto_bar(a, t))
    from .agent_panel import inline_bar

    inline = inline_bar(d, t)
    if inline is not None:
        bars.append(inline)
    return _core.column([header, *bars, area], width="fill", height="fill")


def search_bar(a: CodeAssist, t: Theme) -> Any:
    """The find and replace bar over the editor (Ctrl+F, Ctrl+H), like Zed's buffer search."""
    s = a.search
    assert s is not None

    def option(name: str, icon: str, tip: str) -> Any:
        return ui.icon_button(icon, lambda: a.toggle_option(name), size="sm", selected=getattr(s, name),
                              tooltip=tr(tip), theme=t)

    if s.error:
        count = ui.label(tr("Invalid pattern"), size="sm", color="error", theme=t)
    elif not s.query:
        count = ui.label("", size="sm", theme=t)
    elif s.matches:
        more = "+" if len(s.matches) >= MAX_MATCHES else ""
        count = ui.label(f"{s.index + 1}/{len(s.matches)}{more}", size="sm", color="text_muted", mono=True, theme=t)
    else:
        count = ui.label(tr("No results"), size="sm", color="text_muted", theme=t)
    find = _core.row([
        ui.icon_button("chevron-right" if not s.replacing else "chevron-down", lambda: a.toggle_option("replacing"),
                       size="sm", tooltip=tr("Toggle replace"), theme=t),
        ui.input(s.query, a.set_query, placeholder=tr("Find"), id=FIND_ID, on_submit=lambda: a.next_match(1),
                 size="sm", mono=True, theme=t),
        option("case", "case-sensitive", "Match case"),
        option("word", "whole-word", "Match whole words"),
        option("regex", "regex", "Use regular expressions"),
        _core.container(count, width=74, align_x="center"),
        ui.icon_button("arrow-up", lambda: a.next_match(-1), size="sm", tooltip=tr("Previous match") + "  ⇧F3",
                       theme=t),
        ui.icon_button("arrow-down", lambda: a.next_match(1), size="sm", tooltip=tr("Next match") + "  F3", theme=t),
        ui.icon_button("text-cursor", a.select_all_matches, size="sm", tooltip=tr("Select all matches") + "  Alt+Enter",
                       theme=t),
        ui.icon_button("x", a.close_search, size="sm", tooltip=tr("Close") + "  Esc", theme=t),
    ], spacing=4, align="center")
    rows = [find]
    if s.replacing:
        rows.append(_core.row([
            _core.space(width=26),
            ui.input(s.replacement, a.set_replacement, placeholder=tr("Replace"), id=REPLACE_ID,
                     on_submit=a.replace_current, size="sm", mono=True, theme=t),
            ui.button(tr("Replace"), a.replace_current, variant="ghost", size="sm", theme=t),
            ui.button(tr("Replace all"), a.replace_all, variant="ghost", size="sm", theme=t),
        ], spacing=4, align="center"))
    return _core.container(_core.column(rows, spacing=4), padding=(4, 8), width="fill", bg=t.tab_bar)


def goto_bar(a: CodeAssist, t: Theme) -> Any:
    """The "go to line" field (Ctrl+G): a line, or ``line:column``."""
    lines = a._text.count("\n") + 1
    line, column = a.cursor
    hint = tr("Current line {line} of {lines} (column {column})", line=line, lines=lines, column=column)
    return _core.container(_core.row([
        _icon("hash", size=14, color=t.icon_muted),
        ui.input(a.goto or "", a.set_goto, placeholder=tr("Line or line:column"), id=GOTO_ID,
                 on_submit=a.submit_goto, size="sm", mono=True, width=180, theme=t),
        ui.label(hint, size="sm", color="text_muted", theme=t),
        _core.space(width="fill"),
        ui.icon_button("x", a.close_goto, size="sm", tooltip=tr("Close") + "  Esc", theme=t),
    ], spacing=8, align="center"), padding=(4, 8), width="fill", bg=t.tab_bar)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

STATUS_COLORS = {"ready": "success", "starting": "warning", "error": "error", "missing": "error",
                 "stopped": "text_muted", "disabled": "text_muted"}


def server_status_items(a: CodeAssist, t: Theme, on_press: Any = None) -> List[Any]:
    """Status-bar items for the language servers (only while the code editor is open)."""
    items = []
    for name, status, detail in a.intel.statuses():
        if status == "disabled":
            continue
        tip = f"{name}: {status}" + (f" — {detail}" if detail else "")
        items.append(ui.status_item(f"● {name}", on_press, color=STATUS_COLORS.get(status, "text_muted"),
                                    tooltip=tip, theme=t))
    return items


def settings_dialog(d: "Designer", t: Theme) -> Any:
    """Builds the editor settings dialog: language servers, appearance, cursor, editing and code lens."""
    a = d.assist
    s = a.settings

    def switch(key: str) -> Any:
        return ui.switch(bool(getattr(s, key)), a.setter(key), theme=t)

    shapes = {tr(shape.capitalize()): shape for shape in _settings.CURSOR_SHAPES}
    theme_names = [tr("Same as the designer"), *themes.names()]
    appearance = ui.settings_group(tr("Appearance"), [
        ui.field(tr("Theme"), ui.select(theme_names, s.theme or theme_names[0],
                                    lambda name: a.set("theme", "" if name == theme_names[0] else name), width=200,
                                    theme=t), theme=t),
        ui.field(tr("Font size"), ui.number_field(s.font_size, a.setter("font_size"), min=8, max=32, step=1, width=110,
                                              theme=t),
                 description=tr("Ctrl+= and Ctrl+- (or Ctrl+wheel); Ctrl+0 resets"),
                 theme=t),
        ui.field(tr("Line numbers"), switch("line_numbers"), theme=t),
        ui.field(tr("Highlight current line"), switch("highlight_line"), theme=t),
        ui.field(tr("Show whitespace"), switch("show_whitespace"), description=tr("Spaces as · and tabs as →"),
                 theme=t),
        ui.field(tr("Wrap long lines"), switch("wrap"), theme=t),
        ui.field(tr("Minimap"), switch("minimap"), description=tr("Click or drag it to scroll"), theme=t),
    ], theme=t)
    cursor = ui.settings_group(tr("Cursor"), [
        ui.field(tr("Shape"), ui.segmented(list(shapes), tr(s.cursor_shape.capitalize()),
                                           lambda name: a.set("cursor_shape", shapes[name]), theme=t), theme=t),
        ui.field(tr("Blink"), switch("cursor_blink"), theme=t),
    ], theme=t)
    editing = ui.settings_group(tr("Editing"), [
        ui.field(tr("Tab size"), ui.number_field(float(s.tab_size), lambda v: a.set("tab_size", int(v)), min=1, max=8,
                                             step=1, width=110, theme=t),
                 description=tr("Tab inserts spaces; Enter keeps the indentation"), theme=t),
        ui.field(tr("Autocomplete while typing"), switch("autocomplete"), description=tr("Ctrl+Space opens it anytime"),
                 theme=t),
        ui.field(tr("Auto-close brackets and quotes"), switch("auto_close"),
                 description=tr("Also wraps the selection and steps over the closing one"), theme=t),
        ui.field(tr("Code folding"), switch("folding"), description=tr("Chevrons in the gutter; Ctrl+Shift+[ and ]"),
                 theme=t),
        ui.field(tr("Match brackets"), switch("match_brackets"),
                 description=tr("Outline the bracket that pairs with the one at the cursor; Ctrl+M jumps to it"),
                 theme=t),
        ui.field(tr("Highlight selection matches"), switch("selection_highlight"),
                 description=tr("Ctrl+D adds the next one as a cursor, Ctrl+Shift+L all of them"), theme=t),
        ui.field(tr("Format with ruff on Apply"), switch("format_on_apply"), theme=t),
    ], theme=t)
    lens = ui.settings_group(tr("Code lens and diagnostics"), [
        ui.field(tr("Code lens"), switch("code_lens"), description=tr("References, implementations and wired events"),
                 theme=t),
        ui.field(tr("Inline diagnostics"), switch("inline_diagnostics"),
                 description=tr("Problems at the end of the line"),
                 theme=t),
    ], theme=t)
    rows = []
    for name, status, detail in a.intel.statuses():
        color = STATUS_COLORS.get(status, "text_muted")
        what = {"ty": tr("Types, completion and references"), "ruff": tr("Linting")}[name]
        rows.append(_core.row([
            _core.container(width=10, height=10, radius=5, bg=t.color(color)),
            _core.column([ui.label(f"{name}  ·  {status}", theme=t),
                          ui.label(detail or what, size="sm", color="text_muted", theme=t)], spacing=2, width="fill"),
            switch(name),
        ], spacing=10, align="center"))
    env = a.intel.env
    if env is not None:
        rows.append(_core.column([
            ui.label(f"{tr('Project')}  {env.root}", size="sm", color="text_muted", mono=True, theme=t),
            ui.label(f"Python   {env.python}", size="sm", color="text_muted", mono=True, theme=t),
        ], spacing=2))
    servers = ui.settings_group(tr("Language servers"), rows, theme=t)
    body = _core.scrollable(_core.column([servers, appearance, cursor, editing, lens], spacing=14, padding=(0, 6, 0, 0)),
                            height=580, scrollbar_width=4)
    return ui.modal(body, title=tr("Editor settings"), on_close=d.close_dialog, width=560, footer=[
        ui.button(tr("Restart servers"), a.restart_servers, icon="refresh-cw", variant="ghost", theme=t),
        _core.space(width="fill"),
        ui.button(tr("Done"), d.close_dialog, variant="solid", theme=t),
    ], theme=t)
