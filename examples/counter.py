"""The smallest Pyzed app: state + update + view."""

import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    title = "Counter"
    size = (360, 220)

    def __init__(self):
        self.count = 0

    def update(self, message):
        if message == "increment":
            self.count += 1
        elif message == "decrement":
            self.count -= 1

    def view(self):
        return pz.center(
            pz.column(
                [
                    ui.heading(str(self.count)),
                    pz.row(
                        [
                            ui.button("-1", "decrement", icon="minus"),
                            ui.button("+1", "increment", icon="plus", variant="solid"),
                            ui.icon_button("rotate-ccw", lambda: setattr(self, "count", 0), tooltip="Reset"),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=16,
                align="center",
            ),
            bg=self.theme.editor,
        )


if __name__ == "__main__":
    pz.run(Counter)
