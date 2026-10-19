"""Ready-made tools: what an agent needs to know Pyzed, and to work with files in a project.

``pyzed_tools()`` are the tools of the Pyzed MCP server (components, icons, themes, docs, examples,
generators, checks and screenshots), without needing the MCP SDK. ``file_tools(root)`` read, search
and write files, never outside ``root``.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .agent import Image, Tool, tool

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build", ".ruff_cache"}
#: Bytes of a file ``read_file`` returns at most.
READ_LIMIT = 200_000


def pyzed_tools(*, screenshots: bool = True) -> List[Tool]:
    """Knowledge, generator, checking and screenshot tools about Pyzed (the Pyzed MCP server's tools; they
    change nothing). ``screenshots=False`` leaves out ``screenshot``, which runs the code it is given."""
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

    @tool(title="Listing the examples")
    def list_examples() -> Any:
        """The example apps of Pyzed (a Zed-like editor, a to-do list, dialogs, canvas...) to learn from."""
        return knowledge.list_examples()

    @tool(title="Reading an example")
    def read_example(name: str) -> str:
        """The full source code of an example app.

        name: from list_examples, e.g. "todo".
        """
        return knowledge.read_example(name)

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

    @tool(title="Writing a form")
    def new_form(name: str, title: str = "", controls: Optional[List[Any]] = None, width: float = 480,
                 height: float = 320, theme: str = "One Dark", form_events: Optional[List[Any]] = None) -> Any:
        """A visual designer form as files: the <name>.pzform layout and the <name>.py handlers module.

        controls: [{"type": "input", "name": "email", "props": {"placeholder": "Email"}}, {"type": "button", "name": "send", "props": {"text": "Send"}, "events": ["click"]}] (x/y/width/height optional, stacked when missing).
        form_events: "load", "close", "key", "resize".
        """
        return scaffold.form(name, title=title, width=width, height=height, theme=theme, controls=controls or (),
                             form_events=form_events or ())

    @tool(title="Checking code")
    def validate_code(code: str) -> Any:
        """Checks Pyzed code without running it: unknown names, wrong keyword arguments, missing view() or
        render(), side effects in view(), lambdas in loops, plus ruff when installed."""
        return validate.check_code(code)

    @tool(title="Checking a form")
    def validate_form(form: str, handlers: str = "") -> Any:
        """Validates the JSON of a .pzform and, when given, that its handlers module defines every handler."""
        return validate.check_form(form, handlers)

    @tool(writes=True, title="Taking a screenshot")
    def screenshot(code: str, width: int = 800, height: int = 600) -> Any:
        """Runs Pyzed code off-screen (no window) and returns a picture of its UI, to check how it looks.

        code: a script defining a pz.App (pz.run is intercepted) or a top-level preview() function that returns a widget.
        """
        from ..mcp.preview import render

        return [f"Screenshot of the app at {width}x{height}.", Image(render(code, size=(width, height)), "image/png")]

    out = [get_guide, list_components, describe_component, search_icons, list_themes, read_docs, list_docs,
           list_examples, read_example, new_app, new_component_code, new_form, validate_code, validate_form]
    return out + [screenshot] if screenshots else out


#: Files the file tools never list, read, search or write: keys and credentials a prompt injection could
#: otherwise send to the model's provider. Matched against the file name.
SECRET_FILES = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ecdsa*", "id_ed25519*",
                ".netrc", ".pypirc", ".npmrc", ".git-credentials")


def _secret(path: Path, hidden: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in hidden)


def _inside(root: Path, path: str) -> Path:
    """``path`` resolved under ``root``; raises when it points outside it."""
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(f"{path} is outside the project folder")
    return target


def file_tools(root: Path, hidden: Sequence[str] = SECRET_FILES) -> List[Tool]:
    """Tools to list, read, search and write files in ``root`` (and never outside it). Files whose name
    matches a pattern of ``hidden`` (keys, ``.env``... see ``SECRET_FILES``) are out of their reach."""
    root = Path(root).resolve()

    def target_of(path: str) -> Path:
        target = _inside(root, path)
        if _secret(target, hidden):
            raise PermissionError(f"{path} may hold secrets, so the agent cannot open it")
        return target

    @tool(title="Listing files")
    def list_files(pattern: str = "*", limit: int = 200) -> Any:
        """Files of the project whose path matches a glob pattern (e.g. "*.pzform", "ui/*.py").

        pattern: matched against the path relative to the project folder.
        """
        out: List[str] = []
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file() or _secret(path, hidden):
                continue
            if fnmatch.fnmatch(rel.as_posix(), pattern) or fnmatch.fnmatch(path.name, pattern):
                out.append(rel.as_posix())
                if len(out) >= limit:
                    break
        return {"root": str(root), "files": out}

    @tool(title="Reading a file")
    def read_file(path: str) -> str:
        """The text of a file of the project.

        path: relative to the project folder.
        """
        target = target_of(path)
        data = target.read_bytes()[:READ_LIMIT]
        return data.decode("utf-8", "replace")

    @tool(title="Searching the project")
    def search_text(text: str, pattern: str = "*.py", limit: int = 60) -> Any:
        """Lines that contain text, in the project files matching pattern."""
        hits: List[str] = []
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if any(part in SKIP_DIRS for part in rel.parts) or not path.is_file() or _secret(path, hidden):
                continue
            if not (fnmatch.fnmatch(rel.as_posix(), pattern) or fnmatch.fnmatch(path.name, pattern)):
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
        target = target_of(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        existed = target.exists()
        target.write_bytes(content.encode("utf-8"))  # as given: no newline translation on Windows
        return json.dumps({"path": target.relative_to(root).as_posix(), "created": not existed,
                           "bytes": len(content.encode())})

    return [list_files, read_file, search_text, write_file]
