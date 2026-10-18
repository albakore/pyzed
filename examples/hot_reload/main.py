"""Hot reload demo: run it with hot reload, then edit this file or cards.py and save.

    pyzed dev examples/hot_reload/main.py

The window updates as soon as you save, and the counters keep their values.
A mistake (a syntax error, an exception in view) is shown in the window until you fix it.
"""

import pyzed as pz
from pyzed import ui

from cards import stat


class Dashboard(pz.App):
    title = "Hot reload"
    size = (520, 300)
    clicks = 0
    reloads = 0

    def add(self):
        self.clicks += 1

    def on_reload(self):
        # Runs after every reload: a place to migrate or refresh state.
        self.reloads += 1

    def view(self):
        return pz.column(
            [
                ui.heading("Edit me and save", level=2),
                ui.label("Change any text, color or layout here or in cards.py.", color="text_muted"),
                pz.row([stat("Clicks", self.clicks), stat("Reloads", self.reloads)], spacing=12),
                ui.button("Add one", self.add, icon="plus", variant="filled"),
            ],
            spacing=14,
            padding=24,
        )


if __name__ == "__main__":
    pz.run(Dashboard, reload=True)
