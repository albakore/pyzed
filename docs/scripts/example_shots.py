"""Renders the example screenshots (docs/src/assets/tutorials and docs/src/assets/examples).

    python docs/scripts/example_shots.py              # all of them
    python docs/scripts/example_shots.py styling      # only some

They are drawn off-screen with ``App.screenshot`` (no window or GPU). The showcase shots use
``pz.shader``, which needs a GPU: on Linux without one, install Mesa's software Vulkan driver
(``mesa-vulkan-drivers``) so they render the shaders instead of their fallback colors.
"""

from __future__ import annotations

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
        main = frame(self.main.title, self.main.view, (420, 300), "One Dark")
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


def invaders_title_setup(app):
    for _ in range(30):
        app.tick(1 / 60)


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


if __name__ == "__main__":
    main(sys.argv[1:])
