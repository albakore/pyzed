"""/products/[id]: ``params["id"]`` is the part of the URL; a product that doesn't exist is a 404."""

import pyzed as pz
from pyzed import ui

import api
from state import cart


async def load(params):
    product = await api.product_or_fail(params["id"])
    if product is None:
        pz.not_found()  # shows the closest not_found.py
    return product


def title(data):
    return data.name


@pz.action(refresh=False)
async def add_to_cart(product):
    """A change on the server, then on the global state; a notification says it worked."""
    await api.place_order([product.id])
    cart.add(product.id)
    pz.notify("Added to your cart", f"{product.name} · ${product.price:.0f}", href="/products",
              actions={"/account": "See account"})


def page(data):
    return pz.column([
        pz.link("/products", "← All products"),
        pz.row([pz.icon(data.icon, size=40, color=pz.theme.current().accent), ui.heading(data.name)], spacing=12,
               align="center"),
        ui.label(data.description, color="text_muted"),
        pz.row([ui.badge(f"${data.price:.0f}"),
                ui.button("Adding…" if add_to_cart.pending else "Add to cart", lambda: add_to_cart(data),
                          variant="solid", icon="shopping-cart", loading=add_to_cart.pending)],
               spacing=12, align="center"),
    ], spacing=16)
