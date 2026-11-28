"""Shown for unknown addresses and when a page calls pz.not_found()."""

import pyzed as pz
from pyzed import ui

title = "Not found"


def not_found(pathname):
    return ui.empty_state("Page not found", f"There is nothing at {pathname}.", icon="map-pin-off",
                          actions=[ui.button("Go home", lambda: pz.use_router().push("/"))])
