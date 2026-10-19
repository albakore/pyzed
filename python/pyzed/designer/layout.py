"""Where every control of a form goes, containers included.

Controls inside a container are positioned by it:

* ``free`` containers (panel, group box, card...) keep their children where they were
  dropped, in coordinates relative to the container, and resize them with their anchors;
* ``flex`` containers line their children up in a row or a column, like CSS flexbox
  (``gap``, ``padding``, ``justify``, ``align`` and a per-child ``grow``);
* ``grid`` containers place their children in cells, left to right and top to bottom
  (``columns``, ``gap``, ``padding``, ``row_height`` and a per-child ``span``).

``resolve`` turns a form into absolute rectangles. The designer and the running form
both draw from it, so a layout looks the same while designing and at run time. Like
``geometry`` it has no UI dependency.
"""

from __future__ import annotations

from typing import Any, Collection, Dict, Iterable, List, Optional, Sequence, Tuple

from . import components as _components
from .geometry import MIN_SIZE, anchored, contains
from .model import Control, Form

Rect = Tuple[float, float, float, float]

FLEX_DIRECTIONS = ("row", "column")
JUSTIFY = ("start", "center", "end", "space-between", "space-around", "space-evenly")
ALIGN_ITEMS = ("stretch", "start", "center", "end")


def kind(control: Control) -> Optional[str]:
    """``"free"``, ``"flex"`` or ``"grid"`` for containers, ``None`` for other controls."""
    try:
        return _components.get(control.type).container
    except KeyError:
        return None


def props(control: Control) -> Dict[str, Any]:
    """Returns the control's properties merged over its component's defaults (just its own for an unknown
    type)."""
    try:
        defaults = _components.get(control.type).defaults()
    except KeyError:
        defaults = {}
    return {**defaults, **control.props}


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _padding(p: Dict[str, Any]) -> float:
    return max(_num(p.get("padding")), 0.0)


def managed(form: Form, control: Control) -> bool:
    """``True`` when the parent lays the control out (its x and y are ignored)."""
    parent = form.get(control.parent) if control.parent else None
    return parent is not None and kind(parent) in ("flex", "grid")


# -- layouts -----------------------------------------------------------------------


def flex(box: Rect, items: Sequence[Tuple[float, float, float]], *, direction: str = "row", gap: float = 0,
         justify: str = "start", align: str = "stretch") -> List[Rect]:
    """Rectangles for ``items`` (``(width, height, grow)``) laid out in a row or column inside ``box``."""
    x, y, w, h = box
    row = direction != "column"
    main_total, cross_total = (w, h) if row else (h, w)
    n = len(items)
    if not n:
        return []
    mains = [max(it[0] if row else it[1], MIN_SIZE) for it in items]
    crosses = [max(it[1] if row else it[0], MIN_SIZE) for it in items]
    grows = [max(_num(it[2]), 0.0) for it in items]
    free = main_total - sum(mains) - gap * (n - 1)
    if free > 0 and sum(grows) > 0:
        total = sum(grows)
        mains = [m + free * g / total for m, g in zip(mains, grows)]
        free = 0.0
    elif free < 0:  # too little room: shrink every item by its share of the space, like CSS flex-shrink
        total = sum(mains)
        mains = [max(m + free * m / total, MIN_SIZE) for m in mains]
        free = 0.0
    start, between = 0.0, gap
    if free > 0:
        if justify == "center":
            start = free / 2
        elif justify == "end":
            start = free
        elif justify == "space-between" and n > 1:
            between = gap + free / (n - 1)
        elif justify == "space-around":
            between = gap + free / n
            start = free / n / 2
        elif justify == "space-evenly":
            between = gap + free / (n + 1)
            start = free / (n + 1)
    out: List[Rect] = []
    pos = start
    for main, cross in zip(mains, crosses):
        if align == "stretch":
            c0, size = 0.0, cross_total
        else:
            size = min(cross, cross_total) if cross_total > 0 else cross
            c0 = {"center": (cross_total - size) / 2, "end": cross_total - size}.get(align, 0.0)
        if row:
            out.append((x + pos, y + c0, main, size))
        else:
            out.append((x + c0, y + pos, size, main))
        pos += main + between
    return out


def grid(box: Rect, items: Sequence[Tuple[float, float, int]], *, columns: int = 2, gap: float = 0,
         row_height: float = 0, align: str = "stretch") -> List[Rect]:
    """Rectangles for ``items`` (``(width, height, span)``) placed in cells inside ``box``.

    Items fill the cells left to right, wrapping to a new row; ``span`` makes one take
    several columns. ``row_height`` 0 shares the height equally between the rows.
    """
    x, y, w, h = box
    columns = max(int(columns), 1)
    cells: List[Tuple[int, int, int]] = []  # row, column, span
    r = c = 0
    for _, _, span in items:
        span = min(max(int(span or 1), 1), columns)
        if c + span > columns:
            r, c = r + 1, 0
        cells.append((r, c, span))
        c += span
        if c >= columns:
            r, c = r + 1, 0
    rows = (cells[-1][0] + 1) if cells else 0
    if not rows:
        return []
    cell_w = (w - gap * (columns - 1)) / columns
    cell_h = row_height if row_height > 0 else (h - gap * (rows - 1)) / rows
    out: List[Rect] = []
    for (iw, ih, _), (row, col, span) in zip(items, cells):
        cx = x + col * (cell_w + gap)
        cy = y + row * (cell_h + gap)
        cw = cell_w * span + gap * (span - 1)
        if align == "stretch":
            out.append((cx, cy, max(cw, MIN_SIZE), max(cell_h, MIN_SIZE)))
            continue
        iw, ih = min(iw, cw), min(ih, cell_h)
        dx = {"center": (cw - iw) / 2, "end": cw - iw}.get(align, 0.0)
        dy = {"center": (cell_h - ih) / 2, "end": cell_h - ih}.get(align, 0.0)
        out.append((cx + dx, cy + dy, iw, ih))
    return out


def content_box(control: Control, rect: Rect) -> Rect:
    """The area of a container where its children go."""
    if kind(control) in ("flex", "grid"):
        pad = _padding(props(control))
        x, y, w, h = rect
        return (x + pad, y + pad, max(w - 2 * pad, 0), max(h - 2 * pad, 0))
    return rect


def arrange(form: Form, container: Control, rect: Rect, children: Sequence[Control],
            sizes: Optional[Dict[str, Tuple[float, float]]] = None) -> List[Rect]:
    """Where a flex or grid ``container`` drawn at ``rect`` puts ``children``."""
    p = props(container)
    box = content_box(container, rect)
    sizes = sizes or {}
    gap = max(_num(p.get("gap")), 0.0)
    if kind(container) == "grid":
        items = [(*sizes.get(c.name, (c.width, c.height)), int(_num(c.layout.get("span"), 1))) for c in children]
        return grid(box, items, columns=int(_num(p.get("columns"), 2)), gap=gap,
                    row_height=_num(p.get("row_height")), align=str(p.get("align", "stretch")))
    items = [(*sizes.get(c.name, (c.width, c.height)), _num(c.layout.get("grow"))) for c in children]
    return flex(box, items, direction=str(p.get("direction", "row")), gap=gap,
                justify=str(p.get("justify", "start")), align=str(p.get("align", "stretch")))


def resolve(form: Form, size: Optional[Tuple[float, float]] = None, *, free: Collection[str] = ()) -> Dict[str, Rect]:
    """The absolute rectangle of every control.

    ``size`` is the window's current client size (the design size when ``None``):
    top-level controls and children of free containers follow their anchors. Controls
    named in ``free`` are placed at their own x and y even inside a flex or grid
    container (the designer uses it for controls being dragged).
    """
    design = (form.width, form.height)
    actual = size or design
    out: Dict[str, Rect] = {}

    def place(parent: Optional[Control], origin: Rect, design_size: Tuple[float, float]) -> None:
        children = form.children(parent.name if parent else None)
        if not children:
            return
        ox, oy, ow, oh = origin
        layout = kind(parent) if parent is not None else None
        if layout in ("flex", "grid") and parent is not None:
            laid = [c for c in children if c.name not in free and c.visible]
            for c, r in zip(laid, arrange(form, parent, origin, laid)):
                out[c.name] = r
        for c in children:
            if c.name in out:
                continue
            if layout in ("flex", "grid"):
                x, y, w, h = c.rect
            else:
                x, y, w, h = anchored(c, design_size, (ow, oh))
            out[c.name] = (ox + x, oy + y, w, h)
        for c in children:
            if kind(c) is not None:
                place(c, out[c.name], (c.width, c.height))

    place(None, (0.0, 0.0, actual[0], actual[1]), design)
    return out


def origin(form: Form, rects: Dict[str, Rect], parent: Optional[str]) -> Tuple[float, float]:
    """The absolute point that a child's x and y of ``parent`` are relative to."""
    if not parent or parent not in rects:
        return (0.0, 0.0)
    return rects[parent][0], rects[parent][1]


def container_at(form: Form, rects: Dict[str, Rect], x: float, y: float,
                 exclude: Iterable[str] = ()) -> Optional[Control]:
    """The innermost visible container under ``(x, y)``, skipping ``exclude`` and what is inside them."""
    banned = set(exclude)
    for name in list(banned):
        banned.update(c.name for c in form.descendants(name))
    found: Optional[Control] = None
    for control, _depth in form.walk():
        if control.name in banned or not control.visible or kind(control) is None:
            continue
        if any(not a.visible for a in form.ancestors(control.name)):
            continue
        rect = rects.get(control.name)
        if rect and contains(rect, x, y):
            found = control  # later in walk order = drawn on top or deeper
    return found


def drop_index(form: Form, rects: Dict[str, Rect], container: Control, x: float, y: float,
               exclude: Iterable[str] = ()) -> int:
    """Where a control dropped at ``(x, y)`` goes among the children of a flex or grid container."""
    excluded = set(exclude)
    siblings = [c for c in form.children(container.name) if c.name not in excluded and c.name in rects]
    p = props(container)
    row = kind(container) == "grid" or p.get("direction", "row") != "column"
    for i, c in enumerate(siblings):
        sx, sy, sw, sh = rects[c.name]
        if kind(container) == "grid":
            if y < sy + sh and (y < sy or x < sx + sw / 2):
                return i
        elif (x < sx + sw / 2) if row else (y < sy + sh / 2):
            return i
    return len(siblings)


def visible(form: Form, control: Control) -> bool:
    """``True`` when the control and every container holding it are visible."""
    return control.visible and all(a.visible for a in form.ancestors(control.name))
