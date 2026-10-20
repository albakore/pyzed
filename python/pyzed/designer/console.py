"""The debug console of the designer: what a form prints, the events it raises and its errors while it runs.

Run (F5) starts a session: ``print`` output and tracebacks of the form's handlers, and
each event they handle, go to the Console panel (and still reach the terminal). Its lines can be
selected (click, Shift+click, Ctrl+click, Ctrl+A) and copied (Ctrl+C), and a right click opens a menu
to copy them, go to the file and line of a traceback or clear the console; see ``logs``. A form
run with ``uv run`` (a project whose dependencies the designer lacks) has its output
piped in from the process.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, Optional, Set

from .. import _core, ui
from ..theme import Theme
from . import logs

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer


class ConsoleController:
    """The console's log and filters, and the capture of the running form's output."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.log = ui.Log(on_write=self._wake)
        self.query = ""
        self.hidden: Set[str] = set()
        self.selection = ui.LogSelection()
        self.running: Optional[str] = None  # name of the form whose output is captured
        self.pinned = False  # opened from the View menu: shown even with nothing in it

    @property
    def visible(self) -> bool:
        """Whether the Console panel has a reason to be shown."""
        return self.pinned or self.running is not None or bool(self.log.entries)

    @staticmethod
    def _wake() -> None:
        # Lines written by reader threads should show without waiting for the next event.
        if threading.current_thread() is not threading.main_thread():
            try:
                _core.post(lambda: None)
            except RuntimeError:  # no app running (tests, scripts)
                pass

    # -- sessions ---------------------------------------------------------------
    def start(self, name: str, how: str = "") -> None:
        """Begins capturing for a run of ``name``."""
        self.stop(quiet=True)
        self.running = name
        self.log.write("info", f"▶ {name} started{f' ({how})' if how else ''}")
        logs.event("run", "Started %s%s", name, f" ({how})" if how else "")
        self.log.capture()

    def stop(self, *, quiet: bool = False) -> None:
        """Ends the capture of the running form's output, logging that it stopped unless ``quiet``."""
        if self.running is None:
            return
        self.log.release()
        if not quiet:
            self.log.write("info", f"■ {self.running} stopped")
        logs.event("run", "Stopped %s", self.running)
        self.running = None

    def event(self, level: str, text: str) -> None:
        """Where the running form reports events and handler errors (``FormRuntime.log``)."""
        if level == "event" and not self.d.prefs.log_events:
            return
        origin = logs.origin_in(text) if level == "error" else None
        self.log.write(level, text, origin=origin)
        if level == "error":  # the Logs panel keeps the errors of the running form too
            head, _, rest = text.partition("\n")
            logs.log("run").error(head, extra={"origin": origin, "detail": rest})
        else:
            logs.log("run").log(logs.EVENT if level == "event" else logging.INFO, text)

    def pipe(self, process: Any) -> None:
        """Reads a ``uv run`` process's output into the log."""
        if getattr(process, "stdout", None) is not None:
            def ended() -> None:
                self.log.write("info", "■ process ended")
                logs.event("run", "The process ended (exit code %s)", process.poll())
            self.log.pipe(process.stdout, "auto", on_end=ended)

    # -- toolbar --------------------------------------------------------------------
    def set_query(self, text: str) -> None:
        """Sets the text that filters the console's lines (typed in its search box)."""
        self.query = text

    def toggle_level(self, level: str) -> None:
        """Hides the lines of ``level`` if they are shown, or shows them again."""
        self.hidden ^= {level}

    def clear(self) -> None:
        """Empties the console's log."""
        self.log.clear()
        self.selection.clear()

    def copy(self) -> Any:
        """Returns the command that copies the whole log, as text, to the clipboard."""
        return _core.Command.copy(self.log.text())

    def poll(self) -> None:
        """Ends the session when the form's window was closed."""
        d = self.d
        if self.running is None:
            return
        preview_open = d.preview is not None and d.preview.is_open
        process = d.projects.process
        process_alive = process is not None and process.poll() is None
        if not preview_open and not process_alive:
            self.stop()


def view(d: "Designer", t: Theme) -> Any:
    """Builds the Console panel: the log with its filters and the run, stop and status controls."""
    c = d.console
    running = c.running is not None
    actions = [
        ui.badge("Running" if running else "Idle", tint="success" if running else "accent", icon="circle", theme=t)
        if running else None,
        ui.icon_button("square", d.stop_form, size="sm", tooltip="Stop (Shift+F5)", disabled=not running, theme=t),
        ui.icon_button("play", d.run_form, size="sm", tooltip="Run (F5)", theme=t),
    ]
    c.selection.keep(c.log.entries)
    return ui.console(c.log.entries, query=c.query, on_query=c.set_query, hidden=c.hidden,
                      on_toggle_level=c.toggle_level, on_clear=c.clear, on_copy=c.copy, actions=actions,
                      selection=c.selection, on_context=lambda e: d.logs.open_menu("console", e),
                      on_open=lambda e: d.logs.go_to(e.origin) if e.origin else None,
                      id="designer-console", theme=t)
