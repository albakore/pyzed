"""Talking to the user: validation messages, a confirmation dialog and toast notifications.

    python examples/tutorial/feedback.py

- ``ui.field(..., error=...)`` shows a message under a field; the errors are computed from the state.
- ``ui.dialog_layer(page, dialog)`` puts a dialog (``ui.confirm``, ``ui.alert``...) over the page;
  ``dialog`` is ``None`` when nothing is open.
- ``ui.toasts(page, [...])`` stacks notifications in the corner; ``Command.perform`` waits a few
  seconds in the background and then removes them.

Walkthrough: https://albakore.github.io/pyzed/tutorials/intermediate/dialogs-feedback/
"""

import itertools
import time

import pyzed as pz
from pyzed import ui

_ids = itertools.count()


class Signup(pz.App):
    title = "Create an account"
    size = (640, 560)

    def __init__(self):
        self.name = ""
        self.email = ""
        self.password = ""
        self.tried = False   # show errors only after the first try
        self.confirming = False
        self.notes = []      # (id, kind, title, text) of the visible toasts

    # -- validation -----------------------------------------------------------------------
    def errors(self):
        found = {}
        if not self.name.strip():
            found["name"] = "Tell us your name."
        if "@" not in self.email or "." not in self.email.split("@")[-1]:
            found["email"] = "Enter an email such as ada@example.com."
        if len(self.password) < 8:
            found["password"] = "At least 8 characters."
        return found

    # -- toasts ---------------------------------------------------------------------------
    def notify(self, kind, title, text=""):
        note_id = next(_ids)
        self.notes.append((note_id, kind, title, text))
        # wait 4 seconds in a background thread, then remove it (the window never freezes)
        return pz.Command.perform(lambda: time.sleep(4), lambda _: self.dismiss(note_id))

    def dismiss(self, note_id):
        self.notes = [n for n in self.notes if n[0] != note_id]

    # -- actions --------------------------------------------------------------------------
    def submit(self):
        self.tried = True
        if self.errors():
            return self.notify("error", "Check the form", "Some fields need your attention.")
        self.confirming = True  # open the dialog

    def create(self):
        self.confirming = False
        name = self.name
        self.name = self.email = self.password = ""
        self.tried = False
        return self.notify("success", "Account created", f"Welcome, {name}!")

    # -- view -----------------------------------------------------------------------------
    def view(self):
        t = self.resolved_theme()
        errors = self.errors() if self.tried else {}
        form = pz.column([
            ui.heading("Create an account", level=2),
            ui.muted("Leave a field empty and press the button to see the messages."),
            ui.field("Name", ui.input(self.name, lambda v: setattr(self, "name", v), placeholder="Ada Lovelace"),
                     error=errors.get("name")),
            ui.field("Email", ui.input(self.email, lambda v: setattr(self, "email", v), icon="mail",
                                       placeholder="ada@example.com"), error=errors.get("email")),
            ui.field("Password", ui.input(self.password, lambda v: setattr(self, "password", v), secure=True,
                                          on_submit=self.submit), error=errors.get("password"),
                     description="8 characters or more"),
            pz.row([pz.hspace(), ui.button("Create account", self.submit, variant="solid", icon="user-plus")]),
        ], spacing=14, padding=28, width="fill")
        page = pz.container(form, width="fill", height="fill", bg=t.background)

        dialog = None
        if self.confirming:
            dialog = ui.confirm(f"Create an account for {self.email}?", self.create,
                                lambda: setattr(self, "confirming", False), title="Almost there",
                                confirm_label="Create")
        page = ui.dialog_layer(page, dialog, on_dismiss=lambda: setattr(self, "confirming", False))
        return ui.toasts(page, [ui.toast(title, text, kind=kind, on_dismiss=lambda i=i: self.dismiss(i))
                                for i, kind, title, text in self.notes])


if __name__ == "__main__":
    pz.run(Signup)
