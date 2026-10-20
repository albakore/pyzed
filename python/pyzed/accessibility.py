"""Accessibility preferences of the operating system.

``system_reduced_motion()`` reads the "reduce motion" setting of the desktop:

* macOS: System Settings → Accessibility → Display → Reduce motion.
* Windows: Settings → Accessibility → Visual effects → Animation effects (off means reduce).
* Linux: GNOME's ``enable-animations`` (Settings → Accessibility → Reduce animation) and
  KDE's animation speed set to instant (``AnimationDurationFactor=0``).

It returns ``None`` when the system has no such setting or it can't be read. Pyzed reads
it when an app starts and turns off animations when it is on (see
``pyzed.set_reduced_motion``); the ``PYZED_REDUCED_MOTION`` environment variable (``1`` or
``0``) overrides it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, List, Optional

__all__ = ["system_reduced_motion"]


def _run(args: List[str]) -> Optional[str]:
    import subprocess  # only when the setting is read

    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=1.5, check=False,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _macos(run: Callable[[List[str]], Optional[str]] = _run) -> Optional[bool]:
    value = run(["defaults", "read", "com.apple.universalaccess", "reduceMotion"])
    return None if value is None else value == "1"


def _windows() -> Optional[bool]:
    try:
        import ctypes

        SPI_GETCLIENTAREAANIMATION = 0x1042
        enabled = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(  # type: ignore[attr-defined]
            SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0
        )
    except (AttributeError, OSError, ImportError):
        return None
    return None if not ok else not enabled.value


def _kde(config_home: Optional[Path] = None) -> Optional[bool]:
    base = config_home or Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        lines = (base / "kdeglobals").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    group = ""
    for line in lines:
        line = line.strip()
        if line.startswith("["):
            group = line
        elif group == "[KDE]" and line.startswith("AnimationDurationFactor="):
            try:
                return float(line.split("=", 1)[1]) == 0
            except ValueError:
                return None
    return None


def _linux(run: Callable[[List[str]], Optional[str]] = _run, config_home: Optional[Path] = None) -> Optional[bool]:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" in desktop:
        found = _kde(config_home)
        if found is not None:
            return found
    value = run(["gsettings", "get", "org.gnome.desktop.interface", "enable-animations"])
    if value in ("true", "false"):
        return value == "false"
    return _kde(config_home)


def system_reduced_motion() -> Optional[bool]:
    """Whether the system asks apps to reduce motion (``None`` if unknown)."""
    if sys.platform == "darwin":
        return _macos()
    if sys.platform == "win32":
        return _windows()
    if sys.platform.startswith("linux"):
        return _linux()
    return None
