import pyzed as pz
from pyzed import ui

title = "Home"


def page():
    return pz.column([
        ui.heading("Welcome to the store"),
        ui.label("Every screen of this app is a folder of app/, like the pages of a Next.js site.",
                 color="text_muted"),
        pz.row([
            ui.button("Browse products", lambda: pz.use_router().push("/products"), variant="solid"),
            ui.button("A missing page", lambda: pz.use_router().push("/nowhere")),
            ui.button("Product 42 (doesn't exist)", lambda: pz.use_router().push("/products/42")),
        ], spacing=8),
        pz.link("/docs/guide/routing", "Read how routing works →"),
    ], spacing=16)
