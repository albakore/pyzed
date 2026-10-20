"""A small "kitchen sink" used by every example in this folder.

It only uses theme tokens and ``pyzed.ui`` components, so it takes the look of whatever
theme is current: run any of the examples next to it to see the same screen restyled.

    python examples/theming/brand.py
"""

import pyzed as pz
from pyzed import ui


def preview(title: str = "Preview", subtitle: str = "Every color on this screen comes from the theme."):
    """A heading, buttons in every variant, a small form, badges, a callout and two stats."""
    buttons = pz.row([
        ui.button("Primary", lambda: None, variant="solid"),
        ui.button("Filled", lambda: None),
        ui.button("Outline", lambda: None, variant="outline"),
        ui.button("Ghost", lambda: None, variant="ghost"),
        ui.button("Delete", lambda: None, variant="tinted", tint="error", icon="trash-2"),
    ], spacing=8, wrap=True)
    form = pz.column([
        ui.field("Name", ui.input("Ada Lovelace", lambda _v: None, width=220)),
        ui.field("Email", ui.input("", lambda _v: None, placeholder="you@example.com", width=220)),
        ui.field("Notifications", ui.switch(True, lambda _v: None)),
        ui.field("Volume", pz.container(ui.slider(0.6, lambda _v: None), width=220)),
    ], spacing=10)
    badges = pz.row([
        ui.badge("New"),
        ui.badge("Paid", tint="success"),
        ui.badge("Pending", tint="warning"),
        ui.badge("Failed", tint="error", variant="outline"),
        ui.badge("Beta", tint="info", variant="solid"),
    ], spacing=6, wrap=True)
    stats = pz.row([
        ui.stat("Revenue", "$12.4k", delta=8.2, width="fill"),
        ui.stat("Refunds", "31", delta=-2.5, width="fill"),
    ], spacing=12)
    return pz.column([
        pz.column([ui.heading(title), ui.muted(subtitle)], spacing=4),
        buttons,
        ui.card(pz.column([form, ui.progress(0.7)], spacing=14), title="Account"),
        badges,
        ui.callout("Saved", "Your changes are stored on this device.", tint="success"),
        stats,
    ], spacing=16)
