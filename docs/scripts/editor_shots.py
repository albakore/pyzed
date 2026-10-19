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
def about():
    app = login()
    app.open_dialog_named("about")
    save(app, "about")


if __name__ == "__main__":
    wanted = sys.argv[1:]
    for name, fn in SHOTS.items():
        if not wanted or any(w in name for w in wanted):
            fn()
