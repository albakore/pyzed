"""Todos, after Iced's ``todos`` demo: add, edit, complete, filter and persist tasks.

    python examples/todos.py

Tasks are saved as JSON next to your user config, so they survive restarts.
"""

import json
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path

import pyzed as pz
from pyzed import ui

STORE = Path.home() / ".config" / "pyzed-todos.json"
_ids = count()


@dataclass
class Task:
    text: str
    done: bool = False
    id: int = field(default_factory=lambda: next(_ids))


class Todos(pz.App):
    title = "Todos"
    size = (560, 680)

    def __init__(self, store=STORE):
        self.store = store
        self.draft = ""
        self.filter = "All"
        self.editing = None  # (task id, edited text)
        self.tasks = self.load()

    # -- persistence --------------------------------------------------------
    def load(self):
        try:
            return [Task(t["text"], t["done"]) for t in json.loads(self.store.read_text())]
        except (OSError, ValueError, KeyError, TypeError):
            return [Task("Read the Pyzed examples"), Task("Build something nice", done=True)]

    def save(self):
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            self.store.write_text(json.dumps([{"text": t.text, "done": t.done} for t in self.tasks], indent=2))
        except OSError:
            pass

    # -- actions --------------------------------------------------------------
    def add(self):
        if self.draft.strip():
            self.tasks.append(Task(self.draft.strip()))
            self.draft = ""
            self.save()

    def toggle(self, task):
        task.done = not task.done
        self.save()

    def remove(self, task):
        self.tasks.remove(task)
        self.save()

    def start_edit(self, task):
        self.editing = (task.id, task.text)
        return pz.Command.focus(f"edit-{task.id}")

    def finish_edit(self):
        task_id, text = self.editing
        for task in self.tasks:
            if task.id == task_id and text.strip():
                task.text = text.strip()
        self.editing = None
        self.save()

    def clear_done(self):
        self.tasks = [t for t in self.tasks if not t.done]
        self.save()

    def on_key(self, combo):
        if combo == "escape":
            self.editing = None

    # -- view -------------------------------------------------------------------
    def visible(self):
        if self.filter == "Active":
            return [t for t in self.tasks if not t.done]
        if self.filter == "Completed":
            return [t for t in self.tasks if t.done]
        return self.tasks

    def task_row(self, task):
        t = self.resolved_theme()
        if self.editing and self.editing[0] == task.id:
            return pz.row([
                ui.input(self.editing[1], lambda text: setattr(self, "editing", (task.id, text)),
                         on_submit=self.finish_edit, id=f"edit-{task.id}"),
                ui.icon_button("check", self.finish_edit, tooltip="Save"),
                ui.icon_button("trash-2", lambda: self.remove(task), tooltip="Delete", color=t.error),
            ], spacing=6, align="center")
        return pz.row([
            ui.checkbox(task.done, lambda _: self.toggle(task)),
            pz.mouse_area(
                ui.label(task.text, color="text_muted" if task.done else "text", width="fill"),
                on_double_click=lambda: self.start_edit(task),
            ),
            ui.icon_button("pencil", lambda: self.start_edit(task), tooltip="Edit"),
        ], spacing=10, align="center")

    def view(self):
        t = self.resolved_theme()
        left = sum(not task.done for task in self.tasks)
        tasks = self.visible()
        body = (pz.column([self.task_row(task) for task in tasks], spacing=6)
                if tasks else ui.empty_state("Nothing here", f"No {self.filter.lower()} tasks."))
        return pz.container(
            pz.column([
                ui.heading("todos"),
                ui.input(self.draft, lambda text: setattr(self, "draft", text), on_submit=self.add,
                         placeholder="What needs to be done?", icon="plus"),
                pz.row([
                    ui.muted(f"{left} {'task' if left == 1 else 'tasks'} left"),
                    pz.hspace(),
                    ui.segmented(["All", "Active", "Completed"], self.filter, lambda f: setattr(self, "filter", f)),
                ], align="center"),
                pz.scrollable(body, height="fill"),
                pz.row([pz.hspace(), ui.button("Clear completed", self.clear_done, variant="ghost", size="sm")]),
            ], spacing=14, max_width=520),
            padding=24, width="fill", height="fill", align_x="center", bg=t.editor,
        )


if __name__ == "__main__":
    pz.run(Todos)
