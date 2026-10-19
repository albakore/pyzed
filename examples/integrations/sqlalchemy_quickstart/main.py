"""SQLAlchemy's ORM Quick Start in a Pyzed window: users and their email addresses.

    uv run main.py            # sync Session, run in worker threads (sync_backend.py)
    uv run main.py --async    # AsyncSession on Pyzed's asyncio loop (async_backend.py)

Both backends have the same functions and the window doesn't care which one it gets:
Command.perform runs a regular function in a thread and a coroutine on the loop.
Walkthrough: https://albakore.github.io/pyzed/integrations/sqlalchemy/
"""

from __future__ import annotations

import sys

import pyzed as pz
from pyzed import Command, ui

if "--async" in sys.argv:
    import async_backend as backend
else:
    import sync_backend as backend


class Quickstart(pz.App):
    title = "Users · SQLAlchemy"
    size = (900, 560)

    def __init__(self):
        self.users = []
        self.selected_id: int | None = None
        self.new_user = {"name": "", "fullname": ""}
        self.new_email = ""
        self.editing: tuple[int, str] | None = None  # (address id, text being typed)
        self.errors: dict[str, str] = {}

    # -- database ----------------------------------------------------------------------------
    def on_start(self):
        return Command.perform(backend.setup, lambda _: self.reload())

    def reload(self):
        return Command.perform(backend.users, self.loaded)

    def loaded(self, users):
        self.users = users
        if self.selected_id not in {u.id for u in users}:
            self.selected_id = users[0].id if users else None

    def run(self, work):
        """Runs a backend call, then reloads. ``work`` is a lambda, so its arguments are read now."""
        return Command.perform(work, lambda _: self.reload())

    # -- actions -------------------------------------------------------------------------------
    def add_user(self, *_):
        name, fullname = self.new_user["name"].strip(), self.new_user["fullname"].strip()
        self.errors = {"name": "Required"} if not name else {"name": "30 characters at most"} if len(name) > 30 else {}
        if self.errors:
            return None
        self.new_user = {"name": "", "fullname": ""}
        return self.run(lambda: backend.add_user(name, fullname))

    def add_address(self, *_):
        email, self.new_email = self.new_email.strip(), ""
        user_id = self.selected_id
        return self.run(lambda: backend.add_address(user_id, email)) if "@" in email else None

    def save_address(self, *_):
        address_id, email = self.editing
        self.editing = None
        return self.run(lambda: backend.rename_address(address_id, email.strip()))

    def delete_user(self):
        user_id = self.selected_id
        return self.run(lambda: backend.delete_user(user_id))

    # -- view ----------------------------------------------------------------------------------
    def sidebar(self, t):
        rows = [ui.list_item(u.name, lambda u=u: setattr(self, "selected_id", u.id), icon="user",
                             end=ui.count_badge(len(u.addresses), tint="text_muted") if u.addresses else None,
                             selected=u.id == self.selected_id, inset=True, height=30) for u in self.users]
        form = pz.column([
            ui.input(self.new_user["name"], lambda v: self.new_user.__setitem__("name", v), placeholder="name",
                     on_submit=self.add_user),
            ui.label(self.errors["name"], size="sm", color="error") if self.errors.get("name") else None,
            ui.input(self.new_user["fullname"], lambda v: self.new_user.__setitem__("fullname", v),
                     placeholder="Full name (optional)", on_submit=self.add_user),
            ui.button("Add user", self.add_user, icon="user-plus", full_width=True),
        ], spacing=6)
        return pz.container(pz.column([ui.muted("user_account", size="xs", mono=True), *rows, pz.vspace(), form],
                                      spacing=2), padding=8, width=260, height="fill", bg=t.panel)

    def address_row(self, address):
        if self.editing and self.editing[0] == address.id:
            return pz.row([
                ui.input(self.editing[1], lambda v: setattr(self, "editing", (address.id, v)), on_submit=self.save_address),
                ui.icon_button("check", self.save_address, tooltip="Save"),
            ], spacing=6, align="center")
        return ui.list_item(address.email_address, lambda: setattr(self, "editing", (address.id, address.email_address)),
                            icon="mail", end=ui.muted("click to edit", size="sm"), inset=True, height=30)

    def detail(self):
        user = next((u for u in self.users if u.id == self.selected_id), None)
        if user is None:
            return ui.empty_state("No users", "Add one on the left.", icon="users")
        return pz.column([
            pz.row([ui.heading(user.fullname or user.name, level=2), pz.hspace(),
                    ui.button("Delete user", self.delete_user, icon="trash-2", variant="ghost", tint="error")],
                   align="center"),
            ui.muted(repr(user), mono=True, size="sm"),
            ui.label("Addresses", weight="semibold"),
            *[self.address_row(a) for a in user.addresses],
            pz.row([ui.input(self.new_email, lambda v: setattr(self, "new_email", v), placeholder="new@sqlalchemy.org",
                             icon="mail-plus", on_submit=self.add_address),
                    ui.button("Add", self.add_address)], spacing=6),
        ], spacing=10, padding=24)

    def view(self):
        t = self.resolved_theme()
        mode = "AsyncSession · aiosqlite" if backend.__name__ == "async_backend" else "Session · worker threads"
        return pz.column([
            pz.row([self.sidebar(t), pz.container(self.detail(), width="fill", height="fill", bg=t.editor)]),
            ui.status_bar([ui.status_item(mode, icon="database", icon_color="success")]),
        ])


if __name__ == "__main__":
    pz.run(Quickstart)
