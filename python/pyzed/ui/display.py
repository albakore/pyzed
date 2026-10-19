"""Display components: callouts, tables, empty states, small charts and popovers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence, Union

from .. import _core
from .. import draw
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme, avatar, kbd, label

_CALLOUT_ICONS = {"info": "info", "success": "circle-check", "warning": "triangle-alert", "error": "circle-x",
                  "hint": "lightbulb", "accent": "info"}


def callout(
    title: Any,
    description: Any = None,
    *,
    tint: str = "info",
    icon: Optional[str] = None,
    actions: Iterable[Any] = (),
    on_dismiss: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """An inline message box (Zed's ``Callout``/``Banner``).

    ``tint`` is ``"info"``, ``"success"``, ``"warning"``, ``"error"`` or ``"hint"``; it picks
    the color and the default icon. ``actions`` are extra widgets (usually buttons) shown
    at the end, and ``on_dismiss`` adds a close button.
    """
    t = _theme(theme)
    base = t.color(tint)
    text = _core.column(
        [
            label(title, weight="medium", theme=t) if isinstance(title, str) else title,
            label(description, size="sm", color="text_muted", theme=t) if isinstance(description, str) else description,
        ],
        spacing=2,
        width="fill",
    )
    close = None
    if on_dismiss is not None:
        close = _core.button(_icon("x", size=13, color=t.icon_muted), on_dismiss, padding=3, bg="transparent",
                             hover_bg=t.ghost_hover, radius=t.radius_sm)
    return _core.container(
        _core.row(
            [_icon(icon or _CALLOUT_ICONS.get(tint, "info"), size=16, color=base), text, *actions, close],
            spacing=10,
            align="center",
        ),
        width="fill",
        padding=(10, 12),
        bg=alpha(base, 0.1),
        border_color=alpha(base, 0.35),
        border_width=1.0,
        radius=t.radius,
    )


def count_badge(count: int, *, tint: str = "accent", max: int = 99, theme: Optional[Theme] = None) -> _core.Widget:  # noqa: A002
    """A small round counter (unread notifications, problems...). Shows ``99+`` past ``max``."""
    t = _theme(theme)
    text = f"{max}+" if count > max else str(count)
    return _core.container(
        _core.text(text, size=10.5, weight="semibold", color=t.on_accent, wrap=False),
        height=16,
        padding=(0, 5),
        align_y="center",
        bg=t.color(tint),
        radius=8,
    )


def facepile(
    people: Sequence[str],
    *,
    size: float = 22,
    overlap: float = 6,
    max_shown: int = 5,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Overlapping avatars of collaborators (initials), like Zed's title bar.

    Extra people beyond ``max_shown`` collapse into a ``+N`` bubble.
    """
    t = _theme(theme)
    shown = list(people[:max_shown])
    extra = len(people) - len(shown)
    faces: List[Any] = [avatar(p, size=size, index=i, theme=t) for i, p in enumerate(shown)]
    if extra > 0:
        faces.append(
            _core.container(
                _core.text(f"+{extra}", size=size * 0.42, color=t.text, wrap=False),
                width=size, height=size, center=True, bg=t.element, radius=size / 2,
                border_color=t.border, border_width=1.0,
            )
        )
    step = size - overlap
    width = step * (len(faces) - 1) + size if faces else 0
    return _core.stack(
        [_core.pin(face, x=i * step, y=0) for i, face in enumerate(faces)],
        width=width,
        height=size,
    )


def diff_stat(added: int, removed: int, *, blocks: int = 5, theme: Optional[Theme] = None) -> _core.Widget:
    """``+12 −3`` with GitHub-style colored blocks."""
    t = _theme(theme)
    total = added + removed
    green = round(blocks * added / total) if total else 0
    red = round(blocks * removed / total) if total else 0
    cells = ([t.created] * green) + ([t.deleted] * red) + ([alpha(t.text, 0.15)] * (blocks - green - red))
    return _core.row(
        [
            _core.text(f"+{added}", size=12, color=t.created, font="mono", wrap=False),
            _core.text(f"−{removed}", size=12, color=t.deleted, font="mono", wrap=False),
            _core.row([_core.container(None, width=7, height=7, bg=c, radius=1.5) for c in cells], spacing=2),
        ],
        spacing=6,
        align="center",
    )


def keybinding_hint(text: str, keys: str, *, theme: Optional[Theme] = None) -> _core.Widget:
    """A muted hint such as "Open file ⌘P" for footers and empty states."""
    t = _theme(theme)
    return _core.row([label(text, size="sm", color="text_muted", theme=t), kbd(keys, size="xs", theme=t)],
                     spacing=6, align="center")


def empty_state(
    title: str,
    description: Optional[str] = None,
    *,
    icon: str = "inbox",
    actions: Iterable[Any] = (),
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A centered placeholder for empty lists, search results with no hits, etc."""
    t = _theme(theme)
    actions = list(actions)
    return _core.container(
        _core.column(
            [
                _icon(icon, size=32, color=t.icon_muted),
                label(title, size="lg", weight="medium", theme=t),
                label(description, color="text_muted", align_x="center", theme=t) if description else None,
                _core.row(actions, spacing=8) if actions else None,
            ],
            spacing=8,
            align="center",
            max_width=360,
        ),
        width="fill",
        height="fill",
        center=True,
    )


def settings_group(
    title: str,
    rows: Iterable[Any],
    *,
    description: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A titled block of ``ui.field`` rows separated by thin lines (Zed's settings UI)."""
    t = _theme(theme)
    body: List[Any] = []
    for i, row in enumerate(rows):
        if i:
            body.append(_core.rule(thickness=1, color=t.border_variant))
        body.append(_core.container(row, padding=(10, 14)))
    return _core.column(
        [
            label(title, weight="semibold", theme=t),
            label(description, size="sm", color="text_muted", theme=t) if description else None,
            _core.container(_core.column(body), width="fill", bg=t.surface, border_color=t.border_variant,
                            border_width=1.0, radius=t.radius + 2),
        ],
        spacing=6,
    )


# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------


@dataclass
class Column:
    """A ``ui.table`` column.

    ``key`` is a dict key, an attribute name or a function of the row; ``render`` (optional)
    turns the value into a widget. ``width`` is ``"fill"``, a number or a fill portion
    such as ``("fill", 2)``. ``align`` is ``"start"``, ``"center"`` or ``"end"``.
    """

    title: str
    key: Union[str, Callable[[Any], Any]]
    width: Any = "fill"
    align: str = "start"
    render: Optional[Callable[[Any], Any]] = None
    sortable: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.width, tuple) and len(self.width) == 2 and self.width[0] == "fill":
            self.width = f"fill:{int(self.width[1])}"  # ("fill", 2) is the documented spelling of "fill:2"

    def value(self, row: Any) -> Any:
        """Returns this column's value for ``row``: ``key(row)``, a dict item or an attribute.

        ``None`` when the row has no such item or attribute.
        """
        if callable(self.key):
            return self.key(row)
        if isinstance(row, dict):
            return row.get(self.key)
        return getattr(row, self.key, None)


def table(
    columns: Sequence[Union[Column, str]],
    rows: Sequence[Any],
    *,
    sort_by: Optional[str] = None,
    descending: bool = False,
    on_sort: Any = None,
    on_row_press: Any = None,
    selected: Any = None,
    striped: bool = False,
    row_height: float = 30,
    height: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A data table with a sticky header, optional sorting and row selection.

    ``columns`` are ``ui.Column`` objects or plain keys. ``rows`` are dicts or objects.
    Sorting is done here when ``sort_by`` names a column title: clicking a header calls
    ``on_sort(title)`` and you flip ``sort_by``/``descending`` in your state.
    ``on_row_press(row)`` makes rows clickable; the row equal to ``selected`` is highlighted.

    Rows are virtualized: only the ones in view are built, so a table with hundreds of
    thousands of rows scrolls as smoothly as a short one. ``rows`` should be a list (or any
    sequence); sorting a huge list on every ``view()`` is the remaining cost, so keep it
    sorted in your state or sort it in a ``@pz.memo`` function.
    """
    t = _theme(theme)
    cols = [c if isinstance(c, Column) else Column(str(c), c) for c in columns]

    if sort_by is not None:
        col = next((c for c in cols if c.title == sort_by), None)
        if col is not None:
            def key(row):
                v = col.value(row)
                return (v is None, v if v is not None else 0)
            rows = sorted(rows, key=key, reverse=descending)

    def cell(content: Any, col: Column, color: str, weight=None):
        widget = content if isinstance(content, _core.Widget) else _core.text(
            "" if content is None else content, size=13, color=color, weight=weight, wrap=False)
        return _core.container(widget, width=col.width, align_x=col.align, padding=(0, 10), clip=True)

    header_cells = []
    for col in cols:
        arrow = None
        if col.title == sort_by:
            arrow = _icon("arrow-down" if descending else "arrow-up", size=12, color=t.icon_muted)
        title = _core.row([_core.text(col.title, size=12, weight="semibold", color=t.text_muted, wrap=False), arrow],
                          spacing=4, align="center")
        if on_sort is not None and col.sortable:
            title = _core.mouse_area(title, on_press=lambda c=col.title: on_sort(c), cursor="pointer")
        header_cells.append(_core.container(title, width=col.width, align_x=col.align, padding=(0, 10)))
    header = _core.container(_core.row(header_cells, align="center", height="fill"), height=row_height,
                             width="fill", bg=t.surface)

    if not isinstance(rows, Sequence):
        rows = list(rows)

    def body_row(i: int) -> _core.Widget:
        row = rows[i]
        cells = [cell(col.render(col.value(row)) if col.render else col.value(row), col, t.text) for col in cols]
        content = _core.row(cells, align="center", height="fill")
        is_selected = selected is not None and row == selected
        bg = t.ghost_selected if is_selected else (alpha(t.text, 0.03) if striped and i % 2 else "transparent")
        if on_row_press is not None:
            return _core.button(content, lambda r=row: on_row_press(r), width="fill", height=row_height,
                                padding=0, bg=bg, hover_bg=t.ghost_selected if is_selected else t.ghost_hover,
                                radius=0)
        return _core.container(content, width="fill", height=row_height, bg=bg)

    body = _core.virtual_column(len(rows), body_row, item_height=row_height)
    return _core.container(
        _core.column(
            [
                header,
                _core.rule(thickness=1, color=t.border_variant),
                _core.scrollable(body, height="fill" if height else None,
                                 scroller=t.scrollbar, scroller_hover=t.scrollbar_hover, scrollbar_width=6),
            ]
        ),
        width="fill",
        height=height,
        border_color=t.border_variant,
        border_width=1.0,
        radius=t.radius,
        clip=True,
    )


# ---------------------------------------------------------------------------
# Popovers
# ---------------------------------------------------------------------------


def popover(base: Any, content: Any = None, *, x: float = 0, y: float = 0, on_dismiss: Any = None,
            align_x: str = "start") -> _core.Widget:
    """Shows ``content`` (a ``ui.menu``, a card...) over ``base`` at ``(x, y)``.

    Clicking anywhere else calls ``on_dismiss``. With ``content=None`` only ``base`` is shown.
    For a right-click menu, remember the pointer with ``mouse_area(on_move=...)`` and open
    the popover from ``on_right_press``; see ``examples/context_menu.py``. With
    ``align_x="end"``, ``x`` is the distance from the right edge to the content's right
    side (for menus opened from buttons at the end of a title bar).
    """
    if content is None:
        return base
    shade = _core.container(None, width="fill", height="fill")
    if on_dismiss is not None:
        shade = _core.mouse_area(shade, on_press=on_dismiss, on_right_press=on_dismiss)
    if align_x == "end":
        placed = _core.container(_core.opaque(content), width="fill", height="fill", align_x="end",
                                 align_y="start", padding=(y, x, 0, 0))
    else:
        placed = _core.pin(_core.opaque(content), x=x, y=y)
    return _core.stack([base, shade, placed], width="fill", height="fill")


# ---------------------------------------------------------------------------
# Charts (drawn with pz.canvas)
# ---------------------------------------------------------------------------


def sparkline(
    values: Sequence[float],
    *,
    width: float = 120,
    height: float = 32,
    tint: str = "accent",
    fill: bool = True,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A tiny line chart for trends (CPU, requests per second...)."""
    t = _theme(theme)
    color = t.color(tint)
    values = list(values)
    if len(values) < 2:
        return _core.space(width=width, height=height)
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    step = (width - 2) / (len(values) - 1)
    points = [(1 + i * step, height - 2 - (v - lo) / span * (height - 4)) for i, v in enumerate(values)]
    shapes = []
    if fill:
        shapes.append(draw.polygon([(points[0][0], height), *points, (points[-1][0], height)], fill=alpha(color, 0.18)))
    shapes.append(draw.polyline(points, stroke=color, width=1.5))
    return _core.canvas(shapes, width=width, height=height)


def bar_chart(
    values: Sequence[float],
    *,
    labels: Optional[Sequence[str]] = None,
    width: float = 320,
    height: float = 160,
    tint: str = "accent",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A simple vertical bar chart with optional labels under each bar."""
    t = _theme(theme)
    values = list(values)
    if not values:
        return _core.space(width=width, height=height)
    bottom = height - (18 if labels else 2)
    hi = max(max(values), 1e-9)
    slot = width / len(values)
    bar = slot * 0.6
    shapes: List[Any] = [draw.line(0, bottom + 0.5, width, bottom + 0.5, stroke=t.border_variant)]
    for i, v in enumerate(values):
        h = (bottom - 4) * v / hi
        x = i * slot + (slot - bar) / 2
        shapes.append(draw.rect(x, bottom - h, bar, h, fill=t.color(tint), radius=min(3, bar / 4)))
        if labels:
            shapes.append(draw.text(x + bar / 2, height - 2, labels[i], color=t.text_muted, size=11,
                                    align_x="center", align_y="bottom"))
    return _core.canvas(shapes, width=width, height=height)


def donut(
    values: Sequence[float],
    *,
    colors: Optional[Sequence[str]] = None,
    size: float = 96,
    thickness: float = 14,
    label: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A ring chart; ``label`` is drawn in the middle (e.g. a percentage)."""
    t = _theme(theme)
    palette = list(colors) if colors else [t.accent, t.success, t.warning, t.error, t.info, *t.players]
    total = sum(values) or 1.0
    r = (size - thickness) / 2
    c = size / 2
    shapes: List[Any] = [draw.circle(c, c, r, stroke=alpha(t.text, 0.08), width=thickness)]
    start = -90.0
    for i, v in enumerate(values):
        sweep = 360.0 * v / total
        if sweep > 0:
            shapes.append(draw.arc(c, c, r, start, start + sweep, stroke=t.color(palette[i % len(palette)]),
                                   width=thickness))
        start += sweep
    if label is not None:
        shapes.append(draw.text(c, c, label, color=t.text, size=size * 0.18, align_x="center", align_y="center",
                                weight="semibold"))
    return _core.canvas(shapes, width=size, height=size)


def spinner(*, size: float = 16, tint: str = "accent", speed: float = 1.0, theme: Optional[Theme] = None) -> _core.Widget:
    """A spinning arc for "loading" states.

    Its angle comes from the clock, so it moves whenever the view is redrawn: keep a
    ``pz.every(1/30, ...)`` subscription active while it is on screen.
    """
    t = _theme(theme)
    angle = (time.monotonic() * 360 * speed) % 360
    c = size / 2
    w = max(1.5, size / 8)
    r = c - w
    return _core.canvas(
        [
            draw.circle(c, c, r, stroke=alpha(t.color(tint), 0.2), width=w),
            draw.arc(c, c, r, angle, angle + 100, stroke=t.color(tint), width=w, cap="round"),
        ],
        width=size,
        height=size,
    )


def stat(title: str, value: Any, *, delta: Optional[float] = None, trend: Optional[Sequence[float]] = None,
         width: Any = None, theme: Optional[Theme] = None) -> _core.Widget:
    """A dashboard number: title, big value, optional change (``+4.2%``) and sparkline."""
    t = _theme(theme)
    change = None
    if delta is not None:
        color = t.success if delta >= 0 else t.error
        change = _core.text(f"{delta:+.1f}%", size=12, color=color, wrap=False)
    return _core.container(
        _core.column(
            [
                label(title, size="sm", color="text_muted", theme=t),
                _core.row([_core.text(value, size=24, weight="semibold", color=t.text, wrap=False), change],
                          spacing=8, align="end"),
                sparkline(trend, width=160, height=28, theme=t) if trend else None,
            ],
            spacing=4,
        ),
        padding=14,
        width=width,
        bg=t.surface,
        border_color=t.border_variant,
        border_width=1.0,
        radius=t.radius + 2,
    )



def markdown(source: str, *, size: Optional[float] = None, on_link: Any = None, width: Any = None,
             theme: Optional[Theme] = None) -> _core.Widget:
    """``pz.markdown`` with the theme's text, link and code colors."""
    t = _theme(theme)
    return _core.markdown(source, size=size or t.ui_font_size, color=t.text, link_color=t.text_accent,
                          code_color=t.editor_text, code_bg=t.element, on_link=on_link, width=width)


def split(first: Any, second: Any, *, ratio: float = 0.5, on_resize: Any = None, vertical: bool = False,
          min_size: float = 80, theme: Optional[Theme] = None, **kwargs) -> _core.Widget:
    """``pz.split`` with a divider in the theme's border color (accent while dragged/hovered)."""
    t = _theme(theme)
    return _core.split(first, second, ratio=ratio, on_resize=on_resize, vertical=vertical, min_size=min_size,
                       color=t.border_variant, hover_color=t.border_focused, **kwargs)
