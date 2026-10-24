"""Frames as Pillow images: the pointer drawn on top, crops to what is drawn, resizing."""

from __future__ import annotations

from itertools import pairwise
from typing import Any, Optional, Sequence, Tuple

__all__ = ["changes", "content_box", "crop_box", "draw_pointer", "fit_image", "to_image", "touches_edge"]

Box = Tuple[int, int, int, int]


def to_image(rgba: bytes, size: Tuple[int, int]) -> Any:
    """An RGB image from a frame's RGBA bytes (frames are opaque)."""
    from PIL import Image

    return Image.frombuffer("RGBA", size, rgba, "raw", "RGBA", 0, 1).convert("RGB")


def content_box(image: Any, threshold: int = 10, background: Any = None) -> Optional[Box]:
    """The bounding box of what differs from the background (the color at (2, 2))."""
    from PIL import Image, ImageChops

    bg = Image.new("RGB", image.size, background or image.getpixel((2, 2)))
    return ImageChops.difference(image.convert("RGB"), bg).point(lambda v: 255 if v > threshold else 0).getbbox()


def draw_pointer(img: Any, at: Tuple[float, float], pressed: bool = False, scale: float = 2) -> None:
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


def changes(frames: Sequence[Any]) -> int:
    """How many distinct consecutive frames there are (1: nothing moves)."""
    n = 1
    for a, b in pairwise(frames):
        if a.tobytes() != b.tobytes():
            n += 1
    return n


def crop_box(frames: Sequence[Any], margin: int, even: bool = True) -> Box:
    """The union of every frame's content box (against its own background), plus ``margin``."""
    w, h = frames[0].size
    boxes = [b for b in (content_box(f) for f in _distinct(frames)) if b]
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


def touches_edge(frames: Sequence[Any]) -> bool:
    """Whether what is drawn reaches the edge of the canvas (the canvas is too small)."""
    w, h = frames[0].size
    for f in _distinct(frames):
        b = content_box(f)
        if b and (b[0] <= 2 or b[1] <= 2 or b[2] >= w - 2 or b[3] >= h - 2):
            return True
    return False


def _distinct(frames: Sequence[Any]) -> list:
    """``frames`` without consecutive repeats (a still moment needs measuring once)."""
    out: list = []
    last = None
    for f in frames:
        data = f.tobytes()
        if data != last:
            out.append(f)
            last = data
    return out


def fit_image(image: Any, box: Tuple[int, int]) -> Any:
    """``image`` scaled down to fit ``box`` (never up)."""
    from PIL import Image

    w, h = image.size
    k = min(box[0] / w, box[1] / h, 1.0)
    if k >= 1.0:
        return image
    return image.resize((max(2, round(w * k)), max(2, round(h * k))), Image.LANCZOS)
