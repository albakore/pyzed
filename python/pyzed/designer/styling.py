"""Styles in the designer: what the Style section edits and how saved styles are drawn.

A control's ``style`` (and the form's global ``style``) is a ``pz.Style`` saved as a dict
(``Style.to_dict()``). The property grid edits it one field at a time, so a value can be
half typed (``"#3b8"``): drawing skips the properties that are not valid yet instead of
failing, and theme tokens resolve against the form's theme, not the designer's.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .. import _core
from .. import style as _style
from .. import theme as _theme
from ..theme import Theme


@dataclass(frozen=True)
class Field:
    """One row of the Style section: a style property and how it is edited."""

    key: str
    title: str
    kind: str  # "color", "number", "choice", "toggle", "box", "radius", "shadow"
    choices: Tuple[str, ...] = ()
    min: Optional[float] = None
    max: Optional[float] = None
    step: float = 1
    tip: Optional[str] = None


FONTS = ("", "sans", "serif", "mono")
WEIGHTS = ("", "thin", "light", "normal", "medium", "semibold", "bold", "black")
ALIGN_X = ("", "start", "center", "end")
ALIGN_Y = ("", "start", "center", "end")
TRISTATE = ("", "on", "off")

#: The rows after the background editor, in ``pyzed.style.PROPERTIES`` order. Width and
#: height are left out: the designer sizes controls with their own Position fields.
FIELDS = (
    Field("color", "Text color", "color"),
    Field("font", "Font", "choice", FONTS),
    Field("weight", "Weight", "choice", WEIGHTS),
    Field("italic", "Italic", "choice", TRISTATE),
    Field("size", "Font size", "number", min=0, max=96, tip="0 keeps the component's own size"),
    Field("line_height", "Line height", "number", min=0, max=4, step=0.1, tip="A multiple of the font size; 0 keeps it"),
    Field("border_color", "Border color", "color"),
    Field("border_width", "Border width", "number", min=0, max=32),
    Field("radius", "Corner radius", "radius", tip="One number, or four: top-left top-right bottom-right bottom-left"),
    Field("shadow", "Shadow", "shadow", tip="Color, then the offset and the blur"),
    Field("padding", "Padding", "box", tip="One number, two (vertical horizontal) or four (top right bottom left)"),
    Field("margin", "Margin", "box", tip="Space outside: one, two or four numbers"),
    Field("max_width", "Max width", "number", min=0, max=4096, step=8, tip="0 means no limit"),
    Field("max_height", "Max height", "number", min=0, max=4096, step=8, tip="0 means no limit"),
    Field("align_x", "Align content", "choice", ALIGN_X),
    Field("align_y", "Align vertically", "choice", ALIGN_Y),
    Field("clip", "Clip", "choice", TRISTATE, tip="Cut what overflows the box"),
)
FIELD = {f.key: f for f in FIELDS}

#: The global style edits the properties that make sense for a whole window.
GLOBAL_FIELDS = tuple(f for f in FIELDS if f.key in ("color", "font", "weight", "italic", "size", "line_height",
                                                     "border_color", "radius", "padding"))



# -- reading and writing values --------------------------------------------------


def numbers(text: Any) -> Optional[Any]:
    """``"8"`` -> 8, ``"8 12"`` -> (8, 12), ``"1, 2, 3, 4"`` -> (1, 2, 3, 4); None when empty or invalid."""
    if isinstance(text, (int, float)):
        return text
    if isinstance(text, (list, tuple)):
        return tuple(text)
    parts = [p for p in re.split(r"[\s,]+", str(text or "").strip()) if p]
    try:
        values = [float(p) for p in parts]
    except ValueError:
        return None
    values = [int(v) if v.is_integer() else v for v in values]
    if not values:
        return None
    return values[0] if len(values) == 1 else tuple(values)


def numbers_text(value: Any) -> str:
    """The text a box or radius field shows for a saved value."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return " ".join(_num_text(v) for v in value)
    return _num_text(value)


def _num_text(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def field_value(key: str, raw: Any) -> Any:
    """What a field edit stores: ``None`` (unset) for empty text, 0 sizes, "default" choices..."""
    field = FIELD.get(key)
    kind = field.kind if field else None
    if raw is None:
        return None
    if kind == "color":
        return str(raw).strip() or None
    if kind == "number":
        number = float(raw)
        if number <= 0 and key not in ("border_width",):
            return None
        return int(number) if number.is_integer() else number
    if kind == "choice":
        if raw in ("", "default"):
            return None
        if field is not None and field.choices is TRISTATE:
            return raw == "on"
        return raw
    if kind in ("box", "radius"):
        value = numbers(raw)
        if kind == "radius" and isinstance(value, tuple) and len(value) == 2:
            value = (value[0], value[1], value[0], value[1])
        return value
    return raw


def choice_of(key: str, value: Any) -> str:
    """The choice a choice field shows for a saved value ("" is the default)."""
    if value is None:
        return ""
    if FIELD[key].choices is TRISTATE:
        return "on" if value else "off"
    return str(value)


def shadow_parts(value: Any) -> Tuple[str, float, float, float]:
    """``(color, x, y, blur)`` of a saved shadow (an empty color when there is none)."""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        color, offset, blur = value
        x, y = (list(offset) + [0, 0])[:2] if isinstance(offset, (list, tuple)) else (0, 0)
        return str(color or ""), float(x), float(y), float(blur or 0)
    return "", 0.0, 4.0, 12.0


def shadow_value(color: str, x: float, y: float, blur: float) -> Optional[List[Any]]:
    """Returns a shadow as it is saved, ``[color, [x, y], blur]`` (whole numbers as ints), or ``None``
    when ``color`` is empty (no shadow).
    """
    color = (color or "").strip()
    if not color:
        return None
    return [color, [_int(x), _int(y)], _int(blur)]


def _int(value: float) -> Any:
    value = float(value)
    return int(value) if value.is_integer() else value


def picked(value: Any) -> Any:
    """What a color picker reports (a color, ``pz.Gradient`` or ``pz.Paint``) as it is saved."""
    if isinstance(value, (_style.Gradient, _style.Paint)):
        return value.to_dict()
    return value or None


def unpicked(value: Any, theme: Theme, default: str) -> Any:
    """A saved color or background as a color picker takes it (tokens resolved in the form's theme)."""
    if isinstance(value, dict):
        try:
            return _style.paint_from_dict(value)
        except (KeyError, TypeError, ValueError):
            return default
    if not value:
        return default
    try:
        with _using(theme):
            return _style.to_hex(value)
    except (TypeError, ValueError):
        return default


def describe(value: Any) -> str:
    """A short name for a saved background: "None", "Color", "Gradient" or "Masked"."""
    if not value:
        return "None"
    if isinstance(value, dict):
        if value.get("type") == "linear":
            return "Gradient"
        if value.get("mask"):
            return "Masked"
        return "Gradient" if isinstance(value.get("fill"), dict) else "Color"
    return "Color"


# -- drawing ---------------------------------------------------------------------

_valid: Dict[Tuple[str, str], bool] = {}


def _valid_prop(key: str, value: Any, theme: Theme) -> bool:
    """Whether ``widget.style(key=value)`` accepts the value (memoized by its JSON)."""
    try:
        cache_key = (key, json.dumps(value, sort_keys=True, default=str))
    except (TypeError, ValueError):
        return False
    known = _valid.get(cache_key)
    if known is None:
        try:
            with _using(theme):
                _core.space().style(_style.Style.from_dict({key: value}))
            known = True
        except Exception:  # noqa: BLE001 - half-typed values are skipped, not errors
            known = False
        if len(_valid) > 4096:
            _valid.clear()
        _valid[cache_key] = known
    return known


def clean(style: Optional[Dict[str, Any]], theme: Theme) -> Optional[_style.Style]:
    """The valid part of a saved style as a ``pz.Style`` (``None`` when nothing is set)."""
    if not style:
        return None
    good = {k: v for k, v in style.items() if v is not None and _valid_prop(k, v, theme)}
    return _style.Style.from_dict(good) if good else None


class _using:
    """Resolves theme tokens against ``theme`` while a style is applied."""

    def __init__(self, theme: Theme) -> None:
        self.theme = theme

    def __enter__(self) -> None:
        self.previous = _theme.current()
        _theme.use(self.theme)

    def __exit__(self, *_exc: Any) -> None:
        _theme.use(self.previous)


def apply(widget: Any, style: Optional[Dict[str, Any]], theme: Theme) -> Any:
    """``widget`` with a control's saved style (unchanged when it has none)."""
    clean_style = clean(style, theme)
    if clean_style is None:
        return widget
    with _using(theme):
        return widget.style(clean_style)


def themed(theme: Theme, style: Optional[Dict[str, Any]]) -> Theme:
    """``theme`` with a form's global text color, background, border color, size and radius."""
    clean_style = clean(style, theme)
    return _style.themed(theme, clean_style) if clean_style is not None else theme


def apply_global(view: Any, style: Optional[Dict[str, Any]], theme: Theme, *, background: bool = True) -> Any:
    """``view`` with a form's global style (texts inside take its font, color and size)."""
    clean_style = clean(style, theme)
    if clean_style is not None and not background:
        clean_style = clean_style.without("background")
    if not clean_style:
        return view
    with _using(theme):
        return _style.apply_global(view, clean_style)


def background_layer(style: Optional[Dict[str, Any]], theme: Theme) -> Optional[Any]:
    """A full-size layer with a global gradient or paint background (plain colors go through the theme)."""
    clean_style = clean(style, theme)
    value = clean_style.get("background") if clean_style is not None else None
    if not isinstance(value, (_style.Gradient, _style.Paint)):
        return None
    with _using(theme):
        return _core.container(width="fill", height="fill").style(background=value)
