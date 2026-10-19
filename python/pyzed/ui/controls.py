"""Form controls: selects, radio groups, number fields, split buttons, chips, disclosures and accordions."""

from __future__ import annotations

from typing import Any, Callable, Mapping, NamedTuple, Optional, Sequence, Tuple, Union

from .. import _core
from ..icons import glyph as _glyph
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme, button, label

Option = Union[str, Tuple[Any, str]]


def select(
    options: Sequence[Any],
    selected: Any = None,
    on_select: Any = None,
    *,
    placeholder: str = "Select…",
    width: Any = None,
    size: str = "md",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A themed dropdown (Zed's ``DropdownMenu``) built on ``pz.pick_list``.

    ``on_select`` is called with the chosen option. Options are shown with ``str()``,
    so any value with a readable ``__str__`` works (strings, enums, dataclasses...).
    """
    t = _theme(theme)
    height, pad = {"sm": (22, 6), "md": (28, 8), "lg": (32, 10)}[size]
    options = list(options)
    labels = [str(option) for option in options]
    if callable(on_select) and any(not isinstance(option, str) for option in options):
        # The dropdown works with labels; hand the callback the option object back (a model, an enum...).
        by_label: dict = {}
        for text, option in zip(labels, options):
            by_label.setdefault(text, option)
        user_select = on_select

        def on_select(text: str) -> Any:
            return user_select(by_label.get(text, text))

    return _core.pick_list(
        labels,
        None if selected is None else str(selected),
        on_select,
        placeholder=placeholder,
        width=width,
        padding=((height - 18) / 2, pad),
        text_size=12.5 if size == "sm" else 13.5,
        handle=_glyph("chevron-down"),
        handle_size=12,
        bg=t.element,
        color=t.text,
        placeholder_color=t.text_placeholder,
        handle_color=t.icon_muted,
        border_color=t.border_variant,
        hover_border_color=t.border,
        radius=t.radius_sm,
        menu_bg=t.elevated,
        menu_color=t.text,
        menu_border_color=t.border,
        selected_bg=t.ghost_selected,
        selected_color=t.text,
    )


def radio_group(
    options: Sequence[Option],
    selected: Any,
    on_select: Any = None,
    *,
    horizontal: bool = False,
    spacing: float = 8,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Mutually exclusive choices shown as radio buttons.

    ``options`` are strings or ``(value, label)`` pairs; ``on_select(value)`` is called
    when one is picked.
    """
    t = _theme(theme)
    items = []
    for option in options:
        value, text = option if isinstance(option, tuple) else (option, str(option))
        items.append(
            _core.radio(
                text,
                value == selected,
                (lambda v=value: on_select(v)) if on_select else None,
                size=15,
                text_size=13.5,
                spacing=8,
                accent=t.accent,
                bg=t.element,
                border_color=t.border,
                color=t.text,
            )
        )
    layout = _core.row if horizontal else _core.column
    return layout(items, spacing=spacing * (2 if horizontal else 1))


def _format(value: float, step: float) -> str:
    if float(step).is_integer() and float(value).is_integer():
        return str(int(value))
    decimals = max(0, len(repr(float(step)).split(".")[1].rstrip("0")))
    return f"{value:.{decimals}f}"


def number_field(
    value: float,
    on_change: Any = None,
    *,
    min: Optional[float] = None,  # noqa: A002
    max: Optional[float] = None,  # noqa: A002
    step: float = 1,
    width: float = 120,
    suffix: Optional[str] = None,
    align: str = "center",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A numeric input with −/+ buttons (Zed's ``NumericStepper``).

    ``on_change(value)`` receives the new number, clamped to ``min``/``max``. Typing is
    accepted as long as it parses; anything else is ignored. The number is centered
    between the buttons; ``align="start"`` or ``"end"`` moves it.
    """
    t = _theme(theme)

    def clamp(v: float) -> float:
        if min is not None:
            v = v if v >= min else min
        if max is not None:
            v = v if v <= max else max
        return v

    def typed(text: str):
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return None
        return on_change(clamp(number)) if on_change else None

    def nudge(delta: float):
        return (lambda: on_change(clamp(round(value + delta, 10)))) if on_change else None

    def side(icon: str, delta: float, disabled: bool):
        return _core.button(
            _core.container(_icon(icon, size=12, color=t.text_disabled if disabled else t.icon),
                            height="fill", align_y="center"),
            None if disabled else nudge(delta),
            padding=(0, 6),
            height="fill",
            bg="transparent",
            hover_bg=t.ghost_hover,
            pressed_bg=t.ghost_active,
            radius=t.radius_sm - 1,
        )

    text = _format(value, step)
    return _core.container(
        _core.row(
            [
                side("minus", -step, min is not None and value <= min),
                _core.text_input(
                    text,
                    on_input=typed,
                    width="fill",
                    size=13,
                    padding=(0, 2),
                    bg="transparent",
                    border_width=0.0,
                    color=t.text,
                    selection_color=t.selection,
                    align_x=align,
                ),
                label(suffix, size="sm", color="text_muted", theme=t) if suffix else None,
                side("plus", step, max is not None and value >= max),
            ],
            align="center",
            spacing=2,
            height="fill",
        ),
        width=width,
        height=28,
        padding=2,
        bg=t.element,
        border_color=t.border_variant,
        border_width=1.0,
        radius=t.radius_sm,
    )


def split_button(
    content: Any,
    on_press: Any = None,
    on_menu: Any = None,
    *,
    icon: Optional[str] = None,
    variant: str = "filled",
    size: str = "md",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A button with a separate chevron for more options (Zed's ``SplitButton``).

    ``on_press`` runs the main action; ``on_menu`` usually opens a ``ui.menu`` popover.
    """
    t = _theme(theme)
    return _core.row(
        [
            button(content, on_press, icon=icon, variant=variant, size=size, theme=t),
            button(None, on_menu, icon="chevron-down", variant=variant, size=size, theme=t),
        ],
        spacing=1,
    )


def chip(
    content: Any,
    *,
    on_press: Any = None,
    on_remove: Any = None,
    selected: bool = False,
    icon: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A compact tag, optionally clickable (filters) and removable (an ``x`` at the end)."""
    t = _theme(theme)
    color = t.text if selected else t.text_muted
    parts = [
        _icon(icon, size=12, color=color) if icon else None,
        _core.text(content, size=12, color=color, wrap=False),
        _core.button(
            _icon("x", size=11, color=t.icon_muted),
            on_remove,
            padding=1,
            bg="transparent",
            hover_bg=t.ghost_hover,
            radius=999,
        )
        if on_remove is not None
        else None,
    ]
    body = _core.row(parts, spacing=4, align="center")
    bg = alpha(t.accent, 0.18) if selected else t.element
    border = alpha(t.accent, 0.5) if selected else t.border_variant
    if on_press is None:
        return _core.container(body, padding=(2, 8), bg=bg, border_color=border, border_width=1.0, radius=999)
    return _core.button(
        body,
        on_press,
        padding=(2, 8),
        bg=bg,
        hover_bg=alpha(t.accent, 0.24) if selected else t.element_hover,
        border_color=border,
        border_width=1.0,
        radius=999,
    )


def disclosure(
    title: Any,
    content: Any,
    *,
    open: bool,  # noqa: A002
    on_toggle: Any = None,
    end: Any = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A collapsible section: a header with a chevron that shows or hides ``content``.

    The open state is yours (like every Pyzed widget): flip it in ``on_toggle``.
    """
    t = _theme(theme)
    header = _core.button(
        _core.row(
            [
                _icon("chevron-down" if open else "chevron-right", size=14, color=t.icon_muted),
                label(title, weight="medium", theme=t) if isinstance(title, str) else title,
                _core.space(width="fill"),
                end,
            ],
            spacing=6,
            align="center",
        ),
        on_toggle,
        width="fill",
        padding=(4, 6),
        bg="transparent",
        hover_bg=t.ghost_hover,
        radius=t.radius_sm,
    )
    return _core.column([header, _core.container(content, padding=(4, 0, 4, 26)) if open else None], spacing=2)


class AccordionSection(NamedTuple):
    """One section of an ``accordion``: a ``key``, its ``title``, its ``content`` and an optional header ``end``."""

    key: str
    title: str
    content: Any
    icon: Optional[str] = None
    end: Any = None


def accordion(
    sections: Sequence[Any],
    *,
    open: Any = (),  # noqa: A002
    on_toggle: Optional[Callable[[str], Any]] = None,
    icons: Optional[Mapping[str, str]] = None,
    spacing: float = 8,
    padding: Any = (6, 12, 10, 12),
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Stacked collapsible sections separated by dividers, like the panels of Zed's settings.

    ``sections`` are ``(id, title, content)`` tuples or ``AccordionSection`` items; ``open``
    is the set of open ids (or a ``{id: bool}`` dict, or ``True`` for all) and
    ``on_toggle(id)`` flips one. ``icons`` maps ids to Lucide icons and ``spacing`` is the
    space around the dividers between sections. Headers span the
    whole width, so content lines up with the rest of the panel.
    """
    t = _theme(theme)
    if open is True:
        is_open = lambda k: True  # noqa: E731
    elif isinstance(open, Mapping):
        is_open = lambda k: bool(open.get(k, False))  # noqa: E731
    else:
        is_open = lambda k: k in open  # noqa: E731
    parts: list = []
    for index, raw in enumerate(sections):
        section = raw if isinstance(raw, AccordionSection) else AccordionSection(*raw)
        shown = is_open(section.key)
        icon_name = section.icon or (icons or {}).get(section.key)
        header = _core.button(
            _core.row(
                [
                    _icon("chevron-down" if shown else "chevron-right", size=14, color=t.icon_muted),
                    _icon(icon_name, size=14, color=t.icon_muted) if icon_name else None,
                    label(section.title, size="sm", weight="semibold", wrap=False, theme=t),
                    _core.space(width="fill"),
                ],
                spacing=8,
                align="center",
            ),
            (lambda k=section.key: on_toggle(k)) if on_toggle else None,
            width="fill",
            padding=(8, 12),
            bg="transparent",
            hover_bg=t.ghost_hover,
            radius=0,
        )
        if section.end is not None:
            header = _core.stack([header, _core.container(section.end, width="fill", height="fill",
                                                          align_x="end", align_y="center", padding=(0, 8))])
        if index:
            parts.append(_core.container(_core.container(width="fill", height=1, bg=t.border_variant),
                                         width="fill", padding=(spacing / 2, 0)))
        parts.append(header)
        if shown:
            parts.append(_core.container(section.content, width="fill", padding=padding))
    return _core.column(parts, width="fill")


def toggle_group(
    options: Sequence[Tuple[Any, str]],
    selected: Any,
    on_select: Callable[[Any], Any],
    *,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Icon-only segmented control: ``options`` are ``(value, icon_name)`` pairs."""
    t = _theme(theme)
    buttons = []
    for value, icon_name in options:
        active = value == selected
        buttons.append(
            _core.button(
                _icon(icon_name, size=14, color=t.text if active else t.icon_muted),
                lambda v=value: on_select(v),
                padding=(4, 6),
                bg=t.element_selected if active else "transparent",
                hover_bg=t.element_selected if active else t.ghost_hover,
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
