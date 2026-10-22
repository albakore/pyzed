"""How an app draws its windows: on the GPU or the CPU, which graphics API, power and vsync.

Pyzed picks the best renderer by itself: the GPU (wgpu on Vulkan, Metal or DirectX 12) when there is one,
and its CPU renderer (tiny-skia) on machines without a usable GPU (virtual machines, remote desktops). A
project can pin that choice in ``pyproject.toml``::

    [tool.pyzed.rendering]
    renderer = "cpu"      # "auto", "gpu" or "cpu"
    gpu_api = "vulkan"    # "auto", "vulkan", "metal", "dx12" or "gl"
    power = "low"         # "auto", "high" (the fast GPU) or "low" (the integrated one, saves battery)
    vsync = "off"         # "auto", "on" or "off"

``pz.run`` reads that table (or ``App.rendering``) before the window opens, and ``pyzed build`` bakes it
into the packaged app. The settings become the environment variables Iced and wgpu read
(``ICED_BACKEND``, ``WGPU_BACKEND``, ``WGPU_POWER_PREF``, ``ICED_PRESENT_MODE``), so a variable you set
yourself still wins.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Dict, List, MutableMapping, Optional, Union

__all__ = ["GPU_APIS", "POWER", "RENDERERS", "VSYNC", "Rendering", "find", "save"]

#: Where the app draws: chosen by Pyzed, always the GPU, or always the CPU.
RENDERERS = ("auto", "gpu", "cpu")
#: The graphics API of the GPU renderer.
GPU_APIS = ("auto", "vulkan", "metal", "dx12", "gl")
#: Which GPU to use on machines with two: the fast one ("high") or the one that saves battery ("low").
POWER = ("auto", "high", "low")
#: Wait for the screen's refresh before showing a frame (no tearing) or draw as fast as possible.
VSYNC = ("auto", "on", "off")

_CHOICES = {"renderer": RENDERERS, "gpu_api": GPU_APIS, "power": POWER, "vsync": VSYNC}
_ENV = {
    "renderer": ("ICED_BACKEND", {"gpu": "wgpu", "cpu": "tiny-skia"}),
    "gpu_api": ("WGPU_BACKEND", {"vulkan": "vulkan", "metal": "metal", "dx12": "dx12", "gl": "gl"}),
    "power": ("WGPU_POWER_PREF", {"high": "high", "low": "low"}),
    "vsync": ("ICED_PRESENT_MODE", {"on": "vsync", "off": "no_vsync"}),
}
TABLE = "tool.pyzed.rendering"


@dataclass
class Rendering:
    """The renderer settings of an app (each ``"auto"`` lets Pyzed decide)."""

    renderer: str = "auto"
    gpu_api: str = "auto"
    power: str = "auto"
    vsync: str = "auto"

    def __post_init__(self) -> None:
        for name, choices in _CHOICES.items():
            value = str(getattr(self, name)).lower()
            if value not in choices:
                raise ValueError(f"{name} must be one of {', '.join(choices)}, not {value!r}")
            setattr(self, name, value)

    @classmethod
    def from_table(cls, table: Any) -> "Rendering":
        """Builds the settings from a ``[tool.pyzed.rendering]`` table, ignoring unknown keys and values."""
        out = cls()
        if isinstance(table, dict):
            for name, choices in _CHOICES.items():
                value = str(table.get(name, "auto")).lower()
                if value in choices:
                    setattr(out, name, value)
        return out

    def to_table(self) -> Dict[str, str]:
        """The settings that are not ``"auto"``, as written to ``pyproject.toml``."""
        return {f.name: getattr(self, f.name) for f in fields(self) if getattr(self, f.name) != "auto"}

    @property
    def custom(self) -> bool:
        """Whether any setting is not ``"auto"``."""
        return bool(self.to_table())

    def env(self) -> Dict[str, str]:
        """The environment variables that carry these settings to Iced and wgpu."""
        out = {}
        for name, (variable, values) in _ENV.items():
            value = values.get(getattr(self, name))
            if value is not None and (name == "renderer" or self.renderer != "cpu"):  # the rest is the GPU's
                out[variable] = value
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
    new = ("[tool.pyzed.rendering]\n" + "".join(f'{k} = "{v}"\n' for k, v in table.items())) if table else ""
    if found:
        rest = text[found.end():]
        text = text[:found.start()] + new + ("\n" if new and rest.strip() else "") + rest
    elif new:
        text = text.rstrip() + "\n\n" + new
    file.write_text(re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n", encoding="utf-8")
    return file
