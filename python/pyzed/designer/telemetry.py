"""Opt-in telemetry for the designer: usage counts and timings, kept on this computer.

It is off until the user turns it on (Settings → Telemetry). While on, it counts the commands
and editor actions used and times the designer's startup, renders and commands, in
``telemetry.json`` in the Pyzed config folder. Nothing is sent anywhere unless the user also sets
an endpoint: then the counts are posted there as JSON when a session ends (and the ones a failed
send left behind when the next session starts), and start over. No code, text, file names or paths
are ever recorded.

``PYZED_TELEMETRY=0`` turns it off whatever the settings say.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional

from .settings import config_dir

SCHEMA = 1
#: Seconds between saves of the collected data while the designer runs.
SAVE_EVERY = 30.0
#: Upper bounds of the render-time buckets, in milliseconds.
BUCKETS = (4, 8, 16, 33, 50, 100, 250)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _version() -> str:
    try:
        from .. import __version__

        return str(__version__)
    except ImportError:  # pragma: no cover
        return "unknown"


def _empty() -> Dict[str, Any]:
    return {"since": _now(), "sessions": 0, "counters": {}, "timings": {}}


class Telemetry:
    """The designer's telemetry settings and the data collected while it is on."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else config_dir() / "telemetry.json"
        self.enabled = False
        self.endpoint = ""
        self.installation = ""
        self.data = _empty()
        self.last_sent = ""
        self.last_error = ""
        self._dirty = False
        self._saved_at = time.monotonic()
        self._session: Optional[float] = None
        self._lock = threading.Lock()
        self._load()

    # -- settings -----------------------------------------------------------------
    @property
    def active(self) -> bool:
        """Whether data is being collected (on in the settings and not turned off by ``PYZED_TELEMETRY=0``)."""
        return self.enabled and os.environ.get("PYZED_TELEMETRY", "1") not in ("0", "false", "off", "no")

    def configure(self, *, enabled: Optional[bool] = None, endpoint: Optional[str] = None) -> None:
        """Turns collecting on or off and sets the endpoint (``""`` keeps everything on this computer); saves."""
        if enabled is not None:
            self.enabled = bool(enabled)
            if self.enabled and not self.installation:
                self.installation = uuid.uuid4().hex
        if endpoint is not None:
            self.endpoint = endpoint.strip()
        self._dirty = True
        self.save()

    def clear(self) -> None:
        """Deletes the collected data and the random installation id."""
        with self._lock:
            self.data = _empty()
            self.installation = uuid.uuid4().hex if self.enabled else ""
        self._dirty = True
        self.save()

    # -- collecting ---------------------------------------------------------------
    def count(self, name: str, n: int = 1) -> None:
        """Adds ``n`` to counter ``name`` (``"command.save"``, ``"editor.select_next"``...)."""
        if not self.active:
            return
        with self._lock:
            counters = self.data["counters"]
            counters[name] = counters.get(name, 0) + n
        self._changed()

    def timing(self, name: str, ms: float) -> None:
        """Records a duration of ``ms`` milliseconds for ``name``: count, total, maximum and buckets."""
        if not self.active:
            return
        with self._lock:
            entry = self.data["timings"].setdefault(name, {"count": 0, "total_ms": 0.0, "max_ms": 0.0,
                                                           "buckets": [0] * (len(BUCKETS) + 1)})
            entry["count"] += 1
            entry["total_ms"] = round(entry["total_ms"] + ms, 3)
            entry["max_ms"] = round(max(entry["max_ms"], ms), 3)
            index = next((i for i, top in enumerate(BUCKETS) if ms <= top), len(BUCKETS))
            entry["buckets"][index] += 1
        self._changed()

    @contextmanager
    def timed(self, name: str) -> Iterator[None]:
        """Counts and times the ``with`` block as ``name``."""
        if not self.active:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            self.count(name)
            self.timing(name, (time.perf_counter() - start) * 1000)

    def wrap(self, name: str, function: Callable[..., Any]) -> Callable[..., Any]:
        """Returns ``function`` timed as ``name`` (only its duration, not a count)."""

        def timed(*args: Any, **kwargs: Any) -> Any:
            if not self.active:
                return function(*args, **kwargs)
            start = time.perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                self.timing(name, (time.perf_counter() - start) * 1000)

        return timed

    def session_started(self, started: float) -> None:
        """A designer session started at ``started`` (``time.perf_counter()``): records the startup time and
        sends what a failed send left behind."""
        if not self.active:
            return
        self.count("session.started")
        self.timing("startup", (time.perf_counter() - started) * 1000)
        with self._lock:
            self.data["sessions"] = self.data.get("sessions", 0) + 1
            self._session = time.monotonic()
        if self.endpoint and self.data.get("pending"):
            threading.Thread(target=self.send, daemon=True).start()

    def session_ended(self) -> None:
        """The session ended: records its length, saves and sends (waiting a few seconds at most)."""
        if not self.active:
            return
        if self._session is not None:
            self.timing("session", (time.monotonic() - self._session) * 1000)
        self.save()
        if self.endpoint:
            sender = threading.Thread(target=self.send, daemon=True)
            sender.start()
            sender.join(timeout=5.0)

    def _changed(self) -> None:
        self._dirty = True
        if time.monotonic() - self._saved_at > SAVE_EVERY:
            self.save()

    # -- reporting ----------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        """The data as it would be sent: the installation id, versions, operating system and the counts."""
        with self._lock:
            return {
                "schema": SCHEMA,
                "installation": self.installation,
                "app": "pyzed-designer",
                "version": _version(),
                "os": platform.system().lower(),
                "arch": platform.machine().lower(),
                "python": "{}.{}".format(*sys.version_info[:2]),
                "since": self.data.get("since"),
                "until": _now(),
                "sessions": self.data.get("sessions", 0),
                "counters": dict(self.data["counters"]),
                "timings": json.loads(json.dumps(self.data["timings"])),
            }

    def send(self, timeout: float = 5.0) -> bool:
        """Posts the report to the endpoint; on success the counts start over. Returns whether it was sent."""
        if not (self.active and self.endpoint):
            return False
        if not self.endpoint.startswith(("https://", "http://")):
            self.last_error = "The endpoint must be an http:// or https:// URL"
            return False
        import urllib.request

        report = self.report()
        body = json.dumps(report).encode("utf-8")
        request = urllib.request.Request(self.endpoint, data=body, method="POST", headers={
            "Content-Type": "application/json", "User-Agent": f"pyzed-designer/{report['version']}"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - the user's URL
                ok = 200 <= response.status < 300
        except Exception as err:  # noqa: BLE001 - any network error just keeps the data for later
            self.last_error = str(err)
            with self._lock:
                self.data["pending"] = True
            self.save()
            return False
        if ok:
            with self._lock:
                self.data = _empty()
            self.last_sent = _now()
            self.last_error = ""
            self._dirty = True
            self.save()
        return ok

    # -- storage ------------------------------------------------------------------
    def _load(self) -> None:
        try:
            saved = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(saved, dict):
            return
        self.enabled = bool(saved.get("enabled", False))
        self.endpoint = str(saved.get("endpoint", ""))
        self.installation = str(saved.get("installation", ""))
        self.last_sent = str(saved.get("last_sent", ""))
        data = saved.get("data")
        if isinstance(data, dict) and isinstance(data.get("counters"), dict) and isinstance(data.get("timings"), dict):
            self.data = data

    def save(self) -> Optional[Path]:
        """Writes the settings and the data to ``telemetry.json`` if they changed; returns the path (``None`` if
        it could not be written)."""
        self._saved_at = time.monotonic()
        if not self._dirty and self.path.exists():
            return self.path
        with self._lock:
            payload = {"enabled": self.enabled, "endpoint": self.endpoint, "installation": self.installation,
                       "last_sent": self.last_sent, "data": self.data}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            return None
        self._dirty = False
        return self.path


_instance: Optional[Telemetry] = None


def get() -> Telemetry:
    """The designer's telemetry (loaded from the config folder the first time)."""
    global _instance
    if _instance is None:
        _instance = Telemetry()
    return _instance


def reset(path: Optional[Path] = None) -> Telemetry:
    """Replaces the shared telemetry with one stored at ``path`` (for tests)."""
    global _instance
    _instance = Telemetry(path)
    return _instance
