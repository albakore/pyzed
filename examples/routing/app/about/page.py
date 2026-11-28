import pyzed as pz
from pyzed import ui

metadata = {"title": "About"}


def page(router):
    return pz.column([
        ui.heading("About"),
        ui.label("Routes: " + ", ".join(router.routes()), color="text_muted"),
        ui.label(f"History: {len(router.history)} entries", color="text_muted"),
    ], spacing=12)
