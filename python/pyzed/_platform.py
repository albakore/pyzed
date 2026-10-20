"""Quiet, reliable defaults for the platform the app runs on, applied before a window opens.

On Linux the GPU drivers (Mesa) print warnings while the renderer probes the available
backends, such as ``libEGL warning: failed to get driver name for fd -1`` or
``MESA: error: ZINK: failed to choose pdev``. They are harmless (the app picks a working
backend, or falls back to the software renderer), so they are silenced by default.

Under WSL, the Wayland compositor of WSLg drops the connection on some window changes
(maximizing, resizing), which prints ``Io error: Broken pipe (os error 32)``. There
the app uses X11 (through XWayland) instead, which WSLg handles reliably.

Under WSL there is usually no Linux browser, so web pages (sign-ins, the docs) open in Windows' default
browser (``use_windows_browser``). Pages that call back to the app (``http://127.0.0.1:...``) still reach
it, through WSL's localhost forwarding.

Environment variables (all optional):

* ``PYZED_GPU_LOGS=1`` keeps the driver warnings (useful to debug rendering problems).
* ``PYZED_WAYLAND=1`` keeps Wayland under WSL.
* ``BROWSER`` (Python's own variable) picks the browser yourself; under WSL it wins over Windows'.
* Anything you set yourself (``EGL_LOG_LEVEL``, ``MESA_LOG``, ``WAYLAND_DISPLAY``...) is
  left as it is.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from typing import List, Optional

__all__ = ["is_wsl", "prepare", "use_windows_browser", "windows_command"]

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


#: Where Windows' programs are when they are not on the ``PATH`` (``appendWindowsPath=false`` in wsl.conf).
_SYSTEM32 = "/mnt/c/Windows/System32"


def windows_command(name: str) -> Optional[str]:
    """The path of a Windows program (``"rundll32.exe"``...) as seen from WSL, or ``None``."""
    found = shutil.which(name)
    if found:
        return found
    for folder in (_SYSTEM32, _SYSTEM32 + "/WindowsPowerShell/v1.0"):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            return path
    return None


def windows_open_commands(url: str) -> List[List[str]]:
    """The commands that open ``url`` in Windows' default browser from WSL, best first (none opens a console)."""
    commands = []
    rundll = windows_command("rundll32.exe")
    if rundll:  # the URL goes as one argument: no shell parses its & or %
        commands.append([rundll, "url.dll,FileProtocolHandler", url])
    wslview = shutil.which("wslview")
    if wslview:
        commands.append([wslview, url])
    powershell = windows_command("powershell.exe")
    if powershell:
        quoted = "'" + url.replace("'", "''") + "'"
        commands.append([powershell, "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command",
                         f"Start-Process {quoted}"])
    return commands


class WindowsBrowser(webbrowser.BaseBrowser):
    """Opens pages in Windows' default browser from WSL."""

    def __init__(self) -> None:
        super().__init__("windows-default")

    def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        for command in windows_open_commands(url):
            try:
                subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,  # noqa: S603
                                 stderr=subprocess.DEVNULL, start_new_session=True)
                return True
            except OSError:
                continue
        return False


_windows_browser: Optional[WindowsBrowser] = None


def use_windows_browser() -> bool:
    """Under WSL, makes ``webbrowser.open`` use Windows' default browser (unless ``BROWSER`` picks one);
    returns whether it does. Safe to call more than once."""
    global _windows_browser
    if _windows_browser is not None:
        return True
    if not is_wsl() or os.environ.get("BROWSER") or not windows_open_commands("about:blank"):
        return False
    _windows_browser = WindowsBrowser()
    webbrowser.register(_windows_browser.name, None, _windows_browser, preferred=True)
    return True


def prepare() -> List[str]:
    """Adjusts the environment for the native runtime; returns what was changed (for logs/tests)."""
    if not sys.platform.startswith("linux"):
        return []
    changed = []
    if not _flag("PYZED_GPU_LOGS"):
        # Mesa's EGL loader and its own logger ("null" discards "MESA: error: ZINK: ..." lines);
        # both are read when the driver loads.
        for name, value in (("EGL_LOG_LEVEL", "fatal"), ("MESA_LOG", "null")):
            if name not in os.environ:
                os.environ[name] = value
                changed.append(name)
    if use_windows_browser():
        changed.append("browser")
    if is_wsl() and not _flag("PYZED_WAYLAND") and os.environ.get("DISPLAY") and os.environ.get("WAYLAND_DISPLAY"):
        # winit prefers Wayland whenever WAYLAND_DISPLAY is set; without it, it uses X11.
        del os.environ["WAYLAND_DISPLAY"]
        changed.append("WAYLAND_DISPLAY")
    return changed
