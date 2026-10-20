"""A webcam viewer: the live picture, a snapshot button and the camera's frame rate.

    python examples/audio/webcam.py            # the default camera
    python examples/audio/webcam.py test       # moving color bars, without a camera

It uses OpenCV when it is installed (pip install opencv-python), else the ffmpeg program, else the
test pattern. Snapshots are saved as PNG files next to this script.
"""

import sys
import time
from pathlib import Path

import pyzed as pz
from pyzed import camera, ui


class Webcam(pz.App):
    title = "Webcam"
    size = (760, 600)

    def __init__(self, backend="auto"):
        self.cam = camera.Camera(0, width=1280, height=720, mirror=True, backend=backend)
        self.paused = False
        self.saved = ""

    def on_start(self):
        self.cam.start()

    def on_close(self):
        self.cam.stop()

    def snapshot(self):
        path = Path(__file__).with_name(time.strftime("snapshot-%Y%m%d-%H%M%S.png"))
        self.saved = self.cam.snapshot(path) or "no frame yet"

    def view(self):
        th = self.resolved_theme()
        toolbar = pz.row([
            ui.button("Snapshot", self.snapshot, icon="camera", variant="filled"),
            ui.button("Resume" if self.paused else "Pause", lambda: setattr(self, "paused", not self.paused),
                      icon="play" if self.paused else "pause"),
            pz.space(width="fill"),
            pz.text(f"{self.cam.backend} · {self.cam.measured_fps:.0f} fps", size=12, color=th.text_muted),
        ], spacing=8, align="center")
        return pz.container(pz.column([
            ui.camera.Webcam(camera=self.cam, width=720, height=405, paused=self.paused, radius=10),
            toolbar,
            pz.text(f"Saved {self.saved}" if self.saved else (self.cam.error or ""), size=12, color=th.text_muted),
        ], spacing=12), padding=20, width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Webcam("test" if "test" in sys.argv[1:] else "auto"))
