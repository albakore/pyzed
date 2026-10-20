"""Error boundaries: a part of the view that fails to draw shows an error card instead of taking the
whole window down, and an error dialog shows what went wrong with buttons to copy it and to go to it.

    def view(self):
        sidebar = ui.error_boundary(lambda: self.sidebar(), on_error=self.report, title="Sidebar")
        ...

    def report(self, info: ui.ErrorInfo):
        self.error = info                      # show ui.error_dialog(info, ...) over the view

``ErrorInfo.from_exception`` turns an exception into what the card and the dialog show: its type and
message, the traceback, and the file and line it comes from.
"""

from __future__ import annotations

import os
import sys
import sysconfig
import traceback as _traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, Tuple

from .. import _core
from ..i18n import t as _t
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme, button
from .overlays import modal

#: Folders of the standard library and installed packages: an error's origin is looked for outside them.
_LIBRARY_DIRS = tuple(os.path.normcase(os.path.realpath(p)) for p in {
    sysconfig.get_paths().get("stdlib", ""), sysconfig.get_paths().get("purelib", ""),
    sysconfig.get_paths().get("platlib", "")} if p)
_PYZED_DIR = os.path.normcase(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


def _is_library(path: str) -> bool:
    real = os.path.normcase(os.path.realpath(path))
    return real.startswith(_LIBRARY_DIRS) or real.startswith(_PYZED_DIR) or path.startswith("<")


@dataclass(frozen=True)
class ErrorInfo:
    """An error as the error card and dialog show it."""

    #: The exception's type name: ``"ZeroDivisionError"``.
    kind: str
    message: str
    #: The whole traceback, as Python prints it.
    traceback: str = ""
    #: ``(path, line)`` of the code it comes from: the last frame outside the standard library,
    #: installed packages and Pyzed, or else the last frame.
    origin: Optional[Tuple[str, int]] = None
    #: What was running: ``"Properties panel"``, ``"save"``...
    where: str = ""
    #: When it happened (``time.time()``).
    time: float = field(default=0.0, compare=False)

    @classmethod
    def from_exception(cls, err: BaseException, *, where: str = "",
                       prefer: Optional[Callable[[str], bool]] = None) -> "ErrorInfo":
        """Describes ``err``. ``prefer(path)`` picks the frames that may be its origin (the last of them
        wins); by default, those outside the standard library, installed packages and Pyzed itself."""
        import time

        frames = _traceback.extract_tb(err.__traceback__) if err.__traceback__ is not None else []
        wanted = prefer or (lambda path: not _is_library(path))
        chosen = next((f for f in reversed(frames) if f.filename and wanted(f.filename)), None)
        if chosen is None and frames:
            chosen = frames[-1]
        origin = (chosen.filename, chosen.lineno or 1) if chosen is not None else None
        text = "".join(_traceback.format_exception(type(err), err, err.__traceback__)).rstrip()
        return cls(type(err).__name__, str(err), text, origin, where, time.time())

    @classmethod
    def current(cls, *, where: str = "") -> Optional["ErrorInfo"]:
        """The exception being handled (inside an ``except`` block), or ``None``."""
        err = sys.exc_info()[1]
        return cls.from_exception(err, where=where) if err is not None else None

    @property
    def summary(self) -> str:
        """``Type: message`` (just the type when the message is empty)."""
        return f"{self.kind}: {self.message}" if self.message else self.kind

    @property
    def location(self) -> str:
        """``file.py:12`` for the origin, or ``""``."""
        if self.origin is None:
            return ""
        return f"{os.path.basename(self.origin[0])}:{self.origin[1]}"

    def report(self) -> str:
        """Everything as plain text, to copy into a bug report."""
        head = [f"{self.where}: {self.summary}" if self.where else self.summary]
        if self.origin is not None:
            head.append(f"at {self.origin[0]}:{self.origin[1]}")
        return "\n".join(head) + (f"\n\n{self.traceback}" if self.traceback else "")


def _copy(info: ErrorInfo) -> Callable[[], Any]:
    return lambda: _core.Command.copy(info.report())


def error_card(
    info: ErrorInfo,
    *,
    title: Optional[str] = None,
    on_details: Any = None,
    actions: Iterable[Any] = (),
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """What a failed ``error_boundary`` shows: the error, where it comes from, and buttons to copy it
    and (with ``on_details``) to see all of it."""
    t = _theme(theme)
    heading = title or _t("pyzed.errors.failed_to_draw")
    lines = [
        _core.row([_icon("circle-x", size=16, color=t.error),
                   _core.text(heading, size=13.5, weight="semibold", color=t.text, wrap=True, width="fill")],
                  spacing=8, align="center"),
        _core.text(info.summary, size=12.5, font="mono", color=t.text, wrap=True),
        _core.text(_t("pyzed.errors.at", location=info.location), size=12, color=t.text_muted)
        if info.location else None,
        _core.row([
            button(_t("pyzed.errors.copy"), _copy(info), icon="copy", size="sm", theme=t),
            button(_t("pyzed.errors.details"), on_details, icon="scan-text", size="sm", variant="ghost", theme=t)
            if on_details is not None else None,
            *actions,
        ], spacing=6),
    ]
    card = _core.container(_core.column(lines, spacing=8, width="fill"), padding=12, width="fill",
                           bg=alpha(t.error, 0.08), border_color=alpha(t.error, 0.45), border_width=1,
                           radius=t.radius)
    return _core.container(card, padding=10, width="fill", height="fill")


def error_boundary(
    build: Callable[[], Any],
    *,
    on_error: Optional[Callable[[ErrorInfo], Any]] = None,
    title: Optional[str] = None,
    where: str = "",
    on_details: Optional[Callable[[ErrorInfo], Any]] = None,
    fallback: Optional[Callable[[ErrorInfo], Any]] = None,
    theme: Optional[Theme] = None,
) -> Any:
    """Returns ``build()``, or an error card when it raises, so one broken part never breaks the window.

    ``on_error(info)`` is told about the error (an ``ErrorInfo``) each time the part is drawn and fails;
    report it once per error, for example by comparing ``info.traceback``. ``title`` heads the card and
    ``where`` names the part in the report; ``on_details(info)`` adds a Details button (open an
    ``error_dialog``); ``fallback(info)`` replaces the card with your own widget.
    """
    try:
        return build()
    except Exception as err:  # noqa: BLE001 - the boundary's job
        info = ErrorInfo.from_exception(err, where=where or title or "")
    if on_error is not None:
        try:
            on_error(info)
        except Exception:  # noqa: BLE001 - reporting must not break the fallback
            _traceback.print_exc()
    if fallback is not None:
        return fallback(info)
    return error_card(info, title=title, on_details=(lambda: on_details(info)) if on_details else None,
                      theme=theme)


def error_dialog(
    info: ErrorInfo,
    on_close: Any,
    *,
    title: Optional[str] = None,
    on_go_to: Any = None,
    go_to_label: Optional[str] = None,
    on_logs: Any = None,
    more: int = 0,
    width: Any = 680,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A dialog with an error: its message, where it comes from and the traceback (selectable), with
    buttons to copy it all, to go to its origin (``on_go_to``, labelled ``go_to_label``), to see it among
    the logs (``on_logs``) and to close. ``more`` says how many other errors came after it."""
    t = _theme(theme)
    location = info.location
    body = _core.column([
        _core.text(info.summary, size=13.5, font="mono", color=t.error, wrap=True),
        _core.text(_t("pyzed.errors.in_where", where=info.where), size=12.5, color=t.text_muted)
        if info.where else None,
        _core.text(_t("pyzed.errors.at", location=f"{info.origin[0]}:{info.origin[1]}"), size=12.5,
                   color=t.text_muted, wrap=True) if location and info.origin else None,
        _core.container(
            _core.code_editor(f"pyzed-error:{info.time}:{hash(info.traceback)}", info.traceback or info.summary,
                              size=12, line_height=18, gutter=False, wrap=True, height=240, bg=t.editor,
                              color=t.editor_text, selection_color=t.selection, scrollbar_color=t.scrollbar,
                              cursor_blink=False, cursor_width=1.0, match_brackets=False,
                              selection_highlight=False, readonly=True),
            width="fill", border_color=t.border_variant, border_width=1, radius=t.radius_sm, clip=True)
        if info.traceback else None,
        _core.text(_t("pyzed.errors.more", count=more), size=12, color=t.text_muted) if more else None,
    ], spacing=8, width="fill")
    footer = [
        button(_t("pyzed.errors.show_logs"), on_logs, icon="scroll-text", variant="ghost", theme=t)
        if on_logs is not None else None,
        _core.space(width="fill"),
        button(_t("pyzed.errors.copy"), _copy(info), icon="copy", theme=t),
        button(go_to_label or _t("pyzed.errors.go_to"), on_go_to, icon="arrow-up-right", theme=t)
        if on_go_to is not None else None,
        button(_t("pyzed.close"), on_close, variant="solid", theme=t),
    ]
    return modal(body, title=title or _t("pyzed.errors.title"), icon="circle-x", on_close=on_close, width=width,
                 footer=[f for f in footer if f is not None], theme=t)
