"""Architecture 1, client and server: the API runs on its own and the window talks to it over HTTP.

    uv run fastapi dev main.py     # terminal 1: the API (FastAPI's own CLI)
    uv run client.py               # terminal 2: the desktop client
    uv run client.py https://api.example.com   # or any other deployment of main.py

The usual setup when the API also serves a website or a mobile app, or runs on a server.
"""

import sys

import httpx

import pyzed as pz

from heroes_window import HeroesWindow

API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

if __name__ == "__main__":
    pz.run(HeroesWindow(lambda: httpx.AsyncClient(base_url=API, timeout=5), mode=f"server at {API}",
                        docs_url=f"{API}/docs"))
