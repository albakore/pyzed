"""/items/1, /items/2...: `params["id"]` is the part of the address."""

import pyzed as pz
from pyzed import ui

import api
from state import favorites


async def load(params):
    item = await api.item(params["id"])
    if item is None:
        pz.not_found()
    return item


def title(data):
    return data


@pz.action(on_done=lambda item_id: pz.notify("Saved", f"Item {item_id} is in your favorites", href="/favorites"))
async def save(item_id):
    """Changes data on the server, then updates the global state."""
    await api.save_favorite(item_id)
    favorites.add(item_id)
    return item_id


def page(data, params):
    saved = params["id"] in favorites.ids
    return pz.column([
        pz.link("/items", "← All items"),
        ui.heading(data),
        ui.label(f"This is /items/{params['id']}.", color="text_muted"),
        ui.button("Saved" if saved else "Add to favorites", lambda: save(params["id"]), icon="star",
                  loading=save.pending, disabled=saved),
    ], spacing=12)
