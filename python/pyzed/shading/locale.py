"""The node catalog's texts in other languages (titles, categories, descriptions, port names).

The English text is the key, as in the designer: ``tr("Noise")`` looks up ``shading.Noise``
and falls back to the English text. The translations are ``locales/<language>.json``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import i18n

#: The folder with the catalog's translations.
LOCALES_DIR = Path(__file__).resolve().parent / "locales"


def tr(text: str, **values: Any) -> str:
    """``text`` in the current language."""
    if not text:
        return text
    return i18n.t(f"shading.{text}", default=text, **values)


if LOCALES_DIR.is_dir():
    i18n.load(LOCALES_DIR)
