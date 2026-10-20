"""Moving tabs anywhere: dragging document and panel tabs between places, panel windows and work layouts.

Every tab area of the designer (the main window's center, each dock and each window of its own)
takes any tab: a form, a component, the code editor, the console, the properties... Drag a tab
along its row to reorder it, onto another row to stack it there, over a dock or the center of
the main window to move it there (the place it would go to lights up, and a copy of the tab
follows the pointer), or out of the window to open it in a window of its own; dragging a tab onto
another window stacks it among that window's tabs. **New window** in a panel's menu does the
same without dragging. Closing a window sends its documents to the main window and its panels
back to the docks they came from.

Where every panel is, the dock sizes and the panel windows' size and position are saved with
the preferences and restored on the next start. **Work layouts** keep several of those
arrangements by name (a few come built in, see ``docks.PRESETS``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import alpha
from . import docks
from .docks import DOCKS, PANELS, DockLayout, is_window, tab_height
from .windows import MAIN, PANEL_WINDOW_SIZE, Pane

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: How far into the window a dock's drop zone reaches when the dock is closed or thin.
EDGE = 140.0
#: Height of the status bar under the docks.
STATUS_HEIGHT = 24.0


class TabDrag:
    """A tab being dragged: from which place, which tab (a document's index there, or a panel id) and the
    tab row and insertion index under the pointer."""

    __slots__ = ("place", "key", "over")

    def __init__(self, place: str, key: str) -> None:
        self.place, self.key = place, key
        self.over: Optional[Tuple[str, int]] = None

    @property
    def panel(self) -> Optional[str]:
        """The dragged panel's id (``None`` when a document is dragged)."""
        return self.key if self.key in PANELS else None


class DockWindows:
    """The tab drags between places, the windows that hold only panels and the work layouts."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.drag: Optional[TabDrag] = None

    @property
    def layout(self) -> DockLayout:
        return self.d.layout

    @property
    def open(self) -> Dict[str, Any]:
        """The windows of their own that are in use: place -> window."""
        return {pane.place: pane.window for pane in self.d.panes.windows() if pane.window is not None}

    # -- windows ----------------------------------------------------------------
    def sync(self, screen: Optional[Tuple[float, float]] = None) -> List[Any]:
        """Opens a window for each place of the layout that holds panels and has none yet, and closes the
        windows left with no document and no panel.

        A new window opens under ``screen`` (the pointer on the screen) when it is given.
        """
        panes = self.d.panes
        places = self.layout.window_places()
        commands: List[Any] = []
        for pane in panes.windows():
            if not pane.docs and pane.place not in places:
                panes.panes.remove(pane)
                window, pane.window = pane.window, None
                if window is not None and window.is_open:
                    commands.append(window.close())
        for place in places:
            if panes.at(place) is None:
                saved = self.layout.windows.get(place, {})
                size, position = saved.get("size"), saved.get("position")
                pane = panes.new_window(tuple(size) if size else PANEL_WINDOW_SIZE, screen,
                                        tuple(position) if position else None, place=place)
                commands.append(pane.window.open())
        return commands

    def restore(self) -> List[Any]:
        """Opens the panel windows saved with the layout (when the designer starts)."""
        return self.sync()

    def remember(self) -> None:
        """Records the size and screen position of each window that holds panels in the layout."""
        used = set(self.layout.window_places())
        for place, window in self.open.items():
            if place not in used:
                continue
            entry = self.layout.windows.setdefault(place, {})
            size = window.window_size or window.size
            entry["size"] = [float(size[0]), float(size[1])]
            if window.window_position is not None:
                entry["position"] = [float(window.window_position[0]), float(window.window_position[1])]

    def _changed(self, screen: Optional[Tuple[float, float]] = None) -> Any:
        commands = self.sync(screen)
        self.d._save_layout()
        return commands or None

    def _focus(self, place: str) -> Optional[Any]:
        pane = self.d.panes.at(place)
        window = pane.window if pane is not None else None
        return _core.Command.focus_window(window) if window is not None and window.is_open else None

    def move_to(self, panel: str, place: str, before: Optional[str] = None,
                screen: Optional[Tuple[float, float]] = None) -> Any:
        """Moves ``panel`` to ``place`` (a dock, the center or a window, before the panel ``before`` there) and
        shows it in front there, opening or closing windows as needed."""
        self.layout.move(panel, place, before)
        pane = self.d.panes.at(place)
        if pane is not None:
            pane.front = panel
        commands = self._changed(screen) or []
        focus = self._focus(place)
        if focus is not None:
            commands.append(focus)
        return commands or None

    def detach(self, panel: str, screen: Optional[Tuple[float, float]] = None) -> Any:
        """Opens ``panel`` in a window of its own (under the pointer at ``screen`` when given).

        A panel that is already alone in its window just moves that window there.
        """
        source = self.layout.docks[panel]
        pane = self.d.panes.at(source)
        if is_window(source) and len(self.layout.all_in(source)) == 1 and not (pane is not None and pane.docs):
            if screen is None or pane is None or pane.window is None:
                return None
            dx, dy = self.d.panes.grab_offset()
            return _core.Command.move_window(screen[0] - dx, screen[1] - dy, pane.window)
        self.layout.menu = None
        return self.move_to(panel, self.d.panes.new_place(), screen=screen)

    def dock_back(self, place: str) -> Any:
        """Closes the window ``place``: its documents go to the main window and its panels to their docks."""
        pane = self.d.panes.at(place)
        if pane is None or pane.window is None:
            self.layout.send_home(place)
            return self._changed()
        window = pane.window
        self.d.panes.closed(pane)
        self.d._save_layout()
        return window.close() if window.is_open else None

    def reveal(self, panel: str) -> Any:
        """Shows ``panel`` in front of its place; its window is opened if needed and brought to the front."""
        place = self.layout.show(panel)
        pane = self.d.panes.at(place)
        if pane is not None:
            pane.front = panel
        if not is_window(place):
            return None
        commands = self.sync()
        focus = self._focus(place)
        if focus is not None:
            commands.append(focus)
        return commands or None

    def send_back(self, place: str, panel: str) -> Any:
        """The × of a panel tab outside the docks: the panel goes back to the dock it came from."""
        home = self.layout.home.get(panel, PANELS[panel].dock)
        return self.move_to(panel, home) if home != place else None

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
        for pane in self.d.panes.every():
            pane.front = None
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
    def start_drag(self, place: str, key: str) -> None:
        """A tab started moving (documents and panels move; Reference and What's new stay put)."""
        if not (key.isdigit() or key in PANELS):
            return
        self.drag = TabDrag(place, key)
        self.layout.menu = None
        pane = self.d.panes.at(place)
        self.d.panes.here = pane if pane is not None else self.d.panes.main

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

    def _window_of(self, place: str) -> Pane:
        """The pane of the window that shows ``place`` (the main window's for the center and the docks)."""
        pane = self.d.panes.at(place)
        return pane if pane is not None and pane.window is not None else self.d.panes.main

    def _host_rect(self, pane: Pane) -> Optional[Tuple[float, float, float, float]]:
        """Where the window of ``pane`` is on the screen: (x, y, width, height), if the platform says."""
        host = self.d.panes.host(pane)
        if host is None or host.window_position is None:
            return None
        width, height = host.window_size or host.size
        return host.window_position[0], host.window_position[1], width, height

    def zone_rects(self) -> Dict[str, Tuple[float, float, float, float]]:
        """Where a tab dropped in the main window goes: each dock's zone and the center's, as (x, y, width,
        height). A closed or thin dock still gets a band along its edge."""
        d, layout = self.d, self.layout
        width, height = d.window_size or d.size
        from .app import TITLE_HEIGHT

        top = TITLE_HEIGHT
        bottom = height - (STATUS_HEIGHT if d.prefs.show_status_bar else 0.0)

        def extent(dock: str) -> float:
            return max(layout.sizes[dock] if d.dock_visible(dock) else 0.0, EDGE)

        left, right = extent("left"), extent("right")
        low = extent("bottom")
        high = layout.sizes["top"] if d.dock_visible("top") else 0.0
        rects = {
            "left": (0.0, top, left, bottom - top),
            "right": (width - right, top, right, bottom - top),
            "bottom": (left, bottom - low, width - left - right, low),
        }
        if high:
            rects["top"] = (left, top, width - left - right, high)
        rects[MAIN] = (left, top + high, width - left - right, bottom - low - top - high)
        return rects

    def zone_at(self, x: float, y: float) -> Optional[str]:
        """The place whose drop zone holds the point (``x``, ``y``) of the main window, if any."""
        for place, (rx, ry, rw, rh) in self.zone_rects().items():
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return place
        return None

    def dock_at(self, x: float, y: float) -> Optional[str]:
        """The dock (not the center) whose drop zone holds the point (``x``, ``y``) of the main window."""
        place = self.zone_at(x, y)
        return place if place in DOCKS else None

    def window_at(self, screen: Tuple[float, float], exclude: Pane) -> Optional[Pane]:
        """The pane of the window under the screen point ``screen`` (not the window of ``exclude``)."""
        for pane in self.d.panes.panes:
            rect = self._host_rect(pane)
            if pane is not exclude and rect is not None and _inside(screen, rect):
                return pane
        return None

    def _row(self, place: str) -> List[str]:
        """The ids of the tabs of ``place``, in order: its documents first, then its panels."""
        pane = self.d.panes.at(place)
        keys = [str(i) for i in range(len(pane.docs))] if pane is not None else []
        return keys + [p.id for p in self.layout.panels_in(place, self.d)]

    def move_tab(self, drag: TabDrag, place: str, index: Optional[int] = None) -> Any:
        """Moves the dragged tab to ``place`` (at the insertion ``index`` of its tab row, else last there)."""
        panes = self.d.panes
        if drag.panel is not None:
            before = None
            if index is not None:
                row = self._row(place)
                before = next((key for key in row[index:] if key in PANELS), None)
                if place == drag.place:
                    panels = [key for key in row if key in PANELS]
                    at = panels.index(drag.panel)
                    if before == drag.panel or (before is None and at == len(panels) - 1) or \
                            (before is not None and panels.index(before) == at + 1):
                        return None  # dropped where it already is
            elif place == drag.place:
                return None
            return self.move_to(drag.panel, place, before)
        source, target = panes.at(drag.place), panes.at(place)
        if source is None or target is None:
            return None
        at = None if index is None else min(index, len(target.docs))
        if target is source:
            return panes.reorder(source, int(drag.key), at) if at is not None else None
        commands = [panes.move(source, int(drag.key), target, at), self._focus(place)]
        return [c for c in commands if c is not None] or None

    def drop(self, place: str, key: str, event: Any) -> Any:
        """The dragged tab was released: reorders it, moves it to the place or window it was dropped on, or
        opens it in a new window."""
        drag, self.drag = self.drag, None
        if drag is None or drag.key != key or drag.place != place:
            return None
        if drag.over is not None:  # on a tab row: at that insertion point
            return self.move_tab(drag, *drag.over)
        own = self._window_of(place)
        x, y = getattr(event, "window_x", 0.0), getattr(event, "window_y", 0.0)
        width, height = self.d.panes.window_size(own)
        if 0 <= x < width and 0 <= y < height:  # inside its own window
            if own is not self.d.panes.main:
                return None
            target = self.zone_at(x, y)
            return self.move_tab(drag, target) if target is not None and target != place else None
        screen = getattr(event, "screen", None)
        if screen is not None:
            main = self._host_rect(self.d.panes.main)
            if main is not None and _inside(screen, main):
                target = self.zone_at(screen[0] - main[0], screen[1] - main[1])
                if target is None:
                    target = self.layout.home.get(drag.panel, "left") if drag.panel else MAIN
                return self.move_tab(drag, target)
            other = self.window_at(screen, own)
            if other is not None:
                return self.move_tab(drag, other.place)
        if drag.panel is not None:
            return self.detach(drag.panel, screen)
        source = self.d.panes.at(place)
        return self.d.panes.detach(source, int(key), screen) if source is not None else None

    # -- view -------------------------------------------------------------------
    def tab_bar(self, place: str, shown: tuple, end: List[Any], t: Any) -> Any:
        """The tab row of ``place``: its documents, then its panels. Picking a tab brings it to the front;
        dragging one reorders it, moves it to another place or takes it out of the window."""
        d = self.d
        pane = d.panes.at(place)
        tabs: List[Any] = []
        active: Optional[str] = None
        if pane is not None and pane.docs:
            tabs, active, label = d.doc_tab_items(pane, t)
            if shown[0] == "doc" and label is not None:
                end = [label, *end]
        panels = self.layout.panels_in(place, d)
        front_panel = shown[1].id if shown[0] == "panel" else None
        # When the titles do not fit the dock (three panels on the left), the tabs not shown keep only their icon.
        needed = sum(len(tab.label) * 6.8 + 62 for tab in tabs) + sum(len(p.title) * 6.8 + 62 for p in panels)
        compact = place in ("left", "right") and needed > self.layout.sizes.get(place, 0)
        tabs += [ui.Tab(p.id, "" if compact and p.id != front_panel else p.title, icon=p.icon) for p in panels]
        if front_panel is not None:
            active = front_panel
        closable = pane is not None and (bool(pane.docs) or not pane.docked)

        def select(key: str) -> Any:
            if key in PANELS:
                return d.show_panel(key)
            return d.panes.select(pane, key) if pane is not None else None

        def close(key: str) -> Any:
            if key in PANELS:
                return self.send_back(place, key)
            return d.panes.close(pane, key) if pane is not None else None

        drag = self.drag
        dragging = None if drag is None else drag.key if drag.place == place else ""
        over = drag.over if drag is not None else None
        return ui.tab_bar(
            tabs, active,
            on_select=select,
            on_close=close if closable else None,
            on_drag=lambda key: self.start_drag(place, key),
            on_drop=lambda key, event: self.drop(place, key, event),
            on_drag_over=lambda index: self.drag_over(place, index),
            dragging=dragging,
            drop_index=over[1] if over is not None and over[0] == place else None,
            end=end, height=tab_height(place), theme=t,
        )

    def ghost(self, t: Any) -> Optional[Any]:
        """A copy of the dragged tab, to follow the pointer."""
        drag = self.drag
        if drag is None:
            return None
        if drag.panel is not None:
            icon, label = PANELS[drag.panel].icon, PANELS[drag.panel].title
        else:
            pane = self.d.panes.at(drag.place)
            index = int(drag.key)
            if pane is None or not 0 <= index < len(pane.docs):
                return None
            icon, label = self.d.doc_tab_label(pane.docs[index])
        content = _core.row([_icon(icon, size=14, color=t.accent), _core.text(label, size=13, color=t.text, wrap=False)],
                            spacing=6, align="center")
        return _core.container(content, padding=(6, 12), bg=t.tab_active, border_color=t.accent, border_width=1,
                               radius=t.radius, shadow=(t.shadow, (0, 4), 12))

    def drag_layer(self, pane: Pane, t: Any) -> Any:
        """Over the window of ``pane`` while a tab is dragged from it: the place it would go to, highlighted,
        and a copy of the tab under the pointer. Always a layer (an empty one when idle), so starting a drag
        does not change the view's shape."""
        drag = self.drag
        idle = _core.space(width="fill", height="fill")
        if drag is None or self._window_of(drag.place) is not pane:
            return idle
        layers: List[Any] = []
        px, py = self.d.window_pointer
        if pane is self.d.panes.main and drag.over is None:
            target = self.zone_at(px, py)
            if target is not None and target != drag.place:
                x, y, w, h = self.zone_rects()[target]
                zone = _core.container(width=max(w - 8, 1), height=max(h - 8, 1), bg=alpha(t.accent, 0.14),
                                       border_color=t.accent, border_width=2, radius=t.radius)
                layers.append(_core.pin(zone, x=x + 4, y=y + 4))
        ghost = self.ghost(t)
        if ghost is not None:
            layers.append(_core.pin(ghost, x=px + 12, y=py + 8))
        return _core.stack(layers, width="fill", height="fill") if layers else idle


def _inside(point: Tuple[float, float], rect: Tuple[float, float, float, float]) -> bool:
    x, y, w, h = rect
    return x <= point[0] < x + w and y <= point[1] < y + h
