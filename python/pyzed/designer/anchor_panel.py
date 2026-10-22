"""The Position section of a free-placed control, laid out like Figma's: buttons that align it in its
container, its position and size two by two (fields you drag or double-click to type), rotation, an anchor
preset picker like Unity's, Unreal's and Godot's (Figma's constraints) and, under "More options", size limits
and the pivot."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List

from .. import _core, anchors, draw, ui
from . import spacing
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


def _number(value: float, on_change: Callable[[float], Any], t: Theme, *, tag: str = "", tip: str = "",
            **kwargs: Any) -> Any:
    from . import prop_editors

    return prop_editors.number(value, on_change, t, tag=tag or None, tip=tip or None, **kwargs)


#: The buttons that line a control up with its container (or the form), like Figma's: icon, edge, tooltip.
ALIGN_TOOLS = (("align-start-vertical", "left", "Align left"),
               ("align-center-vertical", "center", "Align horizontal centers"),
               ("align-end-vertical", "right", "Align right"),
               ("align-start-horizontal", "top", "Align top"),
               ("align-center-horizontal", "middle", "Align vertical centers"),
               ("align-end-horizontal", "bottom", "Align bottom"))


def align_row(d: "Designer", c: "Control", t: Theme) -> Any:
    """Six buttons that put the control against an edge or the center of its container."""
    buttons = [ui.icon_button(icon, lambda e=edge: align_in_parent(d, c.name, e), size="sm", tooltip=tr(tip),
                              theme=t) for icon, edge, tip in ALIGN_TOOLS]
    return _core.row(buttons[:3] + [_core.space(width="fill")] + buttons[3:], spacing=0, align="center",
                     width="fill")


def align_in_parent(d: "Designer", name: str, edge: str) -> None:
    """Moves control ``name`` against ``edge`` (left, center, right, top, middle, bottom) of its container."""
    c = d.doc.form.get(name)
    if c is None:
        return
    pw, ph = d.doc.parent_size(name)
    if edge in ("left", "center", "right"):
        x = {"left": 0, "center": (pw - c.width) / 2, "right": pw - c.width}[edge]
        d.set_field(name, "x", round(x))
    else:
        y = {"top": 0, "middle": (ph - c.height) / 2, "bottom": ph - c.height}[edge]
        d.set_field(name, "y", round(y))


def more_open(d: "Designer", key: str) -> bool:
    """Whether the "More options" of section ``key`` are shown."""
    return key in d.__dict__.get("_more_options", set())


def more_toggle(d: "Designer", key: str, t: Theme) -> Any:
    """A small "More options" / "Fewer options" link that shows or hides a section's rarely used rows."""
    shown = more_open(d, key)

    def flip() -> None:
        d.__dict__.setdefault("_more_options", set()).symmetric_difference_update({key})

    return _core.container(ui.button(tr("Fewer options") if shown else tr("More options"), flip,
                                     icon="chevron-up" if shown else "chevron-down", variant="ghost", size="xs",
                                     theme=t), padding=(2, 0))


def position_rows(d: "Designer", c: "Control", t: Theme, prop_row: Callable[..., Any]) -> List[Any]:
    """The rows of the Position section for a control placed freely (not by a flex or grid container), like
    Figma's: align buttons, position and size two by two, rotation, the anchor (Figma's constraints) and, under
    "More options", size limits and the pivot."""
    preset = anchors.preset_of(c.anchor)
    h, v = anchors.axes(c.anchor)
    pw, ph = d.doc.parent_size(c.name)
    left, top, right, bottom = anchors.offsets(c.rect, (pw, ph))
    is_open = d.anchor_presets == c.name

    def num(field: str, tag: str) -> Any:
        return _number(round(getattr(c, field)), lambda val, f=field: d.set_field(c.name, f, val), t, step=1,
                       tag=tag)

    def offset(side: str, value: float, tag: str, tip: str) -> Any:
        return _number(round(value), lambda val, s=side: d.set_offset(c.name, s, val), t, step=1, tag=tag, tip=tip)

    x = offset("left", left, "L", "Distance to the left side of the container (the control stretches)") \
        if h == "wide" else num("x", "X")
    w = offset("right", right, "R", "Distance to the right side of the container (the control stretches)") \
        if h == "wide" else num("width", "W")
    y = offset("top", top, "T", "Distance to the top of the container (the control stretches)") \
        if v == "tall" else num("y", "Y")
    ht = offset("bottom", bottom, "B", "Distance to the bottom of the container (the control stretches)") \
        if v == "tall" else num("height", "H")
    from . import prop_editors

    rows: List[Any] = [
        prop_row("Align", align_row(d, c, t), t, tip=tr("Line the control up with its container")),
        prop_row("Position", prop_editors.pair(x, y), t,
                 tip=tr("Drag a number sideways to change it, or double-click it to type")),
        prop_row("Size", prop_editors.pair(w, ht), t),
        prop_row("Rotation", _number(_rotation(c), lambda val: d.set_style(c.name, "rotate", val or None), t,
                                     min=-360, max=360, step=1, suffix="°"), t,
                 tip=tr("Degrees clockwise, around the pivot")),
    ]
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
    rows.append(prop_row("Anchor", summary, t,
                         tip=tr("Edges of the window (or the container) the control follows when it is resized")))
    if is_open:
        rows.append(_core.container(_core.column([
            preset_grid(preset, lambda name: d.set_anchor(c.name, name), t),
            _core.row([ui.switch(d.anchor_move, lambda on: setattr(d, "anchor_move", on), theme=t),
                       ui.label(tr("Also move it there"), size="sm", theme=t)], spacing=8, align="center"),
        ], spacing=8), padding=(4, 0, 8, spacing.LABEL_WIDTH + spacing.LABEL_GAP)))
    rows.append(more_toggle(d, f"position:{c.name}", t))
    if not more_open(d, f"position:{c.name}"):
        return rows

    def limit(key: str, value: float, tag: str) -> Any:
        return _number(value, lambda val, k=key: d.set_layout(c.name, k, max(val, 0)), t, min=0, step=8, tag=tag,
                       drag_step=1)

    (min_w, min_h), (max_w, max_h) = c.min_size, c.max_size
    px, py = c.pivot
    rows += [
        prop_row("Min size", prop_editors.pair(limit("min_width", min_w, "W"), limit("min_height", min_h, "H")), t,
                 tip=tr("The control never gets smaller than this when it stretches (0: no limit)")),
        prop_row("Max size", prop_editors.pair(limit("max_width", max_w, "W"), limit("max_height", max_h, "H")), t,
                 tip=tr("The control never gets bigger than this when it stretches (0: no limit)")),
        prop_row("Pivot", prop_editors.pair(
            _number(px, lambda val: d.set_pivot(c.name, val, py), t, min=0, max=1, step=0.1, tag="X"),
            _number(py, lambda val: d.set_pivot(c.name, px, val), t, min=0, max=1, step=0.1, tag="Y")), t,
            tip=tr("The point rotation and scale turn around, and that stays put when a size limit stops "
                   "the control from stretching: 0 0 is the top-left corner, 0.5 0.5 the center")),
    ]
    return rows


def _rotation(c: "Control") -> float:
    from ..style import degrees

    try:
        return degrees(c.style.get("rotate") or 0)
    except (TypeError, ValueError):
        return 0.0
