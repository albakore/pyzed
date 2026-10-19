"""A download manager built on httpx's streaming responses, with a live progress bar.

    uv run main.py

It follows httpx's "Monitoring download progress" recipe
(https://www.python-httpx.org/advanced/clients/#monitoring-download-progress), written with
``AsyncClient.stream`` and ``aiter_bytes``. The download is an async generator: every progress
report it yields reaches ``update``, so the window redraws while the bytes arrive.
Files are saved in a ``downloads`` folder next to this file.
Walkthrough: https://albakore.github.io/pyzed/integrations/httpx/
"""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

import pyzed as pz
from pyzed import ui

FOLDER = Path(__file__).with_name("downloads")
EXAMPLE = ("https://files.pythonhosted.org/packages/54/a4/f8188c4f3e07f7737683588210c073478abcb542048cf4ab6fedad0b458a/"
           "numpy-2.1.0.tar.gz")


def size(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024


class Download:
    """One row of the list. ``total`` is None when the server sends no Content-Length."""

    def __init__(self, url: str):
        self.url = url
        self.name = Path(urlsplit(url).path).name or "download"
        self.done, self.total = 0, None
        self.speed = 0.0
        self.state = "waiting"  # waiting, downloading, finished, cancelled or the error text
        self.cancel = False     # set by the Cancel button, read by the loop below


async def download(item: Download):
    """Streams ``item.url`` to disk, yielding ``item`` after every chunk."""
    FOLDER.mkdir(exist_ok=True)
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            async with client.stream("GET", item.url) as response:
                response.raise_for_status()
                length = response.headers.get("Content-Length")
                item.total, item.state = (int(length) if length else None), "downloading"
                with open(FOLDER / item.name, "wb") as file:
                    async for chunk in response.aiter_bytes():
                        if item.cancel:
                            item.state = "cancelled"
                            break
                        file.write(chunk)
                        item.done = response.num_bytes_downloaded
                        item.speed = item.done / max(time.monotonic() - started, 1e-6)
                        yield item
        if item.state == "downloading":
            item.state = "finished"
    except httpx.HTTPStatusError as error:
        item.state = f"The server answered {error.response.status_code}"
    except httpx.HTTPError as error:
        item.state = f"{type(error).__name__}: {error}"
    yield item


class Downloads(pz.App):
    title = "Downloads · httpx"
    size = (760, 480)

    def __init__(self):
        self.url = EXAMPLE
        self.items: list[Download] = []

    def start(self, *_):
        url = self.url.strip()
        if not url.startswith(("http://", "https://")):
            return None
        item = Download(url)
        self.items.insert(0, item)
        return download(item)  # Pyzed runs the generator on its loop and sends each yield to update()

    def update(self, item: Download):
        pass  # the Download object was changed in place; returning from update redraws the window

    def row(self, item: Download):
        t = self.resolved_theme()
        if item.state == "downloading":
            detail = f"{size(item.done)} of {size(item.total) if item.total else '?'} · {size(item.speed)}/s"
            action = ui.icon_button("x", lambda: setattr(item, "cancel", True), tooltip="Cancel")
        elif item.state == "finished":
            detail, action = f"{size(item.done)} · saved in downloads/", None
        else:
            detail, action = item.state.capitalize(), None
        failed = item.state not in ("waiting", "downloading", "finished")
        value = item.done / item.total if item.total else (1.0 if item.state == "finished" else 0.0)
        return ui.card(pz.column([
            pz.row([pz.icon("file-down", size=16, color=t.icon_muted), ui.label(item.name, width="fill"), action],
                   spacing=8, align="center"),
            ui.progress(value, tint="error" if failed else "success" if item.state == "finished" else "accent"),
            ui.muted(detail, size="sm"),
        ], spacing=8), padding=12)

    def view(self):
        t = self.resolved_theme()
        body = pz.scrollable(pz.column([self.row(i) for i in self.items], spacing=8), height="fill") if self.items \
            else ui.empty_state("No downloads", "Paste a URL and press Download.", icon="download")
        return pz.container(pz.column([
            pz.row([ui.input(self.url, lambda v: setattr(self, "url", v), icon="link", on_submit=self.start),
                    ui.button("Download", self.start, icon="download", variant="solid")], spacing=8),
            body,
        ], spacing=14), padding=20, width="fill", height="fill", bg=t.editor)


if __name__ == "__main__":
    pz.run(Downloads)
