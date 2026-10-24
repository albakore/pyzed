"""Renders the screenshots of the Blocks pages (docs/src/assets/blocks) from examples/blocks/*.py.

    python docs/scripts/block_shots.py              # every block, dark and light
    python docs/scripts/block_shots.py login chat   # only some

Each block is drawn off-screen with ``App.screenshot`` (no window or GPU) at 1200x760, scale 2, once with
Pyzed Dark (``<name>-dark.png``) and once with Pyzed Light (``<name>-light.png``).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOCKS = ROOT / "examples" / "blocks"
OUT = ROOT / "docs" / "src" / "assets" / "blocks"
sys.path.insert(0, str(BLOCKS))

import pyzed as pz  # noqa: E402

THEMES = {"dark": "Pyzed Dark", "light": "Pyzed Light"}
SIZE = (1200, 760)


def app_class(module):
    apps = [v for v in vars(module).values()
            if isinstance(v, type) and issubclass(v, pz.App) and v.__module__ == module.__name__]
    return apps[-1]


def main(names):
    OUT.mkdir(parents=True, exist_ok=True)
    names = names or sorted(p.stem for p in BLOCKS.glob("*.py"))
    for name in names:
        cls = app_class(importlib.import_module(name))
        for suffix, theme in THEMES.items():
            app = cls()
            app.theme = theme
            app.__pyzed_view__()  # raises here if the view is broken (the renderer only prints it)
            path = OUT / f"{name}-{suffix}.png"
            app.screenshot(path, size=SIZE, scale=2, wait=0.3)
            print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main(sys.argv[1:])
