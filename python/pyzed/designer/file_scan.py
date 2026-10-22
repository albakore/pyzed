"""Lists of project files for views (the Open dialog, a shader's file picker, base components).

A view runs after every change, and walking a project on each one (its ``.venv`` included) made
typing in those dialogs slow. ``files`` walks the folder once, then answers from memory and walks
it again on a worker thread when the list is older than ``FRESH`` seconds; the window redraws if
something changed on disk.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Tuple

from .. import _core

#: Folders never listed: environments, caches and build output (hidden folders are skipped too).
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build"}
#: How old (in seconds) a list may be before it is read again in the background.
FRESH = 2.0

_lists: Dict[tuple, Tuple[float, List[Path]]] = {}
_reading: set = set()
_lock = threading.Lock()


def files(root: Path, suffixes: Tuple[str, ...], limit: int = 500) -> List[Path]:
    """The files under ``root`` ending in one of ``suffixes``, sorted, at most ``limit``."""
    key = (str(root), tuple(suffixes), limit)
    with _lock:
        known = _lists.get(key)
    if known is None:  # the first look waits for the disk: the view needs something to show
        found = walk(root, suffixes, limit)
        with _lock:
            _lists[key] = (time.monotonic(), found)
        return found
    if time.monotonic() - known[0] > FRESH:
        _read_later(key, root, suffixes, limit)
    return known[1]


def forget() -> None:
    """Drops every list, so the next look reads the disk again (after saving a new file)."""
    with _lock:
        _lists.clear()


def _read_later(key: tuple, root: Path, suffixes: Tuple[str, ...], limit: int) -> None:
    with _lock:
        if key in _reading:
            return
        _reading.add(key)

    def work() -> None:
        found = walk(root, suffixes, limit)
        with _lock:
            _reading.discard(key)
            old = _lists.get(key)
            _lists[key] = (time.monotonic(), found)
        if old is None or old[1] != found:
            try:
                _core.post(lambda: None)  # redraw with the new list
            except RuntimeError:
                pass  # no running app (tests)

    threading.Thread(target=work, daemon=True, name="pyzed-file-scan").start()


def walk(root: Path, suffixes: Tuple[str, ...], limit: int = 500) -> List[Path]:
    """Walks ``root`` now (skipping ``SKIP_DIRS`` and hidden folders) for files ending in ``suffixes``."""
    found: List[Path] = []
    try:
        for folder, dirs, names in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
            found.extend(Path(folder) / n for n in sorted(names) if n.endswith(tuple(suffixes)))
            if len(found) >= limit:
                break
    except OSError:
        pass
    return sorted(found)[:limit]
