"""The style of a control in the property grid, split in short sections like Figma's: Text, Fill, Border and
Spacing (the effects and the shadow are in ``motion_panel``).

Every value is still a ``pz.Style`` property saved in the control's ``style`` (see ``styling``); this module
only decides how they are shown: pairs of fields on one row, an alignment box, and the margin and padding drawn
as a box model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Collection, List, Optional

from .. import _core, ui
from ..theme import Theme
from . import prop_editors, styling
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: The sections, in order, with the style properties each one edits.
SECTIONS = (
    ("Text", ("font", "weight", "size", "line_height", "color", "italic")),
    ("Fill", ("background",)),
    ("Border", ("border_color", "border_width", "radius")),
    ("Spacing", ("margin", "padding", "align_x", "align_y", "max_width", "max_height", "clip")),
)


def _choice(key: str, value: Any, on_change: Callable[[Any], Any], t: Theme) -> Any:
    """A drop-down of a choice field's options ("" reads "Default")."""
    field = styling.FIELD[key]
    shown = styling.choice_of(key, value)
    labels = {prop_editors.choice_label(c): c for c in field.choices}
    current = next((label for label, c in labels.items() if c == shown), tr("Default"))
    return ui.select(list(labels), current, lambda label: on_change(labels.get(label, "")), width="fill",
                     size="sm", theme=t)


def sections(d: "Designer", name: Optional[str], style: dict, t: Theme, prop_row: Callable[..., Any],
             group: Callable[[str], Any], *, keys: Optional[Collection[str]] = None) -> List[Any]:
    """The style sections of control ``name`` (the form's global style when ``None``), each started with
    ``group(title)``. ``keys`` limits them to some style properties (the global style edits fewer)."""
    from .panels import _background_rows, _color_editor

    def wanted(key: str) -> bool:
        return keys is None or key in keys

    def setter(key: str) -> Callable[[Any], None]:
        return lambda v: d.set_style(name, key, v)

    def num(key: str, **kwargs: Any) -> Any:
        value = style.get(key)
        return prop_editors.number(float(value) if isinstance(value, (int, float)) else 0.0, setter(key), t,
                                   **kwargs)

    rows: List[Any] = []
    # -- Text
    text: List[Any] = []
    if wanted("font") or wanted("weight"):
        text.append(prop_row("Font", prop_editors.pair(_choice("font", style.get("font"), setter("font"), t),
                                                       _choice("weight", style.get("weight"), setter("weight"), t)),
                             t, tip=tr("Family and weight (Default keeps the component's)")))
    if wanted("size") or wanted("line_height"):
        text.append(prop_row("Size", prop_editors.pair(
            num("size", min=0, max=96, suffix="px", tip="Font size; 0 keeps the component's own size"),
            num("line_height", min=0, max=4, step=0.1, suffix="×", tip="Line height, a multiple of the font size")),
            t, tip=tr("Font size and line height")))
    if wanted("color"):
        text.append(prop_row("Color", _color_editor(d, name, "color", style.get("color"), setter("color"), t), t,
                             tip=tr("Text color: a theme token (accent, text_muted...) or #rrggbb")))
    if wanted("italic"):
        text.append(prop_row("Italic", prop_editors.segmented(
            [(c, prop_editors.choice_label(c), None) for c in styling.TRISTATE],
            styling.choice_of("italic", style.get("italic")), setter("italic"), t), t))
    if text:
        rows += [group("Text"), *text]
    # -- Fill
    if wanted("background"):
        rows += [group("Fill"), *_background_rows(d, name, style.get("background"), t)]
    # -- Border
    border: List[Any] = []
    if wanted("border_color"):
        border.append(prop_row("Color", _color_editor(d, name, "border_color", style.get("border_color"),
                                                      setter("border_color"), t, "none"), t))
    if wanted("border_width"):
        border.append(prop_row("Width", num("border_width", min=0, max=32, suffix="px"), t))
    if wanted("radius"):
        box_key = f"{name}:radius"
        value = style.get("radius")
        border.append(prop_row("Corners", prop_editors.box_editor(d, box_key, value, setter("radius"), t,
                                                                  corners=True), t,
                               tip=tr("Corner radius: one for all, or one per corner"),
                               lines=2 if prop_editors.is_split(d, box_key, value) else 1))
    if border:
        rows += [group("Border"), *border]
    # -- Spacing
    spacing: List[Any] = []
    if wanted("margin") and wanted("padding"):
        spacing.append(_core.container(prop_editors.box_model(style.get("margin"), style.get("padding"),
                                                              setter("margin"), setter("padding"), t),
                                       width="fill", padding=(2, 0, 4, 0)))
    elif wanted("padding"):
        box_key = f"{name}:padding"
        value = style.get("padding")
        spacing.append(prop_row("Padding", prop_editors.box_editor(d, box_key, value, setter("padding"), t), t,
                                lines=2 if prop_editors.is_split(d, box_key, value) else 1,
                                tip=tr("Space inside the box, between its border and its content")))
    if wanted("align_x") and wanted("align_y"):
        ax = styling.choice_of("align_x", style.get("align_x"))
        ay = styling.choice_of("align_y", style.get("align_y"))

        def place(x: str, y: str) -> None:
            d.set_style(name, "align_x", x)
            d.set_style(name, "align_y", y)

        reset = ui.button(tr("Default"), lambda: place("", ""), variant="ghost", size="xs", theme=t) \
            if ax or ay else None
        spacing.append(prop_row("Align content", _core.row([
            prop_editors.align_box(ax, ay, place, t),
            _core.container(_core.column([
                ui.label(tr("Where the content sits inside the box"), size="xs", color="text_muted", theme=t),
                reset], spacing=4), width="fill", padding=(0, 0, 0, 8))], align="center"), t, lines=3))
    if wanted("max_width") and wanted("max_height"):
        spacing.append(prop_row("Max size", prop_editors.pair(
            num("max_width", min=0, max=4096, step=8, tag="W", drag_step=1, tip="0 means no limit"),
            num("max_height", min=0, max=4096, step=8, tag="H", drag_step=1, tip="0 means no limit")), t,
            tip=tr("The most room the content takes (0: no limit)")))
    if wanted("clip"):
        spacing.append(prop_row("Clip content", prop_editors.segmented(
            [(c, prop_editors.choice_label(c), None) for c in styling.TRISTATE],
            styling.choice_of("clip", style.get("clip")), setter("clip"), t), t,
            tip=tr("Cut what overflows the box")))
    if spacing:
        rows += [group("Spacing"), *spacing]
    if style and rows:
        rows.append(_core.container(ui.button(tr("Reset style"), lambda: d.clear_style(name), icon="rotate-ccw",
                                              variant="ghost", size="sm", theme=t), padding=(4, 0)))
    return rows
