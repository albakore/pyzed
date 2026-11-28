"""/products: the list comes from an async ``load``; ``?sort=price`` changes the order."""

import pyzed as pz
from pyzed import ui

import store

title = "Products"


async def load(query):
    return await store.products(query.get("sort", "name"))


def page(data, query):
    sort = query.get("sort", "name")
    cards = [
        pz.link(f"/products/{p.id}", ui.card(pz.column([
            pz.icon(p.icon, size=28, color=pz.theme.current().accent),
            ui.label(p.name, weight="semibold"),
            ui.label(f"${p.price:.0f}", color="text_muted"),
        ], spacing=6), width=200))
        for p in data
    ]
    return pz.column([
        pz.row([ui.heading("Products"), pz.hspace(),
                ui.segmented(["name", "price"], sort, lambda s: pz.use_router().replace(f"?sort={s}"))],
               align="center"),
        pz.row(cards, spacing=12, wrap=True),
    ], spacing=16)
