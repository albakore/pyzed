"""Animations, transitions and motion for any widget, played natively at full frame rate.

Every widget has ``animate()`` and ``transition()``::

    pz.text("Saved").animate("fade_in_up")                       # plays when it appears
    card.animate("lift", on="hover")                             # forward on hover, back on leave
    icon.animate("pulse", repeat="infinite")                     # loops
    field.animate("shake", key=self.errors)                      # replays when ``key`` changes
    button.animate(on="press", scale=0.96, duration=90)          # ad-hoc: values to animate to
    panel.transition(opacity=1 if self.open else 0, x=0 if self.open else -24)  # like CSS

``animate`` takes preset names (see ``PRESETS``), ``pz.Animation`` objects and options:

- ``on``: what plays it. ``"mount"`` (when the widget appears; the default), ``"hover"``,
  ``"press"``, ``"focus"`` and ``"active"`` (play forward while the condition holds and
  back when it ends), ``"click"`` (from the start on every click).
- ``duration`` and ``delay`` in milliseconds (or ``"0.3s"``/``"300ms"``), ``easing`` (see
  ``EASINGS``, ``(x1, y1, x2, y2)`` for a cubic Bézier, ``"steps(4)"``), ``repeat`` (a
  count or ``"infinite"``), ``direction`` (``"normal"``, ``"reverse"``, ``"alternate"``,
  ``"alternate_reverse"``) and ``fill`` (``"both"``, ``"forwards"``, ``"backwards"``,
  ``"none"``), like CSS.
- ``key``: a new value restarts the animation. ``active``: plays while true.
- ``on_start``/``on_end``: callables or messages sent when it starts and ends.
- Property values (``opacity``, ``x``, ``y``, ``scale``, ``background``, ``border_color``,
  ``color``, ``radius``, ``border_width``, ``glow``, ``glow_color``): without a preset they
  make the animation. On ``mount`` the widget starts from them; on the other triggers it
  goes to them. ``x`` and ``y`` take pixels or ``"50%"`` of the widget's own size.

``Animation(keyframes=...)`` describes any keyframe animation, ``define_animation`` names
one, ``presence`` animates content in and out when it changes, ``stagger`` delays a list
of items one after another and ``set_reduced_motion(True)`` turns motion off (animations
show their resting state); by default it follows the system's "reduce motion" setting.
Windows animate when they open and close with ``Window.transition`` and
``Window.exit_transition``.
"""

from __future__ import annotations

import math
import os
import re
import sys
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from . import _core
from . import style as _style

#: The easing names (also ``(x1, y1, x2, y2)`` cubic Béziers and ``"steps(n)"``).
EASINGS: Tuple[str, ...] = tuple(_core.EASINGS)
#: What plays an animation.
TRIGGERS = ("mount", "hover", "press", "focus", "click", "active")
#: The properties animations and transitions change.
PROPERTIES = ("opacity", "x", "y", "scale", "background", "border_color", "color", "radius",
              "border_width", "glow", "glow_color")
COLOR_PROPERTIES = ("background", "border_color", "color", "glow_color")
DIRECTIONS = ("normal", "reverse", "alternate", "alternate_reverse")
FILLS = ("both", "forwards", "backwards", "none")
#: Preset categories, in the order editors show them.
CATEGORIES = ("entrance", "exit", "attention", "interaction", "loop")

_OPTIONS = ("on", "duration", "delay", "easing", "repeat", "direction", "fill", "key", "active",
            "on_start", "on_end")

Keyframes = Union[Sequence[Mapping[str, Any]], Mapping[Any, Mapping[str, Any]]]


# ---------------------------------------------------------------------------
# Values
# ---------------------------------------------------------------------------

def _ms(value: Any, what: str) -> float:
    """Milliseconds from a number or ``"300ms"``/``"0.3s"``."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < 0:
            raise ValueError(f"{what} can't be negative")
        return float(value)
    if isinstance(value, str):
        text = value.strip().lower()
        try:
            if text.endswith("ms"):
                return _ms(float(text[:-2]), what)
            if text.endswith("s"):
                return _ms(float(text[:-1]) * 1000.0, what)
            return _ms(float(text), what)
        except ValueError:
            pass
    raise ValueError(f"invalid {what} {value!r}: use milliseconds (300) or a string like '0.3s'")


def _easing(value: Any) -> Any:
    """An easing as the native side takes it: a name, ``("cubic_bezier", ...)`` or ``("steps", n)``."""
    if value is None:
        return None
    if isinstance(value, (tuple, list)):
        if len(value) == 4:
            return ("cubic_bezier", *(float(v) for v in value))
        if len(value) == 5 and value[0] == "cubic_bezier":
            return ("cubic_bezier", *(float(v) for v in value[1:]))
        if len(value) == 2 and value[0] == "steps":
            return ("steps", int(value[1]))
        raise ValueError(f"invalid easing {value!r}: use a name or (x1, y1, x2, y2)")
    if isinstance(value, str):
        name = value.strip().lower().replace("-", "_")
        match = re.fullmatch(r"cubic_bezier\(([^)]*)\)", name)
        if match:
            parts = [float(p) for p in match.group(1).split(",")]
            if len(parts) != 4:
                raise ValueError(f"invalid easing {value!r}: cubic-bezier needs four numbers")
            return ("cubic_bezier", *parts)
        match = re.fullmatch(r"steps\((\d+)\)", name)
        if match:
            return ("steps", int(match.group(1)))
        if name in EASINGS:
            return name
    raise ValueError(f"unknown easing {value!r}; available: {', '.join(EASINGS)}, "
                     "(x1, y1, x2, y2) and 'steps(n)'")


def _iterations(value: Any) -> float:
    if value is None:
        return 1.0
    if value is True or value in ("infinite", "forever", "loop"):
        return math.inf
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    raise ValueError(f"invalid repeat {value!r}: use a positive count or 'infinite'")


def _choice(value: Any, choices: Sequence[str], what: str) -> Optional[str]:
    if value is None:
        return None
    name = str(value).replace("-", "_")
    if name not in choices:
        raise ValueError(f"unknown {what} {value!r}; available: {', '.join(choices)}")
    return name


def _value(prop: str, value: Any) -> Any:
    """A property value as the native side takes it (``None`` means the widget's own value)."""
    if prop not in PROPERTIES:
        raise TypeError(f"unknown animated property {prop!r}; available: {', '.join(PROPERTIES)}")
    if value is None:
        return None
    if prop in COLOR_PROPERTIES:
        return _style.to_hex(value)
    if prop in ("x", "y") and isinstance(value, str):
        text = value.strip()
        if text.endswith("%"):
            return ("pct", float(text[:-1]) / 100.0)
        if text.endswith("px"):
            text = text[:-2]
        return float(text)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{prop} must be a number, not {value!r}")
    return float(value)


def _offset(key: Any) -> float:
    if key in ("from", "start"):
        return 0.0
    if key in ("to", "end"):
        return 1.0
    if isinstance(key, str) and key.strip().endswith("%"):
        return float(key.strip()[:-1]) / 100.0
    offset = float(key)
    if not 0.0 <= offset <= 1.0:
        raise ValueError(f"keyframe offsets go from 0 to 1 (or '0%' to '100%'), not {key!r}")
    return offset


def _frames(keyframes: Keyframes) -> List[Tuple[float, Dict[str, Any], Any]]:
    """``[(offset, {prop: value}, easing), ...]`` sorted, from a list or an ``{offset: frame}`` dict."""
    if isinstance(keyframes, Mapping):
        items = [(_offset(k), dict(v)) for k, v in keyframes.items()]
    else:
        items = []
        frames = list(keyframes)
        for i, frame in enumerate(frames):
            frame = dict(frame)
            default = i / (len(frames) - 1) if len(frames) > 1 else 1.0
            items.append((_offset(frame.pop("offset", default)), frame))
    out = []
    for offset, frame in items:
        easing = frame.pop("easing", None)
        for prop in frame:
            if prop not in PROPERTIES:
                raise TypeError(f"unknown animated property {prop!r}; available: {', '.join(PROPERTIES)}")
        out.append((offset, frame, easing))
    if not out:
        raise ValueError("an animation needs at least one keyframe")
    return sorted(out, key=lambda f: f[0])


# ---------------------------------------------------------------------------
# Animation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Animation:
    """A keyframe animation, like a CSS ``@keyframes`` rule with its timing.

    ``keyframes`` is a list of ``{property: value}`` frames (spread evenly; a frame may set
    ``offset`` and ``easing``) or a dict from offsets (``0`` to ``1``, ``"50%"``, ``"from"``,
    ``"to"``) to frames. A property missing at the start or end goes from or to the widget's
    own value, and ``None`` names that value explicitly::

        pz.Animation([{"opacity": 0, "y": 12}, {"opacity": 1, "y": 0}], duration=250)
        pz.Animation({0: {"scale": 1}, "50%": {"scale": 1.1}, 1: {"scale": 1}}, repeat="infinite")

    The other fields are the defaults ``animate()`` options override. ``category`` and
    ``description`` tell editors where and how to show a preset.
    """

    keyframes: Keyframes = field(default=(), compare=False)
    duration: float = 300
    delay: float = 0
    easing: Any = "ease"
    repeat: Any = 1
    direction: str = "normal"
    fill: str = "both"
    on: str = "mount"
    category: str = "custom"
    description: str = ""
    _frames: Tuple[Any, ...] = field(default=(), repr=False)

    def __post_init__(self):
        frames = _frames(self.keyframes)
        for _, frame, easing in frames:
            for prop, value in frame.items():
                _value(prop, value)
            _easing(easing)
        _ms(self.duration, "duration")
        _ms(self.delay, "delay")
        _easing(self.easing)
        _iterations(self.repeat)
        _choice(self.direction, DIRECTIONS, "direction")
        _choice(self.fill, FILLS, "fill")
        _choice(self.on, TRIGGERS, "trigger")
        object.__setattr__(self, "_frames", tuple((o, tuple(sorted(f.items())), e) for o, f, e in frames))

    @property
    def properties(self) -> Tuple[str, ...]:
        """The properties the keyframes change, in order of appearance."""
        seen: Dict[str, None] = {}
        for _, frame, _ in self._frames:
            for prop, _value in frame:
                seen.setdefault(prop, None)
        return tuple(seen)

    @property
    def total(self) -> float:
        """Milliseconds from the start to the end (``inf`` when it repeats forever)."""
        return _ms(self.delay, "delay") + _ms(self.duration, "duration") * _iterations(self.repeat)

    def with_options(self, **options: Any) -> "Animation":
        """A copy with other timing or trigger (``duration``, ``easing``, ``on``...)."""
        return replace(self, **{k: v for k, v in options.items() if v is not None})

    def compile(self, **options: Any) -> Dict[str, Any]:
        """The plain data the native side plays (``animate()`` calls it)."""
        anim = self.with_options(**{k: options.get(k) for k in
                                    ("duration", "delay", "easing", "repeat", "direction", "fill", "on")})
        tracks: Dict[str, List[Tuple[float, Any, Any]]] = {}
        for offset, frame, easing in anim._frames:
            for prop, value in frame:
                tracks.setdefault(prop, []).append((offset, _value(prop, value), _easing(easing)))
        on = anim.on
        if options.get("active") is not None and options.get("on") is None:
            on = "active"
        return {
            "trigger": on,
            "key": None if options.get("key") is None else repr(options["key"]),
            "active": bool(options.get("active")),
            "duration": _ms(anim.duration, "duration"),
            "delay": _ms(anim.delay, "delay"),
            "iterations": _iterations(anim.repeat),
            "direction": anim.direction.replace("-", "_"),
            "fill": anim.fill,
            "easing": _easing(anim.easing),
            "tracks": [(prop, frames) for prop, frames in tracks.items()],
            "on_start": options.get("on_start"),
            "on_end": options.get("on_end"),
        }

    def to_dict(self) -> Dict[str, Any]:
        """JSON-ready data (``Animation.from_dict`` reads it back)."""
        frames = []
        for offset, frame, easing in self._frames:
            out = {"offset": offset, **{k: (list(v) if isinstance(v, tuple) else v) for k, v in frame}}
            if easing is not None:
                out["easing"] = list(easing) if isinstance(easing, tuple) else easing
            frames.append(out)
        data: Dict[str, Any] = {"keyframes": frames, "duration": self.duration}
        defaults = Animation.__dataclass_fields__
        for key in ("delay", "easing", "repeat", "direction", "fill", "on"):
            value = getattr(self, key)
            if value != defaults[key].default:
                data[key] = list(value) if isinstance(value, tuple) else value
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Animation":
        """Rebuilds an animation saved with ``to_dict``."""
        data = dict(data)
        easing = data.get("easing")
        if isinstance(easing, list):
            data["easing"] = tuple(easing)
        frames = []
        for frame in data.pop("keyframes", ()):
            frame = dict(frame)
            if isinstance(frame.get("easing"), list):
                frame["easing"] = tuple(frame["easing"])
            frames.append(frame)
        return cls(keyframes=frames, **{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def _from_props(props: Mapping[str, Any], on: str) -> Animation:
    """The animation ``animate(prop=value)`` makes without a preset."""
    base = {k: None for k in props}
    if on == "mount":
        frames = [dict(props), base]
    elif on == "click":
        frames = [base, dict(props), base]
    else:
        frames = [base, dict(props)]
    return Animation(frames, duration=150 if on in ("hover", "press", "focus") else 300, on=on)


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

_presets: Dict[str, Animation] = {}


def define_animation(name: str, animation: Union[Animation, Keyframes, None] = None, **options: Any) -> Animation:
    """Names an animation so ``animate(name)`` plays it; returns it.

    ``define_animation("wiggle", [{"x": 0}, {"x": -4}, {"x": 4}, {"x": 0}], duration=300)``
    """
    if animation is None:
        animation = Animation(**options)
    elif not isinstance(animation, Animation):
        animation = Animation(animation, **options)
    elif options:
        animation = replace(animation, **options)
    _presets[name] = animation
    return animation


def animation(name: str) -> Animation:
    """The animation named ``name`` (a preset or one defined with ``define_animation``)."""
    try:
        return _presets[name]
    except KeyError:
        raise KeyError(f"no animation named {name!r}; presets: {', '.join(_presets)}") from None


def presets(category: Optional[str] = None) -> Dict[str, Animation]:
    """The named animations (all, or one ``category``: entrance, exit, attention, interaction, loop)."""
    return {n: a for n, a in _presets.items() if category is None or a.category == category}


def _preset(name: str, keyframes: Keyframes, category: str, description: str, **options: Any) -> None:
    _presets[name] = Animation(keyframes, category=category, description=description, **options)


_E = "ease_out_cubic"
for _name, _frames_, _desc in (
    ("fade_in", [{"opacity": 0}, {"opacity": 1}], "Fades in."),
    ("fade_in_up", [{"opacity": 0, "y": 16}, {"opacity": 1, "y": 0}], "Fades in while rising."),
    ("fade_in_down", [{"opacity": 0, "y": -16}, {"opacity": 1, "y": 0}], "Fades in while dropping."),
    ("fade_in_left", [{"opacity": 0, "x": -16}, {"opacity": 1, "x": 0}], "Fades in from the left."),
    ("fade_in_right", [{"opacity": 0, "x": 16}, {"opacity": 1, "x": 0}], "Fades in from the right."),
    ("slide_in_up", [{"y": "100%"}, {"y": 0}], "Slides in from below its own height."),
    ("slide_in_down", [{"y": "-100%"}, {"y": 0}], "Slides in from above."),
    ("slide_in_left", [{"x": "-100%"}, {"x": 0}], "Slides in from the left."),
    ("slide_in_right", [{"x": "100%"}, {"x": 0}], "Slides in from the right."),
    ("zoom_in", [{"opacity": 0, "scale": 0.92}, {"opacity": 1, "scale": 1}], "Grows in from slightly smaller."),
):
    _preset(_name, _frames_, "entrance", _desc, duration=280, easing=_E)
_preset("pop_in", {0: {"opacity": 0, "scale": 0.8}, 0.6: {"opacity": 1, "scale": 1.04}, 1: {"scale": 1}},
        "entrance", "Pops in with a small overshoot.", duration=320, easing="ease_out")
_preset("bounce_in", {0: {"opacity": 0, "scale": 0.3}, 0.5: {"opacity": 1, "scale": 1.08},
                      0.7: {"scale": 0.94}, 1: {"scale": 1}},
        "entrance", "Bounces in from small.", duration=600, easing="ease_out")
_preset("drop_in", [{"opacity": 0, "y": "-40%"}, {"opacity": 1, "y": 0}], "entrance",
        "Falls into place with a bounce.", duration=520, easing="ease_out_bounce")
_preset("blur_in", [{"opacity": 0, "scale": 1.06}, {"opacity": 1, "scale": 1}], "entrance",
        "Settles in from slightly larger, like a lens focusing.", duration=360, easing=_E)

for _name, _frames_, _desc in (
    ("fade_out", [{"opacity": 1}, {"opacity": 0}], "Fades out."),
    ("fade_out_up", [{"opacity": 1, "y": 0}, {"opacity": 0, "y": -16}], "Fades out while rising."),
    ("fade_out_down", [{"opacity": 1, "y": 0}, {"opacity": 0, "y": 16}], "Fades out while dropping."),
    ("fade_out_left", [{"opacity": 1, "x": 0}, {"opacity": 0, "x": -16}], "Fades out to the left."),
    ("fade_out_right", [{"opacity": 1, "x": 0}, {"opacity": 0, "x": 16}], "Fades out to the right."),
    ("slide_out_up", [{"y": 0}, {"y": "-100%"}], "Slides out upwards."),
    ("slide_out_down", [{"y": 0}, {"y": "100%"}], "Slides out downwards."),
    ("slide_out_left", [{"x": 0}, {"x": "-100%"}], "Slides out to the left."),
    ("slide_out_right", [{"x": 0}, {"x": "100%"}], "Slides out to the right."),
    ("zoom_out", [{"opacity": 1, "scale": 1}, {"opacity": 0, "scale": 0.92}], "Shrinks away."),
):
    _preset(_name, _frames_, "exit", _desc, duration=220, easing="ease_in_cubic")
_preset("pop_out", {0: {"scale": 1}, 0.35: {"scale": 1.04, "opacity": 1}, 1: {"opacity": 0, "scale": 0.8}},
        "exit", "Swells a little, then pops away.", duration=260, easing="ease_in")

_preset("pulse", {0: {"scale": 1}, 0.5: {"scale": 1.05}, 1: {"scale": 1}}, "attention",
        "Grows and shrinks once.", duration=600, easing="ease_in_out")
_preset("heartbeat", {0: {"scale": 1}, 0.14: {"scale": 1.15}, 0.28: {"scale": 1}, 0.42: {"scale": 1.15},
                      0.7: {"scale": 1}}, "attention", "Two quick beats.", duration=1000, easing="ease_in_out")
_preset("shake", {0: {"x": 0}, 0.1: {"x": -6}, 0.3: {"x": 6}, 0.5: {"x": -6}, 0.7: {"x": 6}, 0.9: {"x": -3},
                  1: {"x": 0}}, "attention", "Shakes sideways (wrong input).", duration=450, easing="ease_in_out")
_preset("wobble", {0: {"x": 0}, 0.15: {"x": -12}, 0.3: {"x": 10}, 0.45: {"x": -8}, 0.6: {"x": 6},
                   0.75: {"x": -2}, 1: {"x": 0}}, "attention", "Wobbles and settles.", duration=800, easing="ease")
_preset("bounce", {0: {"y": 0}, 0.2: {"y": 0}, 0.4: {"y": -14}, 0.5: {"y": -14}, 0.6: {"y": 0}, 0.75: {"y": -6},
                   0.9: {"y": 0}, 1: {"y": 0}}, "attention", "Jumps twice.", duration=900, easing="ease_in_out")
_preset("flash", {0: {"opacity": 1}, 0.25: {"opacity": 0}, 0.5: {"opacity": 1}, 0.75: {"opacity": 0},
                  1: {"opacity": 1}}, "attention", "Blinks twice.", duration=800, easing="linear")
_preset("rubber_band", {0: {"scale": 1}, 0.3: {"scale": 1.12}, 0.45: {"scale": 0.94}, 0.6: {"scale": 1.05},
                        0.75: {"scale": 0.98}, 1: {"scale": 1}}, "attention", "Stretches and snaps back.",
        duration=800, easing="ease")
_preset("tada", {0: {"scale": 1}, 0.1: {"scale": 0.92}, 0.3: {"scale": 1.08}, 0.5: {"scale": 1.08},
                 0.8: {"scale": 1.04}, 1: {"scale": 1}}, "attention", "A celebratory pop.", duration=900)
_preset("glow_flash", {0: {"glow": 0}, 0.3: {"glow": 22}, 1: {"glow": 0}}, "attention",
        "A burst of glow around the box.", duration=700, easing="ease_out")

_preset("lift", [{"y": 0, "glow": None}, {"y": -2, "glow": 10}], "interaction",
        "Rises with a soft glow (for cards and buttons).", duration=160, easing=_E, on="hover")
_preset("grow", [{"scale": 1}, {"scale": 1.05}], "interaction", "Grows a little.",
        duration=160, easing=_E, on="hover")
_preset("shrink", [{"scale": 1}, {"scale": 0.96}], "interaction", "Presses in (for press).",
        duration=90, easing="ease_out", on="press")
_preset("dim", [{"opacity": 1}, {"opacity": 0.6}], "interaction", "Fades a little.",
        duration=160, easing="ease_out", on="hover")
_preset("glow", [{"glow": None}, {"glow": 14}], "interaction", "Glows around the box.",
        duration=200, easing=_E, on="hover")
_preset("bloom", [{"glow": None, "scale": 1}, {"glow": 28, "scale": 1.02}], "interaction",
        "A strong, wide glow that blooms out of the box.", duration=260, easing=_E, on="hover")
_preset("nudge_right", [{"x": 0}, {"x": 4}], "interaction", "Moves a little to the right (links, chevrons).",
        duration=140, easing=_E, on="hover")

_preset("float", {0: {"y": 0}, 0.5: {"y": -6}, 1: {"y": 0}}, "loop", "Floats up and down.",
        duration=2400, easing="ease_in_out_sine", repeat="infinite")
_preset("breathe", {0: {"opacity": 1, "scale": 1}, 0.5: {"opacity": 0.65, "scale": 0.98},
                    1: {"opacity": 1, "scale": 1}}, "loop", "Slowly fades and shrinks, like breathing.",
        duration=3000, easing="ease_in_out_sine", repeat="infinite")
_preset("blink", {0: {"opacity": 1}, 0.5: {"opacity": 0.15}, 1: {"opacity": 1}}, "loop",
        "Blinks (status lights, cursors).", duration=1000, easing="ease_in_out", repeat="infinite")
_preset("glow_pulse", {0: {"glow": 2}, 0.5: {"glow": 16}, 1: {"glow": 2}}, "loop",
        "The glow swells and fades (recording, live).", duration=1600, easing="ease_in_out_sine",
        repeat="infinite")
_preset("throb", {0: {"scale": 1}, 0.5: {"scale": 1.08}, 1: {"scale": 1}}, "loop",
        "Pulses forever (notifications).", duration=1200, easing="ease_in_out", repeat="infinite")
_preset("drift", {0: {"x": 0}, 0.5: {"x": 6}, 1: {"x": 0}}, "loop", "Drifts sideways.",
        duration=3000, easing="ease_in_out_sine", repeat="infinite")

#: The presets, by name (``define_animation`` adds more).
PRESETS = _presets

#: Window transitions: a name for ``Window.transition`` -> (opening, closing) presets.
WINDOW_TRANSITIONS: Dict[str, Tuple[str, str]] = {
    "fade": ("fade_in", "fade_out"),
    "zoom": ("zoom_in", "zoom_out"),
    "pop": ("pop_in", "pop_out"),
    "slide_up": ("fade_in_up", "fade_out_down"),
    "slide_down": ("fade_in_down", "fade_out_up"),
    "slide_left": ("fade_in_right", "fade_out_left"),
    "slide_right": ("fade_in_left", "fade_out_right"),
}


# ---------------------------------------------------------------------------
# Compiling `animate` and `transition` calls
# ---------------------------------------------------------------------------

def _as_animation(item: Any) -> Animation:
    if isinstance(item, Animation):
        return item
    if isinstance(item, str):
        return animation(item)
    if isinstance(item, Mapping):
        return Animation.from_dict(item)
    raise TypeError(f"an animation is a preset name, a pz.Animation or a dict, not {type(item).__name__}")


def _flatten(items: Iterable[Any]) -> List[Any]:
    out: List[Any] = []
    for item in items:
        if isinstance(item, (list, tuple)):
            out.extend(_flatten(item))
        elif item is not None:
            out.append(item)
    return out


def _compile(animations: Sequence[Any], options: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """What ``Widget.animate`` passes to the native side: one dict per animation."""
    options = dict(options or {})
    props = {k: options.pop(k) for k in list(options) if k in PROPERTIES}
    unknown = [k for k in options if k not in _OPTIONS]
    if unknown:
        raise TypeError(f"unknown animate() option {unknown[0]!r}; options: {', '.join(_OPTIONS)}; "
                        f"properties: {', '.join(PROPERTIES)}")
    on = _choice(options.get("on"), TRIGGERS, "trigger")
    if on is not None:
        options["on"] = on
    items = [_as_animation(a) for a in _flatten(animations)]
    if props:
        if items:
            raise TypeError("animate() takes presets or property values, not both: "
                            "use pz.Animation(...) for a custom animation")
        trigger = on or ("active" if options.get("active") is not None else "mount")
        items = [_from_props(props, trigger)]
    return [a.compile(**options) for a in items]


def _compile_transition(props: Optional[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """What ``Widget.transition`` passes to the native side: one dict per property."""
    props = dict(props or {})
    duration = _ms(props.pop("duration", 200), "duration")
    delay = _ms(props.pop("delay", 0), "delay")
    easing = _easing(props.pop("easing", "ease_out"))
    out = []
    for prop, value in props.items():
        timing = (duration, delay, easing)
        if isinstance(value, Mapping):  # per-property timing: {"value": 1, "duration": 400}
            value = dict(value)
            timing = (_ms(value.get("duration", duration), "duration"), _ms(value.get("delay", delay), "delay"),
                      _easing(value.get("easing", easing)))
            value = value.get("value")
        out.append({"prop": prop, "value": _value(prop, value), "duration": timing[0], "delay": timing[1],
                    "easing": timing[2]})
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ease(easing: Any, t: float) -> float:
    """``easing`` at ``t`` (0 to 1), the curve animations use: ``ease("ease_out", 0.5)``.

    Handy to animate your own drawings (``pz.canvas``) with the same curves.
    """
    value = _easing(easing)
    return _core.ease("ease" if value is None else value, float(t))


def presence(content: Any, key: Any, *, enter: Any = "fade_in", exit: Any = "fade_out",
             id: Optional[str] = None, duration: Any = None, easing: Any = None) -> _core.Widget:
    """Shows ``content`` and, when ``key`` changes, animates the old content out (``exit``)
    while the new one comes in (``enter``), like page transitions::

        pz.presence(self.page_view(), key=self.page, enter="slide_in_right", exit="fade_out")

    ``id`` tells presences apart (it defaults to where it is called from, so give one when
    the same line makes several). ``duration`` and ``easing`` override both animations'.
    """
    if id is None:
        frame = sys._getframe(1)
        id = f"{frame.f_code.co_filename}:{frame.f_lineno}"
    options = {"duration": duration, "easing": easing}
    enter_list = _compile([enter], options) if enter else []
    exit_list = _compile([exit], options) if exit else []
    for anim in (*enter_list, *exit_list):
        anim["trigger"] = "mount"
    return _core.presence(content, id=str(id), key=repr(key), enter=enter_list, exit=exit_list)


def stagger(items: Iterable[Any], animation: Any = "fade_in_up", *, step: Any = 40, delay: Any = 0,
            **options: Any) -> List[_core.Widget]:
    """``items`` with the same animation, each starting ``step`` milliseconds after the previous
    one (a list that cascades in)::

        pz.column(pz.stagger([row(i) for i in items], "fade_in_up", step=30))
    """
    step_ms, start = _ms(step, "step"), _ms(delay, "delay")
    out = []
    for i, item in enumerate(items):
        if not isinstance(item, _core.Widget):
            item = _core.container(item)
        out.append(item.animate(animation, delay=start + i * step_ms, **options))
    return out


#: ``True``/``False`` once the app or ``PYZED_REDUCED_MOTION`` chose; ``None`` follows the system.
_reduced_motion_choice: Optional[bool] = None


def set_reduced_motion(on: Optional[bool] = True) -> None:
    """Turns motion off (``True``) or back on: animations show their resting state at once.

    By default Pyzed follows the system's "reduce motion" accessibility setting (read when
    the app starts, see ``pyzed.system_reduced_motion``). ``True`` or ``False`` overrides it
    (for example from your app's own settings, or in tests) and ``None`` follows the system
    again. The ``PYZED_REDUCED_MOTION`` environment variable (``1`` or ``0``) overrides it too.
    """
    global _reduced_motion_choice
    _reduced_motion_choice = None if on is None else bool(on)
    if on is None:
        _follow_system()
    else:
        _core.set_reduced_motion(bool(on))


def reduced_motion() -> bool:
    """Whether reduced motion is on."""
    return _core.reduced_motion()


def _follow_system() -> None:
    """Applies the system preference unless the app or the environment chose (called by ``run``)."""
    if _reduced_motion_choice is not None:
        return
    from .accessibility import system_reduced_motion

    _core.set_reduced_motion(bool(system_reduced_motion()))


_env = os.environ.get("PYZED_REDUCED_MOTION", "").strip().lower()
if _env in ("1", "true", "yes", "on"):
    set_reduced_motion(True)
elif _env in ("0", "false", "no", "off"):
    set_reduced_motion(False)
del _env


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _window_pair(value: Any, closing: bool) -> Any:
    if isinstance(value, str) and value in WINDOW_TRANSITIONS:
        return WINDOW_TRANSITIONS[value][1 if closing else 0]
    return value


def window_animations(window: Any, closing: bool = False) -> List[Any]:
    """The animation a window plays when it opens (or closes), from its ``transition`` and
    ``exit_transition`` (an empty list when it has none)."""
    enter = getattr(window, "transition", None)
    if not closing:
        return [_window_pair(enter, False)] if enter else []
    exit = getattr(window, "exit_transition", None)
    if exit is None and isinstance(enter, str) and enter in WINDOW_TRANSITIONS:
        exit = enter
    return [_window_pair(exit, True)] if exit else []


def _window_root(window: Any, root: Any) -> Any:
    """The window's view with its opening or closing animation."""
    closing = bool(getattr(window, "_pyzed_closing", False))
    anims = window_animations(window, closing)
    if not anims or not isinstance(root, _core.Widget):
        return root
    return root.animate(*anims, fill="both")


def _window_exit(window: Any) -> float:
    """Marks ``window`` as closing and returns how long (seconds) its exit animation runs."""
    anims = window_animations(window, True)
    if not anims or getattr(window, "_pyzed_closing", False):
        return 0.0
    window._pyzed_closing = True
    total = max(_as_animation(a).total for a in anims)
    return 0.0 if math.isinf(total) else total / 1000.0


__all__ = [
    "Animation", "CATEGORIES", "EASINGS", "PRESETS", "PROPERTIES", "TRIGGERS", "WINDOW_TRANSITIONS",
    "animation", "define_animation", "ease", "presence", "presets", "reduced_motion", "set_reduced_motion",
    "stagger", "window_animations",
]
