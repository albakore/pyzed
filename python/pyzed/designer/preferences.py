"""The designer's own preferences (theme, language, canvas defaults, panels), saved per user.

They share ``designer.json`` with the code editor's settings (see ``settings``), under
the ``"designer"`` key, so one file holds everything the designer remembers.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import package_managers as _package_managers
from .settings import _read, settings_path

#: Smallest and largest interface scale, and the step of zooming in and out.
UI_SCALE = (0.75, 1.5, 0.05)

#: What the outline's eye can do: hide the control when the form runs, or on the canvas only.
EYE_MODES = ("visible", "editor")

#: Where a panel can be docked.
DOCKS = ("left", "right", "bottom", "top")


def is_place(value: Any) -> bool:
    """Whether ``value`` is a dock, the main window's center ("main") or a window of its own ("window:1"...)."""
    return isinstance(value, str) and (value in DOCKS or value == "main"
                                       or (value.startswith("window:") and value[7:].isdigit()))


@dataclass
class DesignerSettings:
    #: Theme of the designer window ("" keeps the default).
    theme: str = ""
    #: Language of the designer's interface ("" follows the system).
    language: str = ""
    #: Font family of the interface ("" keeps IBM Plex Sans).
    ui_font: str = ""
    #: Size of the whole interface, like a zoom (1.0 is 100%).
    ui_scale: float = 1.0
    show_grid: bool = True
    snap: bool = True
    smart_guides: bool = True
    #: Draw every hidden control dimmed on the canvas. Off, a hidden one (a dialog, a drawer) appears only
    #: while it or something inside it is selected.
    show_all_hidden: bool = False
    #: What the outline's eye does: "visible" turns the control's Visible off (hidden when the form runs and
    #: on the canvas, shown while selected); "editor" hides it on the canvas only (see ``EYE_MODES``).
    outline_eye: str = "visible"
    #: Grid step given to new forms.
    grid: int = 8
    show_toolbar: bool = True
    show_status_bar: bool = True
    #: Draw the window's title bar and buttons in Pyzed (False keeps the system's frame).
    window_frame: bool = True
    #: Platform whose window frame the canvas shows around the form ("" follows this system).
    preview_frame: str = ""
    #: Save the form before running it.
    save_on_run: bool = False
    #: Open the console when a form starts running.
    console_on_run: bool = True
    #: Log every event the running form raises in the console.
    log_events: bool = True
    #: Open a dialog with the error when something fails (it is always in the Logs panel).
    error_dialogs: bool = True
    #: Also write the logs to a file in the config folder (``logs/pyzed-design.log``).
    log_file: bool = True
    #: Open the welcome window (start a project, the example gallery) when the designer starts.
    show_welcome: bool = True
    #: Open projects the user did not create or trust in restricted mode (see ``designer.trust``).
    restricted_mode: bool = True
    #: Look for a new version of the designer once a day (the compiled app updates itself).
    check_updates: bool = True
    #: "stable" (final releases) or "preview" (pre-releases too, like Zed Preview).
    update_channel: str = "stable"
    #: The uv that runs the projects' commands: "auto", "bundled", "system" or "custom" (see ``package_managers``).
    uv_source: str = "auto"
    #: The uv executable when ``uv_source`` is "custom".
    uv_path: str = ""
    #: uv's defaults ("" or False: uv's own): the Python of new projects, the package index instead of PyPI, more
    #: indexes (separated by spaces), pre-releases, offline and how packages go into an environment.
    uv_python: str = ""
    uv_index: str = ""
    uv_extra_index: str = ""
    uv_prerelease: bool = False
    uv_offline: bool = False
    uv_link_mode: str = ""
    recent: List[str] = field(default_factory=list)
    #: Panel id -> dock ("left", "right", "bottom", "top"), the center ("main") or a window ("window:1"...).
    docks: Dict[str, str] = field(default_factory=dict)
    #: The order of the panel tabs (panel ids).
    order: List[str] = field(default_factory=list)
    #: Dock or panel window -> the panel shown in front.
    active: Dict[str, str] = field(default_factory=dict)
    #: Panel window -> {"size": [w, h], "position": [x, y]}.
    windows: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    #: Saved work layouts: name -> a dock layout snapshot (see ``docks.DockLayout.snapshot``).
    layouts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    #: The work layout picked last ("" when none).
    layout_name: str = ""
    #: Panel id -> shown or hidden.
    panels: Dict[str, bool] = field(default_factory=dict)
    #: Dock -> size in pixels (width of side docks, height of top and bottom ones).
    sizes: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Returns the preferences as a JSON-ready dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DesignerSettings":
        """Builds preferences from saved ``data``, keeping defaults for missing or invalid values and clamping
        the grid, docks, sizes and recent files to valid ones."""
        out = cls()
        for f in fields(cls):
            if f.name not in data:
                continue
            default = getattr(out, f.name)
            value = data[f.name]
            if isinstance(default, (dict, list)):
                if isinstance(value, type(default)):
                    setattr(out, f.name, value)
                continue
            try:
                setattr(out, f.name, type(default)(value))
            except (TypeError, ValueError):
                continue
        out.grid = min(max(out.grid, 2), 64)
        if out.outline_eye not in EYE_MODES:
            out.outline_eye = "visible"
        if out.uv_source not in _package_managers.SOURCES:
            out.uv_source = "auto"
        if out.uv_link_mode not in _package_managers.LINK_MODES:
            out.uv_link_mode = ""
        out.ui_scale = min(max(round(out.ui_scale, 2), UI_SCALE[0]), UI_SCALE[1])
        out.docks = {k: v for k, v in out.docks.items() if is_place(v)}
        out.layouts = {str(k): v for k, v in out.layouts.items() if isinstance(v, dict)}
        out.sizes = {k: float(v) for k, v in out.sizes.items() if k in DOCKS and isinstance(v, (int, float))}
        out.recent = [str(p) for p in out.recent][:10]
        return out

    def uv(self) -> _package_managers.UvSettings:
        """The uv settings of these preferences."""
        return _package_managers.UvSettings(
            source=self.uv_source, path=self.uv_path, python=self.uv_python, index_url=self.uv_index,
            extra_index_url=self.uv_extra_index, prerelease=self.uv_prerelease, offline=self.uv_offline,
            link_mode=self.uv_link_mode)

    def remember(self, path: Path) -> None:
        """Puts ``path`` first in the recent files."""
        text = str(Path(path).resolve())
        self.recent = [text] + [p for p in self.recent if p != text][:9]


def load() -> DesignerSettings:
    """Returns the designer's saved preferences (defaults if there are none)."""
    section = _read().get("designer")
    return DesignerSettings.from_dict(section) if isinstance(section, dict) else DesignerSettings()


def save(prefs: DesignerSettings, path: Optional[Path] = None) -> Optional[Path]:
    """Writes the preferences (keeping the editor's section); ``None`` if the folder is not writable."""
    from . import profiles

    path = path or settings_path()
    data = _read()
    data["designer"] = profiles.absorb("designer", prefs.to_dict())  # a project's own settings stay in the project
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return None
    return path
