"""Device profiles: one app for desktops, touch panels, car displays, phones, kiosks and TVs.

A profile says how the device is used (touch or mouse, a pointer or none, arrow keys and
remotes, one fullscreen app or windows) and how fast it draws. Pyzed picks one when the app
starts and fills in the window options and the rendering settings the app leaves at their
defaults, so the same code runs on a laptop and on a dashboard::

    class Dashboard(pz.App):
        device = "automotive"          # or PYZED_DEVICE=automotive, or pyproject.toml
        design_size = (1920, 720)      # laid out for this screen, scaled to the real one

The built-in profiles are ``desktop``, ``touch``, ``automotive``, ``mobile``, ``kiosk`` and
``tv`` (see ``PROFILES``). The profile in use comes from, first to last:

1. ``App.device``: a name or a ``pz.Device``;
2. the ``PYZED_DEVICE`` environment variable;
3. ``device = "..."`` in ``[tool.pyzed.platform.<system>]`` (``linux``, ``windows``,
   ``macos``, ``android``) of the project's ``pyproject.toml``, then in ``[tool.pyzed]``;
4. the system: ``mobile`` on Android, ``desktop`` elsewhere.

``[tool.pyzed.device.<name>]`` defines a profile or changes a built-in one; ``extends`` names
the profile it starts from::

    [tool.pyzed]
    device = "dashboard"

    [tool.pyzed.device.dashboard]
    extends = "automotive"
    design_size = [1920, 720]
    quality = "medium"

Styles can ask about the device with media queries: ``pz.media("pointer: coarse")`` (touch),
``pz.media("device: tv")`` or ``"@(pointer: coarse)"`` in a stylesheet.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, fields, replace
from typing import Any, Dict, Mapping, Optional, Tuple, Union

__all__ = ["Device", "PROFILES", "QUALITY", "STRETCH", "device", "set_device", "find"]

#: How ``design_size`` meets the real window: ``"expand"`` scales the view so the design fits and lets
#: it grow into the space left; ``"fit"`` scales it and keeps the design's size, centered, with bars
#: around it; ``"none"`` ignores ``design_size``.
STRETCH = ("expand", "fit", "none")

#: Rendering defaults of each quality level, applied to the settings the project leaves at ``"auto"``.
QUALITY: Dict[str, Dict[str, Any]] = {
    "high": {},
    "medium": {"antialiasing": "2x", "max_fps": 60, "background_fps": 10},
    "low": {"antialiasing": "off", "max_fps": 30, "background_fps": 0, "memory": "low", "power": "low"},
}


@dataclass(frozen=True)
class Device:
    """How a device is used and drawn on (see ``pyzed.devices``)."""

    name: str = "desktop"
    #: The screen is touched more than clicked: ``pz.media("pointer: coarse")`` is true.
    touch: bool = False
    #: Whether there is a pointer to show; ``False`` hides it over the windows.
    pointer: bool = True
    #: One fullscreen app the user cannot close (see ``Window.kiosk``).
    kiosk: bool = False
    #: Windows open fullscreen.
    fullscreen: bool = False
    #: The arrow keys move the focus between controls (remotes, rotary knobs, steering wheel pads).
    arrow_focus: bool = False
    #: Interface scale of the windows that leave ``scale`` at 1.
    scale: float = 1.0
    #: The smallest comfortable size of a control in logical pixels (44 to 64 on touch screens);
    #: components read it with ``pz.device().min_target``.
    min_target: float = 24.0
    #: The window size the app was designed for; ``None`` uses the real size as it is.
    design_size: Optional[Tuple[float, float]] = None
    #: How ``design_size`` meets the real window (see ``STRETCH``).
    stretch: str = "expand"
    #: ``"high"``, ``"medium"`` or ``"low"``: rendering defaults for slower hardware (see ``QUALITY``).
    quality: str = "high"
    #: ``True`` turns animations off, ``False`` keeps them, ``None`` follows the system.
    reduced_motion: Optional[bool] = None
    #: Rendering settings (``pz.Rendering`` fields) on top of the quality level.
    rendering: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.stretch not in STRETCH:
            raise ValueError(f"stretch must be one of {', '.join(STRETCH)}, not {self.stretch!r}")
        if self.quality not in QUALITY:
            raise ValueError(f"quality must be one of {', '.join(QUALITY)}, not {self.quality!r}")
        if self.design_size is not None:
            width, height = (float(v) for v in self.design_size)
            if width <= 0 or height <= 0:
                raise ValueError(f"design_size must be positive, not {self.design_size!r}")
            object.__setattr__(self, "design_size", (width, height))
        if not self.scale > 0:
            raise ValueError(f"scale must be positive, not {self.scale!r}")
        object.__setattr__(self, "rendering", dict(self.rendering))

    def replace(self, **changes: Any) -> "Device":
        """A copy with some fields changed: ``pz.devices.PROFILES["tv"].replace(scale=1.5)``."""
        return replace(self, **changes)

    def window_defaults(self, main: bool) -> Dict[str, Any]:
        """The window options this profile gives a window that leaves them at their defaults."""
        out: Dict[str, Any] = {}
        if self.scale != 1.0:
            out["scale"] = self.scale
        if not self.pointer:
            out["hide_cursor"] = True
        if main:
            if self.kiosk:
                out["kiosk"] = True
            if self.fullscreen:
                out["fullscreen"] = True
            if self.arrow_focus:
                out["arrow_focus"] = True
            if self.design_size is not None:
                out["design_size"] = self.design_size
                out["stretch"] = self.stretch
        return out

    def tune(self, rendering: Any) -> Any:
        """``rendering`` (a ``pz.Rendering``) with the quality level and ``self.rendering`` filling in
        the settings it leaves at their defaults."""
        from .rendering import Rendering

        defaults = Rendering()
        changes = {**QUALITY[self.quality], **self.rendering}
        out = replace(rendering)
        for name, value in changes.items():
            if getattr(out, name) == getattr(defaults, name):
                setattr(out, name, value)
        out.__post_init__()
        return out


PROFILES: Dict[str, Device] = {
    "desktop": Device(),
    "touch": Device("touch", touch=True, min_target=44.0, scale=1.15),
    "automotive": Device("automotive", touch=True, pointer=False, kiosk=True, fullscreen=True,
                         arrow_focus=True, min_target=64.0, scale=1.25, quality="medium",
                         rendering={"background_fps": 0}),
    "mobile": Device("mobile", touch=True, pointer=False, fullscreen=True, min_target=48.0, quality="medium"),
    "kiosk": Device("kiosk", touch=True, kiosk=True, fullscreen=True, min_target=48.0, scale=1.15,
                    rendering={"background_fps": 0}),
    "tv": Device("tv", pointer=False, fullscreen=True, arrow_focus=True, scale=2.0, min_target=48.0,
                 quality="medium"),
}

_FIELDS = {f.name for f in fields(Device)} - {"name"}

_current: Optional[Device] = None


def _system() -> str:
    if hasattr(sys, "getandroidapilevel") or "ANDROID_ROOT" in os.environ:
        return "android"
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def _from_table(name: str, table: Mapping[str, Any], profiles: Mapping[str, Device]) -> Device:
    base = table.get("extends", name if name in profiles else "desktop")
    if base not in profiles:
        raise ValueError(f"[tool.pyzed.device.{name}] extends {base!r}, which is not a profile")
    changes = {key: value for key, value in table.items() if key in _FIELDS}
    if isinstance(changes.get("design_size"), list):
        changes["design_size"] = tuple(changes["design_size"])
    return profiles[base].replace(name=name, **changes)


def _tool(start: Any = None) -> Dict[str, Any]:
    """The ``[tool.pyzed]`` table of the project's ``pyproject.toml`` (empty when there is none)."""
    from pathlib import Path

    from .project import _loads_toml
    from .rendering import _pyproject

    starts = [Path(start)] if start is not None else [Path.cwd()]
    if start is None and sys.argv and sys.argv[0]:
        starts.append(Path(sys.argv[0]).resolve().parent)
    for folder in starts:
        file = _pyproject(folder.resolve() if folder.exists() else folder)
        if file is None:
            continue
        try:
            tool = _loads_toml(file.read_text(encoding="utf-8")).get("tool", {}).get("pyzed")
        except (OSError, ValueError):
            continue
        if isinstance(tool, dict):
            return tool
    return {}


def find(choice: Union[str, Device, None] = None, *, tool: Optional[Mapping[str, Any]] = None,
         environ: Optional[Mapping[str, str]] = None, system: Optional[str] = None) -> Device:
    """The profile for ``choice`` (``App.device``), else ``PYZED_DEVICE``, the project's
    ``pyproject.toml`` or the system (see ``pyzed.devices``)."""
    if isinstance(choice, Device):
        return choice
    environ = os.environ if environ is None else environ
    tool = _tool() if tool is None else tool
    system = system or _system()
    profiles = dict(PROFILES)
    custom = tool.get("device") if isinstance(tool.get("device"), dict) else {}
    for name, table in custom.items():
        if isinstance(table, dict):
            profiles[name] = _from_table(name, table, profiles)
    platform = tool.get("platform", {}).get(system, {}) if isinstance(tool.get("platform"), dict) else {}
    named = tool.get("device") if isinstance(tool.get("device"), str) else None
    name = (choice or environ.get("PYZED_DEVICE", "").strip() or platform.get("device") or named
            or ("mobile" if system == "android" else "desktop"))
    if name not in profiles:
        raise ValueError(f"unknown device {name!r}: use one of {', '.join(profiles)} or define "
                         f"[tool.pyzed.device.{name}] in pyproject.toml")
    return profiles[name]


def device() -> Device:
    """The profile the app runs with (``desktop`` before ``pz.run`` picks one)."""
    return _current or PROFILES["desktop"]


def set_device(choice: Union[str, Device, None]) -> Device:
    """Uses a profile from now on (``None`` picks one again as ``pz.run`` does); returns it."""
    global _current
    _current = None if choice is None else find(choice)
    return device()


def _user_set(window: Any, name: str) -> bool:
    """Whether the app's own class (or the instance) sets ``name``, not Pyzed's ``Window``/``App``."""
    if name in getattr(window, "__dict__", {}):
        return True
    for klass in type(window).__mro__:
        if klass.__module__.startswith("pyzed.") and klass.__module__ != "pyzed.devices":
            break
        if name in klass.__dict__:
            return True
    return False


def _apply_window(window: Any) -> None:
    """Gives ``window`` the options of the current profile it leaves at their defaults (once)."""
    if window.__dict__.get("_pyzed_device_applied"):
        return
    window.__dict__["_pyzed_device_applied"] = True
    app = getattr(window, "app", None)
    main = app is None or app is window
    defaults = device().window_defaults(main)
    mine = {name for name in [*defaults, "scale"] if _user_set(window, name)}
    for name, value in defaults.items():
        if name not in mine:
            setattr(window, name, value)
    if getattr(window, "design_size", None) and "scale" not in mine:
        window.scale = 1.0  # the design's fit is the scale


def _start(app: Any) -> Any:
    """Picks the profile for ``app`` (called by ``pz.run``); returns the rendering settings to apply."""
    global _current
    from . import rendering as _rendering

    choice = getattr(app, "device", None)
    # Pyzed's own apps (the designer) stay on the desktop profile unless they ask
    own = (app if isinstance(app, type) else type(app)).__module__.startswith("pyzed.")
    _current = PROFILES["desktop"] if own and choice is None else find(choice)
    if _current.reduced_motion is not None and "PYZED_REDUCED_MOTION" not in os.environ:
        from .animation import set_reduced_motion

        set_reduced_motion(_current.reduced_motion)
    return _current.tune(getattr(app, "rendering", None) or _rendering.find())
