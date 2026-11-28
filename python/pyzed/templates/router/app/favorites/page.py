"""/favorites: reads the global store (the middleware sends you to /items while it is empty)."""

import pyzed as pz
from pyzed import ui

import api
from state import favorites

title = "Favorites"


def page():
    return pz.column([
        ui.heading("Favorites"),
        *[pz.link(f"/items/{item_id}", api.ITEMS.get(item_id, item_id)) for item_id in favorites.ids],
        ui.button("Clear", favorites.reset, variant="outline"),
    ], spacing=10)
