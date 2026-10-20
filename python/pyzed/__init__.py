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

import os as _os

# The native core allocates with mimalloc, which reads its options when the core loads. On
# Linux it would commit whole memory arenas up front; committing on demand keeps the resident
# memory where it was without the system allocator (and keeps mimalloc's speed).
_os.environ.setdefault("MIMALLOC_ARENA_EAGER_COMMIT", "0")
del _os

import functools as _functools  # noqa: E402

from ._core import (  # noqa: E402 - after the allocator options above
    Command,
    Span,
    Subscription,
    Widget,
    button,
    canvas,
    cell,
    checkbox,
    code_editor,
    column,
    container,
    every,
    frames,
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
    resizable,
    responsive,
    rich_text,
    row,
    rule,
    scrollable,
    shader as _shader,
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
    virtual_column,
    window_edges,
)
from ._async import loop as asyncio_loop, spawn
from .app import App, Window, run, screenshot
from .component import Component, state
from .layout import anchor, anchor_layout, box, flex, flex_item
from .i18n import t
from .hints import Color, Icon, Multiline, Range
from .style import Gradient, Mask, Paint, Style, clear_stylesheet, define_style, set_style, stylesheet
from .animation import Animation, define_animation, presence, set_reduced_motion, stagger
from .animation_player import AnimationLibrary, AnimationPlayer, Call, Clip, Key, Track, load_animations
from .accessibility import system_reduced_motion
from .events import Event, on
from .forms import validation_errors
from .memoize import clear_memos, memo, memo_stats
from .icons import icon
from .theme import AutoTheme, Theme, themes
from . import accessibility, animation, animation_player, component, forms, i18n, layout, style, draw, events, hot_reload, theme, icons, ui

# Loaded on first use, so ``import pyzed`` stays fast (an app that never opens the designer
# or reads the reference doesn't pay for them). ``pz.Dock`` and ``from pyzed import Dock``
# work the same as eager imports.
_LAZY = {
    "designer": ("designer", None),
    "reference": ("reference", None),
    "dock": ("dock", None),
    "game": ("game", None),
    "shading": ("shading", None),
    "Dock": ("dock", "Dock"),
    "DockPanel": ("dock", "DockPanel"),
    "is_pressed": ("game", "is_pressed"),
    "pressed": ("game", "pressed"),
}


def __getattr__(name):
    if name == "__version__":
        # The version lives only in Cargo.toml; read it from the installed package metadata
        # (importlib.metadata is slow to import, so only when someone asks).
        try:
            from importlib.metadata import version as _version

            value = _version("pyzed-ui")
        except Exception:  # pragma: no cover - running from a source tree without metadata
            value = "0+unknown"
    elif name in _LAZY:
        import importlib

        module, attr = _LAZY[name]
        value = importlib.import_module(f".{module}", __name__)
        if attr is not None:
            value = getattr(value, attr)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


def __dir__():
    return sorted({*globals(), *_LAZY, "__version__"})


def hspace(width="fill"):
    """Flexible horizontal gap (pushes siblings in a row apart)."""
    return space(width=width)


def vspace(height="fill"):
    """Flexible vertical gap (pushes siblings in a column apart)."""
    return space(height=height)


def _shader_uniform(value):
    # Theme tokens ("accent", "text_muted"...) become the current theme's color; the core takes hex.
    if isinstance(value, str) and not value.startswith("#") and isinstance(getattr(theme.current(), value, None), str):
        return theme.current().color(value)
    return value


@_functools.wraps(_shader)
def shader(code, *args, uniforms=None, **kwargs):
    if uniforms:
        uniforms = {name: _shader_uniform(value) for name, value in dict(uniforms).items()}
    # A shader graph: a ``.pzshad`` path, a ``pyzed.shading`` Graph or Shader.
    source = code if hasattr(code, "__pyzed_shader__") else None
    if source is None and not (isinstance(code, str) and "fn shade" in code):
        from .shading.runtime import resolve

        source = resolve(code)
    if source is not None:
        code, uniforms, textures, defaults = source.__pyzed_shader__(uniforms)
        for key, value in defaults.items():
            kwargs.setdefault(key, value)
        if textures:
            kwargs.setdefault("textures", textures)
    if uniforms:
        kwargs["uniforms"] = uniforms
    return _shader(code, *args, **kwargs)


shader.__doc__ = (_shader.__doc__ or "") + """

``code`` can also be a shader graph: a ``.pzshad`` file made in Pyzed Design, or a
``pyzed.shading.Graph``/``Shader``. Then ``uniforms`` sets its mutable variables by name.
"""


def center(content, **kwargs):
    """Centers ``content`` in all the available space."""
    return container(content, center=True, **kwargs)


def vertical_slider(min, max, value, **kwargs):  # noqa: A002 - mirrors slider()
    """A slider that moves up and down (``slider(..., vertical=True)``)."""
    return slider(min, max, value, vertical=True, **kwargs)


__all__ = [
    "Animation",
    "AnimationLibrary",
    "AnimationPlayer",
    "Call",
    "Clip",
    "Key",
    "Track",
    "load_animations",
    "App",
    "Color",
    "Gradient",
    "Icon",
    "Multiline",
    "Range",
    "Mask",
    "Paint",
    "Style",
    "AutoTheme",
    "Command",
    "Component",
    "Dock",
    "DockPanel",
    "Event",
    "Span",
    "Subscription",
    "Theme",
    "Widget",
    "Window",
    "accessibility",
    "animation",
    "animation_player",
    "asyncio_loop",
    "button",
    "canvas",
    "cell",
    "center",
    "checkbox",
    "clear_memos",
    "code_editor",
    "column",
    "clear_stylesheet",
    "container",
    "define_animation",
    "define_style",
    "designer",
    "reference",
    "dock",
    "component",
    "draw",
    "events",
    "every",
    "frames",
    "game",
    "anchor",
    "anchor_layout",
    "box",
    "flex",
    "forms",
    "flex_item",
    "grid",
    "hot_reload",
    "hover",
    "is_pressed",
    "hspace",
    "i18n",
    "icon",
    "icons",
    "image",
    "image_viewer",
    "layout",
    "listen",
    "load_font",
    "markdown",
    "memo",
    "memo_stats",
    "mouse_area",
    "on",
    "opaque",
    "pick_list",
    "pin",
    "post",
    "presence",
    "pressed",
    "progress_bar",
    "qr_code",
    "shader",
    "radio",
    "resizable",
    "window_edges",
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
    "set_reduced_motion",
    "system_reduced_motion",
    "set_style",
    "split",
    "stack",
    "stagger",
    "style",
    "stylesheet",
    "state",
    "svg",
    "t",
    "text",
    "text_input",
    "theme",
    "themes",
    "toggler",
    "tooltip",
    "validation_errors",
    "ui",
    "vertical_slider",
    "virtual_column",
    "vspace",
]
