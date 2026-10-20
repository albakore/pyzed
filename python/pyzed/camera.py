"""Webcams: frames from a camera as raw RGBA bytes, ready for ``pz.image`` or ``ui.camera.Webcam``.

    cam = pz.camera.Camera(0, width=640, height=480)
    cam.start()
    ...
    frame = cam.frame          # the latest Frame(width, height, pixels, index, time), or None
    cam.snapshot("photo.png")
    cam.stop()

Backends, picked by ``backend="auto"`` in this order:

* ``"opencv"``: OpenCV (``pip install opencv-python``), the most compatible on every system.
* ``"ffmpeg"``: the ``ffmpeg`` program, reading Video4Linux on Linux, AVFoundation on macOS and
  DirectShow on Windows. Nothing to install in Python.
* ``"test"``: moving color bars, for screenshots, tests and machines without a camera.

A running camera reads frames in a background thread and asks the window to redraw when a
new one arrives, so a view that shows ``cam.frame`` stays live without a timer.
"""

from __future__ import annotations

import os
import platform
import shutil
import struct
import subprocess
import threading
import time
import zlib
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple

from . import _core

__all__ = ["BACKENDS", "Camera", "Frame", "available_backends", "devices", "open_camera", "release_camera"]

BACKENDS = ("opencv", "ffmpeg", "test")


class Frame(NamedTuple):
    """One picture from a camera: ``pixels`` are ``width * height * 4`` RGBA bytes."""

    width: int
    height: int
    pixels: bytes
    index: int
    time: float


def _has_opencv() -> bool:
    try:
        import cv2  # noqa: F401
    except Exception:
        return False
    return True


def available_backends() -> List[str]:
    """The backends that can run here, best first (``"test"`` always can)."""
    out = []
    if _has_opencv():
        out.append("opencv")
    if shutil.which("ffmpeg"):
        out.append("ffmpeg")
    out.append("test")
    return out


def devices() -> List[Tuple[Any, str]]:
    """The cameras found, as ``(device, name)`` pairs (``device`` is what ``Camera`` takes).

    On Linux they are the ``/dev/video*`` nodes; elsewhere the first few indexes OpenCV can open.
    """
    found: List[Tuple[Any, str]] = []
    if platform.system() == "Linux" and os.path.isdir("/sys/class/video4linux"):
        for entry in sorted(os.listdir("/sys/class/video4linux")):
            if not entry.startswith("video"):
                continue
            try:
                with open(f"/sys/class/video4linux/{entry}/name", encoding="utf-8") as f:
                    name = f.read().strip()
            except OSError:
                name = entry
            found.append((int(entry[5:]), name))
        return found
    if _has_opencv():
        import cv2

        for index in range(4):
            cap = cv2.VideoCapture(index)
            if cap is not None and cap.isOpened():
                found.append((index, f"Camera {index}"))
                cap.release()
    return found


class Camera:
    """A camera read in a background thread. ``device`` is an index (``0`` is the default camera),
    a path such as ``"/dev/video2"`` or, with ffmpeg on Windows, the camera's name.

    ``mirror=True`` flips it like a mirror (what people expect from a selfie view). ``on_frame``
    callbacks run in the camera thread with each new ``Frame``; keep them short.
    """

    def __init__(self, device: Any = 0, *, width: int = 640, height: int = 480, fps: int = 30,
                 mirror: bool = False, backend: str = "auto") -> None:
        self.device = device
        self.width = width
        self.height = height
        self.fps = fps
        self.mirror = mirror
        self.backend = available_backends()[0] if backend == "auto" else backend
        if self.backend not in BACKENDS:
            raise ValueError(f"unknown camera backend {backend!r} (use one of {', '.join(BACKENDS)} or 'auto')")
        self.frame: Optional[Frame] = None
        self.error: Optional[str] = None
        self.on_frame: List[Callable[[Frame], Any]] = []
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._redraw_pending = False
        self._process: Optional[subprocess.Popen] = None
        self._count = 0
        self._started = 0.0

    # -- life cycle ------------------------------------------------------------------------------
    @property
    def running(self) -> bool:
        """Whether the capture thread is running."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def measured_fps(self) -> float:
        """Frames per second actually received since ``start``."""
        elapsed = time.monotonic() - self._started
        return self._count / elapsed if elapsed > 0 and self._count else 0.0

    def start(self) -> "Camera":
        """Starts reading frames (does nothing if it already is)."""
        if self.running:
            return self
        self._stop.clear()
        self.error = None
        self._count = 0
        self._started = time.monotonic()
        self._thread = threading.Thread(target=self._run, name=f"pyzed-camera-{self.device}", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        """Stops reading frames and releases the camera."""
        self._stop.set()
        if self._process is not None:
            try:
                self._process.kill()
            except OSError:
                pass
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
        self._thread = None

    def __enter__(self) -> "Camera":
        return self.start()

    def __exit__(self, *_exc: Any) -> None:
        self.stop()

    def read(self, timeout: float = 5.0) -> Optional[Frame]:
        """Waits for the next frame (starting the camera if needed) and returns it."""
        self.start()
        last = self.frame.index if self.frame else -1
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and not self.error:
            if self.frame is not None and self.frame.index != last:
                return self.frame
            time.sleep(0.005)
        return self.frame

    def snapshot(self, path: Any) -> Optional[str]:
        """Saves the latest frame as a PNG at ``path``; returns the path, or ``None`` without a frame."""
        frame = self.frame or self.read()
        if frame is None:
            return None
        with open(path, "wb") as f:
            f.write(png(frame.width, frame.height, frame.pixels))
        return str(path)

    # -- the capture thread ----------------------------------------------------------------------
    def _publish(self, pixels: bytes, width: int, height: int) -> None:
        self._count += 1
        frame = Frame(width, height, pixels, self._count, time.monotonic())
        self.frame = frame
        for callback in list(self.on_frame):
            try:
                callback(frame)
            except Exception as error:  # a bad callback must not stop the camera
                self.error = f"on_frame: {error}"
        if not self._redraw_pending:
            self._redraw_pending = True
            try:
                _core.post(self._redrawn)
            except RuntimeError:  # no window open (scripts, tests)
                self._redraw_pending = False

    def _redrawn(self) -> None:
        self._redraw_pending = False

    def _run(self) -> None:
        try:
            {"opencv": self._run_opencv, "ffmpeg": self._run_ffmpeg, "test": self._run_test}[self.backend]()
        except Exception as error:
            self.error = str(error) or type(error).__name__

    def _run_opencv(self) -> None:
        import cv2

        cap = cv2.VideoCapture(self.device)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)
        if not cap.isOpened():
            raise RuntimeError(f"cannot open camera {self.device!r}")
        try:
            while not self._stop.is_set():
                ok, image = cap.read()
                if not ok:
                    raise RuntimeError("the camera stopped sending frames")
                if self.mirror:
                    image = cv2.flip(image, 1)
                rgba = cv2.cvtColor(image, cv2.COLOR_BGR2RGBA)
                self._publish(rgba.tobytes(), rgba.shape[1], rgba.shape[0])
        finally:
            cap.release()

    def ffmpeg_input(self) -> List[str]:
        """The ffmpeg arguments that open this camera on this system."""
        system = platform.system()
        size = f"{self.width}x{self.height}"
        if system == "Darwin":
            return ["-f", "avfoundation", "-framerate", str(self.fps), "-video_size", size, "-i", f"{self.device}:none"]
        if system == "Windows":
            name = self.device if isinstance(self.device, str) else _dshow_names()[int(self.device)]
            return ["-f", "dshow", "-framerate", str(self.fps), "-video_size", size, "-i", f"video={name}"]
        path = self.device if isinstance(self.device, str) else f"/dev/video{int(self.device)}"
        return ["-f", "v4l2", "-framerate", str(self.fps), "-video_size", size, "-i", path]

    def _run_ffmpeg(self) -> None:
        filters = ["hflip"] if self.mirror else []
        filters.append(f"scale={self.width}:{self.height}")
        command = ["ffmpeg", "-loglevel", "error", "-nostdin", *self.ffmpeg_input(), "-vf", ",".join(filters),
                   "-pix_fmt", "rgba", "-f", "rawvideo", "-"]
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                         creationflags=flags)
        size = self.width * self.height * 4
        try:
            stdout = self._process.stdout
            assert stdout is not None
            while not self._stop.is_set():
                data = stdout.read(size)
                if len(data) < size:
                    if self._stop.is_set():
                        break
                    message = self._process.stderr.read().decode(errors="replace").strip() if self._process.stderr else ""
                    raise RuntimeError(message.splitlines()[-1] if message else "ffmpeg stopped sending frames")
                self._publish(data, self.width, self.height)
        finally:
            if self._process.poll() is None:
                self._process.kill()
            self._process = None

    def _run_test(self) -> None:
        w, h = self.width, self.height
        delay = 1.0 / max(self.fps, 1)
        frame = 0
        while not self._stop.is_set():
            self._publish(test_pattern(w, h, frame), w, h)
            frame += 1
            self._stop.wait(delay)


def _dshow_names() -> List[str]:
    """The DirectShow camera names ffmpeg lists on Windows."""
    result = subprocess.run(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                            capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    names = []
    for line in result.stderr.splitlines():
        if "(video)" in line and '"' in line:
            names.append(line.split('"')[1])
    if not names:
        raise RuntimeError("ffmpeg found no camera")
    return names


_BARS = [(235, 235, 235), (235, 235, 16), (16, 235, 235), (16, 235, 16), (235, 16, 235), (235, 16, 16),
         (16, 16, 235), (24, 24, 28)]


def test_pattern(width: int, height: int, frame: int = 0) -> bytes:
    """Color bars that slide sideways with a bouncing square: a stand-in camera image (RGBA)."""
    row = bytearray()
    for x in range(width * 2):
        r, g, b = _BARS[(x * len(_BARS) // width) % len(_BARS)]
        row += bytes((r, g, b, 255))
    shift = (frame * 4) % width
    line = bytes(row[shift * 4:(shift + width) * 4])
    band = height * 3 // 4
    out = bytearray(line * band)
    ramp = bytearray()
    for x in range(width):
        v = x * 255 // max(width - 1, 1)
        ramp += bytes((v, v, v, 255))
    out += bytes(ramp) * (height - band)
    size = max(8, min(width, height) // 6)
    span_x, span_y = max(width - size, 1), max(band - size, 1)
    px = abs((frame * 7) % (2 * span_x) - span_x)
    py = abs((frame * 5) % (2 * span_y) - span_y)
    block = bytes((20, 20, 24, 255)) * size
    for y in range(py, min(py + size, height)):
        start = (y * width + px) * 4
        out[start:start + size * 4] = block
    return bytes(out)


def png(width: int, height: int, rgba: bytes) -> bytes:
    """Encodes RGBA pixels as a PNG file (no Pillow needed)."""
    raw = b"".join(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")


# -- shared cameras ----------------------------------------------------------------------------------
_OPEN: Dict[Tuple[Any, ...], Tuple[Camera, int]] = {}
_LOCK = threading.Lock()


def open_camera(device: Any = 0, **options: Any) -> Camera:
    """A started camera shared by everything that opens the same device with the same options
    (several ``Webcam`` views of one camera read it once). Pair it with ``release_camera``."""
    key = (device, *sorted(options.items()))
    with _LOCK:
        camera, users = _OPEN.get(key, (None, 0))
        if camera is None:
            camera = Camera(device, **options)
        _OPEN[key] = (camera, users + 1)
    return camera.start()


def release_camera(camera: Camera) -> None:
    """Gives back a camera from ``open_camera``; the last user to give it back stops it."""
    with _LOCK:
        for key, (cam, users) in list(_OPEN.items()):
            if cam is camera:
                if users <= 1:
                    del _OPEN[key]
                    cam.stop()
                else:
                    _OPEN[key] = (cam, users - 1)
                return
