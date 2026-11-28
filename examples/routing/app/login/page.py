"""/login: signs in with an action, then goes where the middleware stopped you."""

import pyzed as pz
from pyzed import ui

import api
from state import session

title = "Sign in"


def signed_in(next_href):
    """Back on the UI thread once the action is done: go where the middleware stopped you."""
    pz.use_router().replace(next_href or "/account")


@pz.action(refresh=False, on_done=signed_in)
async def sign_in(name, next_href):
    session.user = await api.sign_in(name)
    return next_href


class Page(pz.Component):
    query: dict = {}
    name = pz.state("Ada")

    def render(self):
        return pz.column([
            ui.heading("Sign in"),
            ui.label("The account pages are behind a middleware.", color="text_muted"),
            ui.input(self.name, on_input=lambda v: setattr(self, "name", v), placeholder="Your name"),
            ui.button("Signing in…" if sign_in.pending else "Sign in",
                      lambda: sign_in(self.name, self.query.get("next")), variant="solid", icon="log-in",
                      loading=sign_in.pending),
        ], spacing=12, width=320)
