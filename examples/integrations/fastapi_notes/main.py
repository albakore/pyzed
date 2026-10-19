"""A desktop client for a FastAPI REST API: httpx on Pyzed's asyncio loop, 422 errors shown on each field.

    uv run main.py                          # starts the API in a background thread and opens the window
    uv run main.py http://127.0.0.1:8000    # talks to an API that is already running

Walkthrough: https://albakore.github.io/pyzed/integrations/fastapi/
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser

import httpx
import uvicorn

import pyzed as pz
from pyzed import ui

from api import app as api


def serve_in_background() -> str:
    """Runs the FastAPI app with uvicorn in a daemon thread and returns its URL."""
    with socket.socket() as probe:  # ask the OS for a free port
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    return f"http://127.0.0.1:{port}"


def empty_draft() -> dict:
    return {"title": "", "body": "", "tags": ""}


class NotesClient(pz.App):
    title = "Notes · FastAPI"
    size = (1000, 640)

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client: httpx.AsyncClient | None = None  # created on Pyzed's asyncio loop
        self.notes: list[dict] = []
        self.query = ""
        self.selected = None          # a note id, "new" or None
        self.draft = empty_draft()
        self.errors: dict[str, str] = {}
        self.status = "Connecting…"
        self.busy = False
        self.toasts: list[tuple[float, str]] = []

    # -- HTTP: coroutines run on Pyzed's asyncio loop and return a message for update() ----
    async def http(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(base_url=self.base_url, timeout=5)
        return self.client

    async def fetch(self, query: str):
        try:
            response = await (await self.http()).get("/notes", params={"q": query})
            response.raise_for_status()
        except httpx.HTTPError as error:
            return ("offline", str(error) or type(error).__name__)
        return ("loaded", query, response.json())

    async def send(self, note_id, payload: dict):
        client = await self.http()
        try:
            if note_id == "new":
                response = await client.post("/notes", json=payload)
            else:
                response = await client.put(f"/notes/{note_id}", json=payload)
        except httpx.HTTPError as error:
            return ("offline", str(error) or type(error).__name__)
        if response.is_error:  # 422 carries one entry per field; 404 a plain "detail"
            return ("invalid", response.json())
        return ("saved", response.json())

    async def remove(self, note_id: int):
        try:
            (await (await self.http()).delete(f"/notes/{note_id}")).raise_for_status()
        except httpx.HTTPError as error:
            return ("offline", str(error) or type(error).__name__)
        return ("deleted", note_id)

    # -- actions -------------------------------------------------------------------------
    def on_start(self):
        return self.fetch("")

    def search(self, text: str):
        self.query = text
        return self.fetch(text)  # answers that arrive for an older query are dropped in update()

    def open_note(self, note: dict):
        self.selected = note["id"]
        self.draft = {"title": note["title"], "body": note["body"], "tags": ", ".join(note["tags"])}
        self.errors = {}

    def new_note(self):
        self.selected, self.draft, self.errors = "new", empty_draft(), {}

    def edit(self, key: str):
        return lambda value: self.draft.__setitem__(key, value)

    def save(self):
        self.busy = True
        tags = [tag.strip() for tag in self.draft["tags"].split(",") if tag.strip()]
        return self.send(self.selected, {"title": self.draft["title"], "body": self.draft["body"], "tags": tags})

    def delete(self):
        self.busy = True
        return self.remove(self.selected)

    def notify(self, text: str):
        stamp = time.monotonic()
        self.toasts.append((stamp, text))
        threading.Timer(3, pz.post, args=(("dismiss", stamp),)).start()

    def on_key(self, combo):
        if combo == "ctrl-s" and self.selected is not None:
            return self.save()
        if combo == "ctrl-n":
            self.new_note()

    def update(self, message):
        kind, *rest = message
        if kind == "loaded":
            query, notes = rest
            if query == self.query:
                self.notes = notes
                self.status = f"{len(notes)} notes · {self.base_url}"
        elif kind == "offline":
            self.busy, self.status = False, f"Offline: {rest[0]}"
        elif kind == "invalid":
            self.busy, self.errors = False, pz.validation_errors(rest[0])
        elif kind == "saved":
            self.busy = False
            self.open_note(rest[0])
            self.notify(f"Saved “{rest[0]['title']}”")
            return self.fetch(self.query)
        elif kind == "deleted":
            self.busy, self.selected = False, None
            self.notify("Note deleted")
            return self.fetch(self.query)
        elif kind == "dismiss":
            self.toasts = [toast for toast in self.toasts if toast[0] != rest[0]]

    # -- view ----------------------------------------------------------------------------
    def sidebar(self, t):
        def row(note):
            tags = ui.muted(" · ".join(note["tags"]), size="sm") if note["tags"] else None
            return ui.list_item(note["title"], lambda n=note: self.open_note(n), icon="sticky-note",
                                end=tags, selected=note["id"] == self.selected, inset=True, height=30)

        notes = ui.virtual_list(self.notes, row, item_height=30) if self.notes else ui.empty_state(
            "No notes", "Nothing matches your search." if self.query else "Create the first one.", icon="search")
        return pz.container(
            pz.column([
                pz.row([ui.search_input(self.query, self.search, placeholder="Search notes…"),
                        ui.icon_button("plus", self.new_note, tooltip="New note (Ctrl+N)")],
                       spacing=6, align="center"),
                notes,
            ], spacing=8),
            padding=8, width=280, height="fill", bg=t.panel,
        )

    def form(self):
        if self.selected is None:
            return ui.empty_state("Pick a note", "Or press Ctrl+N to write a new one.", icon="sticky-note",
                                  actions=[ui.button("New note", self.new_note, icon="plus")])
        general = self.errors.get("")
        actions = [
            ui.button("Delete", self.delete, icon="trash-2", variant="ghost", tint="error",
                      disabled=self.busy) if self.selected != "new" else None,
            pz.hspace(),
            ui.button("Save", self.save, icon="save", variant="solid", keys="ctrl-s", disabled=self.busy),
        ]
        return pz.column([
            ui.callout("The server refused the note", general, tint="error") if general else None,
            ui.field("Title", ui.input(self.draft["title"], self.edit("title"), placeholder="Untitled", width=380),
                     error=self.errors.get("title")),
            ui.field("Tags", ui.input(self.draft["tags"], self.edit("tags"), placeholder="work, ideas", width=380),
                     description="Separated by commas", error=self.errors.get("tags")),
            ui.editor(f"note-{self.selected}", self.draft["body"], language="md", wrap=True, gutter=False,
                      placeholder="Write Markdown…", on_change=self.edit("body")),
            pz.row([a for a in actions if a is not None], spacing=8, align="center"),
        ], spacing=12, padding=16)

    def view(self):
        t = self.resolved_theme()
        offline = self.status.startswith("Offline")
        body = pz.column([
            pz.row([self.sidebar(t), pz.container(self.form(), width="fill", height="fill", bg=t.editor)],
                   height="fill"),
            ui.status_bar([ui.status_item(self.status, icon="cloud-off" if offline else "server",
                                          icon_color="error" if offline else "success")],
                          [ui.status_item("API docs", lambda: webbrowser.open(f"{self.base_url}/docs"),
                                          icon="book-open")]),
        ])
        return ui.toasts(body, [ui.toast(text, kind="success", on_dismiss=("dismiss", stamp))
                                for stamp, text in self.toasts])


if __name__ == "__main__":
    pz.run(NotesClient(sys.argv[1] if len(sys.argv) > 1 else serve_in_background()))
