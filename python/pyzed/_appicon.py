"""App icon files from one picture: Windows ``.ico``, macOS ``.icns`` and a PNG for Linux and the windows.

Both formats can hold PNG images, so each size is resized by the Rust core
(``_core.resize_image``) and stored as is; no Pillow, ``sips`` or ``iconutil`` is needed.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence, Tuple, Union

Source = Union[str, Path, bytes]

#: The sizes Windows picks from (Explorer, the taskbar, Alt+Tab, high DPI).
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)
#: macOS icon types that hold PNG data, with their size in pixels.
ICNS_TYPES = (("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128), ("ic08", 256), ("ic09", 512),
              ("ic10", 1024), ("ic11", 32), ("ic12", 64), ("ic13", 256), ("ic14", 512))


def _resizer() -> Callable[[Source, int, int], bytes]:
    from . import _core

    return _core.resize_image


def _source(source: Source) -> Union[str, bytes]:
    return source if isinstance(source, bytes) else str(source)


def size_of(source: Source) -> Tuple[int, int]:
    """The width and height of the picture ``source`` (a path or the file's bytes)."""
    from . import _core

    width, height = _core.image_size(_source(source))
    return int(width), int(height)


def pngs(source: Source, sizes: Iterable[int]) -> Dict[int, bytes]:
    """``source`` resized to each of ``sizes`` (squares), as PNG data by size."""
    resize = _resizer()
    return {size: bytes(resize(_source(source), size, size)) for size in sorted(set(sizes))}


def ico(images: Dict[int, bytes]) -> bytes:
    """A Windows icon file holding the PNG ``images`` (by size; 256 at most)."""
    entries = sorted(images.items())
    header = struct.pack("<HHH", 0, 1, len(entries))
    offset = len(header) + 16 * len(entries)
    directory: List[bytes] = []
    for size, data in entries:
        side = 0 if size >= 256 else size  # 0 means 256
        directory.append(struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    return header + b"".join(directory) + b"".join(data for _, data in entries)


def icns(images: Dict[int, bytes]) -> bytes:
    """A macOS icon file holding the PNG ``images`` (by size), each under every icon type of its size."""
    body = b"".join(kind.encode("ascii") + struct.pack(">I", len(images[size]) + 8) + images[size]
                    for kind, size in ICNS_TYPES if size in images)
    return b"icns" + struct.pack(">I", len(body) + 8) + body


def write_all(source: Source, folder: Path, name: str = "icon",
              kinds: Sequence[str] = ("ico", "icns", "png")) -> Dict[str, Path]:
    """Writes ``<name>.ico``, ``<name>.icns`` and ``<name>.png`` (256 pixels) made from ``source`` to ``folder``;
    returns their paths by kind."""
    folder.mkdir(parents=True, exist_ok=True)
    wanted = set(ICO_SIZES) if "ico" in kinds else set()
    if "icns" in kinds:
        wanted |= {size for _, size in ICNS_TYPES}
    if "png" in kinds:
        wanted.add(256)
    images = pngs(source, wanted)
    written: Dict[str, Path] = {}
    if "ico" in kinds:
        written["ico"] = folder / f"{name}.ico"
        written["ico"].write_bytes(ico({s: images[s] for s in ICO_SIZES}))
    if "icns" in kinds:
        written["icns"] = folder / f"{name}.icns"
        written["icns"].write_bytes(icns(images))
    if "png" in kinds:
        written["png"] = folder / f"{name}.png"
        written["png"].write_bytes(images[256])
    return written
