"""Several windows in one app, after Iced's ``multi_window`` demo.

    python examples/multi_window.py

Every ``pz.Window`` has its own view, title, size and theme, but they all share the
app's state: the counter below is the same in every window. Closing the main window
quits the app.
"""

import pyzed as pz
from pyzed import ui


class Note(pz.Window):
    size = (360, 260)

    def __init__(self, number, theme):
        self.number = number
        self.theme = theme
        self.title = f"Window {number}"
        self.text = ""

    def on_close(self):
        # The user clicked the window's close button.
        self.app.windows.remove(self)

    def dismiss(self):
        self.app.windows.remove(self)
        return self.close()

    def view(self):
        t = self.resolved_theme()
        return pz.container(
            pz.column([
                ui.heading(self.title, level=3),
                ui.muted(f"Theme: {t.name}"),
                ui.input(self.text, lambda v: setattr(self, "text", v), placeholder="Type something…"),
                pz.row([
                    ui.button(f"Shared clicks: {self.app.clicks}", self.app.click, icon="mouse-pointer-click"),
                    pz.hspace(),
                    ui.button("Close", self.dismiss, variant="ghost"),
                ], align="center"),
            ], spacing=12),
            padding=20, width="fill", height="fill", bg=t.background,
        )


class Main(pz.App):
    title = "Multi window"
    size = (480, 360)

    def __init__(self):
        self.clicks = 0
        self.windows = []
        self.opened = 0

    def click(self):
        self.clicks += 1

    def open_window(self):
        self.opened += 1
        themes = pz.themes.all()
        window = Note(self.opened, themes[self.opened % len(themes)])
        self.windows.append(window)
        return window.open()

    def close_all(self):
        commands = [w.close() for w in self.windows]
        self.windows = []
        return commands

    def view(self):
        t = self.resolved_theme()
        items = [ui.list_item(w.title, None, icon="app-window", end=ui.muted(w.text or "empty")) for w in self.windows]
        return pz.container(
            pz.column([
                ui.heading("Windows", level=2),
                pz.row([ui.button("Open window", self.open_window, icon="plus", variant="solid"),
                        ui.button("Close all", self.close_all, disabled=not self.windows),
                        ui.button(f"Clicks: {self.clicks}", self.click)], spacing=8),
                pz.column(items) if items else ui.muted("No extra windows yet."),
            ], spacing=14),
            padding=24, width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(Main)
