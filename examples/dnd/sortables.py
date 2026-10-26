"""Sortable lists in every shape: a to-do list you can also reorder with the keyboard, tabs that
slide sideways, a photo grid, and files you drop onto a folder to group them.

    python examples/dnd/sortables.py

Guide: https://albakore.github.io/pyzed/dnd/sortable/
"""

import pyzed as pz
from pyzed import ui

PHOTOS = ["#e06c75", "#e5c07b", "#98c379", "#56b6c2", "#61afef", "#c678dd", "#d19a66", "#be5046"]


class Sortables(pz.App):
    title = "Sortables"
    size = (960, 620)

    def __init__(self):
        self.tasks = ["Buy milk", "Answer emails", "Book flights", "Water the plants"]
        self.tabs = ["main.py", "app.py", "README.md", "styles.css"]
        self.photos = list(PHOTOS)
        self.files = [{"id": "notes.txt"}, {"id": "Photos", "folder": []}, {"id": "budget.xlsx"},
                      {"id": "todo.md"}, {"id": "Work", "folder": []}]

    # -- drops ---------------------------------------------------------------
    def group(self, event):
        if event.combine is None:
            pz.dnd.move(self.files, event)
            return
        moved = self.files.pop(event.from_index)
        target = next(f for f in self.files if f["id"] == event.combine)
        if "folder" in target:                          # onto a folder: it goes in
            target["folder"].append(moved["id"])
        else:                                           # onto a file: both go into a new folder
            at = self.files.index(target)
            self.files[at] = {"id": f"Folder {at + 1}", "folder": [target["id"], moved["id"]]}

    # -- view ----------------------------------------------------------------
    def section(self, title, hint, body):
        t = pz.theme.current()
        return pz.container(pz.column([ui.label(title, weight="bold"), ui.muted(hint), body], spacing=8),
                            padding=14, width="fill").style(background=t.surface, radius=10)

    def task(self, title):
        t = pz.theme.current()
        return pz.container(pz.row([pz.icon("grip-vertical", color=t.text_muted), ui.label(title)], spacing=8),
                            padding=8, width="fill").style(background=t.elevated, radius=6)

    def tab(self, name):
        t = pz.theme.current()
        return pz.container(pz.row([pz.icon("file-code", size=14), ui.label(name, size="sm")], spacing=6),
                            padding=(6, 12)).style(background=t.tab_active, radius=6)

    def photo(self, color):
        return pz.container(None, width=96, height=72).style(background=color, radius=8)

    def file(self, f):
        t = pz.theme.current()
        folder = "folder" in f
        icon = pz.icon("folder" if folder else "file", color=t.accent if folder else t.text_muted)
        extra = ui.badge(str(len(f["folder"])), size="sm") if folder and f["folder"] else pz.space()
        return pz.container(pz.row([icon, ui.label(f["id"]), pz.space(width="fill"), extra], spacing=8,
                                   align="center"), padding=8, width="fill").style(background=t.elevated, radius=6)

    def view(self):
        tasks = pz.sortable(items=self.tasks, item=self.task, key=str, id="tasks", spacing=6, keyboard=True,
                            on_reorder=lambda e: pz.dnd.move(self.tasks, e))
        tabs = pz.sortable(items=self.tabs, item=self.tab, key=str, id="tabs", direction="horizontal", spacing=4,
                           lock_axis=True, source="ghost", placeholder="none",
                           on_reorder=lambda e: pz.dnd.move(self.tabs, e))
        photos = pz.sortable(items=self.photos, item=self.photo, key=str, id="photos", direction="wrap", spacing=8,
                             placeholder="ghost", on_reorder=lambda e: pz.dnd.move(self.photos, e))
        files = pz.sortable(items=self.files, item=self.file, id="files", spacing=4, combine=True,
                            on_reorder=self.group)
        left = pz.column([
            self.section("List", "Drag, or focus an item and press Alt+↑/↓", tasks),
            self.section("Tabs", "They only move sideways", tabs),
        ], spacing=12, width="fill")
        right = pz.column([
            self.section("Grid", "Rows wrap; the others make room", photos),
            self.section("Folders", "Drop a file in the middle of a folder to move it in", files),
        ], spacing=12, width="fill")
        return pz.row([left, right], spacing=12, padding=12)


if __name__ == "__main__":
    Sortables().run()
