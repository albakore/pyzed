"""/items/1, /items/2...: `params["id"]` is the part of the address."""

import pyzed as pz
from pyzed import ui

ITEMS = {"1": "First item", "2": "Second item", "3": "Third item"}


def load(params):
    if params["id"] not in ITEMS:
        pz.not_found()
    return ITEMS[params["id"]]


def title(data):
    return data


def page(data, params):
    return pz.column([
        pz.link("/items", "← All items"),
        ui.heading(data),
        ui.label(f"This is /items/{params['id']}.", color="text_muted"),
    ], spacing=12)
