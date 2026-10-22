"""Editors made for one kind of value each, used by the property grid instead of plain text fields.

* ``segmented``: a few choices side by side (on/off/default, alignments, short enums).
* ``box_editor``: four sides or corners (padding, margin, corner radius) as one linked number, or one number per
  side once unlinked, like Figma's and Zed's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: A choice of a segmented control: its value, its label and an optional icon (shown instead of the label).
Choice = Tuple[Any, str, Optional[str]]

#: Most choices a property can have to be shown as a segmented control rather than a drop-down.
SEGMENTED_MAX = 4

SIDES = ("T", "R", "B", "L")
CORNERS = ("TL", "TR", "BR", "BL")
SIDE_TIPS = ("Top", "Right", "Bottom", "Left")
CORNER_TIPS = ("Top left", "Top right", "Bottom right", "Bottom left")


def segmented(choices: Sequence[Choice], selected: Any, on_select: Callable[[Any], Any], t: Theme) -> Any:
    """The choices side by side, filling the row; the selected one is raised. A choice with an icon shows the
    icon, with its label as the tooltip."""
    buttons = []
    for value, label, icon in choices:
        active = value == selected
        color = t.text if active else t.text_muted
        content = _icon(icon, size=14, color=color) if icon else _core.text(label, size=12.5, color=color,
                                                                            wrap=False)
        button = _core.button(_core.container(content, center=True, width="fill"), lambda v=value: on_select(v),
                              padding=(3, 6), width="fill", bg=t.element_selected if active else "transparent",
                              hover_bg=t.element_selected if active else t.ghost_hover, radius=t.radius_sm - 1)
        buttons.append(ui.tooltip(button, label, theme=t) if icon else button)
    return _core.container(_core.row(buttons, spacing=2, width="fill"), padding=2, width="fill", bg=t.element,
                           border_color=t.border_variant, border_width=1.0, radius=t.radius_sm + 1)


def choice_label(value: str) -> str:
    """How a choice reads: ``""`` is "Default", the rest capitalized and translated."""
    return tr(value.capitalize()) if value else tr("Default")


def fits_segmented(choices: Sequence[str]) -> bool:
    """Whether ``choices`` are few and short enough to sit side by side in the property column."""
    return 1 < len(choices) <= SEGMENTED_MAX and sum(len(choice_label(c)) for c in choices) <= 24


def four(value: Any) -> Tuple[float, float, float, float]:
    """Four numbers from a saved box or radius value: one number, two (vertical horizontal) or four."""
    if value is None or value == "":
        return (0.0, 0.0, 0.0, 0.0)
    if isinstance(value, (int, float)):
        return (float(value),) * 4  # type: ignore[return-value]
    values = [float(v) for v in value]
    if len(values) == 2:
        return (values[0], values[1], values[0], values[1])
    if len(values) == 4:
        return tuple(values)  # type: ignore[return-value]
    return (values[0],) * 4 if values else (0.0, 0.0, 0.0, 0.0)  # type: ignore[return-value]


def _plain(n: float) -> Any:
    return int(n) if float(n).is_integer() else n


def is_split(d: "Designer", key: str, value: Any) -> bool:
    """Whether the box editor of ``key`` shows one field per side: its sides differ, or it was unlinked."""
    return key in d.__dict__.get("_split_boxes", ()) or len(set(four(value))) > 1


def box_editor(d: "Designer", key: str, value: Any, on_change: Callable[[Any], Any], t: Theme, *,
               corners: bool = False, max_value: float = 256) -> Any:
    """One number for every side (or corner) while they are linked, four once unlinked.

    ``on_change`` gets a number (linked), a tuple of four numbers, or ``None`` when everything is 0.
    The link button remembers per property (``key``) that it was opened, even while the four are equal.
    """
    values = four(value)
    split_keys = d.__dict__.setdefault("_split_boxes", set())
    split = is_split(d, key, value)

    def store(new: Sequence[float]) -> None:
        if not any(new):
            on_change(None)
        elif len(set(new)) == 1:
            on_change(_plain(new[0]))
        else:
            on_change(tuple(_plain(n) for n in new))

    def toggle() -> None:
        if split:
            split_keys.discard(key)
            store((values[0],) * 4)  # linking takes the first side for all of them
        else:
            split_keys.add(key)

    link = ui.icon_button("unlink" if split else "link", toggle, size="xs", selected=not split,
                          tooltip=tr("Edit each corner") if corners and not split else
                          tr("Edit each side") if not split else tr("Same value everywhere"), theme=t)
    if not split:
        field = ui.number_field(values[0], lambda v: store((float(v),) * 4), min=0, max=max_value, width="fill",
                                steppers=False, align="start", theme=t)
        return _core.row([_core.container(field, width="fill"), link], spacing=4, align="center")
    tags, tips = (CORNERS, CORNER_TIPS) if corners else (SIDES, SIDE_TIPS)

    def side(i: int) -> Any:
        def change(v: float) -> None:
            new = list(values)
            new[i] = float(v)
            store(new)

        tag = ui.tooltip(_core.container(ui.label(tags[i], size="xs", color="text_muted", theme=t), width=18),
                         tr(tips[i]), theme=t)
        return _core.row([tag, _core.container(ui.number_field(values[i], change, min=0, max=max_value, width="fill",
                                                               steppers=False, align="start", theme=t),
                                               width="fill")], spacing=2, align="center")

    # corners sit where they are (bottom left under top left); sides read in CSS order
    second = (side(3), side(2)) if corners else (side(2), side(3))
    grid = _core.column([_core.row([side(0), side(1)], spacing=6), _core.row(list(second), spacing=6)],
                        spacing=4, width="fill")
    return _core.row([_core.container(grid, width="fill"), _core.container(link, align_y="start")], spacing=4)


# -- Figma-like editors ------------------------------------------------------------------------------------------


def compact(new: Sequence[float]) -> Any:
    """Four sides as they are saved: ``None`` when all are 0, one number when they are equal, else four."""
    if not any(new):
        return None
    if len(set(new)) == 1:
        return _plain(new[0])
    return tuple(_plain(n) for n in new)


def number(value: Any, on_change: Callable[[float], Any], t: Theme, *, tag: Optional[str] = None,
           tip: Optional[str] = None, min: Optional[float] = None, max: Optional[float] = None,  # noqa: A002
           step: float = 1, suffix: Optional[str] = None, decimals: Optional[int] = None,
           drag_step: Optional[float] = None, align: str = "start") -> Any:
    """A compact number field, as in Figma's panels: an optional ``tag`` ("X", "W"...) in front and no −/+
    buttons. Drag over the number to change it, double-click it to type one."""
    number = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0
    field = ui.number_field(number, on_change, min=min, max=max, step=step, width="fill", prefix=tag, suffix=suffix,
                            decimals=decimals, steppers=False, drag_step=drag_step, align=align, theme=t)
    return ui.tooltip(field, tr(tip), theme=t) if tip else field


def pair(first: Any, second: Any, *, spacing: float = 6) -> Any:
    """Two fields side by side, sharing the row (X and Y, width and height)."""
    return _core.row([_core.container(first, width="fill"), _core.container(second, width="fill")],
                     spacing=spacing, width="fill", align="center")


#: The three spots of an axis in the alignment box.
SPOTS = ("start", "center", "end")
_SPOT_NAMES = {("start", "start"): "Top left", ("center", "start"): "Top center", ("end", "start"): "Top right",
               ("start", "center"): "Middle left", ("center", "center"): "Center", ("end", "center"): "Middle right",
               ("start", "end"): "Bottom left", ("center", "end"): "Bottom center", ("end", "end"): "Bottom right"}


def align_box(x: str, y: str, on_pick: Callable[[str, str], Any], t: Theme, *, cell: float = 22,
              spread: Optional[str] = None) -> Any:
    """Figma's alignment box: nine spots in a square; the chosen one (``x``, ``y`` in ``start``/``center``/
    ``end``) is marked. ``on_pick(x, y)`` gets the spot clicked. ``spread`` (``"x"`` or ``"y"``) marks a whole
    column or row instead, for children spread along that axis (space between)."""
    rows = []
    for sy in SPOTS:
        cells = []
        for sx in SPOTS:
            if spread == "x":  # spread along the row: the row is the choice
                chosen = sy == y
            elif spread == "y":
                chosen = sx == x
            else:
                chosen = sx == x and sy == y
            w, h = ((14, 3) if spread == "x" else (3, 14) if spread == "y" else (8, 8)) if chosen else (3, 3)
            mark = _core.container(width=w, height=h, bg=t.accent if chosen else t.text_muted, radius=1.5)
            button = _core.button(_core.container(mark, center=True, width="fill", height="fill"),
                                  lambda sx=sx, sy=sy: on_pick(sx, sy), padding=0, width=cell, height=cell,
                                  bg="transparent", hover_bg=t.ghost_hover, radius=t.radius_sm - 1)
            cells.append(ui.tooltip(button, tr(_SPOT_NAMES[(sx, sy)]), theme=t))
        rows.append(_core.row(cells, spacing=0))
    return _core.container(_core.column(rows, spacing=0), padding=2, bg=t.element, border_color=t.border_variant,
                           border_width=1.0, radius=t.radius_sm + 1)


def box_model(margin: Any, padding: Any, on_margin: Callable[[Any], Any], on_padding: Callable[[Any], Any],
              t: Theme, *, label_margin: str = "Margin", label_padding: str = "Padding") -> Any:
    """The space around and inside a box, drawn like the box model of a browser's inspector: the margin's four
    sides around the padding's four sides around the content. Each side is a number field (drag or type)."""

    def side(values: Tuple[float, ...], i: int, store: Callable[[Any], Any], tip: str) -> Any:
        def change(v: float) -> None:
            new = list(values)
            new[i] = float(v)
            store(compact(new))

        field = ui.number_field(values[i], change, min=0, max=999, width=44, steppers=False, align="center",
                                theme=t)
        return ui.tooltip(field, tr(tip), theme=t)

    def ring(title: str, values: Tuple[float, ...], store: Callable[[Any], Any], inner: Any, tint: str) -> Any:
        head = _core.row([ui.label(tr(title), size="xs", color="text_muted", wrap=False, theme=t),
                          _core.space(width="fill"), side(values, 0, store, f"{title}: {tr('Top')}"),
                          _core.space(width="fill"), _core.space(width=36)], align="center", width="fill")
        middle = _core.row([side(values, 3, store, f"{title}: {tr('Left')}"),
                            _core.container(inner, width="fill"),
                            side(values, 1, store, f"{title}: {tr('Right')}")], spacing=4, align="center",
                           width="fill")
        foot = _core.container(side(values, 2, store, f"{title}: {tr('Bottom')}"), width="fill", align_x="center")
        return _core.container(_core.column([head, middle, foot], spacing=3, width="fill"), padding=4, width="fill",
                               border_color=alpha(tint, 0.45), border_width=1.0, radius=t.radius_sm + 1,
                               bg=alpha(tint, 0.07))

    content = _core.container(ui.label("", size="xs", theme=t), height=18, width="fill", bg=t.element_selected,
                              radius=t.radius_sm - 1)
    # tinted like a browser's inspector: the margin warm, the padding green
    inner = ring(label_padding, four(padding), on_padding, content, t.success)
    return ring(label_margin, four(margin), on_margin, inner, t.warning)
