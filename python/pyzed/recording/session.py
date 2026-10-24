"""Recording off-screen: stills and clips of an app, with no window, display or GPU needed.

The view is drawn by the same off-screen renderer as ``pz.screenshot``, with a pointer, a keyboard
and a clock: hover and press states, tooltips, focus, typing, scrolling and animations show up as
they do in a window, and time moves by exactly one frame per frame, so a clip comes out the same
on every machine however long a frame takes to draw.

Each process keeps the renderers it makes (a GPU device and its pipelines cost more than many
frames), so recording many clips in a row only pays for that once.
"""

from __future__ import annotations

import functools
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

from . import images as _images
from .steps import Context, Step, patch_clock
from .targets import as_app

__all__ = ["RENDERERS", "Take", "clip_time", "gpu", "pick_renderer", "record", "screenshot"]

#: The renderer choices: the GPU when there is a real one (else the CPU), the GPU, or the CPU.
RENDERERS = ("auto", "gpu", "cpu")

_RECORDING: List[Context] = []


@functools.lru_cache(maxsize=1)
def gpu() -> Optional[Tuple[str, str]]:
    """The GPU off-screen recordings draw with: ``(name, kind)`` (kind ``"discrete"``, ``"integrated"``,
    ``"virtual"``, ``"cpu"`` for a software driver like lavapipe, or ``"other"``), ``None`` without one."""
    from .. import _core

    return _core.offscreen_gpu()


def pick_renderer(choice: str = "auto") -> str:
    """``"gpu"`` or ``"cpu"`` for ``choice``. ``"auto"`` takes the GPU whenever there is one, a software
    Vulkan driver (lavapipe) included, so recordings look the same on every machine; the CPU renderer
    (tiny-skia) is two to three times faster than a software GPU, but draws blur, glow and glass a
    little differently: ask for ``"cpu"`` for quick drafts. ``PYZED_RECORD_RENDERER`` overrides ``"auto"``."""
    choice = (choice or "auto").lower()
    if choice == "auto":
        choice = os.environ.get("PYZED_RECORD_RENDERER", "auto").lower()
    if choice in ("gpu", "cpu"):
        return choice
    return "gpu" if gpu() is not None else "cpu"


def clip_time() -> float:
    """Seconds since the clip being recorded started (0 outside a recording): views can read it to
    move things that would otherwise stand still (a progress bar filling up)."""
    return _RECORDING[-1].t if _RECORDING else 0.0


@dataclass
class Take:
    """A recorded clip: its frames (RGBA bytes, ``pixels`` big), where the pointer was on each one,
    and how it was drawn."""

    frames: list
    pixels: Tuple[int, int]
    scale: float
    fps: float
    renderer: str = ""
    #: The view drew a ``pz.shader`` (the CPU renderer shows its fallback color instead).
    shader: bool = False
    _images: dict = field(default_factory=dict, repr=False)

    @property
    def duration(self) -> float:
        """Seconds."""
        return len(self.frames) / self.fps

    def images(self, pointer: bool = True) -> list:
        """The frames as RGB Pillow images, with the pointer drawn on top when ``pointer``."""
        if pointer not in self._images:
            out = []
            for frame in self.frames:
                im = _images.to_image(frame.rgba, self.pixels)
                if pointer and frame.pointer is not None:
                    at = (frame.pointer[0] * self.scale, frame.pointer[1] * self.scale)
                    _images.draw_pointer(im, at, frame.pressed, self.scale)
                out.append(im)
            self._images[pointer] = out
        return self._images[pointer]


def _context(app: Any, steps: Sequence[Step], size: Tuple[float, float], scale: float, fps: float,
             renderer: str) -> Context:
    from .. import _core

    ctx = Context(app=app, size=(float(size[0]), float(size[1])), scale=scale, fps=fps)

    def script():
        ctx.pixels = tuple((yield ("size",)))
        for step in steps:
            yield from step.run(ctx)
        if not ctx.frames:
            yield from ctx.tick()

    patched = patch_clock(ctx)
    _RECORDING.append(ctx)
    try:
        ctx.renderer, ctx.shader = _core.record(app, script(), size=ctx.size, scale=scale, renderer=renderer)
    finally:
        _RECORDING.pop()
        for module, original in patched:
            module.time = original
    return ctx


def record(target: Any, steps: Sequence[Step] = (), *, size: Tuple[float, float] = (720, 360), scale: float = 2,
           fps: float = 20, theme: Optional[str] = None, renderer: str = "auto") -> Take:
    """Plays ``steps`` on ``target`` (an App, App class, or a function returning an App or a widget)
    and returns the frames. Without steps it films one frame. ``renderer`` is ``"auto"``, ``"gpu"`` or
    ``"cpu"`` (see ``pick_renderer``)."""
    steps = list(steps)
    which = pick_renderer(renderer)
    ctx = _context(as_app(target, theme), steps, size, scale, fps, which)
    return Take(ctx.frames, ctx.pixels, scale, fps, ctx.renderer, ctx.shader)


def screenshot(target: Any, *, size: Optional[Tuple[float, float]] = None, scale: float = 2, wait: float = 0.1,
               theme: Optional[str] = None, renderer: str = "auto") -> Any:
    """A still of ``target`` as ``pz.screenshot`` draws it (no pointer, animations at rest), as an RGB
    Pillow image. ``renderer`` works as for ``record``."""
    from .. import _core

    which = pick_renderer(renderer)
    app = as_app(target, theme)
    w, h, rgba, name, _ = _core.screenshot_rgba(app, size=size, scale=scale, wait=wait, renderer=which)
    image = _images.to_image(rgba, (w, h))
    image.info["renderer"] = name
    return image
