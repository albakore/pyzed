"""Flexbox-style layout on top of ``row``/``column``.

``pz.grid`` (track grids with ``pz.cell``) and ``pz.resizable`` live in the Rust core;
``pz.flex`` arranges children along one axis with CSS-like ``justify`` and ``align``.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from . import _core

JUSTIFY = ("start", "center", "end", "between", "around", "evenly")
ALIGN = ("start", "center", "end")
DIRECTIONS = ("row", "column")


class FlexItem:
    """A child of ``pz.flex`` with its own sizing; made with ``pz.flex_item``."""

    __slots__ = ("content", "grow", "basis", "align")

    def __init__(self, content: Any, grow: float, basis: Any, align: Optional[str]):
        self.content = content
        self.grow = grow
        self.basis = basis
        self.align = align

    def __repr__(self) -> str:
        return f"<FlexItem grow={self.grow} basis={self.basis!r} align={self.align!r}>"


def flex_item(content: Any, *, grow: float = 1, basis: Any = None, align: Optional[str] = None) -> FlexItem:
    """Sizes a child of ``pz.flex``.

    ``grow`` is its share of the free space along the main axis (``0`` keeps its natural
    size); ``basis`` gives it a fixed main size instead (pixels). ``align`` overrides the
    flex's cross-axis alignment for this child.
    """
    if grow < 0:
        raise ValueError("grow must be 0 or more")
    if align is not None and align not in ALIGN:
        raise ValueError(f"align must be one of {', '.join(ALIGN)}")
    return FlexItem(content, grow, basis, align)


def _items(children: Any) -> List[Any]:
    if children is None:
        return []
    if isinstance(children, (_core.Widget, FlexItem, str)):
        return [children]
    out: List[Any] = []
    for child in children:
        if child is None or child is False:
            continue
        out.append(child)
    return out


def flex(
    children: Iterable[Any] = (),
    *,
    direction: str = "row",
    justify: str = "start",
    align: str = "start",
    gap: float = 0,
    wrap: bool = False,
    padding: Any = None,
    width: Any = None,
    height: Any = None,
) -> _core.Widget:
    """Lays children out along one axis, like CSS flexbox.

    - ``direction``: ``"row"`` (left to right) or ``"column"`` (top to bottom).
    - ``justify``: where children sit on the main axis: ``"start"``, ``"center"``, ``"end"``,
      ``"between"`` (free space between them), ``"around"`` (around each) or ``"evenly"``.
      It has no effect when a child grows (see ``pz.flex_item``), since growing children
      take the free space.
    - ``align``: cross-axis alignment, ``"start"``, ``"center"`` or ``"end"``.
    - ``gap``: space between children. ``wrap=True`` (rows only) wraps onto new lines.

    The main axis fills the available space when ``justify`` needs room; otherwise pass
    ``width``/``height`` as usual.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"direction must be one of {', '.join(DIRECTIONS)}")
    if justify not in JUSTIFY:
        raise ValueError(f"justify must be one of {', '.join(JUSTIFY)}")
    if align not in ALIGN:
        raise ValueError(f"align must be one of {', '.join(ALIGN)}")
    is_row = direction == "row"
    if wrap and not is_row:
        raise ValueError("wrap=True only works with direction='row'")
    if wrap and justify != "start":
        raise ValueError("wrap=True only works with justify='start'")
    items = _items(children)
    grows = any(isinstance(i, FlexItem) and i.grow > 0 and i.basis is None for i in items)
    main = "width" if is_row else "height"
    cross = "height" if is_row else "width"
    if (justify != "start" or grows) and (width if is_row else height) is None:
        if is_row:
            width = "fill"
        else:
            height = "fill"

    widgets: List[Any] = []
    for item in items:
        if not isinstance(item, FlexItem):
            widgets.append(item)
            continue
        size = item.basis if item.basis is not None else (f"fill:{max(1, round(item.grow))}" if item.grow > 0 else None)
        box: dict = {main: size}
        if item.align is not None:
            box[cross] = "fill"
            box["align_y" if is_row else "align_x"] = item.align
        widgets.append(_core.container(item.content, **box))

    container = _core.row if is_row else _core.column
    options: dict = {"width": width, "height": height, "padding": padding, "align": align}
    if wrap:
        return _core.row(widgets, spacing=gap, wrap=True, **options)
    if justify == "start" or grows or not widgets:
        return container(widgets, spacing=gap, **options)

    def spacer(portion: int) -> _core.Widget:
        return _core.space(**{main: "fill" if portion == 1 else f"fill:{portion}"})

    ends = {"center": 1, "end": 0, "between": 0, "around": 1, "evenly": 1}[justify]
    middle = {"center": 0, "end": 0, "between": 1, "around": 2, "evenly": 1}[justify]
    seq: List[Any] = []
    if ends or justify == "end":
        seq.append(spacer(1 if justify == "end" else ends))
    for i, widget in enumerate(widgets):
        if i:
            if gap:
                seq.append(_core.space(**{main: gap}))
            if middle:
                seq.append(spacer(middle))
        seq.append(widget)
    if ends:
        seq.append(spacer(ends))
    return container(seq, **options)


class AnchorItem:
    """A child of ``pz.anchor_layout`` with its place, size and anchor; made with ``pz.anchor``."""

    __slots__ = ("content", "rect", "edges", "min_size", "max_size", "pivot", "rotate")

    def __init__(self, content: Any, rect: tuple, edges: tuple, min_size: tuple, max_size: tuple, pivot: tuple,
                 rotate: float):
        self.content = content
        self.rect = rect
        self.edges = edges
        self.min_size = min_size
        self.max_size = max_size
        self.pivot = pivot
        self.rotate = rotate

    def __repr__(self) -> str:
        return f"<AnchorItem rect={self.rect!r} anchor={self.edges!r}>"


def anchor(content: Any, *, x: float = 0, y: float = 0, width: float = 100, height: float = 28,
           anchor: Any = "top_left", min_width: float = 0, min_height: float = 0, max_width: float = 0,
           max_height: float = 0, pivot: tuple = (0.5, 0.5), rotate: float = 0) -> AnchorItem:
    """Places a child of ``pz.anchor_layout`` at ``x``, ``y`` with ``width`` and ``height`` (in the layout's
    design size) and says how it follows a resize.

    ``anchor`` is a preset of ``pyzed.anchors.PRESETS`` (``"top_right"``, ``"bottom_wide"``, ``"center"``,
    ``"full"``...), words (``"left right bottom"``) or a tuple of edges. ``min_*`` and ``max_*`` limit the
    size when it stretches (``0``: no limit), ``pivot`` is the point that stays put when a limit stops it
    and that ``rotate`` (degrees clockwise) turns around.
    """
    from . import anchors

    return AnchorItem(content, (float(x), float(y), float(width), float(height)), anchors.edges(anchor),
                      (float(min_width), float(min_height)), (float(max_width), float(max_height)),
                      (float(pivot[0]), float(pivot[1])), float(rotate))


def anchor_layout(children: Iterable[AnchorItem], *, design: Optional[tuple] = None, width: Any = "fill",
                  height: Any = "fill") -> _core.Widget:
    """Places children made with ``pz.anchor`` freely, like a designed form: when the layout is resized,
    each child follows its anchor (keeps its distance to the edges it is anchored to, stretches between
    opposite ones, stays centered otherwise).

    ``design`` is the size the children's ``x``, ``y``, ``width`` and ``height`` were laid out in; by default
    the smallest size that holds them all. Later children are drawn on top::

        pz.anchor_layout([
            pz.anchor(ui.heading("Report"), x=16, y=12, width=368, height=28, anchor="top_wide"),
            pz.anchor(ui.button("Close", on_close), x=284, y=252, width=100, height=32, anchor="bottom_right"),
        ], design=(400, 300))
    """
    from . import anchors

    items = [c for c in children if c is not None]
    for item in items:
        if not isinstance(item, AnchorItem):
            raise TypeError("pz.anchor_layout children must be made with pz.anchor(...)")
    if design is None:
        design = (max((i.rect[0] + i.rect[2] for i in items), default=0.0),
                  max((i.rect[1] + i.rect[3] for i in items), default=0.0))

    def build(available_width: float, available_height: float) -> Any:
        placed = []
        for item in items:
            x, y, w, h = anchors.place(item.rect, item.edges, design, (available_width, available_height),
                                       min_size=item.min_size, max_size=item.max_size, pivot=item.pivot)
            content = _core.container(item.content, width=w, height=h)
            if item.rotate:
                dx, dy = anchors.pivot_offset((w, h), item.pivot, item.rotate)
                content = content.style(rotate=item.rotate, translate=(dx, dy))
            placed.append(_core.pin(content, x=x, y=y))
        return _core.stack(placed, width="fill", height="fill")

    return _core.container(_core.responsive(build), width=width, height=height)
