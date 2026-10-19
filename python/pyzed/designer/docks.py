"""The designer's dockable, resizable panels.

Panels (toolbox and outline, project, properties, events, agent, code, console) live in four
docks around the form: left, right, bottom and top. Each dock shows one panel at a time
with a tab per panel; the dock menu moves a panel to another dock, as in Zed, and the
splitters between docks and the form resize them. Where each panel is, which dock is
open and how big it is are saved with the designer's preferences.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .. import _core, ui
from ..theme import Theme
from .locale import tr
from .preferences import DOCKS

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Default sizes in pixels: width of side docks, height of top and bottom docks.
SIZES = {"left": 240.0, "right": 360.0, "bottom": 300.0, "top": 220.0}
MIN_SIZE = {"left": 170.0, "right": 220.0, "bottom": 120.0, "top": 120.0}
DOCK_ICONS = {"left": "panel-left", "right": "panel-right", "bottom": "panel-bottom", "top": "panel-top"}
TAB_HEIGHT = 32.0


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
    from . import panels

    top = _core.column([ui.panel_header(tr("Toolbox"), icon="component", theme=t), panels.toolbox(d, t)],
                       width="fill", height="fill")
    bottom = _core.column([ui.panel_header(tr("Outline"), icon="layers", theme=t), panels.outline(d, t)],
                          width="fill", height="fill")
    return ui.split(top, bottom, vertical=True, ratio=d.left_ratio, on_resize=d.resize_left, min_size=120, theme=t)


def _project(d: "Designer", t: Theme) -> Any:
    from . import project_panel

    return project_panel.view(d, t)


def _dependencies(d: "Designer", t: Theme) -> Any:
    from . import project_panel

    return project_panel.dependencies_view(d, t)


def _properties(d: "Designer", t: Theme) -> Any:
    from . import panels

    return panels.properties(d, t)


def _events(d: "Designer", t: Theme) -> Any:
    from . import panels

    return panels.events(d, t)


def _code(d: "Designer", t: Theme) -> Any:
    from . import code_panel

    return _core.mouse_area(code_panel.code_panel(d, t), on_enter=d.focus_code)


def _agent(d: "Designer", t: Theme) -> Any:
    from . import agent_panel

    return agent_panel.view(d, t)


def _console(d: "Designer", t: Theme) -> Any:
    from . import console

    return console.view(d, t)


PANELS: Dict[str, Panel] = {p.id: p for p in (
    Panel("design", "Design", "component", "left", _design),
    Panel("project", "Project", "folder-tree", "left", _project),
    Panel("dependencies", "Dependencies", "package", "left", _dependencies, lambda d: d.projects.project is not None),
    Panel("properties", "Properties", "settings-2", "right", _properties),
    Panel("events", "Events", "zap", "right", _events),
    Panel("agent", "Agent", "sparkles", "right", _agent),
    Panel("code", "Code", "code", "bottom", _code, lambda d: d.editing is not None),
    Panel("console", "Console", "terminal", "bottom", _console, lambda d: d.console.visible),
)}


class DockLayout:
    """Where each panel is docked, which panel each dock shows, and the dock sizes."""

    def __init__(self, docks: Optional[Dict[str, str]] = None, sizes: Optional[Dict[str, float]] = None,
                 hidden: Optional[Dict[str, bool]] = None) -> None:
        self.docks: Dict[str, str] = {pid: p.dock for pid, p in PANELS.items()}
        self.docks.update({k: v for k, v in (docks or {}).items() if k in PANELS and v in DOCKS})
        self.sizes: Dict[str, float] = {**SIZES, **(sizes or {})}
        #: docks the user closed (hidden even if they have panels)
        self.closed: Dict[str, bool] = {dock: False for dock in DOCKS}
        self.closed.update({k: bool(v) for k, v in (hidden or {}).items() if k in DOCKS})
        self.active: Dict[str, Optional[str]] = {dock: None for dock in DOCKS}
        #: dock whose "move panel" menu is open
        self.menu: Optional[str] = None
        #: a panel that fills the window (the Agent panel's expand button), or ``None``
        self.zoomed: Optional[str] = None

    def panels_in(self, dock: str, d: "Designer") -> List[Panel]:
        """Returns the panels docked in ``dock`` that currently have something to show."""
        return [p for pid, p in PANELS.items() if self.docks.get(pid) == dock and p.available(d)]

    def shown(self, dock: str, d: "Designer") -> Optional[Panel]:
        """The panel the dock shows (``None`` when it is closed or empty)."""
        if self.closed.get(dock):
            return None
        panels = self.panels_in(dock, d)
        if not panels:
            return None
        active = self.active.get(dock)
        return next((p for p in panels if p.id == active), panels[0])

    def show(self, panel: str) -> None:
        """Brings ``panel`` to the front of its dock and opens the dock."""
        dock = self.docks[panel]
        self.active[dock] = panel
        self.closed[dock] = False

    def is_showing(self, panel: str, d: "Designer") -> bool:
        """Whether ``panel`` is the one its dock currently shows."""
        shown = self.shown(self.docks[panel], d)
        return shown is not None and shown.id == panel

    def move(self, panel: str, dock: str) -> None:
        """Moves ``panel`` to ``dock``, shows it there and closes the dock menu."""
        self.docks[panel] = dock
        self.show(panel)
        self.menu = None

    def toggle(self, dock: str) -> None:
        """Hides ``dock`` if it is open, or opens it again."""
        self.closed[dock] = not self.closed.get(dock)

    def resize(self, dock: str, size: float) -> None:
        """Sets the size of ``dock`` in pixels (rounded, and at least its minimum size)."""
        self.sizes[dock] = max(round(size), MIN_SIZE[dock])


# -- view --------------------------------------------------------------------------


def _dock_menu(d: "Designer", dock: str, panel: Panel, t: Theme) -> Any:
    layout = d.layout
    items: List[Any] = [tr("Move {panel} to", panel=panel.title)]
    for target in DOCKS:
        items.append(ui.MenuItem(tr(target.capitalize()), lambda target=target: d.move_panel(panel.id, target),
                                 icon=DOCK_ICONS[target], checked=layout.docks[panel.id] == target))
    items += [ui.SEPARATOR, ui.MenuItem(tr("Hide dock"), lambda: d.toggle_dock(dock), icon="eye-off")]
    return ui.menu(items, width=200, theme=t)


def dock_view(d: "Designer", dock: str, t: Theme) -> Optional[Any]:
    """Builds ``dock`` with its panel tabs, menu and the shown panel's body; ``None`` if it shows nothing."""
    layout = d.layout
    panel = layout.shown(dock, d)
    if panel is None:
        return None
    panels = layout.panels_in(dock, d)
    # When the titles do not fit the dock (three panels on the left), the tabs not shown keep only their icon.
    needed = sum(len(p.title) * 6.8 + 62 for p in panels)
    compact = dock in ("left", "right") and needed > layout.sizes.get(dock, 0)
    tabs = [ui.Tab(p.id, "" if compact and p.id != panel.id else p.title, icon=p.icon) for p in panels]
    end = [ui.icon_button(DOCK_ICONS[dock], lambda: d.open_dock_menu(dock), size="sm", selected=layout.menu == dock,
                          tooltip=tr("Move this panel"), theme=t),
           ui.icon_button("x", lambda: d.toggle_dock(dock), size="sm", tooltip=tr("Hide dock"), theme=t)]
    bar = ui.tab_bar(tabs, panel.id, on_select=d.show_panel, end=end, height=TAB_HEIGHT, theme=t)
    body = _core.column([bar, panel.view(d, t)], width="fill", height="fill")
    if layout.menu == dock:
        body = ui.popover(body, _dock_menu(d, dock, panel, t), x=6, y=TAB_HEIGHT, align_x="end",
                          on_dismiss=d.close_dock_menu)
    return _core.mouse_area(_core.container(body, width="fill", height="fill", bg=t.panel, clip=True),
                            on_enter=d.focus_code if panel.id == "code" else d.focus_panel)


#: The edge of each dock that carries its resize handle (the one facing the form).
INNER_EDGE = {"left": "right", "right": "left", "bottom": "top", "top": "bottom"}


def workspace(d: "Designer", center: Any, t: Theme) -> Any:
    """``center`` (toolbar and form) surrounded by the open docks, each resizable from its inner edge."""
    layout = d.layout
    if layout.zoomed is not None:
        view = dock_view(d, layout.docks[layout.zoomed], t) if layout.is_showing(layout.zoomed, d) else None
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
