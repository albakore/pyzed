"""The Pyzed MCP server: tools, resources and prompts for AI agents (stdio transport).

Needs the MCP Python SDK (``pip install "pyzed-ui[mcp]"``); works with ``mcp`` 1.x (``FastMCP``)
and 2.x (``MCPServer``).
"""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import knowledge, projects, scaffold, validate

try:  # mcp 2.x
    from mcp.server.mcpserver import Image, MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server, Image  # type: ignore
    from mcp.server.fastmcp.exceptions import ToolError  # type: ignore

INSTRUCTIONS = """\
Pyzed builds native desktop GUIs in Python, rendered by Iced (Rust), with components that look like
the Zed editor (`import pyzed as pz`, `from pyzed import ui`). Never guess an API: look it up here.

What to do for each kind of request:
- "Build an app / a screen": plan_app(description) first (it names the blocks, examples, components and
  guides to read), then follow its steps: project_info (or create_project), start_live_preview so the user
  watches the app while you build it, write_files in small steps, check_project, run_tests and
  screenshot_project until all are clean. The build_project prompt has the whole loop.
- "Make a component": list_components to reuse what exists, new_component, then validate_code and
  screenshot with a preview() function.
- "Make a designer form": list_components(kind="designer"), new_form, validate_form.
- "A shader / visual effect": get_guide("shaders"); node graphs (.pzshad, drawn with pz.shader("x.pzshad"))
  start from new_shader, use list_shader_nodes and check_shader; style effects (glow, glass...) are in the cookbook.
- "How does X work": get_guide(topic) (list_guides), search_reference / read_reference, read_docs.

Knowledge: get_guide("overview"), "best-practices" and "cookbook" (runnable recipes), list_components /
describe_component, search_icons, list_themes, list_examples / read_example (blocks are whole screens).
Checks: validate_code, validate_form, check_project; pictures: screenshot, screenshot_project.
Project tools work in the folder the server runs in and in the project's own environment (its .venv through
uv run; project_info shows it, WSL included). Code goes in the project's files: the entry is its script
(`script` in [tool.pyzed]) or its main form; forms, components and shaders are files of the project."""


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=repr)


def create(allow_code: bool = True, root: Optional[str] = None) -> Any:
    """Builds the server with every tool, resource and prompt registered.

    The project tools work in ``root`` (by default the current folder) and never outside it.
    ``allow_code=False`` leaves out ``screenshot`` and the project tools, which read and write files and run
    code (the app, its tests, uv)."""
    base = Path(root or os.getcwd()).resolve()
    try:
        server = _Server("pyzed", instructions=INSTRUCTIONS, version=knowledge.version())
    except TypeError:  # mcp 1.x takes no version
        server = _Server("pyzed", instructions=INSTRUCTIONS)

    def tool(**options):
        # mcp 2.x hides the text of unexpected exceptions from the client; the agent needs it to fix its call.
        try:
            register = server.tool(**options)
        except TypeError:  # mcp before 1.10 has no structured_output
            register = server.tool()

        def decorate(func):
            @functools.wraps(func)
            def run(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except ToolError:
                    raise
                except Exception as err:  # noqa: BLE001 - reported to the agent as the tool's error
                    raise ToolError(f"{type(err).__name__}: {err}") from err

            return register(run)

        return decorate

    # Tools that read or write files or run code: left out when allow_code is false.
    gated = tool if allow_code else (lambda **_: (lambda func: func))

    # -- knowledge -------------------------------------------------------------------------------------
    @tool()
    def get_guide(topic: str = "overview", lang: str = "en") -> str:
        """How Pyzed works. topic: "overview" (architecture, API layers, components, designer, CLI),
        "best-practices" (rules for views, state, components, styling, layout and testing), "cookbook"
        (runnable recipes for the features most apps need) or any topic of list_guides ("games",
        "shaders", "animation", "performance", "integrations", "editor-shortcuts"...). lang: "en" or "es"."""
        return knowledge.guide(topic, lang)

    @tool()
    def plan_app(description: str) -> str:
        """Where to start for an app or screen: the closest blocks and examples, the components and guide
        topics it needs, the documentation pages to read and the steps to build it. Call it first."""
        return _json(knowledge.plan(description))

    @tool()
    def list_guides() -> str:
        """Every topic get_guide takes, with what it covers."""
        return _json(knowledge.guides())

    @tool()
    def list_components(kind: str = "all", query: str = "", category: str = "") -> str:
        """Lists Pyzed widgets and components with a one-line summary.

        kind: "widget" (pz.* primitives), "ui" (pz.ui.* Zed-style components), "designer" (the visual
        designer's toolbox types), "component" (pz.Component classes) or "all".
        query filters by name or summary; category keeps one section (e.g. "Layout", "Navigation")."""
        return _json(knowledge.list_components(kind, query, category))

    @tool()
    def describe_component(name: str) -> str:
        """The signature, documentation and parameters of a widget or component, or the props and events
        of a designer toolbox type. name: "pz.column", "ui.button", "designer:button" or a bare name."""
        return _json(knowledge.describe_component(name))

    @tool()
    def search_reference(query: str, lang: str = "en", limit: int = 20) -> str:
        """Searches Pyzed's whole reference (widgets, components, classes, functions, modules such as
        pyzed.game or pyzed.updater, designer controls) and returns the ids read_reference takes."""
        return _json(knowledge.search_reference(query, lang, limit))

    @tool()
    def read_reference(name: str, lang: str = "en") -> str:
        """The reference page of anything in Pyzed, in Markdown: signature, description, parameters and
        members. name: "pz.shader", "pyzed.game.vector", "ui.virtual_list", "App", "pyzed.updater"..."""
        return _json(knowledge.read_reference(name, lang))

    @tool()
    def editor_keymap() -> str:
        """The default key bindings of Pyzed's code editor (ui.editor, also used by Pyzed Design), by
        action, and how to change them."""
        return _json(knowledge.editor_keymap())

    @tool()
    def search_icons(query: str = "", limit: int = 50) -> str:
        """Finds bundled Lucide icon names (for icon=... and pz.icon); every word of query must match."""
        return _json(knowledge.search_icons(query, limit))

    @tool()
    def list_themes() -> str:
        """The built-in themes and the color tokens styles and components accept ("accent", "panel"...)."""
        return _json(knowledge.list_themes())

    @tool()
    def list_docs() -> str:
        """Every page of the official documentation, with the slug read_docs takes."""
        return _json(knowledge.list_docs())

    @tool()
    def read_docs(slug: str, lang: str = "en") -> str:
        """The Markdown of a documentation page, e.g. "guides/layout" or "reference/ui". lang: "en" or "es"."""
        return knowledge.read_docs(slug, lang)

    @tool()
    def list_examples(kind: str = "", query: str = "") -> str:
        """The example apps of the repository. kind keeps one group: "app" (a Zed-like editor, a to-do list,
        dialogs, canvas...), "blocks" (whole screens to copy: dashboard, settings, chat, kanban...), "games",
        "showcase" (shaders, effects, animation), "integrations" (FastAPI, SQLAlchemy, SQLModel, Django
        projects), "tutorial" or "designer". query filters by name or summary."""
        return _json(knowledge.list_examples(kind, query))

    @tool()
    def read_example(name: str) -> str:
        """The full source code of an example (name from list_examples, e.g. "todo" or "blocks/dashboard";
        files of an integration project are listed one by one)."""
        return knowledge.read_example(name)

    # -- generators ------------------------------------------------------------------------------------
    @tool()
    def new_app(title: str = "My App", layout: str = "simple", theme: str = "One Dark",
                width: int = 900, height: int = 600) -> str:
        """The code of a runnable pz.App script. layout: "simple" (a counter to build on) or "workspace"
        (a Zed-like window with sidebar, tabs, status bar and command palette)."""
        return scaffold.app(title, size=(width, height), theme=theme, layout=layout)

    @tool()
    def new_component(name: str, description: str = "", props: Optional[List[Dict[str, Any]]] = None,
                      state: Optional[List[Dict[str, Any]]] = None, events: Optional[Dict[str, str]] = None,
                      icon: str = "box", category: str = "Custom") -> str:
        """The skeleton of a reusable pz.Component (it also shows up in the designer's toolbox).

        props / state: lists of {"name", "type"?, "default"?, "doc"?}; events: {"change": "what it means"}.
        Returns the module code and how a view uses it."""
        return _json(scaffold.component(name, description=description, props=props or (), state=state or (),
                                        events=events, icon=icon, category=category))

    @tool()
    def new_form(name: str, title: str = "", controls: Optional[List[Dict[str, Any]]] = None,
                 width: float = 480, height: float = 320, theme: str = "One Dark",
                 form_events: Optional[List[str]] = None) -> str:
        """A visual-designer form: the <name>.pzform layout and the <name>.py handlers module.

        controls: [{"type": "input", "name": "email", "props": {"placeholder": "Email"}},
                   {"type": "button", "name": "send", "props": {"text": "Send"}, "events": ["click"]}]
        (types from list_components(kind="designer"); x/y/width/height optional, stacked when missing).
        form_events: "load", "close", "key", "resize". Save both files side by side and run
        `pyzed run <name>.pzform`."""
        return _json(scaffold.form(name, title=title, width=width, height=height, theme=theme,
                                   controls=controls or (), form_events=form_events or ()))

    # -- shaders (pyzed.shading) -------------------------------------------------------------------------
    @tool()
    def list_shader_nodes(query: str = "", category: str = "") -> str:
        """The nodes of shader graphs (.pzshad, made in Pyzed Design's Shader view or with pyzed.shading.Graph):
        each entry's key (what Graph.add takes, e.g. "noise", "func:sin", "math:multiply"), node type and
        params, inputs, outputs and settings. category: Input, Parameters, Constants, Math, Vector, UV, Noise,
        Patterns, Shapes, Color, Effects, Texture, Logic, Variables, Utility or Output."""
        from . import shaders

        return _json(shaders.list_nodes(query, category))

    @tool()
    def check_shader(shader: str) -> str:
        """Compiles the JSON of a .pzshad to WGSL and checks it with the GPU compiler: the problems by node,
        the generated code, the uniform each mutable variable becomes, and whether it animates."""
        from . import shaders

        return _json(shaders.check(shader))

    @tool()
    def new_shader(template: str = "blank") -> str:
        """The JSON of a new .pzshad from one of Pyzed Design's templates (blank, plasma, clouds, glow_ring,
        cells, retro_screen). Save it as <name>.pzshad and draw it with pz.shader("<name>.pzshad")."""
        from . import shaders

        return shaders.template(template)

    # -- checks ----------------------------------------------------------------------------------------
    @tool()
    def validate_code(code: str) -> str:
        """Checks Pyzed code without running it: unknown pz/ui names, wrong keyword arguments, apps without
        view(), components without render(), side effects in view(), lambdas in loops, plus ruff if installed."""
        return _json(validate.check_code(code))

    @tool()
    def validate_form(form: str, handlers: str = "") -> str:
        """Validates the JSON of a .pzform (component types, props, events, names, parents) and, when the
        handlers module is given, that it defines every handler the form calls."""
        return _json(validate.check_form(form, handlers))

    @gated(structured_output=False)  # images, not JSON
    def screenshot(code: str, width: int = 800, height: int = 600, scale: float = 1.0) -> Any:
        """Runs Pyzed code off-screen (no window, no GPU) and returns a PNG of its UI.

        The code is a script defining a pz.App (pz.run is intercepted) or a top-level preview() function
        that returns a widget. It runs in a separate process with a 60 second limit."""
        from .preview import render

        return Image(data=render(code, size=(width, height), scale=scale), format="png")

    # -- projects --------------------------------------------------------------------------------------
    @gated()
    def project_info(path: str = ".") -> str:
        """The Pyzed project in path (relative to the folder this server works in): name, version, main
        form, forms, components, package, dependencies and files. Says so when there is none yet."""
        return _json(projects.info(base, path))

    @gated()
    def list_files(pattern: str = "*", path: str = ".", limit: int = 300) -> str:
        """Files under path whose relative path or name matches the glob pattern ("*.py", "ui/*.pzform")."""
        return _json(projects.list_files(base, pattern, path, limit))

    @gated()
    def read_file(path: str) -> str:
        """The text of a file of the folder (secrets such as .env and keys are out of reach)."""
        return projects.read_file(base, path)

    @gated()
    def write_files(files: Dict[str, str]) -> str:
        """Creates or replaces files, {"relative/path.py": "text"}, creating folders. Every Python file and
        .pzform written is checked like validate_code / validate_form: fix what "checks" reports."""
        return _json(projects.write_files(base, files))

    @gated()
    def create_project(name: str, folder: str = ".", package: bool = True, git: bool = True,
                       sync: bool = True) -> str:
        """Creates a Pyzed project with uv in folder/name (pyproject with pyzed-ui, ruff and ty, ui/main.pzform
        with its handlers, src/<package> when package, git) and returns its project_info."""
        return _json(projects.create_project(base, name, folder=folder, package=package, git=git, sync=sync))

    @gated()
    def add_dependency(packages: List[str], dev: bool = False, path: str = ".") -> str:
        """`uv add` in the project at path, e.g. ["httpx", "sqlmodel>=0.0.22"]; dev for test tools."""
        return _json(projects.add_dependency(base, packages, dev=dev, path=path))

    @gated()
    def check_project(path: str = ".", tools: bool = True) -> str:
        """Checks every Python file and form under path with Pyzed's own checks and, with tools, ruff and ty
        in the project. Run it after each round of changes and fix what it reports."""
        return _json(projects.check_project(base, path, tools=tools))

    @gated()
    def run_tests(path: str = ".", args: Optional[List[str]] = None) -> str:
        """`uv run pytest -q` in the project at path (args are passed to pytest, e.g. ["-k", "login"])."""
        return _json(projects.run_tests(base, path, args or ()))

    @gated(structured_output=False)
    def screenshot_project(target: str = "", width: int = 0, height: int = 0) -> Any:
        """Renders a script (.py), form (.pzform), component (.pzcomp) or shader graph (.pzshad) of the folder
        off-screen, in the project's environment, and returns a PNG; by default the project's entry (its script,
        else its main form). width/height default to the form's size."""
        caption, png = projects.screenshot(base, target, size=(width, height) if width and height else None)
        return [caption, Image(data=png, format="png")]

    @gated()
    def start_live_preview(target: str = "") -> str:
        """Opens the app in a real window with hot reload, in the project's environment, so the user watches it
        while you build: every file you write updates it on save. target: a script, form, component or shader
        of the folder (default: the project's entry). Returns whether it runs and what it printed."""
        from . import live

        return _json(live.start(base, target))

    @gated()
    def live_preview_status(target: str = "") -> str:
        """The open live previews: whether each still runs and what it printed (read it after your changes:
        tracebacks from view() and handlers show up here)."""
        from . import live

        return _json(live.status(target))

    @gated()
    def stop_live_preview(target: str = "") -> str:
        """Closes the live preview of target, or every one."""
        from . import live

        return _json(live.stop(target))

    # -- resources -------------------------------------------------------------------------------------
    @server.resource("pyzed://guide", mime_type="text/markdown")
    def guide_resource() -> str:
        """How Pyzed works, for agents."""
        return knowledge.guide("overview")

    @server.resource("pyzed://best-practices", mime_type="text/markdown")
    def best_practices_resource() -> str:
        """Rules for writing good Pyzed apps and components."""
        return knowledge.guide("best-practices")

    @server.resource("pyzed://cookbook", mime_type="text/markdown")
    def cookbook_resource() -> str:
        """Runnable recipes for the features most apps need."""
        return knowledge.guide("cookbook")

    @server.resource("pyzed://reference/{name}", mime_type="text/markdown")
    def reference_resource(name: str) -> str:
        """The reference page of anything in Pyzed (pyzed.game.vector, ui.virtual_list...)."""
        return knowledge.read_reference(name)["body"] or ""

    @server.resource("pyzed://components", mime_type="application/json")
    def components_resource() -> str:
        """Every widget, pz.ui component and designer type with a one-line summary."""
        return _json(knowledge.list_components())

    @server.resource("pyzed://component/{name}", mime_type="application/json")
    def component_resource(name: str) -> str:
        """The full description of one widget or component."""
        return _json(knowledge.describe_component(name))

    @server.resource("pyzed://themes", mime_type="application/json")
    def themes_resource() -> str:
        """Built-in themes and color tokens."""
        return _json(knowledge.list_themes())

    @server.resource("pyzed://docs", mime_type="application/json")
    def docs_resource() -> str:
        """The index of the documentation pages."""
        return _json(knowledge.list_docs())

    @server.resource("pyzed://docs/{slug}", mime_type="text/markdown")
    def doc_resource(slug: str) -> str:
        """A documentation page (slugs with a slash use "--" instead: guides--layout)."""
        return knowledge.read_docs(slug.replace("--", "/"))

    # -- prompts ---------------------------------------------------------------------------------------
    @server.prompt()
    def create_component(description: str) -> str:
        """Design and write a reusable Pyzed component."""
        return (f"Write a reusable Pyzed component: {description}\n\n"
                "Read get_guide('best-practices') first. Check existing pz.ui components with list_components "
                "and describe_component so you build on them instead of duplicating them. Start from "
                "new_component, document every prop and event, use theme tokens for colors, then run "
                "validate_code and screenshot (with a preview() function) to check the result.")

    @server.prompt()
    def create_app(description: str) -> str:
        """Plan and write a Pyzed desktop app."""
        return (f"Build a Pyzed desktop app: {description}\n\n"
                "Read get_guide('overview') and get_guide('best-practices'). Start from new_app (layout "
                "'workspace' for an editor-like window), keep view() free of side effects, prefer pz.ui "
                "components (look them up with list_components / describe_component), then check it with "
                "validate_code and screenshot.")

    @server.prompt()
    def create_form(description: str) -> str:
        """Build a form for Pyzed's visual designer."""
        return (f"Create a Pyzed designer form: {description}\n\n"
                "List the toolbox types with list_components(kind='designer') and their props with "
                "describe_component('designer:<type>'). Generate the files with new_form, fill in the handlers "
                "(def <control>_<event>(form, event)), and check both files with validate_form.")

    @server.prompt()
    def build_project(description: str) -> str:
        """Build a complete Pyzed app in this folder, watched live, from the project to a clean check."""
        return (f"Build a complete Pyzed desktop app in this folder: {description}\n\n"
                "1. plan_app with the description; read the guides and the closest examples it names (blocks "
                "first) and get_guide('best-practices').\n"
                "2. project_info: the project, its entry and environment. Without a project, create_project.\n"
                "3. Plan the screens, the state (plain classes in the package, easy to test) and the background "
                "work. Look up every widget with describe_component or read_reference.\n"
                "4. start_live_preview on the entry, so the user sees the app take shape.\n"
                "5. write_files in small steps: state and logic, then views or designer forms, then tests. Fix "
                "what each write reports and what live_preview_status shows.\n"
                "6. add_dependency for libraries, check_project and run_tests until both are clean, and "
                "screenshot_project each screen to check it looks right. Then tell the user how to run it.")

    return server


def main(transport: str = "stdio", allow_code: Optional[bool] = None, root: Optional[str] = None) -> None:
    """Runs the server (blocks). ``transport`` is ``"stdio"`` (the default) or ``"streamable-http"``.

    Over HTTP any local program can reach the server without signing in, so ``screenshot`` and the project
    tools (which read and write files and run code) are only offered there when ``allow_code`` is true; over
    stdio only the agent that started it can. ``root`` is the folder the project tools work in."""
    if allow_code is None:
        allow_code = transport == "stdio"
    create(allow_code, root).run(transport)  # type: ignore[arg-type]
