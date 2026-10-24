"""Two themes in one window, and a theme picker that remembers your choice.

    python examples/theming/mixed.py

- ``with theme:`` draws a block with another theme (here, a light sidebar in a dark app).
- ``self.theme = name`` changes the theme at runtime; the whole window restyles at once.
- ``Theme.save`` and ``Theme.load`` keep the chosen theme in a JSON file.
"""

from pathlib import Path

import pyzed as pz
from pyzed import ui
from preview import preview

SAVED = Path(__file__).with_name("my-theme.json")


class MixedApp(pz.App):
    title = "Mixed themes"
    size = (980, 580)

    def __init__(self):
        self.theme = "Pyzed Dark"
        if SAVED.exists():
            self.theme = pz.themes.register(pz.Theme.load(SAVED)).name

    def pick(self, name):
        self.theme = name
        pz.themes.get(name).save(SAVED)  # remembered for the next start

    def view(self):
        current = self.resolved_theme().name
        with pz.themes.get("Pyzed Light"):  # everything built in this block uses Pyzed Light
            sidebar = pz.container(pz.column([
                ui.heading("Settings", level=3),
                ui.field("Theme", ui.select(pz.themes.names(), current, self.pick, width=200)),
                ui.muted("This panel always uses Pyzed Light."),
            ], spacing=12), padding=16, width=300, height="fill").style(background="background")
        main = pz.container(preview(current, "The main area follows the theme you pick."),
                            padding=24, width="fill", height="fill")
        return pz.row([sidebar, main], height="fill")


if __name__ == "__main__":
    pz.run(MixedApp)
