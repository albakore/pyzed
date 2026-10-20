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

- Placement inside a ``pz.box``: ``position="absolute"`` with ``top``, ``right``,
  ``bottom``, ``left`` and ``z_index`` (see ``pz.box``).
- Size limits: ``min_width``/``min_height`` (pixels) next to ``max_width``/``max_height``.
- States, like CSS ``:hover``, ``:active`` and ``:focus``: ``hover``, ``pressed`` and
  ``focus`` take the properties to show in that state (``background``, ``color``,
  ``border_color``, ``border_width``, ``radius``, ``opacity``, ``translate``, ``scale``,
  ``rotate`` and ``blur``). ``transition`` animates the change, like CSS: milliseconds
  (``150``, ``"0.2s"``), ``True`` (150 ms) or ``{"duration": ..., "easing": ..., "delay": ...}``.
  With a transition, changes of ``opacity``, ``translate``, ``scale``, ``rotate`` and ``blur``
  between renders animate too::

      ui.button("Save", save).style(background="accent", radius=6,
                                    hover={"background": "#4f8cff", "translate": (0, -1)},
                                    pressed={"scale": 0.97}, transition=120)

Colors may be theme tokens (``"accent"``, ``"text_muted"``, ``"panel"``...), so styles follow
theme switches. ``pz.Style`` keeps a style to reuse and combine (``base | accent``), and
``pz.define_style("card", ...)`` names one: ``widget.style("card")``. The app's global style
is ``App.style`` (or ``pz.set_style`` for every window); it applies to the whole view.

Stylesheets work like CSS: ``pz.stylesheet({...})`` adds rules by selector and
``widget.classes("card", id="main")`` (or a component's ``class_=`` and ``id=``) applies the
matching ones::

    pz.stylesheet({
        ".card": {"background": "panel", "padding": 16, "radius": 8},
        ".card:hover": {"border_color": "accent"},
        ".card.selected, #featured": {"border": (2, "accent")},
        "Rating": {"padding": 4},               # every Rating component
    })
    pz.column([...]).classes("card", "selected" if chosen else "")

A selector is an optional component name, ``.class`` names, an ``#id`` and an optional
state (``:hover``, ``:pressed``/``:active``, ``:focus``); commas list several. More
specific selectors win (ids, then classes, then names), then later rules; a ``style()``
call after ``classes()`` goes on top. Named styles (``define_style``) also work as classes.

Responsive styles follow the window's size, like CSS media queries::

    pz.stylesheet({
        ".sidebar": {"width": 260},
        "@media (max_width: 700)": {".sidebar": {"width": 64}},
        "@md": {".grid": {"padding": 24}},          # a breakpoint: 768 px wide and up
    })
    panel.style(padding=24, media={"max_width: 600": {"padding": 8}})

Queries: ``min_width``, ``max_width``, ``min_height`` and ``max_height`` (pixels, ``px``
optional), ``orientation`` (``portrait``/``landscape``) and ``theme`` (``dark``/``light``),
joined with ``and``, or a breakpoint name of ``BREAKPOINTS`` (``sm``, ``md``, ``lg``,
``xl``, ``xxl``: that width and up). ``pz.viewport()``, ``pz.media(...)`` and
``pz.current_breakpoint()`` answer the same questions in a view.
"""

from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet, Iterable, List, Mapping, NamedTuple, Optional, Sequence, Tuple, Union

from . import theme as _theme

#: Every style property, in the order editors show them.
PROPERTIES = (
    "background", "color", "font", "weight", "italic", "size", "line_height",
    "border_color", "border_width", "radius", "shadow", "padding", "margin",
    "width", "height", "max_width", "max_height", "min_width", "min_height", "align_x", "align_y", "clip",
    "opacity", "translate", "scale", "rotate", "blur", "backdrop_blur", "glow", "bloom", "glass",
    "position", "top", "right", "bottom", "left", "z_index",
)
#: Where a child of ``pz.box`` sits: ``position="absolute"`` takes it out of the flow and
#: places it by ``top``/``right``/``bottom``/``left`` (pixels), above the others by ``z_index``.
POSITION_PROPERTIES = ("position", "top", "right", "bottom", "left", "z_index")
POSITIONS = ("static", "relative", "absolute")
#: The effect properties (``glow``, ``bloom`` and ``glass`` also add box properties).
EFFECT_PROPERTIES = ("opacity", "translate", "scale", "rotate", "blur", "backdrop_blur", "glow", "bloom",
                     "glass")
TEXT_PROPERTIES = ("color", "font", "weight", "italic", "size", "line_height")
ALIASES = {"bg": "background", "text_color": "color", "font_size": "size", "font_weight": "weight",
           "font_family": "font"}
#: The interaction states a style can set, like CSS ``:hover``, ``:active`` and ``:focus``.
STATES = ("hover", "pressed", "focus")
STATE_ALIASES = {"press": "pressed", "active": "pressed"}
#: The properties a state can change (they animate, so the box keeps its layout).
STATE_PROPERTIES = ("background", "color", "border_color", "border_width", "radius", "opacity", "translate",
                    "scale", "rotate", "blur")
#: The effects a ``transition`` animates when they change between renders.
TRANSITION_PROPERTIES = ("opacity", "translate", "scale", "rotate", "blur")
_STATE_TRIGGERS = {"hover": "hover", "pressed": "press", "focus": "focus"}
#: Breakpoints for ``@md``-style rules and ``media={"md": ...}``: each applies from that window
#: width (logical pixels) up, like Tailwind's.
BREAKPOINTS = {"sm": 640, "md": 768, "lg": 1024, "xl": 1280, "xxl": 1536}

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
    if isinstance(value, dict):  # a state's properties
        return {k: _value_to_json(v) for k, v in value.items()}
    if isinstance(value, (Gradient, Paint)):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_value_to_json(v) for v in value]
    return value


def _value_from_json(key: str, value: Any) -> Any:
    if key == "media" and isinstance(value, dict):
        return {q: {k: _value_from_json(ALIASES.get(k, STATE_ALIASES.get(k, k)), v) for k, v in props.items()}
                for q, props in value.items()}
    if key in STATES and isinstance(value, dict):
        return {k: _value_from_json(ALIASES.get(k, k), v) for k, v in value.items()}
    if key == "background" and isinstance(value, dict):
        return paint_from_dict(value)
    if key in ("padding", "margin", "radius", "border", "translate") and isinstance(value, list):
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
        key = ALIASES.get(key, STATE_ALIASES.get(key, key))
        if key in STATES:
            out[key] = None if value is None else _state(key, value)
            continue
        if key == "transition":
            _timing(value)  # validates it
            out[key] = value
            continue
        if key == "media":
            if value is None:
                out[key] = None
                continue
            if not isinstance(value, Mapping):
                raise TypeError("media takes {query: style}, such as {\"max_width: 600\": {\"padding\": 8}}")
            for query in value:
                _parse_query(str(query))  # validates it
            out[key] = {str(q): _props_of(v) for q, v in value.items()}
            continue
        if key == "border":
            if value is None:
                out["border_width"] = out["border_color"] = None
                continue
            width, color = value
            out["border_width"], out["border_color"] = width, color
            continue
        if key == "position" and value is not None and value not in POSITIONS:
            raise ValueError(f"position must be one of {', '.join(POSITIONS)}, not {value!r}")
        if key not in PROPERTIES:
            raise TypeError(f"unknown style property {key!r}; available: {', '.join(PROPERTIES)}, "
                            f"the states {', '.join(STATES)} and transition")
        out[key] = value
    return out


def _state(name: str, value: Any) -> Dict[str, Any]:
    """The properties of a state (``hover={...}``), checked."""
    props = _props_of(value)
    for key in props:
        if key not in STATE_PROPERTIES:
            raise TypeError(f"{name} can't set {key!r}; a state sets {', '.join(STATE_PROPERTIES)}")
    background = props.get("background")
    if isinstance(background, (Gradient, Paint)):
        raise TypeError(f"{name}: a state's background must be a color, not a gradient or paint")
    radius = props.get("radius")
    if radius is not None and not isinstance(radius, (int, float)):
        raise TypeError(f"{name}: a state's radius must be a number")
    return props


def _merge(target: Dict[str, Any], props: Mapping[str, Any]) -> Dict[str, Any]:
    """``props`` on top of ``target``; states merge property by property, like CSS rules."""
    for key, value in props.items():
        if (key in STATES or key == "media") and isinstance(value, dict) and isinstance(target.get(key), dict):
            target[key] = {**target[key], **value}
        else:
            target[key] = value
    return target


def _timing(value: Any) -> Optional[Tuple[float, Any, float]]:
    """``(duration, easing, delay)`` from a ``transition`` value (``None``: no transition)."""
    if value is None or value is False:
        return None
    from . import animation as _animation

    if value is True:
        return 150.0, _animation._easing("ease_out"), 0.0
    if isinstance(value, Mapping):
        unknown = set(value) - {"duration", "easing", "delay"}
        if unknown:
            raise TypeError(f"unknown transition option {sorted(unknown)[0]!r}; use duration, easing and delay")
        return (_animation._ms(value.get("duration", 150), "duration"),
                _animation._easing(value.get("easing", "ease_out")),
                _animation._ms(value.get("delay", 0), "delay"))
    return _animation._ms(value, "transition"), _animation._easing("ease_out"), 0.0


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
            _merge(merged, _props_of(style))
        _merge(merged, _normalize(props))
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
        return cls(**{k: _value_from_json(ALIASES.get(k, STATE_ALIASES.get(k, k)), v) for k, v in data.items()})


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
            _merge(merged, _props_of(item))
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
        _merge(merged, _props_of(style))
    _merge(merged, _normalize(props or {}))
    merged = {k: v for k, v in merged.items() if v is not None}
    source = merged  # kept with its media queries, so a later style() call checks them again
    if "media" in merged:
        merged = {k: v for k, v in merged.items() if k != "media"}
        for query, extra in source["media"].items():
            if _matches(_parse_query(query)):
                _merge(merged, {k: v for k, v in extra.items() if v is not None})
    skip = ("glow", "bloom", "glass", "transition", *STATES)
    drawn = {**_effects(merged), **{k: v for k, v in merged.items() if k not in skip}}
    timing = _timing(merged.get("transition"))
    out: Dict[str, Any] = {}
    if timing is not None:
        # The effects become transitions (set, not multiplied), so changes between renders
        # animate; the states below are relative to them.
        moving = {k: drawn.pop(k) for k in TRANSITION_PROPERTIES if k in drawn}
        out["transitions"] = _transitions(moving, timing)
    states = _states(merged, timing)
    if states:
        out["states"] = states
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
    return source, out


def _anim_values(props: Mapping[str, Any]) -> Dict[str, Any]:
    """Style properties as the animation properties they map to."""
    out: Dict[str, Any] = {}
    for key, value in props.items():
        if key == "translate":
            x, y = (value, 0) if isinstance(value, (int, float, str)) else value
            out["x"], out["y"] = x, y
        else:
            out[key] = value
    return out


def _transitions(props: Mapping[str, Any], timing: Tuple[float, Any, float]) -> List[Dict[str, Any]]:
    from . import animation as _animation

    duration, easing, delay = timing
    values = {"opacity": 1.0, "x": 0.0, "y": 0.0, "scale": 1.0, "rotate": 0.0, "blur": 0.0}
    values.update(_anim_values(props))
    return _animation._compile_transition({**values, "duration": duration, "easing": easing, "delay": delay})


def _relative(key: str, value: Any, base: Any) -> Any:
    """A state's effect value relative to the widget's own one (animations stack on it)."""
    if base is None:
        return value
    if key in ("opacity", "scale"):
        base = float(base)
        return float(value) / base if base else float(value)
    if isinstance(value, str) or isinstance(base, str):
        if isinstance(value, str) and isinstance(base, str) and value.strip().endswith("%") \
                and base.strip().endswith("%"):
            return f"{float(value.strip()[:-1]) - float(base.strip()[:-1])}%"
        if isinstance(value, str) or isinstance(base, str):
            if key == "rotate":
                return degrees(value) - degrees(base)
            return value  # pixels and percentages: can't subtract, the state's value wins
    return float(value) - float(base)


def _states(merged: Mapping[str, Any], timing: Optional[Tuple[float, Any, float]]) -> List[Dict[str, Any]]:
    """The animations that show the ``hover``, ``pressed`` and ``focus`` styles."""
    from . import animation as _animation

    duration, easing, delay = timing or (0.0, _animation._easing("linear"), 0.0)
    own = _anim_values({k: merged[k] for k in TRANSITION_PROPERTIES if k in merged})
    out: List[Dict[str, Any]] = []
    for state in STATES:
        props = merged.get(state)
        if not props:
            continue
        values = {k: v for k, v in _anim_values(props).items() if v is not None}
        for key in ("opacity", "scale", "x", "y", "rotate", "blur"):
            if key in values:
                values[key] = _relative(key, values[key], own.get(key))
        if not values:
            continue
        for key in ("background", "color", "border_color"):
            if key in values:
                values[key] = to_hex(values[key])
        out.extend(_animation._compile((), {"on": _STATE_TRIGGERS[state], "duration": duration,
                                            "easing": easing, "delay": delay, **values}))
    return out


# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

_SELECTOR = re.compile(r"^(?P<name>[A-Za-z_][\w-]*)?(?P<parts>(?:[.#][A-Za-z_][\w-]*)*)(?::(?P<state>[a-z_]+))?$")


class Rule(NamedTuple):
    """One rule of ``pz.stylesheet``: a single selector and its properties."""

    selector: str
    name: Optional[str]
    classes: FrozenSet[str]
    id: Optional[str]
    state: Optional[str]
    props: Dict[str, Any]
    #: The ``@media`` conditions the rule needs (``None``: always).
    media: Optional[Tuple[Tuple[str, Any], ...]] = None

    @property
    def specificity(self) -> Tuple[int, int, int]:
        """Like CSS: ``(ids, classes, names)``."""
        return (1 if self.id else 0, len(self.classes), 1 if self.name else 0)

    def matches(self, name: Optional[str], classes: FrozenSet[str], id: Optional[str]) -> bool:
        return ((self.name is None or self.name == name) and self.classes <= classes
                and (self.id is None or self.id == id) and (self.media is None or _matches(self.media)))


_rules: Dict[str, List[Rule]] = {}


def _parse_selector(text: str) -> Tuple[Optional[str], FrozenSet[str], Optional[str], Optional[str]]:
    match = _SELECTOR.match(text.strip())
    if not match or not (match["name"] or match["parts"]):
        raise ValueError(f"invalid selector {text!r}: use a component name, .class, #id and an optional "
                         f":hover, :pressed or :focus (descendant selectors are not supported)")
    classes, ids = set(), []
    for part in re.findall(r"[.#][A-Za-z_][\w-]*", match["parts"] or ""):
        (classes.add(part[1:]) if part[0] == "." else ids.append(part[1:]))
    if len(ids) > 1:
        raise ValueError(f"invalid selector {text!r}: one #id at most")
    state = match["state"]
    if state is not None:
        state = STATE_ALIASES.get(state, state)
        if state not in STATES:
            raise ValueError(f"unknown state :{match['state']} in {text!r}; use :hover, :pressed or :focus")
    return match["name"], frozenset(classes), ids[0] if ids else None, state


def stylesheet(rules: Optional[Mapping[str, Any]] = None, **classes: Any) -> Dict[str, Style]:
    """Adds CSS-like rules: ``{selector: style}``. Returns every rule, by selector.

    Selectors: ``".card"``, ``".card.selected"``, ``"#main"``, ``"Rating"`` (a component),
    ``".card:hover"`` (also ``:pressed``/``:active`` and ``:focus``) and comma lists
    (``".a, .b"``). Keywords add classes: ``stylesheet(card={...})`` is ``".card"``. A rule
    given again replaces the old one, so reloading the code keeps one copy.
    """
    items = list((rules or {}).items()) + [("." + k, v) for k, v in classes.items()]
    for selector, style in items:
        selector = str(selector)
        if selector.startswith("@"):
            if not isinstance(style, Mapping):
                raise TypeError(f"{selector} takes {{selector: style}} rules")
            query = selector[1:].strip()
            query = query[len("media"):].strip() if query.startswith("media") else query
            conditions = _parse_query(query)
            parsed = [Rule(one.strip(), *_parse_selector(one), _rule_props(one, inner), conditions)
                      for inner_selector, inner in style.items() for one in str(inner_selector).split(",")]
        else:
            parsed = [Rule(one.strip(), *_parse_selector(one), _rule_props(one, style)) for one in selector.split(",")]
        _rules.pop(selector, None)
        _rules[selector] = parsed
    return {selector: Style(*[r.props for r in rules if r.media is None]) for selector, rules in _rules.items()}


def _rule_props(selector: str, style: Any) -> Dict[str, Any]:
    props = _props_of(style)
    state = _parse_selector(selector)[3]
    return {state: _state(state, props)} if state else props


def clear_stylesheet() -> None:
    """Removes every rule added with ``pz.stylesheet``."""
    _rules.clear()


def stylesheet_rules() -> List[Rule]:
    """Every rule of the stylesheet, in order (one per selector of a comma list)."""
    return [rule for rules in _rules.values() for rule in rules]


def _class_names(names: Iterable[Any]) -> FrozenSet[str]:
    out = set()
    for name in names:
        if name is None or name is False:
            continue
        if isinstance(name, (list, tuple, set, frozenset)):
            out |= _class_names(name)
        else:
            out.update(str(name).split())
    return frozenset(out)


def matching(name: Optional[str] = None, classes: Iterable[Any] = (), id: Optional[str] = None, *,
             specific: bool = False) -> Style:
    """The style the stylesheet gives a component ``name`` with these classes and ``id``.

    ``specific=True`` leaves out the rules that only name the component.
    """
    names = _class_names([classes] if isinstance(classes, str) else classes)
    found = [(r.specificity, i, r.props) for i, r in enumerate(stylesheet_rules())
             if r.matches(name, names, id) and not (specific and not r.classes and not r.id)]
    # Named styles work as classes, under the rules (same specificity, earlier).
    found += [((0, 1, 0), -1, dict(_named[n].props)) for n in sorted(names) if n in _named]
    merged: Dict[str, Any] = {}
    for _spec, _order, props in sorted(found, key=lambda f: (f[0], f[1])):
        _merge(merged, props)
    return Style(merged)


def _apply_component_rules(widget: Any, name: str, classes: Any, id: Optional[str]) -> Any:
    """A component's root styled by the stylesheet: rules for its name are defaults under what
    ``render()`` set, rules for the ``class_``/``id`` it was given go on top."""
    if not _rules and not _named:
        return widget
    base = matching(name)
    if base:
        # Under what render() set, when that is the root's own style (a style around on() or
        # animate() is another box, so the rules go around it).
        own = widget.style_props() if repr(widget).endswith(".style()") else None
        widget = widget.style(base, own) if own else widget.style(base)
    if classes is not None or id is not None:
        top = matching(name, () if classes is None else (classes,), id, specific=True)
        if top:
            widget = widget.style(top)
    return widget


def _apply_classes(widget: Any, names: Iterable[Any], id: Optional[str] = None, name: Optional[str] = None) -> Any:
    """What ``Widget.classes`` does: the widget styled by the matching rules."""
    if not _rules and not _named:
        return widget
    style = matching(name, names, id)
    return widget.style(style) if style else widget


# ---------------------------------------------------------------------------
# Responsive: the window's size, media queries and breakpoints
# ---------------------------------------------------------------------------

#: The size of the window whose view is being built (set by the runtime before ``view()``).
_viewport: Optional[Tuple[float, float]] = None
#: The size a screenshot renders at (set while ``pz.screenshot`` runs).
_screen: Optional[Tuple[float, float]] = None
_QUERY_KEYS = ("min_width", "max_width", "min_height", "max_height", "orientation", "theme")


def viewport() -> Tuple[float, float]:
    """The size of the window being drawn, in logical pixels (like ``window.innerWidth``/``innerHeight``).

    Inside ``view()`` it is that window's size; elsewhere the last one drawn (``(0, 0)`` before any).
    """
    return _viewport or (0.0, 0.0)


def _px(value: Any) -> float:
    text = str(value).strip().lower()
    return float(text[:-2] if text.endswith("px") else text)


def _parse_query(text: str) -> Tuple[Tuple[str, Any], ...]:
    """``"(max_width: 600px) and (orientation: portrait)"`` or ``"md"`` as ``((key, value), ...)``."""
    text = text.strip()
    if text in BREAKPOINTS:
        return (("min_width", float(BREAKPOINTS[text])),)
    out = []
    for part in re.split(r"\s+and\s+", text):
        part = part.strip().strip("()").strip()
        key, sep, value = part.partition(":")
        key, value = key.strip().replace("-", "_"), value.strip()
        if not sep or key not in _QUERY_KEYS:
            raise ValueError(f"invalid media query {text!r}: use {', '.join(_QUERY_KEYS)} (\"max_width: 600\"), "
                             f"joined with 'and', or a breakpoint ({', '.join(BREAKPOINTS)})")
        if key == "orientation" and value not in ("portrait", "landscape"):
            raise ValueError(f"orientation is portrait or landscape, not {value!r}")
        if key == "theme" and value not in ("dark", "light"):
            raise ValueError(f"theme is dark or light, not {value!r}")
        out.append((key, value if key in ("orientation", "theme") else _px(value)))
    return tuple(out)


def _matches(conditions: Iterable[Tuple[str, Any]]) -> bool:
    width, height = viewport()
    for key, value in conditions:
        if key == "min_width" and not width >= value:
            return False
        if key == "max_width" and not width <= value:
            return False
        if key == "min_height" and not height >= value:
            return False
        if key == "max_height" and not height <= value:
            return False
        if key == "orientation" and (value == "portrait") != (height > width):
            return False
        if key == "theme":
            try:
                dark = _theme.current().is_dark
            except AttributeError:  # pragma: no cover - every theme says whether it is dark
                dark = True
            if (value == "dark") != bool(dark):
                return False
    return True


def media(query: Optional[str] = None, **conditions: Any) -> bool:
    """Whether the window being drawn matches a media query, like CSS ``@media``.

    ``pz.media("max_width: 600")``, ``pz.media(min_width=768, orientation="landscape")`` or a
    breakpoint name: ``pz.media("md")`` (768 px wide and up).
    """
    parsed = list(_parse_query(query)) if query else []
    for key, value in conditions.items():
        parsed.extend(_parse_query(f"{key}: {value}"))
    return _matches(parsed)


def current_breakpoint() -> str:
    """The widest breakpoint the window reaches: ``"xs"`` (under 640 px), ``"sm"``, ``"md"``,
    ``"lg"``, ``"xl"`` or ``"xxl"``."""
    width = viewport()[0]
    reached = [name for name, at in BREAKPOINTS.items() if width >= at]
    return reached[-1] if reached else "xs"
