"""A sign-up form whose rules live in a Pydantic model; accounts are saved to accounts.json.

    uv run main.py

The window keeps what the user types as plain strings and hands them to
``SignUp.model_validate``: Pydantic converts them (a date, an email, a bool), checks every rule
and reports the errors per field, which ``pz.validation_errors`` turns into ``{field: message}``.
Walkthrough: https://albakore.github.io/pyzed/integrations/pydantic/
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

import pyzed as pz
from pyzed import ui

from models import Account, Accounts, SignUp

FILE = Path(__file__).with_name("accounts.json")
EMPTY = {"username": "", "email": "", "birthday": "", "plan": "free", "password": "", "password_repeat": "",
         "newsletter": False}


def load() -> list[Account]:
    return Accounts.validate_json(FILE.read_bytes()) if FILE.exists() else []


class SignUpForm(pz.App):
    title = "Sign up · Pydantic"
    size = (860, 600)

    def __init__(self):
        self.draft = dict(EMPTY)
        self.errors: dict[str, str] = {}
        self.accounts = load()
        self.preview = ""  # the JSON Pydantic produced for the last account

    def edit(self, key):
        return lambda value: self.draft.__setitem__(key, value)

    def submit(self, *_):
        try:
            signup = SignUp.model_validate(self.draft)
        except ValidationError as error:
            self.errors = pz.validation_errors(error)  # the model validator's error has the key ""
            return
        account = Account.model_validate(signup.model_dump(exclude={"password", "password_repeat"}))
        if any(a.username == account.username for a in self.accounts):
            self.errors = {"username": "That username is taken"}
            return
        self.accounts.append(account)
        FILE.write_bytes(Accounts.dump_json(self.accounts, indent=2))
        self.preview = account.model_dump_json(indent=2)
        self.draft, self.errors = dict(EMPTY), {}

    def form(self):
        e, d = self.errors.get, self.draft

        def text(key, title, placeholder="", **kwargs):
            return ui.field(title, ui.input(d[key], self.edit(key), placeholder=placeholder, on_submit=self.submit,
                                            **kwargs), error=e(key))

        return pz.column([
            ui.heading("Create an account", level=2),
            text("username", "Username", "lowercase letters, digits and _"),
            text("email", "Email", "you@example.com"),
            text("birthday", "Birthday", "YYYY-MM-DD"),
            ui.field("Plan", ui.segmented(["free", "pro", "team"], d["plan"], self.edit("plan"))),
            text("password", "Password", "8 characters or more", secure=True),
            text("password_repeat", "Repeat the password", secure=True),
            ui.checkbox(d["newsletter"], self.edit("newsletter"), label="Send me the newsletter"),
            ui.callout(e(""), tint="error") if e("") else None,
            ui.button("Sign up", self.submit, icon="user-plus", variant="solid", full_width=True),
        ], spacing=12, padding=24, width=420)

    def side(self, t):
        rows = [ui.list_item(a.username, None, icon="user", end=ui.badge(a.plan), inset=True, height=30)
                for a in reversed(self.accounts)]
        return pz.container(pz.column([
            ui.muted("accounts.json", size="xs", mono=True),
            *rows,
            ui.card(ui.label(self.preview, mono=True, size="sm"), title="model_dump_json()") if self.preview else None,
        ], spacing=6), padding=16, width="fill", height="fill", bg=t.panel)

    def view(self):
        t = self.resolved_theme()
        return pz.row([pz.container(pz.scrollable(self.form()), height="fill", bg=t.editor), self.side(t)])


if __name__ == "__main__":
    pz.run(SignUpForm)
