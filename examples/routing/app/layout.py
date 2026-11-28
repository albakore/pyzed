"""The shell around every page: a sidebar that keeps its state, and the page on its right."""

import pyzed as pz
from pyzed import ui

from state import cart, session

title_template = "%s · Pyzed Store"
default_title = "Pyzed Store"

LINKS = [("/", "Home", "house"), ("/products", "Products", "shopping-bag"), ("/account", "Account", "user"),
         ("/docs", "Docs", "book-open"), ("/settings", "Settings", "settings"), ("/about", "About", "info")]


class Layout(pz.Component):
    """A component, so its state (the collapsed sidebar) survives every navigation."""

    children: list = ()
    collapsed = pz.state(False)

    def render(self):
        router = pz.use_router()
        bar = pz.row([
            ui.icon_button("arrow-left", router.back if router.can_go_back else None, tooltip="Back (Alt+Left)"),
            ui.icon_button("arrow-right", router.forward if router.can_go_forward else None,
                           tooltip="Forward (Alt+Right)"),
            ui.label(router.url, color="text_muted", mono=True),
            pz.hspace(),
            ui.badge(f"Cart · {cart.count}", icon="shopping-cart"),
            ui.label(session.user.get("name", "Guest"), color="text_muted"),
            ui.icon_button("panel-left", self.toggle, tooltip="Toggle the sidebar"),
        ], spacing=4, align="center", padding=(6, 12))
        side = pz.column([
            ui.label("STORE", size="xs", color="text_muted", weight="semibold"),
            *[pz.nav_link(href, label, icon=icon) for href, label, icon in LINKS],
        ], spacing=2, padding=12, width=200)
        page = pz.container(pz.column(self.children, width="fill"), padding=24, width="fill", height="fill")
        body = pz.row([side if not self.collapsed else None, ui.divider(vertical=True) if not self.collapsed else None,
                       pz.scrollable(page, height="fill")], height="fill")
        return pz.column([bar, ui.divider(), body], width="fill", height="fill").style(background="background")

    def toggle(self):
        self.collapsed = not self.collapsed
