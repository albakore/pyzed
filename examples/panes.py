"""Resizable panes, after Iced's ``pane_grid`` demo, using nested ``ui.split``.

    python examples/panes.py

Drag the dividers; each pane can be split again or closed. The layout is a small
tree of ``("h" | "v", ratio, first, second)`` tuples kept in your state.
"""

from itertools import count

import pyzed as pz
from pyzed import ui

_ids = count(1)


class Panes(pz.App):
    title = "Panes"
    size = (1000, 680)

    def __init__(self):
        self.layout = next(_ids)  # a leaf is a pane number
        self.focus = self.layout

    def replace(self, node, target, new):
        if node == target:
            return new
        if isinstance(node, list):
            node[2] = self.replace(node[2], target, new)
            node[3] = self.replace(node[3], target, new)
        return node

    def remove(self, node, target):
        if isinstance(node, list):
            if node[2] == target:
                return node[3]
            if node[3] == target:
                return node[2]
            node[2] = self.remove(node[2], target)
            node[3] = self.remove(node[3], target)
        return node

    def split(self, pane, vertical):
        new = next(_ids)
        self.layout = self.replace(self.layout, pane, ["v" if vertical else "h", 0.5, pane, new])
        self.focus = new

    def close(self, pane):
        if self.layout != pane:
            self.layout = self.remove(self.layout, pane)
            self.focus = None

    def pane(self, number):
        t = self.resolved_theme()
        focused = number == self.focus
        header = pz.container(
            pz.row([
                ui.label(f"Pane {number}", weight="medium", color="text" if focused else "text_muted"),
                pz.hspace(),
                ui.icon_button("columns-2", lambda: self.split(number, False), size="sm", tooltip="Split right"),
                ui.icon_button("rows-2", lambda: self.split(number, True), size="sm", tooltip="Split down"),
                ui.icon_button("x", lambda: self.close(number), size="sm", tooltip="Close",
                               disabled=self.layout == number),
            ], spacing=2, align="center"),
            padding=(4, 8), width="fill", bg=t.tab_active if focused else t.tab_inactive,
        )
        body = pz.mouse_area(pz.center(ui.muted("Click to focus")), on_press=lambda: setattr(self, "focus", number))
        return pz.container(pz.column([header, body]), width="fill", height="fill", bg=t.editor,
                            border_color=t.border_focused if focused else t.border_variant, border_width=1)

    def render(self, node):
        if not isinstance(node, list):
            return self.pane(node)
        direction, ratio, first, second = node

        def resize(r, node=node):
            node[1] = r

        return ui.split(self.render(first), self.render(second), ratio=ratio, on_resize=resize,
                        vertical=direction == "v", min_size=120)

    def view(self):
        return pz.container(self.render(self.layout), padding=8, width="fill", height="fill",
                            bg=self.resolved_theme().background)


if __name__ == "__main__":
    pz.run(Panes)
