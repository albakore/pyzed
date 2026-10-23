"""A small app for trying Pyzed on a phone: the safe area, the soft keyboard and the back button."""

import pyzed as pz
from pyzed import ui


class Phone(pz.App):
    title = "Pyzed on Android"

    def __init__(self):
        self.page = "home"
        self.name = ""
        self.count = 0

    def update(self, message):
        if message == "increment":
            self.count += 1
        elif message == "details":
            self.page = "details"

    def on_back(self):
        # On the second page, back returns to the first; on the first, the app goes away.
        if self.page == "details":
            self.page = "home"
            return None
        return False

    def view(self):
        top, right, bottom, left = pz.safe_area()
        if self.page == "details":
            body = [
                ui.heading("Details"),
                ui.text(f"Safe area: top {top:.0f}, right {right:.0f}, bottom {bottom:.0f}, left {left:.0f}"),
                ui.text("The back button returns to the first page."),
            ]
        else:
            body = [
                ui.heading(f"Hello{', ' + self.name if self.name else ''}!"),
                ui.input(self.name, placeholder="Your name", on_input=lambda v: setattr(self, "name", v)),
                pz.row(
                    [
                        ui.button(str(self.count), "increment", icon="plus", variant="solid"),
                        ui.button("Details", "details", icon="chevron-right"),
                    ],
                    spacing=8,
                ),
            ]
        return pz.container(
            pz.column(body, spacing=16, padding=24, width="fill"),
            width="fill",
            height="fill",
            bg=self.theme.editor,
        )


if __name__ == "__main__":
    pz.run(Phone)
