"""The Pyzed window: a desktop client for the heroes API in main.py, written with httpx.

It only knows the API's URLs and JSON, so it works the same whether the API runs in another
process, in a thread of this one or in-process without a network (see client.py,
embedded.py and in_process.py).
"""

from __future__ import annotations

import webbrowser
from typing import Callable

import httpx

import pyzed as pz
from pyzed import ui

EMPTY = {"name": "", "secret_name": "", "age": ""}


class HeroesWindow(pz.App):
    title = "Heroes · FastAPI"
    size = (980, 620)

    def __init__(self, make_client: Callable[[], httpx.AsyncClient], mode: str, docs_url: str | None = None):
        self.make_client = make_client  # called once, inside a coroutine, so the client lives on Pyzed's loop
        self.client: httpx.AsyncClient | None = None
        self.mode, self.docs_url = mode, docs_url
        self.heroes: list[dict] = []
        self.selected: dict | None = None  # the hero being edited, or None for a new one
        self.draft = dict(EMPTY)
        self.errors: dict[str, str] = {}
        self.status = "Connecting…"

    # -- the API, with httpx --------------------------------------------------------------
    async def api(self, method: str, url: str, **kwargs) -> httpx.Response | str:
        """Sends a request; returns the response, or the error text when the API can't be reached."""
        if self.client is None:
            self.client = self.make_client()
        try:
            return await self.client.request(method, url, **kwargs)
        except httpx.HTTPError as error:
            return f"Can't reach the API: {error or type(error).__name__}"

    async def load(self):
        response = await self.api("GET", "/heroes/", params={"limit": 100})  # GET /heroes/?offset=0&limit=100
        if isinstance(response, str):
            return ("offline", response)
        return ("loaded", response.json())

    async def save(self):
        body = {key: value for key, value in self.draft.items() if value != ""}  # leave empty fields out
        if self.selected is None:
            response = await self.api("POST", "/heroes/", json=body)
        else:
            response = await self.api("PATCH", f"/heroes/{self.selected['id']}", json=body)
        if isinstance(response, str):
            return ("offline", response)
        if response.status_code == 422:  # FastAPI's validation error, one entry per field
            return ("invalid", response.json())
        response.raise_for_status()
        return ("saved", response.json())

    async def delete(self):
        response = await self.api("DELETE", f"/heroes/{self.selected['id']}")
        if isinstance(response, str):
            return ("offline", response)
        return ("deleted", self.selected["id"])

    # -- state -----------------------------------------------------------------------------
    def on_start(self):
        return self.load()

    def pick(self, hero: dict | None):
        self.selected, self.errors = hero, {}
        self.draft = dict(EMPTY) if hero is None else {
            "name": hero["name"], "secret_name": "", "age": "" if hero["age"] is None else str(hero["age"])}

    def edit(self, key: str):
        return lambda value: self.draft.__setitem__(key, value)

    def update(self, message):
        kind, value = message
        if kind == "loaded":
            self.heroes, self.status = value, f"{len(value)} heroes · {self.mode}"
        elif kind == "offline":
            self.status = value
        elif kind == "invalid":
            self.errors = pz.validation_errors(value)
        elif kind == "saved":
            self.pick(value)
            return self.load()
        elif kind == "deleted":
            self.pick(None)
            return self.load()

    # -- view --------------------------------------------------------------------------------
    def form(self):
        e = self.errors.get
        new = self.selected is None
        return pz.column([
            ui.heading("New hero" if new else f"Hero #{self.selected['id']}", level=3),
            ui.field("Name", ui.input(self.draft["name"], self.edit("name"), placeholder="Deadpond", width=220),
                     error=e("name")),
            ui.field("Secret name", ui.input(self.draft["secret_name"], self.edit("secret_name"),
                                             placeholder="Dive Wilson" if new else "unchanged", width=220),
                     description="Never sent back by the API", error=e("secret_name")),
            ui.field("Age", ui.input(self.draft["age"], self.edit("age"), placeholder="optional", width=220),
                     error=e("age")),
            pz.row([
                None if new else ui.button("Delete", self.delete, icon="trash-2", variant="ghost", tint="error"),
                pz.hspace(),
                ui.button("New", lambda: self.pick(None), variant="ghost") if not new else None,
                ui.button("Create" if new else "Save", self.save, icon="check", variant="solid"),
            ], spacing=8),
        ], spacing=14, padding=16, width=380)

    def view(self):
        t = self.resolved_theme()
        columns = [ui.Column("ID", "id", width=50), ui.Column("Name", "name"),
                   ui.Column("Age", lambda h: "—" if h["age"] is None else h["age"], width=70, align="end")]
        table = ui.table(columns, self.heroes, on_row_press=self.pick, selected=self.selected, height="fill")
        offline = self.status.startswith("Can't")
        status = ui.status_bar(
            [ui.status_item(self.status, icon="cloud-off" if offline else "server",
                            icon_color="error" if offline else "success")],
            [ui.status_item("API docs", lambda: webbrowser.open(self.docs_url), icon="book-open")] if self.docs_url else [],
        )
        body = pz.row([pz.container(table, padding=16, width="fill", height="fill"),
                       pz.container(self.form(), height="fill", bg=t.panel)])
        return pz.container(pz.column([body, status]), width="fill", height="fill", bg=t.editor)
