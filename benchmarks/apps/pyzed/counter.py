"""Reference app: a counter with -, + and Reset."""

import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    title = "Counter"
    size = (320, 200)

    def __init__(self):
        self.count = 0

    def add(self, step):
        self.count += step

    def view(self):
        return pz.center(pz.column([
            ui.heading(str(self.count)),
            pz.row([
                ui.button(icon="minus", on_press=lambda: self.add(-1)),
                ui.button(icon="plus", on_press=lambda: self.add(1), variant="solid"),
                ui.button("Reset", lambda: setattr(self, "count", 0), variant="ghost"),
            ], spacing=8),
        ], spacing=16, align="center"))


pz.run(Counter)
