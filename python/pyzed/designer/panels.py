"""The designer's docks: toolbox, outline, property grid, events list and event code editor.

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

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

LABEL_WIDTH = 92.0
ROW_HEIGHT = 28.0
ACCENTS = ("#74ade8", "#b477cf", "#a1c181", "#e5c07b", "#d07277", "#6eb4bf", "#ff8a65")


# -- small building blocks -------------------------------------------------------


def section(title: str, t: Theme, end: Any = None) -> Any:
    return _core.container(
        _core.row([ui.label(title.upper(), size="xs", weight="semibold", color="text_muted", theme=t),
                   _core.space(width="fill"), end], align="center"),
        padding=(10, 12, 4, 12), width="fill")


def prop_row(title: str, editor: Any, t: Theme, *, tip: Optional[str] = None) -> Any:
    label = ui.label(title, size="sm", color="text_muted", wrap=False, theme=t)
    if tip:
        label = ui.tooltip(label, tip, theme=t)
    return _core.container(
        _core.row([_core.container(label, width=LABEL_WIDTH, clip=True), _core.container(editor, width="fill")],
                  spacing=8, align="center"),
        padding=(3, 12), width="fill")


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
        return ui.number_field(number, on_change, min=prop.min, max=prop.max, step=prop.step, width=150, theme=t)
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
        ui.list_item("Pointer", d.pick_tool(None), icon="mouse-pointer-2", selected=d.tool is None, height=26,
                     theme=t),
    ]
    for category, items in _components.categories().items():
        shown = [c for c in items if not query or query in c.label.lower() or query in c.type]
        if not shown:
            continue
        rows.append(section(category, t))
        for spec in shown:
            rows.append(ui.tooltip(
                ui.list_item(spec.label, d.pick_tool(spec.type), icon=spec.icon, selected=d.tool == spec.type,
                             height=26, theme=t),
                spec.description or spec.label, position="right", theme=t))
    return _core.column([
        _core.container(ui.search_input(d.toolbox_query, d.set_toolbox_query, placeholder="Search components…",
                                        size="sm", theme=t), padding=8),
        _core.scrollable(_core.column(rows, width="fill", padding=(0, 0, 8, 0)), height="fill"),
    ], width="fill", height="fill")


def outline(d: "Designer", t: Theme) -> Any:
    doc = d.doc
    rows: List[Any] = [ui.list_item(doc.form.name, d.select_form, icon="app-window", selected=not doc.selection,
                                    height=24, theme=t)]
    for c in reversed(doc.form.controls):
        spec = _components.get(c.type)
        end = _core.row([
            ui.icon_button("eye" if c.visible else "eye-off", lambda n=c.name, v=c.visible: d.set_field(n, "visible",
                                                                                                       not v),
                           size="xs", tooltip="Visible", theme=t),
            ui.icon_button("lock" if c.locked else "lock-open", lambda n=c.name, v=c.locked: d.set_field(n, "locked",
                                                                                                        not v),
                           size="xs", selected=c.locked, tooltip="Lock", theme=t),
        ], spacing=0)
        rows.append(ui.list_item(c.name, lambda n=c.name: d.select_from_outline(n), icon=spec.icon,
                                 selected=doc.is_selected(c.name), indent=14, height=24, end=end,
                                 color=None if c.visible else "text_muted", theme=t))
    return _core.scrollable(_core.column(rows, width="fill"), height="fill")


def left_dock(d: "Designer", t: Theme) -> Any:
    top = _core.column([ui.panel_header("Toolbox", icon="component", theme=t), toolbox(d, t)],
                       width="fill", height="fill")
    bottom = _core.column([ui.panel_header("Outline", icon="layers", theme=t), outline(d, t)],
                          width="fill", height="fill")
    return ui.split(top, bottom, vertical=True, ratio=d.left_ratio, on_resize=d.resize_left, min_size=120, theme=t)


# -- properties ------------------------------------------------------------------


def _anchor_editor(d: "Designer", name: str, anchor, t: Theme) -> Any:
    edges = (("left", "arrow-left-to-line"), ("top", "arrow-up-to-line"), ("right", "arrow-right-to-line"),
             ("bottom", "arrow-down-to-line"))
    return _core.row([ui.icon_button(icon, lambda e=edge: d.toggle_anchor(name, e), size="sm",
                                     selected=edge in anchor, tooltip=f"Anchor {edge}", theme=t)
                      for edge, icon in edges], spacing=2)


def _layout_rows(d: "Designer", c, t: Theme) -> List[Any]:
    def num(field: str):
        return ui.number_field(round(getattr(c, field)), lambda v, f=field: d.set_field(c.name, f, v), step=1,
                               width=150, theme=t)

    return [
        section("Layout", t),
        prop_row("X", num("x"), t),
        prop_row("Y", num("y"), t),
        prop_row("Width", num("width"), t),
        prop_row("Height", num("height"), t),
        prop_row("Anchor", _anchor_editor(d, c.name, c.anchor, t), t,
                 tip="Edges that follow the window when it is resized"),
        section("Behavior", t),
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
                                   _core.column([ui.label(spec.label, weight="semibold", theme=t),
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
        rows.append(section(group, t))
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
        rows.append(section(title, t))
        rows.append(_core.container(_core.row([ui.icon_button(icon, lambda e=edge: d.align(e), tooltip=tip, theme=t)
                                               for icon, edge, tip in items], spacing=2), padding=(0, 12)))
    rows.append(section("Spacing and size", t))
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
        section("Window", t),
        prop_row("Name", ui.input(form.name, setter("name"), size="sm", mono=True, theme=t), t),
        prop_row("Title", ui.input(form.title, setter("title"), size="sm", theme=t), t),
        prop_row("Width", ui.number_field(form.width, setter("width", float), min=120, step=8, width=150, theme=t), t),
        prop_row("Height", ui.number_field(form.height, setter("height", float), min=80, step=8, width=150, theme=t),
                 t),
        prop_row("Resizable", _core.container(ui.switch(form.resizable, setter("resizable"), theme=t), width="fill",
                                              align_x="end"), t),
        section("Look", t),
        prop_row("Theme", ui.select(themes.names(), form.theme, setter("theme"), width="fill", size="sm", theme=t), t),
        prop_row("Accent", accent_row, t),
        prop_row("Custom accent", ui.input(form.accent or "", setter("accent", lambda v: v or None),
                                           placeholder="#rrggbb", size="sm", mono=True, theme=t), t),
        prop_row("Background", ui.input(form.background or "", setter("background", lambda v: v or None),
                                        placeholder="theme default", size="sm", mono=True, theme=t), t),
        prop_row("Corner radius", ui.number_field(form.radius if form.radius is not None else 6,
                                                  setter("radius", float), min=0, max=24, width=150, theme=t), t),
        prop_row("Font size", ui.number_field(form.font_size, setter("font_size", float), min=8, max=32, width=150,
                                              theme=t), t),
        section("Designer", t),
        prop_row("Grid size", ui.number_field(form.grid, setter("grid", int), min=2, max=64, width=150, theme=t), t),
    ]


def properties(d: "Designer", t: Theme) -> Any:
    if len(d.doc.selection) > 1:
        rows = multi_properties(d, t)
    elif d.doc.primary is not None:
        rows = control_properties(d, t)
    else:
        rows = form_properties(d, t)
    return _core.scrollable(_core.column(rows, width="fill", padding=(0, 0, 16, 0)), height="fill")


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


def right_dock(d: "Designer", t: Theme) -> Any:
    tabs = [ui.Tab("properties", "Properties", icon="settings-2"), ui.Tab("events", "Events", icon="zap")]
    body = properties(d, t) if d.right_tab == "properties" else events(d, t)
    return _core.column([ui.tab_bar(tabs, d.right_tab, on_select=d.set_right_tab, theme=t), body],
                        width="fill", height="fill")


# -- code ------------------------------------------------------------------------


def code_panel(d: "Designer", t: Theme) -> Any:
    assert d.editing is not None
    handler, text = d.editing
    whole = handler == "*"
    path = d.doc.code_path.name if d.doc.code_path else f"{d.doc.form.name}.py"
    title = path if whole else f"{path} › {handler}()"
    header = ui.panel_header(title, icon="code", actions=[
        ui.button("Whole file" if not whole else "This handler", d.toggle_whole_file, variant="ghost", size="sm",
                  theme=t),
        ui.button("Apply", d.apply_code, icon="check", variant="tinted", size="sm", theme=t),
        ui.icon_button("x", d.close_code, size="sm", tooltip="Close", theme=t),
    ], theme=t)
    error = None
    if d.code_error:
        error = _core.container(ui.label(d.code_error, size="sm", color="error", mono=True, theme=t),
                                padding=(4, 12), width="fill", bg=alpha(t.error, 0.1))
    editor = ui.editor(f"code:{handler}:{d.code_revision}", text, language="py", on_change=d.set_code_buffer,
                       theme=t)
    return _core.column([header, error, editor], width="fill", height="fill")
