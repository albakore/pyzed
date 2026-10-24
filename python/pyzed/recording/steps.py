"""The steps of a clip: what the pointer, the keyboard and the clock do while frames are filmed.

Each step films the frames it takes, at the clip's ``fps``:

* ``wait(ms)``: time passes (animations, spinners, carets and shaders move).
* ``move(target, ms)`` / ``hover(target, ms, hold)``: the pointer glides to ``target`` (and stays).
* ``press(target=None, hold)`` / ``click``: a left click (pressed for ``hold`` ms).
* ``drag(start, end, ms)``: press at ``start``, glide to ``end``, release (sliders, splitters).
* ``type_text(text, cps)``: types into the focused field, ``cps`` characters per second.
* ``key(name, mods="")``: one key ("Enter", "Tab", "Down", "a"; mods like ``"ctrl"``).
* ``scroll(lines, target=None)``: the wheel over ``target`` (positive scrolls down).
* ``leave(ms)``: the pointer leaves (hover states end).
* ``call(fn)``: ``fn(app)`` changes the app's state; ``set_state(**attrs)`` sets attributes.
* ``theme(name)``: switches the app's theme.
* ``snap()``: films one frame.

A ``target`` is a point ``(x, y)`` in logical pixels, a text shown in the view (``"Save"``: its
center; ``"1#1"``: the second text ``"1"``), ``"input"`` / ``"input:1"`` (the first / second text field), ``"focusable:n"``,
``"scrollable"``, ``"center"`` (the center of what is drawn), ``"@0.25,0.5"`` (a point relative to
what is drawn), a ``(target, dx, dy)`` tuple to aim beside a target, or ``fn(ctx) -> (x, y)``.
"""

from __future__ import annotations

import ast
import sys
import time as _time
import types
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, List, Optional, Tuple

__all__ = ["STEPS", "Context", "Frame", "Step", "call", "click", "drag", "ease", "glide", "hover", "key", "leave",
           "move", "parse_steps", "press", "scroll", "set_state", "snap", "theme", "type_text", "wait"]

Point = Tuple[float, float]


@dataclass
class Step:
    """One piece of a clip: ``run(ctx)`` is a generator that drives ``ctx`` (see ``Context``)."""

    run: Callable[[Context], Iterator[Any]]
    label: str = ""

    def __repr__(self) -> str:
        return f"<step {self.label}>"


def _frames(ms: float, fps: float) -> int:
    return max(1, round(ms / 1000 * fps))


def ease(t: float) -> float:
    """Ease-in-out (smoothstep), like a hand moving a mouse."""
    return t * t * (3 - 2 * t)


def glide(a: Point, b: Point, frames: int) -> Iterator[Point]:
    """Points from ``a`` to ``b`` with an ease-in-out, ``frames`` of them (``b`` last)."""
    for i in range(1, frames + 1):
        t = ease(i / frames)
        yield (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def wait(ms: float = 500) -> Step:
    def run(ctx):
        for _ in range(_frames(ms, ctx.fps)):
            yield from ctx.tick()

    return Step(run, f"wait({ms})")


def move(target: Any, ms: float = 350) -> Step:
    def run(ctx):
        to = yield from ctx.resolve(target)
        start = ctx.pointer if ctx.pointer is not None else ctx.entry_point(to)
        if ctx.pointer is None:
            ctx.pointer = start
            yield ("move", *start)
        for p in glide(start, to, _frames(ms, ctx.fps)):
            ctx.pointer = p
            yield ("move", *p)
            yield from ctx.tick()

    return Step(run, f"move({target!r})")


def hover(target: Any, ms: float = 350, hold: float = 500) -> Step:
    def run(ctx):
        yield from move(target, ms).run(ctx)
        yield from wait(hold).run(ctx)

    return Step(run, f"hover({target!r})")


def press(target: Any = None, hold: float = 160, after: float = 300) -> Step:
    def run(ctx):
        if target is not None:
            yield from move(target).run(ctx)
        ctx.pressed = True
        yield ("down", "left")
        yield from wait(hold).run(ctx)
        ctx.pressed = False
        yield ("up", "left")
        yield from wait(after).run(ctx)

    return Step(run, f"press({target!r})")


click = press


def drag(start: Any, end: Any, ms: float = 700, after: float = 300) -> Step:
    def run(ctx):
        yield from move(start).run(ctx)
        ctx.pressed = True
        yield ("down", "left")
        yield from wait(120).run(ctx)
        to = yield from ctx.resolve(end)
        for p in glide(ctx.pointer, to, _frames(ms, ctx.fps)):
            ctx.pointer = p
            yield ("move", *p)
            yield from ctx.tick()
        ctx.pressed = False
        yield ("up", "left")
        yield from wait(after).run(ctx)

    return Step(run, f"drag({start!r}, {end!r})")


def type_text(text: str, cps: float = 14, after: float = 300) -> Step:
    def run(ctx):
        per = max(1, round(ctx.fps / cps))
        for ch in text:
            yield ("type", ch)
            for _ in range(per):
                yield from ctx.tick()
        yield from wait(after).run(ctx)

    return Step(run, f"type_text({text!r})")


def key(name: str, mods: str = "", after: float = 300) -> Step:
    def run(ctx):
        yield ("key", name, mods)
        yield from wait(after).run(ctx)

    return Step(run, f"key({name!r})")


def scroll(lines: float, target: Any = None, ms: float = 600) -> Step:
    def run(ctx):
        if target is not None:
            yield from move(target).run(ctx)
        n = _frames(ms, ctx.fps)
        for _ in range(n):
            yield ("scroll", 0.0, -lines / n)
            yield from ctx.tick()

    return Step(run, f"scroll({lines})")


def leave(ms: float = 300) -> Step:
    def run(ctx):
        if ctx.pointer is not None:
            out = ctx.entry_point(ctx.pointer)
            for p in glide(ctx.pointer, out, _frames(ms, ctx.fps)):
                ctx.pointer = p
                yield ("move", *p)
                yield from ctx.tick()
        ctx.pointer = None
        yield ("leave",)
        yield from ctx.tick()

    return Step(run, "leave()")


def call(fn: Callable[[Any], Any]) -> Step:
    def run(ctx):
        fn(ctx.app)
        yield from ctx.tick()

    return Step(run, f"call({getattr(fn, '__name__', fn)})")


def set_state(**attrs: Any) -> Step:
    def run(ctx):
        for name, value in attrs.items():
            setattr(ctx.app, name, value)
        yield from ctx.tick()

    return Step(run, f"set_state({', '.join(attrs)})")


def theme(name: str) -> Step:
    def run(ctx):
        from .. import themes

        ctx.app.theme = themes.get(name)
        yield from ctx.tick()

    return Step(run, f"theme({name!r})")


def snap() -> Step:
    def run(ctx):
        yield from ctx.tick()

    return Step(run, "snap()")


#: The steps a text script may use (``parse_steps``).
STEPS = {f.__name__: f for f in (wait, move, hover, press, drag, type_text, key, scroll, leave, theme, snap)}
STEPS["click"] = click


def parse_steps(text: str) -> List[Step]:
    """Steps written as text, one call per line or separated by ``;``: ``hover("Save"); press(); wait(600)``.

    Only the step functions and plain values (numbers, strings, tuples, lists) are allowed, so a
    job file can't run other code."""
    try:
        tree = ast.parse("\n".join(line.strip() for line in text.splitlines()), mode="exec")
    except SyntaxError as err:
        raise ValueError(f"steps: {err.msg} (line {err.lineno})") from None
    steps = []
    for node in tree.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            raise ValueError(f"not a step: {ast.unparse(node)!r}")
        call_ = node.value
        if not isinstance(call_.func, ast.Name) or call_.func.id not in STEPS:
            raise ValueError(f"unknown step {ast.unparse(call_.func)!r} (use {', '.join(sorted(STEPS))})")
        try:
            args = [ast.literal_eval(a) for a in call_.args]
            kwargs = {k.arg: ast.literal_eval(k.value) for k in call_.keywords if k.arg}
        except ValueError:
            raise ValueError(f"{ast.unparse(call_)}: only plain values (numbers, text, tuples)") from None
        steps.append(STEPS[call_.func.id](*args, **kwargs))
    return steps


# -- the context the steps drive -------------------------------------------------------------------
@dataclass
class Frame:
    rgba: bytes
    pointer: Optional[Point]
    pressed: bool


@dataclass
class Context:
    """What the steps drive: the app, the pointer, the clock and the frames filmed so far."""

    app: Any
    size: Point
    scale: float
    fps: float
    pixels: Tuple[int, int] = (0, 0)
    pointer: Optional[Point] = None
    pressed: bool = False
    t: float = 0.0
    frames: List[Frame] = field(default_factory=list)
    #: Which renderer drew the frames ("wgpu" or "tiny-skia") and whether a ``pz.shader`` was drawn.
    renderer: str = ""
    shader: bool = False
    _probe: Optional[list] = None
    _content: Optional[Tuple[float, float, float, float]] = None

    def tick(self):
        """One frame: the clock moves by 1/fps, then the view is drawn."""
        self.t += 1 / self.fps
        yield ("advance", 1 / self.fps)
        rgba = yield ("snap",)
        self.frames.append(Frame(rgba, self.pointer, self.pressed))
        self._probe = None

    def probe(self):
        if self._probe is None:
            self._probe = yield ("probe",)
        return self._probe

    def content(self) -> Tuple[float, float, float, float]:
        """The bounds of what is drawn on the first frame (logical pixels): x, y, w, h."""
        if self._content is None:
            from .images import content_box, to_image

            image = to_image(self.frames[0].rgba, self.pixels)
            box = content_box(image) or (0, 0, image.width, image.height)
            s = self.scale
            self._content = (box[0] / s, box[1] / s, (box[2] - box[0]) / s, (box[3] - box[1]) / s)
        return self._content

    def entry_point(self, to: Point) -> Point:
        """Where the pointer comes from: below and to the right of ``to``, inside the frame."""
        w, h = self.size
        return (min(w - 4, to[0] + max(60, w * 0.18)), min(h - 4, to[1] + max(40, h * 0.22)))

    def resolve(self, target: Any):
        """``target`` as a point (a generator: it may need to probe the view)."""
        if callable(target):
            return target(self)
        if isinstance(target, (tuple, list)) and len(target) == 3 and isinstance(target[0], str):
            x, y = yield from self.resolve(target[0])
            return (x + target[1], y + target[2])
        if isinstance(target, (tuple, list)):
            return (float(target[0]), float(target[1]))
        if not isinstance(target, str):
            raise TypeError(f"not a target: {target!r}")
        if not self.frames:
            yield from self.tick()
        if target == "center":
            x, y, w, h = self.content()
            return (x + w / 2, y + h / 2)
        if target.startswith("@"):
            fx, fy = (float(v) for v in target[1:].split(","))
            x, y, w, h = self.content()
            return (x + w * fx, y + h * fy)
        found = yield from self.probe()
        kind, _, index = target.partition(":")
        if kind in ("input", "focusable", "scrollable", "container"):
            items = [f for f in found if f[0] == kind]
            i = int(index or 0)
            if i < len(items):
                _, _, x, y, w, h = items[i]
                return (x + min(w / 2, 60) if kind == "input" else x + w / 2, y + h / 2)
            raise LookupError(f"no {target} in the view ({len(items)} found)")
        text, nth = target, 0
        head, sep, tail = target.rpartition("#")
        if sep and head and tail.isdigit():  # "1#2": the third text "1"
            text, nth = head, int(tail)
        # In reading order (top to bottom, then left to right), so "#n" counts the way a person does.
        texts = sorted((f for f in found if f[0] == "text"), key=lambda f: (round(f[3]), f[2]))
        for match in (lambda s: s == text, lambda s: s.strip() == text.strip(), lambda s: text in s):
            hits = [f for f in texts if match(f[1])]
            if len(hits) > nth:
                _, _, x, y, w, h = hits[nth]
                return (x + w / 2, y + h / 2)
        raise LookupError(f"no text {target!r} in the view")


class _Clock(types.ModuleType):
    """A stand-in for the ``time`` module whose clocks follow the recording's virtual time."""

    def __init__(self, ctx: Context):
        super().__init__("time")
        self._ctx = ctx
        self._base = _time.monotonic()
        self._wall = _time.time()

    def __getattr__(self, name):
        return getattr(_time, name)

    def monotonic(self):
        return self._base + self._ctx.t

    perf_counter = monotonic

    def time(self):
        return self._wall + self._ctx.t


def patch_clock(ctx: Context) -> List[Tuple[Any, Any]]:
    """Points the ``time`` that Pyzed's modules imported (``ui.spinner`` reads it) at the clip's clock;
    returns what to put back."""
    clock = _Clock(ctx)
    patched = []
    for name, module in list(sys.modules.items()):
        if (name == "pyzed" or name.startswith("pyzed.")) and getattr(module, "time", None) is _time:
            patched.append((module, _time))
            module.time = clock
    return patched
