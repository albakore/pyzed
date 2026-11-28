import pyzed as pz
from pyzed import ui

title_template = "Settings: %s · Pyzed Store"

TABS = [("/settings/profile", "Profile"), ("/settings/notifications", "Notifications")]


def layout(children, router):
    tabs = pz.row([ui.button(label, lambda href=href: router.push(href),
                             variant="tinted" if router.is_active(href) else "ghost", size="sm")
                   for href, label in TABS], spacing=4)
    return pz.column([ui.heading("Settings"), tabs, ui.divider(), children], spacing=16)
