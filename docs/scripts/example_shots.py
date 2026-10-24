"""Renders the example screenshots (docs/src/assets: tutorials, examples, showcase, games, contributing).

    python docs/scripts/example_shots.py              # all of them
    python docs/scripts/example_shots.py styling      # only some

They are drawn off-screen with ``App.screenshot`` (no window or GPU). The showcase shots use
``pz.shader``, which needs a GPU: on Linux without one, install Mesa's software Vulkan driver
(``mesa-vulkan-drivers``) so they render the shaders instead of their fallback colors.
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "src" / "assets"
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "examples" / "tutorial"))
sys.path.insert(0, str(ROOT / "examples" / "showcase"))
sys.path.insert(0, str(ROOT / "examples" / "games"))

import pyzed as pz  # noqa: E402
from pyzed import ui  # noqa: E402

ui.base.KEY_STYLE = "words"


def frame(title, view, size, theme):
    """A fake window: title bar plus the window's own view, so several windows fit in one image."""
    t = pz.themes.get(theme) if isinstance(theme, str) else theme
    with t:  # components read the window's theme, as they do when Pyzed renders each window
        body = view()
        return pz.container(
            pz.column([
                pz.container(pz.row([ui.label(title, size="sm"), pz.hspace(), pz.icon("x", size=12, color=t.icon)], align="center"),
                             padding=(6, 10), width="fill", bg=t.title_bar),
                pz.container(body, width="fill", height="fill"),
            ]),
            width=size[0], height=size[1], radius=8, clip=True, border_color=t.border, border_width=1,
        )


class Windows(pz.App):
    """examples/multi_window.py: the main window plus two Note windows."""

    def __init__(self):
        from multi_window import Main, Note

        self.main = Main()
        self.main.clicks = 3
        self.notes = []
        for n, theme in [(1, "Ayu Mirage"), (2, "Gruvbox Light")]:
            note = Note(n, theme)
            note.app = self.main
            self.notes.append(note)
        self.notes[0].text = "Hello from another window"
        self.main.windows, self.main.opened = self.notes, 2

    def view(self):
        main = frame(self.main.title, self.main.view, (420, 300), "Pyzed Dark")
        notes = [frame(n.title, n.view, (360, 236), n.theme) for n in self.notes]
        return pz.container(pz.row([main, pz.column(notes, spacing=16)], spacing=16),
                            padding=20, width="fill", height="fill", bg="#1b1d22")


def app(module, cls, setup=None, *args):
    def make():
        mod = __import__(module)
        instance = getattr(mod, cls)(*args)
        if setup:
            setup(instance)
        return instance
    return make


def components_setup(app):
    app.rating = 4
    app.tags = ["python", "rust", "iced"]
    app.note = (40, 60)
    app.pinned = True
    app.log = ["double_click", "drag_end", "drag +12, +4", "drag +20, +8", "drag_start", "focus"]


def layout_setup(app):
    app.layout = {"positions": {"outline": "right"}, "sizes": {"left": 220, "right": 260, "bottom": 150},
                  "active": {"right": "outline"}, "hidden": []}
    app.log = ["layout → outline: right", "Drag a tab onto a drop zone, or a panel edge to resize it."]


def dialogs_setup(app):
    app.dialog = "confirm"


def life_setup(app):
    random.seed(4)
    app.randomize()
    for _ in range(30):
        app.tick()


def timeline_setup(app):
    app.player.owner = app
    app.player.pause()
    app.player.seek(app.player.length)
    app.message = "New record! Press Next to continue"


def snake_setup(app):
    path = [(6, 4), (6, 5), (6, 6), (6, 7), (6, 8), (6, 9), (6, 10), (7, 10), (8, 10), (9, 10), (10, 10),
            (11, 10), (12, 10), (12, 9), (12, 8)]
    app.body = list(reversed(path))
    app.direction = (0, -1)
    app.food = (12, 4)
    app.score, app.best = 12, 18


def snake_over_setup(app):
    snake_setup(app)
    app.over = True


def breakout_setup(app):
    """Plays a few seconds with the paddle following the ball, then stops mid-flight."""
    app.launch()
    for frame in range(60 * 9):
        app.paddle_x = app.ball_x + 18
        app.tick(1 / 60)
        if app.stuck:
            app.launch()
        if frame > 60 * 8 and app.vy < 0 and app.ball_y < 340 and app.combo >= 1:
            break


def invaders_setup(app):
    app.started = True
    app.new_game()
    app.banner = 0
    for frame in range(60 * 4):
        if frame % 9 == 0:
            app.fire()
        app.x = 380 + 140 * __import__("math").sin(frame / 50)
        app.hurt = 1  # keep the ship safe while the shot is set up
        app.tick(1 / 60)
    app.hurt = 0
    app.triple = 6
    app.powerups.append([520, 300])


def window_frame_setup(app):
    app.frame = "gnome"  # the same picture on every desktop
    app.log = "New note"


def downloads_setup(app):
    """One file done, one half-way, and the "downloaded" toast."""
    app.progress = {"iced-0.14.tar.gz": 1.0, "zed-themes.json": 0.42}
    app.toasts = [("done", "iced-0.14.tar.gz descargado", None, "success")]


def mini_editor_setup(app):
    app.expanded = {"examples"}
    app.open_file("examples/counter.py")
    app.open_file("examples/todo.py")
    app.cursor = (12, 5)
    app.root = app.root.with_name("pyzed")  # the checkout's folder name (a worktree, a clone) is not shown


def mini_editor_palette_setup(app):
    mini_editor_setup(app)
    app.palette_open, app.query = True, "tog"


def pomodoro_setup(app):
    app.running, app.left, app.done = True, 17 * 60 + 42, 2


def invaders_title_setup(app):
    for _ in range(30):
        app.tick(1 / 60)


def contacts_app():
    """The contacts tutorial on a throwaway database with four people in it."""
    import tempfile

    import contacts_backend

    repo = contacts_backend.ContactsRepository(Path(tempfile.mkdtemp()) / "contacts.db", delay=0)
    repo.add("Grace Hopper", "grace@example.com")
    repo.add("Katherine Johnson", "katherine@example.com")
    instance = contacts_backend.Contacts(repo)
    instance.loaded(repo.search())
    return instance


def dodge_setup(app):
    for _ in range(150):
        app.tick(1 / 60)


def feedback_errors_setup(app):
    app.email = "ada@"
    app.submit()


def feedback_confirm_setup(app):
    app.name, app.email, app.password = "Ada", "ada@example.com", "analytical"
    app.submit()


def books_setup(app):
    import lists_tables

    app.selected = next(b for b in lists_tables.BOOKS if b["title"] == "Neuromancer")


def settings_page_setup(app):
    app.on_key("ctrl-3")
    app.tab = "Notifications"


def themes_light_setup(app):
    app.choose("base")("Pyzed Light")
    app.choose("accent")("Purple")


def themes_sunset_setup(app):
    app.choose("base")("Sunset")


def context_menu_setup(app):
    app.log += ["Copy", "Paste"]
    app.menu_at = (220, 150)


def ticker_setup(app):
    """A minute of made-up prices, the same on every run, with the feed itself switched off."""
    rng = random.Random(7)
    for symbol in app.history:
        price = rng.uniform(80, 180)
        for _ in range(60):
            price *= 1 + rng.gauss(0, 0.01)
            app.history[symbol].append(price)
    app.subscriptions = lambda: []


def gallery_app():
    import gallery

    return gallery.Gallery(pz.themes.PYZED_DARK)


def form(name, setup=None):
    """A tutorial form (examples/tutorial/designer) run as the reader runs it, ``setup(runtime)`` applied."""
    def make():
        from pyzed.designer.runtime import open_form

        instance = open_form(ROOT / "examples" / "tutorial" / "designer" / f"{name}.pzform")
        instance.runtime.load()
        if setup:
            setup(instance.runtime)
        return instance
    return make


def typed(rt, values):
    for control, prop, value in values:
        rt.ctx.on(rt.form[control], "change", prop)(value)


def hello_setup(rt):
    typed(rt, [("your_name", "text", "Ada")])
    rt.dispatch(rt.form["greet"], "click")


def contact_setup(rt):
    typed(rt, [("your_name", "text", "Ada Lovelace"), ("email", "text", "ada@example.com"),
               ("message", "text", "Can Pyzed draw a whole app without code?")])
    rt.dispatch(rt.form["send"], "click")


def signup_setup(rt):
    typed(rt, [("your_name", "text", "Ada"), ("email", "text", "ada@example"), ("password", "text", "abc")])
    rt.dispatch(rt.form["create"], "click")


def rating_shots():
    """The two images of contributing/adding-components (the code on that page, in a temporary folder)."""
    import tempfile

    sys.path.insert(0, str(ROOT / "examples" / "designer" / "components"))
    import rating  # noqa: F401 - registers the component

    from pyzed import designer
    from pyzed.designer import Document

    folder = Path(tempfile.mkdtemp())
    doc = Document(designer.Form(name="review", title="Review", width=360, height=150))
    doc.add("label", 16, 16, 320, 24).props["text"] = "How was your stay?"
    doc.add("rating", 16, 48)
    doc.add("label", 16, 88, 320, 24)
    doc.rename("label2", "status")
    handler = doc.wire("rating1", "change")
    doc.set_handler_source(handler, (
        "def rating1_change(form, event):\n"
        '    form.status.text = f"You gave it {event.value} stars"\n'))
    path = doc.save(folder / "review.pzform")
    out = ASSETS / "contributing"
    app = designer.open_form(path)
    rt = app.runtime
    rt.ctx.on(rt.form["rating1"], "change", "value")(4)
    app.screenshot(out / "rating-run.png", scale=2)
    os.environ["PYZED_TRUST_ALL"] = "1"  # a temporary folder would open in restricted mode
    editor = designer.Designer(path)
    editor.doc.select("rating1")
    editor.screenshot(out / "rating-designer.png", size=(1280, 760), scale=2)
    print("wrote docs/src/assets/contributing/rating-run.png, rating-designer.png")


SHOTS = {
    # Guide illustrations
    "tutorials/multi-window": (Windows, (820, 560)),
    "tutorials/game-of-life": (app("game_of_life", "Life", life_setup), None),
    "tutorials/styling": (app("styling", "Styling"), (1000, 400)),
    "tutorials/components": (app("components", "Demo", components_setup), None),
    "tutorials/layout": (app("layout", "LayoutDemo", layout_setup), (1100, 680)),
    "tutorials/dialogs": (app("dialogs", "DialogsDemo", dialogs_setup), (720, 420)),
    "tutorials/styles": (app("styles", "StylesDemo"), (860, 480)),
    "tutorials/color-picker": (app("color_picker", "ColorPickerDemo"), (640, 560)),
    "tutorials/animations": (app("animations", "Animations"), (980, 500)),
    "tutorials/effects": (app("effects", "Effects"), (900, 460)),
    "tutorials/timeline": (app("timeline", "Timeline", timeline_setup), (760, 560)),
    "tutorials/todo": (app("todo", "Todo"), None),
    "tutorials/downloads": (app("downloads", "Downloads", downloads_setup), None),
    "tutorials/mini-editor": (app("mini_editor", "MiniEditor", mini_editor_setup, str(ROOT)), (1100, 700)),
    "tutorials/mini-editor-palette": (app("mini_editor", "MiniEditor", mini_editor_palette_setup, str(ROOT)),
                                      (1100, 700)),
    "ai/pomodoro": (app("pomodoro", "Pomodoro", pomodoro_setup), None),
    "tutorials/window-frames": (app("window_frame", "Notes", window_frame_setup), (760, 520)),
    "showcase/hud": (app("hud", "Hud"), (1280, 720)),
    "showcase/main-menu": (app("main_menu", "MainMenu"), (1280, 720)),
    "showcase/inventory": (app("inventory", "Inventory"), (1180, 640)),
    "showcase/glass-dashboard": (app("glass_dashboard", "Dashboard"), (1180, 700)),
    "showcase/shaders": (app("shaders", "Shaders"), (1140, 720)),
    # Games (examples/games)
    "games/snake": (app("snake", "Snake", snake_setup, 2), None),
    "games/snake-over": (app("snake", "Snake", snake_over_setup, 2), None),
    "games/breakout": (app("breakout", "Breakout", breakout_setup, 3), None),
    "games/neon-invaders": (app("neon_invaders", "NeonInvaders", invaders_setup, 5), None),
    "games/neon-invaders-title": (app("neon_invaders", "NeonInvaders", invaders_title_setup, 5), None),
    # Step-by-step tutorial (examples/tutorial)
    "tutorials/step1": (app("step1_hello", "Hello"), None),
    "tutorials/step2": (app("step2_state", "Greeter"), None),
    "tutorials/step3": (app("step3_layout", "Settings"), None),
    "tutorials/step4": (app("step4_async", "Quotes"), None),
    "tutorials/step5": (app("step5_notes", "Notes"), None),
    "tutorials/layout-basics": (app("layout_basics", "Profile"), None),
    "tutorials/lists-tables": (app("lists_tables", "Library", books_setup), None),
    "tutorials/navigation": (app("navigation", "Navigation", lambda a: a.go("Inbox")), None),
    "tutorials/navigation-settings": (app("navigation", "Navigation", settings_page_setup), None),
    "tutorials/feedback-errors": (app("feedback", "Signup", feedback_errors_setup), None),
    "tutorials/feedback-confirm": (app("feedback", "Signup", feedback_confirm_setup), None),
    "tutorials/themes-light": (app("theme_switcher", "ThemeSwitcher", themes_light_setup), None),
    "tutorials/themes-sunset": (app("theme_switcher", "ThemeSwitcher", themes_sunset_setup), None),
    "tutorials/contacts-backend": (contacts_app, None),
    "tutorials/dodge": (app("dodge", "Dodge", dodge_setup, 1), None),
    "tutorials/aurora": (app("aurora_graph", "Aurora"), None),
    "tutorials/designer-hello": (form("hello", hello_setup), None),
    "tutorials/designer-contact": (form("contact", contact_setup), None),
    "tutorials/designer-signup": (form("signup", signup_setup), None),
    "tutorials/designer-welcome": (form("welcome"), None),
    # Showcase of the example apps (examples/)
    "showcase/apps/animations": (app("animations", "Animations"), None),
    "showcase/apps/context_menu": (app("context_menu", "ContextMenu", context_menu_setup), None),
    "showcase/apps/effects": (app("effects", "Effects"), None),
    "showcase/apps/gallery": (gallery_app, None),
    "showcase/apps/panes": (app("panes", "Panes"), None),
    "showcase/apps/styles": (app("styles", "StylesDemo"), None),
    "showcase/apps/websocket_stream": (app("websocket_stream", "Ticker", ticker_setup), None),
    # Examples gallery
    "examples/clock": (app("clock", "Clock"), None),
    "examples/image_viewer": (app("image_viewer", "Viewer"), None),
    "examples/markdown_viewer": (app("markdown_viewer", "MarkdownViewer"), None),
    "examples/qr_code": (app("qr_code", "QR"), None),
    "examples/stopwatch": (app("stopwatch", "Stopwatch"), None),
    "examples/todos": (app("todos", "Todos"), None),
}


def main(names):
    for name, (make, size) in SHOTS.items():
        if names and not any(n in name for n in names):
            continue
        out = ASSETS / f"{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        instance = make()
        instance.screenshot(out, size=size or getattr(instance, "size", (800, 600)), scale=2, wait=0.3)
        print(f"wrote {out.relative_to(ROOT)}")
    if not names or any(n in "contributing/rating" for n in names):
        rating_shots()


if __name__ == "__main__":
    main(sys.argv[1:])
