"""Records the short muted clips the docs embed (docs/public/media/): MP4 (H.264) + WebM (VP9) + a WebP
poster, and an animated WebP when it is smaller than the MP4. ``manifest.json`` there lists every clip.

    python docs/scripts/record.py                 # every clip
    python docs/scripts/record.py snake shader    # only the clips whose name contains a word
    python docs/scripts/record.py --list          # what there is to record

Two ways of recording:

* **Off-screen** (most clips): the same renderer as the screenshot scripts draws one PNG per frame
  while the clip steps the app's state between frames (a game's ``tick``, a shader's time, a form
  being typed into, a drag in Pyzed Design). No window, display or GPU is needed, the result is the
  same on every machine, and a pointer is drawn on top where the clip moves one.
* **Live** (clips about hover and press effects, which only a real pointer triggers): the app runs in
  a virtual X display (``Xvfb``) at 2x, a script moves and clicks the pointer through XTEST, and
  ``ffmpeg -f x11grab`` films it. Linux only; needs ``Xvfb`` and ``python-xlib``::

      uv run --with python-xlib python docs/scripts/record.py hover

Needs ``ffmpeg`` (with libx264 and libvpx-vp9) and Pillow. Clips aim for 6-12 s, at most 1280 px wide
and under ~400 KB per file: the encoder raises its quality factor until the clip fits.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "public" / "media"
MANIFEST = OUT / "manifest.json"
EXAMPLES = ROOT / "examples"
SCALE = 2
#: Largest width of an encoded clip, in pixels.
MAX_WIDTH = 1280
#: Each encoded file should stay under this many bytes.
BUDGET = 400_000

os.environ.setdefault("PYZED_CONFIG_DIR", tempfile.mkdtemp(prefix="pyzed-record-"))
for sub in ("", "games", "showcase", "tutorial"):
    sys.path.insert(0, str(EXAMPLES / sub) if sub else str(EXAMPLES))


# -- clips -----------------------------------------------------------------------------------------
@dataclass
class Frame:
    """One frame of an off-screen clip: ``app`` drawn at ``size``, with the pointer at ``pointer``
    (logical pixels, ``None`` hides it) and ``hold`` copies of it (a still moment costs one render)."""

    app: Any
    size: tuple[float, float]
    pointer: tuple[float, float] | None = None
    pressed: bool = False
    hold: int = 1


@dataclass
class Clip:
    name: str
    title: str
    description: str
    fps: int
    make: Callable[[Clip], Any]
    live: bool = False
    #: Which frame becomes the poster, as a fraction of the clip.
    poster: float = 0.5
    tags: list[str] = field(default_factory=list)


CLIPS: dict[str, Clip] = {}


def clip(name: str, title: str, description: str, *, fps: int = 24, live: bool = False, poster: float = 0.5,
         tags: list[str] | None = None):
    def register(fn):
        CLIPS[name] = Clip(name, title, description, fps, fn, live, poster, tags or [])
        return fn

    return register


def glide(a: tuple[float, float], b: tuple[float, float], frames: int) -> Iterator[tuple[float, float]]:
    """Points from ``a`` to ``b`` with an ease-in-out, like a hand moving a mouse."""
    for i in range(1, frames + 1):
        t = i / frames
        t = t * t * (3 - 2 * t)
        yield (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


# -- games -----------------------------------------------------------------------------------------
def _snake_autopilot(app) -> None:
    """Steers toward the food without biting itself (a greedy pick among the three turns)."""
    from snake import COLS, ROWS

    hx, hy = app.body[0]
    fx, fy = app.food
    options = []
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if (d[0] + app.direction[0], d[1] + app.direction[1]) == (0, 0):
            continue
        nx, ny = (hx + d[0]) % COLS, (hy + d[1]) % ROWS
        if (nx, ny) in app.body[:-1]:
            continue
        dist = min(abs(nx - fx), COLS - abs(nx - fx)) + min(abs(ny - fy), ROWS - abs(ny - fy))
        free = sum(((nx + e[0]) % COLS, (ny + e[1]) % ROWS) not in app.body for e in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        options.append((dist - free * 0.3, d))
    if options:
        app.direction = min(options)[1]


@clip("snake", "Snake", "The Snake game from examples/games: a fixed-rate loop steering toward the food.",
      fps=24, tags=["games"])
def snake_clip(c: Clip):
    from snake import Snake

    app = Snake(seed=3)
    size = app.size
    acc = 0.0
    for _ in range(c.fps * 9):
        acc += min(app.speed, 12) / c.fps
        while acc >= 1:
            _snake_autopilot(app)
            app.step()
            acc -= 1
            if app.over:
                app.reset()
        yield Frame(app, size)


@clip("breakout", "Breakout", "Breakout from examples/games: a ball, a paddle that follows it and bricks that break.",
      fps=30, tags=["games"])
def breakout_clip(c: Clip):
    from breakout import Breakout

    app = Breakout(3)
    app.launch()
    for _ in range(c.fps * 8):
        for _ in range(2):
            app.paddle_x = app.ball_x + 18
            app.tick(1 / 60)
            if app.stuck:
                app.launch()
        yield Frame(app, app.size)


@clip("neon-invaders", "Neon Invaders", "Neon Invaders from examples/games: waves, shots, explosions and power-ups.",
      fps=30, tags=["games"])
def invaders_clip(c: Clip):
    from neon_invaders import NeonInvaders

    random.seed(5)
    app = NeonInvaders(5)
    app.started = True
    app.new_game()
    frame = 0
    for _ in range(c.fps * 9):
        for _ in range(2):
            frame += 1
            if frame % 9 == 0:
                app.fire()
            app.x = 380 + 160 * math.sin(frame / 45)
            app.hurt = 1  # the ship is not hit while it films
            app.tick(1 / 60)
        app.hurt = 0
        yield Frame(app, app.size)


@clip("game-of-life", "Game of Life", "Conway's Game of Life drawn on a canvas, one generation every few frames.",
      fps=20, tags=["apps"])
def life_clip(c: Clip):
    from game_of_life import Life

    random.seed(4)
    app = Life()
    app.randomize()
    for i in range(c.fps * 7):
        if i % 2 == 0:
            app.tick()
        yield Frame(app, app.size)


# -- shaders ---------------------------------------------------------------------------------------
class _ShaderWall:
    """A grid of the showcase's shader graphs, all drawn at the time ``t``."""

    title = "Shaders"

    def __init__(self):
        import pyzed as pz

        self.pz = pz
        self.t = 0.0
        folder = EXAMPLES / "showcase" / "shaders"
        self.names = ["plasma", "tunnel", "fire", "voronoi", "synthwave", "nebula"]
        self.files = [str(folder / f"{n}.pzshad") for n in self.names]
        self.theme = "One Dark"

    def view(self):
        pz = self.pz
        from pyzed import ui

        cells = []
        for name, path in zip(self.names, self.files):
            cells.append(pz.column([
                pz.container(pz.shader(path, width=300, height=180, time=self.t), radius=10, clip=True),
                ui.label(name.capitalize(), size="sm", color="text_muted"),
            ], spacing=6))
        rows = [pz.row(cells[i:i + 3], spacing=16) for i in range(0, len(cells), 3)]
        return pz.container(pz.column(rows, spacing=14), padding=24, width="fill", height="fill", center=True,
                            bg=self.pz.themes.get("One Dark").editor)


@clip("shaders", "Shader graphs", "Six node-based shaders from examples/showcase/shaders running at once.",
      fps=24, tags=["shading", "showcase"])
def shaders_clip(c: Clip):
    import pyzed as pz

    class Wall(_ShaderWall, pz.App):
        pass

    app = Wall()
    for i in range(c.fps * 8):
        app.t = i / c.fps
        yield Frame(app, (1000, 520))


# -- themes ----------------------------------------------------------------------------------------
THEMES = ["One Dark", "One Light", "Ayu Mirage", "Gruvbox Dark", "Ayu Light", "Gruvbox Light"]


@clip("themes", "One app, six themes", "The component gallery (examples/gallery.py) switching between built-in themes.",
      fps=12, poster=0.0, tags=["library", "theming"])
def themes_clip(c: Clip):
    import pyzed as pz
    from gallery import Gallery

    for name in THEMES:
        app = Gallery(pz.themes.get(name))
        yield Frame(app, (1280, 800), hold=int(c.fps * 1.3))


@clip("designer-themes", "Pyzed Design in other themes", "Pyzed Design's own look following the theme picked in Settings.",
      fps=12, poster=0.0, tags=["designer", "theming"])
def designer_themes_clip(c: Clip):
    import pyzed as pz

    app = _designer(EXAMPLES / "designer" / "login.pzform")
    app.doc.select("sign_in")
    app._selection_changed()
    for name in THEMES:
        app.theme = pz.themes.get(name)
        yield Frame(app, DESIGNER_SIZE, hold=int(c.fps * 1.3))


# -- forms -----------------------------------------------------------------------------------------
@clip("form-validation", "A form validating as you type",
      "The login form made in Pyzed Design: a wrong email is flagged, fixed, then Sign in runs its progress.",
      fps=24, poster=0.3, tags=["designer", "forms"])
def form_clip(c: Clip):
    import pyzed as pz
    from pyzed.designer.runtime import FormWindow, load_handlers

    path = EXAMPLES / "designer" / "login.pzform"
    form = _designer(path).doc.form  # the form with its code (login.py), as Run opens it
    form["email"].bind = "email"
    form["email"].rules = {"required": True, "pattern": r"[^@]+@[^@]+\.\w+", "message": "Enter a valid email"}
    form["password"].bind = "password"
    form["password"].rules = {"required": True, "min_length": 8}
    window = FormWindow(form, load_handlers(path, form), path=path)
    rt = window.runtime
    rt.load()

    class Host(pz.App):
        def __init__(self):
            self.theme = rt.theme

        def view(self):
            return window.view()

    app = Host()
    size = (int(form.width), int(form.height))
    email, password, remember, sign_in = (rt.form[n] for n in ("email", "password", "remember", "sign_in"))
    pos = {"email": (230, 168), "password": (230, 232), "remember": (40, 277), "sign_in": (236, 321)}
    pointer = (380.0, 380.0)

    def move(to, frames=10):
        nonlocal pointer
        for p in glide(pointer, to, frames):
            pointer = p
            yield Frame(app, size, pointer)

    def type_into(control, text, start=""):
        value = start
        for ch in text:
            value += ch
            rt.ctx.on(control, "change", "text")(value)
            if control is email:
                rt.validate(["email"])
            yield Frame(app, size, pointer, hold=2)

    yield Frame(app, size, pointer, hold=12)
    yield from move(pos["email"])
    yield Frame(app, size, pointer, pressed=True, hold=3)
    yield from type_into(email, "ada.lovelace")
    yield Frame(app, size, pointer, hold=12)
    yield from type_into(email, "@analytical.dev", "ada.lovelace")
    yield Frame(app, size, pointer, hold=10)
    yield from move(pos["password"])
    yield Frame(app, size, pointer, pressed=True, hold=3)
    yield from type_into(password, "babbage1843")
    yield from move(pos["remember"])
    yield Frame(app, size, pointer, pressed=True, hold=3)
    rt.ctx.on(remember, "change", "checked")(False)
    yield Frame(app, size, pointer, hold=6)
    yield from move(pos["sign_in"])
    yield Frame(app, size, pointer, pressed=True, hold=3)
    rt.dispatch(sign_in, "click")
    ticker = rt.form["ticker"]
    for _ in range(30):
        rt.dispatch(ticker, "tick")
        yield Frame(app, size, pointer)
    yield Frame(app, size, pointer, hold=c.fps * 2)


# -- Pyzed Design ----------------------------------------------------------------------------------
def _designer(path=None):
    from pyzed.designer.app import Designer

    app = Designer(path, language_servers=False)
    app.frame = "gnome"
    app.toasts.clear()
    app.dialog = None
    return app


#: Where things are in a 1280x800 designer window (logical pixels), for the pointer the clips draw.
DESIGNER_SIZE = (1280, 800)


@clip("designer-place-controls", "Placing controls from the toolbox",
      "Pyzed Design: a button, a text box and a check box dragged from the toolbox onto an empty form.",
      fps=24, poster=0.98, tags=["designer"])
def designer_place_clip(c: Clip):
    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    app = _designer(work / "form1.pzform")
    size = DESIGNER_SIZE
    origin = _form_origin(app)
    rows = {"label": 204, "button": 255, "input": 281, "checkbox": 333}
    pointer = (640.0, 600.0)
    yield Frame(app, size, pointer, hold=10)
    drops = [("label", (24, 20)), ("input", (24, 56)), ("checkbox", (24, 104)), ("button", (24, 146))]
    for type_, (fx, fy) in drops:
        start = (70.0, float(rows.get(type_, 255)))
        for p in glide(pointer, start, 12):
            pointer = p
            yield Frame(app, size, pointer)
        app.window_pointer = pointer
        app.press_tool(type_)
        yield Frame(app, size, pointer, pressed=True, hold=3)
        target = (origin[0] + fx + 6, origin[1] + fy + 6)
        app.enter_form()
        for p in glide(pointer, target, 16):
            pointer = p
            app.window_moved(*p)
            app.pointer_moved(p[0] - origin[0], p[1] - origin[1])
            yield Frame(app, size, pointer, pressed=True)
        app.window_release()
        app.toasts.clear()
        yield Frame(app, size, pointer, hold=8)
    yield Frame(app, size, pointer, hold=c.fps)


def _form_origin(app) -> tuple[float, float]:
    """Where the form's top-left corner is in the window: the left dock, the canvas's margin and the
    title bar the canvas draws around the form (GNOME's, see ``_designer``)."""
    from pyzed.designer import surface
    from pyzed.ui import frame as ui_frame

    return (240.0 + surface.MARGIN + 1, 102.0 + surface.MARGIN + ui_frame.HEIGHTS["gnome"] + 1)


@clip("shader-graph", "Building a shader graph",
      "Pyzed Design's Shader view: Voronoi and Palette nodes dragged in and wired to the Output, with live previews.",
      fps=24, poster=0.85, tags=["designer", "shading"])
def shader_graph_clip(c: Clip):
    from pyzed import shading
    from pyzed.shading import layout as L
    from pyzed.shading.nodes import PRESETS

    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    g = shading.new("cells")
    for node_id in [n.id for n in g.nodes.values() if n.type != "output"]:
        g.remove(node_id)
    path = g.save(work / "cells.pzshad")
    app = _designer(path)
    ed = app.shading
    doc = app.doc
    size = DESIGNER_SIZE
    t0 = 0.0
    frame = 0

    def tick():
        nonlocal frame
        frame += 1
        ed.paused = t0 + frame / c.fps

    out = doc.graph.output_node
    out.x, out.y = 540.0, 40.0
    doc.zoom, doc.pan = 0.78, (30.0, 130.0)
    doc.fit_pending = False
    canvas = (240.0, 101.0)  # the canvas's top-left corner in the window

    def to_window(x, y):
        vx, vy = doc.to_view(x, y)
        return (canvas[0] + vx, canvas[1] + vy)

    pointer = (700.0, 520.0)
    tick()
    yield Frame(app, size, pointer, hold=8)
    keys = {p.type: p.key for p in PRESETS}
    ed.set_query("")
    for type_, at in (("voronoi", (10.0, 40.0)), ("palette", (275.0, 40.0))):
        ed.set_query(type_[:4])
        tick()
        yield Frame(app, size, pointer, hold=6)
        start = (70.0, 176.0)  # the first match under the sidebar's search
        for p in glide(pointer, start, 12):
            pointer = p
            tick()
            yield Frame(app, size, pointer)
        app.window_pointer = pointer
        ed.press_preset(keys[type_])
        tick()
        yield Frame(app, size, pointer, pressed=True, hold=2)
        target = to_window(at[0] + L.WIDTH / 2, at[1] + 15)
        for p in glide(pointer, target, 16):
            pointer = p
            app.window_moved(*p)
            ed.enter()
            ed.moved(p[0] - canvas[0], p[1] - canvas[1])
            tick()
            yield Frame(app, size, pointer, pressed=True)
        app.window_release()
        ed.set_query("")
        tick()
        yield Frame(app, size, pointer, hold=6)
    g = doc.graph
    vor = next(n for n in g.nodes.values() if n.type == "voronoi")
    pal = next(n for n in g.nodes.values() if n.type == "palette")
    out = g.output_node
    for src, port, dst, inp in ((vor, "distance", pal, "t"), (pal, "rgb", out, "color")):
        a = to_window(*L.port_position(g, src, port, True))
        b = to_window(*L.port_position(g, dst, inp, False))
        for p in glide(pointer, a, 10):
            pointer = p
            tick()
            yield Frame(app, size, pointer)
        ed.press_port(src.id, port, True)
        ed.over = True
        for p in glide(pointer, b, 14):
            pointer = p
            ed.moved(p[0] - canvas[0], p[1] - canvas[1])
            tick()
            yield Frame(app, size, pointer, pressed=True)
        ed.release()
        tick()
        yield Frame(app, size, pointer, hold=4)
    away = (900.0, 700.0)
    for p in glide(pointer, away, 10):
        pointer = p
        tick()
        yield Frame(app, size, pointer)
    for _ in range(c.fps * 3):
        tick()
        yield Frame(app, size, None)


@clip("shader-preview", "A shader's Preview tab", "The Preview tab of the Shader view: the glow ring pulsing as time runs.",
      fps=24, tags=["designer", "shading"])
def shader_preview_clip(c: Clip):
    from pyzed.designer import shader_editor

    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    src = ROOT / "python" / "pyzed" / "designer" / "templates" / "shaders" / "glow_ring.pzshad"
    shutil.copy(src, work / src.name)
    app = _designer(work / src.name)
    shader_editor.set_tab(app, "preview")
    for i in range(c.fps * 6):
        app.shading.paused = i / c.fps
        yield Frame(app, DESIGNER_SIZE)


# -- live: hover and press effects -----------------------------------------------------------------
def controls_app():
    """The demo the ``hover`` clip films: buttons, a switch, a check box, a slider and tabs."""
    import pyzed as pz
    from pyzed import ui

    class Controls(pz.App):
        title = "Controls"
        size = (640, 360)
        theme = "One Dark"

        def __init__(self):
            self.on, self.checked, self.volume, self.view_ = False, False, 0.3, "Day"
            self.saved = 0
            self.toasts = []

        def save(self):
            self.saved += 1
            self.toasts = [("Saved", f"Saved {self.saved} time{'s' if self.saved > 1 else ''}")]

        def view(self):
            body = pz.container(pz.column([
                ui.heading("Controls", level=3),
                pz.row([
                    ui.button("Save", self.save, icon="save", variant="solid"),
                    ui.button("Outline", lambda: None, variant="outline"),
                    ui.button("Ghost", lambda: None, variant="ghost"),
                    ui.tooltip(ui.button(None, lambda: None, icon="settings", variant="ghost"), "Settings"),
                ], spacing=12, align="center"),
                pz.row([ui.switch(self.on, lambda v: setattr(self, "on", v), label="Wi-Fi"),
                        ui.checkbox(self.checked, lambda v: setattr(self, "checked", v), label="Remember me")],
                       spacing=32, align="center"),
                pz.row([ui.label("Volume", width=80), ui.slider(self.volume, lambda v: setattr(self, "volume", v)),
                        ui.label(f"{self.volume:.0%}", width=48)], spacing=12, align="center"),
                ui.segmented(["Day", "Week", "Month"], self.view_, lambda v: setattr(self, "view_", v)),
            ], spacing=22), padding=32, width="fill", height="fill")
            return ui.toasts(body, [ui.toast(t, m, kind="success") for t, m in self.toasts])

    return Controls


LIVE_APPS = {"controls": controls_app}


@clip("hover", "Hover, press and toggle",
      "Pyzed controls reacting to a real pointer: hover and press states, a tooltip, a switch, a check box, a slider.",
      fps=30, live=True, poster=0.35, tags=["library"])
def hover_clip(c: Clip):
    """Steps for the live recorder: ("move", x, y, seconds), ("down",), ("up",), ("wait", seconds)."""
    steps = [
        ("move", 560, 320, 0.0), ("wait", 0.6),
        ("move", 66, 89, 0.7), ("wait", 0.6), ("down",), ("wait", 0.15), ("up",), ("wait", 0.8),
        ("move", 145, 89, 0.5), ("wait", 0.5), ("move", 217, 89, 0.4), ("wait", 0.5),
        ("move", 274, 89, 0.4), ("wait", 1.2),
        ("move", 50, 134, 0.6), ("wait", 0.3), ("down",), ("up",), ("wait", 0.6),
        ("move", 147, 134, 0.6), ("wait", 0.3), ("down",), ("up",), ("wait", 0.6),
        ("move", 254, 174, 0.5), ("down",), ("move", 470, 174, 0.8), ("move", 400, 174, 0.4), ("up",), ("wait", 0.5),
        ("move", 101, 219, 0.6), ("down",), ("up",), ("wait", 0.5),
        ("move", 156, 219, 0.4), ("down",), ("up",), ("wait", 1.0),
    ]
    pace = 0.7  # a bit brisker than the numbers above, to stay near 10 s
    steps = [(k, *a[:2], a[2] * pace) if k == "move" else (k, a[0] * pace) if k == "wait" else (k,)
             for k, *a in steps]
    return "controls", (640, 360), steps


# -- rendering -------------------------------------------------------------------------------------
def _cursor(img, at, pressed):
    """Draws an arrow pointer (and a ring while the button is down) at ``at`` (physical pixels)."""
    from PIL import ImageDraw

    x, y = at
    s = SCALE
    d = ImageDraw.Draw(img, "RGBA")
    if pressed:
        r = 13 * s
        d.ellipse((x - r, y - r, x + r, y + r), fill=(116, 173, 232, 70), outline=(116, 173, 232, 200), width=s)
    arrow = [(0, 0), (0, 17), (4.2, 13.2), (7, 19.5), (9.6, 18.4), (6.9, 12.3), (12.3, 12.3)]
    pts = [(x + px * s, y + py * s) for px, py in arrow]
    d.polygon([(px + s, py + s) for px, py in pts], fill=(0, 0, 0, 90))
    d.polygon(pts, fill=(255, 255, 255, 255), outline=(20, 20, 24, 255))
    d.line(pts + [pts[0]], fill=(20, 20, 24, 255), width=max(1, s))


def render_offscreen(c: Clip, folder: Path) -> int:
    """Renders the clip's frames to ``folder/00001.png``...; returns how many there are."""
    import pyzed as pz
    from PIL import Image

    n = 0
    last: Path | None = None
    started = time.time()
    for frame in c.make(c):
        path = folder / "render.png"
        pz.screenshot(frame.app, path, size=frame.size, scale=SCALE, wait=0.0)
        with Image.open(path) as im:
            im = im.convert("RGB")
            if frame.pointer is not None:
                _cursor(im, (frame.pointer[0] * SCALE, frame.pointer[1] * SCALE), frame.pressed)
            for _ in range(frame.hold):
                n += 1
                last = folder / f"{n:05d}.png"
                im.save(last, compress_level=1)
    print(f"  {n} frames in {time.time() - started:.0f}s")
    return n


def render_live(c: Clip, folder: Path) -> Path:
    """Runs the clip's app in Xvfb at 2x, plays its pointer script and films it; returns the capture."""
    from Xlib import X, display
    from Xlib.ext import xtest

    app_name, size, steps = c.make(c)
    w, h = int(size[0] * SCALE), int(size[1] * SCALE)
    num = 90 + os.getpid() % 100
    xvfb = subprocess.Popen(["Xvfb", f":{num}", "-screen", "0", f"{w}x{h}x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env = {**os.environ, "DISPLAY": f":{num}", "WINIT_X11_SCALE_FACTOR": str(SCALE)}
    capture = folder / "capture.mkv"
    procs = [xvfb]
    try:
        time.sleep(1.0)
        app = subprocess.Popen([sys.executable, __file__, "--serve", app_name], env=env)
        procs.append(app)
        time.sleep(4.0)  # the window opens and draws its first frames
        grab = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "1",
                                 "-framerate", str(c.fps), "-video_size", f"{w}x{h}", "-i", f":{num}+0,0",
                                 "-c:v", "libx264rgb", "-preset", "ultrafast", "-crf", "0", str(capture)],
                                env=env, stdin=subprocess.PIPE)
        procs.append(grab)
        dpy = display.Display(f":{num}")
        pos = [w / 2, h / 2]

        def warp(x, y):
            xtest.fake_input(dpy, X.MotionNotify, x=int(x), y=int(y))
            dpy.sync()

        time.sleep(0.3)
        for step in steps:
            kind = step[0]
            if kind == "move":
                x, y, seconds = step[1] * SCALE, step[2] * SCALE, step[3]
                frames = max(1, int(seconds * 60))
                for p in glide(tuple(pos), (x, y), frames):
                    warp(*p)
                    time.sleep(seconds / frames if seconds else 0)
                pos = [x, y]
            elif kind == "down":
                xtest.fake_input(dpy, X.ButtonPress, 1)
                dpy.sync()
                time.sleep(0.08)
            elif kind == "up":
                xtest.fake_input(dpy, X.ButtonRelease, 1)
                dpy.sync()
                time.sleep(0.05)
            elif kind == "wait":
                time.sleep(step[1])
        time.sleep(0.3)
        grab.communicate(b"q", timeout=30)
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
    return capture


# -- encoding --------------------------------------------------------------------------------------
def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def _probe_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def encode(c: Clip, source: list[str], width: int, frames: int, folder: Path) -> dict[str, Any]:
    """Encodes the frames (``source``: ffmpeg input arguments) into the clip's files in OUT."""
    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    scale = f"scale={width}:-2:flags=lanczos"
    files: dict[str, Path] = {}

    def fit(ext: str, start: int, stop: int, step: int, args: Callable[[int], list[str]]) -> Path:
        out = OUT / f"{c.name}.{ext}"
        q = start
        while True:
            _ffmpeg(*source, *args(q), str(out))
            if out.stat().st_size <= BUDGET or q >= stop:
                return out
            q += step

    files["mp4"] = fit("mp4", 26, 40, 3, lambda q: [
        "-vf", f"{scale},format=yuv420p", "-c:v", "libx264", "-preset", "veryslow", "-tune", "animation",
        "-crf", str(q), "-movflags", "+faststart", "-an"])
    files["webm"] = fit("webm", 36, 54, 4, lambda q: [
        "-vf", scale, "-c:v", "libvpx-vp9", "-crf", str(q), "-b:v", "0", "-row-mt", "1", "-deadline", "good",
        "-cpu-used", "2", "-pix_fmt", "yuv420p", "-an"])
    # the poster: one frame as a light WebP
    poster = OUT / f"{c.name}.poster.webp"
    index = max(1, min(frames, int(frames * c.poster)))
    still = folder / "poster.png"
    _ffmpeg(*source, "-vf", f"select=eq(n\\,{index - 1}),{scale}", "-frames:v", "1", str(still))
    with Image.open(still) as im:
        im.save(poster, "WEBP", quality=82, method=6)
    files["poster"] = poster
    # an animated WebP, kept only when it beats the MP4
    anim = OUT / f"{c.name}.webp"
    _ffmpeg(*source, "-vf", scale, "-c:v", "libwebp_anim", "-q:v", "60", "-compression_level", "6", "-loop", "0",
            "-an", str(anim))
    if anim.stat().st_size < files["mp4"].stat().st_size:
        files["webp"] = anim
    else:
        anim.unlink()
    w, h = _probe_size(files["mp4"])
    entry = {
        "name": c.name,
        "title": c.title,
        "description": c.description,
        "tags": c.tags,
        "width": w,
        "height": h,
        "fps": c.fps,
        "duration": round(frames / c.fps, 2),
        "recorded": "live (Xvfb)" if c.live else "off-screen",
    }
    for kind, path in files.items():
        entry[kind] = f"media/{path.name}"
        entry[f"{kind}_bytes"] = path.stat().st_size
    return entry


def record(c: Clip) -> dict[str, Any]:
    print(f"recording {c.name}")
    folder = Path(tempfile.mkdtemp(prefix=f"pyzed-{c.name}-"))
    try:
        if c.live:
            capture = render_live(c, folder)
            natural = _probe_size(capture)[0]
            count = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(capture)],
                                       capture_output=True, text=True, check=True).stdout.strip() or 0)
            source = ["-i", str(capture)]
        else:
            count = render_offscreen(c, folder)
            from PIL import Image

            with Image.open(folder / "00001.png") as im:
                natural = im.width
            source = ["-framerate", str(c.fps), "-i", str(folder / "%05d.png")]
        width = min(MAX_WIDTH, natural)
        width -= width % 2
        entry = encode(c, source, width, count, folder)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    sizes = ", ".join(f"{k.removesuffix('_bytes')} {v / 1000:.0f} KB" for k, v in entry.items() if k.endswith("_bytes"))
    print(f"  {entry['width']}x{entry['height']}, {entry['duration']}s: {sizes}")
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="*", help="record only the clips whose name contains one of these")
    parser.add_argument("--list", action="store_true", help="list the clips")
    parser.add_argument("--serve", help=argparse.SUPPRESS)  # runs a live clip's app (inside Xvfb)
    args = parser.parse_args()
    if args.serve:
        import pyzed as pz

        pz.run(LIVE_APPS[args.serve]())
        return
    if args.list:
        for c in CLIPS.values():
            print(f"{c.name:26} {'live' if c.live else 'off-screen':10} {c.description}")
        return
    manifest: dict[str, Any] = {"clips": []}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = {e["name"]: e for e in manifest.get("clips", [])}
    for c in CLIPS.values():
        if args.names and not any(n in c.name for n in args.names):
            continue
        if c.live and (shutil.which("Xvfb") is None or sys.platform != "linux"):
            print(f"skipping {c.name}: live clips need Linux and Xvfb")
            continue
        entries[c.name] = record(c)
    order = list(CLIPS)
    manifest = {
        "about": "Short muted looping clips for the docs, made by docs/scripts/record.py. Paths are relative to "
                 "the site's base URL (public/). Embed with <video autoplay muted loop playsinline poster=...> "
                 "and a WebM source before the MP4.",
        "clips": sorted(entries.values(), key=lambda e: order.index(e["name"]) if e["name"] in order else 999),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
