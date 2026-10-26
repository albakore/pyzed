"""A page builder: drag blocks from the library onto the page, nest them in columns,
reorder them anywhere and switch between the desktop and phone widths.

    python examples/dnd/page_builder.py

Walkthrough: https://albakore.github.io/pyzed/dnd/tutorials/page-builder/
"""

from itertools import count

import pyzed as pz
from pyzed import ui

_ids = count(1)

LIBRARY = {
    "heading": ("heading", "Heading"),
    "text": ("text", "Text"),
    "image": ("image", "Image"),
    "button": ("mouse-pointer-click", "Button"),
    "quote": ("quote", "Quote"),
    "columns": ("columns-2", "Two columns"),
}


def block(kind):
    b = {"id": f"block-{next(_ids)}", "kind": kind}
    if kind == "columns":  # a block that holds blocks: two lists of its own
        b["left"], b["right"] = [], []
    return b


class PageBuilder(pz.App):
    title = "Page builder"
    size = (1080, 680)

    def __init__(self):
        hero = block("columns")
        hero["left"] = [block("heading"), block("text"), block("button")]
        hero["right"] = [block("image")]
        self.page = [hero, block("quote"), block("text")]
        self.width = "Desktop"

    # -- the page as lists by id, so pz.dnd.move can move blocks between any of them --------
    def lists(self):
        found = {"page": self.page}
        for b in self.page:
            if b["kind"] == "columns":
                found[b["id"] + ":left"], found[b["id"] + ":right"] = b["left"], b["right"]
        return found

    def drop(self, event):
        if event.from_list == "library":
            self.lists()[event.target].insert(event.index, block(event.data))
        else:
            pz.dnd.move(self.lists(), event)

    def delete(self, event):
        lists = self.lists()
        lists[event.from_list].pop(event.from_index)

    # -- rendering one block ------------------------------------------------------------------
    def render(self, b):
        t = pz.theme.current()
        kind = b["kind"]
        if kind == "heading":
            body = ui.heading("Build pages by dragging", level=2)
        elif kind == "text":
            body = ui.label("Every block is a sortable item. Drop new ones from the library, "
                            "move them between columns, or drag them to the trash.", color="text_muted")
        elif kind == "image":
            body = pz.container(pz.icon("image", size=40, color=t.text_muted), height=140, width="fill",
                                align_x="center", align_y="center").style(background=t.element, radius=8)
        elif kind == "button":
            body = pz.row([ui.button("Get started", variant="solid"), ui.button("Learn more", variant="ghost")],
                          spacing=8)
        elif kind == "quote":
            body = pz.container(ui.label("“Drag and drop made our editor feel native.”", italic=True),
                                padding=12, width="fill").style(border_color=t.accent, border_width=0,
                                                               background=pz.theme.alpha(t.accent, 0.08), radius=6)
        else:
            body = self.columns(b)
        handle = pz.drag_handle(pz.container(pz.icon("grip-vertical", size=14, color=t.text_muted), padding=2))
        return pz.container(pz.row([handle, pz.container(body, width="fill")], spacing=6), padding=8,
                            width="fill").style(radius=8, border_color=t.border_variant, border_width=1)

    def columns(self, b):
        stacked = self.width == "Phone"
        sides = [self.area(b, "left"), self.area(b, "right")]
        return pz.column(sides, spacing=8) if stacked else pz.row(sides, spacing=8)

    def area(self, b, side):
        t = pz.theme.current()
        return pz.sortable(
            items=b[side], item=self.render, id=f"{b['id']}:{side}", group="blocks", handle=True, spacing=8,
            padding=8, width="fill", on_reorder=self.drop,
            # Columns don't go inside columns.
            can_drop=lambda e: e.data != "columns" and not (isinstance(e.data, dict) and e.data["kind"] == "columns"),
            over_style={"background": pz.theme.alpha(t.accent, 0.06), "border_color": t.accent, "radius": 8},
        ).style(min_height=60, background=t.background, radius=8)

    # -- view ---------------------------------------------------------------------------------
    def library_item(self, kind):
        t = pz.theme.current()
        icon, name = LIBRARY[kind]
        return pz.container(pz.column([pz.icon(icon, size=22, color=t.accent), ui.label(name, size="sm")],
                                      spacing=4, align="center"),
                            padding=10, width=88).style(background=t.elevated, radius=8, border_color=t.border,
                                                        border_width=1)

    def view(self):
        t = pz.theme.current()
        library = pz.sortable(items=list(LIBRARY), item=self.library_item, key=lambda k: f"lib-{k}", id="library",
                              group="blocks", pull="clone", sort=False, direction="wrap", spacing=8, placeholder="none")
        trash = pz.droppable(
            pz.container(pz.row([pz.icon("trash-2"), ui.label("Drop to delete")], spacing=6), padding=10,
                         width="fill", align_x="center").style(border_color=t.border, border_width=1, radius=8),
            "trash", accepts="blocks", can_drop=lambda e: e.from_list != "library", on_drop=self.delete)
        sidebar = pz.column([ui.label("Blocks", weight="bold"), library, pz.space(height="fill"), trash],
                            spacing=10, width=210, padding=12)
        page = pz.sortable(items=self.page, item=self.render, id="page", group="blocks", handle=True, spacing=10,
                           padding=16, on_reorder=self.drop)
        canvas = pz.container(page, width=360 if self.width == "Phone" else 680).style(
            background=t.background, radius=10, border_color=t.border, border_width=1)
        top = pz.row([ui.label("Untitled page", weight="bold"), pz.space(width="fill"),
                      ui.segmented(["Desktop", "Phone"], self.width, lambda v: setattr(self, "width", v))],
                     align="center")
        main = pz.column([top, pz.scrollable(pz.container(canvas, width="fill", align_x="center"), height="fill")],
                         spacing=12, padding=14, width="fill")
        return pz.row([sidebar, main]).style(background=t.surface)


if __name__ == "__main__":
    PageBuilder().run()
