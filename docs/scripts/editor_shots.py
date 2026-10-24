"""Screenshots for the Pyzed Design manual (docs/src/content/docs/editor), rendered off-screen.

    python docs/scripts/editor_shots.py            # every shot, at 2x
    python docs/scripts/editor_shots.py palette    # only the shots whose name contains "palette"

They are written to docs/screenshots/editor-*.png. The designer runs with a throwaway settings
folder, so your own preferences (theme, docks, recent files) never leak into the images.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "screenshots"
EXAMPLES = ROOT / "examples" / "designer"
SIZE = (1440, 900)
SCALE = 2

os.environ["PYZED_CONFIG_DIR"] = tempfile.mkdtemp(prefix="pyzed-shots-")

import pyzed as pz  # noqa: E402
from pyzed import designer  # noqa: E402

pz.ui.base.KEY_STYLE = "words"

SHOTS = {}


def shot(fn):
    SHOTS[fn.__name__] = fn
    return fn


def login():
    app = designer.Designer(EXAMPLES / "login.pzform", language_servers=False)
    app.toasts.clear()
    return app


def save(app, name, size=SIZE):
    app.toasts.clear()
    app.screenshot(OUT / f"editor-{name}.png", size=size, scale=SCALE)
    print("wrote", f"editor-{name}.png")


@shot
def palette():
    app = login()
    app.open_palette()
    app.set_picker_query("align")
    app.set_picker_query("")
    save(app, "palette")


@shot
def add_control():
    app = login()
    app.open_add_child("card")
    app.set_picker_query("box")
    save(app, "add-control")


@shot
def context_menu():
    app = login()
    app.window_pointer = (720, 470)
    app.open_context_menu("sign_in")
    save(app, "context-menu")


@shot
def file_menu():
    app = login()
    for name in ("settings.pzform", "orders.pzform", "login.pzform"):
        app.prefs.remember(EXAMPLES / name)
    app.toggle_app_menu("file")
    save(app, "file-menu")


@shot
def shortcuts():
    app = login()
    app.open_dialog_named("shortcuts")
    save(app, "shortcuts")


@shot
def events():
    app = login()
    app.doc.select("password")
    app._selection_changed()
    app.right_tab = "events"
    save(app, "events")


@shot
def dock_menu():
    app = login()
    app.doc.select("sign_in")
    app._selection_changed()
    app.open_dock_menu("right")
    save(app, "dock-menu")


@shot
def guides():
    app = login()
    app.doc.select("remember")
    app._selection_changed()
    control = app.doc.form["remember"]
    start = (control.x + 10, control.y + 8)
    app.pointer = start
    app.view_pointer = (0.0, 0.0)
    app.press_control("remember")
    best = None
    for dx in range(12, 160, 2):
        for dy in (0,):
            app.view_pointer = (float(dx), float(dy))
            app._drag_to()
            if app.guides and any(g[2] - g[0] <= 1 for g in app.guides):
                best = (dx, dy)
                break
        if best:
            break
    if best is None:
        app.view_pointer = (60.0, 0.0)
    app.pointer = (start[0] + app.view_pointer[0], start[1] + app.view_pointer[1])
    app._drag_to()
    save(app, "guides")
    app.cancel_drag()


@shot
def placing():
    app = login()
    app.doc.select(None)
    app._selection_changed()
    app.pick_tool("button")()
    app.pointer = (232.0, 258.0)
    app.view_pointer = (0.0, 0.0)
    app.press_empty()
    app.view_pointer = (136.0, 24.0)
    app.pointer = (368.0, 282.0)
    app._drag_to()
    save(app, "placing")


def lists_form():
    doc = designer.Document(designer.Form(name="inbox", title="Inbox", width=640, height=420))
    doc.add("list_box", 16, 16, 200, 180)
    doc.form["list_box1"].props["items"] = ["Inbox", "Drafts", "Sent", "Archive"]
    doc.add("table", 232, 16, 392, 180)
    doc.form["table1"].props["data"] = "Name, Role, Stars\nAda, Mathematician, 5\nGrace, Admiral, 5\nLinus, Engineer, 4"
    return doc


@shot
def list_editors():
    app = designer.Designer(None, language_servers=False)
    app.doc = lists_form()
    app.doc.select("list_box1")
    app._selection_changed()
    save(app, "items")
    app.doc.select("table1")
    app._selection_changed()
    app.collapsed_sections |= {"Style"}
    save(app, "rows")


@shot
def motion():
    app = login()
    app.doc.select("sign_in")
    app._selection_changed()
    app.set_style_value("sign_in", "glow", ["accent", 16])
    app.add_animation("sign_in", "mount")
    app.add_animation("sign_in", "hover")
    app.set_animation("sign_in", 1, "duration", 180.0)
    app.add_animation("sign_in", "press")
    app.add_animation("sign_in", "manual")
    app.set_animation("sign_in", 3, "preset", "tada")
    app.stop_preview("sign_in")
    app.collapsed_sections |= {"Style", "Behavior", "Position", "Button", "Appearance", "Text"}
    save(app, "motion")


@shot
def outline():
    app = login()
    app.doc.form["subtitle"].visible = False
    app.doc.form["remember"].locked = True
    app.doc.select("remember")
    app._selection_changed()
    save(app, "outline")


@shot
def new_project():
    app = login()
    app.projects.new_folder = "/home/ada/projects"
    app.projects.new_name = "shop"
    app.dialog = "project:new"
    save(app, "new-project")


@shot
def open_project():
    folder = Path(tempfile.mkdtemp(prefix="pyzed-shots-projects-")) / "projects"
    for name in ("shop", "weather", "notes"):
        (folder / name).mkdir(parents=True)
        (folder / name / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n')
    for name in ("archive", "scratch"):
        (folder / name).mkdir()
    app = login()
    app.projects.show("open")()
    app.projects.browser.go(folder)
    save(app, "open-project")


@shot
def project_picker():
    folder = Path(tempfile.mkdtemp(prefix="pyzed-shots-picker-")) / "projects"
    for name in ("weather", "notes", "shop"):
        (folder / name / "ui").mkdir(parents=True)
        (folder / name / ".venv").mkdir()
        (folder / name / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
                                                       '[tool.pyzed]\nui = "ui"\n')
    app = login()
    for name in ("weather", "notes", "shop"):
        app.projects.open(str(folder / name))
    app.projects.close_project(folder / "weather")
    app.picker_projects.open()
    save(app, "project-picker", size=(1100, 420))


@shot
def reference():
    app = login()
    app.doc.select("sign_in")
    app._selection_changed()
    app.reference_here()
    save(app, "reference")


@shot
def reference_search():
    app = login()
    app.open_reference("pyzed.ui.tab_bar")
    app.help.set_query("tab")
    save(app, "reference-search")


def bound_login(app):
    """The login form with its inputs bound to form.data and validated, as the Data section docs show."""
    form = app.doc.form
    form["email"].bind = "email"
    form["email"].rules = {"required": True, "pattern": r"[^@]+@[^@]+\.\w+", "message": "Enter a valid email"}
    form["password"].bind = "password"
    form["password"].rules = {"required": True, "min_length": 8}
    form["remember"].bind = "remember"
    form["status"].bind = 'f"Signing in as {email}" if email else ""'
    return app


@shot
def icon_picker():
    app = login()
    app.doc.select("sign_in")
    app._selection_changed()
    app.open_icon_picker("log-in", lambda name: app.doc.set_prop("sign_in", "icon", name))
    save(app, "icon-picker")


@shot
def anchors():
    from pyzed.designer import anchor_panel, panels

    app = login()
    app.doc.select("sign_in")
    app._selection_changed()
    app.toggle_anchor_presets("sign_in")
    control = app.doc.form["sign_in"]

    class Position(pz.App):
        def view(self):
            t = app.theme_obj
            rows = anchor_panel.position_rows(app, control, t, panels.prop_row)
            return pz.container(pz.column(rows, spacing=4), padding=12, width="fill", height="fill", bg=t.panel)

    pz.screenshot(Position(), OUT / "editor-anchors.png", size=(380, 520))
    print("editor-anchors.png")


@shot
def data():
    app = bound_login(login())
    app.doc.select("email")
    app._selection_changed()
    save(app, "data")


@shot
def validation():
    from pyzed.designer.runtime import FormWindow

    app = bound_login(login())
    window = FormWindow(app.doc.form, path=app.doc.path)
    runtime = window.runtime
    runtime.ctx.on(runtime.form["email"], "change", "text")("ada@")
    runtime.validate()
    form = app.doc.form
    pz.screenshot(_Host(window), OUT / "editor-validation.png", size=(int(form.width), int(form.height)),
                  scale=SCALE)
    print("wrote editor-validation.png")


class _Host(pz.App):
    """Shows a form window's view as an app, for an off-screen screenshot."""

    def __init__(self, window=None):
        self.window_ = window
        self.theme = window.runtime.theme if window else None

    def view(self):
        return self.window_.view()


@shot
def preview():
    from pyzed import i18n

    i18n.add("es", {"login": {"title": "Iniciar sesión", "welcome": "Hola de nuevo", "email": "Correo",
                              "password": "Contraseña", "remember": "Recordarme", "sign_in": "Entrar"}})
    app = login()
    form = app.doc.form
    form.title = "@login.title"
    for name, key in (("title", "welcome"), ("user_label", "email"), ("password_label", "password"),
                      ("remember", "remember"), ("sign_in", "sign_in")):
        form[name].props["text"] = f"@login.{key}"
    app.set_preview("theme", "Pyzed Light")
    app.set_preview("language", "es")
    app.open_preview_picker("language")
    save(app, "preview")


@shot
def about():
    app = login()
    app.open_dialog_named("about")
    save(app, "about")


if __name__ == "__main__":
    wanted = sys.argv[1:]
    for name, fn in SHOTS.items():
        if not wanted or any(w in name for w in wanted):
            fn()
