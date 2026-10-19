"""Architecture 3, in process: the window calls the FastAPI app directly, with no server or port.

    uv run in_process.py

httpx can send requests straight to an ASGI app (httpx.ASGITransport), so the same API code
and the same client code run inside one desktop program that works offline. Nothing listens
on the network. ASGITransport doesn't send startup events, so the tables are created here.
"""

import httpx

import pyzed as pz

from heroes_window import HeroesWindow
from main import app, create_db_and_tables

if __name__ == "__main__":
    create_db_and_tables()
    transport = httpx.ASGITransport(app=app)
    pz.run(HeroesWindow(lambda: httpx.AsyncClient(transport=transport, base_url="http://heroes"), mode="in process"))
