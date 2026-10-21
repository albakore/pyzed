"""Splash screens: an image shown in a window without a frame while the app starts.

Give your app one with ``App.splash``::

    class Main(pz.App):
        splash = pz.Splash("assets/splash.png", duration=1.5)

The splash opens first, centered on the screen. After ``duration`` seconds the main window
opens, ``on_start`` runs (so slow work there keeps the splash up a little longer) and the
splash closes. ``pyzed build`` adds one to a packaged app from ``[tool.pyzed.build.splash]``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple, Union

from . import _core
from .app import Window

#: The largest window a splash gets from the size of its image, in logical pixels.
MAX_SIZE = (900.0, 600.0)


def fit(size: Tuple[float, float], limit: Tuple[float, float] = MAX_SIZE) -> Tuple[float, float]:
    """``size`` scaled down, keeping its proportions, to fit in ``limit`` (never scaled up)."""
    width, height = size
    scale = min(1.0, limit[0] / max(width, 1.0), limit[1] / max(height, 1.0))
    return (round(width * scale), round(height * scale))


class Splash(Window):
    """A splash screen: ``image`` (a path or the file's bytes) filling a frameless, centered window.

    ``duration`` is how long it stays up at least, in seconds. ``size`` defaults to the image's size
    (scaled down to fit 900 × 600). ``text`` is written over the bottom of the image (for example
    ``"Loading…"``), in ``color``; ``background`` fills what the image leaves uncovered.
    """

    title = ""
    decorations = False
    resizable = False
    position = "center"

    def __init__(self, image: Union[str, Path, bytes], *, duration: float = 1.5,
                 size: Optional[Tuple[float, float]] = None, text: Optional[str] = None,
                 color: str = "#ffffff", background: Optional[str] = None, title: Optional[str] = None,
                 icon: Any = None) -> None:
        self.image = image if isinstance(image, bytes) else str(image)
        self.duration = float(duration)
        if size is None:
            try:
                width, height = _core.image_size(self.image)
                size = fit((float(width), float(height)))
            except (OSError, ValueError):
                size = (480.0, 320.0)
        self.size = size
        self.min_size = self.max_size = size
        self.text = text
        self.color = color
        self.background = background
        if title is not None:
            self.title = title
        if icon is not None:
            self.icon = icon

    def view(self) -> Any:
        picture = _core.image(self.image, width="fill", height="fill", content_fit="cover")
        layers = [picture]
        if self.text:
            layers.append(_core.container(_core.text(self.text, size=13, color=self.color), width="fill",
                                          height="fill", align_x="center", align_y="bottom", padding=16))
        return _core.container(_core.stack(layers, width="fill", height="fill"), width="fill", height="fill",
                               bg=self.background)
