"""Shown while a page's `load` runs."""

import pyzed as pz
from pyzed import ui


def loading():
    return pz.row([ui.spinner(), ui.label("Loading…", color="text_muted")], spacing=8)
