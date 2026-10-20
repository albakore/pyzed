"""Records the animated WebP clips of the non-visual components' pages (docs/public/media/services/).

    python docs/scripts/record_services.py            # every clip
    python docs/scripts/record_services.py tray       # only the clips whose name contains a word
    python docs/scripts/record_services.py --list     # what there is to record

Frames are drawn off-screen with ``record.py``'s renderer (no window, display or GPU), at 2x, and
encoded by ffmpeg (``libwebp_anim``) into one looping animated WebP per clip, at most ``WIDTH`` pixels
wide. The events the clips show (a tick, a line of output, a worker's progress) are raised by hand
between frames, so every run gives the same clip. Needs ffmpeg and Pillow.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("PYZED_CONFIG_DIR", tempfile.mkdtemp(prefix="pyzed-record-config-"))

import record  # noqa: E402
from record import DESIGNER_SIZE, Clip, Frame, _designer, _form_origin, glide  # noqa: E402

ROOT = HERE.parents[1]
OUT = ROOT / "docs" / "public" / "media" / "services"
EXAMPLE = ROOT / "examples" / "designer" / "tasks.pzform"
WIDTH = 960
CLIPS: dict[str, Clip] = {}


def clip(name: str, title: str, *, fps: int = 20):
    def register(fn):
        CLIPS[name] = Clip(name, title, title, fps, fn)
        return fn
    return register


#: Rows of the toolbox once it is filtered to one category (logical pixels of a 1280x800 window).
TOOL_ROW = 203.0


def _tray_chip(app, index: int) -> tuple[float, float]:
    """Where the ``index``-th chip of the component tray is, under the 640x420 form of a new document."""
    from pyzed.designer import surface

    ox, oy = _form_origin(app)
    x = ox - 1 + 8 + 8 + index * (surface.TRAY_CHIP + surface.TRAY_GAP) + surface.TRAY_CHIP / 2
    return (x, oy + 420 + 16 + 10 + 18 + surface.TRAY_GAP + 14)


@clip("tray", "Adding non-visual components: they go to the tray under the form")
def tray_clip(c: Clip):
    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    app = _designer(work / "form1.pzform")
    app.doc.add("label", 24, 20, 240, 24)
    app.doc.form["label1"].props["text"] = "00:00:00"
    app.doc.select(None)
    size = DESIGNER_SIZE
    pointer = (640.0, 500.0)
    yield Frame(app, size, pointer, hold=8)
    for index, (query, type_) in enumerate((("tim", "timer"), ("watch", "file_watcher"), ("web", "http_request"))):
        target = (110.0, 117.0)
        for p in glide(pointer, target, 10):
            pointer = p
            yield Frame(app, size, pointer)
        typed = ""
        for ch in query:
            typed += ch
            app.set_toolbox_query(typed)
            yield Frame(app, size, pointer, hold=2)
        for p in glide(pointer, (70.0, TOOL_ROW), 8):
            pointer = p
            yield Frame(app, size, pointer)
        yield Frame(app, size, pointer, pressed=True, hold=3)
        app.pick_tool(type_)()
        app.toasts.clear()
        yield Frame(app, size, pointer, hold=10)
        app.set_toolbox_query("")
    # select the timer in the tray and open its tick handler
    chip = _tray_chip(app, 0)
    for p in glide(pointer, chip, 14):
        pointer = p
        yield Frame(app, size, pointer)
    app.press_tray("timer1")
    yield Frame(app, size, pointer, pressed=True, hold=3)
    yield Frame(app, size, pointer, hold=14)
    app.open_default_event("timer1")
    app.toasts.clear()
    yield Frame(app, size, pointer, pressed=True, hold=3)
    yield Frame(app, size, pointer, hold=c.fps * 2)


def _runner():
    """The task runner example, running off-screen, with its window host."""
    import pyzed as pz
    from pyzed.designer.model import load
    from pyzed.designer.runtime import FormWindow, load_handlers

    form = load(EXAMPLE)
    window = FormWindow(form, load_handlers(EXAMPLE, form), path=EXAMPLE)
    rt = window.runtime
    for service in rt.services.values():  # the clip raises the events itself
        service.stop()
    rt.services["toast"].enabled = False  # no real desktop notification while recording
    rt.loaded = True
    rt.dispatch(None, "load")

    class Host(pz.App):
        def __init__(self):
            self.theme = rt.theme

        def view(self):
            return window.view()

    return Host(), rt, (int(form.width), int(form.height))


ZEN = ["Beautiful is better than ugly.", "Explicit is better than implicit.", "Simple is better than complex.",
       "Complex is better than complicated.", "Flat is better than nested.", "Sparse is better than dense.",
       "Readability counts.", "Special cases aren't special enough to break the rules.",
       "Although practicality beats purity.", "Errors should never pass silently."]


@clip("runner", "A form with a timer, a process and a background worker, running")
def runner_clip(c: Clip):
    app, rt, size = _runner()
    form = rt.form
    clock = 0

    def tick():
        nonlocal clock
        clock += 1
        form["clock"].props["text"] = f"10:24:{clock:02d}"

    pointer = (300.0, 300.0)
    tick()
    yield Frame(app, size, pointer, hold=8)
    run = (486.0, 84.0)
    for p in glide(pointer, run, 10):
        pointer = p
        yield Frame(app, size, pointer)
    yield Frame(app, size, pointer, pressed=True, hold=3)
    rt.dispatch(form["run"], "click")
    for i, line in enumerate(ZEN):
        rt.dispatch(form["proc"], "output", line)
        if i % 4 == 0:
            tick()
        yield Frame(app, size, pointer, hold=3)
    rt.dispatch(form["proc"], "finished", 0)
    yield Frame(app, size, pointer, hold=10)
    count = (94.0, 344.0)
    for p in glide(pointer, count, 12):
        pointer = p
        yield Frame(app, size, pointer)
    yield Frame(app, size, pointer, pressed=True, hold=3)
    rt.dispatch(form["count"], "click")
    form["count"].props["text"] = "Cancel"
    for step, value in enumerate(range(0, 101, 4)):
        rt.dispatch(form["primes"], "progress", value)
        if step % 6 == 0:
            tick()
        yield Frame(app, size, pointer, hold=2)
    rt.dispatch(form["primes"], "done", 17984)
    yield Frame(app, size, pointer, hold=12)
    rt.dispatch(form["notes"], "change", ["/home/ada/todo.txt"])
    tick()
    yield Frame(app, size, pointer, hold=c.fps * 2)


@clip("watcher", "A File watcher listing the files created and deleted in a folder")
def watcher_clip(c: Clip):
    import pyzed as pz
    from pyzed import ui

    class Files(pz.App):
        def __init__(self):
            self.files = ["budget.csv", "notes.txt"]
            self.last = "Watching ~/inbox"

        def view(self):
            t = self.resolved_theme()
            rows = [ui.list_item(name, icon="file-text", theme=t) for name in self.files]
            return pz.container(pz.column([
                ui.heading("Inbox", level=3, theme=t),
                pz.container(pz.column(rows, spacing=2), height=150, width="fill"),
                ui.label(self.last, size="sm", color="text_muted", theme=t),
            ], spacing=12), padding=24, width="fill", height="fill", bg=t.background)

    app = Files()
    size = (420, 280)
    yield Frame(app, size, None, hold=16)
    for event, name in (("created", "photo.png"), ("created", "invoice.pdf"), ("deleted", "budget.csv"),
                        ("created", "plan.md")):
        if event == "created":
            app.files.append(name)
        else:
            app.files.remove(name)
        app.last = f"{event}: {name}"
        yield Frame(app, size, None, hold=16)
    yield Frame(app, size, None, hold=c.fps)


def encode(c: Clip, folder: Path, frames: int) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{c.name}.webp"
    from PIL import Image

    with Image.open(folder / "00001.png") as im:
        width = min(WIDTH, im.width)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(c.fps), "-i", str(folder / "%05d.png"),
                    "-vf", f"scale={width - width % 2}:-2:flags=lanczos", "-c:v", "libwebp_anim", "-q:v", "70",
                    "-compression_level", "6", "-loop", "0", "-an", str(out)], check=True)
    print(f"  {out.relative_to(ROOT)}: {frames} frames, {out.stat().st_size / 1000:.0f} KB")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="*")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    for c in CLIPS.values():
        if args.list:
            print(f"{c.name:10} {c.title}")
            continue
        if args.names and not any(n in c.name for n in args.names):
            continue
        print(f"recording {c.name}")
        folder = Path(tempfile.mkdtemp(prefix=f"pyzed-{c.name}-"))
        try:
            encode(c, folder, record.render_offscreen(c, folder))
        finally:
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
