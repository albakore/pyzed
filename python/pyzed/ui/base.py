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
    """Text using a theme color token (``"text"``, ``"text_muted"``, ``"accent"``...) or a hex color.

    ``selectable=True`` lets the mouse select it (Ctrl+C copies); a string names a selection group,
    so one drag can select across every text of the group (the lines of a log, a chat's messages).
    """
    t = _theme(theme)
    if kwargs.get("selectable") and kwargs.get("selection_color") is None:
        kwargs["selection_color"] = t.selection
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


# Widgets and keyword arguments that only depend on the theme and a few plain values (the inside
# of a text button, key caps, tooltip bubbles...). Views build the same few over and over, and
# widgets are immutable, so one copy serves every place that shows them. The theme is kept to
# tell a reused id apart. Shared values must not be changed: copy them first.
_SHARED: dict = {}


def _shared(t: Theme, key: tuple, build):
    full = (id(t),) + key
    hit = _SHARED.get(full)
    if hit is None or hit[0] is not t:
        if len(_SHARED) > 2048:
            _SHARED.clear()
        hit = _SHARED[full] = (t, build())
    return hit[1]


def _button_kwargs(t: Theme, variant: str, tint: Optional[str], selected: bool, size: str, full_width: bool):
    """The keyword arguments of ``_core.button`` for these settings (shared: copy before changing)."""
    def build():
        colors = _button_colors(t, variant, tint, selected)
        border_color = colors.pop("border_color", None)
        kwargs = {
            "padding": (0, BUTTON_SIZES[size][1]),
            "height": BUTTON_SIZES[size][0],
            "width": "fill" if full_width else None,
            "radius": t.radius_sm,
            "border_color": border_color,
            "border_width": 1.0 if border_color else 0.0,
            "disabled_color": t.text_disabled,
        }
        kwargs.update(colors)
        return kwargs

    return _shared(t, ("button", variant, tint, selected, size, full_width), build)


def _button_inner(t: Theme, content, icon, icon_position, icon_color, size, keys, full_width, loading):
    _, _, font_size, icon_size = BUTTON_SIZES[size]
    parts = []
    glyph = _icon(icon, size=icon_size, color=t.color(icon_color) if icon_color else None) if icon else None
    if loading:
        from .display import spinner

        glyph, icon_position = spinner(size=icon_size, tint=icon_color or "text_muted", theme=t), "start"
    if glyph is not None and icon_position == "start":
        parts.append(glyph)
    if content is not None:
        parts.append(content if isinstance(content, _core.Widget) else _core.text(content, size=font_size, wrap=False))
    if glyph is not None and icon_position == "end":
        parts.append(glyph)
    if keys:
        parts.append(_core.space(width=4))
        parts.append(kbd(keys, theme=t, size="xs"))
    return _core.container(
        _core.row(parts, spacing=6, align="center"),
        height="fill",
        width="fill" if full_width else None,
        align_y="center",
        align_x="center" if full_width else None,
    )


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
    loading: bool = False,
    tooltip: Optional[str] = None,
    theme: Optional[Theme] = None,
    **style,
) -> _core.Widget:
    """A Zed-style button.

    variant: "filled" | "ghost" | "subtle" | "outline" | "solid" | "tinted" | "accent" | "error" | ...
    size:    "xs" | "sm" | "md" | "lg"
    keys:    optional key binding shown at the end, e.g. ``"ctrl-s"``.
    loading: shows a spinner in place of the icon and ignores presses (it spins by itself).
    tooltip: text shown on hover (with ``keys`` in it too).

    Events:
        ``on_press()``: Message or callable sent on press. ``None`` disables the control.
    """
    t = _theme(theme)
    if loading:
        disabled = True
    if loading or not (content is None or isinstance(content, str)):
        inner = _button_inner(t, content, icon, icon_position, icon_color, size, keys, full_width, loading)
    else:
        # Plain text and icons: the same few insides come back on every view.
        inner = _shared(t, ("button_inner", content, icon, icon_position, icon_color, size, keys, full_width),
                        lambda: _button_inner(t, content, icon, icon_position, icon_color, size, keys,
                                              full_width, False))
    kwargs = _button_kwargs(t, variant, tint, selected, size, full_width)
    if style:
        # The caller's ``**style`` goes last, so e.g. ``radius=`` or ``padding=`` override the defaults.
        kwargs = {**kwargs, **style}
        if "border_color" in style and "border_width" not in style:
            kwargs["border_width"] = 1.0 if style["border_color"] else 0.0
    widget = _core.button(inner, None if disabled else on_press, **kwargs)
    return tooltip_text(widget, tooltip, keys=keys, theme=t) if tooltip else widget


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
    keys: Optional[str] = None,
    tint: Optional[str] = None,
    loading: bool = False,
    indicator: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A square, icon-only button (like Zed's ``IconButton``).

    ``keys`` shows a key binding in the tooltip; ``tint`` colors it (``"error"``,
    ``"accent"``...); ``loading`` swaps the icon for a spinner and ignores presses;
    ``indicator`` adds a small dot in that color at the top right (unread, changes...).

    Events:
        ``on_press()``: Message or callable sent on press. ``None`` disables the control.
    """
    t = _theme(theme)
    if loading:
        disabled = True
        content = _icon_button_content(t, name, size, indicator, True)
    else:
        content = _shared(t, ("icon_button", name, size, indicator),
                          lambda: _icon_button_content(t, name, size, indicator, False))
    widget = _core.button(content, None if disabled else on_press,
                          **_icon_button_kwargs(t, variant, tint, selected, size, color))
    return tooltip_text(widget, tooltip, keys=keys, theme=t) if tooltip else widget


def _icon_button_kwargs(t: Theme, variant: str, tint: Optional[str], selected: bool, size: str,
                        color: Optional[str]):
    def build():
        height = BUTTON_SIZES[size][0]
        colors = _button_colors(t, variant, tint, selected)
        colors.pop("border_color", None)
        if color:
            colors["color"] = t.color(color)
        elif variant == "ghost" and not selected and not tint:
            colors["color"] = t.icon_muted
            colors["hover_color"] = t.icon
        return dict(padding=0, width=height, height=height, radius=t.radius_sm, disabled_color=t.text_disabled,
                    **colors)

    return _shared(t, ("icon_button_kwargs", variant, tint, selected, size, color), build)


def _icon_button_content(t: Theme, name: str, size: str, indicator: Optional[str], loading: bool):
    icon_size = BUTTON_SIZES[size][3]
    if loading:
        from .display import spinner

        glyph = spinner(size=icon_size, tint="text_muted", theme=t)
    else:
        glyph = _icon(name, size=icon_size)
    content = _core.container(glyph, center=True)
    if indicator:
        dot = _core.container(None, width=6, height=6, bg=t.color(indicator), radius=3, border_color=t.background,
                              border_width=1.0)
        content = _core.stack([content, _core.container(dot, width="fill", height="fill", align_x="end",
                                                        align_y="start", padding=3)])
    return content


def badge(
    content: Any,
    *,
    tint: str = "accent",
    variant: str = "soft",
    icon: Optional[str] = None,
    size: str = "md",
    on_press: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A small pill. variant: "soft" | "solid" | "outline"; size: "sm" | "md" | "lg".

    ``on_press`` makes it clickable (a filter, a link to the issues it counts...).

    Events:
        ``on_press()``: Makes it clickable.
    """
    t = _theme(theme)
    font_size, pad, icon_size = {"sm": (10.5, (0, 5), 10), "md": (11.5, (1, 7), 11), "lg": (12.5, (2, 9), 12)}[size]
    base = t.color(tint)
    if variant == "solid":
        bg, fg, border = base, t.on_accent, None
    elif variant == "outline":
        bg, fg, border = "transparent", base, alpha(base, 0.6)
    else:
        bg, fg, border = alpha(base, 0.16), base, None
    parts = [_icon(icon, size=icon_size) if icon else None,
             _core.text(content, size=font_size, weight="medium", wrap=False)]
    pill = _core.container(
        _core.row(parts, spacing=4, align="center"),
        padding=pad,
        bg=bg,
        color=fg,
        border_color=border,
        border_width=1.0 if border else 0.0,
        radius=999,
    )
    return pill if on_press is None else pill.on(click=on_press, cursor="pointer")


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


def keys_text(keys: str) -> str:
    """A binding as plain text for a label or a status line: ``"ctrl-shift-p"`` -> ``"Ctrl+Shift+P"``
    (``"⌃⇧P"`` with macOS symbols), chords separated by a space. Tooltips and menus take ``keys=``
    and draw key caps instead."""
    joiner = "" if (KEY_STYLE == "symbols" or (KEY_STYLE == "auto" and sys.platform == "darwin")) else "+"
    return " ".join(joiner.join(chord) for chord in format_keys(keys))


def kbd(keys: str, *, size: str = "sm", theme: Optional[Theme] = None) -> _core.Widget:
    """Renders a key binding such as ``"ctrl-shift-p"`` as key caps."""
    t = _theme(theme)
    return _shared(t, ("kbd", keys, size, KEY_STYLE), lambda: _kbd(t, keys, size))


def _kbd(t: Theme, keys: str, size: str) -> _core.Widget:
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


def key_focus(content: Any, on_key: Any, *, keys: Sequence[str], id: Optional[str] = None,  # noqa: A002
              radius: Optional[float] = None, theme: Optional[Theme] = None) -> _core.Widget:
    """Lets a control take the keyboard focus (``pz.focusable``) with the theme's focus ring.

    A click or Tab focuses it; while focused, the combos in ``keys`` call ``on_key(combo)``
    instead of reaching the app's ``on_key``. ``on_key=None`` (a disabled control) leaves
    ``content`` as it is.
    """
    if on_key is None:
        return content
    t = _theme(theme)
    return _core.focusable(content, on_key, keys=list(keys), id=id, ring_color=t.border_focused,
                           ring_radius=t.radius_sm if radius is None else radius)


#: The keys that move between the options of a choice control (segmented, radio group).
CHOICE_KEYS = ("left", "right", "up", "down", "home", "end")


def step_choice(values: Sequence[Any], selected: Any, combo: str) -> Any:
    """The value ``combo`` (one of ``CHOICE_KEYS``) moves to from ``selected``; ``None`` if it stays."""
    if not values:
        return None
    index = values.index(selected) if selected in values else -1
    if combo == "home":
        target = 0
    elif combo == "end":
        target = len(values) - 1
    elif combo in ("left", "up"):
        target = max(index - 1, 0) if index >= 0 else len(values) - 1
    elif combo in ("right", "down"):
        target = min(index + 1, len(values) - 1)
    else:
        return None
    return None if target == index else values[target]


def send(handler: Any, *args: Any) -> Any:
    """Calls ``handler`` with ``args`` when it is callable; otherwise it is a message and is returned."""
    return handler(*args) if callable(handler) else handler


def divider(*, vertical: bool = False, color: Optional[str] = None, label: Optional[str] = None,
            spacing: float = 0, theme: Optional[Theme] = None) -> _core.Widget:
    """A 1px horizontal (or ``vertical``) line, in the theme's border color unless ``color`` is given.

    ``label`` writes a muted text in the middle of a horizontal line ("or", a date...);
    ``spacing`` adds that much space on both sides of the line.
    """
    t = _theme(theme)
    line_color = t.color(color) if color else t.border_variant
    line = _core.rule(vertical=vertical, thickness=1, color=line_color)
    if label and not vertical:
        line = _core.row([_core.rule(thickness=1, color=line_color),
                          _core.text(label, size=12, color=t.text_muted, wrap=False),
                          _core.rule(thickness=1, color=line_color)], spacing=8, align="center", width="fill")
    if spacing:
        line = _core.container(line, padding=(0, spacing) if vertical else (spacing, 0),
                               width=None if vertical else "fill", height="fill" if vertical else None)
    return line


def avatar(
    initials: str,
    *,
    color: Optional[str] = None,
    size: float = 22,
    index: int = 0,
    image: Any = None,
    status: Optional[str] = None,
    tooltip: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A round avatar with initials. ``index`` picks a collaborator color from the theme.

    ``image`` (a path or bytes) shows a picture instead of the initials; ``status`` adds a
    presence dot: ``"online"``, ``"away"``, ``"busy"``, ``"offline"`` or a color;
    ``tooltip`` names the person on hover.
    """
    t = _theme(theme)
    bg = t.color(color) if color else (t.players[index % len(t.players)] if t.players else t.accent)
    face = (_core.image(image, width=size, height=size, content_fit="cover", radius=size / 2) if image is not None else
            _core.text(initials[:2].upper(), size=size * 0.45, weight="semibold", color=t.on_accent, wrap=False))
    widget = _core.container(
        face,
        width=size,
        height=size,
        center=True,
        bg=bg,
        radius=size / 2,
        clip=image is not None,
        border_color=t.border,
        border_width=1.0,
    )
    if status:
        dot_size = max(6.0, size * 0.32)
        dot_color = {"online": t.success, "away": t.warning, "busy": t.error, "offline": t.text_disabled}.get(
            status, None) or t.color(status)
        dot = _core.container(None, width=dot_size, height=dot_size, bg=dot_color, radius=dot_size / 2,
                              border_color=t.background, border_width=1.5)
        widget = _core.stack([widget, _core.container(dot, width="fill", height="fill", align_x="end", align_y="end")],
                             width=size, height=size)
    return tooltip_text(widget, tooltip, theme=t) if tooltip else widget


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
    tip = _shared(t, ("tooltip", text, keys), lambda: _core.container(_core.row(
        [_core.text(text, size=12.5, color=t.text, wrap=False), kbd(keys, theme=t, size="xs") if keys else None],
        spacing=8,
        align="center",
    ), padding=(4, 8)))
    style = _shared(t, ("tooltip_style",), lambda: dict(
        gap=6, bg=t.elevated, border_color=t.border, border_width=1.0, radius=t.radius, shadow=(t.shadow, (0, 2), 8)))
    return _core.tooltip(content, tip, position=position, **style)


def card(
    content: Any,
    *,
    title: Optional[str] = None,
    actions: Iterable[Any] = (),
    padding: float = 16,
    width: Any = None,
    footer: Iterable[Any] = (),
    on_press: Any = None,
    selected: bool = False,
    elevated: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A bordered surface for grouping content.

    ``footer`` widgets go at the bottom right (buttons); ``on_press`` makes the whole card
    clickable (a choice, a project to open) and ``selected`` outlines it in the accent color;
    ``elevated`` adds a shadow.

    Events:
        ``on_press()``: Makes the whole card clickable.
    """
    t = _theme(theme)
    footer = list(footer)
    header = None
    if title or actions:
        header = _core.row(
            [label(title or "", weight="semibold", theme=t), _core.space(width="fill"), *actions],
            spacing=4,
            align="center",
        )
    bottom = _core.row([_core.space(width="fill"), *footer], spacing=8, align="center") if footer else None
    box = _core.container(
        _core.column([header, content, bottom], spacing=12),
        padding=padding,
        width=width,
        bg=t.surface,
        border_color=t.accent if selected else t.border_variant,
        border_width=1.0,
        radius=t.radius + 2,
        shadow=(t.shadow, (0, 4), 16) if elevated else None,
    )
    return box if on_press is None else box.on(click=on_press, cursor="pointer")
