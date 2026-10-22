"""Animations and effects of designed controls: what the Animation section edits and how it plays.

A control keeps its animations in ``Control.animations``, a list of plain dicts saved in the
``.pzform``::

    {"preset": "fade_in_up", "on": "mount", "duration": 280, "delay": 0, "easing": "ease_out_cubic",
     "repeat": 1}

Only ``preset`` is required; the other keys override the preset's own timing. Effects
(``opacity``, ``glow``, ``bloom``, ``glass``) are style properties, saved in ``Control.style``.

The running form plays every animation. The designer's canvas stays still while you edit
and plays a control's animations when you press Preview (``preview`` maps control names to
a counter that restarts them).

An entry with ``"on": "manual"`` waits for the form's code: ``form.title.play_animation()``
plays it (and replays the ones that play when the control appears), and
``form.title.play_animation("shake")`` plays any preset once. ``Played`` keeps that state.

Other triggers play once on each event of the control (a double click, the pointer entering
or leaving, a new value, Enter, a failed validation rule) or of another control or the form
(``{"on": "event", "source": "save", "event": "click"}``, ``"source": ""`` for the form). The
running form counts the events (``Played.fired``) and replays the animation on each one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .. import animation as _animation

#: The triggers the Animation section offers, in order, with their labels.
TRIGGERS: Tuple[Tuple[str, str], ...] = (
    ("mount", "When it appears"),
    ("hover", "While hovered"),
    ("press", "While pressed"),
    ("focus", "While focused"),
    ("click", "On click"),
    ("double_click", "On double click"),
    ("right_click", "On right click"),
    ("enter", "When the pointer enters"),
    ("leave", "When the pointer leaves"),
    ("change", "When its value changes"),
    ("submit", "When Enter is pressed"),
    ("invalid", "When its value is invalid"),
    ("event", "On another control's event"),
    ("manual", "When played from code"),
)
TRIGGER_LABELS = dict(TRIGGERS)
#: Triggers that play once each time an event happens, and the control's event that plays them ("invalid" is
#: raised when a validation rule fails; "event" names the control and event in the entry: ``source``,
#: ``event``). The running form counts the events (``Played.fired``) and replays the animation on each one.
EVENT_TRIGGERS = {"double_click": "double_click", "right_click": "right_click", "enter": "mouse_enter",
                  "leave": "mouse_leave", "change": "change", "submit": "submit", "invalid": "invalid",
                  "event": ""}
#: What a form's event wiring gets for an event only an animation listens to: the running form raises it, and
#: the dispatcher plays the animations without looking for a handler.
ANIMATION_ONLY = "·animation"
#: The easings offered first (every name in ``pz.animation.EASINGS`` is valid).
EASINGS = ("ease", "linear", "ease_in", "ease_out", "ease_in_out", "ease_out_cubic", "ease_in_out_sine",
           "ease_out_back", "ease_out_elastic", "ease_out_bounce", "spring")
#: The repeat counts offered ("infinite" loops).
REPEATS = ("1", "2", "3", "5", "infinite")
#: The category each trigger suggests first in the preset list.
SUGGESTED = {"mount": "entrance", "hover": "interaction", "press": "interaction", "focus": "interaction",
             "click": "attention", "manual": "attention", **{k: "attention" for k in EVENT_TRIGGERS}}
CATEGORY_LABELS = {"entrance": "Entrance", "exit": "Exit", "attention": "Attention", "interaction": "Interaction",
                   "loop": "Loop"}


def label(name: str) -> str:
    """A preset's name as people read it: ``"fade_in_up"`` -> ``"Fade in up"``."""
    return name.replace("_", " ").capitalize()


def presets_for(trigger: str) -> List[str]:
    """Preset names, the ones that suit ``trigger`` first, then the rest by category."""
    first = SUGGESTED.get(trigger, "entrance")
    names = list(_animation.presets(first))
    for category in _animation.CATEGORIES:
        if category != first:
            names.extend(_animation.presets(category))
    return names


def new_entry(trigger: str = "mount") -> Dict[str, Any]:
    """The animation a new row starts with for ``trigger``."""
    preset = {"mount": "fade_in_up", "hover": "lift", "press": "shrink", "focus": "glow", "click": "pulse",
              "manual": "pulse", "invalid": "shake", "change": "pulse", "enter": "rubber_band",
              "leave": "pulse", "submit": "pulse", "double_click": "tada", "right_click": "pulse",
              "event": "pulse"}.get(trigger, "pulse")
    entry: Dict[str, Any] = {"preset": preset, "on": trigger}
    if trigger == "event":
        entry.update(source="", event="click")
    return entry


#: Ready-made animations the Animation section offers in one click: label, trigger, preset and the events a
#: control must have for it to make sense (empty: any control).
RECIPES: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...] = (
    ("Fade in when it appears", "mount", "fade_in_up", ()),
    ("Lift on hover", "hover", "lift", ()),
    ("Pulse on click", "click", "pulse", ("click",)),
    ("Press in while pressed", "press", "shrink", ("click",)),
    ("Bounce when the value changes", "change", "rubber_band", ("change",)),
    ("Shake when the value is invalid", "invalid", "shake", ("change",)),
    ("Float forever", "mount", "float", ()),
)


def recipes_for(events: Tuple[str, ...]) -> List[Tuple[str, str, str]]:
    """The recipes that suit a control with ``events``: ``(label, trigger, preset)``."""
    return [(label, trigger, preset) for label, trigger, preset, needs in RECIPES
            if all(e in events for e in needs)]


def listens(entry: Mapping[str, Any], owner: str) -> Optional[Tuple[str, str]]:
    """``(control, event)`` an entry plays on (``""`` names the form), or ``None`` for the triggers the
    widget plays by itself (appearing, hover, press, focus, click) and from code."""
    trigger = str(entry.get("on") or "")
    if trigger not in EVENT_TRIGGERS:
        return None
    if trigger == "event":
        event = str(entry.get("event") or "")
        return (str(entry.get("source") or ""), event) if event else None
    return (owner, EVENT_TRIGGERS[trigger])


def listeners(controls: Any) -> Dict[Tuple[str, str], List[Tuple[str, int]]]:
    """Which animations each event plays: ``{(source, event): [(control, index), ...]}`` over ``controls``."""
    out: Dict[Tuple[str, str], List[Tuple[str, int]]] = {}
    for control in controls:
        for index, entry in enumerate(control.animations or ()):
            key = listens(entry, control.name)
            if key is not None:
                out.setdefault(key, []).append((control.name, index))
    return out


def preset_of(entry: Mapping[str, Any]) -> Optional[_animation.Animation]:
    """The preset an entry plays (``None`` when it names an unknown one)."""
    try:
        return _animation.animation(str(entry.get("preset", "")))
    except KeyError:
        return None


def timing(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """The entry's effective ``on``, ``duration``, ``delay``, ``easing`` and ``repeat`` (its own, or the preset's)."""
    preset = preset_of(entry)
    defaults = {"on": preset.on if preset else "mount", "duration": preset.duration if preset else 300,
                "delay": preset.delay if preset else 0, "easing": preset.easing if preset else "ease",
                "repeat": preset.repeat if preset else 1}
    out = dict(defaults)
    for key in defaults:
        if entry.get(key) not in (None, ""):
            out[key] = entry[key]
    return out


def repeat_text(value: Any) -> str:
    """How a repeat count shows in the drop-down."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "infinite" if value in ("infinite", True) else "1"
    if math.isinf(number):
        return "infinite"
    return str(int(number)) if number.is_integer() else f"{number:g}"


def summary(entry: Mapping[str, Any]) -> str:
    """A one-line description: ``"Fade in up · 280 ms"``."""
    t = timing(entry)
    repeat = repeat_text(t["repeat"])
    parts = [label(str(entry.get("preset", "?"))), f"{_num(t['duration'])} ms"]
    if float(t["delay"] or 0):
        parts.append(f"+{_num(t['delay'])} ms")
    if repeat != "1":
        parts.append("∞" if repeat == "infinite" else f"×{repeat}")
    return " · ".join(parts)


def _num(value: Any) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def options(entry: Mapping[str, Any]) -> Dict[str, Any]:
    """The ``animate()`` options an entry gives (only what it sets)."""
    out: Dict[str, Any] = {}
    for key in ("on", "duration", "delay", "easing"):
        if entry.get(key) not in (None, ""):
            out[key] = entry[key]
    if entry.get("repeat") not in (None, ""):
        out["repeat"] = "infinite" if repeat_text(entry["repeat"]) == "infinite" else float(entry["repeat"])
    return out


@dataclass
class Played:
    """What a running form's code asked a control to play (``form.title.play_animation(...)``)."""

    #: How many times ``play_animation`` was called: a new count plays again.
    count: int = 0
    #: The animations ``play_animation("shake")`` plays besides the control's own.
    extra: List[Any] = field(default_factory=list)
    #: ``stop_animation()`` was called: the control's "from code" animations and the extra ones stop.
    stopped: bool = False
    #: How many times the event of each of the control's event-triggered animations happened, by index.
    fired: Dict[int, int] = field(default_factory=dict)

    def fire(self, index: int) -> None:
        self.fired[index] = self.fired.get(index, 0) + 1

    def play(self, animation: Any = None, **opts: Any) -> None:
        self.count += 1
        self.stopped = False
        self.extra = [] if animation is None else [(animation, opts)]

    def stop(self) -> None:
        self.stopped = True
        self.extra = []


def apply(widget: Any, animations: Optional[List[Mapping[str, Any]]], *, preview: Optional[int] = None,
          played: Optional[Played] = None) -> Any:
    """``widget`` with a control's animations. ``preview`` (the designer's Preview counter) plays
    them all once, as if the control had just appeared; ``played`` is what the form's code asked
    for (``form.title.play_animation()``). Invalid entries are skipped."""
    for index, entry in enumerate(animations or ()):
        preset = preset_of(entry)
        if preset is None:
            continue
        opts = options(entry)
        on = timing(entry)["on"]
        if preview is not None:
            opts["on"] = "mount"
            opts["key"] = preview
        elif on in EVENT_TRIGGERS:  # waits for its event, then plays from the start on each one
            opts["on"] = "manual"
            opts["key"] = played.fired.get(index, 0) if played is not None else 0
        elif played is not None and played.count and on in ("mount", "manual"):
            if played.stopped and on == "manual":
                continue
            opts["key"] = played.count  # play_animation() plays them again
        try:
            widget = widget.animate(preset, **opts)
        except (TypeError, ValueError):
            continue
    if played is not None and preview is None:
        for animation, opts in played.extra:
            # a new animation plays as it is added; the same one again plays because its key changed
            widget = widget.animate(animation, **{**opts, "on": "mount", "key": played.count})
    return widget


def moves(animations: Optional[List[Mapping[str, Any]]], style: Optional[Mapping[str, Any]] = None) -> bool:
    """Whether a control draws outside its box (animations, glow, bloom, glass or a shadow), so its
    frame must not clip it."""
    style = style or {}
    return bool(animations) or any(style.get(k) for k in ("shadow", "glow", "bloom", "glass", "translate", "scale",
                                                                "rotate", "blur"))


# -- effects (style properties) --------------------------------------------------------


def glow_parts(value: Any, default_size: float) -> Tuple[str, float]:
    """``(color, size)`` of a saved ``glow`` or ``bloom`` (an empty color when it is off)."""
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return str(value[0] or ""), float(value[1])
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "accent", float(value)
    if isinstance(value, str) and value:
        return value, default_size
    return "", default_size


def glow_value(color: str, size: float) -> Optional[List[Any]]:
    """A glow or bloom as it is saved, ``[color, size]``, or ``None`` when ``color`` is empty."""
    color = (color or "").strip()
    if not color:
        return None
    size = float(size)
    return [color, int(size) if size.is_integer() else size]


def glass_parts(value: Any) -> Tuple[bool, str, float]:
    """``(on, tint, strength)`` of a saved ``glass``."""
    if isinstance(value, Mapping):
        return True, str(value.get("tint") or "#ffffff"), float(value.get("strength", 0.08))
    if isinstance(value, str) and value:
        return True, value, 0.08
    return bool(value), "#ffffff", 0.08


def glass_value(on: bool, tint: str, strength: float) -> Any:
    """A glass effect as it is saved (``None`` when off, ``True`` for the default tint)."""
    if not on:
        return None
    tint = (tint or "").strip() or "#ffffff"
    if tint.lower() in ("#ffffff", "#fff", "white") and abs(strength - 0.08) < 1e-6:
        return True
    return {"tint": tint, "strength": round(float(strength), 3)}
