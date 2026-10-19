"""A journal on aiosqlite: one async SQLite connection living on Pyzed's asyncio loop.

    uv run main.py

The database (journal.db) is created next to this file on the first run.
Walkthrough: https://albakore.github.io/pyzed/integrations/other-libraries/#aiosqlite
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import aiosqlite

import pyzed as pz
from pyzed import ui

DATABASE = Path(__file__).with_name("journal.db")
MOODS = {"great": ("smile", "success"), "okay": ("meh", "warning"), "rough": ("frown", "error")}


class Journal(pz.App):
    title = "Journal · aiosqlite"
    size = (720, 560)

    def __init__(self):
        self.db: aiosqlite.Connection | None = None  # opened on Pyzed's loop, used only from coroutines
        self.entries: list[aiosqlite.Row] = []
        self.text = ""
        self.mood = "great"

    async def on_start(self):
        self.db = await aiosqlite.connect(DATABASE)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("""CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY, written TEXT NOT NULL, mood TEXT NOT NULL, text TEXT NOT NULL)""")
        await self.db.commit()
        return await self.load()

    async def load(self):
        async with self.db.execute("SELECT * FROM entries ORDER BY id DESC LIMIT 200") as cursor:
            return ("loaded", await cursor.fetchall())

    async def add(self, text: str, mood: str):
        await self.db.execute("INSERT INTO entries (written, mood, text) VALUES (?, ?, ?)",
                              (datetime.now().isoformat(timespec="minutes"), mood, text))
        await self.db.commit()
        return await self.load()

    async def remove(self, entry_id: int):
        await self.db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        await self.db.commit()
        return await self.load()

    def submit(self, *_):
        text, self.text = self.text.strip(), ""
        return self.add(text, self.mood) if text else None

    def update(self, message):
        kind, rows = message
        if kind == "loaded":
            self.entries = rows

    def entry(self, row):
        icon, tint = MOODS[row["mood"]]
        return ui.card(pz.row([
            pz.icon(icon, size=18, color=self.resolved_theme().color(tint)),
            pz.column([ui.label(row["text"]), ui.muted(row["written"].replace("T", " · "), size="sm")],
                      spacing=4, width="fill"),
            ui.icon_button("trash-2", lambda: self.remove(row["id"]), size="sm", tooltip="Delete"),
        ], spacing=12, align="center"), padding=12)

    def view(self):
        t = self.resolved_theme()
        composer = pz.row([
            ui.toggle_group([(mood, icon) for mood, (icon, _) in MOODS.items()], self.mood, lambda m: setattr(self, "mood", m)),
            ui.input(self.text, lambda v: setattr(self, "text", v), placeholder="How was your day? (Enter to save)",
                     on_submit=self.submit),
        ], spacing=8, align="center")
        entries = pz.scrollable(pz.column([self.entry(r) for r in self.entries], spacing=8), height="fill") \
            if self.entries else ui.empty_state("Nothing written yet", "Your entries are stored in journal.db.",
                                                icon="notebook-pen")
        return pz.container(pz.column([ui.heading("Journal", level=2), composer, entries], spacing=14),
                            padding=20, width="fill", height="fill", bg=t.editor)


if __name__ == "__main__":
    pz.run(Journal)
