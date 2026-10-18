"""A to-do list: state, text input, list items, filters and keyboard shortcuts.

    python examples/todo.py

Walkthrough: https://albakore.github.io/pyzed/tutorials/todo-app/
"""

from dataclasses import dataclass
from itertools import count

import pyzed as pz
from pyzed import Command, ui

_ids = count(1)


@dataclass
class Task:
    title: str
    done: bool = False
    id: int = 0

    def __post_init__(self):
        self.id = self.id or next(_ids)


class Todo(pz.App):
    title = "Tareas"
    size = (520, 560)
    min_size = (400, 360)

    def __init__(self):
        self.tasks = [Task("Leer la guía de Pyzed", done=True), Task("Crear mi primera app"), Task("Probar los temas")]
        self.draft = ""
        self.filter = "Todas"

    # -- actions -----------------------------------------------------------
    def add(self):
        if self.draft.strip():
            self.tasks.append(Task(self.draft.strip()))
            self.draft = ""
        return Command.focus("new-task")

    def toggle(self, task):
        task.done = not task.done

    def remove(self, task):
        self.tasks.remove(task)

    def clear_done(self):
        self.tasks = [t for t in self.tasks if not t.done]

    def on_start(self):
        return Command.focus("new-task")

    def on_key(self, combo):
        if combo == "ctrl-l":
            return self.clear_done()
        if combo == "ctrl-t":
            self.theme = pz.themes.ONE_LIGHT if self.theme.is_dark else pz.themes.ONE_DARK

    # -- view ----------------------------------------------------------------
    def visible(self):
        if self.filter == "Pendientes":
            return [t for t in self.tasks if not t.done]
        if self.filter == "Hechas":
            return [t for t in self.tasks if t.done]
        return self.tasks

    def task_row(self, task):
        return ui.list_item(
            ui.label(task.title, color="text_muted" if task.done else "text"),
            lambda: self.toggle(task),
            start=ui.checkbox(task.done, lambda _: self.toggle(task)),
            end=ui.icon_button("trash-2", lambda: self.remove(task), size="sm", tooltip="Eliminar"),
            height=34,
            inset=True,
        )

    def view(self):
        pending = sum(not t.done for t in self.tasks)
        tasks = self.visible()
        return pz.container(
            pz.column(
                [
                    pz.row([ui.heading("Tareas", level=2), pz.hspace(), ui.badge(f"{pending} pendientes")],
                           align="center"),
                    pz.row(
                        [
                            ui.input(self.draft, lambda text: setattr(self, "draft", text), id="new-task",
                                     placeholder="¿Qué hay que hacer?", on_submit=self.add, icon="plus"),
                            ui.button("Añadir", self.add, variant="solid"),
                        ],
                        spacing=8,
                    ),
                    pz.row(
                        [
                            ui.segmented(["Todas", "Pendientes", "Hechas"], self.filter,
                                         lambda f: setattr(self, "filter", f)),
                            pz.hspace(),
                            ui.button("Limpiar hechas", self.clear_done, variant="ghost", size="sm", keys="ctrl-l"),
                        ],
                        align="center",
                    ),
                    ui.card(
                        pz.scrollable(pz.column([self.task_row(t) for t in tasks], spacing=2), height="fill")
                        if tasks else pz.center(ui.muted("No hay tareas aquí."), height=120),
                        padding=6,
                    ),
                ],
                spacing=14,
                max_width=640,
            ),
            padding=24,
            width="fill",
            height="fill",
            align_x="center",
            bg=self.theme.editor,
        )


if __name__ == "__main__":
    pz.run(Todo)
