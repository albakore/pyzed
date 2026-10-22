"""The color convention of the designer: every component has a role, and each role a color.

The toolbox, the outline, the component tray and the panel headers draw a component's icon in the
color of its role, so a form's structure reads at a glance: blue boxes hold other controls, green
fields take input, yellow buttons run actions, and so on. The colors come from the theme's terminal
palette, so they follow every theme (light or dark) without new tokens.

A role is worked out from what the component is (visual or not, a container, its category and
events); a ``Component`` can also name its own with ``role`` (a ``pz.Component`` of the project is ``"custom"``).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..theme import Theme, mix
from .locale import tr

#: Every role, in the order the docs and the legend list them, with its name and what it stands for.
ROLES: Dict[str, Tuple[str, str]] = {
    "layout": ("Layout", "Holds and arranges other controls: panels, cards, rows, columns, grids, docks."),
    "input": ("Input", "Takes a value from the user: text boxes, checks, selects, sliders, pickers."),
    "action": ("Action", "Runs something when pressed: buttons and split buttons."),
    "navigation": ("Navigation", "Moves between views: tabs, trees, breadcrumbs, links."),
    "display": ("Display", "Shows content: text, images, tables, charts, badges."),
    "media": ("Media", "Sound and video: knobs, faders, meters, waveforms, the webcam."),
    "system": ("System", "Non-visual: timers, processes, files, requests, the clipboard."),
    "custom": ("Custom", "Your own components, made with the designer or pz.Component."),
}

#: Categories whose components share a role whatever their events say.
_CATEGORY_ROLES = {"Layout": "layout", "Containers": "layout", "Navigation": "navigation",
                   "Audio": "media", "Media": "media", "Custom": "custom"}
#: Plain controls that lay others out without holding them.
_LAYOUT_TYPES = frozenset({"divider", "spacer"})
_NAVIGATION_TYPES = frozenset({"link", "breadcrumbs", "tabs", "tree"})
#: Events that make a control an input (it gives back a value).
_INPUT_EVENTS = frozenset({"change", "submit"})


def of(spec: Any) -> str:
    """The role of the component ``spec`` (a ``designer.components.Component``)."""
    own = getattr(spec, "role", None)
    if own in ROLES:
        return own
    if not spec.visual:
        return "system"
    category = _CATEGORY_ROLES.get(spec.category)
    if category is not None:
        return category
    if spec.container is not None or spec.type in _LAYOUT_TYPES:
        return "layout"
    if spec.type in _NAVIGATION_TYPES:
        return "navigation"
    if spec.type.endswith("button"):
        return "action"
    if spec.category != "Display" and _INPUT_EVENTS.intersection(spec.events):
        return "input"
    return "display"


#: The colors of the last theme asked for, by role (themes hold dicts, so they can't be dict keys).
_colors: Tuple[Optional[Theme], Dict[str, str]] = (None, {})


def color(role: str, t: Theme) -> str:
    """The color of ``role`` in the theme ``t``."""
    global _colors
    theme, colors = _colors
    if theme is not t:
        colors = {r: _color(r, t) for r in ROLES}
        _colors = (t, colors)
    return colors.get(role, t.icon)


def _color(role: str, t: Theme) -> str:
    ansi = t.ansi

    def pick(name: str, fallback: str) -> str:
        return ansi.get(name) or fallback

    red = pick("red", t.error)
    yellow = pick("yellow", t.warning)
    if role == "layout":
        return pick("blue", t.accent)
    if role == "input":
        return pick("green", t.success)
    if role == "action":
        return yellow
    if role == "navigation":
        return pick("cyan", t.info)
    if role == "media":
        return red
    if role == "system":
        return mix(red, yellow)  # orange
    if role == "custom":
        return pick("magenta", t.text_accent)
    return t.icon  # display: plain content stays neutral


def icon_color(spec: Optional[Any], t: Theme) -> str:
    """The color of the icon of ``spec`` (the neutral icon color when there is none)."""
    return t.icon_muted if spec is None else color(of(spec), t)


def name(role: str) -> str:
    """The name of ``role`` in the designer's language."""
    return tr(ROLES[role][0])


def describe(role: str) -> str:
    """What ``role`` stands for, in the designer's language."""
    return tr(ROLES[role][1])
