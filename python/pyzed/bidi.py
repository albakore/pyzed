"""Writing direction: right-to-left layouts for Arabic, Hebrew, Persian, Urdu...

    import pyzed as pz

    class App(pz.App):
        direction = "rtl"          # the whole window, or "auto" to follow pz.i18n's language

        def view(self):
            return pz.column([
                pz.text("مرحبا بالعالم"),
                pz.row([pz.icon("chevron-right"), pz.text("التالي")]),   # the chevron points left
                pz.text("+1 555 0100").direction("ltr"),             # a part that stays left to right
            ])

Right to left mirrors the layout: rows run from the right, ``"left"`` alignment, padding and
margins mean the start side, pop-ups and tooltips on the ``"left"`` open on the right, sliders
and progress bars grow from the right and arrow, chevron and side panel icons point the other way.
Text keeps its own order: the text engine follows the Unicode bidirectional algorithm, so a line
that mixes Arabic or Hebrew with Latin words, numbers, URLs or code reads correctly, and it lines
up on the right. Code editors stay left to right.

The direction of a window is ``Window.direction`` (``"ltr"``, ``"rtl"``, ``"auto"`` or ``None`` to
use the app's), then ``pz.set_direction`` for every window, which starts as ``"auto"``: right to
left when ``pz.i18n``'s language is written that way (``pz.i18n.set_language("ar")``).
``widget.direction("rtl")`` or ``pz.direction(content, "rtl")`` sets it for one part.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from . import _core

__all__ = [
    "RTL_LANGUAGES",
    "direction",
    "get_direction",
    "is_rtl",
    "is_rtl_language",
    "mirrored_icon",
    "set_direction",
]

#: Languages written right to left (ISO 639 codes): Arabic, Hebrew, Persian, Urdu, Pashto, Sindhi,
#: Kurdish (Sorani), Uyghur, Dhivehi, Yiddish, Syriac and N'Ko.
RTL_LANGUAGES = frozenset({"ar", "he", "iw", "fa", "ur", "ps", "sd", "ckb", "ug", "dv", "yi", "syr", "nqo"})

_DIRECTIONS = ("ltr", "rtl", "auto")
_global = "auto"
#: The direction of the window being drawn (``is_rtl()`` inside ``view``).
_drawing: Optional[str] = None


def _check(value: str) -> str:
    value = str(value).lower()
    if value not in _DIRECTIONS:
        raise ValueError(f"direction must be 'ltr', 'rtl' or 'auto', not {value!r}")
    return value


def is_rtl_language(language: str) -> bool:
    """Whether a language is written right to left: ``"ar"``, ``"he-IL"``, ``"fa_IR"``, ``"ur"``..."""
    code = str(language).replace("_", "-").split("-")[0].lower()
    return code in RTL_LANGUAGES


def _resolve(value: Optional[str]) -> str:
    """``"ltr"`` or ``"rtl"`` for a direction setting (``None`` and ``"auto"`` follow on)."""
    value = _global if value is None else _check(value)
    if value == "auto":
        from . import i18n

        return "rtl" if is_rtl_language(i18n.language()) else "ltr"
    return value


def set_direction(direction: str) -> None:
    """Sets the writing direction of every window that doesn't set its own ``direction``:
    ``"ltr"``, ``"rtl"`` or ``"auto"`` (the default: right to left when ``pz.i18n``'s language
    is). Windows follow it on their next update."""
    global _global
    _global = _check(direction)


def get_direction() -> str:
    """The writing direction windows use when they don't set their own, as ``"ltr"`` or ``"rtl"``
    (``"auto"`` resolved from ``pz.i18n``'s language)."""
    return _resolve(None)


def is_rtl() -> bool:
    """Whether the window being drawn is right to left (inside ``view``), else whether windows are
    by default. For components that place things themselves (a canvas, a pin at a computed x)."""
    return (_drawing or get_direction()) == "rtl"


def direction(content: Any, direction: str) -> _core.Widget:
    """Lays ``content`` out in a writing direction: ``"rtl"``, ``"ltr"`` or ``"auto"`` (from
    ``pz.i18n``'s language). See the module documentation for what right to left changes."""
    return _core.direction(content, direction)


def _mirrored_names(codepoints: Dict[str, int]) -> Dict[str, str]:
    """Lucide icons that point along the line, with their mirror image: names with ``left`` and
    ``right`` swapped among arrows, chevrons, side panels and corners, and undo/redo."""
    kinds = ("arrow", "chevron", "panel", "corner", "move-")
    names = {}
    for name in codepoints:
        parts = name.split("-")
        if ("left" not in parts and "right" not in parts) or not any(kind in name for kind in kinds):
            continue
        other = "-".join("right" if part == "left" else "left" if part == "right" else part for part in parts)
        if other != name and other in codepoints and codepoints[other] != codepoints[name]:
            names[name] = other
    for a, b in (("undo", "redo"), ("undo-2", "redo-2"), ("undo-dot", "redo-dot")):
        if a in codepoints and b in codepoints:
            names[a], names[b] = b, a
    return names


def mirrored_icon(name: str) -> str:
    """The icon shown for ``name`` in a right-to-left part: ``"chevron-left"`` for
    ``"chevron-right"``, ``"redo"`` for ``"undo"``; ``name`` itself for an icon that is not mirrored."""
    from ._lucide import CODEPOINTS

    return _mirrored_names(CODEPOINTS).get(name, name)


def _install() -> None:
    from ._lucide import CODEPOINTS

    names = _mirrored_names(CODEPOINTS)
    _core._set_mirrored_icons([(chr(CODEPOINTS[a]), chr(CODEPOINTS[b])) for a, b in names.items()])


_install()
