"""Regenerates the images in docs/screenshots (rendered off-screen, no window or GPU needed).

    python examples/screenshots.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "docs" / "screenshots"
sys.path.insert(0, str(HERE))

import pyzed as pz  # noqa: E402
from counter import Counter  # noqa: E402
from gallery import Gallery  # noqa: E402
from zed_editor import Zed  # noqa: E402

pz.ui.base.KEY_STYLE = "words"

# Illustrative git state so the screenshots show Zed's status colors and gutter markers.
STATUS = {
    "src/render.rs": "modified",
    "src/app.rs": "modified",
    "python/pyzed/ui/overlays.py": "modified",
    "examples/zed_editor.py": "created",
}
MARKERS = {
    "src/render.rs": {28: "modified", 29: "modified", 41: "created", 42: "created", 43: "created", 55: "deleted"},
    "python/pyzed/ui/overlays.py": {14: "modified", 33: "created", 34: "created"},
}


def workspace(theme, files, active, expanded=(), **flags):
    app = Zed(str(ROOT), status=STATUS)
    app.theme = theme
    app.expanded |= set(expanded)
    for path in files:
        app.open_file(path)
    app.open_file(active)
    app.markers.update({k: v for k, v in MARKERS.items()})
    for key, value in flags.items():
        setattr(app, key, value)
    return app


def hot_reload_shots(scale):
    """Before, after and failed-reload images of examples/hot_reload, using the real reloader."""
    import importlib
    import os
    import shutil
    import tempfile
    import time

    from pyzed import hot_reload

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for name in ("main.py", "cards.py"):
            shutil.copy(HERE / "hot_reload" / name, tmp / name)
        sys.path.insert(0, str(tmp))
        try:
            demo = importlib.import_module("main")
            app = demo.Dashboard()
            app.clicks = 3
            app.screenshot(OUT / "hot-reload-before.png", scale=scale)

            reloader = hot_reload.Reloader(app)
            cards, main = tmp / "cards.py", tmp / "main.py"

            def edit(path, old, new):
                path.write_text(path.read_text().replace(old, new))
                stamp = time.time() + 5
                os.utime(path, (stamp, stamp))
                reloader.reload([path])

            edit(cards, 'ACCENT = "#61afef"', 'ACCENT = "#98c379"')
            edit(main, '"Edit me and save"', '"Saved, still 3 clicks"')
            app.screenshot(OUT / "hot-reload-after.png", scale=scale)

            edit(main, "self.clicks += 1", "self.clicks += 1)")
            app.screenshot(OUT / "hot-reload-error.png", scale=scale)
            reloader.stop()
        finally:
            sys.path.remove(str(tmp))
            for name in ("main", "cards"):
                sys.modules.pop(name, None)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    scale = 1.5

    dark = workspace(pz.themes.ONE_DARK, ["src/app.rs", "python/pyzed/ui/overlays.py"], "src/render.rs",
                     expanded={"src", "python", "python/pyzed", "examples"})
    dark.dirty.add("python/pyzed/ui/overlays.py")
    dark.cursor = (28, 14)
    dark.screenshot(OUT / "zed-one-dark.png", scale=scale)

    dark.palette, dark.query = "commands", "toggle"
    dark.screenshot(OUT / "zed-command-palette.png", scale=scale)

    light = workspace(pz.themes.ONE_LIGHT, ["src/app.rs", "examples/gallery.py"], "python/pyzed/ui/overlays.py",
                      expanded={"python", "python/pyzed", "python/pyzed/ui"}, show_bottom=True, show_right=True)
    light.cursor = (14, 5)
    light.screenshot(OUT / "zed-one-light.png", scale=scale)

    finder = Zed(str(ROOT), status=STATUS)
    finder.theme = pz.themes.GRUVBOX_DARK
    finder.palette, finder.query = "files", "ui"
    finder.screenshot(OUT / "zed-file-finder.png", scale=scale)

    Gallery().screenshot(OUT / "components-dark.png", scale=scale)
    Gallery(pz.themes.ONE_LIGHT).screenshot(OUT / "components-light.png", scale=scale)
    Counter().screenshot(OUT / "counter.png", scale=2)
    hot_reload_shots(scale)
    print(f"wrote {len(list(OUT.glob('*.png')))} screenshots to {OUT}")


if __name__ == "__main__":
    main()
