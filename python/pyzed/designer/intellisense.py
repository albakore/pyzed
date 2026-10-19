"""Code intelligence for the designer's editor: diagnostics, completion and code lens.

``CodeIntel`` keeps ty and ruff (see ``designer.lsp``) in sync with the handlers module while
one handler is being edited. The editor shows a single function, so the document sent to the
servers is the whole module with that function swapped for the editor's text; positions are
translated between the editor (1-based, relative to the function) and the file.

It also completes what the servers cannot know: ``form.`` lists the form's controls,
``form.button1.`` the properties of a button and ``event.`` the event's fields.
"""

from __future__ import annotations

import ast
import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import code as _code
from . import components as _components
from . import lsp
from .locale import tr
from .model import Form
from .settings import EditorSettings

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

#: LSP ``CompletionItemKind`` -> the kind names used for icons.
KINDS = {
    1: "text", 2: "method", 3: "function", 4: "constructor", 5: "field", 6: "variable", 7: "class",
    8: "interface", 9: "module", 10: "property", 11: "unit", 12: "value", 13: "enum", 14: "keyword",
    15: "snippet", 16: "color", 17: "file", 18: "reference", 19: "folder", 20: "enum_member",
    21: "constant", 22: "struct", 23: "event", 24: "operator", 25: "type_parameter",
}

#: Icon and theme color of every kind, VS Code style (``private`` names get a lock badge).
KIND_STYLE: Dict[str, Tuple[str, str]] = {
    "method": ("box", "purple"),
    "function": ("square-function", "purple"),
    "constructor": ("hammer", "purple"),
    "class": ("component", "yellow"),
    "struct": ("component", "yellow"),
    "interface": ("component", "yellow"),
    "enum": ("list-ordered", "yellow"),
    "enum_member": ("list-ordered", "cyan"),
    "variable": ("variable", "blue"),
    "field": ("tag", "blue"),
    "property": ("wrench", "blue"),
    "constant": ("square-pi", "cyan"),
    "value": ("hash", "cyan"),
    "module": ("package", "orange"),
    "keyword": ("key-round", "text_muted"),
    "snippet": ("scissors", "text_muted"),
    "type_parameter": ("type", "yellow"),
    "control": ("mouse-pointer-click", "accent"),
    "event": ("zap", "orange"),
    "text": ("text", "text_muted"),
}

SEVERITIES = {1: "error", 2: "warning", 3: "info", 4: "hint"}


@dataclass
class Diagnostic:
    """A problem in the editor's text; lines and columns are 1-based and relative to the editor."""

    line: int
    column: int
    end_line: int
    end_column: int
    severity: int
    message: str
    source: str = ""
    code: Optional[str] = None

    @property
    def level(self) -> str:
        """The severity's name: ``"error"``, ``"warning"``, ``"info"`` or ``"hint"``."""
        return SEVERITIES.get(self.severity, "info")

    @property
    def label(self) -> str:
        """The message, prefixed with the rule's code in brackets when there is one."""
        code = f"[{self.code}] " if self.code else ""
        return f"{code}{self.message}"


@dataclass
class CompletionItem:
    label: str
    kind: str = "text"
    detail: str = ""
    documentation: str = ""
    insert_text: Optional[str] = None
    sort_text: str = ""
    #: Text between the start of the word and the cursor that the item replaces.
    filter_text: str = ""
    #: Extra LSP ``TextEdit``s in file coordinates (the ``import`` an auto-import item adds).
    additional_edits: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def private(self) -> bool:
        """Whether the name starts with an underscore and is not a dunder."""
        return self.label.startswith("_") and not self.is_dunder

    @property
    def is_dunder(self) -> bool:
        """Whether the name is a ``__dunder__`` name."""
        return self.label.startswith("__") and self.label.endswith("__") and len(self.label) > 4

    @property
    def text(self) -> str:
        """The text inserted when the item is accepted (``insert_text``, or the label)."""
        return self.insert_text or self.label

    @property
    def icon(self) -> Tuple[str, str]:
        """The ``(icon, color)`` shown for the item's kind."""
        return KIND_STYLE.get(self.kind, KIND_STYLE["text"])


@dataclass
class Lens:
    """A code lens: a note shown at the end of a definition line (1-based, editor-relative)."""

    line: int
    name: str
    parts: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        """The lens's parts joined into the note shown on the line."""
        return " · ".join(self.parts)


def item_from_lsp(data: Dict[str, Any]) -> CompletionItem:
    """Builds a ``CompletionItem`` from an LSP completion item ``data`` (documentation, details, insert text
    from a ``textEdit`` and the extra edits of auto-imports)."""
    doc = data.get("documentation") or ""
    if isinstance(doc, dict):
        doc = doc.get("value") or ""
    detail = data.get("detail") or ""
    details = data.get("labelDetails") or {}
    if not detail and details:
        detail = (details.get("detail") or "") + (" " + details["description"] if details.get("description") else "")
    insert = data.get("insertText")
    edit = data.get("textEdit")
    if isinstance(edit, dict) and edit.get("newText"):
        insert = edit["newText"]
    return CompletionItem(
        label=data.get("label", ""),
        kind=KINDS.get(data.get("kind") or 1, "text"),
        detail=detail.strip(),
        documentation=str(doc).strip(),
        insert_text=insert,
        sort_text=data.get("sortText") or "",
        filter_text=data.get("filterText") or "",
        additional_edits=[e for e in data.get("additionalTextEdits") or [] if isinstance(e, dict)],
    )


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-z0-9_]*$")


def word_before(line: str, column: int) -> str:
    """The identifier characters right before the 1-based ``column``."""
    match = _WORD.search(line[: max(column - 1, 0)])
    return match.group(0) if match else ""


def should_complete(line: str, column: int) -> bool:
    """Whether typing just produced a place to complete: after a dot or inside a word, not in a comment or string."""
    before = line[: max(column - 1, 0)]
    if not before or before.lstrip().startswith("#"):
        return False
    if before.count('"') % 2 or before.count("'") % 2:
        return False
    if before.endswith("."):
        return not re.search(r"\d\.$", before)
    word = word_before(line, column)
    return bool(word) and not word[0].isdigit()


def filter_items(items: Sequence[CompletionItem], prefix: str, limit: int = 200) -> List[CompletionItem]:
    """Items matching ``prefix`` (case-insensitive prefix first, then subsequence), private ones last."""
    p = prefix.lower()

    def subsequence(label: str) -> bool:
        it = iter(label)
        return all(ch in it for ch in p)

    scored = []
    for item in items:
        label = (item.filter_text or item.label).lower()
        if p and not label.startswith(p) and not subsequence(label):
            continue
        rank = (0 if label.startswith(p) else 1, 2 if item.is_dunder else 1 if item.private else 0,
                item.sort_text or "~", item.label.lower())
        scored.append((rank, item))
    scored.sort(key=lambda pair: pair[0])
    return [item for _, item in scored[:limit]]


def apply_completion(text: str, line: int, column: int, item: CompletionItem) -> Tuple[str, int, int]:
    """Inserts ``item`` at the cursor, replacing the word being typed; returns ``(text, line, column)``."""
    lines = text.split("\n")
    index = min(max(line - 1, 0), len(lines) - 1)
    current = lines[index]
    word = word_before(current, column)
    start = max(column - 1 - len(word), 0)
    end = column - 1
    # also swallow the rest of the identifier after the cursor
    while end < len(current) and (current[end].isalnum() or current[end] == "_"):
        end += 1
    lines[index] = current[:start] + item.text + current[end:]
    return "\n".join(lines), line, start + len(item.text) + 1


def apply_edits(text: str, edits: Sequence[Dict[str, Any]], line_offset: int = 0) -> str:
    """Applies LSP ``TextEdit``s (shifted up by ``line_offset`` lines) to ``text``, last one first."""
    lines = text.split("\n")

    def index(pos: Dict[str, int]) -> int:
        line = min(max(pos["line"] - line_offset, 0), len(lines))
        before = sum(len(x) + 1 for x in lines[:line])
        width = len(lines[line]) if line < len(lines) else 0
        return before + min(pos["character"], width)

    ordered = sorted(edits, key=lambda e: (e["range"]["start"]["line"], e["range"]["start"]["character"]),
                     reverse=True)
    for edit in ordered:
        start, end = index(edit["range"]["start"]), index(edit["range"]["end"])
        text = text[:start] + edit.get("newText", "") + text[end:]
        lines = text.split("\n")
    return text


# ---------------------------------------------------------------------------
# Designer-aware completions
# ---------------------------------------------------------------------------

_FORM_MEMBERS = [
    ("title", "property", "str", "The window title; assigning it renames the running window."),
    ("name", "property", "str", "The form's name."),
    ("size", "property", "tuple[float, float]", "The current size of the window."),
    ("window", "property", "Window", "The Pyzed window running this form (for `Command` helpers)."),
    ("close", "method", "() -> Command", "Returns a command that closes the window."),
]
_CONTROL_MEMBERS = [
    ("name", "property", "str", "The control's name."),
    ("type", "property", "str", "The component type (`button`, `input`...)."),
    ("visible", "property", "bool", "Whether the control is shown."),
    ("enabled", "property", "bool", "Whether the control reacts to the user."),
    ("show", "method", "() -> None", "Makes the control visible."),
    ("hide", "method", "() -> None", "Hides the control."),
    ("focus", "method", "() -> Command", "A command that focuses this control (text boxes and text areas)."),
]
_EVENT_MEMBERS = [
    ("sender", "property", "Control | Form", "The control (or form) that raised the event."),
    ("name", "property", "str", "The event name (`click`, `change`...)."),
    ("value", "property", "Any", "The event's value: new text, checked state, key combo..."),
]


def designer_completions(form: Optional[Form], line: str, column: int) -> Optional[List[CompletionItem]]:
    """Completions for ``form.``, ``form.<control>.`` and ``event.``; ``None`` when not in that position."""
    if form is None:
        return None
    before = line[: max(column - 1, 0)]
    m = re.search(r"\b(form|event)\.(?:([A-Za-z_]\w*)\.)?[A-Za-z_0-9]*$", before)
    if m is None:
        return None
    owner, control_name = m.group(1), m.group(2)
    if owner == "event":
        return None if control_name else [CompletionItem(n, k, d, doc) for n, k, d, doc in _EVENT_MEMBERS]
    if control_name is None:
        items = []
        for control in form.controls:
            comp = _components.get(control.type)
            items.append(CompletionItem(control.name, "control", comp.label if comp else control.type,
                                        comp.description if comp else ""))
        items += [CompletionItem(n, k, d, doc) for n, k, d, doc in _FORM_MEMBERS]
        return items
    control = form.get(control_name)
    if control is None:
        return None
    comp = _components.get(control.type)
    items = []
    if comp is not None:
        for prop in comp.props:
            items.append(CompletionItem(prop.name, "property", _prop_type(prop), prop.label or ""))
    items += [CompletionItem(n, k, d, doc) for n, k, d, doc in _CONTROL_MEMBERS]
    return items


def _prop_type(prop: Any) -> str:
    kind = getattr(prop, "kind", "")
    return {"text": "str", "multiline": "str", "number": "float", "bool": "bool", "color": "str (color)",
            "choice": "str", "list": "list[str]", "icon": "str (icon)"}.get(kind, kind or "Any")


# ---------------------------------------------------------------------------
# The manager
# ---------------------------------------------------------------------------


class CodeIntel:
    """Runs the language servers of a form's project and translates between file and editor.

    ``dispatch`` moves server callbacks onto the UI thread (``pyzed.post`` in the designer);
    ``on_update`` is called (through it) whenever diagnostics, statuses or lenses change.
    """

    def __init__(self, settings: Optional[EditorSettings] = None, *, dispatch: Optional[lsp.Dispatch] = None,
                 on_update: Optional[Callable[[], None]] = None) -> None:
        self.settings = settings or EditorSettings()
        self.dispatch: lsp.Dispatch = dispatch or (lambda fn: fn())
        self.on_update = on_update
        self.env: Optional[lsp.Environment] = None
        self.servers: Dict[str, lsp.LanguageServer] = {}
        self.file: Optional[Path] = None
        self.uri: Optional[str] = None
        self.text = ""
        #: First line (0-based) of the editor's text inside the file, and how many lines it has.
        self.offset = 0
        self.length = 0
        self._raw: Dict[str, List[Dict[str, Any]]] = {}
        self._completion: Optional[Tuple[lsp.LanguageServer, int]] = None
        self.lenses: List[Lens] = []
        self._lens_timer: Optional[threading.Timer] = None
        self._generation = 0

    # -- servers ------------------------------------------------------------
    def attach(self, file: Path) -> None:
        """Starts (or keeps) the servers for the project of ``file``, the handlers module."""
        file = Path(file).resolve()
        env = lsp.find_environment(file)
        same = self.env is not None and self.env.root == env.root and self.env.venv == env.venv
        if self.uri and self.file != file:
            for server in self.servers.values():
                server.close(self.uri)
        self.file, self.uri = file, lsp.uri(file)
        if same:
            self.env = env
            self._sync_enabled()
            return
        self.shutdown()
        self.env = env
        self._sync_enabled()

    def _sync_enabled(self) -> None:
        """Starts the enabled servers and stops the disabled ones."""
        if self.env is None:
            return
        wanted = {"ty": self.settings.ty, "ruff": self.settings.ruff}
        for name, on in wanted.items():
            server = self.servers.get(name)
            if on and server is None:
                make = lsp.ty_server if name == "ty" else lsp.ruff_server
                server = make(self.env, dispatch=self.dispatch, on_status=self._status,
                              on_notification=lambda m, p, name=name: self._notification(name, m, p))
                self.servers[name] = server
                server.start()
                if self.uri and self.text:
                    server.open(self.uri, self.text)
            elif not on and server is not None:
                server.stop()
                del self.servers[name]
                self._raw.pop(name, None)
        self._changed()

    def apply_settings(self, settings: EditorSettings) -> None:
        """Uses the new editor ``settings``, starting or stopping servers that were enabled or disabled."""
        self.settings = settings
        self._sync_enabled()

    def restart(self, name: Optional[str] = None) -> None:
        """Restarts server ``name`` (or all with ``None``), forgetting its diagnostics and reopening the
        text."""
        for key, server in list(self.servers.items()):
            if name in (None, key):
                self._raw.pop(key, None)
                server.restart()
                if self.uri and self.text:
                    server.open(self.uri, self.text)
        self._changed()

    def shutdown(self) -> None:
        """Stops every server and the pending code lens refresh, and forgets their diagnostics."""
        if self._lens_timer is not None:
            self._lens_timer.cancel()
        for server in self.servers.values():
            server.stop()
        self.servers.clear()
        self._raw.clear()

    def statuses(self) -> List[Tuple[str, str, str]]:
        """``(name, status, detail)`` of every known server, including disabled ones."""
        out = []
        for name in ("ty", "ruff"):
            server = self.servers.get(name)
            if server is None:
                out.append((name, "disabled", ""))
            else:
                out.append((name, server.status, server.detail))
        return out

    def _status(self, server: lsp.LanguageServer) -> None:
        if server.ready and self.uri and self.text and self.uri not in server.versions:
            server.open(self.uri, self.text)
        self._changed()

    def _changed(self) -> None:
        if self.on_update is not None:
            self.on_update()

    # -- the document -------------------------------------------------------
    def update(self, module: str, handler: Optional[str], buffer: str) -> None:
        """Sends the module with ``handler`` replaced by ``buffer`` (the whole module when ``handler`` is None)."""
        text, offset = compose(module, handler, buffer)
        self.offset, self.length = offset, buffer.count("\n") + 1
        if text == self.text:
            return
        self.text = text
        self._generation += 1
        if self.uri is None:
            return
        for server in self.servers.values():
            server.change(self.uri, text)
        self._schedule_lenses()

    def _notification(self, name: str, method: str, params: Any) -> None:
        if method != "textDocument/publishDiagnostics" or not isinstance(params, dict):
            return
        if params.get("uri") != self.uri:
            return
        self._raw[name] = list(params.get("diagnostics") or [])
        self._changed()

    def diagnostics(self) -> List[Diagnostic]:
        """Diagnostics inside the editor's text, sorted by position.

        ty and ruff often report the same problem (an undefined name, a syntax error) at the same
        place; only ty's is kept.
        """
        out: List[Diagnostic] = []
        seen = set()
        for _, items in sorted(self._raw.items(), key=lambda pair: pair[0] != "ty"):
            for item in items:
                start = item["range"]["start"]
                end = item["range"]["end"]
                line = start["line"] - self.offset + 1
                if line < 1 or line > self.length:
                    continue
                key = (line, start["character"], item.get("severity") or 1)
                if key in seen:
                    continue
                seen.add(key)
                code = item.get("code")
                out.append(Diagnostic(
                    line=line, column=start["character"] + 1,
                    end_line=end["line"] - self.offset + 1, end_column=end["character"] + 1,
                    severity=item.get("severity") or 1, message=str(item.get("message", "")).split("\n")[0],
                    source=str(item.get("source") or ""), code=str(code) if code is not None else None))
        out.sort(key=lambda d: (d.line, d.column, d.severity))
        return out

    # -- completion ---------------------------------------------------------
    def complete(self, line: int, column: int, callback: Callable[[List[CompletionItem]], None]) -> bool:
        """Asks ty for completions at an editor position; ``False`` when no server can answer."""
        server = self.servers.get("ty")
        if server is None or not server.ready or not server.supports("completionProvider") or self.uri is None:
            return False
        if self._completion is not None:
            self._completion[0].cancel(self._completion[1])
        def done(result: Any) -> None:
            # Answers for an older version are still useful: the list is refiltered as the user types.
            self._completion = None
            raw = result.get("items", []) if isinstance(result, dict) else (result or [])
            callback([item_from_lsp(item) for item in raw if isinstance(item, dict)])

        id_ = server.request("textDocument/completion", {
            "textDocument": {"uri": self.uri},
            "position": {"line": line - 1 + self.offset, "character": column - 1},
            "context": {"triggerKind": 1},
        }, done)
        self._completion = (server, id_) if id_ is not None else None
        return id_ is not None

    # -- code lens ----------------------------------------------------------
    def _schedule_lenses(self, delay: float = 0.6) -> None:
        if not self.settings.code_lens:
            return
        if self._lens_timer is not None:
            self._lens_timer.cancel()
        self._lens_timer = threading.Timer(delay, lambda: self.dispatch(self.refresh_lenses))
        self._lens_timer.daemon = True
        self._lens_timer.start()

    def refresh_lenses(self, form: Optional[Form] = None) -> None:
        """Recomputes the lenses of the definitions in the editor: references, implementations, wiring."""
        if form is not None:
            self._form = form
        form = getattr(self, "_form", None)
        defs = definitions(self.text)
        lenses: Dict[int, Lens] = {}
        for d in defs:
            if not (self.offset < d.line <= self.offset + self.length):
                continue
            lens = Lens(d.line - self.offset, d.name)
            if form is not None and d.kind == "function" and d.depth == 0:
                lens.parts.extend(tr("on {event}", event=f"{owner}.{event}") for owner, event in wired_to(form, d.name))
            if d.kind == "class":
                subclasses = [c.name for c in defs if c.kind == "class" and d.name in c.bases]
                if subclasses:
                    lens.parts.append(_plural(len(subclasses), "implementation"))
            lenses[lens.line] = lens
        self.lenses = sorted(lenses.values(), key=lambda lens: lens.line)
        self._changed()
        server = self.servers.get("ty")
        if server is None or not server.ready or not server.supports("referencesProvider") or self.uri is None:
            self._fallback_references(defs)
            return
        generation = self._generation
        for lens in self.lenses:
            d = next(x for x in defs if x.line - self.offset == lens.line and x.name == lens.name)

            def done(result: Any, lens: Lens = lens) -> None:
                if generation != self._generation:
                    return
                count = len(result or [])
                lens.parts.insert(0, _plural(count, "reference"))
                self._changed()

            server.request("textDocument/references", {
                "textDocument": {"uri": self.uri},
                "position": {"line": d.line - 1, "character": d.column},
                "context": {"includeDeclaration": False},
            }, done)

    def _fallback_references(self, defs: List["Definition"]) -> None:
        counts = name_counts(self.text)
        for lens in self.lenses:
            lens.parts.insert(0, _plural(max(counts.get(lens.name, 1) - 1, 0), "reference"))
        self._changed()

    def lens_annotations(self) -> Dict[int, str]:
        """Returns the code lens notes by editor line (lenses with nothing to say are left out)."""
        return {lens.line: lens.text for lens in self.lenses if lens.parts}


def _plural(n: int, word: str) -> str:
    return tr(f"{{count}} {word}" if n == 1 else f"{{count}} {word}s", count=n)


def compose(module: str, handler: Optional[str], buffer: str) -> Tuple[str, int]:
    """The module with ``handler`` replaced by ``buffer`` and the 0-based line where it starts."""
    if handler is None:
        return buffer, 0
    span = _code.find_function(module, handler)
    lines = module.split("\n")
    if span is None:
        head = module.rstrip("\n")
        prefix = head + "\n\n\n" if head else ""
        return prefix + buffer, prefix.count("\n")
    first, last = span
    before = "\n".join(lines[: first - 1])
    after = "\n".join(lines[last:])
    text = (before + "\n" if first > 1 else "") + buffer.rstrip("\n") + ("\n" + after if after or last < len(lines) else "")
    return text, first - 1


@dataclass
class Definition:
    name: str
    kind: str  # "function" | "class" | "method"
    line: int  # 1-based, in the file
    column: int  # 0-based column of the name
    depth: int
    bases: Tuple[str, ...] = ()


def definitions(source: str) -> List[Definition]:
    """Functions, classes and methods of ``source`` (empty when it does not parse)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    lines = source.split("\n")
    out: List[Definition] = []

    def visit(body: Sequence[ast.stmt], depth: int, in_class: bool) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                text = lines[node.lineno - 1]
                keyword = "class " if isinstance(node, ast.ClassDef) else "def "
                column = text.find(keyword + node.name)
                column = column + len(keyword) if column >= 0 else node.col_offset
                if isinstance(node, ast.ClassDef):
                    bases = tuple(b.id if isinstance(b, ast.Name) else getattr(b, "attr", "") for b in node.bases)
                    out.append(Definition(node.name, "class", node.lineno, column, depth, bases))
                    visit(node.body, depth + 1, True)
                else:
                    out.append(Definition(node.name, "method" if in_class else "function", node.lineno, column, depth))

    visit(tree.body, 0, False)
    return out


def name_counts(source: str) -> Dict[str, int]:
    """How many times each name appears (definitions, calls, attribute accesses)."""
    counts: Dict[str, int] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return counts
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        if name:
            counts[name] = counts.get(name, 0) + 1
    return counts


def wired_to(form: Form, handler: str) -> List[Tuple[str, str]]:
    """The ``(control, event)`` pairs whose event calls ``handler`` (``"form"`` for form events)."""
    out = [("form", event) for event, name in form.events.items() if name == handler]
    for control in form.controls:
        out += [(control.name, event) for event, name in control.events.items() if name == handler]
    return out


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_code(source: str, env: Optional[lsp.Environment]) -> Optional[str]:
    """``source`` formatted by ``ruff format`` (``None`` when ruff is missing or the code does not parse)."""
    exe = env.tool("ruff") if env else lsp.Environment(Path.cwd()).tool("ruff")
    if not exe:
        return None
    try:
        done = subprocess.run([exe, "format", "--stdin-filename", "handlers.py", "-"], input=source,
                              capture_output=True, text=True, timeout=10,
                              cwd=str(env.root) if env else None,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


__all__ = [
    "CodeIntel", "CompletionItem", "Diagnostic", "Lens", "KIND_STYLE", "apply_completion", "compose",
    "definitions", "designer_completions", "filter_items", "format_code", "should_complete", "word_before",
    "wired_to",
]
