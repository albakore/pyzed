"""Translations: change the language of an app while it runs.

Register a catalog per language, pick a language and look texts up with ``pz.t``::

    from pyzed import i18n
    import pyzed as pz

    i18n.add("en", {"greeting": "Hello, {name}!", "files": {"one": "{count} file", "other": "{count} files"}})
    i18n.add("es", {"greeting": "¡Hola, {name}!", "files": {"one": "{count} archivo", "other": "{count} archivos"}})
    i18n.set_language("es")

    pz.t("greeting", name="Kev")   # "¡Hola, Kev!"
    pz.t("files", count=3)         # "3 archivos"

Catalogs can also live in files, one per language (``locales/es.json``, ``locales/es.toml``),
loaded with ``i18n.load("locales")``. Nested tables become dotted keys
(``{"menu": {"open": "Abrir"}}`` is ``"menu.open"``).

A view calls ``pz.t`` every time it renders, so calling ``set_language`` from a handler
redraws the whole app in the new language. Lookups fall back from ``"es_AR"`` to ``"es"``,
then to the fallback language (``"en"``), then to the key itself.

Pyzed's own components (dialogs, the dock...) are translated too: their texts use keys
that start with ``pyzed.``; English and Spanish are built in, and ``add`` can override them
or add more languages.
"""

from __future__ import annotations

import json
import locale
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Union

PathLike = Union[str, Path]

_catalogs: Dict[str, Dict[str, Any]] = {}
_language = "en"
_fallback = "en"
_listeners: List[Callable[[str], Any]] = []


def normalize(language: str) -> str:
    """``"es-AR"``, ``"es_AR.UTF-8"`` -> ``"es_ar"``."""
    return str(language).split(".")[0].split("@")[0].replace("-", "_").lower()


def _flatten(catalog: Mapping[str, Any], prefix: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in catalog.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping) and not _is_plural(value):
            out.update(_flatten(value, name + "."))
        else:
            out[name] = value
    return out


def _is_plural(value: Mapping[str, Any]) -> bool:
    return bool(value) and "other" in value and set(value) <= {"zero", "one", "two", "few", "many", "other"}


def add(language: str, catalog: Mapping[str, Any]) -> None:
    """Adds (or overrides) texts for ``language``. Nested tables become dotted keys."""
    _catalogs.setdefault(normalize(language), {}).update(_flatten(catalog))


def load(folder: PathLike) -> List[str]:
    """Loads every ``<language>.json`` / ``<language>.toml`` in ``folder``; returns the languages."""
    found: List[str] = []
    for file in sorted(Path(folder).iterdir()):
        if file.suffix == ".json":
            data = json.loads(file.read_text(encoding="utf-8"))
        elif file.suffix == ".toml":
            from .project import _loads_toml

            data = _loads_toml(file.read_text(encoding="utf-8"))
        else:
            continue
        add(file.stem, data)
        found.append(normalize(file.stem))
    return found


def languages() -> List[str]:
    """The languages with a catalog, sorted."""
    return sorted(_catalogs)


def language() -> str:
    """The current language."""
    return _language


def set_language(language: str) -> None:
    """Switches the language; the app shows it on its next render."""
    global _language
    language = normalize(language)
    if language == _language:
        return
    _language = language
    for listener in list(_listeners):
        listener(language)


def set_fallback(language: str) -> None:
    """The language used when a text is missing in the current one (default ``"en"``)."""
    global _fallback
    _fallback = normalize(language)


def on_change(listener: Callable[[str], Any]) -> Callable[[], None]:
    """Calls ``listener(language)`` after every switch; returns a function that removes it."""
    _listeners.append(listener)
    return lambda: _listeners.remove(listener) if listener in _listeners else None


def system_language(default: str = "en") -> str:
    """The language of the operating system (``LANG``/``LC_ALL``, or the locale), e.g. ``"es_ar"``."""
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var, "").split(":")[0]
        if value and value not in ("C", "POSIX", "C.UTF-8"):
            return normalize(value)
    try:
        value = locale.getlocale()[0]
    except ValueError:  # pragma: no cover - unusual locale settings
        value = None
    return normalize(value) if value else default


def _chain(language: Optional[str]) -> List[str]:
    lang = normalize(language) if language else _language
    chain = [lang]
    base = lang.split("_")[0]
    for candidate in (base, _fallback, _fallback.split("_")[0]):
        if candidate not in chain:
            chain.append(candidate)
    return chain


def _plural(forms: Mapping[str, Any], count: Any) -> Any:
    if count == 0 and "zero" in forms:
        return forms["zero"]
    if count == 1 and "one" in forms:
        return forms["one"]
    return forms["other"]


def has(key: str, *, language: Optional[str] = None) -> bool:
    """Whether ``key`` has a text in ``language`` (or the current one) or its fallbacks."""
    return any(key in _catalogs.get(lang, {}) for lang in _chain(language))


def t(key: str, *, language: Optional[str] = None, default: Optional[str] = None, **values: Any) -> str:
    """The text for ``key`` in the current language, formatted with ``values``.

    A text with plural forms (``{"one": ..., "other": ...}``) is picked by ``count=``.
    Missing keys return ``default``, or the key itself.
    """
    for lang in _chain(language):
        catalog = _catalogs.get(lang)
        if catalog is not None and key in catalog:
            text = catalog[key]
            break
    else:
        text = key if default is None else default
    if isinstance(text, Mapping):
        text = _plural(text, values.get("count"))
    text = str(text)
    if values:
        try:
            return text.format(**values)
        except (KeyError, IndexError, ValueError):
            return text
    return text


# Texts used by Pyzed's own components.
add("en", {
    "pyzed": {
        "ok": "OK",
        "cancel": "Cancel",
        "close": "Close",
        "yes": "Yes",
        "no": "No",
        "save": "Save",
        "dont_save": "Don't save",
        "delete": "Delete",
        "confirm": "Are you sure?",
        "unsaved": {"title": "Unsaved changes", "message": "Save your changes to {name} before closing?"},
        "dock": {"left": "Dock Left", "right": "Dock Right", "bottom": "Dock Bottom", "top": "Dock Top"},
        "validation": {"required": "This field is required", "min_length": "At least {min} characters",
                       "max_length": "At most {max} characters", "pattern": "The format is not valid",
                       "min": "Must be {min} or more", "max": "Must be {max} or less"},
        "reference": {"title": "Reference", "search": "Search the reference", "back": "Back", "forward": "Forward",
                      "online": "Open online", "no_results": "Nothing matches “{query}”.",
                      "empty": "Pick a page in the list, or search a widget, component or function.",
                      "parameter": "Parameter", "description": "Description", "members": "Methods and properties",
                      "your_components": "Your components", "props": "Properties", "state": "State",
                      "events": "Events", "methods": "Methods", "name": "Name", "type": "Type",
                      "default": "Default", "kinds": {"class": "class", "function": "function", "constant": "constant",
                      "module": "module", "control": "control", "component": "component", "page": "page"},
                      "results": {"one": "{count} result", "other": "{count} results"}},
        "icons": {"title": "Choose an icon", "search": "Search icons by name or tag", "all": "All icons",
                  "no_icon": "No icon", "clear": "No icon", "none_found": "No icon matches “{query}”.",
                  "count": {"one": "{count} icon", "other": "{count} icons"},
                  "categories": {"arrows": "Arrows", "text": "Text", "files": "Files", "layout": "Layout",
                                 "media": "Media", "communication": "Communication", "people": "People",
                                 "devices": "Devices", "development": "Development", "shapes": "Shapes",
                                 "weather": "Weather", "commerce": "Commerce", "maps": "Maps and travel",
                                 "status": "Status"}},
        "color": {"solid": "Solid", "gradient": "Gradient", "angle": "Angle", "mask": "Mask", "opacity": "Opacity",
                  "remove_stop": "Remove stop"},
    }
})
add("es", {
    "pyzed": {
        "ok": "Aceptar",
        "cancel": "Cancelar",
        "close": "Cerrar",
        "yes": "Sí",
        "no": "No",
        "save": "Guardar",
        "dont_save": "No guardar",
        "delete": "Eliminar",
        "confirm": "¿Seguro?",
        "unsaved": {"title": "Cambios sin guardar", "message": "¿Guardar los cambios de {name} antes de cerrar?"},
        "dock": {"left": "Acoplar a la izquierda", "right": "Acoplar a la derecha", "bottom": "Acoplar abajo",
                 "top": "Acoplar arriba"},
        "validation": {"required": "Este campo es obligatorio", "min_length": "Al menos {min} caracteres",
                       "max_length": "Como mucho {max} caracteres", "pattern": "El formato no es válido",
                       "min": "Debe ser {min} o más", "max": "Debe ser {max} o menos"},
        "reference": {"title": "Referencia", "search": "Buscar en la referencia", "back": "Atrás",
                      "forward": "Adelante", "online": "Abrir en la web", "no_results": "Nada coincide con “{query}”.",
                      "empty": "Elige una página de la lista o busca un widget, un componente o una función.",
                      "parameter": "Parámetro", "description": "Descripción", "members": "Métodos y propiedades",
                      "your_components": "Tus componentes", "props": "Propiedades", "state": "Estado",
                      "events": "Eventos", "methods": "Métodos", "name": "Nombre", "type": "Tipo",
                      "default": "Por defecto", "kinds": {"class": "clase", "function": "función",
                      "constant": "constante", "module": "módulo", "control": "control", "component": "componente",
                      "page": "página"}, "results": {"one": "{count} resultado", "other": "{count} resultados"}},
        "icons": {"title": "Elegir un icono", "search": "Buscar iconos por nombre o etiqueta", "all": "Todos los iconos",
                  "no_icon": "Sin icono", "clear": "Sin icono", "none_found": "Ningún icono coincide con “{query}”.",
                  "count": {"one": "{count} icono", "other": "{count} iconos"},
                  "categories": {"arrows": "Flechas", "text": "Texto", "files": "Archivos", "layout": "Diseño",
                                 "media": "Multimedia", "communication": "Comunicación", "people": "Personas",
                                 "devices": "Dispositivos", "development": "Desarrollo", "shapes": "Formas",
                                 "weather": "Clima", "commerce": "Comercio", "maps": "Mapas y viajes",
                                 "status": "Estado"}},
        "color": {"solid": "Sólido", "gradient": "Degradado", "angle": "Ángulo", "mask": "Máscara",
                  "opacity": "Opacidad", "remove_stop": "Quitar parada"},
    }
})
