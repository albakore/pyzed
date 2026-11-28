"""Takes the picture of a native desktop notification over the store (docs/src/assets/guides/routing-notification.png).

    uv run python docs/scripts/routing_notification.py

Linux only: it starts a virtual screen (Xvfb), a session bus and dunst (styled by routing/dunstrc),
opens ``examples/routing`` in a real window and calls ``pz.notify`` like "Add to cart" does, then
captures the screen with ImageMagick's ``import``. Needs ``xvfb``, ``dunst`` and ``imagemagick``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "src" / "assets" / "guides" / "routing-notification.png"
SCREEN = (1040, 680)  # the window fills it; the notification shows over its top right


def inside() -> None:
    """Runs in the session bus: dunst, the app, the notification, the picture."""
    fonts = Path.home() / ".local" / "share" / "fonts" / "pyzed-docs"
    fonts.mkdir(parents=True, exist_ok=True)
    for font in (ROOT / "assets" / "fonts").glob("IBMPlexSans-*.ttf"):
        shutil.copy(font, fonts)
    subprocess.run(["fc-cache", "-f", str(fonts)], check=False)
    subprocess.run(["xsetroot", "-solid", "#0b0c10"], check=False)
    dunst = subprocess.Popen(["dunst", "-config", str(Path(__file__).parent / "routing" / "dunstrc")])
    app = subprocess.Popen([sys.executable, "-c", (
        "import sys; sys.path.insert(0, 'examples/routing'); import api; api.DELAY = 0; "
        "import pyzed as pz; from main import Store; from state import cart; cart.add(3); app = Store(); app.router.replace('/products/3'); pz.run(app)")],
        cwd=ROOT, env={**os.environ, "WGPU_BACKEND": os.environ.get("WGPU_BACKEND", "gl")})
    try:
        time.sleep(6)
        import pyzed as pz

        pz.notifications.app_name = "Pyzed Store"
        pz.notify("Added to your cart", "4K monitor · $399\nWe'll let you know when it ships.",
                  icon=ROOT / "assets" / "brand" / "app-icon-256.png", href="/products",
                  actions={"/account": "See account"})
        time.sleep(1.5)
        subprocess.run(["import", "-window", "root", str(OUT)], check=True)
        print("wrote", OUT.relative_to(ROOT))
    finally:
        app.terminate()
        dunst.terminate()


def main() -> None:
    if os.environ.get("PYZED_DOCS_NOTIFY") == "1":
        inside()
        return
    display = ":93"
    xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", f"{SCREEN[0]}x{SCREEN[1]}x24"])
    try:
        time.sleep(1)
        env = {**os.environ, "DISPLAY": display, "PYZED_DOCS_NOTIFY": "1"}
        subprocess.run(["dbus-run-session", "--", sys.executable, __file__], env=env, check=True)
    finally:
        xvfb.terminate()


if __name__ == "__main__":
    main()
