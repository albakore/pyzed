"""The designer's logs and error handling: every error and event of the designer and of the forms it
runs, in the Logs panel, and error boundaries so that a failure never takes the window down.

The designer's modules log with Python's ``logging``, under ``pyzed.designer.<type>``::

    from . import logs
    logs.event("document", "Saved %s", path.name)      # an event (between DEBUG and INFO)
    logs.log("project").warning("uv is not installed")

The Logs panel (View → Logs) shows them with their time, level and type, filters by level, type and
text, and copies lines; the same lines go to ``logs/pyzed-design.log`` in the Pyzed config folder (the
file is renewed past 1 MB, keeping three old ones), to attach to a bug report.

Errors nobody expected are caught at three places and never close the designer:

- a callback (a click, a key, a menu command) that raises: ``sys.excepthook``, which the native
  runtime calls with the error;
- a background thread that raises: ``threading.excepthook``;
- a panel, dialog or the canvas that fails to draw: ``ui.error_boundary`` shows an error card in
  its place.

Each one is logged with its traceback and shown in an error dialog with buttons to copy it, to open
the file and line it comes from, and to see it in the Logs panel.

A crash of the process itself (a panic of the native core, a fatal error of Python) is written to
``logs/crash.log``; the next start moves it to ``crash-previous.log`` and tells the user about it
(``LogCenter.last_crash``).
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import re
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import _core, ui
from ..theme import Theme
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: The level of events (a command ran, a file was saved...): between DEBUG and INFO.
EVENT = 15
logging.addLevelName(EVENT, "EVENT")

#: The types of log line, in the order the Logs panel's filter lists them: (type, English name).
TYPES: Tuple[Tuple[str, str], ...] = (
    ("designer", "Designer"),
    ("command", "Commands"),
    ("document", "Documents"),
    ("project", "Project"),
    ("run", "Run"),
    ("code", "Code"),
    ("agent", "Agent"),
    ("layout", "Layout"),
    ("updates", "Updates"),
    ("system", "System"),
)
_TYPE_IDS = {kind for kind, _ in TYPES}

_LEVELS = ((logging.ERROR, "error"), (logging.WARNING, "warning"), (logging.INFO, "info"), (EVENT, "event"))

#: Name of the log file in the logs folder.
LOG_FILE = "pyzed-design.log"
#: Where a crash of the process is written (native panics and Python's faulthandler), in the logs folder.
CRASH_FILE = "crash.log"
#: The crash of the previous session, moved aside when the designer starts.
PREVIOUS_CRASH_FILE = "crash-previous.log"
#: Seconds before the same error, failing again, is logged again (a panel that fails on every frame).
REPEAT_AFTER = 60.0

_FRAME = re.compile(r'File "([^"]+)", line (\d+)')


def log(kind: str) -> logging.Logger:
    """The logger for lines of type ``kind`` (one of ``TYPES``)."""
    return logging.getLogger(f"pyzed.designer.{kind}")


def event(kind: str, message: str, *args: Any) -> None:
    """Logs an event of type ``kind`` (``message % args``, as with ``logging``)."""
    log(kind).log(EVENT, message, *args)


def level_name(levelno: int) -> str:
    """The console level (``"error"``, ``"warning"``, ``"info"``, ``"event"``, ``"debug"``) of a ``logging`` level."""
    return next((name for number, name in _LEVELS if levelno >= number), "debug")


def type_of(logger: str) -> str:
    """The type of a logger's lines: ``pyzed.designer.project`` is ``"project"``; anything else is ``"system"``."""
    prefix = "pyzed.designer."
    if logger.startswith(prefix):
        kind = logger[len(prefix):].split(".", 1)[0]
        return kind if kind in _TYPE_IDS else "designer"
    return "system"


def logs_dir() -> Path:
    """The folder of the designer's log files."""
    from .settings import config_dir

    return config_dir() / "logs"


def origin_in(text: str) -> Optional[Tuple[str, int]]:
    """The last ``File "...", line N`` of a traceback in ``text`` whose file exists, as ``(path, line)``."""
    for path, line in reversed(_FRAME.findall(text)):
        if os.path.isfile(path):
            return path, int(line)
    return None


class _Handler(logging.Handler):
    """Writes ``logging`` records into the Logs panel of the designer that is running."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.center: Optional["LogCenter"] = None

    def emit(self, record: logging.LogRecord) -> None:
        center = self.center
        if center is None:
            return
        try:
            detail = getattr(record, "detail", "") or ""
            if not detail and record.exc_info and record.exc_info[1] is not None:
                detail = logging.Formatter().formatException(record.exc_info)
            origin = getattr(record, "origin", None) or (origin_in(detail) if detail else None)
            center.log.write(level_name(record.levelno), record.getMessage(), source=type_of(record.name),
                             detail=detail, origin=origin)
        except Exception:  # noqa: BLE001 - logging never raises
            self.handleError(record)


_HANDLER = _Handler()


def _wake() -> None:
    # Lines written by other threads should show without waiting for the next event.
    if threading.current_thread() is not threading.main_thread():
        try:
            _core.post(lambda: None)
        except RuntimeError:  # no app running (tests, scripts)
            pass


class LogCenter:
    """The designer's log (the Logs panel), its filters and selection, the menu of the Console and Logs
    panels, and the errors shown in the error dialog."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.log = ui.Log(limit=10000, on_write=_wake)
        self.query = ""
        self.hidden = {"debug"}
        #: The type shown (``None``: every type).
        self.source: Optional[str] = None
        self.selection = ui.LogSelection()
        #: The open line menu: (panel "logs" or "console", the line or ``None``, x, y in the window).
        self.menu: Optional[Tuple[str, Optional[int], float, float]] = None
        #: The error in the error dialog, and how many came after it.
        self.error: Optional[ui.ErrorInfo] = None
        self.more = 0
        self._seen: Dict[str, float] = {}
        self._hooks: Optional[Tuple[Any, Any]] = None
        self._file: Optional[logging.Handler] = None
        self._crash: Optional[Any] = None
        self._faulthandler = False
        #: What the previous session wrote when it crashed (``None`` if it closed normally).
        self.last_crash: Optional[str] = None
        self.pinned = False
        _HANDLER.center = self
        root = logging.getLogger("pyzed")
        if _HANDLER not in root.handlers:
            root.addHandler(_HANDLER)
        root.setLevel(logging.DEBUG)

    # -- hooks ---------------------------------------------------------------------------
    def install(self, *, file: bool = True) -> None:
        """Catches the errors of callbacks and threads, routes Python warnings here and, with ``file``,
        writes the log file. Called when the designer starts; ``uninstall`` undoes it."""
        if self._hooks is None:
            self._hooks = (sys.excepthook, threading.excepthook)
            sys.excepthook = self._excepthook
            threading.excepthook = self._thread_excepthook
        logging.captureWarnings(True)
        warnings = logging.getLogger("py.warnings")
        if _HANDLER not in warnings.handlers:
            warnings.addHandler(_HANDLER)
        if file and self._file is None:
            try:
                folder = logs_dir()
                folder.mkdir(parents=True, exist_ok=True)
                handler = logging.handlers.RotatingFileHandler(folder / LOG_FILE, maxBytes=1_000_000, backupCount=3,
                                                               encoding="utf-8")
            except OSError:
                return
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
            handler.setLevel(EVENT)
            logging.getLogger("pyzed").addHandler(handler)
            logging.getLogger("py.warnings").addHandler(handler)
            self._file = handler
            self._watch_crashes(folder)
        event("designer", "Pyzed Design started (Python %s, %s)", sys.version.split()[0], sys.platform)

    def uninstall(self) -> None:
        """Puts back the hooks ``install`` replaced and closes the log file."""
        if self._hooks is not None:
            sys.excepthook, threading.excepthook = self._hooks
            self._hooks = None
        logging.captureWarnings(False)
        logging.getLogger("py.warnings").removeHandler(_HANDLER)
        if self._file is not None:
            for name in ("pyzed", "py.warnings"):
                logging.getLogger(name).removeHandler(self._file)
            self._file.close()
            self._file = None
        if self._crash is not None:
            import faulthandler

            from .. import _core

            if self._faulthandler:
                faulthandler.disable()
                self._faulthandler = False
            _core.set_crash_file(None)
            self._crash.close()
            self._crash = None

    def _watch_crashes(self, folder: Path) -> None:
        """Keeps what the last session left in ``crash.log`` (it crashed) and writes this session's crashes
        there: native panics and Python's fatal errors (a segmentation fault, for one)."""
        import faulthandler

        from .. import _core

        crash = folder / CRASH_FILE
        try:
            text = crash.read_text(encoding="utf-8", errors="replace").strip() if crash.is_file() else ""
            if text:
                os.replace(crash, folder / PREVIOUS_CRASH_FILE)
                self.last_crash = text
                log("designer").error("Pyzed Design closed unexpectedly last time:\n%s", text)
            self._crash = open(crash, "a", encoding="utf-8")  # noqa: SIM115 - open while the designer runs
        except OSError:
            return
        if not faulthandler.is_enabled():  # (pytest or ``-X faulthandler`` already write them somewhere)
            faulthandler.enable(self._crash)
            self._faulthandler = True
        _core.set_crash_file(str(crash))

    @property
    def file(self) -> Optional[Path]:
        """The log file being written, if any."""
        return Path(self._file.baseFilename) if isinstance(self._file, logging.FileHandler) else None

    def _excepthook(self, kind: type, value: BaseException, tb: Any) -> None:
        previous: Callable[..., Any] = self._hooks[0] if self._hooks else sys.__excepthook__
        try:
            previous(kind, value, tb)
        except Exception:  # noqa: BLE001
            pass
        if not isinstance(value, Exception):  # KeyboardInterrupt, SystemExit
            return
        if value.__traceback__ is None:
            value = value.with_traceback(tb)
        self.report(ui.ErrorInfo.from_exception(value, where=_callback_name(tb)))

    def _thread_excepthook(self, args: Any) -> None:
        previous = self._hooks[1] if self._hooks else threading.__excepthook__
        try:
            previous(args)
        except Exception:  # noqa: BLE001
            pass
        if not isinstance(args.exc_value, Exception):
            return
        name = args.thread.name if args.thread is not None else "?"
        info = ui.ErrorInfo.from_exception(args.exc_value, where=tr("Thread {name}", name=name))
        try:
            _core.post(lambda: self.report(info))
        except RuntimeError:  # no app running
            self.report(info)

    # -- errors --------------------------------------------------------------------------
    def report(self, info: ui.ErrorInfo, *, show: bool = True) -> None:
        """Logs ``info`` (once, even when a panel fails on every frame) and, with ``show``, opens the error
        dialog (or counts it if the dialog is open; a toast if another dialog is open)."""
        key = f"{info.where}\n{info.traceback}"
        now = time.monotonic()
        last = self._seen.get(key)
        self._seen[key] = now
        if last is not None and now - last < REPEAT_AFTER:
            return
        if len(self._seen) > 200:
            self._seen = dict(sorted(self._seen.items(), key=lambda kv: kv[1])[-100:])
        text = f"{info.where}: {info.summary}" if info.where else info.summary
        self.log.write("error", text, source="designer", detail=info.traceback, origin=info.origin)
        d = self.d
        if not show or not d.prefs.error_dialogs:
            return
        if d.dialog == "error" and self.error is not None:
            self.more += 1
        elif d.dialog is None:
            self.error, self.more = info, 0
            d.dialog = "error"
        else:
            d.notify(tr("Something went wrong"), info.summary, kind="error", seconds=6, log=False)
        try:
            _core.post(lambda: None)  # redraw now: the error may come from drawing
        except RuntimeError:
            pass

    def boundary(self, build: Callable[[], Any], where: str, t: Theme) -> Any:
        """``build()``, or an error card when it fails (logged once, with a Details button for the error
        dialog): what each panel and the canvas are drawn through."""
        return ui.error_boundary(build, on_error=lambda info: self.report(info, show=False), where=where,
                                 title=tr("{part} could not be drawn", part=where), on_details=self.show_error,
                                 theme=t)

    def show_error(self, info: ui.ErrorInfo) -> None:
        """Opens the error dialog on ``info``."""
        self.error, self.more = info, 0
        self.d.dialog = "error"

    def close_error(self) -> None:
        """Closes the error dialog."""
        self.error, self.more = None, 0
        if self.d.dialog == "error":
            self.d.dialog = None

    def go_to(self, origin: Optional[Tuple[str, int]]) -> Any:
        """Opens ``(path, line)`` in the Code panel with the cursor on the line; ``None`` if it cannot."""
        if origin is None or not os.path.isfile(origin[0]):
            return None
        d = self.d
        if not d.buffers.open(Path(origin[0])):
            return None
        if d.dialog == "error":
            self.close_error()
        line = max(int(origin[1]), 1)
        d.assist.cursor = (line, 1)
        event("code", "Opened %s at line %d", Path(origin[0]).name, line)
        return _core.Command.set_editor_cursor(d.editor_id, line, 1)

    def show_panel(self) -> None:
        """Shows the Logs panel (from the error dialog: with the errors only)."""
        if self.d.dialog == "error":
            self.close_error()
            self.hidden = {level for level in ui.LOG_LEVELS if level not in ("error", "warning")}
        self.pinned = True
        self.d.show_panel("logs")

    # -- toolbar ---------------------------------------------------------------------------
    def set_query(self, text: str) -> None:
        self.query = text

    def toggle_level(self, level: str) -> None:
        self.hidden ^= {level}

    def set_source(self, source: Optional[str]) -> None:
        self.source = source

    def clear(self) -> None:
        self.log.clear()
        self.selection.clear()

    def copy(self) -> Any:
        return copy_lines(self)

    def open_folder(self) -> None:
        """Opens the folder with the log files in the file manager."""
        folder = logs_dir()
        folder.mkdir(parents=True, exist_ok=True)
        self.d.open_url(folder.as_uri())

    # -- the line menu of the Console and Logs panels ---------------------------------------
    def views(self) -> Dict[str, Any]:
        """The panels with lines: ``"console"`` and ``"logs"`` -> the object with their log and selection."""
        return {"console": self.d.console, "logs": self}

    def open_menu(self, panel: str, entry: Optional[ui.LogEntry]) -> None:
        """Right click on a line (or the empty space) of ``panel``: opens the line menu at the pointer."""
        self.menu = (panel, entry.id if entry is not None else None, *self.d.window_pointer)

    def close_menu(self) -> None:
        self.menu = None

    def _act(self, action: Callable[[], Any]) -> Callable[[], Any]:
        def run() -> Any:
            self.menu = None
            return action()
        return run

    def menu_items(self) -> List[Any]:
        """The items of the open line menu."""
        assert self.menu is not None
        panel, entry_id, _, _ = self.menu
        view = self.views()[panel]
        log, selection = view.log, view.selection
        entry = log.find(entry_id) if entry_id is not None else None
        chosen = [e.id for e in log.entries if e.id in selection]
        shown = [e.id for e in shown_entries(view)]
        items: List[Any] = []
        if entry is not None:
            picked = set(chosen or [entry.id])
            items.append(ui.MenuItem(tr("Copy line") if len(chosen) <= 1 else
                                     tr("Copy {count} lines", count=len(chosen)),
                                     self._act(lambda: copy_selection(view)), icon="copy", keys="ctrl-c"))
            items.append(ui.MenuItem(tr("Copy text only"), self._act(lambda: _core.Command.copy(
                "\n".join(e.text + (f"\n{e.detail}" if e.detail else "") for e in log.entries
                          if e.id in picked))), icon="text"))
        items += [
            ui.MenuItem(tr("Copy all"), self._act(lambda: _core.Command.copy(log.text(shown))), icon="clipboard-copy"),
            ui.MenuItem(tr("Select all"), self._act(lambda: selection.select(shown)), icon="text-select",
                        keys="ctrl-a"),
        ]
        if entry is not None and (entry.origin or entry.detail):
            items.append(ui.SEPARATOR)
            if entry.origin is not None and os.path.isfile(entry.origin[0]):
                items.append(ui.MenuItem(tr("Go to {place}", place=f"{Path(entry.origin[0]).name}:{entry.origin[1]}"),
                                         self._act(lambda: self.go_to(entry.origin)), icon="arrow-up-right"))
            if entry.detail or entry.level == "error":
                items.append(ui.MenuItem(tr("Show the error…"), self._act(lambda: self.show_error(_entry_error(entry))),
                                         icon="scan-text"))
        if entry is not None:
            items += [ui.SEPARATOR,
                      ui.MenuItem(tr("Hide {level} lines", level=entry.level),
                                  self._act(lambda: view.toggle_level(entry.level)), icon="eye-off")]
            if panel == "logs" and entry.source:
                items.append(ui.MenuItem(tr("Only {type}", type=type_label(entry.source)),
                                         self._act(lambda: self.set_source(entry.source)), icon="filter"))
            if panel == "console":
                items.append(ui.MenuItem(tr("Show in Logs"), self._act(self.show_panel), icon="scroll-text"))
        items += [ui.SEPARATOR, ui.MenuItem(tr("Clear"), self._act(view.clear), icon="trash-2", danger=True)]
        return items

    def menu_at(self, t: Theme) -> Tuple[Any, float, float]:
        """The line menu and where it goes, kept inside the window."""
        assert self.menu is not None
        items = self.menu_items()
        _, _, x, y = self.menu
        width, height = self.d.panes.window_size()
        separators = sum(1 for i in items if i == ui.SEPARATOR)
        tall = (len(items) - separators) * 28 + separators * 10 + 12
        if x + MENU_WIDTH > width - 4:
            x = max(x - MENU_WIDTH, 4)
        if y + tall > height - 4:
            y = max(height - tall - 4, 4)
        return ui.menu(items, width=MENU_WIDTH, theme=t), x, y

    def on_key(self, panel: str, combo: str) -> Tuple[bool, Any]:
        """Ctrl+C copies the selected lines, Ctrl+A selects every line shown and Escape clears the selection
        of ``panel`` while it has the keyboard; returns ``(handled, result)``."""
        view = self.views()[panel]
        if combo == "escape" and self.menu is not None:
            self.menu = None
            return True, None
        if combo in ("ctrl-c", "cmd-c") and len(view.selection):
            return True, copy_selection(view)
        if combo in ("ctrl-a", "cmd-a"):
            view.selection.select(e.id for e in shown_entries(view))
            return True, None
        if combo == "escape" and len(view.selection):
            view.selection.clear()
            return True, None
        return False, None


MENU_WIDTH = 240


def _callback_name(tb: Any) -> str:
    """What raised, for the error report: the first function the runtime called (skipping lambdas)."""
    names = []
    while tb is not None:
        names.append(tb.tb_frame.f_code.co_name)
        tb = tb.tb_next
    name = next((n for n in names if not n.startswith("<")), names[0] if names else "")
    return f"{name}()" if name else ""


def _entry_error(entry: ui.LogEntry) -> ui.ErrorInfo:
    """An error dialog's content made from a log line (its text, traceback and origin)."""
    head = entry.text.splitlines()[0] if entry.text else ""
    kind, _, message = head.partition(": ")
    if not message:
        kind, message = tr("Error"), head
    detail = entry.detail or ("\n".join(entry.text.splitlines()[1:]) if "\n" in entry.text else "")
    return ui.ErrorInfo(kind, message, detail or entry.text, entry.origin or origin_in(entry.text), time=entry.time)


def type_label(kind: str) -> str:
    """The name of the log type ``kind`` in the designer's language."""
    return tr(next((name for k, name in TYPES if k == kind), kind.capitalize()))


def shown_entries(view: Any) -> List[ui.LogEntry]:
    """The lines ``view`` (the console or the logs) shows with its filters."""
    from ..ui.console import filtered

    return filtered(view.log.entries, query=view.query, hidden=view.hidden, source=getattr(view, "source", None))


def copy_selection(view: Any) -> Any:
    """The command that copies the selected lines of ``view``."""
    copied(view, len(view.selection))
    return _core.Command.copy(view.log.text(view.selection.ids))


def copy_lines(view: Any) -> Any:
    """The Copy button of ``view`` (the console or the logs): the selected lines, or every line shown."""
    if len(view.selection):
        return copy_selection(view)
    shown = [e.id for e in shown_entries(view)]
    copied(view, len(shown))
    return _core.Command.copy(view.log.text(shown))


def copied(view: Any, lines: int) -> None:
    """Says how many lines were copied (a short toast)."""
    designer = getattr(view, "d", None)
    if designer is not None:
        title = tr("Copied 1 line") if lines == 1 else tr("Copied {count} lines", count=lines)
        designer.notify(title, kind="success", seconds=2, log=False)


def view(d: "Designer", t: Theme) -> Any:
    """Builds the Logs panel."""
    c = d.logs
    c.selection.keep(c.log.entries)
    actions = [ui.icon_button("folder-open", c.open_folder, size="sm", tooltip=tr("Open the log folder"), theme=t)]
    return ui.console(c.log.entries, query=c.query, on_query=c.set_query, hidden=c.hidden,
                      on_toggle_level=c.toggle_level, on_clear=c.clear, on_copy=c.copy, actions=actions,
                      selection=c.selection, on_context=lambda e: c.open_menu("logs", e),
                      on_open=lambda e: c.show_error(_entry_error(e)) if e.detail or e.level == "error" else None,
                      sources=[(kind, type_label(kind)) for kind, _ in TYPES], source=c.source,
                      on_source=c.set_source, show_source=True, placeholder=tr("Filter logs…"),
                      empty=tr("Nothing logged yet."), id="designer-logs", theme=t)


def error_dialog(d: "Designer", t: Theme) -> Any:
    """The error dialog (``d.dialog == "error"``)."""
    c = d.logs
    info = c.error
    if info is None:
        d.dialog = None
        return None
    origin = info.origin if info.origin is not None and os.path.isfile(info.origin[0]) else None
    return ui.error_dialog(info, c.close_error, on_go_to=(lambda: c.go_to(origin)) if origin else None,
                           go_to_label=tr("Go to {place}", place=info.location) if origin else None,
                           on_logs=c.show_panel, more=c.more, theme=t)


def summary(entries: Sequence[ui.LogEntry]) -> Tuple[int, int]:
    """How many error and warning lines there are (the status bar's counter)."""
    errors = sum(e.count for e in entries if e.level == "error")
    warnings = sum(e.count for e in entries if e.level == "warning")
    return errors, warnings
