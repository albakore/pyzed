"""What the designer's agent can do: read and change the open form or component, its code, and files.

Every tool here runs on the designer's UI thread (``ui=True``), so it changes the document exactly
like a click would: each change is one undo step, and "Reject" in the agent panel puts the form and
its code back as they were before the agent started. Tools that write files on disk are marked
``writes=True`` and ask first (Settings → AI agents → Ask before writing files).
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..agents import Tool, file_tools, pyzed_tools, tool
from . import components as _components
from . import layout as _layout

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

SYSTEM = """\
You are the AI agent of Pyzed Design, the visual designer of Pyzed (a Python GUI library rendered by \
Iced in Rust, with components that look like the Zed editor). You work inside the designer, next to \
the user, on the form or component open in the active tab.

How the designer works:
- A form (.pzform) is a window: controls placed at x/y/width/height in logical pixels, relative to the \
form or to their container. Containers (panel, group, row, column, grid, scroll...) hold children; \
flex and grid containers lay their children out themselves, so x/y only matter in free containers.
- Each control has a type (list them with list_components(kind="designer")), props (see \
describe_component("designer:<type>")), a style and events. An event runs a handler in the form's \
Python module: def <control>_<event>(form, event), where form.<control> reaches any control and \
event.value carries the new value.
- A component (.pzcomp) is a reusable piece designed the same way, with a Python class beside it.

How to work:
- Start with get_document to see what is open. Look types and props up instead of guessing.
- Build with add_control / update_control / remove_controls / set_form; give controls meaningful \
names (email, send_button). Lay forms out neatly on the grid: consistent margins (16 px), aligned \
labels and inputs, primary action at the bottom right.
- Write logic with wire_event and set_handler (or set_code for the whole module), then check the \
module with validate_code. Keep handlers short and readable.
- To make a new form or component use new_document; it opens in a new tab.
- Be brief in your answers: say what you changed. The user can undo every step or reject all.
"""


def _doc(d: "Designer") -> Any:
    return d.doc


def _control_info(c: Any) -> Dict[str, Any]:
    info: Dict[str, Any] = {"name": c.name, "type": c.type, "rect": [c.x, c.y, c.width, c.height]}
    if c.parent:
        info["parent"] = c.parent
    if c.props:
        info["props"] = c.props
    if c.events:
        info["events"] = c.events
    if c.style:
        info["style"] = c.style
    if c.layout:
        info["layout"] = c.layout
    if not c.visible:
        info["visible"] = False
    if not c.enabled:
        info["enabled"] = False
    return info


def _types() -> List[str]:
    return sorted(c.type for c in _components.all_components())


def _check_props(type_: str, props: Dict[str, Any]) -> None:
    spec = _components.get(type_)
    unknown = [k for k in props if spec.prop(k) is None]
    if unknown:
        names = ", ".join(p.name for p in spec.props) or "none"
        raise ValueError(f"{type_} has no prop {', '.join(unknown)}; its props are: {names}")


def designer_tools(d: "Designer") -> List[Tool]:
    """The tools of the designer's agent, bound to designer ``d``."""

    @tool(ui=True, title="Reading the open document")
    def get_document() -> Any:
        """The form or component open in the active tab: its settings, every control (name, type, rect,
        parent, props, events, style), the selection and the handlers module."""
        doc = _doc(d)
        f = doc.form
        return {
            "kind": "component" if getattr(doc, "is_scene", False) else "form",
            "file": str(doc.path) if doc.path else None,
            "unsaved": doc.dirty,
            "form": {"name": f.name, "title": f.title, "width": f.width, "height": f.height, "theme": f.theme,
                     "grid": f.grid, "events": f.events, "style": f.style},
            "controls": [_control_info(c) for c in f.controls],
            "selection": list(doc.selection),
            "code": doc.code,
            "open_tabs": [x.display_name for x in d.docs],
        }

    @tool(ui=True, title="Adding a control")
    def add_control(type: str, name: str = "", parent: str = "", x: float = 16, y: float = 16,  # noqa: A002
                    width: float = 0, height: float = 0, props: Optional[Dict[str, Any]] = None,
                    style: Optional[Dict[str, Any]] = None) -> Any:
        """Places a new control on the open form (or inside the container parent) and returns it.

        type: a designer toolbox type, e.g. "label", "input", "button", "row", "panel".
        name: the control's name (a Python identifier); a free one is picked when empty.
        parent: the name of a container to put it in ("" for the form).
        x: left edge in pixels, relative to the form or the parent.
        y: top edge in pixels.
        width: 0 keeps the type's default width.
        height: 0 keeps the type's default height.
        props: the type's props, e.g. {"text": "Send", "variant": "solid"}.
        style: CSS-like style, e.g. {"background": "#1e1e2e", "radius": 6}.
        """
        doc = _doc(d)
        if type not in _types():
            raise ValueError(f"unknown type {type!r}; use one of: {', '.join(_types())}")
        if parent and doc.form.get(parent) is None:
            raise ValueError(f"there is no control named {parent!r}")
        if parent and _layout.kind(doc.form[parent]) is None:
            raise ValueError(f"{parent!r} is not a container")
        _check_props(type, props or {})
        control = doc.add(type, x, y, width or None, height or None, snap=False, parent=parent or None)
        for key, value in (props or {}).items():
            control.props[key] = value
        if style:
            control.style.update(style)
        if name and name != control.name:
            doc.rename(control.name, name)
        doc.commit()
        d._selection_changed()
        return _control_info(doc.form[doc.selection[0]] if doc.selection else control)

    @tool(ui=True, title="Changing a control")
    def update_control(name: str, props: Optional[Dict[str, Any]] = None, style: Optional[Dict[str, Any]] = None,
                       x: Optional[float] = None, y: Optional[float] = None, width: Optional[float] = None,
                       height: Optional[float] = None, new_name: str = "", parent: Optional[str] = None,
                       visible: Optional[bool] = None, enabled: Optional[bool] = None) -> Any:
        """Changes a control: some props (others are kept), style keys (null removes one), its rect, name,
        container or visibility.

        name: the control to change.
        parent: move it into this container ("" moves it to the form).
        """
        doc = _doc(d)
        control = doc.form.get(name)
        if control is None:
            raise ValueError(f"there is no control named {name!r}; the controls are {doc.form.names()}")
        _check_props(control.type, props or {})
        control.props.update(props or {})
        for key, value in (style or {}).items():
            if value is None:
                control.style.pop(key, None)
            else:
                control.style[key] = value
        for key, value in (("x", x), ("y", y), ("width", width), ("height", height)):
            if value is not None:
                setattr(control, key, float(value))
        if visible is not None:
            control.visible = visible
        if enabled is not None:
            control.enabled = enabled
        doc.commit()
        if parent is not None and (parent or None) != control.parent:
            if parent and (doc.form.get(parent) is None or _layout.kind(doc.form[parent]) is None):
                raise ValueError(f"{parent!r} is not a container")
            doc.reparent([name], parent or None)
        if new_name and new_name != name:
            name = doc.rename(name, new_name)
        d._selection_changed()
        return _control_info(doc.form[name])

    @tool(ui=True, title="Removing controls")
    def remove_controls(names: List[str]) -> Any:
        """Deletes controls (and what is inside them)."""
        doc = _doc(d)
        missing = [n for n in names if doc.form.get(n) is None]
        if missing:
            raise ValueError(f"no control named {', '.join(missing)}")
        doc.select(names)
        removed = doc.delete()
        d._selection_changed()
        return {"removed": removed}

    @tool(ui=True, title="Changing the form")
    def set_form(title: Optional[str] = None, width: Optional[float] = None, height: Optional[float] = None,
                 theme: Optional[str] = None, resizable: Optional[bool] = None,
                 style: Optional[Dict[str, Any]] = None) -> Any:
        """Changes the form's title, size, theme (a built-in theme name), resizability or global style."""
        doc = _doc(d)
        for key, value in (("title", title), ("width", width), ("height", height), ("theme", theme),
                           ("resizable", resizable)):
            if value is not None:
                doc.set_form(key, float(value) if key in ("width", "height") else value)
        if style:
            for key, value in style.items():
                doc.set_style(None, key, value)
        f = doc.form
        return {"title": f.title, "width": f.width, "height": f.height, "theme": f.theme}

    @tool(ui=True, title="Selecting controls")
    def select_controls(names: List[str]) -> Any:
        """Selects controls on the canvas so the user sees them (an empty list clears the selection)."""
        doc = _doc(d)
        doc.select([n for n in names if doc.form.get(n) is not None])
        d._selection_changed()
        return {"selection": list(doc.selection)}

    @tool(ui=True, title="Wiring an event")
    def wire_event(event: str, control: str = "") -> Any:
        """Connects an event of a control (or of the form when control is "") to a handler, creating the stub,
        and returns the handler's name and code. Set its code with set_handler.

        event: e.g. "click", "change", "submit", or a form event: "load", "close", "key", "resize".
        """
        doc = _doc(d)
        target = control or None
        if target and doc.form.get(target) is None:
            raise ValueError(f"there is no control named {control!r}")
        events = doc.events_of(target)
        if event not in events:
            raise ValueError(f"{control or 'the form'} has no event {event!r}; it has {', '.join(events)}")
        handler = doc.wire(target, event)
        d.code_revision += 1
        return {"handler": handler, "code": doc.handler_source(handler)}

    @tool(ui=True, title="Writing a handler")
    def set_handler(handler: str, code: str) -> Any:
        """Replaces one handler function in the form's module with code (a complete def, with its decorators
        and docstring)."""
        doc = _doc(d)
        doc.set_handler_source(handler, code)  # raises SyntaxError and changes nothing when invalid
        _sync_editor(d)
        return {"handler": handler, "ok": True}

    @tool(ui=True, title="Writing the module")
    def set_code(code: str) -> Any:
        """Replaces the whole handlers module of the open form (imports, helpers and every handler)."""
        ast.parse(code)
        _doc(d).set_code(code)
        _sync_editor(d)
        return {"ok": True, "lines": code.count("\n") + 1}

    @tool(ui=True, writes=True, title="Creating a document")
    def new_document(kind: str, name: str, folder: str = "", title: str = "") -> Any:
        """Creates a new form or component file next to the open one (or in folder), saves it and opens it in
        a new tab, so add_control and the other tools work on it.

        kind: "form" or "component".
        name: the file and class name, e.g. "login" or "user_card".
        """
        return d.agent.create_document(kind, name, folder, title)

    @tool(ui=True, writes=True, title="Saving")
    def save_document() -> Any:
        """Saves the open document (and its handlers module) to its file."""
        doc = _doc(d)
        if doc.path is None:
            raise ValueError("this document has no file yet; ask the user to save it first")
        d.save()
        return {"saved": str(doc.path)}

    tools = [get_document, add_control, update_control, remove_controls, set_form, select_controls, wire_event,
             set_handler, set_code, new_document, save_document]
    root = d.agent.project_root()
    return tools + pyzed_tools() + file_tools(root)


def _sync_editor(d: "Designer") -> None:
    """Shows the agent's code in the code editor when it is open on the changed handler or file."""
    if d.editing is None:
        return
    handler, _ = d.editing
    doc = d.doc
    d.editing = (handler, doc.code if handler == "*" else doc.handler_source(handler))
    d.code_revision += 1


def context_note(d: "Designer") -> str:
    """A short description of where the user is, sent with each message (the agent reads more with tools)."""
    doc = d.doc
    kind = "component" if getattr(doc, "is_scene", False) else "form"
    parts = [f"Open {kind}: {doc.display_name} ({len(doc.form.controls)} controls)."]
    if doc.selection:
        parts.append(f"Selected: {', '.join(doc.selection[:8])}.")
    if d.editing is not None:
        handler, _ = d.editing
        parts.append("The code editor shows the whole module." if handler == "*"
                     else f"The code editor shows the handler {handler}().")
    return " ".join(parts)

