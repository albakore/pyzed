"""The Pyzed MCP server: tools, resources and prompts for AI agents (stdio transport).

Needs the MCP Python SDK (``pip install "pyzed-ui[mcp]"``); works with ``mcp`` 1.x (``FastMCP``)
and 2.x (``MCPServer``).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from . import knowledge, scaffold, validate

try:  # mcp 2.x
    from mcp.server.mcpserver import Image, MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server, Image  # type: ignore

INSTRUCTIONS = """\
Pyzed builds native desktop GUIs in Python, rendered by Iced (Rust), with components that look like
the Zed editor (`import pyzed as pz`, `from pyzed import ui`).
Start with get_guide("overview") and get_guide("best-practices"). Look names up with
list_components / describe_component / search_icons / list_themes instead of guessing, generate
skeletons with new_app / new_component / new_form, then check your code with validate_code
(validate_form for .pzform files) and look at it with screenshot. read_docs and read_example
return the official documentation and example apps."""


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=repr)


def create() -> Any:
    """Builds the server with every tool, resource and prompt registered."""
    try:
        server = _Server("pyzed", instructions=INSTRUCTIONS, version=knowledge.version())
    except TypeError:  # mcp 1.x takes no version
        server = _Server("pyzed", instructions=INSTRUCTIONS)

    # -- knowledge -------------------------------------------------------------------------------------
    @server.tool()
    def get_guide(topic: str = "overview") -> str:
        """How Pyzed works. topic: "overview" (architecture, API layers, components, designer, CLI)
        or "best-practices" (rules for views, state, components, styling, layout and testing)."""
        return knowledge.guide(topic)

    @server.tool()
    def list_components(kind: str = "all", query: str = "", category: str = "") -> str:
        """Lists Pyzed widgets and components with a one-line summary.

        kind: "widget" (pz.* primitives), "ui" (pz.ui.* Zed-style components), "designer" (the visual
        designer's toolbox types), "component" (pz.Component classes) or "all".
        query filters by name or summary; category keeps one section (e.g. "Layout", "Navigation")."""
        return _json(knowledge.list_components(kind, query, category))

    @server.tool()
    def describe_component(name: str) -> str:
        """The signature, documentation and parameters of a widget or component, or the props and events
        of a designer toolbox type. name: "pz.column", "ui.button", "designer:button" or a bare name."""
        return _json(knowledge.describe_component(name))

    @server.tool()
    def search_icons(query: str = "", limit: int = 50) -> str:
        """Finds bundled Lucide icon names (for icon=... and pz.icon); every word of query must match."""
        return _json(knowledge.search_icons(query, limit))

    @server.tool()
    def list_themes() -> str:
        """The built-in themes and the color tokens styles and components accept ("accent", "panel"...)."""
        return _json(knowledge.list_themes())

    @server.tool()
    def list_docs() -> str:
        """Every page of the official documentation, with the slug read_docs takes."""
        return _json(knowledge.list_docs())

    @server.tool()
    def read_docs(slug: str, lang: str = "en") -> str:
        """The Markdown of a documentation page, e.g. "guides/layout" or "reference/ui". lang: "en" or "es"."""
        return knowledge.read_docs(slug, lang)

    @server.tool()
    def list_examples() -> str:
        """The example apps of the repository (a Zed-like editor, a to-do list, dialogs, canvas...)."""
        return _json(knowledge.list_examples())

    @server.tool()
    def read_example(name: str) -> str:
        """The full source code of an example app (name from list_examples, e.g. "todo")."""
        return knowledge.read_example(name)

    # -- generators ------------------------------------------------------------------------------------
    @server.tool()
    def new_app(title: str = "My App", layout: str = "simple", theme: str = "One Dark",
                width: int = 900, height: int = 600) -> str:
        """The code of a runnable pz.App script. layout: "simple" (a counter to build on) or "workspace"
        (a Zed-like window with sidebar, tabs, status bar and command palette)."""
        return scaffold.app(title, size=(width, height), theme=theme, layout=layout)

    @server.tool()
    def new_component(name: str, description: str = "", props: Optional[List[Dict[str, Any]]] = None,
                      state: Optional[List[Dict[str, Any]]] = None, events: Optional[Dict[str, str]] = None,
                      icon: str = "box", category: str = "Custom") -> str:
        """The skeleton of a reusable pz.Component (it also shows up in the designer's toolbox).

        props / state: lists of {"name", "type"?, "default"?, "doc"?}; events: {"change": "what it means"}.
        Returns the module code and how a view uses it."""
        return _json(scaffold.component(name, description=description, props=props or (), state=state or (),
                                        events=events, icon=icon, category=category))

    @server.tool()
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

    # -- checks ----------------------------------------------------------------------------------------
    @server.tool()
    def validate_code(code: str) -> str:
        """Checks Pyzed code without running it: unknown pz/ui names, wrong keyword arguments, apps without
        view(), components without render(), side effects in view(), lambdas in loops, plus ruff if installed."""
        return _json(validate.check_code(code))

    @server.tool()
    def validate_form(form: str, handlers: str = "") -> str:
        """Validates the JSON of a .pzform (component types, props, events, names, parents) and, when the
        handlers module is given, that it defines every handler the form calls."""
        return _json(validate.check_form(form, handlers))

    @server.tool()
    def screenshot(code: str, width: int = 800, height: int = 600, scale: float = 1.0) -> Any:
        """Runs Pyzed code off-screen (no window, no GPU) and returns a PNG of its UI.

        The code is a script defining a pz.App (pz.run is intercepted) or a top-level preview() function
        that returns a widget. It runs in a separate process with a 60 second limit."""
        from .preview import render

        return Image(data=render(code, size=(width, height), scale=scale), format="png")

    # -- resources -------------------------------------------------------------------------------------
    @server.resource("pyzed://guide", mime_type="text/markdown")
    def guide_resource() -> str:
        """How Pyzed works, for agents."""
        return knowledge.guide("overview")

    @server.resource("pyzed://best-practices", mime_type="text/markdown")
    def best_practices_resource() -> str:
        """Rules for writing good Pyzed apps and components."""
        return knowledge.guide("best-practices")

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

    return server


def main(transport: str = "stdio") -> None:
    """Runs the server (blocks). ``transport`` is ``"stdio"`` (the default) or ``"streamable-http"``."""
    create().run(transport)  # type: ignore[arg-type]
