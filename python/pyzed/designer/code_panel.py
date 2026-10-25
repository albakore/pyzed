"""The designer's code editor: event code with completion, diagnostics, code lens, search and settings.

``CodeAssist`` holds the editor's state (cursor, completion list, search, settings) and talks to the
language servers through ``CodeIntel``; ``code_panel`` and ``settings_dialog`` are its views.
The designer forwards the editor's callbacks and the keys pressed while it has focus.
"""

from __future__ import annotations

import ast
import bisect
import io
import keyword
import re
import tokenize
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .. import _core, ui
from ..icons import for_file
from ..icons import icon as _icon
from ..theme import Theme, alpha, themes
from . import intellisense as _intel
from . import keymap as _keymap
from . import settings as _settings
from . import telemetry as _telemetry
from . import code as _code
from .intellisense import CodeAction, CodeIntel, CompletionItem, Diagnostic, Location
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
#: Height of a row of the problems list under the editor.
PROBLEM_ROW = 22.0
#: Height of the list's padding and footer.
FOOTER = 34.0
LIST_WIDTH = 320.0
#: Width of the completion list's scrollbar.
SCROLLBAR = 4.0
DOC_WIDTH = 340.0
CAPTURED = ("up", "down", "enter", "tab", "escape", "pageup", "pagedown")
#: The sections of the editor settings, in the order of the index.
SETTINGS_SECTIONS = ("appearance", "cursor", "editing", "scrolling", "diagnostics", "servers")
FIND_ID = "designer-code-find"
REPLACE_ID = "designer-code-replace"
GOTO_ID = "designer-code-goto"
RENAME_ID = "designer-code-rename"
#: Headers sticky scroll pins at most.
STICKY_LINES = 5
HOVER_WIDTH = 520.0
HOVER_HEIGHT = 300.0
ACTIONS_WIDTH = 420.0
#: How many places Go back remembers.
HISTORY = 50
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


@dataclass
class HoverCard:
    """What the mouse rests on: the symbol's documentation and the problems there."""

    line: int
    column: int
    #: 1-based byte columns of the word (``end`` excluded).
    start: int
    end: int
    #: Where the word is drawn, relative to the editor.
    x: float
    y: float
    height: float
    text: str = ""
    diagnostics: List[Diagnostic] = field(default_factory=list)
    loading: bool = True


@dataclass
class RenameBox:
    """The rename field (F2) over the symbol being renamed."""

    line: int
    start: int
    end: int
    old: str
    text: str


@dataclass
class ActionMenu:
    """The quick fixes and refactorings offered at a line (Ctrl+.)."""

    line: int
    column: int
    items: List[CodeAction] = field(default_factory=list)
    index: int = 0
    #: Answers still awaited from the language servers.
    pending: int = 0

    @property
    def selected(self) -> Optional[CodeAction]:
        """The highlighted action, or ``None`` if there is none."""
        return self.items[self.index] if 0 <= self.index < len(self.items) else None


@dataclass
class References:
    """Every use of a symbol (Shift+F12), listed under the editor."""

    name: str
    items: List[Tuple[Location, str]] = field(default_factory=list)
    loading: bool = True


#: A place in the code to go back to: ``("form", handler or "*", line, column)`` or ``("file", path, line, column)``.
Place = Tuple[str, str, int, int]


class CodeAssist:
    """Completion, diagnostics, code lens and preferences for the designer's code editor."""

    def __init__(self, designer: "Designer", *, servers: bool = True) -> None:
        self.d = designer
        self.settings = _settings.load()
        if self.settings.keymap:  # the old per-action keys move to keymap.json
            _keymap.get().migrate(self.settings.keymap)
            self.settings = replace(self.settings, keymap={})
            _settings.save(self.settings)
        self.intel = CodeIntel(self.settings, dispatch=self._post, on_update=self._noop)
        self.servers = servers
        self.cursor: Tuple[int, int] = (1, 1)
        self.scroll: Tuple[float, float] = (0.0, 0.0)
        self.completion: Optional[Completion] = None
        self.problems_open = True
        self.search: Optional[Search] = None
        #: The "go to line" field's text while it is open.
        self.goto: Optional[str] = None
        #: The section shown in the editor settings.
        self.settings_section = "appearance"
        self._typed = False
        self._text = ""
        #: The hover card, the rename field, the quick fixes menu and the references list, while shown.
        self.hover: Optional[HoverCard] = None
        self.rename: Optional[RenameBox] = None
        self.actions: Optional[ActionMenu] = None
        self.references: Optional[References] = None
        #: Places left by jumps (Go to definition, a reference), for Go back and Go forward.
        self.back: List[Place] = []
        self.forward: List[Place] = []

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
    def plain(self) -> bool:
        """True while the editor shows a project file that is not Python: no language servers or completion,
        only editing."""
        buffer = self.d.buffers.current
        return buffer is not None and buffer.language != "py"

    @property
    def line_height(self) -> int:
        """The editor's line height in pixels, from the font size and the line height setting."""
        return round(self.settings.font_size * _settings.LINE_HEIGHTS.get(self.settings.line_height, 1.6))

    @property
    def readonly(self) -> bool:
        """Whether the file shown belongs to an installed package (opened by Go to definition): look, don't touch."""
        buffer = self.d.buffers.current
        return buffer is not None and _is_library(buffer.path)

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
        """The editor shows a new handler, the whole file or a project file."""
        self.completion = None
        self.hover = self.rename = self.actions = None
        self.cursor = (1, 1)
        self.scroll = (0.0, 0.0)
        buffer = self.d.buffers.current
        if buffer is not None:
            self._text = buffer.text
            if self.search is not None:
                self._find()
            if not self.plain and self.servers:
                self.intel.attach(buffer.path)
            self._sync()
            return
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
        if self.plain:
            return
        if self.d.buffers.current is not None:
            text = self.d.buffers.current.text
            self.intel.update(text, None, text)
            self.intel.use_form(None)
            self.intel.refresh_lenses()
            return
        if self.d.editing is None:
            return
        self.intel.update(self.d.doc.code, self.handler, self.d.editing[1])
        self.intel.refresh_lenses(self.d.doc.form)

    def _document(self, text: str) -> Tuple[str, Optional[str], str]:
        """What the language servers get for editor text ``text``: ``(module, handler, buffer)``."""
        if self.d.buffers.current is not None:
            return text, None, text
        return self.d.doc.code, self.handler, text

    def environment_changed(self) -> None:
        """The project's packages may have changed (uv add, sync): restarts the servers if they did."""
        if self.servers:
            self.intel.refresh_environment()

    # -- editor callbacks ---------------------------------------------------------
    def changed(self, text: str) -> None:
        """The text changed (called by the designer after storing it)."""
        self._typed = len(text) == len(self._text) + 1
        if len(text) < len(self._text) and self.completion is not None:
            self._typed = True  # deleting inside a word keeps the list open and refilters it
        self._text = text
        self.hover = None
        if not self.plain:
            self.intel.update(*self._document(text))
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
        if typed and not self.plain and self.settings.autocomplete and _intel.should_complete(current, column):
            self.open_completion()
        return None

    def scrolled(self, info: Dict[str, float]) -> Any:
        """The editor scrolled; stores its ``x``/``y`` offsets in pixels (used to place the completion
        list and the other popups). Without a popup open nothing else changes: the designer is not drawn
        again for every step of the wheel."""
        self.scroll = (float(info.get("x", 0.0)), float(info.get("y", 0.0)))
        if self.completion is None and self.hover is None and self.rename is None and self.actions is None:
            return _core.UNCHANGED
        return None

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

    def run_action(self, name: str) -> Any:
        """Runs the code panel's keymap action ``name`` (``code_panel::`` in the keymap)."""
        if name == "show_completions":
            return None if self.plain else self.open_completion()
        panel = {
            "find": lambda: self.open_search(),
            "replace": lambda: self.open_search(replacing=True),
            "go_to_line": self.open_goto,
            "toggle_soft_wrap": lambda: self.set("wrap", not self.settings.wrap),
            "go_to_definition": self.go_to_definition,
            "go_to_type_definition": lambda: self.go_to_definition("typeDefinition"),
            "find_all_references": self.find_references,
            "rename_symbol": self.start_rename,
            "code_actions": lambda: self.open_actions(),
            "organize_imports": lambda: self.source_action("source.organizeImports"),
            "fix_all": lambda: self.source_action("source.fixAll"),
            "go_back": lambda: self.go_back(1),
            "go_forward": lambda: self.go_back(-1),
            "toggle_sticky_scroll": lambda: self.set("sticky_scroll", not self.settings.sticky_scroll),
        }
        return panel[name]() if name in panel else None

    def on_key(self, combo: str) -> Any:
        """The keys of the find bar, go to line, the rename field, the quick fixes and the completion list while
        they are open (before the keymap's); returns ``(handled, result)``."""
        if self.rename is not None and combo == "escape":
            return True, self.cancel_rename()
        m = self.actions
        if m is not None and combo in ("up", "down", "enter", "tab", "escape", "pageup", "pagedown"):
            if combo == "escape":
                return True, self.close_actions()
            if combo in ("enter", "tab"):
                return True, self.apply_action(m.index)
            step = {"up": -1, "down": 1, "pageup": -8, "pagedown": 8}[combo]
            if m.items:
                m.index = (m.index + step) % len(m.items) if abs(step) == 1 else \
                    max(0, min(len(m.items) - 1, m.index + step))
            return True, None
        if self.hover is not None and combo == "escape":
            self.hover = None
            return True, None
        if self.references is not None and combo == "escape" and self.search is None and self.goto is None:
            self.references = None
            return True, None
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
        a completion list is shown, and the keymap's keys without Ctrl for the designer's actions (Alt+Z)."""
        keys = _keymap.get().captured(("Editor", "CodePanel", "Workspace"))
        lists = (self.completion is not None and self.completion.shown) or self.actions is not None
        return (CAPTURED if lists else ()) + keys

    # -- hover ------------------------------------------------------------------------
    def hovered(self, info: Optional[Dict[str, Any]]) -> None:
        """The mouse rests on a word (``info`` from the editor's ``on_hover``), or left it (``None``): shows or
        hides its hover card with the symbol's documentation and the problems there."""
        if info is None:
            self.hover = None
            return
        if self.plain or not self.settings.hover or self.rename is not None or self.actions is not None \
                or (self.completion is not None and self.completion.shown):
            return
        card = HoverCard(int(info["line"]), int(info["column"]), int(info["start"]), int(info["end"]),
                         float(info["x"]), float(info["y"]), float(info["height"]))
        card.diagnostics = [d for d in self.diagnostics() if _covers(d, card.line, card.start, card.end)]
        text = self._line(card.line)
        if self.d.buffers.current is None:
            card.text = _intel.designer_hover(self.d.doc.form, text, card.start, card.end)
        self.hover = card
        if card.text or not self.intel.hover(card.line, card.column, lambda doc: self._hover_text(card, doc)):
            card.loading = False
            if not card.text and not card.diagnostics:
                self.hover = None
        _telemetry.get().count("editor.hover")

    def _hover_text(self, card: HoverCard, text: str) -> None:
        if self.hover is not card:
            return
        card.text, card.loading = text, False
        if not text and not card.diagnostics:
            self.hover = None

    # -- navigation -------------------------------------------------------------------
    def _place(self) -> Optional[Place]:
        """Where the cursor is now, to come back to it."""
        line, column = self.cursor
        buffer = self.d.buffers.current
        if buffer is not None:
            return ("file", str(buffer.path), line, column)
        if self.d.editing is not None:
            return ("form", self.d.editing[0], line, column)
        return None

    def _remember(self) -> None:
        place = self._place()
        if place is not None and (not self.back or self.back[-1] != place):
            self.back = (self.back + [place])[-HISTORY:]
        self.forward = []

    def go_back(self, step: int = 1) -> Any:
        """Goes back to where the cursor was before the last jump (``step=-1``: forward again)."""
        source, target = (self.back, self.forward) if step > 0 else (self.forward, self.back)
        if not source:
            return None
        here = self._place()
        place = source.pop()
        if here is not None:
            target.append(here)
        _telemetry.get().count("editor.go_back" if step > 0 else "editor.go_forward")
        return self._go(place)

    def _go(self, place: Place) -> Any:
        kind, where, line, column = place
        if kind == "file":
            path = Path(where)
            current = self.d.buffers.current
            if current is None or current.path.resolve() != path.resolve():
                if not self.d.buffers.open(path):
                    return None
        else:
            current = self.d.editing[0] if self.d.editing is not None else None
            if (self.d.buffers.current is not None or current != where) and not self.d.edit_code(where):
                return None
        return self._move_to(line, column)

    def _move_to(self, line: int, column: int) -> Any:
        self.cursor = (line, column)
        self.completion = self.hover = None
        editor = self.d.editor_id
        return _core.Command.batch([_core.Command.set_editor_cursor(editor, line, column),
                                    _core.Command.focus(editor)])

    def go_to_definition(self, kind: str = "definition") -> Any:
        """Goes to where the symbol at the cursor is defined (F12, Ctrl+click), or its type's definition with
        ``kind="typeDefinition"``. Without ty, looks for a ``def`` or ``class`` of that name in the code."""
        if self.plain:
            return None
        line, column = self.cursor
        word = _word_at(self._line(line), _char_index(self._line(line), column))
        if not word:
            return None
        _telemetry.get().count(f"editor.go_to_{'type_' if kind != 'definition' else ''}definition")

        def found(locations: List[Location]) -> Any:
            if locations:
                return self.open_location(locations[0])
            return self._local_definition(word)

        if not self.intel.definition(line, column, found, kind=kind):
            return self._local_definition(word)
        return None

    def _local_definition(self, word: str) -> Any:
        """Goes to a ``def``/``class`` named ``word`` (or the control of ``form.<word>``) without ty."""
        for d in _intel.definitions(self.intel.text or self._text):
            if d.name == word:
                where = self.intel.editor_position(d.line - 1, d.column) if self.intel.text else (d.line, d.column + 1)
                if where is not None:
                    self._remember()
                    return self._move_to(*where)
                if self.d.buffers.current is None and self.d.editing is not None:
                    self._remember()
                    return self._open_form_code(d.line - 1, d.column)
        if self.d.buffers.current is None and self.d.doc.form.get(word) is not None:
            self.d.doc.select(word)  # form.<control>: select it on the canvas
            self.d.notify(tr("{name} is a control of the form", name=word), kind="info", seconds=2)
            return None
        self.d.notify(tr("No definition found for {name}", name=word), kind="info", seconds=2)
        return None

    def open_location(self, loc: Location, remember: bool = True) -> Any:
        """Shows ``loc`` in the editor: in the text shown, another handler of the form or another file (opened in a
        tab); returns the commands that move the cursor there."""
        if remember:
            self._remember()
        target = loc.path.resolve()
        here = self.intel.file
        if here is not None and target == here and not self.plain:
            where = self.intel.editor_position(loc.line, loc.character)
            if where is not None:
                return self._move_to(*where)
            if self.d.buffers.current is None and self.d.editing is not None:
                return self._open_form_code(loc.line, loc.character)
        code = self.d.doc.code_path
        if code is not None and target == code.resolve():
            return self._open_form_code(loc.line, loc.character)
        if not self.d.buffers.open(loc.path):
            self.d.notify(tr("Could not open {name}", name=loc.path.name), kind="error", seconds=3)
            return None
        text = self.d.buffers.current.text if self.d.buffers.current is not None else ""
        lines = text.split("\n")
        line = min(loc.line, max(len(lines) - 1, 0))
        return self._move_to(line + 1, _intel.byte_column(lines[line] if lines else "", loc.character))

    def _open_form_code(self, line: int, character: int) -> Any:
        """Opens the form's function holding file line ``line`` (0-based) in the editor, or the whole file when
        it is outside every function, with the cursor there."""
        if self.d.editing is not None and not self.d._flush_code():
            return None
        source = self.d.doc.code
        handler, first = "*", 1
        try:
            tree = ast.parse(source)
        except SyntaxError:
            tree = None
        for node in tree.body if tree is not None else []:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                span = _code.find_function(source, node.name)
                if span is not None and span[0] <= line + 1 <= span[1]:
                    handler, first = node.name, span[0]
                    break
        if not self.d.edit_code(handler):
            return None
        text = source.split("\n")
        column = _intel.byte_column(text[line] if line < len(text) else "", character)
        return self._move_to(line + 2 - first, column)

    # -- references -------------------------------------------------------------------
    def find_references(self) -> Any:
        """Lists every use of the symbol at the cursor under the editor (Shift+F12)."""
        if self.plain:
            return None
        line, column = self.cursor
        word = _word_at(self._line(line), _char_index(self._line(line), column))
        if not word:
            return None
        refs = References(word)
        self.references = refs
        _telemetry.get().count("editor.find_references")

        def found(locations: List[Location]) -> None:
            if self.references is not refs:
                return
            refs.items = [(loc, self._preview(loc)) for loc in locations]
            refs.loading = False

        if not self.intel.references(line, column, found):
            refs.loading = False
            source = self.intel.text or self._text
            for i, text in enumerate(source.split("\n")):
                for m in re.finditer(rf"\b{re.escape(word)}\b", text):
                    path = self.intel.file or self.code_file()
                    loc = Location(path, i, len(text[: m.start()].encode("utf-16-le")) // 2)
                    refs.items.append((loc, text.strip()))
        return None

    def _preview(self, loc: Location) -> str:
        """The text of the line at ``loc`` (from the editor, an open tab or the disk)."""
        target = loc.path.resolve()
        if self.intel.file is not None and target == self.intel.file:
            text = self.intel.text
        else:
            index = self.d.buffers.index_of(loc.path)
            if index is not None:
                text = self.d.buffers.items[index].text
            else:
                from .files import read_text

                text = read_text(loc.path) or ""
        lines = text.split("\n")
        return lines[loc.line].strip() if loc.line < len(lines) else ""

    def close_references(self) -> None:
        """Closes the references list."""
        self.references = None

    # -- rename -----------------------------------------------------------------------
    def start_rename(self) -> Any:
        """Opens the rename field (F2) on the symbol at the cursor; returns the command that focuses it."""
        if self.plain:
            return None
        line, column = self.cursor
        text = self._line(line)
        index = _char_index(text, column)
        word = _word_at(text, index)
        if not word or not word.isidentifier():
            return None
        start = index
        while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "_"):
            start -= 1
        first = len(text[:start].encode("utf-8")) + 1
        self.rename = RenameBox(line, first, first + len(word.encode("utf-8")), word, word)
        self.completion = self.hover = None
        return _core.Command.batch([_core.Command.focus(RENAME_ID), _core.Command.select_all(RENAME_ID)])

    def set_rename_text(self, text: str) -> None:
        """The rename field changed."""
        if self.rename is not None:
            self.rename.text = text

    def cancel_rename(self) -> Any:
        """Closes the rename field and gives the keyboard back to the editor."""
        self.rename = None
        return _core.Command.focus(self.d.editor_id)

    def submit_rename(self) -> Any:
        """Renames the symbol everywhere it is used (ty knows the uses across files; without it, the names in
        this code). A renamed handler stays wired to its events."""
        r = self.rename
        if r is None:
            return None
        new = r.text.strip()
        if not new.isidentifier() or keyword.iskeyword(new):
            self.d.notify(tr("{name} is not a valid name", name=new or "''"), kind="error", seconds=3)
            return None
        self.rename = None
        focus = _core.Command.focus(self.d.editor_id)
        if new == r.old:
            return focus
        _telemetry.get().count("editor.rename")

        def done(edit: Optional[Dict[str, Any]]) -> Any:
            if not edit or not _intel.edits_by_path(edit):
                return self._local_rename(r.old, new)
            return self.apply_workspace_edit(edit, renamed=(r.old, new))

        if not self.intel.rename(r.line, r.start, new, done):
            return _core.Command.batch([self._local_rename(r.old, new), focus])
        return focus

    def _local_rename(self, old: str, new: str) -> Any:
        """Renames ``old`` in the code shown (names only, not in strings or comments)."""
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(self._text).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            tokens = []
        lines = self._text.split("\n")
        ranges = []
        for tok in tokens:
            if tok.type == tokenize.NAME and tok.string == old:
                (row, col), (end_row, end_col) = tok.start, tok.end
                head, tail = lines[row - 1][:col], lines[end_row - 1][:end_col]
                ranges.append(((row, len(head.encode("utf-8")) + 1, end_row, len(tail.encode("utf-8")) + 1), new))
        if not ranges:
            self.d.notify(tr("Nothing to rename"), kind="info", seconds=2)
            return None
        self._rename_wiring(old, new)
        return _core.Command.replace_editor_ranges(self.d.editor_id, ranges)

    def _rename_wiring(self, old: str, new: str) -> None:
        """Keeps the events of a renamed handler pointing at it."""
        if self.d.buffers.current is None or (self.d.doc.code_path is not None and self.intel.file is not None
                                              and self.d.doc.code_path.resolve() == self.intel.file):
            self.d.doc.rename_handler(old, new)

    # -- edits from the language servers --------------------------------------------------
    def apply_workspace_edit(self, edit: Dict[str, Any], renamed: Optional[Tuple[str, str]] = None) -> Any:
        """Applies an LSP ``WorkspaceEdit`` (a rename or a fix): to the code shown, the form's code, open tabs,
        and other files, which open as unsaved tabs to review; returns the editor's commands."""
        changes = _intel.edits_by_path(edit)
        here = self.intel.file
        commands = []
        others = []
        for path, edits in changes.items():
            if here is not None and path.resolve() == here and not self.plain:
                command = self._edit_shown(edits, renamed)
                if command is not None:
                    commands.append(command)
            elif self._edit_elsewhere(path, edits):
                others.append(path.name)
        if renamed is not None:
            self._rename_wiring(*renamed)
        if others:
            self.d.notify(tr("Changed {count} more files", count=len(others)), ", ".join(others[:4]), kind="info",
                          seconds=4)
        return _core.Command.batch(commands) if commands else None

    def _edit_shown(self, edits: List[Dict[str, Any]], renamed: Optional[Tuple[str, str]]) -> Any:
        """Applies edits (file coordinates) to the document the editor shows."""
        handler = self.handler if self.d.buffers.current is None else None
        if handler is None:
            # The editor shows the whole file: replace the ranges, so Undo takes them back.
            ranges = []
            for e in edits:
                start, end = e["range"]["start"], e["range"]["end"]
                a = self._editor_point(start["line"], start["character"])
                b = self._editor_point(end["line"], end["character"])
                ranges.append(((*a, *b), e.get("newText", "")))
            if not ranges:
                return None
            line, column = _shifted(self.cursor, ranges)
            return _core.Command.batch([_core.Command.replace_editor_ranges(self.d.editor_id, ranges),
                                        _core.Command.set_editor_cursor(self.d.editor_id, line, column)])
        # One handler is shown: edit the whole module and show the handler again.
        full = _intel.apply_edits(self.intel.text, edits)
        try:
            ast.parse(full)
        except SyntaxError:
            self.d.notify(tr("Fix the errors in the code first"), kind="error", seconds=3)
            return None
        name = handler
        if renamed is not None and renamed[0] == handler and _code.find_function(full, renamed[1]) \
                and not _code.find_function(full, handler):
            name = renamed[1]
        self.d.doc.set_code(full)
        text = self.d.doc.handler_source(name)
        self.d.editing = (name, text)
        self.d.last_handler = name
        self.d._code_base = None
        self.d.code_revision += 1  # a new editor buffer with the new text
        line, column = self.cursor
        self.opened()
        self.cursor = (line, column)
        return _core.Command.set_editor_cursor(self.d.editor_id, line, column)

    def _editor_point(self, line: int, character: int) -> Tuple[int, int]:
        """The editor position of an LSP position, clamped to the text (the end of the file included)."""
        where = self.intel.editor_position(line, character)
        if where is not None:
            return where
        lines = self._text.split("\n")
        if line - self.intel.offset >= len(lines):
            return len(lines), len(lines[-1].encode("utf-8")) + 1
        return 1, 1

    def _edit_elsewhere(self, path: Path, edits: List[Dict[str, Any]]) -> bool:
        """Applies edits to a file not shown: its open tab, the form's code, or the file opened in a new unsaved
        tab; returns whether it changed."""
        from .files import Buffer, read_text

        buffers = self.d.buffers
        index = buffers.index_of(path)
        if index is not None:
            buffer = buffers.items[index]
            buffer.text = _intel.apply_edits(buffer.text, edits)
            buffer.revision += 1
            return True
        code = self.d.doc.code_path
        if code is not None and path.resolve() == code.resolve():
            self.d.doc.set_code(_intel.apply_edits(self.d.doc.code, edits))
            return True
        text = read_text(path)
        if text is None:
            return False
        buffers.items.append(Buffer(path, _intel.apply_edits(text, edits), text))
        return True

    # -- quick fixes and refactorings ----------------------------------------------------
    def open_actions(self, line: Optional[int] = None) -> Any:
        """Shows the quick fixes and refactorings for a line (the cursor's by default; Ctrl+.): ruff's and ty's
        fixes, imports for undefined names and installing a missing package."""
        if self.plain:
            return None
        line = line or self.cursor[0]
        column = self.cursor[1] if line == self.cursor[0] else 1
        menu = ActionMenu(line, column)
        self.actions = menu
        self.completion = self.hover = None
        diags = [d for d in self.intel.diagnostics() if d.line <= line <= d.end_line]
        project = self.d.projects.project
        installed = {d.name for d in self.d.projects.deps}
        for diag in diags:
            package = _intel.missing_package(diag)
            if package and project is not None and _project_name(package) not in installed:
                menu.items.append(CodeAction(tr("Install {package} in the project (uv add)", package=package),
                                             preferred=True, run=lambda package=package: self.install(package)))
        for diag in diags:
            undefined = re.search(r"[Nn]ame `(\w+)` used when not defined", diag.message)
            if undefined:
                menu.pending += 1
                name = undefined.group(1)
                asked = self.intel.complete(diag.end_line, diag.end_column,
                                            lambda items, name=name: self._imports_received(menu, name, items))
                if not asked:
                    menu.pending -= 1
                break  # one completion request at a time
        if self.intel.code_actions(line, line, lambda items: self._actions_received(menu, items)):
            menu.pending += 1
        _telemetry.get().count("editor.code_actions")
        if not menu.pending and not menu.items:
            self.actions = None
            self.d.notify(tr("No quick fixes here"), kind="info", seconds=2)
        return None

    def _imports_received(self, menu: ActionMenu, name: str, items: List[CompletionItem]) -> None:
        menu.pending -= 1
        if self.actions is not menu or self.intel.uri is None:
            return
        fixes = []
        for item in items:
            if item.label == name and item.additional_edits:
                found = re.search(r"from ([\w.]+) import|import ([\w.]+)", item.detail or "")
                where = (found.group(1) or found.group(2)) if found else (item.detail or "").strip(" ()")
                title = tr("Import {name} from {module}", name=name, module=where) if where else \
                    tr("Import {name}", name=name)
                fixes.append(CodeAction(title, edit={"changes": {self.intel.uri: item.additional_edits}},
                                        preferred=not fixes))
        menu.items[:0] = fixes[:5]
        self._settle(menu)

    def _actions_received(self, menu: ActionMenu, items: List[CodeAction]) -> None:
        menu.pending -= 1
        if self.actions is not menu:
            return
        menu.items.extend(items)
        self._settle(menu)

    def _settle(self, menu: ActionMenu) -> None:
        if not menu.pending and not menu.items:
            self.actions = None
            self.d.notify(tr("No quick fixes here"), kind="info", seconds=2)

    def apply_action(self, index: int) -> Any:
        """Runs quick fix ``index`` of the open menu and closes it."""
        menu, self.actions = self.actions, None
        if menu is None or not 0 <= index < len(menu.items):
            return _core.Command.focus(self.d.editor_id)
        action = menu.items[index]
        _telemetry.get().count("editor.apply_code_action")
        focus = _core.Command.focus(self.d.editor_id)
        if action.run is not None:
            return _core.Command.batch([c for c in (action.run(), focus) if c is not None])
        result = self.apply_workspace_edit(action.edit or {})
        return _core.Command.batch([c for c in (result, focus) if c is not None])

    def close_actions(self) -> Any:
        """Closes the quick fixes menu."""
        self.actions = None
        return _core.Command.focus(self.d.editor_id)

    def source_action(self, kind: str) -> Any:
        """Runs ruff's ``source.organizeImports`` or ``source.fixAll`` on the code."""
        if self.plain:
            return None
        lines = (self.intel.text or self._text).count("\n") + 1 - self.intel.offset

        def received(items: List[CodeAction]) -> Any:
            for item in items:
                if item.kind.startswith(kind) and item.edit:
                    return self.apply_workspace_edit(item.edit)
            self.d.notify(tr("Nothing to change"), kind="info", seconds=2)
            return None

        if not self.intel.code_actions(1, max(min(lines, self.intel.length or lines), 1), received):
            self.d.notify(tr("ruff is not running"), kind="warning", seconds=3)
        _telemetry.get().count(f"editor.{kind.split('.')[-1]}")
        return None

    def install(self, package: str) -> Any:
        """Adds ``package`` to the project with ``uv add``; the servers restart once it is installed, so its
        imports resolve."""
        return self.d.projects.add_package(package)

    # -- diagnostics and lenses -----------------------------------------------------
    def diagnostics(self) -> List[Diagnostic]:
        """Returns the language servers' errors, warnings and information (hints left out) for the code."""
        if self.plain:
            return []
        return [d for d in self.intel.diagnostics() if d.severity <= 3]

    def annotations(self, t: Theme) -> Dict[int, Any]:
        """Returns the end-of-line annotations by line: code lens texts and, if enabled, the most severe
        diagnostic of each line as ``(text, color)`` in theme ``t``."""
        out: Dict[int, Any] = {}
        if self.plain:
            return out
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
        if key == "font_family":
            self.d.apply_fonts()
        if key == "code_lens" and value:
            self.intel.refresh_lenses(self.d.doc.form)

    def editor_keymap(self) -> Dict[str, Optional[str]]:
        """The ``ui.editor(keymap=...)`` for the user's ``Editor`` bindings in ``keymap.json``."""
        return _keymap.get().editor_keymap()

    def show_settings_section(self, section: str) -> None:
        """Shows ``section`` of the editor settings (a page of the Settings dialog)."""
        self.settings_section = section
        self.d.settings_ui.show(f"editor.{section}")

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

    def action_ran(self, name: str) -> Any:
        """An editor action ran (``on_action``): counted by the telemetry when it is on. Ctrl+click reports
        ``go_to_definition``, which goes there."""
        _telemetry.get().count(f"editor.{name}")
        if name == "go_to_definition":
            return self.go_to_definition()
        return None

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


def _shifted(cursor: Tuple[int, int], ranges: List[Tuple[Tuple[int, int, int, int], str]]) -> Tuple[int, int]:
    """Where the cursor ends up after one-line replacements on its line (a rename): text replaced before it moves
    it, and inside a replaced word it stays at the same distance from the word's start."""
    line, column = cursor
    shift = 0
    for (l1, c1, l2, c2), text in sorted(ranges, key=lambda r: r[0]):
        if l1 != line or l2 != line or "\n" in text or c1 > column:
            continue
        size = len(text.encode("utf-8"))
        if c2 <= column:
            shift += size - (c2 - c1)
        else:
            return line, c1 + shift + min(column - c1, size)
    return line, column + shift


def _is_library(path: Path) -> bool:
    """Whether ``path`` is inside an installed package (a ``site-packages`` folder or a Python install)."""
    parts = {p.lower() for p in path.parts}
    return bool(parts & {"site-packages", "dist-packages", "typeshed"})


def _covers(diag: Diagnostic, line: int, start: int, end: int) -> bool:
    """Whether diagnostic ``diag`` touches the word at ``line`` between byte columns ``start`` and ``end``."""
    if not diag.line <= line <= diag.end_line:
        return False
    if diag.line == line and diag.column > end:
        return False
    return not (diag.end_line == line and diag.end_column < start)


def _project_name(package: str) -> str:
    """A package name as the project lists it (lower case, ``-`` for ``_`` and ``.``)."""
    return re.sub(r"[-_.]+", "-", package).lower()


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
    """The editor, with its popups pinned over it (the completion list under or above the word being completed,
    the hover card, the rename field and the quick fixes), and ``below`` it.

    The widget tree is the same with or without the popups, so the editor keeps its focus.
    """
    t = a.d.theme_obj
    lh = a.line_height
    left = (MARKER_WIDTH + max(len(str(line_count)), 2) * size * 0.62 + 28) if gutter else 0.0
    char = size * CHAR_WIDTH
    below_height = sum(h for _, h in below)
    nothing = _core.space(width=0, height=0)

    def anchor(line: int, column: int) -> Tuple[float, float]:
        """Where 1-based ``column`` of ``line`` is drawn: its left and the bottom of its line."""
        sx, sy = a.scroll
        return left + PAD_LEFT + (column - 1) * char - sx, PAD_Y + line * lh - sy

    def place(width: float, height: float) -> Any:
        visible = height - below_height
        pins = []
        c = a.completion
        popup: Any = nothing
        x = y = 0.0
        if c is not None and (c.shown or c.loading):
            x, y = anchor(c.line, c.start)
            x, y = x - 30, y + 2
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
        pins.append(_core.pin(popup, x=x, y=y))
        h = a.hover
        card: Any = nothing
        x = y = 0.0
        if h is not None and (h.text or h.diagnostics):
            room_width = max(min(HOVER_WIDTH, width - 8), 200.0)
            estimate = min(HOVER_HEIGHT, 24 + 30 * len(h.diagnostics) + 19 * _text_rows(h.text, room_width))
            below_room = visible - (h.y + h.height) - 6
            up = below_room < estimate and h.y - 6 > below_room
            room = h.y - 6 if up else below_room
            tall = max(min(room, HOVER_HEIGHT), 80)
            card = hover_card(a, h, t, room_width, tall)
            x = max(4.0, min(h.x - 6, width - room_width - 4))
            y = h.y + h.height + 2
            if up:  # its bottom right above the word, however tall it turns out
                card = _core.container(card, height=tall, align_y="bottom")
                y = h.y - tall - 2
        pins.append(_core.pin(card, x=x, y=y))
        r = a.rename
        box: Any = nothing
        x = y = 0.0
        if r is not None:
            x, y = anchor(r.line, r.start)
            box = rename_box(a, r, t)
            x = max(4.0, min(x - 8, width - 300))
            y = y + 2 if y + 70 < visible else y - lh - 70
        pins.append(_core.pin(box, x=x, y=y))
        m = a.actions
        menu: Any = nothing
        x = y = 0.0
        if m is not None:
            x, y = anchor(m.line, m.column)
            rows = max(len(m.items) + (1 if m.pending else 0), 1)
            tall = min(rows, 10) * ROW_HEIGHT + 10
            space_below, space_above = visible - y - 6, y - lh - 6
            up = space_below < tall and space_above > space_below
            tall = max(min(tall, space_above if up else space_below), ROW_HEIGHT + 10)
            menu = actions_menu(a, m, t, tall)
            x = max(4.0, min(x - 8, width - ACTIONS_WIDTH - 4))
            y = max(y - lh - tall - 4, 0.0) if up else y + 2
        pins.append(_core.pin(menu, x=x, y=y))
        area = _core.stack([editor, *pins], width="fill", height="fill")
        return _core.column([area, *(w for w, _ in below)], width="fill", height="fill")

    return _core.responsive(place)


def _text_rows(text: str, width: float) -> int:
    """About how many rows ``text`` (Markdown) takes in the hover card, ``width`` pixels wide."""
    per_row = max(int((width - 24) / 7.2), 20)
    return sum(max(1, -(-len(line) // per_row)) for line in text.split("\n")) if text else 0


def hover_card(a: CodeAssist, h: HoverCard, t: Theme, width: float, max_height: float) -> Any:
    """The hover card: the problems at the word (with their quick fix) over the symbol's documentation."""
    icons = {1: ("circle-x", t.error), 2: ("triangle-alert", t.warning), 3: ("info", t.info), 4: ("info", t.info)}
    parts: List[Any] = []
    for diag in h.diagnostics:
        icon, color = icons.get(diag.severity, icons[3])
        source = " ".join(x for x in (diag.source, f"({diag.code})" if diag.code else "") if x)
        parts.append(_core.row([_icon(icon, size=13, color=color),
                                _core.text(diag.message, size=12, color=t.text, width="fill"),
                                _core.text(source, size=11, color=t.text_muted, wrap=False)], spacing=8))
    if h.diagnostics:
        package = next((p for p in (_intel.missing_package(d) for d in h.diagnostics) if p), None)
        actions = [ui.button(tr("Quick fix…"), lambda: a.open_actions(h.line), icon="lightbulb", variant="ghost",
                             size="sm", theme=t)]
        if package and a.d.projects.project is not None:
            actions.insert(0, ui.button(tr("Install {package}", package=package), lambda: a.install(package),
                                        icon="package-plus", variant="tinted", size="sm", theme=t))
        parts.append(_core.row(actions, spacing=6))
    if h.text:
        if parts:
            parts.append(ui.divider(theme=t))
        parts.append(ui.markdown(h.text, size=12, selectable=True, theme=t))
    elif h.loading:
        parts.append(ui.label(tr("Loading…"), size="sm", color="text_muted", theme=t))
    body = _core.scrollable(_core.column(parts, spacing=8, width="fill", padding=(0, 6, 0, 0)), scrollbar_width=4,
                            height="shrink")
    card = _core.container(body, width=width, max_height=max_height, padding=10, clip=True, bg=t.elevated,
                           border_color=t.border, border_width=1, radius=6)
    return _core.mouse_area(card, cursor="default")


def rename_box(a: CodeAssist, r: RenameBox, t: Theme) -> Any:
    """The rename field over the symbol (F2): Enter renames it everywhere, Escape cancels."""
    return _core.container(_core.column([
        ui.input(r.text, a.set_rename_text, id=RENAME_ID, on_submit=a.submit_rename, size="sm", mono=True,
                 width=280, theme=t),
        ui.label(tr("Enter to rename, Esc to cancel"), size="xs", color="text_muted", theme=t),
    ], spacing=4), padding=6, bg=t.elevated, border_color=t.border_focused, border_width=1, radius=6)


def actions_menu(a: CodeAssist, m: ActionMenu, t: Theme, max_height: float = 10 * ROW_HEIGHT + 10) -> Any:
    """The quick fixes and refactorings at a line (Ctrl+.), at most ``max_height`` pixels tall (scrolling with the
    highlighted one in view)."""
    rows: List[Any] = []
    best = next((i for i, item in enumerate(m.items) if item.preferred), None)
    for i, item in enumerate(m.items[:30]):
        icon = "package-plus" if item.run is not None else "lightbulb" if item.kind.startswith("quickfix") else \
            "wand-sparkles"
        color = t.warning if item.kind.startswith("quickfix") else t.accent
        rows.append(_core.button(_core.row([
            _icon(icon, size=13, color=color),
            _core.text(item.title, size=13, color=t.text, wrap=False, width="fill"),
            ui.badge(tr("preferred"), theme=t) if i == best else None,
        ], spacing=8, align="center"), lambda i=i: a.apply_action(i), padding=(0, 8), height=ROW_HEIGHT, width="fill",
            bg=t.element_selected if i == m.index else "transparent", hover_bg=t.element_hover, radius=4))
    if m.pending:
        rows.append(_core.container(ui.label(tr("Loading…"), size="sm", color="text_muted", theme=t), padding=(4, 8)))
    fits = max(int((max_height - 10) // ROW_HEIGHT), 1)
    top = min(max(m.index - fits + 1, 0), max(len(rows) - fits, 0))
    listing = _core.column(rows[top: top + fits], spacing=0, width="fill")
    return _core.container(listing, width=ACTIONS_WIDTH, max_height=max_height, padding=4, clip=True,
                           bg=t.elevated, border_color=t.border, border_width=1, radius=6)


def references_list(a: CodeAssist, refs: References, t: Theme) -> Tuple[Any, float]:
    """The uses of a symbol under the editor (Shift+F12), each one a link to it; returns ``(widget, height)``."""
    root = a.d.projects.files.root
    rows = []
    for loc, preview in refs.items:
        try:
            name = loc.path.relative_to(root).as_posix() if root is not None else loc.path.name
        except ValueError:
            name = loc.path.name
        rows.append(_core.button(
            _core.row([_core.text(f"{name}:{loc.line + 1}", size=12, font="mono", color=t.text_muted, wrap=False),
                       _core.text(preview, size=12, font="mono", color=t.text, wrap=False, width="fill")],
                      spacing=10, align="center"),
            lambda loc=loc: a.open_location(loc), padding=(2, 12), width="fill", bg="transparent",
            hover_bg=t.element_hover))
    if refs.loading:
        title = tr("Looking for the uses of {name}…", name=refs.name)
    else:
        title = tr("{count} uses of {name}", count=len(refs.items), name=refs.name)
    header = _core.container(_core.row([
        _icon("list-tree", size=13, color=t.icon_muted),
        ui.label(title, size="sm", theme=t),
        _core.space(width="fill"),
        ui.icon_button("x", a.close_references, size="sm", tooltip=tr("Close"), keys="escape", theme=t),
    ], spacing=8, align="center"), padding=(2, 8), width="fill")
    height = min(len(rows), 6) * 22 + 34
    body = _core.scrollable(_core.column(rows, width="fill"), scrollbar_width=4)
    return _core.container(_core.column([header, body], spacing=0), height=height, width="fill", bg=t.panel), height


def problems_list(a: CodeAssist, diags: List[Diagnostic], t: Theme) -> Tuple[Any, float]:
    """Builds the clickable list of diagnostics under the editor; returns ``(widget, height)`` in pixels. Only the
    rows in view are built, so a file with hundreds of problems still types fast."""
    icons = {1: ("circle-x", t.error), 2: ("triangle-alert", t.warning), 3: ("info", t.info)}

    def row(i: int) -> Any:
        diag = diags[i]
        icon, color = icons.get(diag.severity, icons[3])
        source = " ".join(x for x in (diag.source, f"({diag.code})" if diag.code else "") if x)
        return _core.button(
            _core.row([_icon(icon, size=13, color=color),
                       _core.text(f"{diag.line}:{diag.column}", size=12, font="mono", color=t.text_muted, width=52),
                       _core.text(diag.message, size=12, color=t.text, wrap=False, width="fill"),
                       _core.text(source, size=11, color=t.text_muted, wrap=False)], spacing=8, align="center"),
            lambda: a.go_to(diag), padding=(2, 12), width="fill", height=PROBLEM_ROW, bg="transparent",
            hover_bg=t.element_hover)

    height = min(len(diags), 4) * PROBLEM_ROW + 6
    rows = _core.virtual_column(len(diags), row, item_height=PROBLEM_ROW, overscan=4)
    return _core.container(_core.scrollable(rows, width="fill", scrollbar_width=4),
                           height=height, width="fill", padding=(3, 0), bg=t.panel), height


def code_panel(d: "Designer", t: Theme) -> Any:
    """Builds the Code panel: a tab per open project file (and the form's code) over the file or the form
    code being edited."""
    b = d.buffers
    if b.current is None and d.editing is None and b.items:
        b.select(len(b.items) - 1)
    body = file_view(d, t) if b.current is not None else form_code(d, t)
    tabs = code_tabs(d, t)
    return _core.column([tabs, body], width="fill", height="fill") if tabs is not None else body


def code_tabs(d: "Designer", t: Theme) -> Optional[Any]:
    """The Code panel's tabs while project files are open: the form's code first, then each file."""
    b = d.buffers
    if not b.items:
        return None
    tabs: List[ui.Tab] = []
    if d.editing is not None:
        name = d.doc.code_path.name if d.doc.code_path else f"{d.doc.form.name}.py"
        tabs.append(ui.Tab("form", name, icon="layout-template", icon_color="accent"))
    for i, buffer in enumerate(b.items):
        icon, color = for_file(buffer.name)
        tabs.append(ui.Tab(f"file:{i}", buffer.name, icon=icon, icon_color=color, dirty=buffer.dirty))
    active = "form" if b.current is None else f"file:{b.active}"

    def select(tab: str) -> None:
        if tab == "form":
            d.show_form_code()
        else:
            b.select(int(tab.split(":")[1]))

    def close(tab: str) -> None:
        if tab == "form":
            b.select(None)
            d.close_code()
        else:
            b.close(int(tab.split(":")[1]))

    return ui.tab_bar(tabs, active, on_select=select, on_close=close, height=30, theme=t)


def _editor(d: "Designer", text: str, language: str, annotations: Dict[int, Any], et: Theme) -> Any:
    a = d.assist
    s = a.settings
    return ui.editor(
        d.editor_id, text, language=language, on_change=d.set_code_buffer, on_cursor=d.set_code_cursor,
        on_scroll=a.scrolled, font_size=s.font_size, gutter=s.line_numbers, wrap=s.wrap,
        active_line=s.highlight_line, show_whitespace=s.show_whitespace, tab_size=s.tab_size, hard_tabs=s.hard_tabs,
        backspace_unindent=s.backspace_unindent, **s.key_repeat,
        annotations=annotations, capture_keys=a.captured_keys, auto_close=s.auto_close, folding=s.folding,
        minimap=s.minimap, cursor_shape=s.cursor_shape, cursor_blink=s.cursor_blink, on_zoom=a.zoom,
        on_action=a.action_ran, highlights=a.search.matches if a.search else None,
        match_brackets=s.match_brackets, selection_highlight=s.selection_highlight, cursor_width=s.cursor_width,
        line_height=a.line_height, scrollbar=s.scrollbar, keymap=a.editor_keymap(),
        on_hover=a.hovered if s.hover and not a.plain else None,
        sticky_scroll=STICKY_LINES if s.sticky_scroll else 0, readonly=a.readonly,
        indent_guides=(s.indent_guides_coloring if s.indent_guides else False), theme=et)


def _bars(d: "Designer", t: Theme) -> List[Any]:
    a = d.assist
    bars = []
    if a.search is not None:
        bars.append(search_bar(a, t))
    if a.goto is not None:
        bars.append(goto_bar(a, t))
    return bars


def file_view(d: "Designer", t: Theme) -> Any:
    """A project file in the editor: its path, Save and Close over the text."""
    buffer = d.buffers.current
    assert buffer is not None
    a = d.assist
    root = d.projects.files.root
    try:
        title = buffer.path.relative_to(root).as_posix() if root is not None else str(buffer.path)
    except ValueError:
        title = str(buffer.path)
    icon, _ = for_file(buffer.name)
    header = ui.panel_header(title, icon=icon, actions=[
        _problems_button(a, t) if not a.plain else None,
        ui.icon_button("settings", d.open_editor_settings, size="sm", tooltip=tr("Editor settings"), theme=t),
        ui.button(tr("Save"), d.buffers.save, icon="save", variant="tinted", size="sm", disabled=not buffer.dirty,
                  theme=t),
        ui.icon_button("x", d.close_code, size="sm", tooltip=tr("Close"), theme=t),
    ], theme=t)
    et = a.editor_theme(t)
    editor = _editor(d, buffer.text, buffer.language, a.annotations(et), et)
    area = _editor_area(a, editor, _below(a, t), a.settings.font_size, buffer.text.count("\n") + 1,
                        a.settings.line_numbers)
    return _core.column([header, *_bars(d, t), area], width="fill", height="fill")


def _problems_button(a: CodeAssist, t: Theme) -> Any:
    """The header's errors · warnings count, which shows or hides the problems list."""
    diags = a.diagnostics()
    errors = sum(1 for x in diags if x.severity == 1)
    warnings = sum(1 for x in diags if x.severity == 2)
    problems = ui.button(f"{errors}  ·  {warnings}", a.toggle_problems, icon="circle-x" if errors else "circle-check",
                         variant="ghost", size="sm", selected=a.problems_open and bool(diags), theme=t)
    return ui.tooltip(problems, tr("Problems"), theme=t)


def _below(a: CodeAssist, t: Theme) -> List[Tuple[Any, float]]:
    """What goes under the editor: the references list (Shift+F12) or the problems list."""
    if a.references is not None:
        return [references_list(a, a.references, t)]
    diags = a.diagnostics()
    return [problems_list(a, diags, t)] if diags and a.problems_open else []


def form_code(d: "Designer", t: Theme) -> Any:
    """The form's code: header with the problems toggle and actions, the editor with its completion list,
    and the error line and problems list below it."""
    assert d.editing is not None
    a = d.assist
    s = a.settings
    handler, text = d.editing
    whole = handler == "*"
    path = d.doc.code_path.name if d.doc.code_path else f"{d.doc.form.name}.py"
    title = path if whole else f"{path} › {handler}()"
    header = ui.panel_header(title, icon="code", actions=[
        _problems_button(a, t),
        ui.icon_button("sparkles", d.agent.open_inline, size="sm", tooltip=tr("Inline assist"),
                       keys=_keymap.shown_keys("inline_assist"), theme=t),
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
    below += _below(a, t)
    et = a.editor_theme(t)
    editor = _editor(d, text, "py", a.annotations(et), et)
    area = _editor_area(a, editor, below, s.font_size, text.count("\n") + 1, s.line_numbers)
    bars = _bars(d, t)
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
        ui.icon_button("arrow-up", lambda: a.next_match(-1), size="sm", tooltip=tr("Previous match"), keys="shift-f3",
                       theme=t),
        ui.icon_button("arrow-down", lambda: a.next_match(1), size="sm", tooltip=tr("Next match"), keys="f3", theme=t),
        ui.icon_button("text-cursor", a.select_all_matches, size="sm", tooltip=tr("Select all matches"),
                       keys="alt-enter", theme=t),
        ui.icon_button("x", a.close_search, size="sm", tooltip=tr("Close"), keys="escape", theme=t),
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
        ui.icon_button("x", a.close_goto, size="sm", tooltip=tr("Close"), keys="escape", theme=t),
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
        items.append(ui.status_item(name, on_press, led=STATUS_COLORS.get(status, "text_muted"), tooltip=tip,
                                    theme=t))
    return items


def settings_dialog(d: "Designer", t: Theme) -> Any:
    """The Settings dialog on the code editor's page (see ``settings_ui``)."""
    from . import settings_ui

    if not d.settings_ui.page.startswith("editor."):
        d.settings_ui.show(f"editor.{d.assist.settings_section}")
    return settings_ui.dialog(d, t)
