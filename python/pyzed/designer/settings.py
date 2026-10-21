"""Preferences of the designer's code editor, saved per user.

They live in ``designer.json`` inside the Pyzed config folder (``%APPDATA%\\pyzed`` on Windows,
``~/Library/Application Support/pyzed`` on macOS, ``$XDG_CONFIG_HOME/pyzed`` or ``~/.config/pyzed``
elsewhere; ``$PYZED_CONFIG_DIR`` overrides it).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, Optional


MIN_FONT, MAX_FONT, DEFAULT_FONT = 8.0, 32.0, 14.0
#: Backspace and Delete held down: the wait before they repeat (ms) and their pace (per second).
DEFAULT_REPEAT_DELAY, MAX_REPEAT_DELAY = 500.0, 2000.0
DEFAULT_REPEAT_RATE, MAX_REPEAT_RATE = 20.0, 100.0
CURSOR_SHAPES = ("bar", "block", "underline", "hollow")
#: Line heights, as a multiple of the font size.
LINE_HEIGHTS = {"compact": 1.35, "standard": 1.6, "comfortable": 1.85}


@dataclass
class EditorSettings:
    #: Theme of the code editor; empty to follow the designer's theme.
    theme: str = ""
    #: Font family of the code ("" keeps IBM Plex Mono).
    font_family: str = ""
    font_size: float = DEFAULT_FONT
    tab_size: int = 4
    #: Tab and Enter indent with tab characters instead of spaces.
    hard_tabs: bool = False
    #: Saving a file rewrites its indentation with tabs (``hard_tabs``) or spaces, so they never mix.
    convert_indentation: bool = False
    #: Backspace in leading spaces removes a whole level (off: one space).
    backspace_unindent: bool = True
    #: Holding Backspace or Delete: milliseconds before it repeats (0 keeps the system's).
    repeat_delay: float = DEFAULT_REPEAT_DELAY
    #: Holding Backspace or Delete: deletions per second at most (0 keeps the system's).
    repeat_rate: float = DEFAULT_REPEAT_RATE
    show_whitespace: bool = False
    wrap: bool = False
    line_numbers: bool = True
    highlight_line: bool = True
    #: Show completions while typing (Ctrl+Space always opens them).
    autocomplete: bool = True
    code_lens: bool = True
    #: Show the first problem of a line at its end, like Error Lens.
    inline_diagnostics: bool = True
    #: Run ``ruff format`` on the code when it is applied.
    format_on_apply: bool = False
    #: Typing a bracket or quote inserts its closing pair.
    auto_close: bool = True
    #: Fold chevrons in the gutter (Ctrl+Shift+[ and ] fold and unfold).
    folding: bool = True
    minimap: bool = True
    #: ``"bar"``, ``"block"``, ``"underline"`` or ``"hollow"``.
    cursor_shape: str = "bar"
    cursor_blink: bool = True
    #: Width of the bar cursor, in pixels.
    cursor_width: float = 2.0
    #: ``"compact"``, ``"standard"`` or ``"comfortable"`` (see ``LINE_HEIGHTS``).
    line_height: str = "standard"
    scrollbar: bool = True
    #: Outline the bracket that matches the one next to the cursor.
    match_brackets: bool = True
    #: Highlight the other occurrences of the selected text.
    selection_highlight: bool = True
    ty: bool = True
    ruff: bool = True
    #: Keys changed by the user: action name -> bindings separated by commas (``""``: no key).
    keymap: Dict[str, str] = field(default_factory=dict)

    @property
    def key_repeat(self) -> Dict[str, Optional[float]]:
        """The editor's ``repeat_delay`` and ``repeat_rate`` (``None`` where the system's key repeat stays)."""
        return {"repeat_delay": self.repeat_delay or None, "repeat_rate": self.repeat_rate or None}

    def to_dict(self) -> Dict[str, Any]:
        """Returns the settings as a JSON-ready dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EditorSettings":
        """Builds settings from saved ``data``, keeping defaults for missing or invalid values and clamping
        the tab size, font size and cursor shape to valid ones."""
        out = cls()
        for f in fields(cls):
            if f.name in data:
                default = getattr(out, f.name)
                value = data[f.name]
                try:
                    value = type(default)(value)
                except (TypeError, ValueError):
                    continue
                setattr(out, f.name, value)
        out.tab_size = min(max(out.tab_size, 1), 16)
        out.font_size = min(max(out.font_size, MIN_FONT), MAX_FONT)
        if out.cursor_shape not in CURSOR_SHAPES:
            out.cursor_shape = "bar"
        if out.line_height not in LINE_HEIGHTS:
            out.line_height = "standard"
        out.cursor_width = min(max(out.cursor_width, 1.0), 4.0)
        out.repeat_delay = min(max(out.repeat_delay, 0.0), MAX_REPEAT_DELAY)
        out.repeat_rate = min(max(out.repeat_rate, 0.0), MAX_REPEAT_RATE)
        out.keymap = {k: v for k, v in out.keymap.items() if isinstance(k, str) and isinstance(v, str)}
        return out


def config_dir() -> Path:
    """Returns the folder of the user's Pyzed settings: ``$PYZED_CONFIG_DIR``, or the platform's config folder
    (``%APPDATA%``, ``~/Library/Application Support`` or ``$XDG_CONFIG_HOME``) plus ``pyzed``."""
    if os.environ.get("PYZED_CONFIG_DIR"):
        return Path(os.environ["PYZED_CONFIG_DIR"])
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "pyzed"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "pyzed"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "pyzed"


def settings_path() -> Path:
    """Returns the path of ``designer.json``, which holds the editor and designer settings."""
    return config_dir() / "designer.json"


def _read() -> Dict[str, Any]:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load() -> EditorSettings:
    """Returns the code editor's saved settings (defaults if there are none)."""
    editor = _read().get("editor")
    return EditorSettings.from_dict(editor) if isinstance(editor, dict) else EditorSettings()


def save(settings: EditorSettings, path: Optional[Path] = None) -> Optional[Path]:
    """Writes the settings (keeping other sections of the file); ``None`` if the folder is not writable."""
    path = path or settings_path()
    data = _read()
    data["editor"] = settings.to_dict()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return None
    return path
