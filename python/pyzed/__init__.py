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

Layout and primitives live at the top level (``pz.column``, ``pz.text``, ``pz.canvas``...),
ready-made Zed-style components in ``pz.ui`` and colors in ``pz.themes``.
"""

from ._core import (
    Command,
    Span,
    Subscription,
    Widget,
    button,
    canvas,
    checkbox,
    code_editor,
    column,
    container,
    every,
    grid,
    hover,
    image,
    image_viewer,
    listen,
    load_font,
    markdown,
    mouse_area,
    opaque,
    pick_list,
    pin,
    post,
    progress_bar,
    qr_code,
    radio,
    responsive,
    rich_text,
    row,
    rule,
    scrollable,
    slider,
    space,
    span,
    split,
    stack,
    svg,
    text,
    text_input,
    toggler,
    tooltip,
)
from ._async import loop as asyncio_loop, spawn
from .app import App, Window, run, screenshot
from .icons import icon
from .theme import AutoTheme, Theme, themes
from . import designer, draw, hot_reload, theme, icons, ui

__version__ = "0.2.0"


def hspace(width="fill"):
    """Flexible horizontal gap (pushes siblings in a row apart)."""
    return space(width=width)


def vspace(height="fill"):
    """Flexible vertical gap (pushes siblings in a column apart)."""
    return space(height=height)


def center(content, **kwargs):
    """Centers ``content`` in all the available space."""
    return container(content, center=True, **kwargs)


def vertical_slider(min, max, value, **kwargs):  # noqa: A002 - mirrors slider()
    """A slider that moves up and down (``slider(..., vertical=True)``)."""
    return slider(min, max, value, vertical=True, **kwargs)


__all__ = [
    "App",
    "AutoTheme",
    "Command",
    "Span",
    "Subscription",
    "Theme",
    "Widget",
    "Window",
    "asyncio_loop",
    "button",
    "canvas",
    "center",
    "checkbox",
    "code_editor",
    "column",
    "container",
    "designer",
    "draw",
    "every",
    "grid",
    "hot_reload",
    "hover",
    "hspace",
    "icon",
    "icons",
    "image",
    "image_viewer",
    "listen",
    "load_font",
    "markdown",
    "mouse_area",
    "opaque",
    "pick_list",
    "pin",
    "post",
    "progress_bar",
    "qr_code",
    "radio",
    "responsive",
    "rich_text",
    "row",
    "rule",
    "run",
    "screenshot",
    "scrollable",
    "slider",
    "space",
    "span",
    "spawn",
    "split",
    "stack",
    "svg",
    "text",
    "text_input",
    "theme",
    "themes",
    "toggler",
    "tooltip",
    "ui",
    "vertical_slider",
    "vspace",
]
