"""The designer's dockable, resizable panels.

Panels (toolbox and outline, project, properties, events, code, console) live in four
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
from .preferences import DOCKS

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Default sizes in pixels: width of side docks, height of top and bottom docks.
SIZES = {"left": 240.0, "right": 320.0, "bottom": 300.0, "top": 220.0}
MIN_SIZE = {"left": 170.0, "right": 220.0, "bottom": 120.0, "top": 120.0}
#: The form keeps at least this much room.
MIN_CENTER = 320.0
DOCK_ICONS = {"left": "panel-left", "right": "panel-right", "bottom": "panel-bottom", "top": "panel-top"}
TAB_HEIGHT = 32.0


@dataclass(frozen=True)
class Panel:
    """A panel that can be docked: ``view(designer, theme)`` draws its body."""

    id: str
    title: str
    icon: str
    dock: str
    view: Callable[["Designer", Theme], Any]
    #: ``False`` while the panel has nothing to show (the code panel with no handler open).
    available: Callable[["Designer"], bool] = lambda d: True


def _design(d: "Designer", t: Theme) -> Any:
    from . import panels

    top = _core.column([ui.panel_header("Toolbox", icon="component", theme=t), panels.toolbox(d, t)],
                       width="fill", height="fill")
    bottom = _core.column([ui.panel_header("Outline", icon="layers", theme=t), panels.outline(d, t)],
                          width="fill", height="fill")
    return ui.split(top, bottom, vertical=True, ratio=d.left_ratio, on_resize=d.resize_left, min_size=120, theme=t)


def _project(d: "Designer", t: Theme) -> Any:
    from . import project_panel

    return project_panel.view(d, t)


def _properties(d: "Designer", t: Theme) -> Any:
    from . import panels

    return panels.properties(d, t)


def _events(d: "Designer", t: Theme) -> Any:
    from . import panels

    return panels.events(d, t)


def _code(d: "Designer", t: Theme) -> Any:
    from . import code_panel

    return _core.mouse_area(code_panel.code_panel(d, t), on_enter=d.focus_code)


def _console(d: "Designer", t: Theme) -> Any:
    from . import console

    return console.view(d, t)


PANELS: Dict[str, Panel] = {p.id: p for p in (
    Panel("design", "Design", "component", "left", _design),
    Panel("project", "Project", "package", "left", _project),
    Panel("properties", "Properties", "settings-2", "right", _properties),
    Panel("events", "Events", "zap", "right", _events),
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

    def panels_in(self, dock: str, d: "Designer") -> List[Panel]:
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
        shown = self.shown(self.docks[panel], d)
        return shown is not None and shown.id == panel

    def move(self, panel: str, dock: str) -> None:
        self.docks[panel] = dock
        self.show(panel)
        self.menu = None

    def toggle(self, dock: str) -> None:
        self.closed[dock] = not self.closed.get(dock)

    def resize(self, dock: str, size: float) -> None:
        self.sizes[dock] = max(round(size), MIN_SIZE[dock])


# -- view --------------------------------------------------------------------------


def _dock_menu(d: "Designer", dock: str, panel: Panel, t: Theme) -> Any:
    layout = d.layout
    items: List[Any] = [f"Move {panel.title} to"]
    for target in DOCKS:
        items.append(ui.MenuItem(target.capitalize(), lambda target=target: d.move_panel(panel.id, target),
                                 icon=DOCK_ICONS[target], checked=layout.docks[panel.id] == target))
    items += [ui.SEPARATOR, ui.MenuItem("Hide dock", lambda: d.toggle_dock(dock), icon="eye-off")]
    return ui.menu(items, width=200, theme=t)


def dock_view(d: "Designer", dock: str, t: Theme) -> Optional[Any]:
    layout = d.layout
    panel = layout.shown(dock, d)
    if panel is None:
        return None
    panels = layout.panels_in(dock, d)
    tabs = [ui.Tab(p.id, p.title, icon=p.icon) for p in panels]
    end = [ui.icon_button(DOCK_ICONS[dock], lambda: d.open_dock_menu(dock), size="sm", selected=layout.menu == dock,
                          tooltip="Move this panel", theme=t),
           ui.icon_button("x", lambda: d.toggle_dock(dock), size="sm", tooltip="Hide dock", theme=t)]
    bar = ui.tab_bar(tabs, panel.id, on_select=d.show_panel, end=end, height=TAB_HEIGHT, theme=t)
    body = _core.column([bar, panel.view(d, t)], width="fill", height="fill")
    if layout.menu == dock:
        body = ui.popover(body, _dock_menu(d, dock, panel, t), x=6, y=TAB_HEIGHT, align_x="end",
                          on_dismiss=d.close_dock_menu)
    return _core.mouse_area(_core.container(body, width="fill", height="fill", bg=t.panel, clip=True),
                            on_enter=d.focus_code if panel.id == "code" else d.focus_panel)


def _clamp(dock: str, size: float, total: float) -> float:
    return max(MIN_SIZE[dock], min(size, max(total - MIN_CENTER, MIN_SIZE[dock])))


def workspace(d: "Designer", center: Any, t: Theme) -> Any:
    """``center`` (toolbar and form) surrounded by the open docks, with draggable splitters."""
    views = {dock: dock_view(d, dock, t) for dock in DOCKS}
    layout = d.layout

    def build(width: float, height: float) -> Any:
        column = center
        middle_h = height
        top, bottom = views["top"], views["bottom"]
        left, right = views["left"], views["right"]
        if top is not None:
            middle_h = height - _clamp("top", layout.sizes["top"], height) - 1
        if bottom is not None:
            size = _clamp("bottom", layout.sizes["bottom"], middle_h)
            avail = max(middle_h - 1, 1)
            column = ui.split(column, bottom, vertical=True, ratio=(avail - size) / avail,
                              on_resize=lambda r, a=avail: d.resize_dock("bottom", a * (1 - r)),
                              min_size=MIN_CENTER / 2, min_size_second=MIN_SIZE["bottom"], theme=t)
        if top is not None:
            size = _clamp("top", layout.sizes["top"], height)
            avail = max(height - 1, 1)
            column = ui.split(top, column, vertical=True, ratio=size / avail,
                              on_resize=lambda r, a=avail: d.resize_dock("top", a * r),
                              min_size=MIN_SIZE["top"], min_size_second=MIN_CENTER / 2, theme=t)
        row = column
        inner_w = width
        if left is not None:
            inner_w = width - _clamp("left", layout.sizes["left"], width) - 1
        if right is not None:
            size = _clamp("right", layout.sizes["right"], inner_w)
            avail = max(inner_w - 1, 1)
            row = ui.split(row, right, ratio=(avail - size) / avail,
                           on_resize=lambda r, a=avail: d.resize_dock("right", a * (1 - r)),
                           min_size=MIN_CENTER, min_size_second=MIN_SIZE["right"], theme=t)
        if left is not None:
            size = _clamp("left", layout.sizes["left"], width)
            avail = max(width - 1, 1)
            row = ui.split(left, row, ratio=size / avail, on_resize=lambda r, a=avail: d.resize_dock("left", a * r),
                           min_size=MIN_SIZE["left"], min_size_second=MIN_CENTER, theme=t)
        return row

    return _core.responsive(build)
