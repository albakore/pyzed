"""Icons from the bundled Lucide font (https://lucide.dev, ISC License).

    pz.icon("folder", size=16, color="#74ade8")

Any of the ~2000 Lucide names works; ``icons.names()`` lists them, ``icons.search("user")``
finds them by name and tag, and ``ui.IconPicker`` lets the user pick one.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

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


def tags(name: str) -> List[str]:
    """Returns the search tags of an icon (``tags("user")`` is ``["person", "account", "contact"]``)."""
    from ._lucide_tags import TAGS

    text = TAGS.get(name)
    return text.split(", ") if text else []


#: Groups of icons for browsing, each matched by the words of the icon's name and tags.
CATEGORIES: Dict[str, Tuple[str, ...]] = {
    "arrows": ("arrow", "arrows", "chevron", "chevrons", "move", "corner", "undo", "redo", "refresh", "rotate",
               "direction"),
    "text": ("text", "type", "heading", "pilcrow", "align", "bold", "italic", "underline", "strikethrough", "quote",
             "letter", "font", "formatting", "list"),
    "files": ("file", "files", "folder", "folders", "archive", "document", "save", "clipboard", "paperclip"),
    "layout": ("layout", "panel", "columns", "rows", "grid", "table", "sidebar", "window", "frame", "kanban"),
    "media": ("play", "pause", "music", "video", "camera", "image", "film", "mic", "volume", "speaker", "headphones",
              "audio", "radio", "tv", "podcast"),
    "communication": ("mail", "message", "messages", "phone", "send", "chat", "inbox", "bell", "megaphone",
                      "notification", "email"),
    "people": ("user", "users", "person", "people", "baby", "account", "smile", "hand", "face"),
    "devices": ("monitor", "laptop", "smartphone", "tablet", "keyboard", "mouse", "printer", "cpu", "drive", "server",
                "battery", "plug", "usb", "wifi", "bluetooth", "device", "computer"),
    "development": ("code", "terminal", "git", "bug", "braces", "brackets", "database", "binary", "variable",
                    "function", "regex", "webhook", "programming", "developer"),
    "shapes": ("circle", "square", "triangle", "hexagon", "pentagon", "octagon", "diamond", "shape", "shapes"),
    "weather": ("sun", "moon", "cloud", "rain", "snow", "wind", "thermometer", "umbrella", "weather", "storm"),
    "commerce": ("shopping", "cart", "card", "wallet", "dollar", "euro", "coins", "banknote", "receipt", "store",
                 "money", "payment", "gift", "currency"),
    "maps": ("map", "navigation", "compass", "pin", "globe", "route", "location", "plane", "car", "bus", "train",
             "bike", "ship", "travel"),
    "status": ("check", "alert", "info", "help", "ban", "shield", "lock", "unlock", "loader", "warning", "error",
               "success", "security"),
}

_words_cache: Dict[str, frozenset] = {}


def _words(name: str) -> frozenset:
    words = _words_cache.get(name)
    if words is None:
        words = frozenset(name.split("-")) | frozenset(w for tag in tags(name) for w in tag.split())
        _words_cache[name] = words
    return words


def category(key: str, among: Optional[Iterable[str]] = None) -> List[str]:
    """Returns the icons of category ``key`` (one of ``CATEGORIES``), sorted. An icon can be in several."""
    keywords = frozenset(CATEGORIES[key])
    return [n for n in (sorted(CODEPOINTS) if among is None else among) if _words(n) & keywords]


def search(query: str, among: Optional[Iterable[str]] = None) -> List[str]:
    """Returns the icons matching ``query`` by name and tag, best first.

    Every word of the query must appear in the name or the tags (``"arrow up"``, ``"person"``). Exact names
    come first, then names that start with the query, names with every word, and icons found by their tags.
    """
    pool = sorted(CODEPOINTS) if among is None else list(among)
    words = query.lower().replace("-", " ").split()
    if not words:
        return pool
    joined = "-".join(words)
    scored = []
    for name in pool:
        if name == joined:
            rank = 0
        elif name.startswith(joined):
            rank = 1
        elif all(w in name for w in words):
            rank = 2
        else:
            haystack = name + " " + " ".join(tags(name))
            if not all(w in haystack for w in words):
                continue
            rank = 3
        scored.append((rank, len(name), name))
    return [name for _rank, _length, name in sorted(scored)]


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
