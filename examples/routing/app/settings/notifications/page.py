import pyzed as pz
from pyzed import ui

title = "Notifications"


class Page(pz.Component):
    email = pz.state(True)
    push = pz.state(False)

    def render(self):
        return pz.column([
            ui.switch(self.email, lambda v: setattr(self, "email", v), label="Email me about orders"),
            ui.switch(self.push, lambda v: setattr(self, "push", v), label="Push notifications"),
        ], spacing=10)
