"""A debug console: log entries with levels, a filter and a toolbar (like a browser's dev tools console).

    log = ui.Log()
    log.write("info", "Started")
    print("hello")                         # with log.capture() active, goes to the log too

    ui.console(log.entries, query=self.query, on_query=self.set_query, on_clear=log.clear)

``Log`` is plain data with a lock, so other threads may write to it (call ``pz.post``
afterwards if the window should redraw right away).

Their text can be selected by dragging (across lines) and copied with Ctrl+C. Whole lines can be
selected like in a list (click, Shift+click for a range, Ctrl+click to add one) when the
console gets a ``LogSelection``; ``on_context`` opens a menu on right click (copy the line, the
selection or everything...) and a selected entry with ``detail`` (a traceback) shows it under the line.
Entries may carry a ``source`` ("project", "agent"...) that ``ui.console`` can filter on.
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Collection, Dict, Iterable, List, Optional, Sequence, Set, TextIO, Tuple

from .. import _core
from ..i18n import t as _t
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme, icon_button
from .inputs import search_input

#: Levels a console knows how to color, in the order its filter buttons show them.
LEVELS = ("debug", "info", "event", "stdout", "stderr", "warning", "error")

_LEVEL_STYLE = {
    "debug": ("bug", "text_muted"),
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
    #: What it comes from ("project", "agent"...): a console can show and filter it.
    source: str = ""
    #: More text, shown under the line while it is selected (a traceback).
    detail: str = ""
    #: ``(path, line)`` of the code the entry is about (where an error comes from).
    origin: Optional[Tuple[str, int]] = None
    #: The entry's number in its log (what a ``LogSelection`` keeps).
    id: int = 0

    @property
    def clock(self) -> str:
        """The entry's local time as ``HH:MM:SS``."""
        return time.strftime("%H:%M:%S", time.localtime(self.time))

    def line(self, *, details: bool = True) -> str:
        """The entry as one line of plain text (its time, level and source, then ``detail`` below it)."""
        source = f" [{self.source}]" if self.source else ""
        text = f"{self.clock} [{self.level}]{source} {self.text}" + (f" (×{self.count})" if self.count > 1 else "")
        return f"{text}\n{self.detail}" if details and self.detail else text


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
    """Entries for ``ui.console``: thread-safe, capped at ``limit``, repeated lines folded.

    Events:
        ``on_write()``: Called after every write (from any thread).
    """

    def __init__(self, limit: int = 5000, on_write: Optional[Callable[[], Any]] = None) -> None:
        self.limit = limit
        self.entries: List[LogEntry] = []
        self.on_write = on_write
        self._lock = threading.Lock()
        self._saved: Optional[tuple] = None
        self.revision = 0
        self._next_id = 1

    def write(self, level: str, text: str, *, source: str = "", detail: str = "",
              origin: Optional[Tuple[str, int]] = None) -> LogEntry:
        """Adds a line at ``level`` (from ``source``, with ``detail`` and ``origin``), calls ``on_write`` and
        returns the entry.

        A line equal to the last one only bumps its count and time; the oldest entries
        are dropped past ``limit``.
        """
        text = str(text).rstrip("\r\n")  # pipes from Windows processes end lines with \r\n
        with self._lock:
            last = self.entries[-1] if self.entries else None
            if last is not None and last.level == level and last.text == text and last.source == source \
                    and last.detail == detail:
                last.count += 1
                last.time = time.time()
                entry = last
            else:
                entry = LogEntry(level, text, source=source, detail=detail, origin=origin, id=self._next_id)
                self._next_id += 1
                self.entries.append(entry)
                del self.entries[: -self.limit]
            self.revision += 1
        if self.on_write is not None:
            self.on_write()
        return entry

    def find(self, entry_id: int) -> Optional[LogEntry]:
        """The entry numbered ``entry_id``, or ``None`` when it is gone."""
        with self._lock:
            return next((e for e in self.entries if e.id == entry_id), None)

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

    def text(self, ids: Optional[Collection[int]] = None) -> str:
        """Everything (or the entries numbered ``ids``) as plain text, for copying."""
        with self._lock:
            return "\n".join(e.line() for e in self.entries if ids is None or e.id in ids)

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


class LogSelection:
    """The selected lines of a ``ui.console``: click selects one, Shift+click a range from the last one
    clicked, Ctrl+click (Cmd on macOS) adds or removes one."""

    def __init__(self) -> None:
        self.ids: Set[int] = set()
        self.anchor: Optional[int] = None

    def __len__(self) -> int:
        return len(self.ids)

    def __contains__(self, entry_id: object) -> bool:
        return entry_id in self.ids

    def click(self, entry_id: int, shown: Sequence[int], *, shift: bool = False, ctrl: bool = False) -> None:
        """Selects after a click on line ``entry_id``; ``shown`` are the ids of the lines on screen, in order."""
        if shift and self.anchor in shown and entry_id in shown:
            a, b = sorted((shown.index(self.anchor), shown.index(entry_id)))
            span = set(shown[a:b + 1])
            self.ids = self.ids | span if ctrl else span
            return
        if ctrl:
            self.ids ^= {entry_id}
        else:
            self.ids = {entry_id}
        self.anchor = entry_id

    def select(self, ids: Iterable[int]) -> None:
        """Selects exactly ``ids`` (all the lines shown, for Ctrl+A)."""
        self.ids = set(ids)

    def clear(self) -> None:
        """Selects nothing."""
        self.ids.clear()
        self.anchor = None

    def keep(self, entries: Iterable[LogEntry]) -> None:
        """Forgets selected lines that are no longer in ``entries`` (cleared or dropped)."""
        alive = {e.id for e in entries}
        self.ids &= alive
        if self.anchor not in alive:
            self.anchor = None


def filtered(entries: Sequence[LogEntry], *, query: str = "", hidden: Collection[str] = (),
             source: Optional[str] = None) -> List[LogEntry]:
    """The entries a ``ui.console`` shows: not of a ``hidden`` level, from ``source`` (if given), with
    ``query`` in their text."""
    needle = query.strip().lower()
    return [e for e in entries if e.level not in hidden and (source is None or e.source == source)
            and (not needle or needle in e.text.lower() or needle in e.source.lower())]


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
    selection: Optional[LogSelection] = None,
    on_context: Optional[Callable[[Optional[LogEntry]], Any]] = None,
    on_open: Optional[Callable[[LogEntry], Any]] = None,
    sources: Sequence[Tuple[str, str]] = (),
    source: Optional[str] = None,
    on_source: Optional[Callable[[Optional[str]], Any]] = None,
    show_source: bool = False,
    placeholder: Optional[str] = None,
    empty: Optional[str] = None,
    font_size: float = 12.5,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A log view with a toolbar: filter box, one toggle per level (with counts), copy and clear.

    ``hidden`` are levels not shown; ``on_toggle_level(level)`` flips one. The list keeps
    scrolling to the newest entry while it is at the bottom.

    The text of the lines can be selected by dragging over it (across lines, like a terminal) and
    copied with Ctrl+C. With a ``selection`` (a ``LogSelection``) a click also selects whole lines; a
    selected line with ``detail`` shows it below. ``on_context(entry)`` runs on right click (``None`` over
    the empty space): open a menu there. ``on_open(entry)`` runs on double click.
    ``sources`` (``(value, label)`` pairs) adds a dropdown that shows only the entries of one
    ``source`` (``None`` for all; ``on_source`` gets the choice), and ``show_source`` tags each line
    with it.

    Events:
        ``on_query(text)``: Receives each edit of the filter.
        ``on_toggle_level(level)``: Called with the level of the clicked toggle.
        ``on_clear()``: Adds a Clear button.
        ``on_copy()``: Adds a Copy button (copy the selected lines, or every line shown).
        ``on_context(line)``: Called with the line right-clicked (``None`` under the lines): open a menu there
            (copy, go to source, clear...).
        ``on_open(line)``: Called with the line double-clicked.
        ``on_source(source)``: Receives the source picked in the dropdown (``None`` for all).
    """
    from .controls import select as _select

    t = _theme(theme)
    counts: Dict[str, int] = {}
    for e in entries:
        counts[e.level] = counts.get(e.level, 0) + e.count
    shown = filtered(entries, query=query, hidden=hidden, source=source)

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
    picker = None
    if sources:
        every = _t("pyzed.console.all_sources")
        labels = {label: value for value, label in sources}
        current = next((label for value, label in sources if value == source), every)
        picker = _core.container(_select([every, *labels], current,
                                         (lambda label: on_source(labels.get(label))) if on_source else None,
                                         size="sm", theme=t), width=150)
    tools = _core.row([
        _core.container(search_input(query, on_query, placeholder=placeholder or _t("pyzed.console.filter"), size="sm", theme=t), width=180),
        picker,
        *toggles,
        _core.space(width="fill"),
        *actions,
        icon_button("copy", on_copy, size="sm", tooltip=_t("pyzed.console.copy_selected" if selection
                                                            else "pyzed.console.copy_all"), theme=t)
        if on_copy is not None else None,
        icon_button("trash-2", on_clear, size="sm", tooltip=_t("pyzed.console.clear"), theme=t)
        if on_clear is not None else None,
    ], spacing=4, align="center")
    bar = _core.container(tools, padding=(4, 8), width="fill", clip=True)

    visible = shown[-1000:]  # drawing tens of thousands of rows would be slow; the newest matter
    group = f"console:{id or 'log'}"  # one drag selects text across lines, like a terminal
    order = [e.id for e in visible]
    rows: List[Any] = []
    for e in visible:
        icon, color = _LEVEL_STYLE.get(e.level, ("dot", "text"))
        fg = t.color(color) if e.level in ("error", "warning", "stderr", "event") else t.text
        picked = selection is not None and e.id in selection
        bg = t.ghost_selected if picked else (
            alpha(t.error, 0.08) if e.level == "error" else (alpha(t.warning, 0.06) if e.level == "warning" else None))
        line = _core.row([
            _core.text(e.clock, size=font_size - 1, font="mono", color=t.text_placeholder, wrap=False),
            _icon(icon, size=12, color=t.color(color)),
            _core.container(_core.text(e.source, size=11, color=t.text_muted, wrap=False), padding=(0, 6),
                            bg=t.element, radius=t.radius_sm) if show_source and e.source else None,
            _core.text(e.text, size=font_size, font="mono", color=fg, wrap=True, width="fill", selectable=group,
                       selection_color=t.selection),
            _icon("chevron-down" if picked else "chevron-right", size=12, color=t.icon_muted) if e.detail else None,
            _core.container(_core.text(f"×{e.count}", size=11, color=t.text_muted), padding=(0, 6), bg=t.element,
                            radius=8) if e.count > 1 else None,
        ], spacing=8, align="start")
        detail = _core.container(_core.text(e.detail, size=font_size - 1, font="mono", color=t.text_muted,
                                            wrap=True, width="fill", selectable=group, selection_color=t.selection),
                                 padding=(4, 0, 2, 20), width="fill") \
            if picked and e.detail else None
        row = _core.container(_core.column([line, detail], width="fill"), padding=(2, 10), width="fill", bg=bg)
        handlers: Dict[str, Any] = {}
        if selection is not None:
            handlers["click"] = lambda ev, i=e.id: selection.click(i, order, shift=bool(ev.shift),
                                                                   ctrl=bool(ev.ctrl or ev.logo))
        if on_context is not None:
            def context(_ev: Any, e: LogEntry = e) -> Any:
                if selection is not None and e.id not in selection:
                    selection.click(e.id, order)
                return on_context(e)
            handlers["right_click"] = context
        if on_open is not None:
            handlers["double_click"] = lambda e=e: on_open(e)
        rows.append(row.on(**handlers) if handlers else row)
    if not rows:
        message = empty or _t("pyzed.console.empty")
        rows.append(_core.container(_core.text(message if not entries else _t("pyzed.console.no_match"),
                                               size=12.5, color=t.text_muted), padding=(8, 10)))
    body: Any = _core.column(rows, width="fill", padding=(2, 0))
    if on_context is not None or selection is not None:
        # a press on the empty space under the lines clears the selection or opens the menu there
        rest = _core.space(width="fill", height=40).on(
            click=selection.clear if selection is not None else None,
            right_click=(lambda: on_context(None)) if on_context is not None else None)
        body = _core.column([body, rest], width="fill")
    body = _core.scrollable(body, id=id, anchor_bottom=True, height="fill", scroller=t.scrollbar,
                            scroller_hover=t.scrollbar_hover, scrollbar_width=6)
    return _core.column([bar, _core.rule(thickness=1, color=t.border_variant), body], width="fill", height="fill")
