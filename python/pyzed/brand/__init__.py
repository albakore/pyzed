"""Pyzed's logo as widgets: the python "p" mark and the wordmark, in the current theme's colors.

    pz.brand.mark(20)          # the mark, tinted with the theme's accent text color
    pz.brand.wordmark(28)      # "pyzed" with the python as its "p", for dark or light themes

The files come from ``assets/brand`` (``scripts/brand.py`` writes both): ``ICON`` is Pyzed Design's
window icon, ``MARK`` and ``WORDMARK`` the logo for light backgrounds and the ``*_DARK`` ones for dark.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .. import _core
from ..theme import Theme, current

_HERE = Path(__file__).resolve().parent
ICON = str(_HERE / "icon.png")
MARK = str(_HERE / "pyzed-mark.svg")
MARK_DARK = str(_HERE / "pyzed-mark-dark.svg")
WORDMARK = str(_HERE / "pyzed-wordmark.svg")
WORDMARK_DARK = str(_HERE / "pyzed-wordmark-dark.svg")

#: Width over height of the mark and of the wordmark.
MARK_RATIO = 76 / 108
WORDMARK_RATIO = 2654 / 940


def mark(size: float = 20, *, color: Optional[str] = None, theme: Optional[Theme] = None) -> Any:
    """The python "p" ``size`` pixels tall, in ``color`` (a token or hex; the theme's ``text_accent`` by
    default)."""
    t = theme or current()
    return _core.svg(MARK, width=size * MARK_RATIO, height=size, color=t.color(color or "text_accent"))


def wordmark(height: float = 28, *, theme: Optional[Theme] = None) -> Any:
    """The wordmark, ``height`` pixels from the top of the "d" to the python's tail; the dark version on dark
    themes."""
    t = theme or current()
    return _core.svg(WORDMARK_DARK if t.is_dark else WORDMARK, width=height * WORDMARK_RATIO, height=height)
