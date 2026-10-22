"""Records the animated WebP illustrations of the Animation section (docs/public/media/animation/).

    python docs/scripts/animation_media.py               # every clip
    python docs/scripts/animation_media.py easing keys   # only the clips whose name contains a word
    python docs/scripts/animation_media.py --list        # what there is to record

Every clip is drawn off-screen, frame by frame, with the same renderer as the screenshot scripts, so
no window, display or GPU is needed and the result is the same on every machine. Animations normally
show their resting state in screenshots; here each one is *frozen* at the frame's time instead
(``Frozen`` below seeks it, like a paused ``AnimationPlayer``), and timeline clips are played by a
paused ``AnimationPlayer`` that the clip seeks. State-based animations (hover, press, focus) are
frozen at how far they have gone, and a pointer is drawn where the clip moves one.

Needs Pillow. Each WebP aims for at most ~450 KB: the quality drops until it fits.
"""

from __future__ import annotations

import argparse
import io
import math
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "public" / "media" / "animation"
EXAMPLES = ROOT / "examples"
SCALE = 2
BUDGET = 450_000

os.environ.setdefault("PYZED_CONFIG_DIR", tempfile.mkdtemp(prefix="pyzed-anim-media-"))
sys.path.insert(0, str(EXAMPLES))

import pyzed as pz  # noqa: E402
from pyzed import animation as A  # noqa: E402
from pyzed import draw, ui  # noqa: E402

# The look shared by the clips (the dark navy of examples/timeline.py).
BG = "#0b0e1a"
CARD = "#161b2e"
EDGE = "#ffffff1a"
MUTED = "#ffffff99"
FAINT = "#ffffff55"
ACCENT = "#6366f1"
CYAN = "#22d3ee"
PINK = "#f472b6"
GOLD = "#fbbf24"
GREEN = "#34d399"
THEME = pz.themes.ONE_DARK


# -- freezing animations at a time ----------------------------------------------------------------
class Frozen:
    """``widget.animate(Frozen(t, "pop_in"))``: the animation as it looks ``t`` seconds after it
    started. Takes what ``animate()`` takes (presets, ``pz.Animation``, options, property values).
    State-based animations are played as if their condition started at 0."""

    def __init__(self, t: float, *animations: Any, **options: Any):
        self.t, self.animations, self.options = t, animations, options

    def _pyzed_compiled(self) -> list[dict[str, Any]]:
        out = A._compile(self.animations, self.options)
        for d in out:
            d.update(seek=max(0.0, self.t) * 1000, paused=True, trigger="mount", active=None)
        return out


class Held(Frozen):
    """A state-based animation (hover, press, focus, active) ``progress`` of the way in (0 to 1)."""

    def _pyzed_compiled(self) -> list[dict[str, Any]]:
        out = A._compile(self.animations, self.options)
        for d in out:
            d.update(seek=(d["delay"] + max(0.0, min(1.0, self.t)) * d["duration"]), paused=True,
                     trigger="mount", active=None, iterations=1, direction="normal", fill="both")
        return out


def toward(t: float, on: float, off: float = math.inf, seconds: float = 0.25) -> float:
    """How far (0 to 1) a state animation has gone at ``t`` when its condition holds from ``on`` to
    ``off``: it plays forward, then back from wherever it got to."""
    if t < on:
        return 0.0
    reached = min(1.0, (min(t, off) - on) / seconds)
    if t < off:
        return reached
    return max(0.0, reached - (t - off) / seconds)


def glide(t: float, points: list[tuple[float, float, float]]) -> tuple[float, float]:
    """The pointer at ``t`` along ``(time, x, y)`` stops, moving between them with an ease-in-out."""
    if t <= points[0][0]:
        return points[0][1:]
    for (t0, x0, y0), (t1, x1, y1) in zip(points, points[1:]):
        if t <= t1:
            f = (t - t0) / max(t1 - t0, 1e-6)
            f = f * f * (3 - 2 * f)
            return (x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)
    return points[-1][1:]


# -- building blocks ----------------------------------------------------------------------------
def code(text: str, size: int = 12, color: str = MUTED) -> Any:
    return pz.text(text, size=size, font="mono", color=color)


def label(text: str, size: int = 13, color: str = "#ffffff", weight: str = "semibold") -> Any:
    return pz.text(text, size=size, weight=weight, color=color)


def chip(text: str, width: Any = 132, height: Any = 56, color: str = CARD) -> Any:
    """A small card with a centered label: what most clips animate."""
    return pz.container(label(text), width=width, height=height, align_x="center", align_y="center").style(
        background=color, border=(1, EDGE), radius=10)


def cell(widget: Any, caption: str, width: float = 168, height: float = 110) -> Any:
    """A widget over its code, in a fixed box so the grid doesn't move while it animates."""
    return pz.column([
        pz.container(widget, width="fill", height="fill", align_x="center", align_y="center"),
        pz.container(code(caption, 11), width="fill", align_x="center"),
    ], spacing=6, width=width, height=height)


def stage(content: Any, padding: Any = 24) -> Any:
    return pz.container(content, width="fill", height="fill", padding=padding).style(background=BG)


def grid(cells: list[Any], columns: int, spacing: float = 10) -> Any:
    rows = [pz.row(cells[i:i + columns], spacing=spacing) for i in range(0, len(cells), columns)]
    return pz.column(rows, spacing=spacing)


def title(text: str, sub: str = "") -> Any:
    items = [label(text, 15)]
    if sub:
        items.append(code(sub, 12, FAINT))
    return pz.row(items, spacing=12, align="center")


# -- clips ----------------------------------------------------------------------------------------
@dataclass
class Shot:
    """One frame: the view, and the pointer (logical pixels) when the clip shows one."""

    view: Any
    pointer: tuple[float, float] | None = None
    pressed: bool = False


@dataclass
class Clip:
    name: str
    description: str
    size: tuple[float, float]
    seconds: float
    make: Callable[[float], Any]
    fps: int = 30
    #: (x, y, w, h) in logical pixels: keep only this part of each frame.
    crop: tuple[float, float, float, float] | None = None
    scale: float = SCALE
    #: Build an app once (Pyzed Design) instead of a new view per frame: ``make(t)`` steps ``app``.
    app: Callable[[], Any] | None = None
    tags: list[str] = field(default_factory=list)


CLIPS: dict[str, Clip] = {}


def clip(name: str, description: str, size: tuple[float, float], seconds: float, **options: Any):
    def register(fn):
        CLIPS[name] = Clip(name, description, size, seconds, fn, **options)
        return fn

    return register


class _View(pz.App):
    theme = THEME

    def __init__(self, root: Any):
        self.root = root

    def view(self):
        return self.root


# -- clips: animate() --------------------------------------------------------------------------------
@clip("overview", "A dashboard coming in: a header, cards one after another, a pulsing badge and a spinner.",
      (760, 360), 4.0)
def overview_clip(t):
    t0 = t - 0.2
    stats = [("Revenue", "$48.2k", GREEN), ("Users", "2,931", CYAN), ("Orders", "614", PINK), ("Uptime", "99.9%", GOLD)]
    cards = [pz.column([code(name, 11, MUTED), pz.text(value, size=24, weight="bold", color=color)], spacing=6)
             .style(background=CARD, border=(1, EDGE), radius=12, padding=16, width=163)
             .animate(Frozen(t0 - 0.25 - i * 0.08, "fade_in_up")) for i, (name, value, color) in enumerate(stats)]
    badge = pz.container(pz.text("3 new", size=12, weight="bold", color="#ffffff"), padding=(4, 10)).style(
        background=PINK, radius=999).animate(Frozen(t0 - 0.9, "pulse", repeat="infinite"))
    record = ui.button("Recording", lambda: None, icon="circle", variant="accent").style(glow=("#ef4444", 4)).animate(
        Frozen(t0 - 0.9, "glow_pulse"))
    spinner = pz.icon("loader-circle", size=22, color=MUTED).animate(Frozen(t0, "spin"))
    return stage(pz.column([
        pz.row([pz.text("Welcome back", size=26, weight="bold", color="#ffffff"), badge], spacing=14,
               align="center").animate(Frozen(t0, "fade_in_down")),
        pz.row(cards, spacing=20),
        pz.row([record, pz.row([spinner, code("Syncing…", 13)], spacing=8, align="center")], spacing=24,
               align="center").animate(Frozen(t0 - 0.6, "fade_in")),
    ], spacing=28), padding=32)


START_BUTTON = (24 + 24 + 146, 24 + 24 + 30 + 14 + 36 + 14 + 18)


@clip("start", "Apply and play: a card rises in, its button lifts on hover, a pz.Trigger shakes the field and another "
      "pops a check in.", (760, 270), 6.0)
def start_clip(t):
    shake = t - 2.1 if t >= 2.1 else None
    done = t - 3.75 if t >= 3.75 else None
    wrong = shake is not None and done is None
    hover = toward(t, 1.35, 4.7, 0.16)
    field = pz.container(code("•" * (6 if t < 3.0 or t >= 3.4 else 3), 14, "#ffffff"), width=292, height=36,
                         padding=(0, 12), align_y="center").style(
        background="#0f1324", border=(1, PINK if wrong else EDGE), radius=8)
    if shake is not None and done is None:
        field = field.animate(Frozen(shake, "shake"))
    button = pz.container(label("Sign in"), width=292, height=36, align_x="center", align_y="center").style(
        background=ACCENT, radius=8).animate(Held(hover, "lift"))
    status: Any = pz.text("Wrong password" if wrong else "", size=12, color=PINK)
    if done is not None:
        status = pz.row([pz.icon("circle-check", size=18, color=GREEN).animate(Frozen(done, "pop_in")),
                         pz.text("Signed in", size=13, color=GREEN).animate(Frozen(done - 0.1, "fade_in_left"))],
                        spacing=8, align="center")
    card = pz.column([
        pz.container(label("Welcome back", 20, weight="bold"), height=30),
        field,
        button,
        pz.container(status, height=28, align_y="center"),
    ], spacing=14).style(background=CARD, border=(1, EDGE), radius=14, padding=24, width=340).animate(
        Frozen(t - 0.2, "fade_in_up"))

    def line(text: str, lit: bool) -> Any:
        return code(text, 12, "#ffffff" if lit else FAINT)

    lines = pz.column([
        code("# where it goes → when it plays", 11, FAINT),
        line('card.animate("fade_in_up")', t < 0.9),
        line('button.animate("lift", on="hover")', 1.35 <= t < 4.9),
        line('field.animate("shake", on=self.wrong)', shake is not None and shake < 0.6),
        line('check.animate("pop_in", on=self.done)', done is not None and done < 0.6),
        pz.space(height=6),
        code("# in a handler", 11, FAINT),
        line("self.wrong.fire()", shake is not None and shake < 0.6),
        line("self.done.fire()", done is not None and done < 0.6),
    ], spacing=8)
    pointer = glide(t, [(0, 700, 300), (1.2, *START_BUTTON), (4.8, *START_BUTTON), (5.6, 700, 300), (6.0, 700, 300)])
    pressed = any(a <= t < b for a, b in ((2.0, 2.1), (3.65, 3.75)))
    return Shot(stage(pz.row([card, lines], spacing=36, align="center")), pointer, pressed)


TRIGGER_X = [24 + 56 + i * 120 for i in range(6)]
TRIGGER_Y = 120


@clip("triggers", "What plays an animation: mount, hover, press, focus, click and active.", (760, 230), 7.0)
def triggers_clip(t):
    hover = toward(t, 1.0, 2.0, 0.16)
    press = toward(t, 2.75, 3.05, 0.09)
    focus = toward(t, 3.95, math.inf, 0.2)
    click = t - 4.75 if t >= 4.75 else -1
    active = t - 5.85 if t >= 5.85 else None
    tiles = [
        cell(chip("mount", 104).animate(Frozen(t - 0.2, "fade_in_up")), 'on="mount"', 112),
        cell(chip("hover", 104).animate(Held(hover, "lift")), 'on="hover"', 112),
        cell(chip("press", 104).animate(Held(press, "shrink")), 'on="press"', 112),
        cell(chip("focus", 104).animate(Held(focus, on="focus", border_color=ACCENT, glow=12, glow_color=ACCENT, duration=200)),
             'on="focus"', 112),
        cell(chip("click", 104).animate(Frozen(click, "tada")), 'on="click"', 112),
        cell(_with(chip("active", 104, color="#3b1d2a" if active is not None else CARD),
                   Frozen(active, "glow_pulse") if active is not None else None), "active=True", 112),
    ]
    pointer = glide(t, [(0, 690, 210), (0.9, TRIGGER_X[1], TRIGGER_Y), (2.0, TRIGGER_X[1], TRIGGER_Y),
                        (2.6, TRIGGER_X[2], TRIGGER_Y), (3.5, TRIGGER_X[2], TRIGGER_Y),
                        (3.85, TRIGGER_X[3], TRIGGER_Y), (4.3, TRIGGER_X[3], TRIGGER_Y),
                        (4.65, TRIGGER_X[4], TRIGGER_Y), (5.4, TRIGGER_X[4], TRIGGER_Y),
                        (5.75, TRIGGER_X[5], TRIGGER_Y), (6.4, TRIGGER_X[5], TRIGGER_Y), (7.0, 690, 210)])
    pressed = any(a <= t < b for a, b in ((2.75, 3.05), (3.85, 3.95), (4.65, 4.75), (5.75, 5.85)))
    return Shot(stage(pz.column([title("widget.animate(preset, on=...)"), pz.row(tiles, spacing=8)], spacing=24)),
                pointer, pressed)


BALL = 360


def _dot(color: str = ACCENT) -> Any:
    return pz.container(width=22, height=22).style(background=color, radius=11, glow=(color, 8))


def _lane(dot: Any) -> Any:
    return pz.container(dot, width=BALL + 22, height=22, align_y="center").style(background="#ffffff0d", radius=11)


@clip("options", "The timing options of animate(): duration, delay, repeat, direction, fill and easing.",
      (760, 330), 4.2)
def options_clip(t):
    move = pz.Animation({0: {"x": 0}, 1: {"x": BALL}}, duration=1000, easing="ease_in_out")
    t0 = t - 0.3
    rows = [
        ("duration=1000", {}),
        ("delay=600", {"delay": 600}),
        ("repeat=3, duration=500", {"repeat": 3, "duration": 500}),
        ('direction="alternate", repeat=4', {"direction": "alternate", "repeat": 4, "duration": 800}),
        ('direction="reverse"', {"direction": "reverse"}),
        ('fill="none"', {"fill": "none"}),
    ]
    lines = [pz.row([pz.container(code(text, 12, "#ffffffcc"), width=290), _lane(_dot().animate(Frozen(t0, move, **opts)))],
                    spacing=12, align="center") for text, opts in rows]
    return stage(pz.column([title("animate(animation, **options)"), *lines], spacing=16))


PROPS = [
    ("opacity", {0: {"opacity": 1}, 1: {"opacity": 0.15}}),
    ("x", {0: {"x": -34}, 1: {"x": 34}}),
    ("y", {0: {"y": -22}, 1: {"y": 22}}),
    ("scale", {0: {"scale": 0.7}, 1: {"scale": 1.15}}),
    ("rotate", {0: {"rotate": -25}, 1: {"rotate": 25}}),
    ("blur", {0: {"blur": 0}, 1: {"blur": 6}}),
    ("background", {0: {"background": CARD}, 1: {"background": ACCENT}}),
    ("border_color", {0: {"border_color": EDGE}, 1: {"border_color": CYAN}}),
    ("radius", {0: {"radius": 2}, 1: {"radius": 28}}),
    ("glow", {0: {"glow": 0, "glow_color": PINK}, 1: {"glow": 22, "glow_color": PINK}}),
    ("width", {0: {"width": 64}, 1: {"width": 150}}),
    ("font_size", {0: {"font_size": 11}, 1: {"font_size": 22}}),
]


@clip("properties", "Every animatable property, each one going back and forth.", (760, 410), 3.2)
def properties_clip(t):
    cells = []
    for name, frames in PROPS:
        anim = pz.Animation(frames, duration=1600, easing="ease_in_out", repeat="infinite", direction="alternate")
        widget = chip("Aa" if name == "font_size" else name, 116, 52)
        if name == "border_color":
            widget = widget.style(border=(2, EDGE))
        cells.append(cell(widget.animate(Frozen(t, anim)), name, 172, 104))
    return stage(pz.column([title("animate(**properties)"), grid(cells, 4, 8)], spacing=16))


def _keys_bar(offsets: list[float], progress: float, width: float = 300) -> Any:
    """A keyframe bar: a diamond at each offset and the playhead at ``progress``."""
    shapes = [draw.rect(0, 13, width, 4, fill="#ffffff22", radius=2)]
    for o in offsets:
        x = 10 + o * (width - 20)
        lit = progress >= o - 1e-6
        shapes.append(draw.polygon([(x, 7), (x + 8, 15), (x, 23), (x - 8, 15)], fill=GOLD if lit else "#ffffff66"))
    x = 10 + progress * (width - 20)
    shapes.append(draw.line(x, 0, x, 30, stroke=CYAN, width=2))
    return pz.canvas(shapes, width=width, height=30)


@clip("keyframes", "Keyframes: a heartbeat and a wiggle, with their keys and the playhead.", (760, 300), 2.0)
def keyframes_clip(t):
    beat = pz.Animation({0: {"scale": 1}, "30%": {"scale": 1.25, "easing": "ease_out"}, "45%": {"scale": 1},
                         "60%": {"scale": 1.15}, 1: {"scale": 1}}, duration=1000, repeat="infinite")
    wiggle = pz.Animation([{"x": 0}, {"x": -10}, {"x": 10}, {"x": -6}, {"x": 0}], duration=1000, repeat="infinite")
    p = (t % 1.0)

    def column(widget, offsets, caption):
        return pz.column([
            pz.container(widget, width=300, height=120, align_x="center", align_y="center"),
            _keys_bar(offsets, p),
            pz.container(code(caption, 11), width=300, align_x="center"),
        ], spacing=10)

    heart = pz.icon("heart", size=64, color=PINK).style(bloom=(PINK, 0.5)).animate(Frozen(t, beat))
    return stage(pz.row([
        column(heart, [0, 0.3, 0.45, 0.6, 1], '{0, "30%", "45%", "60%", 1}'),
        column(chip("wiggle", 140).animate(Frozen(t, wiggle)), [0, 0.25, 0.5, 0.75, 1], "[x: 0, -10, 10, -6, 0]"),
    ], spacing=64), padding=(28, 50))


EASINGS = ["linear", "ease", "ease_in", "ease_out_cubic", "ease_in_out", "ease_out_back", "ease_out_bounce", "spring",
           "steps(5)"]


def _curve(name: str, p: float) -> Any:
    w, h, pad = 64, 40, 4
    f = (lambda x: math.floor(x * 5) / 5 if x < 1 else 1.0) if name.startswith("steps") else (lambda x: A.ease(name, x))
    points = [(pad + i / 40 * (w - 2 * pad), h - pad - f(i / 40) * (h - 2 * pad) * 0.8 - (h - 2 * pad) * 0.1)
              for i in range(41)]
    x = pad + p * (w - 2 * pad)
    y = h - pad - f(p) * (h - 2 * pad) * 0.8 - (h - 2 * pad) * 0.1
    return pz.canvas([draw.rect(0, 0, w, h, fill="#ffffff0a", radius=6),
                      draw.polyline(points, stroke="#ffffff88", width=1.5),
                      draw.circle(x, y, 3, fill=CYAN)], width=w, height=h)


@clip("easing", "Easing curves: the same move with each curve.", (760, 520), 2.8)
def easing_clip(t):
    duration = 1.6
    t0 = t - 0.4
    p = max(0.0, min(1.0, t0 / duration))
    rows = []
    for name in EASINGS:
        move = pz.Animation({0: {"x": 0}, 1: {"x": BALL}}, duration=duration * 1000, easing=name)
        rows.append(pz.row([pz.container(code(f'"{name}"', 12, "#ffffffcc"), width=150), _curve(name, p),
                            _lane(_dot(CYAN if name != "linear" else MUTED).animate(Frozen(t0, move)))],
                           spacing=14, align="center"))
    return stage(pz.column([title("easing=", "pz.animation.EASINGS"), *rows], spacing=10))


def _frozen_change(t: float, changes: list[tuple[float, Any]], prop: str, duration: float = 220,
                   easing: str = "ease_out_cubic") -> tuple[Any, Any]:
    """What ``transition(prop=value)`` shows at ``t`` when the value changes at the given times:
    the value to set, and the animation from the previous one (or ``None``)."""
    value, previous, since = changes[0][1], None, -1.0
    for at, v in changes[1:]:
        if t >= at:
            previous, value, since = value, v, at
    if previous is None or (t - since) * 1000 >= duration:
        return value, None
    anim = pz.Animation({0: {prop: previous}, 1: {prop: value}}, duration=duration, easing=easing)
    return value, Frozen(t - since, anim)


def _with(widget: Any, anim: Any) -> Any:
    return widget.animate(anim) if anim is not None else widget


@clip("transition", "transition(): a sidebar opening and closing, and a selection moving.", (760, 340), 6.0)
def transition_clip(t):
    toggles = [(0, False), (1.1, True), (4.3, False)]
    open_now, width_anim = _frozen_change(t, [(a, 220 if v else 64) for a, v in toggles], "width")
    _, fade_anim = _frozen_change(t, [(a, 1 if v else 0) for a, v in toggles], "opacity")
    selected = 1 if t < 2.6 else 2
    items = []
    for i, (icon, name) in enumerate([("house", "Home"), ("inbox", "Inbox"), ("chart-line", "Reports"),
                                      ("settings", "Settings")]):
        sel_change = [(0, CARD if i != 1 else ACCENT), (2.6, ACCENT if i == 2 else CARD)]
        bg, bg_anim = _frozen_change(t, sel_change, "background", 260)
        text = pz.text(name, size=13, color="#ffffff")
        text = _with(text.style(opacity=1 if open_now == 220 else 0), fade_anim)
        items.append(_with(pz.row([pz.icon(icon, size=16, color="#ffffff"), text], spacing=12, align="center")
                           .style(background=bg, radius=8, padding=(9, 12), width="fill"), bg_anim))
    sidebar = _with(pz.column(items, spacing=6).style(background="#11162a", border=(1, EDGE), radius=12, padding=8,
                                                      width=open_now, height="fill"), width_anim)
    cards = pz.column([pz.row([pz.container(width="fill", height=70).style(background=CARD, border=(1, EDGE), radius=10)
                               for _ in range(3)], spacing=10) for _ in range(2)], spacing=10, width="fill")
    toggle = ui.button("Menu", lambda: None, icon="panel-left")
    body = pz.column([pz.row([toggle, code("sidebar.transition(width=220 if self.open else 64)", 12)], spacing=14,
                             align="center"), cards], spacing=14, width="fill")
    pointer = glide(t, [(0, 400, 300), (0.8, 140, 40), (1.3, 140, 40), (2.2, 95, 131), (2.9, 95, 131),
                        (3.8, 296, 40), (4.6, 296, 40), (6.0, 400, 300)])
    pressed = any(a <= t < b for a, b in ((1.0, 1.1), (2.5, 2.6), (4.2, 4.3)))
    return Shot(stage(pz.row([sidebar, body], spacing=16, height="fill")), pointer, pressed)


@clip("states", "Style states with a transition, like CSS: hover, pressed and focus.", (760, 250), 5.6)
def states_clip(t):
    save_hover = toward(t, 0.8, 1.9, 0.12)
    save_press = toward(t, 1.35, 1.5, 0.08)
    delete_hover = toward(t, 2.4, 3.4, 0.12)
    card_hover = toward(t, 3.9, 5.0, 0.12)
    save = ui.button("Save", lambda: None, icon="save").animate(
        Held(save_hover, on="hover", background=ACCENT, y=-1, duration=120)).animate(
        Held(save_press, on="press", scale=0.97, duration=80))
    delete = ui.button("Delete", lambda: None, icon="trash-2", variant="outline").animate(
        Held(delete_hover, on="hover", background="#3b1218", border_color="#ef4444", color="#fca5a5", duration=120))
    card = pz.column([label("Card", 14), code("hover → scale 1.03", 11)], spacing=4).style(
        background=CARD, border=(1, EDGE), radius=12, padding=16, width=200).animate(
        Held(card_hover, on="hover", scale=1.03, border_color=ACCENT, duration=150))
    cells = [cell(save, 'hover={"background": ...}', 220, 110), cell(delete, 'hover={"border_color": ...}', 220, 110),
             cell(card, 'hover={"scale": 1.03}', 220, 110)]
    pointer = glide(t, [(0, 700, 230), (0.75, 132, 112), (1.9, 132, 112), (2.35, 362, 112), (3.4, 362, 112),
                        (3.85, 600, 112), (5.0, 600, 112), (5.6, 700, 230)])
    return Shot(stage(pz.column([title("style(hover=..., pressed=..., transition=120)"),
                                 pz.row(cells, spacing=26)], spacing=22)), pointer, 1.35 <= t < 1.5)


PAGES = ["Overview", "Activity", "Settings"]


def _page(index: int, t: float) -> Any:
    """A page whose rows cascade in (``pz.stagger``), ``t`` seconds after it appeared."""
    if index == 0:
        rows = [pz.row([pz.container(pz.column([code(n, 11), pz.text(v, size=20, weight="bold", color=c)], spacing=4),
                                     width="fill").style(background=CARD, border=(1, EDGE), radius=10, padding=12)
                        .animate(Frozen(t - i * 0.06, "fade_in_up"))
                        for i, (n, v, c) in enumerate([("Visits", "12.4k", CYAN), ("Sales", "318", GREEN),
                                                       ("Refunds", "4", PINK)])], spacing=10)]
    elif index == 1:
        rows = [pz.row([pz.icon(icon, size=16, color=MUTED), pz.text(text, size=13, color="#ffffffdd")], spacing=10,
                       align="center").style(background=CARD, radius=8, padding=(8, 12), width="fill")
                .animate(Frozen(t - i * 0.05, "fade_in_up"))
                for i, (icon, text) in enumerate([("git-commit-horizontal", "Ana pushed 3 commits"),
                                                  ("message-circle", "Leo commented on #42"),
                                                  ("circle-check", "Build 118 passed"), ("tag", "v1.4.0 released")])]
    else:
        rows = [pz.row([pz.text(text, size=13, color="#ffffffdd", width="fill"), ui.switch(on, lambda v: None)],
                       align="center").style(background=CARD, radius=8, padding=(8, 12), width="fill")
                .animate(Frozen(t - i * 0.05, "fade_in_up"))
                for i, (text, on) in enumerate([("Notifications", True), ("Dark mode", True), ("Auto-update", False)])]
    return pz.column([pz.text(PAGES[index], size=20, weight="bold", color="#ffffff"), *rows], spacing=10,
                     width="fill")


@clip("presence", "pz.presence and pz.stagger: pages slide in and out, and their rows cascade.", (760, 340), 6.0)
def presence_clip(t):
    changes = [(0.0, 0), (1.3, 1), (3.3, 2), (5.3, 0)]
    current, since, previous = 0, -10.0, None
    for at, page in changes:
        if t >= at:
            previous, current, since = current, page, at
    age = t - since
    layers = []
    if previous is not None and previous != current and age < 0.4:
        layers.append(_page(previous, 10).animate(Frozen(age, "fade_out_left")))
    layers.append(_page(current, age if since > 0 else t).animate(Frozen(age if since > 0 else t, "fade_in_right")))
    tabs = pz.row([pz.container(pz.text(name, size=13, color="#ffffff" if i == current else MUTED), padding=(6, 14))
                   .style(background=ACCENT if i == current else "transparent", radius=8)
                   for i, name in enumerate(PAGES)], spacing=4).style(background=CARD, radius=10, padding=4)
    tab_x = {0: 70, 1: 166, 2: 262}
    stops = [(0, 600, 300)]
    for at, page in changes[1:]:
        stops += [(at - 0.45, tab_x[page], 44), (at + 0.3, tab_x[page], 44)]
    stops.append((6.0, 600, 300))
    pressed = any(at - 0.1 <= t < at for at, _ in changes[1:])
    body = pz.column([pz.row([tabs, code("pz.presence(page, key=self.page, enter=..., exit=...)", 12)], spacing=16, align="center"),
                      pz.stack(layers, width="fill", height="fill")], spacing=20)
    return Shot(stage(body), glide(t, stops), pressed)


def _window(name: str) -> Any:
    bar = pz.row([pz.container(width=10, height=10).style(background=c, radius=5) for c in ("#ef4444", GOLD, GREEN)],
                 spacing=6)
    return pz.column([bar, label(name.replace("_", " ").title(), 14), code(f'transition = "{name}"', 11)], spacing=12)\
        .style(background="#1c2238", border=(1, "#ffffff26"), radius=12, padding=14, width=210, height=130)


@clip("windows", "Window transitions: how a window opens and closes.", (760, 260), 3.0)
def windows_clip(t):
    cells = []
    for name in ("zoom", "pop", "slide_up"):
        enter, leave = A.WINDOW_TRANSITIONS[name]
        anim = Frozen(t - 2.1, leave) if t >= 2.1 else Frozen(t - 0.2, enter)
        cells.append(pz.container(_window(name).animate(anim), width=226, height=170, align_x="center",
                                  align_y="center"))
    return stage(pz.column([title("class Settings(pz.Window): transition = ..."), pz.row(cells, spacing=17)],
                           spacing=12))


def _presets_clip(category: str, play: Callable[[str, float], Any], seconds: float, columns: int = 5):
    names = list(A.presets(category))

    def make(t):
        cells = [cell(chip(name.replace("_", " "), 122, 46).animate(play(name, t)), f'"{name}"', 136, 92)
                 for name in names]
        return stage(pz.column([title(f"{category.title()} presets", f'pz.animation.presets("{category}")'),
                                grid(cells, columns, 8)], spacing=14))

    return make


clip("presets-entrance", "Entrance presets: how a widget appears.", (760, 400), 2.2)(
    _presets_clip("entrance", lambda n, t: Frozen(t - 0.25, n), 2.2))
clip("presets-exit", "Exit presets: how a widget leaves.", (760, 400), 2.2)(
    _presets_clip("exit", lambda n, t: Frozen(t - 0.5, n), 2.2))
clip("presets-attention", "Attention presets: a nudge to look here.", (760, 300), 2.0)(
    _presets_clip("attention", lambda n, t: Frozen(t - 0.2, n), 2.0))
clip("presets-interaction", "Interaction presets: hover, press and focus feedback, in and out.", (760, 300), 2.0)(
    _presets_clip("interaction", lambda n, t: Held(toward(t, 0.3, 1.3, 0.2), n), 2.0))
clip("presets-loop", "Loop presets: motion that goes on.", (760, 300), 4.0)(
    _presets_clip("loop", lambda n, t: Frozen(t, n), 4.0))

AURORA = pz.Gradient(["#0f172a", "#312e81", "#0e7490"], angle=135)


@clip("effects", "Effects that animate: blur, rotation, glow, opacity, and glass moving over color.", (760, 330), 4.0)
def effects_clip(t):
    def swing(frames):
        return Frozen(t, pz.Animation(frames, duration=2000, easing="ease_in_out", repeat="infinite",
                                      direction="alternate"))

    def effect(name, **style):
        return pz.container(label(name, 14), width=150, height=70, align_x="center", align_y="center").style(
            radius=12, **style)

    blobs = pz.row([pz.container(width=70, height=70).style(background=c, radius=35) for c in (PINK, GOLD, GREEN, CYAN)],
                   spacing=40)
    glass = pz.container(label("glass=True", 13), width=170, height=86, align_x="center", align_y="center").style(
        glass=True, radius=16).animate(swing({0: {"x": -150}, 1: {"x": 150}}))
    row = pz.row([
        effect("blur", background="#0b1220", border=(1, "#ffffff33")).animate(swing({0: {"blur": 0}, 1: {"blur": 5}})),
        effect("rotate", background="#0b1220", border=(1, "#ffffff33")).animate(swing({0: {"rotate": -20},
                                                                                       1: {"rotate": 20}})),
        effect("glow", background="#0b1220").animate(swing({0: {"glow": 2, "glow_color": CYAN},
                                                            1: {"glow": 26, "glow_color": CYAN}})),
        effect("opacity", background="#0b1220", border=(1, "#ffffff33")).animate(swing({0: {"opacity": 1},
                                                                                        1: {"opacity": 0.2}})),
    ], spacing=24)
    lower = pz.stack([pz.container(blobs, width="fill", height=110, align_x="center", align_y="center"),
                      pz.container(glass, width="fill", height=110, align_x="center", align_y="center")],
                     width="fill", height=110)
    return pz.container(pz.column([row, lower], spacing=30), width="fill", height="fill", padding=32).style(
        background=AURORA)


# -- clips: timelines ---------------------------------------------------------------------------------
def _at_x(widget: Any, x: float) -> Any:
    """``widget`` laid out ``x`` pixels from the left."""
    return pz.row([pz.container(width=max(0.0, x), height=1), widget])


def _tri(t: float, length: float) -> float:
    """Ping-pong time: 0 → length → 0 → ..."""
    t %= 2 * length
    return t if t <= length else 2 * length - t


def _paused(player: Any, name: str, at: float) -> None:
    """Shows clip ``name`` of ``player`` at ``at`` seconds, paused (so screenshots draw that moment)."""
    if player.current != name:
        player.play(name, restart=True)
    if player.playing:
        player.pause()
    player.seek(at)


def _level_app():
    from timeline import Timeline

    app = Timeline()
    app.player.owner = app
    app.player.pause()
    return app


@clip("timeline-intro", "examples/timeline.py: one clip moves a card, a title, stars, a score and a button.",
      (760, 560), 4.8, app=_level_app, crop=(0, 0, 760, 470))
def timeline_intro_clip(app, t):
    if t < 2.4:
        _paused(app.player, "intro", min(t, 2.2))
        app.message = "New record!" if t >= 1.6 else ""
    else:
        _paused(app.player, "idle", _tri(t - 2.4, 1.2))
    return Shot(None)


TRACKS_DEMO = pz.Clip("intro", length=2.0, tracks=[
    pz.Track("card:opacity", {0: 0, 0.4: 1}),
    pz.Track("card:y", [(0, 40, "ease_out_back"), (0.6, 0)]),
    pz.Track("title:scale", [(0.5, 0.5, "ease_out_back"), (0.9, 1)]),
    pz.Track(":score", [(0.8, 0, "ease_out_cubic"), (1.7, 980)]),
], calls=[pz.Call(1.7, "chime")])


def _track_chart(clip_: Any, time: float, width: float = 420, row: float = 30) -> Any:
    """A timeline drawn like the Animation panel: a ruler, one lane per track and per call, the playhead."""
    left, ruler = 104, 22
    scale = (width - left - 26) / clip_.length
    lanes = [(tr.path, [k.time for k in tr.keys]) for tr in clip_.tracks] + [("calls", [c.time for c in clip_.calls])]
    height = ruler + row * len(lanes)
    shapes = [draw.rect(0, 0, width, height, fill="#ffffff08", radius=8)]
    for s in range(int(clip_.length * 2) + 1):
        x = left + s * 0.5 * scale
        shapes.append(draw.line(x, 4, x, ruler - 6 if s % 2 else ruler - 2, stroke="#ffffff44", width=1))
        if s % 2 == 0:
            shapes.append(draw.text(x + 3, 4, f"{s // 2}s", color="#ffffff66", size=10, font="mono"))
    for i, (path, times) in enumerate(lanes):
        y = ruler + i * row + row / 2
        if i % 2 == 0:
            shapes.append(draw.rect(left - 6, y - row / 2, width - left, row, fill="#ffffff06"))
        shapes.append(draw.text(10, y, path, color="#ffffffaa", size=11, font="mono", align_y="center"))
        for a, b in zip(times, times[1:]):
            shapes.append(draw.line(left + a * scale, y, left + b * scale, y, stroke="#ffffff33", width=2))
        for k in times:
            x = left + k * scale
            lit = time >= k - 1e-6
            color = (GOLD if path != "calls" else ACCENT) if lit else "#ffffff55"
            if path == "calls":
                shapes.append(draw.rect(x - 4, y - 8, 8, 16, fill=color, radius=2))
            else:
                shapes.append(draw.polygon([(x, y - 7), (x + 7, y), (x, y + 7), (x - 7, y)], fill=color))
    x = left + min(time, clip_.length) * scale
    shapes.append(draw.line(x, 0, x, height, stroke=CYAN, width=2))
    shapes.append(draw.polygon([(x - 6, 0), (x + 6, 0), (x, 8)], fill=CYAN))
    return pz.canvas(shapes, width=width, height=height)


class _Score:
    score = 0.0

    def chime(self):
        pass


@clip("timeline-tracks", "A clip's tracks and keys, and what they do to the widgets as the playhead moves.",
      (760, 330), 2.6)
def timeline_tracks_clip(t):
    state = _Score()
    player = pz.AnimationPlayer(TRACKS_DEMO, owner=state)
    _paused(player, "intro", min(t, TRACKS_DEMO.length))
    card = pz.column([
        pz.text("LEVEL 3", size=22, weight="black", color="#ffffff").animate(player["title"]),
        pz.text(f"{state.score:,.0f}", size=30, weight="bold", color=GOLD, font="mono"),
    ], spacing=8, align="center").style(background=CARD, border=(1, EDGE), radius=16, padding=22, width=220)\
        .animate(player["card"])
    left = pz.container(card, width=250, height="fill", align_x="center", align_y="center")
    right = pz.column([code(f"player.position = {player.position:.2f}", 12, "#ffffffcc"),
                       _track_chart(TRACKS_DEMO, player.position)], spacing=10)
    return stage(pz.row([left, pz.container(right, height="fill", align_y="center")], spacing=24))


INTERP = [
    ('{0: 0, 1: 300, 2: 120}', pz.Track("a:x", {0: 0, 1: 300, 2: 120})),
    ('[(0, 0, "ease_out_back"), (1, 300, "ease_in_out"), (2, 120)]',
     pz.Track("a:x", [(0, 0, "ease_out_back"), (1, 300, "ease_in_out"), (2, 120)])),
    ('interpolation="discrete"', pz.Track("a:x", {0: 0, 1: 300, 2: 120}, interpolation="discrete")),
]


def _value_chart(track: Any, time: float, length: float = 2.0, width: float = 220, height: float = 64) -> Any:
    def pos(tm, v):
        return 8 + tm / length * (width - 16), height - 8 - v / 340 * (height - 16)

    points = [pos(i / 80 * length, track.value_at(i / 80 * length)) for i in range(81)]
    shapes = [draw.rect(0, 0, width, height, fill="#ffffff08", radius=8),
              draw.polyline(points, stroke="#ffffff77", width=1.5)]
    for k in track.keys:
        x, y = pos(k.time, k.value)
        shapes.append(draw.polygon([(x, y - 6), (x + 6, y), (x, y + 6), (x - 6, y)], fill=GOLD))
    x, y = pos(min(time, length), track.value_at(min(time, length)))
    shapes += [draw.line(x, 0, x, height, stroke=CYAN, width=1.5), draw.circle(x, y, 4, fill=CYAN)]
    return pz.canvas(shapes, width=width, height=height)


@clip("timeline-keys", "Interpolation between keys: linear, a curve per key, and discrete.", (760, 330), 2.8)
def timeline_keys_clip(t):
    time = min(max(t - 0.2, 0), 2.0)
    rows = []
    for text, track in INTERP:
        dot = pz.container(width=20, height=20).style(background=CYAN, radius=10, glow=(CYAN, 8))
        lane = pz.container(_at_x(dot, track.value_at(time)), width=340, height=20, align_y="center").style(
            background="#ffffff0d", radius=10)
        rows.append(pz.column([code(f"pz.Track(\"dot:x\", {text})", 11, "#ffffffcc"),
                               pz.row([_value_chart(track, time), pz.container(lane, height=64, align_y="center")],
                                      spacing=20)], spacing=6))
    return stage(pz.column(rows, spacing=14), padding=(18, 24))


@clip("timeline-loops", 'loop="none", "loop" and "pingpong".', (760, 250), 4.8)
def timeline_loops_clip(t):
    length = 1.2
    rows = []
    for mode, local in (("none", min(t, length)), ("loop", t % length), ("pingpong", _tri(t, length))):
        p = local / length
        bar = [draw.rect(0, 13, 260, 4, fill="#ffffff22", radius=2)]
        for o in (0, 1):
            x = 10 + o * 240
            bar.append(draw.polygon([(x, 7), (x + 8, 15), (x, 23), (x - 8, 15)], fill=GOLD))
        x = 10 + p * 240
        bar.append(draw.line(x, 0, x, 30, stroke=CYAN, width=2))
        dot = _at_x(pz.container(width=20, height=20).style(background=ACCENT, radius=10, glow=(ACCENT, 8)), p * 270)
        rows.append(pz.row([pz.container(code(f'loop="{mode}"', 12, "#ffffffcc"), width=130),
                            pz.canvas(bar, width=260, height=30),
                            pz.container(dot, width=290, height=20).style(background="#ffffff0d", radius=10)],
                           spacing=16, align="center"))
    return stage(pz.column([title("pz.Clip(..., loop=...)"), *rows], spacing=20))


CALLS_DEMO = pz.Clip("upload", length=2.0, tracks=[
    pz.Track(":progress", [(0, 0, "ease_in_out"), (1.8, 1)]),
    pz.Track(":status", {0: "Uploading…", 0.9: "Almost there", 1.8: "Done"}),
    pz.Track(":files", [(0, 0), (1.8, 24)]),
], calls=[pz.Call(0.9, "halfway"), pz.Call(1.8, "finished", "report.pdf")])


class _Upload(pz.App):
    """The owner of the CALLS_DEMO player: attribute tracks set its attributes, calls run its methods."""

    theme = THEME

    def __init__(self):
        self.reset()

    def reset(self):
        self.progress, self.status, self.files, self.log, self.clock = 0.0, "", 0, [], 0.0
        self.player = pz.AnimationPlayer(CALLS_DEMO, owner=self)
        _paused(self.player, "upload", 0.0)

    def halfway(self):
        self.log.append((self.player.position, "halfway()"))

    def finished(self, name):
        self.log.append((self.player.position, f'finished("{name}")'))

    def view(self):
        bar = pz.container(pz.container(width=max(0.001, self.progress) * 300, height=10).style(
            background=GREEN, radius=5), width=300, height=10).style(background="#ffffff14", radius=5)
        card = pz.column([
            label(self.status, 18),
            bar,
            code(f"{self.files:.0f} / 24 files", 12),
        ], spacing=12).style(background=CARD, border=(1, EDGE), radius=14, padding=20, width=340)
        log = pz.column([code("calls", 11, FAINT)] + [
            pz.row([pz.icon("zap", size=14, color=ACCENT), code(text, 12, "#ffffffdd")], spacing=8, align="center")
            .style(background="#ffffff0d", radius=8, padding=(6, 10)).animate(Frozen(self.clock - at, "fade_in_up"))
            for at, text in self.log], spacing=8, width=280)
        attrs = code(f"self.progress = {self.progress:.2f}\nself.status = {self.status!r}", 12, "#ffffffcc")
        return stage(pz.column([
            pz.row([pz.column([attrs, card], spacing=14), log], spacing=36),
            _track_chart(CALLS_DEMO, self.clock, width=712, row=24),
        ], spacing=18), padding=(20, 24))


@clip("timeline-calls", "Attribute tracks change the app's own values (text, numbers) and calls run its methods.",
      (760, 420), 2.6, app=_Upload)
def timeline_calls_clip(app, t):
    if t == 0:
        app.reset()
    step = min(t, CALLS_DEMO.length) - app.clock
    app.clock = t
    if step > 0:
        app.player.advance(step)
    return Shot(None)


class _Playing(pz.AnimationPlayer):
    """A paused player that tells the controls it is playing, for clips of a moving timeline."""

    shown_playing = False

    @property
    def playing(self) -> bool:
        return self.shown_playing


class _Transport(pz.App):
    theme = THEME

    def __init__(self):
        from timeline import Timeline

        self.level = Timeline()
        self.level.player.__class__ = _Playing
        self.level.player.owner = self.level
        self.level.player.pause()
        self.call = ""

    def view(self):
        banner = pz.row([pz.icon("terminal", size=14, color=CYAN), code(self.call, 13, "#ffffff")], spacing=8,
                        align="center").style(background="#0f1630", border=(1, "#22d3ee55"), radius=8, padding=(6, 12))
        return pz.column([pz.container(banner, width="fill", padding=(12, 24, 0, 24)).style(background="#0b0e1a"),
                          self.level.view()], width="fill", height="fill").style(background="#0b0e1a")


TRANSPORT = [  # (from, to, call shown, position at the start, speed: seconds of clip per second)
    (0.0, 1.6, 'player.play("intro")', 0.0, 1.0),
    (1.6, 2.4, "player.pause()", 1.6, 0.0),
    (2.4, 3.2, "player.seek(0.5)", 0.5, 0.0),
    (3.2, 5.2, "player.play_backwards()", 2.2, -1.1),
    (5.2, 7.2, "player.speed = 2  ·  player.play()", 0.0, 2.0),
]


@clip("timeline-player", "The player's controls: play, pause, seek, play backwards and speed.", (760, 600), 7.2,
      app=_Transport, crop=(0, 0, 760, 600))
def timeline_player_clip(app, t):
    p = app.level.player
    for start, end, call, at, speed in TRANSPORT:
        if start <= t < end or end == TRANSPORT[-1][1]:
            position = max(0.0, min(2.2, at + (t - start) * speed))
            app.call = call
            p.shown_playing = speed != 0 and 0 < position < 2.2
            p.speed = abs(speed) if call.startswith("player.speed") else 1.0
            _paused(p, "intro", position)
            app.level.message = "New record!" if position >= 1.6 else ""
            if start <= t < end:
                break
    return Shot(None)


RETARGET = pz.Clip("bounce", length=1.2, loop="loop", tracks=[
    pz.Track("card:y", [(0, 0, "ease_out_quad"), (0.3, -26, "ease_in_quad"), (0.6, 0), (1.2, 0)]),
    pz.Track("card:scale", {0: 1, 0.55: 1, 0.62: 0.92, 0.75: 1}),
])


@clip("timeline-reuse", "One clip reused: on its own target, retargeted to another widget, and as a pz.Animation.",
      (760, 260), 2.4)
def timeline_reuse_clip(t):
    player = pz.AnimationPlayer(RETARGET)
    _paused(player, "bounce", t % 1.2)
    other = pz.AnimationPlayer(RETARGET.retarget({"card": "panel"}))
    _paused(other, "bounce", t % 1.2)
    cells = [
        cell(chip("card", 140).animate(player["card"]), 'player["card"]', 220, 150),
        cell(chip("panel", 140, color="#1d2a3b").animate(other["panel"]), 'clip.retarget({"card": "panel"})', 220, 150),
        cell(chip("button", 140, color="#2a1d3b").animate(
            Frozen(t, RETARGET.animation("card"), repeat="infinite")), 'clip.animation("card")', 220, 150),
    ]
    return stage(pz.column([title("Reusing clips"), pz.row(cells, spacing=26)], spacing=18))


# -- clips: the Animation panel of Pyzed Design ----------------------------------------------------------
DESIGNER_SIZE = (1440, 900)
DESIGNER_CROP = (240, 36, 840, 834)
LANE_X0, PX_PER_S, RULER_Y = 493, 160, 622


def _designer(build: Callable[[Any], None]) -> Callable[[], Any]:
    def make():
        from pyzed import designer

        app = designer.Designer(EXAMPLES / "designer" / "login.pzform", language_servers=False)
        app.theme = THEME
        build(app)
        app.timeline.show()
        app.layout.resize("bottom", 330)
        app.toasts.clear()
        return app

    return make


def _intro(app: Any) -> None:
    e = app.timeline
    e.new_clip()
    e.rename_clip("intro")
    keys = [("title:opacity", [(0, 0.0), (0.4, 1.0)]), ("title:y", [(0, 24.0), (0.5, 0.0)]),
            ("subtitle:opacity", [(0.2, 0.0), (0.6, 1.0)]), ("sign_in:scale", [(0.5, 0.8), (0.9, 1.0)])]
    for path, values in keys:
        app.doc.select(path.split(":")[0])
        app._selection_changed()
        e.seek(values[0][0])
        e.add_track(path)
        e.select_key(path, values[0][0])
        e.set_key_value(values[0][1])
        e.seek(values[1][0])
        e.add_key(path)
        e.set_key_value(values[1][1])
    e.select_key("title:y", 0.0)
    e.set_key_easing("ease_out_back")
    app.doc.select("status")
    app._selection_changed()
    e.seek(0.5); e.add_track(":status.text"); e.seek(1.0); e.add_key(":status.text"); e.set_key_value("Welcome!")
    e.call_draft = "intro_done"; e.seek(1.0); e.submit_call()
    e.toggle_autoplay()
    e.selected = None
    e.seek(0)


def _ruler(time: float) -> tuple[float, float]:
    return (LANE_X0 + time * PX_PER_S, RULER_Y)


@clip("editor-scrub", "The Animation panel: dragging the playhead plays the clip on the form, frame by frame.",
      DESIGNER_SIZE, 4.6, app=_designer(_intro), crop=DESIGNER_CROP, scale=1.0, fps=24)
def editor_scrub_clip(app, t):
    e = app.timeline
    stops = [(0, 640, 760), (0.6, *_ruler(0.0)), (0.8, *_ruler(0.0)), (2.6, *_ruler(1.1)), (3.0, *_ruler(1.1)),
             (3.9, *_ruler(0.35)), (4.6, *_ruler(0.35))]
    x, y = glide(t, stops)
    dragging = 0.8 <= t < 3.9
    if t >= 0.8:
        e.seek(max(0.0, round((x - LANE_X0) / PX_PER_S, 2)))
    return Shot(None, (x, y), dragging)


def _fade_only(app: Any) -> None:
    e = app.timeline
    e.new_clip()
    e.rename_clip("intro")
    app.doc.select("title")
    app._selection_changed()
    e.add_track("title:opacity"); e.seek(0.6); e.add_key("title:opacity"); e.set_key_value(1.0)
    e.seek(0); e.select_key("title:opacity", 0.0); e.set_key_value(0.0)
    e.selected = None
    e.seek(0)


SCALE_LANE_Y = 679


@clip("editor-keys", "Adding a track from the panel, double-clicking a lane to add a key, dragging it and picking its easing.",
      DESIGNER_SIZE, 7.0, app=_designer(_fade_only), crop=DESIGNER_CROP, scale=1.0, fps=24)
def editor_keys_clip(app, t):
    e = app.timeline
    if t == 0 and e.clip.track("title:scale") is not None:  # a second pass (a still, then the recording)
        e.remove_track("title:scale")
    stops = [(0, 700, 760), (0.6, 330, 708), (1.1, 330, 708), (1.6, 313, 818), (2.0, 313, 818),
             (2.6, *_ruler(0.8)[:1], SCALE_LANE_Y), (3.2, *_ruler(0.8)[:1], SCALE_LANE_Y),
             (4.4, *_ruler(0.45)[:1], SCALE_LANE_Y), (4.9, *_ruler(0.45)[:1], SCALE_LANE_Y),
             (5.5, 760, 853), (7.0, 760, 853)]
    x, y = glide(t, stops)
    clicks = [(0.8, 0.9), (1.85, 1.95), (2.75, 2.82), (2.9, 2.97), (5.6, 5.7)]
    pressed = any(a <= t < b for a, b in clicks) or 3.4 <= t < 4.5
    track = e.clip.track("title:scale")
    if 0.9 <= t and track is None and not e.adding:
        e.adding = True
    if t >= 1.95 and track is None:
        e.adding = False
        e.add_track("title:scale")
        e.select_key("title:scale", 0.0)
        e.set_key_value(0.6)
        e.selected = None
    if t >= 2.97 and len(e.clip.track("title:scale").keys) == 1:
        e.add_key_x("title:scale", 0.8 * PX_PER_S)
        e.set_key_value(1.0)
        e.seek(0)
    if 3.4 <= t < 4.5:
        if e.dragging is None:
            e.start_drag("title:scale", 0.8)
        e.drag_to(x - LANE_X0)
    elif e.dragging is not None:
        e.end_drag()
    if t >= 5.7 and e.key() is not None and e.key().easing != "ease_out_back":
        e.set_key_easing("ease_out_back")
    return Shot(None, (x, y), pressed)


# -- rendering ------------------------------------------------------------------------------------
def _cursor(img: Any, at: tuple[float, float], pressed: bool, s: float) -> None:
    """Draws an arrow pointer (and a ring while the button is down) at ``at`` (physical pixels)."""
    from PIL import ImageDraw

    x, y = at
    d = ImageDraw.Draw(img, "RGBA")
    if pressed:
        r = 13 * s
        d.ellipse((x - r, y - r, x + r, y + r), fill=(116, 173, 232, 70), outline=(116, 173, 232, 200),
                  width=int(s))
    arrow = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.5), (9.6, 18.4), (6.9, 12.3), (12.3, 12.3)]
    pts = [(x + px * s, y + py * s) for px, py in arrow]
    d.polygon([(px + s, py + s) for px, py in pts], fill=(0, 0, 0, 90))
    d.polygon(pts, fill=(255, 255, 255, 255), outline=(20, 20, 24, 255))
    d.line(pts + [pts[0]], fill=(20, 20, 24, 255), width=max(1, int(s)))


def frames(c: Clip, folder: Path) -> Iterator[Any]:
    from PIL import Image

    count = max(1, round(c.seconds * c.fps))
    app = c.app() if c.app else None
    path = folder / "frame.png"
    for i in range(count):
        t = i / c.fps
        shot = c.make(app, t) if app is not None else c.make(t)
        if not isinstance(shot, Shot):
            shot = Shot(shot)
        target = app if app is not None and shot.view is None else _View(shot.view)
        pz.screenshot(target, path, size=c.size, scale=c.scale, wait=0.0)
        with Image.open(path) as im:
            im = im.convert("RGB")
            if shot.pointer is not None:
                _cursor(im, (shot.pointer[0] * c.scale, shot.pointer[1] * c.scale), shot.pressed, c.scale)
            if c.crop:
                x, y, w, h = (round(v * c.scale) for v in c.crop)
                im = im.crop((x, y, x + w, y + h))
            yield im


def encode(c: Clip, images: list[Any]) -> Path:
    """Writes the animated WebP, merging repeated frames and lowering the quality until it fits."""
    from PIL import Image, ImageChops

    still: list[Any] = []
    durations: list[int] = []
    step = 1000 / c.fps
    for im in images:
        if still and ImageChops.difference(im, still[-1]).getbbox() is None:
            durations[-1] += step
        else:
            still.append(im)
            durations.append(step)
    durations = [round(d) for d in durations]
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{c.name}.webp"
    # Opaque RGB frames and no sub-frame packing: lossy frames that blend over the previous one
    # leave blocky trails. Past quality 56 the frames shrink instead of getting blurrier.
    still = [im.convert("RGB") for im in still]
    while True:
        for quality in (80, 72, 64, 56):
            buffer = io.BytesIO()
            still[0].save(buffer, "WEBP", save_all=True, append_images=still[1:], duration=durations, loop=0,
                          quality=quality, method=6, allow_mixed=False)
            if buffer.tell() <= BUDGET:
                break
        if buffer.tell() <= BUDGET or still[0].width < 900:
            break
        still = [im.resize((round(im.width * 0.85), round(im.height * 0.85)), Image.LANCZOS) for im in still]
    out.write_bytes(buffer.getvalue())
    return out


def record(c: Clip) -> None:
    started = time.time()
    with tempfile.TemporaryDirectory(prefix=f"pyzed-{c.name}-") as folder:
        images = list(frames(c, Path(folder)))
    out = encode(c, images)
    w, h = images[0].size
    print(f"{c.name:28} {w}x{h} {len(images)} frames {out.stat().st_size / 1000:.0f} KB "
          f"({time.time() - started:.0f}s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="*", help="record only the clips whose name contains one of these")
    parser.add_argument("--list", action="store_true", help="list the clips")
    parser.add_argument("--still", type=float, metavar="SECONDS",
                        help="save one frame of each clip at this time as a PNG in the current folder")
    args = parser.parse_args()
    if args.list:
        for c in CLIPS.values():
            print(f"{c.name:28} {c.description}")
        return
    for c in CLIPS.values():
        if args.names and not any(n in c.name for n in args.names):
            continue
        if args.still is not None:
            frame = next(frames(Clip(**{**c.__dict__, "seconds": 1 / c.fps, "make": _at(c, args.still)}),
                                Path(tempfile.mkdtemp())))
            frame.save(f"{c.name}.png")
            continue
        record(c)


def _at(c: Clip, seconds: float) -> Callable[..., Any]:
    """``c.make`` shifted so that its first frame is at ``seconds``."""
    return lambda *args: c.make(*args[:-1], args[-1] + seconds)


if __name__ == "__main__":
    main()
