"""The editor chrome: title bar, docks/panels, status bar and the workspace layout."""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .. import _core
from ..icons import icon as _icon
from ..theme import Theme
from .base import _theme, tooltip_text


def title_bar(
    start: Iterable[Any] = (),
    end: Iterable[Any] = (),
    *,
    center: Any = None,
    height: float = 34,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """The top bar: project/branch switchers on the left, account and actions on the right."""
    t = _theme(theme)
    middle = [_core.space(width="fill"), center, _core.space(width="fill")] if center is not None else [_core.space(width="fill")]
    return _core.column(
        [
            _core.container(
                _core.row([*start, *middle, *end], spacing=2, align="center"),
                padding=(0, 8),
                height=height - 1,
                width="fill",
                align_y="center",
                bg=t.title_bar,
            ),
            _core.rule(thickness=1, color=t.border),
        ]
    )


def title_button(
    content: str,
    on_press: Any = None,
    *,
    icon: Optional[str] = None,
    muted: bool = False,
    chevron: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A compact ghost button for the title bar (``pyzed ▾``, ``main``...)."""
    t = _theme(theme)
    color = t.text_muted if muted else t.text
    parts = [
        _icon(icon, size=14, color=t.icon_muted) if icon else None,
        _core.text(content, size=13.5, color=color, weight=None if muted else "medium", wrap=False),
        _icon("chevron-down", size=12, color=t.icon_muted) if chevron else None,
    ]
    return _core.button(
        _core.container(_core.row(parts, spacing=6, align="center"), height="fill", align_y="center"),
        on_press,
        padding=(0, 8),
        height=24,
        bg="transparent",
        hover_bg=t.ghost_hover,
        pressed_bg=t.ghost_active,
        radius=t.radius_sm,
    )


def status_bar(
    start: Iterable[Any] = (),
    end: Iterable[Any] = (),
    *,
    height: float = 28,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """The bottom status bar: ``start`` items on the left and ``end`` items on the right."""
    t = _theme(theme)
    return _core.column(
        [
            _core.rule(thickness=1, color=t.border),
            _core.container(
                _core.row([*start, _core.space(width="fill"), *end], spacing=2, align="center"),
                padding=(0, 6),
                height=height - 1,
                width="fill",
                align_y="center",
                bg=t.status_bar,
            ),
        ]
    )


def status_item(
    content: Optional[str] = None,
    on_press: Any = None,
    *,
    icon: Optional[str] = None,
    color: Optional[str] = None,
    icon_color: Optional[str] = None,
    selected: bool = False,
    tooltip: Optional[str] = None,
    keys: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """An icon and/or label in the status bar (diagnostics, cursor position, language...)."""
    t = _theme(theme)
    text_color = t.color(color) if color else t.text_muted
    parts = [
        _icon(icon, size=14, color=t.color(icon_color) if icon_color else (t.icon if selected else t.icon_muted)) if icon else None,
        _core.text(content, size=12.5, color=text_color, wrap=False) if content is not None else None,
    ]
    widget = _core.button(
        _core.container(_core.row(parts, spacing=4, align="center"), height="fill", align_y="center"),
        on_press,
        padding=(0, 6),
        height=22,
        bg=t.ghost_selected if selected else "transparent",
        hover_bg=t.ghost_hover,
        pressed_bg=t.ghost_active,
        radius=t.radius_sm,
    )
    return tooltip_text(widget, tooltip, keys=keys, position="top", theme=t) if tooltip else widget


def panel_header(
    title: str,
    actions: Iterable[Any] = (),
    *,
    icon: Optional[str] = None,
    height: float = 32,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A panel's title row with an optional ``icon`` and ``actions`` on the right."""
    t = _theme(theme)
    return _core.container(
        _core.row(
            [
                _icon(icon, size=14, color=t.icon_muted) if icon else None,
                _core.text(title, size=13.5, weight="medium", color=t.text, wrap=False),
                _core.space(width="fill"),
                *actions,
            ],
            spacing=6,
            align="center",
        ),
        padding=(0, 6, 0, 10),
        height=height,
        width="fill",
        align_y="center",
    )


def panel(
    content: Any,
    *,
    header: Any = None,
    width: Any = None,
    height: Any = None,
    side: str = "left",
    resizable: bool = True,
    on_resize: Any = None,
    min_size: float = 120,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A dock panel (project panel, outline, terminal, assistant...). ``side`` picks the border edge.

    With a numeric ``width`` (``height`` for ``side="bottom"``) the border facing the center
    can be dragged to resize the panel; ``on_resize(size)`` is called when a drag ends.
    ``resizable=False`` keeps it fixed.
    """
    t = _theme(theme)
    body = _core.container(
        _core.column([header, content], width="fill", height="fill"),
        width="fill",
        height="fill",
        bg=t.panel,
    )
    size = height if side == "bottom" else width
    if resizable and isinstance(size, (int, float)) and side in INNER_EDGES:
        return _core.resizable(
            body,
            edge=INNER_EDGES[side],
            size=size,
            min_size=min_size,
            on_resize=on_resize,
            color=t.border,
            hover_color=t.accent,
        )
    edge = _core.rule(vertical=side in ("left", "right"), thickness=1, color=t.border)
    if side == "left":
        layout = _core.row([body, edge], width=width, height=height or "fill")
    elif side == "right":
        layout = _core.row([edge, body], width=width, height=height or "fill")
    else:
        layout = _core.column([edge, body], width=width or "fill", height=height)
    return layout


# The edge of a docked panel that faces the center (where its resize handle goes).
INNER_EDGES = {"left": "right", "right": "left", "bottom": "top"}


def workspace(
    center: Any,
    *,
    title_bar: Any = None,  # noqa: F811
    left: Any = None,
    right: Any = None,
    bottom: Any = None,
    status_bar: Any = None,  # noqa: F811
    left_width: float = 240,
    right_width: float = 320,
    bottom_height: float = 220,
    on_resize: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Lays out a full Zed-like window. Pass ``None`` for any dock to hide it.

    The docks can be resized by dragging their inner border; ``on_resize(side, size)`` is
    called when a drag ends (``side`` is "left", "right" or "bottom"). For panels the user
    can also move between sides, use ``pz.Dock``.
    """

    def resized(side: str) -> Any:
        return None if on_resize is None else (lambda size: on_resize(side, size))

    t = _theme(theme)
    middle = _core.column(
        [
            _core.container(center, width="fill", height="fill", bg=t.editor),
            panel(bottom, side="bottom", height=bottom_height, on_resize=resized("bottom"), min_size=80,
                  theme=t) if bottom is not None else None,
        ],
        width="fill",
        height="fill",
    )
    body = _core.row(
        [
            panel(left, side="left", width=left_width, on_resize=resized("left"), theme=t) if left is not None else None,
            middle,
            panel(right, side="right", width=right_width, on_resize=resized("right"), theme=t) if right is not None else None,
        ],
        width="fill",
        height="fill",
    )
    return _core.container(
        _core.column([title_bar, body, status_bar], width="fill", height="fill"),
        width="fill",
        height="fill",
        bg=t.background,
        color=t.text,
    )
