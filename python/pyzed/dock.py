"""A Zed-style dock: a center area with panels docked to its sides.

Panels can be resized by dragging their inner edge and moved to another side by
dragging their tab onto one of the drop zones that appear around the center, or from
the tab's right-click menu::

    pz.Dock(
        center=editor,
        panels=[
            pz.DockPanel("project", "Project", project_tree, icon="folder", side="left"),
            pz.DockPanel("outline", "Outline", outline, icon="list-tree", side="left"),
            pz.DockPanel("terminal", "Terminal", terminal, icon="terminal", side="bottom"),
        ],
        on_layout=lambda e: settings.save("dock", e.value),
    )

The dock remembers where each panel is, which tab is active and how big each side is.
``on_layout`` receives that as a plain dict whenever it changes; pass it back as
``layout=`` to restore it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import _core
from .component import Component
from .icons import icon as _icon
from .theme import current as _current_theme

SIDES = ("left", "right", "bottom", "top")
SIDE_LABELS = {"left": "Dock Left", "right": "Dock Right", "bottom": "Dock Bottom", "top": "Dock Top"}
SIDE_ICONS = {"left": "panel-left", "right": "panel-right", "bottom": "panel-bottom", "top": "panel-top"}
DEFAULT_SIZES = {"left": 240, "right": 320, "bottom": 220, "top": 180}
# The edge of each side's panel that carries the resize handle (the one facing the center).
INNER_EDGE = {"left": "right", "right": "left", "bottom": "top", "top": "bottom"}


class DockPanel:
    """A panel for ``pz.Dock``: a stable ``id``, a tab ``title``, the ``content`` widget,
    an optional ``icon`` and the ``side`` it starts on ("left", "right", "bottom" or "top")."""

    __slots__ = ("id", "title", "content", "icon", "side")

    def __init__(self, id: str, title: str, content: Any, *, icon: Optional[str] = None, side: str = "left"):
        if side not in SIDES:
            raise ValueError(f"side must be one of {', '.join(SIDES)}")
        self.id = id
        self.title = title
        self.content = content
        self.icon = icon
        self.side = side

    def __repr__(self) -> str:
        return f"<DockPanel {self.id!r} side={self.side!r}>"


class Dock(Component):
    """A center area with movable, resizable panels on its sides (like Zed's docks)."""

    center: Any = None
    panels: list = ()
    layout: dict = None
    events = {"layout": "Panels were moved, resized or switched (``event.value`` is the layout dict)."}
    icon = "layout-dashboard"
    category = "Layout"
    designer = False

    def setup(self) -> None:
        saved = dict(self.layout or {})
        self.positions: Dict[str, str] = dict(saved.get("positions", {}))
        self.sizes: Dict[str, float] = {**DEFAULT_SIZES, **saved.get("sizes", {})}
        self.active: Dict[str, str] = dict(saved.get("active", {}))
        self.hidden: set = set(saved.get("hidden", ()))
        self.dragging: Optional[str] = None
        self._dropped: Optional[str] = None
        self.hover_zone: Optional[str] = None
        self.menu: Optional[str] = None

    # -- state ------------------------------------------------------------------
    def side_of(self, panel: DockPanel) -> str:
        side = self.positions.get(panel.id, panel.side)
        return side if side in SIDES else panel.side

    def groups(self) -> Dict[str, List[DockPanel]]:
        out: Dict[str, List[DockPanel]] = {side: [] for side in SIDES}
        for panel in self.panels:
            out[self.side_of(panel)].append(panel)
        return out

    def snapshot(self) -> dict:
        return {
            "positions": dict(self.positions),
            "sizes": dict(self.sizes),
            "active": dict(self.active),
            "hidden": sorted(self.hidden),
        }

    def changed(self) -> Any:
        return self.emit("layout", self.snapshot())

    def move(self, panel_id: str, side: str) -> Any:
        """Docks a panel on another side and makes it the active tab there."""
        if side not in SIDES:
            raise ValueError(f"side must be one of {', '.join(SIDES)}")
        self.positions[panel_id] = side
        self.active[side] = panel_id
        self.hidden.discard(side)
        self.menu = None
        return self.changed()

    def select(self, side: str, panel_id: str) -> Any:
        self.active[side] = panel_id
        return self.changed()

    def toggle(self, side: str) -> Any:
        """Shows or hides a whole side."""
        self.hidden ^= {side}
        return self.changed()

    def resized(self, side: str, size: float) -> Any:
        self.sizes[side] = size
        return self.changed()

    # -- drag and drop ----------------------------------------------------------
    def start_drag(self, panel_id: str) -> None:
        self.dragging = panel_id
        self.menu = None

    def end_drag(self) -> None:
        # The drop zone's mouse_up may arrive after this; remember what was dragged.
        self._dropped, self.dragging, self.hover_zone = self.dragging, None, None

    def drop(self, side: str) -> Any:
        panel_id = self.dragging or self._dropped
        self.dragging = self._dropped = self.hover_zone = None
        if panel_id is None:
            return None
        return self.move(panel_id, side)

    # -- view -------------------------------------------------------------------
    def tab(self, panel: DockPanel, side: str, active: bool, t: Any) -> Any:
        label = _core.row(
            [
                _icon(panel.icon, size=13, color=t.icon if active else t.icon_muted) if panel.icon else None,
                _core.text(panel.title, size=12.5, color=t.text if active else t.text_muted, wrap=False),
            ],
            spacing=5,
            align="center",
        )
        box = _core.container(
            label,
            padding=(4, 8),
            radius=t.radius,
            bg=t.element_selected if active else None,
            height=26,
            align_y="center",
        )
        return box.on(
            click=lambda: self.select(side, panel.id),
            right_click=lambda: setattr(self, "menu", panel.id),
            drag_start=lambda: self.start_drag(panel.id),
            drag_end=self.end_drag,
            cursor="grabbing" if self.dragging == panel.id else "pointer",
        )

    def move_menu(self, panel: DockPanel, side: str, t: Any) -> Any:
        options = [
            _core.button(
                _core.row([_icon(SIDE_ICONS[s], size=13, color=t.icon_muted), _core.text(SIDE_LABELS[s], size=12.5)],
                          spacing=6, align="center"),
                on_press=lambda s=s: self.move(panel.id, s),
                padding=(4, 8),
                width="fill",
                hover_bg=t.element_hover,
                color=t.text,
                radius=t.radius_sm,
            )
            for s in SIDES
            if s != side
        ]
        menu = _core.container(
            _core.column(options, spacing=2, width=150),
            padding=4,
            bg=t.elevated,
            border_color=t.border,
            border_width=1,
            radius=t.radius,
        )
        return menu.on(mouse_leave=lambda: setattr(self, "menu", None))

    def side_view(self, side: str, panels: List[DockPanel], t: Any) -> Any:
        active_id = self.active.get(side)
        if active_id not in {p.id for p in panels}:
            active_id = panels[0].id
        current = next(p for p in panels if p.id == active_id)
        tabs = [self.tab(p, side, p.id == active_id, t) for p in panels]
        header = _core.container(
            _core.row(tabs, spacing=2, align="center"),
            padding=(3, 6),
            width="fill",
            height=32,
            align_y="center",
        )
        menu_panel = next((p for p in panels if p.id == self.menu), None)
        if menu_panel is not None:
            header = _core.column([header, _core.container(self.move_menu(menu_panel, side, t), padding=(0, 6, 4, 6))])
        body = _core.container(
            _core.column([header, _core.container(current.content, width="fill", height="fill")],
                         width="fill", height="fill"),
            width="fill",
            height="fill",
            bg=t.panel,
            clip=True,
        )
        return _core.resizable(
            body,
            edge=INNER_EDGE[side],
            size=self.sizes.get(side, DEFAULT_SIZES[side]),
            min_size=120 if side in ("left", "right") else 80,
            on_resize=lambda size: self.resized(side, size),
            color=t.border,
            hover_color=t.accent,
        )

    def drop_zones(self, t: Any) -> Any:
        def zone(side: str, **size: Any) -> Any:
            hovered = self.hover_zone == side
            box = _core.container(
                _core.column(
                    [_icon(SIDE_ICONS[side], size=18, color=t.accent if hovered else t.icon_muted),
                     _core.text(SIDE_LABELS[side], size=12, color=t.text if hovered else t.text_muted)],
                    spacing=4,
                    align="center",
                ),
                center=True,
                bg=_with_alpha(t.accent, 0.22 if hovered else 0.08),
                border_color=t.accent if hovered else t.border,
                border_width=1,
                radius=t.radius,
                **size,
            )
            return box.on(
                mouse_enter=lambda: setattr(self, "hover_zone", side),
                mouse_leave=lambda: setattr(self, "hover_zone", None) if self.hover_zone == side else None,
                mouse_up=lambda: self.drop(side),
            )

        return _core.container(
            _core.column(
                [
                    zone("top", width="fill", height=56),
                    _core.row([zone("left", width=110, height="fill"), _core.space(width="fill"),
                               zone("right", width=110, height="fill")], spacing=8, height="fill"),
                    zone("bottom", width="fill", height=56),
                ],
                spacing=8,
                width="fill",
                height="fill",
            ),
            padding=16,
            width="fill",
            height="fill",
        )

    def render(self) -> Any:
        t = _current_theme()
        groups = self.groups()
        shown = {s: p for s, p in groups.items() if p and s not in self.hidden}
        center = _core.container(self.center, width="fill", height="fill", clip=True)
        middle = _core.column(
            [
                self.side_view("top", shown["top"], t) if "top" in shown else None,
                center,
                self.side_view("bottom", shown["bottom"], t) if "bottom" in shown else None,
            ],
            width="fill",
            height="fill",
        )
        body = _core.row(
            [
                self.side_view("left", shown["left"], t) if "left" in shown else None,
                middle,
                self.side_view("right", shown["right"], t) if "right" in shown else None,
            ],
            width="fill",
            height="fill",
        )
        # The drop zones always have a layer so the tree (and the tab's drag) survives.
        overlay = self.drop_zones(t) if self.dragging is not None else _core.space()
        return _core.stack([body, overlay], width="fill", height="fill")


def _with_alpha(color: Any, alpha: float) -> Any:
    """``color`` (a "#rrggbb" string or an (r, g, b[, a]) tuple) with a new alpha."""
    if isinstance(color, str) and color.startswith("#") and len(color) in (7, 9):
        return color[:7] + f"{round(alpha * 255):02x}"
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        return (*color[:3], alpha)
    return color
