"""Regenerates the images in docs/screenshots (rendered off-screen, no window or GPU needed).

    python examples/screenshots.py
"""

import os
import sys
import time
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
    app = designer.Designer(login, language_servers=False)
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


def designer_layout_shots(scale, folder):
    """Containers and layouts, the New form dialog, menus, settings and the debug console."""
    from pyzed.designer import new

    path = new.new_form(folder / "shell.pzform", template="sidebar", title="Shell", overwrite=True)
    app = designer.Designer(path, language_servers=False)
    app.doc.select("content")
    app._selection_changed()
    app.screenshot(OUT / "designer-layout.png", size=(1440, 900), scale=scale)

    app.doc.select(None)
    app._selection_changed()
    app.toggle_app_menu("view")
    app.screenshot(OUT / "designer-menu.png", size=(1440, 900), scale=scale)
    app.toggle_app_menu("view")

    here = os.getcwd()
    os.chdir(folder)  # the dialog shows the folder relative to the current one
    try:
        app.new()
        app.set_new("template", "login")
        app.screenshot(OUT / "designer-new.png", size=(1440, 900), scale=scale)
    finally:
        os.chdir(here)
    app.close_dialog()

    app.open_settings()
    app.screenshot(OUT / "designer-settings.png", size=(1440, 900), scale=scale)
    app.close_dialog()

    log = app.console.log
    log.write("info", "▶ shell started")
    log.write("event", "nav1.click → nav1_click()")
    log.write("stdout", "Opening Home")
    log.write("event", "nav2.click → nav2_click()")
    log.write("error", "Traceback (most recent call last):\n  File \"shell.py\", line 9, in nav2_click\n"
                       "    projects[0].open()\nIndexError: list index out of range")
    app.show_panel("console")
    app.screenshot(OUT / "designer-console.png", size=(1440, 900), scale=scale)


def component_designer_shots(scale):
    """The designer's component mode on examples/designer/components (Rating inside ProfileCard)."""
    from pyzed.designer import scene_panel

    folder = HERE / "designer" / "components"
    cwd = Path.cwd()
    os.chdir(folder)  # the designer discovers the components of the current folder
    try:
        app = designer.Designer(folder / "profile_card.pzcomp", language_servers=False)
        app.screenshot(OUT / "designer-component.png", size=(1440, 900), scale=scale)

        app.select_from_outline("headline")
        app.screenshot(OUT / "designer-component-bindings.png", size=(1440, 900), scale=scale)

        rating = designer.Designer(folder / "rating.pzcomp", language_servers=False)
        scene_panel.open_method(rating, "pick")
        rating.screenshot(OUT / "designer-component-code.png", size=(1440, 900), scale=scale)

        designer.open_form(folder / "reviews.pzform").screenshot(OUT / "designer-component-run.png", scale=2)
        narrow = designer.open_form(folder / "reviews.pzform")
        narrow.window_size = (440, 240)  # the cards shrink with the window
        narrow.screenshot(OUT / "designer-component-responsive.png", size=(440, 240), scale=2)

        tabs = designer.Designer(folder / "reviews.pzform", language_servers=False)
        tabs.toggle_members("ada")
        tabs.screenshot(OUT / "designer-component-outline.png", size=(1440, 900), scale=scale)
        tabs.open_default_event("ada")  # double-click: the component opens in its own tab
        tabs.toasts.clear()
        tabs.screenshot(OUT / "designer-component-tabs.png", size=(1440, 900), scale=scale)
        tabs.__dict__["_scene_open"] = {"properties", "methods"}
        tabs.screenshot(OUT / "designer-component-members.png", size=(1440, 1100), scale=scale)

        team = designer.Designer(folder / "team_card.pzcomp", language_servers=False)
        team.screenshot(OUT / "designer-component-inherit.png", size=(1440, 900), scale=scale)
        team.new_component()
        team.set_new("name", "compact card")
        team.set_new("extends", str(folder / "profile_card.pzcomp"))
        team.screenshot(OUT / "designer-component-new.png", size=(1440, 900), scale=scale)

        preview = scene_panel.ComponentPreview(scene_panel.compile_class(rating.doc))
        preview.log = ["10:42:05  mount  None", "10:42:07  change  3"]

        class Preview(pz.App):
            size = preview.size

            def view(self):
                return preview.view()

        Preview().screenshot(OUT / "designer-component-preview.png", scale=2)
    finally:
        os.chdir(cwd)


PROJECT_TOML = """[project]
name = "shop"
version = "0.1.0"
dependencies = ["httpx>=0.28", "pyzed-ui>=0.4"]

[dependency-groups]
dev = ["ruff>=0.17", "ty>=0.0.89"]

[tool.pyzed]
ui = "ui"
main = "ui/main.pzform"
"""


def project_shot(scale):
    """The designer's Project tab on a sample uv project (no uv or network needed)."""
    import tempfile

    from pyzed import project

    cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "shop"
        (root / "ui").mkdir(parents=True)
        (root / "pyproject.toml").write_text(PROJECT_TOML)
        (root / "uv.lock").write_text("".join(
            f'[[package]]\nname = "{n}"\nversion = "{v}"\n\n'
            for n, v in [("httpx", "0.28.1"), ("pyzed-ui", "0.4.0"), ("ruff", "0.17.1"), ("ty", "0.0.89")]))
        shop = project.Project.open(root)
        project._write_main_form(shop, "Shop")
        (root / "ui" / "cart.pzform").write_text((root / "ui" / "main.pzform").read_text())
        app = designer.Designer(shop.main_form)
        app.left_tab = "project"
        p = app.projects
        p.branch = "main"
        p.tools = {n: project.Tool(n, n, v) for n, v in
                   [("uv", "0.11.3"), ("git", "2.43.0"), ("ruff", "0.17.1"), ("ty", "0.0.89")]}
        p.latest = {"ruff": "0.18.0"}
        p.last = project.Result(["ruff", "check"], 0, "All checks passed!")
        app.screenshot(OUT / "designer-project.png", size=(1440, 900), scale=scale)
        os.chdir(cwd)  # opening a project makes its folder the current one


def _wait(predicate, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not predicate():
        time.sleep(0.05)


def code_editor_shots(scale):
    """The designer's code editor: completion with docs, diagnostics and code lens, settings.

    Uses the real ty and ruff servers (``uv add --dev ty ruff``), like the designer does.
    """
    login = HERE / "designer" / "login.pzform"
    app = designer.Designer(login)
    app.assist.settings = designer.EditorSettings(show_whitespace=False)
    app.doc.code = "import re\n\n" + app.doc.code
    app.open_default_event("sign_in")
    intel = app.assist.intel
    _wait(lambda: all(s.ready for s in intel.servers.values()))

    def type_code(buffer):
        lines = buffer.split("\n")
        app.set_code_buffer(buffer[:-1])
        app.set_code_cursor(len(lines), len(lines[-1]))
        app.set_code_buffer(buffer)
        app.set_code_cursor(len(lines), len(lines[-1]) + 1)

    head = (
        'def sign_in_click(form, event):\n'
        '    """Checks the address and starts signing in."""\n'
        '    email = form.email.text.strip()\n'
    )
    type_code(head + "    if not re.f")
    _wait(lambda: app.assist.completion is not None and not app.assist.completion.loading)
    app.screenshot(OUT / "designer-completion.png", size=(1440, 900), scale=scale)

    app.assist.close_completion()
    type_code(head + "    form.")
    app.screenshot(OUT / "designer-completion-form.png", size=(1440, 900), scale=scale)

    app.assist.close_completion()
    buffer = head + (
        '    if not re.fullmatch(r"[^@]+@[^@]+", email):\n'
        '        form.status.text = "Enter a valid email address."\n'
        '        return form.email.focus()\n'
        '    form.status.text = f"Welcome, {emial}"\n'
        '    form.sign_in.enabled = False\n'
        '    form.ticker.running = True\n'
    )
    app.set_code_buffer(buffer)
    _wait(lambda: any("emial" in d.message for d in app.assist.diagnostics()))
    intel.refresh_lenses(app.doc.form)
    _wait(lambda: all(lens.parts and "reference" in lens.parts[0] for lens in intel.lenses), 5)
    app.screenshot(OUT / "designer-diagnostics.png", size=(1440, 900), scale=scale)

    # The whole file with two handlers folded and the minimap.
    app.edit_whole_file()
    lines = app.editing[1].split("\n")
    folded = [n for n, line in enumerate(lines, 1) if line.startswith(("def sign_in_click", "def ticker_tick"))]
    app.on_start = lambda: pz.Command.batch([pz.Command.fold_line(app.editor_id, n) for n in folded])
    app.screenshot(OUT / "designer-code-folding.png", size=(1440, 900), scale=scale)
    del app.on_start

    app.assist.settings = designer.EditorSettings(show_whitespace=True)
    app.open_editor_settings()
    app.screenshot(OUT / "designer-editor-settings.png", size=(1440, 900), scale=scale)
    app.assist.shutdown()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    # Logical sizes stay the same; scale 2 renders sharp HiDPI images for the docs.
    scale = 2

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
    designer_shots(scale)
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        designer_layout_shots(scale, Path(tmp))
    component_designer_shots(scale)
    project_shot(scale)
    code_editor_shots(scale)
    print(f"wrote {len(list(OUT.glob('*.png')))} screenshots to {OUT}")


if __name__ == "__main__":
    main()
