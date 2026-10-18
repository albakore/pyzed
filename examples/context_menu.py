"""A right-click context menu built from ``ui.popover`` and ``ui.menu``.

    python examples/context_menu.py

The pointer position is remembered with ``mouse_area(on_move=...)`` so the menu opens
where you clicked. Clicking anywhere else (or pressing Escape) closes it.
"""

import pyzed as pz
from pyzed import ui


class ContextMenu(pz.App):
    title = "Context menu"
    size = (640, 420)

    def __init__(self):
        self.pointer = (0, 0)
        self.menu_at = None
        self.log = ["Right-click anywhere in the box."]
        self.soft_wrap = True

    def act(self, what):
        def run():
            self.log.append(what)
            self.menu_at = None
        return run

    def toggle_wrap(self):
        self.soft_wrap = not self.soft_wrap
        self.menu_at = None

    def on_key(self, combo):
        if combo == "escape":
            self.menu_at = None

    def view(self):
        t = self.resolved_theme()
        area = pz.mouse_area(
            pz.container(pz.column([ui.muted(line) for line in self.log[-12:]], spacing=4), padding=16,
                         width="fill", height="fill", bg=t.editor, border_color=t.border_variant, border_width=1,
                         radius=t.radius),
            on_move=lambda x, y: setattr(self, "pointer", (x, y)),
            on_right_press=lambda: setattr(self, "menu_at", self.pointer),
        )
        menu = None
        if self.menu_at:
            menu = ui.menu([
                ui.MenuItem("Cut", self.act("cut"), icon="scissors", keys="ctrl-x"),
                ui.MenuItem("Copy", self.act("copy"), icon="copy", keys="ctrl-c"),
                ui.MenuItem("Paste", self.act("paste"), icon="clipboard", keys="ctrl-v"),
                ui.SEPARATOR,
                ui.MenuItem("Soft wrap", self.toggle_wrap, checked=self.soft_wrap),
                ui.SEPARATOR,
                ui.MenuItem("Delete", self.act("delete"), icon="trash-2", danger=True),
            ], width=220)
        x, y = self.menu_at or (0, 0)
        return pz.container(
            ui.popover(area, menu, x=x + 16, y=y + 16, on_dismiss=lambda: setattr(self, "menu_at", None)),
            padding=16, width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(ContextMenu)
