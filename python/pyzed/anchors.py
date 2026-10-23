"""Anchors: where a box goes when its parent is resized, like Unity's, Unreal's and Godot's.

A box is anchored by the edges of its parent it follows. On each axis it can follow the start
edge (``left``/``top``: it keeps its distance to it), the end edge (``right``/``bottom``), both
(it stretches) or neither (it stays centered: it keeps its distance to the middle). That makes
the 16 presets of the anchor picker, named after where the box sits::

    PRESETS["top_right"]      # ("top", "right")
    PRESETS["bottom_wide"]    # ("left", "right", "bottom"): stretches across the bottom
    PRESETS["full"]           # ("left", "top", "right", "bottom"): fills the parent

``place`` moves a box from its design size to the parent's current size, with size limits and a
pivot (the point of the box that stays put when a limit stops it from stretching, and that
rotation and scale turn around)::

    place((20, 20, 100, 30), PRESETS["top_right"], design=(400, 300), actual=(600, 300))
    # (220, 20, 100, 30)

``pz.anchor_layout`` uses it to place widgets in a running app.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Sequence, Tuple

Rect = Tuple[float, float, float, float]

#: Edges a box can be anchored to. Anchoring to opposite edges stretches it.
EDGES = ("left", "top", "right", "bottom")
#: Where a box sits on each axis, in the order of the picker's columns and rows.
HORIZONTAL = ("left", "center", "right", "wide")
VERTICAL = ("top", "center", "bottom", "tall")
MIN_SIZE = 8.0

_H_EDGES = {"left": ("left",), "center": (), "right": ("right",), "wide": ("left", "right")}
_V_EDGES = {"top": ("top",), "center": (), "bottom": ("bottom",), "tall": ("top", "bottom")}


def _preset_name(h: str, v: str) -> str:
    if h == "wide" and v == "tall":
        return "full"
    if v == "tall":
        return f"{h}_tall"
    if h == "wide":
        return f"{v}_wide"
    if h == "center" and v == "center":
        return "center"
    return f"{v}_{h}"


def _sorted(edges: Iterable[str]) -> Tuple[str, ...]:
    chosen = set(edges)
    return tuple(e for e in EDGES if e in chosen)


#: The 16 anchor presets, by name: ``top_left``, ``top_center``, ``top_right``, ``top_wide``,
#: ``center_left``, ``center``, ``center_right``, ``center_wide``, ``bottom_left``... ``bottom_wide``,
#: ``left_tall``, ``center_tall``, ``right_tall`` and ``full``.
PRESETS: Dict[str, Tuple[str, ...]] = {
    _preset_name(h, v): _sorted(_H_EDGES[h] + _V_EDGES[v]) for v in VERTICAL for h in HORIZONTAL
}


def axes(edges: Iterable[str]) -> Tuple[str, str]:
    """``(horizontal, vertical)`` placement of an anchor: ``("right", "top")``, ``("wide", "center")``..."""
    a = set(edges)
    h = "wide" if {"left", "right"} <= a else "left" if "left" in a else "right" if "right" in a else "center"
    v = "tall" if {"top", "bottom"} <= a else "top" if "top" in a else "bottom" if "bottom" in a else "center"
    return h, v


def preset(horizontal: str, vertical: str) -> str:
    """The name of the preset placed ``horizontal`` (``left``, ``center``, ``right``, ``wide``) and ``vertical``
    (``top``, ``center``, ``bottom``, ``tall``): ``preset("right", "top")`` is ``"top_right"``."""
    if horizontal not in HORIZONTAL or vertical not in VERTICAL:
        raise ValueError(f"placements are {HORIZONTAL} and {VERTICAL}")
    return _preset_name(horizontal, vertical)


def preset_of(edges: Iterable[str]) -> str:
    """The name of the preset an anchor matches (every set of edges is one of the 16)."""
    return _preset_name(*axes(edges))


def edges(anchor: Any) -> Tuple[str, ...]:
    """The edges of ``anchor``: a preset name (``"top_right"``), words (``"top right"``) or edges."""
    if isinstance(anchor, str):
        key = anchor.strip().lower().replace("-", "_").replace(" ", "_")
        if key in PRESETS:
            return PRESETS[key]
        words = key.split("_")
        if all(w in EDGES for w in words):
            return _sorted(words)
        raise ValueError(f"unknown anchor {anchor!r}; use a preset ({', '.join(PRESETS)}) or edges")
    found = tuple(anchor or ())
    bad = [e for e in found if e not in EDGES]
    if bad:
        raise ValueError(f"unknown anchor edges {bad!r}; edges are {', '.join(EDGES)}")
    return _sorted(found)


def _limit(size: float, low: float, high: float) -> float:
    if high > 0:
        size = min(size, high)
    return max(size, low)


def _axis(pos: float, size: float, mode: str, delta: float, low: float, high: float,
          pivot: float) -> Tuple[float, float]:
    if mode == "wide":
        stretched = max(size + delta, MIN_SIZE)
        size = _limit(stretched, low, high)
        return pos + (stretched - size) * pivot, size
    limited = _limit(size, low, high)
    pos += (size - limited) * pivot
    if mode == "end":
        pos += delta
    elif mode == "center":
        pos += delta / 2
    return pos, limited


def place(rect: Sequence[float], anchor: Any, design: Sequence[float], actual: Sequence[float], *,
          min_size: Sequence[float] = (0, 0), max_size: Sequence[float] = (0, 0),
          pivot: Sequence[float] = (0.5, 0.5)) -> Rect:
    """Where box ``rect`` (``x, y, width, height``, designed in a parent of size ``design``) goes in a parent
    of size ``actual``.

    An edge the box is anchored to keeps its distance to that side; anchored to both sides it stretches;
    anchored to neither it keeps its distance to the middle. ``min_size`` and ``max_size`` limit the size
    (``0`` means no limit); when a limit stops a box from stretching, ``pivot`` (``0`` to ``1`` on each axis)
    is the point that stays where the stretched box would have it.
    """
    h, v = axes(edges(anchor))
    x, y, w, ht = (float(n) for n in rect)
    dw, dh = float(actual[0]) - float(design[0]), float(actual[1]) - float(design[1])
    hm = {"left": "start", "right": "end", "center": "center", "wide": "wide"}[h]
    vm = {"top": "start", "bottom": "end", "center": "center", "tall": "wide"}[v]
    x, w = _axis(x, w, hm, dw, float(min_size[0] or 0), float(max_size[0] or 0), float(pivot[0]))
    y, ht = _axis(y, ht, vm, dh, float(min_size[1] or 0), float(max_size[1] or 0), float(pivot[1]))
    return (x, y, w, ht)


def snap_to(anchor: Any, rect: Sequence[float], parent: Sequence[float], margin: float = 0.0) -> Rect:
    """``rect`` moved (and, on stretched axes, sized) to sit where ``anchor`` points: against the anchored
    edge ``margin`` pixels in, centered, or filling the parent minus ``margin`` on both sides."""
    h, v = axes(edges(anchor))
    x, y, w, ht = (float(n) for n in rect)
    pw, ph = float(parent[0]), float(parent[1])
    if h == "left":
        x = margin
    elif h == "right":
        x = pw - w - margin
    elif h == "center":
        x = (pw - w) / 2
    else:
        x, w = margin, max(pw - 2 * margin, MIN_SIZE)
    if v == "top":
        y = margin
    elif v == "bottom":
        y = ph - ht - margin
    elif v == "center":
        y = (ph - ht) / 2
    else:
        y, ht = margin, max(ph - 2 * margin, MIN_SIZE)
    return (x, y, w, ht)


def offsets(rect: Sequence[float], parent: Sequence[float]) -> Tuple[float, float, float, float]:
    """The distances ``(left, top, right, bottom)`` from each side of the parent to the box."""
    x, y, w, h = (float(n) for n in rect)
    return (x, y, float(parent[0]) - x - w, float(parent[1]) - y - h)


def pivot_offset(size: Sequence[float], pivot: Sequence[float], rotate: float = 0.0,
                 scale: float = 1.0) -> Tuple[float, float]:
    """The translation that makes a rotation (degrees clockwise) and a scale, which turn around the box's
    center, turn around ``pivot`` instead (``(0, 0)`` is the top-left corner, ``(1, 1)`` the bottom-right)."""
    dx = (float(pivot[0]) - 0.5) * float(size[0])
    dy = (float(pivot[1]) - 0.5) * float(size[1])
    if not dx and not dy:
        return (0.0, 0.0)
    angle = math.radians(float(rotate or 0.0))
    s = float(1.0 if scale is None else scale)
    rx = (dx * math.cos(angle) - dy * math.sin(angle)) * s
    ry = (dx * math.sin(angle) + dy * math.cos(angle)) * s
    return (round(dx - rx, 4), round(dy - ry, 4))

