"""Tutorial, step 3: layout, ready-made components and themes.

    python examples/tutorial/step3_layout.py
"""

import pyzed as pz
from pyzed import ui


class Settings(pz.App):
    title = "Settings"
    size = (640, 420)
    theme = "Pyzed Dark"  # any name from pz.themes.names(), a Theme, or pz.themes.auto()

    def __init__(self):
        self.font_size = 14
        self.wrap = True
        self.language = "Python"

    def view(self):
        t = self.resolved_theme()  # the Theme in use, handy for colors
        return pz.container(
            pz.column([
                pz.row([ui.heading("Settings", level=2), pz.hspace(),
                        ui.select(pz.themes.names(), t.name, lambda n: setattr(self, "theme", n), width=200)],
                       align="center"),
                ui.settings_group("Editor", [
                    ui.field("Font size", ui.number_field(self.font_size, lambda v: setattr(self, "font_size", v),
                                                          min=8, max=32)),
                    ui.field("Soft wrap", ui.switch(self.wrap, lambda v: setattr(self, "wrap", v)),
                             description="Wrap long lines at the window edge"),
                    ui.field("Language", ui.select(["Python", "Rust", "Go"], self.language,
                                                   lambda v: setattr(self, "language", v), width=140)),
                ]),
                ui.callout("Tip", "Every component reads its colors from the theme.", tint="hint"),
            ], spacing=16),
            padding=24, width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(Settings)
