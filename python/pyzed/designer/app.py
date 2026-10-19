"""Pyzed Design: a Visual Basic / Qt Designer style editor for Pyzed forms, built with Pyzed.

    pyzed design login.pzform        # or: python -m pyzed.designer login.pzform

Pick a component in the toolbox and click (or drag a rectangle) on the form to place
it; drag to move, use the handles to resize, and set its properties on the right.
Double-click a control to write the code of its main event. F5 runs the form in a
new window with all its logic.
"""

from __future__ import annotations

import ast
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .. import _core, ui
from ..app import App
from ..icons import icon as _icon
from ..theme import themes
from . import binding as _binding
from . import code as _code
from . import components as _components
from . import agent_panel, code_panel, dialogs, docks, geometry, panels, preferences, project_panel, surface
from . import commands as _commands
from . import layout as _layout
from . import new as _new
from .console import ConsoleController
from . import locale as _locale
from .locale import tr
from .code_panel import CodeAssist
from .components import Prop
from .document import Document
from .model import SUFFIX
from .project_panel import ProjectController
from .updates import TAB_ID as _NOTES_TAB, UpdateController
from ..i18n import t as _t
from .runtime import FormWindow
from . import scene as _scene
from . import scene_code as _scene_code
from . import scene_panel
from . import telemetry as _telemetry
from ..project import Project
from .. import reference as _reference
from . import help as _help

Rect = Tuple[float, float, float, float]
TITLE_HEIGHT = 34.0
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build"}

#: Files the designer opens: forms and components designed visually.
DOCUMENT_SUFFIXES = (SUFFIX, _scene.SUFFIX)

#: What "New" can create: (label, icon, suffix, factory returning a new document).
NEW_DOCUMENT_KINDS: List[Tuple[str, str, str, Callable[[], Document]]] = [
    ("Form", "app-window", SUFFIX, Document),
    ("Component", "component", _scene.SUFFIX, _scene.new_component),
]


@dataclass
class Drag:
    """A pointer gesture in progress on the design surface."""

    mode: str  # "move" | "resize" | "create" | "band" | "form"
    origin: Tuple[float, float]  # pointer in view coordinates when it started
    start: Tuple[float, float] = (0.0, 0.0)  # pointer in form coordinates when it started
    rects: Dict[str, Rect] = field(default_factory=dict)
    handle: Optional[str] = None
    moved: bool = False
    #: absolute rectangles of ``rects`` when the gesture started (they differ inside containers)
    absolute: Dict[str, Rect] = field(default_factory=dict)


@dataclass
class Carry:
    """Something dragged out of a panel: a component from the toolbox or controls from the outline."""

    kind: str  # "tool" | "outline"
    names: List[str]  # the component type, or the controls being moved
    origin: Tuple[float, float]  # pointer in window coordinates when it started
    moved: bool = False


CONTEXT_MENU_WIDTH = 220
#: The id of the Reference tab in the tab bar.
HELP_TAB = "__reference__"

#: Pixels the pointer must travel before a press in the toolbox or outline becomes a drag.
CARRY_THRESHOLD = 4


@dataclass
class Toast:
    title: str
    message: Optional[str] = None
    kind: str = "info"
    expires: float = 0.0


def _component_registry() -> Dict[str, type]:
    from ..component import _REGISTRY

    return _REGISTRY


class Designer(App):
    """The visual form editor."""

    title = "Pyzed Design"
    size = (1440, 900)
    min_size = (960, 600)

    def __init__(self, path: Optional[Union[str, Path]] = None, *, theme: Any = None,
                 language_servers: bool = True) -> None:
        if path is not None and Path(path).exists():
            self.doc = _scene.open_document(path)
        elif path is not None and Path(path).suffix == _scene.SUFFIX:
            self.doc = _scene.new_component(Path(path).stem, path)
        else:
            self.doc = Document(path=Path(path).with_suffix(SUFFIX) if path else None)
        if theme is not None:
            self.theme = theme
        # tools and gestures
        self.tool: Optional[str] = None
        self.drag: Optional[Drag] = None
        self.pointer: Tuple[float, float] = (0.0, 0.0)
        self.view_pointer: Tuple[float, float] = (0.0, 0.0)
        self.guides: List[Rect] = []
        self.drop_name: Optional[str] = None
        #: the context menu: control name and where it opens, in window coordinates
        self.menu: Optional[Tuple[str, float, float]] = None
        self.window_pointer: Tuple[float, float] = (0.0, 0.0)
        self.carry: Optional[Carry] = None
        self.over_form = False  # the pointer is over the form being designed
        self.color_picker: Optional[Tuple[Optional[str], str]] = None  # (control or None, style key) being picked
        self.picker_at: Tuple[float, float] = (0.0, 0.0)  # window point where the picker was opened
        self.text_editors: set = set()  # "control.prop" lists and tables edited as plain text
        #: outline row under the pointer while carrying, and where it would drop: "before", "inside" or "after"
        self.outline_target: Optional[Tuple[str, str]] = None
        self.hovered_row: Optional[str] = None  # toolbox or outline row under the pointer
        self.focus = "canvas"
        # preferences and view options
        self.prefs = preferences.load()
        self.show_grid = self.prefs.show_grid
        self.snap = self.prefs.snap
        self.smart_guides = self.prefs.smart_guides
        self.show_hidden = self.prefs.show_hidden
        if self.prefs.language:
            _locale.apply(self.prefs.language)
        if theme is None and self.prefs.theme and self.prefs.theme in themes.names():
            self.theme = themes.get(self.prefs.theme)
        self.layout = docks.DockLayout(self.prefs.docks, self.prefs.sizes,
                                       {k: not v for k, v in self.prefs.panels.items()})
        self.app_menu: Optional[str] = None  # the title bar menu that is open: "file", "view" or "help"
        self.new_state: Dict[str, str] = {}
        self.left_ratio = 0.62
        self.toolbox_query = ""
        self.name_buffer = ""
        self.folded: set = set()  # containers folded in the outline
        self.members_open: set = set()  # placed components whose properties and methods the outline lists
        self.collapsed_sections: set = set()  # property groups folded in the Properties panel
        self.motion_preview: Dict[str, int] = {}  # controls whose animations play on the canvas (restart counter)
        self.motion_open: Optional[Tuple[str, int]] = None  # (control, index) of the animation being edited
        self.add_parent: Optional[str] = None  # container the "Add control" picker adds into
        self.picker_query = ""
        self.picker_index = 0
        # code editor: (handler name or "*" for the whole file, text being edited)
        self.editing: Optional[Tuple[str, str]] = None
        self._code_base: Optional[Tuple[Any, str]] = None  # what the code editor's text was last synced with
        self.last_handler: Optional[str] = None
        self.code_error: Optional[str] = None
        self.code_revision = 0
        self.assist = CodeAssist(self, servers=language_servers)
        # the AI agent (Agent panel, inline assist)
        self.agent = agent_panel.AgentController(self)
        # dialogs, messages and the running preview
        self.dialog: Optional[str] = None
        self.dialog_path = ""
        self.pending: Optional[Callable[[], Any]] = None
        self.toasts: List[Toast] = []
        self.preview: Optional[FormWindow] = None
        #: A theme and a language to look at the form in (canvas and Run), without changing the form.
        self.preview_theme: Optional[str] = None
        self.icon_value = ""
        self.icon_pick: Optional[Callable[[str], Any]] = None
        self.preview_language: Optional[str] = None
        self.console = ConsoleController(self)
        # the uv project the form belongs to (Project panel)
        self.projects = ProjectController(self)
        self.updates = UpdateController(self)
        # the built-in reference (Help → Reference): its own tab next to the documents
        self.help = _reference.Browser()
        self.help_open = False
        self.help_active = False
        found = Project.find(path or Path.cwd())
        if found is not None and found.is_pyzed:
            self.projects.attach(found)
        # Designed components (.pzcomp) of the project join the toolbox.
        _scene.discover(found.root if found is not None else Path(path).resolve().parent if path else Path.cwd())
        self.title = self.window_title

    def on_start(self) -> Any:
        """Loads the project's tools and checks for updates when the app starts; returns the commands."""
        return [c for c in (self.projects.load_tools(), *self.updates.on_start()) if c is not None]

    # -- window title ---------------------------------------------------------
    def window_title(self) -> str:
        """Returns the window title: the document's name, after a ``●`` when it has unsaved changes."""
        return f"{'● ' if self.doc.dirty else ''}{self.doc.display_name} — Pyzed Design"

    # -- messages -------------------------------------------------------------
    def notify(self, title: str, message: Optional[str] = None, kind: str = "info", seconds: float = 3.0) -> None:
        """Shows a toast for ``seconds`` (``kind`` is "info", "success", "warning" or "error").

        Only the four most recent toasts are kept.
        """
        self.toasts.append(Toast(title, message, kind, time.monotonic() + seconds))
        del self.toasts[:-4]

    def _expire_toasts(self) -> None:
        now = time.monotonic()
        self.toasts = [t for t in self.toasts if t.expires > now]

    def dismiss_toast(self, toast: Toast) -> None:
        """Removes ``toast`` from the screen (its close button was clicked)."""
        if toast in self.toasts:
            self.toasts.remove(toast)

    def subscriptions(self):
        subs = [_core.every(0.5, self._expire_toasts, key="designer-toasts")] if self.toasts else []
        if self.projects.busy:  # keeps the spinner of a running uv command moving
            subs.append(_core.every(1 / 30, lambda: None, key="designer-busy"))
        if self.updates.status == "downloading":  # redraws the download progress
            subs.append(_core.every(0.2, lambda: None, key="designer-update"))
        if self.agent.active:  # streams the agent's answer and runs its tools on this thread
            subs.append(_core.every(1 / 30, self.agent.poll, key="designer-agent"))
        if self.console.running is not None:  # notices when the running form's window is closed
            subs.append(_core.every(1.0, self.console.poll, key="designer-console"))
        return subs

    # -- selection ------------------------------------------------------------
    def _selection_changed(self) -> None:
        primary = self.doc.primary
        self.name_buffer = primary.name if primary else ""
        self.menu = None
        self.color_picker = None

    def select_form(self) -> None:
        """Clears the selection, so the Properties panel shows the form itself."""
        self.doc.select(None)
        self._selection_changed()

    def select_from_outline(self, name: str) -> None:
        """Selects the control ``name`` from an outline row and gives the keyboard to the canvas."""
        self.doc.select(name)
        self.focus = "canvas"
        self._selection_changed()

    def toggle_section(self, title: str) -> None:
        """Folds or unfolds the property group ``title`` in the Properties panel."""
        self.collapsed_sections ^= {title}

    def toggle_folded(self, name: str) -> None:
        """Folds or unfolds the children of the container ``name`` in the outline."""
        self.folded ^= {name}

    def toggle_members(self, name: str) -> None:
        """Shows or hides the properties and methods of a component placed as ``name`` in the outline."""
        self.members_open ^= {name}

    def open_add_child(self, parent: Optional[str]) -> Any:
        """Shows the component picker to add a control inside ``parent`` (the form when ``None``)."""
        self.add_parent = parent
        self.menu = None
        self.open_dialog_named("add_control")
        return _core.Command.focus(dialogs.PICKER_ID)

    def add_child(self, type_: str) -> None:
        """Adds a ``type_`` control inside the container chosen with ``open_add_child``."""
        doc = self.doc
        parent = doc.form.get(self.add_parent) if self.add_parent else None
        self.dialog = None
        if parent is not None:
            doc.add(type_, 8, 8, snap=self.snap, parent=parent.name)
            self.folded.discard(parent.name)
        else:
            spec = _components.get(type_)
            doc.add(type_, (doc.form.width - spec.size[0]) / 2, (doc.form.height - spec.size[1]) / 2, snap=self.snap)
        self.right_tab = "properties"
        self._selection_changed()

    def set_picker_query(self, text: str) -> None:
        """Filters the component picker or palette by ``text`` and moves the highlight to the first row."""
        self.picker_query = text
        self.picker_index = 0

    def move_out(self, name: str) -> None:
        """Moves the control ``name`` out of its container, into the container's parent."""
        self.doc.move_out(name)

    def wrap(self, type_: str) -> None:
        """Groups the selected controls in a new ``type_`` container (row, column, grid or panel)."""
        if self.doc.wrap(type_) is not None:
            self._selection_changed()

    def set_layout(self, name: str, key: str, value: Any) -> None:
        """Sets the layout option ``key`` of the control ``name`` (whole floats are stored as ints)."""
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        self.doc.set_layout(name, key, value)

    def open_outline_menu(self, name: str) -> None:
        """Right-click in the outline: the control's context menu, where the pointer is."""
        self.doc.select(name)
        self._selection_changed()
        self.menu = (name, *self.window_pointer)

    def pick_tool(self, type_: Optional[str]) -> Callable[[], None]:
        """Returns a callback that picks ``type_`` as the placing tool, or drops it if already picked."""
        def pick() -> None:
            self.tool = None if self.tool == type_ else type_
            self.focus = "canvas"
        return pick

    def set_toolbox_query(self, text: str) -> None:
        """Filters the toolbox by ``text``."""
        self.toolbox_query = text

    # -- pointer gestures on the surface ------------------------------------
    def pointer_moved(self, x: float, y: float) -> None:
        """Pointer over the form, in form coordinates."""
        self.pointer = (x, y)
        if self.carry is not None and self.carry.moved:
            self.drop_name = self._carry_container()

    def window_moved(self, x: float, y: float) -> None:
        """Pointer anywhere in the window, in window coordinates (menus and drags out of panels)."""
        self.window_pointer = (x, y)
        carry = self.carry
        if carry is not None and not carry.moved:
            ox, oy = carry.origin
            carry.moved = abs(x - ox) + abs(y - oy) > CARRY_THRESHOLD

    def enter_form(self) -> None:
        """The pointer entered the form being designed."""
        self.over_form = True

    def exit_form(self) -> None:
        """The pointer left the form being designed: a control carried out of a panel has no drop target."""
        self.over_form = False
        if self.carry is not None:
            self.drop_name = None

    # -- dragging out of the toolbox and the outline ------------------------------
    def press_tool(self, type_: str) -> None:
        """Press on a toolbox component: a click picks it as the tool, a drag drops it on the form."""
        self.focus = "canvas"
        self.menu = None
        self.carry = Carry("tool", [type_], self.window_pointer)

    def press_outline(self, name: str) -> None:
        """Press on an outline row: selects the control and starts a possible drag to reorder it."""
        self.menu = None
        if not self.doc.is_selected(name):
            self.select_from_outline(name)
        self.focus = "canvas"
        names = [n for n in self.doc.selection if not any(self.doc.is_selected(a.name)
                                                           for a in self.doc.form.ancestors(n))]
        self.carry = Carry("outline", names or [name], self.window_pointer)

    def hover_outline(self, name: str, y: float, height: float) -> None:
        """The pointer over an outline row while carrying: before, inside (a container) or after it."""
        if self.carry is None or not self.carry.moved or self.carry.kind != "outline" or name in self.carry.names:
            self.outline_target = None
            return
        control = self.doc.form.get(name)
        container = control is not None and _layout.kind(control) is not None
        edge = height / 4 if container else height / 2
        if y < edge:
            zone = "before"
        elif y > height - edge:
            zone = "after"
        else:
            zone = "inside" if container else "after"
        target = (name, zone)
        if zone == "inside" and not all(self.doc.can_contain(name, n) for n in self.carry.names):
            target = None
        self.outline_target = target

    def enter_row(self, key: str) -> None:
        """The pointer entered the toolbox or outline row ``key``, which is drawn highlighted."""
        self.hovered_row = key

    def leave_row(self, key: str) -> None:
        """The pointer left the row ``key``: clears the highlight if it is still on that row."""
        if self.hovered_row == key:
            self.hovered_row = None

    def leave_outline(self, name: str) -> None:
        """The pointer left the outline row ``name``: forgets it as the drop target of a carry."""
        if self.outline_target is not None and self.outline_target[0] == name:
            self.outline_target = None

    def _carry_container(self) -> Optional[str]:
        carry = self.carry
        if carry is None or not self.over_form:
            return None
        exclude = carry.names if carry.kind == "outline" else ()
        found = self._container_under(*self.pointer, exclude=exclude)
        if found is not None and carry.kind == "outline" and not all(self.doc.can_contain(found, n)
                                                                      for n in carry.names):
            return None
        return found

    def window_release(self) -> None:
        """The mouse button went up anywhere: ends a drag out of the toolbox or the outline."""
        carry, self.carry = self.carry, None
        target, self.outline_target = self.outline_target, None
        if carry is None:
            return
        self.drop_name = None
        if not carry.moved:
            if carry.kind == "tool":  # a plain click picks the tool, as before
                self.pick_tool(carry.names[0])()
            return
        if carry.kind == "tool":
            if self.over_form:
                self.drop_tool(carry.names[0], self.pointer)
        elif target is not None:
            self.drop_in_outline(carry.names, *target)
        elif self.over_form:
            self.drop_on_form(carry.names, self.pointer)

    def _flow_index(self, parent: Optional[str], x: float, y: float, exclude=()) -> Optional[int]:
        container = self.doc.form.get(parent) if parent else None
        if container is None or _layout.kind(container) not in ("flex", "grid"):
            return None
        return _layout.drop_index(self.doc.form, self.rects, container, x, y, exclude=exclude)

    def drop_tool(self, type_: str, at: Tuple[float, float]) -> None:
        """Places a new ``type_`` control with its top-left corner at ``at`` (form coordinates), in the container there."""
        doc = self.doc
        rects = self.rects
        parent = self._container_under(*at)
        index = self._flow_index(parent, *at)
        ox, oy = _layout.origin(doc.form, rects, parent)
        control = doc.add(type_, at[0] - ox, at[1] - oy, snap=self.snap, parent=parent)
        if index is not None:
            doc.reparent([control.name], parent, index=index)
        self.tool = None
        self.right_tab = "properties"
        self._selection_changed()

    def drop_on_form(self, names: List[str], at: Tuple[float, float]) -> None:
        """Controls dragged from the outline onto the form: into the container under the pointer, or onto the form."""
        doc = self.doc
        parent = self._container_under(*at, exclude=names)
        if parent is not None and not all(doc.can_contain(parent, n) for n in names):
            return
        index = self._flow_index(parent, *at, exclude=names)
        if doc.reparent(names, parent, index=index, at=at):
            self._selection_changed()

    def drop_in_outline(self, names: List[str], target: str, zone: str) -> None:
        """Controls dropped on an outline row: inside it (a container), or just before or after it."""
        doc = self.doc
        form = doc.form
        control = form.get(target)
        if control is None or target in names:
            return
        at = None
        if zone == "inside":
            parent = target
            index = len([c for c in form.children(target) if c.name not in names])  # last, or top-most
            rects = self.rects
            box, first = rects.get(target), rects.get(names[0])
            if (_layout.kind(control) == "free" and box is not None and first is not None
                    and not geometry.intersects(box, first)):
                at = (box[0] + 8, box[1] + 8)  # it would be out of sight: put it in the top-left corner
        else:
            parent = control.parent
            siblings = [c.name for c in form.children(parent) if c.name not in names]
            position = siblings.index(target)
            holder = form.get(parent) if parent else None
            flowing = holder is not None and _layout.kind(holder) in ("flex", "grid")
            # the outline lists flex and grid children in order, and the others top-most first
            below = zone == "after"
            index = position + 1 if below == flowing else position
        if parent is not None and not all(doc.can_contain(parent, n) for n in names):
            return
        if doc.reparent(names, parent, index=index, at=at):
            self._selection_changed()

    def pointer_moved_view(self, x: float, y: float) -> None:
        """Pointer anywhere over the surface's scroll view, in view coordinates."""
        self.view_pointer = (x, y)
        if self.drag is not None:
            self._drag_to()

    def _start(self, mode: str, **kwargs: Any) -> None:
        self.drag = Drag(mode, self.view_pointer, start=self.pointer, **kwargs)

    @property
    def rects(self) -> Dict[str, Rect]:
        """Where every control is drawn; controls being dragged follow the pointer, even out of a flex row."""
        drag = self.drag
        free = drag.rects.keys() if drag is not None and drag.mode == "move" and drag.moved else ()
        return _layout.resolve(self.doc.form, free=free)

    @property
    def drop_target(self):
        """The container highlighted as the place a dragged or new control will go."""
        return self.doc.form.get(self.drop_name) if self.drop_name else None

    def _container_under(self, x: float, y: float, exclude=()) -> Optional[str]:
        found = _layout.container_at(self.doc.form, self.rects, x, y, exclude)
        return found.name if found is not None else None

    def press_control(self, name: str) -> None:
        """Mouse press on the control ``name``: selects it and starts moving the selection.

        Pressing a control that is already selected makes it the primary one (the alignment reference).
        With a tool picked, the press starts placing a new control instead. Locked controls do not move.
        """
        self.focus = "canvas"
        self.menu = None
        if self.tool:
            self.press_empty()
            return
        doc = self.doc
        if not doc.is_selected(name):
            doc.select(name)
        else:  # clicking a selected control makes it the primary one (alignment reference)
            doc.selection.remove(name)
            doc.selection.insert(0, name)
        self._selection_changed()
        form = doc.form
        absolute = self.rects
        moving = [c for c in doc.selected if not c.locked
                  and not any(doc.is_selected(a.name) for a in form.ancestors(c.name))]
        for c in moving:  # a control laid out by a flex or grid container starts from where it is drawn
            if _layout.managed(form, c) and c.name in absolute:
                ox, oy = _layout.origin(form, absolute, c.parent)
                c.x, c.y = absolute[c.name][0] - ox, absolute[c.name][1] - oy
        rects = {c.name: c.rect for c in moving}
        if rects:
            starts = {n: (*absolute[n][:2], r[2], r[3]) if n in absolute else r for n, r in rects.items()}
            self._start("move", rects=rects, absolute=starts)

    def press_handle(self, handle: str) -> None:
        """Mouse press on the resize ``handle`` ("n", "se", ...) of the primary control: resizes it."""
        primary = self.doc.primary
        if primary is not None:
            self.focus = "canvas"
            self._start("resize", rects={primary.name: primary.rect}, handle=handle)

    def press_form_grip(self) -> None:
        """Mouse press on the form's corner grip: starts resizing the form."""
        self._start("form", rects={"": (0.0, 0.0, self.doc.form.width, self.doc.form.height)})

    def press_empty(self) -> None:
        """Mouse press on an empty spot of the form.

        With a tool picked it starts placing a control (click or drag a rectangle); otherwise it clears
        the selection and starts a rubber band selection.
        """
        self.focus = "canvas"
        self.menu = None
        if self.tool:
            self._start("create")
        else:
            self.doc.select(None)
            self._selection_changed()
            self._start("band")

    def _drag_to(self) -> None:
        drag = self.drag
        assert drag is not None
        doc = self.doc
        form = doc.form
        grid = form.grid
        dx = self.view_pointer[0] - drag.origin[0]
        dy = self.view_pointer[1] - drag.origin[1]
        if abs(dx) + abs(dy) > 2:
            drag.moved = True
        if not drag.moved:
            return
        if drag.mode == "move":
            self._drag_move(dx, dy)
        elif drag.mode == "resize":
            (name, start), = drag.rects.items()
            x, y, w, h = geometry.resize(start, drag.handle or "se", dx, dy, grid=grid, snapping=self.snap)
            control = form.get(name)
            parent = form.get(control.parent) if control is not None and control.parent else None
            limit = (parent.width, parent.height) if parent is not None else (form.width, form.height)
            if control is not None and not _layout.managed(form, control):
                x, y = max(x, 0), max(y, 0)
                w, h = min(w, limit[0] - x), min(h, limit[1] - y)
            if control is not None:
                control.x, control.y, control.width, control.height = x, y, w, h
        elif drag.mode == "create":
            sx, sy = drag.start
            self.drop_name = self._container_under(sx, sy)
        elif drag.mode == "form":
            start = drag.rects[""]
            form.width = max(geometry.snap(start[2] + dx, grid, self.snap), 120)
            form.height = max(geometry.snap(start[3] + dy, grid, self.snap), 80)

    def _drag_move(self, dx: float, dy: float) -> None:
        drag = self.drag
        assert drag is not None
        doc = self.doc
        form = doc.form
        primary = doc.primary
        absolute = drag.absolute or drag.rects
        if primary is None or primary.name not in absolute:
            primary_rect = next(iter(absolute.values()))
        else:
            primary_rect = absolute[primary.name]
        px, py = primary_rect[0], primary_rect[1]
        nx = geometry.snap(px + dx, form.grid, self.snap)
        ny = geometry.snap(py + dy, form.grid, self.snap)
        # keep the whole group inside the form (in absolute coordinates: some may be in containers)
        x1 = min(r[0] for r in absolute.values())
        y1 = min(r[1] for r in absolute.values())
        x2 = max(r[0] + r[2] for r in absolute.values())
        y2 = max(r[1] + r[3] for r in absolute.values())
        ddx = max(-x1, min(nx - px, form.width - x2))
        ddy = max(-y1, min(ny - py, form.height - y2))
        self.guides = []
        if self.smart_guides:
            moving = (x1 + ddx, y1 + ddy, x2 - x1, y2 - y1)
            inside = {c.name for n in drag.rects for c in form.descendants(n)}
            rects = _layout.resolve(form, free=drag.rects.keys())
            others = [rects[c.name] for c in form.controls
                      if c.name not in drag.rects and c.name not in inside and c.visible and c.name in rects]
            gx, gy, self.guides = geometry.smart_guides(moving, others, (form.width, form.height))
            ddx += gx
            ddy += gy
        sx, sy = drag.start
        self.drop_name = self._container_under(sx + dx, sy + dy, exclude=drag.rects.keys())
        for name, (x, y, _, _) in drag.rects.items():
            control = form.get(name)
            if control is not None:
                control.x, control.y = x + ddx, y + ddy

    @property
    def band_rect(self) -> Optional[Rect]:
        """The rectangle being dragged to select or to place a control, in form coordinates.

        ``None`` when no such drag is in progress or the pointer has not moved yet. While placing a
        control its corners snap to the grid.
        """
        drag = self.drag
        if drag is None or drag.mode not in ("create", "band") or not drag.moved:
            return None
        dx = self.view_pointer[0] - drag.origin[0]
        dy = self.view_pointer[1] - drag.origin[1]
        sx, sy = drag.start
        ex, ey = sx + dx, sy + dy
        if drag.mode == "create":
            grid = self.doc.form.grid
            sx, sy = geometry.snap(sx, grid, self.snap), geometry.snap(sy, grid, self.snap)
            ex, ey = geometry.snap(ex, grid, self.snap), geometry.snap(ey, grid, self.snap)
        return geometry.normalize(sx, sy, ex, ey)

    def release(self) -> None:
        """Mouse button released on the surface: finishes the drag in progress.

        Places the new control (a dragged rectangle of at least 6x6 sets its size), selects what the band
        touched, drops moved controls into the container under them, or commits a resize to the history.
        """
        drag = self.drag
        if drag is None:
            return
        doc = self.doc
        form = doc.form
        band = self.band_rect
        moving_rects = self.rects  # still following the pointer
        self.drag = None
        self.guides = []
        target, self.drop_name = self.drop_name, None
        if drag.mode == "create" and self.tool:
            rects = _layout.resolve(form)
            parent = self._container_under(*drag.start)
            ox, oy = _layout.origin(form, rects, parent)
            if band is not None and band[2] >= 6 and band[3] >= 6:
                doc.add(self.tool, band[0] - ox, band[1] - oy, band[2], band[3], snap=self.snap, parent=parent)
            else:
                doc.add(self.tool, drag.start[0] - ox, drag.start[1] - oy, snap=self.snap, parent=parent)
            self.tool = None
            self.right_tab = "properties"
            self._selection_changed()
        elif drag.mode == "band":
            if band is not None:
                rects = _layout.resolve(form)
                hit = [c.name for c in form.controls if c.name in rects and geometry.intersects(rects[c.name], band)]
                # a container and what is inside it move together: keep the outermost
                doc.select([n for n in hit if not any(a.name in hit for a in form.ancestors(n))])
                self._selection_changed()
        elif drag.mode == "move" and drag.moved:
            self._drop(list(drag.rects), target, moving_rects)
        elif drag.moved:
            doc.commit()

    def _drop(self, names: List[str], target: Optional[str], rects: Dict[str, Rect]) -> None:
        """Ends a move: controls dropped on another container go inside it, in the spot they landed."""
        doc = self.doc
        form = doc.form
        container = form.get(target) if target else None
        flowing = container is not None and _layout.kind(container) in ("flex", "grid")
        changed = [n for n in names if form.get(n) is not None and form[n].parent != target]
        if flowing or changed:
            index = None
            if flowing:
                first = rects[names[0]]
                cx, cy = first[0] + first[2] / 2, first[1] + first[3] / 2
                index = _layout.drop_index(form, rects, container, cx, cy, exclude=names)
            doc.reparent(names, target, index=index, rects=rects, commit=False)
        doc.commit()

    # -- context menu ---------------------------------------------------------
    def open_context_menu(self, name: str) -> None:
        """Right-click on the control ``name``: selects it and opens its context menu at the pointer."""
        if not self.doc.is_selected(name):
            self.doc.select(name)
            self._selection_changed()
        self.menu = (name, *self.window_pointer)

    def close_menu(self) -> None:
        """Closes the control context menu."""
        self.menu = None

    def _menu_action(self, action: Callable[[], Any]) -> Callable[[], Any]:
        def run() -> Any:
            self.menu = None
            return action()
        return run

    def context_menu(self, t) -> Any:
        """Returns the control context menu widget, themed with ``t``."""
        return ui.menu(self._context_items(), width=CONTEXT_MENU_WIDTH, theme=t)

    def _context_items(self) -> List[Any]:
        assert self.menu is not None
        name = self.menu[0]
        control = self.doc.form.get(name)
        locked = bool(control and control.locked)
        container = control is not None and _layout.kind(control) is not None
        items = [
            ui.MenuItem(tr("View code"), self._menu_action(lambda: self.open_default_event(name)), icon="code"),
            ui.MenuItem(tr("Help"), self._menu_action(lambda: self.open_reference(self.help_page_of(name))),
                        icon="book-marked", keys="shift-f1"),
            ui.MenuItem(tr("Add inside…"), self._menu_action(lambda: self.open_add_child(name)), icon="plus")
            if container else None,
            ui.SEPARATOR,
            ui.MenuItem(tr("Group in a row"), self._menu_action(lambda: self.wrap("row")), icon="columns-3"),
            ui.MenuItem(tr("Group in a column"), self._menu_action(lambda: self.wrap("column")), icon="rows-3"),
            ui.MenuItem(tr("Group in a grid"), self._menu_action(lambda: self.wrap("grid")), icon="layout-grid"),
            ui.MenuItem(tr("Group in a panel"), self._menu_action(lambda: self.wrap("panel")), icon="panel-top"),
            ui.MenuItem(tr("Move out of {parent}", parent=control.parent),
                        self._menu_action(lambda: self.move_out(name)),
                        icon="arrow-up-left") if control is not None and control.parent else None,
            ui.SEPARATOR,
            ui.MenuItem(tr("Cut"), self._menu_action(self.cut), icon="scissors", keys="ctrl-x"),
            ui.MenuItem(tr("Copy"), self._menu_action(self.copy), icon="copy", keys="ctrl-c"),
            ui.MenuItem(tr("Paste"), self._menu_action(self.paste), icon="clipboard", keys="ctrl-v"),
            ui.MenuItem(tr("Duplicate"), self._menu_action(self.duplicate), icon="copy-plus", keys="ctrl-d"),
            ui.SEPARATOR,
            ui.MenuItem(tr("Bring to front"), self._menu_action(lambda: self.reorder("front")), icon="bring-to-front"),
            ui.MenuItem(tr("Send to back"), self._menu_action(lambda: self.reorder("back")), icon="send-to-back"),
            ui.MenuItem(tr("Unlock") if locked else tr("Lock"), self._menu_action(
                lambda: self.set_field(name, "locked", not locked)), icon="lock-open" if locked else "lock"),
            ui.SEPARATOR,
            ui.MenuItem(tr("Delete"), self._menu_action(self.delete), icon="trash-2", keys="delete", danger=True),
        ]
        return [i for i in items if i is not None]

    def context_menu_at(self, t) -> Tuple[Any, float, float]:
        """The context menu and where it goes in the window: at the pointer, kept inside the window."""
        assert self.menu is not None
        items = self._context_items()
        _, x, y = self.menu
        width, height = self.window_size or self.size
        separators = sum(1 for i in items if i == ui.SEPARATOR)
        tall = (len(items) - separators) * 28 + separators * 10 + 12  # a little more than drawn: never clipped
        if x + CONTEXT_MENU_WIDTH > width - 4:
            x = max(x - CONTEXT_MENU_WIDTH, 4)
        if y + tall > height - 4:
            y = max(height - tall - 4, 4)
        return ui.menu(items, width=CONTEXT_MENU_WIDTH, theme=t), x, y

    def carry_ghost(self, t) -> Optional[Any]:
        """A chip that follows the pointer while a component or control is dragged out of a panel."""
        carry = self.carry
        if carry is None or not carry.moved:
            return None
        if carry.kind == "tool":
            spec = _components.get(carry.names[0])
            icon, text = spec.icon, tr(spec.label)
        else:
            control = self.doc.form.get(carry.names[0])
            icon = _components.get(control.type).icon if control is not None else "box"
            text = carry.names[0] if len(carry.names) == 1 else f"{carry.names[0]} +{len(carry.names) - 1}"
        return _core.container(_core.row([_icon(icon, size=13, color=t.accent),
                                          _core.text(text, size=12.5, color=t.text, wrap=False)],
                                         spacing=6, align="center"),
                               padding=(4, 8), bg=t.elevated, border_color=t.border_focused,
                               border_width=1, radius=t.radius_sm)

    # -- editing commands -------------------------------------------------------
    def undo(self) -> None:
        """Undoes the last change to the document."""
        if self.doc.undo():
            self._selection_changed()

    def redo(self) -> None:
        """Redoes the last undone change."""
        if self.doc.redo():
            self._selection_changed()

    def delete(self) -> None:
        """Deletes the selected controls."""
        self.doc.delete()
        self._selection_changed()

    def cut(self) -> Any:
        """Cuts the selected controls to the clipboard (the system's too, so another form can paste them)."""
        count = self.doc.cut()
        self._selection_changed()
        return _core.Command.copy(self.doc.clipboard_text()) if count else None

    def copy(self) -> Any:
        """Copies the selected controls to the clipboard, the system's too, and tells how many were copied."""
        count = self.doc.copy()
        if not count:
            return None
        self.notify(tr("Copied {count} controls", count=count) if count > 1 else tr("Copied 1 control"))
        return _core.Command.copy(self.doc.clipboard_text())

    def paste(self) -> Any:
        """Pastes the controls on the system clipboard (copied in any form or Pyzed Design window) and selects
        them; returns the command that reads the clipboard."""
        return _core.Command.paste(self.paste_text)

    def paste_text(self, text: str) -> None:
        """Pastes the controls in system clipboard ``text``, or the last ones copied here when it holds none."""
        if self.doc.paste_text(text) is None:
            self.doc.paste()
        self._selection_changed()

    def duplicate(self) -> None:
        """Duplicates the selected controls."""
        self.doc.duplicate()
        self._selection_changed()

    def align(self, edge: str) -> None:
        """Aligns the selected controls on ``edge`` ("left", "center", "right", "top", "middle", "bottom")."""
        self.doc.align(edge)

    def distribute(self, axis: str) -> None:
        """Spaces the selected controls evenly along ``axis`` ("horizontal" or "vertical")."""
        self.doc.distribute(axis)

    def same_size(self, which: str) -> None:
        """Gives the selected controls the primary one's ``which`` ("width" or "height")."""
        self.doc.same_size(which)

    def center(self, axis: str) -> None:
        """Centers the selected controls in the form along ``axis`` ("horizontal" or "vertical")."""
        self.doc.center(axis)

    def reorder(self, where: str) -> None:
        """Moves the selected controls to the front or the back (``where`` is "front" or "back")."""
        self.doc.reorder(where)

    def set_field(self, name: str, key: str, value: Any) -> None:
        """Sets the field ``key`` (``locked``, ``visible``, ...) of the control ``name`` to ``value``."""
        self.doc.set_field(name, key, value)

    def toggle_anchor(self, name: str, edge: str) -> None:
        """Turns the anchor of the control ``name`` to the ``edge`` of its container on or off."""
        self.doc.toggle_anchor(name, edge)

    def prop_setter(self, name: str, prop: Prop) -> Callable[[Any], None]:
        """Returns a callback that sets the property ``prop`` of the control ``name``.

        Whole floats given to number properties are stored as ints.
        """
        def setter(value: Any) -> None:
            if prop.kind == "number" and isinstance(value, float) and value.is_integer():
                value = int(value)
            self.doc.set_prop(name, prop.name, value)
        return setter

    def set_form(self, key: str, value: Any) -> None:
        """Sets the form's own setting ``key`` (title, size, grid, ...) to ``value``."""
        self.doc.set_form(key, value)

    def set_style(self, name: Optional[str], key: str, value: Any) -> None:
        """A Style section edit: ``value`` as the field gives it (text, number, choice)."""
        from . import styling

        try:
            stored = styling.field_value(key, value)
        except (TypeError, ValueError):
            return
        self.doc.set_style(name, key, stored)

    def set_style_value(self, name: Optional[str], key: str, value: Any) -> None:
        """Stores an already built style value (a background, a shadow) as it is."""
        self.doc.set_style(name, key, value)

    def clear_style(self, name: Optional[str]) -> None:
        """Removes every style override of the control ``name`` (the form's when ``None``)."""
        self.doc.clear_style(name)

    # -- animations ------------------------------------------------------------------

    def add_animation(self, name: str, trigger: str = "mount") -> None:
        """Adds an animation (a preset that suits ``trigger``) to the control ``name`` and previews it."""
        from . import motion

        animations = [*self.doc.form[name].animations, motion.new_entry(trigger)]
        self.doc.set_animations(name, animations)
        self.motion_open = (name, len(animations) - 1)
        self.preview_animations(name)

    def open_animation(self, name: str, index: int) -> None:
        """Opens (or closes) the editor of animation ``index`` of the control ``name``."""
        self.motion_open = None if self.motion_open == (name, index) else (name, index)

    def set_animation(self, name: str, index: int, key: str, value: Any) -> None:
        """Sets ``key`` (preset, on, duration, delay, easing, repeat) of animation ``index`` of the control
        ``name``; ``None`` or ``""`` goes back to the preset's own value. Changing it previews it."""
        animations = [dict(a) for a in self.doc.form[name].animations]
        if not 0 <= index < len(animations):
            return
        entry = animations[index]
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if value in (None, ""):
            entry.pop(key, None)
        else:
            entry[key] = value
        if key == "preset":  # a new preset brings its own timing
            for k in ("duration", "delay", "easing", "repeat"):
                entry.pop(k, None)
        self.doc.set_animations(name, animations, group=f"animation:{name}:{index}:{key}")
        if key != "on":
            self.preview_animations(name)

    def remove_animation(self, name: str, index: int) -> None:
        """Removes animation ``index`` of the control ``name``."""
        animations = list(self.doc.form[name].animations)
        if 0 <= index < len(animations):
            del animations[index]
            self.doc.set_animations(name, animations)
            self.motion_open = None
            if not animations:
                self.stop_preview(name)

    def preview_animations(self, name: str) -> None:
        """Plays the animations of the control ``name`` on the canvas (again, if they were playing)."""
        self.motion_preview[name] = self.motion_preview.get(name, 0) + 1

    def stop_preview(self, name: Optional[str] = None) -> None:
        """Stops the canvas preview of one control's animations (every control's when ``name`` is ``None``)."""
        if name is None:
            self.motion_preview.clear()
        else:
            self.motion_preview.pop(name, None)

    def toggle_color_picker(self, name: Optional[str], key: str) -> None:
        """Opens the color picker of a Style row as a floating card next to the pointer (or closes it)."""
        if self.color_picker == (name, key):
            self.color_picker = None
            return
        self.color_picker = (name, key)
        self.picker_at = self.window_pointer

    def toggle_text_editor(self, key: str) -> None:
        """Switches a list or table property between its item editor and plain text."""
        self.text_editors ^= {key}

    def close_color_picker(self) -> None:
        """Closes the floating color picker."""
        self.color_picker = None

    def color_picker_at(self, t) -> Optional[Tuple[Any, float, float]]:
        """The color picker card and where it goes: beside the pointer, away from the panel, inside the window."""
        card = panels.color_popover(self, t)
        if card is None:
            return None
        px, py = self.picker_at
        width, height = self.window_size or self.size
        x = px - panels.PICKER_WIDTH - 16  # the Style rows are in a side panel: open towards the form
        if x < 4:
            x = min(px + 16, max(width - panels.PICKER_WIDTH - 4, 4))
        y = min(max(py - 40, 4), max(height - panels.PICKER_HEIGHT - 4, 4))
        return card, x, y

    def set_name_buffer(self, text: str) -> None:
        """Keeps the text typed in the Name field until it is committed."""
        self.name_buffer = text

    def commit_name(self) -> None:
        """Renames the primary control to the Name field's text (the document may adjust it).

        Closes the handler being edited, since its name may follow the control's.
        """
        primary = self.doc.primary
        if primary is not None:
            self.name_buffer = self.doc.rename(primary.name, self.name_buffer)
            if self.editing and self.editing[0] != "*":
                self.close_code()

    def toggle(self, attr: str) -> Callable[[], None]:
        """Returns a callback that flips the designer's boolean attribute ``attr`` (``show_grid``, ...)."""
        def flip() -> None:
            setattr(self, attr, not getattr(self, attr))
        return flip

    # -- docks ------------------------------------------------------------------
    @property
    def left_tab(self) -> str:
        """The panel shown with the toolbox ("design" or "project"), wherever it is docked."""
        return "project" if self.layout.is_showing("project", self) else "design"

    @left_tab.setter
    def left_tab(self, tab: str) -> None:
        self.layout.show(tab)

    @property
    def right_tab(self) -> str:
        """The panel shown on the inspector side: "events" or "properties", wherever it is docked."""
        return "events" if self.layout.is_showing("events", self) else "properties"

    @right_tab.setter
    def right_tab(self, tab: str) -> None:
        self.layout.show(tab)

    def set_left_tab(self, tab: str) -> None:
        """Shows the panel ``tab`` ("design" or "project")."""
        self.left_tab = tab

    def set_right_tab(self, tab: str) -> None:
        """Shows the panel ``tab`` ("properties" or "events")."""
        self.right_tab = tab

    def resize_left(self, ratio: float) -> None:
        """Sets how much of the left column the upper panel takes (``ratio`` from 0 to 1)."""
        self.left_ratio = ratio

    def show_panel(self, panel: str) -> None:
        """Shows the panel ``panel`` in its dock and saves the layout (the console stays pinned open)."""
        if panel == "console":
            self.console.pinned = True
        self.layout.show(panel)
        self.layout.menu = None
        self._save_layout()

    def toggle_agent(self) -> Any:
        """Shows the Agent panel and focuses its message box, or hides its dock when it is showing."""
        if self.layout.is_showing("agent", self):
            self.toggle_dock(self.layout.docks["agent"])
            return None
        self.show_panel("agent")
        return _core.Command.focus(agent_panel.INPUT_ID)

    def move_panel(self, panel: str, dock: str) -> None:
        """Moves the panel ``panel`` to the dock ``dock`` and saves the layout."""
        self.layout.move(panel, dock)
        self._save_layout()

    def toggle_dock(self, dock: str) -> None:
        """Shows or hides the dock ``dock`` and saves the layout."""
        self.layout.toggle(dock)
        self.layout.menu = None
        self._save_layout()

    def resize_dock(self, dock: str, size: float) -> None:
        """A dock's edge was dragged (called when it is let go)."""
        self.layout.resize(dock, size)
        self._save_layout()

    def dock_visible(self, dock: str) -> bool:
        """Returns whether the dock ``dock`` is open and has a panel to show."""
        return self.layout.shown(dock, self) is not None

    def open_dock_menu(self, dock: str) -> None:
        """Opens the panel menu of the dock ``dock``, or closes it if it is already open."""
        self.layout.menu = None if self.layout.menu == dock else dock

    def close_dock_menu(self) -> None:
        """Closes the dock's panel menu."""
        self.layout.menu = None

    def reset_layout(self) -> None:
        """Puts every panel back in its default dock and size, and saves that layout."""
        self.layout = docks.DockLayout()
        self._save_layout()

    def _save_layout(self) -> None:
        self.prefs.docks = dict(self.layout.docks)
        self.prefs.sizes = dict(self.layout.sizes)
        self.prefs.panels = {dock: not closed for dock, closed in self.layout.closed.items()}
        preferences.save(self.prefs)

    # -- preferences, menus and help ---------------------------------------------
    def set_pref(self, key: str, value: Any) -> None:
        """Sets the preference ``key`` to ``value`` and saves the preferences.

        The view options (``show_grid``, ``snap``, ``smart_guides``, ``show_hidden``) apply at once.
        """
        setattr(self.prefs, key, value)
        if key in ("show_grid", "snap", "smart_guides", "show_hidden"):
            setattr(self, key, value)
        preferences.save(self.prefs)

    def toggle_pref(self, key: str) -> None:
        """Flips the boolean preference ``key`` and saves it."""
        current = getattr(self, key) if key in ("show_grid", "snap", "smart_guides", "show_hidden") else \
            getattr(self.prefs, key)
        self.set_pref(key, not current)

    def set_language(self, code: str) -> None:
        """Switches the designer's language to ``code`` and remembers it in the preferences."""
        self.prefs.language = code
        preferences.save(self.prefs)
        _locale.apply(code)

    def open_settings(self) -> None:
        """Opens the Settings dialog."""
        self.app_menu = None
        self.dialog = "settings"

    def open_dialog_named(self, name: str) -> Any:
        """Opens the dialog ``name`` with an empty search and the first row highlighted; returns ``None``."""
        self.app_menu = None
        self.picker_query = ""
        self.picker_index = 0
        self.dialog = name
        return None

    def open_palette(self) -> Any:
        """Opens the command palette and returns the command that focuses its search field."""
        self.open_dialog_named("palette")
        return _core.Command.focus(dialogs.PICKER_ID)

    def open_preview_picker(self, which: str) -> Any:
        """Opens the list of themes (``which="theme"``) or languages (``"language"``) to preview the form in."""
        if self.doc.path is not None:
            _binding.load_texts(self.doc.path)
        self.open_dialog_named(f"preview_{which}")
        return _core.Command.focus(dialogs.PICKER_ID)

    def open_icon_picker(self, value: str, on_pick: Callable[[str], Any]) -> None:
        """Opens the icon dialog on ``value``; the icon clicked there goes to ``on_pick(name)``."""
        self.open_dialog_named("icon_picker")
        self.icon_value = value or ""
        self.icon_pick = on_pick

    def pick_icon(self, name: str) -> Any:
        """The icon dialog's choice: hands ``name`` to the property that opened it and closes the dialog."""
        on_pick, self.icon_pick = self.icon_pick, None
        self.dialog = None
        return on_pick(name) if on_pick is not None else None

    def set_preview(self, which: str, value: Optional[str]) -> None:
        """Previews the form in theme or language ``value`` (``None`` goes back to the form's own) on the canvas
        and when it runs."""
        setattr(self, f"preview_{which}", value or None)
        self.dialog = None

    def toggle_app_menu(self, name: str) -> None:
        """Opens the title bar menu ``name`` ("file", "view" or "help"), or closes it if open."""
        self.app_menu = None if self.app_menu == name else name
        self.layout.menu = None

    def close_app_menu(self) -> None:
        """Closes the title bar menu."""
        self.app_menu = None

    def run_action(self, action_id: str) -> Any:
        """Runs a command from the menus or the palette (closing them first)."""
        self.app_menu = None
        if self.dialog in ("palette",):
            self.dialog = None
        return _commands.run(action_id, self)

    def open_url(self, url: str) -> None:
        """Opens ``url`` in the web browser, in a background thread so the UI does not wait."""
        import threading
        import webbrowser

        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    def open_docs(self) -> None:
        """Opens Pyzed's documentation in the web browser."""
        self.open_url(_commands.DOCS_URL)

    def select_all(self) -> None:
        """Selects every control of the form."""
        self.doc.select_all()
        self._selection_changed()

    def show_save_as(self) -> None:
        """Opens the "Save as" dialog, filled with the current path or a name made from the form's."""
        self.dialog = "save_as"
        self.dialog_path = str(self.doc.path or f"{self.doc.form.name.lower()}{SUFFIX}")

    def focus_panel(self) -> None:
        """Gives the keyboard to a side panel, so canvas shortcuts stop acting."""
        self.focus = "panel"

    def focus_code(self) -> None:
        """Gives the keyboard to the code editor."""
        self.focus = "code"

    # -- events and code ----------------------------------------------------
    def open_default_event(self, name: str) -> None:
        """Double-click on the control ``name``: opens the code of its main event.

        A placed designed component opens its own file in a Component tab instead.
        """
        self.drag = None
        control = self.doc.form.get(name)
        if control is None:
            return
        if self.open_component_of(name):  # a designed component opens in its Component view
            return
        event = _components.get(control.type).default_event
        if event:
            self.edit_event(name, event)

    def edit_event(self, target: Optional[str], event: str) -> None:
        """Opens the handler of ``event`` on ``target`` (the form when ``None``) in the code editor.

        Wires the event first if it has no handler yet. Does nothing if the open code does not parse.
        """
        if not self._flush_code():
            return
        if target is not None and self.doc.selection != [target]:
            self.doc.select(target)
            self._selection_changed()
        handler = self.doc.wire(target, event)
        self.editing = (handler, self.doc.handler_source(handler))
        self.last_handler = handler
        self.code_revision += 1
        self.code_error = None
        self.right_tab = "events"
        self.layout.show("code")
        self.focus = "code"
        self.assist.opened()

    def unwire(self, target: Optional[str], event: str) -> None:
        """Disconnects ``event`` of ``target`` and deletes its handler's code (closing it if it is open)."""
        _, events = self.doc.owner(target)
        handler = events.get(event)
        if self.editing and self.editing[0] == handler:
            self.close_code()
        self.doc.unwire(target, event, delete_code=True)

    @property
    def editor_id(self) -> str:
        """The id of the code editor's buffer (a new one for each handler opened)."""
        handler = self.editing[0] if self.editing else ""
        return f"code:{handler}:{self.code_revision}"

    def set_code_buffer(self, text: str) -> None:
        """Keeps the code editor's text as it is typed and tells the code assistant."""
        if self.editing is not None:
            self.editing = (self.editing[0], text)
            self.focus = "code"
            self.assist.changed(text)

    def set_code_cursor(self, line: int, column: int) -> Any:
        """The editor's cursor moved to ``line``, ``column``; returns the assistant's command, if any."""
        self.focus = "code"
        return self.assist.moved(line, column)

    def open_editor_settings(self) -> None:
        """Opens the code editor settings dialog."""
        self.app_menu = None
        self.dialog = "editor_settings"

    def _code_scope(self) -> str:
        """The document's text of what the code editor shows: the whole file or one handler."""
        assert self.editing is not None
        handler = self.editing[0]
        return self.doc.code if handler == "*" else self.doc.handler_source(handler)

    def sync_code(self) -> None:
        """Brings changes made outside the code editor (Properties, the Events tab, undo) into it.

        Text typed in the editor and not applied yet is kept: both changes are merged, and the merge is
        applied to the document when it parses.
        """
        if self.editing is None:
            self._code_base = None
            return
        key = (id(self.doc), self.editing[0], self.code_revision)
        theirs = self._code_scope()
        if self._code_base is None or self._code_base[0] != key:
            self._code_base = (key, theirs)
            return
        base, ours = self._code_base[1], self.editing[1]
        if theirs == base:
            return
        if ours == theirs:
            self._code_base = (key, theirs)
            return
        merged = theirs if ours == base else _code.merge3(base, ours, theirs)
        if merged != theirs:
            try:
                ast.parse(merged)
            except SyntaxError:
                pass  # keep the document as it is; the editor shows the merge until it parses
            else:
                if self.editing[0] == "*":
                    self.doc.set_code(merged)
                else:
                    self.doc.set_handler_source(self.editing[0], merged)
                theirs = self._code_scope()
        self.editing = (self.editing[0], merged)
        self.code_revision += 1  # a new editor buffer with the merged text
        self._code_base = ((id(self.doc), self.editing[0], self.code_revision), theirs)

    def _flush_code(self) -> bool:
        """Applies the open editor to the document; ``False`` (and an error shown) if it does not parse."""
        self.sync_code()
        if self.editing is None:
            return True
        handler, text = self.editing
        try:
            if handler == "*":
                ast.parse(text)
                if text != self.doc.code:
                    self.doc.set_code(text)
            elif text != self.doc.handler_source(handler):
                self.doc.set_handler_source(handler, text)
        except SyntaxError as err:
            self.code_error = f"Line {err.lineno}: {err.msg}"
            return False
        self.code_error = None
        self._code_base = ((id(self.doc), handler, self.code_revision), self._code_scope())
        return True

    def apply_code(self) -> Any:
        """Applies the editor's code to the document and formats it.

        Returns the command that puts the formatted text in the editor, or ``None`` if nothing changed
        or the code does not parse.
        """
        if self.editing is None or not self._flush_code():
            return None
        self.notify("Code applied", kind="success", seconds=1.5)
        formatted = self.assist.format(self.editing[1])
        if formatted == self.editing[1]:
            return None
        self.set_code_buffer(formatted)
        self._flush_code()
        return _core.Command.set_editor_text(self.editor_id, formatted)

    def toggle_whole_file(self) -> None:
        """Switches the code editor between the current handler and the whole code file."""
        if self.editing is None or not self._flush_code():
            return
        if self.editing[0] == "*":
            if self.last_handler and _code.find_function(self.doc.code, self.last_handler):
                self.editing = (self.last_handler, self.doc.handler_source(self.last_handler))
            else:
                self.editing = None
        else:
            self.editing = ("*", self.doc.code)
        self.code_revision += 1
        self.assist.opened()

    def close_code(self) -> None:
        """Closes the code editor, unless its code does not parse."""
        if self._flush_code():
            self.editing = None
            self.assist.closed()

    def edit_whole_file(self) -> None:
        """Opens the form's whole code file in the code editor (F7)."""
        if self._flush_code():
            self.editing = ("*", self.doc.code)
            self.code_revision += 1
            self.layout.show("code")
            self.focus = "code"
            self.assist.opened()

    # -- files --------------------------------------------------------------
    def _guard(self, action: Callable[[], Any]) -> Any:
        """Runs ``action``: opening or creating a file adds a tab, so nothing unsaved is lost."""
        return action()

    # -- open documents (tabs) ------------------------------------------------
    @property
    def doc(self) -> Document:
        """The document of the active tab."""
        return self.docs[self.active_doc]

    @doc.setter
    def doc(self, value: Document) -> None:
        """Opens ``value`` in a tab: the tab of the same file, an untouched empty tab, or a new one."""
        self.__dict__["help_active"] = False  # show the document, not the Reference tab
        docs: List[Document] = self.__dict__.setdefault("docs", [])
        if not docs:
            docs.append(value)
            self.active_doc = 0
            return
        if value.path is not None:
            for i, other in enumerate(docs):
                if other.path is not None and other.path.resolve() == value.path.resolve():
                    docs[i] = value
                    self.active_doc = i
                    return
        current = docs[self.active_doc]
        if current.path is None and not current.dirty and not current.form.controls and current is not value:
            docs[self.active_doc] = value  # an empty untitled form: reuse its tab
            return
        docs.append(value)
        self.active_doc = len(docs) - 1

    def _leave_doc(self) -> bool:
        """Closes what belongs to the active tab (the code editor, menus) before switching."""
        if not self._flush_code():
            self.notify("Fix the code first", self.code_error, kind="error", seconds=4)
            return False
        self.editing = None
        self.menu = None
        self.drag = None
        return True

    def select_doc(self, index: int) -> None:
        """Switches to the tab at ``index``."""
        if index == self.active_doc or not 0 <= index < len(self.docs) or not self._leave_doc():
            return
        self.active_doc = index
        self.code_revision += 1
        self._selection_changed()

    def close_doc(self, index: Optional[int] = None) -> None:
        """Closes a tab (the active one by default), asking first when it has unsaved changes."""
        index = self.active_doc if index is None else index
        if not 0 <= index < len(self.docs):
            return
        doc = self.docs[index]

        def close() -> None:
            if index == self.active_doc:
                self.editing = None
            self.docs.pop(index)
            if not self.docs:
                self.docs.append(Document())
            if self.active_doc >= index and self.active_doc > 0:
                self.active_doc -= 1
            self.active_doc = min(self.active_doc, len(self.docs) - 1)
            self._selection_changed()

        if doc.dirty:
            if index != self.active_doc:
                self.select_doc(index)
            self.pending = close
            self.dialog = "confirm"
            return
        close()

    def open_component_of(self, name: str) -> bool:
        """Opens the designed component placed as ``name`` in its own Component tab (double-click)."""
        control = self.doc.form.get(name)
        cls = _component_registry().get(control.type) if control is not None else None
        path = getattr(cls, "scene_file", None) if cls is not None else None
        if path is None or not Path(path).exists():
            return False
        if not self._leave_doc():
            return True
        for i, other in enumerate(self.docs):
            if other.path is not None and other.path.resolve() == Path(path).resolve():
                self.select_doc(i)
                return True
        self.open_path(path)
        return True

    def doc_tabs(self, t) -> Any:
        """One tab per open file: forms open in the Form view, components in the Component view."""
        tabs = []
        for i, doc in enumerate(self.docs):
            scene = getattr(doc, "is_scene", False)
            kind = tr("Component") if scene else tr("Form")
            tabs.append(ui.Tab(id=str(i), label=f"{kind} · {doc.display_name}",
                               icon="component" if scene else "app-window",
                               icon_color="accent" if scene else None, dirty=doc.dirty))
        notes = self.updates.tab()
        if notes is not None:
            tabs.append(notes)
        if self.help_open:
            tabs.append(ui.Tab(id=HELP_TAB, label=_t("pyzed.reference.title"), icon="book-open", icon_color="accent"))
        view = tr("Component view") if getattr(self.doc, "is_scene", False) else tr("Form view")
        active = HELP_TAB if self.help_shown else _NOTES_TAB if self.updates.notes_active else str(self.active_doc)
        return ui.tab_bar(tabs, active, on_select=self._select_tab, on_close=self._close_tab,
                          end=[ui.label(view, size="xs", color="text_muted", theme=t)], height=30, theme=t)

    def _select_tab(self, tab_id: str) -> None:
        """Switches to a document tab, or to the What's new tab."""
        self.help_active = tab_id == HELP_TAB
        if tab_id == HELP_TAB:
            self.updates.activate_notes(False)
            return
        if tab_id == _NOTES_TAB:
            self.updates.activate_notes()
            return
        self.updates.activate_notes(False)
        self.select_doc(int(tab_id))

    def _close_tab(self, tab_id: str) -> None:
        if tab_id == HELP_TAB:
            self.close_reference()
        elif tab_id == _NOTES_TAB:
            self.updates.close_notes()
        else:
            self.close_doc(int(tab_id))

    # -- built-in reference ---------------------------------------------------
    def open_reference(self, page: Optional[str] = None) -> None:
        """Opens the Reference tab, on ``page`` when given (an id of ``pyzed.reference``)."""
        self.app_menu = None
        self.menu = None
        if page is not None:
            self.help.open(page)
        self.help_open = self.help_active = True
        self.updates.activate_notes(False)

    @property
    def help_shown(self) -> bool:
        """Whether the Reference tab is the one in front (What's new takes over when it opens)."""
        return self.help_active and not self.updates.notes_active

    def close_reference(self) -> None:
        """Closes the Reference tab."""
        self.help_open = self.help_active = False

    def reference_here(self) -> None:
        """Opens the reference about what is in front of the user (Shift+F1).

        The name under the cursor in the code editor (``form.button1.text`` opens the Button page,
        ``ui.button`` its library page), else the selected control, else the reference as it was.
        """
        page = None
        if self.editing is not None and self.focus == "code":
            line, column = self.assist.cursor
            symbol = _help.word_at(self.assist._line(line), column - 1)
            page = _help.lookup_code(symbol, self.doc.form) if symbol else None
            if page is None and symbol:
                self.help.set_query(symbol.rsplit(".", 1)[-1])
        elif self.doc.primary is not None:
            page = self.help_page_of(self.doc.primary.name)
        self.open_reference(page)

    def help_page_of(self, name: str) -> Optional[str]:
        """The reference page of the control ``name`` (its toolbox type, or the component placed there)."""
        control = self.doc.form.get(name)
        if control is None:
            return None
        return _help.lookup_code(f"form.{name}", self.doc.form)

    def new(self, kind: str = "form") -> Any:
        """Shows the "New" dialog: a form (name, title, template and folder) or a component (``kind``)."""
        folder = self.doc.path.parent if self.doc.path else (
            self.projects.project.ui_dir if self.projects.project else Path.cwd())
        try:
            folder = folder.resolve().relative_to(Path.cwd())
        except ValueError:
            pass
        self.new_state = {"title": "", "folder": str(folder), "template": "blank", "extends": ""}
        self.set_new("kind", kind)
        self.dialog = "new"
        return _core.Command.focus("new-form-name")

    def new_component(self) -> Any:
        """Shows the "New component" dialog."""
        return self.new("component")

    def set_new(self, key: str, value: str) -> None:
        """Sets the field ``key`` of the "New" dialog to ``value``.

        Changing the kind or the folder picks a free default name (``form1``, ``component2``, ...).
        """
        self.new_state[key] = value
        if key in ("kind", "folder"):  # a free default name for that kind in that folder
            s = self.new_state
            base, suffix = ("component", _scene.SUFFIX) if s["kind"] == "component" else ("form", SUFFIX)
            folder = Path(s["folder"] or ".")
            taken = {p.stem for p in folder.glob(f"*{suffix}")} if folder.is_dir() else set()
            if not s.get("name") or re.fullmatch(r"(form|component)\d+", s["name"]):
                n = 1
                while f"{base}{n}" in taken:
                    n += 1
                s["name"] = f"{base}{n}"

    def base_components(self) -> List[Path]:
        """The designed components of the project, to inherit from."""
        root = self.projects.project.root if self.projects.project else Path.cwd()
        return _scene.component_files(root)

    def create_new_component(self) -> None:
        """Creates the component described in the "New" dialog, saves it and opens it."""
        s = self.new_state
        name = s.get("name") or "component1"
        path = Path(s.get("folder") or ".") / f"{_scene_code.member_identifier(name)}{_scene.SUFFIX}"
        if path.exists():
            self.notify(f"{path.name} already exists", kind="warning")
            return

        def create() -> None:
            try:
                doc = _scene.new_component(name, path, extends=s.get("extends") or None)
                doc.form.grid = self.prefs.grid
                doc.save()
            except (OSError, ValueError, SyntaxError) as err:
                self.notify("Could not create the component", str(err), kind="error", seconds=5)
                return
            self.dialog = None
            self.open_path(path)

        self.dialog = None
        self._guard(create)

    def create_new_form(self) -> None:
        """Creates the form described in the "New form" dialog and opens it (after asking to keep unsaved changes)."""
        s = self.new_state
        path = Path(s.get("folder") or ".") / f"{s.get('name') or 'form1'}{SUFFIX}"
        if path.exists():
            self.notify(f"{path.name} already exists", kind="warning")
            return

        def create() -> None:
            try:
                created = _new.new_form(path, title=s.get("title") or None, template=s.get("template", "blank"))
            except (OSError, ValueError, KeyError) as err:
                self.notify("Could not create the form", str(err), kind="error", seconds=5)
                return
            self.dialog = None
            self.open_path(created)
            self.doc.form.grid = self.prefs.grid

        self.dialog = None
        self._guard(create)

    def create_untitled_form(self) -> None:
        """A new form that is only saved when the user saves it."""
        s = self.new_state

        def create() -> None:
            self.doc = _new.create(s.get("name") or "form1", title=s.get("title") or None,
                                   template=s.get("template", "blank"))
            self.doc.form.grid = self.prefs.grid
            self.editing = None
            self.dialog = None
            self._selection_changed()

        self.dialog = None
        self._guard(create)

    def _new(self, factory: Callable[[], Document] = Document) -> None:
        self.dialog = None
        self.doc = factory()
        self.doc.form.grid = self.prefs.grid
        self.editing = None
        self._selection_changed()

    def open_dialog(self) -> None:
        """Opens the "Open" dialog to pick a form or component file."""
        self._guard(self._show_open)

    def _show_open(self) -> None:
        self.dialog = "open"
        self.dialog_path = ""

    def open_path(self, path: Union[str, Path]) -> None:
        """Opens the form or component at ``path`` in a tab (``.pzform`` is added when there is no suffix).

        Switches to its tab if it is already open, and remembers it among the recent files.
        """
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix(SUFFIX)
        for i, other in enumerate(self.docs):
            if other.path is not None and path.exists() and other.path.resolve() == path.resolve():
                self.dialog = None
                self.select_doc(i)  # already open: keep its unsaved changes
                return
        if not self._leave_doc():
            return
        try:
            self.doc = _scene.open_document(path)
        except (OSError, ValueError) as err:
            self.notify("Could not open the form", str(err), kind="error", seconds=5)
            return
        _binding.load_texts(path)  # the form's own translations, for @key texts and Preview language
        self.dialog = None
        self.editing = None
        self._selection_changed()
        self.prefs.remember(path)
        preferences.save(self.prefs)
        self.notify(f"Opened {path.name}")

    def save(self) -> None:
        """Saves the active document, asking for a path first if it has none.

        Does not save if the open code does not parse. A running preview reloads what was saved.
        """
        if self.doc.path is None:
            self.dialog = "save_as"
            self.dialog_path = f"{self.doc.form.name.lower()}{getattr(self.doc, 'suffix', SUFFIX)}"
            return
        if not self._flush_code():
            self.notify("Fix the code before saving", self.code_error, kind="error", seconds=4)
            return
        path = self.doc.save()
        self.notify(f"Saved {path.name}", kind="success", seconds=2)
        if self.preview is not None and self.preview.is_open:
            # the running form picks up the saved layout and code, keeping what was typed in it
            self.preview.runtime.reload(path)

    def save_as(self, path: str) -> None:
        """Saves the active document at ``path`` (the document's suffix is added when it has none)."""
        if not path.strip():
            return
        suffix = getattr(self.doc, "suffix", SUFFIX)
        self.doc.path = Path(path.strip()) if Path(path.strip()).suffix else Path(path.strip()).with_suffix(suffix)
        self.dialog = None
        self.save()

    def set_dialog_path(self, text: str) -> None:
        """Keeps the path or filter typed in the Open or Save as dialog."""
        self.dialog_path = text

    def close_dialog(self) -> None:
        """Closes the dialog and drops the action waiting on it."""
        self.dialog = None
        self.pending = None

    def confirm_save(self) -> Any:
        """"Save" in the unsaved-changes dialog: saves, then goes on with what was asked (a new file is saved as first)."""
        if self.doc.path is None:
            self.pending = None
            return self.save()
        self.save()
        if self.doc.dirty:  # the code has an error: stay on this form
            self.dialog = None
            self.pending = None
            return None
        return self.confirm_discard()

    def confirm_discard(self) -> Any:
        """"Don't save" in the unsaved-changes dialog: drops the changes and runs the waiting action."""
        action, self.pending = self.pending, None
        self.dialog = None
        self.doc.dirty = False
        return action() if action else None

    def form_files(self, limit: int = 40) -> List[Path]:
        """Returns up to ``limit`` form and component files under the working folder, relative to it.

        Folders such as ``.git``, ``.venv`` and ``node_modules`` are skipped.
        """
        found: List[Path] = []
        root = Path.cwd()
        for path in sorted(p for suffix in DOCUMENT_SUFFIXES for p in root.rglob(f"*{suffix}")):
            if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                continue
            found.append(path.relative_to(root))
            if len(found) >= limit:
                break
        return found

    # -- running ------------------------------------------------------------
    def run_form(self) -> Any:
        """Opens the form in a new window with its handlers loaded fresh (F5)."""
        if not self._flush_code():
            self.notify("Fix the code before running", self.code_error, kind="error", seconds=4)
            return None
        if scene_panel.is_scene(self):
            return scene_panel.run(self)
        if self.prefs.save_on_run and self.doc.path is not None:
            self.save()
        if self.prefs.console_on_run:
            self.layout.show("console")
        name = self.doc.display_name
        if self.projects.runs_outside and self.doc.path is not None:
            # The designer does not have the project's dependencies: run it with `uv run`.
            self.save()
            self.console.start(name, "uv run")
            env = {k: v for k, v in (("PYZED_PREVIEW_THEME", self.preview_theme),
                                     ("PYZED_PREVIEW_LANGUAGE", self.preview_language)) if v}
            self.projects.run_form(Path(self.doc.path), capture=True, env=env)
            self.console.pipe(self.projects.process)
            return None
        self.console.start(name)
        try:
            handlers = self._compile_handlers()
        except Exception as err:  # noqa: BLE001 - show any import-time error to the user
            import traceback

            self.console.event("error", "The code file has an error\n" + traceback.format_exc().rstrip())
            self.console.stop()
            self.notify("The code file has an error", f"{type(err).__name__}: {err}", kind="error", seconds=6)
            return None
        commands = []
        if self.preview is not None and self.preview.is_open:
            commands.append(self.preview.close())
        self.preview = FormWindow(self.doc.form, handlers, path=self.doc.path, theme=self.preview_theme,
                                  language=self.preview_language)
        self.preview.app = self
        self.preview.runtime.log = self.console.event
        commands.append(self.preview.open())
        return commands

    def _compile_handlers(self) -> Dict[str, Any]:
        import types

        module = types.ModuleType(f"pyzed_form_{self.doc.form.name}")
        module.__file__ = str(self.doc.code_path or Path.cwd() / f"{self.doc.form.name}.py")
        exec(compile(self.doc.code, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the user's own code
        return _code.handlers(module)

    def stop_form(self) -> Any:
        """Stops the running form (its uv process or preview window) and the console capture."""
        self.projects.stop()
        self.console.stop()
        if self.preview is not None and self.preview.is_open:
            return self.preview.close()
        return None

    # -- keyboard -------------------------------------------------------------
    def on_key(self, combo: str) -> Any:
        """Handles a key ``combo`` the focused widget did not use.

        Global shortcuts come first, then the code editor's, the picker's arrows, Escape (closes what is
        open or cancels a drag) and, when the canvas has the keyboard, editing and nudging shortcuts.
        """
        action = _commands.by_keys(combo, global_only=True)
        if action is not None and (not self.dialog or action.id in ("palette", "settings", "shortcuts")):
            self.app_menu = None
            return _commands.run(action.id, self)
        if self.focus == "code" and self.editing is not None and not self.dialog:
            handled, result = self.assist.on_key(combo)
            if handled:
                return result
        if self.dialog in ("palette", "add_control", "preview_theme", "preview_language") and combo in ("up", "down"):
            self.picker_index = max(self.picker_index + (1 if combo == "down" else -1), 0)
            return None
        if combo == "escape":
            if self.dialog:
                return self.close_dialog()
            if self.app_menu or self.layout.menu:
                self.app_menu = None
                self.layout.menu = None
                return None
            if self.menu:
                return self.close_menu()
            if self.drag:
                return self.cancel_drag()
            self.tool = None
            return None
        if self.dialog:
            return None
        if self.focus == "code":
            return None
        if self.focus != "canvas":
            return None
        step = self.doc.form.grid if self.snap else 1
        canvas: Dict[str, Callable[[], Any]] = {
            "ctrl-z": self.undo,
            "ctrl-shift-z": self.redo,
            "ctrl-y": self.redo,
            "delete": self.delete,
            "backspace": self.delete,
            "ctrl-c": self.copy,
            "ctrl-x": self.cut,
            "ctrl-v": self.paste,
            "ctrl-d": self.duplicate,
            "ctrl-a": lambda: (self.doc.select_all(), self._selection_changed()),
            "left": lambda: self.doc.nudge(-1, 0),
            "right": lambda: self.doc.nudge(1, 0),
            "up": lambda: self.doc.nudge(0, -1),
            "down": lambda: self.doc.nudge(0, 1),
            "shift-left": lambda: self.doc.nudge(-step, 0),
            "shift-right": lambda: self.doc.nudge(step, 0),
            "shift-up": lambda: self.doc.nudge(0, -step),
            "shift-down": lambda: self.doc.nudge(0, step),
            "enter": lambda: self.open_default_event(self.doc.primary.name) if self.doc.primary else None,
            "g": self.toggle("show_grid"),
        }
        action = canvas.get(combo)
        return action() if action else None

    def cancel_drag(self) -> None:
        """Escape during a drag puts everything back where it was."""
        drag, self.drag = self.drag, None
        self.guides = []
        if drag is None:
            return
        self.drop_name = None
        form = self.doc.form
        for name, (x, y, w, h) in drag.rects.items():
            if name == "":
                form.width, form.height = w, h
            elif form.get(name) is not None:
                c = form[name]
                c.x, c.y, c.width, c.height = x, y, w, h

    # -- view -------------------------------------------------------------------
    def view(self):
        """Builds the whole window: title bar, docks around the tabs, toolbar and surface, the status bar,
        and the menus, popovers, toasts and dialog over them.
        """
        self.sync_code()
        t = self.theme_obj
        canvas = _core.container(surface.form_surface(self, t), width="fill", height="fill", bg=t.background)
        if self.help_shown:
            center = _core.column([self.doc_tabs(t), ui.reference_browser(self.help, on_open_url=self.open_url,
                                                                          theme=t)], width="fill", height="fill")
        elif self.updates.notes_active:
            center = _core.column([self.doc_tabs(t), self.updates.notes_view(t)], width="fill", height="fill")
        else:
            center = _core.column([self.doc_tabs(t), self.toolbar(t) if self.prefs.show_toolbar else None, canvas],
                                  width="fill", height="fill")
        body = _core.container(_core.column([
            self.title_bar(t),
            docks.workspace(self, center, t),
            self.status_bar(t) if self.prefs.show_status_bar else None,
        ], width="fill", height="fill"), width="fill", height="fill", bg=t.background)
        if self.app_menu is not None:
            menu = self.title_menu(self.app_menu, t)
            if self.app_menu == "file":
                body = ui.popover(body, menu, x=8, y=TITLE_HEIGHT, on_dismiss=self.close_app_menu)
            else:  # the View and Help buttons sit at the end of the title bar, before the gear
                right = 8 + 30 * (1 if self.app_menu == "help" else 2)
                body = ui.popover(body, menu, x=right, y=TITLE_HEIGHT, align_x="end", on_dismiss=self.close_app_menu)
        if self.menu is not None:
            menu, mx, my = self.context_menu_at(t)
            body = ui.popover(body, menu, x=mx, y=my, on_dismiss=self.close_menu)
        if self.color_picker is not None:
            placed = self.color_picker_at(t)
            if placed is not None:
                card, cx, cy = placed
                body = ui.popover(body, card, x=cx, y=cy, on_dismiss=self.close_color_picker)
        ghost = self.carry_ghost(t)
        if ghost is not None:
            gx, gy = self.window_pointer
            body = _core.stack([body, _core.pin(ghost, x=gx + 14, y=gy + 10)], width="fill", height="fill")
        # the whole window reports the pointer, for menus and for drags that leave a panel
        body = _core.mouse_area(body, on_move=self.window_moved, on_release=self.window_release)
        body = ui.toasts(body, [ui.toast(x.title, x.message, kind=x.kind, on_dismiss=lambda x=x: self.dismiss_toast(x),
                                         theme=t) for x in self.toasts])
        return ui.layer(body, self.dialog_view(t), on_dismiss=self.close_dialog)

    @property
    def theme_obj(self):
        """The resolved theme the window is drawn with."""
        return self.resolved_theme()

    def title_menu(self, name: str, t) -> Any:
        """The File, View or Help menu, built from the command table."""
        groups = {"file": ("File", "Run"), "view": ("View",), "help": ("Help",)}[name]
        items: List[Any] = []
        for group, actions in _commands.groups():
            if group not in groups:
                continue
            if items:
                items.append(ui.SEPARATOR)
            for a in actions:
                if not a.menu:
                    continue
                items.append(ui.MenuItem(a.label, (lambda a=a: self.run_action(a.id)) if a.enabled(self) else None,
                                         icon=None if a.checked else a.icon, keys=a.keys,
                                         checked=a.checked(self) if a.checked else None,
                                         disabled=not a.enabled(self)))
            if group == "File" and self.prefs.recent:
                items += [ui.SEPARATOR, tr("Recent")]
                for path in self.prefs.recent[:5]:
                    items.append(ui.MenuItem(Path(path).name, lambda path=path: self._open_recent(path),
                                             icon="layout-template"))
            if group == "View":
                items += [ui.SEPARATOR, tr("Panels")]
                for pid, panel in docks.PANELS.items():
                    items.append(ui.MenuItem(f"{panel.title}  ·  {tr(self.layout.docks[pid].capitalize())}",
                                             lambda pid=pid: self.run_panel(pid), icon=panel.icon,
                                             disabled=pid == "code" and self.editing is None))
        return ui.menu(items, width=260, theme=t)

    def run_panel(self, panel: str) -> None:
        """Shows the panel ``panel`` from the View menu, closing the menu."""
        self.app_menu = None
        self.show_panel(panel)

    def _open_recent(self, path: str) -> None:
        self.app_menu = None
        self._guard(lambda: self.open_path(path))

    def title_bar(self, t) -> Any:
        """Returns the title bar: menu, project and file buttons, Run and Stop, View, Help and Settings."""
        doc = self.doc
        start = [
            ui.icon_button("menu", lambda: self.toggle_app_menu("file"), selected=self.app_menu == "file",
                           tooltip=None if self.app_menu else tr("Menu"), theme=t),
            _core.container(_icon("layout-template", size=14, color=t.accent), padding=(0, 4, 0, 6)),
            ui.title_button(self.projects.project.name, lambda: self.show_panel("project"), icon="package")
            if self.projects.project else ui.title_button("Pyzed Design", lambda: self.show_panel("project")),
            ui.label("/", color="text_muted", size="sm", theme=t),
            ui.title_button(doc.display_name, self.open_dialog, icon="file", chevron=True),
            ui.indicator("modified", theme=t) if doc.dirty else None,
            ui.badge("Component", tint="accent", icon="component", theme=t) if scene_panel.is_scene(self) else None,
        ]
        end = [
            ui.button(tr("Run"), self.run_form, icon="play", variant="solid", tint="success", size="sm", keys="f5",
                      theme=t),
            ui.icon_button("square", self.stop_form, size="sm", tooltip=f"{tr('Stop')} (Shift+F5)",
                           disabled=self.console.running is None, theme=t),
            _core.space(width=8),
            ui.icon_button("panels-top-left", lambda: self.toggle_app_menu("view"), selected=self.app_menu == "view",
                           tooltip=None if self.app_menu else tr("View"), theme=t),
            ui.icon_button("circle-help", lambda: self.toggle_app_menu("help"), selected=self.app_menu == "help",
                           tooltip=None if self.app_menu else tr("Help"), theme=t),
            ui.icon_button("settings", self.open_settings, tooltip=f"{tr('Settings')} (Ctrl+,)", theme=t),
        ]
        return ui.title_bar(start, end, height=TITLE_HEIGHT, theme=t)

    def set_designer_theme(self, name: str) -> None:
        """Switches the designer to the theme ``name`` and saves it in the preferences."""
        self.theme = themes.get(name)
        self.prefs.theme = name
        preferences.save(self.prefs)

    def toolbar(self, t) -> Any:
        """Returns the toolbar: file, undo, alignment, sizing, order, grid and code tools.

        It scrolls sideways when the window is too narrow.
        """
        doc = self.doc
        has = bool(doc.selection)
        many = len(doc.selection) > 1

        def tool(icon: str, action: Any, tip: str, *, enabled: bool = True, selected: bool = False,
                 keys: Optional[str] = None) -> Any:
            tip = tr(tip)
            label = f"{tip} ({ui.format_keys(keys)})" if keys else tip
            return ui.icon_button(icon, action, disabled=not enabled, selected=selected, tooltip=label, theme=t)

        sep = _core.container(ui.divider(vertical=True, theme=t), height=18, padding=(0, 4))
        start = [
            tool("file-plus", self.new, "New form", keys="ctrl-n"),
            tool("folder-open", self.open_dialog, "Open", keys="ctrl-o"),
            tool("save", self.save, "Save", keys="ctrl-s"),
            ui.tooltip(ui.button(tr("New component"), self.new_component, icon="component", variant="tinted",
                                 tint="accent", size="sm", theme=t),
                       tr("A reusable piece for forms and other components, not a window"), theme=t),
            sep,
            tool("undo-2", self.undo, "Undo", enabled=doc.history.can_undo, keys="ctrl-z"),
            tool("redo-2", self.redo, "Redo", enabled=doc.history.can_redo, keys="ctrl-shift-z"),
            sep,
            tool("align-start-vertical", lambda: self.align("left"), "Align left", enabled=has),
            tool("align-center-vertical", lambda: self.align("center"), "Align centers", enabled=has),
            tool("align-end-vertical", lambda: self.align("right"), "Align right", enabled=has),
            tool("align-start-horizontal", lambda: self.align("top"), "Align top", enabled=has),
            tool("align-center-horizontal", lambda: self.align("middle"), "Align middles", enabled=has),
            tool("align-end-horizontal", lambda: self.align("bottom"), "Align bottom", enabled=has),
            sep,
            tool("align-horizontal-distribute-center", lambda: self.distribute("horizontal"),
                 "Distribute horizontally", enabled=len(doc.selection) > 2),
            tool("align-vertical-distribute-center", lambda: self.distribute("vertical"), "Distribute vertically",
                 enabled=len(doc.selection) > 2),
            tool("stretch-horizontal", lambda: self.same_size("width"), "Same width", enabled=many),
            tool("stretch-vertical", lambda: self.same_size("height"), "Same height", enabled=many),
            tool("move-horizontal", lambda: self.center("horizontal"), "Center in form horizontally", enabled=has),
            tool("move-vertical", lambda: self.center("vertical"), "Center in form vertically", enabled=has),
            sep,
            tool("bring-to-front", lambda: self.reorder("front"), "Bring to front", enabled=has),
            tool("send-to-back", lambda: self.reorder("back"), "Send to back", enabled=has),
            tool("trash-2", self.delete, "Delete", enabled=has, keys="delete"),
        ]
        end = [
            tool("grid-3x3", self.toggle("show_grid"), "Show grid", selected=self.show_grid, keys="g"),
            tool("magnet", self.toggle("snap"), "Snap to grid", selected=self.snap),
            tool("ruler", self.toggle("smart_guides"), "Smart guides", selected=self.smart_guides),
            tool("scaling", doc.snap_to_grid, "Fit selection to grid"),
            sep,
            tool("code", self.edit_whole_file, "Edit code file", keys="f7"),
        ]
        # One row that scrolls sideways when the window is too narrow for every tool.
        tools = _core.row([*start, sep, *end], spacing=4, align="center")
        return _core.container(
            _core.scrollable(tools, direction="horizontal", scrollbar_width=2, width="fill"),
            padding=(0, 8), height=36, width="fill", align_y="center", bg=t.editor)

    def status_bar(self, t) -> Any:
        """Returns the status bar: pointer position, selection, tool hint, control count, grid and snap.

        While editing code it also shows the cursor position and the language servers.
        """
        doc = self.doc
        x, y = self.pointer
        primary = doc.primary
        if len(doc.selection) > 1:
            info = tr("{count} selected", count=len(doc.selection))
        elif primary is not None:
            info = f"{primary.name}  {primary.width:g}×{primary.height:g} " + tr(
                "at {x}, {y}", x=f"{primary.x:g}", y=f"{primary.y:g}")
        else:
            info = f"{doc.form.name}  {doc.form.width:g}×{doc.form.height:g}"
        tool = tr(_components.get(self.tool).label) if self.tool else None
        start = [
            ui.status_item(f"{x:.0f}, {y:.0f}", icon="mouse-pointer-2"),
            ui.status_item(info, icon="square-dashed"),
            ui.status_item(tr("Placing {tool}: click or drag on the form", tool=tool), icon="plus",
                           color="accent") if tool else None,
        ]
        end = [
            ui.status_item(self.preview_theme, lambda: self.open_preview_picker("theme"), icon="palette",
                           color="accent") if self.preview_theme else None,
            ui.status_item(self.preview_language, lambda: self.open_preview_picker("language"), icon="languages",
                           color="accent") if self.preview_language else None,
            ui.status_item(tr("{count} controls", count=len(doc.form.controls)), icon="layers"),
            ui.status_item(tr("Grid {size}px", size=doc.form.grid), self.toggle("show_grid"), icon="grid-3x3",
                           selected=self.show_grid),
            ui.status_item(tr("Snap"), self.toggle("snap"), icon="magnet", selected=self.snap),
            *self.updates.status_items(t),
        ]
        if self.editing is not None:
            line, column = self.assist.cursor
            end = [ui.status_item(tr("Ln {line}, Col {column}", line=line, column=column), theme=t),
                   *code_panel.server_status_items(self.assist, t, self.open_editor_settings), *end]
        return ui.status_bar(start, end, theme=t)

    def dialog_view(self, t) -> Any:
        """Returns the widget of the open dialog, or ``None`` when no dialog is open."""
        if self.dialog and self.dialog.startswith("project:"):
            return project_panel.dialog(self, t)
        if self.dialog == "confirm":
            return ui.unsaved_changes(self.doc.display_name, self.confirm_save, self.confirm_discard,
                                      self.close_dialog, theme=t)
        if self.dialog == "save_as":
            return ui.modal(
                ui.field("File", ui.input(self.dialog_path, self.set_dialog_path,
                                          on_submit=lambda: self.save_as(self.dialog_path), mono=True, width=280,
                                          theme=t),
                         description=f"Relative to {Path.cwd()}. The code goes next to it as .py.", theme=t),
                title="Save form", on_close=self.close_dialog, width=520, theme=t,
                footer=[ui.button("Cancel", self.close_dialog, variant="ghost", theme=t),
                        ui.button("Save", lambda: self.save_as(self.dialog_path), variant="solid", theme=t)])
        if self.dialog == "open":
            files = self.form_files()
            rows = [ui.list_item(str(p), lambda p=p: self.open_path(p), icon="layout-template", inset=True, theme=t)
                    for p in files if not self.dialog_path or self.dialog_path.lower() in str(p).lower()]
            if not rows:
                rows = [ui.label("No .pzform or .pzcomp files here; type a path above.", size="sm", color="text_muted",
                                 theme=t)]
            return ui.modal(
                _core.column([
                    ui.input(self.dialog_path, self.set_dialog_path, placeholder="Filter or type a path…",
                             icon="search", on_submit=lambda: self.open_path(self.dialog_path), theme=t),
                    _core.container(_core.scrollable(_core.column(rows, width="fill")), height=260),
                ], spacing=10),
                title="Open form or component", on_close=self.close_dialog, width=520, theme=t)
        if self.dialog == "icon_picker":
            return ui.icon_picker_dialog(self.icon_value, self.pick_icon, on_close=self.close_dialog,
                                         theme=t)
        if self.dialog == "editor_settings":
            return code_panel.settings_dialog(self, t)
        if self.dialog == "agent_settings":
            return agent_panel.settings_dialog(self, t)
        named = {"settings": dialogs.settings, "shortcuts": dialogs.shortcuts, "about": dialogs.about,
                 "new": dialogs.new_form, "add_control": dialogs.add_control, "palette": dialogs.palette,
                 "preview_theme": dialogs.preview_theme, "preview_language": dialogs.preview_language}
        if self.dialog in named:
            return named[self.dialog](self, t)
        return None


def design(path: Optional[Union[str, Path]] = None, *, theme: Any = None) -> None:
    """Opens the designer (on ``path`` if given; it is created on first save if missing)."""
    started = time.perf_counter()
    designer = Designer(path, theme=theme)
    telemetry = _telemetry.get()
    if telemetry.active:
        designer.view = telemetry.wrap("render", designer.view)  # type: ignore[method-assign]
    telemetry.session_started(started)
    try:
        designer.run()
    finally:
        telemetry.session_ended()
    if designer.updates.restart_pending:
        # The update swaps the app once this process is gone: a background task still running (a uv
        # command, a download, a sign-in) must not keep the old version alive and delay the restart.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
