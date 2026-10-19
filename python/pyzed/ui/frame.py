"""Window frames: a title bar of your own, with window buttons and menus, instead of the system's.

``ui.window_frame`` draws the whole frame of a window opened without system decorations
(``Window.frame = "custom"``): a title bar you can drag (double click maximizes), the minimize,
maximize and close buttons in the style of a platform, menus on the left like Zed, and the
borders that resize the window. ``ui.window_title_bar`` is the bar alone, and with no callbacks
it is inert, which is how Pyzed Design previews a form in the frame of each platform.
"""

from __future__ import annotations

import dataclasses
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, List, Optional, Sequence, Union

from .. import _core
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme
from .display import popover
from .lists import MenuItem, menu as _menu

#: The control styles a frame can draw.
PLATFORMS = ("macos", "windows", "gnome", "ubuntu", "kde")
#: Names to show for each style.
PLATFORM_LABELS = {"macos": "macOS", "windows": "Windows 11", "gnome": "GNOME", "ubuntu": "Ubuntu",
                   "kde": "KDE Plasma"}
#: The title bar height each platform uses by default.
HEIGHTS = {"macos": 30.0, "windows": 32.0, "gnome": 38.0, "ubuntu": 38.0, "kde": 30.0, "overlay": 30.0}
#: Room left for the system's own buttons when macOS draws them over the bar (``overlay``).
OVERLAY_INSET = 78.0

FrameLike = Union[str, bool, None]


@dataclass
class Menu:
    """A menu of a window frame's menu bar: ``Menu("File", [ui.MenuItem("Open", app.open), ...])``."""

    label: str
    items: Sequence[Union[MenuItem, str]] = field(default_factory=list)


def system_platform() -> str:
    """The style of the system's own window buttons: ``"macos"``, ``"windows"``, ``"kde"``, ``"ubuntu"`` or
    ``"gnome"`` (other Linux desktops). Under WSL it is ``"windows"``, the desktop the window shows up on."""
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    from .._platform import is_wsl

    if is_wsl():
        return "windows"
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP", "") + ":" + os.environ.get("DESKTOP_SESSION", "")).lower()
    if "kde" in desktop or "plasma" in desktop:
        return "kde"
    if "ubuntu" in desktop:
        return "ubuntu"
    return "gnome"


def resolve(frame: FrameLike) -> Optional[str]:
    """What ``Window.frame`` means here: ``None`` for the system's frame, otherwise the style of the buttons
    to draw (one of ``PLATFORMS``), or ``"overlay"`` on macOS, where the system draws its own buttons over
    the custom bar."""
    if frame is None or frame is False or frame == "system":
        return None
    if frame is True or frame in ("custom", "auto"):
        style = system_platform()
        return "overlay" if style == "macos" else style
    if frame in PLATFORMS:
        return str(frame)
    raise ValueError(f"invalid window frame {frame!r}: use None, 'system', 'custom' or one of {', '.join(PLATFORMS)}")


def controls_on_left(style: str) -> bool:
    """Whether the window buttons of ``style`` sit at the start of the bar (macOS) instead of the end."""
    return style in ("macos", "overlay")


def controls_width(style: str) -> float:
    """How much of the bar the window buttons of ``style`` take, with their margins."""
    return {"macos": 70.0, "overlay": OVERLAY_INSET, "windows": 138.0, "gnome": 108.0, "ubuntu": 108.0,
            "kde": 86.0}.get(style, 0.0)


def start_x(style: str) -> float:
    """Where the first ``start`` item of a title bar in ``style`` begins, from the window's left edge
    (to open a menu under it)."""
    return controls_width(style) + 10 if controls_on_left(style) else 8.0


def end_x(style: str) -> float:
    """How far the last ``end`` item of a title bar in ``style`` ends from the window's right edge."""
    return 8.0 if controls_on_left(style) else controls_width(style) + 10


# ---------------------------------------------------------------------------
# The window being drawn
# ---------------------------------------------------------------------------


class _Drawing:
    __slots__ = ("window", "style", "drawn")

    def __init__(self, window: Any, style: Optional[str]) -> None:
        self.window, self.style, self.drawn = window, style, False


_drawing: List[_Drawing] = []


@contextmanager
def drawing(window: Any) -> Iterator[_Drawing]:
    """Marks ``window`` as the one whose ``view()`` runs, so ``window_frame`` finds it; the runtime does this.
    ``drawn`` tells afterwards whether the view drew its own frame."""
    current = _Drawing(window, resolve(getattr(window, "frame", None)))
    _drawing.append(current)
    try:
        yield current
    finally:
        _drawing.pop()


def _current() -> Optional[_Drawing]:
    return _drawing[-1] if _drawing else None


class _MenuState:
    """Which menu of a frame is open, where, and whether the menu button shows every menu's name."""

    __slots__ = ("open", "x", "expanded")

    def __init__(self) -> None:
        self.open: Optional[int] = None
        self.x = 0.0
        self.expanded = False


_loose_state = _MenuState()


def _menu_state(window: Any) -> _MenuState:
    if window is None:
        return _loose_state
    state = window.__dict__.get("_pyzed_frame_menu")
    if state is None:
        state = window.__dict__["_pyzed_frame_menu"] = _MenuState()
    return state


def _close_window(window: Any) -> Any:
    """Asks to close ``window`` like the system's close button does: ``on_close()`` may keep it open."""
    hook = getattr(window, "on_close", None)
    if hook is not None and hook() is False:
        return None
    return _core.Command.close_window(window)


# ---------------------------------------------------------------------------
# Window buttons
# ---------------------------------------------------------------------------


def _plain(content: Any, width: float, height: float, *, bg: Optional[str] = None, color: Optional[str] = None,
           radius: float = 0) -> Any:
    return _core.container(content, width=width, height=height, center=True, bg=bg, color=color, radius=radius)


def _press(content: Any, on_press: Any, width: float, height: float, *, color: str, hover_bg: str,
           hover_color: Optional[str] = None, bg: Optional[str] = None, radius: float = 0) -> Any:
    return _core.button(_core.container(content, width="fill", height="fill", center=True), on_press,
                        width=width, height=height, padding=0, bg=bg or "transparent", color=color,
                        hover_bg=hover_bg, hover_color=hover_color or color, pressed_bg=hover_bg, radius=radius)


def _macos(on: dict, focused: bool, t: Theme) -> Any:
    colors = [("close", "#ff5f57", "#e0443e", "x"), ("minimize", "#febc2e", "#dea123", "minus"),
              ("maximize", "#28c840", "#1aab29", "plus")]
    idle = alpha(t.text_muted, 0.35)

    def dot(name: str, fill: str, rim: str, glyph: Optional[str]) -> Any:
        if not focused:
            fill, rim = idle, idle
        inner = _icon(glyph, size=9, color="#4d0000" if name == "close" else "#5a3d00" if name == "minimize"
                      else "#0b4d10") if glyph else None
        face = _core.container(inner, width=12, height=12, center=True, bg=fill, radius=6, border_color=rim,
                               border_width=0.5)
        callback = on.get(name)
        if callback is None:
            return face
        return _core.button(face, callback, padding=0, width=12, height=12, bg="transparent", radius=6)

    plain = _core.row([dot(n, f, r, None) for n, f, r, _g in colors], spacing=8, align="center")
    if not on:
        return plain
    # macOS shows the symbols on all three buttons while the pointer is over any of them
    marked = _core.row([dot(n, f, r, g) for n, f, r, g in colors], spacing=8, align="center")
    return _core.hover(plain, marked)


def _windows(on: dict, maximized: bool, focused: bool, height: float, t: Theme) -> Any:
    color = t.text if focused else t.text_muted
    hover = alpha(t.text, 0.08)
    glyphs = [("minimize", "minus", 15), ("maximize", "copy" if maximized else "square", 11), ("close", "x", 16)]
    out = []
    for name, glyph, size in glyphs:
        mark = _icon(glyph, size=size)
        callback = on.get(name)
        if callback is None:
            out.append(_plain(mark, 46, height, color=color))
        elif name == "close":
            out.append(_press(mark, callback, 46, height, color=color, hover_bg="#c42b1c", hover_color="#ffffff"))
        else:
            out.append(_press(mark, callback, 46, height, color=color, hover_bg=hover))
    return _core.row(out, align="center")


def _gnome(on: dict, maximized: bool, focused: bool, t: Theme, ubuntu: bool = False) -> Any:
    color = t.text if focused else t.text_muted
    out = []
    glyphs = [("minimize", "minus", 14), ("maximize", "copy" if maximized else "square", 11), ("close", "x", 14)]
    for name, glyph, size in glyphs:
        bg, mark_color, hover = alpha(t.text, 0.1), color, alpha(t.text, 0.16)
        if ubuntu:  # Yaru: an orange close button, the others only show a circle on hover
            if name == "close":
                bg, mark_color, hover = ("#e95420" if focused else alpha(t.text, 0.18)), "#ffffff", "#f06a3a"
            else:
                bg = "transparent"
        mark = _icon(glyph, size=size)
        callback = on.get(name)
        if callback is None:
            out.append(_plain(mark, 24, 24, bg=bg, color=mark_color, radius=12))
        else:
            out.append(_press(mark, callback, 24, 24, color=mark_color, bg=bg, hover_bg=hover, radius=12))
    return _core.row(out, spacing=12, align="center")


def _kde(on: dict, maximized: bool, focused: bool, t: Theme) -> Any:
    color = t.text if focused else t.text_muted
    glyphs = [("minimize", "chevron-down", 16), ("maximize", "diamond" if maximized else "chevron-up", 16),
              ("close", "x", 13)]
    out = []
    for name, glyph, size in glyphs:
        mark = _icon(glyph, size=size)
        callback = on.get(name)
        bg = alpha(t.text, 0.14) if name == "close" else None
        if callback is None:
            out.append(_plain(mark, 20, 20, bg=bg, color=color, radius=10))
        elif name == "close":
            out.append(_press(mark, callback, 20, 20, color=color, bg=bg, hover_bg="#da4453", hover_color="#ffffff",
                              radius=10))
        else:
            out.append(_press(mark, callback, 20, 20, color=color, hover_bg=alpha(t.text, 0.12), radius=10))
    return _core.row(out, spacing=8, align="center")


def window_controls(
    style: Optional[str] = None,
    *,
    on_minimize: Any = None,
    on_maximize: Any = None,
    on_close: Any = None,
    maximized: bool = False,
    focused: bool = True,
    height: Optional[float] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """The minimize, maximize and close buttons in the style of a platform (``"macos"``, ``"windows"``,
    ``"gnome"``, ``"ubuntu"`` or ``"kde"``; ``None`` is this system's). A button without a callback is drawn
    but does nothing (for previews). ``maximized`` shows the restore symbol, ``focused=False`` the dimmed
    look of a window in the background."""
    t = _theme(theme)
    style = style or system_platform()
    if style == "overlay":  # the system draws them
        return _core.space(width=OVERLAY_INSET, height=1)
    on = {k: v for k, v in (("minimize", on_minimize), ("maximize", on_maximize), ("close", on_close)) if v is not None}
    height = height or HEIGHTS.get(style, 32.0)
    width = controls_width(style)
    if style == "macos":
        return _core.container(_macos(on, focused, t), width=width, height=height, padding=(0, 0, 0, 12),
                               align_y="center")
    if style == "windows":
        return _core.container(_windows(on, maximized, focused, height, t), width=width, height=height)
    if style in ("gnome", "ubuntu"):
        return _core.container(_gnome(on, maximized, focused, t, ubuntu=style == "ubuntu"), width=width,
                               height=height, padding=(0, 8, 0, 4), align_x="end", align_y="center")
    if style == "kde":
        return _core.container(_kde(on, maximized, focused, t), width=width, height=height, padding=(0, 6, 0, 4),
                               align_x="end", align_y="center")
    raise ValueError(f"invalid window controls style {style!r}: use one of {', '.join(PLATFORMS)}")


# ---------------------------------------------------------------------------
# Title bar and frame
# ---------------------------------------------------------------------------


def _menu_bar(menus: Sequence[Menu], state: _MenuState, button: bool, height: float, t: Theme) -> List[Any]:
    def opener(index: int) -> Callable[[Any], None]:
        def open_menu(event: Any) -> None:
            if state.open == index:
                state.open, state.expanded = None, False
            else:
                state.open, state.expanded = index, True
                state.x = event.window_x - event.x
        return open_menu

    def hover(index: int) -> Callable[[Any], None]:
        def switch(event: Any) -> None:
            if state.open is not None and state.open != index:  # an open menu follows the pointer
                state.open, state.x = index, event.window_x - event.x
        return switch

    def face(content: Any, selected: bool, **size: Any) -> Any:
        def box(bg: Optional[str]) -> Any:
            return _core.container(content, height=24, radius=t.radius, bg=bg, **size)
        if selected:
            return box(alpha(t.text, 0.1))
        return _core.hover(box(None), box(alpha(t.text, 0.08)))

    if button and not state.expanded:
        mark = _icon("menu", size=15, color=t.icon_muted)
        return [face(mark, False, width=28, center=True).on(click=opener(0), cursor="pointer")]
    out = []
    for index, m in enumerate(menus):
        name = _core.text(m.label, size=13, color=t.text, wrap=False)
        out.append(face(name, state.open == index, padding=(0, 8), align_y="center")
                   .on(click=opener(index), mouse_enter=hover(index), cursor="pointer"))
    return out


def window_title_bar(
    title: Any = None,
    *,
    style: Optional[str] = None,
    start: Sequence[Any] = (),
    center: Any = None,
    end: Sequence[Any] = (),
    on_drag: Any = None,
    on_minimize: Any = None,
    on_maximize: Any = None,
    on_close: Any = None,
    on_menu: Any = None,
    maximized: bool = False,
    focused: bool = True,
    width: Any = "fill",
    height: Optional[float] = None,
    bg: Optional[str] = None,
    border: bool = True,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A window's title bar: window buttons in the style of ``style`` (on the left for macOS, on the right
    elsewhere), ``start`` items (menus, project...), ``title`` (centered, or after the start items on
    Windows) or your own ``center``, and ``end`` items.

    ``on_drag`` is called when the empty part of the bar is dragged (return ``Command.drag_window()``) and
    double clicking it calls ``on_maximize``; a right click calls ``on_menu``. Without callbacks the bar
    only shows (Pyzed Design previews forms with it). Most apps use ``window_frame`` instead.
    """
    t = _theme(theme)
    style = style or system_platform()
    height = height or HEIGHTS.get(style, 32.0)
    controls = window_controls(style, on_minimize=on_minimize, on_maximize=on_maximize, on_close=on_close,
                               maximized=maximized, focused=focused, height=height, theme=t)
    left = controls_on_left(style)
    title_text = None
    if title is not None and center is None:
        title_text = title if isinstance(title, _core.Widget) else _core.text(
            str(title), size=12.5 if style in ("macos", "overlay", "kde") else 13,
            color=t.text if focused else t.text_muted, weight="medium" if style in ("gnome", "ubuntu") else None,
            wrap=False)
    # Windows puts the title after the icon, unless menus or other items are there (then centered)
    inline_title = title_text is not None and style == "windows" and not any(x is not None for x in start)
    gap: Any = _core.space(width="fill", height="fill")
    if on_drag is not None or on_maximize is not None or on_menu is not None:
        handlers = {k: v for k, v in (("drag_start", on_drag), ("double_click", on_maximize),
                                      ("right_click", on_menu)) if v is not None}
        gap = _core.container(None, width="fill", height="fill").on(**{k: (lambda _e, v=v: v())
                                                                         for k, v in handlers.items()})
    # keep in step with start_x() and end_x()
    items: List[Any] = [controls if left else None, _core.space(width=6)]
    items += [s for s in start if s is not None]
    if inline_title:
        items.append(_core.container(title_text, padding=(0, 0, 0, 4 if start else 0)))
    items.append(gap)
    items += [e for e in end if e is not None]
    items += [_core.space(width=6), None if left else controls]
    bar = _core.row(items, spacing=2, align="center", height="fill")
    middle = center if center is not None else (None if inline_title else title_text)
    if middle is not None:
        # centered on the whole window, over the bar (a label lets the pointer through to the bar)
        bar = _core.stack([bar, _core.container(middle, width="fill", height="fill", center=True)],
                          width="fill", height="fill")
    body = _core.container(bar, width=width, height=height - (1 if border else 0), bg=bg or t.title_bar)
    if not border:
        return body
    return _core.column([body, _core.rule(thickness=1, color=t.border)], width=width)


def window_frame(
    content: Any,
    *,
    title: Any = None,
    menus: Optional[Sequence[Menu]] = None,
    menu_button: bool = True,
    start: Sequence[Any] = (),
    center: Any = None,
    end: Sequence[Any] = (),
    style: Optional[str] = None,
    window: Any = None,
    height: Optional[float] = None,
    resize_border: float = 6.0,
    resize_edges: bool = True,
    bg: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """The whole frame of a window without system decorations, around ``content``.

    The title bar has the window buttons in the style of ``style`` (``None`` follows ``Window.frame``, or the
    system), ``menus`` on the left like Zed (``[ui.Menu("File", [...]), ...]``; behind a menu button unless
    ``menu_button=False``), then ``start`` items, the ``title`` (the window's title by default) or your own
    ``center``, and ``end`` items. Dragging the empty part of the bar moves the window, double clicking it
    maximizes, and the borders resize it (``resize_border`` pixels; ``resize_edges=False`` leaves them to you).

    Open the window with ``frame="custom"`` (``Window.frame``) so the system draws no frame of its own.
    Called from a window's ``view()``, the buttons act on that window; ``window`` names another.
    """
    t = _theme(theme)
    drawing_now = _current()
    if drawing_now is not None:
        drawing_now.drawn = True
        if window is None:
            window = drawing_now.window
        if style is None:
            style = drawing_now.style
    style = style or resolve(True)
    assert style is not None
    if title is None and window is not None and not start:
        raw = getattr(window, "title", None)
        title = raw() if callable(raw) else raw
    maximized = bool(getattr(window, "window_maximized", False))
    focused = bool(getattr(window, "window_focused", True))
    height = height or HEIGHTS.get(style, 32.0)
    state = _menu_state(window)
    menus = list(menus or [])
    if state.open is not None and state.open >= len(menus):
        state.open, state.expanded = None, False
    bar_start = [*(_menu_bar(menus, state, menu_button, height, t) if menus else []), *start]
    bar = window_title_bar(
        title, style=style, start=bar_start, center=center, end=end,
        on_drag=lambda: _core.Command.drag_window(window),
        on_minimize=lambda: _core.Command.minimize_window(window),
        on_maximize=lambda: _core.Command.toggle_maximize_window(window),
        on_close=lambda: _close_window(window),
        on_menu=lambda: _core.Command.show_window_menu(window),
        maximized=maximized, focused=focused, height=height, bg=bg, theme=t,
    )
    body: Any = _core.column([bar, content], width="fill", height="fill")
    if style != "overlay" and not maximized:
        body = _core.container(body, width="fill", height="fill", border_color=t.border, border_width=1)
    if state.open is not None:
        def close_menu() -> None:
            state.open, state.expanded = None, False

        def chosen(callback: Any) -> Any:
            def run() -> Any:
                close_menu()
                return callback() if callback is not None else None
            return run

        items = [dataclasses.replace(i, on_press=chosen(i.on_press) if i.on_press is not None else None)
                 if isinstance(i, MenuItem) else i for i in menus[state.open].items]
        body = popover(body, _menu(items, theme=t), x=state.x, y=height, on_dismiss=close_menu)
    if resize_edges:
        body = _core.window_edges(body, border=resize_border, enabled=not maximized and style != "overlay")
    return body
