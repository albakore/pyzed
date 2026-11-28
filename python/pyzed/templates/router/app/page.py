"""/ : the home page."""

import pyzed as pz
from pyzed import ui

title = "Home"


def page():
    return pz.column([
        ui.heading("Welcome"),
        ui.label("Each folder of app/ is a page. Edit app/page.py and save to see it change.", color="text_muted"),
        pz.link("/items", "See the items →"),
    ], spacing=12)
