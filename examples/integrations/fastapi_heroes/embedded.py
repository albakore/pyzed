"""Architecture 2, embedded server: one program starts the API and opens the window.

    uv run embedded.py

The API runs with Uvicorn (the server `fastapi run` and `fastapi dev` use) in a background
thread, so other programs on this computer, a browser at /docs for instance, can use it
while the window is open. It stops when the window closes.
"""

import threading

import httpx
import uvicorn

import pyzed as pz

from heroes_window import HeroesWindow
from main import app

HOST, PORT = "127.0.0.1", 8000


def start_api() -> None:
    # What `fastapi run main.py` does, but in a thread of this process.
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()


if __name__ == "__main__":
    start_api()
    url = f"http://{HOST}:{PORT}"
    pz.run(HeroesWindow(lambda: httpx.AsyncClient(base_url=url, timeout=5), mode=f"embedded at {url}",
                        docs_url=f"{url}/docs"))
