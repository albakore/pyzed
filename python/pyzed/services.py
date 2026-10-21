"""Services: the parts of an app that draw nothing but raise events.

Visual Basic and Qt Designer kept them in a tray under the form: a timer, a file watcher, a
process, a background worker... They have properties and events like any control, but no
place on the window. Pyzed has the same ones, and each works on its own, in a ``pz.App``, in
a form made with Pyzed Design or in a script with no window at all::

    import pyzed as pz

    class Notes(pz.App):
        def __init__(self):
            self.files = []
            self.watcher = pz.FileWatcher("notes", pattern="*.md", on_change=self.reload)
            self.watcher.start()

        def reload(self, changed):
            self.files = sorted(p.name for p in Path("notes").glob("*.md"))

Handlers are given as ``on_<event>=`` (or later with ``service.on("event", handler)``). A
handler with a parameter receives the event's value; one without is just called. Events
raised by a background thread (file changes, process output, web responses...) reach the
handler on the app's thread, so it can change the app's state and return commands like any
callback. With no app running (a script, a test) they are called right away.

====================  ===================================================================
``Timer``             Ticks every ``interval`` milliseconds (``tick``).
``Shortcut``          A keyboard shortcut for the whole window (``activate``).
``FileWatcher``       Files created, modified or deleted in a folder (``change``...).
``Process``           Runs a command and streams its output (``output``, ``finished``...).
``Worker``            Runs slow work in a background thread (``progress``, ``done``...).
``HttpRequest``       Calls a web address without blocking (``response``, ``failed``).
``Clipboard``         Copies, pastes and notices what is copied (``change``, ``paste``).
``Settings``          Values kept between runs, in a JSON file (``change``).
``FileDialog``        The system's open, save and folder dialogs (``chosen``, ``cancelled``).
``Notification``      A desktop notification.
====================  ===================================================================
"""

from __future__ import annotations

import fnmatch
import json as _json
import os
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from . import _core

__all__ = [
    "Clipboard", "FileDialog", "FileWatcher", "HttpRequest", "HttpResponse", "Notification", "Process", "Service",
    "Settings", "Shortcut", "Timer", "Worker", "parse_filters",
]

Handler = Callable[..., Any]


def deliver(call: Callable[[], Any]) -> Any:
    """Runs ``call`` on the app's thread: right away from the main thread (returning its result), else
    posted to the running app, or called here when no app is running."""
    if threading.current_thread() is threading.main_thread():
        return call()
    try:
        _core.post(call)
    except RuntimeError:  # no app: a script or a test
        return call()
    return None


class Service:
    """The base of every service: its handlers, ``enabled`` and how events reach them.

    ``events`` lists the events a service raises; ``emit(event, value)`` calls the handler of
    one (on the app's thread). Subclasses that need a timer of the app return it from
    ``subscriptions()``; return those from your app's ``subscriptions`` too.
    """

    #: The events this service raises.
    events: Tuple[str, ...] = ()

    def __init__(self, **handlers: Optional[Handler]) -> None:
        self._handlers: Dict[str, Handler] = {}
        #: A disabled service raises no events.
        self.enabled = True
        for key, handler in handlers.items():
            if not key.startswith("on_"):
                raise TypeError(f"{type(self).__name__}() got an unexpected keyword argument {key!r}")
            if handler is not None:
                self.on(key[3:], handler)

    def on(self, event: str, handler: Optional[Handler]) -> "Service":
        """Sets (or with ``None`` removes) the handler of ``event``; returns the service."""
        if event not in self.events:
            raise ValueError(f"{type(self).__name__} has no event {event!r} (it has: {', '.join(self.events)})")
        if handler is None:
            self._handlers.pop(event, None)
        else:
            self._handlers[event] = handler
        return self

    def handles(self, event: str) -> bool:
        """Whether ``event`` has a handler."""
        return event in self._handlers

    def emit(self, event: str, value: Any = None) -> Any:
        """Raises ``event``: calls its handler with ``value`` on the app's thread (see ``deliver``)."""
        handler = self._handlers.get(event)
        if handler is None or not self.enabled:
            return None
        from .events import accepts_argument

        if accepts_argument(handler):
            return deliver(lambda: handler(value))
        return deliver(handler)

    def subscriptions(self) -> List[Any]:
        """The app subscriptions this service needs while it runs (timers); none by default."""
        return []

    def stop(self) -> None:
        """Stops whatever the service is doing (nothing by default)."""

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


# -- Timer ---------------------------------------------------------------------------------------------------------
class Timer(Service):
    """Raises ``tick`` every ``interval`` milliseconds while it is running, like Visual Basic's and Qt's timers.

    ``repeat=False`` ticks once and stops (a delay). ``count`` is how many times it ticked since
    it last started. Add ``timer.subscriptions()`` to your app's ``subscriptions``::

        self.clock = pz.Timer(1000, on_tick=self.refresh)

        def subscriptions(self):
            return self.clock.subscriptions()

    Events:
        ``on_tick()``:
    """

    events = ("tick",)

    def __init__(self, interval: float = 1000, *, running: bool = True, repeat: bool = True,
                 key: Optional[str] = None, on_tick: Optional[Handler] = None) -> None:
        super().__init__(on_tick=on_tick)
        self.interval = interval
        self.running = running
        self.repeat = repeat
        self.count = 0
        self.key = key or f"pyzed-timer-{id(self)}"

    def start(self) -> None:
        """Starts ticking (again) from zero."""
        self.count = 0
        self.running = True

    def stop(self) -> None:
        """Stops ticking."""
        self.running = False

    def tick(self) -> Any:
        """One tick: counts it, raises ``tick`` and stops a timer that does not repeat."""
        if not self.running or not self.enabled:
            return None
        self.count += 1
        if not self.repeat:
            self.running = False
        return self.emit("tick", self.count)

    def subscriptions(self) -> List[Any]:
        if not self.running or not self.enabled:
            return []
        return [_core.every(max(float(self.interval), 10) / 1000, self.tick, key=self.key)]


# -- Shortcut ------------------------------------------------------------------------------------------------------
_MODIFIERS = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "option": "alt", "opt": "alt", "shift": "shift",
              "cmd": "cmd", "command": "cmd", "super": "cmd", "meta": "cmd", "win": "cmd", "logo": "cmd"}


def _combo(text: str) -> Optional[Tuple[frozenset, str]]:
    """``"Ctrl+Shift+S"`` -> ``({"ctrl", "shift"}, "s")``; ``mod`` is cmd on macOS and ctrl elsewhere."""
    parts = [p for p in text.strip().lower().replace("+", "-").split("-") if p]
    if not parts:
        return None
    mods = set()
    for part in parts[:-1]:
        if part in ("mod", "secondary"):
            mods.add("cmd" if sys.platform == "darwin" else "ctrl")
        elif part in _MODIFIERS:
            mods.add(_MODIFIERS[part])
        else:
            return None
    return frozenset(mods), {"esc": "escape", "return": "enter", "del": "delete"}.get(parts[-1], parts[-1])


class Shortcut(Service):
    """Raises ``activate`` when one of its ``keys`` is pressed anywhere in the window.

    ``keys`` is a combo like ``"ctrl-s"`` (Zed's style, also ``"Ctrl+S"``), or several separated by
    commas: ``"ctrl-s, cmd-s"``. ``mod-s`` means Cmd+S on macOS and Ctrl+S elsewhere. Call
    ``handle(combo)`` from your app's ``on_key``::

        self.save = pz.Shortcut("mod-s", on_activate=self.save_file)

        def on_key(self, combo):
            return self.save.handle(combo)

    Events:
        ``on_activate()``:
    """

    events = ("activate",)

    def __init__(self, keys: str = "", *, on_activate: Optional[Handler] = None) -> None:
        super().__init__(on_activate=on_activate)
        self.keys = keys

    @property
    def combos(self) -> List[Tuple[frozenset, str]]:
        """The parsed combos of ``keys`` (invalid ones are left out)."""
        return [c for c in (_combo(k) for k in str(self.keys or "").split(",")) if c is not None]

    def matches(self, combo: str) -> bool:
        """Whether the pressed ``combo`` (``"ctrl-shift-p"``) is one of the shortcut's keys."""
        pressed = _combo(combo)
        return pressed is not None and pressed in self.combos

    def handle(self, combo: str) -> Any:
        """Raises ``activate`` (with the combo) when ``combo`` matches; returns the handler's result."""
        if self.enabled and self.matches(combo):
            return self.emit("activate", combo)
        return None


# -- FileWatcher ---------------------------------------------------------------------------------------------------
class _Loop:
    """A daemon thread that calls ``step`` every ``interval()`` seconds until stopped."""

    def __init__(self, name: str, step: Callable[[], None], interval: Callable[[], float]) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(step, interval), name=name, daemon=True)
        self._thread.start()

    def _run(self, step: Callable[[], None], interval: Callable[[], float]) -> None:
        while not self._stop.wait(max(interval(), 0.02)):
            step()

    def stop(self) -> None:
        self._stop.set()

    @property
    def alive(self) -> bool:
        return not self._stop.is_set()


class FileWatcher(Service):
    """Watches a folder (or one file) and raises an event for every file created, modified or deleted.

    ``pattern`` picks the files (``"*.csv"``, several separated by ``;``), ``recursive`` looks in
    subfolders too. Each check raises ``created``, ``modified`` and ``deleted`` with a file's path,
    then ``change`` once with the list of every changed path. It checks every ``interval``
    milliseconds by looking at the files' times and sizes, so it works the same on every system and on
    network drives. ``start()`` begins watching, ``stop()`` ends it.

    Events:
        ``on_change(value)``: Callable that receives the new value.
        ``on_created()``:
        ``on_modified()``:
        ``on_deleted()``:
    """

    events = ("change", "created", "modified", "deleted")

    def __init__(self, path: Union[str, Path] = ".", *, pattern: str = "*", recursive: bool = False,
                 interval: float = 500, on_change: Optional[Handler] = None, on_created: Optional[Handler] = None,
                 on_modified: Optional[Handler] = None, on_deleted: Optional[Handler] = None) -> None:
        super().__init__(on_change=on_change, on_created=on_created, on_modified=on_modified, on_deleted=on_deleted)
        self.path = path
        self.pattern = pattern
        self.recursive = recursive
        self.interval = interval
        self._loop: Optional[_Loop] = None
        self._seen: Dict[str, Tuple[float, int]] = {}

    @property
    def running(self) -> bool:
        """Whether it is watching (set it to start or stop)."""
        return self._loop is not None and self._loop.alive

    @running.setter
    def running(self, value: bool) -> None:
        if value and not self.running:
            self.start()
        elif not value:
            self.stop()

    def _files(self) -> Iterator[Path]:
        root = Path(self.path).expanduser()
        if root.is_file():
            yield root
            return
        patterns = [p.strip() for p in str(self.pattern or "*").split(";") if p.strip()] or ["*"]
        try:
            found = root.rglob("*") if self.recursive else root.iterdir()
            for path in found:
                if any(fnmatch.fnmatch(path.name, p) for p in patterns) and path.is_file():
                    yield path
        except OSError:  # the folder is gone or cannot be read: nothing to list
            return

    def snapshot(self) -> Dict[str, Tuple[float, int]]:
        """``{path: (modified time, size)}`` of every watched file right now."""
        out: Dict[str, Tuple[float, int]] = {}
        for path in self._files():
            try:
                stat = path.stat()
            except OSError:
                continue
            out[str(path)] = (stat.st_mtime, stat.st_size)
        return out

    def check(self) -> List[str]:
        """Compares the files with the last check, raises the events and returns the changed paths."""
        now = self.snapshot()
        before, self._seen = self._seen, now
        created = [p for p in now if p not in before]
        modified = [p for p in now if p in before and now[p] != before[p]]
        deleted = [p for p in before if p not in now]
        for event, paths in (("created", created), ("modified", modified), ("deleted", deleted)):
            for path in paths:
                self.emit(event, path)
        changed = sorted(created + modified + deleted)
        if changed:
            self.emit("change", changed)
        return changed

    def start(self) -> None:
        """Starts watching: what is there now is the starting point, later changes raise events."""
        self.stop()
        self._seen = self.snapshot()
        self._loop = _Loop("pyzed-file-watcher", self.check, lambda: float(self.interval) / 1000)

    def stop(self) -> None:
        """Stops watching."""
        if self._loop is not None:
            self._loop.stop()
            self._loop = None


# -- Process -------------------------------------------------------------------------------------------------------
class Process(Service):
    """Runs a program and raises an event for every line it prints, like Qt's ``QProcess``.

    ``command`` is a command line (``"git status"``) or a list of arguments. ``output`` and
    ``error_output`` get each line without its line break, ``finished`` the exit code (``0`` when it
    went well) and ``failed`` the message when the program could not start. ``write()`` sends text
    to its input, ``kill()`` ends it and ``wait()`` blocks until it ends (for scripts).

    Events:
        ``on_started()``:
        ``on_output()``:
        ``on_error_output()``:
        ``on_finished()``:
        ``on_failed()``:
    """

    events = ("started", "output", "error_output", "finished", "failed")

    def __init__(self, command: Union[str, Sequence[str]] = "", *, directory: Union[str, Path, None] = None,
                 env: Optional[Mapping[str, str]] = None, shell: bool = False,
                 on_started: Optional[Handler] = None, on_output: Optional[Handler] = None,
                 on_error_output: Optional[Handler] = None, on_finished: Optional[Handler] = None,
                 on_failed: Optional[Handler] = None) -> None:
        super().__init__(on_started=on_started, on_output=on_output, on_error_output=on_error_output,
                         on_finished=on_finished, on_failed=on_failed)
        self.command = command
        self.directory = directory
        self.env = dict(env) if env else None
        self.shell = shell
        #: The exit code of the last run (``None`` while running or before the first one).
        self.exit_code: Optional[int] = None
        self._popen: Optional[subprocess.Popen] = None
        self._done = threading.Event()
        self._done.set()

    @property
    def running(self) -> bool:
        """Whether the program is running."""
        return not self._done.is_set()

    @property
    def pid(self) -> Optional[int]:
        """The process id of the running program (``None`` when it is not running)."""
        return self._popen.pid if self._popen is not None and self.running else None

    def _args(self, command: Union[str, Sequence[str]]) -> Union[str, List[str]]:
        if self.shell:
            return command if isinstance(command, str) else subprocess.list2cmdline(list(command))
        if isinstance(command, str):
            # Windows splits a command line itself; non-POSIX shlex would keep the quotes in the arguments.
            return command if os.name == "nt" else shlex.split(command)
        return [str(a) for a in command]

    def start(self, command: Union[str, Sequence[str], None] = None) -> bool:
        """Starts ``command`` (or the one set); returns ``False`` if it is already running or cannot start."""
        if self.running:
            return False
        command = self.command if command is None else command
        if not command:
            self.emit("failed", "no command to run")
            return False
        env = {**os.environ, **self.env} if self.env else None
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # type: ignore[attr-defined]
        try:
            self._popen = subprocess.Popen(
                self._args(command), cwd=str(self.directory) if self.directory else None, env=env, shell=self.shell,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                encoding="utf-8", errors="replace", creationflags=flags)
        except (OSError, ValueError) as err:
            self.emit("failed", str(err))
            return False
        self.exit_code = None
        self._done.clear()
        popen = self._popen
        readers = [threading.Thread(target=self._read, args=(popen.stdout, "output"), daemon=True),
                   threading.Thread(target=self._read, args=(popen.stderr, "error_output"), daemon=True)]
        for reader in readers:
            reader.start()
        threading.Thread(target=self._wait, args=(popen, readers), name="pyzed-process", daemon=True).start()
        self.emit("started", popen.pid)
        return True

    def _read(self, stream: Any, event: str) -> None:
        for line in iter(stream.readline, ""):
            self.emit(event, line.rstrip("\r\n"))
        stream.close()

    def _wait(self, popen: subprocess.Popen, readers: List[threading.Thread]) -> None:
        code = popen.wait()
        for reader in readers:  # every line is out before ``finished``
            reader.join()
        self.exit_code = code
        self._done.set()
        self.emit("finished", code)

    def write(self, text: str) -> None:
        """Sends ``text`` to the program's input (add ``"\\n"`` to end a line)."""
        if self._popen is not None and self.running and self._popen.stdin is not None:
            try:
                self._popen.stdin.write(text)
                self._popen.stdin.flush()
            except (OSError, ValueError):
                pass  # it closed its input

    def kill(self) -> None:
        """Ends the program."""
        if self._popen is not None and self.running:
            try:
                self._popen.kill()
            except OSError:
                pass

    stop = kill

    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        """Blocks until the program ends (or ``timeout`` seconds) and returns its exit code."""
        self._done.wait(timeout)
        return self.exit_code


# -- Worker --------------------------------------------------------------------------------------------------------
class Worker(Service):
    """Runs slow work in a background thread so the window stays responsive (``BackgroundWorker``).

    ``work(value)`` runs in the thread with the value given to ``run(value)``; it may call
    ``report(progress)`` (raises ``progress`` on the app's thread) and look at ``cancelled`` to stop
    early. What it returns arrives in ``done``; an exception in ``failed`` (with the exception)::

        def count(n):
            for i in range(n):
                if worker.cancelled:
                    return None
                worker.report(i * 100 // n)
            return n

        worker = pz.Worker(count, on_progress=show, on_done=finish)
        worker.run(1_000_000)

    Events:
        ``on_progress()``:
        ``on_done()``:
        ``on_failed()``:
    """

    events = ("progress", "done", "failed")

    def __init__(self, work: Optional[Callable[..., Any]] = None, *, on_progress: Optional[Handler] = None,
                 on_done: Optional[Handler] = None, on_failed: Optional[Handler] = None) -> None:
        super().__init__(on_progress=on_progress, on_done=on_done, on_failed=on_failed)
        self.work = work
        #: What the last run returned.
        self.result: Any = None
        self._cancel = threading.Event()
        self._done = threading.Event()
        self._done.set()

    @property
    def busy(self) -> bool:
        """Whether the work is running."""
        return not self._done.is_set()

    @property
    def cancelled(self) -> bool:
        """Whether ``cancel()`` was called during this run (the work should return soon)."""
        return self._cancel.is_set()

    def run(self, value: Any = None) -> bool:
        """Starts the work with ``value``; returns ``False`` (and does nothing) while it is still busy."""
        if self.busy or self.work is None:
            return False
        self._cancel.clear()
        self._done.clear()
        threading.Thread(target=self._run, args=(self.work, value), name="pyzed-worker", daemon=True).start()
        return True

    def _run(self, work: Callable[..., Any], value: Any) -> None:
        from .events import accepts_argument

        try:
            result = work(value) if accepts_argument(work) else work()
        except Exception as err:
            self._done.set()
            self.emit("failed", err)
            return
        self.result = result
        self._done.set()
        self.emit("done", result)

    def report(self, progress: Any) -> None:
        """Raises ``progress`` with ``progress`` (call it from the work: a percent, a message...)."""
        self.emit("progress", progress)

    def cancel(self) -> None:
        """Asks the work to stop (it checks ``cancelled``)."""
        self._cancel.set()

    stop = cancel

    def wait(self, timeout: Optional[float] = None) -> Any:
        """Blocks until the work ends (or ``timeout`` seconds) and returns its result."""
        self._done.wait(timeout)
        return self.result


# -- HttpRequest ---------------------------------------------------------------------------------------------------
@dataclass
class HttpResponse:
    """What a web server answered: ``status`` (``200``...), ``headers``, the raw ``content`` and ``url``."""

    status: int
    content: bytes = b""
    headers: Dict[str, str] = field(default_factory=dict)
    url: str = ""

    @property
    def ok(self) -> bool:
        """Whether the status is a success (200 to 299)."""
        return 200 <= self.status < 300

    @property
    def text(self) -> str:
        """The content as text (UTF-8 unless the server said otherwise)."""
        kind = self.headers.get("content-type", "")
        charset = kind.split("charset=", 1)[1].split(";")[0].strip() if "charset=" in kind else "utf-8"
        return self.content.decode(charset or "utf-8", errors="replace")

    def json(self) -> Any:
        """The content parsed as JSON."""
        return _json.loads(self.text)


def _headers(value: Union[str, Mapping[str, str], None]) -> Dict[str, str]:
    """Headers from a dict or from ``"Name: value"`` lines."""
    if not value:
        return {}
    if isinstance(value, Mapping):
        return {str(k): str(v) for k, v in value.items()}
    out = {}
    for line in str(value).splitlines():
        name, sep, rest = line.partition(":")
        if sep and name.strip():
            out[name.strip()] = rest.strip()
    return out


class HttpRequest(Service):
    """Calls a web address in the background and raises ``response`` with an ``HttpResponse``.

    Every answer arrives in ``response``, errors too (check ``response.ok`` or ``status``);
    ``failed`` gets the message when there was no answer at all (no network, wrong address,
    timeout). ``send()`` uses the request's ``url``, ``method``, ``headers`` and ``body``, or what it
    is given; ``json=`` sends JSON (with ``POST`` when the method is ``GET``)::

        api = pz.HttpRequest("https://api.github.com/repos/albakore/pyzed", on_response=self.show)
        api.send()

        def show(self, response):
            self.stars = response.json()["stargazers_count"]

    Events:
        ``on_response()``:
        ``on_failed()``:
    """

    events = ("response", "failed")

    def __init__(self, url: str = "", *, method: str = "GET", headers: Union[str, Mapping[str, str], None] = None,
                 body: Union[str, bytes, None] = None, timeout: float = 30.0,
                 on_response: Optional[Handler] = None, on_failed: Optional[Handler] = None) -> None:
        super().__init__(on_response=on_response, on_failed=on_failed)
        self.url = url
        self.method = method
        self.headers = headers
        self.body = body
        self.timeout = float(timeout)
        #: The last answer (``None`` before the first one).
        self.response: Optional[HttpResponse] = None
        self._done = threading.Event()
        self._done.set()

    @property
    def busy(self) -> bool:
        """Whether a request is on its way."""
        return not self._done.is_set()

    def send(self, url: Optional[str] = None, *, method: Optional[str] = None, body: Union[str, bytes, None] = None,
             json: Any = None, headers: Union[str, Mapping[str, str], None] = None) -> bool:
        """Sends the request in the background; returns ``False`` while another one is on its way."""
        if self.busy:
            return False
        url = url or self.url
        if not url:
            self.emit("failed", "no address to call")
            return False
        sent_headers = {**_headers(self.headers), **_headers(headers)}
        data = self.body if body is None else body
        if json is not None:
            data = _json.dumps(json)
            sent_headers.setdefault("Content-Type", "application/json")
        if isinstance(data, str):
            data = data.encode("utf-8") if data else None
        verb = (method or self.method or "GET").upper()
        if verb == "GET" and method is None and (body is not None or json is not None):
            verb = "POST"  # data given to send() goes out with POST unless a method is named
        self._done.clear()
        threading.Thread(target=self._send, args=(url, verb, sent_headers, data), name="pyzed-http",
                         daemon=True).start()
        return True

    def _send(self, url: str, method: str, headers: Dict[str, str], data: Optional[bytes]) -> None:
        import urllib.error
        import urllib.request

        headers.setdefault("User-Agent", "Pyzed")
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as answer:
                response = HttpResponse(answer.status, answer.read(), {k.lower(): v for k, v in answer.headers.items()},
                                        answer.url)
        except urllib.error.HTTPError as err:  # an answer, with an error status
            response = HttpResponse(err.code, err.read() or b"", {k.lower(): v for k, v in (err.headers or {}).items()},
                                    url)
        except Exception as err:
            self._done.set()
            reason = getattr(err, "reason", None) or err
            self.emit("failed", str(reason))
            return
        self.response = response
        self._done.set()
        self.emit("response", response)

    def wait(self, timeout: Optional[float] = None) -> Optional[HttpResponse]:
        """Blocks until the answer arrives (or ``timeout`` seconds) and returns it."""
        self._done.wait(timeout)
        return self.response


# -- Clipboard -----------------------------------------------------------------------------------------------------
class Clipboard(Service):
    """The system clipboard: ``copy(text)`` and ``paste()`` return commands (return them from a callback).

    ``paste()`` raises ``paste`` with the text (or calls ``then``). With ``watch=True`` it looks at the
    clipboard every ``interval`` milliseconds and raises ``change`` when something new is copied, in this
    app or another one; add ``clipboard.subscriptions()`` to your app's ``subscriptions``.
    ``text`` is the last text it saw.

    Events:
        ``on_change(value)``: Callable that receives the new value.
        ``on_paste()``:
    """

    events = ("change", "paste")

    def __init__(self, *, watch: bool = False, interval: float = 500, key: Optional[str] = None,
                 on_change: Optional[Handler] = None, on_paste: Optional[Handler] = None) -> None:
        super().__init__(on_change=on_change, on_paste=on_paste)
        self.watch = watch
        self.interval = interval
        self.text: Optional[str] = None
        self.key = key or f"pyzed-clipboard-{id(self)}"

    def copy(self, text: Any) -> _core.Command:
        """The command that puts ``text`` on the clipboard."""
        self.text = str(text)
        return _core.Command.copy(self.text)

    def paste(self, then: Optional[Callable[[str], Any]] = None) -> _core.Command:
        """The command that reads the clipboard and raises ``paste`` with its text (or calls ``then``)."""
        def got(text: str) -> Any:
            self.text = text
            return then(text) if then is not None else self.emit("paste", text)
        return _core.Command.paste(got)

    def seen(self, text: str) -> Any:
        """Takes the clipboard's current ``text`` and raises ``change`` if it is new."""
        first, changed = self.text is None, text != self.text
        self.text = text
        if changed and not first:
            return self.emit("change", text)
        return None

    def subscriptions(self) -> List[Any]:
        if not self.watch or not self.enabled:
            return []
        return [_core.every(max(float(self.interval), 100) / 1000, lambda: _core.Command.paste(self.seen),
                            key=self.key)]


# -- Settings ------------------------------------------------------------------------------------------------------
class Settings(Service):
    """Values kept between runs (``QSettings``, ``My.Settings``): a dict saved as JSON.

    ``settings["volume"] = 7`` saves it at once (``autosave``) and raises ``change`` with
    ``(key, value)``; ``settings.get("volume", 5)`` reads it back next time. The file is
    ``<name>.json`` in ``folder``, by default Pyzed's per-user settings folder (``settings/``
    inside ``pyzed.project.config_dir()``), so each user keeps their own.

    Events:
        ``on_change(value)``: Callable that receives the new value.
    """

    events = ("change",)

    def __init__(self, name: str = "settings", *, folder: Union[str, Path, None] = None,
                 defaults: Optional[Mapping[str, Any]] = None, autosave: bool = True,
                 on_change: Optional[Handler] = None) -> None:
        super().__init__(on_change=on_change)
        self.name = name
        self.folder = folder
        self.defaults = dict(defaults or {})
        self.autosave = autosave
        self._values: Dict[str, Any] = {}
        self._loaded_from: Optional[Path] = None

    @property
    def path(self) -> Path:
        """The JSON file the values live in."""
        if self.folder:
            folder = Path(self.folder).expanduser()
        else:
            from .project import config_dir

            folder = config_dir() / "settings"
        name = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(self.name or "settings"))
        return folder / f"{name}.json"

    def load(self) -> "Settings":
        """Reads the file again (a missing or broken file means no values yet)."""
        path = self.path
        try:
            data = _json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self._values = data if isinstance(data, dict) else {}
        self._loaded_from = path
        return self

    def _ensure(self) -> Dict[str, Any]:
        if self._loaded_from != self.path:
            self.load()
        return self._values

    def save(self) -> Path:
        """Writes the values to the file (``autosave`` does it after every change)."""
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json.dumps(self._ensure(), indent=2, ensure_ascii=False, default=str) + "\n",
                        encoding="utf-8")
        return path

    def get(self, key: str, default: Any = None) -> Any:
        """The value of ``key``: saved, else from ``defaults``, else ``default``."""
        values = self._ensure()
        if key in values:
            return values[key]
        return self.defaults.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Sets ``key`` (saved right away with ``autosave``) and raises ``change`` when it changed."""
        values = self._ensure()
        if key in values and values[key] == value:
            return
        values[key] = value
        if self.autosave:
            self.save()
        self.emit("change", (key, value))

    def delete(self, key: str) -> None:
        """Forgets ``key``."""
        values = self._ensure()
        if key in values:
            del values[key]
            if self.autosave:
                self.save()

    def clear(self) -> None:
        """Forgets every value."""
        self._ensure().clear()
        if self.autosave:
            self.save()

    def keys(self) -> List[str]:
        """The saved keys."""
        return list(self._ensure())

    def items(self) -> List[Tuple[str, Any]]:
        """The saved ``(key, value)`` pairs."""
        return list(self._ensure().items())

    def __getitem__(self, key: str) -> Any:
        values = self._ensure()
        if key in values:
            return values[key]
        if key in self.defaults:
            return self.defaults[key]
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        self.set(key, value)

    def __delitem__(self, key: str) -> None:
        self.delete(key)

    def __contains__(self, key: object) -> bool:
        return key in self._ensure() or key in self.defaults

    def __iter__(self) -> Iterator[str]:
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._ensure())


# -- FileDialog ----------------------------------------------------------------------------------------------------
def parse_filters(value: Any) -> List[Tuple[str, List[str]]]:
    """File filters from ``[("Images", ["png", "jpg"])]``, ``{"Images": "png jpg"}`` or text with one
    ``Images: png, jpg`` per line (or separated by ``;``)."""
    if not value:
        return []
    if isinstance(value, Mapping):
        pairs = list(value.items())
    elif isinstance(value, str):
        pairs = []
        for part in value.replace(";", "\n").splitlines():
            name, sep, exts = part.partition(":")
            if sep and name.strip():
                pairs.append((name.strip(), exts))
    else:
        pairs = [tuple(p) for p in value]
    out = []
    for name, exts in pairs:
        if isinstance(exts, str):
            exts = exts.replace(",", " ").split()
        exts = [e.strip().lstrip("*").lstrip(".") for e in exts if e.strip()]
        if exts:
            out.append((str(name), exts))
    return out


class FileDialog(Service):
    """The system's file dialog: ``show()`` returns the command that opens it (return it from a callback).

    ``mode`` is ``"open"`` (one file), ``"open_many"``, ``"save"`` or ``"folder"``. ``chosen`` gets
    the path (a list of paths with ``"open_many"``) and ``cancelled`` runs when it is closed without
    choosing. ``filters`` limits the files shown (see ``parse_filters``), ``directory`` is where it
    opens and ``file_name`` the name suggested when saving. ``path``/``paths`` keep the last choice.

    Events:
        ``on_chosen()``:
        ``on_cancelled()``:
    """

    events = ("chosen", "cancelled")
    MODES = ("open", "open_many", "save", "folder")

    def __init__(self, mode: str = "open", *, title: str = "", filters: Any = None,
                 directory: Union[str, Path, None] = None, file_name: str = "",
                 on_chosen: Optional[Handler] = None, on_cancelled: Optional[Handler] = None) -> None:
        super().__init__(on_chosen=on_chosen, on_cancelled=on_cancelled)
        if mode not in self.MODES:
            raise ValueError(f"mode must be one of {', '.join(self.MODES)}, not {mode!r}")
        self.mode = mode
        self.title = title
        self.filters = filters
        self.directory = directory
        self.file_name = file_name
        self.paths: List[str] = []

    @property
    def path(self) -> Optional[str]:
        """The path chosen last (the first one with ``"open_many"``)."""
        return self.paths[0] if self.paths else None

    def chose(self, paths: Sequence[str]) -> Any:
        """What the dialog answers: keeps ``paths`` and raises ``chosen`` (or ``cancelled`` when empty)."""
        self.paths = [str(p) for p in paths or ()]
        if not self.paths:
            return self.emit("cancelled")
        return self.emit("chosen", list(self.paths) if self.mode == "open_many" else self.paths[0])

    def show(self, *, mode: Optional[str] = None) -> _core.Command:
        """The command that opens the dialog."""
        mode = mode or self.mode
        options: Dict[str, Any] = {"title": self.title or None, "filters": parse_filters(self.filters) or None,
                                   "directory": str(Path(self.directory).expanduser()) if self.directory else None}
        if mode == "save":
            return _core.Command.save_file(self.chose, file_name=self.file_name or "", **options)
        return _core.Command.pick_files(self.chose, multiple=mode == "open_many", folder=mode == "folder",
                                        **options)


# -- Notification --------------------------------------------------------------------------------------------------
class Notification(Service):
    """A desktop notification (Windows' balloon, macOS' Notification Center, ``notify-send`` on Linux).

    ``show()`` shows ``text`` under ``title``, or what it is given, and returns whether it could;
    ``shown`` and ``failed`` follow with the text.

    Events:
        ``on_shown()``:
        ``on_failed()``:
    """

    events = ("shown", "failed")

    def __init__(self, title: str = "", text: str = "", *, on_shown: Optional[Handler] = None,
                 on_failed: Optional[Handler] = None) -> None:
        super().__init__(on_shown=on_shown, on_failed=on_failed)
        self.title = title
        self.text = text

    def show(self, text: Optional[str] = None, *, title: Optional[str] = None) -> bool:
        """Shows the notification; returns ``False`` when this system has no way to."""
        from ._platform import notify

        body = str(self.text if text is None else text)
        ok = self.enabled and notify(str(title or self.title or "Pyzed"), body)
        self.emit("shown" if ok else "failed", body)
        return ok
