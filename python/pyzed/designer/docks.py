"""The designer's dockable, resizable panels and the tab areas they share with the documents.

Panels (toolbox and outline, project, properties, events, agent, code, console, logs) live in four
docks around the form (left, right, bottom and top), in the main window's center next to the form
tabs, or in windows of their own. Every place is one tab area: its documents (forms, components)
and its panels share one row of tabs and show one of them at a time. Dragging a tab reorders it,
drops it on another place or takes it out of the window (``dock_windows``); the dock menu does the
same, as in Zed, and the splitters between docks and the form resize them. Where each panel is,
which dock is open, how big it is and where the panel windows are are saved with the designer's
preferences, and named work layouts keep several of those arrangements.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .. import _core, ui
from ..theme import Theme
from .locale import tr
from .preferences import DOCKS
from .windows import MAIN, WINDOW

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Default sizes in pixels: width of side docks, height of top and bottom docks.
SIZES = {"left": 240.0, "right": 360.0, "bottom": 300.0, "top": 220.0}
MIN_SIZE = {"left": 170.0, "right": 220.0, "bottom": 120.0, "top": 120.0}
DOCK_ICONS = {"left": "panel-left", "right": "panel-right", "bottom": "panel-bottom", "top": "panel-top"}
TAB_HEIGHT = 32.0
#: Height of the tab row of the main window's center and of the windows of their own.
CENTER_TAB_HEIGHT = 30.0


def tab_height(place: str) -> float:
    """The height of the tab row of ``place``."""
    return TAB_HEIGHT if place in DOCKS else CENTER_TAB_HEIGHT


@dataclass(frozen=True)
class Panel:
    """A panel that can be docked: ``view(designer, theme)`` draws its body."""

    id: str
    #: The English title; ``title`` is the one in the designer's language.
    name: str
    icon: str
    dock: str
    view: Callable[["Designer", Theme], Any]
    #: ``False`` while the panel has nothing to show (the code panel with no handler open).
    available: Callable[["Designer"], bool] = lambda d: True

    @property
    def title(self) -> str:
        """The panel's title in the designer's language."""
        return tr(self.name)


def _design(d: "Designer", t: Theme) -> Any:
    from . import component_view, panels, shader_editor

    if shader_editor.is_shader(d):  # the Shading sidebar and the shader's variables
        return shader_editor.design_panel(d, t)
    top = panels.toolbox(d, t)  # the tab already says "Toolbox"
    outline = _nothing_open(t, "layers") if d.nothing_open else panels.outline(d, t)
    bottom = _core.column([ui.panel_header(tr("Outline"), icon="layers", theme=t), outline],
                          width="fill", height="fill")
    if not d.nothing_open and component_view.is_component(d):  # what the class brings, under its controls
        members = _core.column([ui.panel_header(tr("Members"), icon="braces", theme=t),
                                component_view.members_view(d, t)], width="fill", height="fill")
        bottom = ui.split(bottom, members, vertical=True, ratio=d.members_ratio, on_resize=d.resize_members,
                          min_size=80, theme=t)
    return ui.split(top, bottom, vertical=True, ratio=d.left_ratio, on_resize=d.resize_left, min_size=120, theme=t)


def _nothing_open(t: Theme, icon: str) -> Any:
    """What the form panels show while every tab is closed."""
    return ui.empty_state(tr("No form open"), tr("Open or create a form to see its controls here."), icon=icon,
                          size="sm", theme=t)


def _project(d: "Designer", t: Theme) -> Any:
    from . import project_panel

    return project_panel.view(d, t)


def _dependencies(d: "Designer", t: Theme) -> Any:
    from . import project_panel

    return project_panel.dependencies_view(d, t)


def _properties(d: "Designer", t: Theme) -> Any:
    from . import panels, shader_editor

    if shader_editor.is_shader(d):
        return shader_editor.properties(d, t)
    if d.nothing_open:
        return _nothing_open(t, "settings-2")
    return panels.properties(d, t)


def _events(d: "Designer", t: Theme) -> Any:
    from . import panels, shader_editor

    if shader_editor.is_shader(d):
        return shader_editor.events(d, t)
    if d.nothing_open:
        return _nothing_open(t, "zap")
    return panels.events(d, t)


def _code(d: "Designer", t: Theme) -> Any:
    from . import code_panel

    return _core.mouse_area(code_panel.code_panel(d, t), on_enter=d.focus_code)


def _agent(d: "Designer", t: Theme) -> Any:
    from . import agent_panel

    return agent_panel.view(d, t)


def _animation(d: "Designer", t: Theme) -> Any:
    from . import timeline_panel

    return timeline_panel.view(d, t)


def _console(d: "Designer", t: Theme) -> Any:
    from . import console

    return console.view(d, t)


def _search(d: "Designer", t: Theme) -> Any:
    from . import project_search

    return project_search.view(d, t)


def _logs(d: "Designer", t: Theme) -> Any:
    from . import logs

    return logs.view(d, t)


PANELS: Dict[str, Panel] = {p.id: p for p in (
    # the id stays "design" so saved layouts keep their place; the tab is named after what it holds
    Panel("design", "Toolbox", "component", "left", _design),
    Panel("project", "Project", "folder-tree", "left", _project),
    Panel("search", "Search", "text-search", "left", _search, lambda d: d.search.visible),
    Panel("dependencies", "Dependencies", "package", "left", _dependencies, lambda d: d.projects.project is not None),
    Panel("properties", "Properties", "settings-2", "right", _properties),
    Panel("events", "Events", "zap", "right", _events),
    Panel("agent", "Agent", "sparkles", "right", _agent),
    Panel("code", "Code", "code", "bottom", _code, lambda d: d.editing is not None or bool(d.buffers.items)),
    Panel("console", "Console", "terminal", "bottom", _console, lambda d: d.console.visible),
    Panel("logs", "Logs", "scroll-text", "bottom", _logs, lambda d: d.logs.pinned),
    Panel("animation", "Animation", "clapperboard", "bottom", _animation,
          lambda d: d.timeline.open or bool(d.doc.form.animations)),
)}


def is_window(place: Optional[str]) -> bool:
    """Whether ``place`` is a window of its own (not one of the four docks or the main window's center)."""
    return bool(place) and place.startswith(WINDOW)  # type: ignore[union-attr]


def valid_place(place: Any) -> bool:
    """Whether ``place`` is a dock ("left", "right", "bottom", "top"), the main window's center ("main") or a
    window of its own ("window:N")."""
    return isinstance(place, str) and (place in DOCKS or place == MAIN
                                       or (is_window(place) and place[len(WINDOW):].isdigit()))


def front(d: "Designer", place: str) -> Optional[tuple]:
    """What ``place`` shows: ``("panel", panel)``, ``("doc", pane)`` (its document in front) or ``None`` (a
    closed dock, or nothing to show). A panel whose tab was picked last comes before the documents."""
    layout = d.layout
    if layout.closed.get(place):
        return None
    pane = d.panes.at(place)
    panels = layout.panels_in(place, d)
    if pane is not None and pane.front is not None:
        picked = next((p for p in panels if p.id == pane.front), None)
        if picked is not None:
            return "panel", picked
    if pane is not None and pane.docs:
        return "doc", pane
    if panels:
        active = layout.active.get(place)
        return "panel", next((p for p in panels if p.id == active), panels[0])
    return None


class DockLayout:
    """Where each panel is (a dock or a window of its own), which panel each place shows, the order of
    the tabs, the dock sizes and where the panel windows are."""

    def __init__(self, docks: Optional[Dict[str, str]] = None, sizes: Optional[Dict[str, float]] = None,
                 hidden: Optional[Dict[str, bool]] = None, order: Optional[List[str]] = None,
                 windows: Optional[Dict[str, Dict[str, Any]]] = None,
                 active: Optional[Dict[str, str]] = None) -> None:
        self.docks: Dict[str, str] = {pid: p.dock for pid, p in PANELS.items()}
        self.docks.update({k: v for k, v in (docks or {}).items() if k in PANELS and valid_place(v)})
        #: The dock a panel goes back to when its window closes (the last dock it was in).
        self.home: Dict[str, str] = {pid: place if place in DOCKS else PANELS[pid].dock
                                     for pid, place in self.docks.items()}
        #: The order of the tabs (panel ids); a place shows its panels in this order.
        self.order: List[str] = [pid for pid in (order or []) if pid in PANELS]
        self.order += [pid for pid in PANELS if pid not in self.order]
        self.sizes: Dict[str, float] = {**SIZES, **(sizes or {})}
        #: docks the user closed (hidden even if they have panels)
        self.closed: Dict[str, bool] = {dock: False for dock in DOCKS}
        self.closed.update({k: bool(v) for k, v in (hidden or {}).items() if k in DOCKS})
        self.active: Dict[str, Optional[str]] = {dock: None for dock in DOCKS}
        self.active.update({k: v for k, v in (active or {}).items() if valid_place(k) and v in PANELS})
        #: Size and screen position of each panel window ("window:N" -> {"size": [w, h], "position": [x, y]}).
        self.windows: Dict[str, Dict[str, Any]] = {k: dict(v) for k, v in (windows or {}).items()
                                                   if is_window(k) and isinstance(v, dict)}
        #: place whose "move panel" menu is open
        self.menu: Optional[str] = None
        #: a panel that fills the window (the Agent panel's expand button), or ``None``
        self.zoomed: Optional[str] = None

    # -- places -----------------------------------------------------------------
    def window_places(self) -> List[str]:
        """The panel windows in use, in order."""
        return sorted({p for p in self.docks.values() if is_window(p)}, key=lambda p: int(p[len(WINDOW):]))

    def new_window(self) -> str:
        """A free panel window place."""
        used = {int(p[len(WINDOW):]) for p in self.docks.values() if is_window(p)} | {
            int(p[len(WINDOW):]) for p in self.windows}
        n = 1
        while n in used:
            n += 1
        return f"{WINDOW}{n}"

    def all_in(self, place: str) -> List[str]:
        """The ids of every panel in ``place`` (shown or not), in tab order."""
        return [pid for pid in self.order if self.docks.get(pid) == place]

    def panels_in(self, place: str, d: "Designer") -> List[Panel]:
        """Returns the panels in ``place`` that currently have something to show, in tab order."""
        return [PANELS[pid] for pid in self.all_in(place) if PANELS[pid].available(d)]

    def shown(self, place: str, d: "Designer") -> Optional[Panel]:
        """The panel ``place`` shows (``None`` when it is a closed dock or has nothing to show)."""
        if self.closed.get(place):
            return None
        panels = self.panels_in(place, d)
        if not panels:
            return None
        active = self.active.get(place)
        return next((p for p in panels if p.id == active), panels[0])

    def show(self, panel: str) -> str:
        """Brings ``panel`` to the front of its place, opens its dock and returns the place."""
        place = self.docks[panel]
        self.active[place] = panel
        if place in DOCKS:
            self.closed[place] = False
        return place

    def is_showing(self, panel: str, d: "Designer") -> bool:
        """Whether ``panel`` is the one its place currently shows."""
        shown = front(d, self.docks[panel])
        return shown is not None and shown[0] == "panel" and shown[1].id == panel

    def move(self, panel: str, place: str, before: Optional[str] = None) -> None:
        """Moves ``panel`` to ``place`` (a dock or a panel window), before the panel ``before`` there (else
        last), shows it there and closes the dock menu."""
        if not valid_place(place):
            raise ValueError(f"not a dock or a panel window: {place!r}")
        source = self.docks.get(panel)
        self.docks[panel] = place
        if place in DOCKS:
            self.home[panel] = place
        others = [pid for pid in self.all_in(place) if pid != panel]
        self.order.remove(panel)
        if before in others:
            self.order.insert(self.order.index(before), panel)
        elif others:
            self.order.insert(self.order.index(others[-1]) + 1, panel)
        else:
            self.order.append(panel)
        self.show(panel)
        self.menu = None
        if source is not None and source != place and self.active.get(source) == panel:
            self.active[source] = None
        self.forget_empty()

    def forget_empty(self) -> None:
        """Drops what is remembered about panel windows that have no panel left."""
        used = set(self.window_places())
        for place in [p for p in self.windows if p not in used]:
            del self.windows[place]
        for place in [p for p in self.active if is_window(p) and p not in used]:
            del self.active[place]

    def send_home(self, place: str) -> List[str]:
        """Moves every panel of the window ``place`` back to the dock it came from; returns them."""
        moved = self.all_in(place)
        for pid in moved:
            self.move(pid, self.home.get(pid, PANELS[pid].dock))
        self.forget_empty()
        return moved

    def toggle(self, dock: str) -> None:
        """Hides ``dock`` if it is open, or opens it again."""
        self.closed[dock] = not self.closed.get(dock)

    def resize(self, dock: str, size: float) -> None:
        """Sets the size of ``dock`` in pixels (rounded, and at least its minimum size)."""
        self.sizes[dock] = max(round(size), MIN_SIZE[dock])

    def place_label(self, panel: str) -> str:
        """Where ``panel`` is, in words: "Left", "Bottom"..., "Center" or "Window"."""
        place = self.docks[panel]
        return tr("Window") if is_window(place) else tr("Center") if place == MAIN else tr(place.capitalize())

    # -- saving -----------------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        """The layout as a JSON-ready dict (what ``from_snapshot`` and the saved work layouts take)."""
        return {
            "docks": dict(self.docks),
            "sizes": dict(self.sizes),
            "hidden": {dock: closed for dock, closed in self.closed.items() if closed},
            "order": list(self.order),
            "active": {k: v for k, v in self.active.items() if v},
            "windows": {k: dict(v) for k, v in self.windows.items()},
        }

    @classmethod
    def from_snapshot(cls, data: Dict[str, Any]) -> "DockLayout":
        """A layout from a ``snapshot`` (unknown panels and places are ignored)."""
        def part(key: str, kind: type) -> Any:
            value = data.get(key)
            return value if isinstance(value, kind) else None

        return cls(part("docks", dict), part("sizes", dict), part("hidden", dict), part("order", list),
                   part("windows", dict), part("active", dict))


#: The work layouts that come with the designer: name -> how to change the default layout.
def _coding(layout: DockLayout) -> None:
    layout.move("code", "right", before="properties")
    layout.move("console", "bottom")
    layout.sizes["right"] = 620.0


def _focus(layout: DockLayout) -> None:
    for dock in ("left", "bottom", "top"):
        layout.closed[dock] = True


def _review(layout: DockLayout) -> None:
    layout.move("events", "left")
    layout.move("code", "bottom", before="console")
    layout.sizes["bottom"] = 360.0


def _code_with_forms(layout: DockLayout) -> None:
    layout.move("code", MAIN)
    layout.move("events", "left")
    layout.active[MAIN] = None


PRESETS: Dict[str, Callable[[DockLayout], None]] = {
    "Default": lambda layout: None,
    "Coding": _coding,
    "Focus": _focus,
    "Events and code": _review,
    "Code with the forms": _code_with_forms,
}


def preset(name: str) -> DockLayout:
    """The built-in work layout ``name`` (see ``PRESETS``)."""
    layout = DockLayout()
    PRESETS[name](layout)
    layout.menu = None
    return layout


# -- view --------------------------------------------------------------------------


def _dock_menu(d: "Designer", place: str, panel: Panel, t: Theme) -> Any:
    layout = d.layout
    items: List[Any] = [tr("Move {panel} to", panel=panel.title)]
    for target in DOCKS:
        items.append(ui.MenuItem(tr(target.capitalize()), lambda target=target: d.move_panel(panel.id, target),
                                 icon=DOCK_ICONS[target], checked=layout.docks[panel.id] == target))
    items.append(ui.MenuItem(tr("Center"), lambda: d.move_panel(panel.id, MAIN), icon="app-window",
                             checked=layout.docks[panel.id] == MAIN))
    pane = d.panes.at(place)
    alone = is_window(place) and len(layout.all_in(place)) == 1 and not (pane is not None and pane.docs)
    items.append(ui.MenuItem(tr("New window"), None if alone else lambda: d.dock_windows.detach(panel.id),
                             icon="square-arrow-out-up-right", disabled=alone))
    if place in DOCKS:
        items += [ui.SEPARATOR, ui.MenuItem(tr("Hide dock"), lambda: d.toggle_dock(place), icon="eye-off")]
    elif is_window(place):
        items += [ui.SEPARATOR, ui.MenuItem(tr("Dock everything here back"), lambda: d.dock_windows.dock_back(place),
                                            icon="panel-left-close")]
    return ui.menu(items, width=220, theme=t)


def panel_body(d: "Designer", panel: Panel, t: Theme) -> Any:
    """The body of ``panel``; one that fails to draw shows the error in its place and the rest of the window
    keeps working."""
    content = d.logs.boundary(lambda: panel.view(d, t), tr("The {panel} panel", panel=panel.title), t)
    return _core.mouse_area(_core.container(content, width="fill", height="fill", bg=t.panel, clip=True),
                            on_enter=d.focus_code if panel.id == "code" else lambda: d.focus_panel(panel.id))


def place_end(d: "Designer", place: str, shown: tuple, t: Theme) -> List[Any]:
    """The buttons at the end of the tab row of ``place``: the menu of the panel in front, and closing the
    dock (or docking a window's tabs back)."""
    layout = d.layout
    items: List[Any] = []
    window = is_window(place)
    if shown[0] == "panel":
        items.append(ui.icon_button("square-arrow-out-up-right" if window or place == MAIN else DOCK_ICONS[place],
                                    lambda: d.open_dock_menu(place), size="sm", selected=layout.menu == place,
                                    tooltip=tr("Move this panel"), theme=t))
    if window:
        items.append(ui.icon_button("x", lambda: d.dock_windows.dock_back(place), size="sm",
                                    tooltip=tr("Dock everything here back"), theme=t))
    elif place in DOCKS:
        items.append(ui.icon_button("x", lambda: d.toggle_dock(place), size="sm", tooltip=tr("Hide dock"), theme=t))
    return items


def with_menu(d: "Designer", place: str, shown: tuple, body: Any, t: Theme) -> Any:
    """``body`` with the panel menu of ``place`` open over it, when it is."""
    if d.layout.menu == place and shown[0] == "panel":
        return ui.popover(body, _dock_menu(d, place, shown[1], t), x=6, y=tab_height(place), align_x="end",
                          on_dismiss=d.close_dock_menu)
    return body


def dock_view(d: "Designer", place: str, t: Theme) -> Optional[Any]:
    """Builds the dock ``place`` with its tabs (documents and panels), its menu and what is in front; ``None``
    if it shows nothing. The tabs can be dragged to reorder them, to another place or out of the window."""
    shown = front(d, place)
    if shown is None:
        return None
    bar = d.dock_windows.tab_bar(place, shown, place_end(d, place, shown, t), t)
    if shown[0] == "panel":
        content = panel_body(d, shown[1], t)
    else:
        content = d.doc_body(shown[1], t)
    body = with_menu(d, place, shown, _core.column([bar, content], width="fill", height="fill"), t)
    return _core.container(body, width="fill", height="fill", bg=t.panel, clip=True)


#: The edge of each dock that carries its resize handle (the one facing the form).
INNER_EDGE = {"left": "right", "right": "left", "bottom": "top", "top": "bottom"}


def workspace(d: "Designer", center: Any, t: Theme) -> Any:
    """``center`` (toolbar and form) surrounded by the open docks, each resizable from its inner edge."""
    layout = d.layout
    if layout.zoomed is not None:
        place = layout.docks[layout.zoomed]
        view = dock_view(d, place, t) if place in DOCKS and layout.is_showing(layout.zoomed, d) else None
        if view is not None:
            return view
        layout.zoomed = None

    def sized(dock: str) -> Optional[Any]:
        view = dock_view(d, dock, t)
        if view is None:
            return None
        return _core.resizable(view, edge=INNER_EDGE[dock], size=layout.sizes[dock], min_size=MIN_SIZE[dock],
                               on_resize=lambda size, dock=dock: d.resize_dock(dock, size), color=t.border,
                               hover_color=t.border_focused)

    middle = _core.column([sized("top"), _core.container(center, width="fill", height="fill", clip=True),
                           sized("bottom")], width="fill", height="fill")
    return _core.row([sized("left"), middle, sized("right")], width="fill", height="fill")
