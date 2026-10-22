"""The designer's dialogs: settings, new form, add control, command palette, keyboard shortcuts and about.

Each function is a view of a ``Designer`` returning the overlay shown by ``ui.layer``;
behavior stays in ``Designer``. The generic parts (``ui.shortcuts``, ``ui.about``,
``ui.picker``...) live in the ``ui`` library so any app can use them.
"""

from __future__ import annotations

import functools
import platform
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme
from . import commands as _commands
from . import components as _components
from . import keymap as _keymap
from . import new as _new
from . import telemetry as _telemetry
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

PICKER_ID = "designer-picker"

#: Interface languages offered in the settings ("" follows the system).
LANGUAGES = (("", "System default"), ("en", "English"), ("es", "Español"))
#: Names shown in their own language, except the first one.


#: Interface sizes offered in the settings, as a scale (1.0 is 100%).
UI_SCALES = (0.75, 0.8, 0.85, 0.9, 1.0, 1.1, 1.2, 1.25, 1.3, 1.4, 1.5)


@functools.lru_cache(maxsize=1)
def font_families() -> Tuple[str, ...]:
    """The font families the interface and the code can use (bundled, loaded and the system's)."""
    return tuple(f for f in _core.font_families() if f not in ("lucide", "Iced-Icons"))


def font_select(value: str, default: str, on_change: Callable[[str], Any], t: Theme) -> Any:
    """A drop-down of the font families; the first entry is the default font, saved as ``""``."""
    first = tr("Default ({font})", font=default)
    names = [first, *(f for f in font_families() if f != default)]
    return ui.select(names, value or first, lambda name: on_change("" if name == first else name), width=200,
                     theme=t)


def _footer_done(d: "Designer", t: Theme) -> List[Any]:
    return [_core.space(width="fill"), ui.button(tr("Done"), d.close_dialog, variant="solid", theme=t)]


def settings(d: "Designer", t: Theme) -> Any:
    """The Settings dialog: every preference of the designer and the code editor, by page, with search, the user
    and project scopes and the profiles (see ``settings_ui``)."""
    from . import settings_ui

    return settings_ui.dialog(d, t)


def telemetry_group(d: "Designer", t: Theme) -> Any:
    """The telemetry settings: off by default; the data stays on this computer unless an endpoint is set."""
    tel = _telemetry.get()
    rows = [
        ui.field(tr("Collect usage and performance data"), ui.switch(tel.enabled, lambda v: tel.configure(enabled=v),
                                                                     theme=t),
                 description=tr("Counts of the commands and editor actions you use, and startup, render and "
                                "command times. Never your code, texts or file names."), theme=t),
    ]
    if tel.enabled:
        status = tr("Kept on this computer only") if not tel.endpoint else (
            tr("Last sent {when}", when=tel.last_sent) if tel.last_sent else tr("Sent when the designer closes"))
        if tel.last_error:
            status = tr("Could not send: {error}", error=tel.last_error)
        rows += [
            ui.field(tr("Endpoint"), ui.input(tel.endpoint, lambda v: tel.configure(endpoint=v),
                                              placeholder="https://…", size="sm", width=240, mono=True, theme=t),
                     description=tr("Where to post the data as JSON; leave it empty to send nothing"), theme=t),
            ui.field(tr("Collected data"), _core.row([
                ui.button(tr("View"), lambda: d.open_url(tel.save().as_uri()) if tel.save() else None, icon="file-json",
                          variant="ghost", size="sm", theme=t),
                ui.button(tr("Delete"), tel.clear, icon="trash-2", variant="ghost", size="sm", theme=t),
            ], spacing=4), description=status, theme=t),
        ]
    return ui.settings_group(tr("Telemetry"), rows, theme=t)


def shortcuts(d: "Designer", t: Theme) -> Any:
    """The keyboard shortcuts dialog: every command's keys, grouped and searchable."""
    return ui.modal(ui.shortcuts(_commands.shortcut_groups(), query=d.picker_query, on_query=d.set_picker_query,
                                 theme=t),
                    title=tr("Keyboard shortcuts"), on_close=d.close_dialog, width=520, theme=t)


def about(d: "Designer", t: Theme) -> Any:
    """The About dialog: versions of Pyzed, Python and Iced, the platform, and links."""
    from .. import __version__

    details = [(tr("Version"), __version__), ("Python", platform.python_version()),
               (tr("Platform"), f"{platform.system()} {platform.machine()}"), ("Iced", _core.ICED_VERSION)]
    blurb = tr("Build windows visually, wire their events to Python and run them.")
    return ui.modal(ui.about("Pyzed Design", __version__, blurb, icon="layout-template", details=details,
                             links=[(tr("Documentation"), d.open_docs),
                                    (tr("Source code"), lambda: d.open_url("https://github.com/albakore/pyzed"))],
                             theme=t),
                    on_close=d.close_dialog, width=400, theme=t)


KINDS = (
    ("form", "Form", "app-window", "A window of your app, with its own handlers."),
    ("component", "Component", "component",
     "A reusable piece, not a window: you place it in forms and in other components."),
    ("shader", "Shader", "blend", "Nodes wired into a GPU shader, for backgrounds, effects and games."),
)


def _choice_card(title: str, description: str, selected: bool, on_press: Any, t: Theme, icon: Optional[str] = None) -> Any:
    head = ui.label(title, weight="semibold", size="sm", theme=t)
    if icon:
        head = _core.row([_icon(icon, size=14, color=t.accent if selected else t.text_muted), head], spacing=6,
                         align="center")
    return _core.button(
        _core.column([head, ui.label(description, size="xs", color="text_muted", theme=t)], spacing=2, width="fill"),
        on_press, padding=(8, 10), width="fill", bg=t.element_selected if selected else t.surface,
        hover_bg=t.element_hover, border_color=t.border_selected if selected else t.border_variant,
        border_width=1, radius=t.radius)


def new_form(d: "Designer", t: Theme) -> Any:
    """The "New" dialog: a form (name, title, template and folder) or a component (name, folder, base)."""
    s = d.new_state
    component = s.get("kind") == "component"
    kinds = _core.grid([_choice_card(tr(label), tr(text), s.get("kind", "form") == key,
                                     lambda k=key: d.set_new("kind", k), t, icon=icon)
                        for key, label, icon, text in KINDS], columns="1fr 1fr 1fr", spacing=8)
    if component:
        return _new_component(d, t, kinds)
    if s.get("kind") == "shader":
        return _new_shader(d, t, kinds)
    cards = [_choice_card(tr(template.label), tr(template.description), template.name == s["template"],
                          lambda name=template.name: d.set_new("template", name), t)
             for template in _new.templates()]
    grid = _core.grid(cards, columns="1fr 1fr", spacing=8)
    folder = Path(s["folder"] or ".")
    path = folder / f"{s['name'] or 'form1'}.pzform"
    exists = path.exists()
    body = _core.column([
        kinds,
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
    return ui.modal(body, title=tr("New form"), on_close=d.close_dialog, width=560, theme=t, footer=[
        ui.button(tr("Unsaved form"), d.create_untitled_form, variant="ghost", theme=t),
        _core.space(width="fill"),
        ui.button(tr("Cancel"), d.close_dialog, variant="ghost", theme=t),
        ui.button(tr("Create"), d.create_new_form, variant="solid", disabled=exists, theme=t),
    ])


def _new_component(d: "Designer", t: Theme, kinds: Any) -> Any:
    from . import scene as _scene
    from . import scene_code as _scene_code

    s = d.new_state
    folder = Path(s["folder"] or ".")
    name = s["name"] or "component1"
    path = folder / f"{_scene_code.member_identifier(name)}{_scene.SUFFIX}"
    exists = path.exists()
    bases = {_base_label(p): str(p) for p in d.base_components()}
    none = tr("Nothing (a new component)")
    chosen = next((label for label, p in bases.items() if p == s.get("extends")), none)
    body = _core.column([
        kinds,
        ui.field(tr("Name"), ui.input(name, lambda v: d.set_new("name", v), mono=True, width=240,
                                  on_submit=d.create_new_component, id="new-form-name", theme=t),
                 description=tr("Class {name}", name=_scene_code.class_identifier(name)), theme=t),
        ui.field(tr("Folder"), ui.input(s["folder"], lambda v: d.set_new("folder", v), mono=True, width=240, theme=t),
                 description=tr("Creates {path}", path=path), theme=t),
        ui.field(tr("Inherits from"),
                 ui.select([none, *bases], chosen, lambda v: d.set_new("extends", bases.get(v, "")), width=240,
                           theme=t),
                 description=tr("Starts with its controls, properties, events and methods"), theme=t),
        ui.callout(tr("{name} already exists", name=path.name), tr("Pick another name or folder."), tint="warning", theme=t)
        if exists else None,
    ], spacing=10)
    return ui.modal(body, title=tr("New component"), on_close=d.close_dialog, width=560, theme=t, footer=[
        _core.space(width="fill"),
        ui.button(tr("Cancel"), d.close_dialog, variant="ghost", theme=t),
        ui.button(tr("Create component"), d.create_new_component, variant="solid", icon="component",
                  disabled=exists, theme=t),
    ])


def _new_shader(d: "Designer", t: Theme, kinds: Any) -> Any:
    from . import shader_doc

    s = d.new_state
    folder = Path(s["folder"] or ".")
    name = s["name"] or "shader1"
    path = folder / f"{name}{shader_doc.SUFFIX}"
    exists = path.exists()
    template = s.get("template") or "blank"
    cards = [_choice_card(tr(title), tr(text), key == template, lambda k=key: d.set_new("template", k), t)
             for key, title, text in shader_doc.templates()]
    body = _core.column([
        kinds,
        ui.field(tr("Name"), ui.input(name, lambda v: d.set_new("name", v), mono=True, width=240,
                                  on_submit=d.create_new_shader, id="new-form-name", theme=t),
                 description=tr("The file name, and how code loads it"), theme=t),
        ui.field(tr("Folder"), ui.input(s["folder"], lambda v: d.set_new("folder", v), mono=True, width=240, theme=t),
                 description=tr("Creates {path}", path=path), theme=t),
        ui.label(tr("Template"), size="sm", weight="medium", theme=t),
        _core.grid(cards, columns="1fr 1fr", spacing=8),
        ui.callout(tr("{name} already exists", name=path.name), tr("Pick another name or folder."), tint="warning", theme=t)
        if exists else None,
    ], spacing=10)
    return ui.modal(body, title=tr("New shader"), on_close=d.close_dialog, width=560, theme=t, footer=[
        _core.space(width="fill"),
        ui.button(tr("Cancel"), d.close_dialog, variant="ghost", theme=t),
        ui.button(tr("Create shader"), d.create_new_shader, variant="solid", icon="blend", disabled=exists, theme=t),
    ])


def _base_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)


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
    """The command palette (the search field in the title bar): a fuzzy-searchable list of the enabled
    commands with their keys, then places to go: panels, settings sections and recent files."""
    items = []
    km = _keymap.get()
    for action in _commands.ACTIONS:
        if not action.enabled(d):
            continue
        label = f"{tr(action.group)}: {action.label.rstrip('…')}"
        items.append(ui.PaletteItem(label, lambda a=action: d.run_action(a.id), keys=km.keys_for(f"workspace::{action.id}"),
                                    icon=action.icon))
    items += places(d, t)
    matches = ui.fuzzy_filter(d.picker_query, items, key=lambda i: i.label)
    index = min(d.picker_index, max(len(matches) - 1, 0))
    chosen = matches[index][0].on_press if matches else None
    return ui.picker(d.picker_query, d.set_picker_query, matches, selected=index,
                     placeholder=tr("Search commands, panels, settings and files…"), input_id=PICKER_ID, on_submit=chosen, theme=t)


def places(d: "Designer", t: Theme) -> List[Any]:
    """The places of the editor the palette goes to: the panels, the pages of the settings and the recent files
    (the keymap editor is already a command)."""
    from . import docks

    def go(open_place: Any) -> Any:
        def press() -> Any:
            d.dialog = None
            return open_place()
        return press

    items = []
    for pid, panel in docks.PANELS.items():
        if panel.available(d):
            items.append(ui.PaletteItem(f"{tr('Panel')}: {panel.title}", go(lambda pid=pid: d.show_panel(pid)),
                                        icon=panel.icon))

    from . import settings_ui

    for group, pages in settings_ui.PAGES:
        for key, title, icon in pages:
            if key.startswith("project.") and d.projects.project is None:
                continue
            items.append(ui.PaletteItem(f"{tr('Settings')}: {tr(title)}", go(lambda k=key: d.open_settings(k)),
                                        icon=icon, detail=tr(group)))
    for path in d.prefs.recent:
        items.append(ui.PaletteItem(f"{tr('Recent')}: {Path(path).name}", go(lambda p=path: d._open_recent(p)),
                                    icon="history", detail=str(Path(path).parent)))
    return items


_PREVIEW_ICONS = {"theme": "palette", "language": "languages", "frame": "app-window"}
_PREVIEW_PLACEHOLDERS = {"theme": "Preview the form in a theme…", "language": "Preview the form in a language…",
                         "frame": "Preview the form in the window frame of…"}


def _preview_picker(d: "Designer", which: str, options: List[str], own: str, t: Theme,
                    labels: Optional[dict] = None) -> Any:
    current = getattr(d, f"preview_{which}")
    items = [ui.PaletteItem(own, lambda: d.set_preview(which, None), icon="undo-2",
                            detail=tr("current") if current is None else "")]
    for option in options:
        items.append(ui.PaletteItem((labels or {}).get(option, option), lambda o=option: d.set_preview(which, o),
                                    icon=_PREVIEW_ICONS[which], detail=tr("current") if option == current else ""))
    matches = ui.fuzzy_filter(d.picker_query, items, key=lambda i: i.label)
    index = min(d.picker_index, max(len(matches) - 1, 0))
    chosen = matches[index][0].on_press if matches else None
    placeholder = tr(_PREVIEW_PLACEHOLDERS[which])
    return ui.picker(d.picker_query, d.set_picker_query, matches, selected=index, placeholder=placeholder,
                     input_id=PICKER_ID, on_submit=chosen, theme=t)


def preview_theme(d: "Designer", t: Theme) -> Any:
    """The themes to look at the form in, first the form's own."""
    from ..theme import themes

    return _preview_picker(d, "theme", themes.names(), tr("The form's theme ({name})", name=d.doc.form.theme), t)


def preview_frame(d: "Designer", t: Theme) -> Any:
    """The platforms whose window frame the canvas can show around the form, first this system's."""
    labels = ui.frame.PLATFORM_LABELS
    own = tr("This system ({name})", name=labels[ui.system_platform()])
    return _preview_picker(d, "frame", list(ui.frame.PLATFORMS), own, t, labels=labels)


def preview_language(d: "Designer", t: Theme) -> Any:
    """The languages with translations (``locales/`` next to the form), first the designer's own."""
    from .. import i18n

    return _preview_picker(d, "language", i18n.languages(),
                           tr("The current language ({name})", name=i18n.language()), t)
