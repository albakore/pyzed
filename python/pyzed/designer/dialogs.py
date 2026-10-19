"""The designer's dialogs: settings, new form, add control, command palette, keyboard shortcuts and about.

Each function is a view of a ``Designer`` returning the overlay shown by ``ui.layer``;
behavior stays in ``Designer``. The generic parts (``ui.shortcuts``, ``ui.about``,
``ui.picker``...) live in the ``ui`` library so any app can use them.
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

from .. import _core, ui
from ..theme import Theme, themes
from . import commands as _commands
from . import components as _components
from . import new as _new
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

PICKER_ID = "designer-picker"

#: Interface languages offered in the settings ("" follows the system).
LANGUAGES = (("", "System default"), ("en", "English"), ("es", "Español"))
#: Names shown in their own language, except the first one.


def _footer_done(d: "Designer", t: Theme) -> List[Any]:
    return [_core.space(width="fill"), ui.button(tr("Done"), d.close_dialog, variant="solid", theme=t)]


def settings(d: "Designer", t: Theme) -> Any:
    """General settings: appearance and language, canvas defaults, running, and a link to the editor settings."""
    p = d.prefs

    def switch(key: str) -> Any:
        return ui.switch(bool(getattr(p, key)), lambda v, k=key: d.set_pref(k, v), theme=t)

    names = {code: tr(name) if not code else name for code, name in LANGUAGES}
    language_names = list(names.values())
    current = names.get(p.language, language_names[0])
    general = ui.settings_group(tr("Appearance"), [
        ui.field(tr("Theme"), ui.select(themes.names(), t.name, d.set_designer_theme, width=200, theme=t), theme=t),
        ui.field(tr("Language"), ui.select(language_names, current,
                                       lambda name: d.set_language(next(c for c, n in names.items() if n == name)),
                                       width=200, theme=t),
                 description=tr("Language of the designer's menus and panels"), theme=t),
        ui.field(tr("Toolbar"), switch("show_toolbar"), theme=t),
        ui.field(tr("Status bar"), switch("show_status_bar"), theme=t),
    ], theme=t)
    canvas = ui.settings_group(tr("Form canvas"), [
        ui.field(tr("Show grid"), switch("show_grid"), theme=t),
        ui.field(tr("Snap to grid"), switch("snap"), theme=t),
        ui.field(tr("Smart guides"), switch("smart_guides"), description=tr("Align to other controls while dragging"),
                 theme=t),
        ui.field(tr("Show hidden controls"), switch("show_hidden"), theme=t),
        ui.field(tr("Grid size for new forms"), ui.number_field(float(p.grid), lambda v: d.set_pref("grid", int(v)), min=2,
                                                            max=64, step=1, width=110, theme=t), theme=t),
    ], theme=t)
    running = ui.settings_group(tr("Running"), [
        ui.field(tr("Save before running"), switch("save_on_run"), theme=t),
        ui.field(tr("Open the console on Run"), switch("console_on_run"), theme=t),
        ui.field(tr("Log events in the console"), switch("log_events"),
                 description=tr("Every event the running form handles, with its value"), theme=t),
    ], theme=t)
    panels = ui.settings_group(tr("Panels"), [
        ui.field(tr("Layout"), ui.button(tr("Reset"), d.reset_layout, icon="layout-dashboard", variant="ghost", size="sm",
                                     theme=t),
                 description=tr("Put every panel back in its default dock and size"), theme=t),
        ui.field(tr("Code editor"), ui.button(tr("Editor settings…"), d.open_editor_settings, icon="code", variant="ghost",
                                          size="sm", theme=t),
                 description=tr("Font, tabs, completion, language servers"), theme=t),
    ], theme=t)
    body = _core.scrollable(_core.column([general, canvas, running, panels], spacing=14, padding=(0, 6, 0, 0)),
                            height=560, scrollbar_width=4)
    return ui.modal(body, title=tr("Settings"), on_close=d.close_dialog, width=560, footer=_footer_done(d, t), theme=t)


def shortcuts(d: "Designer", t: Theme) -> Any:
    return ui.modal(ui.shortcuts(_commands.shortcut_groups(), query=d.picker_query, on_query=d.set_picker_query,
                                 theme=t),
                    title=tr("Keyboard shortcuts"), on_close=d.close_dialog, width=520, theme=t)


def about(d: "Designer", t: Theme) -> Any:
    from .. import __version__

    details = [(tr("Version"), __version__), ("Python", platform.python_version()),
               (tr("Platform"), f"{platform.system()} {platform.machine()}"), ("Iced", _core.ICED_VERSION)]
    blurb = tr("Build windows visually, wire their events to Python and run them.")
    return ui.modal(ui.about("Pyzed Designer", __version__, blurb, icon="layout-template", details=details,
                             links=[(tr("Documentation"), d.open_docs),
                                    (tr("Source code"), lambda: d.open_url("https://github.com/albakore/pyzed"))],
                             theme=t),
                    on_close=d.close_dialog, width=400, theme=t)


def new_form(d: "Designer", t: Theme) -> Any:
    """Name, title, template and folder of a new form."""
    s = d.new_state
    cards = []
    for template in _new.templates():
        selected = template.name == s["template"]
        cards.append(_core.button(
            _core.column([ui.label(tr(template.label), weight="semibold", size="sm", theme=t),
                          ui.label(tr(template.description), size="xs", color="text_muted", theme=t)],
                         spacing=2, width="fill"),
            lambda name=template.name: d.set_new("template", name),
            padding=(8, 10), width="fill", bg=t.element_selected if selected else t.surface,
            hover_bg=t.element_hover, border_color=t.border_selected if selected else t.border_variant,
            border_width=1, radius=t.radius))
    grid = _core.grid(cards, columns="1fr 1fr", spacing=8)
    folder = Path(s["folder"] or ".")
    path = folder / f"{s['name'] or 'form1'}.pzform"
    exists = path.exists()
    body = _core.column([
        ui.field(tr("Name"), ui.input(s["name"], lambda v: d.set_new("name", v), mono=True, width=240,
                                  on_submit=d.create_new_form, id="new-form-name", theme=t),
                 description=tr("File name and handler prefix"), theme=t),
        ui.field(tr("Title"), ui.input(s["title"], lambda v: d.set_new("title", v), placeholder=tr("Same as the name"),
                                   width=240, theme=t), theme=t),
        ui.field(tr("Folder"), ui.input(s["folder"], lambda v: d.set_new("folder", v), mono=True, width=240, theme=t),
                 description=tr("Creates {path}", path=path), theme=t),
        ui.label(tr("Template"), size="sm", weight="medium", theme=t),
        grid,
        ui.callout(tr("{name} already exists", name=path.name), tr("Pick another name or folder."), tint="warning", theme=t)
        if exists else None,
    ], spacing=10)
    from .app import NEW_DOCUMENT_KINDS

    others = [ui.button(tr("New {kind}", kind=tr(label).lower()), lambda f=factory: d._new(f), icon=icon, variant="ghost", theme=t)
              for label, icon, _suffix, factory in NEW_DOCUMENT_KINDS if label != "Form"]
    return ui.modal(body, title=tr("New form"), on_close=d.close_dialog, width=560, theme=t, footer=[
        *others,
        ui.button(tr("Unsaved form"), d.create_untitled_form, variant="ghost", theme=t),
        _core.space(width="fill"),
        ui.button(tr("Cancel"), d.close_dialog, variant="ghost", theme=t),
        ui.button(tr("Create"), d.create_new_form, variant="solid", disabled=exists, theme=t),
    ])


def add_control(d: "Designer", t: Theme) -> Any:
    """A searchable list of components to add (inside a container when one was picked)."""
    items = []
    for spec in _components.all_components():
        items.append(ui.PaletteItem(tr(spec.label), lambda type_=spec.type: d.add_child(type_), icon=spec.icon,
                                    detail=tr(spec.category)))
    matches = ui.fuzzy_filter(d.picker_query, items, key=lambda i: f"{i.label} {i.detail}")
    where = tr("Add to {name}", name=d.add_parent) if d.add_parent else tr("Add a control to the form")
    index = min(d.picker_index, max(len(matches) - 1, 0))
    chosen = matches[index][0].on_press if matches else None
    return ui.picker(d.picker_query, d.set_picker_query, matches, selected=index, placeholder=f"{where}…",
                     input_id=PICKER_ID, on_submit=chosen, theme=t)


def palette(d: "Designer", t: Theme) -> Any:
    items = []
    for action in _commands.ACTIONS:
        if not action.enabled(d):
            continue
        label = f"{tr(action.group)}: {action.label.rstrip('…')}"
        items.append(ui.PaletteItem(label, lambda a=action: d.run_action(a.id), keys=action.keys, icon=action.icon))
    matches = ui.fuzzy_filter(d.picker_query, items, key=lambda i: i.label)
    index = min(d.picker_index, max(len(matches) - 1, 0))
    chosen = matches[index][0].on_press if matches else None
    return ui.picker(d.picker_query, d.set_picker_query, matches, selected=index,
                     placeholder=tr("Run a command…"), input_id=PICKER_ID, on_submit=chosen, theme=t)
