"""Animated illustrations of the audio engine for the docs: docs/public/media/audio/*.webp.

    uv run --with pillow python docs/scripts/audio_shots.py          # every animation
    uv run --with pillow python docs/scripts/audio_shots.py adsr     # only some

Every curve, spectrum and step comes from the real engine (``pyzed.audio``) rendered offline, so
the pictures show what the modules actually do. The files are animated WebP loops served as they
are from ``public/`` (Astro would keep only the first frame of an animation it optimizes).
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pyzed import audio

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "public" / "media" / "audio"
FONTS = ROOT / "assets" / "fonts"
SR = 48000
W, H = 720, 300
FPS = 20

BG = (30, 33, 40)
PANEL = (40, 44, 52)
GRID = (55, 60, 70)
FG = (171, 178, 191)
DIM = (110, 118, 130)
BLUE = (97, 175, 239)
GREEN = (152, 195, 121)
ORANGE = (209, 154, 102)
RED = (224, 108, 117)
PURPLE = (198, 120, 221)
CYAN = (86, 182, 194)
YELLOW = (229, 192, 123)


def font(size: int, mono: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "IBMPlexMono-Regular.ttf" if mono else ("IBMPlexSans-SemiBold.ttf" if bold else "IBMPlexSans-Regular.ttf")
    return ImageFont.truetype(str(FONTS / name), size)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def panel(d: ImageDraw.ImageDraw, box, title: str | None = None, color=FG) -> None:
    d.rounded_rectangle(box, 10, fill=PANEL)
    if title:
        d.text((box[0] + 12, box[1] + 8), title, font=font(14, bold=True), fill=color)


def curve(d, box, values, lo=-1.0, hi=1.0, color=BLUE, width=3, pad=10):
    x0, y0, x1, y1 = box
    x0, x1, y0, y1 = x0 + pad, x1 - pad, y0 + pad, y1 - pad
    n = len(values)
    if n < 2:
        return
    pts = []
    for i, v in enumerate(values):
        t = (v - lo) / (hi - lo)
        pts.append((x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * max(0.0, min(1.0, t))))
    d.line(pts, fill=color, width=width, joint="curve")


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def save(name: str, frames: list[Image.Image], fps: int = FPS) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.webp"
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0,
                   quality=78, method=6)
    print(f"{path.relative_to(ROOT)}  {len(frames)} frames  {path.stat().st_size // 1024} KB")


# ---------------------------------------------------------------------------------------------


def oscillator_waves() -> None:
    """The four waves of the oscillator, scrolling as they play."""
    e = audio.Engine("offline", sample_rate=SR)
    osc = e.add("oscillator", freq=SR / 400, level=1.0)
    scopes = {}
    for wave in ("sine", "triangle", "saw", "square"):
        scopes[wave] = e.add("scope")
        e.connect(osc, wave, scopes[wave], "in")
    e.render(0.1)
    colors = [BLUE, GREEN, ORANGE, PURPLE]
    frames = []
    for f in range(40):
        e.render(frames=40)
        img, d = canvas()
        for i, (wave, scope) in enumerate(scopes.items()):
            x = 12 + i * 177
            box = (x, 12, x + 168, H - 12)
            panel(d, box, wave, colors[i])
            d.line((x + 10, H / 2 + 14, x + 158, H / 2 + 14), fill=GRID, width=1)
            curve(d, (x, 40, x + 168, H - 12), scope.scope(1000), lo=-1.2, hi=1.2, color=colors[i])
        frames.append(img)
    save("oscillator-waves", frames)


def filter_sweep() -> None:
    """A saw through the low-pass filter while its cutoff sweeps up and down."""
    e = audio.Engine("offline", sample_rate=SR)
    osc = e.add("oscillator", freq=110, wave="saw", level=0.8)
    lpf = e.add("filter", cutoff=400, resonance=0.7)
    e.chain(osc, lpf, e.add("audio_out"))
    e.render(0.1)
    bins = 72
    frames = []
    n = 48
    for f in range(n):
        t = 0.5 - 0.5 * math.cos(2 * math.pi * f / n)
        cutoff = 150 * (8000 / 150) ** t
        lpf["cutoff"] = cutoff
        e.render(0.06)
        before = osc.spectrum(bins=bins, size=4096)
        after = lpf.spectrum(bins=bins, size=4096)
        img, d = canvas()
        panel(d, (12, 12, W - 12, H - 12), "filter · lowpass", CYAN)
        x0, x1, y0, y1 = 30, W - 30, 50, H - 40
        bw = (x1 - x0) / bins
        for i, (b, a) in enumerate(zip(before, after)):
            top_b = y1 - (y1 - y0) * max(0, (b + 90) / 90)
            top_a = y1 - (y1 - y0) * max(0, (a + 90) / 90)
            bx = x0 + i * bw
            d.rectangle((bx + 1, top_b, bx + bw - 1, y1), fill=(60, 66, 78))
            d.rectangle((bx + 1, top_a, bx + bw - 1, y1), fill=mix(CYAN, BLUE, i / bins))
        # Where the cutoff sits on the same octave scale as the bands.
        pos = math.log(cutoff / 20) / math.log((SR / 2) / 20)
        cx = x0 + (x1 - x0) * pos
        d.line((cx, y0 - 6, cx, y1), fill=YELLOW, width=2)
        d.text((min(cx + 6, x1 - 120), y0 - 8), f"cutoff {audio.module('filter').param('cutoff').format(cutoff)}",
               font=font(14, mono=True), fill=YELLOW)
        for hz, label in ((100, "100 Hz"), (1000, "1 kHz"), (10000, "10 kHz")):
            lx = x0 + (x1 - x0) * math.log(hz / 20) / math.log((SR / 2) / 20)
            d.text((lx - 18, y1 + 6), label, font=font(12, mono=True), fill=DIM)
        frames.append(img)
    save("filter-sweep", frames)


def adsr() -> None:
    """An envelope drawn as it happens: a key is held, then let go."""
    e = audio.Engine("offline", sample_rate=SR)
    keys = e.add("midi_in")
    env = e.add("adsr", attack=0.25, decay=0.3, sustain=0.55, release=0.6)
    e.connect(keys, "gate", env, "gate")
    stages = ["idle", "attack", "decay", "sustain", "release"]
    colors = [DIM, GREEN, YELLOW, BLUE, PURPLE]
    history: list[float] = []
    gates: list[float] = []
    step = 0.04
    frames = []
    total = 60
    for f in range(total):
        if f == 4:
            e.note_on("C4")
        if f == 34:
            e.note_off("C4")
        e.render(step)
        history.append(env.state["level"])
        gates.append(keys.state["gate"])
        img, d = canvas()
        stage = int(env.state["stage"])
        panel(d, (12, 12, W - 12, H - 12), "adsr", colors[stage])
        d.text((W - 150, 20), stages[stage], font=font(16, bold=True), fill=colors[stage])
        x0, x1, y0, y1 = 30, W - 30, 50, H - 80
        d.line((x0, y1, x1, y1), fill=GRID)
        pts = [(x0 + (x1 - x0) * i / (total - 1), y1 - (y1 - y0) * v) for i, v in enumerate(history)]
        if len(pts) > 1:
            d.line(pts, fill=colors[stage], width=3, joint="curve")
        px, py = pts[-1]
        d.ellipse((px - 6, py - 6, px + 6, py + 6), fill=colors[stage])
        # The gate below: when the key is held.
        gy0, gy1 = H - 60, H - 30
        d.text((x0, gy0 - 20), "gate", font=font(12, mono=True), fill=DIM)
        for i, g in enumerate(gates):
            gx = x0 + (x1 - x0) * i / (total - 1)
            if g:
                d.rectangle((gx, gy0, gx + (x1 - x0) / (total - 1) + 1, gy1), fill=(70, 90, 70))
        frames.append(img)
    frames += [frames[-1]] * 10
    save("adsr", frames)


def sequencer() -> None:
    """Eight steps lighting up as the clock advances them, with the gate they send."""
    e = audio.Engine("offline", sample_rate=SR)
    pitches = [0, 7, 3, 12, 0, -5, 10, 7]
    gates = [1, 1, 0, 1, 1, 1, 0, 1]
    seq = e.add("sequencer", steps=8, bpm=150, gate_length=0.6,
                **{f"pitch_{i + 1}": p for i, p in enumerate(pitches)},
                **{f"gate_{i + 1}": g for i, g in enumerate(gates)})
    history: list[float] = []
    frames = []
    for f in range(64):
        for _ in range(5):
            e.render(0.01)
            history.append(seq.probe("gate"))
        step = int(seq.state["step"])
        img, d = canvas()
        panel(d, (12, 12, W - 12, H - 12), "sequencer · 8 steps", ORANGE)
        x0, y0 = 40, 50
        cw, ch = (W - 80) / 8, 130
        for i, (p, g) in enumerate(zip(pitches, gates)):
            bx = x0 + i * cw
            active = i == step
            d.rounded_rectangle((bx + 4, y0, bx + cw - 4, y0 + ch), 8,
                                fill=(70, 58, 45) if active else (48, 52, 61),
                                outline=ORANGE if active else GRID, width=2)
            h = (p + 12) / 24 * (ch - 30)
            d.rectangle((bx + 18, y0 + ch - 10 - h, bx + cw - 18, y0 + ch - 10),
                        fill=ORANGE if active else (120, 100, 80))
            led = (bx + cw / 2 - 7, y0 + ch + 12, bx + cw / 2 + 7, y0 + ch + 26)
            d.ellipse(led, fill=(ORANGE if active and g else (GREEN if g else GRID)))
            d.text((bx + cw / 2 - 12, y0 + 6), f"{p:+d}", font=font(12, mono=True), fill=FG if active else DIM)
        d.text((40, H - 76), "gate", font=font(12, mono=True), fill=DIM)
        recent = history[-150:]
        curve(d, (30, H - 70, 30 + (W - 60) * len(recent) / 150, H - 16), recent, lo=-0.1, hi=1.1,
              color=GREEN, width=2, pad=4)
        frames.append(img)
    save("sequencer", frames)


def patch() -> None:
    """A small synth voice as modules and cables, the signal flowing through them."""
    e = audio.Engine("offline", sample_rate=SR)
    keys = e.add("midi_in", id="keys")
    vco = e.add("oscillator", id="vco", wave="saw")
    vcf = e.add("filter", id="vcf", cutoff=600, resonance=0.5)
    env = e.add("adsr", id="env", attack=0.02, decay=0.25, sustain=0.4, release=0.3)
    vca = e.add("vca", id="vca")
    out = e.add("audio_out", id="out")
    e.connect(keys, "pitch", vco, "pitch")
    e.connect(keys, "gate", env, "gate")
    e.connect(env, "out", vca, "cv")
    e.connect(env, "out", vcf, "cutoff")
    e.chain(vco, vcf, vca, out)
    boxes = {
        "keys": (30, 60, "MIDI", ["pitch", "gate"], PURPLE),
        "vco": (190, 30, "VCO", ["out"], BLUE),
        "env": (190, 170, "ADSR", ["out"], YELLOW),
        "vcf": (350, 30, "VCF", ["out"], CYAN),
        "vca": (510, 100, "VCA", ["out"], GREEN),
        "out": (640, 100, "OUT", [], RED),
    }
    bw, bh = 120, 90
    cables = [("keys", "vco", "pitch", PURPLE), ("keys", "env", "gate", PURPLE), ("vco", "vcf", "out", BLUE),
              ("vcf", "vca", "out", CYAN), ("env", "vca", "out", YELLOW), ("env", "vcf", "out", YELLOW),
              ("vca", "out", "out", GREEN)]
    melody = ["C3", "Eb3", "G3", "Bb3"]
    frames = []
    n = 64
    for f in range(n):
        if f % 16 == 0:
            e.note_on(melody[f // 16 % 4])
        if f % 16 == 10:
            e.note_off(melody[f // 16 % 4])
        e.render(0.04)
        img, d = canvas()
        for src, dst, port, color in cables:
            sx, sy = boxes[src][0] + bw, boxes[src][1] + bh / 2
            dx, dy = boxes[dst][0], boxes[dst][1] + bh / 2
            if dst == "out":
                dx = boxes[dst][0]
            level = min(1.0, abs(e.node(src).probe(port)) * 1.5) if e.node(src).info.outputs else 0
            glow = mix(GRID, color, 0.35 + 0.65 * level)
            pts = []
            for k in range(25):
                t = k / 24
                # A sagging cable, like a patch cord hanging between two jacks.
                x = sx + (dx - sx) * t
                y = sy + (dy - sy) * t + math.sin(math.pi * t) * 30
                pts.append((x, y))
            d.line(pts, fill=glow, width=4, joint="curve")
            for k in range(3):
                t = ((f / 20) + k / 3) % 1
                i = min(23, int(t * 24))
                px, py = pts[i]
                r = 3 + 2 * level
                d.ellipse((px - r, py - r, px + r, py + r), fill=color)
        for name, (x, y, label, _, color) in boxes.items():
            w = 70 if name == "out" else bw
            d.rounded_rectangle((x, y, x + w, y + bh), 10, fill=PANEL, outline=color, width=2)
            d.text((x + 12, y + 10), label, font=font(16, bold=True), fill=color)
            rms, peak = e.node(name).level()
            meter = min(1.0, peak * 1.2)
            d.rectangle((x + 12, y + bh - 18, x + 12 + (w - 24) * meter, y + bh - 12), fill=color)
            d.rectangle((x + 12, y + bh - 18, x + w - 12, y + bh - 12), outline=GRID)
        frames.append(img)
    save("patch", frames)


def visualizer() -> None:
    """A beat and a bass line, with the waveform and the spectrum a visualizer reads from them."""
    e = audio.Engine("offline", sample_rate=SR)
    clock = e.add("clock", bpm=124, division="1/16")
    kick = e.add("drum", sound="kick", decay=0.35)
    hat = e.add("drum", sound="hihat", decay=0.08, level=0.4)
    beat = e.add("clock", bpm=124, division="1/4")
    e.connect(beat, "clock", kick, "trigger")
    e.connect(clock, "clock", hat, "trigger")
    seq = e.add("sequencer", steps=8, bpm=0, **{f"pitch_{i + 1}": p for i, p in enumerate([0, 0, 12, 0, 3, 0, 10, 7])})
    e.connect(clock, "clock", seq, "clock")
    bass = e.add("oscillator", wave="saw", freq=55, level=0.5)
    e.connect(seq, "pitch", bass, "pitch")
    vcf = e.add("filter", cutoff=700, resonance=0.6)
    env = e.add("adsr", attack=0.002, decay=0.12, sustain=0.0, release=0.05)
    vca = e.add("vca")
    e.connect(seq, "gate", env, "gate")
    e.connect(env, "out", vca, "cv")
    e.connect(env, "out", vcf, "cutoff")
    e.chain(bass, vcf, vca)
    mixer = e.add("mixer")
    for i, src in enumerate([kick, hat, vca]):
        e.connect(src, "out", mixer, f"in_{i + 1}")
    e.chain(mixer, e.add("audio_out", volume=1))
    frames = []
    smooth = [-120.0] * 48
    for f in range(60):
        e.render(1 / FPS)
        img, d = canvas()
        panel(d, (12, 12, W - 12, 120), "engine.scope()", GREEN)
        wave = e.scope(4800)[::8]
        gain = 0.9 / max(0.2, max(map(abs, wave)))
        curve(d, (12, 36, W - 12, 120), [x * gain for x in wave], lo=-1, hi=1, color=GREEN, width=2)
        panel(d, (12, 132, W - 12, H - 12), "engine.spectrum(bins=48)", BLUE)
        spec = e.spectrum(bins=48, size=2048)
        smooth = [max(s, v) if v > s else s - (s - v) * 0.35 for s, v in zip(smooth, spec)]
        x0, x1, y0, y1 = 30, W - 30, 160, H - 24
        bw = (x1 - x0) / len(smooth)
        for i, v in enumerate(smooth):
            t = max(0.0, (v + 80) / 80)
            top = y1 - (y1 - y0) * t
            d.rounded_rectangle((x0 + i * bw + 2, top, x0 + (i + 1) * bw - 2, y1), 3,
                                fill=mix(BLUE, PURPLE, i / len(smooth)))
        frames.append(img)
    save("visualizer", frames)


def latency() -> None:
    """Blocks of 64 frames filling the device's buffer: what buffer_size and latency mean."""
    frames = []
    slots, slot, gap = 4, 80, 12
    x0, y0 = 50, 120
    travel = 8
    for f in range((slots + 1) * travel):
        img, d = canvas()
        panel(d, (12, 12, W - 12, H - 12), "buffer_size = 256 frames → 5.3 ms at 48 kHz", FG)
        d.text((x0, 60), "the audio thread computes blocks of 64 frames…", font=font(14), fill=GREEN)
        filled, t = divmod(f, travel)
        flush = filled == slots
        for i in range(slots):
            bx = x0 + i * (slot + gap)
            on = i < filled and not flush
            color = mix(PANEL, BLUE, 0.9) if on else (mix(BLUE, YELLOW, t / travel) if flush else PANEL)
            d.rounded_rectangle((bx, y0, bx + slot, y0 + 70), 8, fill=color, outline=GRID, width=2)
            d.text((bx + 26, y0 + 24), "64", font=font(16, mono=True), fill=BG if on or flush else DIM)
        sx = x0 + slots * (slot + gap) + 10
        d.polygon([(sx, y0 + 20), (sx + 26, y0 + 35), (sx, y0 + 50)], fill=YELLOW if flush else GRID)
        d.text((sx + 40, y0 + 24), "speakers", font=font(16), fill=YELLOW if flush else DIM)
        if not flush:
            # The next block slides in from the right to its slot.
            target = x0 + filled * (slot + gap)
            start = W - 40 - slot
            bx = start + (target - start) * (t + 1) / travel
            d.rounded_rectangle((bx, y0, bx + slot, y0 + 70), 8, fill=GREEN)
        d.text((x0, y0 + 95), "…and the device takes 256 at once: that wait is the latency",
               font=font(14), fill=YELLOW if flush else BLUE)
        frames.append(img)
    save("latency", frames, fps=10)


SHOTS = {
    "oscillator-waves": oscillator_waves,
    "filter-sweep": filter_sweep,
    "adsr": adsr,
    "sequencer": sequencer,
    "patch": patch,
    "visualizer": visualizer,
    "latency": latency,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="*", help=", ".join(SHOTS))
    args = parser.parse_args()
    for name in args.names or SHOTS:
        SHOTS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
