"""/products/[id]: ``params["id"]`` is the part of the URL; a product that doesn't exist is a 404."""

import pyzed as pz
from pyzed import ui

import store


async def load(params):
    product = await store.product(params["id"])
    if product is None:
        pz.not_found()  # shows the closest not_found.py
    return product


def title(data):
    return data.name


def page(data):
    return pz.column([
        pz.link("/products", "← All products"),
        pz.row([pz.icon(data.icon, size=40, color=pz.theme.current().accent), ui.heading(data.name)], spacing=12, align="center"),
        ui.label(data.description, color="text_muted"),
        pz.row([ui.badge(f"${data.price:.0f}"), ui.button("Add to cart", lambda: None, variant="solid", icon="shopping-cart")], spacing=12,
               align="center"),
    ], spacing=16)
