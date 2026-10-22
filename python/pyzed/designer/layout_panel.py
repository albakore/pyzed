"""The Auto layout section of flex and grid containers, and how their children are sized, laid out like Figma's.

A Flex row or column is Figma's auto layout frame: a direction, an alignment box (where the children sit, or
spread along the main axis), the gap between them and the padding inside. A child of one picks, per axis,
**Fixed** (its own width or height) or **Fill** (it grows along the main axis and stretches across the other).
A Grid has columns, gaps and a row height instead of a direction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List, Optional

from .. import _core, i18n, ui
from ..theme import Theme
from . import layout as _layout
from . import prop_editors
from .locale import tr
from .model import Control

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: The container properties the Auto layout section edits (their plain rows are left out of the grid).
EDITED = ("direction", "gap", "padding", "justify", "align", "columns", "row_height")
#: How the children are spread along the main axis: Packed (where the alignment box puts them) or with the
#: free space between them.
SPREAD = (("", "Packed"), ("space-between", "Space between"), ("space-around", "Space around"),
          ("space-evenly", "Space evenly"))


def is_auto(control: Control) -> bool:
    """Whether ``control`` is a flex or grid container (it gets the Auto layout section)."""
    return _layout.kind(control) in ("flex", "grid")


def _set(d: "Designer", name: str, key: str, value: Any) -> None:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    d.doc.set_prop(name, key, value)


def auto_layout_rows(d: "Designer", c: Control, t: Theme, prop_row: Callable[..., Any]) -> List[Any]:
    """The rows of the Auto layout section of a flex or grid container."""
    p = _layout.props(c)
    name = c.name
    grid = _layout.kind(c) == "grid"
    rows: List[Any] = []
    if grid:
        rows.append(prop_row("Columns", prop_editors.number(
            p.get("columns", 2), lambda v: _set(d, name, "columns", max(int(v), 1)), t, min=1, max=24,
            tag="#"), t, tip=tr("How many cells each row has")))
    else:
        direction = str(p.get("direction", "row"))
        rows.append(prop_row("Direction", prop_editors.segmented([
            ("row", tr("Horizontal"), "arrow-right"), ("column", tr("Vertical"), "arrow-down"),
        ], direction, lambda v: _set(d, name, "direction", v), t), t,
            tip=tr("Line the children up side by side or one under the other")))
    rows.append(prop_row("Align", _align_editor(d, c, p, grid, t), t, lines=3,
                         tip=tr("Where the children sit inside the container")))
    gap = prop_editors.number(p.get("gap", 0), lambda v: _set(d, name, "gap", max(v, 0)), t, min=0, max=512,
                              tag="↔" if grid or p.get("direction", "row") != "column" else "↕",
                              tip="Space between the children")
    if grid:
        rows.append(prop_row("Gap", prop_editors.pair(gap, prop_editors.number(
            p.get("row_height", 0), lambda v: _set(d, name, "row_height", max(v, 0)), t, min=0, max=2048, tag="H",
            tip="Height of each row (0 shares the height)")), t))
    else:
        spread = str(p.get("justify", "start"))
        labels = {tr(label): value for value, label in SPREAD}
        current = next((label for label, value in labels.items() if value == spread), tr("Packed"))

        def pick(label: str) -> None:
            value = labels.get(label, "")
            _set(d, name, "justify", value or _packed_justify(p))

        rows.append(prop_row("Gap", prop_editors.pair(gap, ui.select(list(labels), current, pick, width="fill",
                                                                       size="sm", theme=t)), t,
                             tip=tr("Space between the children, or spread them over the free space")))
    rows.append(prop_row("Padding", _padding_editor(d, c, p, t), t,
                         lines=2 if prop_editors.is_split(d, f"{name}:layout_padding", p.get("padding")) else 1,
                         tip=tr("Space between the container's border and its children")))
    stretch = str(p.get("align", "stretch")) == "stretch"
    rows.append(prop_row("Fill across", _core.container(ui.switch(stretch, lambda v: _set(
        d, name, "align", "stretch" if v else "start"), theme=t), width="fill", align_x="end"), t,
        tip=tr("Children stretch to the container's height (in a row) or width (in a column)")))
    return rows


def _packed_justify(p: dict) -> str:
    justify = str(p.get("justify", "start"))
    return justify if justify in ("start", "center", "end") else "start"


def _align_editor(d: "Designer", c: Control, p: dict, grid: bool, t: Theme) -> Any:
    """The alignment box of a container: the spot clicked sets where the children go along both axes."""
    name = c.name
    row = grid or str(p.get("direction", "row")) != "column"
    justify = str(p.get("justify", "start"))
    align = str(p.get("align", "stretch"))
    cross = align if align in prop_editors.SPOTS else "start"
    spread = None
    if grid:
        main = cross
    elif justify in prop_editors.SPOTS:
        main = justify
    else:
        main, spread = "", ("x" if row else "y")
    x, y = (main, cross) if row else (cross, main)

    def pick(sx: str, sy: str) -> None:
        new_main, new_cross = (sx, sy) if row else (sy, sx)
        if not grid:
            d.doc.set_prop(name, "justify", new_main if spread is None else justify)
        _set(d, name, "align", new_cross)

    box = prop_editors.align_box(x, y, pick, t, spread=spread)
    note = tr("Spread over the free space") if spread else (tr("Children fill across") if align == "stretch"
                                                          else "")
    return _core.row([box, _core.container(ui.label(note, size="xs", color="text_muted", theme=t), width="fill",
                                           padding=(0, 0, 0, 8))], align="center")


def _padding_editor(d: "Designer", c: Control, p: dict, t: Theme) -> Any:
    """Horizontal and vertical padding (Figma's), or the four sides once unlinked."""
    name = c.name
    key = f"{name}:layout_padding"
    value = p.get("padding")
    if prop_editors.is_split(d, key, value):
        return prop_editors.box_editor(d, key, value, lambda v: d.doc.set_prop(name, "padding", v or 0), t)
    top, right, _bottom, _left = prop_editors.four(value)

    def change(horizontal: Optional[float] = None, vertical: Optional[float] = None) -> None:
        h = right if horizontal is None else float(horizontal)
        v = top if vertical is None else float(vertical)
        if h == v:  # one number, as the plain property always was
            d.doc.set_prop(name, "padding", prop_editors.compact((v, h, v, h)) or 0)
        else:  # vertical horizontal, like CSS
            d.doc.set_prop(name, "padding", [prop_editors._plain(v), prop_editors._plain(h)])

    def split() -> None:
        d.__dict__.setdefault("_split_boxes", set()).add(key)

    return _core.row([
        _core.container(prop_editors.pair(
            prop_editors.number(right, lambda v: change(horizontal=v), t, min=0, max=512, tag="↔",
                                tip="Left and right"),
            prop_editors.number(top, lambda v: change(vertical=v), t, min=0, max=512, tag="↕",
                                tip="Top and bottom")), width="fill"),
        ui.icon_button("square-dashed", split, size="xs", tooltip=tr("Edit each side"), theme=t),
    ], spacing=4, align="center")


# -- children of flex and grid containers -----------------------------------------------------------------------


def child_rows(d: "Designer", c: Control, parent: Control, t: Theme, prop_row: Callable[..., Any]) -> List[Any]:
    """How a child of a flex or grid container is sized: Fixed or Fill per axis (flex), its column span
    (grid) and its width and height."""
    kind = _layout.kind(parent)
    p = _layout.props(parent)
    name = c.name

    def num(field: str, tag: str) -> Any:
        return prop_editors.number(round(getattr(c, field)), lambda v, f=field: d.set_field(name, f, v), t, step=1,
                                   tag=tag)

    rows: List[Any] = []
    if kind == "flex":
        row = str(p.get("direction", "row")) != "column"
        grows = float(c.layout.get("grow", 0) or 0) > 0
        own = c.layout.get("align_self") or str(p.get("align", "stretch"))
        stretches = own == "stretch"
        fill_w, fill_h = (grows, stretches) if row else (stretches, grows)

        def sizing(axis: str, fill: bool) -> Any:
            main = (axis == "width") == row

            def pick(v: str) -> None:
                if main:
                    d.set_layout(name, "grow", 1 if v == "fill" else 0)
                else:
                    d.set_layout(name, "align_self", "stretch" if v == "fill" else "start")

            # "Fill" alone is the background section ("Relleno" in Spanish): this one has its own key
            fill_label = i18n.t("designer.Fill (size)", default="Fill")
            return prop_editors.segmented([("fixed", tr("Fixed"), None), ("fill", fill_label, None)],
                                          "fill" if fill else "fixed", pick, t)

        rows.append(prop_row("Width", prop_editors.pair(sizing("width", fill_w), num("width", "W")), t,
                             tip=tr("Fixed keeps this width; Fill takes the room the container leaves")))
        rows.append(prop_row("Height", prop_editors.pair(sizing("height", fill_h), num("height", "H")), t,
                             tip=tr("Fixed keeps this height; Fill takes the room the container leaves")))
        if grows:
            rows.append(prop_row("Grow", prop_editors.number(
                float(c.layout.get("grow", 1)), lambda v: d.set_layout(name, "grow", max(v, 0)), t, min=0, max=24,
                step=1), t, tip=tr("Share of the free space this control takes next to others that fill")))
    else:
        rows.append(prop_row("Column span", prop_editors.number(
            float(c.layout.get("span", 1)), lambda v: d.set_layout(name, "span", int(v)), t, min=1, max=24), t,
            tip=tr("How many cells of its row the control takes")))
        rows.append(prop_row("Size", prop_editors.pair(num("width", "W"), num("height", "H")), t))
    rows.append(_core.container(ui.label(tr("Placed by {name}: drag it to reorder.", name=parent.name), size="xs",
                                         color="text_muted", theme=t), padding=(2, 0)))
    return rows


def wrap_auto_layout(d: "Designer") -> None:
    """Shift+A, like Figma: puts the selection in a flex row (or a column, when it is stacked). With a single
    container of freely placed controls selected, its children go in the new row or column, inside it."""
    form = d.doc.form
    picked = [form[n] for n in d.doc.selection if form.get(n) is not None]
    if not picked:
        return
    if len(picked) == 1 and _layout.kind(picked[0]) == "free" and form.children(picked[0].name):
        d.doc.selection = [c.name for c in form.children(picked[0].name)]
        picked = [form[n] for n in d.doc.selection]
    rects = d.doc.rects()
    xs = [rects[c.name][0] for c in picked if c.name in rects]
    ys = [rects[c.name][1] for c in picked if c.name in rects]
    stacked = len(picked) > 1 and (max(ys) - min(ys)) > (max(xs) - min(xs))
    d.wrap("column" if stacked else "row")


def ungroup(d: "Designer") -> None:
    """Ctrl+Shift+G: takes the controls out of the selected containers (where they are on screen) and removes
    the containers."""
    if d.doc.ungroup():
        d._selection_changed()


def group(d: "Designer") -> None:
    """Ctrl+G: puts the selection in an invisible panel (a group that keeps them where they are)."""
    if d.doc.wrap("panel", props={"background": "transparent", "border": False}) is not None:
        d._selection_changed()

