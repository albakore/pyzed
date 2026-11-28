"""/account: only reached through the middleware, which hands over the user in `locals`."""

import pyzed as pz
from pyzed import ui

from state import cart, session

title = "Account"


def page(locals):  # noqa: A002 - the name the router passes
    user = locals["user"]
    return pz.column([
        ui.heading(f"Hello, {user['name']}"),
        ui.label(user["email"], color="text_muted"),
        ui.label(f"{cart.count} item(s) in your cart.", color="text_muted"),
        ui.button("Sign out", sign_out, icon="log-out"),
    ], spacing=12)


def sign_out():
    session.reset()
    pz.use_router().push("/")
