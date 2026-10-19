"""The designer's docks: toolbox, outline, property grid and events list (the code editor is in ``code_panel``).

Each function is a view of a ``Designer``: it reads its state and wires widget callbacks
to its methods, so all behavior stays in ``Designer``/``Document``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, List, Optional

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha, themes
from . import components as _components
from .components import Prop
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

LABEL_WIDTH = 92.0
ROW_HEIGHT = 28.0
#: Icons of the property groups in the accordion.
SECTION_ICONS = {"Appearance": "palette", "Data": "database", "Behavior": "mouse-pointer-click",
                 "Layout": "layout-dashboard", "Window": "app-window", "Look": "paintbrush", "Designer": "grid-3x3",
                 "Align": "align-start-vertical", "Spacing and size": "ruler", "Position": "move"}
ACCENTS = ("#74ade8", "#b477cf", "#a1c181", "#e5c07b", "#d07277", "#6eb4bf", "#ff8a65")


# -- small building blocks -------------------------------------------------------


def section(title: str, t: Theme, end: Any = None) -> Any:
    return _core.container(
        _core.row([ui.label(title.upper(), size="xs", weight="semibold", color="text_muted", theme=t),
                   _core.space(width="fill"), end], align="center"),
        padding=(10, 12, 4, 12), width="fill")


class Group:
    """Starts a collapsible section of the property grid (see ``properties``)."""

    def __init__(self, title: str) -> None:
        self.title = title


def prop_row(title: str, editor: Any, t: Theme, *, tip: Optional[str] = None) -> Any:
    label = ui.label(tr(title), size="sm", color="text_muted", wrap=False, theme=t)
    if tip:
        label = ui.tooltip(label, tip, theme=t)
    return _core.container(
        _core.row([_core.container(label, width=LABEL_WIDTH, clip=True),
                   _core.container(editor, width="fill", height=ROW_HEIGHT, align_y="center")],
                  spacing=10, align="center"),
        padding=(3, 10), width="fill")


def swatch(color: Optional[str], t: Theme, on_press: Any = None, *, selected: bool = False) -> Any:
    box = _core.container(width=16, height=16, bg=color or "transparent", radius=4,
                          border_color=t.text if selected else t.border, border_width=2 if selected else 1)
    if on_press is None:
        return box
    return _core.button(box, on_press, padding=0, bg="transparent", hover_bg="transparent")


def editor_for(d: "Designer", prop: Prop, value: Any, on_change: Callable[[Any], Any], key: str, t: Theme) -> Any:
    """The property-grid editor for one property, picked by ``prop.kind``."""
    kind = prop.kind
    if kind == "bool":
        return _core.container(ui.switch(bool(value), on_change, theme=t), width="fill", align_x="end")
    if kind == "number":
        number = 0.0 if value in (None, "") else float(value)
        return ui.number_field(number, on_change, min=prop.min, max=prop.max, step=prop.step, width="fill", theme=t)
    if kind == "choice":
        return ui.select(list(prop.choices), str(value), on_change, width="fill", size="sm", theme=t)
    if kind in ("multiline", "list"):
        text = value if isinstance(value, str) else "\n".join(map(str, value or []))
        return _core.container(
            ui.editor(f"prop:{key}:{d.doc.revision}", text, on_change=on_change, gutter=False, wrap=True,
                      active_line=False, font_size=12.5, height=88, theme=t),
            width="fill", height=88, border_color=t.border_variant, border_width=1, radius=t.radius_sm, clip=True)
    if kind == "color":
        resolved = None
        if value:
            try:
                resolved = t.color(str(value))
            except (KeyError, ValueError):
                resolved = None
        return _core.row([swatch(resolved, t), ui.input(str(value or ""), on_change, placeholder="token or #hex",
                                                        size="sm", mono=True, theme=t)], spacing=6, align="center")
    if kind == "icon":
        preview = _icon(str(value), size=14) if value else _icon("circle-dashed", size=14, color=t.icon_muted)
        return _core.row([preview, ui.input(str(value or ""), on_change, placeholder="lucide name", size="sm",
                                            theme=t)], spacing=6, align="center")
    return ui.input("" if value is None else str(value), on_change, size="sm", theme=t)


# -- toolbox ---------------------------------------------------------------------


def toolbox(d: "Designer", t: Theme) -> Any:
    query = d.toolbox_query.strip().lower()
    rows: List[Any] = [
        ui.list_item(tr("Pointer"), d.pick_tool(None), icon="mouse-pointer-2", selected=d.tool is None, height=26,
                     theme=t),
    ]
    for category, items in _components.categories().items():
        shown = [c for c in items if not query or query in c.label.lower() or query in tr(c.label).lower()
                 or query in c.type]
        if not shown:
            continue
        rows.append(section(tr(category), t))
        for spec in shown:
            rows.append(ui.tooltip(
                ui.list_item(tr(spec.label), d.pick_tool(spec.type), icon=spec.icon, selected=d.tool == spec.type,
                             height=26, theme=t),
                spec.description or tr(spec.label), position="right", theme=t))
    return _core.column([
        _core.container(ui.search_input(d.toolbox_query, d.set_toolbox_query, placeholder=tr("Search components…"),
                                        size="sm", theme=t), padding=8),
        _core.scrollable(_core.column(rows, width="fill", padding=(0, 0, 8, 0)), height="fill"),
    ], width="fill", height="fill")


def outline(d: "Designer", t: Theme) -> Any:
    """The form's controls as a tree: containers can be folded and get a "+" to add controls inside them."""
    doc = d.doc
    form = doc.form
    rows: List[Any] = [ui.list_item(form.name, d.select_form, icon="app-window", selected=not doc.selection,
                                    height=24, end=ui.icon_button("plus", lambda: d.open_add_child(None), size="xs",
                                                                  tooltip="Add a control", theme=t),
                                    theme=t)]

    def add(parent: Optional[str], depth: int) -> None:
        children = form.children(parent)
        holder = form.get(parent) if parent else None
        # top-most first, like layers in a drawing app; flex rows and grids list them in reading order
        flowing = holder is not None and _components.get(holder.type).container in ("flex", "grid")
        for c in (children if flowing else reversed(children)):
            spec = _components.get(c.type)
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
            if container:
                chevron = ui.icon_button("chevron-right" if folded else "chevron-down",
                                         lambda n=c.name: d.toggle_folded(n), size="xs", theme=t)
            else:
                chevron = _core.space(width=20)
            rows.append(ui.list_item(c.name, lambda n=c.name: d.select_from_outline(n), icon=spec.icon,
                                     selected=doc.is_selected(c.name), indent=4 + depth * 14, start=chevron,
                                     height=24, end=_core.row(buttons, spacing=0),
                                     on_right_press=lambda n=c.name: d.open_outline_menu(n),
                                     color=None if c.visible else "text_muted", theme=t))
            if container and not folded:
                add(c.name, depth + 1)

    add(None, 0)
    return _core.scrollable(_core.column(rows, width="fill"), height="fill")


# -- properties ------------------------------------------------------------------


def _anchor_editor(d: "Designer", name: str, anchor, t: Theme) -> Any:
    edges = (("left", "arrow-left-to-line"), ("top", "arrow-up-to-line"), ("right", "arrow-right-to-line"),
             ("bottom", "arrow-down-to-line"))
    return _core.row([ui.icon_button(icon, lambda e=edge: d.toggle_anchor(name, e), size="sm",
                                     selected=edge in anchor, tooltip=f"Anchor {edge}", theme=t)
                      for edge, icon in edges], spacing=2)


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
                                          color="text_muted", theme=t), padding=(2, 12))]
    else:
        rows += [
            prop_row("X", num("x"), t),
            prop_row("Y", num("y"), t),
            prop_row("Width", num("width"), t),
            prop_row("Height", num("height"), t),
            prop_row(tr("Anchor"), _anchor_editor(d, c.name, c.anchor, t), t,
                     tip="Edges that follow the window (or the container) when it is resized"),
        ]
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


def control_properties(d: "Designer", t: Theme) -> List[Any]:
    c = d.doc.primary
    assert c is not None
    spec = _components.get(c.type)
    rows: List[Any] = [
        _core.container(_core.row([_icon(spec.icon, size=16, color=t.accent),
                                   _core.column([ui.label(tr(spec.label), weight="semibold", theme=t),
                                                 ui.label(spec.description, size="xs", color="text_muted", theme=t)],
                                                width="fill")],
                                  spacing=10, align="center"), padding=(10, 12), width="fill"),
        prop_row("Name", ui.input(d.name_buffer, d.set_name_buffer, on_submit=d.commit_name, size="sm", mono=True,
                                  theme=t), t, tip="Press Enter to rename (handlers are renamed too)"),
    ]
    groups: dict = {}
    for prop in spec.props:
        groups.setdefault(prop.group, []).append(prop)
    for group, props in groups.items():
        rows.append(Group(group))
        for prop in props:
            value = c.props.get(prop.name, prop.default)
            rows.append(prop_row(prop.title, editor_for(d, prop, value, d.prop_setter(c.name, prop), f"{c.name}.{prop.name}",
                                                        t), t))
    rows.extend(_layout_rows(d, c, t))
    return rows


def multi_properties(d: "Designer", t: Theme) -> List[Any]:
    count = len(d.doc.selection)
    tools = [
        ("Align", [("align-start-vertical", "left", "Left edges"), ("align-center-vertical", "center", "Centers"),
                   ("align-end-vertical", "right", "Right edges"), ("align-start-horizontal", "top", "Top edges"),
                   ("align-center-horizontal", "middle", "Middles"), ("align-end-horizontal", "bottom",
                                                                      "Bottom edges")]),
    ]
    rows: List[Any] = [_core.container(ui.label(f"{count} controls selected", weight="semibold", theme=t),
                                       padding=(10, 12))]
    for title, items in tools:
        rows.append(Group(title))
        rows.append(_core.container(_core.row([ui.icon_button(icon, lambda e=edge: d.align(e), tooltip=tip, theme=t)
                                               for icon, edge, tip in items], spacing=2), padding=(0, 12)))
    rows.append(Group("Spacing and size"))
    rows.append(_core.container(_core.row([
        ui.icon_button("align-horizontal-distribute-center", lambda: d.distribute("horizontal"),
                       tooltip="Distribute horizontally", theme=t),
        ui.icon_button("align-vertical-distribute-center", lambda: d.distribute("vertical"),
                       tooltip="Distribute vertically", theme=t),
        ui.icon_button("stretch-horizontal", lambda: d.same_size("width"), tooltip="Same width", theme=t),
        ui.icon_button("stretch-vertical", lambda: d.same_size("height"), tooltip="Same height", theme=t),
    ], spacing=2), padding=(0, 12)))
    return rows


def form_properties(d: "Designer", t: Theme) -> List[Any]:
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
                        padding=(10, 12)),
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
                                        placeholder="theme default", size="sm", mono=True, theme=t), t),
        prop_row("Corner radius", ui.number_field(form.radius if form.radius is not None else 6,
                                                  setter("radius", float), min=0, max=24, width="fill", theme=t), t),
        prop_row("Font size", ui.number_field(form.font_size, setter("font_size", float), min=8, max=32, width="fill",
                                              theme=t), t),
        Group("Designer"),
        prop_row("Grid size", ui.number_field(form.grid, setter("grid", int), min=2, max=64, width="fill", theme=t), t),
    ]


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
    sections = [(title, tr(title), _core.column(items, width="fill", spacing=2)) for title, items in groups]
    body = ui.accordion(sections, open={title for title, _ in groups} - d.collapsed_sections,
                        on_toggle=d.toggle_section, icons=SECTION_ICONS, theme=t)
    top = _core.container(_core.column(head, width="fill", spacing=2), padding=(0, 11, 6, 11), width="fill")
    return _core.scrollable(_core.column([top, _core.container(body, padding=(0, 10, 16, 10), width="fill")],
                                         width="fill"), height="fill")


# -- events ----------------------------------------------------------------------


def events(d: "Designer", t: Theme) -> Any:
    doc = d.doc
    target = None if len(doc.selection) != 1 else doc.selection[0]
    if len(doc.selection) > 1:
        return ui.empty_state("Select one control", "Events belong to a single control or to the form.",
                              icon="zap", theme=t)
    owner, wired = doc.owner(target)
    rows: List[Any] = [_core.container(ui.label(f"Events of {owner}", weight="semibold", theme=t), padding=(10, 12))]
    for event in doc.events_of(target):
        handler = wired.get(event)
        doc_text = _components.EVENT_DOCS.get(event, "").format(name=owner).replace("``", "")
        name = ui.label(handler or "—", size="sm", mono=True, color="text_accent" if handler else "text_muted",
                        wrap=False, theme=t)
        actions = _core.row([
            ui.icon_button("code", lambda e=event: d.edit_event(target, e), size="sm",
                           tooltip="Edit code" if handler else "Create handler", theme=t),
            ui.icon_button("unlink", lambda e=event: d.unwire(target, e), size="sm", tooltip="Disconnect",
                           theme=t) if handler else None,
        ], spacing=0)
        rows.append(ui.tooltip(_core.mouse_area(
            _core.container(_core.row([
                _core.container(ui.label(event, size="sm", theme=t), width=LABEL_WIDTH),
                _core.container(name, width="fill", clip=True),
                actions,
            ], spacing=8, align="center"), padding=(2, 12), width="fill", height=ROW_HEIGHT, align_y="center",
                bg=alpha(t.accent, 0.08) if d.editing and d.editing[0] == handler else None),
            on_double_click=lambda e=event: d.edit_event(target, e)), doc_text, position="left", theme=t))
    rows.append(_core.container(ui.label("Double-click an event, or a control on the form, to write its code.",
                                         size="xs", color="text_muted", theme=t), padding=(12, 12)))
    return _core.scrollable(_core.column(rows, width="fill"), height="fill")
