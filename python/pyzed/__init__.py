"""Pyzed: fast, modern GUIs for Python, rendered by Iced (Rust).

    import pyzed as pz

    class Counter(pz.App):
        count = 0

        def increment(self):
            self.count += 1

        def view(self):
            return pz.column([
                pz.text(f"Clicks: {self.count}", size=24),
                pz.ui.button("Click me", on_press=self.increment),
            ], spacing=12, padding=24)

    pz.run(Counter)
"""

from ._core import (
    Command,
    Widget,
    button,
    checkbox,
    code_editor,
    column,
    container,
    hover,
    load_font,
    mouse_area,
    opaque,
    post,
    progress_bar,
    row,
    rule,
    scrollable,
    slider,
    space,
    stack,
    svg,
    text,
    text_input,
    toggler,
    tooltip,
)
from .app import App, run, screenshot
from .icons import icon
from .theme import Theme, themes
from . import theme, icons, ui

__version__ = "0.1.0"


def hspace(width="fill"):
    """Flexible horizontal gap (pushes siblings in a row apart)."""
    return space(width=width)


def vspace(height="fill"):
    """Flexible vertical gap (pushes siblings in a column apart)."""
    return space(height=height)


def center(content, **kwargs):
    """Centers ``content`` in all the available space."""
    return container(content, center=True, **kwargs)


__all__ = [
    "App",
    "Command",
    "Theme",
    "Widget",
    "button",
    "center",
    "checkbox",
    "code_editor",
    "column",
    "container",
    "hover",
    "hspace",
    "icon",
    "icons",
    "load_font",
    "mouse_area",
    "opaque",
    "post",
    "progress_bar",
    "row",
    "rule",
    "run",
    "screenshot",
    "scrollable",
    "slider",
    "space",
    "stack",
    "svg",
    "text",
    "text_input",
    "theme",
    "themes",
    "toggler",
    "tooltip",
    "ui",
    "vspace",
]
