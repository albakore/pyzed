"""Display components: callouts, tables, empty states, small charts and popovers."""

from __future__ import annotations

import builtins
import math
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

    Events:
        ``on_dismiss()``: Adds a close button.
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


def count_badge(count: int, *, tint: str = "accent", max: int = 99, show_zero: bool = True,  # noqa: A002
                theme: Optional[Theme] = None) -> _core.Widget:
    """A small round counter (unread notifications, problems...). Shows ``99+`` past ``max``.

    With ``show_zero=False`` a count of 0 draws nothing, so it can stay in the layout.
    """
    t = _theme(theme)
    if count <= 0 and not show_zero:
        return _core.space(width=0, height=0)
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
    size: str = "md",
    height: Any = "fill",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A centered placeholder for empty lists, search results with no hits, etc.

    ``size="sm"`` makes it compact (inside a panel or a table); ``height`` is ``"fill"`` by
    default, a number or ``"shrink"`` to take only what it needs.
    """
    t = _theme(theme)
    actions = list(actions)
    icon_size, title_size, text_size = {"sm": (20, "md", "sm"), "md": (32, "lg", "md"), "lg": (44, "xl", "md")}[size]
    return _core.container(
        _core.column(
            [
                _icon(icon, size=icon_size, color=t.icon_muted),
                label(title, size=title_size, weight="medium", theme=t),
                label(description, size=text_size, color="text_muted", align_x="center", theme=t) if description else None,
                _core.row(actions, spacing=8) if actions else None,
            ],
            spacing=6 if size == "sm" else 8,
            align="center",
            max_width=360,
        ),
        width="fill",
        height=height,
        padding=12 if height == "shrink" else 0,
        center=True,
    )


def settings_group(
    title: str,
    rows: Iterable[Any],
    *,
    description: Optional[str] = None,
    end: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A titled block of ``ui.field`` rows separated by thin lines (Zed's settings UI).

    ``end`` goes at the right of the title (a Reset button, a link...).
    """
    t = _theme(theme)
    body: List[Any] = []
    for i, row in enumerate(rows):
        if i:
            body.append(_core.rule(thickness=1, color=t.border_variant))
        body.append(_core.container(row, padding=(10, 14)))
    return _core.column(
        [
            _core.row([label(title, weight="semibold", theme=t), _core.space(width="fill"), end], align="center")
            if end is not None else label(title, weight="semibold", theme=t),
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
    such as ``"fill:2"``. ``align`` is ``"start"``, ``"center"`` or ``"end"``.
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
    on_row_double_press: Any = None,
    on_row_context: Any = None,
    empty: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A data table with a sticky header, optional sorting and row selection.

    ``columns`` are ``ui.Column`` objects or plain keys. ``rows`` are dicts or objects.
    Sorting is done here when ``sort_by`` names a column title: clicking a header calls
    ``on_sort(title)`` and you flip ``sort_by``/``descending`` in your state.
    ``on_row_press(row)`` makes rows clickable; the row equal to ``selected`` (or every row in
    it, when it is a list or set) is highlighted. ``on_row_double_press(row)`` runs on a double
    click (open, edit) and ``on_row_context(row)`` on a right click (a context menu). ``empty``
    (a text or a widget) is shown in place of the rows when there are none.

    Rows are virtualized: only the ones in view are built, so a table with hundreds of
    thousands of rows scrolls as smoothly as a short one. ``rows`` should be a list (or any
    sequence); sorting a huge list on every ``view()`` is the remaining cost, so keep it
    sorted in your state or sort it in a ``@pz.memo`` function.

    Events:
        ``on_sort(title)``: Callable that receives the clicked title.
        ``on_row_press(row)``: Callable that receives the clicked row.
        ``on_row_double_press(row)``: Called with the row on a double click (open, edit…).
        ``on_row_context(row)``: Called with the row on a right click (a context menu).
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
    many = isinstance(selected, (list, set, frozenset, tuple))

    def body_row(i: int) -> _core.Widget:
        row = rows[i]
        cells = [cell(col.render(col.value(row)) if col.render else col.value(row), col, t.text) for col in cols]
        content = _core.row(cells, align="center", height="fill")
        is_selected = selected is not None and (row in selected if many else row == selected)
        bg = t.ghost_selected if is_selected else (alpha(t.text, 0.03) if striped and i % 2 else "transparent")
        if on_row_press is not None:
            widget = _core.button(content, lambda r=row: on_row_press(r), width="fill", height=row_height,
                                  padding=0, bg=bg, hover_bg=t.ghost_selected if is_selected else t.ghost_hover,
                                  radius=0)
        else:
            widget = _core.container(content, width="fill", height=row_height, bg=bg)
        handlers = {}
        if on_row_double_press is not None:
            handlers["double_click"] = lambda r=row: on_row_double_press(r)
        if on_row_context is not None:
            handlers["right_click"] = lambda r=row: on_row_context(r)
        return widget.on(**handlers) if handlers else widget

    if not rows and empty is not None:
        placeholder = empty if isinstance(empty, _core.Widget) else label(empty, color="text_muted", theme=t)
        body = _core.container(placeholder, width="fill", padding=16, align_x="center")
    else:
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

    Events:
        ``on_dismiss()``: Message or callable sent on close.
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


def _short(value: float) -> str:
    """``1260`` → ``"1.3k"``: an axis label that stays narrow."""
    magnitude = abs(value)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if magnitude >= limit:
            return f"{value / limit:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{value:.2f}".rstrip("0").rstrip(".") if magnitude < 10 and value != int(value) else f"{value:.0f}"


def _nice_step(raw: float) -> float:
    """The round step (1, 2, 2.5 or 5 times a power of ten) closest above ``raw``."""
    power = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1.0
    for factor in (1, 2, 2.5, 5, 10):
        if raw <= factor * power + 1e-12:
            return factor * power
    return 10 * power


def line_chart(
    series: Any,
    *,
    labels: Optional[Sequence[str]] = None,
    width: float = 360,
    height: float = 180,
    colors: Optional[Sequence[str]] = None,
    fill: bool = False,
    points: bool = False,
    grid: bool = True,
    legend: Optional[bool] = None,
    min: Optional[float] = None,  # noqa: A002
    max: Optional[float] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A line chart with axes: one list of numbers, several lists, or ``{name: values}``.

    ``labels`` go under the x axis (thinned out when they do not fit); the y axis shows four
    steps from ``min`` to ``max`` (worked out from the data when ``None``). ``fill`` shades
    under each line, ``points`` marks each value and ``grid`` draws the horizontal lines.
    With a dict, a ``legend`` of the names goes under the chart (``legend=False`` hides it).
    """
    t = _theme(theme)
    if isinstance(series, dict):
        names: List[str] = [str(k) for k in series]
        lines = [list(v) for v in series.values()]
    elif series and isinstance(next(iter(series)), (list, tuple)):
        names, lines = [], [list(v) for v in series]
    else:
        names, lines = [], [list(series)]
    lines = [values for values in lines if values]
    palette = list(colors) if colors else [t.accent, t.success, t.warning, t.error, t.info, *t.players]
    if not lines:
        return _core.space(width=width, height=height)
    flat = [v for values in lines for v in values]
    lo = builtins.min(flat) if min is None else min
    hi = builtins.max(flat) if max is None else max
    if min is None and lo > 0 and lo < (hi - lo):
        lo = 0.0  # small positive data reads better from zero
    if hi == lo:
        hi = lo + 1.0
    # round steps (1, 2, 2.5 or 5 times a power of ten) unless both ends are given
    step_y = _nice_step((hi - lo) / 4)
    if min is None:
        lo = math.floor(lo / step_y + 1e-9) * step_y
    if max is None:
        hi = math.ceil(hi / step_y - 1e-9) * step_y
    span = hi - lo
    ticks = [lo + step_y * i for i in range(int(round(span / step_y)) + 1)] if min is None or max is None \
        else [lo + span * i / 4 for i in range(5)]
    axis = builtins.max(len(_short(v)) for v in ticks) * 6.5 + 8
    last = str(labels[builtins.min(len(labels), builtins.max(len(v) for v in lines)) - 1]) if labels else ""
    left, top, right = axis, 6.0, builtins.max(8.0, len(last) * 3.5)
    bottom = height - (20 if labels else 6)
    plot_w, plot_h = width - left - right, bottom - top
    count = builtins.max(len(values) for values in lines)
    step = plot_w / builtins.max(count - 1, 1)

    def at(i: int, v: float) -> tuple:
        return (left + i * step, bottom - (v - lo) / span * plot_h)

    shapes: List[Any] = []
    for value in ticks:
        y = bottom - (value - lo) / span * plot_h
        if grid:
            shapes.append(draw.line(left, y, width - right, y, stroke=alpha(t.text, 0.07 if value != lo else 0.2)))
        shapes.append(draw.text(left - 6, y, _short(value), color=t.text_placeholder, size=10.5, align_x="end",
                                align_y="center"))
    if labels:
        every = builtins.max(1, int(len(labels) * 44 / builtins.max(plot_w, 1)) + 1)
        for i, text in enumerate(labels[:count]):
            if i % every == 0:
                shapes.append(draw.text(left + i * step, height - 2, text, color=t.text_muted, size=11,
                                        align_x="center", align_y="bottom"))
    for n, values in enumerate(lines):
        color = t.color(palette[n % len(palette)])
        pts = [at(i, v) for i, v in enumerate(values)]
        if fill and len(pts) > 1:
            shapes.append(draw.polygon([(pts[0][0], bottom), *pts, (pts[-1][0], bottom)], fill=alpha(color, 0.14)))
        if len(pts) > 1:
            shapes.append(draw.polyline(pts, stroke=color, width=2))
        if points or len(pts) == 1:
            shapes.extend(draw.circle(x, y, 3, fill=color) for x, y in pts)
    chart = _core.canvas(shapes, width=width, height=height)
    if not names or legend is False:
        return chart
    keys = _core.row([
        _core.row([_core.container(None, width=10, height=3, radius=2, bg=t.color(palette[n % len(palette)])),
                   label(name, size="sm", color="text_muted", wrap=False, theme=t)], spacing=5, align="center")
        for n, name in enumerate(names[:len(lines)])
    ], spacing=14, wrap=True, padding=(0, 0, 0, left))
    return _core.column([chart, keys], spacing=6)


def gauge(
    value: float,
    *,
    min: float = 0.0,  # noqa: A002
    max: float = 100.0,  # noqa: A002
    size: float = 140,
    thickness: float = 12,
    unit: str = "",
    label: Any = None,
    tint: str = "accent",
    thresholds: Optional[Sequence[tuple]] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A half-circle meter for one number, like a speedometer: CPU use, temperature, a score.

    ``unit`` follows the number in the middle and ``label`` goes under it. ``thresholds``
    are ``(from_value, color)`` pairs that recolor the arc as the value climbs, such as
    ``[(70, "warning"), (90, "error")]``.
    """
    t = _theme(theme)
    span = (max - min) or 1.0
    fraction = _fraction((value - min) / span)
    color = tint
    for limit, tone in sorted(thresholds or (), key=lambda pair: pair[0]):
        if value >= limit:
            color = tone
    r = (size - thickness) / 2
    c = size / 2
    base = c + 2
    shapes: List[Any] = [draw.arc(c, base, r, 180, 360, stroke=alpha(t.text, 0.08), width=thickness, cap="round")]
    if fraction > 0:
        shapes.append(draw.arc(c, base, r, 180, 180 + 180 * fraction, stroke=t.color(color), width=thickness,
                               cap="round"))
    number = f"{value:.0f}" if float(value).is_integer() or abs(value) >= 100 else f"{value:.1f}"
    shapes.append(draw.text(c, base - 2, number + unit, color=t.text, size=size * 0.17, weight="semibold",
                            align_x="center", align_y="bottom"))
    height = base + thickness / 2 + 2
    if label is not None:
        shapes.append(draw.text(c, base + 6, label, color=t.text_muted, size=12, align_x="center"))
        height = base + 22
    return _core.canvas(shapes, width=size, height=height)


def progress_ring(
    value: Optional[float],
    *,
    max: float = 1.0,  # noqa: A002
    size: float = 40,
    thickness: float = 4,
    tint: str = "accent",
    show_value: bool = False,
    label: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A round progress bar: the ring fills clockwise from the top as ``value`` reaches ``max``.

    ``value=None`` spins (indeterminate). ``show_value`` writes the percentage in the middle and
    ``label`` any other text there instead (``"3/8"``).
    """
    t = _theme(theme)
    if value is None:
        return spinner(size=size, tint=tint, theme=t)
    fraction = _fraction(value / (max or 1.0))
    c = size / 2
    r = c - thickness / 2
    shapes: List[Any] = [draw.circle(c, c, r, stroke=alpha(t.color(tint), 0.18), width=thickness)]
    if fraction >= 1:
        shapes.append(draw.circle(c, c, r, stroke=t.color(tint), width=thickness))
    elif fraction > 0:
        shapes.append(draw.arc(c, c, r, -90, -90 + 360 * fraction, stroke=t.color(tint), width=thickness,
                               cap="round"))
    text = label if label is not None else (f"{fraction:.0%}" if show_value else None)
    if text is not None:
        shapes.append(draw.text(c, c, text, color=t.text, size=builtins.max(size * 0.26, 9), weight="medium",
                                align_x="center", align_y="center"))
    return _core.canvas(shapes, width=size, height=size)


def _fraction(value: float) -> float:
    return 0.0 if value < 0 else 1.0 if value > 1 else float(value)


def skeleton(
    width: Any = "fill",
    height: float = 12,
    *,
    lines: int = 1,
    circle: bool = False,
    radius: Optional[float] = None,
    spacing: float = 8,
    animated: bool = True,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A grey placeholder that pulses where content is still loading.

    One bar of ``width`` × ``height``; ``lines`` stacks several, the last one shorter, like a
    paragraph; ``circle`` makes a round one of ``height`` (an avatar). ``animated=False``
    keeps it still (it also stays still when the system asks for reduced motion).
    """
    t = _theme(theme)
    color = alpha(t.text, 0.09)

    def bar(w: Any, h: float, r: float) -> Any:
        return _core.container(None, width=w, height=h, bg=color, radius=r)

    if circle:
        shape = bar(height, height, height / 2)
    elif lines > 1:
        r = t.radius_sm if radius is None else radius
        rows = [bar(width, height, r) for _ in range(lines - 1)]
        rows.append(_core.row([bar("fill:3", height, r), _core.space(width="fill:2")], width=width))
        shape = _core.column(rows, spacing=spacing, width=width)
    else:
        shape = bar(width, height, t.radius_sm if radius is None else radius)
    if not animated:
        return shape
    return shape.animate(opacity=0.45, duration=900, repeat="infinite", direction="alternate", easing="ease_in_out")


@dataclass
class TimelineItem:
    """One entry of a ``timeline``: a ``title``, its ``time`` and ``description``, an ``icon``
    in the dot, the dot's ``tint`` and any widget as ``content`` under the text."""

    title: str
    description: Optional[str] = None
    time: Optional[str] = None
    icon: Optional[str] = None
    tint: str = "accent"
    content: Any = None


def timeline(
    items: Sequence[Any],
    *,
    on_press: Optional[Callable[[int], Any]] = None,
    dense: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Events in order down a line: a history, a changelog, the steps of a delivery.

    ``items`` are ``TimelineItem`` objects, dicts with the same keys, or plain titles. Each
    gets a dot (with its ``icon`` inside, if any) joined to the next by a line; ``time`` goes
    to the right of the title. ``dense`` uses small dots and less space; ``on_press(index)``
    makes the entries clickable.

    Events:
        ``on_press(index)``: Called with the index of the clicked entry.
    """
    t = _theme(theme)
    entries = [item if isinstance(item, TimelineItem) else
               TimelineItem(**item) if isinstance(item, dict) else TimelineItem(str(item)) for item in items]
    dot_size = 10 if dense else 22
    rows: List[Any] = []
    for i, item in enumerate(entries):
        color = t.color(item.tint)
        if item.icon and not dense:
            dot = _core.container(_icon(item.icon, size=12, color=color), width=dot_size, height=dot_size,
                                  center=True, radius=dot_size / 2, bg=alpha(color, 0.16),
                                  border_color=alpha(color, 0.6), border_width=1.0)
        else:
            dot = _core.container(None, width=dot_size, height=dot_size, radius=dot_size / 2,
                                  bg=color if dense else alpha(color, 0.16), border_color=color, border_width=2.0)
        last = i == len(entries) - 1
        rail = _core.column([
            _core.container(dot, padding=(2 if dense else 0, 0, 0, 0)),
            None if last else _core.container(None, width=2, height="fill", bg=t.border_variant, radius=1),
        ], spacing=2 if dense else 4, align="center", width=dot_size, height="fill")
        text = _core.column([
            _core.row([label(item.title, weight="medium", wrap=False, theme=t), _core.space(width="fill"),
                       label(item.time, size="sm", color="text_placeholder", wrap=False, theme=t)
                       if item.time else None], spacing=8, align="center", width="fill"),
            label(item.description, size="sm", color="text_muted", theme=t) if item.description else None,
            item.content,
        ], spacing=2 if dense else 4, width="fill", padding=(0, 0, 4 if dense else 14, 0))
        body = _core.container(text, width="fill", padding=(0, 0, 0, 0))
        if on_press is not None:
            body = body.on(click=lambda i=i: on_press(i), cursor="pointer")
        rows.append(_core.row([rail, body], spacing=8 if dense else 12, width="fill", height="shrink"))
    return _core.column(rows, width="fill")


def description_list(
    items: Any,
    *,
    label_width: Any = 140,
    vertical: bool = False,
    dividers: bool = True,
    mono_values: bool = False,
    selectable: bool = True,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Name and value pairs, one per row: the details of a file, an order or a device.

    ``items`` is a dict or ``(name, value)`` pairs; a value may be text or any widget (a
    badge, a link). Names take ``label_width`` on the left, or go above the value with
    ``vertical``. ``mono_values`` writes text values in the monospace font (ids, hashes);
    ``selectable`` lets them be selected and copied.
    """
    t = _theme(theme)
    pairs = list(items.items()) if isinstance(items, dict) else [tuple(pair) for pair in items]
    rows: List[Any] = []
    for i, (name, value) in enumerate(pairs):
        if isinstance(value, _core.Widget):
            shown = value
        else:
            shown = label("—" if value is None else str(value), mono=mono_values, theme=t,
                          selectable="description_list" if selectable else False)
        title = label(name, size="sm", color="text_muted", wrap=False, theme=t)
        if vertical:
            row = _core.column([title, shown], spacing=2, width="fill")
        else:
            row = _core.row([_core.container(title, width=label_width), _core.container(shown, width="fill")],
                            spacing=12, align="center", width="fill")
        if i and dividers:
            rows.append(_core.container(None, width="fill", height=1, bg=t.border_variant))
        rows.append(_core.container(row, width="fill", padding=(6, 0)))
    return _core.column(rows, width="fill")


def spinner(*, size: float = 16, tint: str = "accent", speed: float = 1.0, theme: Optional[Theme] = None) -> _core.Widget:
    """A spinning arc for "loading" states.

    It turns by itself (``speed`` turns per second), redrawn without calling ``view()`` again:
    no subscription is needed to keep it moving.
    """
    t = _theme(theme)
    c = size / 2
    w = max(1.5, size / 8)
    r = c - w
    return _core.canvas(
        [
            draw.circle(c, c, r, stroke=alpha(t.color(tint), 0.2), width=w),
            draw.arc(c, c, r, 0, 100, stroke=t.color(tint), width=w, cap="round"),
        ],
        width=size,
        height=size,
        spin=speed,
    )


def stat(title: str, value: Any, *, delta: Optional[float] = None, trend: Optional[Sequence[float]] = None,
         width: Any = None, icon: Optional[str] = None, inverse: bool = False, on_press: Any = None,
         theme: Optional[Theme] = None) -> _core.Widget:
    """A dashboard number: title, big value, optional change (``+4.2%``) and sparkline.

    ``icon`` goes before the title; ``inverse=True`` colors a drop green and a rise red (for
    errors, latency...); ``on_press`` makes the card clickable (drill down).

    Events:
        ``on_press()``: Makes the card clickable.
    """
    t = _theme(theme)
    change = None
    if delta is not None:
        good = delta <= 0 if inverse else delta >= 0
        color = t.success if good else t.error
        change = _core.text(f"{delta:+.1f}%", size=12, color=color, wrap=False)
    heading = label(title, size="sm", color="text_muted", theme=t)
    if icon:
        heading = _core.row([_icon(icon, size=13, color=t.icon_muted), heading], spacing=6, align="center")
    card = _core.container(
        _core.column(
            [
                heading,
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
    return card if on_press is None else card.on(click=on_press, cursor="pointer")


def markdown(source: str, *, size: Optional[float] = None, on_link: Any = None, width: Any = None,
             selectable: Any = None, theme: Optional[Theme] = None) -> _core.Widget:
    """``pz.markdown`` with the theme's text, link and code colors.

    ``selectable=True`` lets the mouse select its text (Ctrl+C copies); a string names a selection
    group shared with other texts (the messages of a chat), so one drag can cross them.

    Events:
        ``on_link(url)``: Callable that receives the URL when a link is clicked.
    """
    t = _theme(theme)
    return _core.markdown(source, size=size or t.ui_font_size, color=t.text, link_color=t.text_accent,
                          code_color=t.editor_text, code_bg=t.element, on_link=on_link, width=width,
                          selectable=selectable, selection_color=t.selection if selectable else None)


def split(first: Any, second: Any, *, ratio: float = 0.5, on_resize: Any = None, vertical: bool = False,
          min_size: float = 80, theme: Optional[Theme] = None, **kwargs) -> _core.Widget:
    """``pz.split`` with a divider in the theme's border color (accent while dragged/hovered).

    Events:
        ``on_resize(ratio)``: Callable that receives the new ratio.
    """
    t = _theme(theme)
    return _core.split(first, second, ratio=ratio, on_resize=on_resize, vertical=vertical, min_size=min_size,
                       color=t.border_variant, hover_color=t.border_focused, **kwargs)
