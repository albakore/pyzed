"""A design canvas like Figma: move shapes freely with snapping and alignment guides, drop new
shapes from the toolbar where you want them, and reorder layers in the layers panel.

    python examples/dnd/design_canvas.py

Walkthrough: https://albakore.github.io/pyzed/dnd/tutorials/design-canvas/
"""

from itertools import count

import pyzed as pz
from pyzed import ui

_ids = count(1)

COLORS = ["#5c78e2", "#e06c75", "#98c379", "#e5c07b", "#c678dd", "#56b6c2"]
SHAPES = {"rect": ("square", 140, 90), "circle": ("circle", 100, 100), "pill": ("rectangle-horizontal", 160, 48),
          "text": ("type", 180, 40)}


def shape(kind, x, y):
    n = next(_ids)
    _, w, h = SHAPES[kind]
    return {"id": f"shape-{n}", "kind": kind, "name": f"{kind.title()} {n}", "x": x, "y": y, "w": w, "h": h,
            "color": COLORS[n % len(COLORS)]}


class DesignCanvas(pz.App):
    title = "Design canvas"
    size = (1120, 680)

    def __init__(self):
        # The layers list is the drawing order: the first one is on top.
        self.layers = [shape("text", 60, 40), shape("circle", 380, 180), shape("rect", 120, 200),
                       shape("pill", 420, 60)]
        self.selected = None
        self.grid = 8
        self.guides = True

    # -- drops ---------------------------------------------------------------
    def drop(self, event):
        if event.from_list is None and event.source.startswith("new-"):
            item = shape(event.data, event.item_x, event.item_y)   # from the toolbar
            self.layers.insert(0, item)
        else:
            item = next(s for s in self.layers if s["id"] == event.source)
            item["x"], item["y"] = event.item_x, event.item_y
        self.selected = item["id"]

    def reorder_layers(self, event):
        pz.dnd.reorder(self.layers, event.from_index, event.index)

    # -- view ----------------------------------------------------------------
    def body(self, s):
        t = pz.theme.current()
        selected = s["id"] == self.selected
        border = {"border_color": t.text, "border_width": 2} if selected else {}
        if s["kind"] == "text":
            return pz.container(ui.label("Headline", size="xl", weight="bold"), width=s["w"], height=s["h"],
                                align_y="center").style(**border)
        radius = min(s["w"], s["h"]) / 2 if s["kind"] in ("circle", "pill") else 6
        return pz.container(None, width=s["w"], height=s["h"]).style(background=s["color"], radius=radius, **border)

    def placed(self, s):
        piece = pz.draggable(
            self.body(s), s["id"], type="shape",
            source="hide", lift=1.0, shadow=False,      # the shape itself moves, as in a design tool
            drop_animation=0, on_drag_start=lambda e, i=s["id"]: setattr(self, "selected", i),
        ).on(click=lambda i=s["id"]: setattr(self, "selected", i))
        return pz.pin(piece, x=s["x"], y=s["y"])

    def tool(self, kind):
        t = pz.theme.current()
        icon, _, _ = SHAPES[kind]
        button = pz.container(pz.icon(icon, size=18), padding=8).style(background=t.element, radius=6)
        return pz.draggable(button, f"new-{kind}", data=kind, type="shape", source="keep")

    def layer_row(self, s):
        t = pz.theme.current()
        selected = s["id"] == self.selected
        return pz.container(pz.row([pz.container(None, width=12, height=12).style(background=s["color"], radius=3),
                                    ui.label(s["name"], size="sm")], spacing=8, align="center"),
                            padding=6, width="fill").style(background=t.element_selected if selected else None,
                                                           radius=6)

    def view(self):
        t = pz.theme.current()
        canvas = pz.droppable(
            pz.stack([pz.space(width="fill", height="fill"),
                      *[self.placed(s) for s in reversed(self.layers)]]),  # the last one drawn is on top
            "canvas", accepts="shape", snap=self.grid or None, guides=self.guides, over_style=False,
            on_drop=self.drop,
        )
        toolbar = pz.row([*[self.tool(k) for k in SHAPES], pz.space(width=16),
                          ui.switch(self.guides, lambda v: setattr(self, "guides", v), label="Guides"),
                          ui.segmented(["Off", "8", "16"], str(self.grid) if self.grid else "Off",
                                       lambda v: setattr(self, "grid", 0 if v == "Off" else int(v)))],
                         spacing=8, align="center")
        layers = pz.sortable(items=self.layers, item=self.layer_row, id="layers", spacing=2, lock_axis=True,
                             on_reorder=self.reorder_layers, placeholder="ghost")
        side = pz.column([ui.label("Layers", weight="bold"), layers], spacing=8, width=220, padding=12)
        board = pz.container(canvas, width="fill", height="fill").style(background=t.editor, radius=10, clip=True)
        return pz.row([side, pz.column([toolbar, board], spacing=10, padding=12, width="fill")]).style(
            background=t.surface)


if __name__ == "__main__":
    DesignCanvas().run()
