"""Tutorial, step 2: state, messages and callbacks.

    python examples/tutorial/step2_state.py
"""

import pyzed as pz
from pyzed import ui


class Greeter(pz.App):
    title = "Greeter"
    size = (420, 260)

    def __init__(self):
        # State is plain attributes on your object.
        self.name = ""
        self.greetings = 0

    def update(self, message):
        # Widgets given a plain value (here the string "greet") send it to update().
        if message == "greet" and self.name:
            self.greetings += 1

    def view(self):
        return pz.container(
            pz.column([
                # Callbacks that receive data get the new value: here the input's text.
                ui.input(self.name, lambda text: setattr(self, "name", text), placeholder="Your name",
                         on_submit="greet"),
                ui.button("Greet", "greet", variant="solid"),
                # A callable is called directly, no update() needed.
                ui.button("Reset", self.reset, variant="ghost"),
                ui.label(f"Hello, {self.name}! ({self.greetings})" if self.greetings else "Nobody greeted yet."),
            ], spacing=12),
            padding=24,
        )

    def reset(self):
        self.name, self.greetings = "", 0


if __name__ == "__main__":
    pz.run(Greeter)
