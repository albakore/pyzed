"""Animated WebP captures for the docs: a Pyzed view, driven off-screen by a short script.

    from anim_webp import record_webp, hover, press, type_text, wait

    record_webp(MyApp(), [hover("Save"), press(), wait(600)], size=(480, 200), out="save.webp")

The view is drawn by the same off-screen renderer as ``pz.screenshot`` (no window, display or GPU),
but with a pointer, a keyboard and a clock (``pyzed._core.record``): hover and press states,
tooltips, focus, typing, scrolling and animations show up as they do in a window, and time moves
by exactly one frame per frame, so a clip comes out the same on every machine.

Steps (each one films the frames it takes, at ``fps``):

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

A ``target`` is a point ``(x, y)`` in logical pixels, a text shown in the view (``"Save"``: its
center), ``"input"`` / ``"input:1"`` (the first / second text field), ``"focusable:n"``,
``"scrollable"``, ``"center"`` (the center of what is drawn), ``"@0.25,0.5"`` (a point relative to
what is drawn), a ``(target, dx, dy)`` tuple to aim beside a target, or ``fn(ctx) -> (x, y)``.

Encoding: identical consecutive frames are merged (one frame, a longer duration), the clip loops
forever and is lossy (``quality``) with lossless frames where they come out smaller
(``allow_mixed``), which keeps text crisp. ``crop="content"`` trims the clip to what changes plus a
margin. ``poster=`` also writes the first frame as a still WebP (for ``prefers-reduced-motion``).

CLI (records a snippet, the last expression of which is the widget, with a list of steps)::

    python docs/scripts/anim_webp.py out.webp --code 'ui.button("Save", None)' \\
        --steps 'hover("Save"); press(); wait(500)' --size 320x120 --theme "One Light"
"""

from __future__ import annotations

import argparse
import ast
import builtins
import io
import itertools
import sys
import time as _time
import types
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyzed as pz
from pyzed import _core

Point = tuple[float, float]

DARK_THEMES = ["One Dark", "Ayu Mirage", "Gruvbox Dark", "Pyzed Midnight"]
LIGHT_THEMES = ["One Light", "Ayu Light", "Gruvbox Light", "Pyzed Dawn"]


# -- steps -----------------------------------------------------------------------------------------
@dataclass
class Step:
    """One piece of a clip: ``run(ctx)`` is a generator that drives ``ctx`` (see ``Context``)."""

    run: Callable[[Context], Iterator[Any]]
    label: str = ""

    def __repr__(self) -> str:
        return f"<step {self.label}>"


def _frames(ms: float, fps: int) -> int:
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
        ctx.app.theme = pz.themes.get(name)
        yield from ctx.tick()

    return Step(run, f"theme({name!r})")


def snap() -> Step:
    def run(ctx):
        yield from ctx.tick()

    return Step(run, "snap()")


# -- recording -------------------------------------------------------------------------------------
@dataclass
class Frame:
    rgba: bytes
    pointer: Point | None
    pressed: bool


@dataclass
class Context:
    """What the steps drive: the app, the pointer, the clock and the frames filmed so far."""

    app: Any
    size: Point
    scale: float
    fps: int
    pixels: tuple[int, int] = (0, 0)
    pointer: Point | None = None
    pressed: bool = False
    t: float = 0.0
    frames: list[Frame] = field(default_factory=list)
    _probe: list | None = None
    _content: tuple[float, float, float, float] | None = None

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

    def content(self) -> tuple[float, float, float, float]:
        """The bounds of what is drawn on the first frame (logical pixels): x, y, w, h."""
        if self._content is None:
            from PIL import Image

            image = Image.frombytes("RGBA", self.pixels, self.frames[0].rgba).convert("RGB")
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
        if isinstance(target, tuple) and len(target) == 3 and isinstance(target[0], str):
            x, y = yield from self.resolve(target[0])
            return (x + target[1], y + target[2])
        if isinstance(target, tuple):
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
        texts = [f for f in found if f[0] == "text"]
        for match in (lambda s: s == target, lambda s: s.strip() == target.strip(), lambda s: target in s):
            hits = [f for f in texts if match(f[1])]
            if hits:
                _, _, x, y, w, h = hits[0]
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


def _patch_clock(ctx: Context) -> list[tuple[Any, Any]]:
    """Points the ``time`` that Pyzed's modules imported (``ui.spinner`` reads it) at the clip's clock."""
    clock = _Clock(ctx)
    patched = []
    for name, module in list(sys.modules.items()):
        if (name == "pyzed" or name.startswith("pyzed.")) and getattr(module, "time", None) is _time:
            patched.append((module, _time))
            module.time = clock
    return patched


def as_app(target: Any, theme_name: str | None = None, bg: str | None = "editor", padding: float = 24) -> Any:
    """An ``App`` for ``target``: an App (instance or class) or a function returning the widget."""
    if isinstance(target, type):
        target = target()
    if isinstance(target, pz.App):
        if theme_name:
            target.theme = pz.themes.get(theme_name)
        return target
    if not callable(target):
        raise TypeError("record a pz.App or a function that returns the widget")
    build = target

    class Clip(pz.App):
        theme = pz.themes.get(theme_name or "One Dark")

        def view(self):
            widget = build()
            if bg is None:
                return widget
            t = self.resolved_theme()
            return pz.container(widget, center=True, padding=padding, width="fill", height="fill",
                                bg=getattr(t, bg))

    return Clip()


_RECORDING: list[Context] = []


def clip_time() -> float:
    """Seconds since the clip being recorded started (0 outside a recording): views can read it to
    move things that would otherwise stand still (a progress bar filling up)."""
    return _RECORDING[-1].t if _RECORDING else 0.0


def record_frames(app: Any, steps: Sequence[Step], *, size: Point, scale: float = 2, fps: int = 20) -> Context:
    """Plays ``steps`` on ``app`` and returns the context with its frames (RGBA, ``ctx.pixels``)."""
    ctx = Context(app=app, size=(float(size[0]), float(size[1])), scale=scale, fps=fps)

    def script():
        ctx.pixels = tuple((yield ("size",)))
        for step in steps:
            yield from step.run(ctx)
        if not ctx.frames:
            yield from ctx.tick()

    patched = _patch_clock(ctx)
    _RECORDING.append(ctx)
    try:
        _core.record(app, script(), size=ctx.size, scale=scale)
    finally:
        _RECORDING.pop()
        for module, original in patched:
            module.time = original
    return ctx


# -- images ----------------------------------------------------------------------------------------
def content_box(image, threshold: int = 10, background=None) -> tuple[int, int, int, int] | None:
    """The bounding box of what differs from the background (the color at (2, 2))."""
    from PIL import Image, ImageChops

    bg = Image.new("RGB", image.size, background or image.getpixel((2, 2)))
    return ImageChops.difference(image.convert("RGB"), bg).point(lambda v: 255 if v > threshold else 0).getbbox()


def draw_pointer(img, at: Point, pressed: bool = False, scale: float = 2) -> None:
    """Draws an arrow pointer (and a ring while the button is down) at ``at`` (image pixels)."""
    from PIL import ImageDraw

    x, y = at
    s = scale
    d = ImageDraw.Draw(img, "RGBA")
    if pressed:
        r = 13 * s
        d.ellipse((x - r, y - r, x + r, y + r), fill=(116, 173, 232, 70), outline=(116, 173, 232, 200), width=int(s))
    arrow = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.5), (9.6, 18.4), (6.9, 12.3), (12.3, 12.3)]
    pts = [(x + px * s, y + py * s) for px, py in arrow]
    d.polygon([(px + s, py + s) for px, py in pts], fill=(0, 0, 0, 90))
    d.polygon(pts, fill=(255, 255, 255, 255), outline=(20, 20, 24, 255))
    d.line(pts + [pts[0]], fill=(20, 20, 24, 255), width=max(1, int(s)))


def images(ctx: Context, pointer: bool = True) -> list:
    """The frames as RGB images, with the pointer drawn on top when ``pointer``."""
    from PIL import Image

    out = []
    for frame in ctx.frames:
        im = Image.frombytes("RGBA", ctx.pixels, frame.rgba).convert("RGB")
        if pointer and frame.pointer is not None:
            draw_pointer(im, (frame.pointer[0] * ctx.scale, frame.pointer[1] * ctx.scale), frame.pressed, ctx.scale)
        out.append(im)
    return out


def changes(frames: Sequence) -> int:
    """How many distinct consecutive frames there are (1: nothing moves)."""
    n = 1
    for a, b in itertools.pairwise(frames):
        if a.tobytes() != b.tobytes():
            n += 1
    return n


def crop_box(frames: Sequence, margin: int, even: bool = True) -> tuple[int, int, int, int]:
    """The union of every frame's content box (against its own background), plus ``margin``."""
    w, h = frames[0].size
    boxes = [b for b in (content_box(f) for f in frames) if b]
    if not boxes:
        return (0, 0, w, h)
    left = max(min(b[0] for b in boxes) - margin, 0)
    top = max(min(b[1] for b in boxes) - margin, 0)
    right = min(max(b[2] for b in boxes) + margin, w)
    bottom = min(max(b[3] for b in boxes) + margin, h)
    if even:
        right -= (right - left) % 2
        bottom -= (bottom - top) % 2
    return (left, top, right, bottom)


def touches_edge(frames: Sequence) -> bool:
    """Whether what is drawn reaches the edge of the canvas (the canvas is too small)."""
    w, h = frames[0].size
    for f in frames:
        b = content_box(f)
        if b and (b[0] <= 2 or b[1] <= 2 or b[2] >= w - 2 or b[3] >= h - 2):
            return True
    return False


def encode_webp(frames: Sequence, out: Path | str | None, *, fps: float = 20, quality: int = 80, method: int = 6,
                durations: Sequence[int] | None = None, lossless: bool = False) -> bytes:
    """Encodes ``frames`` (PIL images) as a looping animated WebP; identical frames are merged."""
    merged, times = [], []
    step = durations or [round(1000 / fps)] * len(frames)
    for im, ms in zip(frames, step):
        if merged and im.tobytes() == merged[-1].tobytes():
            times[-1] += ms
        else:
            merged.append(im)
            times.append(ms)
    buf = io.BytesIO()
    first, rest = merged[0], merged[1:]
    first.save(buf, "WEBP", save_all=True, append_images=rest, duration=times, loop=0, quality=quality,
               method=method, lossless=lossless, allow_mixed=not lossless, minimize_size=True)
    data = buf.getvalue()
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_bytes(data)
    return data


def fit_webp(frames: Sequence, out: Path | str, *, fps: float = 20, target: int = 150_000,
             qualities: Sequence[int] = (82, 76, 70, 64, 58, 52), method: int = 6) -> tuple[bytes, int]:
    """Like :func:`encode_webp`, lowering the quality step by step until the file fits ``target`` bytes
    (or the lowest quality is reached). Returns the bytes written and the quality used."""
    for quality in qualities:
        data = encode_webp(frames, None, fps=fps, quality=quality, method=method)
        if len(data) <= target:
            break
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(data)
    return data, quality


def save_poster(image, out: Path | str, quality: int = 82) -> None:
    """A still WebP of one frame (what ``prefers-reduced-motion`` shows)."""
    image.save(out, "WEBP", quality=quality, method=6)


def record_webp(target: Any, steps: Sequence[Step], *, out: Path | str, size: Point = (720, 360),
                theme: str | None = "One Dark", scale: float = 2, fps: int = 20, pointer: bool = True,
                crop: str | tuple | None = None, margin: int = 40, quality: int = 80, poster: Path | str | None = None,
                fit: tuple[int, int] | None = None) -> dict:
    """Records ``target`` (an App, App class or a function returning the widget) playing ``steps``
    and writes an animated WebP to ``out``. Returns ``{"bytes", "frames", "unique", "size"}``.

    ``crop="content"`` trims to what is drawn (plus ``margin`` image pixels); ``fit=(w, h)``
    then scales the clip down to fit that box (gallery thumbnails).
    """
    app = as_app(target, theme)
    ctx = record_frames(app, steps, size=size, scale=scale, fps=fps)
    frames = images(ctx, pointer=pointer)
    if crop == "content":
        box = crop_box(images(ctx, pointer=False), margin)
        frames = [f.crop(box) for f in frames]
    elif isinstance(crop, tuple):
        frames = [f.crop(crop) for f in frames]
    if fit:
        frames = [fit_image(f, fit) for f in frames]
    data = encode_webp(frames, out, fps=fps, quality=quality)
    if poster:
        save_poster(frames[0], poster)
    return {"bytes": len(data), "frames": len(frames), "unique": changes(frames), "size": frames[0].size}


def fit_image(image, box: tuple[int, int]):
    from PIL import Image

    w, h = image.size
    k = min(box[0] / w, box[1] / h, 1.0)
    if k >= 1.0:
        return image
    return image.resize((max(2, round(w * k)), max(2, round(h * k))), Image.LANCZOS)


def info(path: Path | str) -> dict:
    """Frames, total duration (ms), size and bytes of an animated WebP."""
    from PIL import Image

    with Image.open(path) as im:
        n = getattr(im, "n_frames", 1)
        total = 0
        for i in range(n):
            im.seek(i)
            total += im.info.get("duration", 0)
        return {"frames": n, "duration": total, "size": im.size, "bytes": Path(path).stat().st_size}


# -- CLI -------------------------------------------------------------------------------------------
STEPS = {f.__name__: f for f in (wait, move, hover, press, click, drag, type_text, key, scroll, leave, theme, snap)}


def snippet_widget(code: str) -> Callable[[], Any]:
    """A function that runs ``code`` (``pz``, ``ui`` and ``draw`` imported; its last expression is
    the widget; other free names are do-nothing callbacks) and returns the widget."""
    from pyzed import draw, ui

    tree = ast.parse(code)
    *body, last = tree.body
    if not isinstance(last, ast.Expr):
        raise ValueError("the snippet must end with an expression (the widget)")

    def build():
        ns: dict = {"pz": pz, "ui": ui, "draw": draw}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id not in ns and not hasattr(builtins, node.id):
                ns[node.id] = lambda *a, **k: None
        exec(compile(ast.Module(body=body, type_ignores=[]), "app.py", "exec"), ns)
        return eval(compile(ast.Expression(last.value), "app.py", "eval"), ns)

    return build


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", help="the .webp to write")
    parser.add_argument("--code", required=True, help="a snippet whose last expression is the widget")
    parser.add_argument("--steps", default="hover('center'); press(); wait(600)",
                        help="steps separated by ';' (wait, move, hover, press, drag, type_text, key, scroll...)")
    parser.add_argument("--size", default="720x360", help="canvas in logical pixels, WxH")
    parser.add_argument("--theme", default="One Dark")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--quality", type=int, default=80)
    parser.add_argument("--crop", action="store_true", help="trim to the content plus a margin")
    parser.add_argument("--no-pointer", action="store_true", help="don't draw the pointer")
    parser.add_argument("--poster", help="also write the first frame here (a still .webp)")
    args = parser.parse_args(argv)
    w, h = (float(v) for v in args.size.lower().split("x"))
    steps = [eval(s, {"__builtins__": {}}, STEPS) for s in args.steps.split(";") if s.strip()]
    result = record_webp(snippet_widget(args.code), steps, out=args.out, size=(w, h), theme=args.theme, fps=args.fps,
                         quality=args.quality, crop="content" if args.crop else None, pointer=not args.no_pointer,
                         poster=args.poster)
    print(f"wrote {args.out}: {result['size'][0]}x{result['size'][1]}, {result['frames']} frames "
          f"({result['unique']} distinct), {result['bytes'] / 1000:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
