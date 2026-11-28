"""Renders the stills of the Routing section (docs/src/assets/guides/routing-*.png).

    uv run python docs/scripts/routing_shots.py

Each picture is the store of ``examples/routing`` at one address: the product list, a product, the
skeleton of its ``loading.py`` while ``load`` runs, the ``not_found.py`` of a product that doesn't
exist and the settings with their own layout. The animations come
from routing_media.py. Run optimize_images.py after.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyzed as pz

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "src" / "assets" / "guides"
sys.path.insert(0, str(ROOT / "examples" / "routing"))

import api  # noqa: E402
from main import Store  # noqa: E402

SIZE = (1040, 620)


def shot(url: str, path: Path, *, loading: bool = False, scale: float = 2.0) -> None:
    api.DELAY = 30 if loading else 0
    app = Store()
    app.router.replace(url)
    if not loading:
        app.router.prefetch(url)
        app.router.wait()
    pz.screenshot(app, path, size=SIZE, scale=scale)
    if not loading:  # a page that loaded after the first view (a layout's data)
        app.router.wait()
        pz.screenshot(app, path, size=SIZE, scale=scale)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shot("/products?sort=price", OUT / "routing-products.png")
    shot("/products/3", OUT / "routing-product.png")
    shot("/products/3", OUT / "routing-loading.png", loading=True)
    shot("/products/42", OUT / "routing-not-found.png")
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("routing-*"))))


if __name__ == "__main__":
    main()
