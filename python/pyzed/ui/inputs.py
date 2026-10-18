"""Form controls styled with the current theme."""

from __future__ import annotations

from typing import Any, Optional, Sequence

from .. import _core
from ..icons import glyph
from ..theme import Theme, alpha
from .base import _theme, label


def input(  # noqa: A001 - mirrors HTML naming
    value: str,
    on_input: Any = None,
    *,
    placeholder: str = "",
    icon: Optional[str] = None,
    on_submit: Any = None,
    id: Optional[str] = None,  # noqa: A002
    size: str = "md",
    secure: bool = False,
    width: Any = "fill",
    borderless: bool = False,
    mono: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A text field. ``on_input`` receives the new text and returns a message (or ``None``)."""
    t = _theme(theme)
    font_size, pad = {"sm": (12.5, (3, 6)), "md": (13.5, (5, 8)), "lg": (15.0, (8, 10))}[size]
    return _core.text_input(
        value,
        placeholder=placeholder,
        on_input=on_input,
        on_submit=on_submit,
        id=id,
        size=font_size,
        font="mono" if mono else None,
        padding=pad,
        width=width,
        secure=secure,
        icon=glyph(icon) if icon else None,
        icon_size=font_size,
        bg="transparent" if borderless else t.editor,
        border_color="transparent" if borderless else t.border,
        hover_border_color="transparent" if borderless else t.border,
        focus_border_color="transparent" if borderless else t.border_focused,
        border_width=0.0 if borderless else 1.0,
        radius=t.radius_sm,
        color=t.text,
        placeholder_color=t.text_placeholder,
        selection_color=t.selection,
        icon_color=t.icon_muted,
    )


def search_input(value: str, on_input: Any = None, *, placeholder: str = "Search…", **kwargs) -> _core.Widget:
    return input(value, on_input, placeholder=placeholder, icon="search", **kwargs)


def switch(
    checked: bool,
    on_toggle: Any = None,
    *,
    label: Optional[str] = None,  # noqa: F811
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """An on/off toggle. ``on_toggle`` receives the new ``bool``."""
    t = _theme(theme)
    return _core.toggler(
        checked,
        label,
        on_toggle=on_toggle,
        size=18,
        text_size=13.5,
        accent=t.accent,
        bg=t.element_active,
        knob_color=t.text if t.is_dark else "#ffffff",
        color=t.text,
    )


def checkbox(
    checked: bool,
    on_toggle: Any = None,
    *,
    label: Optional[str] = None,  # noqa: F811
    theme: Optional[Theme] = None,
) -> _core.Widget:
    t = _theme(theme)
    return _core.checkbox(
        checked,
        label,
        on_toggle=on_toggle,
        size=16,
        text_size=13.5,
        accent=t.accent,
        bg=t.editor,
        border_color=t.border,
        check_color=t.on_accent,
        color=t.text,
    )


def slider(
    value: float,
    on_change: Any = None,
    *,
    min: float = 0.0,  # noqa: A002
    max: float = 1.0,  # noqa: A002
    step: float = 0.01,
    width: Any = "fill",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    t = _theme(theme)
    return _core.slider(
        min, max, value, step=step, on_change=on_change, width=width,
        accent=t.accent, bg=t.element_active, knob_color=t.text, border_color=t.border,
    )


def progress(value: float, *, max: float = 1.0, tint: str = "accent", height: float = 4,  # noqa: A002
             width: Any = "fill", theme: Optional[Theme] = None) -> _core.Widget:
    t = _theme(theme)
    return _core.progress_bar(value, min=0.0, max=max, width=width, height=height,
                              accent=t.color(tint), bg=alpha(t.text, 0.1), radius=height / 2)


def segmented(
    options: Sequence[str],
    selected: str,
    on_select: Any = None,
    *,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A group of mutually exclusive toggle buttons (Zed's ``ToggleButtonGroup``).

    ``on_select`` is called with the chosen option.
    """
    t = _theme(theme)
    buttons = []
    for option in options:
        is_selected = option == selected
        buttons.append(
            _core.button(
                _core.container(label(option, size="sm", color="text" if is_selected else "text_muted", theme=t),
                                height="fill", align_y="center"),
                (lambda o=option: on_select(o)) if on_select else None,
                padding=(0, 10),
                height=24,
                bg=t.element_selected if is_selected else "transparent",
                hover_bg=t.element_selected if is_selected else t.ghost_hover,
                radius=t.radius_sm - 1,
            )
        )
    return _core.container(
        _core.row(buttons, spacing=2),
        padding=2,
        bg=t.element,
        border_color=t.border_variant,
        border_width=1.0,
        radius=t.radius_sm + 1,
    )


def field(title: str, control: Any, *, description: Optional[str] = None,
          theme: Optional[Theme] = None) -> _core.Widget:
    """A labelled form row: title + optional description on the left, control on the right."""
    t = _theme(theme)
    return _core.row(
        [
            _core.column(
                [label(title, theme=t), label(description, size="sm", color="text_muted", theme=t) if description else None],
                spacing=2,
                width="fill",
            ),
            control,
        ],
        spacing=16,
        align="center",
    )
