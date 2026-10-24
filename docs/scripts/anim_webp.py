"""Animated WebP captures for the docs: a Pyzed view, driven off-screen by a short script.

    from anim_webp import record_webp, hover, press, type_text, wait

    record_webp(MyApp(), [hover("Save"), press(), wait(600)], size=(480, 200), out="save.webp")

The recording itself is ``pyzed.recording`` (also ``pyzed record`` on the command line, with batches
and a window): this module keeps the names the docs scripts use. The view is drawn by the same
off-screen renderer as ``pz.screenshot`` (no window, display or GPU), but with a pointer, a keyboard
and a clock: hover and press states, tooltips, focus, typing, scrolling and animations show up as
they do in a window, and time moves by exactly one frame per frame, so a clip comes out the same on
every machine.

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
(``allow_mixed``), which keeps text crisp. WebP effort is ``method=4``: ``6`` takes ten times as long
for files about 2 % smaller. ``crop="content"`` trims the clip to what changes plus a
margin. ``poster=`` also writes the first frame as a still WebP (for ``prefers-reduced-motion``).

CLI (records a snippet, the last expression of which is the widget, with a list of steps)::

    python docs/scripts/anim_webp.py out.webp --code 'ui.button("Save", None)' \\
        --steps 'hover("Save"); press(); wait(500)' --size 320x120 --theme "Pyzed Light"
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pyzed.recording import session as _session
from pyzed.recording.encode import encode_webp as _encode_webp
from pyzed.recording.encode import fit_quality, merge, save_poster  # noqa: F401
from pyzed.recording.images import (changes, content_box, crop_box, draw_pointer, fit_image,  # noqa: F401
                                    touches_edge)
from pyzed.recording.session import Take, clip_time  # noqa: F401
from pyzed.recording.steps import (STEPS, Context, Frame, Step, call, click, drag, ease, glide, hover, key,  # noqa: F401
                                   leave, move, parse_steps, press, scroll, set_state, snap, theme, type_text, wait)
from pyzed.recording.targets import as_app, snippet_widget  # noqa: F401

Point = tuple[float, float]

DARK_THEMES = ["Pyzed Dark", "One Dark", "Ayu Mirage", "Gruvbox Dark"]
LIGHT_THEMES = ["Pyzed Light", "One Light", "Ayu Light", "Gruvbox Light"]


def record_frames(app: Any, steps: Sequence[Step], *, size: Point, scale: float = 2, fps: int = 20) -> Take:
    """Plays ``steps`` on ``app`` and returns the take (its frames, ``pixels`` big)."""
    return _session.record(app, steps, size=size, scale=scale, fps=fps)


def images(take: Take, pointer: bool = True) -> list:
    """The frames as RGB images, with the pointer drawn on top when ``pointer``."""
    return list(take.images(pointer))


def encode_webp(frames: Sequence, out: Path | str | None, *, fps: float = 20, quality: int = 80, method: int = 4,
                durations: Sequence[int] | None = None, lossless: bool = False) -> bytes:
    """Encodes ``frames`` (PIL images) as a looping animated WebP; identical frames are merged."""
    merged = None
    if durations:
        merged = ([], [])
        for im, ms in zip(frames, durations):
            if merged[0] and im.tobytes() == merged[0][-1].tobytes():
                merged[1][-1] += ms
            else:
                merged[0].append(im)
                merged[1].append(ms)
    data = _encode_webp(frames, fps=fps, quality=quality, method=method, lossless=lossless, merged=merged)
    if out is not None:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_bytes(data)
    return data


def fit_webp(frames: Sequence, out: Path | str, *, fps: float = 20, target: int = 150_000,
             qualities: Sequence[int] = (82, 52), method: int = 4) -> tuple[bytes, int]:
    """Like :func:`encode_webp`, with the best quality between ``qualities`` (highest and lowest) whose
    file fits ``target`` bytes, found by bisection. Returns the bytes written and the quality used."""
    merged = merge(frames, fps)
    data, quality = fit_quality(
        lambda q: _encode_webp(frames, fps=fps, quality=q, method=method, merged=merged), target,
        low=min(qualities), high=max(qualities))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(data)
    return data, quality



def record_webp(target: Any, steps: Sequence[Step], *, out: Path | str, size: Point = (720, 360),
                theme: str | None = "Pyzed Dark", scale: float = 2, fps: int = 20, pointer: bool = True,  # noqa: F811
                crop: str | tuple | None = None, margin: int = 40, quality: int = 80, poster: Path | str | None = None,
                fit: tuple[int, int] | None = None) -> dict:
    """Records ``target`` (an App, App class or a function returning the widget) playing ``steps``
    and writes an animated WebP to ``out``. Returns ``{"bytes", "frames", "unique", "size"}``.

    ``crop="content"`` trims to what is drawn (plus ``margin`` image pixels); ``fit=(w, h)``
    then scales the clip down to fit that box (gallery thumbnails).
    """
    take = _session.record(target, steps, size=size, scale=scale, fps=fps, theme=theme)
    frames = images(take, pointer=pointer)
    if crop == "content":
        box = crop_box(images(take, pointer=False), margin)
        frames = [f.crop(box) for f in frames]
    elif isinstance(crop, tuple):
        frames = [f.crop(crop) for f in frames]
    if fit:
        frames = [fit_image(f, fit) for f in frames]
    data = encode_webp(frames, out, fps=fps, quality=quality)
    if poster:
        save_poster(frames[0], poster)
    return {"bytes": len(data), "frames": len(frames), "unique": changes(frames), "size": frames[0].size}


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
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", help="the .webp to write")
    parser.add_argument("--code", required=True, help="a snippet whose last expression is the widget")
    parser.add_argument("--steps", default="hover('center'); press(); wait(600)",
                        help="steps separated by ';' (wait, move, hover, press, drag, type_text, key, scroll...)")
    parser.add_argument("--size", default="720x360", help="canvas in logical pixels, WxH")
    parser.add_argument("--theme", default="Pyzed Dark")
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--quality", type=int, default=80)
    parser.add_argument("--crop", action="store_true", help="trim to the content plus a margin")
    parser.add_argument("--no-pointer", action="store_true", help="don't draw the pointer")
    parser.add_argument("--poster", help="also write the first frame here (a still .webp)")
    args = parser.parse_args(argv)
    w, h = (float(v) for v in args.size.lower().split("x"))
    steps = parse_steps(args.steps)
    result = record_webp(snippet_widget(args.code), steps, out=args.out, size=(w, h), theme=args.theme, fps=args.fps,
                         quality=args.quality, crop="content" if args.crop else None, pointer=not args.no_pointer,
                         poster=args.poster)
    print(f"wrote {args.out}: {result['size'][0]}x{result['size'][1]}, {result['frames']} frames "
          f"({result['unique']} distinct), {result['bytes'] / 1000:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
