"""Layout: track grids, flex rows and a Zed-style dock with movable, resizable panels.

    python examples/layout.py

- Drag a panel's inner edge to resize it.
- Drag a tab onto one of the zones that appear to move the panel, or right-click it.
- The center shows ``pz.grid`` (sized tracks, cells that span) and ``pz.flex``.
"""

import pyzed as pz
from pyzed import ui


def swatch(label, t, color=None):
    return pz.container(ui.label(label, size="sm"), padding=8, bg=color or t.element, radius=t.radius,
                        width="fill", height="fill")


class LayoutDemo(pz.App):
    title = "Layout"
    size = (1000, 640)

    def __init__(self):
        self.layout = None
        self.log = ["Drag a tab onto a drop zone, or a panel edge to resize it."]

    def saved(self, event):
        self.layout = event.value
        sides = ", ".join(f"{p}: {s}" for p, s in sorted(event.value["positions"].items())) or "default"
        self.log = [f"layout → {sides}", *self.log][:6]

    def center(self, t):
        grid = pz.grid(
            [
                pz.cell(swatch("Header (spans 3 columns)", t, t.element_selected), column=0, row=0, column_span=3),
                pz.cell(swatch("Sidebar (2 rows)", t), column=0, row=1, row_span=2),
                swatch("1fr", t),
                pz.container(ui.label("auto: fits me", size="sm"), padding=8, bg=t.element,
                             radius=t.radius, height="fill"),
                swatch("1fr", t),
                pz.cell(ui.badge("centered"), align_x="center", align_y="center"),
            ],
            columns=[140, "1fr", "auto"],
            rows=[44, "1fr", "1fr"],
            spacing=8,
            height=240,
        )
        bar = lambda justify: pz.container(  # noqa: E731
            pz.flex([ui.badge("A"), ui.badge("B"), ui.badge("C")], justify=justify, align="center", gap=6),
            padding=6, bg=t.element, radius=t.radius, width="fill",
        )
        flexes = pz.column([
            ui.label("pz.flex(justify=...)", weight="semibold"),
            *[pz.row([pz.container(ui.label(j, size="sm", color="text_muted"), width=60), bar(j)], align="center", spacing=8)
              for j in ("start", "center", "end", "between", "around", "evenly")],
            pz.flex([pz.flex_item(swatch("grow=1", t)), pz.flex_item(swatch("grow=2", t), grow=2),
                     pz.flex_item(swatch("basis=120", t), basis=120)], gap=6, height=36),
        ], spacing=6)
        return pz.scrollable(pz.column([ui.label("pz.grid(columns=[140, '1fr', 'auto'])", weight="semibold"), grid,
                                        flexes], spacing=12, padding=16))

    def view(self):
        t = self.resolved_theme()
        files = ui.tree(ui.TreeNode.from_paths(["src/main.py", "src/app.py", "README.md"]), expanded={"src"})
        log = pz.column([ui.label(line, mono=True, size="sm") for line in self.log], spacing=2, padding=8)
        return pz.Dock(
            center=self.center(t),
            panels=[
                pz.DockPanel("project", "Project", pz.container(files, padding=8), icon="folder", side="left"),
                pz.DockPanel("outline", "Outline", pz.container(ui.label("Outline"), padding=8), icon="list-tree",
                             side="left"),
                pz.DockPanel("log", "Log", log, icon="terminal", side="bottom"),
                pz.DockPanel("props", "Properties", pz.container(ui.label("Properties"), padding=8),
                             icon="settings-2", side="right"),
            ],
            layout=self.layout,
            on_layout=self.saved,
        )


if __name__ == "__main__":
    pz.run(LayoutDemo)
