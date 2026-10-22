"""The same to-do list three ways (2 of 3): declarative.

Every event is a message (a small dataclass) and one ``update()`` decides what each one does.
See docs/guides/code-styles.md; the other two are imperative.py and functional.py.

    python examples/code_styles/declarative.py
"""

from dataclasses import dataclass

import pyzed as pz
from pyzed import ui


# -- the messages: everything that can happen ------------------------------------
@dataclass
class Type:
    text: str


@dataclass
class Add:
    pass


@dataclass
class Toggle:
    index: int
    done: bool


@dataclass
class Remove:
    index: int


@dataclass
class Filter:
    name: str


class Todo(pz.App):
    title = "Tasks"
    size = (420, 360)

    def __init__(self):
        self.tasks = [{"title": "Write the docs", "done": False}]
        self.draft = ""
        self.filter = "All"

    # -- one place decides how each message changes the state ------------------
    def update(self, message):
        match message:
            case Type(text):
                self.draft = text
            case Add() if self.draft.strip():
                self.tasks.append({"title": self.draft.strip(), "done": False})
                self.draft = ""
            case Toggle(index, done):
                self.tasks[index]["done"] = done
            case Remove(index):
                del self.tasks[index]
            case Filter(name):
                self.filter = name

    # -- the view only describes the window and the messages -------------------
    def view(self):
        rows = [(i, t) for i, t in enumerate(self.tasks)
                if self.filter == "All" or t["done"] == (self.filter == "Done")]
        return pz.column([
            ui.input(self.draft, Type, placeholder="New task", on_submit=Add()),
            ui.segmented(["All", "To do", "Done"], self.filter, Filter),
            *[pz.row([
                ui.checkbox(t["done"], lambda done, i=i: Toggle(i, done), label=t["title"]),
                pz.hspace(),
                ui.icon_button("trash-2", Remove(i), size="sm"),
            ], align="center") for i, t in rows],
        ], spacing=8, padding=16)


if __name__ == "__main__":
    pz.run(Todo)
