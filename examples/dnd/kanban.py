"""A Kanban board like Trello: drag cards between columns, reorder the columns by their
header, drop a card on the trash that shows up while dragging.

    python examples/dnd/kanban.py

Walkthrough: https://albakore.github.io/pyzed/dnd/tutorials/kanban/
"""

from itertools import count

import pyzed as pz
from pyzed import ui

_ids = count(1)


def card(title, tag=None):
    return {"id": f"card-{next(_ids)}", "title": title, "tag": tag}


TAGS = {"bug": "error", "feature": "accent", "docs": "success"}


class Kanban(pz.App):
    title = "Kanban"
    size = (980, 620)

    def __init__(self):
        self.columns = [
            {"id": "todo", "title": "To do"},
            {"id": "doing", "title": "In progress"},
            {"id": "done", "title": "Done"},
        ]
        self.cards = {
            "todo": [card("Design the login screen", "feature"), card("Crash when saving", "bug"),
                     card("Write the API guide", "docs"), card("Dark mode icons")],
            "doing": [card("Drag and drop", "feature"), card("Translate the docs", "docs")],
            "done": [card("Project setup")],
        }
        self.drafts = {c["id"]: "" for c in self.columns}
        self.dragging = False

    # -- drops ---------------------------------------------------------------
    def move_card(self, event):
        pz.dnd.move(self.cards, event)

    def move_column(self, event):
        pz.dnd.reorder(self.columns, event.from_index, event.index)

    def delete(self, event):
        self.cards[event.from_list].pop(event.from_index)

    def add(self, column):
        title = self.drafts[column].strip()
        if title:
            self.cards[column].append(card(title))
            self.drafts[column] = ""

    # -- view ----------------------------------------------------------------
    def card_view(self, item):
        t = pz.theme.current()
        parts = [ui.label(item["title"])]
        if item["tag"]:
            parts.insert(0, ui.badge(item["tag"], tint=TAGS[item["tag"]], size="sm"))
        return pz.container(pz.column(parts, spacing=6), padding=10, width="fill").style(
            background=t.elevated, border_color=t.border, border_width=1, radius=8)

    def column_view(self, column):
        t = pz.theme.current()
        cid = column["id"]
        header = pz.row([
            pz.drag_handle(pz.icon("grip-vertical", size=14, color=t.text_muted)),
            ui.label(column["title"], weight="bold"),
            ui.count_badge(len(self.cards[cid])),
        ], spacing=6, align="center")
        cards = pz.sortable(
            items=self.cards[cid], item=self.card_view, id=cid, group="cards",
            spacing=8, height="fill", on_reorder=self.move_card,
            on_drag_start=lambda e: setattr(self, "dragging", True),
            on_drag_end=lambda e: setattr(self, "dragging", False),
        )
        new = ui.input(self.drafts[cid], lambda v, c=cid: self.drafts.__setitem__(c, v),
                       placeholder="Add a card…", on_submit=lambda c=cid: self.add(c), size="sm")
        return pz.container(pz.column([header, pz.scrollable(cards, height="fill"), new], spacing=10),
                            padding=12, width=280, height="fill").style(background=t.surface, radius=10)

    def trash(self):
        t = pz.theme.current()
        bin_ = pz.container(pz.row([pz.icon("trash-2", color=t.error), ui.label("Drop here to delete")], spacing=8),
                            padding=14).style(background=t.background, border_color=t.error, border_width=1, radius=10)
        return pz.droppable(bin_, "trash", accepts="cards", on_drop=self.delete,
                            over_style={"background": pz.theme.alpha(t.error, 0.15), "border_color": t.error,
                                        "border_width": 2, "radius": 10})

    def view(self):
        board = pz.sortable(
            items=self.columns, item=self.column_view, id="board", group="columns",
            direction="horizontal", spacing=14, handle=True, height="fill", placeholder="shadow",
            on_reorder=self.move_column,
        )
        bottom = self.trash() if self.dragging else ui.muted("Drag cards between columns · drag a column by ⋮⋮")
        return pz.column([board, pz.container(bottom, width="fill", align_x="center")], spacing=12, padding=16)


if __name__ == "__main__":
    Kanban().run()
