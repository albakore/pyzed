"""Custom components and events: a star rating, a tag editor and a draggable note.

    python examples/components.py

- ``Rating`` and ``TagInput`` are ``pz.Component`` classes: props, their own state,
  their own events (``change``, ``add``, ``remove``), reusable anywhere.
- The note uses the common events every widget has: drag it around, double-click to
  pin it, hover it, click it and press keys (they show up in the log).
"""

import pyzed as pz
from pyzed import ui


class Rating(pz.Component):
    """Stars the user can click; shows a preview while hovering."""

    value: int = 0
    max: int = 5
    events = {"change": "A star was picked (``event.value`` is the new rating)."}
    icon = "star"
    size = (140, 28)

    def setup(self):
        self.hover = None  # state: which star is under the pointer

    def render(self):
        t = pz.theme.current()
        shown = self.hover or self.value
        stars = []
        for i in range(1, self.max + 1):
            color = t.warning if i <= shown else t.text_disabled
            stars.append(
                pz.icon("star", size=20, color=color).on(
                    click=lambda i=i: self.emit("change", i),
                    mouse_enter=lambda i=i: setattr(self, "hover", i),
                    mouse_leave=lambda: setattr(self, "hover", None),
                )
            )
        return pz.row(stars, spacing=2)


class TagInput(pz.Component):
    """A list of tags with a box to add more."""

    tags: list = ()
    placeholder: str = "Add a tag…"
    events = {"add": "Enter was pressed (``event.value`` is the text).",
              "remove": "A tag's x was clicked (``event.value`` is the tag)."}
    icon = "tags"
    size = (280, 64)

    def setup(self):
        self.draft = ""

    def submit(self):
        text, self.draft = self.draft.strip(), ""
        return self.emit("add", text) if text else None

    def render(self):
        chips = [ui.chip(tag, on_remove=lambda tag=tag: self.emit("remove", tag)) for tag in self.tags]
        return pz.column([
            pz.row(chips, spacing=6, wrap=True, width="fill") if chips
            else ui.label("No tags yet", color="text_muted", size="sm"),
            ui.input(self.draft, lambda text: setattr(self, "draft", text), placeholder=self.placeholder,
                     on_submit=self.submit, icon="tag"),
        ], spacing=8)


class Demo(pz.App):
    title = "Components and events"
    size = (720, 460)

    def __init__(self):
        self.rating = 3
        self.tags = ["python", "rust"]
        self.note = (20, 40)
        self.pinned = False
        self.log = ["Drag the note, double-click it, click it and type."]

    def record(self, event):
        detail = event.key or (f"{event.dx:+.0f}, {event.dy:+.0f}" if event.type == "drag" else "")
        self.log = [f"{event.type} {detail}".strip(), *self.log][:9]

    def move(self, event):
        if not self.pinned:
            x, y = self.note
            self.note = (x + event.dx, y + event.dy)

    def view(self):
        t = self.resolved_theme()
        form = ui.card(pz.column([
            ui.field("Rating", Rating(value=self.rating, on_change=lambda e: setattr(self, "rating", e.value))),
            ui.label(f"{self.rating} of 5", color="text_muted", size="sm"),
            ui.label("Tags"),
            TagInput(
                tags=self.tags,
                on_add=lambda e: setattr(self, "tags", [*self.tags, e.value]),
                on_remove=lambda e: setattr(self, "tags", [x for x in self.tags if x != e.value]),
            ),
        ], spacing=14), title="Components", width=320)

        note = pz.container(
            pz.column([
                pz.row([pz.icon("pin" if self.pinned else "grip", size=14, color=t.text_muted),
                        ui.label("Pinned" if self.pinned else "Drag me", weight="semibold")], spacing=6, align="center"),
                ui.label("Double-click to pin", size="sm", color="text_muted"),
            ], spacing=4),
            width=180, padding=12, bg=t.elevated, border_color=t.accent if self.pinned else t.border, border_width=1,
            radius=t.radius,
        ).on(
            drag=self.move, drag_end=self.record, double_click=lambda: setattr(self, "pinned", not self.pinned),
            click=self.record, key_down=self.record, focus=self.record, blur=self.record,
            cursor="pointer" if self.pinned else "grab",
        )

        log = ui.card(pz.column([ui.label(line, mono=True, size="sm") for line in self.log], spacing=2),
                      title="Event log", width=320)
        x, y = self.note
        canvas = pz.stack([
            pz.container(width="fill", height="fill"),
            pz.pin(note, x=x, y=y),
        ], width="fill", height="fill")
        return pz.row([pz.column([form, log], spacing=16), canvas], spacing=24, padding=24)


if __name__ == "__main__":
    pz.run(Demo)
