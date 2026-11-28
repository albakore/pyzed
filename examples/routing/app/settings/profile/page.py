import pyzed as pz
from pyzed import ui

title = "Profile"


class Page(pz.Component):
    name = pz.state("Ada")

    def render(self):
        return pz.column([
            ui.label("Display name"),
            ui.input(self.name, on_input=lambda v: setattr(self, "name", v), width=280),
            ui.label(f"Hello, {self.name}!", color="text_muted"),
        ], spacing=8)
