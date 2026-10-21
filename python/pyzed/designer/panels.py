"""The designer's docks: toolbox, outline, property grid and events list (the code editor is in ``code_panel``).

Each function is a view of a ``Designer``: it reads its state and wires widget callbacks
to its methods, so all behavior stays in ``Designer``/``Document``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha, themes
from . import components as _components
from . import help as _help
from . import scene_code as _scene_code
from . import prop_editors, spacing
from .components import Prop
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

LABEL_WIDTH = spacing.LABEL_WIDTH
ROW_HEIGHT = spacing.ROW_HEIGHT
#: Icons of the property groups in the accordion.
SECTION_ICONS = {"Appearance": "palette", "Data": "database", "Behavior": "mouse-pointer-click",
                 "Layout": "layout-dashboard", "Window": "app-window", "Look": "paintbrush", "Designer": "grid-3x3",
                 "Align": "align-start-vertical", "Spacing and size": "ruler", "Position": "move", "Style": "paint-bucket",
                 "Effects": "sparkles", "Animation": "clapperboard"}
ACCENTS = ("#74ade8", "#b477cf", "#a1c181", "#e5c07b", "#d07277", "#6eb4bf", "#ff8a65")


# -- small building blocks -------------------------------------------------------


def section(title: str, t: Theme, end: Any = None) -> Any:
    """Builds a section heading of a panel: ``title`` in small capitals, with ``end`` at the right."""
    return _core.container(
        _core.row([ui.label(title.upper(), size="xs", weight="semibold", color="text_muted", theme=t),
                   _core.space(width="fill"), end], align="center"),
        padding=(10, spacing.GUTTER, 4, spacing.GUTTER), width="fill")


def scroll_panel(content: Any) -> Any:
    """A dock panel's scrolling body, with room for the scroll bar so the gutter shows on both sides."""
    return _core.scrollable(_core.container(content, padding=(0, spacing.SCROLLBAR, 0, 0), width="fill"),
                            height="fill")


class Group:
    """Starts a collapsible section of the property grid (see ``properties``)."""

    def __init__(self, title: str) -> None:
        self.title = title


def prop_row(title: str, editor: Any, t: Theme, *, tip: Optional[str] = None, tall: bool = False,
             end: Any = None, lines: int = 1) -> Any:
    """A property: its name, then its editor on the same line, or below it at full width when ``tall``
    (lists, tables and text areas). ``end`` goes at the end of a tall row's title line. ``lines`` is how many
    rows of fields the editor stacks (two for a box edited side by side)."""
    label = ui.label(tr(title), size="sm", color="text_muted", wrap=False, theme=t)
    if tip:
        label = ui.tooltip(label, tip, theme=t)
    if tall:
        head = _core.row([label, _core.space(width="fill"), end], align="center", height=ROW_HEIGHT - 4)
        return _core.container(_core.column([head, editor], spacing=4, width="fill"), padding=(spacing.ROW_PAD, 0),
                               width="fill")
    return _core.container(
        _core.row([_core.container(label, width=LABEL_WIDTH, clip=True),
                   _core.container(editor, width="fill", height=ROW_HEIGHT * lines + 4 * (lines - 1),
                                   align_y="center")],
                  spacing=spacing.LABEL_GAP, align="center"),
        padding=(spacing.ROW_PAD, 0), width="fill")


_HEX = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")


def valid_color(value: Any, t: Theme) -> Optional[str]:
    """``value`` (a theme token or ``#hex``) as a color the renderer takes, or ``None`` while it is not one
    (a half-typed ``#3b8`` or an unknown token)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        color = t.color(value.strip())
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    if not isinstance(color, str):
        return None
    return color if color == "transparent" or _HEX.fullmatch(color) else None


def swatch(color: Optional[str], t: Theme, on_press: Any = None, *, selected: bool = False) -> Any:
    """Builds a 16-pixel color square (outlined when ``selected``); a button when ``on_press`` is given."""
    color = valid_color(color, t) if color else None
    box = _core.container(width=16, height=16, bg=color or "transparent", radius=4,
                          border_color=t.text if selected else t.border, border_width=2 if selected else 1)
    if on_press is None:
        return box
    return _core.button(box, on_press, padding=0, bg="transparent", hover_bg="transparent")


def icon_editor(d: "Designer", value: Any, on_change: Callable[[Any], Any], t: Theme, *,
                placeholder: str = "lucide name", size: str = "sm") -> Any:
    """An icon property: its preview (click it to pick from the icon dialog), the name and a "…" button."""
    from ..icons import CODEPOINTS

    name = str(value or "")
    known = name in CODEPOINTS
    preview = _core.button(
        _core.container(_icon(name if known else "circle-dashed", size=14,
                              color=None if known else t.icon_muted), center=True),
        lambda: d.open_icon_picker(name, on_change), padding=0, width=22, height=22, radius=t.radius_sm,
        bg="transparent", hover_bg=t.element_hover, color=t.icon)
    return _core.row([
        ui.tooltip(preview, tr("Choose an icon…"), theme=t),
        ui.input(name, on_change, placeholder=tr(placeholder), size=size, mono=True, theme=t),
        ui.icon_button("ellipsis", lambda: d.open_icon_picker(name, on_change), size="xs",
                       tooltip=tr("Choose an icon…"), theme=t),
    ], spacing=4, align="center")


def editor_for(d: "Designer", prop: Prop, value: Any, on_change: Callable[[Any], Any], key: str, t: Theme) -> Any:
    """The property-grid editor for one property, picked by ``prop.kind``."""
    kind = prop.kind
    if kind == "bool":
        return _core.container(ui.switch(bool(value), on_change, theme=t), width="fill", align_x="end")
    if kind == "number":
        number = 0.0 if value in (None, "") else float(value)
        return ui.number_field(number, on_change, min=prop.min, max=prop.max, step=prop.step, width="fill", theme=t)
    if kind == "choice":
        choices = [str(c) for c in prop.choices]
        if prop_editors.fits_segmented(choices):
            return prop_editors.segmented([(c, c, None) for c in choices], str(value), on_change, t)
        return ui.select(choices, str(value), on_change, width="fill", size="sm", theme=t)
    if kind == "typed":
        return typed_editor(d, prop, value, on_change, key, t)
    if kind == "list" and key not in d.text_editors:
        return list_editor(value, on_change, t)
    if kind == "rows" and key not in d.text_editors:
        return rows_editor(value, on_change, t)
    if kind in ("multiline", "list", "rows"):
        return text_area(d, key, value, on_change, t)
    if kind == "color":
        return prop_color_editor(d, value, on_change, key, t)
    if kind == "icon":
        return icon_editor(d, value, on_change, t)
    return ui.input("" if value is None else str(value), on_change, size="sm", theme=t)


TALL_KINDS = ("multiline", "list", "rows", "typed")


def typed_editor(d: "Designer", prop: Prop, value: Any, on_change: Callable[[Any], Any], key: str, t: Theme) -> Any:
    """The editor of a property of any annotation (``int | None``, ``dict[str, int]``...): its value on one
    line and its items (list items, dict entries) below, like a details panel."""
    import ast

    from . import type_editor

    def change(source: str) -> None:
        try:
            on_change(ast.literal_eval(source))
        except (ValueError, SyntaxError):
            pass  # a form keeps plain values: lists, dicts, numbers, text and None

    kind = type_editor.parse_type(prop.type)
    ctx = type_editor.Context(d, t, drafts=d.__dict__.setdefault("_type_drafts", {}))
    head, items = type_editor.build(kind, _scene_code.literal(value), change, ctx, key)
    if not items:
        return head
    return _core.column([head, type_editor.rows_view(items, t, LABEL_WIDTH)], spacing=4, width="fill")


def _text_toggle(d: "Designer", prop: Prop, key: str, t: Theme) -> Any:
    """For lists and tables: switch between the item editor and plain text."""
    if prop.kind not in ("list", "rows"):
        return None
    as_text = key in d.text_editors
    return ui.icon_button("list" if as_text else "file-text", lambda: d.toggle_text_editor(key), size="xs",
                          tooltip="Edit item by item" if as_text else "Edit as text", theme=t)


def text_area(d: "Designer", key: str, value: Any, on_change: Callable[[Any], Any], t: Theme, height: float = 132) -> Any:
    """Builds a small code-editor text area for a property (a list value is shown one item per line).

    Its id includes the document's revision, so undo and redo reload its text.
    """
    text = value if isinstance(value, str) else "\n".join(map(str, value or []))
    return _core.container(
        ui.editor(f"prop:{key}:{d.doc.revision}", text, on_change=on_change, gutter=False, wrap=True,
                  active_line=False, font_size=12.5, height=height, theme=t),
        width="fill", height=height, border_color=t.border_variant, border_width=1, radius=t.radius_sm, clip=True)


def _items(value: Any) -> List[str]:
    if isinstance(value, str):
        return value.split("\n") if value else []
    return [str(v) for v in (value or [])]


def list_editor(value: Any, on_change: Callable[[str], Any], t: Theme) -> Any:
    """One field per item, with buttons to move and remove it, and Add item at the end."""
    items = _items(value)

    def save(new: List[str]) -> None:
        on_change("\n".join(new))

    def edit(i: int, text: str) -> None:
        save(items[:i] + [text.replace("\n", " ")] + items[i + 1:])

    def move(i: int, step: int) -> None:
        j = i + step
        if 0 <= j < len(items):
            new = list(items)
            new[i], new[j] = new[j], new[i]
            save(new)

    rows: List[Any] = []
    for i, item in enumerate(items):
        rows.append(_core.row([
            _core.container(ui.label(str(i + 1), size="xs", color="text_muted", mono=True, theme=t), width=18),
            ui.input(item, lambda v, i=i: edit(i, v), size="sm", theme=t),
            ui.icon_button("chevron-up", lambda i=i: move(i, -1), size="xs", tooltip="Move up", disabled=i == 0,
                           theme=t),
            ui.icon_button("chevron-down", lambda i=i: move(i, 1), size="xs", tooltip="Move down",
                           disabled=i == len(items) - 1, theme=t),
            ui.icon_button("x", lambda i=i: save(items[:i] + items[i + 1:]), size="xs", tooltip="Remove", theme=t),
        ], spacing=4, align="center"))
    rows.append(ui.button(tr("Add item"), lambda: save(items + [f"{tr('Item')} {len(items) + 1}"]), icon="plus",
                          variant="ghost", size="sm", theme=t))
    return _core.column(rows, spacing=3, width="fill")


CELL_WIDTH = 96.0


def parse_rows(value: Any) -> List[List[str]]:
    """CSV text as rows of cells (the first row is the header), every row as long as the longest."""
    lines = [line for line in str(value or "").splitlines() if line.strip()]
    rows = [[cell.strip() for cell in line.split(",")] for line in lines]
    width = max((len(r) for r in rows), default=0)
    return [r + [""] * (width - len(r)) for r in rows]


def format_rows(rows: List[List[str]]) -> str:
    """Returns ``rows`` as CSV text, one line per row (commas inside cells become spaces); the reverse of
    ``parse_rows``."""
    return "\n".join(", ".join(cell.replace(",", " ").strip() for cell in row) for row in rows)


def rows_editor(value: Any, on_change: Callable[[str], Any], t: Theme) -> Any:
    """A small spreadsheet: the header row, then one row of cells per data row, with add and remove buttons."""
    rows = parse_rows(value) or [[tr("Column") + " 1"]]
    columns = len(rows[0])

    def save(new: List[List[str]]) -> None:
        on_change(format_rows(new))

    def edit(r: int, c: int, text: str) -> None:
        new = [list(row) for row in rows]
        new[r][c] = text
        save(new)

    def add_row() -> None:
        save(rows + [[""] * columns])

    def add_column() -> None:
        save([row + [tr("Column") + f" {columns + 1}" if i == 0 else ""] for i, row in enumerate(rows)])

    def remove_column(c: int) -> None:
        if columns > 1:
            save([row[:c] + row[c + 1:] for row in rows])

    def cell(r: int, c: int) -> Any:
        field = ui.input(rows[r][c], lambda v, r=r, c=c: edit(r, c, v), size="sm", width=CELL_WIDTH,
                         placeholder=tr("Header") if r == 0 else "", theme=t)
        return field if r else _core.container(field, bg=t.element, radius=t.radius_sm)

    gutter = 22.0
    lines: List[Any] = [_core.row([_core.space(width=gutter)] + [
        _core.container(ui.icon_button("x", lambda c=c: remove_column(c), size="xs", tooltip="Remove column",
                                       disabled=columns == 1, theme=t), width=CELL_WIDTH, align_x="end")
        for c in range(columns)], spacing=4)]
    for r in range(len(rows)):
        start = (_core.container(ui.label(str(r), size="xs", color="text_muted", mono=True, theme=t), width=gutter)
                 if r else _core.container(_icon("heading", size=12, color=t.icon_muted), width=gutter))
        end = (ui.icon_button("x", lambda r=r: save(rows[:r] + rows[r + 1:]), size="xs", tooltip="Remove row", theme=t)
               if r else _core.space(width=22))
        lines.append(_core.row([start] + [cell(r, c) for c in range(columns)] + [end], spacing=4, align="center"))
    grid = _core.scrollable(_core.column(lines, spacing=3), direction="horizontal", width="fill")
    buttons = _core.row([ui.button(tr("Add row"), add_row, icon="plus", variant="ghost", size="sm", theme=t),
                         ui.button(tr("Add column"), add_column, icon="plus", variant="ghost", size="sm", theme=t)],
                        spacing=4)
    return _core.column([grid, buttons], spacing=4, width="fill")


# -- toolbox ---------------------------------------------------------------------


def press_row(d: "Designer", key: str, label: str, on_press: Callable[[], Any], t: Theme, *, icon: Optional[str] = None,
              selected: bool = False, height: float = spacing.ITEM_HEIGHT, indent: float = 0, start: Any = None, end: Any = None,
              color: Optional[str] = None, on_right_press: Any = None, on_move: Any = None, on_exit: Any = None,
              drop: Optional[str] = None) -> Any:
    """A list row that reacts on press (not on click, like ``ui.list_item``), so it can start a drag.

    ``drop`` marks where a dragged control would land: a line ``"before"`` or ``"after"`` the
    row, or a frame around it for ``"inside"``.
    """
    hovered = d.hovered_row == key
    text_color = t.color(color) if color else t.text
    row = _core.row([
        _core.space(width=indent) if indent else None,
        start,
        _icon(icon, size=14, color=t.icon_muted) if icon else None,
        _core.container(_core.text(label, size=13.5, color=text_color, wrap=False), width="fill", clip=True),
        end,
    ], spacing=6, align="center")
    body = _core.container(row, padding=(0, spacing.GUTTER), width="fill", height=height, align_y="center",
                           bg=t.ghost_selected if selected else (t.ghost_hover if hovered else None),
                           border_color=t.accent if drop == "inside" else None,
                           border_width=1.5 if drop == "inside" else 0)
    if drop in ("before", "after"):
        line = _core.container(width="fill", height=2, bg=t.accent)
        body = _core.stack([body, _core.container(line, width="fill", height=height,
                                                  align_y="start" if drop == "before" else "end")],
                           width="fill", height=height)

    def leave() -> None:
        d.leave_row(key)
        if on_exit is not None:
            on_exit()

    return _core.mouse_area(body, on_press=on_press, on_right_press=on_right_press,
                            on_enter=lambda: d.enter_row(key), on_exit=leave, on_move=on_move)


def toolbox(d: "Designer", t: Theme) -> Any:
    """Builds the toolbox: a search box, the pointer, and the components by category, each of which can be
    picked or dragged onto the form."""
    query = d.toolbox_query.strip().lower()
    rows: List[Any] = [
        press_row(d, "tool:", tr("Pointer"), d.pick_tool(None), t, icon="mouse-pointer-2", selected=d.tool is None),
    ]
    for category, items in _components.categories().items():
        shown = [c for c in items if not query or query in c.label.lower() or query in tr(c.label).lower()
                 or query in c.type]
        if not shown:
            continue
        rows.append(section(tr(category), t))
        for spec in shown:
            # press and drag onto the form (or a container), or click to pick it and then click on the form
            rows.append(ui.tooltip(
                press_row(d, f"tool:{spec.type}", tr(spec.label), lambda type_=spec.type: d.press_tool(type_), t,
                          icon=spec.icon, selected=d.tool == spec.type),
                tr(spec.description) if spec.description else tr(spec.label), position="right", theme=t))
    if not query:  # a reusable component of your own joins the toolbox once it is created
        rows.append(ui.tooltip(press_row(d, "tool:+component", tr("New component…"), d.new_component, t,
                                         icon="plus", color="text_muted"),
                               tr("A reusable piece for forms and other components, not a window"), position="right",
                               theme=t))
    return _core.column([
        _core.container(ui.search_input(d.toolbox_query, d.set_toolbox_query, placeholder=tr("Search components…"),
                                        size="sm", theme=t), padding=(spacing.BLOCK, spacing.GUTTER)),
        scroll_panel(_core.column(rows, width="fill", padding=(0, 0, spacing.BLOCK, 0))),
    ], width="fill", height="fill")


OUTLINE_ROW = 24


def outline(d: "Designer", t: Theme) -> Any:
    """The form's controls as a tree: containers can be folded and get a "+" to add controls inside them."""
    from . import scene_panel

    doc = d.doc
    form = doc.form
    rows: List[Any] = [press_row(d, "outline:", form.name, d.select_form, t, icon="app-window",
                                 selected=not doc.selection, height=OUTLINE_ROW,
                                 end=ui.icon_button("plus", lambda: d.open_add_child(None), size="xs",
                                                    tooltip="Add a control", theme=t))]

    def add(parent: Optional[str], depth: int) -> None:
        children = form.children(parent)
        holder = form.get(parent) if parent else None
        # top-most first, like layers in a drawing app; flex rows and grids list them in reading order
        flowing = holder is not None and _components.get(holder.type).container in ("flex", "grid")
        for c in (children if flowing else reversed(children)):
            spec = _components.get(c.type)
            if not spec.visual:
                continue  # listed at the end, with the other non-visual components
            container = spec.container is not None
            folded = c.name in d.folded
            buttons = [
                ui.icon_button("plus", lambda n=c.name: d.open_add_child(n), size="xs", tooltip="Add inside",
                               theme=t) if container else None,
                ui.icon_button("eye" if c.visible else "eye-off",
                               lambda n=c.name, v=c.visible: d.set_field(n, "visible", not v), size="xs",
                               tooltip="Visible", theme=t),
                ui.icon_button("lock" if c.locked else "lock-open",
                               lambda n=c.name, v=c.locked: d.set_field(n, "locked", not v), size="xs",
                               selected=c.locked, tooltip="Lock", theme=t),
            ]
            chevron = None
            members = None if container else scene_panel.child_members(c.type)  # a component placed here
            if container:
                chevron = ui.icon_button("chevron-right" if folded else "chevron-down",
                                         lambda n=c.name: d.toggle_folded(n), size="xs", theme=t)
            elif members:
                opened = c.name in d.members_open
                chevron = ui.icon_button("chevron-down" if opened else "chevron-right",
                                         lambda n=c.name: d.toggle_members(n), size="xs",
                                         tooltip="Its properties and methods", theme=t)
            else:
                chevron = _core.space(width=20)
            target = d.outline_target
            # press to select, drag to reorder or to move into another container (or onto the form)
            rows.append(press_row(
                d, f"outline:{c.name}", c.name, lambda n=c.name: d.press_outline(n), t, icon=spec.icon,
                selected=doc.is_selected(c.name), indent=4 + depth * 14, start=chevron, height=OUTLINE_ROW,
                end=_core.row(buttons, spacing=0), color=None if c.visible else "text_muted",
                on_right_press=lambda n=c.name: d.open_outline_menu(n),
                on_move=lambda _x, y, n=c.name: d.hover_outline(n, y, OUTLINE_ROW),
                on_exit=lambda n=c.name: d.leave_outline(n),
                drop=target[1] if target is not None and target[0] == c.name else None))
            if container and not folded:
                add(c.name, depth + 1)
            if members and c.name in d.members_open:
                rows.extend(scene_panel.member_rows(d, c, members, 4 + (depth + 1) * 14 + 20, t))

    add(None, 0)
    tray = [c for c in form.controls if not _components.get(c.type).visual]
    if tray:  # timers, watchers... belong to the form but have no place on it
        rows.append(_core.container(ui.label(tr("Non-visual"), size="xs", color="text_muted", theme=t),
                                    padding=(6, spacing.GUTTER, 2, spacing.GUTTER + 4), width="fill"))
        for c in tray:
            rows.append(press_row(
                d, f"outline:{c.name}", c.name, lambda n=c.name: d.press_outline(n), t,
                icon=_components.get(c.type).icon, selected=doc.is_selected(c.name), indent=4, height=OUTLINE_ROW,
                start=_core.space(width=20), color=None if c.enabled else "text_muted",
                on_right_press=lambda n=c.name: d.open_outline_menu(n)))
    return scroll_panel(_core.column(rows, width="fill"))


# -- properties ------------------------------------------------------------------


def _layout_rows(d: "Designer", c, t: Theme) -> List[Any]:
    from . import layout as _layout

    def num(field: str):
        return ui.number_field(round(getattr(c, field)), lambda v, f=field: d.set_field(c.name, f, v), step=1,
                               width="fill", theme=t)

    form = d.doc.form
    parent = form.get(c.parent) if c.parent else None
    kind = _layout.kind(parent) if parent is not None else None
    rows: List[Any] = [Group("Position")]
    if parent is not None:
        rows.append(prop_row(tr("Inside"), _core.row([
            ui.button(parent.name, lambda: d.select_from_outline(parent.name), icon=_components.get(parent.type).icon,
                      variant="ghost", size="sm", theme=t),
            _core.space(width="fill"),
            ui.icon_button("arrow-up-left", lambda: d.move_out(c.name), size="sm", tooltip="Move out of the container",
                           theme=t),
        ], align="center"), t, tip="The container holding this control"))
    if kind in ("flex", "grid"):
        if kind == "flex":
            rows.append(prop_row(tr("Grow"), ui.number_field(float(c.layout.get("grow", 0)),
                                                         lambda v: d.set_layout(c.name, "grow", v), min=0, step=1,
                                                         width="fill", theme=t), t,
                                 tip="Share of the free space this control takes (0 keeps its size)"))
        else:
            rows.append(prop_row(tr("Column span"), ui.number_field(float(c.layout.get("span", 1)),
                                                                lambda v: d.set_layout(c.name, "span", int(v)), min=1,
                                                                max=24, step=1, width="fill", theme=t), t))
        rows += [prop_row("Width", num("width"), t), prop_row("Height", num("height"), t),
                 _core.container(ui.label(f"Placed by {parent.name}: drag it to reorder.", size="xs",
                                          color="text_muted", theme=t), padding=(2, 0))]
    elif kind == "dock":
        rows.append(_core.container(ui.label(tr("Placed by its dock: change its Side, or the dock's sizes."),
                                             size="xs", color="text_muted", theme=t), padding=(2, 0)))
    else:
        from . import anchor_panel

        rows += anchor_panel.position_rows(d, c, t, prop_row)
    return rows + [
        Group("Behavior"),
        prop_row("Visible", _core.container(ui.switch(c.visible, lambda v: d.set_field(c.name, "visible", v),
                                                      theme=t), width="fill", align_x="end"), t),
        prop_row("Enabled", _core.container(ui.switch(c.enabled, lambda v: d.set_field(c.name, "enabled", v),
                                                      theme=t), width="fill", align_x="end"), t),
        prop_row("Locked", _core.container(ui.switch(c.locked, lambda v: d.set_field(c.name, "locked", v),
                                                     theme=t), width="fill", align_x="end"), t,
                 tip="Locked controls cannot be moved or resized"),
    ]


def _help_button(d: "Designer", name: str, t: Theme) -> Any:
    """The "?" of a control's header: opens its page in the built-in reference (Shift+F1)."""
    return ui.icon_button("book-marked", lambda: d.open_reference(d.help_page_of(name)), size="sm",
                          tooltip=tr("Help") + " (Shift+F1)", theme=t)


def control_properties(d: "Designer", t: Theme) -> List[Any]:
    """Returns the property grid rows of the primary selected control: its name, its properties by group, then
    its style and layout rows."""
    c = d.doc.primary
    assert c is not None
    spec = _components.get(c.type)
    rows: List[Any] = [
        _core.container(_core.row([_icon(spec.icon, size=16, color=t.accent),
                                   _core.column([ui.label(tr(spec.label), weight="semibold", theme=t),
                                                 ui.label(tr(spec.description), size="xs", color="text_muted", theme=t)],
                                                width="fill"),
                                   _help_button(d, c.name, t)],
                                  spacing=10, align="center"), padding=spacing.HEADER_PADDING, width="fill"),
        # inset like the rows inside the sections below, so every label and field lines up
        _core.container(prop_row("Name", ui.input(d.name_buffer, d.set_name_buffer, on_submit=d.commit_name, size="sm",
                                                  mono=True, theme=t), t,
                                 tip="Press Enter to rename (handlers are renamed too)"), padding=(0, spacing.GUTTER),
                        width="fill"),
    ]
    groups: dict = {}
    for prop in spec.props:
        groups.setdefault(prop.group, []).append(prop)
    # the binding and validation rows join the control's Data group (or make one)
    data = data_rows(d, c, t) if not getattr(d.doc, "is_scene", False) else []
    for group, props in groups.items():
        rows.append(Group(group))
        for prop in props:
            value = c.props.get(prop.name, prop.default)
            key = f"{c.name}.{prop.name}"
            rows.append(prop_row(prop.title, editor_for(d, prop, value, d.prop_setter(c.name, prop), key, t), t,
                                 tip=_help.prop_doc(c.type, prop.name) or None, tall=prop.kind in TALL_KINDS,
                                 end=_text_toggle(d, prop, key, t)))
        if group == "Data":
            rows.extend(data)
            data = []
    if data:
        rows += [Group("Data"), *data]
    if not spec.visual:  # it draws nothing: no style, animations or position, only whether it runs
        return rows + ([] if "Behavior" in groups else [Group("Behavior")]) + [prop_row(
            "Enabled", _core.container(ui.switch(c.enabled, lambda v: d.set_field(c.name, "enabled", v), theme=t),
                                       width="fill", align_x="end"), t,
            tip="A disabled component raises no events")]
    rows.extend(style_rows(d, c.name, c.style, t))
    from . import motion_panel

    rows.extend(motion_panel.effect_rows(d, c, t))
    rows.extend(motion_panel.animation_rows(d, c, t))
    rows.extend(_layout_rows(d, c, t))
    return rows


def data_rows(d: "Designer", c, t: Theme) -> List[Any]:
    """The binding rows of a control's Data section: the field of ``form.data`` it is bound to and its
    validation rules (empty when it cannot be bound)."""
    from . import binding

    prop = binding.bound_prop(c.type)
    if prop is None:
        return []
    doc = d.doc
    two_way = binding.two_way(c.type)
    hint = (tr("The field of form.data this control shows and edits ({prop})", prop=prop) if two_way else
            tr("The field of form.data, or a Python expression over its fields, this control shows ({prop})",
               prop=prop))
    rows: List[Any] = [prop_row(
        "Bind to", ui.input(c.bind, lambda v: doc.set_bind(c.name, v), size="sm", mono=True,
                            placeholder="customer.name" if two_way else 'f"{first} {last}"', theme=t), t, tip=hint)]

    def number(rule: str, title: str, tip: str, integer: bool = True) -> Any:
        def set_value(text: str) -> None:
            text = text.strip()
            try:
                value = (int(text) if integer else float(text)) if text else None
            except ValueError:
                return
            doc.set_rule(c.name, rule, value)
        current = c.rules.get(rule)
        shown = "" if current is None else (f"{current:g}" if isinstance(current, float) else str(current))
        return prop_row(title, ui.input(shown, set_value, size="sm", mono=True, placeholder=tr("none"), theme=t), t,
                        tip=tr(tip))

    for rule in binding.rules_for(c.type):
        if rule == "required":
            tip = ("The box must be checked (to accept terms, for example)" if c.type in ("checkbox", "switch")
                   else "The value cannot be empty")
            rows.append(prop_row("Required", _core.container(
                ui.switch(bool(c.rules.get("required")), lambda v: doc.set_rule(c.name, "required", v), theme=t),
                width="fill", align_x="end"), t, tip=tr(tip)))
        elif rule == "min_length":
            rows.append(number("min_length", "Minimum length", "Fewest characters allowed"))
        elif rule == "max_length":
            rows.append(number("max_length", "Maximum length", "Most characters allowed"))
        elif rule == "pattern":
            rows.append(prop_row("Pattern", ui.input(c.rules.get("pattern", ""),
                                                     lambda v: doc.set_rule(c.name, "pattern", v), size="sm",
                                                     mono=True, placeholder=r"[^@]+@[^@]+\.\w+", theme=t), t,
                                 tip=tr("A regular expression the whole text must match")))
        elif rule == "min":
            rows.append(number("min", "Minimum", "Smallest value allowed", integer=False))
        elif rule == "max":
            rows.append(number("max", "Maximum", "Largest value allowed", integer=False))
        elif rule == "message":
            rows.append(prop_row("Message", ui.input(c.rules.get("message", ""),
                                                     lambda v: doc.set_rule(c.name, "message", v), size="sm",
                                                     placeholder=tr("built-in message"), theme=t), t,
                                 tip=tr("Shown instead of the built-in message when a rule fails (@key translates "
                                        "it)")))
    return rows


def multi_properties(d: "Designer", t: Theme) -> List[Any]:
    """Returns the property grid rows shown when several controls are selected: align, distribute and
    same-size tools."""
    count = len(d.doc.selection)
    tools = [
        ("Align", [("align-start-vertical", "left", "Left edges"), ("align-center-vertical", "center", "Centers"),
                   ("align-end-vertical", "right", "Right edges"), ("align-start-horizontal", "top", "Top edges"),
                   ("align-center-horizontal", "middle", "Middles"), ("align-end-horizontal", "bottom",
                                                                      "Bottom edges")]),
    ]
    rows: List[Any] = [_core.container(ui.label(f"{count} controls selected", weight="semibold", theme=t),
                                       padding=spacing.HEADER_PADDING)]
    for title, items in tools:
        rows.append(Group(title))
        rows.append(_core.container(_core.row([ui.icon_button(icon, lambda e=edge: d.align(e), tooltip=tip, theme=t)
                                               for icon, edge, tip in items], spacing=2)))
    rows.append(Group("Spacing and size"))
    rows.append(_core.container(_core.row([
        ui.icon_button("align-horizontal-distribute-center", lambda: d.distribute("horizontal"),
                       tooltip="Distribute horizontally", theme=t),
        ui.icon_button("align-vertical-distribute-center", lambda: d.distribute("vertical"),
                       tooltip="Distribute vertically", theme=t),
        ui.icon_button("stretch-horizontal", lambda: d.same_size("width"), tooltip="Same width", theme=t),
        ui.icon_button("stretch-vertical", lambda: d.same_size("height"), tooltip="Same height", theme=t),
    ], spacing=2)))
    return rows


def form_properties(d: "Designer", t: Theme) -> List[Any]:
    """Returns the property grid rows of the form itself: window, look (theme, accent, background, style...)
    and designer settings."""
    form = d.doc.form

    def setter(key: str, cast: Callable[[Any], Any] = lambda v: v):
        return lambda v: d.set_form(key, cast(v))

    accent_row = _core.row([swatch(color, t, lambda c=color: d.set_form("accent", c), selected=form.accent == color)
                            for color in ACCENTS]
                           + [ui.icon_button("x", lambda: d.set_form("accent", None), size="xs",
                                             tooltip="Theme default", theme=t)], spacing=6, align="center")
    return [
        _core.container(_core.row([_icon("app-window", size=16, color=t.accent),
                                   ui.label("Form", weight="semibold", theme=t)], spacing=10, align="center"),
                        padding=spacing.HEADER_PADDING),
        Group("Window"),
        prop_row("Name", ui.input(form.name, setter("name"), size="sm", mono=True, theme=t), t),
        prop_row("Title", ui.input(form.title, setter("title"), size="sm", theme=t), t),
        prop_row("Width", ui.number_field(form.width, setter("width", float), min=120, step=8, width="fill", theme=t), t),
        prop_row("Height", ui.number_field(form.height, setter("height", float), min=80, step=8, width="fill", theme=t),
                 t),
        prop_row("Resizable", _core.container(ui.switch(form.resizable, setter("resizable"), theme=t), width="fill",
                                              align_x="end"), t),
        Group("Look"),
        prop_row("Theme", ui.select(themes.names(), form.theme, setter("theme"), width="fill", size="sm", theme=t), t),
        prop_row("Accent", accent_row, t),
        prop_row("Custom accent", ui.input(form.accent or "", setter("accent", lambda v: v or None),
                                           placeholder="#rrggbb", size="sm", mono=True, theme=t), t),
        prop_row("Background", ui.input(form.background or "", setter("background", lambda v: v or None),
                                        placeholder=tr("theme default"), size="sm", mono=True, theme=t), t),
        prop_row("Corner radius", ui.number_field(form.radius if form.radius is not None else 6,
                                                  setter("radius", float), min=0, max=24, width="fill", theme=t), t),
        prop_row("Font size", ui.number_field(form.font_size, setter("font_size", float), min=8, max=32, width="fill",
                                              theme=t), t),
        *style_rows(d, None, form.style, t, fields=_global_fields()),
        Group("Designer"),
        prop_row("Grid size", ui.number_field(form.grid, setter("grid", int), min=2, max=64, width="fill", theme=t), t),
    ]


def _global_fields() -> Any:
    from .styling import GLOBAL_FIELDS

    return GLOBAL_FIELDS


def properties(d: "Designer", t: Theme) -> Any:
    """The property grid: a header, then one collapsible box per group of properties."""
    if len(d.doc.selection) > 1:
        rows = multi_properties(d, t)
    elif d.doc.primary is not None:
        rows = control_properties(d, t)
    else:
        rows = form_properties(d, t)
    if getattr(d.doc, "is_scene", False):  # component mode: the component itself, and bindings
        from . import scene_panel

        rows = scene_panel.properties(d, t, rows)
    head: List[Any] = []
    groups: List[Any] = []
    for row in rows:
        if isinstance(row, Group):
            groups.append((row.title, []))
        elif groups:
            groups[-1][1].append(row)
        else:
            head.append(row)
    sections = [(title, tr(title), _core.column(items, width="fill", spacing=spacing.ROW_GAP))
                for title, items in groups]
    body = ui.accordion(sections, open={title for title, _ in groups} - d.collapsed_sections,
                        on_toggle=d.toggle_section, icons=SECTION_ICONS, padding=spacing.GROUP_PADDING, theme=t)
    top = _core.column(head, width="fill", spacing=spacing.ROW_GAP, padding=(0, 0, spacing.ROW_GAP * 2, 0))
    return scroll_panel(_core.column([top, _core.container(body, padding=(0, 0, 16, 0), width="fill")],
                                     width="fill"))


# -- events ----------------------------------------------------------------------


def events(d: "Designer", t: Theme) -> Any:
    """Builds the Events panel for the selected control (or the form): each event with its handler and buttons
    to edit or disconnect it."""
    doc = d.doc
    target = None if len(doc.selection) != 1 else doc.selection[0]
    if len(doc.selection) > 1:
        return ui.empty_state("Select one control", "Events belong to a single control or to the form.",
                              icon="zap", theme=t)
    owner, wired = doc.owner(target)
    control = doc.form.get(target) if target else None
    spec = _components.get(control.type) if control is not None else None
    icon = spec.icon if spec is not None else "app-window"
    kind = tr(spec.label) if spec is not None else tr("Form")
    head = _core.container(_core.row([_icon(icon, size=16, color=t.accent),
                                      _core.column([ui.label(owner, weight="semibold", mono=True, theme=t),
                                                    ui.label(kind, size="xs", color="text_muted", theme=t)],
                                                   width="fill"),
                                      _help_button(d, control.name, t) if control is not None else None],
                                     spacing=10, align="center"),
                           padding=spacing.HEADER_PADDING, width="fill")
    rows: List[Any] = []
    for event in doc.events_of(target):
        handler = wired.get(event)
        doc_text = _help.event_doc(event, owner, control.type if control is not None else None).replace("``", "")
        name = ui.label(handler or "—", size="sm", mono=True, color="text_accent" if handler else "text_muted",
                        wrap=False, theme=t)
        actions = _core.row([
            ui.icon_button("code", lambda e=event: d.edit_event(target, e), size="xs",
                           tooltip=tr("Edit code") if handler else tr("Create handler"), theme=t),
            ui.icon_button("unlink", lambda e=event: d.unwire(target, e), size="xs", tooltip=tr("Disconnect"),
                           theme=t) if handler else None,
        ], spacing=2)
        rows.append(ui.tooltip(_core.mouse_area(
            _core.container(_core.row([
                _core.container(ui.label(event, size="sm", color="text_muted", wrap=False, theme=t), width=LABEL_WIDTH,
                                clip=True),
                _core.container(name, width="fill", clip=True),
                actions,
            ], spacing=spacing.LABEL_GAP, align="center"), padding=(spacing.ROW_PAD, 0), width="fill",
                height=ROW_HEIGHT + 2 * spacing.ROW_PAD, align_y="center",
                radius=t.radius_sm, bg=alpha(t.accent, 0.08) if d.editing and d.editing[0] == handler else None),
            on_double_click=lambda e=event: d.edit_event(target, e)), doc_text, position="left", theme=t))
    rows.append(_core.container(ui.label(tr("Double-click an event, or a control on the form, to write its code."),
                                         size="xs", color="text_muted", theme=t), padding=(6, 0)))
    body = ui.accordion([("Events", tr("Events"), _core.column(rows, width="fill", spacing=spacing.ROW_GAP))],
                        open={"Events"}, icons={"Events": "zap"}, padding=spacing.GROUP_PADDING, theme=t)
    # the same insets as the property grid, so both docks line up
    return scroll_panel(_core.column([head, _core.container(body, padding=(0, 0, 16, 0), width="fill")],
                                     width="fill"))


# -- style -----------------------------------------------------------------------


def _choice_editor(options: Any, value: str, on_change: Callable[[str], Any], t: Theme) -> Any:
    """A drop-down of ``options`` (values) shown translated; ``""`` reads "Default"."""
    labels = {(tr(o.capitalize()) if o else tr("Default")): o for o in options}
    current = next((label for label, o in labels.items() if o == value), tr("Default"))
    return ui.select(list(labels), current, lambda label: on_change(labels.get(label, "")), width="fill", size="sm",
                     theme=t)


#: Icons of the alignment choices, by field: start, center, end.
ALIGN_ICONS = {
    "align_x": ("align-start-vertical", "align-center-vertical", "align-end-vertical"),
    "align_y": ("align-start-horizontal", "align-center-horizontal", "align-end-horizontal"),
}


def _style_choice_editor(field: Any, value: str, on_change: Callable[[str], Any], t: Theme) -> Any:
    """On/off/default and alignments side by side; longer lists of choices as a drop-down."""
    icons = ALIGN_ICONS.get(field.key)
    if icons:
        choices = [("", prop_editors.choice_label(""), None)]
        choices += [(c, prop_editors.choice_label(c), i) for c, i in zip(field.choices[1:], icons)]
        return prop_editors.segmented(choices, value, on_change, t)
    if prop_editors.fits_segmented(field.choices):
        return prop_editors.segmented([(c, prop_editors.choice_label(c), None) for c in field.choices], value,
                                      on_change, t)
    return _choice_editor(field.choices, value, on_change, t)


#: Size of the floating color picker card (for placing it inside the window).
PICKER_WIDTH = 290.0
PICKER_HEIGHT = 520.0


PROP_PICKER = "prop:"  # the key prefix of a color picker opened from a property (not a Style row)


def prop_color_editor(d: "Designer", value: Any, on_change: Callable[[Any], Any], key: str, t: Theme) -> Any:
    """A color property: its swatch (click it for the color picker) and the token or ``#hex`` as text.

    Text that is not a color yet (``#`` while typing) leaves the swatch empty."""
    from .runtime import theme_for
    from .styling import _using

    picker = PROP_PICKER + key
    d.picker_targets[picker] = (value, on_change)
    ft = theme_for(d.doc.form)
    with _using(ft):
        box = ui.color_swatch(valid_color(value, ft) or "transparent", size=18,
                              on_press=lambda: d.toggle_color_picker(None, picker))
    return _core.row([box, ui.input(str(value or ""), on_change, placeholder=tr("token or #hex"), size="sm",
                                    mono=True, theme=t)], spacing=6, align="center")


def color_popover(d: "Designer", t: Theme) -> Any:
    """The color picker of the Style row or color property that is open, as a floating card (like the context
    menu)."""
    from .runtime import theme_for
    from .styling import picked, shadow_parts, shadow_value, unpicked

    assert d.color_picker is not None
    name, key = d.color_picker
    form = d.doc.form
    if key.startswith(PROP_PICKER):
        target_prop = d.picker_targets.get(key)
        if target_prop is None:
            return None
        current, change = target_prop
        ft = theme_for(form)
        return ui.ColorPicker(value=unpicked(valid_color(current, ft), ft, ft.accent), gradients=False, masks=False,
                              on_change=lambda e: change(picked(e.value) or ""), key=f"picker:{key}")
    target = form if name is None else form.get(name)
    if target is None:
        return None
    style = target.style
    if key == "background":
        value: Any = style.get("background")

        def pick(v: Any) -> None:
            d.set_style_value(name, "background", picked(v))
    elif key == "shadow":
        color, x, y, blur = shadow_parts(style.get("shadow"))
        value = color

        def pick(v: Any) -> None:
            d.set_style_value(name, "shadow", shadow_value(picked(v) or "", x, y, blur))
    elif key in ("glow", "bloom", "glass"):
        from . import motion

        if key == "glass":
            _on, value, strength = motion.glass_parts(style.get("glass"))

            def pick(v: Any) -> None:
                d.set_style_value(name, "glass", motion.glass_value(True, picked(v) or "", strength))
        else:
            value, size = motion.glow_parts(style.get(key), 12.0 if key == "glow" else 0.6)

            def pick(v: Any) -> None:
                d.set_style_value(name, key, motion.glow_value(picked(v) or "", size))
    else:
        value = style.get(key)

        def pick(v: Any) -> None:
            d.set_style(name, key, picked(v))
    fill = key == "background"
    ft = theme_for(form)
    # the picker is already a card: it floats as it is, and a click outside closes it
    return ui.ColorPicker(value=unpicked(value, ft, ft.accent), gradients=fill, masks=fill,
                          on_change=lambda e: pick(e.value), key=f"picker:{name}:{key}")


def _swatch(d: "Designer", name: Optional[str], key: str, value: Any) -> Any:
    from .runtime import theme_for
    from .styling import _using, clean

    ft = theme_for(d.doc.form)
    shown = clean({"background": value}, ft) if value else None
    with _using(ft):
        return ui.color_swatch(shown.get("background") if shown else "transparent", size=18,
                               on_press=lambda: d.toggle_color_picker(name, key))


def _color_editor(d: "Designer", name: Optional[str], key: str, value: Any, on_change: Callable[[str], Any],
                  t: Theme, placeholder: str = "token or #rrggbbaa") -> Any:
    return _core.row([_swatch(d, name, key, value),
                      ui.input(str(value or ""), on_change, placeholder=tr(placeholder), size="sm", mono=True, theme=t)],
                     spacing=6, align="center")


def _color_rows(d: "Designer", name: Optional[str], key: str, title: str, value: Any, on_change: Callable[[Any], Any],
                t: Theme, *, tip: Optional[str] = None, placeholder: str = "token or #rrggbbaa") -> List[Any]:
    return [prop_row(title, _color_editor(d, name, key, value, on_change, t, placeholder), t, tip=tip)]


def _background_rows(d: "Designer", name: Optional[str], value: Any, t: Theme) -> List[Any]:
    from .styling import describe, picked

    def pick(v: Any) -> None:
        d.set_style_value(name, "background", picked(v))

    summary = _core.row([
        _swatch(d, name, "background", value),
        _core.button(ui.label(tr(describe(value)), size="sm", color="text" if value else "text_muted", theme=t),
                     lambda: d.toggle_color_picker(name, "background"), bg="transparent", hover_bg=t.element_hover,
                     padding=(2, 6), width="fill"),
        ui.icon_button("x", lambda: d.set_style_value(name, "background", None), size="xs", tooltip="No background",
                       theme=t) if value else _core.space(width=0),
    ], spacing=6, align="center")
    return [prop_row("Background", summary, t, tip="A color, a gradient or a masked fill: click to pick")]


def style_rows(d: "Designer", name: Optional[str], style: dict, t: Theme, *, fields: Any = None) -> List[Any]:
    """The Style section: background, text, border, corners, shadow, spacing and alignment.

    ``name`` is the control being edited, or ``None`` for the form's global style.
    """
    from . import styling

    fields = styling.FIELDS if fields is None else fields
    rows: List[Any] = [Group("Style")]
    rows.extend(_background_rows(d, name, style.get("background"), t))
    for field in fields:
        value = style.get(field.key)

        def on_change(v: Any, key: str = field.key) -> None:
            d.set_style(name, key, v)

        if field.kind == "color":
            rows.extend(_color_rows(d, name, field.key, field.title, value, on_change, t, tip=field.tip))
            continue
        if field.kind == "number":
            number = float(value) if isinstance(value, (int, float)) else 0.0
            editor = ui.number_field(number, on_change, min=field.min, max=field.max, step=field.step, width="fill",
                                     theme=t)
        elif field.kind == "choice":
            editor = _style_choice_editor(field, styling.choice_of(field.key, value), on_change, t)
        elif field.kind in ("box", "radius"):
            box_key = f"{name}:{field.key}"
            editor = prop_editors.box_editor(d, box_key, value, on_change, t, corners=field.kind == "radius")
            if prop_editors.is_split(d, box_key, value):
                rows.append(prop_row(field.title, editor, t, tip=field.tip, lines=2))
                continue
        elif field.kind == "shadow":
            color, x, y, blur = styling.shadow_parts(value)

            def shadow(part: int, v: Any, parts: tuple = (color, x, y, blur)) -> None:
                values = list(parts)
                values[part] = v
                d.set_style_value(name, "shadow", styling.shadow_value(*values))

            rows.extend(_color_rows(d, name, "shadow", field.title, color, lambda v: shadow(0, v), t, tip=field.tip,
                                    placeholder="none"))
            if color:
                rows.append(prop_row("Offset", _core.row([
                    ui.number_field(x, lambda v: shadow(1, v), min=-64, max=64, width="fill", theme=t),
                    ui.number_field(y, lambda v: shadow(2, v), min=-64, max=64, width="fill", theme=t),
                ], spacing=6), t, tip="Horizontal and vertical offset"))
                rows.append(prop_row("Blur", ui.number_field(blur, lambda v: shadow(3, v), min=0, max=96, width="fill",
                                                             theme=t), t))
            continue
        else:
            editor = ui.input("" if value is None else str(value), on_change, size="sm", theme=t)
        rows.append(prop_row(field.title, editor, t, tip=field.tip))
    if style:
        rows.append(_core.container(ui.button(tr("Reset style"), lambda: d.clear_style(name), icon="rotate-ccw",
                                              variant="ghost", size="sm", theme=t), padding=(4, 0)))
    return rows
