"""Concurrent downloads with live progress, after Iced's ``download_progress`` demo.

    python examples/download_progress.py

Each download is an ``async def`` generator: every value it yields goes to ``update``
while it keeps running on Pyzed's asyncio loop, so the UI never blocks. Swap the
simulated transfer for ``aiohttp``/``httpx`` streaming to download real files.
"""

import asyncio
import random

import pyzed as pz
from pyzed import ui


async def download(index, size):
    """Simulates a transfer that sometimes fails; yields ``(index, event, value)``."""
    received = 0
    while received < size:
        await asyncio.sleep(random.uniform(0.02, 0.08))
        received = min(size, received + random.randint(20_000, 120_000))
        if random.random() < 0.004:
            yield index, "failed", "connection reset"
            return
        yield index, "progress", received / size
    yield index, "finished", size


class Download:
    def __init__(self, index):
        self.index = index
        self.size = random.randint(2, 12) * 1_000_000
        self.state = "idle"  # idle | running | finished | failed
        self.progress = 0.0
        self.error = ""


class Downloads(pz.App):
    title = "Downloads"
    size = (560, 520)

    def __init__(self):
        self.downloads = [Download(0)]

    def start(self, item):
        item.state, item.progress = "running", 0.0
        # Returning an async generator runs it in the background.
        return download(item.index, item.size)

    def add(self):
        self.downloads.append(Download(len(self.downloads)))

    def start_all(self):
        return [pz.Command.perform(self.start(d)) for d in self.downloads if d.state != "running"]

    def update(self, message):
        index, event, value = message
        item = self.downloads[index]
        if event == "progress":
            item.progress = value
        elif event == "finished":
            item.state, item.progress = "finished", 1.0
        elif event == "failed":
            item.state, item.error = "failed", value

    def row(self, item):
        t = self.resolved_theme()
        mb = item.size / 1_000_000
        if item.state == "idle":
            status, action = ui.muted(f"{mb:.0f} MB"), ui.button("Start", lambda: self.start(item), size="sm")
        elif item.state == "running":
            status, action = ui.muted(f"{item.progress * mb:.1f} / {mb:.0f} MB"), ui.spinner(size=14)
        elif item.state == "finished":
            status = ui.label("Done", color="success", size="sm")
            action = ui.icon_button("rotate-ccw", lambda: self.start(item), tooltip="Again")
        else:
            status = ui.label(f"Failed: {item.error}", color="error", size="sm")
            action = ui.button("Retry", lambda: self.start(item), size="sm", tint="error")
        return ui.card(pz.column([
            pz.row([ui.label(f"file-{item.index + 1}.bin", weight="medium"), pz.hspace(), status, action],
                   spacing=10, align="center"),
            ui.progress(item.progress, tint="error" if item.state == "failed" else "accent",
                        theme=t),
        ], spacing=8), padding=12)

    def subscriptions(self):
        # Keep the spinners turning while something is downloading.
        busy = any(d.state == "running" for d in self.downloads)
        return [pz.every(1 / 30, lambda: None)] if busy else []

    def view(self):
        t = self.resolved_theme()
        return pz.container(
            pz.column([
                pz.row([ui.heading("Downloads", level=2), pz.hspace(),
                        ui.button("Add", self.add, icon="plus"),
                        ui.button("Start all", self.start_all, icon="download", variant="solid")], spacing=8,
                       align="center"),
                pz.scrollable(pz.column([self.row(d) for d in self.downloads], spacing=8), height="fill"),
            ], spacing=16),
            padding=24, width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(Downloads)
