"""Writing frames to files: PNG, animated or still WebP, GIF, APNG, MP4 and WebM.

Identical consecutive frames are merged into one longer frame (WebP, GIF, APNG), so a pause costs
nothing. ``target`` (bytes) lowers the quality by bisection until the file fits, which takes
three or four encodes instead of one per quality step. MP4 and WebM need ``ffmpeg`` on the PATH;
frames are piped to it raw, without writing a PNG per frame.
"""

from __future__ import annotations

import io
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, Tuple

__all__ = ["FORMATS", "VIDEO", "encode", "encode_webp", "fit_quality", "merge", "save_poster"]

#: Every format ``encode`` writes, by file extension.
FORMATS = ("webp", "png", "gif", "apng", "mp4", "webm")
#: The formats that need ffmpeg.
VIDEO = ("mp4", "webm")


def merge(frames: Sequence[Any], fps: float) -> Tuple[List[Any], List[int]]:
    """``frames`` with consecutive repeats folded into the frame before, and each one's duration (ms)."""
    merged: List[Any] = []
    times: List[float] = []
    last = None
    step = 1000 / fps
    for im in frames:
        data = im.tobytes()
        if merged and data == last:
            times[-1] += step
        else:
            merged.append(im)
            times.append(step)
            last = data
    # Round the running total, so a long clip doesn't drift from its frame rate.
    out, total = [], 0.0
    for t in times:
        before = round(total)
        total += t
        out.append(max(1, round(total) - before))
    return merged, out


def encode_webp(frames: Sequence[Any], *, fps: float = 20, quality: int = 80, method: int = 4,
                lossless: bool = False, merged: Optional[Tuple[List[Any], List[int]]] = None) -> bytes:
    """An animated WebP that loops forever (a still one for a single frame). Lossy frames, with
    lossless ones where they come out smaller (``allow_mixed``), which keeps text crisp."""
    images, times = merged or merge(frames, fps)
    buf = io.BytesIO()
    if len(images) == 1:
        images[0].save(buf, "WEBP", quality=quality, method=method, lossless=lossless)
    else:
        images[0].save(buf, "WEBP", save_all=True, append_images=images[1:], duration=times, loop=0,
                       quality=quality, method=method, lossless=lossless, allow_mixed=not lossless, minimize_size=True)
    return buf.getvalue()


def fit_quality(make: Callable[[int], bytes], target: int, low: int = 40, high: int = 90) -> Tuple[bytes, int]:
    """The best quality between ``low`` and ``high`` whose ``make(quality)`` fits ``target`` bytes
    (the lowest one if none does), found by bisection."""
    best = None
    data = make(high)
    if len(data) <= target:
        return data, high
    lo, hi = low, high - 1
    smallest = None
    while lo <= hi:
        mid = (lo + hi) // 2
        data = make(mid)
        if len(data) <= target:
            best = (data, mid)
            lo = mid + 1
        else:
            smallest = (data, mid)
            hi = mid - 1
    if best:
        return best
    return smallest if smallest and smallest[1] == low else (make(low), low)


def save_poster(image: Any, out: Path, quality: int = 82) -> None:
    """A still WebP of one frame (what ``prefers-reduced-motion`` shows)."""
    image.save(out, "WEBP", quality=quality, method=6)


def _gif(frames: Sequence[Any], fps: float, merged: Optional[tuple] = None) -> bytes:
    from PIL import Image

    images, times = merged or merge(frames, fps)
    # One palette for the whole clip keeps colors from flickering between frames; it is made from a
    # strip of frames spread over the clip, so colors that only show up later (a press) are in it.
    picks = images[:: max(1, len(images) // 8)][:8]
    w, h = images[0].size
    strip = Image.new("RGB", (w, h * len(picks)))
    for i, im in enumerate(picks):
        strip.paste(im, (0, h * i))
    palette = strip.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    paletted = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    buf = io.BytesIO()
    if len(paletted) == 1:
        paletted[0].save(buf, "GIF", optimize=True)
    else:
        paletted[0].save(buf, "GIF", save_all=True, append_images=paletted[1:], duration=times, loop=0,
                         optimize=True, disposal=1)
    return buf.getvalue()


def _apng(frames: Sequence[Any], fps: float, merged: Optional[tuple] = None) -> bytes:
    images, times = merged or merge(frames, fps)
    buf = io.BytesIO()
    if len(images) == 1:
        images[0].save(buf, "PNG", optimize=False, compress_level=6)
    else:
        images[0].save(buf, "PNG", save_all=True, append_images=images[1:], duration=times, loop=0,
                       default_image=False, compress_level=6)
    return buf.getvalue()


def _video(frames: Sequence[Any], out: Path, fmt: str, fps: float, quality: int) -> None:
    """Pipes the frames to ffmpeg. ``quality`` (0-100, higher is better) becomes its CRF."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(f"{fmt.upper()} needs ffmpeg on the PATH (https://ffmpeg.org/download.html)")
    w, h = frames[0].size
    w2, h2 = w - w % 2, h - h % 2
    if fmt == "mp4":
        crf = round(51 - quality * 0.33)  # 80 -> 25
        codec = ["-c:v", "libx264", "-preset", "slow", "-tune", "animation", "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    else:
        crf = round(63 - quality * 0.35)  # 80 -> 35
        codec = ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0", "-row-mt", "1", "-deadline", "good",
                 "-cpu-used", "2", "-pix_fmt", "yuv420p"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-", "-vf", f"crop={w2}:{h2}:0:0", *codec, "-an", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for im in frames:
            proc.stdin.write(im.tobytes())
    except BrokenPipeError:
        pass
    _, err = proc.communicate()
    if proc.returncode:
        raise RuntimeError(f"ffmpeg failed: {err.decode(errors='replace').strip()}")


def encode(frames: Sequence[Any], out: Path, fmt: str, *, fps: float = 20, quality: int = 80,
           target: int = 0, method: int = 4, lossless: bool = False, poster: float = 0.0) -> dict:
    """Writes ``frames`` (RGB Pillow images) to ``out`` as ``fmt``; returns what was written
    (``bytes``, ``quality``, ``frames``: the distinct ones). ``target`` > 0 fits the file under that many
    bytes (WebP, MP4 and WebM). ``poster`` picks the frame a PNG shows (0: the first, 0.5: the middle)."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt.lower()
    if fmt == "png":
        index = max(0, min(len(frames) - 1, int(len(frames) * poster)))
        frames[index].save(out, "PNG", optimize=True)
        return {"bytes": out.stat().st_size, "frames": 1, "quality": 100}
    if fmt in VIDEO:
        def make_video(q: int) -> bytes:
            _video(frames, out, fmt, fps, q)
            return out.read_bytes()

        data, q = fit_quality(make_video, target, low=30) if target else (make_video(quality), quality)
        out.write_bytes(data)
        return {"bytes": len(data), "frames": len(frames), "quality": q}
    merged = merge(frames, fps)
    if fmt == "webp":
        def make_webp(q: int) -> bytes:
            return encode_webp(frames, fps=fps, quality=q, method=method, lossless=lossless, merged=merged)

        data, q = fit_quality(make_webp, target) if target and not lossless else (make_webp(quality), quality)
    elif fmt == "gif":
        data, q = _gif(frames, fps, merged), 100
    elif fmt == "apng":
        data, q = _apng(frames, fps, merged), 100
    else:
        raise ValueError(f"unknown format {fmt!r} (use {', '.join(FORMATS)})")
    out.write_bytes(data)
    return {"bytes": len(data), "frames": len(merged[0]), "quality": q}
