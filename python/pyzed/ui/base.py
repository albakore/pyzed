"""Basic building blocks: labels, buttons, badges, key bindings, avatars, tooltips."""

from __future__ import annotations

import sys
from typing import Any, Iterable, Optional, Sequence, Union

from .. import _core
from ..icons import icon as _icon
from ..theme import Theme, alpha, current, mix

TEXT_SIZES = {"xs": 11.0, "sm": 12.0, "md": 13.5, "lg": 16.0, "xl": 20.0, "2xl": 26.0}

# height, horizontal padding, font size, icon size
BUTTON_SIZES = {
    "xs": (18.0, 4.0, 12.0, 12.0),
    "sm": (22.0, 6.0, 12.5, 14.0),
    "md": (28.0, 10.0, 13.5, 14.0),
    "lg": (32.0, 14.0, 14.0, 16.0),
}

TINTS = ("accent", "error", "warning", "success", "info")


def _theme(theme: Optional[Theme]) -> Theme:
    return theme or current()


def _size(size: Union[str, float]) -> float:
    return TEXT_SIZES[size] if isinstance(size, str) else float(size)


def label(
    content: Any,
    *,
    color: str = "text",
    size: Union[str, float] = "md",
    weight: Optional[str] = None,
    mono: bool = False,
    italic: bool = False,
    wrap: bool = True,
    theme: Optional[Theme] = None,
    **kwargs,
) -> _core.Widget:
    """Text using a theme color token (``"text"``, ``"text_muted"``, ``"accent"``...) or a hex color."""
    t = _theme(theme)
    return _core.text(
        content,
        size=_size(size),
        color=t.color(color),
        font="mono" if mono else None,
        weight=weight,
        italic=italic,
        wrap=wrap,
        **kwargs,
    )


def muted(content: Any, **kwargs) -> _core.Widget:
    """A ``label`` in the theme's muted text color (unless ``color`` is given)."""
    kwargs.setdefault("color", "text_muted")
    return label(content, **kwargs)


def heading(content: Any, *, level: int = 1, theme: Optional[Theme] = None, **kwargs) -> _core.Widget:
    """A semibold ``label`` sized by ``level``: 1 is ``2xl``, 2 ``xl``, 3 ``lg`` and deeper ``md``."""
    size = {1: "2xl", 2: "xl", 3: "lg"}.get(level, "md")
    return label(content, size=size, weight="semibold", theme=theme, **kwargs)


# Colors of each (theme, variant, tint, selected): mixing them is most of what a button costs
# to build, and a view builds the same few kinds over and over. Themes are immutable, so the
# entry stays valid while its theme is alive (the theme is kept to tell a reused id apart).
_BUTTON_COLORS: dict = {}


def _button_colors(t: Theme, variant: str, tint: Optional[str], selected: bool):
    key = (id(t), variant, tint, selected)
    cached = _BUTTON_COLORS.get(key)
    if cached is None or cached[0] is not t:
        if len(_BUTTON_COLORS) > 512:
            _BUTTON_COLORS.clear()
        cached = _BUTTON_COLORS[key] = (t, _mix_button_colors(t, variant, tint, selected))
    return dict(cached[1])


def _mix_button_colors(t: Theme, variant: str, tint: Optional[str], selected: bool):
    if variant in TINTS:
        tint, variant = variant, "tinted"
    if tint and variant not in ("solid", "tinted"):
        variant = "tinted"
    if variant == "filled":
        colors = dict(bg=t.element, hover_bg=t.element_hover, pressed_bg=t.element_active, color=t.text,
                      border_color=t.border_variant)
    elif variant == "solid":
        base = t.color(tint or "accent")
        colors = dict(bg=base, hover_bg=mix(base, "#ffffff", 0.12), pressed_bg=mix(base, "#000000", 0.12),
                      color=t.on_accent, border_color=None)
    elif variant == "tinted":
        base = t.color(tint or "accent")
        colors = dict(bg=alpha(base, 0.15), hover_bg=alpha(base, 0.25), pressed_bg=alpha(base, 0.32), color=base,
                      border_color=alpha(base, 0.4))
    elif variant == "outline":
        colors = dict(bg="transparent", hover_bg=t.ghost_hover, pressed_bg=t.ghost_active, color=t.text,
                      border_color=t.border)
    elif variant in ("ghost", "subtle", "transparent"):
        colors = dict(bg="transparent", hover_bg=t.ghost_hover, pressed_bg=t.ghost_active,
                      color=t.text if variant != "subtle" else t.text_muted, border_color=None)
    else:
        raise ValueError(f"unknown button variant {variant!r}")
    if selected:
        colors["bg"] = t.ghost_selected
        colors["hover_bg"] = t.ghost_selected
        colors["color"] = t.text
    return colors


def button(
    content: Any = None,
    on_press: Any = None,
    *,
    icon: Optional[str] = None,
    icon_position: str = "start",
    icon_color: Optional[str] = None,
    variant: str = "filled",
    tint: Optional[str] = None,
    size: str = "md",
    selected: bool = False,
    disabled: bool = False,
    full_width: bool = False,
    keys: Optional[str] = None,
    theme: Optional[Theme] = None,
    **style,
) -> _core.Widget:
    """A Zed-style button.

    variant: "filled" | "ghost" | "subtle" | "outline" | "solid" | "tinted" | "accent" | "error" | ...
    size:    "xs" | "sm" | "md" | "lg"
    keys:    optional key binding shown at the end, e.g. ``"ctrl-s"``.
    """
    t = _theme(theme)
    height, pad_x, font_size, icon_size = BUTTON_SIZES[size]
    colors = _button_colors(t, variant, tint, selected)
    colors.update(style)

    parts = []
    glyph = _icon(icon, size=icon_size, color=t.color(icon_color) if icon_color else None) if icon else None
    if glyph is not None and icon_position == "start":
        parts.append(glyph)
    if content is not None:
        parts.append(content if isinstance(content, _core.Widget) else _core.text(content, size=font_size, wrap=False))
    if glyph is not None and icon_position == "end":
        parts.append(glyph)
    if keys:
        parts.append(_core.space(width=4))
        parts.append(kbd(keys, theme=t, size="xs"))

    inner = _core.container(
        _core.row(parts, spacing=6, align="center"),
        height="fill",
        width="fill" if full_width else None,
        align_y="center",
        align_x="center" if full_width else None,
    )
    border_color = colors.pop("border_color", None)
    return _core.button(
        inner,
        None if disabled else on_press,
        padding=(0, pad_x),
        height=height,
        width="fill" if full_width else None,
        radius=t.radius_sm,
        border_color=border_color,
        border_width=1.0 if border_color else 0.0,
        disabled_color=t.text_disabled,
        **colors,
    )


def icon_button(
    name: str,
    on_press: Any = None,
    *,
    size: str = "md",
    variant: str = "ghost",
    color: Optional[str] = None,
    selected: bool = False,
    disabled: bool = False,
    tooltip: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A square, icon-only button (like Zed's ``IconButton``)."""
    t = _theme(theme)
    height, _, _, icon_size = BUTTON_SIZES[size]
    colors = _button_colors(t, variant, None, selected)
    colors.pop("border_color", None)
    if color:
        colors["color"] = t.color(color)
    elif variant == "ghost" and not selected:
        colors["color"] = t.icon_muted
        colors["hover_color"] = t.icon
    widget = _core.button(
        _core.container(_icon(name, size=icon_size), center=True),
        None if disabled else on_press,
        padding=0,
        width=height,
        height=height,
        radius=t.radius_sm,
        disabled_color=t.text_disabled,
        **colors,
    )
    return tooltip_text(widget, tooltip, theme=t) if tooltip else widget


def badge(
    content: Any,
    *,
    tint: str = "accent",
    variant: str = "soft",
    icon: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A small pill. variant: "soft" | "solid" | "outline"."""
    t = _theme(theme)
    base = t.color(tint)
    if variant == "solid":
        bg, fg, border = base, t.on_accent, None
    elif variant == "outline":
        bg, fg, border = "transparent", base, alpha(base, 0.6)
    else:
        bg, fg, border = alpha(base, 0.16), base, None
    parts = [_icon(icon, size=11) if icon else None, _core.text(content, size=11.5, weight="medium", wrap=False)]
    return _core.container(
        _core.row(parts, spacing=4, align="center"),
        padding=(1, 7),
        bg=bg,
        color=fg,
        border_color=border,
        border_width=1.0 if border else 0.0,
        radius=999,
    )


def indicator(color: str = "accent", *, size: float = 6, theme: Optional[Theme] = None) -> _core.Widget:
    """A colored dot (status, unsaved changes, presence...)."""
    t = _theme(theme)
    return _core.container(None, width=size, height=size, bg=t.color(color), radius=size / 2)


_MAC_KEYS = {"cmd": "⌘", "ctrl": "⌃", "alt": "⌥", "shift": "⇧", "enter": "⏎", "escape": "esc",
             "backspace": "⌫", "tab": "⇥", "up": "↑", "down": "↓", "left": "←", "right": "→"}
_WORD_KEYS = {"cmd": "Super", "ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "enter": "Enter",
              "escape": "Esc", "backspace": "Backspace", "tab": "Tab", "up": "↑", "down": "↓",
              "left": "←", "right": "→", "space": "Space"}

#: "auto" (symbols on macOS, words elsewhere), "symbols" or "words".
KEY_STYLE = "auto"


def format_keys(keys: str) -> Sequence[str]:
    """Splits a Zed-style binding (``"ctrl-shift-p"``, ``"cmd-k cmd-s"``) into display labels."""
    style = KEY_STYLE
    if style == "auto":
        style = "symbols" if sys.platform == "darwin" else "words"
    table = _MAC_KEYS if style == "symbols" else _WORD_KEYS
    out = []
    for chord in keys.split():
        parts = chord.split("-") if chord != "-" else ["-"]
        out.append([table.get(p, p.upper() if len(p) == 1 else p.capitalize()) for p in parts])
    return out


def kbd(keys: str, *, size: str = "sm", theme: Optional[Theme] = None) -> _core.Widget:
    """Renders a key binding such as ``"ctrl-shift-p"`` as key caps."""
    t = _theme(theme)
    font_size = 11.0 if size == "xs" else 12.0
    chords = []
    for chord in format_keys(keys):
        caps = [
            _core.container(
                _core.text(k, size=font_size, color=t.text_muted, wrap=False),
                padding=(0, 4) if len(k) > 1 else (0, 5),
                height=font_size + 6,
                align_y="center",
                bg=t.element,
                border_color=t.border_variant,
                border_width=1.0,
                radius=3,
            )
            for k in chord
        ]
        chords.append(_core.row(caps, spacing=2, align="center"))
    return _core.row(chords, spacing=6, align="center")


def divider(*, vertical: bool = False, color: Optional[str] = None, theme: Optional[Theme] = None) -> _core.Widget:
    """A 1px horizontal (or ``vertical``) line, in the theme's border color unless ``color`` is given."""
    t = _theme(theme)
    return _core.rule(vertical=vertical, thickness=1, color=t.color(color) if color else t.border_variant)


def avatar(
    initials: str,
    *,
    color: Optional[str] = None,
    size: float = 22,
    index: int = 0,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A round avatar with initials. ``index`` picks a collaborator color from the theme."""
    t = _theme(theme)
    bg = t.color(color) if color else (t.players[index % len(t.players)] if t.players else t.accent)
    return _core.container(
        _core.text(initials[:2].upper(), size=size * 0.45, weight="semibold", color=t.on_accent, wrap=False),
        width=size,
        height=size,
        center=True,
        bg=bg,
        radius=size / 2,
        border_color=t.border,
        border_width=1.0,
    )


def tooltip_text(
    content: Any,
    text: str,
    *,
    keys: Optional[str] = None,
    position: str = "bottom",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Wraps ``content`` with a Zed-like tooltip (optionally showing its key binding)."""
    t = _theme(theme)
    tip = _core.row(
        [_core.text(text, size=12.5, color=t.text, wrap=False), kbd(keys, theme=t, size="xs") if keys else None],
        spacing=8,
        align="center",
    )
    return _core.tooltip(
        content,
        _core.container(tip, padding=(4, 8)),
        position=position,
        gap=6,
        bg=t.elevated,
        border_color=t.border,
        border_width=1.0,
        radius=t.radius,
        shadow=(t.shadow, (0, 2), 8),
    )


def card(
    content: Any,
    *,
    title: Optional[str] = None,
    actions: Iterable[Any] = (),
    padding: float = 16,
    width: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A bordered surface for grouping content."""
    t = _theme(theme)
    header = None
    if title or actions:
        header = _core.row(
            [label(title or "", weight="semibold", theme=t), _core.space(width="fill"), *actions],
            spacing=4,
            align="center",
        )
    return _core.container(
        _core.column([header, content], spacing=12),
        padding=padding,
        width=width,
        bg=t.surface,
        border_color=t.border_variant,
        border_width=1.0,
        radius=t.radius + 2,
    )
