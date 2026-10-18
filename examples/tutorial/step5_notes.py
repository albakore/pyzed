"""Tutorial, step 5: a small notes app that puts it all together.

    python examples/tutorial/step5_notes.py

A list of notes, a code editor with a live Markdown preview in a resizable split,
a command (ctrl-n) and a separate "About" window.
"""

import pyzed as pz
from pyzed import ui


class About(pz.Window):
    title = "About Notes"
    size = (320, 180)
    resizable = False

    def view(self):
        return pz.container(pz.column([ui.heading("Notes", level=3), ui.muted("Built with Pyzed."),
                                       ui.button("Close", self.close)], spacing=10),
                            padding=20, width="fill", height="fill", bg=self.resolved_theme().background)


class Notes(pz.App):
    title = "Notes"
    size = (1000, 640)

    def __init__(self):
        self.notes = {"Welcome": "# Welcome\n\nWrite **Markdown** on the left.", "Ideas": "- One\n- Two"}
        self.current = "Welcome"
        self.ratio = 0.5

    def new_note(self):
        name = f"Note {len(self.notes) + 1}"
        self.notes[name] = f"# {name}\n"
        self.current = name

    def on_key(self, combo):
        if combo == "ctrl-n":
            self.new_note()

    def view(self):
        t = self.resolved_theme()
        sidebar = pz.container(
            pz.column([
                pz.row([ui.label("Notes", weight="semibold"), pz.hspace(),
                        ui.icon_button("plus", self.new_note, tooltip="New note (ctrl-n)"),
                        ui.icon_button("info", lambda: About().open(), tooltip="About")], align="center"),
                *[ui.list_item(name, lambda n=name: setattr(self, "current", n), icon="file-text",
                               selected=name == self.current) for name in self.notes],
            ], spacing=2),
            padding=8, width=220, height="fill", bg=t.panel,
        )
        # The editor's id is the note name, so each note keeps its own cursor and undo history.
        editor = ui.editor(self.current, self.notes[self.current], language="md", wrap=True,
                           on_change=lambda text: self.notes.__setitem__(self.current, text))
        preview = pz.container(pz.scrollable(pz.container(ui.markdown(self.notes[self.current]), padding=20),
                                             height="fill"), width="fill", height="fill", bg=t.background)
        return pz.row([sidebar, ui.split(editor, preview, ratio=self.ratio,
                                         on_resize=lambda r: setattr(self, "ratio", r))])


if __name__ == "__main__":
    pz.run(Notes)
