"""Reference app: add tasks (button or Enter), tick them off, delete them, see how many are left."""

import pyzed as pz
from pyzed import ui


class Todo(pz.App):
    title = "To-do"
    size = (420, 480)

    def __init__(self):
        self.tasks = []  # [title, done]
        self.draft = ""

    def add(self):
        if self.draft.strip():
            self.tasks.append([self.draft.strip(), False])
            self.draft = ""

    def toggle(self, task, done):
        task[1] = done

    def row(self, task):
        return pz.row([
            ui.checkbox(task[1], lambda done: self.toggle(task, done)),
            ui.label(task[0], color="text_muted" if task[1] else "text", width="fill"),
            ui.icon_button("trash-2", lambda: self.tasks.remove(task)),
        ], spacing=8, align="center")

    def view(self):
        left = sum(not done for _, done in self.tasks)
        return pz.column([
            ui.heading(f"{left} left", level=3),
            pz.row([
                ui.input(self.draft, lambda text: setattr(self, "draft", text), on_submit=self.add),
                ui.button("Add", self.add, variant="solid"),
            ], spacing=8),
            pz.scrollable(pz.column([self.row(t) for t in self.tasks], spacing=4), height="fill"),
        ], spacing=12, padding=16)


pz.run(Todo)
