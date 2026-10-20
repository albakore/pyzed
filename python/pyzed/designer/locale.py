"""The designer's own texts in other languages (Settings → Language), through ``pyzed.i18n``.

The English text is the key: ``tr("Save as…")`` looks up ``designer.Save as…`` and falls
back to the English text, so a missing translation never shows a raw key. The translations
are data: one ``locales/<language>.json`` per language, ``{"designer": {"Save": "Guardar", ...}}``.
Add a language by dropping a file there, or from code with
``i18n.add("fr", {"designer": {"Save": "Enregistrer", ...}})``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .. import i18n

#: The folder with the designer's translations.
LOCALES_DIR = Path(__file__).resolve().parent / "locales"


def tr(text: str, **values: Any) -> str:
    """``text`` in the designer's language (``{name}`` placeholders filled from ``values``)."""
    return i18n.t(f"designer.{text}", default=text, **values)


def apply(language: str) -> None:
    """Switches to ``language`` (``""`` follows the system language)."""
    i18n.set_language(language or i18n.system_language())


def catalog(language: str) -> Dict[str, str]:
    """The designer's texts in ``language`` as shipped (English text -> translation)."""
    path = LOCALES_DIR / f"{language}.json"
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8")).get("designer", {}))


i18n.load(LOCALES_DIR)

#: The Spanish texts (used by the tests that check every text is translated).
_ES = catalog("es")
