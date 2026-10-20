"""Connecting a backend: a contacts app whose data lives in SQLite, behind a small repository class.

    python examples/tutorial/contacts_backend.py

- ``ContactsRepository`` is the backend: plain Python with no UI in it, easy to test and to swap
  for SQLAlchemy, an HTTP API or anything else.
- The window never talks to the database directly: ``Command.perform(work, then)`` runs the query
  in a background thread and hands the result to ``then`` on the UI thread, so the window never
  freezes, even on a slow disk or network.
- A spinner shows while a query runs; errors become a callout instead of a crash.

Walkthrough: https://albakore.github.io/pyzed/tutorials/advanced/backend/
"""

import sqlite3
import tempfile
import time
from pathlib import Path

import pyzed as pz
from pyzed import ui

DEFAULT_DB = Path(tempfile.gettempdir()) / "pyzed-tutorial-contacts.db"


class ContactsRepository:
    """The backend. One connection per call, so it is safe to use from any thread."""

    def __init__(self, path=DEFAULT_DB, delay=0.3):
        self.path = Path(path)
        self.delay = delay  # pretend the database is far away, to see the spinner
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS contacts (id INTEGER PRIMARY KEY, name TEXT, email TEXT)")
            if not db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]:
                db.executemany("INSERT INTO contacts (name, email) VALUES (?, ?)",
                               [("Ada Lovelace", "ada@example.com"), ("Alan Turing", "alan@example.com")])

    def connect(self):
        return sqlite3.connect(self.path)

    def search(self, text=""):
        time.sleep(self.delay)
        with self.connect() as db:
            rows = db.execute("SELECT id, name, email FROM contacts WHERE name LIKE ? OR email LIKE ? ORDER BY name",
                              (f"%{text}%", f"%{text}%")).fetchall()
        return [{"id": i, "name": n, "email": e} for i, n, e in rows]

    def add(self, name, email):
        if not name.strip() or "@" not in email:
            raise ValueError("A contact needs a name and a valid email.")
        time.sleep(self.delay)
        with self.connect() as db:
            db.execute("INSERT INTO contacts (name, email) VALUES (?, ?)", (name.strip(), email.strip()))

    def delete(self, contact_id):
        with self.connect() as db:
            db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))


class Contacts(pz.App):
    title = "Contacts"
    size = (640, 520)

    def __init__(self, repository=None):
        self.repo = repository or ContactsRepository()
        self.contacts = []
        self.query = ""
        self.name = self.email = ""
        self.busy = False
        self.error = None

    # -- talking to the backend ---------------------------------------------------------
    def background(self, work, then=None):
        """Runs ``work()`` in a thread; ``then(result)`` gets the result on the UI thread."""
        self.busy, self.error = True, None

        def guarded():
            try:
                return ("ok", work())
            except Exception as exc:  # noqa: BLE001 - show the problem instead of crashing
                return ("error", str(exc))

        def done(outcome):
            self.busy = False
            kind, value = outcome
            if kind == "error":
                self.error = value
            elif then is not None:
                return then(value)

        return pz.Command.perform(guarded, done)

    def on_start(self):
        return self.reload()

    def reload(self):
        return self.background(lambda: self.repo.search(self.query), self.loaded)

    def loaded(self, contacts):
        self.contacts = contacts

    def search(self, text):
        self.query = text
        return self.reload()

    def add(self):
        name, email = self.name, self.email
        self.name = self.email = ""
        return self.background(lambda: self.repo.add(name, email), lambda _: self.reload())

    def delete(self, contact):
        return self.background(lambda: self.repo.delete(contact["id"]), lambda _: self.reload())

    # -- view ---------------------------------------------------------------------------
    def row(self, contact):
        initials = "".join(part[0] for part in contact["name"].split()[:2])
        return ui.list_item(
            pz.row([ui.label(contact["name"], weight="medium"), ui.muted(contact["email"])], spacing=10),
            None, start=ui.avatar(initials, size=26, index=contact["id"]), height=40,
            end=ui.icon_button("trash-2", lambda: self.delete(contact), size="sm", tooltip="Delete"),
        )

    def view(self):
        t = self.resolved_theme()
        form = pz.row([
            ui.input(self.name, lambda v: setattr(self, "name", v), placeholder="Name"),
            ui.input(self.email, lambda v: setattr(self, "email", v), placeholder="Email", on_submit=self.add),
            ui.button("Add", self.add, variant="solid", icon="plus"),
        ], spacing=8)
        body = (ui.empty_state("No contacts", "Add one above.", icon="users") if not self.contacts else
                pz.scrollable(pz.column([self.row(c) for c in self.contacts], spacing=2), height="fill"))
        return pz.container(pz.column([
            pz.row([ui.heading("Contacts", level=2), pz.hspace(), ui.spinner() if self.busy else None],
                   align="center"),
            ui.search_input(self.query, self.search, placeholder="Search by name or email…"),
            form,
            ui.callout("Could not save", self.error, tint="error") if self.error else None,
            body,
        ], spacing=12), padding=24, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(Contacts)
