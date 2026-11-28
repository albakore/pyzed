"""/about"""

import pyzed as pz
from pyzed import ui

title = "About"


def page(router):
    return pz.column([
        ui.heading("About"),
        ui.label("Pages of this app: " + ", ".join(router.routes()), color="text_muted"),
    ], spacing=12)
