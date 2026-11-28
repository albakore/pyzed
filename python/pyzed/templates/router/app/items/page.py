"""/items: the data comes from `load`, which runs in the background (loading.py shows meanwhile)."""

import pyzed as pz
from pyzed import ui

import api

title = "Items"


async def load():
    return await api.items()  # a call to the server: off the UI thread


def page(data):
    return pz.column([
        ui.heading("Items"),
        *[pz.link(f"/items/{key}", name) for key, name in data.items()],
    ], spacing=10)
