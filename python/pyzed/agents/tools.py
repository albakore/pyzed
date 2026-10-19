"""Ready-made tools: what an agent needs to know Pyzed, and to work with files in a project.

``pyzed_tools()`` are the same knowledge tools the Pyzed MCP server offers (components, icons,
themes, docs, generators and checks), without needing the MCP SDK. ``file_tools(root)`` read, search
and write files, never outside ``root``.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .agent import Tool, tool

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build", ".ruff_cache"}
#: Bytes of a file ``read_file`` returns at most.
READ_LIMIT = 200_000


def pyzed_tools() -> List[Tool]:
    """Knowledge, generator and checking tools about Pyzed (no side effects)."""
    from ..mcp import knowledge, scaffold, validate

    @tool(title="Reading a Pyzed guide")
    def get_guide(topic: str = "overview") -> str:
        """How Pyzed works.

        topic: "overview" (architecture, API layers, components, designer) or "best-practices".
        """
        return knowledge.guide(topic)

    @tool(title="Listing components")
    def list_components(kind: str = "all", query: str = "", category: str = "") -> Any:
        """Lists Pyzed widgets and components with a one-line summary.

        kind: "widget" (pz.*), "ui" (pz.ui.*), "designer" (toolbox types of the visual designer), "component" or "all".
        query: filters by name or summary.
        category: keeps one section, e.g. "Layout".
        """
        return knowledge.list_components(kind, query, category)

    @tool(title="Reading a component's reference")
    def describe_component(name: str) -> Any:
        """The signature, documentation and parameters of a widget or component, or the props and events of a
        designer toolbox type.

        name: "pz.column", "ui.button", "designer:button" or a bare name.
        """
        return knowledge.describe_component(name)

    @tool(title="Searching icons")
    def search_icons(query: str = "", limit: int = 40) -> Any:
        """Finds bundled Lucide icon names (for icon=... and pz.icon); every word of query must match."""
        return knowledge.search_icons(query, limit)

    @tool(title="Listing themes")
    def list_themes() -> Any:
        """The built-in themes and the color tokens styles and components accept."""
        return knowledge.list_themes()

    @tool(title="Reading the documentation")
    def read_docs(slug: str, lang: str = "en") -> str:
        """The Markdown of a documentation page, e.g. "guides/layout" or "editor/code-editor".

        slug: the page, as list_docs returns it.
        lang: "en" or "es".
        """
        return knowledge.read_docs(slug, lang)

    @tool(title="Listing the documentation")
    def list_docs() -> Any:
        """Every page of the official documentation, with the slug read_docs takes."""
        return knowledge.list_docs()

    @tool(title="Writing an app skeleton")
    def new_app(title: str = "My App", layout: str = "simple", theme: str = "One Dark") -> str:
        """The code of a runnable pz.App script.

        layout: "simple" (a counter to build on) or "workspace" (a Zed-like window).
        """
        return scaffold.app(title, theme=theme, layout=layout)

    @tool(title="Writing a component skeleton")
    def new_component_code(name: str, description: str = "", props: Optional[List[Any]] = None,
                           events: Optional[Dict[str, Any]] = None) -> Any:
        """The skeleton of a reusable pz.Component written in code (not a designed .pzcomp).

        props: a list of {"name", "type"?, "default"?, "doc"?}.
        events: {"change": "what it means"}.
        """
        return scaffold.component(name, description=description, props=props or (), events=events)

    @tool(title="Checking code")
    def validate_code(code: str) -> Any:
        """Checks Pyzed code without running it: unknown names, wrong keyword arguments, missing view() or
        render(), side effects in view(), lambdas in loops, plus ruff when installed."""
        return validate.check_code(code)

    @tool(title="Checking a form")
    def validate_form(form: str, handlers: str = "") -> Any:
        """Validates the JSON of a .pzform and, when given, that its handlers module defines every handler."""
        return validate.check_form(form, handlers)

    return [get_guide, list_components, describe_component, search_icons, list_themes, read_docs, list_docs,
            new_app, new_component_code, validate_code, validate_form]


def _inside(root: Path, path: str) -> Path:
    """``path`` resolved under ``root``; raises when it points outside it."""
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(f"{path} is outside the project folder")
    return target


def file_tools(root: Path) -> List[Tool]:
    """Tools to list, read, search and write files in ``root`` (and never outside it)."""
    root = Path(root).resolve()

    @tool(title="Listing files")
    def list_files(pattern: str = "*", limit: int = 200) -> Any:
        """Files of the project whose path matches a glob pattern (e.g. "*.pzform", "ui/*.py").

        pattern: matched against the path relative to the project folder.
        """
        out: List[str] = []
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
                continue
            if fnmatch.fnmatch(str(rel), pattern) or fnmatch.fnmatch(path.name, pattern):
                out.append(rel.as_posix())
                if len(out) >= limit:
                    break
        return {"root": str(root), "files": out}

    @tool(title="Reading a file")
    def read_file(path: str) -> str:
        """The text of a file of the project.

        path: relative to the project folder.
        """
        target = _inside(root, path)
        data = target.read_bytes()[:READ_LIMIT]
        return data.decode("utf-8", "replace")

    @tool(title="Searching the project")
    def search_text(text: str, pattern: str = "*.py", limit: int = 60) -> Any:
        """Lines that contain text, in the project files matching pattern."""
        hits: List[str] = []
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file():
                continue
            if not (fnmatch.fnmatch(str(rel), pattern) or fnmatch.fnmatch(path.name, pattern)):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for number, line in enumerate(lines, 1):
                if text in line:
                    hits.append(f"{rel.as_posix()}:{number}: {line.strip()[:200]}")
                    if len(hits) >= limit:
                        return {"matches": hits, "truncated": True}
        return {"matches": hits}

    @tool(writes=True, title="Writing a file")
    def write_file(path: str, content: str) -> str:
        """Creates or replaces a text file of the project with content.

        path: relative to the project folder; folders are created.
        """
        target = _inside(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_text(content, encoding="utf-8")
        return json.dumps({"path": target.relative_to(root).as_posix(), "created": not existed,
                           "bytes": len(content.encode())})

    return [list_files, read_file, search_text, write_file]
