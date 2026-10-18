"""Tabs, breadcrumbs and toolbars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence, Union

from .. import _core
from ..icons import for_file
from ..icons import icon as _icon
from ..theme import Theme
from .base import _theme, icon_button, indicator


@dataclass
class Tab:
    id: str
    label: str
    icon: Optional[str] = None
    icon_color: Optional[str] = None
    dirty: bool = False
    preview: bool = False  # italic, like Zed's preview tabs
    status: Optional[str] = None  # git status tint: "modified" | "created" | "deleted"

    @classmethod
    def for_file(cls, path: str, **kwargs) -> "Tab":
        name = path.rsplit("/", 1)[-1]
        icon_name, color = for_file(name)
        kwargs.setdefault("icon", icon_name)
        kwargs.setdefault("icon_color", color)
        return cls(id=path, label=name, **kwargs)


def tab(
    item: Tab,
    *,
    active: bool,
    on_select: Any = None,
    on_close: Any = None,
    height: float = 32,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    t = _theme(theme)
    status_color = {"modified": t.modified, "created": t.created, "deleted": t.deleted}.get(item.status or "")
    text_color = status_color or (t.text if active else t.text_muted)

    close = icon_button("x", on_close, size="xs", theme=t) if on_close is not None else _core.space(width=18)
    if item.dirty:
        idle = _core.container(indicator("text_muted" if not active else "text", size=7, theme=t), width=18, height=18, center=True)
    else:
        idle = _core.space(width=18, height=18)
    end = close if active else _core.hover(idle, close)

    content = _core.row(
        [
            _icon(item.icon, size=14, color=t.color(item.icon_color) if item.icon_color else t.icon_muted) if item.icon else None,
            _core.text(item.label, size=13.5, color=text_color, italic=item.preview, wrap=False),
            end,
        ],
        spacing=6,
        align="center",
    )
    body = _core.button(
        _core.container(content, height="fill", align_y="center"),
        on_select,
        padding=(0, 6, 0, 12),
        height="fill",
        bg=t.tab_active if active else t.tab_inactive,
        hover_bg=t.tab_active if active else t.ghost_hover,
        pressed_bg=t.tab_active,
        color=text_color,
    )
    return _core.row(
        [
            _core.column(
                [body, None if active else _core.rule(thickness=1, color=t.border)],
                width="shrink",
                height=height,
            ),
            _core.rule(vertical=True, thickness=1, color=t.border),
        ],
        height=height,
    )


def tab_bar(
    tabs: Sequence[Tab],
    active: Optional[str],
    *,
    on_select: Optional[Callable[[str], Any]] = None,
    on_close: Optional[Callable[[str], Any]] = None,
    start: Iterable[Any] = (),
    end: Iterable[Any] = (),
    height: float = 32,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A row of editor tabs with optional leading/trailing controls (navigation, split, +)."""
    t = _theme(theme)
    items: List[Any] = []
    start = list(start)
    if start:
        items.append(
            _core.column([
                _core.container(_core.row(start, spacing=2, align="center"), height="fill", padding=(0, 4), align_y="center"),
                _core.rule(thickness=1, color=t.border),
            ], width="shrink", height=height)
        )
        items.append(_core.rule(vertical=True, thickness=1, color=t.border))
    for item in tabs:
        items.append(
            tab(
                item,
                active=item.id == active,
                on_select=(lambda i=item.id: on_select(i)) if on_select else None,
                on_close=(lambda i=item.id: on_close(i)) if on_close else None,
                height=height,
                theme=t,
            )
        )
    items.append(
        _core.column(
            [
                _core.container(_core.row(list(end), spacing=2, align="center"), width="fill", height="fill",
                                align_x="end", align_y="center", padding=(0, 6)),
                _core.rule(thickness=1, color=t.border),
            ],
            width="fill",
            height=height,
        )
    )
    return _core.container(
        _core.row(items, height=height, clip=True),
        bg=t.tab_bar,
        width="fill",
        height=height,
    )


def breadcrumbs(
    parts: Sequence[Union[str, tuple]],
    *,
    separator: str = "›",
    on_press: Optional[Callable[[int], Any]] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """``src › main.rs › fn main`` — parts may be strings or ``(icon, text)`` tuples."""
    t = _theme(theme)
    items: List[Any] = []
    for i, part in enumerate(parts):
        if i:
            items.append(_core.text(separator, size=13, color=t.text_placeholder, wrap=False))
        icon_name, text = part if isinstance(part, tuple) else (None, part)
        is_last = i == len(parts) - 1
        content = _core.row(
            [_icon(icon_name, size=13, color=t.icon_muted) if icon_name else None,
             _core.text(text, size=13, color=t.text if is_last else t.text_muted, wrap=False)],
            spacing=4,
            align="center",
        )
        if on_press:
            content = _core.button(content, lambda i=i: on_press(i), padding=(2, 4), bg="transparent",
                                   hover_bg=t.ghost_hover, radius=t.radius_sm)
        items.append(content)
    return _core.row(items, spacing=4, align="center")


def toolbar(
    start: Iterable[Any] = (),
    end: Iterable[Any] = (),
    *,
    height: float = 32,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """The bar under the tabs (breadcrumbs on the left, buffer actions on the right)."""
    t = _theme(theme)
    return _core.container(
        _core.row([*start, _core.space(width="fill"), *end], spacing=4, align="center"),
        padding=(0, 8, 0, 12),
        height=height,
        width="fill",
        align_y="center",
        bg=t.editor,
    )
