"""Pure geometry for the designer: snapping, alignment, distribution, resizing and anchors.

Everything here works on ``Control`` objects (or plain ``(x, y, w, h)`` tuples) and
has no UI dependency, so the same rules apply in the designer, in scripts and in tests.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .model import Control

Rect = Tuple[float, float, float, float]

MIN_SIZE = 8.0

#: Resize handles, named by compass direction, and which edges each one moves.
HANDLES: Dict[str, Tuple[bool, bool, bool, bool]] = {
    #      left   top    right  bottom
    "nw": (True, True, False, False),
    "n": (False, True, False, False),
    "ne": (False, True, True, False),
    "e": (False, False, True, False),
    "se": (False, False, True, True),
    "s": (False, False, False, True),
    "sw": (True, False, False, True),
    "w": (True, False, False, False),
}

ALIGNMENTS = ("left", "center", "right", "top", "middle", "bottom")


def snap(value: float, grid: float, enabled: bool = True) -> float:
    """Rounds ``value`` to the nearest multiple of ``grid`` (unchanged if disabled)."""
    if not enabled or grid <= 1:
        return round(value)
    return round(value / grid) * grid


def normalize(x1: float, y1: float, x2: float, y2: float) -> Rect:
    """The rectangle between two corners, whatever order they come in."""
    return (min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))


def contains(rect: Rect, x: float, y: float) -> bool:
    """Whether the point ``(x, y)`` is inside ``rect`` (edges included)."""
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


def intersects(a: Rect, b: Rect) -> bool:
    """Whether rectangles ``a`` and ``b`` overlap (touching edges do not count)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def bounds(controls: Iterable[Control]) -> Optional[Rect]:
    """The smallest rectangle containing every control (``None`` if there are none)."""
    rects = [c.rect for c in controls]
    if not rects:
        return None
    x1 = min(r[0] for r in rects)
    y1 = min(r[1] for r in rects)
    x2 = max(r[0] + r[2] for r in rects)
    y2 = max(r[1] + r[3] for r in rects)
    return (x1, y1, x2 - x1, y2 - y1)


def hit(controls: Sequence[Control], x: float, y: float) -> Optional[Control]:
    """The top-most visible control under ``(x, y)``."""
    for control in reversed(controls):
        if control.visible and contains(control.rect, x, y):
            return control
    return None


def in_rect(controls: Iterable[Control], rect: Rect) -> List[Control]:
    """The controls touched by a rubber-band selection."""
    return [c for c in controls if intersects(c.rect, rect)]


def move(controls: Iterable[Control], dx: float, dy: float, *, limit: Optional[Tuple[float, float]] = None) -> None:
    """Moves controls by ``(dx, dy)``, keeping the group inside ``limit`` (form size) if given."""
    controls = [c for c in controls if not c.locked]
    box = bounds(controls)
    if box is None:
        return
    if limit is not None:
        dx = max(-box[0], min(dx, limit[0] - box[0] - box[2]))
        dy = max(-box[1], min(dy, limit[1] - box[1] - box[3]))
    for c in controls:
        c.x += dx
        c.y += dy


def resize(start: Rect, handle: str, dx: float, dy: float, *, grid: float = 1, snapping: bool = False) -> Rect:
    """The rectangle after dragging ``handle`` of ``start`` by ``(dx, dy)``.

    The moved edges snap to the grid; the opposite edges stay put. The result is never
    smaller than ``MIN_SIZE`` in either direction.
    """
    left, top, right, bottom = HANDLES[handle]
    x, y, w, h = start
    x1, y1, x2, y2 = x, y, x + w, y + h
    if left:
        x1 = min(snap(x1 + dx, grid, snapping), x2 - MIN_SIZE)
    if right:
        x2 = max(snap(x2 + dx, grid, snapping), x1 + MIN_SIZE)
    if top:
        y1 = min(snap(y1 + dy, grid, snapping), y2 - MIN_SIZE)
    if bottom:
        y2 = max(snap(y2 + dy, grid, snapping), y1 + MIN_SIZE)
    return (x1, y1, x2 - x1, y2 - y1)


def align(controls: Sequence[Control], edge: str, *, to: Optional[Rect] = None) -> None:
    """Lines controls up on ``edge`` (left, center, right, top, middle, bottom).

    With ``to`` (e.g. the form rectangle) they align to it; otherwise to the bounds of the
    selection, or to the form when a single control is given via ``to``.
    """
    if edge not in ALIGNMENTS:
        raise ValueError(f"unknown alignment {edge!r}; use one of {ALIGNMENTS}")
    controls = [c for c in controls if not c.locked]
    box = to or bounds(controls)
    if box is None:
        return
    bx, by, bw, bh = box
    for c in controls:
        if edge == "left":
            c.x = bx
        elif edge == "right":
            c.x = bx + bw - c.width
        elif edge == "center":
            c.x = round(bx + (bw - c.width) / 2)
        elif edge == "top":
            c.y = by
        elif edge == "bottom":
            c.y = by + bh - c.height
        elif edge == "middle":
            c.y = round(by + (bh - c.height) / 2)


def distribute(controls: Sequence[Control], axis: str) -> None:
    """Spaces three or more controls evenly along ``"horizontal"`` or ``"vertical"``."""
    controls = [c for c in controls if not c.locked]
    if len(controls) < 3:
        return
    horizontal = axis == "horizontal"
    ordered = sorted(controls, key=lambda c: c.x if horizontal else c.y)
    first, last = ordered[0], ordered[-1]
    if horizontal:
        span = last.x + last.width - first.x
        gap = (span - sum(c.width for c in ordered)) / (len(ordered) - 1)
        pos = first.x
        for c in ordered:
            c.x = round(pos)
            pos += c.width + gap
    else:
        span = last.y + last.height - first.y
        gap = (span - sum(c.height for c in ordered)) / (len(ordered) - 1)
        pos = first.y
        for c in ordered:
            c.y = round(pos)
            pos += c.height + gap


def same_size(controls: Sequence[Control], which: str = "both", *, reference: Optional[Control] = None) -> None:
    """Gives every control the ``"width"``, ``"height"`` or ``"both"`` of ``reference`` (the first one)."""
    controls = [c for c in controls if not c.locked]
    if not controls:
        return
    ref = reference or controls[0]
    for c in controls:
        if which in ("width", "both"):
            c.width = ref.width
        if which in ("height", "both"):
            c.height = ref.height


def snap_controls(controls: Iterable[Control], grid: float) -> None:
    """Moves and resizes controls onto the grid."""
    for c in controls:
        if c.locked:
            continue
        c.x, c.y = snap(c.x, grid), snap(c.y, grid)
        c.width = max(snap(c.width, grid), MIN_SIZE)
        c.height = max(snap(c.height, grid), MIN_SIZE)


def anchored(control: Control, design: Tuple[float, float], actual: Tuple[float, float]) -> Rect:
    """Where a control goes when its form is resized from ``design`` to ``actual`` size.

    Like WinForms anchors: an edge anchored to the form keeps its distance to that
    side; anchored to both sides it stretches; anchored to neither it keeps its
    relative position (centered controls stay centered). The control's minimum and
    maximum size and its pivot (``Control.layout``) apply too; see ``pyzed.anchors.place``.
    """
    from .. import anchors

    return anchors.place(control.rect, control.anchor, design, actual, min_size=control.min_size,
                         max_size=control.max_size, pivot=control.pivot)


Line = Tuple[float, float, float, float]


def smart_guides(rect: Rect, others: Iterable[Rect], size: Tuple[float, float],
                 threshold: float = 4.0) -> Tuple[float, float, List[Line]]:
    """Snaps a moving rectangle to the edges and centers of ``others`` and of the form.

    Returns ``(dx, dy, lines)``: the correction to apply and the guide lines to draw
    (as thin ``(x1, y1, x2, y2)`` boxes), like the alignment guides of Figma or Qt Designer.
    """
    x, y, w, h = rect
    others = list(others)
    targets_x = [(0.0, None), (size[0] / 2, None), (size[0], None)]
    targets_y = [(0.0, None), (size[1] / 2, None), (size[1], None)]
    for o in others:
        ox, oy, ow, oh = o
        targets_x += [(ox, o), (ox + ow / 2, o), (ox + ow, o)]
        targets_y += [(oy, o), (oy + oh / 2, o), (oy + oh, o)]

    def best(points, targets):
        found = None
        for p in points:
            for t, owner in targets:
                d = t - p
                if abs(d) <= threshold and (found is None or abs(d) < abs(found[0])):
                    found = (d, t, owner)
        return found

    lines: List[Line] = []
    dx = dy = 0.0
    bx = best((x, x + w / 2, x + w), targets_x)
    if bx:
        dx, gx, owner = bx
        top, bottom = (0.0, size[1]) if owner is None else (min(y, owner[1]), max(y + h, owner[1] + owner[3]))
        lines.append((gx, top, gx + 1, bottom))
    by = best((y, y + h / 2, y + h), targets_y)
    if by:
        dy, gy, owner = by
        left, right = (0.0, size[0]) if owner is None else (min(x, owner[0]), max(x + w, owner[0] + owner[2]))
        lines.append((left, gy, right, gy + 1))
    return dx, dy, lines
