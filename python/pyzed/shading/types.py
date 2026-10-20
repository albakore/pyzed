"""The data types that flow through a shader graph, and how one becomes another.

Every port and variable has one of ``TYPES``. Connecting two ports of different types
converts the value the way Godot's visual shaders do: a number fills every component of
a vector, a ``vec3`` gains an alpha of 1 to become a ``vec4``, a ``vec4`` keeps its first
three components to become a ``vec3``, and so on. ``texture`` only connects to
``texture``.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Sequence, Tuple

#: Every type a port or a variable can have.
TYPES = ("float", "int", "bool", "vec2", "vec3", "vec4", "texture")

#: The WGSL spelling of each type.
WGSL = {
    "float": "f32",
    "int": "i32",
    "bool": "bool",
    "vec2": "vec2<f32>",
    "vec3": "vec3<f32>",
    "vec4": "vec4<f32>",
}

#: How many numbers a value of each type holds.
SIZE = {"float": 1, "int": 1, "bool": 1, "vec2": 2, "vec3": 3, "vec4": 4}

#: The order types widen in, when a node takes inputs of several types (``float + vec3`` is a ``vec3``).
RANK = {"bool": 0, "int": 1, "float": 2, "vec2": 3, "vec3": 4, "vec4": 5}

#: The color of each type's ports and wires, as in Godot.
COLORS = {
    "float": "#a1a1aa",
    "int": "#5eead4",
    "bool": "#f472b6",
    "vec2": "#a78bfa",
    "vec3": "#c084fc",
    "vec4": "#f0abfc",
    "texture": "#fbbf24",
}

#: A short name for each type, shown next to ports.
LABELS = {"float": "float", "int": "int", "bool": "bool", "vec2": "vec2", "vec3": "vec3", "vec4": "vec4",
          "texture": "tex"}

#: The vector type with ``n`` components (``1`` is ``float``).
BY_SIZE = {1: "float", 2: "vec2", 3: "vec3", 4: "vec4"}

#: Generic port types: ``T`` takes the widest type among the inputs marked ``T``.
GENERIC = "T"


def is_vector(type_: str) -> bool:
    """Whether ``type_`` is ``vec2``, ``vec3`` or ``vec4``."""
    return type_ in ("vec2", "vec3", "vec4")


def widest(types: Sequence[str], at_least: str = "bool") -> str:
    """The type every one of ``types`` converts to without losing components (``float`` when empty)."""
    out = at_least
    for t in types:
        if t in RANK and RANK[t] > RANK[out]:
            out = t
    return out


def convert(expr: str, from_: str, to: str) -> str:
    """The WGSL expression that turns ``expr`` (of type ``from_``) into a value of type ``to``.

    Raises ``TypeError`` for conversions that make no sense (a texture into a number).
    """
    if from_ == to:
        return expr
    if "texture" in (from_, to):
        raise TypeError(f"a {from_} can't connect to a {to}")
    if from_ == "bool":
        expr, from_ = f"select(0.0, 1.0, {expr})", "float"
        if to == "float":
            return expr
    if to == "bool":
        if is_vector(from_):
            return f"any({expr} != {WGSL[from_]}(0.0))"
        zero = "0" if from_ == "int" else "0.0"
        return f"({expr} != {zero})"
    if from_ == "int":
        if to == "float":
            return f"f32({expr})"
        expr, from_ = f"f32({expr})", "float"
    if to == "int":
        if is_vector(from_):
            return f"i32(({expr}).x)"
        return f"i32({expr})"
    if from_ == "float":
        return expr if to == "float" else f"{WGSL[to]}({expr})"
    n_from, n_to = SIZE[from_], SIZE[to]
    if to == "float":
        return f"({expr}).x"
    if n_to < n_from:
        return f"({expr}).{'xyzw'[:n_to]}"
    # widening: vec2 -> vec3 adds z = 0; anything -> vec4 ends with alpha 1
    if to == "vec4":
        pad = ", 0.0, 1.0" if from_ == "vec2" else ", 1.0"
    else:
        pad = ", 0.0"
    return f"{WGSL[to]}({expr}{pad})"


def can_connect(from_: str, to: str) -> bool:
    """Whether an output of type ``from_`` can feed an input of type ``to`` (``T`` takes anything but a texture)."""
    if to == GENERIC:
        return from_ != "texture"
    if from_ == GENERIC:
        return to != "texture"
    return (from_ == "texture") == (to == "texture")


def _number(v: float) -> str:
    v = float(v)
    if math.isnan(v) or math.isinf(v):
        v = 0.0
    text = repr(v)
    if "e" in text or "E" in text:
        text = f"{v:.9f}".rstrip("0")
        if text.endswith("."):
            text += "0"
    return f"({text})" if v < 0 else text


def literal(value: Any, type_: str) -> str:
    """``value`` as a WGSL literal of ``type_`` (a number, a sequence of numbers or a color)."""
    if type_ == "bool":
        return "true" if bool(value) else "false"
    if type_ == "int":
        return f"i32({int(_scalar(value))})"
    if type_ == "float":
        return _number(_scalar(value))
    if type_ in SIZE:
        parts = components(value, SIZE[type_])
        return f"{WGSL[type_]}({', '.join(_number(p) for p in parts)})"
    raise TypeError(f"a {type_} has no literal")


def _scalar(value: Any) -> float:
    if isinstance(value, (list, tuple)):
        return float(value[0]) if value else 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def components(value: Any, n: int) -> Tuple[float, ...]:
    """``value`` as ``n`` numbers: a number repeats, a shorter tuple is padded (alpha 1), a color is RGBA."""
    if isinstance(value, str):
        value = parse_color(value)
    if isinstance(value, (int, float, bool)):
        return tuple(float(value) for _ in range(n))
    parts = [float(v) for v in list(value or ())[:n]]
    while len(parts) < n:
        parts.append(1.0 if len(parts) == 3 else 0.0)
    return tuple(parts)


def parse_color(text: str) -> Tuple[float, float, float, float]:
    """``"#rrggbb"``, ``"#rrggbbaa"``, ``"#rgb"`` as RGBA numbers from 0 to 1 (black when it doesn't parse)."""
    s = text.strip().lstrip("#")
    if len(s) in (3, 4):
        s = "".join(c * 2 for c in s)
    try:
        values = [int(s[i:i + 2], 16) / 255 for i in range(0, len(s), 2)]
    except ValueError:
        return (0.0, 0.0, 0.0, 1.0)
    if len(values) == 3:
        values.append(1.0)
    if len(values) != 4:
        return (0.0, 0.0, 0.0, 1.0)
    return tuple(round(v, 4) for v in values)  # type: ignore[return-value]


def to_hex(value: Any) -> str:
    """An RGB(A) tuple from 0 to 1 as ``"#rrggbb"`` (or ``"#rrggbbaa"`` when it is not opaque)."""
    r, g, b, a = components(value, 4)
    clamp = lambda v: max(0, min(255, round(v * 255)))  # noqa: E731
    out = f"#{clamp(r):02x}{clamp(g):02x}{clamp(b):02x}"
    return out if clamp(a) == 255 else out + f"{clamp(a):02x}"


def default_value(type_: str) -> Any:
    """The value a new variable or input of ``type_`` starts with."""
    return {"float": 0.0, "int": 0, "bool": False, "vec2": (0.0, 0.0), "vec3": (0.0, 0.0, 0.0),
            "vec4": (0.0, 0.0, 0.0, 1.0)}.get(type_)


def coerce(value: Any, type_: str) -> Any:
    """``value`` stored the way a ``type_`` is saved in a ``.pzshad`` (JSON numbers and lists)."""
    if type_ == "bool":
        return bool(value)
    if type_ == "int":
        return int(_scalar(value))
    if type_ == "float":
        return float(_scalar(value))
    if type_ in SIZE:
        return list(components(value, SIZE[type_]))
    return value


def describe(value: Any, type_: Optional[str]) -> str:
    """A short text for ``value`` (``0.5``, ``(1, 0, 0)``), for the outline and node rows."""
    if type_ in ("float",):
        return f"{_scalar(value):.3g}"
    if type_ == "int":
        return str(int(_scalar(value)))
    if type_ == "bool":
        return "true" if value else "false"
    if type_ in SIZE:
        return "(" + ", ".join(f"{v:.3g}" for v in components(value, SIZE[type_])) + ")"
    if type_ == "texture":
        return str(value or "white")
    return str(value)
