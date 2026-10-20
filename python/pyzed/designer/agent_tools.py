"""What the designer's agent can do: read and change the open form or component, its code, and files.

Every tool here runs on the designer's UI thread (``ui=True``), so it changes the document exactly
like a click would: each change is one undo step, and "Reject" in the agent panel puts the form and
its code back as they were before the agent started. Tools that write files on disk are marked
``writes=True`` and ask first (Settings → AI agents → Ask before writing files).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from ..agents import Image, Tool, file_tools, pyzed_tools, tool
from . import components as _components
from . import layout as _layout
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
- Start with get_document to see what is open. Look types and props up instead of guessing.
- Build with add_control / update_control / remove_controls / set_form; give controls meaningful \
names (email, send_button). Lay forms out neatly on the grid: consistent margins (16 px), aligned \
labels and inputs, primary action at the bottom right.
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
- Learn from Pyzed instead of guessing: get_guide, list_components, describe_component, read_docs, \
list_examples and read_example are Pyzed's own documentation and examples (the Pyzed MCP server).
"""

#: What the designer is, for the agent (how to use it, so it can explain and drive it).
EDITOR_KNOWLEDGE = """Pyzed Design, the editor you are in: a canvas with the open form or component, the toolbox (types to \
drop), Outline (the tree of controls), Properties (props, style, layout, events of the selection), the \
code editor (the handlers module, with completion and diagnostics), the Project panel (files, \
dependencies with uv, ruff and ty checks, git), the Motion panel (animations), the Component designer \
(.pzcomp with typed properties), Preview/Run (F5 runs the form), the command palette (Ctrl+Shift+P) and \
this Agent panel. Tabs hold several documents; File > New project creates a uv project."""


def system_prompt(d: "Designer") -> str:
    """The agent's instructions: how the designer works, how to build apps, and the editor itself."""
    return f"{SYSTEM}\n{EDITOR_KNOWLEDGE}\n"


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
    tools = [get_document, add_control, update_control, remove_controls, set_form, select_controls, wire_event,
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
        "main_form": project.main_form.relative_to(root).as_posix() if project.main_form.exists() else None,
        "forms": [p.relative_to(root).as_posix() for p in project.forms],
        "package": project.src_dir.relative_to(root).as_posix() if project.src_dir else None,
        "dependencies": [str(dep.name) + (" (dev)" if dep.dev else "") for dep in project.dependencies()],
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
    import pyzed

    from .. import project as _project
    from .model import Form

    form = Form.from_json(path.read_text(encoding="utf-8"))
    size = (int(form.width) or 480, int(form.height) or 320)
    with tempfile.TemporaryDirectory(prefix="pyzed-run-") as tmp:
        script, out = Path(tmp) / "run_app.py", Path(tmp) / "window.png"
        script.write_text("import pyzed as pz\nfrom pyzed.designer.runtime import open_form\n"
                          f"pz.run(open_form({str(path)!r}))\n", encoding="utf-8")
        args = ["-m", "pyzed.mcp.preview", str(script), str(out), str(size[0]), str(size[1])]
        uv = _project.find_uv() if project is not None and not project.can_run_in_process else None
        if uv is not None:
            cmd, cwd, env = [uv, "run", "--project", str(project.root), "python", *args], project.root, \
                _project._clean_env()
        else:  # the designer has what the form needs: run it with this same pyzed
            here = str(Path(pyzed.__file__).resolve().parents[1])
            env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in (here, os.environ.get("PYTHONPATH", ""))
                                                              if p)}
            cmd, cwd = [sys.executable, *args], path.parent
        env.update(PYZED_RELOAD="0", PYTHONUNBUFFERED="1")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(cwd), env=env)
        except subprocess.TimeoutExpired:
            return {"ok": False, "output": f"{path.name} did not start within {timeout:g} seconds"}
        except OSError as err:
            return {"ok": False, "output": f"could not start {path.name}: {err}"}
        output = "\n".join(x for x in (result.stdout.strip(), result.stderr.strip()) if x)[-6000:]
        if result.returncode != 0 or not out.is_file():
            return {"ok": False, "output": output or f"{path.name} did not start"}
        text = f"{path.name} started ({size[0]}x{size[1]})." + (f" Its output:\n{output}" if output else
                                                               " It printed nothing.")
        return [text, Image(out.read_bytes(), "image/png")]


def screenshot_job(d: "Designer") -> Callable[[], bytes]:
    """A function that renders the open form off-screen and returns the PNG. Call this on the UI thread
    (it copies the form and its code) and the function it returns in a worker (it takes a few seconds)."""
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

    def render() -> bytes:
        import tempfile

        from ..mcp.preview import render as run

        with tempfile.TemporaryDirectory(prefix="pyzed-shot-") as tmp:
            path = Path(tmp) / f"{stem}.pzform"
            path.write_text(data, encoding="utf-8")
            path.with_suffix(".py").write_text(code, encoding="utf-8")
            script = (f"import sys\nsys.path.insert(0, {folder!r})\nimport pyzed as pz\n"
                      f"from pyzed.designer.runtime import open_form\npz.run(open_form({str(path)!r}))\n")
            return run(script, size=size)

    return render


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
    return " ".join(parts)

