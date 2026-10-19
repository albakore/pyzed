"""The designer's code editor: event code with completion, diagnostics, code lens and settings.

``CodeAssist`` holds the editor's state (cursor, completion list, settings) and talks to the
language servers through ``CodeIntel``; ``code_panel`` and ``settings_dialog`` are its views.
The designer forwards the editor's callbacks and the keys pressed while it has focus.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha, themes
from . import intellisense as _intel
from . import settings as _settings
from .intellisense import CodeIntel, CompletionItem, Diagnostic

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
DOC_WIDTH = 340.0
CAPTURED = ("up", "down", "enter", "tab", "escape", "pageup", "pagedown")


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
        unsaved).
        """
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

    def moved(self, line: int, column: int) -> Any:
        """The editor's cursor moved to ``line``, ``column`` (1-based).

        Refilters or closes the open completion list, and opens one after a typed character when
        autocomplete is on and the context calls for it. Returns ``None``.
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
        """The editor scrolled; stores its ``x``/``y`` offsets in pixels (used to place the completion list).
        """
        self.scroll = (float(info.get("x", 0.0)), float(info.get("y", 0.0)))

    def _line(self, line: int) -> str:
        lines = self._text.split("\n")
        return lines[line - 1] if 0 < line <= len(lines) else ""

    # -- completion ---------------------------------------------------------------
    def open_completion(self) -> None:
        """Opens the completion list for the word before the cursor.

        Designer completions (controls of the form) are shown right away; otherwise the list waits,
        marked ``loading``, for the language server. Closes it if there is nothing to show.
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

    def move_selection(self, delta: int) -> None:
        """Moves the highlighted completion by ``delta`` rows: wrapping around for one step, clamped for
        larger (page) steps.
        """
        c = self.completion
        if c is None or not c.shown:
            return
        c.index = (c.index + delta) % len(c.shown) if abs(delta) == 1 else max(0, min(len(c.shown) - 1, c.index + delta))

    def select(self, index: int) -> Any:
        """Highlights completion ``index`` and accepts it (a click in the list); returns the editor commands.
        """
        if self.completion is not None:
            self.completion.index = index
            return self.accept()
        return None

    def accept(self) -> Any:
        """Inserts the highlighted completion (and any auto-import it brings) and closes the list.

        Returns the commands that set the editor's text and cursor, or ``None`` if nothing was
        highlighted.
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
        """Keys the editor must hand to the designer instead of handling them: the list navigation keys
        while a completion list is shown, else none.
        """
        return CAPTURED if self.completion is not None and self.completion.shown else ()

    # -- diagnostics and lenses -----------------------------------------------------
    def diagnostics(self) -> List[Diagnostic]:
        """Returns the language servers' errors, warnings and information (hints left out) for the code."""
        return [d for d in self.intel.diagnostics() if d.severity <= 3]

    def annotations(self, t: Theme) -> Dict[int, Any]:
        """Returns the end-of-line annotations by line: code lens texts and, if enabled, the most severe
        diagnostic of each line as ``(text, color)`` in theme ``t``.
        """
        out: Dict[int, Any] = {}
        if self.settings.code_lens:
            out.update(self.intel.lens_annotations())
        if self.settings.inline_diagnostics:
            for diag in sorted(self.diagnostics(), key=lambda d: -d.severity):
                color = {1: t.error, 2: t.warning}.get(diag.severity, t.info)
                out[diag.line] = (f"● {diag.message}", alpha(color, 0.9))
        return out

    def go_to(self, diag: Diagnostic) -> Any:
        """Moves the cursor to diagnostic ``diag`` (a click in the problems list); returns the editor command.
        """
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
        widgets).
        """
        return lambda value: self.set(key, value)

    def zoom(self, step: float) -> None:
        """Ctrl+= / Ctrl+- / Ctrl+0 and Ctrl+wheel in the editor: one point bigger, smaller or back to default."""
        size = _settings.DEFAULT_FONT if step == 0 else self.settings.font_size + (1 if step > 0 else -1)
        size = min(max(size, _settings.MIN_FONT), _settings.MAX_FONT)
        if size != self.settings.font_size:
            self.set("font_size", size)

    def restart_servers(self) -> None:
        """Restarts the language servers, re-attaching them to the code file if the editor is open."""
        if self.servers and self.d.editing is not None:
            self.intel.attach(self.code_file())
        self.intel.restart()

    def format(self, source: str) -> str:
        """Returns ``source`` formatted with ruff when "format on apply" is on (unchanged otherwise or if
        formatting fails).
        """
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
# Views
# ---------------------------------------------------------------------------


def _kind_color(t: Theme, name: str) -> str:
    if name in t.ansi:
        return t.ansi[name]
    return t.color(name)


_ANSI_FOR = {"purple": "magenta", "orange": "red"}


def kind_badge(item: CompletionItem, t: Theme, size: float = 16) -> Any:
    """Returns the colored icon of a completion item's kind, ``size`` pixels square, with a small lock
    for private names.
    """
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
    """Builds the completion list (at most ``visible_rows`` rows around the highlighted one) and, beside
    it, the highlighted item's signature and documentation, at most ``max_height`` pixels tall.
    """
    c = a.completion
    assert c is not None
    rows: List[Any] = []
    first = min(max(c.index - visible_rows // 2, 0), max(len(c.shown) - visible_rows, 0))
    for i, item in enumerate(c.shown[first: first + visible_rows], start=first):
        selected = i == c.index
        label_color = t.text_muted if item.private or item.is_dunder else t.text
        rows.append(_core.button(
            _core.row([
                kind_badge(item, t),
                _core.text(item.label, size=13, font="mono", color=label_color, wrap=False),
                _core.space(width="fill"),
                _core.text(_short(item.detail, 28), size=11, color=t.text_muted, wrap=False),
            ], spacing=8, align="center"),
            lambda i=i: a.select(i), padding=(0, 8), height=ROW_HEIGHT, width="fill",
            bg=t.element_selected if selected else "transparent", hover_bg=t.element_hover, radius=4))
    if c.loading and not rows:
        rows.append(_core.container(ui.label("Loading…", size="sm", color="text_muted", theme=t), padding=(4, 8)))
    footer = _core.container(
        _core.row([ui.label(f"{c.index + 1}/{len(c.shown)}" if c.shown else "", size="xs", color="text_muted",
                            theme=t),
                   _core.space(width="fill"),
                   ui.label("↵ insert  esc close", size="xs", color="text_muted", theme=t)]),
        padding=(2, 8), width="fill")
    listing = _core.container(_core.column([*rows, footer], spacing=0), width=LIST_WIDTH, padding=4,
                              bg=t.elevated, border_color=t.border, border_width=1, radius=6)
    item = c.selected
    if item is None or not (item.detail or item.documentation):
        return listing
    doc_parts = [
        _core.row([kind_badge(item, t, 18), _core.text(item.label, size=13, font="mono", color=t.text, wrap=False),
                   ui.badge("private", theme=t) if item.private else None], spacing=8, align="center"),
        _core.text(item.detail, size=12, font="mono", color=t.text_muted) if item.detail else None,
        ui.divider(theme=t) if item.documentation else None,
        _core.container(ui.markdown(_short_doc(item.documentation), size=12, theme=t),
                        max_height=max(max_height - 80, 40), clip=True) if item.documentation else None,
    ]
    docs = _core.container(_core.column(doc_parts, spacing=6), width=DOC_WIDTH, max_height=max_height, clip=True,
                           padding=10, bg=t.elevated,
                           border_color=t.border, border_width=1, radius=6)
    return _core.row([listing, docs], spacing=4)


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
    completion list, and the error line and problems list below it.
    """
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
    problems = ui.tooltip(problems, "Problems", theme=t)
    header = ui.panel_header(title, icon="code", actions=[
        problems,
        ui.icon_button("settings", d.open_editor_settings, size="sm", tooltip="Editor settings", theme=t),
        ui.button("Whole file" if not whole else "This handler", d.toggle_whole_file, variant="ghost", size="sm",
                  theme=t),
        ui.button("Apply", d.apply_code, icon="check", variant="tinted", size="sm", theme=t),
        ui.icon_button("x", d.close_code, size="sm", tooltip="Close", theme=t),
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
        minimap=s.minimap, cursor_shape=s.cursor_shape, cursor_blink=s.cursor_blink, on_zoom=a.zoom, theme=et)
    area = _editor_area(a, editor, below, s.font_size, text.count("\n") + 1, s.line_numbers)
    return _core.column([header, area], width="fill", height="fill")


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

    theme_names = ["Same as the designer", *themes.names()]
    appearance = ui.settings_group("Appearance", [
        ui.field("Theme", ui.select(theme_names, s.theme or theme_names[0],
                                    lambda name: a.set("theme", "" if name == theme_names[0] else name), width=200,
                                    theme=t), theme=t),
        ui.field("Font size", ui.number_field(s.font_size, a.setter("font_size"), min=8, max=32, step=1, width=110,
                                              theme=t), description="Ctrl+= and Ctrl+- (or Ctrl+wheel); Ctrl+0 resets",
                 theme=t),
        ui.field("Line numbers", switch("line_numbers"), theme=t),
        ui.field("Highlight current line", switch("highlight_line"), theme=t),
        ui.field("Show whitespace", switch("show_whitespace"), description="Spaces as · and tabs as →", theme=t),
        ui.field("Wrap long lines", switch("wrap"), theme=t),
        ui.field("Minimap", switch("minimap"), description="Click or drag it to scroll", theme=t),
    ], theme=t)
    cursor = ui.settings_group("Cursor", [
        ui.field("Shape", ui.segmented([shape.capitalize() for shape in _settings.CURSOR_SHAPES],
                                       s.cursor_shape.capitalize(),
                                       lambda name: a.set("cursor_shape", name.lower()), theme=t), theme=t),
        ui.field("Blink", switch("cursor_blink"), theme=t),
    ], theme=t)
    editing = ui.settings_group("Editing", [
        ui.field("Tab size", ui.number_field(float(s.tab_size), lambda v: a.set("tab_size", int(v)), min=1, max=8,
                                             step=1, width=110, theme=t),
                 description="Tab inserts spaces; Enter keeps the indentation", theme=t),
        ui.field("Autocomplete while typing", switch("autocomplete"), description="Ctrl+Space opens it anytime",
                 theme=t),
        ui.field("Auto-close brackets and quotes", switch("auto_close"),
                 description="Also wraps the selection and steps over the closing one", theme=t),
        ui.field("Code folding", switch("folding"), description="Chevrons in the gutter; Ctrl+Shift+[ and ]",
                 theme=t),
        ui.field("Format with ruff on Apply", switch("format_on_apply"), theme=t),
    ], theme=t)
    lens = ui.settings_group("Code lens and diagnostics", [
        ui.field("Code lens", switch("code_lens"), description="References, implementations and wired events",
                 theme=t),
        ui.field("Inline diagnostics", switch("inline_diagnostics"), description="Problems at the end of the line",
                 theme=t),
    ], theme=t)
    rows = []
    for name, status, detail in a.intel.statuses():
        color = STATUS_COLORS.get(status, "text_muted")
        what = {"ty": "Types, completion and references", "ruff": "Linting"}[name]
        rows.append(_core.row([
            _core.container(width=10, height=10, radius=5, bg=t.color(color)),
            _core.column([ui.label(f"{name}  ·  {status}", theme=t),
                          ui.label(detail or what, size="sm", color="text_muted", theme=t)], spacing=2, width="fill"),
            switch(name),
        ], spacing=10, align="center"))
    env = a.intel.env
    if env is not None:
        rows.append(_core.column([
            ui.label(f"Project  {env.root}", size="sm", color="text_muted", mono=True, theme=t),
            ui.label(f"Python   {env.python}", size="sm", color="text_muted", mono=True, theme=t),
        ], spacing=2))
    servers = ui.settings_group("Language servers", rows, theme=t)
    body = _core.scrollable(_core.column([servers, appearance, cursor, editing, lens], spacing=14, padding=(0, 6, 0, 0)),
                            height=580, scrollbar_width=4)
    return ui.modal(body, title="Editor settings", on_close=d.close_dialog, width=560, footer=[
        ui.button("Restart servers", a.restart_servers, icon="refresh-cw", variant="ghost", theme=t),
        _core.space(width="fill"),
        ui.button("Done", d.close_dialog, variant="solid", theme=t),
    ], theme=t)
