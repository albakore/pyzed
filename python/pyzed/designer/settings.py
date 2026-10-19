"""Preferences of the designer's code editor, saved per user.

They live in ``designer.json`` inside the Pyzed config folder (``%APPDATA%\\pyzed`` on Windows,
``~/Library/Application Support/pyzed`` on macOS, ``$XDG_CONFIG_HOME/pyzed`` or ``~/.config/pyzed``
elsewhere; ``$PYZED_CONFIG_DIR`` overrides it).
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict, Optional


MIN_FONT, MAX_FONT, DEFAULT_FONT = 8.0, 32.0, 14.0
CURSOR_SHAPES = ("bar", "block", "underline", "hollow")


@dataclass
class EditorSettings:
    #: Theme of the code editor; empty to follow the designer's theme.
    theme: str = ""
    font_size: float = DEFAULT_FONT
    tab_size: int = 4
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
    ty: bool = True
    ruff: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EditorSettings":
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
        return out


def config_dir() -> Path:
    if os.environ.get("PYZED_CONFIG_DIR"):
        return Path(os.environ["PYZED_CONFIG_DIR"])
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "pyzed"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "pyzed"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "pyzed"


def settings_path() -> Path:
    return config_dir() / "designer.json"


def _read() -> Dict[str, Any]:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load() -> EditorSettings:
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
