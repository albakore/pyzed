"""The designer's component mode: the Component panel, bindings and the live preview.

When the open document is a ``SceneDocument`` (a ``.pzcomp``), the property grid shows,
with nothing selected, the component itself: its class, how it shows in the toolbox,
its properties (public or private, with type and default), its custom events and its
methods. With a control selected, a Bindings section links the control's properties
to the component's. F5 opens the component in a window with an event log.

Everything here edits the document through ``SceneDocument``, which writes the class
code, so the designer and the code stay the same thing.
"""

from __future__ import annotations

import ast
import time
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List

from .. import _core, ui
from ..app import Window
from ..icons import icon as _icon
from ..theme import Theme
from . import components as _components
from . import scene_code
from .panels import prop_row, section
from .scene import SceneDocument
from .scene_runtime import SceneComponent, scenes

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

TYPE_ICONS = {"str": "type", "int": "hash", "float": "percent", "bool": "toggle-right", "list": "list",
              "dict": "braces", "Any": "asterisk"}
NONE = "—"
EXPRESSION = "Expression…"


def is_scene(d: "Designer") -> bool:
    return isinstance(d.doc, SceneDocument)


def _guard(d: "Designer", action: Callable[[], Any]) -> Any:
    """Runs a code-changing action, reporting instead of failing when the class does not parse."""
    try:
        return action()
    except SyntaxError as err:
        d.notify("Fix the code first", f"The component class does not parse: {err.msg}", kind="error", seconds=4)
    except KeyError:
        return None
    return None


# -- the Component panel -------------------------------------------------------------


def properties(d: "Designer", t: Theme, rows: List[Any]) -> List[Any]:
    """The property-grid rows in component mode (``rows`` are the ones of a normal form)."""
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    if not doc.selection:
        return component_rows(d, t)
    if len(doc.selection) == 1 and doc.primary is not None:
        return rows + binding_rows(d, t)
    return rows


def component_rows(d: "Designer", t: Theme) -> List[Any]:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    scene = doc.scene

    def scene_setter(key: str, cast: Callable[[Any], Any] = lambda v: v) -> Callable[[Any], None]:
        return lambda v: doc.set_scene(key, cast(v))

    rows: List[Any] = [
        _core.container(_core.row([
            _icon(scene.icon or "component", size=16, color=t.accent),
            ui.label(scene.name, weight="semibold", theme=t),
            _core.space(width="fill"),
            ui.badge("Component", tint="accent", theme=t),
        ], spacing=10, align="center"), padding=(10, 12)),
    ]
    if not doc.code_ok:
        rows.append(_core.container(ui.callout("The class does not parse",
                                               "Showing its last good version; fix the code to edit it here.",
                                               tint="warning", theme=t), padding=(0, 12, 8, 12)))
    rows += [
        section("Class", t),
        prop_row("Name", ui.input(scene.name, lambda v: _guard(d, lambda: doc.set_class_name(v)), size="sm",
                                  mono=True, theme=t), t, tip="The Python class name (CamelCase)."),
        prop_row("Description", ui.input(scene.description, lambda v: _guard(d, lambda: doc.set_description(v)),
                                         placeholder="What it is for", size="sm", theme=t), t,
                 tip="The docstring of the class; the toolbox shows it as a tooltip."),
        section("Toolbox", t),
        prop_row("Label", ui.input(scene.label, scene_setter("label"), placeholder=_spaced(scene.name), size="sm",
                                   theme=t), t),
        prop_row("Icon", _core.row([_icon(scene.icon or "component", size=14),
                                    ui.input(scene.icon, scene_setter("icon"), placeholder="lucide name", size="sm",
                                             mono=True, theme=t)], spacing=6, align="center"), t),
        prop_row("Category", ui.input(scene.category, scene_setter("category"), size="sm", theme=t), t),
        section("Layout", t),
        prop_row("Width", ui.number_field(scene.width, lambda v: d.set_form("width", float(v)), min=16, step=8,
                                          width=150, theme=t), t),
        prop_row("Height", ui.number_field(scene.height, lambda v: d.set_form("height", float(v)), min=16, step=8,
                                           width=150, theme=t), t),
        prop_row("Background", ui.input(scene.background or "", lambda v: d.set_form("background", v or None),
                                        placeholder="transparent", size="sm", mono=True, theme=t), t),
        prop_row("Grid size", ui.number_field(scene.grid, lambda v: d.set_form("grid", int(v)), min=2, max=64,
                                              width=150, theme=t), t),
    ]
    rows += member_rows(d, t)
    rows += event_rows(d, t)
    rows += method_rows(d, t)
    return rows


def _spaced(name: str) -> str:
    out = ""
    for i, ch in enumerate(name):
        out += (" " + ch) if ch.isupper() and i else ch
    return out


def member_rows(d: "Designer", t: Theme) -> List[Any]:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    add = _core.row([
        ui.icon_button("plus", lambda: _guard(d, lambda: doc.add_member("value")), size="xs",
                       tooltip="Add a public property (a prop)", theme=t),
        ui.icon_button("lock", lambda: _guard(d, lambda: doc.add_member("state", "int", public=False)), size="xs",
                       tooltip="Add a private property (state)", theme=t),
    ], spacing=0)
    rows: List[Any] = [section("Properties", t, end=add)]
    if not doc.members:
        rows.append(_hint("Public properties are props the parent passes (Rating(value=3)); private ones are "
                          "state kept between renders. Both are attributes: self.value.", t))
    for member in doc.members:
        rows.append(_member_row(d, member, t))
    return rows


def _member_row(d: "Designer", m: scene_code.Member, t: Theme) -> Any:
    doc = d.doc
    assert isinstance(doc, SceneDocument)

    def update(**changes: Any) -> None:
        _guard(d, lambda: doc.update_member(m.name, **changes))

    types_ = list(scene_code.TYPES)
    if m.type not in types_:
        types_.append(m.type)
    head = _core.row([
        ui.tooltip(ui.icon_button("eye" if m.public else "lock", lambda: update(public=not m.public), size="xs",
                                  selected=not m.public, theme=t),
                   "Public (a prop): click to make it private state" if m.public else
                   "Private (state): click to make it a public prop", theme=t),
        _core.container(ui.input(m.name, lambda v: update(name=v), size="sm", mono=True, theme=t), width="fill"),
        _core.container(ui.select(types_, m.type, lambda v: update(type=v), size="sm", width="fill", theme=t),
                        width=84),
        ui.icon_button("chevron-up", lambda: _guard(d, lambda: doc.move_member(m.name, -1)), size="xs",
                       tooltip="Move up", theme=t),
        ui.icon_button("trash-2", lambda: _guard(d, lambda: doc.remove_member(m.name)), size="xs",
                       tooltip="Remove", theme=t),
    ], spacing=4, align="center")
    return _core.container(_core.column([
        head,
        _core.row([_core.container(ui.label("default", size="xs", color="text_muted", theme=t), width=52),
                   _core.container(_default_editor(m, lambda v: update(default=v), t), width="fill")],
                  spacing=6, align="center"),
    ], spacing=4), padding=(4, 12, 6, 12), width="fill")


def _default_editor(m: scene_code.Member, on_change: Callable[[Any], None], t: Theme) -> Any:
    if m.source is not None:  # not a literal: edit it as Python
        return ui.input(m.source, lambda v: _literal_change(v, on_change), size="sm", mono=True, theme=t)
    if m.type == "bool":
        return _core.container(ui.switch(bool(m.default), on_change, theme=t), width="fill", align_x="end")
    if m.type in ("int", "float"):
        value = m.default if isinstance(m.default, (int, float)) else 0
        return ui.number_field(float(value), lambda v: on_change(int(v) if m.type == "int" else float(v)),
                               step=1 if m.type == "int" else 0.1, width=150, theme=t)
    if m.type == "str":
        return ui.input("" if m.default is None else str(m.default), on_change, size="sm", theme=t)
    return ui.input(repr(m.default), lambda v: _literal_change(v, on_change), size="sm", mono=True,
                    placeholder="a Python literal", theme=t)


def _literal_change(text: str, on_change: Callable[[Any], None]) -> None:
    try:
        on_change(ast.literal_eval(text))
    except (ValueError, SyntaxError):
        pass  # keep the last valid value until the text parses


def event_rows(d: "Designer", t: Theme) -> List[Any]:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    add = ui.icon_button("plus", lambda: _guard(d, lambda: doc.add_event("changed")), size="xs",
                         tooltip="Add a custom event", theme=t)
    rows: List[Any] = [section("Custom events", t, end=add)]
    events = doc.custom_events
    if not events:
        rows.append(_hint("Raise them from a method with self.emit(\"name\", value); the parent handles them "
                          "with on_name=..., or in the Events tab of a form.", t))
    for name, description in events.items():
        rows.append(_core.container(_core.column([
            _core.row([
                _icon("zap", size=13, color=t.icon_muted),
                _core.container(ui.input(name, lambda v, n=name: _guard(d, lambda: doc.update_event(n, new_name=v)),
                                         size="sm", mono=True, theme=t), width="fill"),
                ui.icon_button("trash-2", lambda n=name: _guard(d, lambda: doc.remove_event(n)), size="xs",
                               tooltip="Remove", theme=t),
            ], spacing=6, align="center"),
            ui.input(description, lambda v, n=name: _guard(d, lambda: doc.update_event(n, description=v)),
                     placeholder="Description", size="sm", theme=t),
        ], spacing=4), padding=(4, 12, 6, 12), width="fill"))
    return rows


def method_rows(d: "Designer", t: Theme) -> List[Any]:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    methods = doc.info.methods
    rows: List[Any] = [section("Methods", t, end=ui.icon_button("code", d.edit_whole_file, size="xs",
                                                                tooltip="Edit the class", theme=t))]
    lifecycle = [m for m in scene_code.LIFECYCLE if m not in methods]
    for name in methods:
        rows.append(ui.list_item(f"{name}()", lambda n=name: open_method(d, n), icon="square-function",
                                 selected=bool(d.editing and d.editing[0] == name), height=24, inset=True,
                                 theme=t))
    for name in lifecycle:
        rows.append(ui.list_item(f"{name}()", lambda n=name: open_method(d, n), icon="plus",
                                 color="text_muted", height=24, inset=True, theme=t))
    return rows


def _hint(text: str, t: Theme) -> Any:
    return _core.container(ui.label(text, size="xs", color="text_muted", theme=t), padding=(2, 12, 6, 12))


def open_method(d: "Designer", name: str) -> None:
    """Opens a method of the class in the code editor (adding a stub for a lifecycle method)."""
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    if name in scene_code.LIFECYCLE:
        event = next((e for e, m in {"setup": "setup", "mount": "on_mount", "unmount": "on_unmount"}.items()
                      if m == name), None)
        if event is not None:
            _guard(d, lambda: d.edit_event(None, event))
            return
    if not d._flush_code():
        return
    d.editing = (name, doc.handler_source(name))
    d.last_handler = name
    d.code_revision += 1
    d.code_error = None
    d.focus = "code"
    d.assist.opened()


# -- bindings ------------------------------------------------------------------------


def binding_rows(d: "Designer", t: Theme) -> List[Any]:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    control = doc.primary
    assert control is not None
    spec = _components.get(control.type)
    bound = doc.scene.bound(control.name)
    members = [m.name for m in doc.members]
    expressions: Dict[Any, bool] = d.__dict__.setdefault("_scene_expressions", {})
    rows: List[Any] = [section("Bindings", t)]
    if not spec.props:
        return []
    if not members:
        rows.append(_hint("Add properties to the component (select the empty canvas) to bind them here.", t))
    for prop in spec.props:
        expr = bound.get(prop.name, "")
        key = (control.name, prop.name)
        custom = bool(expr) and expr not in members
        if custom or expressions.get(key):
            editor = _core.row([
                _core.container(ui.input(expr, lambda v, p=prop.name: doc.set_binding(control.name, p, v),
                                         placeholder='f"{value} items"', size="sm", mono=True, theme=t),
                                width="fill"),
                ui.icon_button("x", lambda k=key, p=prop.name: (expressions.pop(k, None),
                                                                doc.set_binding(control.name, p, None)),
                               size="xs", tooltip="Remove the binding", theme=t),
            ], spacing=4, align="center")
        else:
            def pick(value: str, p: str = prop.name, k: Any = key) -> None:
                if value == EXPRESSION:
                    expressions[k] = True
                else:
                    doc.set_binding(control.name, p, None if value == NONE else value)

            editor = ui.select([NONE, *members, EXPRESSION], expr or NONE, pick, size="sm", width="fill", theme=t)
        rows.append(prop_row(prop.title, editor, t, tip=f"{control.name}.{prop.name} follows this component "
                                                        f"property (or Python expression) on every render."))
    return rows


# -- running -------------------------------------------------------------------------


class ComponentPreview(Window):
    """A window with one instance of the component and a log of the custom events it raises."""

    def __init__(self, cls: type, theme: Any = None) -> None:
        self.cls = cls
        self.log: List[str] = []
        w, h = getattr(cls, "size", (240, 120))
        self.size = (max(w + 96, 420), h + 220)
        self.title = f"{cls.__name__} · preview"
        if theme is not None:
            self.theme = theme

    def _record(self, name: str, event: Any) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log.append(f"{stamp}  {name}  {event.value!r}")
        del self.log[:-50]

    def view(self):
        t = self.resolved_theme()
        handlers = {f"on_{name}": (lambda e, name=name: self._record(name, e))
                    for name in self.cls.__events__}
        try:
            body = self.cls(**handlers)
        except Exception as err:  # noqa: BLE001 - e.g. a required prop without default
            body = ui.callout(f"Cannot render {self.cls.__name__}", f"{type(err).__name__}: {err}", tint="error",
                              theme=t)
        stage = _core.container(body, width="fill", height="fill", center=True, bg=t.background)
        lines = [ui.label(line, size="sm", mono=True, theme=t) for line in reversed(self.log)] or [
            ui.label("Custom events raised by the component show up here.", size="sm", color="text_muted",
                     theme=t)]
        log = _core.column([
            ui.panel_header("Events", icon="zap", theme=t),
            _core.container(_core.scrollable(_core.column(lines, spacing=2, width="fill"), height="fill"),
                            padding=(6, 12), height="fill", width="fill"),
        ], width="fill", height="fill")
        return _core.column([stage, _core.container(log, height=150, width="fill", bg=t.surface)],
                            width="fill", height="fill")


def compile_class(doc: SceneDocument) -> type:
    """Executes the document's code (unsaved edits included) and returns its component class."""
    file = doc.code_path or Path.cwd() / f"{doc.scene.name.lower()}.py"
    module = types.ModuleType(f"pyzed_component_{doc.scene.name}")
    module.__file__ = str(file)
    exec(compile(doc.code, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the user's own code
    for value in vars(module).values():
        if isinstance(value, type) and issubclass(value, SceneComponent) and value is not SceneComponent \
                and value.__module__ == module.__name__:
            if value.scene_file is not None:
                scenes.overrides[value.scene_file] = doc.scene.copy()  # preview the unsaved layout
            value.size = (doc.scene.width, doc.scene.height)
            return value
    raise TypeError(f"the code has no SceneComponent subclass (class {doc.scene.name}(SceneComponent, scene=...))")


def run(d: "Designer") -> Any:
    """F5 in component mode: opens the component in a preview window."""
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    try:
        cls = compile_class(doc)
    except Exception as err:  # noqa: BLE001 - show any error to the user
        d.notify("The component code has an error", f"{type(err).__name__}: {err}", kind="error", seconds=6)
        return None
    commands = []
    if d.preview is not None and d.preview.is_open:
        commands.append(d.preview.close())
    d.preview = ComponentPreview(cls, d.theme_obj)  # type: ignore[assignment]
    d.preview.app = d  # type: ignore[union-attr]
    commands.append(d.preview.open())  # type: ignore[union-attr]
    return commands


def run_file(path: Any) -> None:
    """``pyzed run rating.pzcomp``: opens a designed component on its own."""
    from ..app import App
    from ..app import run as run_app
    from ..project import activate_for
    from .scene import discover, errors, load_component

    activate_for(path)
    discover(Path(path).resolve().parent)
    cls = load_component(path)
    if cls is None:
        raise SystemExit(f"error: {errors.get(Path(path).resolve(), 'could not load the component')}")
    preview = ComponentPreview(cls)

    class _Preview(App):
        title = preview.title
        size = preview.size

        def view(self):
            return preview.view()

    run_app(_Preview())
