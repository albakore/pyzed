"""The Component view: what a ``.pzcomp`` tab shows that a form's Form view does not.

A form is edited visually and its code only runs when the app does. A component is a
reusable piece whose class says what it can do, so its view adds:

* **Try values**: the component's properties with a value to try, in the inspector (the
  property grid with nothing selected). Changing one redraws the canvas through the
  bindings, without running any logic, and is never saved: the defaults stay in the code.
* **Design / Live**: the canvas toolbar switches between placing controls (Design, the
  bindings drawn with the tried values) and the component as its code renders it (Live:
  its class runs, ``setup``, handlers and all, with the tried values as props).
* **Members**: what the class brings, under the Outline: variables (public props and
  private state), methods, custom events and the other classes of its module. A click
  opens it in the inspector or the code editor.

Form and component tabs share the script link of the outline (``script_button``): the
root row shows the ``.py`` the document is tied to, like the script icon of a Godot node,
and controls that are designed components link to their own script. Components written
only in code show none: their code makes everything, there is nothing to link.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha
from . import scene_code, spacing
from . import type_editor as _type_editor
from .locale import tr
from .scene import SceneDocument

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: The icon of a linked script, in the outline and the Members panel.
SCRIPT_ICON = "file-code-2"
MEMBER_ROW = 24


@dataclass
class ViewState:
    """What the Component view keeps for one open component (not saved with it)."""

    #: Values being tried, as Python source, by property name (missing: its default).
    tries: Dict[str, str] = field(default_factory=dict)
    #: Whether the canvas shows the component running (Live) instead of the controls to edit (Design).
    live: bool = False
    #: Custom events the live component raised, newest last.
    log: List[str] = field(default_factory=list)
    #: Bumped by Restart: the live instance starts again from ``setup``.
    run: int = 0
    #: ``(key, class or None, error)`` of the last class compiled for Live.
    compiled: Tuple[Any, Optional[type], str] = (None, None, "")


def state(doc: Any) -> ViewState:
    """The Component view state of ``doc`` (created on first use)."""
    found = doc.__dict__.get("_component_view")
    if found is None:
        found = doc.__dict__["_component_view"] = ViewState()
    return found


def is_component(d: "Designer") -> bool:
    return isinstance(d.doc, SceneDocument)


# -- tried values ------------------------------------------------------------------------


def tried_source(doc: SceneDocument, member: scene_code.Member) -> str:
    """The source of the value tried for ``member``: the one typed in the inspector, else its default."""
    return state(doc).tries.get(member.name, member.default_source)


def is_tried(doc: SceneDocument, name: str) -> bool:
    """Whether ``name`` has a value being tried that is not its default."""
    member = next((m for m in doc.all_members if m.name == name), None)
    tried = state(doc).tries.get(name)
    return member is not None and tried is not None and tried != member.default_source


def set_try(doc: SceneDocument, name: str, source: Optional[str]) -> None:
    """Tries ``source`` as the value of property ``name`` (``None``: back to its default)."""
    tries = state(doc).tries
    if source is None:
        tries.pop(name, None)
    else:
        tries[name] = source


def reset_tries(doc: SceneDocument) -> None:
    """Every property back to its default."""
    state(doc).tries.clear()


def _value(source: str, fallback: Any) -> Any:
    try:
        return ast.literal_eval(source)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return fallback


def values(doc: SceneDocument, *, public_only: bool = False) -> Dict[str, Any]:
    """The value of every property (its own and inherited ones) as it is being tried: literals only, so no
    code runs; a value that is not a literal keeps the default read from the class."""
    out: Dict[str, Any] = {}
    for m in doc.all_members:
        if public_only and not m.public:
            continue
        out[m.name] = _value(tried_source(doc, m), m.default)
    return out


def bound_props(doc: SceneDocument, *, expressions: bool = True) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """What the bindings give each control with the tried values: ``({control: {prop: value}}, {"control.prop":
    error})``. A binding to a property is a plain lookup; a Python expression is evaluated only with
    ``expressions`` (the designer passes whether the project is trusted)."""
    names = values(doc)
    out: Dict[str, Dict[str, Any]] = {}
    errors: Dict[str, str] = {}
    for control, props in doc.scene.bindings.items():
        if doc.scene.get(control) is None:
            continue
        for prop, expression in props.items():
            if not expression:
                continue
            if expression in names:
                out.setdefault(control, {})[prop] = names[expression]
                continue
            if not expressions:
                continue
            try:
                code = compile(expression, "<binding>", "eval")
                out.setdefault(control, {})[prop] = eval(code, {"__builtins__": __builtins__}, dict(names))  # noqa: S307
            except Exception as err:  # noqa: BLE001 - shown on the control
                errors[f"{control}.{prop}"] = f"{type(err).__name__}: {err}"
    return out, errors


def canvas_props(d: "Designer") -> Dict[str, Dict[str, Any]]:
    """The control properties the canvas draws from the bindings of the component being designed (none for a
    form)."""
    if not is_component(d):
        return {}
    props, _errors = bound_props(d.doc, expressions=d.trust.trusted())
    return props


# -- the inspector: Try values ------------------------------------------------------------


def try_section(d: "Designer", t: Theme, type_context: Callable[..., Any]) -> Any:
    """The Try values section of the inspector: each public property with an editor whose value redraws the
    canvas (and the Live component) without touching the code."""
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    members = [m for m in doc.all_members if m.public]
    rows: List[Any] = []
    ctx = type_context(d, t)
    for m in members:
        kind = _type_editor.parse_type(m.type)
        tried = is_tried(doc, m.name)

        def set_source(source: str, name: str = m.name) -> None:
            set_try(doc, name, source)

        editor, items = _type_editor.build(kind, tried_source(doc, m), set_source, ctx, f"try:{m.name}")
        name = _core.row([w for w in [
            _type_editor.type_badge(kind, t),
            _core.container(_core.text(m.name, size=13, font="mono", color=t.text, wrap=False), width="fill",
                            clip=True),
            ui.icon_button("rotate-ccw", lambda n=m.name: set_try(doc, n, None), size="xs",
                           tooltip=tr("Back to the default"), theme=t) if tried else None,
        ] if w is not None], spacing=4, align="center")
        head = _core.row([_core.container(name, width=116, clip=True), _core.container(editor, width="fill")],
                         spacing=8, align="center", width="fill")
        rows.append(head)
        if items:
            rows.append(_type_editor.rows_view(items, t, 116, gap=4))
    if not members:
        rows.append(ui.label(tr("Add a public property to try its values here."), size="xs", color="text_muted",
                             theme=t))
    else:
        rows.append(ui.label(tr("Only the canvas changes: the defaults stay in the code."), size="xs",
                             color="text_muted", theme=t))
        if state(doc).tries:
            rows.append(_core.row([ui.button(tr("Reset to defaults"), lambda: reset_tries(doc), icon="rotate-ccw",
                                             variant="ghost", size="sm", theme=t)]))
    _props, errors = bound_props(doc, expressions=d.trust.trusted())
    for where, error in errors.items():
        rows.append(ui.callout(tr("Binding error"), f"{where}: {error}", tint="warning", theme=t))
    return ui.AccordionSection("try", tr("Try values"), _core.column(rows, spacing=8, width="fill"),
                               icon="flask-conical")


# -- the canvas: Design or Live --------------------------------------------------------------


def set_live(d: "Designer", live: bool) -> Any:
    """Switches the canvas between editing the controls (Design) and running the component (Live)."""
    if not is_component(d):
        return None
    if live and not d.trust.allow(lambda: set_live(d, True)):
        return None
    st = state(d.doc)
    st.live = live
    if live:  # nothing to place or select while it runs: the inspector shows the values to try
        d.select_form()
    return None


def restart(d: "Designer") -> None:
    """Runs the live component again from ``setup`` (its state starts over)."""
    st = state(d.doc)
    st.run += 1
    st.log.clear()


def mode_switch(d: "Designer", t: Theme) -> Any:
    """The Design | Live switch at the start of a component's toolbar."""
    live = state(d.doc).live
    return ui.segmented([tr("Design"), tr("Live")], tr("Live") if live else tr("Design"),
                        lambda v: set_live(d, v == tr("Live")), size="sm", theme=t)


def _compiled(d: "Designer") -> Tuple[Optional[type], str]:
    from .scene_panel import compile_class

    doc = d.doc
    st = state(doc)
    key = (doc.code, doc.history.snapshot)
    if st.compiled[0] != key:
        try:
            st.compiled = (key, compile_class(doc), "")
        except Exception as err:  # noqa: BLE001 - shown on the canvas
            st.compiled = (key, None, f"{type(err).__name__}: {err}")
    return st.compiled[1], st.compiled[2]


def _record(doc: SceneDocument, name: str, event: Any) -> None:
    log = state(doc).log
    log.append(f"{time.strftime('%H:%M:%S')}  {name}  {getattr(event, 'value', event)!r}")
    del log[:-30]


def live_surface(d: "Designer", t: Theme) -> Any:
    """The canvas in Live mode: the component as its code renders it, at its design size, with the tried
    values as props, and the custom events it raises under it."""
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    st = state(doc)
    scene = doc.scene
    cls, error = _compiled(d)
    if cls is None:
        body = ui.callout(tr("The component code has an error"), error, tint="error", theme=t)
    else:
        handlers = {f"on_{name}": (lambda e, name=name: _record(doc, name, e)) for name in cls.__events__}
        props = {k: v for k, v in values(doc, public_only=True).items() if k in cls.__props__}
        try:
            body = cls(key=("pyzed-live", id(doc), st.run), **props, **handlers)
        except Exception as err:  # noqa: BLE001 - e.g. a prop of the wrong type
            body = ui.callout(tr("Cannot render {name}", name=scene.name), f"{type(err).__name__}: {err}",
                              tint="error", theme=t)
    from .runtime import theme_for

    ft = theme_for(scene, d.preview_theme)
    stage = _core.container(body, width=scene.width, height=scene.height, clip=True, bg=ft.background,
                            color=ft.text)
    chrome = _core.container(_core.row([
        _icon("play", size=12, color=t.success),
        ui.label(f"{tr('Live')} · {scene.name}", size="sm", color="success", theme=t, wrap=False),
        _core.space(width="fill"),
        ui.icon_button("rotate-ccw", lambda: restart(d), size="xs", tooltip=tr("Restart from setup()"), theme=t),
    ], spacing=6, align="center"), width=scene.width, height=30, padding=(0, 6, 0, 10), align_y="center",
        bg=alpha(t.success, 0.12))
    frame = _core.container(_core.container(_core.column([chrome, stage]), border_color=t.success, border_width=1,
                                            radius=t.radius, clip=True),
                            padding=3, radius=t.radius + 3, border_color=alpha(t.shadow, 0.5), border_width=3)
    lines = [ui.label(line, size="xs", mono=True, theme=t) for line in reversed(st.log)] or [
        ui.label(tr("Custom events raised by the component show up here."), size="xs", color="text_muted", theme=t)]
    log = _core.container(_core.column([
        _core.row([_icon("zap", size=12, color=t.icon_muted),
                   ui.label(tr("Events"), size="xs", color="text_muted", theme=t)], spacing=6, align="center"),
        *lines[:8],
    ], spacing=3), width=scene.width + 8, padding=(8, 10), bg=alpha(t.panel, 0.6), radius=t.radius,
        border_color=t.border_variant, border_width=1)
    hint = ui.label(tr("Change the values in the inspector: the component runs with them."), size="xs",
                    color="text_muted", theme=t)
    content = _core.column([frame, log, hint], spacing=10)
    return _core.scrollable(_core.container(content, padding=48), direction="both", width="fill", height="fill")


# -- the Members panel -----------------------------------------------------------------------


@dataclass
class ClassEntry:
    """A class of the component's module (other than the component), or one nested in it."""

    name: str
    line: int
    nested: bool = False
    bases: str = ""


def module_classes(doc: SceneDocument) -> List[ClassEntry]:
    """The classes the component's module defines besides the component (helpers, data classes, enums...), and
    the ones nested in the component class."""
    try:
        tree = ast.parse(doc.code)
    except SyntaxError:
        return []
    out: List[ClassEntry] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name == doc.scene.name:
            out += [ClassEntry(n.name, n.lineno, True, _bases(n)) for n in node.body if isinstance(n, ast.ClassDef)]
        else:
            out.append(ClassEntry(node.name, node.lineno, False, _bases(node)))
    return out


def _bases(node: ast.ClassDef) -> str:
    return ", ".join(ast.unparse(b) for b in node.bases)


def _section(title: str, icon: str, count: int, t: Theme, add: Optional[Callable[[], Any]] = None,
             tip: str = "") -> Any:
    return _core.container(_core.row([w for w in [
        _icon(icon, size=12, color=t.icon_muted),
        ui.label(f"{title} ({count})", size="xs", weight="medium", color="text_muted", theme=t),
        _core.space(width="fill"),
        ui.icon_button("plus", add, size="xs", tooltip=tip, theme=t) if add is not None else None,
    ] if w is not None], spacing=6, align="center"), padding=(8, spacing.GUTTER, 2, spacing.GUTTER + 4), width="fill")


def _row(label: str, icon: str, action: Callable[[], Any], t: Theme, *, color: Optional[str] = None,
         detail: str = "", end: Any = None, icon_color: Optional[str] = None) -> Any:
    return ui.list_item(label, action, icon=icon, icon_color=icon_color, color=color, height=MEMBER_ROW, indent=10,
                        end=_core.container(_core.row([w for w in [
                            ui.label(detail, size="xs", color="text_muted", mono=True, wrap=False, theme=t)
                            if detail else None, end] if w is not None], spacing=4, align="center"),
                            padding=(0, 10, 0, 0)),
                        theme=t)


def members_view(d: "Designer", t: Theme) -> Any:
    """The Members panel of a component: its variables, methods, events and classes, as the code declares them.

    A variable opens its card in the inspector; a method, its code; an event, the Events tab; a class, the
    module at its line."""
    from . import scene_panel

    doc = d.doc
    assert isinstance(doc, SceneDocument)
    info = doc.info
    own = {m.name for m in doc.members}
    members = doc.all_members
    tried = values(doc)
    rows: List[Any] = [_section(tr("Variables"), "variable", len(members), t,
                                add=lambda: scene_panel._guard(d, lambda: open_member(d, doc.add_member("value").name)),
                                tip=tr("Add a property"))]
    for m in members:
        kind = _type_editor.parse_type(m.type)
        shown = repr(tried.get(m.name))
        rows.append(_row(m.name, _type_editor.type_icon(kind), lambda n=m.name: open_member(d, n), t,
                         icon_color=_type_editor.type_color(kind, t),
                         color=None if m.name in own else "text_muted",
                         detail=shown if len(shown) <= 14 else shown[:13] + "…",
                         end=_icon("lock", size=11, color=t.icon_muted) if not m.public else None))
    if not members:
        rows.append(_hint(tr("Public properties are what a parent passes; private ones are its state."), t))
    handlers = {h for c in doc.scene.controls for h in c.events.values()} | set(doc.scene.events.values())
    methods = info.methods
    rows.append(_section(tr("Methods"), "square-function", len(methods), t,
                         add=lambda: scene_panel.add_method(d), tip=tr("Add a method")))
    for name in methods:
        role = tr("lifecycle") if name in scene_code.LIFECYCLE else tr("handler") if name in handlers else ""
        rows.append(_row(f"{name}()", "square-function", lambda n=name: scene_panel.open_method(d, n), t,
                         detail=role, icon_color=t.accent if name in scene_code.LIFECYCLE else None))
    events = doc.custom_events
    rows.append(_section(tr("Events"), "zap", len(events), t,
                         add=lambda: scene_panel._guard(d, lambda: (doc.add_event("changed"), show_events(d))),
                         tip=tr("Add an event")))
    for name, description in events.items():
        rows.append(ui.tooltip(_row(name, "zap", lambda: show_events(d), t, icon_color=t.warning),
                               description or tr("Raised with self.emit(\"{name}\", value)", name=name),
                               position="right", theme=t))
    classes = module_classes(doc)
    rows.append(_section(tr("Classes"), "box", len(classes) + 1, t))
    rows.append(_row(doc.scene.name, "component", d.edit_whole_file, t, icon_color=t.accent,
                     detail=", ".join(b for b in _component_bases(doc)) or "SceneComponent"))
    for entry in classes:
        rows.append(_row(entry.name, "box", lambda line=entry.line: open_line(d, line), t,
                         detail=(f"↳ {doc.scene.name}" if entry.nested else entry.bases)))
    return _core.scrollable(_core.column(rows, width="fill", padding=(0, 0, spacing.BLOCK, 0)), width="fill",
                            height="fill")


def _component_bases(doc: SceneDocument) -> List[str]:
    try:
        tree = ast.parse(doc.code)
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == doc.scene.name:
            return [ast.unparse(b) for b in node.bases]
    return []


def _hint(text: str, t: Theme) -> Any:
    return _core.container(ui.label(text, size="xs", color="text_muted", theme=t),
                           padding=(2, spacing.GUTTER, 2, spacing.GUTTER + 14), width="fill")


def open_member(d: "Designer", name: str) -> None:
    """Shows property ``name`` in the inspector: the component selected, its card open."""
    from . import scene_panel

    if name is None:
        return
    d.select_form()
    scene_panel._open_member(d, name)
    scene_panel._open(d).add("properties")
    d.layout.show("properties")


def show_events(d: "Designer") -> None:
    """Shows the component's own events in the Events tab."""
    d.select_form()
    d.layout.show("events")


def open_line(d: "Designer", line: int) -> Any:
    """Opens the whole class module in the code editor with the cursor on ``line``."""
    d.edit_whole_file()
    d.assist.cursor = (line, 1)
    return _core.Command.set_editor_cursor(d.editor_id, line, 1)


# -- the script link (forms and components) -------------------------------------------------


def script_of_type(type_: str) -> Optional[Path]:
    """The script of a control of ``type_`` when it is a designed component (a ``.pzcomp`` with its class), else
    ``None``: library controls have no script, and a component made only in code has nothing to link."""
    from ..component import find
    from .scene_runtime import SceneComponent

    cls = find(type_)
    if not (isinstance(cls, type) and issubclass(cls, SceneComponent)) or cls.scene_file is None:
        return None
    import sys

    module = sys.modules.get(cls.__module__)
    file = getattr(module, "__file__", None)
    if file:
        return Path(file)
    from .scene import code_path

    return code_path(cls.scene_file)


def script_button(d: "Designer", t: Theme, control: Optional[str] = None) -> Any:
    """The script icon of an outline row: on the root row, the ``.py`` the form or component is tied to (muted
    while it has no file yet); on a placed designed component, its class. ``None`` for anything else."""
    doc = d.doc
    if control is None:
        path = doc.code_path
        has_code = bool(getattr(doc, "code", "").strip()) or (path is not None and path.exists())
        name = path.name if path is not None else tr("not saved yet")
        tip = tr("Script: {name}", name=name) if has_code else tr("No script yet: click to write one")
        return ui.icon_button(SCRIPT_ICON, d.edit_whole_file, size="xs", tooltip=tip, theme=t,
                              selected=bool(d.editing and d.editing[0] == "*"),
                              color="accent" if has_code else None)
    c = doc.form.get(control)
    path = script_of_type(c.type) if c is not None else None
    if path is None:
        return None
    return ui.icon_button(SCRIPT_ICON, lambda: d.open_path(path), size="xs",
                          tooltip=tr("Script: {name}", name=path.name), color="accent", theme=t)
