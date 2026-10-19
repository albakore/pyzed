"""Shapes for ``pz.canvas``: plain dicts, so they are cheap to build every frame.

    import pyzed as pz
    from pyzed import draw

    pz.canvas([
        draw.background("#1e2127"),
        draw.circle(100, 100, 40, fill="#74ade8"),
        draw.line(0, 0, 200, 200, stroke="#d07277", width=2, dash=[6, 4]),
        draw.text(100, 180, "Hello", color="#dce0e5", align_x="center"),
    ], width=200, height=200)

Angles are in degrees; ``y`` grows downwards. Colors accept anything ``pz.text`` does.
Transforms (``translate``, ``rotate``, ``scale``) apply to the shapes after them; wrap
them in ``save()`` / ``restore()`` (or use ``group``) to scope them.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

Shape = Dict[str, Any]
Point = Tuple[float, float]


def _paint(fill, stroke, width, dash=None, cap=None) -> Shape:
    out: Shape = {}
    if fill is not None:
        out["fill"] = fill
    if stroke is not None:
        out["stroke"] = stroke
    if width != 1.0:
        out["width"] = width
    if dash:
        out["dash"] = list(dash)
    if cap:
        out["cap"] = cap
    return out


def background(color: Any) -> Shape:
    """Fills the whole canvas."""
    return {"type": "background", "color": color}


def rect(x: float, y: float, w: float, h: float, *, fill: Any = None, stroke: Any = None, width: float = 1.0,
         radius: float = 0.0, dash: Optional[Sequence[float]] = None) -> Shape:
    """A rectangle (rounded with ``radius``), filled and/or stroked."""
    return {"type": "rect", "x": x, "y": y, "w": w, "h": h, "radius": radius, **_paint(fill, stroke, width, dash)}


def rects(items: Iterable[Tuple[float, float, float, float]], *, fill: Any) -> Shape:
    """Many filled rectangles of one color in a single shape (fast for grids and bars)."""
    return {"type": "rects", "rects": [tuple(r) for r in items], "fill": fill}


def circle(x: float, y: float, r: float, *, fill: Any = None, stroke: Any = None, width: float = 1.0,
           dash: Optional[Sequence[float]] = None) -> Shape:
    """A circle centered at ``(x, y)``."""
    return {"type": "circle", "x": x, "y": y, "r": r, **_paint(fill, stroke, width, dash)}


def line(x1: float, y1: float, x2: float, y2: float, *, stroke: Any = "#ffffff", width: float = 1.0,
         dash: Optional[Sequence[float]] = None, cap: Optional[str] = None) -> Shape:
    """A straight line. ``cap="round"`` rounds its ends."""
    return {"type": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, **_paint(None, stroke, width, dash, cap)}


def path(ops: Iterable[tuple], *, fill: Any = None, stroke: Any = None, width: float = 1.0,
         dash: Optional[Sequence[float]] = None, cap: Optional[str] = None) -> Shape:
    """A free-form path from SVG-like operations::

        ("M", x, y)                      move to
        ("L", x, y)                      line to
        ("Q", cx, cy, x, y)              quadratic curve
        ("C", c1x, c1y, c2x, c2y, x, y)  cubic curve
        ("A", cx, cy, r, start, end)     circular arc (degrees)
        ("Z",)                           close
    """
    return {"type": "path", "ops": [tuple(op) for op in ops], **_paint(fill, stroke, width, dash, cap)}


def polyline(points: Iterable[Point], *, stroke: Any = "#ffffff", width: float = 1.0, closed: bool = False,
             fill: Any = None, dash: Optional[Sequence[float]] = None, cap: Optional[str] = "round") -> Shape:
    """Connects ``points`` with straight lines (``closed=True`` makes a polygon)."""
    pts = list(points)
    ops: List[tuple] = []
    for i, (x, y) in enumerate(pts):
        ops.append(("M" if i == 0 else "L", x, y))
    if closed and pts:
        ops.append(("Z",))
    return path(ops, fill=fill, stroke=stroke, width=width, dash=dash, cap=cap)


def polygon(points: Iterable[Point], *, fill: Any = None, stroke: Any = None, width: float = 1.0) -> Shape:
    """A closed shape through ``points``."""
    return polyline(points, stroke=stroke, width=width, closed=True, fill=fill, cap=None)


def arc(x: float, y: float, r: float, start: float, end: float, *, stroke: Any = None, fill: Any = None,
        width: float = 1.0, pie: bool = False, cap: Optional[str] = None) -> Shape:
    """An arc of a circle from ``start`` to ``end`` degrees (0 = 3 o'clock, clockwise).

    ``pie=True`` closes it through the center (a pie slice, good for donut/pie charts).
    """
    ops: List[tuple] = []
    if pie:
        ops.append(("M", x, y))
        ops.append(("L", x + r * math.cos(math.radians(start)), y + r * math.sin(math.radians(start))))
    else:
        ops.append(("M", x + r * math.cos(math.radians(start)), y + r * math.sin(math.radians(start))))
    ops.append(("A", x, y, r, start, end))
    if pie:
        ops.append(("Z",))
    return path(ops, fill=fill, stroke=stroke, width=width, cap=cap)


def text(x: float, y: float, content: Any, *, color: Any = "#ffffff", size: float = 14, font: str = "sans",
         weight: Optional[str] = None, align_x: str = "start", align_y: str = "top") -> Shape:
    """Text anchored at ``(x, y)``; ``align_x``/``align_y`` choose which side of it sits there."""
    shape: Shape = {"type": "text", "x": x, "y": y, "content": str(content), "color": color, "size": size,
                    "font": font, "align_x": align_x, "align_y": align_y}
    if weight:
        shape["weight"] = weight
    return shape


def image(source: Any, x: float, y: float, w: float, h: float, *, rotation: float = 0.0,
          opacity: float = 1.0, pixelated: bool = False, size: Optional[Tuple[int, int]] = None) -> Shape:
    """A bitmap (a sprite) drawn in the box ``(x, y, w, h)``.

    ``source`` is a path, the bytes of a PNG/JPEG... or raw RGBA bytes with ``size=(w, h)``,
    like ``pz.image``. It is decoded once and cached, so drawing it every frame is cheap.
    ``rotation`` (degrees) turns it around its center; ``pixelated=True`` keeps pixel art
    sharp when scaled up.
    """
    shape: Shape = {"type": "image", "source": source, "x": x, "y": y, "w": w, "h": h}
    if rotation:
        shape["rotation"] = rotation
    if opacity != 1.0:
        shape["opacity"] = opacity
    if pixelated:
        shape["pixelated"] = True
    if size is not None:
        shape["size"] = tuple(size)
    return shape


def save() -> Shape:
    """Remembers the current transform (pair it with ``restore``)."""
    return {"type": "save"}


def restore() -> Shape:
    """Goes back to the transform remembered by the last ``save``."""
    return {"type": "restore"}


def translate(x: float, y: float) -> Shape:
    """Moves the origin of the following shapes by ``(x, y)``."""
    return {"type": "translate", "x": x, "y": y}


def rotate(degrees: float) -> Shape:
    """Rotates the following shapes around the current origin."""
    return {"type": "rotate", "degrees": degrees}


def scale(x: float, y: Optional[float] = None) -> Shape:
    """Scales the following shapes by ``x`` horizontally and ``y`` vertically (``y`` defaults to ``x``)."""
    return {"type": "scale", "x": x, "y": x if y is None else y}


def group(shapes: Iterable[Shape], *, x: float = 0.0, y: float = 0.0, rotation: float = 0.0,
          scale_by: Optional[float] = None) -> List[Shape]:
    """Draws ``shapes`` moved to ``(x, y)``, rotated and scaled, without affecting later shapes."""
    out: List[Shape] = [save()]
    if x or y:
        out.append(translate(x, y))
    if rotation:
        out.append(rotate(rotation))
    if scale_by is not None:
        out.append(scale(scale_by))
    out.extend(shapes)
    out.append(restore())
    return out
