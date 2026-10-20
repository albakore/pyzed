"""Records the animated WebP illustrations of the audio components and the rack (docs/public/media/audio/ui/*.webp).

    python docs/scripts/audio_ui_shots.py               # every animation
    python docs/scripts/audio_ui_shots.py knob rack     # only the ones whose name contains a word
    python docs/scripts/audio_ui_shots.py --list

Each animation is an app drawn off-screen (the renderer of the screenshots: no window or GPU
needed) one frame at a time while the scene changes its state: a knob turning, a spectrum of a
synthesized song, a cable being plugged. The frames are joined with Pillow into a looping WebP.
Meters and analyzers read a simulated clock, so their falloff matches the animation's frame rate.
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "public" / "media" / "audio" / "ui"
os.environ.setdefault("PYZED_CONFIG_DIR", tempfile.mkdtemp(prefix="pyzed-audio-shots-"))
sys.path.insert(0, str(ROOT / "examples" / "audio"))

import pyzed as pz  # noqa: E402
from pyzed import draw, ui  # noqa: E402
from pyzed.ui import audio as au  # noqa: E402

#: Pixels per logical pixel in the frames (then scaled down to fit ``MAX_WIDTH``).
SCALE = 2
MAX_WIDTH = 960

CLOCK = [0.0]
au._now = lambda: CLOCK[0]  # meters and analyzers follow the animation's time


@dataclass
class Frame:
    app: Any
    pointer: Optional[Tuple[float, float]] = None
    pressed: bool = False


@dataclass
class Scene:
    name: str
    size: Tuple[int, int]
    fps: int
    make: Callable[["Scene"], Iterator[Frame]]
    quality: int = 62


SCENES: dict = {}


def scene(name: str, size: Tuple[int, int], *, fps: int = 15, quality: int = 62):
    def register(fn):
        SCENES[name] = Scene(name, size, fps, fn, quality)
        return fn

    return register


# -- music from the engine --------------------------------------------------------------------------
class Song:
    """The visualizer demo's groove (examples/audio/visualizer.py) rendered offline, step by step."""

    def __init__(self):
        from pyzed import audio
        from visualizer import change_chord, demo_song

        self.engine = audio.Engine("offline")
        self.tap = demo_song(self.engine)
        self._chord = change_chord
        self.time = 0.0

    def step(self, dt: float) -> None:
        self.time += dt
        self._chord(self.engine, self.time)
        self.engine.render(dt)

    def spectrum(self) -> List[float]:
        return self.tap.spectrum(512)

    def wave(self, n: int = 1024) -> List[float]:
        return self.tap.scope(n)

    def level(self) -> Tuple[float, float]:
        return self.tap.level()


def card(content: Any, title: str = "", pad: int = 16) -> Any:
    th = pz.theme.current()
    parts = [pz.text(title, size=12, color=th.text_muted)] if title else []
    return pz.container(pz.column([*parts, content], spacing=10), padding=pad, bg=th.panel, radius=8,
                        border_color=th.border, border_width=1)


class View(pz.App):
    """An app whose view is a function of its ``t`` (seconds)."""

    def __init__(self, build: Callable[["View"], Any]):
        self.t = 0.0
        self.build = build

    def view(self):
        th = self.resolved_theme()
        return pz.container(self.build(self), width="fill", height="fill", padding=20, bg=th.background, center=True)


def run(make_view: Callable[[View], Any], seconds: float, fps: int, step: Optional[Callable[[View], None]] = None,
        song: Optional[Song] = None, warmup: float = 0.0):
    app = View(make_view)
    app.song = song
    if song is not None and warmup:
        song.step(warmup)
    for i in range(int(seconds * fps)):
        app.t = i / fps
        CLOCK[0] = app.t
        if song is not None:
            song.step(1 / fps)
        if step:
            step(app)
        yield Frame(app)


# -- scenes ----------------------------------------------------------------------------------------------
@scene("knob", (720, 190))
def knob_scene(s: Scene):
    variants = ["arc", "fl", "vintage", "rack", "minimal"]
    colors = ["accent", "#ff9f3d", "accent", "#3dd68c", "#b26cf0"]

    def build(v: View):
        knobs = []
        for i, (variant, color) in enumerate(zip(variants, colors)):
            value = 0.5 + 0.45 * math.sin(v.t * 1.6 + i * 1.1)
            knobs.append(au.Knob(value=value, variant=variant, color=color, caption=variant, diameter=64))
        pan = math.sin(v.t * 1.3) * 0.9
        knobs.append(au.Knob(value=pan, min=-1, max=1, bipolar=True, caption="bipolar", diameter=64, variant="fl",
                             color="#2fd3d3"))
        return card(pz.row(knobs, spacing=22))

    return run(build, 6, s.fps)


@scene("fader", (640, 300))
def fader_scene(s: Scene):
    def build(v: View):
        faders = [
            au.Fader(value=0.55 + 0.35 * math.sin(v.t * 1.2), caption="Console", level=min(1, v.song.level()[1])),
            au.Fader(value=0.5 + 0.4 * math.sin(v.t * 1.5 + 1), caption="FL", variant="fl", color="#ff9f3d",
                     level=min(1, v.song.level()[0] * 2.5)),
            au.Fader(value=0.5 + 0.4 * math.sin(v.t * 1.1 + 2), caption="Flat", variant="flat", color="#3dd68c"),
            pz.column([au.Fader(value=0.5 + 0.45 * math.sin(v.t * 0.9), vertical=False, length=220,
                                caption="Crossfader", variant="fl", color="#b26cf0")], spacing=0),
        ]
        return card(pz.row(faders, spacing=28, align="center"))

    return run(build, 6, s.fps, song=Song(), warmup=0.5)


@scene("pads", (720, 270))
def pads_scene(s: Scene):
    names = ["KICK", "SNARE", "CLAP", "HAT", "TOM 1", "TOM 2", "RIM", "OPEN", "CRASH", "RIDE", "PERC", "FX"]
    colors = ["#ff9f3d", "#ff6b9d", "#f5d547", "#3dd68c", "#4fc3f7", "#4fc3f7", "#b26cf0", "#3dd68c",
              "#2fd3d3", "#2fd3d3", "#ff8a3d", "#e2463c"]
    pattern = {0: [0, 4, 8, 12], 1: [4, 12], 3: [0, 2, 4, 6, 8, 10, 12, 14], 2: [12], 5: [14], 7: [6], 8: [0]}

    def build(v: View):
        step = int(v.t * 8) % 16
        lit = {p for p, steps in pattern.items() if step in steps}
        grid = pz.column([pz.row([au.Pad(text=names[r * 4 + c], color=colors[r * 4 + c], lit=(r * 4 + c) in lit,
                                         width=64, height=52) for c in range(4)], spacing=8) for r in range(3)],
                         spacing=8)
        buttons = pz.column([
            au.LedButton(text="PLAY", on=True, color="success"),
            au.LedButton(text="REC", on=int(v.t * 2) % 2 == 0, color="error", variant="round"),
            au.LedButton(text="MUTE", on=int(v.t / 1.5) % 2 == 1, color="warning"),
            au.LedButton(text="SOLO", color="info", variant="pill", on=int(v.t / 2) % 3 == 0),
        ], spacing=8)
        return card(pz.row([grid, buttons], spacing=24, align="center"))

    return run(build, 6, s.fps)


@scene("step-sequencer", (720, 200))
def sequencer_scene(s: Scene):
    pattern = ["x...x...x...x...", "....x.......x...", "..x...x...x...xx", "x.x.x.x.x.x.x.x.", ".......x.......x"]

    def build(v: View):
        return card(au.StepSequencer(pattern=pattern, labels=["Kick", "Snare", "Clap", "Hat", "Perc"],
                                     current=int(v.t * 8) % 16, color="#ff9f3d", cell=34))

    return run(build, 4, s.fps)


@scene("piano", (720, 200))
def piano_scene(s: Scene):
    chords = [[48, 60, 64, 67], [45, 57, 60, 64], [41, 53, 57, 60], [43, 55, 59, 62]]

    def build(v: View):
        chord = chords[int(v.t / 1.0) % 4]
        arp = chord[1 + int(v.t * 6) % 3] + 12
        return card(au.Piano(start=36, octaves=4, pressed=[*chord, arp], key_width=19, height=120))

    return run(build, 4, s.fps)


@scene("vu-meter", (720, 260))
def vu_scene(s: Scene):
    def build(v: View):
        rms, peak = v.song.level()
        l, r = min(1.0, rms * 2.2), min(1.0, peak)
        return card(pz.row([
            au.VuMeter(level=[l, r], length=180),
            au.VuMeter(level=[l * 0.8, r * 0.8], variant="bar", length=180, thickness=14),
            au.VuMeter(level=[l, r, l * 0.6, r * 0.7], length=180, segments=30, thickness=8, colors="neon"),
            au.VuMeter(level=l, variant="analog", length=260),
        ], spacing=30, align="center"))

    return run(build, 5, s.fps, song=Song(), warmup=0.5)


@scene("waveform", (720, 330))
def waveform_scene(s: Scene):
    song = Song()
    left, _right = song.engine.render(6.0)  # six seconds of the groove, drawn whole
    clip = left[::8]

    def build(v: View):
        head = (v.t / 6) % 1.0
        return card(pz.column([
            au.Waveform(samples=clip, variant="bars", playhead=head, width=640, height=70, color="#ff9f3d"),
            au.Waveform(samples=clip, variant="mirror", playhead=head, width=640, height=70, selection=(0.62, 0.8)),
            au.Waveform(samples=v.song.wave(1200), variant="line", glow=True, width=640, height=70,
                        color="#3dd68c"),
        ], spacing=12))

    return run(build, 6, s.fps, song=song)


@scene("scope", (720, 260), fps=12, quality=50)
def scope_scene(s: Scene):
    def build(v: View):
        n = 1024
        a = [math.sin(i / 16 + v.t * 2) * 0.7 + 0.15 * math.sin(i / 3) for i in range(n)]
        b = [(2 * ((i / 40 + v.t) % 1.0) - 1) * 0.5 for i in range(n)]
        x = [math.sin(i / 20) * 0.8 for i in range(n)]
        y = [math.sin(i / 20 * 1.5 + v.t * 1.4) * 0.8 for i in range(n)]
        return card(pz.row([
            au.Scope(traces=[a, b], width=380, height=200, persistence=3),
            au.Scope(traces=[x, y], xy=True, width=220, height=200, colors=["#4fc3f7"]),
        ], spacing=16))

    return run(build, 5, s.fps)


@scene("spectrum", (760, 420), fps=12, quality=52)
def spectrum_scene(s: Scene):
    variants = [("bars", "fl"), ("blocks", "fl"), ("line", "neon"), ("filled", "ice"), ("mirror", "fire"),
                ("radial", "neon")]

    def build(v: View):
        mags = v.song.spectrum()
        cells = [card(au.Spectrum(magnitudes=mags, variant=variant, colors=colors, width=210, height=110,
                                  bands=40 if variant != "radial" else 64,
                                  color_by="frequency" if variant in ("mirror", "radial") else "level",
                                  key=variant), variant, pad=10)
                 for variant, colors in variants]
        return pz.column([pz.row(cells[:3], spacing=12), pz.row(cells[3:], spacing=12)], spacing=12)

    return run(build, 6, s.fps, song=Song(), warmup=0.5)


@scene("spectrogram", (720, 250))
def spectrogram_scene(s: Scene):
    def build(v: View):
        mags = v.song.spectrum()
        return card(pz.row([
            au.Spectrogram(magnitudes=mags, width=420, height=180, history=140, bands=64, colors="magma"),
            au.Spectrogram(magnitudes=mags, width=200, height=180, history=70, bands=40, colors="viridis",
                           key="small"),
        ], spacing=12))

    return run(build, 7, s.fps, song=Song())


@scene("palettes", (720, 220), fps=12, quality=55)
def palette_scene(s: Scene):
    names = list(au.PALETTES)

    def build(v: View):
        name = names[int(v.t / 1.2) % len(names)]
        mags = v.song.spectrum()
        return card(pz.column([
            pz.text(f'colors="{name}"', font="mono", size=13),
            au.Spectrum(magnitudes=mags, variant="blocks", colors=name, width=640, height=130, bands=56),
        ], spacing=8))

    return run(build, len(names) * 1.2, s.fps, song=Song(), warmup=0.5)


@scene("webcam", (560, 330))
def webcam_scene(s: Scene):
    from pyzed import camera

    class Fake(camera.Camera):
        pass

    cam = Fake(backend="test", width=320, height=240)
    cam.frame = None

    def step(v: View):
        index = int(v.t * s.fps)
        cam.frame = camera.Frame(320, 240, camera.test_pattern(320, 240, index), index, v.t)
        cam._count, cam._started = index + 1, time.monotonic() - (index + 1) / 30

    def build(v: View):
        return card(ui.camera.Webcam(camera=cam, width=480, height=270, device=0))

    return run(build, 4, s.fps, step)


@scene("cables", (760, 360))
def cables_scene(s: Scene):
    from pyzed.ui import rack

    jacks = [(70, 60), (70, 150), (420, 70), (640, 150), (330, 200)]
    pairs = [(0, 2, "#f5c542", 0.2), (1, 3, "#e2463c", 1.4), (0, 4, "#3dd68c", 2.6), (4, 3, "#4f8ff7", 3.6)]

    def build(v: View):
        shapes: List[Any] = [draw.rect(0, 0, 710, 310, fill="#2a2c31", radius=6)]
        for x, y in jacks:
            shapes += draw.group(rack._jack_shapes(False, False), x=x - 11, y=y - 11)
        for a, b, color, at in pairs:
            age = v.t - at
            if age < 0:
                continue
            p0, p1 = jacks[a], jacks[b]
            if age < 0.6:  # the plug travels from the first jack to the second
                k = age / 0.6
                k = k * k * (3 - 2 * k)
                end = (p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k - 30 * math.sin(k * math.pi))
                shapes += rack._cable_shapes(p0, end, color, tension=0.75, drop=0.6, opacity=1.0, flow=None)
            else:
                flow = (v.t * 0.6) % 1.0
                shapes += rack._cable_shapes(p0, p1, color, tension=0.45, drop=rack._drop(age - 0.6), opacity=0.9,
                                             flow=flow)
        return pz.canvas(shapes, width=710, height=310)

    return run(build, 6, s.fps)


# -- demos -------------------------------------------------------------------------------------------------
def _component(app: Any, cls: type) -> Any:
    """The instance of component ``cls`` the app rendered last (to drive it like a pointer would)."""
    return next(c for c in app.__dict__.get("_pyzed_components", {}).values() if isinstance(c, cls))


def _demo(module: str, name: str):
    from pyzed import audio

    engine = audio.Engine("offline")
    return getattr(__import__(module), name)(engine), engine


@scene("synth", (1120, 560))
def synth_scene(s: Scene):
    app, engine = _demo("synth", "Synth")
    melody = [(57, 0.0, 0.45), (60, 0.5, 0.45), (64, 1.0, 0.45), (67, 1.5, 0.9), (65, 2.5, 0.45), (64, 3.0, 0.45),
              (60, 3.5, 0.9), (55, 4.5, 0.45), (57, 5.0, 1.2)]
    app.load("Lead")
    fps = s.fps
    for i in range(int(6.5 * fps)):
        t = i / fps
        CLOCK[0] = t
        for note, start, length in melody:
            if start <= t < start + 1 / fps:
                app.note_on(note, 100)
            if start + length <= t < start + length + 1 / fps:
                app.note_off(note)
        app.put("cutoff", 600 + 2600 * (0.5 - 0.5 * math.cos(t * 1.1)))
        engine.render(1 / fps)
        key = min((n for n in app.held), default=None)
        pointer = None
        if key is not None:  # the pointer over the key being played (white keys are 22 px wide)
            whites = [n for n in range(36, 97) if n % 12 not in (1, 3, 6, 8, 10)]
            if key in whites:
                pointer = (18 + whites.index(key) * 22 + 11, 470)
        yield Frame(app, pointer, pressed=pointer is not None)


@scene("visualizer", (1180, 600), fps=12, quality=50)
def visualizer_scene(s: Scene):
    app, engine = _demo("visualizer", "Visualizer")
    looks = [("blocks", "fl"), ("bars", "neon"), ("filled", "ice"), ("mirror", "fire"), ("line", "viridis")]
    pz.screenshot(app, Path(tempfile.mkdtemp()) / "warm.png", size=s.size, wait=0.0)  # creates the components
    sgram = _component(app, au.Spectrogram)
    for _ in range(sgram.history):  # fill the spectrogram's history before the first frame
        engine.render(1 / s.fps)
        app.tick(1 / s.fps)
        sgram.magnitudes = app.tap().spectrum(512)
        sgram.shapes()
    for i in range(int(7.5 * s.fps)):
        t = i / s.fps
        CLOCK[0] = t
        app.variant, app.palette = looks[int(t / 1.5) % len(looks)]
        app.tick(1 / s.fps)
        engine.render(1 / s.fps)
        yield Frame(app)


@scene("midi-controller", (1280, 480))
def controller_scene(s: Scene):
    app, engine = _demo("midi_controller", "Controller")
    app.play(True)
    for i in range(int(6 * s.fps)):
        t = i / s.fps
        CLOCK[0] = t
        for k in range(8):
            app.levels[k] = 0.55 + 0.3 * math.sin(t * 1.3 + k * 0.7)
        app.pans[2] = math.sin(t)
        app.apply_mix()
        app.tick(1 / s.fps)
        engine.render(1 / s.fps)
        yield Frame(app)


@scene("drum-machine", (980, 470))
def drum_scene(s: Scene):
    app, engine = _demo("drum_machine", "DrumMachine")
    painted = False
    for i in range(int(6 * s.fps)):
        t = i / s.fps
        CLOCK[0] = t
        pointer = None
        if 3.0 <= t < 4.2:  # paint four tom steps
            col = 8 + int((t - 3.0) / 0.3)
            pointer = (18 + 36 + 72 + col * 30 + 15, 110 + 5 * 30 + 15)
            if col < 12:
                pattern = [list(r) for r in app.pattern]
                pattern[5][col] = True
                app.write_pattern(pattern)
                painted = True
        elif painted and t >= 4.2:
            pointer = None
        engine.render(1 / s.fps)
        app.tick(1 / s.fps)
        yield Frame(app, pointer, pressed=pointer is not None)


@scene("rack", (1400, 420), fps=12, quality=55)
def rack_scene(s: Scene):
    from pyzed.ui import rack as rk

    app, engine = _demo("modular", "Modular")
    engine.disconnect("delay1", "out", "scope1", "in")
    engine.connect("vca1", "out", "scope1", "in")
    left = 190  # the module browser's width: the rack starts there
    plugged = False
    rack_comp = None
    for i in range(int(8 * s.fps)):
        t = i / s.fps
        CLOCK[0] = t
        engine.render(1 / s.fps)
        pointer = None
        pressed = False
        if i > 0 and rack_comp is None:
            rack_comp = _component(app, rk.Rack)
        if rack_comp is not None and 1.5 <= t < 3.5:
            src = rack_comp.jack_at("delay1", "out", True)
            dst = rack_comp.jack_at("scope1", "in", False)
            k = min(1.0, (t - 1.5) / 1.6)
            k = k * k * (3 - 2 * k)
            x, y = src[0] + (dst[0] - src[0]) * k, src[1] + (dst[1] - src[1]) * k - 60 * math.sin(k * math.pi)
            if rack_comp.wire is None and not plugged:
                rack_comp._wire_start("delay1", "out", True, SimpleEvent(11, 11))
                engine.disconnect("vca1", "out", "scope1", "in")
            rack_comp.wire["pointer"] = (x, y)
            pointer, pressed = (left + x, y), True
        elif rack_comp is not None and t >= 3.5 and not plugged:
            rack_comp._wire_end()
            plugged = True
        if rack_comp is not None and 4.5 <= t < 7.5:  # turn the filter's cutoff
            engine.set("filter1", "cutoff", 300 + 1500 * (0.5 - 0.5 * math.cos((t - 4.5) * 2)))
            panel = rk.panel_layout(next(m for m in __import__("pyzed").audio.modules() if m.kind == "filter"))
            ox, oy = rack_comp.origin("filter1")
            kx, ky = panel.knobs["cutoff"]
            pointer, pressed = (left + ox + kx + 15, oy + ky + 15), True
        yield Frame(app, pointer, pressed)


class SimpleEvent:
    """A pointer event at ``(x, y)`` of a widget, for driving components without a window."""

    def __init__(self, x: float, y: float):
        self.x, self.y, self.dx, self.dy, self.shift = x, y, 0.0, 0.0, False


# -- rendering -------------------------------------------------------------------------------------------
def _cursor(im, at, pressed):
    from PIL import ImageDraw

    d = ImageDraw.Draw(im)
    x, y = at
    k = SCALE
    pts = [(x, y), (x, y + 17 * k), (x + 4.5 * k, y + 13 * k), (x + 8 * k, y + 20 * k), (x + 10.5 * k, y + 19 * k),
           (x + 7 * k, y + 12 * k), (x + 12.5 * k, y + 12 * k)]
    if pressed:
        d.ellipse((x - 9 * k, y - 9 * k, x + 9 * k, y + 9 * k), outline=(255, 255, 255, 160), width=2 * k)
    d.polygon(pts, fill=(255, 255, 255), outline=(20, 20, 24))


def record(s: Scene) -> Path:
    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=f"pyzed-audio-{s.name}-"))
    frames = []
    started = time.time()
    for frame in s.make(s):
        path = folder / "frame.png"
        pz.screenshot(frame.app, path, size=s.size, scale=SCALE, wait=0.0)
        with Image.open(path) as im:
            im = im.convert("RGB")
            if frame.pointer is not None:
                _cursor(im, (frame.pointer[0] * SCALE, frame.pointer[1] * SCALE), frame.pressed)
            width = min(MAX_WIDTH, im.width)
            if width != im.width:
                im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
            frames.append(im.copy())
    out = OUT / f"{s.name}.webp"
    frames[0].save(out, "WEBP", save_all=True, append_images=frames[1:], duration=round(1000 / s.fps), loop=0,
                   quality=s.quality, method=6)
    print(f"{s.name}: {len(frames)} frames, {out.stat().st_size / 1000:.0f} KB in {time.time() - started:.0f}s")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="*")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        print("\n".join(SCENES))
        return
    for name, s in SCENES.items():
        if not args.names or any(word in name for word in args.names):
            record(s)


if __name__ == "__main__":
    main()
