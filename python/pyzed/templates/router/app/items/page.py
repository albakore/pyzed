"""/items: the data comes from `load`, which runs in the background (loading.py shows meanwhile)."""

import asyncio

import pyzed as pz
from pyzed import ui

title = "Items"

ITEMS = {"1": "First item", "2": "Second item", "3": "Third item"}


async def load():
    await asyncio.sleep(0.3)  # an API call, a database query...
    return ITEMS


def page(data):
    return pz.column([
        ui.heading("Items"),
        *[pz.link(f"/items/{key}", name) for key, name in data.items()],
    ], spacing=10)
