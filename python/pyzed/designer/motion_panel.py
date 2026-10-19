"""The Effects and Animation sections of the property grid (see ``designer.motion``).

Effects are a few style properties with friendly editors: opacity, glow, bloom and glass.
Animations are a list of rows: each shows what plays and when (``Fade in up · 280 ms``),
with buttons to preview and remove it; clicking a row opens its editor (trigger, preset,
duration, delay, easing, repeat). The canvas stays still while you edit and plays a
control's animations when you preview them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme
from . import motion
from .locale import tr
from .model import Control
from .panels import Group, _color_editor, prop_row

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Icons of the triggers in the animation rows.
TRIGGER_ICONS = {"mount": "sparkles", "hover": "mouse-pointer-2", "press": "pointer", "focus": "scan",
                 "click": "mouse-pointer-click"}


def _number(value: Any, on_change: Callable[[Any], Any], t: Theme, *, min: float = 0, max: float = 10000,
            step: float = 1) -> Any:
    number = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0
    return ui.number_field(number, on_change, min=min, max=max, step=step, width="fill", theme=t)


def _named_select(options: Any, value: str, on_change: Callable[[str], Any], t: Theme) -> Any:
    """A drop-down of identifiers shown as words (``ease_out_cubic`` reads "Ease out cubic"), translated."""
    labels = {tr(motion.label(o)): o for o in options}
    if value not in labels.values():  # a value typed in code that the list doesn't offer
        labels[value] = value
    current = next(label for label, o in labels.items() if o == value)
    return ui.select(list(labels), current, lambda label: on_change(labels.get(label, label)), width="fill",
                     size="sm", theme=t)


def effect_rows(d: "Designer", c: Control, t: Theme) -> List[Any]:
    """The Effects section: opacity, rotation, blur, glow, bloom and glass (all saved in the control's style)."""
    style = c.style
    name = c.name
    rows: List[Any] = [Group("Effects")]

    opacity = style.get("opacity")
    rows.append(prop_row("Opacity", _number(1.0 if opacity is None else opacity,
                                            lambda v: d.set_style_value(name, "opacity", None if v >= 1 else round(v, 3)),
                                            t, min=0, max=1, step=0.05),
                         t, tip="How visible the control and everything inside it is (1 is opaque)"))
    for key, title, maximum, step, tip in (
        ("rotate", "Rotation", 360, 1, "Degrees, clockwise, around the center"),
        ("blur", "Blur", 64, 1, "Blurs the control and everything inside it, in pixels"),
        ("backdrop_blur", "Backdrop blur", 64, 1, "Blurs what is behind the box, in pixels"),
    ):
        rows.append(prop_row(title, _number(style.get(key) or 0, lambda v, key=key: d.set_style_value(
            name, key, None if not v else round(v, 2)), t, min=-maximum if key == "rotate" else 0, max=maximum,
            step=step), t, tip=tip))

    for key, title, size_title, default, maximum, step, tip in (
        ("glow", "Glow", "Glow size", 12.0, 96, 1, "A soft halo around the box"),
        ("bloom", "Bloom", "Intensity", 0.6, 1, 0.1, "Light that spills from the bright parts of the control"),
    ):
        color, size = motion.glow_parts(style.get(key), default)

        def set_color(v: Any, key: str = key, size: float = size) -> None:
            d.set_style_value(name, key, motion.glow_value(str(v or ""), size))

        def set_size(v: Any, key: str = key, color: str = color) -> None:
            d.set_style_value(name, key, motion.glow_value(color, v))

        rows.append(prop_row(title, _color_editor(d, name, key, color, set_color, t, "none"), t, tip=tip))
        if color:
            rows.append(prop_row(size_title, _number(size, set_size, t, max=maximum, step=step), t))

    on, tint, strength = motion.glass_parts(style.get("glass"))
    rows.append(prop_row("Glass", _core.container(
        ui.switch(on, lambda v: d.set_style_value(name, "glass", motion.glass_value(v, tint, strength)), theme=t),
        width="fill", align_x="end"), t, tip="A translucent panel that blurs what is behind it"))
    if on:
        rows.append(prop_row("Tint", _color_editor(
            d, name, "glass", tint, lambda v: d.set_style_value(name, "glass", motion.glass_value(True, str(v or ""),
                                                                                                  strength)), t), t))
        rows.append(prop_row("Strength", _number(
            strength, lambda v: d.set_style_value(name, "glass", motion.glass_value(True, tint, v)), t, max=1,
            step=0.02), t, tip="How much of the tint shows"))
    return rows


def animation_rows(d: "Designer", c: Control, t: Theme) -> List[Any]:
    """The Animation section: one row per animation, the open one's editor, and the add and preview buttons."""
    name = c.name
    rows: List[Any] = [Group("Animation")]
    opened = d.motion_open if d.motion_open and d.motion_open[0] == name else None
    for index, entry in enumerate(c.animations):
        is_open = opened is not None and opened[1] == index
        rows.append(_entry_row(d, name, index, entry, is_open, t))
        if is_open:
            rows.append(_entry_editor(d, name, index, entry, t))
    if not c.animations:
        rows.append(_core.container(ui.label(tr("No animations yet: add one to play it when the control appears, "
                                                "on hover, on click..."), size="xs", color="text_muted", theme=t),
                                    padding=(4, 10), width="fill"))
    previewing = name in d.motion_preview
    buttons = [ui.button(tr("Add animation"), lambda: d.add_animation(name), icon="plus", variant="ghost", size="sm",
                         theme=t)]
    if c.animations:
        buttons.append(_core.space(width="fill"))
        buttons.append(ui.button(tr("Stop") if previewing else tr("Preview"),
                                 (lambda: d.stop_preview(name)) if previewing else (lambda: d.preview_animations(name)),
                                 icon="square" if previewing else "play", variant="ghost", size="sm", theme=t))
    rows.append(_core.container(_core.row(buttons, spacing=6, align="center"), padding=(4, 10), width="fill"))
    return rows


def _entry_row(d: "Designer", name: str, index: int, entry: dict, is_open: bool, t: Theme) -> Any:
    trigger = motion.timing(entry)["on"]
    valid = motion.preset_of(entry) is not None
    head = _core.row([
        _icon(TRIGGER_ICONS.get(trigger, "sparkles"), size=14, color=t.accent if valid else t.error),
        _core.column([
            ui.label(motion.summary(entry) if valid else tr("Unknown animation"), size="sm", wrap=False, theme=t),
            ui.label(tr(motion.TRIGGER_LABELS.get(trigger, trigger)), size="xs", color="text_muted", wrap=False,
                     theme=t),
        ], spacing=0, width="fill"),
        _icon("chevron-down" if is_open else "chevron-right", size=12, color=t.icon_muted),
    ], spacing=8, align="center")
    body = _core.button(head, lambda: d.open_animation(name, index), bg=t.element_selected if is_open else "transparent",
                        hover_bg=t.element_hover, padding=(4, 6), width="fill", radius=t.radius_sm)
    return _core.container(_core.row([
        body,
        ui.icon_button("play", lambda: d.preview_animations(name), size="xs", tooltip=tr("Preview"), theme=t),
        ui.icon_button("trash-2", lambda: d.remove_animation(name, index), size="xs", tooltip=tr("Remove"), theme=t),
    ], spacing=2, align="center"), padding=(1, 4), width="fill")


def _entry_editor(d: "Designer", name: str, index: int, entry: dict, t: Theme) -> Any:
    timing = motion.timing(entry)
    trigger = timing["on"]

    def setter(key: str) -> Callable[[Any], None]:
        return lambda v: d.set_animation(name, index, key, v)

    triggers = {tr(label): key for key, label in motion.TRIGGERS}
    current_trigger = next((label for label, key in triggers.items() if key == trigger), tr("When it appears"))
    presets = motion.presets_for(trigger)
    labels = {tr(motion.label(p)): p for p in presets}
    current_preset = next((label for label, p in labels.items() if p == entry.get("preset")),
                          str(entry.get("preset", "")))
    preset = motion.preset_of(entry)
    hint = tr(preset.description) if preset and preset.description else ""
    rows = [
        prop_row("When", ui.select(list(triggers), current_trigger, lambda label: d.set_animation(
            name, index, "on", triggers.get(label, "mount")), width="fill", size="sm", theme=t), t,
            tip="What plays it: appearing, hovering, pressing, focusing or clicking the control"),
        prop_row("Animation", ui.select(list(labels), current_preset, lambda label: d.set_animation(
            name, index, "preset", labels.get(label, label)), width="fill", size="sm", theme=t), t,
            tip=hint or None),
        prop_row("Duration", _number(timing["duration"], setter("duration"), t, max=10000, step=20), t,
                 tip="Milliseconds"),
        prop_row("Delay", _number(timing["delay"], setter("delay"), t, max=10000, step=20), t,
                 tip="Milliseconds before it starts"),
        prop_row("Easing", _named_select(motion.EASINGS, str(timing["easing"]), setter("easing"), t), t,
                 tip="How the speed changes along the way"),
        prop_row("Repeat", _named_select(motion.REPEATS, motion.repeat_text(timing["repeat"]), setter("repeat"), t),
                 t),
    ]
    # inset under the row it edits, with a line on the left tying them together
    return _core.container(_core.column(rows, spacing=2, width="fill"), padding=(2, 0, 6, 10), width="fill")
