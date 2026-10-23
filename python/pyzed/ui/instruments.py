"""Instrument-panel pieces from Pyzed's brand: LEDs, LED toggles and LCD readouts, like the panels of an
audio rack. They take the theme's ``led``, ``led_off``, ``display`` and ``display_text`` colors, which every
theme has (themes that do not set them use their warning color and a dark editor shade).

    ui.led(True)                                       # a lit amber LED
    ui.led_toggle("Snap", self.snap, self.toggle_snap) # a mono label with its LED, toggled on click
    ui.lcd("60 FPS", "wgpu")                           # an amber readout, the parts split by "|"
"""

from __future__ import annotations

from typing import Any, Optional

from .. import _core
from ..icons import icon as _icon
from ..theme import Theme, alpha, mix
from .base import _theme, tooltip_text


def led(on: bool = True, *, color: Optional[str] = None, size: float = 7, glow: bool = True,
        theme: Optional[Theme] = None) -> _core.Widget:
    """A round LED: lit in ``color`` (a token or hex; the theme's ``led`` by default) with a soft glow, or
    dark (the theme's ``led_off``) when ``on`` is false."""
    t = _theme(theme)
    lit = t.color(color) if color else t.led
    return _core.container(None, width=size, height=size, radius=size / 2, bg=lit if on else t.led_off,
                           shadow=(alpha(lit, 0.85), (0, 0), size + 1) if on and glow else None)


def led_toggle(label: str, on: bool, on_toggle: Any = None, *, color: Optional[str] = None,
               tooltip: Optional[str] = None, keys: Optional[str] = None, height: float = 24,
               theme: Optional[Theme] = None) -> _core.Widget:
    """A toggle button that shows its state with an LED next to a small mono ``label`` (in capitals), like
    the SNAP and GUIDES switches of Pyzed Design's canvas.

    Events:
        ``on_toggle(on)``: Callable that receives the new state, or a message sent on press. ``None``
        disables the control.
    """
    t = _theme(theme)
    content = _core.row([
        led(on, color=color, size=6, theme=t),
        _core.text(label.upper(), size=11, font="mono", weight="medium", color=t.text if on else t.text_muted,
                   wrap=False),
    ], spacing=7, align="center")
    action = (lambda: on_toggle(not on)) if callable(on_toggle) else on_toggle
    widget = _core.button(
        _core.container(content, height="fill", align_y="center"), action, padding=(0, 9), height=height,
        bg=t.panel, hover_bg=t.element_hover, pressed_bg=t.element_active, border_color=t.border_variant,
        hover_border_color=t.border, border_width=1.0, radius=t.radius_sm,
    )
    return tooltip_text(widget, tooltip, keys=keys, theme=t) if tooltip else widget


def lcd(*parts: Any, size: float = 12, height: Optional[float] = 24, color: Optional[str] = None,
        theme: Optional[Theme] = None) -> _core.Widget:
    """An LCD readout: ``parts`` (texts or numbers) in amber mono on the theme's ``display`` color, split by
    dim bars. ``color`` replaces the text color (a token or hex)."""
    t = _theme(theme)
    ink = t.color(color) if color else t.display_text
    dim = mix(ink, t.display, 0.55)
    items: list = []
    for part in parts:
        if part is None or part == "":
            continue
        if items:
            items.append(_core.text("|", size=size, font="mono", color=dim, wrap=False))
        items.append(_core.text(str(part), size=size, font="mono", weight="medium", color=ink, wrap=False))
    return _core.container(_core.row(items, spacing=8, align="center"), padding=(0, 10), height=height,
                           align_y="center", bg=t.display, border_color=mix(t.display, t.border, 0.6),
                           border_width=1.0, radius=t.radius_sm)


def _swatches(theme: Theme) -> list:
    keyword = theme.syntax.get("keyword", theme.accent)
    keyword = keyword[0] if isinstance(keyword, tuple) else keyword
    return [theme.editor, theme.panel, theme.text, theme.text_accent, keyword, theme.success, theme.warning,
            theme.error]


def theme_rack(themes: Any, current: Optional[str], on_pick: Any = None, *, columns: int = 2,
               theme: Optional[Theme] = None) -> _core.Widget:
    """Themes to pick from as a rack of modules: each one an LED (lit on ``current``, a theme name), its name,
    eight swatches of its colors (editor, panel, text, accent, keywords, success, warning and error) and a moon
    or a sun for dark and light. ``themes`` are ``Theme`` objects (``pz.themes.all()``).

    Events:
        ``on_pick(name)``: Callable that receives the name of the theme clicked.
    """
    t = _theme(theme)
    modules = []
    for item in themes:
        on = item.name == current
        swatches = _core.row([_core.container(None, width="fill", height=14, radius=2, bg=color,
                                              border_color=alpha(t.text, 0.08), border_width=1.0)
                              for color in _swatches(item)], spacing=2, width="fill")
        content = _core.row([
            led(on, size=6, theme=t),
            _core.text(item.name, size=12.5, weight="semibold" if on else None, color=t.text if on else t.text_muted,
                       wrap=False, width=124),
            swatches,
            _icon("moon" if item.is_dark else "sun", size=12, color=t.icon_muted),
        ], spacing=8, align="center")
        modules.append(_core.button(
            content, (lambda n=item.name: on_pick(n)) if on_pick else None, padding=(6, 10), width="fill",
            bg=t.editor if on else t.panel, hover_bg=t.element_hover, pressed_bg=t.element_active,
            border_color=t.border if on else t.border_variant, border_width=1.0, radius=t.radius_sm,
        ))
    rows = [_core.row(modules[i:i + columns] + [_core.space(width="fill")] * (columns - len(modules[i:i + columns])),
                      spacing=6) for i in range(0, len(modules), columns)]
    return _core.container(_core.column(rows, spacing=6), padding=8, width="fill", bg=mix(t.background, t.panel, 0.5),
                           border_color=t.border_variant, border_width=1.0, radius=t.radius)
