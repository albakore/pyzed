"""The same to-do list three ways (3 of 3): functional.

The state is one frozen dataclass, the view and the logic are pure functions, and the only class
keeps the current state. See docs/guides/code-styles.md; the other two are imperative.py and
declarative.py.

    python examples/code_styles/functional.py
"""

from dataclasses import dataclass, replace

import pyzed as pz
from pyzed import ui


@dataclass(frozen=True)
class Task:
    title: str
    done: bool = False


@dataclass(frozen=True)
class State:                                   # the whole state, immutable
    tasks: tuple = (Task("Write the docs"),)
    draft: str = ""
    filter: str = "All"


# -- pure functions: they change nothing, they return new values -----------------
def added(tasks, title):
    return tasks + (Task(title.strip()),) if title.strip() else tasks


def toggled(tasks, index, done):
    return tuple(replace(t, done=done) if i == index else t for i, t in enumerate(tasks))


def removed(tasks, index):
    return tasks[:index] + tasks[index + 1:]


def visible(tasks, filter):
    return [(i, t) for i, t in enumerate(tasks) if filter == "All" or t.done == (filter == "Done")]


# -- the view: a pure function of the state ---------------------------------------
def task_row(task, on_toggle, on_remove):      # a function component
    return pz.row([
        ui.checkbox(task.done, on_toggle, label=task.title),
        pz.hspace(),
        ui.icon_button("trash-2", on_remove, size="sm"),
    ], align="center")


def view(state, set_state):
    return pz.column([
        ui.input(state.draft, lambda text: set_state(draft=text), placeholder="New task",
                 on_submit=lambda: set_state(tasks=added(state.tasks, state.draft), draft="")),
        ui.segmented(["All", "To do", "Done"], state.filter, lambda f: set_state(filter=f)),
        *[task_row(t, lambda done, i=i: set_state(tasks=toggled(state.tasks, i, done)),
                   lambda i=i: set_state(tasks=removed(state.tasks, i)))
          for i, t in visible(state.tasks, state.filter)],
    ], spacing=8, padding=16)


# -- the only class: it keeps the current state ------------------------------------
class Todo(pz.App):
    title = "Tasks"
    size = (420, 360)
    state = State()

    def set_state(self, **changes):
        self.state = replace(self.state, **changes)

    def view(self):
        return view(self.state, self.set_state)


if __name__ == "__main__":
    pz.run(Todo)
