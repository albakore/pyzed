"""Renders the pictures of the routing guide (docs/src/assets/guides/routing-*.png, docs/public/media/routing/*.webp).

    uv run python docs/scripts/routing_shots.py

Each picture is the store of ``examples/routing`` at one address: the product list, a product, the
skeleton of its ``loading.py`` while ``load`` runs, the ``not_found.py`` of a product that doesn't
exist and the settings with their own layout. The animation goes through them like a user would.
Run optimize_images.py after.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pyzed as pz

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "src" / "assets" / "guides"
MEDIA = ROOT / "docs" / "public" / "media" / "routing"
sys.path.insert(0, str(ROOT / "examples" / "routing"))

import store  # noqa: E402
from main import Store  # noqa: E402

SIZE = (1040, 620)


def shot(url: str, path: Path, *, loading: bool = False, scale: float = 2.0) -> None:
    store.DELAY = 30 if loading else 0
    app = Store()
    app.router.replace(url)
    if not loading:
        app.router.prefetch(url)
        app.router.wait()
    pz.screenshot(app, path, size=SIZE, scale=scale)
    if not loading:  # a page that loaded after the first view (a layout's data)
        app.router.wait()
        pz.screenshot(app, path, size=SIZE, scale=scale)


def animation(frames, path: Path) -> None:
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        images, durations = [], []
        for index, (url, loading, ms) in enumerate(frames):
            file = Path(tmp) / f"{index}.png"
            shot(url, file, loading=loading, scale=1.0)
            images.append(Image.open(file).convert("RGB"))
            durations.append(ms)
        images[0].save(path, save_all=True, append_images=images[1:], duration=durations, loop=0, quality=80,
                       method=6)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    MEDIA.mkdir(parents=True, exist_ok=True)
    shot("/products?sort=price", OUT / "routing-products.png")
    shot("/products/3", OUT / "routing-product.png")
    shot("/products/3", OUT / "routing-loading.png", loading=True)
    shot("/products/42", OUT / "routing-not-found.png")
    shot("/settings/notifications", OUT / "routing-settings.png")
    animation([("/", False, 1400), ("/products", True, 500), ("/products", False, 1400), ("/products/3", True, 500),
               ("/products/3", False, 1400), ("/products/42", False, 1400), ("/docs/guide/routing", False, 1400),
               ("/settings/profile", False, 1400)], MEDIA / "navigation.webp")
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("routing-*"))))


if __name__ == "__main__":
    main()
