"""The same to-do list three ways (1 of 3): imperative.

The state is plain attributes of the app and every event calls a method that changes them.
See docs/guides/code-styles.md; the other two are declarative.py and functional.py.

    python examples/code_styles/imperative.py
"""

import pyzed as pz
from pyzed import ui


class Todo(pz.App):
    title = "Tasks"
    size = (420, 360)

    def __init__(self):
        self.tasks = [{"title": "Write the docs", "done": False}]
        self.draft = ""
        self.filter = "All"

    # -- event handlers: each one changes the state --------------------------
    def type(self, text):
        self.draft = text

    def add(self):
        if self.draft.strip():
            self.tasks.append({"title": self.draft.strip(), "done": False})
            self.draft = ""

    def toggle(self, task, done):
        task["done"] = done

    def remove(self, task):
        self.tasks.remove(task)

    # -- the view reads the state ----------------------------------------------
    def view(self):
        shown = [t for t in self.tasks if self.filter == "All" or t["done"] == (self.filter == "Done")]
        return pz.column([
            ui.input(self.draft, self.type, placeholder="New task", on_submit=self.add),
            ui.segmented(["All", "To do", "Done"], self.filter, lambda f: setattr(self, "filter", f)),
            *[pz.row([
                ui.checkbox(t["done"], lambda done, t=t: self.toggle(t, done), label=t["title"]),
                pz.hspace(),
                ui.icon_button("trash-2", lambda t=t: self.remove(t), size="sm"),
            ], align="center") for t in shown],
        ], spacing=8, padding=16)


if __name__ == "__main__":
    pz.run(Todo)
