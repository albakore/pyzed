"""A debug console: log entries with levels, a filter and a toolbar (like a browser's dev tools console).

    log = ui.Log()
    log.write("info", "Started")
    print("hello")                         # with log.capture() active, goes to the log too

    ui.console(log.entries, query=self.query, on_query=self.set_query, on_clear=log.clear)

``Log`` is plain data with a lock, so other threads may write to it (call ``pz.post``
afterwards if the window should redraw right away).
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, Iterable, List, Optional, Sequence, TextIO

from .. import _core
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme, icon_button
from .inputs import search_input

#: Levels a console knows how to color, in the order its filter buttons show them.
LEVELS = ("info", "event", "stdout", "stderr", "warning", "error")

_LEVEL_STYLE = {
    "info": ("info", "text_muted"),
    "event": ("zap", "text_accent"),
    "stdout": ("chevron-right", "text"),
    "stderr": ("chevron-right", "warning"),
    "warning": ("triangle-alert", "warning"),
    "error": ("circle-x", "error"),
}


@dataclass
class LogEntry:
    level: str
    text: str
    time: float = field(default_factory=time.time)
    #: How many identical entries in a row this one stands for.
    count: int = 1

    @property
    def clock(self) -> str:
        """The entry's local time as ``HH:MM:SS``."""
        return time.strftime("%H:%M:%S", time.localtime(self.time))


class _Tee:
    """A text stream that writes to the original stream and, line by line, to a ``Log``."""

    def __init__(self, log: "Log", level: str, original: TextIO) -> None:
        self.log = log
        self.level = level
        self.original = original
        self._buffer = ""

    def write(self, text: str) -> int:
        try:
            self.original.write(text)
        except (OSError, ValueError):  # pragma: no cover - a closed console
            pass
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.log.write(self.level, line)
        return len(text)

    def flush(self) -> None:
        if self._buffer:
            self.log.write(self.level, self._buffer)
            self._buffer = ""
        try:
            self.original.flush()
        except (OSError, ValueError):  # pragma: no cover
            pass

    def __getattr__(self, name: str) -> Any:
        return getattr(self.original, name)


class Log:
    """Entries for ``ui.console``: thread-safe, capped at ``limit``, repeated lines folded."""

    def __init__(self, limit: int = 5000, on_write: Optional[Callable[[], Any]] = None) -> None:
        self.limit = limit
        self.entries: List[LogEntry] = []
        self.on_write = on_write
        self._lock = threading.Lock()
        self._saved: Optional[tuple] = None
        self.revision = 0

    def write(self, level: str, text: str) -> None:
        """Adds a line at ``level`` and calls ``on_write``.

        A line equal to the last one only bumps its count and time; the oldest entries
        are dropped past ``limit``.
        """
        text = str(text).rstrip("\r\n")  # pipes from Windows processes end lines with \r\n
        with self._lock:
            last = self.entries[-1] if self.entries else None
            if last is not None and last.level == level and last.text == text:
                last.count += 1
                last.time = time.time()
            else:
                self.entries.append(LogEntry(level, text))
                del self.entries[: -self.limit]
            self.revision += 1
        if self.on_write is not None:
            self.on_write()

    def clear(self) -> None:
        """Removes every entry."""
        with self._lock:
            self.entries.clear()
            self.revision += 1

    def counts(self) -> Dict[str, int]:
        """Returns how many lines there are per level, counting folded repeats."""
        out: Dict[str, int] = {}
        with self._lock:
            for e in self.entries:
                out[e.level] = out.get(e.level, 0) + e.count
        return out

    def text(self) -> str:
        """Everything as plain text (for copying)."""
        with self._lock:
            return "\n".join(f"{e.clock} [{e.level}] {e.text}" + (f" (×{e.count})" if e.count > 1 else "")
                             for e in self.entries)

    # -- capturing print() and tracebacks ---------------------------------------
    @property
    def capturing(self) -> bool:
        """Whether ``sys.stdout``/``sys.stderr`` are being copied into the log."""
        return self._saved is not None

    def capture(self) -> "Log":
        """Copies ``sys.stdout``/``sys.stderr`` into the log (they still reach the terminal)."""
        if self._saved is None:
            self._saved = (sys.stdout, sys.stderr)
            sys.stdout = _Tee(self, "stdout", sys.stdout)  # type: ignore[assignment]
            sys.stderr = _Tee(self, "stderr", sys.stderr)  # type: ignore[assignment]
        return self

    def release(self) -> None:
        """Stops capturing and puts the original streams back."""
        if self._saved is None:
            return
        for stream in (sys.stdout, sys.stderr):
            if isinstance(stream, _Tee):
                stream.flush()
        sys.stdout, sys.stderr = self._saved
        self._saved = None

    def __enter__(self) -> "Log":
        return self.capture()

    def __exit__(self, *_exc: Any) -> None:
        self.release()

    def pipe(self, stream: Any, level: str = "stdout", on_end: Optional[Callable[[], Any]] = None) -> threading.Thread:
        """Reads a subprocess pipe (bytes or text) line by line into the log, in a background thread."""

        def read() -> None:
            try:
                for raw in iter(stream.readline, b"" if "b" in getattr(stream, "mode", "rb") else ""):
                    line = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
                    if not line:
                        break
                    line = line.rstrip("\r\n")  # Windows pipes end lines with \r\n
                    self.write("stderr" if level == "auto" and _looks_like_error(line) else
                               ("stdout" if level == "auto" else level), line)
            except (OSError, ValueError):
                pass
            if on_end is not None:
                on_end()

        thread = threading.Thread(target=read, daemon=True, name="pyzed-log-pipe")
        thread.start()
        return thread


def _looks_like_error(line: str) -> bool:
    return line.startswith(("Traceback", "  File ", "    ")) or "Error" in line.split(":", 1)[0]


def console(
    entries: Sequence[LogEntry],
    *,
    query: str = "",
    on_query: Any = None,
    hidden: Collection[str] = (),
    on_toggle_level: Optional[Callable[[str], Any]] = None,
    on_clear: Any = None,
    on_copy: Any = None,
    actions: Iterable[Any] = (),
    font_size: float = 12.5,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A log view with a toolbar: filter box, one toggle per level (with counts), copy and clear.

    ``hidden`` are levels not shown; ``on_toggle_level(level)`` flips one. The list keeps
    scrolling to the newest entry while it is at the bottom.
    """
    t = _theme(theme)
    counts: Dict[str, int] = {}
    for e in entries:
        counts[e.level] = counts.get(e.level, 0) + e.count
    needle = query.strip().lower()
    shown = [e for e in entries if e.level not in hidden and (not needle or needle in e.text.lower())]

    toggles = []
    for level in LEVELS:
        if not counts.get(level):
            continue
        icon, color = _LEVEL_STYLE[level]
        on = level not in hidden
        toggles.append(_core.button(
            _core.row([_icon(icon, size=12, color=t.color(color) if on else t.text_disabled),
                       _core.text(f"{counts[level]}", size=12, color=t.text if on else t.text_disabled)],
                      spacing=4, align="center"),
            (lambda lv=level: on_toggle_level(lv)) if on_toggle_level else None,
            padding=(2, 6), bg=t.ghost_selected if on else "transparent", hover_bg=t.ghost_hover,
            radius=t.radius_sm))
    tools = _core.row([
        _core.container(search_input(query, on_query, placeholder="Filter output…", size="sm", theme=t), width=180),
        *toggles,
        _core.space(width="fill"),
        *actions,
        icon_button("copy", on_copy, size="sm", tooltip="Copy all", theme=t) if on_copy is not None else None,
        icon_button("trash-2", on_clear, size="sm", tooltip="Clear", theme=t) if on_clear is not None else None,
    ], spacing=4, align="center")
    bar = _core.container(tools, padding=(4, 8), width="fill", clip=True)

    rows: List[Any] = []
    for e in shown[-1000:]:  # drawing tens of thousands of rows would be slow; the newest matter
        icon, color = _LEVEL_STYLE.get(e.level, ("dot", "text"))
        fg = t.color(color) if e.level in ("error", "warning", "stderr", "event") else t.text
        bg = alpha(t.error, 0.08) if e.level == "error" else (alpha(t.warning, 0.06) if e.level == "warning" else None)
        rows.append(_core.container(_core.row([
            _core.text(e.clock, size=font_size - 1, font="mono", color=t.text_placeholder, wrap=False),
            _icon(icon, size=12, color=t.color(color)),
            _core.text(e.text, size=font_size, font="mono", color=fg, wrap=True, width="fill"),
            _core.container(_core.text(f"×{e.count}", size=11, color=t.text_muted), padding=(0, 6), bg=t.element,
                            radius=8) if e.count > 1 else None,
        ], spacing=8, align="start"), padding=(2, 10), width="fill", bg=bg))
    if not rows:
        rows.append(_core.container(_core.text("No output yet." if not entries else "Nothing matches the filter.",
                                               size=12.5, color=t.text_muted), padding=(8, 10)))
    body = _core.scrollable(_core.column(rows, width="fill", padding=(2, 0)), id=id, anchor_bottom=True,
                            height="fill", scroller=t.scrollbar, scroller_hover=t.scrollbar_hover,
                            scrollbar_width=6)
    return _core.column([bar, _core.rule(thickness=1, color=t.border_variant), body], width="fill", height="fill")
