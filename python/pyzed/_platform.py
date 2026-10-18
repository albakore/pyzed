"""Quiet, reliable defaults for the platform the app runs on, applied before a window opens.

On Linux the GPU drivers (Mesa) print warnings while the renderer probes the available
backends, such as ``libEGL warning: failed to get driver name for fd -1`` or
``MESA: error: ZINK: failed to choose pdev``. They are harmless (the app picks a working
backend, or falls back to the software renderer), so they are silenced by default.

Under WSL, the Wayland compositor of WSLg drops the connection on some window changes
(maximizing, resizing), which prints ``Io error: Broken pipe (os error 32)``. There
the app uses X11 (through XWayland) instead, which WSLg handles reliably.

Environment variables (all optional):

* ``PYZED_GPU_LOGS=1`` keeps the driver warnings (useful to debug rendering problems).
* ``PYZED_WAYLAND=1`` keeps Wayland under WSL.
* Anything you set yourself (``EGL_LOG_LEVEL``, ``MESA_LOG``, ``WAYLAND_DISPLAY``...) is
  left as it is.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

__all__ = ["is_wsl", "prepare"]

_TRUE = {"1", "true", "yes", "on"}


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE


def is_wsl(release: Optional[str] = None) -> bool:
    """Whether this is Linux running under the Windows Subsystem for Linux."""
    if not sys.platform.startswith("linux"):
        return False
    if os.environ.get("WSL_DISTRO_NAME") or os.environ.get("WSL_INTEROP"):
        return True
    if release is None:
        try:
            with open("/proc/sys/kernel/osrelease", encoding="utf-8") as f:
                release = f.read()
        except OSError:
            return False
    return "microsoft" in release.lower()


def prepare() -> List[str]:
    """Adjusts the environment for the native runtime; returns what was changed (for logs/tests)."""
    if not sys.platform.startswith("linux"):
        return []
    changed = []
    if not _flag("PYZED_GPU_LOGS"):
        # Mesa's EGL loader and its own logger; both are read when the driver loads.
        for name, value in (("EGL_LOG_LEVEL", "fatal"), ("MESA_LOG", "silent")):
            if name not in os.environ:
                os.environ[name] = value
                changed.append(name)
    if is_wsl() and not _flag("PYZED_WAYLAND") and os.environ.get("DISPLAY") and os.environ.get("WAYLAND_DISPLAY"):
        # winit prefers Wayland whenever WAYLAND_DISPLAY is set; without it, it uses X11.
        del os.environ["WAYLAND_DISPLAY"]
        changed.append("WAYLAND_DISPLAY")
    return changed
