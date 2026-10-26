"""A form builder: drag fields from the palette into the form, reorder them by their handle,
select one to edit it and see the finished form live.

    python examples/dnd/form_builder.py

Walkthrough: https://albakore.github.io/pyzed/dnd/tutorials/form-builder/
"""

from itertools import count

import pyzed as pz
from pyzed import ui

_ids = count(1)

# The palette: what each kind of field looks like and its defaults.
KINDS = {
    "text": ("type", "Text", "Your name"),
    "email": ("at-sign", "Email", "you@example.com"),
    "number": ("hash", "Number", "0"),
    "check": ("square-check", "Checkbox", "I agree"),
    "choice": ("list", "Choice", "Small, Medium, Large"),
    "note": ("align-left", "Paragraph", "Tell us more"),
}


def new_field(kind):
    icon, label, hint = KINDS[kind]
    return {"id": f"field-{next(_ids)}", "kind": kind, "label": label, "hint": hint, "required": False}


class FormBuilder(pz.App):
    title = "Form builder"
    size = (1100, 640)

    def __init__(self):
        self.fields = [new_field("text"), new_field("email")]
        self.selected = self.fields[0]["id"]
        self.values = {}

    # -- drops ---------------------------------------------------------------
    def drop(self, event):
        if event.from_list == "palette":
            field = new_field(event.data)       # a palette item is a template: make a new field
            self.fields.insert(event.index, field)
            self.selected = field["id"]
        else:
            pz.dnd.move(self.fields, event)

    def remove(self, event):
        self.fields = [f for f in self.fields if f["id"] != event.source]

    def field(self):
        return next((f for f in self.fields if f["id"] == self.selected), None)

    def edit(self, key, value):
        field = self.field()
        if field is not None:
            field[key] = value

    # -- view ----------------------------------------------------------------
    def palette_item(self, kind):
        t = pz.theme.current()
        icon, label, _ = KINDS[kind]
        return pz.container(pz.row([pz.icon(icon, color=t.accent), ui.label(label)], spacing=8, align="center"),
                            padding=10, width="fill").style(background=t.elevated, radius=8, border_color=t.border,
                                                            border_width=1)

    def editor_item(self, field):
        t = pz.theme.current()
        icon, kind, _ = KINDS[field["kind"]]
        selected = field["id"] == self.selected
        row = pz.row([
            pz.drag_handle(pz.icon("grip-vertical", color=t.text_muted)),
            pz.icon(icon, color=t.accent),
            pz.column([ui.label(field["label"], weight="bold"), ui.muted(f"{kind} · {field['hint']}")], spacing=2,
                      width="fill"),
            ui.badge("required", tint="warning", size="sm") if field["required"] else pz.space(),
        ], spacing=10, align="center")
        return pz.container(row, padding=12, width="fill").style(
            background=t.elevated, radius=8, border_width=1.5 if selected else 1,
            border_color=t.accent if selected else t.border,
        ).on(click=lambda f=field: setattr(self, "selected", f["id"]))

    def preview_field(self, field):
        kind, value = field["kind"], self.values.get(field["id"], "")
        setter = lambda v, f=field: self.values.__setitem__(f["id"], v)  # noqa: E731
        title = field["label"] + (" *" if field["required"] else "")
        if kind == "check":
            return ui.checkbox(bool(value), setter, label=field["hint"])
        if kind == "choice":
            options = [o.strip() for o in field["hint"].split(",") if o.strip()]
            return ui.field(title, ui.select(options, value or None, setter))
        return ui.field(title, ui.input(value, setter, placeholder=field["hint"]))

    def inspector(self):
        field = self.field()
        if field is None:
            return ui.muted("Select a field to edit it")
        return pz.column([
            ui.heading("Field", level=3),
            ui.field("Label", ui.input(field["label"], lambda v: self.edit("label", v))),
            ui.field("Hint", ui.input(field["hint"], lambda v: self.edit("hint", v))),
            ui.switch(field["required"], lambda v: self.edit("required", v), label="Required"),
        ], spacing=12)

    def view(self):
        t = pz.theme.current()
        palette = pz.sortable(
            items=list(KINDS), item=self.palette_item, key=lambda k: f"palette-{k}", id="palette",
            group="fields", pull="clone", sort=False, spacing=6, placeholder="none",
        )
        form = pz.sortable(
            items=self.fields, item=self.editor_item, id="form", group="fields", handle=True,
            spacing=8, padding=12, height="fill", on_reorder=self.drop,
            over_style={"background": pz.theme.alpha(t.accent, 0.04), "radius": 10},
        )
        trash = pz.droppable(
            pz.container(pz.row([pz.icon("trash-2"), ui.label("Remove")], spacing=6), padding=10, width="fill",
                         align_x="center").style(border_color=t.border, border_width=1, radius=8),
            "trash", accepts="fields", can_drop=lambda e: e.from_list == "form", on_drop=self.remove,
        )
        left = pz.column([ui.label("Fields", weight="bold"), palette, pz.space(height="fill"), trash], spacing=10,
                         width=200, padding=12)
        middle = pz.container(pz.scrollable(form, height="fill"), width="fill", height="fill").style(
            background=t.surface, radius=12)
        preview = pz.container(
            pz.column([ui.heading("Preview", level=3), *[self.preview_field(f) for f in self.fields],
                       ui.button("Submit", variant="solid")], spacing=12),
            padding=16, width=300).style(background=t.surface, radius=12)
        right = pz.column([pz.container(self.inspector(), padding=16).style(background=t.surface, radius=12),
                           pz.scrollable(preview, height="fill")], spacing=12, width=320)
        return pz.row([left, middle, right], spacing=14, padding=14)


if __name__ == "__main__":
    FormBuilder().run()
