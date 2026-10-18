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
from pyzed import designer  # noqa: E402

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


def designer_shots(scale):
    """The visual designer and the forms it makes."""
    login = HERE / "designer" / "login.pzform"
    app = designer.Designer(login)
    app.doc.select("sign_in")
    app._selection_changed()
    app.screenshot(OUT / "designer.png", size=(1440, 900), scale=scale)

    app.open_default_event("sign_in")
    app.screenshot(OUT / "designer-code.png", size=(1440, 900), scale=scale)

    app.close_code()
    app.right_tab = "properties"
    app.doc.select(["user_label", "email", "password"])
    app._selection_changed()
    app.screenshot(OUT / "designer-align.png", size=(1440, 900), scale=scale)

    app.doc.select(None)
    app._selection_changed()
    app.doc.form.theme = "Gruvbox Light"
    app.doc.form.accent = "#b16286"
    app.theme = pz.themes.ONE_LIGHT
    app.screenshot(OUT / "designer-light.png", size=(1440, 900), scale=scale)

    designer.open_form(login).screenshot(OUT / "designer-run.png", scale=2)

    # every built-in component on one form, as the toolbox places them
    form = designer.Form(title="Components", width=760, height=560)
    x, y, row_h = 16, 16, 0
    for spec in designer.all_components():
        w, h = spec.size
        if x + w > form.width - 16:
            x, y, row_h = 16, y + row_h + 16, 0
        form.add(spec.create(spec.type, x, y))
        x += w + 16
        row_h = max(row_h, h)
    form.get("panel").props["title"] = "Panel"
    designer.FormApp(form).screenshot(OUT / "designer-components.png", scale=scale)


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
    designer_shots(1.0)
    print(f"wrote {len(list(OUT.glob('*.png')))} screenshots to {OUT}")


if __name__ == "__main__":
    main()
