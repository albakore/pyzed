"""The Position section of a free-placed control: an anchor preset picker like Unity's, Unreal's and
Godot's, the offsets or position and size it implies, size limits, pivot and rotation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List

from .. import _core, anchors, draw, ui
from ..theme import Theme
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer
    from .model import Control

H_NAMES = {"left": "Left", "center": "Center", "right": "Right", "wide": "Stretch"}
V_NAMES = {"top": "Top", "center": "Middle", "bottom": "Bottom", "tall": "Stretch"}


def preset_label(preset: str) -> str:
    """``"Top · Right"``, ``"Stretch · Stretch"``... for a preset (vertical first, as Unity shows it)."""
    h, v = anchors.axes(anchors.PRESETS[preset])
    return f"{tr(V_NAMES[v])} · {tr(H_NAMES[h])}"


def preset_icon(preset: str, t: Theme, size: float = 30, *, selected: bool = False) -> Any:
    """A small drawing of a preset: the parent's frame, the box where it sits and, on stretched axes, a line
    with end marks across the frame."""
    h, v = anchors.axes(anchors.PRESETS[preset])
    pad, box = 4.0, size * 0.32
    inner = size - 2 * pad
    accent = t.accent if selected else t.text_muted
    if h == "wide":
        x, w = pad + 2, inner - 4
    else:
        w = box
        x = {"left": pad + 2, "center": (size - w) / 2, "right": size - pad - 2 - w}[h]
    if v == "tall":
        y, ht = pad + 2, inner - 4
    else:
        ht = box
        y = {"top": pad + 2, "center": (size - ht) / 2, "bottom": size - pad - 2 - ht}[v]
    shapes = [draw.rect(pad, pad, inner, inner, stroke=t.border, width=1.0),
              draw.rect(x, y, w, ht, fill=accent)]
    marks = t.accent if selected else t.icon
    if h == "wide":
        shapes += [draw.line(pad, size / 2, size - pad, size / 2, stroke=marks, width=1.0),
                   draw.line(pad, size / 2 - 3, pad, size / 2 + 3, stroke=marks, width=1.5),
                   draw.line(size - pad, size / 2 - 3, size - pad, size / 2 + 3, stroke=marks, width=1.5)]
    if v == "tall":
        shapes += [draw.line(size / 2, pad, size / 2, size - pad, stroke=marks, width=1.0),
                   draw.line(size / 2 - 3, pad, size / 2 + 3, pad, stroke=marks, width=1.5),
                   draw.line(size / 2 - 3, size - pad, size / 2 + 3, size - pad, stroke=marks, width=1.5)]
    return _core.canvas(shapes, width=size, height=size)


def preset_grid(current: str, on_pick: Callable[[str], Any], t: Theme, cell: float = 34) -> Any:
    """The 16 presets in a 4×4 grid (rows top, middle, bottom, stretch; columns left, center, right, stretch)."""
    rows = []
    for v in anchors.VERTICAL:
        buttons = []
        for h in anchors.HORIZONTAL:
            name = anchors.preset(h, v)
            chosen = name == current
            button = _core.button(_core.container(preset_icon(name, t, cell - 6, selected=chosen), center=True),
                                  lambda n=name: on_pick(n), padding=0, width=cell, height=cell,
                                  radius=t.radius_sm, bg=t.element_selected if chosen else "transparent",
                                  hover_bg=t.element_hover)
            buttons.append(ui.tooltip(button, preset_label(name), theme=t))
        rows.append(_core.row(buttons, spacing=2))
    return _core.column(rows, spacing=2)


def _number(value: float, on_change: Callable[[float], Any], t: Theme, **kwargs: Any) -> Any:
    return ui.number_field(float(value), on_change, width="fill", theme=t, **kwargs)


def _pair(first: str, a: Any, second: str, b: Any, t: Theme) -> Any:
    def tag(text: str) -> Any:
        return _core.container(ui.label(text, size="xs", color="text_muted", theme=t), width=14)

    return _core.row([tag(first), _core.container(a, width="fill"), tag(second), _core.container(b, width="fill")],
                     spacing=4, align="center")


def position_rows(d: "Designer", c: "Control", t: Theme, prop_row: Callable[..., Any]) -> List[Any]:
    """The rows of the Position section for a control placed freely (not by a flex or grid container)."""
    preset = anchors.preset_of(c.anchor)
    h, v = anchors.axes(c.anchor)
    pw, ph = d.doc.parent_size(c.name)
    left, top, right, bottom = anchors.offsets(c.rect, (pw, ph))
    is_open = d.anchor_presets == c.name
    summary = _core.row([
        ui.tooltip(_core.button(_core.container(preset_icon(preset, t, 26, selected=True), center=True),
                                lambda: d.toggle_anchor_presets(c.name), padding=0, width=30, height=30,
                                radius=t.radius_sm, bg=t.element_selected if is_open else "transparent",
                                hover_bg=t.element_hover),
                   tr("Anchor presets"), theme=t),
        ui.label(preset_label(preset), size="sm", theme=t),
        _core.space(width="fill"),
        ui.icon_button("chevron-up" if is_open else "chevron-down", lambda: d.toggle_anchor_presets(c.name),
                       size="xs", tooltip=tr("Anchor presets"), theme=t),
    ], spacing=8, align="center")
    rows: List[Any] = [prop_row("Anchor", summary, t,
                                tip=tr("Edges of the window (or the container) the control follows when it is resized"))]
    if is_open:
        rows.append(_core.container(_core.column([
            preset_grid(preset, lambda name: d.set_anchor(c.name, name), t),
            _core.row([ui.switch(d.anchor_move, lambda on: setattr(d, "anchor_move", on), theme=t),
                       ui.label(tr("Also move it there"), size="sm", theme=t)], spacing=8, align="center"),
        ], spacing=8), padding=(4, 12, 8, 120)))

    def num(field: str) -> Any:
        return _number(round(getattr(c, field)), lambda val, f=field: d.set_field(c.name, f, val), t, step=1)

    def offset(side: str, value: float) -> Any:
        return _number(round(value), lambda val, s=side: d.set_offset(c.name, s, val), t, step=1)

    if h == "wide":
        rows.append(prop_row("Left · Right", _pair("L", offset("left", left), "R", offset("right", right), t), t,
                             tip=tr("Distances to the left and right sides of the container (the control stretches)")))
    else:
        rows.append(prop_row("X · Width", _pair("X", num("x"), "W", num("width"), t), t))
    if v == "tall":
        rows.append(prop_row("Top · Bottom", _pair("T", offset("top", top), "B", offset("bottom", bottom), t), t,
                             tip=tr("Distances to the top and bottom of the container (the control stretches)")))
    else:
        rows.append(prop_row("Y · Height", _pair("Y", num("y"), "H", num("height"), t), t))

    def limit(key: str, value: float) -> Any:
        return _number(value, lambda val, k=key: d.set_layout(c.name, k, max(val, 0)), t, min=0, step=8)

    (min_w, min_h), (max_w, max_h) = c.min_size, c.max_size
    px, py = c.pivot
    rows += [
        prop_row("Min size", _pair("W", limit("min_width", min_w), "H", limit("min_height", min_h), t), t,
                 tip=tr("The control never gets smaller than this when it stretches (0: no limit)")),
        prop_row("Max size", _pair("W", limit("max_width", max_w), "H", limit("max_height", max_h), t), t,
                 tip=tr("The control never gets bigger than this when it stretches (0: no limit)")),
        prop_row("Pivot", _pair("X", _number(px, lambda val: d.set_pivot(c.name, val, py), t, min=0, max=1,
                                                  step=0.1),
                                    "Y", _number(py, lambda val: d.set_pivot(c.name, px, val), t, min=0, max=1,
                                                 step=0.1), t), t,
                 tip=tr("The point rotation and scale turn around, and that stays put when a size limit stops "
                     "the control from stretching: 0 0 is the top-left corner, 0.5 0.5 the center")),
        prop_row("Rotation", _number(_rotation(c), lambda val: d.set_style(c.name, "rotate", val or None), t,
                                         min=-360, max=360, step=15), t,
                 tip=tr("Degrees clockwise, around the pivot")),
    ]
    return rows


def _rotation(c: "Control") -> float:
    from ..style import degrees

    try:
        return degrees(c.style.get("rotate") or 0)
    except (TypeError, ValueError):
        return 0.0
