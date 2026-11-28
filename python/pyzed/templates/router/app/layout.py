"""Wraps every page (a layout keeps its state while you navigate)."""

import pyzed as pz
from pyzed import ui

title_template = "%s · {name}"


def layout(children):
    sidebar = pz.column([
        ui.label("{name}", weight="semibold"),
        pz.nav_link("/", "Home", icon="house"),
        pz.nav_link("/items", "Items", icon="list"),
        pz.nav_link("/about", "About", icon="info"),
    ], spacing=4, padding=12, width=200)
    page = pz.scrollable(pz.container(children, padding=24, width="fill"), height="fill")
    return pz.row([sidebar, ui.divider(vertical=True), page], height="fill").style(background="background")
