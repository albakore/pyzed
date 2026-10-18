"""Bitmap images: ``pz.image`` and the zoomable ``pz.image_viewer``.

    python examples/image_viewer.py [picture.png]

Without an argument it shows a picture generated in pure Python (raw RGBA pixels
passed with ``size=(w, h)``). Scroll to zoom the viewer and drag to pan.
"""

import math
import sys

import pyzed as pz
from pyzed import ui

W, H = 480, 320


def generated_pixels():
    """A colorful plasma pattern as raw RGBA bytes."""
    out = bytearray()
    for y in range(H):
        for x in range(W):
            v = math.sin(x / 23) + math.sin(y / 17) + math.sin((x + y) / 31) + math.sin(math.hypot(x - W / 2, y - H / 2) / 19)
            out += bytes((int(128 + 127 * math.sin(v * math.pi)), int(128 + 127 * math.sin(v * math.pi + 2)),
                          int(128 + 127 * math.sin(v * math.pi + 4)), 255))
    return bytes(out)


class Viewer(pz.App):
    title = "Image viewer"
    size = (1000, 640)

    def __init__(self, path=None):
        self.path = path
        self.pixels = None if path else generated_pixels()
        self.fit = "contain"
        self.radius = 12.0
        self.opacity = 1.0

    def source(self, **kwargs):
        if self.path:
            return dict(source=self.path, **kwargs)
        return dict(source=self.pixels, size=(W, H), **kwargs)

    def view(self):
        t = self.resolved_theme()
        thumbs = pz.column([
            ui.label("pz.image", weight="semibold"),
            ui.field("Fit", ui.select(["contain", "cover", "fill", "none", "scale_down"], self.fit,
                                      lambda v: setattr(self, "fit", v), width=130)),
            ui.field("Radius", pz.container(ui.slider(self.radius, lambda v: setattr(self, "radius", v), min=0, max=60),
                                            width=130)),
            ui.field("Opacity", pz.container(ui.slider(self.opacity, lambda v: setattr(self, "opacity", v)),
                                             width=130)),
            pz.container(pz.image(**self.source(width="fill", height=200, content_fit=self.fit, radius=self.radius,
                                                opacity=self.opacity)),
                         width="fill", height=200, bg=t.surface, radius=self.radius),
            pz.row([pz.image(**self.source(width=64, height=64, content_fit="cover", radius=32)),
                    pz.image(**self.source(width=64, height=64, content_fit="cover", radius=8, rotation=15)),
                    pz.image(**self.source(width=64, height=64, content_fit="cover", filter="nearest", scale=2))],
                   spacing=12),
        ], spacing=12, width=320)
        viewer = pz.column([
            ui.label("pz.image_viewer (scroll to zoom, drag to pan)", weight="semibold"),
            pz.container(pz.image_viewer(**self.source(width="fill", height="fill")), width="fill", height="fill",
                         bg=t.surface, radius=t.radius, clip=True),
        ], spacing=12, width="fill")
        return pz.container(pz.row([thumbs, viewer], spacing=20), padding=20, bg=t.background,
                            width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Viewer(sys.argv[1] if len(sys.argv) > 1 else None))
