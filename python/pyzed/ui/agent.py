"""Components for AI agent interfaces, like the ones in Zed's Agent panel.

Each one is a ``pz.Component``: it keeps its own state (folded or open, the search text, an open
menu) and tells what happened through events, so an app only keeps the data::

    from pyzed import ui

    ui.ToolCall(title="Edit file", detail="ui/main.py", kind="edit", status="waiting",
                diffs=[{"path": "ui/main.py", "old": "x = 1\n", "new": "x = 2\n"}],
                on_allow=lambda e: agent.answer(True), on_deny=lambda e: agent.answer(False))
    ui.Plan(steps=[{"step": "Add the form", "status": "done"}, {"step": "Wire the events", "status": "pending"}])
    ui.EditsBar(files=[{"path": "ui/main.py", "added": 12, "removed": 3}], on_keep=..., on_reject=...)
    ui.ThreadHistory(threads=[{"id": "1", "title": "Login form", "updated": time.time()}], on_open=...)
    ui.AuthPrompt(title="Sign in to Claude", methods=[{"id": "login", "name": "Log in with the browser"}],
                  on_pick=lambda e: sign_in(e.value))
    ui.ServiceRow(name="github", detail="npx -y @modelcontextprotocol/server-github", status="running",
                  enabled=True, on_toggle=...)
    ui.Catalog(items=[{"id": "gemini", "name": "Gemini CLI", "version": "0.64.0"}], on_install=...)
    ui.context_meter(48_000, 200_000)

Texts are translated with ``pz.t`` (keys under ``pyzed.agent``; English and Spanish are built in).
"""

from __future__ import annotations

import inspect
import json
import time
from typing import Any, Dict, List, Mapping, Optional

from .. import _core
from .. import i18n as _i18n
from ..component import Component
from ..i18n import t as _t
from ..icons import icon as _icon
from ..theme import Theme, alpha
from ..theme import current as _current_theme
from .base import button, icon_button, label, tooltip_text
from .display import diff_stat, donut
from .inputs import search_input, switch
from .lists import MenuItem, list_item, menu

__all__ = [
    "AuthPrompt",
    "Catalog",
    "EditsBar",
    "Plan",
    "ServiceRow",
    "ThreadHistory",
    "ToolCall",
    "context_meter",
    "date_group",
    "diff_view",
    "format_tokens",
]

_i18n.add("en", {"pyzed": {"agent": {
    "search_threads": "Search threads…", "no_threads": "No threads yet",
    "no_match": "Nothing matches “{query}”.", "delete": "Delete",
    "groups": {"today": "Today", "yesterday": "Yesterday", "week": "This week", "month": "This month",
               "older": "Older"},
    "allow": "Allow", "allow_always": "Always allow", "deny": "Deny", "failed": "Failed", "rejected": "Rejected",
    "waiting": "Waiting for your answer", "input": "Input", "output": "Output", "more_lines": "… {count} more lines",
    "plan": "Plan", "files_changed": {"one": "{count} file changed", "other": "{count} files changed"},
    "keep_all": "Keep all", "reject_all": "Reject all", "keep": "Keep", "reject": "Reject", "open": "Open",
    "waiting_browser": "Waiting for the browser…", "open_again": "Open the page again", "copy": "Copy",
    "cancel": "Cancel", "more": "More", "search": "Search…", "install": "Install", "installed": "Installed",
    "update_to": "Update to {version}", "nothing": "Nothing to show.",
    "context": "Context window: {used} of {limit} tokens",
    "status": {"running": "Running", "starting": "Starting…", "error": "Error", "off": "Off",
               "installed": "Installed", "missing": "Not installed", "update": "Update available"},
}}})
_i18n.add("es", {"pyzed": {"agent": {
    "search_threads": "Buscar hilos…", "no_threads": "Todavía no hay hilos",
    "no_match": "Nada coincide con “{query}”.", "delete": "Eliminar",
    "groups": {"today": "Hoy", "yesterday": "Ayer", "week": "Esta semana", "month": "Este mes", "older": "Antes"},
    "allow": "Permitir", "allow_always": "Permitir siempre", "deny": "Rechazar", "failed": "Falló",
    "rejected": "Rechazado", "waiting": "Esperando tu respuesta", "input": "Entrada", "output": "Salida",
    "more_lines": "… {count} líneas más",
    "plan": "Plan", "files_changed": {"one": "{count} archivo cambiado", "other": "{count} archivos cambiados"},
    "keep_all": "Conservar todo", "reject_all": "Rechazar todo", "keep": "Conservar", "reject": "Rechazar",
    "open": "Abrir", "waiting_browser": "Esperando al navegador…", "open_again": "Abrir la página otra vez",
    "copy": "Copiar", "cancel": "Cancelar", "more": "Más", "search": "Buscar…", "install": "Instalar",
    "installed": "Instalado", "update_to": "Actualizar a {version}", "nothing": "No hay nada que mostrar.",
    "context": "Ventana de contexto: {used} de {limit} tokens",
    "status": {"running": "En marcha", "starting": "Iniciando…", "error": "Error", "off": "Apagado",
               "installed": "Instalado", "missing": "Sin instalar", "update": "Hay una actualización"},
}}})


def _th(theme: Optional[Theme]) -> Theme:
    return theme or _current_theme()


def _get(item: Any, name: str, default: Any = None) -> Any:
    """``item[name]`` for dicts, ``item.name`` for objects."""
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


# -- small helpers -----------------------------------------------------------------------------------

def format_tokens(count: float) -> str:
    """``950`` -> ``"950"``, ``48_000`` -> ``"48k"``, ``1_250_000`` -> ``"1.25M"``."""
    count = max(float(count), 0.0)
    if count < 1000:
        return str(int(count))
    if count < 1_000_000:
        value = count / 1000
        return f"{value:.1f}".rstrip("0").rstrip(".") + "k" if value < 10 else f"{value:.0f}k"
    return f"{count / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M"


def context_meter(used: float, limit: float, *, theme: Optional[Theme] = None) -> _core.Widget:
    """How full the model's context window is, like Zed's token counter: a small ring and ``48k / 200k``.
    It turns yellow past 80% and red past 95%."""
    t = _th(theme)
    share = min(used / limit, 1.0) if limit else 0.0
    color = t.error if share >= 0.95 else t.warning if share >= 0.8 else t.text_muted
    ring = donut([share, 1.0 - share], colors=[color, alpha(t.text, 0.12)], size=14, thickness=2.5, theme=t)
    text = f"{format_tokens(used)} / {format_tokens(limit)}"
    body = _core.row([ring, _core.text(text, size=11.5, color=color, font="mono", wrap=False)], spacing=4,
                     align="center")
    return tooltip_text(body, _t("pyzed.agent.context", used=f"{int(used):,}", limit=f"{int(limit):,}"), theme=t)


def date_group(stamp: float, now: Optional[float] = None) -> str:
    """The history group of a time (``"today"``, ``"yesterday"``, ``"week"``, ``"month"`` or ``"older"``)."""
    now = time.time() if now is None else now
    today = time.localtime(now)
    midnight = time.mktime((today.tm_year, today.tm_mon, today.tm_mday, 0, 0, 0, 0, 0, -1))
    if stamp >= midnight:
        return "today"
    if stamp >= midnight - 86400:
        return "yesterday"
    if stamp >= midnight - 6 * 86400:
        return "week"
    if stamp >= midnight - 30 * 86400:
        return "month"
    return "older"


_GROUPS = ("today", "yesterday", "week", "month", "older")


# -- thread history ----------------------------------------------------------------------------------

class ThreadHistory(Component):
    """Past conversations with a search box, grouped by day like Zed's thread history.

    ``threads`` are dicts or objects with ``id``, ``title``, ``updated`` (a timestamp) and an optional
    ``detail`` (the model, the agent...)."""

    threads: list = None  # type: ignore[assignment]
    selected: str = ""
    theme: Any = None
    events = {"open": "A thread was picked (``event.value`` is its id).",
              "delete": "Delete was pressed on a thread (``event.value`` is its id)."}
    icon = "history"
    category = "Agent"
    designer = False

    def setup(self) -> None:
        self.query = ""

    def set_query(self, text: str) -> None:
        """Filters the threads by ``text``."""
        self.query = text

    def visible(self) -> List[Any]:
        """The threads whose title or detail has every word of the search."""
        words = self.query.lower().split()
        out = []
        for item in self.threads or []:
            text = f"{_get(item, 'title', '')} {_get(item, 'detail', '')}".lower()
            if all(w in text for w in words):
                out.append(item)
        return out

    def render(self) -> Any:
        t = _th(self.theme)
        search = _core.container(search_input(self.query, self.set_query, placeholder=_t("pyzed.agent.search_threads"),
                                              size="sm", theme=t), padding=(6, 8, 4, 8), width="fill")
        items = self.visible()
        if not items:
            text = _t("pyzed.agent.no_match", query=self.query) if self.query else _t("pyzed.agent.no_threads")
            return _core.column([search, _core.container(label(text, size="sm", color="text_muted", theme=t),
                                                         padding=(16, 12), width="fill", align_x="center")],
                                width="fill", height="fill")
        now = time.time()
        groups: Dict[str, List[Any]] = {g: [] for g in _GROUPS}
        for item in sorted(items, key=lambda i: -float(_get(i, "updated", 0) or 0)):
            groups[date_group(float(_get(item, "updated", 0) or 0), now)].append(item)
        rows: List[Any] = []
        for name in _GROUPS:
            if not groups[name]:
                continue
            rows.append(_core.container(label(_t(f"pyzed.agent.groups.{name}"), size="xs", weight="medium",
                                              color="text_muted", theme=t), padding=(8, 8, 2, 8)))
            for item in groups[name]:
                ident = str(_get(item, "id", ""))
                detail = str(_get(item, "detail", "") or "")
                rows.append(_core.row([
                    _core.container(list_item(
                        str(_get(item, "title", "") or ident), lambda i=ident: self.emit("open", i),
                        selected=ident == self.selected, height=28,
                        end=label(detail, size="xs", color="text_placeholder", wrap=False, theme=t) if detail else None,
                        theme=t), width="fill"),
                    icon_button("trash-2", lambda i=ident: self.emit("delete", i), size="sm",
                                tooltip=_t("pyzed.agent.delete"), theme=t),
                ], spacing=2, align="center"))
        return _core.column([search, _core.scrollable(_core.column(rows, spacing=1, width="fill", padding=(0, 6, 6, 6)),
                                                      height="fill", scrollbar_width=4)], width="fill", height="fill")


# -- a tool call -------------------------------------------------------------------------------------

#: The icon of each kind of tool call (ACP's tool kinds).
KIND_ICONS = {"read": "file-text", "edit": "pencil", "delete": "trash-2", "move": "move", "search": "search",
              "execute": "terminal", "think": "brain", "fetch": "globe", "switch_mode": "arrow-left-right",
              "other": "wrench"}


class ToolCall(Component):
    """One action of an agent: a header (status, title and what it works on) that unfolds to show what it
    got and what it answered. While ``status`` is ``"waiting"`` it asks right there, like Zed: Allow,
    Always allow or Deny.

    ``status`` is ``"pending"``, ``"running"``, ``"waiting"``, ``"done"``, ``"failed"`` or ``"rejected"``.
    ``diffs`` (``{"path", "old", "new"}``) are the edits it made, shown as colored diffs; ``progress`` is what
    it printed so far (a command's output), shown under the header while it runs."""

    title: str = ""
    detail: str = ""
    kind: str = ""
    status: str = "done"
    input: Any = None
    output: Any = None
    images: list = None  # type: ignore[assignment]
    diffs: list = None  # type: ignore[assignment]
    progress: str = ""
    allow_always: bool = True
    theme: Any = None
    events = {"allow": "Allow was pressed.", "allow_always": "Always allow was pressed.",
              "deny": "Deny was pressed."}
    icon = "wrench"
    category = "Agent"
    designer = False

    def setup(self) -> None:
        self.expanded = False

    def toggle(self) -> None:
        """Unfolds or folds the input and output."""
        self.expanded = not self.expanded

    def _lead(self, t: Theme) -> Any:
        if self.status in ("running", "pending"):
            from .display import spinner

            return spinner(size=12, theme=t)
        if self.status == "waiting":
            return _icon("hand", size=12, color=t.warning)
        if self.status in ("failed", "rejected"):
            return _icon("circle-x", size=12, color=t.error)
        return _icon(KIND_ICONS.get(self.kind, "check"), size=12, color=t.text_muted)

    def render(self) -> Any:
        t = _th(self.theme)
        end = None
        if self.status in ("failed", "rejected"):
            end = label(_t(f"pyzed.agent.{self.status}"), size="xs", color="error", theme=t)
        has_body = self.input not in (None, {}, "") or self.output not in (None, "") or bool(self.images) \
            or bool(self.diffs)
        head = _core.row([
            self._lead(t),
            label(self.title, size="sm", color="text_muted", wrap=False, theme=t),
            label(self.detail, size="sm", mono=True, color="text_placeholder", wrap=False, theme=t)
            if self.detail else None,
            _core.space(width="fill"),
            end,
            _icon("chevron-down" if self.expanded else "chevron-right", size=11, color=t.text_placeholder)
            if has_body else None,
        ], spacing=6, align="center")
        rows: List[Any] = [_core.button(head, self.toggle if has_body else None, padding=(3, 6), width="fill", bg=None,
                                        hover_bg=t.element_hover, radius=t.radius)]
        if self.expanded and has_body:
            rows.append(self._body(t))
        elif self.status in ("running", "waiting") and (self.diffs or self.progress):
            # what it is doing right now, without unfolding it: the edit, or the last lines it printed
            rows.append(_core.container(_core.column(
                [diff_view(d, theme=t, max_lines=12) for d in self.diffs or []] if self.diffs else
                [label("\n".join(self.progress.rstrip().splitlines()[-6:]), size="xs", mono=True, color="text_muted",
                       theme=t)], spacing=4), padding=(4, 8), width="fill", bg=t.editor, radius=t.radius))
        if self.status == "waiting":
            rows.append(_core.container(_core.row([
                label(_t("pyzed.agent.waiting"), size="xs", color="text_muted", theme=t),
                _core.space(width="fill"),
                button(_t("pyzed.agent.deny"), lambda: self.emit("deny"), variant="ghost", size="sm", theme=t),
                button(_t("pyzed.agent.allow_always"), lambda: self.emit("allow_always"), variant="ghost", size="sm",
                       theme=t) if self.allow_always else None,
                button(_t("pyzed.agent.allow"), lambda: self.emit("allow"), variant="solid", size="sm", theme=t),
            ], spacing=4, align="center", wrap=True), padding=(4, 6), width="fill", bg=alpha(t.warning, 0.08),
                radius=t.radius))
        border = t.warning if self.status == "waiting" else None
        column = _core.column(rows, spacing=2, width="fill")
        if border is None:
            return column
        return _core.container(column, padding=2, width="fill", border_color=alpha(border, 0.5), border_width=1,
                               radius=t.radius + 2)

    def _body(self, t: Theme) -> Any:
        parts: List[Any] = [diff_view(d, theme=t) for d in self.diffs or []]
        for name, value in (("input", None if self.diffs else self.input), ("output", self.output)):
            if value in (None, {}, ""):
                continue
            text = value if isinstance(value, str) else json.dumps(value, indent=1, ensure_ascii=False)
            parts.append(label(_t(f"pyzed.agent.{name}"), size="xs", weight="medium", color="text_placeholder",
                               theme=t))
            parts.append(label(text[:4000], size="xs", mono=True, color="text_muted", theme=t))
        pictures = [_core.image(data, height=160, content_fit="contain", radius=4) for data in self.images or [] if data]
        if pictures:
            parts.append(_core.row(pictures, spacing=6, wrap=True))
        return _core.container(_core.column(parts, spacing=4), padding=(6, 8), width="fill", bg=t.editor,
                               radius=t.radius)


def diff_view(diff: Mapping[str, Any], *, theme: Optional[Theme] = None, max_lines: int = 120) -> _core.Widget:
    """An edit as Zed shows it in a thread: the file's name, then the changed lines (green added, red
    removed) with a few lines around them. ``diff`` has ``path``, ``old`` and ``new`` (texts)."""
    import difflib

    t = _th(theme)
    old, new = str(diff.get("old") or "").splitlines(), str(diff.get("new") or "").splitlines()
    lines = [line for line in difflib.unified_diff(old, new, lineterm="", n=2)][2:]  # without the file headers
    rows: List[Any] = [label(str(diff.get("path") or ""), size="xs", mono=True, color="text_muted", theme=t)]
    for line in lines[:max_lines]:
        if line.startswith("@@"):
            rows.append(_core.text("⋯", size=11, color=t.text_placeholder, font="mono"))
            continue
        sign = line[:1]
        bg = alpha(t.success, 0.14) if sign == "+" else alpha(t.error, 0.14) if sign == "-" else None
        color = t.success if sign == "+" else t.error if sign == "-" else t.text_muted
        rows.append(_core.container(_core.text(line or " ", size=11, color=color, font="mono", wrap=False),
                                    padding=(0, 4), width="fill", bg=bg))
    if len(lines) > max_lines:
        rows.append(label(_t("pyzed.agent.more_lines", count=len(lines) - max_lines), size="xs",
                          color="text_placeholder", theme=t))
    return _core.column(rows, spacing=0, width="fill")


# -- the plan ----------------------------------------------------------------------------------------

class Plan(Component):
    """An agent's plan as a checklist with ``done/total`` in its header, which folds it.

    ``steps`` are ``{"step": text, "status": "pending" | "in_progress" | "done"}``."""

    steps: list = None  # type: ignore[assignment]
    running: bool = False
    theme: Any = None
    icon = "list-checks"
    category = "Agent"
    designer = False

    def setup(self) -> None:
        self.folded = False

    def toggle(self) -> None:
        """Folds or unfolds the steps."""
        self.folded = not self.folded

    def render(self) -> Any:
        t = _th(self.theme)
        steps = list(self.steps or [])
        done = sum(1 for s in steps if _get(s, "status") == "done")
        head = _core.row([
            _icon("list-checks", size=13, color=t.text_accent),
            label(_t("pyzed.agent.plan"), size="sm", weight="medium", theme=t),
            label(f"{done}/{len(steps)}", size="xs", color="text_muted", theme=t),
            _core.space(width="fill"),
            _icon("chevron-right" if self.folded else "chevron-down", size=12, color=t.text_placeholder),
        ], spacing=6, align="center")
        rows: List[Any] = [_core.button(head, self.toggle, padding=(2, 4), bg=None, hover_bg=t.element_hover,
                                        radius=t.radius, width="fill")]
        if not self.folded:
            from .display import spinner

            for step in steps:
                status = _get(step, "status", "pending")
                if status == "in_progress":
                    lead = spinner(size=12, theme=t) if self.running else _icon("circle-dot", size=12, color=t.accent)
                else:
                    lead = _icon("circle-check" if status == "done" else "circle", size=12,
                                 color=t.success if status == "done" else t.text_placeholder)
                rows.append(_core.row([lead, label(str(_get(step, "step", "")), size="sm", theme=t,
                                                   color="text_muted" if status == "done" else "text")],
                                      spacing=8, align="center", padding=(0, 4)))
        return _core.container(_core.column(rows, spacing=4, width="fill"), padding=(6, 8), width="fill", bg=t.surface,
                               border_color=t.border_variant, border_width=1, radius=t.radius + 2)


# -- the files an agent changed ----------------------------------------------------------------------

class EditsBar(Component):
    """The files an agent changed, like Zed's edits bar: ``3 files changed`` with Reject all / Keep all,
    unfolding to one row per file (open it, reject or keep it alone).

    ``files`` are dicts or objects with ``path`` and optional ``added`` / ``removed`` line counts."""

    files: list = None  # type: ignore[assignment]
    theme: Any = None
    events = {"keep": "Keep all was pressed.", "reject": "Reject all was pressed.",
              "keep_file": "Keep was pressed on a file (``event.value`` is its path).",
              "reject_file": "Reject was pressed on a file (``event.value`` is its path).",
              "open": "A file was clicked (``event.value`` is its path)."}
    icon = "file-diff"
    category = "Agent"
    designer = False

    def setup(self) -> None:
        self.expanded = False

    def toggle(self) -> None:
        """Shows or hides the row of each file."""
        self.expanded = not self.expanded

    def render(self) -> Any:
        t = _th(self.theme)
        files = list(self.files or [])
        added = sum(int(_get(f, "added", 0) or 0) for f in files)
        removed = sum(int(_get(f, "removed", 0) or 0) for f in files)
        head = _core.row([
            _core.button(_core.row([
                _icon("chevron-down" if self.expanded else "chevron-right", size=12, color=t.text_placeholder),
                label(_t("pyzed.agent.files_changed", count=len(files)), size="sm", weight="medium", wrap=False,
                      theme=t),
                diff_stat(added, removed, theme=t) if added or removed else None,
            ], spacing=6, align="center"), self.toggle, padding=(2, 4), bg=None, hover_bg=t.element_hover,
                radius=t.radius),
            _core.space(width="fill"),
            button(_t("pyzed.agent.reject_all"), lambda: self.emit("reject"), variant="ghost", size="sm", theme=t),
            button(_t("pyzed.agent.keep_all"), lambda: self.emit("keep"), variant="tinted", size="sm", theme=t),
        ], spacing=4, align="center")
        rows: List[Any] = [head]
        if self.expanded:
            for f in files:
                path = str(_get(f, "path", ""))
                name, _, folder = path.replace("\\", "/").rpartition("/")[::-1]
                rows.append(_core.row([
                    _core.button(_core.row([
                        _icon("file", size=12, color=t.text_muted),
                        label(name or path, size="sm", wrap=False, theme=t),
                        label(folder, size="xs", color="text_placeholder", wrap=False, theme=t) if folder else None,
                    ], spacing=6, align="center"), lambda p=path: self.emit("open", p), padding=(2, 4), bg=None,
                        hover_bg=t.element_hover, radius=t.radius),
                    _core.space(width="fill"),
                    diff_stat(int(_get(f, "added", 0) or 0), int(_get(f, "removed", 0) or 0), blocks=3, theme=t)
                    if _get(f, "added") is not None else None,
                    icon_button("undo-2", lambda p=path: self.emit("reject_file", p), size="sm",
                                tooltip=_t("pyzed.agent.reject"), theme=t),
                    icon_button("check", lambda p=path: self.emit("keep_file", p), size="sm",
                                tooltip=_t("pyzed.agent.keep"), theme=t),
                ], spacing=4, align="center", padding=(0, 0, 0, 14)))
        return _core.container(_core.column(rows, spacing=2, width="fill"), padding=(4, 6), width="fill",
                               bg=alpha(t.accent, 0.06), border_color=t.border_variant, border_width=1,
                               radius=t.radius + 2)


# -- signing in --------------------------------------------------------------------------------------

class AuthPrompt(Component):
    """Asks to sign in, like Zed when an agent needs it: one button per way to sign in (``methods``: dicts
    with ``id``, ``name``, optional ``description`` and ``icon``; the first is the main one). While
    ``waiting`` holds a method id it shows that the browser (or a terminal) is open, with a ``code`` to
    type when there is one, "Open the page again" when ``url`` is set, and Cancel."""

    title: str = ""
    detail: str = ""
    methods: list = None  # type: ignore[assignment]
    waiting: str = ""
    waiting_text: str = ""
    code: str = ""
    url: str = ""
    error: str = ""
    icon_name: str = "key-round"
    theme: Any = None
    events = {"pick": "A way to sign in was picked (``event.value`` is its id).",
              "cancel": "Cancel was pressed while waiting.",
              "open_url": "Open the page again was pressed (``event.value`` is the URL).",
              "copy": "The code was copied (``event.value`` is the code)."}
    icon = "log-in"
    category = "Agent"
    designer = False

    def render(self) -> Any:
        t = _th(self.theme)
        from .display import spinner

        lead = spinner(size=14, theme=t) if self.waiting else _icon(self.icon_name, size=14, color=t.text_accent)
        rows: List[Any] = [_core.row([lead, label(self.title, size="sm", weight="medium", theme=t)], spacing=8,
                                     align="center")]
        if self.waiting:
            rows.append(label(self.waiting_text or _t("pyzed.agent.waiting_browser"), size="xs", color="text_muted",
                              theme=t))
            if self.code:
                rows.append(_core.row([
                    label(self.code, size="lg", weight="semibold", mono=True, theme=t),
                    icon_button("copy", lambda: self.emit("copy", self.code), size="sm", tooltip=_t("pyzed.agent.copy"),
                                theme=t),
                ], spacing=6, align="center"))
            rows.append(_core.row([
                button(_t("pyzed.agent.open_again"), lambda: self.emit("open_url", self.url), variant="ghost",
                       size="sm", theme=t) if self.url else None,
                button(_t("pyzed.agent.cancel"), lambda: self.emit("cancel"), variant="ghost", size="sm", theme=t),
            ], spacing=4, wrap=True))
        else:
            if self.detail:
                rows.append(label(self.detail, size="xs", color="text_muted", theme=t))
            buttons = []
            for i, m in enumerate(self.methods or []):
                ident = str(_get(m, "id", ""))
                text = str(_get(m, "name", "") or ident)
                tip = str(_get(m, "description", "") or "")
                widget = button(text, lambda i=ident: self.emit("pick", i), icon=_get(m, "icon"),
                                variant="solid" if i == 0 else "ghost", size="sm", theme=t)
                buttons.append(tooltip_text(widget, tip, theme=t) if tip else widget)
            rows.append(_core.row(buttons, spacing=4, wrap=True))
        if self.error:
            rows.append(label(self.error, size="xs", color="error", theme=t))
        return _core.container(_core.column(rows, spacing=6, width="fill"), padding=(8, 10), width="fill",
                               bg=alpha(t.accent, 0.08), border_color=t.border_variant, border_width=1,
                               radius=t.radius + 2)


# -- settings rows -----------------------------------------------------------------------------------

#: The dot color of each status of a ``ServiceRow``.
_STATUS_COLORS = {"running": "success", "installed": "success", "starting": "warning", "update": "accent",
                  "error": "error", "missing": "text_placeholder", "off": "text_placeholder"}


class ServiceRow(Component):
    """One configured thing an agent uses (an MCP server, an external agent, a skill), like the rows of
    Zed's agent settings: a status dot, its name and command, an on/off switch, a main button (Update,
    Install...) and a ``⋯`` menu with ``actions`` (``ui.MenuItem``)."""

    name: str = ""
    detail: str = ""
    summary: str = ""
    icon_name: str = "plug"
    status: str = ""
    status_text: str = ""
    version: str = ""
    enabled: Any = None
    busy: bool = False
    primary: str = ""
    actions: list = None  # type: ignore[assignment]
    theme: Any = None
    events = {"toggle": "The switch was flipped (``event.value`` is the new state).",
              "primary": "The main button was pressed."}
    icon = "plug"
    category = "Agent"
    designer = False

    def setup(self) -> None:
        self.menu_open = False

    def toggle_menu(self) -> None:
        """Opens or closes the ``⋯`` menu."""
        self.menu_open = not self.menu_open

    def _run(self, action: Any) -> Any:
        self.menu_open = False
        return action() if callable(action) else None

    def render(self) -> Any:
        t = _th(self.theme)
        from .display import spinner

        dot = None
        if self.status:
            dot = _core.container(None, width=7, height=7, radius=3.5,
                                  bg=t.color(_STATUS_COLORS.get(self.status, "text_placeholder")))
            dot = tooltip_text(dot, self.status_text or _t(f"pyzed.agent.status.{self.status}", default=self.status),
                               theme=t)
        dimmed = self.enabled is False
        title = _core.row([
            label(self.name, size="sm", weight="medium", color="text_muted" if dimmed else "text", wrap=False, theme=t),
            label(self.version, size="xs", color="text_placeholder", wrap=False, theme=t) if self.version else None,
            dot,
        ], spacing=6, align="center")
        info = _core.container(_core.column([
            title,
            label(self.detail[:90], size="xs", mono=True, color="text_placeholder", wrap=False, theme=t)
            if self.detail else None,
            label(self.summary, size="xs", color="text_muted", theme=t) if self.summary else None,
            label(self.status_text, size="xs", color="error" if self.status == "error" else "text_muted", theme=t)
            if self.status_text and self.status in ("error", "missing", "update") else None,
        ], spacing=2, width="fill"), width="fill", clip=True)
        actions = list(self.actions or [])
        row = _core.row([
            _icon(self.icon_name, size=14, color=t.text_muted if dimmed else t.text_accent),
            info,
            spinner(size=12, theme=t) if self.busy else None,
            button(self.primary, lambda: self.emit("primary"), variant="tinted", size="sm", disabled=self.busy,
                   theme=t) if self.primary else None,
            switch(bool(self.enabled), lambda v: self.emit("toggle", v), theme=t) if self.enabled is not None else None,
            icon_button("ellipsis", self.toggle_menu, size="sm", selected=self.menu_open,
                        tooltip=_t("pyzed.agent.more"), theme=t) if actions else None,
        ], spacing=8, align="center")
        if not (self.menu_open and actions):
            return _core.container(row, padding=(4, 0), width="fill")
        items = [a if isinstance(a, str) else MenuItem(a.label, lambda a=a: self._run(a.on_press), icon=a.icon,
                                                       keys=a.keys, disabled=a.disabled, danger=a.danger,
                                                       checked=a.checked) for a in actions]
        return _core.column([row, _core.container(menu(items, width=200, theme=t), width="fill", align_x="end")],
                            spacing=2, width="fill", padding=(4, 0))


class Catalog(Component):
    """Things to install with a search box (agents from a registry, servers, skills...). ``items`` are dicts
    or objects with ``id``, ``name`` and optional ``version``, ``description``, ``installed`` (bool) and
    ``update`` (a newer version)."""

    items: list = None  # type: ignore[assignment]
    busy: str = ""
    height: float = 320
    theme: Any = None
    events = {"install": "Install (or Update) was pressed (``event.value`` is the item's id)."}
    icon = "package-search"
    category = "Agent"
    designer = False

    def setup(self) -> None:
        self.query = ""

    def set_query(self, text: str) -> None:
        """Filters the items by ``text``."""
        self.query = text

    def visible(self) -> List[Any]:
        """The items whose id, name or description has every word of the search."""
        words = self.query.lower().split()
        return [i for i in self.items or [] if all(
            w in f"{_get(i, 'id', '')} {_get(i, 'name', '')} {_get(i, 'description', '')}".lower() for w in words)]

    def render(self) -> Any:
        t = _th(self.theme)
        from .display import spinner

        rows: List[Any] = []
        for item in self.visible():
            ident = str(_get(item, "id", ""))
            update = str(_get(item, "update", "") or "")
            installed = bool(_get(item, "installed", False))
            if self.busy == ident:
                end: Any = spinner(size=12, theme=t)
            elif update:
                end = button(_t("pyzed.agent.update_to", version=update), lambda i=ident: self.emit("install", i),
                             variant="tinted", size="sm", theme=t)
            elif installed:
                end = label(_t("pyzed.agent.installed"), size="xs", color="text_muted", theme=t)
            else:
                end = button(_t("pyzed.agent.install"), lambda i=ident: self.emit("install", i), variant="ghost",
                             size="sm", disabled=bool(self.busy), theme=t)
            rows.append(_core.row([
                _core.column([
                    _core.row([label(str(_get(item, "name", "") or ident), size="sm", weight="medium", wrap=False,
                                     theme=t),
                               label(str(_get(item, "version", "") or ""), size="xs", color="text_placeholder",
                                     wrap=False, theme=t)], spacing=6, align="center"),
                    label(str(_get(item, "description", "") or ""), size="xs", color="text_muted", theme=t),
                ], spacing=2, width="fill"),
                end,
            ], spacing=8, align="center", padding=(4, 4)))
        body: Any = _core.column(rows, spacing=2, width="fill") if rows else _core.container(
            label(_t("pyzed.agent.nothing"), size="sm", color="text_muted", theme=t), padding=12)
        return _core.column([
            search_input(self.query, self.set_query, placeholder=_t("pyzed.agent.search"), size="sm", theme=t),
            _core.scrollable(body, height=self.height, scrollbar_width=4),
        ], spacing=6, width="fill")


def _signature(cls: type) -> None:
    """Gives ``cls`` the signature of its props and events (shown by help() and the reference)."""
    params = [inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY,
                                default=inspect.Parameter.empty if info.required else info.default)
              for name, info in cls.__props__.items()]
    params += [inspect.Parameter(f"on_{name}", inspect.Parameter.KEYWORD_ONLY, default=None)
               for name in cls.__events__ if name not in ("mount", "unmount")]
    cls.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]


for _cls in (ToolCall, Plan, EditsBar, ThreadHistory, AuthPrompt, ServiceRow, Catalog):
    _signature(_cls)
