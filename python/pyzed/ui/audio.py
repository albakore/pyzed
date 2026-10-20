"""Audio components: knobs, faders, pads, LED buttons, a step sequencer, a piano keyboard,
VU meters, waveforms, an oscilloscope, a spectrum analyzer and a spectrogram.

    from pyzed import ui

    ui.audio.Knob(value=self.cutoff, min=20, max=20000, curve="log", unit="Hz", caption="Cutoff",
                  on_change=lambda e: setattr(self, "cutoff", e.value))
    ui.audio.Spectrum(node.spectrum(256), variant="blocks", colors="fl")

They only take numbers and lists of numbers and report what the user does with events, so
they work with Pyzed's audio engine (``node.scope()``, ``node.spectrum()``, ``node.level()``,
``engine.note_on()``) or with any other source: a file, a MIDI device, a sensor. Every color
is a theme token or a hex color, and the look of each one can be switched with ``variant``.

Controls keep the value the user sets even if the parent does not store it (uncontrolled), and
follow the parent when it passes a new ``value`` (controlled).
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Literal, NamedTuple, Optional, Sequence, Tuple

from .. import _core, draw
from ..component import Component
from ..style import to_hex
from ..theme import alpha as _alpha
from ..theme import current as _current_theme
from ..theme import mix as _mix

__all__ = [
    "KEYBOARD",
    "PALETTES",
    "Fader",
    "Knob",
    "LedButton",
    "Note",
    "Pad",
    "Piano",
    "Scope",
    "Spectrogram",
    "Spectrum",
    "StepSequencer",
    "VuMeter",
    "Waveform",
    "format_value",
    "note_name",
]

#: Color ramps for meters and analyzers, from quiet/low to loud/high.
PALETTES: Dict[str, List[str]] = {
    "fl": ["#3dd68c", "#a6e35a", "#f5d547", "#ff9f3d", "#ff4d4d"],
    "neon": ["#00e5ff", "#7c4dff", "#ff2bd6"],
    "fire": ["#2b0a3d", "#a3204a", "#f06a26", "#ffd23f", "#fffbe6"],
    "ice": ["#0b1d3a", "#1565c0", "#4fc3f7", "#e1f5fe"],
    "magma": ["#000004", "#3b0f70", "#8c2981", "#de4968", "#fe9f6d", "#fcfdbf"],
    "viridis": ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
    "mono": ["#5b6370", "#dce0e5"],
    "vu": ["#3dd68c", "#3dd68c", "#3dd68c", "#f5d547", "#ff4d4d"],
    "scope": ["#3dd68c", "#f5d547", "#4fc3f7", "#ff6b9d"],
}

#: Computer keys that play notes, like a piano (semitones above the keyboard's first C).
KEYBOARD: Dict[str, int] = {
    "a": 0, "w": 1, "s": 2, "e": 3, "d": 4, "f": 5, "t": 6, "g": 7, "y": 8, "h": 9, "u": 10, "j": 11,
    "k": 12, "o": 13, "l": 14, "p": 15, ";": 16,
}

_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_BLACK = {1, 3, 6, 8, 10}


def _now() -> float:
    """The clock meters use for peak hold and falloff (the docs' recorder replaces it)."""
    return time.monotonic()


def note_name(note: int) -> str:
    """A MIDI note number as a name: ``60`` is ``"C4"``, ``69`` is ``"A4"``."""
    return f"{_NAMES[note % 12]}{note // 12 - 1}"


def format_value(value: float, unit: str = "", decimals: Optional[int] = None) -> str:
    """A value with its unit, short enough for a knob: ``1.2 kHz``, ``-6.0 dB``, ``250 ms``, ``75%``."""
    if unit == "%":
        return f"{value * 100 if abs(value) <= 1 else value:.0f}%"
    if unit in ("Hz", "hz") and abs(value) >= 1000:
        return f"{value / 1000:.{1 if decimals is None else decimals}f} kHz"
    if unit == "ms" and abs(value) >= 1000:
        return f"{value / 1000:.2f} s"
    if decimals is None:
        decimals = 0 if abs(value) >= 100 else 1 if abs(value) >= 10 else 2
    text = f"{value:.{decimals}f}"
    return f"{text} {unit}" if unit else text


# -- helpers ---------------------------------------------------------------------------------------
def _color(value: Any) -> str:
    return to_hex(value)


def _ramp(colors: Sequence[str], t: float) -> str:
    """The color at ``t`` (0..1) along ``colors``."""
    if len(colors) == 1:
        return colors[0]
    t = min(max(t, 0.0), 1.0) * (len(colors) - 1)
    i = min(int(t), len(colors) - 2)
    return _mix(colors[i], colors[i + 1], t - i)


def _palette(colors: Any, fallback: str = "fl") -> List[str]:
    if colors is None:
        colors = fallback
    if isinstance(colors, str):
        if colors in PALETTES:
            return PALETTES[colors]
        return [_color(colors)]
    return [_color(c) for c in colors]


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return min(max(value, lo), hi)


def _to_unit(value: float, lo: float, hi: float, curve: str) -> float:
    """``value`` as a fraction of the range ``lo..hi`` (``curve="log"`` for frequencies)."""
    if hi == lo:
        return 0.0
    if curve == "log" and lo > 0 and hi > 0:
        return _clamp(math.log(max(value, lo) / lo) / math.log(hi / lo))
    return _clamp((value - lo) / (hi - lo))


def _from_unit(t: float, lo: float, hi: float, curve: str) -> float:
    t = _clamp(t)
    if curve == "log" and lo > 0 and hi > 0:
        return lo * (hi / lo) ** t
    return lo + (hi - lo) * t


def _results(*results: Any) -> Any:
    """What several handlers returned, as one result for the runtime (``None`` when none returned anything)."""
    kept = [r for r in results if r is not None]
    return kept[0] if len(kept) == 1 else (kept or None)


def _numbers(values: Any) -> List[float]:
    """``values`` as floats; text (as the designer passes lists) is parsed and anything else skipped."""
    if values is None:
        return []
    if isinstance(values, (int, float)):
        return [float(values)]
    if isinstance(values, str):
        values = values.replace(",", " ").split()
    out = []
    for v in values:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            continue
    return out


def _db(level: float) -> float:
    return 20 * math.log10(level) if level > 1e-9 else -180.0


class _Valued(Component):
    """A control with a numeric ``value`` in ``min..max`` it can change by itself."""

    value: float = 0.0
    min: float = 0.0
    max: float = 1.0
    default: Optional[float] = None
    step: Optional[float] = None
    curve: Literal["lin", "log"] = "lin"
    caption: str = ""
    unit: str = ""
    decimals: Optional[int] = None
    color: str = "accent"
    disabled: bool = False
    events = {"change": "The user moved it (``event.value`` is the new value)."}
    designer = False

    def setup(self) -> None:
        self._prop = self.value
        self._local: Optional[float] = None
        self._drag_t: Optional[float] = None
        self.active = False
        self.hovered = False

    # the value shown: the parent's, or the one the user set if the parent did not store it
    def shown(self) -> float:
        """The value being shown: the user's last change, or the parent's ``value`` if it changed since."""
        if self.value != self._prop:
            self._prop, self._local = self.value, None
        value = self._local if self._local is not None else self.value
        return min(max(value, min(self.min, self.max)), max(self.min, self.max))

    def unit_value(self) -> float:
        """The shown value as 0..1 along the control's travel."""
        return _to_unit(self.shown(), self.min, self.max, self.curve)

    def display(self) -> str:
        """The shown value formatted with its unit."""
        return format_value(self.shown(), self.unit, self.decimals)

    def put(self, value: float) -> Any:
        """Sets the value (snapped to ``step``, kept in range) and emits ``change`` if it moved."""
        lo, hi = min(self.min, self.max), max(self.min, self.max)
        if self.step:
            value = self.min + round((value - self.min) / self.step) * self.step
        value = round(min(max(value, lo), hi), 9)
        if value == self.shown():
            return None
        self._local = value
        return self.emit("change", value)

    def put_unit(self, t: float) -> Any:
        return self.put(_from_unit(t, self.min, self.max, self.curve))

    def reset(self) -> Any:
        """Goes back to ``default`` (or the start of the range)."""
        return self.put(self.min if self.default is None else self.default)

    # pointer handlers shared by knobs and faders
    def _start(self, _e: Any = None) -> None:
        self._drag_t = self.unit_value()
        self.active = True

    def _move(self, amount: float, fine: bool) -> Any:
        if self.disabled:
            return None
        if self._drag_t is None:
            self._drag_t = self.unit_value()
        self._drag_t = _clamp(self._drag_t + amount / (10 if fine else 1))
        return self.put_unit(self._drag_t)

    def _end(self, _e: Any = None) -> None:
        self._drag_t = None
        self.active = False

    def _wheel(self, e: Any) -> Any:
        if self.disabled:
            return None
        lines = -(e.dy or 0)
        if self.step:
            return self.put(self.shown() + lines * self.step)
        return self.put_unit(self.unit_value() + lines * (0.002 if e.shift else 0.02))

    def _caption(self, width: float) -> List[Any]:
        t = _current_theme()
        lines = []
        if self.caption:
            lines.append(_core.text(self.caption, size=11, color=t.text_muted, align_x="center", width=width))
        return lines


# -- knob ------------------------------------------------------------------------------------------
_START, _SWEEP = 135.0, 270.0


class Knob(_Valued):
    """A rotary knob: drag up or down (Shift for fine steps), scroll, double-click to reset.

    ``variant`` picks the look: ``"arc"`` (a value ring), ``"fl"`` (FL Studio's shaded knob with a
    glowing ring), ``"vintage"`` (a cream knob with ticks), ``"rack"`` (a small Eurorack knob) or
    ``"minimal"`` (only the ring and the value). ``bipolar`` draws the ring from the middle (pan,
    detune). ``options`` turns it into a stepped selector that shows the option's name.
    """

    value: float = 0.5
    diameter: float = 48
    variant: Literal["arc", "fl", "vintage", "rack", "minimal"] = "arc"
    bipolar: bool = False
    options: Optional[list] = None
    show_value: bool = True
    travel: float = 200
    icon = "circle-gauge"
    category = "Audio"
    size = (64, 84)
    designer = True

    def setup(self) -> None:
        super().setup()
        if self.options:
            self.min, self.max, self.step = 0, len(self.options) - 1, 1

    def _set_props(self, props: Dict[str, Any]) -> None:
        super()._set_props(props)
        if self.options:
            self.min, self.max, self.step = 0, len(self.options) - 1, 1

    def display(self) -> str:
        if self.options:
            return str(self.options[int(round(self.shown()))])
        return super().display()

    def shapes(self) -> List[Dict[str, Any]]:
        """The knob drawn with ``pyzed.draw``, ``diameter`` pixels wide."""
        th = _current_theme()
        d = self.diameter
        c = d / 2
        t = self.unit_value()
        angle = _START + _SWEEP * t
        a = math.radians(angle)
        color = _color(self.color) if not self.disabled else th.text_disabled
        origin = _START + _SWEEP / 2 if self.bipolar else _START
        lo, hi = sorted((origin, angle))
        out: List[Dict[str, Any]] = []
        variant = self.variant
        if variant == "fl":
            ring = d * 0.07
            r = c - ring / 2 - 1
            out.append(draw.arc(c, c, r, _START, _START + _SWEEP, stroke=_alpha("#000000", 0.55), width=ring, cap="round"))
            if hi - lo > 0.5:
                out.append(draw.arc(c, c, r, lo, hi, stroke=_alpha(color, 0.35), width=ring * 2.2, cap="round"))
                out.append(draw.arc(c, c, r, lo, hi, stroke=color, width=ring, cap="round"))
            body = r - ring * 1.4
            out.append(draw.circle(c, c + 1.5, body, fill=_alpha("#000000", 0.45)))
            out.append(draw.circle(c, c, body, fill="#2e3238", stroke="#15171a", width=1))
            out.append(draw.circle(c, c - body * 0.08, body * 0.86, fill="#3b4048"))
            out.append(draw.arc(c, c, body * 0.86, 200, 340, stroke=_alpha("#ffffff", 0.18), width=1.5))
            out.append(draw.line(c + math.cos(a) * body * 0.25, c + math.sin(a) * body * 0.25,
                                 c + math.cos(a) * body * 0.8, c + math.sin(a) * body * 0.8,
                                 stroke="#f2f2f2", width=max(2, d * 0.05), cap="round"))
        elif variant == "vintage":
            for i in range(11):
                ta = math.radians(_START + _SWEEP * i / 10)
                out.append(draw.line(c + math.cos(ta) * (c - 1), c + math.sin(ta) * (c - 1),
                                     c + math.cos(ta) * (c - d * 0.1), c + math.sin(ta) * (c - d * 0.1),
                                     stroke=th.text_muted, width=1.2 if i % 5 else 2))
            body = c - d * 0.16
            out.append(draw.circle(c, c + 2, body, fill=_alpha("#000000", 0.35)))
            out.append(draw.circle(c, c, body, fill="#e9dfc6", stroke="#8a7d62", width=1.5))
            out.append(draw.circle(c, c, body * 0.72, fill="#f4ecd8"))
            out.append(draw.line(c + math.cos(a) * body * 0.2, c + math.sin(a) * body * 0.2,
                                 c + math.cos(a) * body * 0.92, c + math.sin(a) * body * 0.92,
                                 stroke="#1d1d1f", width=max(2, d * 0.05), cap="round"))
        elif variant == "rack":
            body = c - 1
            out.append(draw.circle(c, c + 1, body, fill=_alpha("#000000", 0.4)))
            out.append(draw.circle(c, c, body, fill="#1f2125", stroke="#0c0d0f", width=1))
            out.append(draw.circle(c, c, body * 0.78, fill="#2c2f35"))
            out.append(draw.line(c + math.cos(a) * body * 0.15, c + math.sin(a) * body * 0.15,
                                 c + math.cos(a) * body * 0.92, c + math.sin(a) * body * 0.92,
                                 stroke=color if self.color != "accent" else "#f5f5f5", width=max(1.5, d * 0.06),
                                 cap="round"))
        else:  # arc, minimal
            ring = max(3.0, d * 0.09)
            r = c - ring / 2 - 1
            out.append(draw.arc(c, c, r, _START, _START + _SWEEP, stroke=th.element_active, width=ring, cap="round"))
            if hi - lo > 0.5:
                out.append(draw.arc(c, c, r, lo, hi, stroke=color, width=ring, cap="round"))
            if variant != "minimal":
                body = r - ring * 1.3
                out.append(draw.circle(c, c, body, fill=th.elevated, stroke=th.border, width=1))
                out.append(draw.line(c + math.cos(a) * body * 0.3, c + math.sin(a) * body * 0.3,
                                     c + math.cos(a) * body * 0.85, c + math.sin(a) * body * 0.85,
                                     stroke=th.text, width=max(2, d * 0.045), cap="round"))
            else:
                out.append(draw.text(c, c, self.display(), color=th.text, size=max(9, d * 0.2),
                                     align_x="center", align_y="center"))
        if self.hovered or self.active:
            out.append(draw.circle(c, c, c - 0.5, stroke=_alpha(color, 0.35), width=1))
        return out

    def render(self) -> Any:
        th = _current_theme()
        d = self.diameter
        dial = _core.canvas(self.shapes(), width=d, height=d).on(
            drag_start=self._start,
            drag=lambda e: self._move(-e.dy / self.travel, e.shift),
            drag_end=self._end,
            double_click=self.reset,
            scroll=self._wheel,
            mouse_enter=lambda: setattr(self, "hovered", True),
            mouse_leave=lambda: setattr(self, "hovered", False),
            cursor="resize-vertical" if not self.disabled else "not-allowed",
        )
        width = max(d, 56)
        children = [dial, *self._caption(width)]
        if self.show_value and self.variant != "minimal":
            color = th.text if (self.active or self.hovered) else th.text_muted
            children.append(_core.text(self.display(), size=11, color=color, align_x="center", width=width,
                                       font="mono"))
        return _core.column(children, spacing=2, align="center", width=width)


# -- fader -----------------------------------------------------------------------------------------
class Fader(_Valued):
    """A slider like a mixer's channel fader: drag the cap, click the track to jump, scroll,
    double-click to reset. ``level`` (0..1) draws a meter next to the track.

    ``variant``: ``"console"`` (a grooved metal cap), ``"fl"`` (FL Studio's dark cap with a
    colored line and a filled track) or ``"flat"`` (a round handle). ``vertical=False`` lays it
    out horizontally (a crossfader).
    """

    value: float = 0.75
    length: float = 160
    vertical: bool = True
    variant: Literal["console", "fl", "flat"] = "console"
    ticks: int = 11
    level: Optional[float] = None
    show_value: bool = True
    icon = "sliders-vertical"
    category = "Audio"
    size = (56, 200)
    designer = True

    def _dims(self) -> Tuple[float, float, float]:
        """``(thickness of the canvas, cap length, travel)``."""
        cap = 14 if self.variant == "flat" else 26
        across = 34 + (12 if self.level is not None else 0)
        return across, cap, self.length - cap

    def shapes(self) -> List[Dict[str, Any]]:
        """The fader drawn with ``pyzed.draw``."""
        th = _current_theme()
        across, cap, travel = self._dims()
        t = self.unit_value()
        color = _color(self.color) if not self.disabled else th.text_disabled
        mid = 17.0
        along = cap / 2 + (1 - t) * travel if self.vertical else cap / 2 + t * travel

        def box(a: float, b: float, la: float, lb: float, **kw: Any) -> Dict[str, Any]:
            # a rectangle given along/across the fader's axis
            return draw.rect(b, a, lb, la, **kw) if self.vertical else draw.rect(a, b, la, lb, **kw)

        def seg(a1: float, b1: float, a2: float, b2: float, **kw: Any) -> Dict[str, Any]:
            return draw.line(b1, a1, b2, a2, **kw) if self.vertical else draw.line(a1, b1, a2, b2, **kw)

        out: List[Dict[str, Any]] = []
        if self.ticks > 1:
            for i in range(self.ticks):
                a = cap / 2 + travel * i / (self.ticks - 1)
                w = 6 if i in (0, self.ticks - 1) or (self.ticks % 2 and i == self.ticks // 2) else 4
                out.append(seg(a, mid - 9 - w, a, mid - 9, stroke=th.border, width=1))
                out.append(seg(a, mid + 9, a, mid + 9 + w, stroke=th.border, width=1))
        out.append(box(cap / 2 - 2, mid - 2.5, travel + 4, 5, fill="#0d0e10", radius=2.5))
        start = cap / 2 + travel if self.vertical else cap / 2
        if self.variant in ("fl", "flat"):
            lo, hi = sorted((start, along))
            if hi - lo > 0:
                out.append(box(lo, mid - 1.5, hi - lo, 3, fill=color, radius=1.5))
        if self.level is not None:
            lv = _clamp(self.level)
            out.append(box(cap / 2, 36, travel, 6, fill="#0d0e10", radius=2))
            ramp = PALETTES["vu"]
            steps = 16
            for i in range(int(steps * lv + 0.999)):
                f0, f1 = i / steps, min((i + 1) / steps, lv)
                a0 = cap / 2 + travel * (1 - f1) if self.vertical else cap / 2 + travel * f0
                out.append(box(a0, 36, travel * (f1 - f0), 6, fill=_ramp(ramp, f0)))
        if self.variant == "flat":
            out.append(box(along - 7, mid - 7, 14, 14, fill=th.text, radius=7, stroke=color, width=2))
        elif self.variant == "fl":
            out.append(box(along - cap / 2 + 1.5, mid - 13, cap, 26, fill=_alpha("#000000", 0.4), radius=3))
            out.append(box(along - cap / 2, mid - 13, cap, 26, fill="#2e3238", stroke="#15171a", radius=3))
            out.append(box(along - cap / 2 + 2, mid - 11, cap / 2 - 3, 22, fill="#383d44", radius=2))
            out.append(seg(along, mid - 11, along, mid + 11, stroke=color, width=2.5))
        else:  # console
            out.append(box(along - cap / 2 + 2, mid - 14, cap, 28, fill=_alpha("#000000", 0.45), radius=2))
            out.append(box(along - cap / 2, mid - 14, cap, 28, fill="#c9ccd1", stroke="#55595f", radius=2))
            for i, shade in enumerate(("#e9ebee", "#d8dade", "#b3b7bd", "#9a9ea5")):
                out.append(box(along - cap / 2 + 2 + i * (cap - 4) / 4, mid - 13, (cap - 4) / 4, 26, fill=shade))
            out.append(seg(along, mid - 13, along, mid + 13, stroke="#1d1f22", width=2))
        return out

    def _press(self, e: Any) -> Any:
        if self.disabled:
            return None
        _across, cap, travel = self._dims()
        at = e.y if self.vertical else e.x
        t = self.unit_value()
        handle = cap / 2 + (1 - t) * travel if self.vertical else cap / 2 + t * travel
        self._start()
        if abs(at - handle) <= cap / 2:
            return None
        pos = _clamp((at - cap / 2) / travel)
        self._drag_t = 1 - pos if self.vertical else pos
        return self.put_unit(self._drag_t)

    def render(self) -> Any:
        th = _current_theme()
        across, _cap, travel = self._dims()
        w, h = (across, self.length) if self.vertical else (self.length, across)
        track = _core.canvas(self.shapes(), width=w, height=h).on(
            mouse_down=self._press,
            mouse_up=self._end,
            drag=lambda e: self._move((-e.dy if self.vertical else e.dx) / travel, e.shift),
            drag_end=self._end,
            double_click=self.reset,
            scroll=self._wheel,
            cursor="grab" if not self.disabled else "not-allowed",
        )
        width = max(w, 48) if self.vertical else w
        children = [track, *self._caption(width)]
        if self.show_value:
            children.append(_core.text(self.display(), size=11, color=th.text_muted, align_x="center", width=width,
                                       font="mono"))
        return _core.column(children, spacing=4, align="center", width=width)


# -- buttons ---------------------------------------------------------------------------------------
class Pad(Component):
    """A drum pad that lights up while pressed. With ``velocity`` the press is louder near the
    bottom edge (``event.value`` is 1 to 127, like MIDI); ``lit`` keeps it lit from outside
    (a note playing, a step of a sequencer)."""

    text: str = ""
    color: str = "accent"
    lit: bool = False
    velocity: bool = True
    width: float = 72
    height: float = 72
    events = {"press": "The pad was pressed (``event.value``: velocity 1-127).",
              "release": "The pad was released."}
    icon = "square"
    category = "Audio"
    size = (72, 72)

    def setup(self) -> None:
        self.down = False
        self.flash = 0.0

    def _press(self, e: Any) -> Any:
        self.down = True
        vel = 100
        if self.velocity and e.height:
            vel = int(round(20 + 107 * _clamp(e.y / e.height)))
        return self.emit("press", vel)

    def _release(self, _e: Any = None) -> Any:
        if not self.down:
            return None
        self.down = False
        return self.emit("release", None)

    def render(self) -> Any:
        th = _current_theme()
        color = _color(self.color)
        on = self.down or self.lit
        bg = _mix(color, "#ffffff", 0.15) if self.down else color if self.lit else _mix(th.elevated, color, 0.12)
        content = _core.text(self.text, size=11, weight="bold", color=th.on_accent if on else th.text_muted,
                             align_x="center", align_y="center", width="fill", height="fill")
        pad = _core.container(content, width=self.width, height=self.height, bg=bg, radius=6,
                              border_color=_mix(color, "#000000", 0.35) if on else th.border, border_width=1,
                              shadow=(_alpha(color, 0.75), (0, 0), 14) if on else ("#00000066", (0, 2), 3))
        return pad.on(mouse_down=self._press, mouse_up=self._release, mouse_leave=self._release, cursor="pointer")


class LedButton(Component):
    """A button with an LED, like FL Studio's mute, solo and record buttons. It toggles ``on``
    (``event.value``) or, with ``momentary``, only lights while held. ``variant``: ``"fl"``
    (a dark key with a LED on the left), ``"round"`` (a round LED key) or ``"pill"``."""

    text: str = ""
    on: bool = False
    color: str = "success"
    variant: Literal["fl", "round", "pill"] = "fl"
    momentary: bool = False
    icon_name: str = ""
    events = {"toggle": "It was switched (``event.value`` is True or False).",
              "press": "It was pressed.", "release": "It was released."}
    icon = "power"
    category = "Audio"
    size = (72, 26)

    def setup(self) -> None:
        self._prop = self.on
        self._local: Optional[bool] = None
        self.down = False

    def is_on(self) -> bool:
        """Whether it is lit (held, toggled by the user, or ``on`` from the parent)."""
        if self.on != self._prop:
            self._prop, self._local = self.on, None
        if self.momentary:
            return self.down or self.on
        return self._local if self._local is not None else self.on

    def _press(self) -> Any:
        self.down = True
        if self.momentary:
            return self.emit("press", True)
        self._local = not self.is_on()
        return _results(self.emit("press", True), self.emit("toggle", self._local))

    def _release(self) -> Any:
        if not self.down:
            return None
        self.down = False
        return self.emit("release", False)

    def render(self) -> Any:
        th = _current_theme()
        color = _color(self.color)
        lit = self.is_on()
        led_size = 8 if self.variant != "round" else 12
        led = _core.container(None, width=led_size, height=led_size, radius=led_size / 2,
                              bg=color if lit else _mix(color, "#000000", 0.7),
                              border_color=_mix(color, "#000000", 0.5), border_width=1,
                              shadow=(_alpha(color, 0.9), (0, 0), 8) if lit else None)
        parts: List[Any] = [led]
        if self.icon_name:
            from ..icons import icon as _icon

            parts.append(_icon(self.icon_name, size=13, color=th.text if lit else th.text_muted))
        if self.text:
            parts.append(_core.text(self.text, size=11, weight="bold", color=th.text if lit else th.text_muted))
        body = _core.row(parts, spacing=6, align="center")
        radius = {"round": 14, "pill": 13}.get(self.variant, 3)
        face = "#2a2d32" if not self.down else "#202226"
        button = _core.container(body, padding=(5, 9), bg=face, radius=radius,
                                 border_color="#121316", border_width=1,
                                 shadow=("#00000080", (0, 1 if self.down else 2), 2))
        return button.on(mouse_down=self._press, mouse_up=self._release, mouse_leave=self._release, cursor="pointer")


def _steps(row: Any) -> List[Any]:
    """A row of steps: a list as is, or text such as ``"x...x...x...x..."`` (``x``/``1`` is on)."""
    if isinstance(row, str):
        return [c in "xX1#*" for c in row.replace(" ", "")]
    return list(row)


class StepSequencer(Component):
    """A grid of steps like FL Studio's channel rack: click a step to switch it, drag to paint.

    ``pattern`` is a list of rows, each a list of booleans (or velocities 0..1); ``labels`` names
    the rows; ``current`` lights the step being played. ``change`` gives the whole new pattern.
    Steps are grouped by ``group`` with alternating shades, so beats are easy to read.
    """

    pattern: list = ()
    labels: list = ()
    current: int = -1
    color: str = "accent"
    group: int = 4
    cell: float = 22
    events = {"change": "A step was switched (``event.value`` is the new pattern, a list of rows)."}
    icon = "grid-3x3"
    category = "Audio"
    size = (420, 120)

    LABEL_WIDTH = 72

    def setup(self) -> None:
        self._local: Optional[List[List[Any]]] = None
        self._prop = self.pattern
        self.paint: Optional[bool] = None

    def rows(self) -> List[List[Any]]:
        """The pattern being shown (the user's edits until the parent passes a new one)."""
        if self.pattern is not self._prop and self.pattern != self._prop:
            self._prop, self._local = self.pattern, None
        rows = self._local if self._local is not None else self.pattern
        return [_steps(r) for r in rows or ()] or [[False] * 16]

    def _cell_at(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        rows = self.rows()
        left = self.LABEL_WIDTH if self.labels else 0
        col = int((x - left) // self.cell)
        row = int(y // self.cell)
        if 0 <= row < len(rows) and 0 <= col < len(rows[row]) and x >= left:
            return row, col
        return None

    def _put(self, x: float, y: float, start: bool) -> Any:
        hit = self._cell_at(x, y)
        if hit is None:
            return None
        row, col = hit
        rows = self.rows()
        if start or self.paint is None:
            self.paint = not bool(rows[row][col])
        if bool(rows[row][col]) == self.paint:
            return None
        rows[row][col] = self.paint
        self._local = rows
        return self.emit("change", rows)

    def shapes(self) -> List[Dict[str, Any]]:
        """The grid drawn with ``pyzed.draw``."""
        th = _current_theme()
        color = _color(self.color)
        rows = self.rows()
        left = self.LABEL_WIDTH if self.labels else 0
        c = self.cell
        out: List[Dict[str, Any]] = []
        on_cells: List[Tuple[float, float, float, float]] = []
        for r, row in enumerate(rows):
            y = r * c
            if self.labels:
                name = str(self.labels[r]) if r < len(self.labels) else ""
                out.append(draw.rect(0, y + 2, left - 6, c - 4, fill=th.elevated, radius=3))
                out.append(draw.text(8, y + c / 2, name, color=th.text, size=11, align_y="center"))
            for i, step in enumerate(row):
                x = left + i * c
                shade = th.element if (i // max(self.group, 1)) % 2 == 0 else _mix(th.element, color, 0.12)
                if step:
                    level = 1.0 if step is True else _clamp(float(step))
                    on_cells.append((x + 2, y + 2, c - 4, c - 4))
                    out.append(draw.rect(x + 2, y + 2, c - 4, c - 4, fill=_mix(shade, color, 0.35 + 0.65 * level),
                                         radius=3))
                else:
                    out.append(draw.rect(x + 2, y + 2, c - 4, c - 4, fill=shade, radius=3))
                if i == self.current:
                    out.append(draw.rect(x + 2, y + 2, c - 4, c - 4, stroke=th.text, width=1.5, radius=3))
        if 0 <= self.current < max(len(r) for r in rows):
            x = left + self.current * c
            out.append(draw.rect(x + 1, 0, c - 2, len(rows) * c, fill=_alpha("#ffffff", 0.06), radius=3))
        return out

    def render(self) -> Any:
        rows = self.rows()
        left = self.LABEL_WIDTH if self.labels else 0
        w = left + max(len(r) for r in rows) * self.cell
        h = len(rows) * self.cell
        return _core.canvas(self.shapes(), width=w, height=h).on(
            mouse_down=lambda e: self._put(e.x, e.y, True),
            drag=lambda e: self._put(e.x, e.y, False),
            drag_end=lambda: setattr(self, "paint", None),
            cursor="pointer",
        )


# -- piano -----------------------------------------------------------------------------------------
class Note(NamedTuple):
    """A note played on a ``Piano``: MIDI number (60 = C4) and velocity (1-127)."""

    note: int
    velocity: int


class Piano(Component):
    """A piano keyboard. Click or drag across the keys (lower on a key is louder); ``pressed``
    lights notes played from elsewhere (MIDI, a sequencer, the computer keyboard with
    ``KEYBOARD``). ``note_on`` gives a ``Note`` and ``note_off`` the note number."""

    start: int = 48
    octaves: int = 2
    pressed: list = ()
    color: str = "accent"
    key_width: float = 24
    height: float = 110
    labels: bool = True
    events = {"note_on": "A key was pressed (``event.value`` is a ``Note(note, velocity)``).",
              "note_off": "A key was released (``event.value`` is the note number)."}
    icon = "piano"
    category = "Audio"
    size = (340, 110)

    def setup(self) -> None:
        self.held: Optional[int] = None

    def notes(self) -> List[int]:
        """Every note on the keyboard, from ``start`` (rounded down to a C) up to the last C."""
        first = self.start - self.start % 12
        return list(range(first, first + self.octaves * 12 + 1))

    def _layout(self) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        whites, blacks = [], []
        x = 0.0
        for n in self.notes():
            if n % 12 in _BLACK:
                blacks.append((n, x - self.key_width * 0.3))
            else:
                whites.append((n, x))
                x += self.key_width
        return whites, blacks

    def note_at(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """The note under ``(x, y)`` and the velocity there, or ``None``."""
        whites, blacks = self._layout()
        black_h = self.height * 0.62
        bw = self.key_width * 0.6
        if y < black_h:
            for n, bx in blacks:
                if bx <= x < bx + bw:
                    return n, int(30 + 97 * _clamp(y / black_h))
        for n, wx in whites:
            if wx <= x < wx + self.key_width and 0 <= y <= self.height:
                return n, int(30 + 97 * _clamp(y / self.height))
        return None

    def _down(self, e: Any) -> Any:
        hit = self.note_at(e.x, e.y)
        if hit is None:
            return None
        self.held = hit[0]
        return self.emit("note_on", Note(*hit))

    def _drag(self, e: Any) -> Any:
        hit = self.note_at(e.x, e.y)
        note = hit[0] if hit else None
        if note == self.held:
            return None
        off = self.emit("note_off", self.held) if self.held is not None else None
        self.held = note
        return _results(off, self.emit("note_on", Note(*hit)) if hit is not None else None)

    def _up(self, _e: Any = None) -> Any:
        if self.held is None:
            return None
        note, self.held = self.held, None
        return self.emit("note_off", note)

    def shapes(self) -> List[Dict[str, Any]]:
        """The keys drawn with ``pyzed.draw``."""
        color = _color(self.color)
        lit = {int(n) for n in _numbers(self.pressed)}
        if self.held is not None:
            lit.add(self.held)
        whites, blacks = self._layout()
        w, h = self.key_width, self.height
        out: List[Dict[str, Any]] = [draw.rect(0, 0, len(whites) * w, h, fill="#101114", radius=3)]
        for n, x in whites:
            on = n in lit
            out.append(draw.rect(x + 0.5, 0, w - 1, h, fill=_mix("#f4f4f2", color, 0.55) if on else "#f4f4f2",
                                 radius=3))
            out.append(draw.rect(x + 0.5, h - 6, w - 1, 6, fill=_alpha("#000000", 0.08 if not on else 0.0), radius=3))
            if self.labels and n % 12 == 0:
                out.append(draw.text(x + w / 2, h - 10, note_name(n), color="#6b7280", size=max(8, w * 0.36),
                                     align_x="center", align_y="bottom"))
        bw, bh = w * 0.6, h * 0.62
        for n, x in blacks:
            on = n in lit
            out.append(draw.rect(x, 0, bw, bh, fill=color if on else "#1b1c20", radius=2))
            if not on:
                out.append(draw.rect(x + 2, 1, bw - 4, bh - 6, fill="#2a2c31", radius=2))
        out.append(draw.rect(0, 0, len(whites) * w, 3, fill=_alpha("#000000", 0.35)))
        return out

    def render(self) -> Any:
        whites, _ = self._layout()
        return _core.canvas(self.shapes(), width=len(whites) * self.key_width, height=self.height).on(
            mouse_down=self._down, drag=self._drag, mouse_up=self._up, drag_end=self._up, mouse_leave=self._up,
            cursor="pointer",
        )


# -- meters ----------------------------------------------------------------------------------------
_VU_MARKS = [(-20, "20"), (-10, "10"), (-7, "7"), (-5, "5"), (-3, "3"), (0, "0"), (3, "+3")]


class VuMeter(Component):
    """A level meter. ``level`` is one level or a list (one bar per channel), 0..1 as linear
    amplitude; ``scale="db"`` shows it in decibels from ``floor`` to 0 dB, like a mixer.

    ``variant``: ``"led"`` (segments that light up), ``"bar"`` (a smooth gradient) or
    ``"analog"`` (a needle VU meter with ballistics). The peak of each channel is held for
    ``hold`` seconds; ``colors`` is a palette name or a list of colors from quiet to loud.
    """

    level: Any = 0.0
    variant: Literal["led", "bar", "analog"] = "led"
    vertical: bool = True
    length: float = 160
    thickness: float = 10
    segments: int = 24
    scale: Literal["db", "linear"] = "db"
    floor: float = -60.0
    hold: float = 1.2
    colors: Any = "vu"
    icon = "activity"
    category = "Audio"
    size = (40, 170)

    def setup(self) -> None:
        self.peaks: List[Tuple[float, float]] = []
        self.needles: List[float] = []
        self.last = _now()

    def position(self, level: float) -> float:
        """Where ``level`` sits along the meter (0..1)."""
        if self.scale == "db":
            return _clamp((_db(abs(level)) - self.floor) / -self.floor)
        return _clamp(abs(level))

    def _levels(self) -> List[float]:
        return _numbers(self.level) or [0.0]

    def _update_peaks(self, positions: List[float]) -> List[float]:
        now = _now()
        if len(self.peaks) != len(positions):
            self.peaks = [(p, now) for p in positions]
        out = []
        for i, p in enumerate(positions):
            peak, when = self.peaks[i]
            if p >= peak or now - when > self.hold:
                fallen = peak - (now - when - self.hold) * 0.6 if now - when > self.hold else peak
                if p >= fallen:
                    peak, when = p, now
                else:
                    peak = fallen
            self.peaks[i] = (peak, when)
            out.append(peak)
        return out

    def shapes(self) -> List[Dict[str, Any]]:
        """The meter drawn with ``pyzed.draw``."""
        if self.variant == "analog":
            return self._analog()
        ramp = _palette(self.colors, "vu")
        positions = [self.position(v) for v in self._levels()]
        peaks = self._update_peaks(positions)
        gap = 3.0
        out: List[Dict[str, Any]] = []
        for i, (pos, peak) in enumerate(zip(positions, peaks)):
            b0 = i * (self.thickness + gap)
            if self.vertical:
                out.append(draw.rect(b0, 0, self.thickness, self.length, fill="#0d0e10", radius=2))
            else:
                out.append(draw.rect(0, b0, self.length, self.thickness, fill="#0d0e10", radius=2))
            if self.variant == "led":
                seg = self.length / self.segments
                by_color: Dict[str, List[Tuple[float, float, float, float]]] = {}
                for s in range(self.segments):
                    f = (s + 0.5) / self.segments
                    lit = f <= pos
                    base = _ramp(ramp, f)
                    fill = base if lit else _mix("#0d0e10", base, 0.16)
                    a = s * seg + 1
                    rect = ((b0 + 1, self.length - a - seg + 2, self.thickness - 2, seg - 2) if self.vertical
                            else (a, b0 + 1, seg - 2, self.thickness - 2))
                    by_color.setdefault(fill, []).append(rect)
                out.extend(draw.rects(rects, fill=c) for c, rects in by_color.items())
            else:
                steps = 32
                for s in range(int(steps * pos + 0.999)):
                    f0, f1 = s / steps, min((s + 1) / steps, pos)
                    if self.vertical:
                        out.append(draw.rect(b0 + 1, self.length * (1 - f1), self.thickness - 2,
                                             self.length * (f1 - f0) + 0.5, fill=_ramp(ramp, f0)))
                    else:
                        out.append(draw.rect(self.length * f0, b0 + 1, self.length * (f1 - f0) + 0.5,
                                             self.thickness - 2, fill=_ramp(ramp, f0)))
            if peak > 0.01:
                if self.vertical:
                    out.append(draw.rect(b0 + 1, self.length * (1 - peak), self.thickness - 2, 2,
                                         fill=_ramp(ramp, peak)))
                else:
                    out.append(draw.rect(self.length * peak - 2, b0 + 1, 2, self.thickness - 2,
                                         fill=_ramp(ramp, peak)))
        return out

    def _analog(self) -> List[Dict[str, Any]]:
        w, h = self.length, self.length * 0.62
        now = _now()
        dt = min(max(now - self.last, 0.0), 0.2)
        self.last = now
        levels = self._levels()[:1]
        target = levels[0]
        vu = _clamp((_db(abs(target)) + 20) / 23 if target > 0 else 0)  # -20 dB .. +3 dB
        if not self.needles:
            self.needles = [vu]
        k = 1 - math.exp(-dt / 0.3) if dt > 0 else 1.0  # about 300 ms ballistics, like a real VU
        self.needles[0] += (vu - self.needles[0]) * k
        cx, cy, r = w / 2, h * 1.05, h * 0.85
        a0, a1 = 225.0, 315.0
        out: List[Dict[str, Any]] = [
            draw.rect(0, 0, w, h, fill="#151618", radius=6),
            draw.rect(4, 4, w - 8, h - 8, fill="#efe2b8", radius=4),
        ]

        def at(db: float) -> float:
            return a0 + (a1 - a0) * _clamp((db + 20) / 23)

        out.append(draw.arc(cx, cy, r, a0, at(0), stroke="#2b2b2b", width=1.5))
        out.append(draw.arc(cx, cy, r, at(0), a1, stroke="#c62828", width=4))
        for db, label in _VU_MARKS:
            a = math.radians(at(db))
            out.append(draw.line(cx + math.cos(a) * r, cy + math.sin(a) * r, cx + math.cos(a) * (r + 6),
                                 cy + math.sin(a) * (r + 6), stroke="#c62828" if db > 0 else "#2b2b2b", width=1.5))
            out.append(draw.text(cx + math.cos(a) * (r + 14), cy + math.sin(a) * (r + 14), label,
                                 color="#c62828" if db > 0 else "#2b2b2b", size=9, align_x="center",
                                 align_y="center"))
        out.append(draw.text(cx, h * 0.62, "VU", color="#2b2b2b", size=13, weight="bold", align_x="center",
                             align_y="center"))
        a = math.radians(a0 + (a1 - a0) * self.needles[0])
        out.append(draw.line(cx, cy, cx + math.cos(a) * (r + 4), cy + math.sin(a) * (r + 4), stroke="#111111",
                             width=1.5, cap="round"))
        out.append(draw.rect(4, h - 14, w - 8, 10, fill="#151618"))
        return out

    def render(self) -> Any:
        if self.variant == "analog":
            w, h = self.length, self.length * 0.62
        else:
            n = len(self._levels())
            across = n * self.thickness + (n - 1) * 3
            w, h = (across, self.length) if self.vertical else (self.length, across)
        return _core.canvas(self.shapes(), width=w, height=h)


# -- displays --------------------------------------------------------------------------------------
def _columns(samples: Sequence[float], count: int) -> List[Tuple[float, float]]:
    """``samples`` reduced to ``count`` (min, max) pairs, one per pixel column."""
    n = len(samples)
    if n == 0:
        return [(0.0, 0.0)] * count
    out = []
    for i in range(count):
        a = i * n // count
        b = max((i + 1) * n // count, a + 1)
        chunk = samples[a:b]
        out.append((min(chunk), max(chunk)))
    return out


class Waveform(Component):
    """A waveform: the shape of a sound over time. ``samples`` are -1..1 (a buffer, a whole
    file); long buffers are reduced to one min/max pair per pixel, so drawing stays fast.

    ``variant``: ``"line"``, ``"filled"``, ``"mirror"`` (an envelope around the center),
    ``"bars"`` (rounded bars like a music app, played part in ``color`` and the rest dimmed) or
    ``"dots"``. ``playhead`` (0..1) marks the playing position, ``selection`` a ``(start, end)``
    range and ``seek`` reports clicks and drags as 0..1.
    """

    samples: list = ()
    width: float = 360
    height: float = 96
    variant: Literal["mirror", "filled", "line", "bars", "dots"] = "mirror"
    color: str = "accent"
    background: str = "#0f1012"
    gain: float = 1.0
    thickness: float = 1.5
    glow: bool = False
    grid: bool = True
    playhead: Optional[float] = None
    selection: Optional[tuple] = None
    bar: float = 3
    events = {"seek": "The waveform was clicked or dragged (``event.value`` is 0..1)."}
    icon = "audio-waveform"
    category = "Audio"
    size = (360, 96)

    def shapes(self) -> List[Dict[str, Any]]:
        """The waveform drawn with ``pyzed.draw``."""
        th = _current_theme()
        w, h = self.width, self.height
        mid = h / 2
        amp = (h / 2 - 2) * self.gain
        color = _color(self.color)
        out: List[Dict[str, Any]] = [draw.rect(0, 0, w, h, fill=_color(self.background), radius=4)]
        if self.grid:
            for i in range(1, 8):
                out.append(draw.line(w * i / 8, 0, w * i / 8, h, stroke=_alpha(th.border, 0.5), width=1))
            out.append(draw.line(0, mid, w, mid, stroke=_alpha(th.border, 0.9), width=1))
        if self.selection and len(_numbers(self.selection)) == 2:
            s0, s1 = sorted(_numbers(self.selection))
            out.append(draw.rect(w * s0, 0, w * (s1 - s0), h, fill=_alpha(color, 0.18)))
        samples = _numbers(self.samples)
        if samples:
            def clip(v: float) -> float:
                return max(-1.0, min(1.0, v * self.gain)) * (h / 2 - 2)

            variant = self.variant
            if variant == "bars":
                step = self.bar * 2
                count = max(1, int(w // step))
                cols = _columns(samples, count)
                played = self.playhead if self.playhead is not None else 1.0
                for i, (lo, hi) in enumerate(cols):
                    peak = max(abs(lo), abs(hi))
                    bh = max(2.0, min(peak * self.gain, 1.0) * (h - 4))
                    fill = color if (i + 0.5) / count <= played else _mix(color, _color(self.background), 0.65)
                    out.append(draw.rect(i * step + 1, mid - bh / 2, self.bar, bh, fill=fill, radius=self.bar / 2))
            elif variant in ("mirror", "filled") or len(samples) > w * 2:
                count = max(2, int(w))
                cols = _columns(samples, count)
                if variant == "mirror":
                    top = [(i * w / (count - 1), mid - max(abs(lo), abs(hi)) * amp) for i, (lo, hi) in enumerate(cols)]
                    bottom = [(x, 2 * mid - y) for x, y in reversed(top)]
                else:
                    top = [(i * w / (count - 1), mid - clip(hi) * 1.0) for i, (lo, hi) in enumerate(cols)]
                    bottom = [(i * w / (count - 1), mid - clip(lo)) for i, (lo, hi) in reversed(list(enumerate(cols)))]
                if variant in ("mirror", "filled"):
                    out.append(draw.polygon(top + bottom, fill=_alpha(color, 0.55)))
                    out.append(draw.polyline(top, stroke=color, width=1))
                    out.append(draw.polyline(bottom, stroke=color, width=1))
                else:  # a long buffer as a line: its min/max envelope, filled solid
                    out.append(draw.polygon(top + bottom, fill=color))
            else:
                n = len(samples)
                pts = [(i * w / max(n - 1, 1), mid - clip(v)) for i, v in enumerate(samples)]
                if variant == "dots":
                    out.extend(draw.circle(x, y, self.thickness, fill=color) for x, y in pts[:: max(1, n // 160)])
                else:
                    if self.glow:
                        out.append(draw.polyline(pts, stroke=_alpha(color, 0.25), width=self.thickness * 4))
                    out.append(draw.polyline(pts, stroke=color, width=self.thickness))
        if self.playhead is not None and self.variant != "bars":
            x = w * _clamp(self.playhead)
            out.append(draw.rect(0, 0, x, h, fill=_alpha("#ffffff", 0.04)))
            out.append(draw.line(x, 0, x, h, stroke=th.text, width=1.5))
        return out

    def _seek(self, e: Any) -> Any:
        return self.emit("seek", _clamp(e.x / max(self.width, 1)))

    def render(self) -> Any:
        canvas = _core.canvas(self.shapes(), width=self.width, height=self.height)
        if self.handles("seek"):
            canvas = canvas.on(mouse_down=self._seek, drag=self._seek, cursor="crosshair")
        return canvas


def _trigger(samples: Sequence[float], window: int) -> List[float]:
    """``window`` samples starting at the first rising zero crossing, so a periodic wave stands still."""
    n = len(samples)
    if n <= window:
        return list(samples)
    for i in range(1, n - window):
        if samples[i - 1] < 0 <= samples[i]:
            return list(samples[i:i + window])
    return list(samples[-window:])


class Scope(Component):
    """An oscilloscope: one or more ``traces`` (lists of -1..1 samples) over a grid of
    ``divisions``. ``trigger`` keeps a periodic wave still; ``xy`` draws the first trace
    against the second (Lissajous figures, stereo width); ``persistence`` leaves fading
    copies of the last frames like a phosphor screen.
    """

    traces: list = ()
    width: float = 320
    height: float = 180
    colors: Any = "scope"
    background: str = "#0b120e"
    columns: int = 8
    rows: int = 6
    gain: float = 1.0
    trigger: bool = True
    window: int = 512
    xy: bool = False
    persistence: int = 0
    glow: bool = True
    icon = "radio"
    category = "Audio"
    size = (320, 180)

    def setup(self) -> None:
        self.history: List[List[List[Tuple[float, float]]]] = []

    def _traces(self) -> List[List[float]]:
        traces = list(self.traces or ())
        if not traces or not isinstance(traces[0], (list, tuple)) and not hasattr(traces[0], "__len__") \
                or isinstance(traces[0], str):
            return [_numbers(traces)]
        return [_numbers(t) for t in traces]

    def shapes(self) -> List[Dict[str, Any]]:
        """The screen drawn with ``pyzed.draw``."""
        w, h = self.width, self.height
        bg = _color(self.background)
        colors = _palette(self.colors)
        grid = _mix(bg, "#7fbf9f", 0.18)
        out: List[Dict[str, Any]] = [draw.rect(0, 0, w, h, fill=bg, radius=6)]
        cols, rows = max(int(self.columns), 1), max(int(self.rows), 1)
        for i in range(1, cols):
            out.append(draw.line(w * i / cols, 0, w * i / cols, h, stroke=grid, width=1, dash=[2, 3]))
        for j in range(1, rows):
            out.append(draw.line(0, h * j / rows, w, h * j / rows, stroke=grid, width=1, dash=[2, 3]))
        out.append(draw.line(w / 2, 0, w / 2, h, stroke=_mix(bg, "#7fbf9f", 0.3), width=1))
        out.append(draw.line(0, h / 2, w, h / 2, stroke=_mix(bg, "#7fbf9f", 0.3), width=1))
        traces = self._traces()
        frame: List[List[Tuple[float, float]]] = []
        if self.xy and len(traces) >= 2:
            xs, ys = traces[0], traces[1]
            n = min(len(xs), len(ys), 2048)
            r = min(w, h) / 2 - 4
            frame.append([(w / 2 + max(-1, min(1, xs[i] * self.gain)) * r,
                           h / 2 - max(-1, min(1, ys[i] * self.gain)) * r) for i in range(n)])
        else:
            for t in traces:
                data = _trigger(t, self.window) if self.trigger else t[-self.window:]
                n = len(data)
                if n < 2:
                    frame.append([])
                    continue
                if n > w * 2:
                    cols_mm = _columns(data, int(w))
                    pts = []
                    for i, (lo, hi) in enumerate(cols_mm):
                        x = i * w / (len(cols_mm) - 1)
                        pts += [(x, h / 2 - max(-1, min(1, hi * self.gain)) * (h / 2 - 3)),
                                (x, h / 2 - max(-1, min(1, lo * self.gain)) * (h / 2 - 3))]
                else:
                    pts = [(i * w / (n - 1), h / 2 - max(-1, min(1, v * self.gain)) * (h / 2 - 3))
                           for i, v in enumerate(data)]
                frame.append(pts)
        if self.persistence:
            self.history = (self.history + [frame])[-(self.persistence + 1):]
        else:
            self.history = [frame]
        for age, old in enumerate(reversed(self.history)):
            fade = 1.0 / (1 + age * 1.6)
            for i, pts in enumerate(old):
                if len(pts) < 2:
                    continue
                color = colors[i % len(colors)]
                if self.glow and age == 0:
                    out.append(draw.polyline(pts, stroke=_alpha(color, 0.22), width=5))
                out.append(draw.polyline(pts, stroke=_alpha(color, fade), width=1.6 if age == 0 else 1.2))
        return out

    def render(self) -> Any:
        return _core.canvas(self.shapes(), width=self.width, height=self.height)


_BANDS_CACHE: Dict[Tuple[int, int, float, float], List[Tuple[int, int]]] = {}


def _band_ranges(bins: int, bands: int, sample_rate: float, low: float) -> List[Tuple[int, int]]:
    """Bin ranges ``[a, b)`` for ``bands`` log-spaced bands from ``low`` Hz to Nyquist."""
    key = (bins, bands, sample_rate, low)
    if key not in _BANDS_CACHE:
        nyquist = sample_rate / 2
        out = []
        for i in range(bands):
            f0 = low * (nyquist / low) ** (i / bands)
            f1 = low * (nyquist / low) ** ((i + 1) / bands)
            a = int(f0 / nyquist * bins)
            b = max(int(f1 / nyquist * bins), a + 1)
            out.append((min(a, bins - 1), min(b, bins)))
        _BANDS_CACHE[key] = out
    return _BANDS_CACHE[key]


def bands(magnitudes: Sequence[float], count: int, *, sample_rate: float = 48000, low: float = 30.0,
          log: bool = True, floor: float = -120.0) -> List[float]:
    """Groups FFT ``magnitudes`` (dB, bins from 0 Hz to Nyquist) into ``count`` bands, log-spaced
    like the ear hears them; each band takes its loudest bin."""
    mags = _numbers(magnitudes)
    n = len(mags)
    if n == 0:
        return [floor] * count
    if not log:
        return [max(mags[i * n // count:max((i + 1) * n // count, i * n // count + 1)]) for i in range(count)]
    return [max(mags[a:b]) if b > a else floor for a, b in _band_ranges(n, count, sample_rate, low)]


class Spectrum(Component):
    """A spectrum analyzer: how loud each frequency is. ``magnitudes`` are dB values per FFT bin
    (0 Hz to Nyquist, like ``node.spectrum()``), grouped into ``bands`` log-spaced bands.

    ``variant``: ``"bars"``, ``"blocks"`` (LED segments), ``"line"``, ``"filled"``, ``"mirror"``
    or ``"radial"`` (bars around a circle). ``colors`` is a palette name (``"fl"``, ``"neon"``,
    ``"fire"``, ``"ice"``...) or a list, painted by level or by ``color_by="frequency"``.
    Bars rise at once and fall at ``falloff`` dB per second; ``peaks`` leaves a cap on each one.
    """

    magnitudes: list = ()
    width: float = 360
    height: float = 140
    variant: Literal["bars", "blocks", "line", "filled", "mirror", "radial"] = "bars"
    bands: int = 48
    min_db: float = -90.0
    max_db: float = 0.0
    colors: Any = "fl"
    color_by: Literal["level", "frequency"] = "level"
    background: str = "#0f1012"
    falloff: float = 48.0
    peaks: bool = True
    sample_rate: float = 48000
    log: bool = True
    labels: bool = False
    gap: float = 2
    icon = "audio-lines"
    category = "Audio"
    size = (360, 140)

    def setup(self) -> None:
        self.levels: List[float] = []
        self.caps: List[float] = []
        self.last = _now()

    def values(self) -> List[float]:
        """The bands' levels (0..1) after falloff, updated once per render."""
        raw = bands(self.magnitudes, self.bands, sample_rate=self.sample_rate, log=self.log, floor=self.min_db)
        span = (self.max_db - self.min_db) or 1.0
        target = [_clamp((v - self.min_db) / span) for v in raw]
        now = _now()
        dt = min(max(now - self.last, 0.0), 0.25)
        self.last = now
        if len(self.levels) != len(target):
            self.levels = list(target)
            self.caps = list(target)
            return self.levels
        drop = self.falloff / span * dt if self.falloff else 1.0
        for i, v in enumerate(target):
            self.levels[i] = v if v >= self.levels[i] else max(v, self.levels[i] - drop)
            self.caps[i] = self.levels[i] if self.levels[i] >= self.caps[i] else max(self.levels[i], self.caps[i] - drop * 0.35)
        return self.levels

    def shapes(self) -> List[Dict[str, Any]]:
        """The analyzer drawn with ``pyzed.draw``."""
        th = _current_theme()
        w, h = self.width, self.height
        ramp = _palette(self.colors)
        levels = self.values()
        n = len(levels)
        out: List[Dict[str, Any]] = [draw.rect(0, 0, w, h, fill=_color(self.background), radius=4)]
        if self.labels and self.variant != "radial":
            nyquist = self.sample_rate / 2
            for f, name in ((100, "100"), (1000, "1k"), (10000, "10k")):
                if f >= nyquist:
                    continue
                x = w * math.log(f / 30) / math.log(nyquist / 30) if self.log else w * f / nyquist
                out.append(draw.line(x, 0, x, h, stroke=_alpha(th.border, 0.6), width=1, dash=[2, 3]))
                out.append(draw.text(x + 3, 3, name, color=th.text_muted, size=9))
        if n == 0:
            return out

        def color_for(i: int, level: float) -> str:
            return _ramp(ramp, i / max(n - 1, 1) if self.color_by == "frequency" else level)

        variant = self.variant
        bw = w / n
        if variant == "radial":
            cx, cy = w / 2, h / 2
            r0 = min(w, h) * 0.22
            r1 = min(w, h) / 2 - 4
            out.append(draw.circle(cx, cy, r0 - 3, stroke=_alpha(ramp[0], 0.6), width=2))
            for i, v in enumerate(levels):
                a = math.radians(-90 + 360 * i / n)
                length = r0 + (r1 - r0) * v
                out.append(draw.line(cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * length,
                                     cy + math.sin(a) * length, stroke=color_for(i, v),
                                     width=max(1.5, 2 * math.pi * r0 / n - 1.5), cap="round"))
            return out
        if variant in ("line", "filled"):
            pts = [(bw * (i + 0.5), h - 2 - v * (h - 4)) for i, v in enumerate(levels)]
            if variant == "filled":
                out.append(draw.polygon([(0, h), (0, pts[0][1]), *pts, (w, pts[-1][1]), (w, h)],
                                        fill=_alpha(ramp[len(ramp) // 2], 0.35)))
            out.append(draw.polyline(pts, stroke=_alpha(ramp[-1], 0.25), width=5))
            out.append(draw.polyline(pts, stroke=ramp[-1] if len(ramp) > 1 else ramp[0], width=1.8))
            return out
        if variant == "blocks":
            seg_h = 6.0
            rows = max(1, int(h // seg_h))
            by_color: Dict[str, List[Tuple[float, float, float, float]]] = {}
            for i, v in enumerate(levels):
                lit = int(round(v * rows))
                for r in range(lit):
                    c = color_for(i, (r + 0.5) / rows) if self.color_by != "frequency" else color_for(i, v)
                    by_color.setdefault(c, []).append((i * bw + self.gap / 2, h - (r + 1) * seg_h + 1,
                                                       bw - self.gap, seg_h - 2))
            out.extend(draw.rects(rects, fill=c) for c, rects in by_color.items())
        else:
            for i, v in enumerate(levels):
                bh = v * (h - 4)
                if variant == "mirror":
                    out.append(draw.rect(i * bw + self.gap / 2, h / 2 - bh / 2, bw - self.gap, max(bh, 1),
                                         fill=color_for(i, v), radius=min(2, (bw - self.gap) / 2)))
                elif bh > 0.5:
                    if self.color_by == "level":
                        steps = max(1, int(v * 8))
                        for s in range(steps):
                            f0, f1 = s / steps * v, (s + 1) / steps * v
                            out.append(draw.rect(i * bw + self.gap / 2, h - 2 - f1 * (h - 4), bw - self.gap,
                                                 (f1 - f0) * (h - 4) + 0.5, fill=_ramp(ramp, f0)))
                    else:
                        out.append(draw.rect(i * bw + self.gap / 2, h - 2 - bh, bw - self.gap, bh,
                                             fill=color_for(i, v)))
        if self.peaks and variant != "mirror":
            for i, c in enumerate(self.caps):
                if c > 0.01:
                    out.append(draw.rect(i * bw + self.gap / 2, h - 3 - c * (h - 4), bw - self.gap, 2,
                                         fill=_mix(color_for(i, c), "#ffffff", 0.35)))
        return out

    def render(self) -> Any:
        return _core.canvas(self.shapes(), width=self.width, height=self.height)


class Spectrogram(Component):
    """A scrolling spectrogram (waterfall): time runs left to right, frequency bottom to top and
    color is loudness. Each render with a new ``magnitudes`` list adds a column; it keeps the
    last ``history`` columns. ``colors`` is a palette name or a list from silent to loud."""

    magnitudes: list = ()
    width: float = 360
    height: float = 140
    history: int = 120
    bands: int = 48
    min_db: float = -90.0
    max_db: float = 0.0
    colors: Any = "magma"
    levels: int = 24
    sample_rate: float = 48000
    icon = "waves"
    category = "Audio"
    size = (360, 140)

    def setup(self) -> None:
        self.columns: List[List[int]] = []
        self._last: Any = None

    def push(self, magnitudes: Sequence[float]) -> None:
        """Adds a column for ``magnitudes`` (done by ``render`` when the list changes)."""
        raw = bands(magnitudes, self.bands, sample_rate=self.sample_rate, floor=self.min_db)
        span = (self.max_db - self.min_db) or 1.0
        q = self.levels - 1
        self.columns.append([int(round(_clamp((v - self.min_db) / span) * q)) for v in raw])
        del self.columns[:-self.history]

    def shapes(self) -> List[Dict[str, Any]]:
        """The waterfall drawn with ``pyzed.draw`` (one ``rects`` shape per color)."""
        if self.magnitudes is not self._last and len(self.magnitudes):
            self._last = self.magnitudes
            self.push(self.magnitudes)
        w, h = self.width, self.height
        ramp = _palette(self.colors, "magma")
        out: List[Dict[str, Any]] = [draw.rect(0, 0, w, h, fill=ramp[0], radius=4)]
        cw = w / self.history
        bh = h / self.bands
        by_level: Dict[int, List[Tuple[float, float, float, float]]] = {}
        offset = self.history - len(self.columns)
        for c, column in enumerate(self.columns):
            x = (offset + c) * cw
            for b, level in enumerate(column):
                if level:
                    by_level.setdefault(level, []).append((x, h - (b + 1) * bh, cw + 0.5, bh + 0.5))
        q = max(self.levels - 1, 1)
        out.extend(draw.rects(rects, fill=_ramp(ramp, level / q)) for level, rects in sorted(by_level.items()))
        return out

    def render(self) -> Any:
        return _core.canvas(self.shapes(), width=self.width, height=self.height)
