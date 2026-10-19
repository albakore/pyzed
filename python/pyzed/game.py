"""Small helpers for games: held keys, movement, collisions, pixel sprites, particles.

    import pyzed as pz
    from pyzed import draw, game

    class Ship(pz.App):
        def __init__(self):
            self.x = 200
            self.sparks = game.Particles()

        def subscriptions(self):
            return [pz.frames(self.tick)]       # tick(dt) on every displayed frame

        def tick(self, dt):
            self.x += game.axis(("left", "a"), ("right", "d")) * 300 * dt
            self.sparks.update(dt)

        def view(self):
            return pz.canvas([draw.background("#0b0e14"), *game.glow(self.x, 200, 18, "#74ade8"),
                              *self.sparks.shapes()], width=400, height=300)

``pz.frames(callback)`` calls ``callback(dt)`` once per frame with the seconds since the
previous one; ``pz.pressed()`` is the set of keys held down right now. Everything here
is plain Python built on ``pyzed.draw``, so it also works in screenshots and tests.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from . import _core, draw

__all__ = [
    "Particles", "Rect", "Shake", "axis", "circle_rect", "clamp", "glow", "is_pressed", "lerp",
    "pressed", "rgba", "sprite", "vector",
]

Keys = Union[str, Sequence[str]]


def pressed() -> FrozenSet[str]:
    """The keys held down right now, by name (``"left"``, ``"space"``, ``"a"``...).

    Empty when no app is running (and in screenshots). Modifiers are not included.
    """
    return frozenset(_core.pressed_keys())


def _names(keys: Keys) -> Tuple[str, ...]:
    return (keys,) if isinstance(keys, str) else tuple(keys)


def is_pressed(*keys: str, held: Optional[Iterable[str]] = None) -> bool:
    """Whether any of ``keys`` is held down (``held`` replaces ``pressed()``, for tests)."""
    down = pressed() if held is None else frozenset(held)
    return any(k in down for k in keys)


def axis(negative: Keys, positive: Keys, *, held: Optional[Iterable[str]] = None) -> int:
    """-1, 0 or 1 from two groups of keys: ``axis(("left", "a"), ("right", "d"))``."""
    down = pressed() if held is None else frozenset(held)
    return int(any(k in down for k in _names(positive))) - int(any(k in down for k in _names(negative)))


def vector(left: Keys = ("left", "a"), right: Keys = ("right", "d"), up: Keys = ("up", "w"),
           down: Keys = ("down", "s"), *, held: Optional[Iterable[str]] = None) -> Tuple[float, float]:
    """A direction of length 0 or 1 from four groups of keys (arrows and WASD by default).

    Diagonals are normalized, so moving diagonally is not faster.
    """
    keys = pressed() if held is None else frozenset(held)
    x = axis(left, right, held=keys)
    y = axis(up, down, held=keys)
    if x and y:
        return (x / math.sqrt(2), y / math.sqrt(2))
    return (float(x), float(y))


def clamp(value: float, low: float, high: float) -> float:
    """``value`` limited to ``[low, high]``."""
    return low if value < low else high if value > high else value


def lerp(a: float, b: float, t: float) -> float:
    """The value ``t`` of the way from ``a`` to ``b`` (``t`` from 0 to 1)."""
    return a + (b - a) * t


@dataclass
class Rect:
    """An axis-aligned box with collision helpers (``x``, ``y`` is the top-left corner)."""

    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def top(self) -> float:
        return self.y

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.w / 2, self.y + self.h / 2)

    def overlaps(self, other: "Rect") -> bool:
        """Whether the two boxes intersect (touching edges do not count)."""
        return (self.x < other.right and other.x < self.right
                and self.y < other.bottom and other.y < self.bottom)

    def contains(self, x: float, y: float) -> bool:
        """Whether the point is inside the box."""
        return self.x <= x < self.right and self.y <= y < self.bottom

    def moved(self, dx: float, dy: float) -> "Rect":
        """A copy moved by ``(dx, dy)``."""
        return Rect(self.x + dx, self.y + dy, self.w, self.h)

    def shape(self, **paint: Any) -> draw.Shape:
        """The box as a ``draw.rect`` (``fill``, ``stroke``, ``radius``...)."""
        return draw.rect(self.x, self.y, self.w, self.h, **paint)


def circle_rect(cx: float, cy: float, r: float, rect: Rect) -> Optional[Tuple[float, float]]:
    """Where a circle hits a box: the push-out direction ``(nx, ny)``, or ``None``.

    The direction points from the box to the circle along the side it hit, so a ball
    bounces with ``if nx: vx = abs(vx) * nx`` and ``if ny: vy = abs(vy) * ny``.
    """
    nearest_x = clamp(cx, rect.left, rect.right)
    nearest_y = clamp(cy, rect.top, rect.bottom)
    dx, dy = cx - nearest_x, cy - nearest_y
    if dx * dx + dy * dy > r * r:
        return None
    if dx == 0 and dy == 0:  # the center is inside: leave through the closest side
        sides = {(-1.0, 0.0): cx - rect.left, (1.0, 0.0): rect.right - cx,
                 (0.0, -1.0): cy - rect.top, (0.0, 1.0): rect.bottom - cy}
        return min(sides, key=sides.__getitem__)
    if abs(dx) * rect.h >= abs(dy) * rect.w:
        return (math.copysign(1.0, dx), 0.0)
    return (0.0, math.copysign(1.0, dy))


def rgba(color: Any, alpha: float = 1.0) -> Tuple[float, float, float, float]:
    """``color`` (``"#rrggbb[aa]"`` or a tuple) as an ``(r, g, b, a)`` tuple with ``alpha`` applied."""
    if isinstance(color, str):
        value = color.lstrip("#")
        if len(value) in (3, 4):
            value = "".join(c * 2 for c in value)
        parts = [int(value[i:i + 2], 16) / 255 for i in range(0, len(value), 2)]
    else:
        parts = [float(p) for p in color]
        if any(p > 1 for p in parts[:3]):
            parts = [p / 255 for p in parts[:3]] + parts[3:]
    r, g, b = parts[:3]
    a = parts[3] if len(parts) > 3 else 1.0
    return (r, g, b, max(0.0, min(1.0, a * alpha)))


def glow(x: float, y: float, radius: float, color: Any, *, layers: int = 4, strength: float = 0.5,
         core: bool = True) -> List[draw.Shape]:
    """A soft light: translucent circles growing around ``(x, y)`` (bloom on a canvas).

    ``strength`` is the opacity of the innermost halo; ``core=False`` leaves out the solid
    circle in the middle.
    """
    shapes = []
    for i in range(layers, 0, -1):
        alpha = strength * (1 - (i - 1) / layers) ** 2 / 2
        shapes.append(draw.circle(x, y, radius * (1 + i * 0.6), fill=rgba(color, alpha)))
    if core:
        shapes.append(draw.circle(x, y, radius, fill=color))
    return shapes


def sprite(rows: Sequence[str], palette: Mapping[str, Any], x: float = 0.0, y: float = 0.0, *,
           scale: float = 1.0, flip: bool = False) -> List[draw.Shape]:
    """Pixel art from text: each character of ``rows`` is a pixel colored by ``palette``.

    Characters missing from the palette (``.`` or a space) are transparent. One shape is
    made per color, so a sprite costs a handful of shapes whatever its size::

        INVADER = ["..#.....#..",
                   "...#...#...",
                   "..#######..",
                   ".##.###.##."]
        game.sprite(INVADER, {"#": "#a3be8c"}, x, y, scale=4)
    """
    cells: Dict[str, List[Tuple[float, float, float, float]]] = {}
    for row_index, row in enumerate(rows):
        width = len(row)
        for col, char in enumerate(row):
            if char in palette:
                cx = (width - 1 - col) if flip else col
                cells.setdefault(char, []).append((x + cx * scale, y + row_index * scale, scale, scale))
    return [draw.rects(items, fill=palette[char]) for char, items in cells.items()]


@dataclass
class _Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    age: float
    size: float
    color: Any


class Particles:
    """Sparks, smoke, explosions: short-lived dots that move, fall and fade out.

    Call ``burst`` when something happens, ``update(dt)`` every frame and draw
    ``shapes()`` on a canvas. ``limit`` caps how many are alive at once.
    """

    def __init__(self, *, gravity: float = 0.0, drag: float = 0.0, limit: int = 2000,
                 seed: Optional[int] = None) -> None:
        self.gravity = gravity
        self.drag = drag
        self.limit = limit
        self.items: List[_Particle] = []
        self._random = random.Random(seed)

    def __len__(self) -> int:
        return len(self.items)

    def burst(self, x: float, y: float, *, count: int = 16, color: Any = "#ffd166",
              speed: Tuple[float, float] = (60, 220), life: Tuple[float, float] = (0.3, 0.9),
              size: Tuple[float, float] = (1.5, 3.5), angle: float = 0.0, spread: float = 360.0) -> None:
        """Adds ``count`` particles flying out of ``(x, y)``.

        ``angle`` and ``spread`` (degrees) aim them: ``angle=-90, spread=40`` is a fountain.
        ``color`` may be a list to pick from.
        """
        rnd = self._random
        colors = color if isinstance(color, list) else [color]
        for _ in range(count):
            a = math.radians(angle + rnd.uniform(-spread / 2, spread / 2))
            v = rnd.uniform(*speed)
            self.items.append(_Particle(x, y, math.cos(a) * v, math.sin(a) * v, rnd.uniform(*life), 0.0,
                                        rnd.uniform(*size), rnd.choice(colors)))
        if len(self.items) > self.limit:
            del self.items[: len(self.items) - self.limit]

    def update(self, dt: float) -> None:
        """Moves every particle ``dt`` seconds forward and removes the dead ones."""
        keep = []
        damping = max(0.0, 1 - self.drag * dt)
        for p in self.items:
            p.age += dt
            if p.age >= p.life:
                continue
            p.vy += self.gravity * dt
            p.vx *= damping
            p.vy *= damping
            p.x += p.vx * dt
            p.y += p.vy * dt
            keep.append(p)
        self.items = keep

    def shapes(self, *, glow: bool = False) -> List[draw.Shape]:
        """The particles as fading circles (``glow=True`` adds a halo to each one)."""
        out = []
        for p in self.items:
            fade = 1 - p.age / p.life
            if glow:
                out.append(draw.circle(p.x, p.y, p.size * 2.6, fill=rgba(p.color, 0.18 * fade)))
            out.append(draw.circle(p.x, p.y, p.size * (0.4 + 0.6 * fade), fill=rgba(p.color, fade)))
        return out

    def clear(self) -> None:
        self.items.clear()


class Shake:
    """Screen shake: ``kick(8)`` on a hit, ``update(dt)`` every frame, and start the
    canvas shapes with ``*shake.shapes()`` (a translate) so everything moves together."""

    def __init__(self, *, decay: float = 6.0, seed: Optional[int] = None) -> None:
        self.decay = decay
        self.amount = 0.0
        self._random = random.Random(seed)

    def kick(self, amount: float) -> None:
        """Shakes by up to ``amount`` pixels (the strongest kick wins)."""
        self.amount = max(self.amount, amount)

    def update(self, dt: float) -> None:
        self.amount = max(0.0, self.amount - self.amount * self.decay * dt - 2 * dt)

    def offset(self) -> Tuple[float, float]:
        """The displacement for this frame."""
        if self.amount <= 0:
            return (0.0, 0.0)
        a = self.amount
        return (self._random.uniform(-a, a), self._random.uniform(-a, a))

    def shapes(self) -> List[draw.Shape]:
        """``[draw.translate(...)]`` for this frame, or nothing when still."""
        dx, dy = self.offset()
        return [draw.translate(dx, dy)] if dx or dy else []
