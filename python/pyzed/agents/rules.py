"""Project rules, like Zed's: instructions a project keeps for every agent in a file at its root
(``AGENTS.md``, ``CLAUDE.md``, ``.rules``...). The first file found is used, in Zed's order, and goes into
the built-in agent's instructions; external agents such as Claude Code read their own.

    from pyzed.agents import rules

    found = rules.find("my-project")
    if found:
        print(found.name, found.text[:80])
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

#: The files that hold a project's rules, in the order Zed looks for them.
RULE_FILES = (".rules", ".cursorrules", ".windsurfrules", ".clinerules", ".github/copilot-instructions.md",
              "AGENT.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md")
#: Rules longer than this are cut (they go into every request).
MAX_CHARS = 20_000

#: What "Create AGENTS.md" writes.
TEMPLATE = """# Rules for AI agents

Instructions every agent reads before working on this project.

- What the app does and who uses it.
- How to run it and its tests (for example `uv run pyzed run`, `uv run pytest`).
- Conventions: names, folders, the language of the texts.
"""


@dataclass
class Rules:
    """A project's rules file: its ``path``, ``name`` (relative to the project) and ``text``."""

    path: Path
    name: str
    text: str


def find(root: Union[str, Path]) -> Optional[Rules]:
    """The rules of the project at ``root``: the first of ``RULE_FILES`` that exists and has text."""
    root = Path(root)
    for name in RULE_FILES:
        path = root / name
        try:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text:
            return Rules(path, name, text[:MAX_CHARS])
    return None


def prompt(found: Optional[Rules]) -> str:
    """The rules as a part of the agent's instructions (``""`` without any)."""
    if found is None:
        return ""
    return (f"The project's rules, from {found.name}; follow them:\n<project_rules>\n{found.text}\n"
            "</project_rules>")


def create(root: Union[str, Path], name: str = "AGENTS.md") -> Path:
    """Creates the rules file ``name`` at ``root`` from ``TEMPLATE`` (an existing one is left as it is)."""
    path = Path(root) / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TEMPLATE, encoding="utf-8")
    return path
