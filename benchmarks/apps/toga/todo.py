"""Reference app: add tasks (button or Enter), tick them off, delete them, see how many are left."""

import toga
from toga.style import Pack


class Todo(toga.App):
    def startup(self):
        self.tasks = []  # [title, done]
        self.left = toga.Label("0 left", style=Pack(font_size=16, font_weight="bold"))
        self.entry = toga.TextInput(on_confirm=self.add, style=Pack(flex=1))
        entry_row = toga.Box(children=[self.entry, toga.Button("Add", on_press=self.add)],
                             style=Pack(direction="row", gap=8))
        self.list = toga.Box(style=Pack(direction="column", gap=4))
        box = toga.Box(children=[self.left, entry_row, toga.ScrollContainer(content=self.list, style=Pack(flex=1))],
                       style=Pack(direction="column", margin=16, gap=12))
        self.main_window = toga.MainWindow(title="To-do", size=(420, 480))
        self.main_window.content = box
        self.main_window.show()

    def add(self, _widget):
        if self.entry.value.strip():
            self.tasks.append([self.entry.value.strip(), False])
            self.entry.value = ""
            self.refresh()

    def toggle(self, task, done):
        task[1] = done
        self.refresh()

    def remove(self, task):
        self.tasks.remove(task)
        self.refresh()

    def refresh(self):
        self.list.clear()
        for task in self.tasks:
            check = toga.Switch(task[0], value=task[1], style=Pack(flex=1),
                                on_change=lambda w, t=task: self.toggle(t, w.value))
            delete = toga.Button("Delete", on_press=lambda w, t=task: self.remove(t))
            self.list.add(toga.Box(children=[check, delete], style=Pack(direction="row")))
        self.left.text = f"{sum(not done for _, done in self.tasks)} left"


Todo("To-do", "org.pyzed.todo").main_loop()
