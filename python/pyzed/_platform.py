"""Quiet, reliable defaults for the platform the app runs on, applied before a window opens.

On Linux the GPU drivers (Mesa) print warnings while the renderer probes the available
backends, such as ``libEGL warning: failed to get driver name for fd -1`` or
``MESA: error: ZINK: failed to choose pdev``. They are harmless (the app picks a working
backend, or falls back to the software renderer), so they are silenced by default.

Under WSL, the Wayland compositor of WSLg drops the connection on some window changes
(maximizing, resizing), which prints ``Io error: Broken pipe (os error 32)``. There
the app uses X11 (through XWayland) instead, which WSLg handles reliably.

Under WSL, windows usually open as native Windows windows instead, through Windows' own Python (see
``pyzed._wsl_windows``); X11 is for when they open through WSLg (``PYZED_WINDOWS=0``, or no Python on Windows).

Under WSL there is usually no Linux browser, so web pages (sign-ins, the docs) open in Windows' default
browser (``use_windows_browser``). Pages that call back to the app (``http://127.0.0.1:...``) still reach
it, through WSL's localhost forwarding.

Apps opened from the desktop's menu (not from a terminal) do not get the ``PATH`` the user's shell sets up
in ``~/.bashrc``, ``~/.zshrc``... so programs installed with nvm, volta, fnm or in ``~/.local/bin`` (Node's
``npx``, ``claude``, ``uv``...) are not found. ``user_path`` asks the user's shell for its ``PATH`` once and
adds the folders where those tools usually are; ``which`` and ``use_user_path`` use it.

Environment variables (all optional):

* ``PYZED_GPU_LOGS=1`` keeps the driver warnings (useful to debug rendering problems).
* ``PYZED_WAYLAND=1`` keeps Wayland under WSL.
* ``BROWSER`` (Python's own variable) picks the browser yourself; under WSL it wins over Windows'.
* Anything you set yourself (``EGL_LOG_LEVEL``, ``MESA_LOG``, ``WAYLAND_DISPLAY``...) is
  left as it is.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

__all__ = ["browser_env", "desktop_notification_command", "is_wsl", "notify", "prepare", "use_user_path",
           "use_windows_browser", "user_path", "which", "windows_command"]

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


def browser_env() -> Dict[str, str]:
    """Under WSL, a ``BROWSER`` variable for programs Pyzed starts (external agents that sign in through the
    browser), so they open Windows' default browser too; empty elsewhere or when ``BROWSER`` is set."""
    if not is_wsl() or os.environ.get("BROWSER"):
        return {}
    if shutil.which("wslview"):
        return {"BROWSER": "wslview"}
    rundll = windows_command("rundll32.exe")
    return {"BROWSER": f"{shlex.quote(rundll)} url.dll,FileProtocolHandler %s"} if rundll else {}


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

# A balloon from the notification area, with nothing to install (Windows, and Windows from WSL).
_WINDOWS_TOAST = (
    "Add-Type -AssemblyName System.Windows.Forms; $n = New-Object System.Windows.Forms.NotifyIcon; "
    "$n.Icon = [System.Drawing.SystemIcons]::Information; $n.Visible = $true; "
    "$n.ShowBalloonTip(8000, $env:PYZED_TITLE, $env:PYZED_BODY, 'Info'); Start-Sleep -Seconds 9; $n.Dispose()")


def desktop_notification_command(title: str, body: str) -> Optional[List[str]]:
    """The command that shows a desktop notification (``None`` when there is no way to): ``osascript`` on
    macOS, ``notify-send`` on Linux, PowerShell on Windows and under WSL. Under PowerShell the texts go in
    the ``PYZED_TITLE`` and ``PYZED_BODY`` variables, never in the script."""
    if sys.platform == "darwin":
        quote = lambda s: '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'  # noqa: E731
        return ["osascript", "-e", f"display notification {quote(body)} with title {quote(title)}"]
    if sys.platform == "win32":
        return ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", _WINDOWS_TOAST]
    found = shutil.which("notify-send")
    if found:
        return [found, "--app-name=Pyzed", title, body]
    shell = windows_command("powershell.exe") if is_wsl() else None
    if shell:
        return [shell, "-NoProfile", "-WindowStyle", "Hidden", "-Command", _WINDOWS_TOAST]
    return None


def notify(title: str, body: str) -> bool:
    """Shows a desktop notification, without waiting for it; whether one could be shown."""
    command = desktop_notification_command(title, body)
    if command is None:
        return False
    env = {**os.environ, "PYZED_TITLE": title, "PYZED_BODY": body}
    if "WSLENV" in os.environ or is_wsl():  # hand the two variables over to the Windows side
        env["WSLENV"] = ":".join(filter(None, [os.environ.get("WSLENV", ""), "PYZED_TITLE", "PYZED_BODY"]))
    try:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,  # noqa: S603
                         stderr=subprocess.DEVNULL, env=env, start_new_session=sys.platform != "win32")
    except OSError:
        return False
    return True


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


# -- the user's PATH ----------------------------------------------------------------------------------------

_PATH_LOCK = threading.Lock()
_user_path: Optional[str] = None
_MARK = "__PYZED_PATH__"


def _shell_path() -> List[str]:
    """The ``PATH`` the user's login shell sets up (``[]`` on Windows, or when it cannot be read)."""
    if os.name == "nt":
        return []
    shell = os.environ.get("SHELL") or ("/bin/zsh" if sys.platform == "darwin" else "/bin/bash")
    if not os.path.isfile(shell):
        return []
    show = "string join : $PATH" if os.path.basename(shell) == "fish" else 'printf %s "$PATH"'
    try:
        done = subprocess.run([shell, "-ilc", f"printf {_MARK}; {show}; printf {_MARK}"], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=8, start_new_session=True)
    except (OSError, subprocess.SubprocessError):
        return []
    found = re.search(f"{_MARK}(.*?){_MARK}", done.stdout.decode("utf-8", "replace"), re.S)
    return [part for part in found.group(1).strip().split(os.pathsep) if part] if found else []


def _version_key(path: Path) -> List[int]:
    return [int(n) for n in re.findall(r"\d+", path.name)[:3]]


def tool_dirs(home: Optional[Path] = None) -> List[str]:
    """Folders where Node.js, Claude Code, uv and other command-line tools are usually installed."""
    home = Path(home) if home is not None else Path.home()
    found: List[Path] = []
    if os.name == "nt":
        env = os.environ
        found += [Path(env.get("APPDATA") or home / "AppData" / "Roaming") / "npm",
                  Path(env.get("ProgramFiles") or "C:/Program Files") / "nodejs",
                  Path(env.get("LOCALAPPDATA") or home / "AppData" / "Local") / "Programs" / "nodejs"]
        if env.get("NVM_SYMLINK"):
            found.append(Path(env["NVM_SYMLINK"]))
        found += [home / ".local" / "bin", home / ".volta" / "bin", home / ".bun" / "bin", home / ".cargo" / "bin"]
    else:
        nvm = Path(os.environ.get("NVM_DIR") or home / ".nvm") / "versions" / "node"
        if nvm.is_dir():  # the newest Node first
            found += [v / "bin" for v in sorted(nvm.iterdir(), key=_version_key, reverse=True)]
        for fnm in (home / ".local" / "share" / "fnm", home / ".fnm"):
            found.append(fnm / "aliases" / "default" / "bin")
        found += [home / ".volta" / "bin", home / ".asdf" / "shims", home / ".local" / "share" / "mise" / "shims",
                  home / "n" / "bin", home / ".npm-global" / "bin", home / ".bun" / "bin", home / ".local" / "bin",
                  home / ".cargo" / "bin", Path("/opt/homebrew/bin"), Path("/usr/local/bin"), Path("/snap/bin")]
    return [str(p) for p in found if p.is_dir()]


def user_path() -> str:
    """This process's ``PATH`` plus the user's shell ``PATH`` and the usual tool folders (worked out once)."""
    global _user_path
    with _PATH_LOCK:
        if _user_path is None:
            parts: List[str] = []
            for part in [*os.environ.get("PATH", "").split(os.pathsep), *_shell_path(), *tool_dirs()]:
                if part and part not in parts:
                    parts.append(part)
            _user_path = os.pathsep.join(parts)
        return _user_path


def use_user_path() -> None:
    """Makes ``user_path`` this process's ``PATH``, so every program the app starts finds the user's tools."""
    os.environ["PATH"] = user_path()


def process_age() -> Optional[float]:
    """Seconds since this process started (``None`` where that can't be told). Next to the time the app's own code
    took, it shows how long went before it ran: loading the app's files, an antivirus scanning them..."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32")
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)] * 4]
            times = [wintypes.FILETIME() for _ in range(4)]  # created, exited, kernel, user
            if not kernel32.GetProcessTimes(kernel32.GetCurrentProcess(), *(ctypes.byref(t) for t in times)):
                return None
            now = wintypes.FILETIME()
            kernel32.GetSystemTimeAsFileTime(ctypes.byref(now))

            def ticks(value: "wintypes.FILETIME") -> int:  # hundreds of nanoseconds
                return (value.dwHighDateTime << 32) | value.dwLowDateTime

            return (ticks(now) - ticks(times[0])) / 1e7
        if sys.platform.startswith("linux"):
            # the 22nd field of /proc/self/stat: when the process started, in clock ticks after boot
            started = int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19])
            uptime = float(Path("/proc/uptime").read_text().split()[0])
            return uptime - started / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError, AttributeError):
        return None
    return None


#: A process found by ``descendants``: its id and when it started (Windows reuses the ids of ended processes).
Process = Tuple[int, int]


def descendants(pid: Optional[int] = None, *, skip: Tuple[int, ...] = ()) -> List[Process]:
    """The processes ``pid`` (this one by default) started, the ones they started, and so on (Windows only; ``[]``
    elsewhere). ``skip`` leaves out those processes and what they started.

    Windows does not stop what a process started when it ends, and a process whose parent ended can no longer be
    found from it: look them up before stopping the parents, and ``stop`` what is left afterwards.
    """
    if sys.platform != "win32":
        return []
    try:
        table = _windows_processes()
    except (OSError, AttributeError, ValueError):
        return []
    children: Dict[int, List[int]] = {}
    for child, parent in table:
        if child != parent:
            children.setdefault(parent, []).append(child)
    found: List[Process] = []
    seen = set(skip)
    todo = [pid or os.getpid()]
    while todo:
        parent = todo.pop()
        born = _windows_started(parent)
        for child in children.get(parent, []):
            started = _windows_started(child)
            # a process older than its "parent" got the id of an ended one: it is not a child
            if child in seen or born is None or started is None or started < born:
                continue
            seen.add(child)
            found.append((child, started))
            todo.append(child)
    return found


def stop(processes: List[Process]) -> int:
    """Ends the ``processes`` that ``descendants`` found and are still running; returns how many it ended."""
    if sys.platform != "win32":
        return 0
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    ended = 0
    for pid, started in processes:
        if _windows_started(pid) != started:  # already ended (and its id maybe taken by another process)
            continue
        handle = kernel32.OpenProcess(0x0001, False, pid)  # PROCESS_TERMINATE
        if not handle:
            continue
        try:
            ended += bool(kernel32.TerminateProcess(handle, 1))
        finally:
            kernel32.CloseHandle(handle)
    return ended


def _windows_processes() -> List[Tuple[int, int]]:
    """``(process id, parent id)`` of every process running."""
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):  # PROCESSENTRY32W
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                    ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD),
                    ("cntThreads", wintypes.DWORD), ("th32ParentProcessID", wintypes.DWORD),
                    ("pcPriClassBase", ctypes.c_long), ("dwFlags", wintypes.DWORD),
                    ("szExeFile", ctypes.c_wchar * 260)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Process32FirstW.argtypes = kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(Entry)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error(), "could not list the processes")
    entry = Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    found = []
    try:
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            found.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID)))
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return found


def _windows_started(pid: int) -> Optional[int]:
    """When process ``pid`` started (a FILETIME), ``None`` when it is gone or can't be asked."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE, *[ctypes.POINTER(wintypes.FILETIME)] * 4]
    kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
            return None
        times = [wintypes.FILETIME() for _ in range(4)]
        if not kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    finally:
        kernel32.CloseHandle(handle)


def which(name: str) -> Optional[str]:
    """``shutil.which``, also looking in the user's shell ``PATH`` and the usual tool folders."""
    return shutil.which(name) or shutil.which(name, path=user_path())
