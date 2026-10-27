"""Tabs, breadcrumbs and toolbars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence, Union

from .. import _core
from ..icons import for_file
from ..icons import icon as _icon
from ..theme import Theme, alpha, mix
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
    pinned: bool = False  # icon only, no close button, like Zed's pinned tabs
    tooltip: Optional[str] = None  # shown on hover (the full path, for example)

    @classmethod
    def for_file(cls, path: str, **kwargs) -> "Tab":
        """A tab for a file ``path``: its name as label and the matching file icon and color."""
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
    dimmed: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A Zed-style editor tab for ``item``; the active one joins the content below it.

    The label is colored by the git ``status``; a dirty tab shows a dot that turns into the close button
    on hover (``on_close``, also sent on a middle click). ``on_select`` is called when the tab is
    pressed. ``dimmed`` mutes the label (the tab being dragged). A ``pinned`` tab shows only its
    icon and can't be closed from it.

    Events:
        ``on_select()``: Callable that receives the chosen item.
        ``on_close()``: Message or callable sent when the X is pressed.
    """
    t = _theme(theme)
    status_color = {"modified": t.modified, "created": t.created, "deleted": t.deleted}.get(item.status or "")
    text_color = status_color or (t.text if active and not dimmed else t.text_muted)

    if item.pinned:
        on_close = None
    close = icon_button("x", on_close, size="xs", theme=t) if on_close is not None else _core.space(width=18)
    if item.dirty:
        idle = _core.container(indicator("text_muted" if not active else "text", size=7, theme=t), width=18, height=18, center=True)
    else:
        idle = _core.space(width=18, height=18)
    end = close if active else _core.hover(idle, close)

    content = _core.row(
        [
            _icon(item.icon or ("pin" if item.pinned else None), size=14,
                  color=t.color(item.icon_color) if item.icon_color else t.icon_muted)
            if item.icon or item.pinned else None,
            None if item.pinned and item.icon else
            _core.text(item.label, size=13.5, color=text_color, italic=item.preview, wrap=False),
            None if item.pinned else end,
        ],
        spacing=6,
        align="center",
    )
    body = _core.button(
        _core.container(content, height="fill", align_y="center"),
        on_select,
        padding=(0, 10) if item.pinned else (0, 6, 0, 12),
        height="fill",
        bg=t.tab_active if active else t.tab_inactive,
        hover_bg=t.tab_active if active else t.ghost_hover,
        pressed_bg=t.tab_active,
        color=text_color,
    )
    if on_close is not None:
        body = body.on(middle_click=on_close)
    if item.tooltip:
        from .base import tooltip_text

        body = tooltip_text(body, item.tooltip, theme=t)
    return _core.row(
        [
            _core.column(
                # the active tab joins the content below; the same 1px line keeps both labels at one height
                [body, _core.rule(thickness=1, color=t.tab_active if active else t.border)],
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
    on_drag: Optional[Callable[[str], Any]] = None,
    on_drop: Optional[Callable[[str, Any], Any]] = None,
    on_drag_over: Optional[Callable[[Optional[int]], Any]] = None,
    dragging: Optional[str] = None,
    drop_index: Optional[int] = None,
    on_context: Optional[Callable[[str], Any]] = None,
    on_new: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A row of editor tabs with optional leading/trailing controls (navigation, split, +).

    ``on_context(tab_id)`` runs on a right click of a tab (Close others, Pin...) and
    ``on_new`` on a double click of the empty space after the tabs, as in Zed. Pinned tabs
    (``Tab.pinned``) go first.

    Tabs can be dragged: ``on_drag(tab_id)`` is called when a drag starts and
    ``on_drop(tab_id, event)`` when it is released, with the pointer in ``event.window_x``/
    ``window_y`` (outside the window when it was dropped outside) and ``event.screen``.
    While ``dragging`` names a tab, ``on_drag_over(index)`` reports where it would land
    (the insertion index, or ``None`` once the pointer leaves the bar) and ``drop_index``
    draws the insertion mark there.

    Events:
        ``on_select(tab_id)``: Callable that receives the chosen item.
        ``on_close(tab_id)``: Message or callable sent when the X is pressed.
        ``on_drag(tab_id)``: Called with the tab id when a tab starts being dragged.
        ``on_drop(tab_id, event)``: Called with the tab id and the ``Event`` when the dragged tab is released:
            ``event.window_x``/``window_y`` (outside the window if it was dropped outside) and
            ``event.screen``.
        ``on_drag_over(index)``: While ``dragging`` is set: called with the insertion index under the pointer,
            or ``None`` when it leaves the bar.
        ``on_context(tab_id)``: Called with the id of a tab that is right-clicked.
        ``on_new()``: Sent on a double click of the empty space after the tabs.
    """
    t = _theme(theme)
    items: List[Any] = []
    tracking = dragging is not None and on_drag_over is not None
    start = list(start)
    if start:
        items.append(
            _core.column([
                _core.container(_core.row(start, spacing=2, align="center"), height="fill", padding=(0, 4), align_y="center"),
                _core.rule(thickness=1, color=t.border),
            ], width="shrink", height=height)
        )
        items.append(_core.rule(vertical=True, thickness=1, color=t.border))
    tabs = sorted(tabs, key=lambda item: not item.pinned)
    # The insertion marks are always there (zero wide when unused) so a drag never changes the
    # tree's shape: that would reset the dragged tab's state and lose the drop.
    marks = on_drag_over is not None
    for index, item in enumerate(tabs):
        if marks:
            items.append(_drop_mark(drop_index == index, height, t))
        widget = tab(
            item,
            active=item.id == active,
            on_select=(lambda i=item.id: on_select(i)) if on_select else None,
            on_close=(lambda i=item.id: on_close(i)) if on_close else None,
            height=height,
            dimmed=item.id == dragging,
            theme=t,
        )
        handlers: dict = {}
        if on_drag is not None:
            handlers["drag_start"] = lambda i=item.id: on_drag(i)
        if on_drop is not None:
            handlers["drag_end"] = lambda e, i=item.id: on_drop(i, e)
        if tracking:  # the left half of a tab inserts before it, the right half after it
            handlers["mouse_move"] = lambda e, k=index: on_drag_over(k if e.x < e.width / 2 else k + 1)
        if on_context is not None:
            handlers["right_click"] = lambda i=item.id: on_context(i)
        items.append(widget.on(cursor="grabbing" if item.id == dragging else None, **handlers) if handlers else widget)
    if marks:
        items.append(_drop_mark(drop_index is not None and drop_index >= len(tabs), height, t))
    filler = _core.column(
        [
            _core.container(_core.row(list(end), spacing=2, align="center"), width="fill", height="fill",
                            align_x="end", align_y="center", padding=(0, 6)),
            _core.rule(thickness=1, color=t.border),
        ],
        width="fill",
        height=height,
    )
    if marks:  # past the last tab: append
        filler = filler.on(mouse_move=(lambda: on_drag_over(len(tabs))) if tracking else None)
    if on_new is not None:
        filler = filler.on(double_click=on_new)
    items.append(filler)
    bar = _core.container(
        _core.row(items, height=height, clip=True),
        # the row a dragged tab would land in is tinted with the accent color
        bg=mix(t.tab_bar, t.accent, 0.12) if drop_index is not None else t.tab_bar,
        width="fill",
        height=height,
    )
    if marks:
        bar = bar.on(mouse_leave=(lambda: on_drag_over(None)) if tracking else None)
    return bar


def _drop_mark(shown: bool, height: float, t: Theme) -> _core.Widget:
    """The accent bar between two tabs where a dragged tab would land (zero wide when not ``shown``)."""
    return _core.container(width=3 if shown else 0, height=height, bg=t.accent if shown else None,
                           radius=1.5 if shown else 0)


def breadcrumbs(
    parts: Sequence[Union[str, tuple]],
    *,
    separator: str = "›",
    on_press: Optional[Callable[[int], Any]] = None,
    max_items: Optional[int] = None,
    on_more: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """``src › main.rs › fn main`` — parts may be strings or ``(icon, text)`` tuples.

    With ``max_items``, a long path keeps its first part and the last ones and shows ``…``
    for the rest (``on_more`` makes the ``…`` clickable, to list the hidden parts).
    ``on_press(index)`` always gets the index in the full ``parts``.

    Events:
        ``on_press(index)``: Called with the index of the clicked part.
        ``on_more()``: Makes the ``…`` clickable.
    """
    t = _theme(theme)
    items: List[Any] = []
    indexes = list(range(len(parts)))
    if max_items is not None and len(parts) > max(max_items, 2):
        indexes = [0, -1] + indexes[len(parts) - (max_items - 1):]
    for position, i in enumerate(indexes):
        if position:
            items.append(_core.text(separator, size=13, color=t.text_placeholder, wrap=False))
        if i == -1:
            more = _core.text("…", size=13, color=t.text_muted, wrap=False)
            items.append(_core.button(more, on_more, padding=(2, 4), bg="transparent", hover_bg=t.ghost_hover,
                                      radius=t.radius_sm) if on_more is not None else more)
            continue
        part = parts[i]
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
    center: Any = None,
    height: float = 32,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """The bar under the tabs (breadcrumbs on the left, buffer actions on the right).

    ``center`` is kept in the middle of the bar whatever the widths of both sides.
    """
    t = _theme(theme)
    row = _core.row([*start, _core.space(width="fill"), *end], spacing=4, align="center")
    if center is not None:
        row = _core.stack([row, _core.container(center, width="fill", height="fill", align_x="center",
                                                align_y="center")], width="fill")
    return _core.container(
        row,
        padding=(0, 8, 0, 12),
        height=height,
        width="fill",
        align_y="center",
        bg=t.editor,
    )


def stepper(
    steps: Sequence[Union[str, tuple]],
    current: int,
    on_select: Optional[Callable[[int], Any]] = None,
    *,
    vertical: bool = False,
    linear: bool = True,
    errors: Iterable[int] = (),
    tint: str = "accent",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """The steps of a wizard or a checkout: done ones get a check, the ``current`` one is ringed.

    ``steps`` are titles or ``(title, description)`` tuples and ``current`` is the index of
    the step in progress (``len(steps)`` once all are done). ``on_select(index)`` makes the
    steps clickable: with ``linear`` only the done ones and the current one, to go back.
    ``errors`` are indexes drawn in the error color with an ``!``. ``vertical`` stacks them,
    with the description under each title.

    Events:
        ``on_select(index)``: Called with the index of the clicked step.
    """
    t = _theme(theme)
    accent = t.color(tint)
    failed = set(errors)
    items: List[Any] = []
    for i, step in enumerate(steps):
        title, description = (step[0], step[1] if len(step) > 1 else None) if isinstance(step, tuple) else (step, None)
        done, active, wrong = i < current, i == current, i in failed
        color = t.error if wrong else accent
        if wrong:
            mark = _icon("triangle-alert", size=12, color=t.background)
        elif done:
            mark = _icon("check", size=12, color=t.background)
        else:
            mark = _core.text(str(i + 1), size=11, weight="semibold", wrap=False,
                              color=accent if active else t.text_muted)
        dot = _core.container(mark, width=24, height=24, center=True, radius=12,
                              bg=color if done or wrong else (alpha(accent, 0.14) if active else t.element),
                              border_color=color if done or active or wrong else t.border, border_width=1.5)
        words = _core.column([
            _core.text(title, size=13, wrap=False, weight="medium" if active else None,
                       color=t.error if wrong else (t.text if done or active else t.text_muted)),
            _core.text(description, size=12, color=t.text_placeholder) if description and vertical else None,
        ], spacing=1)
        body = _core.row([dot, words], spacing=8, align="center" if not (description and vertical) else "start")
        if on_select is not None and (not linear or i <= current):
            body = _core.button(body, lambda i=i: on_select(i), padding=(2, 4), bg="transparent",
                                hover_bg=t.ghost_hover, radius=t.radius_sm)
        else:
            body = _core.container(body, padding=(2, 4))
        if i:
            line = t.color(tint) if i <= current else t.border
            if vertical:
                items.append(_core.container(_core.container(None, width=2, height=16, bg=line), padding=(0, 0, 0, 15)))
            else:
                items.append(_core.container(None, width="fill", height=2, bg=line, radius=1))
        items.append(body)
    if vertical:
        return _core.column(items, spacing=2)
    return _core.row(items, spacing=6, align="center", width="fill")


def _page_items(page: int, pages: int, siblings: int, boundaries: int) -> List[Optional[int]]:
    """The page numbers to show, with ``None`` for each gap (``1 … 4 5 6 … 20``)."""
    shown = set(range(1, min(boundaries, pages) + 1)) | set(range(max(pages - boundaries + 1, 1), pages + 1))
    shown |= set(range(max(page - siblings, 1), min(page + siblings, pages) + 1))
    out: List[Optional[int]] = []
    previous = 0
    for n in sorted(shown):
        if n - previous == 2:
            out.append(n - 1)  # a gap of one page shows the page instead of "…"
        elif n - previous > 2:
            out.append(None)
        out.append(n)
        previous = n
    return out


def pagination(
    page: int,
    pages: int,
    on_change: Optional[Callable[[int], Any]] = None,
    *,
    siblings: int = 1,
    boundaries: int = 1,
    size: str = "md",
    compact: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Page numbers with previous and next arrows: ``‹ 1 … 4 5 6 … 20 ›``.

    ``page`` counts from 1 to ``pages``; ``siblings`` pages are shown on each side of the
    current one and ``boundaries`` at each end, with ``…`` for the rest. ``compact`` shows
    ``4 / 20`` between the arrows instead of the numbers, for narrow places.

    Events:
        ``on_change(page)``: Called with the page that was clicked (1 to ``pages``).
    """
    t = _theme(theme)
    pages = max(int(pages), 1)
    page = min(max(int(page), 1), pages)
    height = {"sm": 22, "md": 26, "lg": 30}[size]
    text_size = {"sm": 12, "md": 13, "lg": 14}[size]

    def go(n: int) -> Any:
        return (lambda: on_change(n)) if on_change is not None and n != page and 1 <= n <= pages else None

    def arrow(name: str, target: int) -> Any:
        handler = go(target)
        return icon_button(name, handler, size="sm" if size == "sm" else "md", disabled=handler is None, theme=t)

    items: List[Any] = [arrow("chevron-left", page - 1)]
    if compact:
        items.append(_core.text(f"{page} / {pages}", size=text_size, color=t.text_muted, wrap=False))
    else:
        for n in _page_items(page, pages, max(siblings, 0), max(boundaries, 1)):
            if n is None:
                items.append(_core.container(_core.text("…", size=text_size, color=t.text_placeholder, wrap=False),
                                             width=height, height=height, center=True))
                continue
            current = n == page
            number = _core.container(
                _core.text(str(n), size=text_size, wrap=False, weight="medium" if current else None,
                           color=t.text if current else t.text_muted),
                height=height, padding=(0, 4), center=True, width=height if n < 100 else None)
            items.append(_core.button(number, go(n), padding=0,
                                      bg=t.element_selected if current else "transparent",
                                      hover_bg=t.element_selected if current else t.ghost_hover,
                                      border_color=t.border if current else "transparent",
                                      border_width=1.0, radius=t.radius_sm))
    items.append(arrow("chevron-right", page + 1))
    return _core.row(items, spacing=2, align="center")
