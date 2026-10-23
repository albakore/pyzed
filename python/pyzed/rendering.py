"""How an app draws its windows: GPU or CPU, graphics API, antialiasing, frame rate and power.

Pyzed picks the best renderer by itself: the GPU (wgpu on Vulkan, Metal or DirectX 12) when there is one,
and its CPU renderer (tiny-skia) on machines without a usable GPU (virtual machines, remote desktops). A
project can tune that in ``pyproject.toml``::

    [tool.pyzed.rendering]
    renderer = "cpu"         # "auto", "gpu" or "cpu"
    gpu_api = "vulkan"       # "auto", "vulkan", "metal", "dx12" or "gl"
    gpu = "intel"            # part of the name of the GPU to use, when there are several
    power = "low"            # "auto", "high" (the fast GPU) or "low" (the integrated one, saves battery)
    vsync = "off"            # "auto", "on" or "off"
    present = "mailbox"      # "auto", "fifo", "fifo_relaxed", "mailbox" or "immediate" (wins over vsync)
    antialiasing = "8x"      # "auto" (4x), "off", "2x", "4x", "8x" or "16x": edges of canvas and charts
    frame_latency = "2"      # "auto" (1), "1", "2" or "3": frames the GPU may queue (more = smoother, later)
    memory = "performance"   # "auto" (low), "low" or "performance": how the GPU renderer allocates
    max_fps = 30             # the most frames per second animations draw (0 follows the screen)
    background_fps = 0       # the same for windows without the focus (0 pauses their animations)

Input and new content are always drawn at once: the frame rate limits only slow the frames that
animations ask for, which is what saves battery on laptops, phones and touch panels.

``pz.run`` reads that table (or ``App.rendering``) before the window opens, and ``pyzed build`` bakes it
into the packaged app. The settings become the environment variables Iced and wgpu read
(``ICED_BACKEND``, ``WGPU_BACKEND``, ``WGPU_ADAPTER_NAME``, ``WGPU_POWER_PREF``, ``ICED_PRESENT_MODE``,
``ICED_MSAA``, ``ICED_FRAME_LATENCY``, ``ICED_MEMORY``, ``ICED_MAX_FPS``, ``ICED_BACKGROUND_FPS``), so a
variable you set yourself still wins, and a deployed app can be tuned without touching its code.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict, List, MutableMapping, Optional, Union

__all__ = ["ANTIALIASING", "FRAME_LATENCY", "GPU_APIS", "MEMORY", "POWER", "PRESENT", "RENDERERS", "VSYNC",
           "Rendering", "find", "save"]

#: Where the app draws: chosen by Pyzed, always the GPU, or always the CPU.
RENDERERS = ("auto", "gpu", "cpu")
#: The graphics API of the GPU renderer.
GPU_APIS = ("auto", "vulkan", "metal", "dx12", "gl")
#: Which GPU to use on machines with two: the fast one ("high") or the one that saves battery ("low").
POWER = ("auto", "high", "low")
#: Wait for the screen's refresh before showing a frame (no tearing) or draw as fast as possible.
VSYNC = ("auto", "on", "off")
#: How finished frames reach the screen, when ``vsync`` is not enough: "fifo" waits for the screen (least
#: power), "fifo_relaxed" shows late frames at once, "mailbox" keeps only the newest frame (low latency
#: without tearing) and "immediate" shows each frame at once (lowest latency, may tear). Modes the system
#: lacks fall back to vsync on or off.
PRESENT = ("auto", "fifo", "fifo_relaxed", "mailbox", "immediate")
#: Multisampling of the shapes drawn as meshes (canvas, charts, curves): smoother edges for more GPU work.
ANTIALIASING = ("auto", "off", "2x", "4x", "8x", "16x")
#: Frames the GPU may prepare ahead of the screen: 1 answers input soonest, 2 or 3 smooth heavy scenes.
FRAME_LATENCY = ("auto", "1", "2", "3")
#: How the GPU renderer allocates memory: in small blocks freed soon ("low") or large blocks kept.
MEMORY = ("auto", "low", "performance")

_CHOICES = {"renderer": RENDERERS, "gpu_api": GPU_APIS, "power": POWER, "vsync": VSYNC, "present": PRESENT,
            "antialiasing": ANTIALIASING, "frame_latency": FRAME_LATENCY, "memory": MEMORY}
_ENV = {
    "renderer": ("ICED_BACKEND", {"gpu": "wgpu", "cpu": "tiny-skia"}),
    "gpu_api": ("WGPU_BACKEND", {"vulkan": "vulkan", "metal": "metal", "dx12": "dx12", "gl": "gl"}),
    "power": ("WGPU_POWER_PREF", {"high": "high", "low": "low"}),
    "vsync": ("ICED_PRESENT_MODE", {"on": "vsync", "off": "no_vsync"}),
    "present": ("ICED_PRESENT_MODE", {m: m for m in PRESENT[1:]}),
    "antialiasing": ("ICED_MSAA", {"off": "0", "2x": "2", "4x": "4", "8x": "8", "16x": "16"}),
    "frame_latency": ("ICED_FRAME_LATENCY", {"1": "1", "2": "2", "3": "3"}),
    "memory": ("ICED_MEMORY", {"low": "low", "performance": "performance"}),
}
#: Settings that matter for the CPU renderer too (the rest only configure the GPU).
_BOTH = {"renderer", "max_fps", "background_fps"}
TABLE = "tool.pyzed.rendering"


def _fps(value: Any, *, name: str, strict: bool) -> Optional[int]:
    if value is None or value == "auto":
        return None
    if value == "pause":
        return 0
    try:
        fps = int(value)
    except (TypeError, ValueError):
        if strict:
            raise ValueError(f"{name} must be a number of frames per second, not {value!r}") from None
        return None
    if fps < 0 or fps > 1000:
        if strict:
            raise ValueError(f"{name} must be between 0 and 1000, not {fps}")
        return None
    return fps


@dataclass
class Rendering:
    """The renderer settings of an app (each ``"auto"`` lets Pyzed decide)."""

    renderer: str = "auto"
    gpu_api: str = "auto"
    power: str = "auto"
    vsync: str = "auto"
    present: str = "auto"
    antialiasing: str = "auto"
    frame_latency: str = "auto"
    memory: str = "auto"
    #: Part of the name of the GPU to use (``"nvidia"``, ``"intel"``), matched without case; ``""`` lets
    #: ``power`` decide.
    gpu: str = ""
    #: The most frames per second animations draw in a focused window; ``0`` follows the screen.
    max_fps: int = 0
    #: The same for windows without the focus: ``0`` pauses their animations, ``None`` uses ``max_fps``.
    background_fps: Optional[int] = None

    def __post_init__(self) -> None:
        for name, choices in _CHOICES.items():
            value = str(getattr(self, name)).lower()
            if value not in choices:
                raise ValueError(f"{name} must be one of {', '.join(choices)}, not {value!r}")
            setattr(self, name, value)
        self.gpu = str(self.gpu or "").strip()
        self.max_fps = _fps(self.max_fps, name="max_fps", strict=True) or 0
        self.background_fps = _fps(self.background_fps, name="background_fps", strict=True)

    @classmethod
    def from_table(cls, table: Any) -> "Rendering":
        """Builds the settings from a ``[tool.pyzed.rendering]`` table, ignoring unknown keys and values."""
        out = cls()
        if isinstance(table, dict):
            for name, choices in _CHOICES.items():
                value = str(table.get(name, "auto")).lower()
                if value in choices:
                    setattr(out, name, value)
            if isinstance(table.get("gpu"), str):
                out.gpu = table["gpu"].strip()
            out.max_fps = _fps(table.get("max_fps"), name="max_fps", strict=False) or 0
            out.background_fps = _fps(table.get("background_fps"), name="background_fps", strict=False)
        return out

    def to_table(self) -> Dict[str, Any]:
        """The settings that are not ``"auto"`` (or empty), as written to ``pyproject.toml``."""
        out: Dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if value != f.default:
                out[f.name] = value
        return out

    @property
    def custom(self) -> bool:
        """Whether any setting is not ``"auto"``."""
        return bool(self.to_table())

    def env(self) -> Dict[str, str]:
        """The environment variables that carry these settings to Iced and wgpu."""
        gpu = self.renderer != "cpu"  # the rest only configures the GPU renderer
        out = {}
        for name, (variable, values) in _ENV.items():
            value = values.get(getattr(self, name))
            if value is not None and (name in _BOTH or gpu):
                out[variable] = value  # ``present`` comes after ``vsync``: it wins
        if self.gpu and gpu:
            out["WGPU_ADAPTER_NAME"] = self.gpu
        if self.max_fps:
            out["ICED_MAX_FPS"] = str(self.max_fps)
        if self.background_fps is not None:
            out["ICED_BACKGROUND_FPS"] = str(self.background_fps)
        return out

    def apply(self, environ: Optional[MutableMapping[str, str]] = None) -> List[str]:
        """Sets the variables of ``env()`` that are not set yet (yours win); returns the ones it set."""
        environ = os.environ if environ is None else environ
        changed = []
        for name, value in self.env().items():
            if name not in environ:
                environ[name] = value
                changed.append(name)
        return changed


def _pyproject(start: Path) -> Optional[Path]:
    for folder in (start, *start.parents):
        file = folder / "pyproject.toml"
        if file.is_file():
            return file
    return None


def find(start: Union[str, Path, None] = None) -> Rendering:
    """The ``[tool.pyzed.rendering]`` of the project around ``start`` (by default the current folder, then
    the folder of the script that started Python); all ``"auto"`` when there is none."""
    from .project import _loads_toml

    starts = [Path(start)] if start is not None else [Path.cwd()]
    if start is None and sys.argv and sys.argv[0]:
        starts.append(Path(sys.argv[0]).resolve().parent)
    for folder in starts:
        file = _pyproject(folder.resolve() if folder.exists() else folder)
        if file is None:
            continue
        try:
            data = _loads_toml(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tool = data.get("tool", {}).get("pyzed")
        if isinstance(tool, dict):
            return Rendering.from_table(tool.get("rendering"))
    return Rendering()


def save(root: Union[str, Path], rendering: Rendering) -> Path:
    """Writes ``rendering`` to ``[tool.pyzed.rendering]`` of ``root/pyproject.toml`` (removing the table when
    every setting is ``"auto"``), keeping the rest of the file as it is; returns the file."""
    file = Path(root) / "pyproject.toml"
    text = file.read_text(encoding="utf-8")
    found = re.search(r"^\[tool\.pyzed\.rendering\][ \t]*\n(?:(?!\[).*\n?)*", text, re.M)
    table = rendering.to_table()
    def toml(value: Any) -> str:
        return str(value) if isinstance(value, int) and not isinstance(value, bool) else '"%s"' % str(value).replace('"', '\\"')

    new = ("[tool.pyzed.rendering]\n" + "".join(f"{k} = {toml(v)}\n" for k, v in table.items())) if table else ""
    if found:
        rest = text[found.end():]
        text = text[:found.start()] + new + ("\n" if new and rest.strip() else "") + rest
    elif new:
        text = text.rstrip() + "\n\n" + new
    file.write_text(re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n", encoding="utf-8")
    return file
