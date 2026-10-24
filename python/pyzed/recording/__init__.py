"""Screenshots and clips of Pyzed apps, recorded off-screen: one at a time or many in parallel.

    from pyzed import recording as rec

    take = rec.record(MyApp, [rec.hover("Save"), rec.press(), rec.wait(600)], size=(480, 270))
    rec.encode(take.images(), "save.webp", "webp", fps=take.fps)
    rec.screenshot(MyApp, size=(800, 600)).save("app.png")

The same from the command line, with a batch of jobs and a window to build them in::

    pyzed record shot app.py:MyApp -o app.png --size 800x600
    pyzed record clip app.py --steps 'hover("Save"); press()' -f webp,mp4
    pyzed record batch jobs.toml --jobs 4
    pyzed record gui jobs.toml

See ``pyzed.recording.steps`` for the steps, ``pyzed.recording.targets`` for what can be recorded and
``pyzed.recording.batch`` for job files.
"""

from __future__ import annotations

from .batch import Job, Task, expand, load_jobs, run, save_jobs
from .encode import FORMATS, encode, encode_webp, fit_quality, merge
from .images import changes, content_box, crop_box, draw_pointer, fit_image, touches_edge
from .session import RENDERERS, Take, clip_time, gpu, pick_renderer, record, screenshot
from .steps import (STEPS, Context, Frame, Step, call, click, drag, ease, glide, hover, key, leave, move, parse_steps,
                    press, scroll, set_state, snap, theme, type_text, wait)
from .targets import as_app, load, snippet_widget

__all__ = [
    "FORMATS", "RENDERERS", "STEPS", "Context", "Frame", "Job", "Step", "Take", "Task", "as_app", "call", "changes",
    "click", "clip_time", "content_box", "crop_box", "drag", "draw_pointer", "ease", "encode", "encode_webp",
    "expand", "fit_image", "fit_quality", "glide", "gpu", "hover", "key", "leave", "load", "load_jobs", "merge",
    "move", "parse_steps", "pick_renderer", "press", "record", "run", "save_jobs", "screenshot", "scroll",
    "set_state", "snap", "snippet_widget", "theme", "touches_edge", "type_text", "wait",
]
