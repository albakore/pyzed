"""Services that talk to the operating system: what it is, opening things, the network and the battery.

They work like the ones in ``pyzed.services`` (a Timer, a Process...): handlers are given as
``on_<event>=``, background checks reach the handlers on the app's thread, and in Pyzed
Design they are non-visual components in the tray under the form::

    import pyzed as pz

    info = pz.SystemInfo()
    info.os, info.os_version, info.user, info.cpu_count, info.memory_total

    pz.Launcher().open("https://albakore.github.io/pyzed/")   # the browser
    pz.Launcher().open("report.pdf")                          # the PDF viewer
    pz.Launcher().reveal("report.pdf")                        # the file manager, with it selected

    net = pz.NetworkMonitor(on_offline=lambda: print("No connection"))
    net.start()

====================  ===================================================================
``SystemInfo``        The system, user, folders, processors, memory and disk space.
``Launcher``          Opens files, folders and links with their default app (``opened``).
``NetworkMonitor``    Whether there is a connection to the internet (``online``, ``offline``).
``PowerMonitor``      The battery's charge and whether it is plugged in (``change``, ``low``).
====================  ===================================================================
"""

from __future__ import annotations

import getpass
import locale
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .services import Handler, Service, _Loop

__all__ = ["Launcher", "NetworkMonitor", "PowerMonitor", "SystemInfo", "battery", "memory"]


# -- helpers --------------------------------------------------------------------------------------------------


def memory() -> Tuple[Optional[int], Optional[int]]:
    """``(total, available)`` memory in bytes, or ``None`` where this system does not say."""
    try:
        if sys.platform.startswith("linux"):
            values: Dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                name, _, rest = line.partition(":")
                if rest.strip():
                    values[name] = int(rest.split()[0]) * 1024
            return values.get("MemTotal"), values.get("MemAvailable", values.get("MemFree"))
        if sys.platform == "win32":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                            ("available", ctypes.c_ulonglong), ("page_total", ctypes.c_ulonglong),
                            ("page_available", ctypes.c_ulonglong), ("virtual_total", ctypes.c_ulonglong),
                            ("virtual_available", ctypes.c_ulonglong), ("extended", ctypes.c_ulonglong)]

            status = Status()
            status.length = ctypes.sizeof(Status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # type: ignore[attr-defined]
                return int(status.total), int(status.available)
            return None, None
        if sys.platform == "darwin":
            total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
                                       timeout=2).stdout.strip() or 0) or None
            stats = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=2).stdout
            page = int(re.search(r"page size of (\d+)", stats).group(1)) if "page size of" in stats else 4096
            free = sum(int(m) for m in re.findall(r"Pages (?:free|inactive|speculative):\s+(\d+)", stats))
            return total, free * page if free else None
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        pass
    return None, None


def battery() -> Tuple[Optional[float], Optional[bool]]:
    """``(percent, plugged)`` of the battery: ``(None, None)`` on a computer without one."""
    try:
        if sys.platform.startswith("linux"):
            root = Path("/sys/class/power_supply")
            for supply in sorted(root.glob("BAT*")) if root.exists() else ():
                capacity = supply / "capacity"
                if capacity.exists():
                    status = (supply / "status").read_text().strip().lower() if (supply / "status").exists() else ""
                    return float(capacity.read_text().strip()), status in ("charging", "full", "not charging")
            return None, None
        if sys.platform == "win32":
            import ctypes

            class Power(ctypes.Structure):
                _fields_ = [("ac", ctypes.c_byte), ("flag", ctypes.c_byte), ("percent", ctypes.c_byte),
                            ("saver", ctypes.c_byte), ("life", ctypes.c_ulong), ("full_life", ctypes.c_ulong)]

            power = Power()
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(power)):  # type: ignore[attr-defined]
                return None, None
            if power.flag & 128 or power.percent == -1 or (power.percent & 0xFF) == 255:  # no battery
                return None, None
            return float(power.percent & 0xFF), power.ac == 1
        if sys.platform == "darwin":
            out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=2).stdout
            m = re.search(r"(\d+)%", out)
            if not m:
                return None, None
            return float(m.group(1)), "AC Power" in out
    except (OSError, ValueError, AttributeError, subprocess.SubprocessError):
        pass
    return None, None


def _os_name() -> str:
    return {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux" if sys.platform.startswith("linux")
                                                       else platform.system() or sys.platform)


def _os_version() -> str:
    if sys.platform == "darwin":
        return platform.mac_ver()[0] or platform.release()
    if sys.platform == "win32":
        return platform.version()
    try:
        info = platform.freedesktop_os_release()
        return info.get("PRETTY_NAME") or info.get("NAME", "") + " " + info.get("VERSION_ID", "")
    except (OSError, AttributeError):
        return platform.release()


# -- SystemInfo -----------------------------------------------------------------------------------------------


class SystemInfo(Service):
    """What the computer is: its system, user, folders, processors, memory and free disk space.

    The fixed facts are plain attributes (``os``, ``os_version``, ``machine``, ``hostname``,
    ``user``, ``home``, ``language``, ``cpu_count``, ``python_version``, ``memory_total``...).
    ``memory_available`` and ``disk_free`` are read when asked. ``env(name)`` reads an
    environment variable and ``folder("documents")`` finds the user's folders. With
    ``interval`` (milliseconds) above 0, ``start()`` checks the memory and disk every so often
    and raises ``update`` with ``snapshot()``.

    Events:
        ``on_update(value)``: Callable that receives ``snapshot()`` on every check.
    """

    events = ("update",)

    FOLDERS = {"home": "", "desktop": "Desktop", "documents": "Documents", "downloads": "Downloads",
               "music": "Music", "pictures": "Pictures", "videos": "Videos"}
    _XDG = {"desktop": "DESKTOP", "documents": "DOCUMENTS", "downloads": "DOWNLOAD", "music": "MUSIC",
            "pictures": "PICTURES", "videos": "VIDEOS"}

    def __init__(self, *, interval: float = 0, disk_path: Union[str, Path, None] = None,
                 on_update: Optional[Handler] = None) -> None:
        super().__init__(on_update=on_update)
        self.interval = interval
        self.disk_path = disk_path
        self.os = _os_name()
        self.os_version = _os_version()
        self.machine = platform.machine()
        self.hostname = socket.gethostname()
        try:
            self.user = getpass.getuser()
        except (OSError, KeyError, ImportError):
            self.user = ""
        self.home = str(Path.home())
        self.cpu_count = os.cpu_count() or 1
        self.python_version = platform.python_version()
        self.language = (locale.getlocale()[0] or os.environ.get("LANG", "")).split(".")[0]
        self.memory_total = memory()[0]
        self.started = time.time()
        self._loop: Optional[_Loop] = None

    @property
    def is_windows(self) -> bool:
        return self.os == "Windows"

    @property
    def is_mac(self) -> bool:
        return self.os == "macOS"

    @property
    def is_linux(self) -> bool:
        return self.os == "Linux"

    @property
    def memory_available(self) -> Optional[int]:
        """Free memory in bytes (``None`` where this system does not say)."""
        return memory()[1]

    @property
    def disk_free(self) -> Optional[int]:
        """Free space in bytes on the disk of ``disk_path`` (the home folder by default)."""
        try:
            return shutil.disk_usage(str(self.disk_path or self.home)).free
        except OSError:
            return None

    @property
    def disk_total(self) -> Optional[int]:
        try:
            return shutil.disk_usage(str(self.disk_path or self.home)).total
        except OSError:
            return None

    def env(self, name: str, default: str = "") -> str:
        """The environment variable ``name`` (``default`` when it is not set)."""
        return os.environ.get(name, default)

    def folder(self, name: str = "home") -> str:
        """A folder of the user: ``"home"``, ``"desktop"``, ``"documents"``, ``"downloads"``, ``"music"``,
        ``"pictures"`` or ``"videos"`` (on Linux, where ``xdg-user-dirs`` puts them)."""
        name = name.lower()
        if name not in self.FOLDERS:
            raise ValueError(f"folder must be one of {', '.join(self.FOLDERS)}, not {name!r}")
        home = Path(self.home)
        if name == "home":
            return str(home)
        if self.is_linux:
            config = home / ".config" / "user-dirs.dirs"
            try:
                m = re.search(rf'^XDG_{self._XDG[name]}_DIR="([^"]+)"', config.read_text(), re.M)
                if m:
                    return m.group(1).replace("$HOME", str(home))
            except OSError:
                pass
        return str(home / self.FOLDERS[name])

    def snapshot(self) -> Dict[str, Any]:
        """Every fact as a dict, with memory and disk read now."""
        return {"os": self.os, "os_version": self.os_version, "machine": self.machine, "hostname": self.hostname,
                "user": self.user, "home": self.home, "language": self.language, "cpu_count": self.cpu_count,
                "python_version": self.python_version, "memory_total": self.memory_total,
                "memory_available": self.memory_available, "disk_free": self.disk_free, "disk_total": self.disk_total}

    def check(self) -> Dict[str, Any]:
        """Reads the facts and raises ``update``."""
        snapshot = self.snapshot()
        self.emit("update", snapshot)
        return snapshot

    @property
    def running(self) -> bool:
        return self._loop is not None and self._loop.alive

    @running.setter
    def running(self, value: bool) -> None:
        if value and not self.running:
            self.start()
        elif not value:
            self.stop()

    def start(self) -> None:
        """Checks now, then every ``interval`` milliseconds (when it is above 0)."""
        self.stop()
        self.check()
        if float(self.interval or 0) > 0:
            self._loop = _Loop("pyzed-system-info", self.check, lambda: float(self.interval) / 1000)

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.stop()
            self._loop = None


# -- Launcher -------------------------------------------------------------------------------------------------


class Launcher(Service):
    """Opens files, folders and web links with the app the system uses for them.

    ``open(target)`` opens a file (the PDF viewer for a .pdf...), a folder (the file manager)
    or a link (``https://``, ``mailto:``...) and raises ``opened`` or ``failed``;
    ``reveal(path)`` shows a file selected in the file manager; ``email(to, subject, body)``
    starts a message in the mail app. Without an argument they use ``target``.

    Events:
        ``on_opened(value)``: Callable that receives what was opened.
        ``on_failed(value)``: Callable that receives why it could not be opened.
    """

    events = ("opened", "failed")

    def __init__(self, target: str = "", *, on_opened: Optional[Handler] = None,
                 on_failed: Optional[Handler] = None) -> None:
        super().__init__(on_opened=on_opened, on_failed=on_failed)
        self.target = target

    @staticmethod
    def is_link(target: str) -> bool:
        return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]+:", target)) and not re.match(r"^[a-zA-Z]:[\\/]", target)

    def _run(self, args: List[str]) -> None:
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,  # noqa: S603
                         start_new_session=sys.platform != "win32")

    def open(self, target: Optional[str] = None) -> bool:  # noqa: A003
        """Opens ``target`` (a path or a link) with its default app; returns whether it could."""
        target = str(target if target is not None else self.target or "").strip()
        if not target or not self.enabled:
            return False
        try:
            if self.is_link(target):
                from ._platform import use_windows_browser

                use_windows_browser()  # under WSL, Windows' own browser
                if not webbrowser.open(target):
                    raise OSError(f"nothing could open {target}")
            else:
                path = Path(target).expanduser()
                if not path.exists():
                    raise FileNotFoundError(f"{target} does not exist")
                if sys.platform == "win32":
                    os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606
                else:
                    self._run(["open" if sys.platform == "darwin" else "xdg-open", str(path)])
        except (OSError, ValueError) as error:
            self.emit("failed", str(error))
            return False
        self.emit("opened", target)
        return True

    def reveal(self, path: Optional[str] = None) -> bool:
        """Shows ``path`` in the file manager, selected where the system allows it."""
        target = Path(str(path if path is not None else self.target or "")).expanduser()
        if not str(target) or not target.exists():
            self.emit("failed", f"{target} does not exist")
            return False
        try:
            if sys.platform == "darwin":
                self._run(["open", "-R", str(target)])
            elif sys.platform == "win32":
                self._run(["explorer", f"/select,{target}"])
            else:
                self._run(["xdg-open", str(target if target.is_dir() else target.parent)])
        except OSError as error:
            self.emit("failed", str(error))
            return False
        self.emit("opened", str(target))
        return True

    def email(self, to: str = "", subject: str = "", body: str = "") -> bool:
        """Starts an email to ``to`` in the mail app."""
        from urllib.parse import quote

        query = "&".join(f"{k}={quote(v)}" for k, v in (("subject", subject), ("body", body)) if v)
        return self.open(f"mailto:{quote(to, safe='@,')}" + (f"?{query}" if query else ""))


# -- NetworkMonitor -------------------------------------------------------------------------------------------


class NetworkMonitor(Service):
    """Notices when the computer goes online or offline.

    Every ``interval`` milliseconds it tries to reach ``host`` (a DNS server by default) in a
    background thread; ``online`` is the last answer (``None`` before the first check).
    ``check()`` tries right away.

    Events:
        ``on_change(value)``: Callable that receives ``True`` (online) or ``False``.
        ``on_online()``: The connection came back.
        ``on_offline()``: The connection was lost.
    """

    events = ("change", "online", "offline")

    def __init__(self, *, host: str = "1.1.1.1", port: int = 53, interval: float = 5000, timeout: float = 2,
                 on_change: Optional[Handler] = None, on_online: Optional[Handler] = None,
                 on_offline: Optional[Handler] = None) -> None:
        super().__init__(on_change=on_change, on_online=on_online, on_offline=on_offline)
        self.host = host
        self.port = port
        self.interval = interval
        self.timeout = timeout
        self.online: Optional[bool] = None
        self._loop: Optional[_Loop] = None

    def reachable(self) -> bool:
        """Whether ``host`` answers now (blocks up to ``timeout`` seconds)."""
        for host in dict.fromkeys((self.host, "8.8.8.8")):
            try:
                with socket.create_connection((host, int(self.port)), timeout=float(self.timeout)):
                    return True
            except OSError:
                continue
        return False

    def check(self) -> bool:
        """Checks the connection and raises the events when it changed."""
        now = self.reachable()
        before, self.online = self.online, now
        if now != before:
            self.emit("change", now)
            if before is not None or not now:
                self.emit("online" if now else "offline")
        return now

    @property
    def running(self) -> bool:
        return self._loop is not None and self._loop.alive

    @running.setter
    def running(self, value: bool) -> None:
        if value and not self.running:
            self.start()
        elif not value:
            self.stop()

    def start(self) -> None:
        """Starts checking (the first check runs right away in the background)."""
        self.stop()
        self._loop = _Loop("pyzed-network", self.check, lambda: float(self.interval) / 1000)
        import threading

        threading.Thread(target=self.check, name="pyzed-network-first", daemon=True).start()

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.stop()
            self._loop = None


# -- PowerMonitor ---------------------------------------------------------------------------------------------


class PowerMonitor(Service):
    """The battery: how charged it is and whether the computer is plugged in.

    ``percent`` and ``plugged`` are ``None`` on a computer without a battery (``has_battery``).
    Every ``interval`` milliseconds it looks again and raises ``change``; ``low`` when the
    charge drops under ``low_level`` while unplugged, and ``plugged``/``unplugged``.

    Events:
        ``on_change(value)``: Callable that receives ``(percent, plugged)``.
        ``on_low(value)``: The charge dropped under ``low_level`` (``value`` is the percent).
        ``on_plugged()``: The charger was connected.
        ``on_unplugged()``: The charger was disconnected.
    """

    events = ("change", "low", "plugged", "unplugged")

    def __init__(self, *, interval: float = 30000, low_level: float = 20, on_change: Optional[Handler] = None,
                 on_low: Optional[Handler] = None, on_plugged: Optional[Handler] = None,
                 on_unplugged: Optional[Handler] = None) -> None:
        super().__init__(on_change=on_change, on_low=on_low, on_plugged=on_plugged, on_unplugged=on_unplugged)
        self.interval = interval
        self.low_level = low_level
        self.percent, self.plugged = battery()
        self._loop: Optional[_Loop] = None

    @property
    def has_battery(self) -> bool:
        return self.percent is not None

    def check(self) -> Tuple[Optional[float], Optional[bool]]:
        """Reads the battery and raises the events of what changed."""
        before = (self.percent, self.plugged)
        self.percent, self.plugged = now = battery()
        if now != before:
            self.emit("change", now)
            if before[1] is not None and now[1] is not None and now[1] != before[1]:
                self.emit("plugged" if now[1] else "unplugged")
            low = float(self.low_level)
            if now[0] is not None and not now[1] and now[0] < low and (before[0] is None or before[0] >= low):
                self.emit("low", now[0])
        return now

    @property
    def running(self) -> bool:
        return self._loop is not None and self._loop.alive

    @running.setter
    def running(self, value: bool) -> None:
        if value and not self.running:
            self.start()
        elif not value:
            self.stop()

    def start(self) -> None:
        self.stop()
        self._loop = _Loop("pyzed-power", self.check, lambda: float(self.interval) / 1000)

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.stop()
            self._loop = None
