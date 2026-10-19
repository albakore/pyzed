"""A window with a frame drawn by Pyzed: title bar, menus on the left like Zed and the window buttons.

Drag the title bar to move the window, double click it to maximize, and drag the borders to resize.
The body shows the title bar of every platform style.

    python examples/window_frame.py            # this system's buttons
    python examples/window_frame.py windows    # Windows buttons everywhere
"""

import sys

import pyzed as pz
from pyzed import ui


class Notes(pz.App):
    title = "Notes"
    size = (760, 520)
    min_size = (420, 300)
    # "custom" uses this system's buttons; a platform name draws that platform's everywhere
    frame = "custom"

    def __init__(self):
        self.log = "Pick something from the menus."

    def did(self, what):
        self.log = what

    def frame_menus(self):
        return [
            ui.Menu("File", [
                ui.MenuItem("New note", lambda: self.did("New note"), icon="file-plus", keys="ctrl-n"),
                ui.MenuItem("Open…", lambda: self.did("Open"), icon="folder-open", keys="ctrl-o"),
                ui.SEPARATOR,
                ui.MenuItem("Quit", self.close, keys="ctrl-q"),
            ]),
            ui.Menu("Edit", [
                ui.MenuItem("Undo", lambda: self.did("Undo"), keys="ctrl-z"),
                ui.MenuItem("Redo", lambda: self.did("Redo"), keys="ctrl-shift-z"),
            ]),
            ui.Menu("View", [
                ui.MenuItem("Maximize", self.toggle_maximize, icon="maximize-2"),
                ui.MenuItem("Minimize", self.minimize, icon="minimize-2"),
            ]),
        ]

    def view(self):
        bars = [
            pz.column([ui.label(ui.frame.PLATFORM_LABELS[style], size="sm", color="text_muted"),
                       ui.window_title_bar("Notes", style=style)], spacing=4)
            for style in ui.frame.PLATFORMS
        ]
        return pz.container(
            pz.column([ui.label(self.log), *bars], spacing=12),
            padding=20, width="fill", height="fill",
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        Notes.frame = sys.argv[1]
    pz.run(Notes)
