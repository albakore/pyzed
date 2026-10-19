"""Icons from the bundled Lucide font (https://lucide.dev, ISC License).

    pz.icon("folder", size=16, color="#74ade8")

Any of the ~2000 Lucide names works; ``icons.names()`` lists them.
"""

from __future__ import annotations

from typing import List, Optional

from . import _core
from ._lucide import CODEPOINTS


def glyph(name: str) -> str:
    """Returns the character for a Lucide icon name (usable in any text with font="icons")."""
    try:
        return chr(CODEPOINTS[name])
    except KeyError:
        raise ValueError(f"unknown icon {name!r}; see pyzed.icons.names()") from None


def names() -> List[str]:
    """Returns every bundled Lucide icon name, sorted."""
    return sorted(CODEPOINTS)


def icon(name: str, *, size: float = 16, color: Optional[str] = None) -> _core.Widget:
    """An icon widget. ``color`` defaults to the surrounding text color."""
    return _core.text(glyph(name), size=size, color=color, font="icons", line_height=1.0, wrap=False)


# File-type icons used by the project panel and tabs.
_EXTENSIONS = {
    "py": ("file-code", "#3572a5"),
    "rs": ("file-code", "#dea584"),
    "js": ("file-code", "#f1e05a"),
    "ts": ("file-code", "#3178c6"),
    "tsx": ("file-code", "#3178c6"),
    "jsx": ("file-code", "#f1e05a"),
    "go": ("file-code", "#00add8"),
    "c": ("file-code", "#a8b9cc"),
    "h": ("file-code", "#a8b9cc"),
    "cpp": ("file-code", "#f34b7d"),
    "html": ("file-code", "#e34c26"),
    "css": ("file-code", "#563d7c"),
    "json": ("braces", "#cbcb41"),
    "toml": ("file-cog", "#9c4221"),
    "yaml": ("file-cog", "#cb171e"),
    "yml": ("file-cog", "#cb171e"),
    "md": ("file-text", "#519aba"),
    "txt": ("file-text", None),
    "lock": ("lock", None),
    "png": ("file-image", "#a074c4"),
    "svg": ("file-image", "#ffb13b"),
    "sh": ("terminal", "#89e051"),
}


def for_file(name: str):
    """Returns ``(icon_name, color_or_None)`` for a file name."""
    lower = name.lower()
    if lower in ("license", "license.md", "license.txt"):
        return ("scale", None)
    if lower.startswith(".git"):
        return ("git-branch", "#f05133")
    if lower == "dockerfile":
        return ("container", "#2496ed")
    ext = lower.rsplit(".", 1)[-1] if "." in lower else ""
    return _EXTENSIONS.get(ext, ("file", None))


LANGUAGES = {
    "py": "Python",
    "rs": "Rust",
    "js": "JavaScript",
    "ts": "TypeScript",
    "tsx": "TSX",
    "go": "Go",
    "md": "Markdown",
    "toml": "TOML",
    "json": "JSON",
    "yaml": "YAML",
    "yml": "YAML",
    "html": "HTML",
    "css": "CSS",
    "sh": "Shell Script",
    "c": "C",
    "cpp": "C++",
    "txt": "Plain Text",
}


def language_for(name: str) -> str:
    """Returns the language name for a file name from its extension (``"Plain Text"`` if unknown)."""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else "txt"
    return LANGUAGES.get(ext, "Plain Text")
