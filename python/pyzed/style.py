"""CSS-like styles for any widget, reusable styles and the app's global style.

Every widget has a ``style()`` method::

    pz.text("Hello").style(color="accent", size=18, weight="semibold")
    ui.button("Save", on_save).style(radius=0, border_color="#ff0000", border_width=2)
    pz.column([...]).style(background="panel", padding=12, radius=8, shadow=("#0006", (0, 4), 12))

Properties:

- Box: ``background`` (a color, ``pz.Gradient`` or ``pz.Paint``), ``border_color``,
  ``border_width``, ``border`` (``(width, color)``), ``radius`` (number or
  ``(top_left, top_right, bottom_right, bottom_left)``), ``shadow`` (``(color, (x, y), blur)``),
  ``padding``, ``margin``, ``width``, ``height``, ``max_width``, ``max_height``,
  ``align_x``/``align_y`` (where the content sits) and ``clip``.
- Text, inherited by every text inside: ``color``, ``font`` (``"sans"``, ``"mono"``,
  ``"serif"`` or a loaded family), ``weight``, ``italic``, ``size`` and ``line_height``.
- Effects: ``opacity`` (0 to 1, for everything inside), ``translate`` (``(x, y)`` in pixels
  or ``"50%"`` of the size), ``scale``, ``rotate`` (degrees clockwise, or ``"0.25turn"``,
  ``"1rad"``), ``blur`` (a gaussian blur of the widget, in pixels), ``backdrop_blur`` (blurs
  what is behind the box, in pixels), ``glow`` (a color, a blur radius or
  ``(color, radius)``: a soft halo around the box), ``bloom`` (a color, an intensity from 0
  to 1 or ``(color, intensity)``: light that spills from the bright parts) and ``glass``
  (``True``, a tint color or ``{"tint": ..., "strength": ..., "blur": ...}``: a translucent
  panel that blurs what is behind it). Glow, bloom and glass also set the shadow,
  background and border, so properties given with them win.

Colors may be theme tokens (``"accent"``, ``"text_muted"``, ``"panel"``...), so styles follow
theme switches. ``pz.Style`` keeps a style to reuse and combine (``base | accent``), and
``pz.define_style("card", ...)`` names one: ``widget.style("card")``. The app's global style
is ``App.style`` (or ``pz.set_style`` for every window); it applies to the whole view.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from . import theme as _theme

#: Every style property, in the order editors show them.
PROPERTIES = (
    "background", "color", "font", "weight", "italic", "size", "line_height",
    "border_color", "border_width", "radius", "shadow", "padding", "margin",
    "width", "height", "max_width", "max_height", "align_x", "align_y", "clip",
    "opacity", "translate", "scale", "rotate", "blur", "backdrop_blur", "glow", "bloom", "glass",
)
#: The effect properties (``glow``, ``bloom`` and ``glass`` also add box properties).
EFFECT_PROPERTIES = ("opacity", "translate", "scale", "rotate", "blur", "backdrop_blur", "glow", "bloom",
                     "glass")
TEXT_PROPERTIES = ("color", "font", "weight", "italic", "size", "line_height")
ALIASES = {"bg": "background", "text_color": "color", "font_size": "size", "font_weight": "weight",
           "font_family": "font"}

_named: Dict[str, "Style"] = {}
_global: Optional["Style"] = None


# ---------------------------------------------------------------------------
# Colors, gradients and masks
# ---------------------------------------------------------------------------

def _rgba(color: Any) -> Tuple[float, float, float, float]:
    """``(r, g, b, a)`` in 0..255 / 0..1 for a hex string, ``"transparent"``, a token or a tuple."""
    if isinstance(color, (tuple, list)):
        parts = [float(p) for p in color]
        scale = 255.0 if any(p > 1.0 for p in parts[:3]) else 1.0
        r, g, b = (p * 255.0 / scale for p in parts[:3])
        return r, g, b, parts[3] if len(parts) > 3 else 1.0
    color = _token(color)
    if color == "transparent":
        return 0.0, 0.0, 0.0, 0.0
    return _theme._rgba(color)


def _hex(r: float, g: float, b: float, a: float = 1.0) -> str:
    out = _theme._hex(r, g, b, a)
    return out if len(out) == 9 or a >= 1.0 else out + "00"


def to_hex(color: Any) -> str:
    """Any color as ``"#rrggbb"`` or ``"#rrggbbaa"`` (theme tokens resolved)."""
    return _hex(*_rgba(color))


def _token(value: Any) -> Any:
    if isinstance(value, str) and value and not value.startswith("#") and value != "transparent":
        try:
            return _theme.current().color(value)
        except AttributeError:
            raise ValueError(f"invalid color: {value!r} (not a hex color or a theme token)") from None
    return value


def _stops(stops: Iterable[Any], what: str) -> List[Tuple[float, Any]]:
    """``[(offset, value), ...]`` sorted, from plain values (spread evenly) or ``(offset, value)`` pairs."""
    items = list(stops)
    if len(items) < 2:
        raise ValueError(f"a {what} needs at least two stops")
    out = []
    for i, stop in enumerate(items):
        if isinstance(stop, (tuple, list)) and len(stop) == 2 and isinstance(stop[0], (int, float)):
            offset, value = stop
        else:
            offset, value = i / (len(items) - 1), stop
        out.append((min(max(float(offset), 0.0), 1.0), value))
    return sorted(out, key=lambda s: s[0])


def _interpolate(stops: Sequence[Tuple[float, Any]], at: float, mix: Any) -> Any:
    if at <= stops[0][0]:
        return stops[0][1]
    for (o1, v1), (o2, v2) in zip(stops, stops[1:]):
        if at <= o2:
            t = 0.0 if o2 == o1 else (at - o1) / (o2 - o1)
            return mix(v1, v2, t)
    return stops[-1][1]


#: iced draws linear gradients with at most this many stops.
MAX_STOPS = 8


class Gradient:
    """A linear gradient: ``pz.Gradient(["#ff0000", "#0000ff"], angle=90)``.

    ``stops`` are colors (spread evenly) or ``(offset, color)`` pairs with offsets from 0 to 1.
    ``angle`` follows CSS: 0 points up, 90 right, 180 (the default) down. Up to 8 stops.
    """

    __slots__ = ("stops", "angle")

    def __init__(self, stops: Iterable[Any], *, angle: float = 180.0):
        self.stops = _stops(stops, "gradient")
        if len(self.stops) > MAX_STOPS:
            raise ValueError(f"a gradient has at most {MAX_STOPS} stops")
        self.angle = float(angle)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Gradient) and (self.stops, self.angle) == (other.stops, other.angle)

    def __repr__(self) -> str:
        return f"Gradient({[(o, c) for o, c in self.stops]!r}, angle={self.angle:g})"

    def to_value(self) -> Tuple[float, List[Tuple[float, str]]]:
        """``(angle, [(offset, "#rrggbbaa"), ...])``, the form widgets take as ``gradient=``."""
        return self.angle, [(o, to_hex(c)) for o, c in self.stops]

    def to_dict(self) -> Dict[str, Any]:
        """Returns the gradient as JSON-ready data: ``{"type": "linear", "angle", "stops"}``."""
        return {"type": "linear", "angle": self.angle, "stops": [[o, c] for o, c in self.stops]}


class Mask:
    """An opacity mask: how visible a fill is along a direction, like a CSS ``mask-image`` gradient.

    ``pz.Mask([1, 0])`` fades from opaque to transparent; stops are opacities (0 to 1) or
    ``(offset, opacity)`` pairs. A mask on a gradient follows the gradient's direction;
    on a plain color it uses its own ``angle``.
    """

    __slots__ = ("stops", "angle")

    def __init__(self, stops: Iterable[Any], *, angle: float = 180.0):
        self.stops = [(o, min(max(float(a), 0.0), 1.0)) for o, a in _stops(stops, "mask")]
        self.angle = float(angle)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Mask) and (self.stops, self.angle) == (other.stops, other.angle)

    def __repr__(self) -> str:
        return f"Mask({self.stops!r}, angle={self.angle:g})"

    def at(self, offset: float) -> float:
        """Returns the opacity (0 to 1) at ``offset`` (0 to 1), interpolating between stops."""
        return _interpolate(self.stops, offset, lambda a, b, t: a + (b - a) * t)

    def to_dict(self) -> Dict[str, Any]:
        """Returns the mask as JSON-ready data: ``{"angle", "stops"}``."""
        return {"angle": self.angle, "stops": [[o, a] for o, a in self.stops]}


def _mix(a: Tuple[float, ...], b: Tuple[float, ...], t: float) -> Tuple[float, ...]:
    return tuple(x + (y - x) * t for x, y in zip(a, b))


class Paint:
    """A fill: a color or ``Gradient``, with an overall ``opacity`` and an optional ``Mask``.

    ``pz.Paint("#3b82f6", opacity=0.8, mask=pz.Mask([1, 0]))`` is a blue that fades out
    downwards. It works anywhere a background is accepted.
    """

    __slots__ = ("fill", "opacity", "mask")

    def __init__(self, fill: Any, *, opacity: float = 1.0, mask: Optional[Mask] = None):
        if isinstance(fill, Paint):
            fill, opacity, mask = fill.fill, fill.opacity * opacity, mask or fill.mask
        self.fill = fill
        self.opacity = min(max(float(opacity), 0.0), 1.0)
        self.mask = mask

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Paint) and (self.fill, self.opacity, self.mask) == (other.fill, other.opacity, other.mask)

    def __repr__(self) -> str:
        return f"Paint({self.fill!r}, opacity={self.opacity:g}, mask={self.mask!r})"

    def resolve(self) -> Tuple[Optional[str], Optional[Tuple[float, List[Tuple[float, str]]]]]:
        """``(color, gradient)``: what a container draws (one of them is ``None``)."""
        fill, mask = self.fill, self.mask
        if mask is None:
            if isinstance(fill, Gradient):
                return None, (fill.angle, [(o, _hex(*_scale_alpha(_rgba(c), self.opacity))) for o, c in fill.stops])
            return _hex(*_scale_alpha(_rgba(fill), self.opacity)), None
        if isinstance(fill, Gradient):
            angle, stops = fill.angle, fill.stops
        else:
            angle, stops = mask.angle, [(0.0, fill), (1.0, fill)]
        rgba = [(o, _rgba(c)) for o, c in stops]
        offsets = sorted({o for o, _ in stops} | {o for o, _ in mask.stops})
        if len(offsets) > MAX_STOPS:  # keep the ends and spread the rest
            step = (len(offsets) - 1) / (MAX_STOPS - 1)
            offsets = [offsets[round(i * step)] for i in range(MAX_STOPS)]
        out = []
        for offset in offsets:
            r, g, b, a = _interpolate(rgba, offset, _mix)
            out.append((offset, _hex(r, g, b, a * self.opacity * mask.at(offset))))
        return None, (angle, out)

    def to_dict(self) -> Dict[str, Any]:
        """Returns the paint as JSON-ready data: ``fill``, ``opacity`` and ``mask`` when there is one."""
        out: Dict[str, Any] = {"fill": _value_to_json(self.fill), "opacity": self.opacity}
        if self.mask is not None:
            out["mask"] = self.mask.to_dict()
        return out


def _scale_alpha(rgba: Tuple[float, float, float, float], opacity: float) -> Tuple[float, float, float, float]:
    r, g, b, a = rgba
    return r, g, b, a * opacity


def _value_to_json(value: Any) -> Any:
    if isinstance(value, (Gradient, Paint)):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_value_to_json(v) for v in value]
    return value


def _value_from_json(key: str, value: Any) -> Any:
    if key == "background" and isinstance(value, dict):
        return paint_from_dict(value)
    if key in ("padding", "margin", "radius", "border") and isinstance(value, list):
        return tuple(value)
    if key == "shadow" and isinstance(value, list):
        color, offset, blur = value
        return color, tuple(offset), blur
    return value


def paint_from_dict(data: Mapping[str, Any]) -> Union[Gradient, Paint]:
    """Rebuilds a ``Gradient`` or ``Paint`` saved with ``to_dict()``."""
    if data.get("type") == "linear":
        return Gradient([tuple(s) for s in data["stops"]], angle=data.get("angle", 180.0))
    fill = data.get("fill")
    if isinstance(fill, dict):
        fill = paint_from_dict(fill)
    mask = data.get("mask")
    if mask is not None:
        mask = Mask([tuple(s) for s in mask["stops"]], angle=mask.get("angle", 180.0))
    return Paint(fill, opacity=data.get("opacity", 1.0), mask=mask)


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------

def _normalize(props: Mapping[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in props.items():
        key = ALIASES.get(key, key)
        if key == "border":
            if value is None:
                out["border_width"] = out["border_color"] = None
                continue
            width, color = value
            out["border_width"], out["border_color"] = width, color
            continue
        if key not in PROPERTIES:
            raise TypeError(f"unknown style property {key!r}; available: {', '.join(PROPERTIES)}")
        out[key] = value
    return out


class Style:
    """A reusable set of style properties (see ``pyzed.style`` for the list).

    Combine styles with ``|`` (the right side wins) or ``style.merge(**props)``; save them with
    ``to_dict()``/``Style.from_dict()``. Pass them to ``widget.style(...)``, a component's
    ``style=`` or ``App.style``.
    """

    __slots__ = ("props",)

    def __init__(self, *styles: Any, **props: Any):
        merged: Dict[str, Any] = {}
        for style in styles:
            merged.update(_props_of(style))
        merged.update(_normalize(props))
        self.props = merged

    def __or__(self, other: Any) -> "Style":
        return Style(self, other)

    def __ror__(self, other: Any) -> "Style":
        return Style(other, self)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Style) and self.props == other.props

    def __bool__(self) -> bool:
        return bool(self.props)

    def __getitem__(self, key: str) -> Any:
        return self.props[ALIASES.get(key, key)]

    def get(self, key: str, default: Any = None) -> Any:
        """Returns a property's value (aliases accepted), or ``default`` when it is not set."""
        return self.props.get(ALIASES.get(key, key), default)

    def __repr__(self) -> str:
        return "Style(" + ", ".join(f"{k}={v!r}" for k, v in self.props.items()) + ")"

    def merge(self, *styles: Any, **props: Any) -> "Style":
        """A new style with ``styles`` and ``props`` on top of this one."""
        return Style(self, *styles, **props)

    def without(self, *keys: str) -> "Style":
        """A new style without these properties."""
        drop = {ALIASES.get(k, k) for k in keys}
        return Style(**{k: v for k, v in self.props.items() if k not in drop})

    def text(self) -> "Style":
        """Only the text properties (what a style passes down to the texts inside)."""
        return Style(**{k: v for k, v in self.props.items() if k in TEXT_PROPERTIES})

    def to_dict(self) -> Dict[str, Any]:
        """JSON-friendly properties (gradients and paints become dicts)."""
        return {k: _value_to_json(v) for k, v in self.props.items()}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Style":
        """Builds a style from data made by ``to_dict`` (aliases accepted)."""
        return cls(**{k: _value_from_json(ALIASES.get(k, k), v) for k, v in data.items()})


def _props_of(style: Any) -> Dict[str, Any]:
    if style is None:
        return {}
    if isinstance(style, Style):
        return dict(style.props)
    if isinstance(style, str):
        try:
            return dict(_named[style].props)
        except KeyError:
            raise KeyError(f"no style named {style!r}; define it with pz.define_style({style!r}, ...)") from None
    if isinstance(style, Mapping):
        return _normalize(style)
    if isinstance(style, (list, tuple)):
        merged: Dict[str, Any] = {}
        for item in style:
            merged.update(_props_of(item))
        return merged
    raise TypeError(f"a style is a pz.Style, a dict or a style name, not {type(style).__name__}")


def define_style(name: str, *styles: Any, **props: Any) -> Style:
    """Names a style so widgets can use it by name: ``widget.style("card")``. Returns it."""
    style = Style(*styles, **props)
    _named[name] = style
    return style


def named_styles() -> Dict[str, Style]:
    """The styles defined with ``define_style``, by name."""
    return dict(_named)


def set_style(*styles: Any, **props: Any) -> Optional[Style]:
    """Sets the global style applied to every window's view (``None`` clears it); returns it."""
    global _global
    style = Style(*styles, **props) if styles or props else None
    _global = style if style else None
    return _global


def global_style() -> Optional[Style]:
    """The style set with ``set_style`` (``None`` if none)."""
    return _global


#: Global style properties that become theme tokens, so ``pyzed.ui`` components follow them.
THEME_TOKENS = {"color": "text", "background": "background", "border_color": "border", "size": "ui_font_size"}


def themed(theme: "_theme.Theme", style: Any) -> "_theme.Theme":
    """``theme`` with a global style's text color, background, border color, size and radius."""
    props = _props_of(style)
    changes: Dict[str, Any] = {}
    for key, token in THEME_TOKENS.items():
        value = props.get(key)
        if value is None or (key == "background" and isinstance(value, (Gradient, Paint))):
            continue
        if key == "size":
            changes[token] = float(value)
        else:
            changes[token] = theme.color(value) if isinstance(value, str) else to_hex(value)
    radius = props.get("radius")
    if isinstance(radius, (int, float)):
        changes.update(radius=float(radius), radius_sm=max(float(radius) - 2, 0.0))
    return theme.derive(**changes) if changes else theme


def apply_global(view: Any, style: Any = None) -> Any:
    """``view`` with a window's global style: text properties fill in what texts leave unset."""
    from . import _core

    props = _props_of(style)
    if not props:
        return view
    if "background" in props:
        props.setdefault("width", "fill")
        props.setdefault("height", "fill")
    if not isinstance(view, _core.Widget):
        view = _core.container(view)
    return view.style(props, defaults=True)


def _alpha(color: Any, alpha: float) -> str:
    r, g, b, a = _rgba(color)
    return _hex(r, g, b, a * alpha)


def _accent() -> str:
    try:
        return _theme.current().accent
    except AttributeError:  # pragma: no cover - every theme has an accent
        return "#61afef"


def _effects(merged: Mapping[str, Any]) -> Dict[str, Any]:
    """The box properties ``glow``, ``bloom`` and ``glass`` stand for."""
    out: Dict[str, Any] = {}
    glass = merged.get("glass")
    if glass:
        tint, strength = "#ffffff", 0.08
        if isinstance(glass, Mapping):
            tint, strength = glass.get("tint", tint), float(glass.get("strength", strength))
        elif not isinstance(glass, bool):
            tint = glass
        strength = min(max(strength, 0.0), 1.0)
        out["background"] = Gradient([_alpha(tint, min(strength * 1.6, 1.0)), _alpha(tint, strength * 0.6)])
        out["border_color"] = _alpha(tint, min(0.08 + strength * 1.5, 1.0))
        out["border_width"] = 1
        out["radius"] = 12
        out["shadow"] = ("#00000059", (0, 10), 30)
        blur = glass.get("blur", 20) if isinstance(glass, Mapping) else 20
        out["backdrop_blur"] = float(blur)
    glow = merged.get("glow")
    if glow is not None and glow is not False:
        color, radius = _accent(), 12.0
        if isinstance(glow, (tuple, list)) and len(glow) == 2 and isinstance(glow[1], (int, float)):
            color, radius = glow[0], float(glow[1])
        elif isinstance(glow, (int, float)) and not isinstance(glow, bool):
            radius = float(glow)
        elif glow is not True:
            color = glow
        out["shadow"] = (_alpha(color, 0.85), (0, 0), radius)
    bloom = merged.get("bloom")
    if bloom is not None and bloom is not False:
        color, intensity = _accent(), 0.6
        if isinstance(bloom, (tuple, list)) and len(bloom) == 2 and isinstance(bloom[1], (int, float)):
            color, intensity = bloom[0], float(bloom[1])
        elif isinstance(bloom, (int, float)) and not isinstance(bloom, bool):
            intensity = float(bloom)
        elif bloom is not True:
            color = bloom
        intensity = min(max(intensity, 0.0), 1.0)
        # Real bloom: light from the bright parts, tinted. A box (a background or glass) also
        # gets a softer halo and a lit edge; a bare text or icon glows on its own.
        out["bloom_light"] = (color, intensity)
        if merged.get("background") is not None or glass:
            out["shadow"] = (_alpha(color, 0.3 + 0.35 * intensity), (0, 0), 8 + 20 * intensity)
            out["border_color"] = _alpha(color, 0.35 + 0.6 * intensity)
            out["border_width"] = 1
    return out


def degrees(value: Any) -> float:
    """An angle in degrees from a number (degrees) or ``"45deg"``, ``"0.25turn"``, ``"1.2rad"``."""
    if isinstance(value, str):
        text = value.strip().lower()
        for unit, factor in (("deg", 1.0), ("turn", 360.0), ("grad", 0.9), ("rad", 57.29577951308232)):
            if text.endswith(unit):
                return float(text[: -len(unit)]) * factor
        return float(text)
    return float(value)


def _translate(value: Any) -> Tuple[Any, Any]:
    if isinstance(value, (int, float)):
        value = (value, 0)
    x, y = value

    def one(v: Any) -> Any:
        if isinstance(v, str):
            text = v.strip()
            if text.endswith("%"):
                return ("pct", float(text[:-1]) / 100.0)
            return float(text.removesuffix("px"))
        return float(v)

    return one(x), one(y)


def _resolve(previous: Optional[Mapping[str, Any]], styles: Sequence[Any],
             props: Optional[Mapping[str, Any]]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Merges a widget's styles (called by ``Widget.style``).

    Returns the merged properties (kept on the widget, so a later ``style()`` merges with
    them and ``style_props()`` reads them back) and the plain values the native side draws.
    """
    merged: Dict[str, Any] = dict(previous or {})
    for style in styles:
        merged.update(_props_of(style))
    merged.update(_normalize(props or {}))
    merged = {k: v for k, v in merged.items() if v is not None}
    drawn = {**_effects(merged), **{k: v for k, v in merged.items() if k not in ("glow", "bloom", "glass")}}
    out: Dict[str, Any] = {}
    for key, value in drawn.items():
        if key == "background":
            if isinstance(value, Gradient):
                out["gradient"] = value.to_value()
            elif isinstance(value, Paint):
                color, gradient = value.resolve()
                out["gradient" if gradient is not None else "background"] = gradient or color
            elif isinstance(value, tuple) and len(value) == 2 and isinstance(value[1], (list, tuple)):
                out["gradient"] = Gradient(value[1], angle=value[0]).to_value()  # (angle, stops)
            else:
                out["background"] = to_hex(value)
        elif key in ("color", "border_color"):
            out[key] = to_hex(value)
        elif key == "shadow":
            color, offset, blur = value
            out[key] = (to_hex(color), tuple(offset), blur)
        elif key == "translate":
            out[key] = _translate(value)
        elif key in ("opacity", "scale", "blur", "backdrop_blur"):
            out[key] = float(value)
        elif key == "rotate":
            out[key] = degrees(value)
        elif key == "bloom_light":
            out[key] = (to_hex(value[0]), float(value[1]))
        else:
            out[key] = value
    return merged, out
