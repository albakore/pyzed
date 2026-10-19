"""The scenes of the visual regression tests: small apps rendered off-screen and compared with
the reference images in ``tests/visual/references``.

Add a scene with ``@scene(name, size=(w, h))`` on a function returning a ``pz.App``; then create its
reference with ``pytest tests/test_visual.py --update-snapshots -k <name>`` and commit the PNG.
"""

from __future__ import annotations

from typing import Callable, Dict, NamedTuple, Tuple

import pyzed as pz
from pyzed import ui


class Scene(NamedTuple):
    build: Callable[[], pz.App]
    size: Tuple[int, int]


SCENES: Dict[str, Scene] = {}


def scene(name: str, *, size: Tuple[int, int] = (640, 400)):
    def register(build):
        SCENES[name] = Scene(build, size)
        return build

    return register


def _app(view, theme=None) -> pz.App:
    class Shot(pz.App):
        def view(self):
            try:
                return view()
            except Exception as error:
                self.errors.append(error)
                raise

    app = Shot()
    app.errors = []  # exceptions raised by view(), so an error screen never becomes a reference
    if theme is not None:
        app.theme = theme
    return app


FILES = ["README.md", "pyproject.toml", "src/app.rs", "src/render.rs", "python/pyzed/__init__.py",
         "python/pyzed/ui/workspace.py"]
CODE = 'def greet(name: str) -> str:\n    """Says hello."""\n    return f"Hello, {name}!"\n\n\nprint(greet("Pyzed"))\n'


def _workspace(*, bottom=True):
    tabs = [ui.Tab.for_file("python/pyzed/__init__.py"), ui.Tab.for_file("src/app.rs", dirty=True, status="modified"),
            ui.Tab.for_file("README.md", preview=True)]
    center = pz.column([
        ui.tab_bar(tabs, "python/pyzed/__init__.py", on_close=lambda _: None,
                   start=[ui.icon_button("arrow-left", size="sm"), ui.icon_button("arrow-right", size="sm")],
                   end=[ui.icon_button("plus", size="sm")]),
        ui.toolbar([ui.breadcrumbs(["python", "pyzed", ("file-code", "__init__.py")])],
                   [ui.icon_button("search", size="sm")]),
        ui.editor("visual", CODE, path="greet.py", markers={2: "modified", 6: "created"}, height=180),
    ])
    nodes = ui.TreeNode.from_paths(FILES, {"src/app.rs": "modified", "python/pyzed/ui/workspace.py": "created"})
    return ui.workspace(
        center,
        title_bar=ui.title_bar([ui.title_button("pyzed", chevron=True), ui.title_button("main", icon="git-branch",
                                                                                       muted=True)],
                               [ui.avatar("PZ")]),
        left=pz.column([ui.panel_header("Project", icon="folder"),
                        ui.tree(nodes, expanded={"src", "python", "python/pyzed"})]),
        bottom=ui.terminal("$ pytest -q\n\x1b[32m42 passed\x1b[0m in 1.2s") if bottom else None,
        left_width=180,
        bottom_height=80,
        status_bar=ui.status_bar([ui.status_item("main", icon="git-branch"), ui.status_item("0", icon="circle-x")],
                                 [ui.status_item("Ln 3, Col 9"), ui.status_item("Python")]),
    )


@scene("workspace-dark", size=(720, 440))
def workspace_dark():
    return _app(_workspace)


@scene("workspace-light", size=(720, 440))
def workspace_light():
    return _app(_workspace, pz.themes.ONE_LIGHT)


@scene("command-palette", size=(720, 440))
def command_palette():
    commands = [ui.PaletteItem("editor: save", keys="ctrl-s", icon="save"),
                ui.PaletteItem("workspace: save all", keys="ctrl-alt-s"),
                ui.PaletteItem("file finder: toggle", keys="ctrl-p", detail="files"),
                ui.PaletteItem("zed: quit", keys="ctrl-q")]
    return _app(lambda: ui.layer(_workspace(bottom=False), ui.command_palette("sav", lambda q: None, commands),
                                 on_dismiss="close", backdrop="#00000040"))


@scene("modal-and-toasts", size=(640, 400))
def modal_and_toasts():
    def view():
        dialog = ui.modal(
            pz.column([ui.muted("Unsaved changes in 2 files will be lost."),
                       ui.checkbox(True, None, label="Don't ask again")], spacing=10),
            title="Close project?",
            on_close="close",
            footer=[ui.button("Cancel", None), ui.button("Close", None, variant="filled", tint="error")],
        )
        notes = [ui.toast("Saved", "All files were written.", kind="success", on_dismiss="x"),
                 ui.toast("Update available", "Pyzed 1.1.0 is ready.", actions=[ui.button("Restart", None, size="sm")])]
        base = pz.container(ui.heading("Editor"), padding=16, width="fill", height="fill")
        return ui.toasts(ui.layer(base, dialog, backdrop="#00000060", align_y="center"), notes)

    return _app(view)


@scene("controls", size=(640, 400))
def controls():
    def view():
        return pz.container(pz.column([
            pz.row([ui.button("Default", None), ui.button("Filled", None, variant="filled"),
                    ui.button("Outlined", None, variant="outline", icon="plus"),
                    ui.button("Danger", None, tint="error"), ui.button("Disabled", None, disabled=True)], spacing=8),
            pz.row([ui.badge("new", tint="accent"), ui.badge("warning", tint="warning"), ui.count_badge(12),
                    ui.chip("python", selected=True), ui.chip("rust", on_remove=lambda: None),
                    ui.kbd("ctrl-shift-p"), ui.diff_stat(12, 3)], spacing=8, align="center"),
            pz.row([ui.input("", None, placeholder="Search…", icon="search", width=200),
                    ui.select(["One Dark", "One Light"], "One Dark", None, width=160)], spacing=8),
            pz.row([ui.checkbox(True, None, label="Format on save"), ui.switch(True, None, label="Vim mode"),
                    ui.segmented(["Code", "Design"], "Code", None)], spacing=16, align="center"),
            pz.row([ui.slider(40, None, width=200), ui.progress(0.65, width=200)], spacing=16, align="center"),
            ui.callout("Indexing", "The project is being indexed.", tint="info"),
        ], spacing=14), padding=16, width="fill", height="fill")

    return _app(view)


@scene("data", size=(640, 400))
def data():
    def view():
        rows = [{"name": "workspace.py", "lines": 251, "status": "modified"},
                {"name": "navigation.py", "lines": 190, "status": "clean"},
                {"name": "overlays.py", "lines": 299, "status": "created"}]
        return pz.container(pz.column([
            pz.row([ui.stat("Tests", "1,204", delta=38), ui.stat("Coverage", "87%", delta=2)], spacing=12),
            ui.table(["name", "lines", "status"], rows, selected=rows[0], height=150),
            ui.list_header("Recent"),
            ui.list_item("examples/gallery.py", None, icon="file-code", selected=True),
            ui.list_item("examples/todo.py", None, icon="file-code"),
        ], spacing=10), padding=16, width="fill", height="fill")

    return _app(view)


@scene("designer", size=(1280, 800))
def designer_window():
    from pathlib import Path

    from pyzed import designer

    login = Path(__file__).resolve().parents[2] / "examples" / "designer" / "login.pzform"
    app = designer.Designer(login, language_servers=False)
    app.doc.select("sign_in")
    app._selection_changed()
    return app
