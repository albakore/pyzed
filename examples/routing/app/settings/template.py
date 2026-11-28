"""A template is drawn again from scratch on every navigation: its state starts over on each tab."""

import pyzed as pz
from pyzed import ui


class Template(pz.Component):
    children: list = ()
    clicks = pz.state(0)

    def render(self):
        return pz.column([
            pz.row([
                ui.button(f"Clicked {self.clicks} times", self.click, size="sm"),
                ui.label("starts over on every tab (a template); the sidebar doesn't (a layout)",
                         size="sm", color="text_muted"),
            ], spacing=8, align="center"),
            *self.children,
        ], spacing=12)

    def click(self):
        self.clicks += 1
