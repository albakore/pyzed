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


# -- layout helpers ------------------------------------------------------------------

LABEL = 84.0
SECTIONS = ("class", "toolbox", "layout", "inherited", "properties", "events", "methods", "bindings")


def _open(d: "Designer") -> set:
    """The open accordion sections (all of them at first), kept on the designer."""
    return d.__dict__.setdefault("_scene_open", set(SECTIONS))


def _toggle(d: "Designer") -> Callable[[str], None]:
    def flip(key: str) -> None:
        _open(d).symmetric_difference_update({key})
    return flip


def field(title: str, editor: Any, t: Theme, *, tip: str = "", inset: float = 0) -> Any:
    """A label and its editor; every row of the panel shares the label width, so editors line up.

    ``inset`` is how far the row is pushed right (inside a card), so its editor still lines up.
    """
    text = ui.label(title, color="text_muted", wrap=False, theme=t)
    if tip:
        text = ui.tooltip(text, tip, theme=t)
    return _core.row([_core.container(text, width=LABEL - inset, clip=True), _core.container(editor, width="fill")],
                     spacing=8, align="center", width="fill")


def _stack(rows: List[Any]) -> Any:
    return _core.column([r for r in rows if r is not None], spacing=8, width="fill")


def _number(value: float, on_change: Callable[[Any], Any], t: Theme, **kwargs: Any) -> Any:
    return ui.number_field(value, on_change, width="fill", theme=t, **kwargs)


def _accordion(d: "Designer", sections: List[Any], t: Theme) -> Any:
    return ui.accordion(sections, open=_open(d), on_toggle=_toggle(d), theme=t)


# -- the Component panel -------------------------------------------------------------


def properties(d: "Designer", t: Theme, rows: List[Any]) -> List[Any]:
    """The property-grid rows in component mode (``rows`` are the ones of a normal form)."""
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    if not doc.selection:
        return component_rows(d, t)
    if len(doc.selection) == 1 and doc.primary is not None:
        bindings = binding_section(d, t)
        note = None
        if doc.inherited(doc.primary.name):
            base = doc.base.name if doc.base is not None else "the base"
            note = _core.container(ui.callout(f"Inherited from {base}",
                                              "Changes here apply to this component only. It cannot be renamed "
                                              "or deleted: the base component owns it.", tint="info", theme=t),
                                   padding=(0, 12, 12, 12))
        return [note, *rows] + ([_core.container(_accordion(d, [bindings], t), padding=(12, 0, 0, 0))]
                                if bindings else [])
    return rows


def component_rows(d: "Designer", t: Theme) -> List[Any]:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    scene = doc.scene

    def scene_setter(key: str, cast: Callable[[Any], Any] = lambda v: v) -> Callable[[Any], None]:
        return lambda v: doc.set_scene(key, cast(v))

    header = _core.container(_core.row([
        _icon(scene.icon or "component", size=16, color=t.accent),
        ui.label(scene.name, weight="semibold", theme=t),
        _core.space(width="fill"),
        ui.badge("Component", tint="accent", theme=t),
    ], spacing=10, align="center"), padding=(12, 12), width="fill")
    warning = None
    if not doc.code_ok:
        warning = _core.container(ui.callout("The class does not parse",
                                             "Showing its last good version; fix the code to edit it here.",
                                             tint="warning", theme=t), padding=(0, 12, 12, 12))
    sections = [
        ui.AccordionSection("class", "Class", _stack([
            field("Name", ui.input(scene.name, lambda v: _guard(d, lambda: doc.set_class_name(v)),
                                   mono=True, theme=t), t, tip="The Python class name (CamelCase)."),
            field("Description", ui.input(scene.description, lambda v: _guard(d, lambda: doc.set_description(v)),
                                          placeholder="What it is for", theme=t), t,
                  tip="The docstring of the class; the toolbox shows it as a tooltip."),
            field("Inherits", _base_picker(d, t), t,
                  tip="A designed component to extend: this one gets its controls, properties, events and methods."),
        ]), icon="braces"),
        ui.AccordionSection("toolbox", "Toolbox", _stack([
            field("Label", ui.input(scene.label, scene_setter("label"), placeholder=_spaced(scene.name),
                                    theme=t), t),
            field("Icon", ui.input(scene.icon, scene_setter("icon"), placeholder="lucide name", mono=True,
                                   icon=scene.icon or "component", theme=t), t),
            field("Category", ui.input(scene.category, scene_setter("category"), theme=t), t),
        ]), icon="component"),
        ui.AccordionSection("layout", "Layout", _stack([
            field("Width", _number(scene.width, lambda v: d.set_form("width", float(v)), t, min=16, step=8), t),
            field("Height", _number(scene.height, lambda v: d.set_form("height", float(v)), t, min=16, step=8), t),
            field("Background", ui.input(scene.background or "", lambda v: d.set_form("background", v or None),
                                         placeholder="transparent", mono=True, theme=t), t),
            field("Grid size", _number(scene.grid, lambda v: d.set_form("grid", int(v)), t, min=2, max=64), t),
        ]), icon="ruler"),
        inherited_section(d, t),
        member_section(d, t),
        event_section(d, t),
        method_section(d, t),
    ]
    return [header, warning, _accordion(d, [s for s in sections if s is not None], t)]


def _base_picker(d: "Designer", t: Theme) -> Any:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    mine = doc.path.resolve() if doc.path else None
    options = {NONE: None}
    for path in d.base_components():
        if path.resolve() != mine:
            options[_relative_label(path)] = path
    current = doc.base_file
    if current is not None and current not in options.values():
        options[_relative_label(current)] = current
    chosen = next((label for label, path in options.items() if path == current), NONE)

    def pick(label: str) -> None:
        try:
            _guard(d, lambda: doc.set_base(options.get(label)))
        except (ValueError, OSError) as err:
            d.notify("Cannot inherit from it", str(err), kind="error", seconds=4)

    return ui.select(list(options), chosen, pick, width="fill", theme=t)


def _relative_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return path.name


def inherited_section(d: "Designer", t: Theme) -> Any:
    """What the component gets from the components it extends (read only: edit them in their own file)."""
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    chain = doc.base_info()
    if not chain:
        return None
    rows: List[Any] = []
    for file, info in chain:
        rows.append(_core.row([_icon("component", size=14, color=t.accent),
                               ui.label(info.name, weight="semibold", theme=t),
                               ui.label(file, size="xs", color="text_muted", mono=True, theme=t)],
                              spacing=6, align="center"))
        details = [
            ("Properties", ", ".join(m.name for m in info.members)),
            ("Events", ", ".join(info.events)),
            ("Methods", ", ".join(f"{m}()" for m in info.methods)),
        ]
        rows.extend(field(label, ui.label(text or NONE, size="sm", mono=True, theme=t), t)
                    for label, text in details)
    rows.append(_hint("Override a method by defining it again in this class; super() calls the base's.", t))
    base = doc.base
    controls = len(base.controls) if base is not None else 0
    return ui.AccordionSection("inherited", f"Inherited ({controls} controls)", _stack(rows), icon="git-fork")


def _spaced(name: str) -> str:
    out = ""
    for i, ch in enumerate(name):
        out += (" " + ch) if ch.isupper() and i else ch
    return out


def _add_button(label: str, icon: str, action: Callable[[], Any], t: Theme) -> Any:
    return ui.button(label, action, icon=icon, variant="ghost", theme=t)


def member_section(d: "Designer", t: Theme) -> Any:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    rows: List[Any] = [_card_of_member(d, m, t) for m in doc.members]
    if not rows:
        rows.append(_hint("Public properties are props the parent passes (Rating(value=3)); private ones are "
                          "state kept between renders. Both are attributes: self.value.", t))
    rows.append(_core.row([
        _add_button("Public", "plus", lambda: _guard(d, lambda: doc.add_member("value")), t),
        _add_button("Private", "lock", lambda: _guard(d, lambda: doc.add_member("state", "int", public=False)), t),
    ], spacing=4))
    return ui.AccordionSection("properties", f"Properties ({len(doc.members)})", _stack(rows), icon="list")


CARD_PADDING = 8.0
CARD_INSET = CARD_PADDING + 1  # padding plus border: rows inside a card use it to line up with the panel


def _card(rows: List[Any], t: Theme) -> Any:
    return _core.container(_core.column(rows, spacing=6, width="fill"), padding=CARD_PADDING, width="fill", bg=t.editor,
                           border_color=t.border_variant, border_width=1, radius=t.radius)


def _card_of_member(d: "Designer", m: scene_code.Member, t: Theme) -> Any:
    doc = d.doc
    assert isinstance(doc, SceneDocument)

    def update(**changes: Any) -> None:
        _guard(d, lambda: doc.update_member(m.name, **changes))

    types_ = list(scene_code.TYPES)
    if m.type not in types_:
        types_.append(m.type)
    head = _core.row([
        _core.container(ui.input(m.name, lambda v: update(name=v), mono=True,
                                 icon=TYPE_ICONS.get(m.type, "asterisk"), theme=t), width="fill"),
        ui.icon_button("chevron-up", lambda: _guard(d, lambda: doc.move_member(m.name, -1)), size="xs",
                       tooltip="Move up", theme=t),
        ui.icon_button("trash-2", lambda: _guard(d, lambda: doc.remove_member(m.name)), size="xs",
                       tooltip="Remove", theme=t),
    ], spacing=4, align="center")
    access = ui.select(["public", "private"], "public" if m.public else "private",
                       lambda v: update(public=v == "public"), width="fill", theme=t)
    return _card([
        head,
        field("Access", access, t, tip="Public: a prop the parent passes. Private: state declared with pz.state.", inset=CARD_INSET),
        field("Type", ui.select(types_, m.type, lambda v: update(type=v), width="fill", theme=t), t, inset=CARD_INSET),
        field("Default", _default_editor(m, lambda v: update(default=v), t), t, inset=CARD_INSET),
    ], t)


def _default_editor(m: scene_code.Member, on_change: Callable[[Any], None], t: Theme) -> Any:
    if m.source is not None:  # not a literal: edit it as Python
        return ui.input(m.source, lambda v: _literal_change(v, on_change), mono=True, theme=t)
    if m.type == "bool":
        return _core.container(ui.switch(bool(m.default), on_change, theme=t), width="fill", align_x="end")
    if m.type in ("int", "float"):
        value = m.default if isinstance(m.default, (int, float)) else 0
        return _number(float(value), lambda v: on_change(int(v) if m.type == "int" else float(v)), t,
                       step=1 if m.type == "int" else 0.1)
    if m.type == "str":
        return ui.input("" if m.default is None else str(m.default), on_change, theme=t)
    return ui.input(repr(m.default), lambda v: _literal_change(v, on_change), mono=True,
                    placeholder="a Python literal", theme=t)


def _literal_change(text: str, on_change: Callable[[Any], None]) -> None:
    try:
        on_change(ast.literal_eval(text))
    except (ValueError, SyntaxError):
        pass  # keep the last valid value until the text parses


def event_section(d: "Designer", t: Theme) -> Any:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    events = doc.custom_events
    rows: List[Any] = []
    for name, description in events.items():
        rows.append(_card([
            _core.row([
                _core.container(ui.input(name, lambda v, n=name: _guard(d, lambda: doc.update_event(n, new_name=v)),
                                         mono=True, icon="zap", theme=t), width="fill"),
                ui.icon_button("trash-2", lambda n=name: _guard(d, lambda: doc.remove_event(n)), size="xs",
                               tooltip="Remove", theme=t),
            ], spacing=4, align="center"),
            field("Description", ui.input(description, lambda v, n=name: _guard(d, lambda: doc.update_event(
                n, description=v)), placeholder="What it means", theme=t), t, inset=CARD_INSET),
        ], t))
    if not events:
        rows.append(_hint("Raise them from a method with self.emit(\"name\", value); the parent handles them "
                          "with on_name=..., or in the Events tab of a form.", t))
    rows.append(_core.row([_add_button("Event", "plus", lambda: _guard(d, lambda: doc.add_event("changed")), t)]))
    return ui.AccordionSection("events", f"Custom events ({len(events)})", _stack(rows), icon="zap")


def method_section(d: "Designer", t: Theme) -> Any:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    methods = doc.info.methods
    rows: List[Any] = []
    for name in methods:
        rows.append(ui.list_item(f"{name}()", lambda n=name: open_method(d, n), icon="square-function",
                                 selected=bool(d.editing and d.editing[0] == name), height=26, theme=t))
    for name in (m for m in scene_code.LIFECYCLE if m not in methods):
        rows.append(ui.list_item(f"{name}()", lambda n=name: open_method(d, n), icon="plus", color="text_muted",
                                 height=26, theme=t))
    rows.append(_core.row([_add_button("Edit the class", "code", d.edit_whole_file, t)]))
    return ui.AccordionSection("methods", f"Methods ({len(methods)})",
                               _core.column(rows, spacing=2, width="fill"), icon="square-function")


def _hint(text: str, t: Theme) -> Any:
    return ui.label(text, size="xs", color="text_muted", theme=t)


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


def binding_section(d: "Designer", t: Theme) -> Any:
    doc = d.doc
    assert isinstance(doc, SceneDocument)
    control = doc.primary
    assert control is not None
    spec = _components.get(control.type)
    if not spec.props:
        return None
    bound = doc.scene.bound(control.name)
    members = [m.name for m in doc.all_members]
    expressions: Dict[Any, bool] = d.__dict__.setdefault("_scene_expressions", {})
    rows: List[Any] = []
    if not members:
        rows.append(_hint("Add properties to the component (select the empty canvas) to bind them here.", t))
    for prop in spec.props:
        expr = bound.get(prop.name, "")
        key = (control.name, prop.name)
        custom = bool(expr) and expr not in members
        if custom or expressions.get(key):
            editor = _core.row([
                _core.container(ui.input(expr, lambda v, p=prop.name: doc.set_binding(control.name, p, v),
                                         placeholder='f"{value} items"', mono=True, theme=t),
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

            editor = ui.select([NONE, *members, EXPRESSION], expr or NONE, pick, width="fill", theme=t)
        rows.append(field(prop.title, editor, t, tip=f"{control.name}.{prop.name} follows this component "
                                                     f"property (or Python expression) on every render."))
    return ui.AccordionSection("bindings", f"Bindings ({len(bound)})", _stack(rows), icon="link")


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
        lines = [ui.label(line, mono=True, theme=t) for line in reversed(self.log)] or [
            ui.label("Custom events raised by the component show up here.", color="text_muted",
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
                scenes.overrides[value.scene_file] = doc.own_scene().copy()  # preview the unsaved layout
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
