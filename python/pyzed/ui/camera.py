"""A live webcam view.

    ui.camera.Webcam(device=0, width=480, height=360, mirror=True)

It opens the camera when it first appears and releases it when it is no longer shown (views
of the same device share one capture). Pass ``camera=`` to show a ``pyzed.camera.Camera`` you
manage yourself, for example to process its frames.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from .. import _core
from ..camera import Camera, open_camera, release_camera
from ..component import Component
from ..icons import icon as _icon
from ..theme import alpha as _alpha
from ..theme import current as _current_theme

__all__ = ["Webcam"]


class Webcam(Component):
    """The picture of a webcam, updated as frames arrive.

    ``fit``: ``"cover"`` fills the box (cropping), ``"contain"`` shows the whole picture.
    ``overlay`` shows a recording dot, the camera's name and its frame rate on top; ``paused``
    freezes the last frame. ``backend`` is ``"auto"``, ``"opencv"``, ``"ffmpeg"`` or ``"test"``
    (color bars, handy without a camera).
    """

    device: Any = 0
    camera: Optional[Camera] = None
    width: float = 320
    height: float = 240
    capture_width: int = 640
    capture_height: int = 480
    fps: int = 30
    mirror: bool = True
    fit: Literal["cover", "contain", "fill"] = "cover"
    radius: float = 8
    overlay: bool = True
    paused: bool = False
    backend: Literal["auto", "opencv", "ffmpeg", "test"] = "auto"
    icon = "webcam"
    category = "Media"
    size = (320, 240)

    def setup(self) -> None:
        self.opened: Optional[Camera] = None
        self.frozen: Any = None

    def source(self) -> Optional[Camera]:
        """The camera shown: ``camera`` if given, else one opened for ``device``."""
        if self.camera is not None:
            return self.camera
        if self.opened is None:
            try:
                self.opened = open_camera(self.device, width=int(self.capture_width), height=int(self.capture_height),
                                          fps=self.fps, mirror=self.mirror, backend=self.backend)
            except Exception as error:  # an unknown backend, for instance
                self.frozen = str(error)
                return None
        return self.opened

    def on_unmount(self) -> None:
        if self.opened is not None:
            release_camera(self.opened)
            self.opened = None

    def _message(self, text: str, name: str) -> Any:
        th = _current_theme()
        body = _core.column([_icon(name, size=28, color=th.text_muted),
                             _core.text(text, size=12, color=th.text_muted, align_x="center")],
                            spacing=8, align="center")
        return _core.container(body, width=self.width, height=self.height, center=True, bg="#0d0e10",
                               radius=self.radius, border_color=th.border, border_width=1)

    def render(self) -> Any:
        cam = self.source()
        if cam is None:
            return self._message(str(self.frozen or "No camera"), "camera-off")
        frame = cam.frame
        if self.paused:
            frame = self.frozen if not isinstance(self.frozen, str) and self.frozen is not None else frame
        self.frozen = frame
        if frame is None:
            if cam.error:
                return self._message(cam.error, "camera-off")
            return self._message("Waiting for the camera…", "camera")
        picture = _core.image(frame.pixels, size=(frame.width, frame.height), width=self.width, height=self.height,
                              content_fit=self.fit, radius=self.radius)
        if not self.overlay:
            return picture
        dot = _core.container(None, width=8, height=8, radius=4, bg="#ff3b30" if not self.paused else "#9ca3af",
                              shadow=("#ff3b30cc", (0, 0), 6) if not self.paused else None)
        name = "PAUSED" if self.paused else f"CAM {self.device}  ·  {cam.measured_fps:.0f} fps"
        badge = _core.container(_core.row([dot, _core.text(name, size=10, color="#ffffff", font="mono")],
                                          spacing=6, align="center"),
                                padding=(3, 8), bg=_alpha("#000000", 0.55), radius=10)
        return _core.stack([picture, _core.pin(badge, x=8, y=8)], width=self.width, height=self.height)
