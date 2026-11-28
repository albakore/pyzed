"""/docs, /docs/guide, /docs/guide/routing...: an optional catch-all takes any number of parts."""

import pyzed as pz
from pyzed import ui

PAGES = {(): "Introduction", ("guide",): "Guide", ("guide", "routing"): "Routing"}


def title(params):
    return PAGES.get(tuple(params["slug"]), "Docs")


def page(params):
    slug = params["slug"]  # a list: [] for /docs
    if tuple(slug) not in PAGES:
        pz.not_found()
    crumbs = ["docs", *slug]
    return pz.column([
        ui.breadcrumbs(crumbs, on_press=lambda i: pz.use_router().push("/" + "/".join(crumbs[:i + 1]))),
        ui.heading(PAGES[tuple(slug)]),
        pz.column([pz.link("/docs/" + "/".join(k), PAGES[k]) for k in PAGES if k != tuple(slug)], spacing=6),
    ], spacing=16)
