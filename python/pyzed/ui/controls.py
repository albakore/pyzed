"""Form controls: selects, radio groups, number fields, split buttons, chips, disclosures and accordions."""

from __future__ import annotations

from typing import Any, Callable, List, Mapping, NamedTuple, Optional, Sequence, Tuple, Union

from .. import _core
from ..component import Component as _Component
from ..icons import glyph as _glyph
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import CHOICE_KEYS, _theme, button, key_focus, label, send, step_choice

Option = Union[str, Tuple[Any, str]]


def select(
    options: Sequence[Any],
    selected: Any = None,
    on_select: Any = None,
    *,
    placeholder: str = "Select…",
    width: Any = None,
    size: str = "md",
    disabled: bool = False,
    invalid: bool = False,
    on_open: Any = None,
    on_close: Any = None,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A themed dropdown (Zed's ``DropdownMenu``) built on ``pz.pick_list``.

    ``on_select`` is called with the chosen option. Options are shown with ``str()``,
    so any value with a readable ``__str__`` works (strings, enums, dataclasses...).
    ``disabled`` greys it out, ``invalid`` paints the border red, and ``on_open`` /
    ``on_close`` run when the menu opens and closes.

    It takes the keyboard focus like a text field (a click, Tab or ``Command.focus(id)``)
    and keeps it after a choice closes the menu: ↑/↓ then pick the previous or next option
    without opening it, Home/End the first and last, and typing jumps to an option by its
    first letters. Enter, Space, Alt+↓ or F4 open the menu; there ↑/↓ move, Enter picks
    and Escape closes.

    Events:
        ``on_select(item)``: Callable that receives the chosen item.
        ``on_open()``: Sent when the menu opens.
        ``on_close()``: Sent when the menu closes.
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

    if disabled:
        on_select = None
    return _core.pick_list(
        labels,
        None if selected is None else str(selected),
        on_select,
        on_open=None if disabled else on_open,
        on_close=None if disabled else on_close,
        placeholder=placeholder,
        width=width,
        padding=((height - 18) / 2, pad),
        text_size=12.5 if size == "sm" else 13.5,
        handle=_glyph("chevron-down"),
        handle_size=12,
        bg=t.element,
        color=t.text_disabled if disabled else t.text,
        placeholder_color=t.text_placeholder,
        handle_color=t.text_disabled if disabled else t.icon_muted,
        border_color=t.error if invalid else t.border_variant,
        hover_border_color=t.error if invalid else (t.border_variant if disabled else t.border),
        radius=t.radius_sm,
        menu_bg=t.elevated,
        menu_color=t.text,
        menu_border_color=t.border,
        selected_bg=t.ghost_selected,
        selected_color=t.text,
        focus_border_color=t.error if invalid else t.border_focused,
        id=id,
    )


def radio_group(
    options: Sequence[Option],
    selected: Any,
    on_select: Any = None,
    *,
    horizontal: bool = False,
    spacing: float = 8,
    disabled: Any = False,
    descriptions: Optional[Mapping[Any, str]] = None,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Mutually exclusive choices shown as radio buttons.

    ``options`` are strings or ``(value, label)`` pairs; ``on_select(value)`` is called
    when one is picked. ``disabled`` is ``True`` for all of them or a collection of the
    values to disable; ``descriptions`` maps values to a muted line under their label.
    A click or Tab gives the group the keyboard focus; then the arrows pick the previous
    or next choice and Home/End the first and last. ``id`` lets ``Command.focus(id)`` focus it.

    Events:
        ``on_select(value)``: Callable that receives the chosen value.
    """
    t = _theme(theme)
    items = []
    enabled = []
    for option in options:
        value, text = option if isinstance(option, tuple) else (option, str(option))
        off = disabled is True or (not isinstance(disabled, bool) and value in disabled)
        if not off:
            enabled.append(value)
        item = _core.radio(
            text,
            value == selected,
            (lambda v=value: on_select(v)) if on_select and not off else None,
            size=15,
            text_size=13.5,
            spacing=8,
            accent=alpha(t.accent, 0.4) if off else t.accent,
            bg=t.element,
            border_color=t.border_variant if off else t.border,
            color=t.text_disabled if off else t.text,
        )
        note = (descriptions or {}).get(value)
        if note:
            item = _core.column([item, _core.container(label(note, size="sm", color="text_muted", theme=t),
                                                       padding=(0, 0, 0, 23))], spacing=2)
        items.append(item)
    layout = _core.row if horizontal else _core.column
    group = layout(items, spacing=spacing * (2 if horizontal else 1))

    def move(combo: str) -> Any:
        target = step_choice(enabled, selected, combo)
        return None if target is None else send(on_select, target)

    return key_focus(group, move if on_select and enabled else None, keys=CHOICE_KEYS, id=id, theme=t)


def _format(value: float, step: float) -> str:
    if float(step).is_integer() and float(value).is_integer():
        return str(int(value))
    decimals = max(0, len(repr(float(step)).split(".")[1].rstrip("0")))
    return f"{value:.{decimals}f}"


#: The number being dragged (``number_field``): its value when the drag started and the pixels moved since.
_SCRUB: dict = {"start": 0.0, "dx": 0.0}


def _scrubber(value: float, on_change: Any, clamp: Any, step: float, drag_step: Optional[float],
              decimals: Optional[int]) -> Any:
    """``on_scrub(dx)`` of a number field: the value it had when the drag started plus one ``drag_step`` per
    pixel moved (one per three pixels for steps under 1, so small ranges stay controllable)."""
    unit = float(drag_step) if drag_step else (step if step <= 1 else 1.0)
    pixels = 3.0 if unit < 1 else 1.0
    places = decimals if decimals is not None else max(0, len(repr(float(unit)).split(".")[1].rstrip("0")))

    def scrub(dx: float) -> Any:
        _SCRUB["dx"] = _SCRUB.get("dx", 0.0) + dx
        new = clamp(round(float(_SCRUB.get("start", value)) + int(_SCRUB["dx"] / pixels) * unit, places))
        return None if new == value else on_change(new)

    return scrub


def number_field(
    value: float,
    on_change: Any = None,
    *,
    min: Optional[float] = None,  # noqa: A002
    max: Optional[float] = None,  # noqa: A002
    step: float = 1,
    width: float = 120,
    suffix: Optional[str] = None,
    prefix: Optional[str] = None,
    align: str = "center",
    decimals: Optional[int] = None,
    disabled: bool = False,
    invalid: bool = False,
    id: Optional[str] = None,  # noqa: A002
    on_submit: Any = None,
    steppers: bool = True,
    drag: bool = True,
    drag_step: Optional[float] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A numeric input with −/+ buttons (Zed's ``NumericStepper``) that you can also drag, like Figma's.

    ``on_change(value)`` receives the new number, clamped to ``min``/``max``. Press and move
    the mouse sideways over the number to change it (``drag_step`` per pixel: ``step`` up to
    1 by default); double-click it to type a value, and Enter, Escape or a click outside to
    finish. Typing is accepted as long as it parses; anything else is ignored. The number is
    centered between the buttons; ``align="start"`` or ``"end"`` moves it. Once clicked, the
    ↑/↓ keys step it (with Shift, ten steps) and Home/End jump to ``min``/``max``.
    ``decimals`` fixes how many decimals it shows (by default, as many as ``step``).
    ``steppers=False`` leaves out the −/+ buttons (a compact field, as in a property grid)
    and ``drag=False`` makes it a plain text field.

    Events:
        ``on_change(value)``: Callable that receives the new value.
        ``on_submit()``: Sent on Enter.
    """
    t = _theme(theme)
    if disabled:
        on_change = None

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

    def side(icon: str, delta: float, off: bool):
        return _core.button(
            _core.container(_icon(icon, size=12, color=t.text_disabled if off else t.icon),
                            height="fill", align_y="center"),
            None if off else nudge(delta),
            padding=(0, 6),
            height="fill",
            bg="transparent",
            hover_bg=t.ghost_hover,
            pressed_bg=t.ghost_active,
            radius=t.radius_sm - 1,
        )

    def key(event: Any):
        if on_change is None:
            return None
        steps = 10 if "shift" in (event.key or "") else 1
        name = (event.key or "").rsplit("-", 1)[-1]
        if name == "up":
            return on_change(clamp(round(value + step * steps, 10)))
        if name == "down":
            return on_change(clamp(round(value - step * steps, 10)))
        if name == "home" and min is not None:
            return on_change(min)
        if name == "end" and max is not None:
            return on_change(max)
        return None

    text = f"{value:.{decimals}f}" if decimals is not None else _format(value, step)
    muted = "text_disabled" if disabled else "text_muted"
    field = _core.text_input(
        text,
        on_input=typed if on_change else None,
        on_submit=None if disabled else on_submit,
        id=id,
        width="fill",
        size=13,
        padding=(0, 2 if steppers else 4),
        bg="transparent",
        border_width=0.0,
        color=t.text_disabled if disabled else t.text,
        selection_color=t.selection,
        align_x=align,
    )
    if drag and on_change is not None:
        field = _core.scrub(field, _scrubber(value, on_change, clamp, step, drag_step, decimals),
                            on_start=lambda: _SCRUB.update(start=value, dx=0.0))
    box = _core.container(
        _core.row(
            [
                side("minus", -step, disabled or (min is not None and value <= min)) if steppers else None,
                label(prefix, size="sm", color=muted, theme=t) if prefix else None,
                field,
                label(suffix, size="sm", color=muted, theme=t) if suffix else None,
                side("plus", step, disabled or (max is not None and value >= max)) if steppers else None,
            ],
            align="center",
            spacing=2,
            height="fill",
        ),
        width=width,
        height=28,
        padding=2,
        bg=t.element,
        border_color=t.error if invalid else t.border_variant,
        border_width=1.0,
        radius=t.radius_sm,
    )
    return box if disabled else box.on(key_down=key)


def split_button(
    content: Any,
    on_press: Any = None,
    on_menu: Any = None,
    *,
    icon: Optional[str] = None,
    variant: str = "filled",
    tint: Optional[str] = None,
    size: str = "md",
    disabled: bool = False,
    tooltip: Optional[str] = None,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A button with a separate chevron for more options (Zed's ``SplitButton``).

    ``on_press`` runs the main action; ``on_menu`` usually opens a ``ui.menu`` popover.

    Events:
        ``on_press()``: Message or callable sent on press. ``None`` disables the control.
        ``on_menu()``: Message or callable for the menu button.
    """
    from .base import tooltip_text

    t = _theme(theme)
    main = button(content, on_press, icon=icon, variant=variant, tint=tint, size=size, disabled=disabled, theme=t)
    return _core.row(
        [
            tooltip_text(main, tooltip, theme=t) if tooltip else main,
            button(None, on_menu, icon="chevron-down", variant=variant, tint=tint, size=size, disabled=disabled,
                   theme=t),
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
    tint: str = "accent",
    disabled: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A compact tag, optionally clickable (filters) and removable (an ``x`` at the end).

    ``tint`` colors it when selected; ``disabled`` greys it out and ignores presses.

    Events:
        ``on_press()``: Message or callable sent on press. ``None`` disables the control.
        ``on_remove()``: Shows a ✕ that sends this when clicked.
    """
    t = _theme(theme)
    removable = on_remove is not None
    if disabled:
        on_press = on_remove = None
    accent = t.color(tint)
    color = t.text_disabled if disabled else (t.text if selected else t.text_muted)
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
        if removable
        else None,
    ]
    body = _core.row(parts, spacing=4, align="center")
    bg = alpha(accent, 0.18) if selected else t.element
    border = alpha(accent, 0.5) if selected else t.border_variant
    if on_press is None:
        return _core.container(body, padding=(2, 8), bg=bg, border_color=border, border_width=1.0, radius=999)
    return _core.button(
        body,
        on_press,
        padding=(2, 8),
        bg=bg,
        hover_bg=alpha(accent, 0.24) if selected else t.element_hover,
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

    Events:
        ``on_toggle()``: Message or callable when the header is clicked.
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

    Events:
        ``on_toggle(key)``: Called with the key of the clicked header.
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
    options: Sequence[Tuple[Any, ...]],
    selected: Any,
    on_select: Optional[Callable[[Any], Any]] = None,
    *,
    disabled: Any = False,
    multiple: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Icon-only segmented control: ``options`` are ``(value, icon_name)`` or
    ``(value, icon_name, tooltip)``.

    With ``multiple=True``, ``selected`` is a collection and each button toggles its value
    on or off (``on_select`` gets the value). ``disabled`` is ``True`` for all of them or a
    collection of the values to disable.

    Events:
        ``on_select(value)``: Callable that receives the chosen item.
    """
    from .base import tooltip_text

    t = _theme(theme)
    buttons = []
    for value, icon_name, *rest in options:
        active = value in selected if multiple else value == selected
        off = disabled is True or (not isinstance(disabled, bool) and value in disabled)
        item = _core.button(
            _icon(icon_name, size=14, color=t.text_disabled if off else (t.text if active else t.icon_muted)),
            None if off or on_select is None else (lambda v=value: on_select(v)),
            padding=(4, 6),
            bg=t.element_selected if active else "transparent",
            hover_bg=t.element_selected if active else t.ghost_hover,
            radius=t.radius_sm - 1,
        )
        buttons.append(tooltip_text(item, rest[0], theme=t) if rest and rest[0] else item)
    return _core.container(
        _core.row(buttons, spacing=2),
        padding=2,
        bg=t.element,
        border_color=t.border_variant,
        border_width=1.0,
        radius=t.radius_sm + 1,
    )


def rating(
    value: float,
    on_change: Optional[Callable[[int], Any]] = None,
    *,
    max: int = 5,  # noqa: A002
    icon: str = "star",
    size: float = 18,
    tint: str = "warning",
    clearable: bool = True,
    disabled: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A row of ``max`` stars (or any Lucide ``icon``) where the first ``value`` are lit.

    Clicking a star sends its number; with ``clearable`` a click on the current one sends 0.
    Without ``on_change`` (or ``disabled``) it only shows the value, rounded to the nearest
    star, like a product's score. A click or Tab gives it the keyboard focus; then the arrows
    change it by one and Home/End jump to 0 and ``max``.

    Events:
        ``on_change(value)``: Callable that receives the number of stars picked (0 to ``max``).
    """
    t = _theme(theme)
    lit = int(round(value or 0))
    on = t.text_disabled if disabled else t.color(tint)
    off = t.border if disabled else t.text_placeholder
    active = on_change is not None and not disabled
    stars = []
    for n in range(1, int(max) + 1):
        star = _core.text(_glyph(icon), size=size, color=on if n <= lit else off, font="icons", line_height=1.0,
                          wrap=False)
        if active:
            star = _core.button(star, lambda n=n: on_change(0 if clearable and n == lit else n), padding=1,
                                bg="transparent", hover_bg=t.ghost_hover, radius=t.radius_sm)
        stars.append(star)
    row = _core.row(stars, spacing=0 if active else 2, align="center")
    if not active:
        return row

    def nudge(combo: str) -> Any:
        new = {"home": 0, "end": int(max)}.get(combo, lit + (1 if combo in ("right", "up") else -1))
        new = 0 if new < 0 else int(max) if new > max else new
        return None if new == lit else on_change(new)

    return key_focus(row, nudge, keys=("left", "right", "up", "down", "home", "end"), radius=t.radius_sm, theme=t)


def tag_input(
    tags: Sequence[str],
    on_change: Optional[Callable[[List[str]], Any]] = None,
    *,
    text: str = "",
    on_input: Optional[Callable[[str], Any]] = None,
    placeholder: str = "",
    suggestions: Sequence[str] = (),
    max_tags: Optional[int] = None,
    unique: bool = True,
    tint: str = "accent",
    width: Any = "fill",
    disabled: bool = False,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A box of removable chips with a field to type more: labels, recipients, keywords.

    ``tags`` is your list. What is being typed is kept by the box itself, unless you hold it
    in your state with ``text`` and ``on_input`` (to clear it or check it yourself). Enter (or a comma) turns the text into a tag and ``on_change`` gets the new list, as it
    does when the x of a chip is clicked; with ``unique`` a tag already in the list is not
    added twice, and ``max_tags`` hides the field once the list is full. ``suggestions``
    shows the ones that match the text under the field, as chips to click. ``id`` names the
    field, so it keeps the focus after a tag is added (``Command.focus(id)`` focuses it too).

    Events:
        ``on_change(tags)``: Callable that receives the new list of tags.
        ``on_input(text)``: Callable that receives the text being typed.
    """
    from .inputs import input as _input

    tags = list(tags)
    editable = on_change is not None and not disabled
    if on_input is None and editable:
        # nobody holds the typed text: a small component keeps it
        return _TagField(tags=tags, handler=on_change, text=text,
                         options={"placeholder": placeholder, "suggestions": tuple(suggestions), "max_tags": max_tags,
                                  "unique": unique, "tint": tint, "width": width, "id": id, "theme": theme})
    t = _theme(theme)

    def add(raw: str) -> Any:
        new = [part.strip() for part in raw.split(",") if part.strip()]
        result = list(tags)
        for tag in new:
            if (not unique or tag not in result) and (max_tags is None or len(result) < max_tags):
                result.append(tag)
        cleared = send(on_input, "") if on_input is not None else None
        changed = on_change(result) if result != tags else None
        # the field moves when a chip goes in front of it: give it the focus back to keep typing
        out = [r for r in (changed, cleared, _core.Command.focus(id) if id else None) if r is not None]
        return out[0] if len(out) == 1 else (out or None)

    def typed(value: str) -> Any:
        if "," in value and editable:
            return add(value)
        return send(on_input, value) if on_input is not None else None

    def remove(index: int) -> Any:
        return on_change([tag for i, tag in enumerate(tags) if i != index])

    chips: List[Any] = [
        chip(tag, on_remove=(lambda i=i: remove(i)) if editable else None, selected=True, tint=tint,
             disabled=disabled, theme=t)
        for i, tag in enumerate(tags)
    ]
    full = max_tags is not None and len(tags) >= max_tags
    if not full and not disabled:
        chips.append(_input(text, typed if (editable or on_input is not None) else None, placeholder=placeholder,
                            on_submit=(lambda: add(text)) if editable else None, borderless=True, size="sm",
                            width=120, id=id, theme=t))
    box = _core.container(
        _core.row(chips, spacing=4, align="center", wrap=True),
        padding=(3, 6),
        width=width,
        bg=t.element if disabled else t.editor,
        border_color=t.border,
        border_width=1.0,
        radius=t.radius_sm,
    )
    needle = text.strip().lower()
    matches = [s for s in suggestions if needle and needle in s.lower() and (not unique or s not in tags)]
    if not matches or full or not editable:
        return box
    hints = _core.row([chip(s, on_press=lambda s=s: add(s), icon="plus", theme=t) for s in matches[:8]],
                      spacing=4, wrap=True)
    return _core.column([box, hints], spacing=4, width=width)


class _TagField(_Component):
    """``tag_input`` keeping its own typed text, for callers that only care about the tags."""

    tags: Any = ()
    handler: Any = None
    text: str = ""
    options: Any = None
    designer = False

    def setup(self) -> None:
        self.typed = self.text
        self.field = (self.options or {}).get("id") or f"tag-input-{id(self)}"

    def type(self, value: str) -> None:
        self.typed = value

    def render(self) -> Any:
        options = {**(self.options or {}), "id": self.field}
        return tag_input(self.tags, self.handler, text=self.typed, on_input=self.type, **options)
