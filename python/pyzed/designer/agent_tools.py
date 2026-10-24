"""What the designer's agent can do: read and change the open form or component, its code, and files.

Every tool here runs on the designer's UI thread (``ui=True``), so it changes the document exactly
like a click would: each change is one undo step, and "Reject" in the agent panel puts the form and
its code back as they were before the agent started. Tools that write files on disk are marked
``writes=True`` and ask first (Settings → AI agents → Ask before writing files).
"""

from __future__ import annotations

import ast
import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .. import theme as _theme
from ..agents import Image, Tool, file_tools, pyzed_tools, tool
from . import components as _components
from . import layout as _layout
from . import roles as _roles
from . import workspace as _workspace

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
- You already know the editor: the toolbox with every type's props and events, the themes, the pz.ui \
components and Pyzed's best practices are below, and each message ends with a <context> holding the open \
document (its controls and code) and the project. Act on that right away: don't call get_document, \
list_components, describe_component or get_guide for what is already there. Look something up only when \
it is missing (an example to copy, a docs page, a signature of pz.ui you are unsure of).
- Be fast: put independent calls in the same turn, and lay a whole form or group out with one \
add_controls call instead of one add_control per control.
- Build with add_controls / add_control / update_control / remove_controls / set_form; give controls \
meaningful names (email, send_button). Lay forms out neatly on the grid: consistent margins (16 px), \
aligned labels and inputs, primary action at the bottom right.
- Write logic with wire_event and set_handler (or set_code for the whole module), then check the \
module with validate_code. Keep handlers short and readable.
- To make a new form or component use new_document; it opens in a new tab.
- Look at your work: screenshot_form shows the open form as it runs; fix what looks wrong.
- Be brief in your answers: say what you changed. The user can undo every step or reject all.

Building a whole application:
- A Pyzed app is a uv project (create_project): pyproject.toml with [tool.pyzed] (ui = "ui", main = the \
main form), the forms in ui/ (<name>.pzform + <name>.py handlers), and the logic in src/<package>/ when \
it is a package (handlers import it), or main.py for a simple app. `uv run pyzed run` starts the main form.
- Work on your own from start to end: the user expects a running app, not questions. Make a plan with \
update_plan first (the screens, the backend, the checks) and keep it current as each step starts and ends.
- Build each form with new_document and the control tools, wire the events and write the handlers, put \
reusable logic and data access in the package, add dependencies with add_dependency, save with \
save_document, and check everything with check_project and validate_code.
- Then run it: run_app starts the app in its own environment and returns its output and a picture of \
its window. Read the errors and the picture, fix what is wrong and run it again until it starts cleanly \
and looks right. Finish with a short summary of what you built and how to run it.
- Apps written in code (pz.App) are fine too: write them with write_file, check them with validate_code \
and look at them with screenshot.
- For what is not below, Pyzed's own documentation and examples are at hand: get_guide, \
describe_component, read_docs, list_examples and read_example (the Pyzed MCP server).
"""

#: What the designer is, for the agent (how to use it, so it can explain and drive it).
EDITOR_KNOWLEDGE = """Pyzed Design, the editor you are in: a canvas with the open form or component, the toolbox (types to \
drop), Outline (the tree of controls), Properties (props, style, layout, events of the selection), the \
code editor (the handlers module, with completion and diagnostics), the Project panel (files, \
dependencies with uv, ruff and ty checks, git), the Motion panel (animations), the Component designer \
(.pzcomp with typed properties), Preview/Run (F5 runs the form), the command palette (Ctrl+Shift+P) and \
this Agent panel. Tabs hold several documents; File > New project creates a uv project."""


def system_prompt(d: "Designer") -> str:
    """The agent's instructions: how the designer works, how to build apps, the editor itself, and what it
    would otherwise look up on every task (the toolbox, themes, components and best practices)."""
    return f"{SYSTEM}\n{EDITOR_KNOWLEDGE}\n\n{knowledge()}\n"


#: ``knowledge()`` by the number of toolbox types (user components registered later change it).
_KNOWLEDGE: Dict[int, str] = {}


def toolbox_catalog() -> str:
    """Every toolbox type in one line: its category, color role (see ``roles``), default size, props (``name=a|b`` for choices,
    ``name:kind=default`` otherwise) and events."""
    lines = []
    for spec in _components.all_components():
        props = []
        for prop in spec.props:
            if prop.kind == "choice" and prop.choices:
                props.append(f"{prop.name}={'|'.join(map(str, prop.choices))}")
                continue
            default = prop.default
            shown = f"={default!r}" if default not in (None, "", [], (), {}) and len(repr(default)) <= 24 else ""
            props.append(f"{prop.name}:{prop.type or prop.kind}{shown}")
        events = ",".join(spec.events)
        width, height = spec.size
        lines.append(f"- {spec.type} ({spec.category}, {_roles.of(spec)}, {width:g}x{height:g}): "
                     f"{', '.join(props) or 'no props'}"
                     + (f"; events {events}" if events else ""))
    return "\n".join(lines)


def knowledge() -> str:
    """What the agent knows without looking it up: the designer's toolbox, the theme names and tokens, the
    ``pz.ui`` components and Pyzed's best practices (built once)."""
    count = len(_components.all_components())
    if count in _KNOWLEDGE:
        return _KNOWLEDGE[count]
    parts = ["# What you already know (no need to look it up)",
             "## The toolbox: designer types, props and events (every control also has the events "
             f"{', '.join(_components.COMMON_EVENTS)}; the form has {', '.join(_components.FORM_EVENTS)})",
             toolbox_catalog()]
    try:
        from ..mcp import knowledge as _knowledge

        themes = _knowledge.list_themes()
        parts += ["## Themes and color tokens", json.dumps(themes, ensure_ascii=False)]
        groups: Dict[str, List[str]] = {}
        for item in _knowledge.list_components("ui"):
            groups.setdefault(item.get("category") or "Other", []).append(item["name"])
        parts += ["## pz.ui components, by category (describe_component gives a signature)",
                  "\n".join(f"- {cat}: {', '.join(names)}" for cat, names in sorted(groups.items()))]
        parts.append(_knowledge.guide("best-practices"))
    except Exception:  # noqa: BLE001 - the agent can still look these up with its tools
        pass
    _KNOWLEDGE[count] = text = "\n\n".join(parts)
    return text


EXTERNAL = """\
These tools are Pyzed Design itself, the editor the user has open: through them you control it like its \
built-in agent. Work on forms (.pzform) and components (.pzcomp) only with these tools, never by editing \
those files by hand: the user sees every change live in the editor and can undo it. Use your own tools for \
other files and commands. Everything below about the agent applies to you; the tool names are the same.

"""


def external_prompt(d: "Designer") -> str:
    """The instructions handed to an external agent (Claude Code...) with the editor's MCP server."""
    return EXTERNAL + system_prompt(d)


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
    theme = _theme.current()
    for key, value in props.items():
        if spec.prop(key).kind == "color" and isinstance(value, str) and value and theme.find_color(value) is None:
            raise ValueError(f"{key}={value!r} is not a color: use '#rrggbb' or a theme token such as text, "
                             "text_muted, accent, success, warning, error, surface or border")


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
            "open_tabs": [x.display_name for x in d.panes.all_docs()],
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
        info = _place(type, name, parent, x, y, width, height, props, style)
        _doc(d).commit()
        d._selection_changed()
        return info

    def _place(type: str, name: str = "", parent: str = "", x: float = 16, y: float = 16,  # noqa: A002
               width: float = 0, height: float = 0, props: Optional[Dict[str, Any]] = None,
               style: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        return _control_info(doc.form[doc.selection[0]] if doc.selection else control)

    @tool(ui=True, title="Adding controls")
    def add_controls(controls: List[Dict[str, Any]]) -> Any:
        """Places several controls at once (a whole form or group in one call, in order, so a container can be
        the parent of the controls after it) and returns them. One undo step; when one of them is wrong,
        none is added.

        controls: each like add_control's arguments: {"type": "input", "name": "email", "parent": "form_column",
        "x": 16, "y": 48, "width": 240, "props": {"placeholder": "Email"}, "style": {...}}.
        """
        if not controls:
            raise ValueError("controls is empty")
        allowed = {"type", "name", "parent", "x", "y", "width", "height", "props", "style"}
        doc = _doc(d)
        mark = doc.history.steps
        placed: List[Dict[str, Any]] = []
        try:
            for i, item in enumerate(controls):
                if not isinstance(item, dict) or not item.get("type"):
                    raise ValueError(f"controls[{i}] needs a type")
                unknown = sorted(set(item) - allowed)
                if unknown:
                    raise ValueError(f"controls[{i}] has unknown keys {unknown}; use {sorted(allowed)}")
                try:
                    placed.append(_place(**item))
                except (ValueError, KeyError, TypeError) as err:
                    raise ValueError(f"controls[{i}] ({item.get('name') or item['type']}): {err}; nothing was "
                                     "added") from None
            doc.commit()
        finally:
            if doc.history.steps > mark:
                doc.history.merge(mark)
                if len(placed) < len(controls):  # a wrong one: the batch goes away, so a retry starts clean
                    doc.undo()
            d._selection_changed()
        doc.select([p["name"] for p in placed])
        d._selection_changed()
        return {"added": placed}

    add_controls.schema["properties"]["controls"]["items"] = {
        "type": "object", "required": ["type"],
        "properties": {"type": {"type": "string"}, "name": {"type": "string"}, "parent": {"type": "string"},
                       "x": {"type": "number"}, "y": {"type": "number"}, "width": {"type": "number"},
                       "height": {"type": "number"}, "props": {"type": "object"}, "style": {"type": "object"}}}

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

    @tool(title="Looking at the form")
    def screenshot_form() -> Any:
        """A picture of the open form as it looks when it runs (its handlers' load event runs too)."""
        return [f"Screenshot of {d.doc.display_name}.", Image(d.agent.on_ui(lambda: screenshot_job(d))(),
                                                             "image/png")]

    @tool(ui=True, title="Reading the project")
    def get_project() -> Any:
        """The open project: its name, folder, main form, forms, dependencies and files (or that there is none)."""
        return project_info(d)

    @tool(writes=True, title="Creating a project")
    def create_project(name: str, folder: str = "", package: bool = True) -> Any:
        """Creates a Pyzed app project with uv (pyproject.toml, ui/ with a main form, src/<package>) and opens it.

        name: the project name, e.g. "notes-app".
        folder: where to create it (default: next to the open project, or the current folder).
        package: True puts the logic in src/<package> (recommended); False makes a main.py app.
        """
        from .. import project as _project

        if _project.find_uv() is None:
            raise RuntimeError("uv is needed to create projects: https://docs.astral.sh/uv/")
        base = Path(folder).expanduser() if folder else d.agent.on_ui(lambda: d.agent.project_root().parent
                                                                         if d.projects.project else
                                                                         _workspace.start_folder())
        target = (base / name).resolve()
        if target.exists() and any(target.iterdir()) and not (target / "pyproject.toml").exists():
            raise FileExistsError(f"{target} is not empty")
        problem = _workspace.check_writable(target)
        if problem is not None:
            raise PermissionError(problem)
        created = _project.init(target, package=package)
        d.agent.on_ui(lambda: d.projects.open(str(created.root)))
        return d.agent.on_ui(lambda: project_info(d))

    @tool(writes=True, title="Adding a dependency")
    def add_dependency(spec: str, dev: bool = False) -> Any:
        """Adds a package to the open project with uv add (e.g. "httpx", "sqlalchemy>=2").

        dev: a development dependency (tests, tools).
        """
        project = d.agent.on_ui(lambda: d.projects.project)
        if project is None:
            raise ValueError("no project is open; create one with create_project")
        result = project.add(spec, dev=dev)
        d.agent.on_ui(d.projects.refresh)
        return {"ok": result.ok, "output": result.output[-3000:]}

    @tool(title="Checking the project")
    def check_project() -> Any:
        """Runs ruff on the open project and returns what it reports."""
        project = d.agent.on_ui(lambda: d.projects.project)
        if project is None:
            raise ValueError("no project is open")
        result = project.check()
        return {"ok": result.ok, "output": result.output[-6000:]}

    @tool(ui=True, title="Opening a file")
    def open_document(path: str) -> Any:
        """Opens a form (.pzform) or component (.pzcomp) of the project in a tab, so the other tools work on it.

        path: relative to the project folder.
        """
        root = d.agent.project_root().resolve()
        target = (root / path).resolve()
        if target != root and root not in target.parents:
            raise PermissionError(f"{path} is outside the project folder")
        if not target.is_file():
            raise FileNotFoundError(path)
        d.open_path(target)
        return {"open": d.doc.display_name}

    @tool(writes=True, title="Running the app")
    def run_app(form: str = "") -> Any:
        """Runs the app the way the user would, in the project's own environment, without showing a window: \
returns what it printed (errors and tracebacks included) and a picture of its window. It runs the files \
on disk, so save_document first. Run it after building or changing an app, fix what it shows, run again.

        form: a .pzform path relative to the project folder (default: the project's main form, else the open form).
        """
        target, project, note = d.agent.on_ui(lambda: _run_target(d, form))
        result = run_form_check(target, project)
        if note and isinstance(result, list):
            result[0] += f" {note}"
        return result

    @tool(title="Updating the plan")
    def update_plan(steps: List[Dict[str, str]]) -> Any:
        """Shows the plan of a multi-step job (an app, several forms) as a checklist in the Agent panel. \
Call it at the start with every step, and again whenever a step starts or ends.

        steps: every step in order, each {"step": "Build the login form", "status": "pending"}; status is \
pending, in_progress or done.
        """
        clean = _plan_steps(steps)
        left = [s["step"] for s in clean if s["status"] != "done"]
        return {"steps": len(clean), "left": left}

    update_plan.schema["properties"]["steps"]["items"] = {
        "type": "object", "required": ["step", "status"],
        "properties": {"step": {"type": "string"}, "status": {"type": "string", "enum": list(PLAN_STATUSES)}}}
    tools = [get_document, add_control, add_controls, update_control, remove_controls, set_form, select_controls, wire_event,
             set_handler, set_code, new_document, save_document, screenshot_form, get_project, create_project,
             add_dependency, check_project, open_document, run_app, update_plan]
    root = d.agent.project_root()
    return tools + pyzed_tools() + file_tools(root)


def project_info(d: "Designer") -> Dict[str, Any]:
    """What the agent knows about the open project (on the UI thread)."""
    project = getattr(d.projects, "project", None)
    if project is None:
        return {"project": None, "folder": str(d.agent.project_root()),
                "note": "No project is open. create_project makes one; forms can also live in this folder."}
    root = Path(project.root)
    files = []
    try:
        from ..agents.tools import SKIP_DIRS

        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts) or not path.is_file():
                continue
            files.append(rel.as_posix())
            if len(files) >= 200:
                break
    except OSError:
        pass
    return {
        "project": project.name, "folder": str(root), "version": project.version,
        "environment": project.environment.describe(), "branch": d.projects.branch,
        "main_form": project.main_form.relative_to(root).as_posix() if project.main_form.exists() else None,
        "forms": [p.relative_to(root).as_posix() for p in project.forms()],
        "package": project.src_dir.relative_to(root).as_posix() if project.src_dir else None,
        "dependencies": [str(dep.name) + (" (dev)" if dep.dev else "") for dep in project.dependencies()],
        # an old pyzed-ui or packages not installed: fix them before blaming the forms
        "problems": [problem.message for problem in project.problems()],
        "files": files,
    }


PLAN_STATUSES = ("pending", "in_progress", "done")


def _plan_steps(steps: Any) -> List[Dict[str, str]]:
    """The steps of an ``update_plan`` call, checked: each a ``step`` text and a known ``status``."""
    if not isinstance(steps, list) or not steps:
        raise ValueError("steps must be a non-empty list of {step, status}")
    clean = []
    for item in steps:
        if not isinstance(item, dict) or not str(item.get("step") or "").strip():
            raise ValueError("each step needs a 'step' text")
        status = str(item.get("status") or "pending")
        if status not in PLAN_STATUSES:
            raise ValueError(f"unknown status {status!r}: use pending, in_progress or done")
        clean.append({"step": str(item["step"]).strip(), "status": status})
    return clean


def plan_of(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """The thread's current plan: the steps of its last ``update_plan`` call (empty without one)."""
    for message in reversed(messages):
        content = message.get("content")
        if message.get("role") != "assistant" or not isinstance(content, list):
            continue
        for block in reversed(content):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "update_plan":
                steps = (block.get("input") or {}).get("steps")
            elif block.get("type") == "plan":  # an external agent's plan (see acp.ACPAgent)
                steps = block.get("steps")
            else:
                continue
            try:
                return _plan_steps(steps)
            except ValueError:
                return []
    return []


def _run_target(d: "Designer", form: str) -> Tuple[Path, Any, str]:
    """The form ``run_app`` runs, its project and a note on unsaved changes (on the UI thread)."""
    project = getattr(d.projects, "project", None)
    root = d.agent.project_root().resolve()
    if form:
        target = (root / form).resolve()
        if target != root and root not in target.parents:
            raise PermissionError(f"{form} is outside the project folder")
        if not target.is_file():
            raise FileNotFoundError(form)
    elif project is not None and project.main_form.is_file():
        target = project.main_form.resolve()
    elif d.doc.path is not None and not getattr(d.doc, "is_scene", False):
        target = d.doc.path.resolve()
    else:
        raise ValueError("there is no saved form to run: save the open form (save_document) or create a project")
    unsaved = [x.display_name for x in d.panes.all_docs() if getattr(x, "dirty", False)]
    note = f"Not saved (not included): {', '.join(unsaved)}; save_document saves the open one." if unsaved else ""
    return target, project, note


def run_form_check(path: Path, project: Any = None, *, timeout: float = 240.0) -> Any:
    """Runs the form at ``path`` off-screen in its own process, like ``uv run pyzed run`` would (in the
    project's environment when the designer lacks its dependencies), and returns its output and picture."""
    from ..mcp import preview as _preview
    from .model import Form

    form = Form.from_json(path.read_text(encoding="utf-8"))
    size = (int(form.width) or 480, int(form.height) or 320)
    with tempfile.TemporaryDirectory(prefix="pyzed-run-") as tmp:
        script, out = Path(tmp) / "run_app.py", Path(tmp) / "window.png"
        script.write_text("import pyzed as pz\nfrom pyzed.designer.runtime import open_form\n"
                          f"pz.run(open_form({str(path)!r}))\n", encoding="utf-8")
        python, env = _preview_python(project)
        cwd = project.root if python is not None else path.parent
        if python is None or env is None:  # the designer has what the form needs: run it with this same pyzed
            python, env = _preview.this_python()
        env.update(PYZED_RELOAD="0", PYTHONUNBUFFERED="1")
        env.pop("PYZED_DESIGNER_RUN", None)
        rest = [str(script), str(out), str(size[0]), str(size[1])]
        # off-screen first; when the renderer fails (not the form), in a window for a moment
        for window in (False, True):
            cmd = [*python, "-m", "pyzed.mcp.preview", *(["--window"] if window else []), *rest]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout,
                                        cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except subprocess.TimeoutExpired:
                return {"ok": False, "output": f"{path.name} did not start within {timeout:g} seconds"}
            except OSError as err:
                return {"ok": False, "output": f"could not start {path.name}: {err}"}
            output = "\n".join(x for x in (result.stdout.strip(), result.stderr.strip()) if x)[-6000:]
            if result.returncode == 0 and out.is_file():
                break
            log = Path(f"{out}.log")
            output = output or (log.read_text(encoding="utf-8", errors="replace")[-6000:] if log.is_file() else "")
            if window or _form_error(output):
                return {"ok": False, "output": output or f"{path.name} did not start"}
        text = f"{path.name} started ({size[0]}x{size[1]})." + (f" Its output:\n{output}" if output else
                                                               " It printed nothing.")
        return [text, Image(out.read_bytes(), "image/png")]


def screenshot_job(d: "Designer") -> Callable[[], bytes]:
    """A function that renders the open form and returns the PNG. Call this on the UI thread (it copies the
    form and its code) and the function it returns in a worker (it takes a few seconds).

    The form runs in its own process: the project's environment when the designer lacks its packages (as
    ``run_app`` does), else this same Pyzed. It is drawn off-screen; when that fails (a driver that cannot
    draw without a window) the form opens in a window for a moment and the window is captured instead."""
    from .model import identifier

    doc = d.doc
    if getattr(doc, "is_scene", False):
        raise ValueError("Screenshots show forms; this tab is a component")
    form = doc.form.copy()
    form.code = None
    data, code = form.to_json(), doc.code
    stem = doc.path.stem if doc.path is not None else identifier(form.name) or "form"
    folder = str(doc.path.resolve().parent if doc.path is not None else d.agent.project_root())
    size = (int(form.width) or 480, int(form.height) or 320)
    python, env = _preview_python(getattr(d.projects, "project", None))

    def render() -> bytes:
        from ..mcp.preview import render as run

        with tempfile.TemporaryDirectory(prefix="pyzed-shot-") as tmp:
            path = Path(tmp) / f"{stem}.pzform"
            path.write_text(data, encoding="utf-8")
            path.with_suffix(".py").write_text(code, encoding="utf-8")
            script = (f"import sys\nsys.path.insert(0, {folder!r})\nimport pyzed as pz\n"
                      f"from pyzed.designer.runtime import open_form\npz.run(open_form({str(path)!r}))\n")
            try:
                return run(script, size=size, timeout=SHOT_TIMEOUT, python=python, env=env)
            except RuntimeError as err:
                if _form_error(str(err)):
                    raise  # the form's own error: a window would show the same one
                try:
                    return run(script, size=size, timeout=WINDOW_TIMEOUT, window=True, python=python, env=env)
                except RuntimeError as again:
                    raise RuntimeError(f"{err}\n\nIn a window it failed too: {again}") from None

    return render


#: How long a screenshot may take (the first ``uv run`` of a project installs its packages), and its retry
#: in a window.
SHOT_TIMEOUT = 120.0
WINDOW_TIMEOUT = 60.0


def _preview_python(project: Any) -> Tuple[Optional[List[str]], Optional[Dict[str, str]]]:
    """The interpreter that renders forms: the project's environment through ``uv run`` when the designer
    cannot import its packages (a compiled Pyzed Design...), else this one (``None, None``)."""
    from .. import project as _project

    uv = _project.find_uv() if project is not None and not project.can_run_in_process else None
    if uv is None:
        return None, None
    return [uv, "run", "--project", str(project.root), "python"], _project._clean_env()


def _form_error(message: str) -> bool:
    """Whether a failed screenshot is the form's own fault (a Python error in its code), which a window would
    show the same, rather than the renderer's (a crash, a panic, no answer)."""
    return "Traceback (most recent call last)" in message and "panicked" not in message \
        and "PanicException" not in message


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
    project = getattr(d.projects, "project", None)
    parts = [f"Project: {project.name} in {project.root}." if project is not None else
             f"No project is open; the folder is {d.agent.project_root()}."]
    projects = d.projects
    parts.append(f"Environment: {projects.environment.describe()}")
    if project is not None and projects.branch:
        parts.append(f"Git branch: {projects.branch}" + (f" (worktree {projects.worktree})." if projects.worktree
                                                          else "."))
    elsewhere = [root.name for root in projects.window if project is None or root != project.root]
    if elsewhere:
        parts.append(f"Also open in this window (not active): {', '.join(elsewhere[:8])}.")
    others = [x.display_name for x in d.panes.all_docs() if x is not doc]
    parts.append(f"Open {kind}: {doc.display_name} ({len(doc.form.controls)} controls"
                 + (f", saved as {doc.path.name}" if doc.path is not None else ", not saved yet") + ").")
    if others:
        parts.append(f"Other tabs: {', '.join(others[:8])}.")
    if doc.selection:
        parts.append(f"Selected: {', '.join(doc.selection[:8])}.")
    if d.editing is not None:
        handler, _ = d.editing
        parts.append("The code editor shows the whole module." if handler == "*"
                     else f"The code editor shows the handler {handler}().")
    return " ".join(parts) + _document_note(doc)


#: How much of the open document goes with each message (more is read with get_document).
NOTE_LIMIT = 12_000


def _document_note(doc: Any) -> str:
    """The open document as the agent would read it with get_document, when it is small enough: its form
    settings, controls and handlers module, so the agent starts working without looking first."""
    f = doc.form
    controls = json.dumps([_control_info(c) for c in f.controls], ensure_ascii=False, separators=(",", ":"),
                          default=str)
    head = (f"\nThe {('component' if getattr(doc, 'is_scene', False) else 'form')}: name {f.name!r}, title "
            f"{f.title!r}, {f.width:g}x{f.height:g}, theme {f.theme!r}, grid {f.grid}.")
    if len(controls) > NOTE_LIMIT:
        names = ", ".join(f"{c.name} ({c.type})" for c in f.controls[:200])
        return f"{head}\nIts controls (get_document has their props): {names}."
    code = doc.code or ""
    note = f"{head}\nIts controls: {controls}"
    if code.strip() and len(code) + len(controls) <= NOTE_LIMIT:
        note += f"\nIts handlers module:\n```python\n{code}\n```"
    elif code.strip():
        note += f"\nIts handlers module has {code.count(chr(10)) + 1} lines (get_document reads it)."
    return note

