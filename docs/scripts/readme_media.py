"""Animations for README.md and README.es.md, in docs/readme/.

    python docs/scripts/readme_media.py            # everything
    python docs/scripts/readme_media.py counter    # only some: counter, components, media

* ``counter``: the README's quick-start counter, recorded with ``pyzed record`` (Pyzed Dark).
* ``components``: the library's animations (docs/public/library/*.dark.webp) cropped to what they
  show, on the same 16:9 canvas, so they line up in a table.
* ``media``: the docs' MP4 clips (docs/public/media/*.mp4) as small animated WebP (needs ffmpeg),
  since GitHub and PyPI don't play videos in a README.

The README links the files with raw.githubusercontent.com URLs, so PyPI shows them too; clips that
already exist as WebP in docs/public are linked from there, without copies.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageSequence

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "readme"
LIBRARY = ROOT / "docs" / "public" / "library"
MEDIA = ROOT / "docs" / "public" / "media"

COMPONENTS = [
    "button",
    "input",
    "select",
    "slider",
    "switch",
    "toast",
    "command-palette",
    "menu",
    "tree",
    "calendar",
    "accordion",
    "editor",
]
# name: (folder, width, fps, quality, seconds or None, (aspect, background) to pad to, or None)
CLIPS = {
    "hover": ("media", 720, 15, 72, None, None),
    "form-validation": ("media", 480, 15, 72, None, (16 / 9, "0e0e0e")),
    "shader-graph": ("media", 960, 15, 72, None, None),
    "shaders": ("media", 640, 12, 60, 6, None),
    "snake": ("games", 560, 15, 72, None, (4 / 3, "0e0e0e")),
    "breakout": ("games", 560, 15, 72, None, (4 / 3, "0e0e0e")),
    "neon-invaders": ("games", 560, 12, 60, None, (4 / 3, "0c0a14")),
}
# Games already recorded as WebP for the docs, on the same 4:3 canvas as the ones above.
GAMES = ["game-platformer", "game-asteroids", "game-2048"]
COUNTER_STEPS = (
    "wait(400); hover('1#1'); press(); wait(350); press(); wait(350); press(); wait(500); "
    "hover('1#0'); press(); wait(500); hover(('1#1', 36, 0)); wait(400); press(); wait(900); "
    "leave(); wait(300)"
)


def counter() -> None:
    """The quick-start code, taken from README.md so the clip always matches it."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    code = re.search(r"^import pyzed as pz\n.*?^pz\.run\(Counter\)$", readme, re.S | re.M).group(0)
    with tempfile.TemporaryDirectory() as tmp:
        app = Path(tmp) / "counter.py"
        app.write_text(code.replace("pz.run(Counter)", ""), encoding="utf-8")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pyzed.recording",
                "clip",
                f"{app}:Counter",
                "--size",
                "360x220",
                "--scale",
                "2",
                "--theme",
                "Pyzed Dark",
                "--fps",
                "20",
                "-f",
                "webp",
                "--steps",
                COUNTER_STEPS,
                "-o",
                str(OUT / "counter.webp"),
            ],
            check=True,
        )


def _content_box(im: Image.Image) -> tuple[int, int, int, int]:
    """What differs from the background in any frame."""
    box = None
    bg = None
    for frame in ImageSequence.Iterator(im):
        f = frame.convert("RGB")
        if bg is None:
            bg = Image.new("RGB", f.size, f.getpixel((2, 2)))
        diff = ImageChops.difference(f, bg).convert("L").point(lambda v: 255 if v > 12 else 0)
        b = diff.getbbox()
        if b:
            box = b if box is None else (min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3]))
    return box


def _save(frames: list[Image.Image], durations: list[int], path: Path, quality: int = 82) -> None:
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=durations, loop=0, quality=quality, method=4)


def _pad(src: Path, dst: Path, aspect: float, quality: int) -> None:
    """Centers an animation on a canvas of ``aspect`` (width / height), filled with its background."""
    im = Image.open(src)
    w, h = im.size
    w2, h2 = (round(h * aspect), h) if w / h < aspect else (w, round(w / aspect))
    frames, durations, bg = [], [], None
    for frame in ImageSequence.Iterator(im):
        f = frame.convert("RGB")
        bg = bg or f.getpixel((2, 2))
        canvas = Image.new("RGB", (w2, h2), bg)
        canvas.paste(f, ((w2 - w) // 2, (h2 - h) // 2))
        if w2 > 640:
            canvas = canvas.resize((640, round(h2 * 640 / w2)), Image.LANCZOS)
        frames.append(canvas)
        durations.append(frame.info.get("duration", 50))
    _save(frames, durations, dst, quality)


def components() -> None:
    out = OUT / "components"
    out.mkdir(parents=True, exist_ok=True)
    for name in COMPONENTS:
        im = Image.open(LIBRARY / f"{name}.dark.webp")
        x0, y0, x1, y1 = _content_box(im)
        pad = 48
        w, h = x1 - x0 + 2 * pad, y1 - y0 + 2 * pad
        w, h = (round(h * 16 / 9), h) if w / h < 16 / 9 else (w, round(w * 9 / 16))
        if w < 1120:
            w, h = 1120, 630
        left, top = round((x0 + x1 - w) / 2), round((y0 + y1 - h) / 2)
        frames, durations, bg = [], [], None
        for frame in ImageSequence.Iterator(im):
            f = frame.convert("RGB")
            bg = bg or f.getpixel((2, 2))
            canvas = Image.new("RGB", (w, h), bg)
            canvas.paste(f, (-left, -top))
            if w > 960:
                canvas = canvas.resize((960, round(h * 960 / w)), Image.LANCZOS)
            frames.append(canvas)
            durations.append(frame.info.get("duration", 50))
        _save(frames, durations, out / f"{name}.webp")
        print(name)


def media() -> None:
    for name, (folder, width, fps, quality, seconds, pad) in CLIPS.items():
        out = OUT / folder / f"{name}.webp"
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-v", "error", "-y"]
        if seconds:
            cmd += ["-t", str(seconds)]
        vf = f"fps={fps},scale={width}:-2:flags=lanczos"
        if pad:
            a, color = pad
            vf += (
                f",pad=w='max(iw,ceil(ih*{a}/2)*2)':h='max(ih,ceil(iw/{a}/2)*2)'"
                f":x=(ow-iw)/2:y=(oh-ih)/2:color=0x{color}"
            )
        cmd += ["-i", str(MEDIA / f"{name}.mp4"), "-vf", vf]
        cmd += ["-loop", "0", "-c:v", "libwebp_anim", "-quality", str(quality), "-compression_level", "4"]
        subprocess.run([*cmd, "-an", str(out)], check=True)
        print(name)
    for name in GAMES:
        (OUT / "games").mkdir(parents=True, exist_ok=True)
        _pad(MEDIA / f"{name}.webp", OUT / "games" / f"{name.removeprefix('game-')}.webp", 4 / 3, 65)
        print(name)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    steps = {"counter": counter, "components": components, "media": media}
    for step in sys.argv[1:] or steps:
        steps[step]()
