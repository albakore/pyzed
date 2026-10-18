"""Pieces of the hot reload demo's UI. Edit them while the app runs and save."""

import pyzed as pz
from pyzed import ui

ACCENT = "#61afef"


def stat(label, value):
    """A small card with a big number. Try changing the size or the color."""
    return ui.card(
        pz.column(
            [
                ui.label(label, size="sm", color="text_muted"),
                pz.text(str(value), size=30, color=ACCENT),
            ],
            spacing=4,
        ),
        width="fill",
    )
