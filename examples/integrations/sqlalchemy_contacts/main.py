"""A contacts manager on SQLAlchemy 2.0: 20,000 rows in a virtual table, searched and sorted in SQL.

    uv run main.py

The database (contacts.db) is created next to this file on the first run.
Walkthrough: https://albakore.github.io/pyzed/integrations/sqlalchemy/
"""

from __future__ import annotations

import pyzed as pz
from pyzed import Command, ui

import db

FIELDS = [("name", "Name", "Ada Lovelace"), ("email", "Email", "ada@example.com"),
          ("company", "Company", "Analytical Engines"), ("city", "City", "London")]


class Contacts(pz.App):
    title = "Contacts · SQLAlchemy"
    size = (1180, 720)

    def __init__(self):
        self.rows: list[db.Contact] = []
        self.stats = {"total": 0, "companies": 0, "cities": []}
        self.query = ""
        self.sort, self.descending = "Name", False
        self.loading = True
        self.editing = None            # a Contact, "new" or None
        self.draft: dict[str, str] = {}
        self.errors: dict[str, str] = {}

    # -- database work runs in a thread with Command.perform ------------------------------
    def on_start(self):
        return Command.perform(db.setup, lambda _: self.reload())

    def reload(self):
        self.loading = True
        query, sort, descending = self.query, self.sort, self.descending
        return [
            Command.perform(lambda: db.search(query, sort, descending), lambda rows: self.loaded(query, rows)),
            Command.perform(db.stats, lambda stats: setattr(self, "stats", stats)),
        ]

    def loaded(self, query: str, rows: list[db.Contact]):
        if query == self.query:  # a newer search is on its way: keep waiting for it
            self.rows, self.loading = rows, False

    def search(self, text: str):
        self.query = text
        return self.reload()

    def sort_by(self, title: str):
        self.descending = not self.descending if title == self.sort else False
        self.sort = title
        return self.reload()

    # -- the edit panel ------------------------------------------------------------------
    def open(self, contact):
        self.editing, self.errors = contact, {}
        self.draft = {key: "" if contact == "new" else getattr(contact, key) for key, _, _ in FIELDS}

    def save(self):
        contact_id = None if self.editing == "new" else self.editing.id
        values = dict(self.draft)
        return Command.perform(lambda: db.save(contact_id, values), self.saved)

    def saved(self, result):
        if isinstance(result, dict):
            self.errors = result
            return None
        self.editing = None
        return self.reload()

    def delete(self):
        contact_id = self.editing.id
        self.editing = None
        return Command.perform(lambda: db.delete(contact_id), lambda _: self.reload())

    def on_key(self, combo):
        if combo == "escape":
            self.editing = None
        elif combo == "ctrl-n":
            self.open("new")

    # -- view ----------------------------------------------------------------------------
    def header(self):
        cities = self.stats["cities"]
        return pz.row([
            ui.stat("Contacts", f"{self.stats['total']:,}"),
            ui.stat("Companies", self.stats["companies"]),
            ui.card(pz.column([ui.muted("Top cities", size="sm"),
                               ui.bar_chart([count for _, count in cities], labels=[c.split()[0] for c, _ in cities],
                                            width=360, height=90)], spacing=6)),
        ], spacing=12)

    def panel(self, t):
        if self.editing is None:
            return None
        rows = [ui.field(title, ui.input(self.draft[key], lambda v, k=key: self.draft.__setitem__(k, v),
                                         placeholder=hint, width=220),
                         error=self.errors.get(key))
                for key, title, hint in FIELDS]
        new = self.editing == "new"
        return pz.container(
            pz.column([
                pz.row([ui.heading("New contact" if new else "Edit contact", level=3), pz.hspace(),
                        ui.icon_button("x", lambda: setattr(self, "editing", None), tooltip="Close (Esc)")],
                       align="center"),
                *rows,
                pz.row([None if new else ui.button("Delete", self.delete, icon="trash-2", variant="ghost", tint="error"),
                        pz.hspace(), ui.button("Save", self.save, icon="check", variant="solid")], spacing=8),
            ], spacing=14),
            padding=16, width=420, height="fill", bg=t.panel,
        )

    def view(self):
        t = self.resolved_theme()
        columns = [
            ui.Column("Name", "name", width="fill:3"),
            ui.Column("Email", "email", width="fill:3"),
            ui.Column("Company", "company", width="fill:2"),
            ui.Column("City", "city", width="fill:2"),
        ]
        toolbar = pz.row([
            ui.search_input(self.query, self.search, placeholder="Search by name, email or company…", width=360),
            ui.spinner() if self.loading else ui.muted(f"{len(self.rows):,} found", size="sm"),
            pz.hspace(),
            ui.button("New contact", lambda: self.open("new"), icon="user-plus", keys="ctrl-n"),
        ], spacing=10, align="center")
        # Rows come sorted from SQL; sort_by only draws the arrow (re-sorting a sorted list is cheap).
        table = ui.table(columns, self.rows, sort_by=self.sort, descending=self.descending, on_sort=self.sort_by,
                         on_row_press=self.open, selected=self.editing, striped=True, height="fill")
        main = pz.column([self.header(), toolbar, table], spacing=14, padding=16)
        return pz.container(pz.row([main, self.panel(t)]), width="fill", height="fill", bg=t.editor)


if __name__ == "__main__":
    pz.run(Contacts)
