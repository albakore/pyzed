"""Renders the example screenshots (docs/src/assets/tutorials and docs/src/assets/examples).

    python docs/scripts/example_shots.py              # all of them
    python docs/scripts/example_shots.py styling      # only some

They are drawn off-screen with ``App.screenshot`` (no window or GPU).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "src" / "assets"
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "examples" / "tutorial"))

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


def life_setup(app):
    random.seed(4)
    app.randomize()
    for _ in range(30):
        app.tick()


SHOTS = {
    # Guide illustrations
    "tutorials/multi-window": (Windows, (820, 560)),
    "tutorials/game-of-life": (app("game_of_life", "Life", life_setup), None),
    "tutorials/styling": (app("styling", "Styling"), (1000, 400)),
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
