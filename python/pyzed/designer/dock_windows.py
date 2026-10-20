"""Panels in windows of their own, dragging panel tabs, and named work layouts.

Any panel (Code, Console, Properties, Agent...) can leave the main window: drag its tab out of
the window, or pick **New window** in its dock menu. A panel window shows its panels as tabs,
like a dock; dragging another panel's tab onto it stacks the panel there, and dragging a tab
onto the main window docks it on the side under the pointer. Dragging a tab inside the main
window moves it to the dock under the pointer (the target is highlighted), or along a tab row
to reorder it. Closing a panel window sends its panels back to the docks they came from.

Where every panel is, the dock sizes and the panel windows' size and position are saved with
the preferences and restored on the next start. **Work layouts** keep several of those
arrangements by name (a few come built in, see ``docks.PRESETS``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .. import _core, ui
from ..app import Window
from ..ui import frame as ui_frame
from . import docks
from .docks import DOCKS, TAB_HEIGHT, DockLayout, is_window
from .locale import tr
from .windows import GRAB_OFFSET, Pane

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Size of a new panel window.
WINDOW_SIZE = (440.0, 600.0)
#: How far into the window a dock's drop zone reaches when the dock is closed or thin.
EDGE = 140.0
#: Height of the status bar under the docks.
STATUS_HEIGHT = 24.0


class DockWindow(Window):
    """A window that shows the panels of one place ("window:N") as tabs."""

    min_size = (280.0, 220.0)

    def __init__(self, designer: "Designer", place: str, *, size: Optional[Tuple[float, float]] = None,
                 position: Optional[Tuple[float, float]] = None) -> None:
        self.designer = designer
        self.app = designer
        self.place = place
        self.size = size or WINDOW_SIZE
        self.frame = designer.frame
        if position is not None:
            self.position = position
        #: What marks this window as the one in use (menus, dialogs and toasts open there).
        self.key = Pane(window=self)
        self.title = self.window_title

    @property
    def scale(self) -> float:  # type: ignore[override]
        """Panel windows follow the designer's interface scale."""
        return self.designer.scale

    @scale.setter
    def scale(self, _value: float) -> None:
        pass

    def window_title(self) -> str:
        """The panel in front, then "Pyzed Design"."""
        shown = self.designer.layout.shown(self.place, self.designer)
        return f"{shown.title if shown is not None else tr('Panels')} — Pyzed Design"

    def view(self) -> Any:
        return self.designer.dock_windows.view(self)

    def on_close(self) -> None:
        """Closing the window keeps its panels: they go back to their docks."""
        self.designer.dock_windows.closed(self.place)


class PanelDrag:
    """A panel tab being dragged: which panel, from which place, and the tab row and index under the pointer."""

    __slots__ = ("panel", "place", "over")

    def __init__(self, panel: str, place: str) -> None:
        self.panel, self.place = panel, place
        self.over: Optional[Tuple[str, int]] = None


class DockWindows:
    """The panel windows of the designer, the panel tab drags and the work layouts."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.open: Dict[str, DockWindow] = {}
        self.drag: Optional[PanelDrag] = None

    @property
    def layout(self) -> DockLayout:
        return self.d.layout

    # -- windows ----------------------------------------------------------------
    def grab_offset(self) -> Tuple[float, float]:
        """Where the pointer ends up inside a new panel window: over its first tab."""
        style = ui_frame.resolve(self.d.frame)
        return GRAB_OFFSET[0], GRAB_OFFSET[1] + (ui_frame.HEIGHTS[style] if style else 0.0)

    def _open(self, place: str, screen: Optional[Tuple[float, float]] = None) -> Any:
        saved = self.layout.windows.get(place, {})
        size = saved.get("size")
        position = saved.get("position")
        if screen is not None:
            dx, dy = self.grab_offset()
            position = (screen[0] - dx, screen[1] - dy)
        window = DockWindow(self.d, place, size=tuple(size) if size else None,
                            position=tuple(position) if position else None)
        self.open[place] = window
        return window.open()

    def sync(self, screen: Optional[Tuple[float, float]] = None) -> List[Any]:
        """Opens a window for each panel window place in the layout and closes those with no panel left.

        A new window opens under ``screen`` (the pointer on the screen) when it is given.
        """
        places = self.layout.window_places()
        commands: List[Any] = []
        for place in [p for p in self.open if p not in places]:
            window = self.open.pop(place)
            if window.is_open:
                commands.append(window.close())
        for place in places:
            if place not in self.open:
                commands.append(self._open(place, screen))
        return commands

    def restore(self) -> List[Any]:
        """Opens the panel windows saved with the layout (when the designer starts)."""
        return self.sync()

    def remember(self) -> None:
        """Records the size and screen position of each open panel window in the layout."""
        for place, window in self.open.items():
            entry = self.layout.windows.setdefault(place, {})
            size = window.window_size or window.size
            entry["size"] = [float(size[0]), float(size[1])]
            if window.window_position is not None:
                entry["position"] = [float(window.window_position[0]), float(window.window_position[1])]

    def _changed(self, screen: Optional[Tuple[float, float]] = None) -> Any:
        commands = self.sync(screen)
        self.d._save_layout()
        return commands or None

    def move_to(self, panel: str, place: str, before: Optional[str] = None,
                screen: Optional[Tuple[float, float]] = None) -> Any:
        """Moves ``panel`` to ``place`` (a dock or a panel window, before the panel ``before`` there), opening
        or closing panel windows as needed."""
        self.layout.move(panel, place, before)
        commands = self._changed(screen) or []
        window = self.open.get(place)
        if window is not None and window.is_open:
            commands.append(_core.Command.focus_window(window))
        return commands or None

    def detach(self, panel: str, screen: Optional[Tuple[float, float]] = None) -> Any:
        """Opens ``panel`` in a window of its own (under the pointer at ``screen`` when given).

        A panel that is already alone in its window just moves that window there.
        """
        source = self.layout.docks[panel]
        if is_window(source) and len(self.layout.all_in(source)) == 1:
            window = self.open.get(source)
            if screen is None or window is None:
                return None
            dx, dy = self.grab_offset()
            return _core.Command.move_window(screen[0] - dx, screen[1] - dy, window)
        self.layout.menu = None
        return self.move_to(panel, self.layout.new_window(), screen=screen)

    def dock_back(self, place: str) -> Any:
        """Sends every panel of the panel window ``place`` back to its dock and closes the window."""
        self.layout.send_home(place)
        return self._changed()

    def closed(self, place: str) -> None:
        """The panel window ``place`` is closing: its panels go back to their docks."""
        self.open.pop(place, None)
        self.layout.send_home(place)
        self.d._save_layout()

    def reveal(self, panel: str) -> Any:
        """Shows ``panel`` in front of its place; a panel window is opened if needed and brought to the front."""
        place = self.layout.show(panel)
        if not is_window(place):
            return None
        commands = self.sync()
        window = self.open.get(place)
        if window is not None:
            commands.append(_core.Command.focus_window(window))
        return commands or None

    # -- work layouts -----------------------------------------------------------
    def names(self) -> List[str]:
        """The built-in work layouts, then the saved ones."""
        return list(docks.PRESETS) + [n for n in self.d.prefs.layouts if n not in docks.PRESETS]

    def use(self, name: str) -> Any:
        """Switches to the work layout ``name`` (built in or saved)."""
        saved = self.d.prefs.layouts.get(name)
        if saved is not None:
            layout = DockLayout.from_snapshot(saved)
        elif name in docks.PRESETS:
            layout = docks.preset(name)
        else:
            return None
        self.d.layout = layout
        self.d.prefs.layout_name = name
        return self._changed()

    def save_as(self, name: str) -> bool:
        """Saves the current arrangement as the work layout ``name`` (replacing one with that name)."""
        name = name.strip()
        if not name:
            return False
        self.remember()
        self.d.prefs.layouts[name] = self.layout.snapshot()
        self.d.prefs.layout_name = name
        self.d._save_layout()
        return True

    def delete(self, name: str) -> None:
        """Forgets the saved work layout ``name`` (the built-in ones cannot be deleted)."""
        if self.d.prefs.layouts.pop(name, None) is not None:
            if self.d.prefs.layout_name == name:
                self.d.prefs.layout_name = ""
            self.d._save_layout()

    # -- dragging tabs ----------------------------------------------------------
    def start_drag(self, place: str, panel: str) -> None:
        """A panel tab started moving."""
        self.drag = PanelDrag(panel, place)
        self.layout.menu = None

    def drag_over(self, place: str, index: Optional[int]) -> None:
        """The dragged tab is over the tab row of ``place`` at the insertion point ``index`` (``None``: it left
        that row)."""
        drag = self.drag
        if drag is None:
            return
        if index is not None:
            drag.over = (place, index)
        elif drag.over is not None and drag.over[0] == place:
            drag.over = None

    def _host_rect(self, place: str) -> Optional[Tuple[float, float, float, float]]:
        """Where the window that shows ``place`` (a dock or "main": the main window) is on the screen:
        (x, y, width, height), if the platform says."""
        host: Any = self.open.get(place) if is_window(place) else self.d
        if host is None or host.window_position is None:
            return None
        width, height = host.window_size or host.size
        return host.window_position[0], host.window_position[1], width, height

    def dock_rects(self) -> Dict[str, Tuple[float, float, float, float]]:
        """The drop zone of each dock in the main window: (x, y, width, height). A closed or thin dock still
        gets a band along its edge."""
        d, layout = self.d, self.layout
        width, height = d.window_size or d.size
        from .app import TITLE_HEIGHT

        top = TITLE_HEIGHT
        bottom = height - (STATUS_HEIGHT if d.prefs.show_status_bar else 0.0)

        def extent(dock: str) -> float:
            return max(layout.sizes[dock] if d.dock_visible(dock) else 0.0, EDGE)

        left, right = extent("left"), extent("right")
        rects = {
            "left": (0.0, top, left, bottom - top),
            "right": (width - right, top, right, bottom - top),
            "bottom": (left, bottom - extent("bottom"), width - left - right, extent("bottom")),
        }
        if d.dock_visible("top"):
            rects["top"] = (left, top, width - left - right, layout.sizes["top"])
        return rects

    def dock_at(self, x: float, y: float) -> Optional[str]:
        """The dock whose drop zone holds the point (``x``, ``y``) of the main window, if any."""
        for dock, (rx, ry, rw, rh) in self.dock_rects().items():
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return dock
        return None

    def window_at(self, screen: Tuple[float, float], exclude: str) -> Optional[str]:
        """The panel window under the screen point ``screen`` (not ``exclude``)."""
        for place in self.open:
            rect = self._host_rect(place)
            if place != exclude and rect is not None and _inside(screen, rect):
                return place
        return None

    def drop(self, place: str, panel: str, event: Any) -> Any:
        """The dragged tab was released: reorders it, docks it where it was dropped, stacks it on a panel
        window, or opens it in a new window."""
        drag, self.drag = self.drag, None
        if drag is None or drag.panel != panel:
            return None
        layout = self.layout
        if drag.over is not None:  # on a tab row: before the tab at that index
            target, index = drag.over
            row = [p.id for p in layout.panels_in(target, self.d)]
            before = row[index] if index < len(row) else None
            if target == layout.docks[panel] and panel in (before, row[index - 1] if index > 0 else None):
                return None  # dropped where it already is
            return self.move_to(panel, target, before)
        x, y = getattr(event, "window_x", 0.0), getattr(event, "window_y", 0.0)
        host: Any = self.open.get(place) if is_window(place) else self.d
        width, height = (host.window_size or host.size) if host is not None else (0.0, 0.0)
        if 0 <= x < width and 0 <= y < height:  # inside its own window
            if is_window(place):
                return None
            target = self.dock_at(x, y)
            return self.move_to(panel, target) if target is not None and target != place else None
        screen = getattr(event, "screen", None)
        if screen is not None:
            main = self._host_rect("main")
            if main is not None and _inside(screen, main):
                target = self.dock_at(screen[0] - main[0], screen[1] - main[1]) or layout.home.get(panel, "left")
                return self.move_to(panel, target)
            other = self.window_at(screen, place)
            if other is not None:
                return self.move_to(panel, other)
        return self.detach(panel, screen)

    # -- view -------------------------------------------------------------------
    def tab_bar(self, place: str, tabs: List[Any], active: str, end: List[Any], t: Any) -> Any:
        """The tab row of ``place``: its tabs select, reorder and move panels."""
        drag = self.drag
        dragging = None if drag is None else drag.panel if drag.place == place else ""
        over = drag.over if drag is not None else None
        return ui.tab_bar(
            tabs, active,
            on_select=self.d.show_panel,
            on_drag=lambda panel: self.start_drag(place, panel),
            on_drop=lambda panel, event: self.drop(place, panel, event),
            on_drag_over=lambda index: self.drag_over(place, index),
            dragging=dragging,
            drop_index=over[1] if over is not None and over[0] == place else None,
            end=end, height=TAB_HEIGHT, theme=t,
        )

    def drop_hint(self, t: Any) -> Any:
        """Over the main window while a panel tab from it is dragged: the dock it would go to, highlighted.
        Always a layer (an empty one when idle), so starting a drag does not change the view's shape."""
        drag = self.drag
        target = None
        if drag is not None and not is_window(drag.place) and drag.over is None:
            target = self.dock_at(*self.d.window_pointer)
        if target is None or target == drag.place:  # type: ignore[union-attr]
            return _core.space(width="fill", height="fill")
        x, y, w, h = self.dock_rects()[target]
        zone = _core.container(width=max(w, 1), height=max(h, 1), bg=_alpha(t.accent, 0.14),
                               border_color=t.accent, border_width=2, radius=t.radius)
        return _core.stack([_core.pin(zone, x=x, y=y)], width="fill", height="fill")

    def view(self, window: DockWindow) -> Any:
        """The whole view of a panel window: its panels' tabs and the panel in front."""
        d = self.d
        t = d.theme_obj
        body = docks.dock_view(d, window.place, t)
        if body is None:
            names = ", ".join(docks.PANELS[p].title for p in self.layout.all_in(window.place))
            body = ui.empty_state(tr("Nothing to show yet"), names, icon="panels-top-left", theme=t)
        body = _core.container(body, width="fill", height="fill", bg=t.panel)
        return d.window_overlays(body, window.key, t)


def _inside(point: Tuple[float, float], rect: Tuple[float, float, float, float]) -> bool:
    x, y, w, h = rect
    return x <= point[0] < x + w and y <= point[1] < y + h


def _alpha(color: Any, alpha: float) -> Any:
    if isinstance(color, str) and color.startswith("#") and len(color) in (7, 9):
        return color[:7] + f"{round(alpha * 255):02x}"
    return color
