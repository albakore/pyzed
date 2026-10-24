"""Pyzed Design: a Visual Basic / Qt Designer style editor for Pyzed forms, built with Pyzed.

    pyzed design login.pzform        # or: python -m pyzed.designer login.pzform

Pick a component in the toolbox and click (or drag a rectangle) on the form to place
it; drag to move, use the handles to resize, and set its properties on the right.
Double-click a control to write the code of its main event. F5 runs the form in a
new window with all its logic.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from .. import _core, _platform, ui
from ..app import App, renderer_info
from ..ui import frame as ui_frame
from ..icons import icon as _icon
from ..theme import themes
from .. import brand
from .. import rendering as _rendering
from . import binding as _binding
from . import spacing
from . import code as _code
from . import components as _components
from . import agent_panel, code_panel, dialogs, docks, file_scan, geometry, panels, preferences, project_panel, surface
from . import profiles as _profiles
from . import settings_ui
from . import commands as _commands
from . import export_panel as _export
from . import keymap as _keymap
from . import files as _files
from . import layout as _layout
from . import roles as _roles
from . import new as _new
from .console import ConsoleController
from . import logs as _logs
from . import locale as _locale
from .locale import tr
from .code_panel import CodeAssist
from .components import Prop
from .document import Document
from . import keymap_editor
from .keymap_editor import KeymapEditor
from .model import SUFFIX, Control
from .project_panel import ProjectController
from .updates import TAB_ID as _NOTES_TAB, UpdateController
from . import project_picker as _project_picker
from . import welcome as _welcome
from . import workspace as _workspace
from .welcome import Welcome
from .windows import Pane, PaneController, is_blank
from .dock_windows import DockWindows
from ..i18n import t as _t
from .runtime import FormWindow
from . import scene as _scene
from . import scene_code as _scene_code
from . import scene_panel
from . import shader_doc as _shader_doc
from . import shader_editor
from . import telemetry as _telemetry
from ..project import Project
from .. import reference as _reference
from .. import animation_player as _animation_player
from . import indentation as _indentation
from . import help as _help
from . import tab_order as _tab_order
from .project_search import ProjectSearch
from . import trust as _trust

Rect = Tuple[float, float, float, float]
TITLE_HEIGHT = 34.0

#: Files the designer opens: forms and components designed visually.
DOCUMENT_SUFFIXES = (SUFFIX, _scene.SUFFIX, _shader_doc.SUFFIX)
#: Every Pyzed file the Open dialog lists: the documents and the animation libraries (``.pzanim``, opened as JSON).
PYZED_SUFFIXES = (*DOCUMENT_SUFFIXES, _animation_player.SUFFIX)
#: What each Pyzed file is, for the Open dialog: suffix -> (kind, icon).
FILE_KINDS = {SUFFIX: ("Form", "layout-template"), _scene.SUFFIX: ("Component", "component"),
              _shader_doc.SUFFIX: ("Shader", "sparkles"), _animation_player.SUFFIX: ("Animation library",
                                                                                     "clapperboard")}

#: What "New" can create: (label, icon, suffix, factory returning a new document).
NEW_DOCUMENT_KINDS: List[Tuple[str, str, str, Callable[[], Document]]] = [
    ("Form", "app-window", SUFFIX, Document),
    ("Component", "component", _scene.SUFFIX, _scene.new_component),
    ("Shader", shader_editor.ICON, _shader_doc.SUFFIX, _shader_doc.new_shader),
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
    #: rectangles of what is inside the form or container being resized, to follow their anchors
    inside: Dict[str, Rect] = field(default_factory=dict)


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
#: Seconds the pointer rests over the form before the status bar shows where it is.
POINTER_REST = 0.12


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
    icon = brand.ICON
    #: Matches the ``dev.pyzed.design.desktop`` file that install.sh writes (Wayland takes the icon from it).
    app_id = "dev.pyzed.design"

    def __init__(self, path: Optional[Union[str, Path]] = None, *, theme: Any = None,
                 language_servers: bool = True) -> None:
        #: When each part of the start ended (``time.perf_counter()``; ``"system"`` is seconds), for the startup
        #: time in the Logs panel (see ``startup_times``).
        self.startup: Dict[str, Any] = {"started": time.perf_counter(), "system": None}
        # the open documents: the main window's tabs, and those moved to windows of their own
        self.panes = PaneController(self)
        #: A file given to open that is not a document (a ``.pzanim``, a script): opened once the panels exist.
        opened_later = None
        if path is not None and Path(path).exists() and Path(path).suffix not in DOCUMENT_SUFFIXES:
            opened_later, path = Path(path), None
            self.doc = Document()
        elif path is not None and Path(path).exists():
            self.doc = _scene.open_document(path)
        elif path is not None and Path(path).suffix == _scene.SUFFIX:
            self.doc = _scene.new_component(Path(path).stem, path)
        elif path is not None and Path(path).suffix == _shader_doc.SUFFIX:
            self.doc = _shader_doc.new_shader(Path(path).stem, path)
        else:
            self.doc = Document(path=Path(path).with_suffix(SUFFIX) if path else None)
        if theme is not None:
            self.theme = theme
        # tools and gestures
        self.tool: Optional[str] = None
        self.drag: Optional[Drag] = None
        #: Edit → Edit tab order: numbering the fields on the canvas.
        self.tab_editor = _tab_order.TabOrderEditor(self)
        #: The Shader view's gestures, search and menus (when a .pzshad is open).
        self.shading = shader_editor.ShaderEditor(self)
        self.pointer: Tuple[float, float] = (0.0, 0.0)
        self.view_pointer: Tuple[float, float] = (0.0, 0.0)
        self.guides: List[Rect] = []
        self.drop_name: Optional[str] = None
        #: the context menu: control name and where it opens, in window coordinates
        self.menu: Optional[Tuple[str, float, float]] = None
        self.window_pointer: Tuple[float, float] = (0.0, 0.0)
        self.carry: Optional[Carry] = None
        self.over_form = False  # the pointer is over the form being designed
        #: The grip tabs drawn by the last view and when the pointer last moved over the form: a move that
        #: changes neither redraws nothing, and the status bar's position follows once the pointer rests.
        self.shown_grips: Dict[int, List[Tuple[str, float, float]]] = {}  # by id() of each document drawn
        self._pointer_moved_at = 0.0
        self._pointer_refresh: Optional[threading.Timer] = None
        self.color_picker: Optional[Tuple[Optional[str], str]] = None  # (control or None, style key) being picked
        self.picker_at: Tuple[float, float] = (0.0, 0.0)  # window point where the picker was opened
        #: The value and setter of each color property shown, so its picker can change it.
        self.picker_targets: Dict[str, Tuple[Any, Callable[[Any], Any]]] = {}
        self.text_editors: set = set()  # "control.prop" lists and tables edited as plain text
        #: outline row under the pointer while carrying, and where it would drop: "before", "inside" or "after"
        self.outline_target: Optional[Tuple[str, str]] = None
        self.focus = "canvas"
        #: The first keys of a chord (such as ctrl-k) waiting for the second.
        self.key_prefix: Optional[str] = None
        # preferences and view options
        self.prefs = preferences.load()
        #: The user's and the open project's preferences, and the user's profiles (see ``profiles``).
        self.profile_store = _profiles.use(_profiles.Store())
        # the Logs panel, the error dialog and the error boundaries (first: everything after may log)
        self.logs = _logs.LogCenter(self)
        # Pyzed's own title bar and window buttons, or the system's frame (applies when the window opens)
        self.frame = "custom" if self.prefs.window_frame else None
        #: The variables of the renderer Pyzed Design started with (``None`` when it was not started by ``design``),
        #: to tell when a change of Settings → Rendering waits for a restart.
        self.rendering_started: Optional[Dict[str, str]] = None
        self.preview_frame: Optional[str] = self.prefs.preview_frame or None
        self.show_grid = self.prefs.show_grid
        self.snap = self.prefs.snap
        self.smart_guides = self.prefs.smart_guides
        self.show_all_hidden = self.prefs.show_all_hidden
        if self.prefs.language:
            _locale.apply(self.prefs.language)
        if theme is None and self.prefs.theme and self.prefs.theme in themes.names():
            self.theme = themes.get(self.prefs.theme)
        self.layout = docks.DockLayout(self.prefs.docks, self.prefs.sizes,
                                       {k: not v for k, v in self.prefs.panels.items()}, self.prefs.order,
                                       self.prefs.windows, self.prefs.active)
        # panels in windows of their own, panel tab drags and work layouts
        self.dock_windows = DockWindows(self)
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
        self.scale = self.prefs.ui_scale
        self.apply_fonts()
        # project files open in the code editor (tabs of the Code panel)
        self.buffers = _files.Buffers(self)
        # the AI agent (Agent panel, inline assist)
        self.agent = agent_panel.AgentController(self)
        self.keymap_editor = KeymapEditor(self)
        # dialogs, messages and the running preview
        self.dialog: Optional[str] = None
        self.dialog_path = ""
        self.pending: Optional[Callable[[], Any]] = None
        self.layout_name_buffer = ""  # the name typed in the "Save layout" dialog
        self.toasts: List[Toast] = []
        self.preview: Optional[FormWindow] = None
        #: A theme and a language to look at the form in (canvas and Run), without changing the form.
        self.preview_theme: Optional[str] = None
        self.icon_value = ""
        self.anchor_presets: Optional[str] = None
        self.anchor_move = False
        self.icon_pick: Optional[Callable[[str], Any]] = None
        self.preview_language: Optional[str] = None
        self.console = ConsoleController(self)
        from .timeline import TimelineEditor

        self.timeline = TimelineEditor(self)
        # restricted mode: the code of a folder the user did not trust does not run
        self.trust = _trust.TrustController(self)
        # the uv project the form belongs to (Project panel)
        self.projects = ProjectController(self)
        self.projects.on_change(self.agent.project_changed)  # the agents work on the active project
        self.settings_ui = settings_ui.SettingsController(self)
        self.projects.on_change(self._project_settings)  # a project may set its own preferences
        # File → Export app…: package the project for each platform (pyzed build)
        self.exporter = _export.ExportController(self)
        # Edit → Find in project…: the Search panel
        self.search = ProjectSearch(self)
        self.updates = UpdateController(self)
        # the welcome window and its gallery of example projects (Help → Welcome)
        self.welcome = Welcome(self)
        #: The title bar's project picker (the projects of this window and the recent ones).
        self.picker_projects = _project_picker.ProjectPicker(self)
        # the built-in reference (Help → Reference): its own tab next to the documents
        self.help = _reference.Browser()
        self.help_open = False
        self.help_active = False
        found = Project.find(path or Path.cwd())
        if found is not None and found.is_pyzed:
            self.projects.attach(found)
        # The project's components (.pzcomp and pz.Component classes) join the toolbox (once trusted).
        start = found.root if found is not None else Path(path).resolve().parent if path else None
        if self.trust.trusted(start or Path.cwd()):
            _scene.discover_project(start)
        elif start is not None and found is None:
            self.trust.opened(start)
        self.title = self.window_title
        if opened_later is not None:
            self.open_path(opened_later)

    def on_start(self) -> Any:
        """Loads the project's tools, checks for updates and adds Pyzed's MCP server to the AI agents of this
        computer when the app starts; returns the commands."""
        self.startup["ready"] = time.perf_counter()
        if self.logs.last_crash:
            self.notify(tr("Pyzed Design closed unexpectedly last time"),
                        tr("The details are in {path} and in the Logs panel",
                           path=_logs.logs_dir() / _logs.PREVIOUS_CRASH_FILE), kind="warning", seconds=10, log=False)
        self.agent.on_start()
        return [c for c in (self.projects.load_tools(), *self.updates.on_start(), *self.dock_windows.restore())
                if c is not None]

    def on_open(self) -> None:
        """The main window is on screen: writes how long that took in the Logs panel (once)."""
        if "window" not in self.startup:
            self.startup["window"] = time.perf_counter()
            self._log_startup()

    def startup_times(self) -> Dict[str, float]:
        """How long each part of the start took, in seconds: ``"system"`` (from the process's start until the
        designer's code ran: loading the app's files and Python, an antivirus scanning them the first time),
        ``"editor"`` (its code and settings), ``"window"`` (the window and the graphics) and ``"total"``."""
        marks = self.startup
        ready = marks.get("ready", marks["started"])
        times = {"editor": ready - marks["started"], "window": marks.get("window", ready) - ready}
        if marks.get("system") is not None:
            times["system"] = marks["system"]
        times["total"] = sum(times.values())
        return {k: round(v, 3) for k, v in times.items()}

    def _log_startup(self) -> None:
        times = self.startup_times()
        if "system" in times:
            _logs.event("designer", "Pyzed Design opened in %.1f s (%.1f s starting the app, %.1f s loading the "
                        "editor, %.1f s opening the window)", times["total"], times["system"], times["editor"],
                        times["window"])
        else:
            _logs.event("designer", "Pyzed Design opened in %.1f s (%.1f s loading the editor, %.1f s opening the "
                        "window)", times["total"], times["editor"], times["window"])
        report = os.environ.get("PYZED_STARTUP_REPORT")
        if report:  # measuring the start (benchmarks, CI): write the times and quit
            try:
                Path(report).write_text(json.dumps(times), encoding="utf-8")
            finally:
                os._exit(0)

    # -- window title ---------------------------------------------------------
    def window_title(self) -> str:
        """Returns the window title: the document's name, after a ``●`` when it has unsaved changes."""
        if self.nothing_open:
            return "Pyzed Design"
        return f"{'● ' if self.doc.dirty else ''}{self.doc.display_name} — Pyzed Design"

    # -- messages -------------------------------------------------------------
    def notify(self, title: str, message: Optional[str] = None, kind: str = "info", seconds: float = 3.0, *,
               log: bool = True) -> None:
        """Shows a toast for ``seconds`` (``kind`` is "info", "success", "warning" or "error") and, with ``log``,
        writes it in the Logs panel.

        Only the four most recent toasts are kept.
        """
        self.toasts.append(Toast(title, message, kind, time.monotonic() + seconds))
        del self.toasts[:-4]
        if not log:
            return
        # every message shown is also in the Logs panel (errors and warnings with their level)
        level = {"error": logging.ERROR, "warning": logging.WARNING}.get(kind, logging.INFO)
        _logs.log("designer").log(level, "%s%s", title, f": {message}" if message else "")

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
        elif self.projects.loading:  # shows the files and branch of a WSL project once they are read
            subs.append(_core.every(0.2, lambda: None, key="designer-loading"))
        elif self.projects.project is not None and self.layout.is_showing("dependencies", self):
            # notices packages added, removed or upgraded outside the editor (a terminal, the agent)
            subs.append(_core.every(1.0, self.projects.poll, key="designer-dependencies"))
        if self.updates.status == "downloading":  # redraws the download progress
            subs.append(_core.every(0.2, lambda: None, key="designer-update"))
        else:  # looks for a new version again every few hours while the designer stays open
            subs.append(_core.every(600, self.updates.tick, key="designer-update-check"))
        if self.agent.active:  # streams the agent's answer and runs its tools on this thread
            subs.append(_core.every(1 / 30, self.agent.poll, key="designer-agent"))
        if self.exporter.running:  # the elapsed time of the build in the Export dialog
            subs.append(_core.every(1.0, lambda: None, key="designer-export"))
        if self.console.running is not None:  # notices when the running form's window is closed
            subs.append(_core.every(1.0, self.console.poll, key="designer-console"))
        subs.extend(self.timeline.subscriptions())  # the Animation panel's preview
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
            if type_ is not None and not _components.get(type_).visual:
                self.add_non_visual(type_)  # it has no place on the form: straight to the tray
                return
            self.tool = None if self.tool == type_ else type_
            self.tab_editor.stop()
            self.focus = "canvas"
        return pick

    def add_non_visual(self, type_: str) -> None:
        """Adds a non-visual component (a timer, a file watcher...) to the form's tray and selects it."""
        self.doc.add(type_, 0, 0, snap=False)
        self.tool = None
        self.focus = "canvas"
        self.right_tab = "properties"
        self._selection_changed()

    def press_tray(self, name: str) -> None:
        """Mouse press on a chip of the component tray: selects that non-visual component."""
        self.focus = "canvas"
        self.menu = None
        self.tool = None
        self.doc.select(name)
        self._selection_changed()

    def set_toolbox_query(self, text: str) -> None:
        """Filters the toolbox by ``text``."""
        self.toolbox_query = text

    # -- pointer gestures on the surface ------------------------------------
    def pointer_moved(self, x: float, y: float) -> Any:
        """Pointer over the form, in form coordinates. Redraws only when what is shown depends on it (a carry,
        the grip tabs under the pointer); the status bar's position follows once the pointer rests."""
        self.pointer = (x, y)
        if self.carry is not None and self.carry.moved:
            self.drop_name = self._carry_container()
            return None
        if self._grips_changed():
            return None
        self._pointer_moved_at = time.monotonic()
        if self._pointer_refresh is None:
            self._refresh_pointer_later(POINTER_REST)
        return _core.UNCHANGED

    def _grips_changed(self) -> bool:
        return surface.grips(self) != self.shown_grips.get(id(self.doc))

    def _refresh_pointer_later(self, delay: float) -> None:
        """Redraws (for the status bar's position) once the pointer has rested ``POINTER_REST`` seconds."""
        def check() -> None:
            rest = POINTER_REST - (time.monotonic() - self._pointer_moved_at)
            if rest > 0.005:
                self._refresh_pointer_later(rest)
                return
            self._pointer_refresh = None
            try:
                _core.post(lambda: None)
            except RuntimeError:  # the app has stopped
                pass

        timer = threading.Timer(delay, check)
        timer.daemon = True
        self._pointer_refresh = timer
        timer.start()

    def window_moved(self, x: float, y: float) -> Any:
        """Pointer anywhere in the window, in window coordinates (menus and drags out of panels). Redraws only
        while something follows the pointer (a control or node carried out of a panel, a dragged tab)."""
        self.window_pointer = (x, y)
        self.shading.window_moved(x, y)
        carry = self.carry
        if carry is not None and not carry.moved:
            ox, oy = carry.origin
            carry.moved = abs(x - ox) + abs(y - oy) > CARRY_THRESHOLD
        if carry is None and self.shading.carry is None and self.dock_windows.drag is None:
            return _core.UNCHANGED
        return None

    def enter_form(self) -> Any:
        """The pointer entered the form being designed."""
        self.over_form = True
        return None if self.carry is not None or self._grips_changed() else _core.UNCHANGED

    def exit_form(self) -> Any:
        """The pointer left the form being designed: a control carried out of a panel has no drop target."""
        self.over_form = False
        if self.carry is not None:
            self.drop_name = None
            return None
        return None if self._grips_changed() else _core.UNCHANGED

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

    def hover_outline(self, name: str, y: float, height: float) -> Any:
        """The pointer over an outline row while carrying: before, inside (a container) or after it."""
        before = self.outline_target
        self._hover_outline(name, y, height)
        return _core.UNCHANGED if self.outline_target == before else None

    def _hover_outline(self, name: str, y: float, height: float) -> None:
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

    def leave_outline(self, name: str) -> Any:
        """The pointer left the outline row ``name``: forgets it as the drop target of a carry."""
        if self.outline_target is None or self.outline_target[0] != name:
            return _core.UNCHANGED
        self.outline_target = None
        return None

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
        if shader_editor.is_shader(self):
            self.shading.window_release()
            return
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

    def pointer_moved_view(self, x: float, y: float) -> Any:
        """Pointer anywhere over the surface's scroll view, in view coordinates (redraws only while dragging)."""
        self.view_pointer = (x, y)
        if self.drag is None:
            return _core.UNCHANGED
        self._drag_to()
        return None

    def _start(self, mode: str, **kwargs: Any) -> None:
        self.drag = Drag(mode, self.view_pointer, start=self.pointer, **kwargs)

    @property
    def rects(self) -> Dict[str, Rect]:
        """Where every control is drawn; controls being dragged follow the pointer, even out of a flex row."""
        drag = self.drag
        free = drag.rects.keys() if drag is not None and drag.mode == "move" and drag.moved else ()
        return _layout.resolve(self.doc.form, free=free)

    @property
    def revealed(self) -> Tuple[Optional[str], Set[str]]:
        """The hidden control drawn in front while it (or something inside it) is selected, and every hidden
        control the canvas shows for the selection (see ``layout.reveal``). Nothing when the outline's eye
        only hides controls in the editor: those stay hidden even when selected."""
        if self.prefs.outline_eye == "editor":
            return None, set()
        return _layout.reveal(self.doc.form, self.doc.selection)

    def hidden_on_canvas(self, control: Control) -> bool:
        """Whether the canvas leaves ``control`` out (or, with every hidden control shown, dims it): hidden
        when the form runs and not revealed, or hidden in the editor, itself or a container holding it."""
        form = self.doc.form
        if self.prefs.outline_eye == "editor":
            return any(c.hidden_in_editor for c in (control, *form.ancestors(control.name)))
        return not _layout.visible(form, control, self.revealed[1])

    def on_canvas(self, control: Control) -> bool:
        """Whether ``control`` is drawn on the canvas (hidden ones only when revealed or all are shown)."""
        return self.show_all_hidden or not self.hidden_on_canvas(control)

    def toggle_eye(self, name: str) -> None:
        """The outline's eye on control ``name``: its Visible, or whether the canvas hides it (``outline_eye``)."""
        control = self.doc.form[name]
        if self.prefs.outline_eye == "editor":
            self.set_field(name, "hidden_in_editor", not control.hidden_in_editor)
        else:
            self.set_field(name, "visible", not control.visible)

    @property
    def drop_target(self):
        """The container highlighted as the place a dragged or new control will go."""
        return self.doc.form.get(self.drop_name) if self.drop_name else None

    def _container_under(self, x: float, y: float, exclude=()) -> Optional[str]:
        form = self.doc.form
        found = _layout.container_at(form, self.rects, x, y, exclude,
                                     shown=lambda c: not self.hidden_on_canvas(c))
        # a dock only takes Dock panels: anything else goes to what holds the dock
        placing = [form[n].type for n in exclude if form.get(n) is not None]
        if not placing:
            carry = self.carry
            placing = list(carry.names) if carry is not None and carry.kind == "tool" else [self.tool or ""]
        while found is not None and _layout.kind(found) == "dock" and any(t != "dock_panel" for t in placing):
            found = form.get(found.parent) if found.parent else None
        return found.name if found is not None else None

    def press_control(self, name: str) -> None:
        """Mouse press on the control ``name``: selects it and starts moving the selection.

        Pressing a control that is already selected makes it the primary one (the alignment reference).
        With a tool picked, the press starts placing a new control instead. Locked controls do not move.
        """
        self.focus = "canvas"
        self.menu = None
        if self.tab_editor.active:
            self.tab_editor.click(name)
            return
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
            inside = {c.name: c.rect for c in self.doc.form.descendants(primary.name)}
            self._start("resize", rects={primary.name: primary.rect}, handle=handle, inside=inside)

    def press_form_grip(self) -> None:
        """Mouse press on the form's corner grip: starts resizing the form."""
        form = self.doc.form
        self._start("form", rects={"": (0.0, 0.0, form.width, form.height)},
                    inside={c.name: c.rect for c in form.controls})

    def press_empty(self) -> None:
        """Mouse press on an empty spot of the form.

        With a tool picked it starts placing a control (click or drag a rectangle); otherwise it clears
        the selection and starts a rubber band selection.
        """
        self.focus = "canvas"
        self.menu = None
        if self.tab_editor.active:  # numbering fields: an empty spot does nothing
            return
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
                self._follow_anchors(name, start)
        elif drag.mode == "create":
            sx, sy = drag.start
            self.drop_name = self._container_under(sx, sy)
        elif drag.mode == "form":
            start = drag.rects[""]
            form.width = max(geometry.snap(start[2] + dx, grid, self.snap), 120)
            form.height = max(geometry.snap(start[3] + dy, grid, self.snap), 80)
            self._follow_anchors(None, start)

    def _follow_anchors(self, parent: Optional[str], start: Rect) -> None:
        """While the form or container ``parent`` is resized from ``start``, what is inside follows its anchors."""
        drag, form = self.drag, self.doc.form
        if drag is None or not self.doc.follow_anchors:
            return
        box = form if parent is None else form[parent]
        _layout.reflow(form, parent, drag.inside, (start[2], start[3]), (box.width, box.height))

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
                      if c.name not in drag.rects and c.name not in inside and c.visible and c.name in rects
                      and _components.spec(c.type).visual]
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
                hit = [c.name for c in form.controls if c.name in rects and _components.spec(c.type).visual
                       and self.on_canvas(c) and geometry.intersects(rects[c.name], band)]
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
        if control is not None and not _components.spec(control.type).visual:  # in the tray: nothing to lay out
            return [
                ui.MenuItem(tr("View code"), self._menu_action(lambda: self.open_default_event(name)), icon="code"),
                ui.MenuItem(tr("Help"), self._menu_action(lambda: self.open_reference(self.help_page_of(name))),
                            icon="book-marked", keys="shift-f1"),
                ui.SEPARATOR,
                ui.MenuItem(tr("Cut"), self._menu_action(self.cut), icon="scissors", keys="ctrl-x"),
                ui.MenuItem(tr("Copy"), self._menu_action(self.copy), icon="copy", keys="ctrl-c"),
                ui.MenuItem(tr("Duplicate"), self._menu_action(self.duplicate), icon="copy-plus", keys="ctrl-d"),
                ui.MenuItem(tr("Enable") if not control.enabled else tr("Disable"), self._menu_action(
                    lambda: self.set_field(name, "enabled", not control.enabled)), icon="power"),
                ui.SEPARATOR,
                ui.MenuItem(tr("Delete"), self._menu_action(self.delete), icon="trash-2", keys="delete", danger=True),
            ]
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
            ui.MenuItem(tr("Bring forward"), self._menu_action(lambda: self.reorder("forward")), icon="move-up",
                        keys=_keymap.shown_keys("bring_forward")),
            ui.MenuItem(tr("Send backward"), self._menu_action(lambda: self.reorder("backward")), icon="move-down",
                        keys=_keymap.shown_keys("send_backward")),
            ui.MenuItem(tr("Bring to front"), self._menu_action(lambda: self.reorder("front")), icon="bring-to-front",
                        keys=_keymap.shown_keys("bring_to_front")),
            ui.MenuItem(tr("Send to back"), self._menu_action(lambda: self.reorder("back")), icon="send-to-back",
                        keys=_keymap.shown_keys("send_to_back")),
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
        width, height = self.panes.window_size()
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
            text = tr(spec.label)
        else:
            control = self.doc.form.get(carry.names[0])
            spec = _components.spec(control.type) if control is not None else None
            text = carry.names[0] if len(carry.names) == 1 else f"{carry.names[0]} +{len(carry.names) - 1}"
        icon = spec.icon if spec is not None else "box"
        return _core.container(_core.row([_icon(icon, size=13, color=_roles.icon_color(spec, t)),
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
        if shader_editor.is_shader(self):
            self.notify(tr("Copied {count} nodes", count=count) if count > 1 else tr("Copied 1 node"))
        else:
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
        """Moves the selected controls in the z-order: to the ``"front"`` or ``"back"``, or one step ``"forward"``
        or ``"backward"`` (see ``Form.reorder``)."""
        self.doc.reorder(where)

    def guarded(self, action: Callable[[], Any]) -> Any:
        """Runs ``action`` (Export, Build) when the project may run code; in restricted mode asks first and runs it
        once trusted."""
        return action() if self.trust.allow(action) else None

    def trust_changed(self, then: Optional[Callable[[], Any]] = None) -> Any:
        """The active folder was just trusted: its components join the toolbox, its environment gets ready, the
        code editor's servers use its ``.venv``, and ``then`` (what restricted mode held back) runs."""
        folder = self.trust.folder()
        if folder is not None:
            _scene.discover_project(folder)
        self.assist.environment_changed()
        commands = [self.projects.prepare(), self.projects.load_tools(), then() if then is not None else None]
        return [c for c in commands if c is not None]

    @property
    def tab_order_mode(self) -> bool:
        """Whether the canvas is numbering the fields' tab order (Edit → Edit tab order)."""
        return self.tab_editor.active

    def toggle_tab_order(self) -> None:
        """Turns the tab order mode of the canvas on or off."""
        self.tab_editor.toggle()

    def set_field(self, name: str, key: str, value: Any) -> None:
        """Sets the field ``key`` (``locked``, ``visible``, ...) of the control ``name`` to ``value``."""
        self.doc.set_field(name, key, value)

    def toggle_anchor(self, name: str, edge: str) -> None:
        """Turns the anchor of the control ``name`` to the ``edge`` of its container on or off."""
        self.doc.toggle_anchor(name, edge)

    def toggle_anchor_presets(self, name: str) -> None:
        """Shows or hides the anchor presets of control ``name`` in the Position section."""
        self.anchor_presets = None if self.anchor_presets == name else name

    def set_anchor(self, name: str, preset: str) -> None:
        """Anchors control ``name`` with ``preset``; with "Also move" on it is also moved to where it points."""
        self.doc.set_anchor(name, preset, move=self.anchor_move)
        self.anchor_presets = None

    def set_offset(self, name: str, side: str, value: float) -> None:
        """Sets the distance from the ``side`` of the container to control ``name``."""
        self.doc.set_offset(name, side, value)

    def set_pivot(self, name: str, x: float, y: float) -> None:
        """Sets the point control ``name`` turns and scales around."""
        self.doc.set_pivot(name, x, y)

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
        width, height = self.panes.window_size()
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

    def toggle_follow_anchors(self) -> None:
        """Turns on or off moving what is inside the form or a container by its anchors when it is resized."""
        self.doc.follow_anchors = not self.doc.follow_anchors

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

    def show_panel(self, panel: str) -> Any:
        """Shows the panel ``panel`` in its dock or window and saves the layout (the console stays pinned open)."""
        if panel == "console":
            self.console.pinned = True
        if panel == "logs":
            self.logs.pinned = True
        _logs.log("layout").debug("Showed the %s panel", panel)
        shown = self.dock_windows.reveal(panel)
        self.layout.menu = None
        self._save_layout()
        return shown

    def toggle_agent(self) -> Any:
        """Shows the Agent panel and focuses its message box, or hides its dock when it is showing."""
        if self.layout.is_showing("agent", self):
            place = self.layout.docks["agent"]
            if place in preferences.DOCKS:
                self.toggle_dock(place)
            else:  # in the center or a window: the document comes back to the front
                pane = self.panes.at(place)
                if pane is not None and pane.docs:
                    pane.front = None
            return None
        self.show_panel("agent")
        return _core.Command.focus(agent_panel.INPUT_ID)

    def move_panel(self, panel: str, dock: str) -> Any:
        """Moves the panel ``panel`` to the dock ``dock`` (or a panel window) and saves the layout."""
        _logs.event("layout", "Moved the %s panel to %s", panel, dock)
        return self.dock_windows.move_to(panel, dock)

    def toggle_dock(self, dock: str) -> None:
        """Shows or hides the dock ``dock`` and saves the layout (a form in a hidden dock stops being the one
        the panels follow)."""
        self.layout.toggle(dock)
        self.layout.menu = None
        if self.layout.closed.get(dock) and self.panes.active is self.panes.at(dock):
            self.panes.activate(self.panes.main)
        self._save_layout()

    def resize_dock(self, dock: str, size: float) -> None:
        """A dock's edge was dragged (called when it is let go)."""
        self.layout.resize(dock, size)
        self._save_layout()

    def dock_visible(self, dock: str) -> bool:
        """Returns whether the dock ``dock`` is open and has a panel or a document to show."""
        return docks.front(self, dock) is not None

    def open_dock_menu(self, dock: str) -> None:
        """Opens the panel menu of the dock ``dock``, or closes it if it is already open."""
        self.layout.menu = None if self.layout.menu == dock else dock

    def close_dock_menu(self) -> None:
        """Closes the dock's panel menu."""
        self.layout.menu = None

    def reset_layout(self) -> Any:
        """Puts every panel back in its default dock and size (closing the panel windows) and saves that."""
        return self.dock_windows.use("Default")

    def use_layout(self, name: str) -> Any:
        """Switches to the work layout ``name`` from the View menu."""
        self.app_menu = None
        return self.dock_windows.use(name)

    def ask_layout_name(self) -> Any:
        """**Save layout as…**: asks for a name for the current arrangement of panels."""
        self.app_menu = None
        self.layout_name_buffer = self.prefs.layout_name if self.prefs.layout_name not in docks.PRESETS else ""
        self.dialog = "save_layout"
        return _core.Command.focus("layout-name")

    def set_layout_name(self, text: str) -> None:
        """Keeps the name typed in the "Save layout" dialog."""
        self.layout_name_buffer = text

    def save_layout_as(self) -> None:
        """Saves the panels as the work layout named in the dialog."""
        if self.dock_windows.save_as(self.layout_name_buffer):
            self.dialog = None
            self.notify(tr("Layout saved"), self.layout_name_buffer.strip(), kind="success")

    def delete_layout(self) -> None:
        """Deletes the saved work layout in use."""
        self.dock_windows.delete(self.prefs.layout_name)

    def _save_layout(self) -> None:
        self.dock_windows.remember()
        snapshot = self.layout.snapshot()
        self.prefs.docks = snapshot["docks"]
        self.prefs.sizes = snapshot["sizes"]
        self.prefs.order = snapshot["order"]
        self.prefs.active = snapshot["active"]
        self.prefs.windows = snapshot["windows"]
        self.prefs.panels = {dock: not closed for dock, closed in self.layout.closed.items()}
        preferences.save(self.prefs)

    # -- preferences, menus and help ---------------------------------------------
    def set_pref(self, key: str, value: Any) -> None:
        """Sets the preference ``key`` to ``value`` and saves the preferences.

        The view options (``show_grid``, ``snap``, ``smart_guides``, ``show_all_hidden``) apply at once.
        """
        setattr(self.prefs, key, value)
        if key in ("show_grid", "snap", "smart_guides", "show_all_hidden"):
            setattr(self, key, value)
        _logs.event("designer", "Setting %s = %r", key, value)
        preferences.save(self.prefs)

    def apply_fonts(self) -> None:
        """Makes the interface and the code use the fonts chosen in the settings (IBM Plex when none)."""
        _core.set_fonts(ui=self.prefs.ui_font or None, code=self.assist.settings.font_family or None)

    def set_ui_font(self, family: str) -> None:
        """The interface font: a family name, or ``""`` for the default (IBM Plex Sans)."""
        self.set_pref("ui_font", family)
        self.apply_fonts()

    def set_ui_scale(self, scale: float) -> None:
        """The size of the whole interface (1.0 is 100%), applied at once to every window."""
        low, high, _ = preferences.UI_SCALE
        scale = min(max(round(float(scale), 2), low), high)
        self.scale = scale
        self.set_pref("ui_scale", scale)

    def zoom_ui(self, step: int) -> None:
        """Zooms the interface in (1), out (-1) or back to 100% (0)."""
        self.set_ui_scale(1.0 if step == 0 else self.scale + step * preferences.UI_SCALE[2])

    def toggle_pref(self, key: str) -> None:
        """Flips the boolean preference ``key`` and saves it."""
        current = getattr(self, key) if key in ("show_grid", "snap", "smart_guides", "show_all_hidden") else \
            getattr(self.prefs, key)
        self.set_pref(key, not current)

    def set_language(self, code: str) -> None:
        """Switches the designer's language to ``code`` and remembers it in the preferences."""
        self.prefs.language = code
        preferences.save(self.prefs)
        _locale.apply(code)

    def open_settings(self, page: Optional[str] = None) -> Any:
        """Opens the Settings dialog (on ``page``, such as "canvas" or "editor.cursor") and focuses its search."""
        self.app_menu = None
        self.settings_ui.open(page)
        self.dialog = "settings"
        return _core.Command.focus(settings_ui.SEARCH_ID)

    # -- settings: scopes and profiles -------------------------------------------
    def change_setting(self, section: str, key: str, value: Any, scope: str = "user") -> None:
        """Sets preference ``key`` of ``section`` ("designer" or "editor") in ``scope`` ("user": the active profile,
        "project": the open project's ``.pyzed/settings.json``), saves it and applies what changes."""
        value = self.profile_store.set(section, key, value, scope)
        _logs.event("designer", "Setting %s.%s = %r (%s)", section, key, value, scope)
        self.apply_settings(section, notify=True)

    def reset_setting(self, section: str, key: str, scope: str = "user") -> None:
        """Puts ``key`` back to its default (``scope="user"``) or drops the project's own value."""
        self.profile_store.reset(section, key, scope)
        self.apply_settings(section, notify=True)

    def reset_all_settings(self, scope: str = "user") -> None:
        """Every preference back to its default in the active profile, or every project setting removed."""
        self.profile_store.reset_all(scope)
        self.apply_settings(notify=True)
        self.notify(tr("Settings reset"), tr("The project uses the user's settings again") if scope == "project"
                    else tr("Every setting of this profile is back to its default"), seconds=3)

    def switch_profile(self, name: str) -> None:
        """Makes profile ``name`` the active one and applies its preferences."""
        self.profile_store.switch(name)
        self.apply_settings(notify=True)

    def create_profile(self, name: str) -> str:
        """Adds a profile with the current preferences and switches to it; returns its name."""
        name = self.profile_store.create(name)
        self.apply_settings(notify=True)
        return name

    def delete_profile(self, name: str) -> None:
        """Deletes profile ``name`` (the default one stays); deleting the active one goes back to the default."""
        if self.profile_store.delete(name):
            self.apply_settings(notify=True)

    def _project_settings(self, project: Optional[Project]) -> None:
        self.profile_store.open_project(project.root if project is not None else None)
        if project is None and self.settings_ui.scope == "project":
            self.settings_ui.scope = "user"
        self.apply_settings()

    def apply_settings(self, section: Optional[str] = None, *, notify: bool = False) -> None:
        """Makes the designer use the preferences of the store (the user's, overlaid with the project's) where they
        differ from the ones in use: theme, language, fonts, scale, view options and the code editor."""
        if section in (None, "editor"):
            values = self.profile_store.effective("editor")
            current = self.assist.settings
            changed = {k: v for k, v in values.items() if getattr(current, k) != v}
            if changed:
                self.assist.settings = replace(current, **changed)
                self.assist.intel.apply_settings(self.assist.settings)
                if "font_family" in changed:
                    self.apply_fonts()
                if changed.get("code_lens"):
                    self.assist.intel.refresh_lenses(self.doc.form)
        if section in (None, "designer"):
            values = self.profile_store.effective("designer")
            changed = {k: v for k, v in values.items() if getattr(self.prefs, k) != v}
            for key, value in changed.items():
                setattr(self.prefs, key, value)
                if key in ("show_grid", "snap", "smart_guides", "show_all_hidden"):
                    setattr(self, key, value)
            if "theme" in changed:
                self.theme = themes.get(changed["theme"]) if changed["theme"] in themes.names() else type(self).theme
            if "language" in changed:
                _locale.apply(changed["language"])
            if "ui_font" in changed:
                self.apply_fonts()
            if "ui_scale" in changed:
                self.scale = changed["ui_scale"]
            if "preview_frame" in changed:
                self.preview_frame = changed["preview_frame"] or None
            if "window_frame" in changed and notify:
                self.notify(tr("Window frame"), tr("Restart Pyzed Design to apply the change"), kind="info")
            if settings_ui.RESTART_KEYS & set(changed) and notify:
                self.notify(tr("Rendering"), tr("Restart Pyzed Design to apply the change"), kind="info")

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
        and when it runs, or (``which="frame"``) in the window frame of platform ``value`` on the canvas
        (``None`` is this system's; remembered in the preferences)."""
        setattr(self, f"preview_{which}", value or None)
        if which == "frame":
            self.prefs.preview_frame = value or ""
            preferences.save(self.prefs)
        self.dialog = None

    def set_window_frame(self, custom: bool) -> None:
        """Draws the designer's own title bar and window buttons (``custom``) or uses the system's frame.
        Saved in the preferences; it applies the next time the designer opens."""
        if custom == bool(self.prefs.window_frame):
            return
        self.set_pref("window_frame", custom)
        self.notify(tr("Window frame"), tr("Restart Pyzed Design to apply the change"), kind="info")

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
        self.dialog_path = str(self.doc.path or self._new_document_path(SUFFIX))

    def focus_panel(self, panel: Optional[str] = None) -> Any:
        """Gives the keyboard to a side panel, so canvas shortcuts stop acting (the Project tree keeps it
        when the pointer comes back to its panel). Only the keys change: nothing is redrawn."""
        if panel == "project" and self.focus == "files":
            return _core.UNCHANGED
        if panel == "animation":  # the timeline's keys: Delete, Space, arrows (see TimelineEditor.on_key)
            self.focus = "timeline"
            return _core.UNCHANGED
        self.focus = panel if panel in ("console", "logs") else "panel"  # their lines take Ctrl+C and Ctrl+A
        return _core.UNCHANGED

    def focus_code(self) -> Any:
        """Gives the keyboard to the code editor (nothing is redrawn)."""
        self.focus = "code"
        return _core.UNCHANGED

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
        event = _components.spec(control.type).default_event
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
        self.buffers.active = None
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
        """The id of the code editor's buffer (a new one for each handler or file opened)."""
        buffer = self.buffers.current
        if buffer is not None:
            return f"file:{id(buffer)}:{buffer.revision}:{self.code_revision}"
        handler = self.editing[0] if self.editing else ""
        return f"code:{handler}:{self.code_revision}"

    def set_code_buffer(self, text: str) -> None:
        """Keeps the code editor's text as it is typed and tells the code assistant."""
        if self.buffers.current is not None:
            self.buffers.set_text(text)
            self.focus = "code"
            self.assist.changed(text)
        elif self.editing is not None:
            self.editing = (self.editing[0], text)
            self.focus = "code"
            self.assist.changed(text)

    def set_code_cursor(self, line: int, column: int) -> Any:
        """The editor's cursor moved to ``line``, ``column``; returns the assistant's command, if any."""
        self.focus = "code"
        return self.assist.moved(line, column)

    def open_editor_settings(self) -> Any:
        """Opens the Settings dialog on the code editor's pages."""
        return self.open_settings(f"editor.{self.assist.settings_section}")

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
        self.notify(tr("Code applied"), kind="success", seconds=1.5)
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
        """Closes the file or the form code the code editor shows (the form code only if it parses)."""
        if self.buffers.current is not None:
            self.buffers.close()
            return
        if self._flush_code():
            self.editing = None
            self.assist.closed()
            if self.buffers.items:
                self.buffers.select(len(self.buffers.items) - 1)

    def show_form_code(self) -> None:
        """Shows the form's code (its tab in the Code panel) instead of an open file."""
        if self.editing is not None:
            self.buffers.select(None)

    def edit_code(self, handler: str) -> bool:
        """Shows function ``handler`` of the form's code (``"*"``: the whole file) in the code editor; ``False``
        if the code open now does not parse."""
        if not self._flush_code():
            return False
        self.buffers.active = None
        self.editing = (handler, self.doc.code if handler == "*" else self.doc.handler_source(handler))
        if handler != "*":
            self.last_handler = handler
        self.code_revision += 1
        self.code_error = None
        self.layout.show("code")
        self.focus = "code"
        self.assist.opened()
        return True

    def edit_whole_file(self) -> None:
        """Opens the form's whole code file in the code editor (F7)."""
        if self._flush_code():
            self.buffers.active = None
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
    def docs(self) -> List[Document]:
        """The documents of the window being worked in (the active pane), as tabs."""
        return self.panes.active.docs

    @property
    def active_doc(self) -> int:
        """The index of the tab in front in the active pane."""
        return self.panes.active.active

    @active_doc.setter
    def active_doc(self, index: int) -> None:
        self.panes.active.active = index

    @property
    def doc(self) -> Document:
        """The document of the active tab."""
        return self.docs[self.active_doc]

    @property
    def nothing_open(self) -> bool:
        """Whether every tab was closed: the main window shows an empty area (``doc`` is a hidden blank form)."""
        return is_blank(self.doc)

    @doc.setter
    def doc(self, value: Document) -> None:
        """Opens ``value`` in a tab: the tab of the same file (in any window), an untouched empty tab, or a new one."""
        self.__dict__["help_active"] = False  # show the document, not the Reference tab
        self.panes.active.front = None
        docs: List[Document] = self.docs
        if not docs:
            docs.append(value)
            self.active_doc = 0
            return
        found = self.panes.find_path(value.path) if value.path is not None else None
        if found is not None:
            pane, i = found
            pane.docs[i] = value
            pane.active = i
            self.panes.active = pane
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
            self.notify(tr("Fix the code first"), self.code_error, kind="error", seconds=4)
            return False
        self.editing = None
        self.menu = None
        self.drag = None
        return True

    def select_doc(self, index: int) -> None:
        """Switches to the tab at ``index``."""
        self.panes.active.front = None
        if index == self.active_doc or not 0 <= index < len(self.docs) or not self._leave_doc():
            return
        self.active_doc = index
        self.code_revision += 1
        self._selection_changed()

    def close_doc(self, index: Optional[int] = None) -> Any:
        """Closes a tab (the active one by default), asking first when it has unsaved changes."""
        index = self.active_doc if index is None else index
        if not 0 <= index < len(self.docs):
            return
        doc = self.docs[index]
        if is_blank(doc):  # nothing open: no tab to close
            return None

        def close() -> None:
            if index == self.active_doc:
                self.editing = None
            self.docs.pop(index)
            pane = self.panes.active
            if not self.docs:
                closing = self.panes.emptied(pane)
                self._selection_changed()
                return closing
            if self.active_doc >= index and self.active_doc > 0:
                self.active_doc -= 1
            self.active_doc = min(self.active_doc, len(self.docs) - 1)
            self._selection_changed()
            return None

        if doc.dirty:
            if index != self.active_doc:
                self.select_doc(index)
            self.pending = close
            self.dialog = "confirm"
            return None
        return close()

    def open_component_of(self, name: str) -> bool:
        """Opens the designed component placed as ``name`` in its own Component tab (double-click)."""
        control = self.doc.form.get(name)
        cls = _component_registry().get(control.type) if control is not None else None
        path = getattr(cls, "scene_file", None) if cls is not None else None
        if path is None or not Path(path).exists():
            return False
        if not self._leave_doc():
            return True
        found = self.panes.find_path(Path(path))
        if found is not None:
            self._show_tab(*found)
            return True
        self.open_path(path)
        return True

    def _show_tab(self, pane: Pane, index: int) -> Any:
        """Brings the tab ``index`` of ``pane`` to the front (and its window, when it has one of its own)."""
        if not self.panes.activate(pane):
            return None
        pane.front = None
        self.select_doc(index)
        if pane.docked:
            self.layout.closed[pane.place] = False
        return _core.Command.focus_window(pane.window) if pane.window is not None and pane.window.is_open else None

    @staticmethod
    def doc_tab_label(doc: Document) -> Tuple[str, str]:
        """The icon and the label of the tab of ``doc``: "Form · Login", "Component · Card"..."""
        scene = getattr(doc, "is_scene", False)
        shader = getattr(doc, "is_shader", False)
        kind = tr("Shader") if shader else tr("Component") if scene else tr("Form")
        return shader_editor.ICON if shader else "component" if scene else "app-window", f"{kind} · {doc.display_name}"

    def doc_tab_items(self, pane: Pane, t) -> Tuple[List[Any], str, Any]:
        """The tabs of the documents of ``pane`` (forms open in the Form view, components in the Component
        view; the main window also has Reference and What's new), the one in front, and the label of its
        view."""
        main = pane is self.panes.main
        tabs = []
        for i, doc in enumerate(pane.docs):
            if is_blank(doc):
                continue
            icon, label = self.doc_tab_label(doc)
            accent = getattr(doc, "is_scene", False) or getattr(doc, "is_shader", False)
            tabs.append(ui.Tab(id=str(i), label=label, icon=icon, icon_color="accent" if accent else None,
                               dirty=doc.dirty))
        notes = self.updates.tab() if main else None
        if notes is not None:
            tabs.append(notes)
        if self.help_open and main:
            tabs.append(ui.Tab(id=HELP_TAB, label=_t("pyzed.reference.title"), icon="book-open", icon_color="accent"))
        view = "" if is_blank(pane.doc) else tr("Shader view") if getattr(pane.doc, "is_shader", False) else \
            tr("Component view") if getattr(pane.doc, "is_scene", False) else tr("Form view")
        active = str(pane.active)
        if main:
            active = HELP_TAB if self.help_shown else _NOTES_TAB if self.updates.notes_active else active
        return tabs, active, ui.label(view, size="xs", color="text_muted", theme=t)

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
        if key == "kind":
            self.new_state["template"] = "blank"
        if key in ("kind", "folder"):  # a free default name for that kind in that folder
            s = self.new_state
            base, suffix = {"component": ("component", _scene.SUFFIX),
                            "shader": ("shader", _shader_doc.SUFFIX)}.get(s["kind"], ("form", SUFFIX))
            folder = Path(s["folder"] or ".")
            taken = {p.stem for p in folder.glob(f"*{suffix}")} if folder.is_dir() else set()
            if not s.get("name") or re.fullmatch(r"(form|component|shader)\d+", s["name"]):
                n = 1
                while f"{base}{n}" in taken:
                    n += 1
                s["name"] = f"{base}{n}"

    def base_components(self) -> List[Path]:
        """The designed components of the project, to inherit from."""
        root = self.projects.project.root if self.projects.project else Path.cwd()
        return file_scan.files(root, (_scene.SUFFIX,))

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
                self.notify(tr("Could not create the component"), str(err), kind="error", seconds=5)
                return
            self.dialog = None
            self.open_path(path)

        self.dialog = None
        self._guard(create)

    def create_new_shader(self) -> None:
        """Creates the shader described in the "New" dialog (from its template), saves it and opens it."""
        s = self.new_state
        path = Path(s.get("folder") or ".") / f"{s.get('name') or 'shader1'}{_shader_doc.SUFFIX}"
        if path.exists():
            self.notify(tr("{name} already exists", name=path.name), kind="warning")
            return

        def create() -> None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                _shader_doc.new_shader(path.stem, path, s.get("template") or "blank").save()
            except (OSError, ValueError) as err:
                self.notify(tr("Could not create the shader"), str(err), kind="error", seconds=5)
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
                self.notify(tr("Could not create the form"), str(err), kind="error", seconds=5)
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

    def open_path(self, path: Union[str, Path]) -> Any:
        """Opens the Pyzed file at ``path``: a form, component or shader in a tab (``.pzform`` is added when there
        is no suffix), an animation library (``.pzanim``) or any other text file in the code editor.

        Switches to its tab if it is already open, and remembers it among the recent files.
        """
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix(SUFFIX)
        if path.suffix not in DOCUMENT_SUFFIXES:
            return self._open_text(path)
        found = self.panes.find_path(path) if path.exists() else None
        if found is not None:
            self.dialog = None
            return self._show_tab(*found)  # already open: keep its unsaved changes
        if not self._leave_doc():
            return
        if self.trust.trusted(path.resolve().parent):
            _scene.discover_project(path)  # a form of another folder may use its components
        else:
            self.trust.opened(path.resolve().parent)
        try:
            self.doc = _scene.open_document(path)
        except (OSError, ValueError) as err:
            _logs.log("document").warning("Could not open %s: %s", path, err)
            self.notify(tr("Could not open the form"), str(err), kind="error", seconds=5)
            return
        _binding.load_texts(path)  # the form's own translations, for @key texts and Preview language
        self.dialog = None
        self.editing = None
        self._selection_changed()
        self.prefs.remember(path)
        preferences.save(self.prefs)
        _logs.event("document", "Opened %s", path)
        self.notify(f"Opened {path.name}")

    def _open_text(self, path: Path) -> Any:
        """Opens a file that is not a document in the code editor; an animation library says what clips it has."""
        if not path.is_file():
            self.notify(tr("Could not open {name}", name=path.name), tr("The file does not exist"), kind="error",
                        seconds=5)
            return None
        if not self.buffers.open(path):
            self.notify(tr("{name} is not a text file", name=path.name), kind="error", seconds=4)
            return None
        self.dialog = None
        if path.suffix == _animation_player.SUFFIX:
            try:
                clips = _animation_player.AnimationLibrary.load(path).names
            except (OSError, ValueError) as err:
                self.notify(tr("{name} is not a valid animation library", name=path.name), str(err),
                            kind="warning", seconds=6)
            else:
                self.notify(tr("Opened {name}", name=path.name),
                            tr("Clips: {clips}. Play them with pz.AnimationPlayer(\"{name}\")",
                               clips=", ".join(clips) or "-", name=path.name), seconds=5)
        _logs.event("document", "Opened %s", path)
        return _core.Command.focus(self.editor_id)

    def save(self) -> Any:
        """Saves the active document, asking for a path first if it has none.

        Does not save if the open code does not parse. A running preview reloads what was saved. While a
        project file has the keyboard in the code editor, that file is saved instead.
        """
        if self.focus == "code" and self.buffers.current is not None:
            buffer = self.buffers.current
            before = buffer.text
            self.buffers.save()
            if buffer.text != before:  # "Convert indentation on save" rewrote it
                return _core.Command.set_editor_text(self.editor_id, buffer.text)
            return None
        if self.nothing_open:
            return None
        if self.doc.path is None:
            self.dialog = "save_as"
            self.dialog_path = self._new_document_path(getattr(self.doc, "suffix", SUFFIX))
            return
        if not self._flush_code():
            self.notify(tr("Fix the code before saving"), self.code_error, kind="error", seconds=4)
            return
        self._convert_form_code()
        path = self.doc.save()
        _logs.event("document", "Saved %s", path)
        self.notify(f"Saved {path.name}", kind="success", seconds=2)
        self.projects.files.refresh()  # a new file, or new git colors, in the Project tab
        if self.preview is not None and self.preview.is_open:
            # the running form picks up the saved layout and code, keeping what was typed in it
            self.preview.runtime.reload(path)

    def _convert_form_code(self) -> None:
        """With "Convert indentation on save", rewrites the form's code with tabs or spaces before it is saved."""
        settings = self.assist.settings
        code = getattr(self.doc, "code", None)
        if not settings.convert_indentation or not isinstance(code, str) or not hasattr(self.doc, "set_code"):
            return
        converted = _indentation.convert(code, settings.hard_tabs, settings.tab_size)
        if converted != code:
            self.doc.set_code(converted)  # the code editor picks it up (sync_code)

    def convert_indentation(self, tabs: Optional[bool] = None) -> Any:
        """Rewrites the indentation of what the code editor shows with tabs (``tabs``) or spaces (by default as
        "Indent with tabs" says); returns the command that puts the new text in the editor."""
        settings = self.assist.settings
        tabs = settings.hard_tabs if tabs is None else tabs
        buffer = self.buffers.current
        if buffer is not None:
            text, python = buffer.text, buffer.language == "py"
        elif self.editing is not None:
            text, python = self.editing[1], True
        else:
            self.notify(tr("Open a file in the code editor first"), kind="warning", seconds=3)
            return None
        converted = _indentation.convert(text, tabs, settings.tab_size, python=python)
        if converted == text:
            self.notify(tr("The indentation already uses tabs") if tabs else
                        tr("The indentation already uses spaces"), seconds=2)
            return None
        self.set_code_buffer(converted)
        self.notify(tr("Indentation converted to tabs") if tabs else tr("Indentation converted to spaces"),
                    kind="success", seconds=2)
        return _core.Command.set_editor_text(self.editor_id, converted)

    def _new_document_path(self, suffix: str) -> str:
        """Where an unsaved document goes by default: the project's UI folder (forms belong to the project), named
        after the form."""
        name = f"{self.doc.form.name.lower()}{suffix}"
        project = self.projects.project
        if project is None:
            return name
        folder = project.ui_dir
        try:
            folder = folder.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            pass
        return (folder / name).as_posix()

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
        if self.dialog == "error":
            self.logs.close_error()
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

    def on_close(self) -> Optional[bool]:
        """The window's close button (or Alt+F4): asks about each form and file with unsaved changes first,
        one at a time, and closes once every answer was Save or Don't save."""
        order = [self.active_doc] + [i for i in range(len(self.docs)) if i != self.active_doc]
        for index in order:
            if 0 <= index < len(self.docs) and self.docs[index].dirty:
                self.select_doc(index)
                if index == self.active_doc:  # (switching fails while the code shown has an error)
                    self.pending = self._close_window
                    self.dialog = "confirm"
                return False
        dirty = self.buffers.dirty
        if dirty:
            index = self.buffers.items.index(dirty[0])
            self.buffers.select(index)
            self.buffers.close(index, then=self._close_window)
            return False
        return None

    def _close_window(self) -> Any:
        """Closes the window once nothing is left unsaved (the next question otherwise)."""
        if self.on_close() is False:
            return None
        return _core.Command.close_window(self)

    def pyzed_files(self, limit: int = 200) -> List[Path]:
        """Returns up to ``limit`` Pyzed files (forms, components, shaders, animation libraries) of the project
        (or the working folder), relative to the working folder when they are inside it.

        Folders such as ``.git``, ``.venv`` and ``node_modules`` are skipped.
        """
        found: List[Path] = []
        here = Path.cwd()
        root = self.projects.project.root if self.projects.project is not None else here
        for path in file_scan.files(root, tuple(PYZED_SUFFIXES)):  # read in the background, not on each view
            try:
                found.append(path.resolve().relative_to(here.resolve()))
            except ValueError:
                found.append(path)
            if len(found) >= limit:
                break
        return found

    def browse_open(self) -> Any:
        """The Open dialog's "Browse…": the system's file dialog, for a Pyzed file anywhere."""
        root = self.projects.project.root if self.projects.project is not None else Path.cwd()

        def chosen(paths: List[str]) -> Any:
            return self.open_path(paths[0]) if paths else None

        return _core.Command.pick_files(chosen, title=tr("Open a Pyzed file"), multiple=False, directory=str(root),
                                        filters=[(tr("Pyzed files"), [x.lstrip(".") for x in PYZED_SUFFIXES]),
                                                 (tr("Python files"), ["py"]), (tr("All files"), ["*"])])

    # -- running ------------------------------------------------------------
    def run_form(self) -> Any:
        """Opens the form in a new window with its handlers loaded fresh (F5)."""
        if not self.trust.allow(self.run_form):  # restricted mode: asks first
            return None
        if not self._flush_code():
            self.notify(tr("Fix the code before running"), self.code_error, kind="error", seconds=4)
            return None
        if scene_panel.is_scene(self):
            return scene_panel.run(self)
        if shader_editor.is_shader(self):
            return self.shading.run()
        project = self.projects.project
        nothing_open = self.doc.path is None and not self.doc.dirty
        if project is not None and project.script is not None and nothing_open:
            return self.run_script()
        if project is not None and nothing_open and project.main_form.is_file():
            self.open_path(project.main_form)  # nothing open: run the startup form
            if self.doc.path is None:
                return None
        if self.nothing_open:
            self.notify(tr("Nothing to run"), tr("Open a form, or a project with a startup file."), kind="info",
                        seconds=4)
            return None
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
            env["PYZED_DESIGNER_RUN"] = "1"
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
            self.notify(tr("The code file has an error"), f"{type(err).__name__}: {err}", kind="error", seconds=6)
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

    def can_use_as_startup(self) -> bool:
        """Whether the open document is a form of the project that is not its startup file yet."""
        project = self.projects.project
        path = getattr(self.doc, "path", None)
        if project is None or path is None or Path(path).suffix != SUFFIX:
            return False
        path = Path(path).resolve()
        return path.is_relative_to(project.root.resolve()) and path != project.startup.resolve()

    def use_as_startup(self) -> None:
        """Makes the open form the file the app starts from (instead of a script or another form)."""
        if self.can_use_as_startup():
            self.projects.set_startup(Path(self.doc.path).resolve())

    def run_script(self) -> Any:
        """Runs the project's ``script`` with ``uv run`` (F5 when no form is open), its output in the console;
        the project's files with unsaved changes are saved first."""
        project = self.projects.project
        if project is None or project.script is None or not self.trust.allow(self.run_script):
            return None
        for index, buffer in enumerate(self.buffers.items):
            if buffer.dirty and Path(buffer.path).resolve().is_relative_to(project.root.resolve()):
                self.buffers.save(index)
        if self.prefs.console_on_run:
            self.layout.show("console")
        self.console.start(project.script.name, "uv run")
        if self.projects.run_script(capture=True):
            self.console.pipe(self.projects.process)
        else:
            self.console.stop(quiet=True)
        return None

    def _compile_handlers(self) -> Dict[str, Any]:
        import types

        module = types.ModuleType(f"pyzed_form_{self.doc.form.name}")
        module.__file__ = str(self.doc.code_path or Path.cwd() / f"{self.doc.form.name}.py")
        exec(compile(self.doc.code, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the user's own code
        return _code.handlers(module)

    def stop_children(self) -> None:
        """Stops every process the designer started (language servers, the running form, an export, agents)."""
        for stop in (self.assist.shutdown, self.projects.stop, self.exporter.cancel, self.agent.shutdown):
            try:
                stop()
            except Exception:  # noqa: BLE001 - one that fails must not keep the others running
                _logs.log("designer").exception("Could not stop %s", getattr(stop, "__qualname__", stop))

    def stop_form(self) -> Any:
        """Stops the running form (its uv process or preview window) and the console capture."""
        self.projects.stop()
        self.console.stop()
        if self.preview is not None and self.preview.is_open:
            return self.preview.close()
        return None

    # -- keyboard -------------------------------------------------------------
    #: Commands whose keys also work while a dialog is open.
    DIALOG_KEYS = ("workspace::palette", "workspace::settings", "workspace::shortcuts", "workspace::open_keymap")

    def key_contexts(self) -> Tuple[str, ...]:
        """The keymap contexts that have the keyboard, deepest first (see ``keymap.CONTEXTS``)."""
        if self.dialog or self.app_menu:
            return ("Workspace",)
        if self.focus == "files":
            return ("ProjectPanel", "Workspace")
        if self.focus == "code" and (self.editing is not None or self.buffers.current):
            return ("Editor", "CodePanel", "Workspace")
        if self.focus == "canvas" and not shader_editor.is_shader(self):
            return ("Canvas", "Workspace")
        return ("Workspace",)

    def on_key(self, combo: str) -> Any:
        """Handles a key ``combo`` the focused widget did not use.

        The keymap decides what keys do, from the deepest context with the keyboard (the project tree, the
        code panel, the canvas) to the whole workspace; the keymap editor takes the keys while it records them.
        Then come the agent's and the shader graph's own keys, the pickers' arrows and Escape (closes what is
        open or cancels a drag).
        """
        if self.dialog == "keymap" and self.keymap_editor.recording is not None:
            return self.keymap_editor.record(combo)
        km = _keymap.get()
        km.refresh()
        keys = _keymap.normalize(combo) or combo
        contexts = self.key_contexts()
        if self.key_prefix is not None:  # the second key of a chord; if none matches, both keys act alone
            prefix, self.key_prefix = self.key_prefix, None
            action = km.resolve(f"{prefix} {keys}", contexts)
            if action is not None:
                return self.run_key_action(action)
            first = km.resolve(prefix, contexts)
            results = [self.run_key_action(first) if first is not None else None, self.on_key(combo)]
            return [r for r in results if r is not None] or None
        if km.is_prefix(keys, [c for c in contexts if c != "Editor"]):
            self.key_prefix = keys
            return None
        if self.focus in ("console", "logs") and not self.dialog and not self.app_menu:
            handled, result = self.logs.on_key(self.focus, combo)
            if handled:
                return result
        if self.focus == "timeline" and not self.dialog and not self.app_menu:  # before Delete deletes controls
            handled, result = self.timeline.on_key(keys)
            if handled:
                return result
        code = self.focus == "code" and (self.editing is not None or self.buffers.current) and not self.dialog
        if code:  # the completion list, find bar and go to line take their keys first
            handled, result = self.assist.on_key(combo)
            if handled:
                return result
        action = km.resolve(keys, contexts)
        if action is not None and (not self.dialog or action in self.DIALOG_KEYS):
            return self.run_key_action(action)
        if self.focus == "agent" and not self.dialog:
            handled, result = self.agent.on_key(combo)
            if handled:
                return result
        if self.app_menu == "projects" and not self.dialog and combo in ("up", "down"):
            self.picker_projects.move(1 if combo == "down" else -1)
            return None
        if self.dialog in ("palette", "add_control", "preview_theme", "preview_language", "preview_frame") \
                and combo in ("up", "down"):
            self.picker_index = max(self.picker_index + (1 if combo == "down" else -1), 0)
            return None
        if shader_editor.is_shader(self) and self.focus == "canvas" and not self.dialog and not self.app_menu \
                and not self.layout.menu and self.color_picker is None:
            handled, result = self.shading.on_key(combo)
            if handled:
                return result
            action = km.resolve(keys, ("Canvas",))
            if action is not None:
                return self.run_key_action(action)
        if combo == "escape":
            if self.dialog:
                return self.close_dialog()
            if self.app_menu or self.layout.menu:
                self.app_menu = None
                self.layout.menu = None
                return None
            if self.menu:
                return self.close_menu()
            if self.logs.menu:
                return self.logs.close_menu()
            if self.drag:
                return self.cancel_drag()
            if self.tab_editor.active:
                self.tab_editor.stop()
            elif self.tool:
                self.tool = None
            elif self.focus == "canvas" and self.revealed[0] is not None:
                self.select_form()  # leave the hidden dialog being edited
        return None

    def run_key_action(self, action: str) -> Any:
        """Runs keymap action ``action`` (``"workspace::save"``, ``"canvas::nudge_left"``...)."""
        namespace, _, name = action.partition("::")
        if namespace == "workspace":
            self.app_menu = None
            return _commands.run(name, self) if name in _commands.BY_ID else None
        if namespace == "canvas":
            return self.canvas_action(name)
        if namespace == "project_panel":
            return self.projects.files.run_action(name)[1]
        if namespace == "code_panel":
            return self.assist.run_action(name)
        if namespace == "editor" and (self.editing is not None or self.buffers.current):
            return _core.Command.editor_action(self.editor_id, name)
        return None

    def canvas_action(self, name: str) -> Any:
        """The canvas's own keymap actions: nudging the selection and opening the main event."""
        step = self.doc.form.grid if self.snap else 1
        moves = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}
        if name.startswith("nudge_"):
            where = name.removeprefix("nudge_")
            scale = step if where.startswith("grid_") else 1
            dx, dy = moves[where.removeprefix("grid_")]
            return self.doc.nudge(dx * scale, dy * scale)
        if name == "open_main_event" and self.doc.primary:
            return self.open_default_event(self.doc.primary.name)
        return None

    def open_keymap(self) -> Any:
        """Opens the keymap editor."""
        self.app_menu = None
        return self.keymap_editor.open()

    def keymap_changed(self) -> None:
        """The keymap editor saved ``keymap.json``: an open, unchanged copy of it in the code panel follows."""
        path = _keymap.get().path
        index = self.buffers.index_of(path) if path.exists() else None
        if index is not None and not self.buffers.items[index].dirty:
            buffer = self.buffers.items[index]
            buffer.text = buffer.saved = path.read_text(encoding="utf-8")
            if self.buffers.active == index:
                self.code_revision += 1

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
        """The whole window, or, if building it fails, a plain view with the error (never a crash)."""
        t = self.theme_obj
        try:
            return self._view()
        except Exception as err:  # noqa: BLE001 - the last boundary: the window must stay usable
            info = ui.ErrorInfo.from_exception(err, where=tr("the window"))
            self.logs.report(info, show=False)
            self.dialog = None  # a dialog may be what fails
            self.menu = self.app_menu = self.logs.menu = None
            return self.fallback_view(info, t)

    def fallback_view(self, info: Any, t) -> Any:
        """What the window shows when it cannot be drawn: the error and ways out of it."""
        card = ui.error_card(info, title=tr("Pyzed Design could not draw the window"), theme=t, actions=[
            ui.button(tr("Reset layout"), self.reset_layout, icon="layout-dashboard", size="sm", variant="ghost",
                      theme=t),
            ui.button(tr("Show the error…"), lambda: self.logs.show_error(info), icon="scan-text", size="sm",
                      variant="ghost", theme=t),
        ])
        body = _core.container(_core.container(card, max_width=720), width="fill", height="fill", center=True,
                               bg=t.background)
        try:
            body = ui.layer(body, self.safe_dialog_view(t), on_dismiss=self.close_dialog)
            if self.__pyzed_frame__() is not None:  # keep a title bar to move and close the window
                body = ui.window_frame(body, height=TITLE_HEIGHT, resize_edges=False, theme=t)
        except Exception:  # noqa: BLE001
            pass
        return body

    def _view(self):
        """Builds the whole window: title bar, docks around the tabs, toolbar and surface, the status bar,
        and the menus, popovers, toasts and dialog over them.
        """
        self.sync_code()
        t = self.theme_obj
        main = self.panes.main
        frame = self.__pyzed_frame__()
        inside = [docks.workspace(self, self.center_view(main, t), t),
                  self.status_bar(t) if self.prefs.show_status_bar else None]
        if frame is not None:  # Pyzed's own window frame, with the title bar's items in it
            start, end = self.title_items(t)
            body = ui.window_frame(_core.column(inside, width="fill", height="fill"), start=start, end=end,
                                   center=self.title_center(t), height=TITLE_HEIGHT, resize_edges=False, theme=t)
        else:
            body = _core.column([self.title_bar(t), *inside], width="fill", height="fill")
        body = _core.container(body, width="fill", height="fill", bg=t.background)
        if self.app_menu is not None:
            menu = self.title_menu(self.app_menu, t)
            if self.app_menu in ("file", "projects", "branches"):
                x = ui_frame.start_x(frame) if frame else 8
                if self.app_menu != "file":
                    x += _project_picker.anchor(self, self.app_menu)
                body = ui.popover(body, menu, x=x, y=TITLE_HEIGHT, on_dismiss=self.close_app_menu)
            else:  # the View and Help buttons sit at the end of the title bar, before the gear
                right = (ui_frame.end_x(frame) if frame else 8) + 30 * (1 if self.app_menu == "help" else 2)
                body = ui.popover(body, menu, x=right, y=TITLE_HEIGHT, align_x="end", on_dismiss=self.close_app_menu)
        # where a dragged tab would go, and a copy of it (always a layer, so a drag never changes the view's shape)
        body = _core.stack([body, self.dock_windows.drag_layer(main, t)], width="fill", height="fill")
        body = self.window_overlays(body, main, t)
        if frame is not None:  # the borders resize the window, above the menus and dialogs
            body = _core.window_edges(body, enabled=not self.window_maximized and frame != "overlay")
        return body

    def center_view(self, pane: Pane, t) -> Any:
        """``_center_view`` through an error boundary: a canvas that fails to draw shows the error instead."""
        return self.logs.boundary(lambda: self._center_view(pane, t), tr("The canvas"), t)

    def _center_view(self, pane: Pane, t) -> Any:
        """The tabs of ``pane`` (the main window's center or a window of its own) over what is in front: a
        panel placed there, or its document's toolbar and canvas (or, in the main window, the Reference or
        What's new tab)."""
        shown = docks.front(self, pane.place)
        if shown is None:
            return None
        tabs = self.dock_windows.tab_bar(pane.place, shown, docks.place_end(self, pane.place, shown, t), t)
        content = docks.panel_body(self, shown[1], t) if shown[0] == "panel" else self.doc_body(pane, t)
        return docks.with_menu(self, pane.place, shown, _core.column([tabs, content], width="fill", height="fill"), t)

    def doc_body(self, pane: Pane, t) -> Any:
        """The document in front of ``pane``: its toolbar and canvas (or, in the main window, the Reference or
        What's new tab). The canvas of a pane that is not the active one wakes up on the first click."""
        if pane is self.panes.main and self.help_shown:
            return ui.reference_browser(self.help, on_open_url=self.open_url, theme=t)
        if pane is self.panes.main and self.updates.notes_active:
            return self.updates.notes_view(t)
        if is_blank(pane.doc):
            return self.nothing_open_view(t)
        with self.panes.showing(pane):
            if shader_editor.is_shader(self):
                content = shader_editor.view(self, t)
            else:
                canvas = _core.container(surface.form_surface(self, t), width="fill", height="fill", bg=t.canvas)
                content = _core.column([self.toolbar(t) if self.prefs.show_toolbar else None, canvas],
                                       width="fill", height="fill")
        return self.panes.asleep(pane, content)

    #: What the empty area offers when every tab is closed.
    NOTHING_OPEN_ACTIONS = ("new", "new_component", "open", "find_file", "open_recent", "palette")

    def nothing_open_view(self, t) -> Any:
        """The main window's center when every tab was closed: what can be opened, with its keys."""
        km = _keymap.get()
        rows = []
        for action_id in self.NOTHING_OPEN_ACTIONS:
            action = _commands.BY_ID.get(action_id)
            if action is None:
                continue
            keys = km.keys_for(f"workspace::{action_id}")
            rows.append(_core.button(
                _core.row([_icon(action.icon, size=14, color=t.icon_muted),
                           ui.label(tr(action.label), size="sm", theme=t, width="fill"),
                           ui.kbd(keys, size="xs", theme=t) if keys else None], spacing=10, align="center"),
                lambda a=action_id: self.run_action(a), padding=(5, 10), width="fill", bg="transparent",
                hover_bg=t.ghost_hover, radius=t.radius))
        body = _core.column([
            _core.container(_icon("app-window", size=40, color=t.text_placeholder), padding=(0, 0, 8, 0)),
            ui.label(tr("No open files"), size="lg", weight="medium", theme=t),
            ui.label(tr("Open a form, a component or a file of the project, or start a new one."), size="sm",
                     color="text_muted", theme=t),
            _core.container(_core.column(rows, spacing=2, width="fill"), padding=(12, 0, 0, 0), width="fill"),
        ], spacing=6, align="center", max_width=340)
        return _core.container(body, width="fill", height="fill", align_x="center", align_y="center",
                               bg=t.background)

    def window_overlays(self, body: Any, pane: Pane, t) -> Any:
        """Adds what opens over a window to ``body``, the view of the window of ``pane``: the context menu,
        toasts and dialogs show in the window used last; the window reports the pointer for menus and drags."""
        here = self.panes.is_here(pane)
        if here and self.projects.files.menu is not None:
            menu, mx, my = self.projects.files.menu_at(t)
            body = ui.popover(body, menu, x=mx, y=my, on_dismiss=self.projects.files.close_menu)
        if here and self.color_picker is not None:
            placed = self.color_picker_at(t)
            if placed is not None:
                card, cx, cy = placed
                body = ui.popover(body, card, x=cx, y=cy, on_dismiss=self.close_color_picker)
        ghost = self.carry_ghost(t) if here else None
        if ghost is not None:
            gx, gy = self.window_pointer
            body = _core.stack([body, _core.pin(ghost, x=gx + 14, y=gy + 10)], width="fill", height="fill")
        if here and self.menu is not None:
            menu, mx, my = self.context_menu_at(t)
            body = ui.popover(body, menu, x=mx, y=my, on_dismiss=self.close_menu)
        if here and self.logs.menu is not None:  # the line menu of the Console and Logs panels
            menu, mx, my = self.logs.menu_at(t)
            body = ui.popover(body, menu, x=mx, y=my, on_dismiss=self.logs.close_menu)
        # a press anywhere marks this window as the one in use (the top layer sees it first, keeps nothing)
        body = _core.stack([body, _core.space(width="fill", height="fill").on(mouse_down=lambda: self.panes.used(pane))],
                           width="fill", height="fill")
        # the whole window reports the pointer, for menus and for drags that leave a panel
        body = _core.mouse_area(body, on_move=self.window_moved, on_release=self.window_release)
        toasts = self.toasts if here else []
        body = ui.toasts(body, [ui.toast(x.title, x.message, kind=x.kind, on_dismiss=lambda x=x: self.dismiss_toast(x),
                                         theme=t) for x in toasts])
        return ui.layer(body, self.safe_dialog_view(t) if here else None, on_dismiss=self.close_dialog)

    def safe_dialog_view(self, t) -> Any:
        """``dialog_view``, but a dialog that fails to draw is closed and reported once (in the console and a
        toast), instead of failing on every frame."""
        try:
            return self.dialog_view(t)
        except Exception as err:  # noqa: BLE001 - one broken dialog must not break the window
            import traceback

            traceback.print_exc()
            failed, self.dialog = self.dialog, None
            info = ui.ErrorInfo.from_exception(err, where=tr("the {name} dialog", name=failed))
            self.logs.report(info, show=False)
            if failed != "error":  # the error dialog itself failing must not loop
                self.logs.show_error(info)
                try:
                    return self.dialog_view(t)
                except Exception:  # noqa: BLE001
                    self.dialog = None
            self.notify(tr("Could not show the dialog"), info.summary, kind="error", seconds=6, log=False)
            return None

    @property
    def theme_obj(self):
        """The resolved theme the window is drawn with."""
        return self.resolved_theme()

    def title_menu(self, name: str, t) -> Any:
        """The File, View or Help menu, built from the command table (or the project picker or branch menu)."""
        if name == "projects":
            return _project_picker.view(self, t)
        if name == "branches":
            return _project_picker.branch_menu(self, t)
        groups = {"file": ("File", "Run"), "view": ("View",), "help": ("Help",)}[name]
        km = _keymap.get()
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
                                         icon=None if a.checked else a.icon, keys=km.keys_for(f"workspace::{a.id}"),
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
                    items.append(ui.MenuItem(f"{panel.title}  ·  {self.layout.place_label(pid)}",
                                             lambda pid=pid: self.run_panel(pid), icon=panel.icon,
                                             disabled=pid == "code" and self.editing is None
                                                      and not self.buffers.items))
                items += [ui.SEPARATOR, tr("Layouts")]
                for name in self.dock_windows.names():
                    items.append(ui.MenuItem(tr(name), lambda name=name: self.use_layout(name),
                                             checked=self.prefs.layout_name == name))
        return ui.menu(items, width=260, theme=t)

    def run_panel(self, panel: str) -> None:
        """Shows the panel ``panel`` from the View menu, closing the menu."""
        self.app_menu = None
        self.show_panel(panel)

    def _open_recent(self, path: str) -> None:
        self.app_menu = None
        self._guard(lambda: self.open_path(path))

    def title_bar(self, t) -> Any:
        """Returns the title bar: menu, project and file buttons, Run, Stop and search, View, Help and Settings."""
        start, end = self.title_items(t)
        return ui.title_bar(start, end, center=self.title_center(t), height=TITLE_HEIGHT, theme=t)

    def title_center(self, t) -> Any:
        """The middle of the title bar: Run and Stop, and the search field that opens the command palette
        (commands, panels, settings and recent files)."""
        search = _core.button(
            _core.container(_core.row([
                _icon("search", size=14, color=t.icon_muted),
                _core.text(tr("Search commands, settings…"), size=13, color=t.text_muted, wrap=False),
                _core.space(width="fill"),
                ui.kbd(_keymap.shown_keys("palette") or "ctrl-shift-p", size="xs", theme=t),
            ], spacing=8, align="center"), height="fill", align_y="center", clip=True),
            self.open_palette, padding=(0, 6, 0, 10), width=320, height=24, bg=t.element,
            border_color=t.border_variant, border_width=1.0, hover_bg=t.element_hover,
            hover_border_color=t.border, radius=t.radius_sm,
        )
        return _core.row([
            ui.button(tr("Run"), self.run_form, icon="play", variant="solid", tint="accent", size="sm",
                      keys=_keymap.shown_keys("run"), theme=t),
            ui.icon_button("square", self.stop_form, size="sm", tooltip=tr("Stop"), keys=_keymap.shown_keys("stop"),
                           disabled=self.console.running is None, theme=t),
            _core.space(width=6),
            search,
        ], spacing=4, align="center")

    def title_items(self, t) -> Tuple[List[Any], List[Any]]:
        """The items at the start (menu, project, file) and end (View, Help, Settings) of the title bar;
        ``title_center`` has the middle."""
        doc = self.doc
        start = [
            ui.icon_button("menu", lambda: self.toggle_app_menu("file"), selected=self.app_menu == "file",
                           tooltip=None if self.app_menu else tr("Menu"), theme=t),
            _core.container(brand.mark(16, theme=t), padding=(0, 4, 0, 6)),
            *_project_picker.title_items(self, t),
            ui.label("/", color="text_muted", size="sm", theme=t),
            ui.title_button(tr("Open…") if self.nothing_open else doc.display_name, self.open_dialog, icon="file",
                            chevron=True),
            ui.indicator("modified", theme=t) if doc.dirty else None,
            ui.badge("Component", tint="accent", icon="component", theme=t) if scene_panel.is_scene(self) else None,
            ui.badge(tr("Shader"), tint="accent", icon=shader_editor.ICON, theme=t)
            if shader_editor.is_shader(self) else None,
        ]
        end = [
            *self.updates.title_items(t),
            self.title_display(t),
            ui.icon_button("panels-top-left", lambda: self.toggle_app_menu("view"), selected=self.app_menu == "view",
                           tooltip=None if self.app_menu else tr("View"), theme=t),
            ui.icon_button("circle-help", lambda: self.toggle_app_menu("help"), selected=self.app_menu == "help",
                           tooltip=None if self.app_menu else tr("Help"), theme=t),
            ui.icon_button("settings", self.open_settings, tooltip=tr("Settings"), keys=_keymap.shown_keys("settings"),
                           theme=t),
        ]
        return start, end

    def title_display(self, t) -> Any:
        """The title bar's LCD: the graphics API drawing the window (or CPU) and the interface size; a click goes
        back to 100%."""
        info = renderer_info()  # None until the window is open (and in screenshots)
        if info is not None:
            renderer = "cpu" if info[0] == "CPU" else info[1].lower()
            tip = f"{info[0]} · {info[1]}"
        else:
            renderer = "tiny-skia" if "tiny" in os.environ.get("ICED_BACKEND", "").lower() else "wgpu"
            tip = renderer
        return ui.tooltip(_core.button(ui.lcd(renderer, f"{self.scale * 100:.0f}%", size=11, height=22, theme=t),
                                       lambda: self.zoom_ui(0), padding=0, bg="transparent", radius=t.radius_sm),
                          f"{tip}: " + tr("Renderer and interface size (a click goes back to 100%)"),
                          keys=_keymap.shown_keys("reset_ui_zoom"), theme=t)

    def set_designer_theme(self, name: str) -> None:
        """Switches the designer to the theme ``name`` and saves it in the preferences."""
        self.theme = themes.get(name)
        self.prefs.theme = name
        preferences.save(self.prefs)

    def toolbar(self, t) -> Any:
        """Returns the form editor's toolbar, in groups that read left to right like Zed's:

        * create and history: "New…" (a form, a component or a shader, picked in the dialog), undo and redo;
        * the selection: align, distribute and size, then order and delete. These only show while something
          is selected (a hint takes their place otherwise), so the bar is not a wall of disabled buttons;
        * at the end, how the canvas behaves (grid, snap, guides, anchors) and the code file.

        Opening and saving live in the File menu and their shortcuts. The bar scrolls sideways when the
        window is too narrow.
        """
        doc = self.doc
        count = len(doc.selection)

        def tool(icon: str, action: Any, tip: str, *, enabled: bool = True, selected: bool = False,
                 command: Optional[str] = None) -> Any:
            keys = _keymap.shown_keys(command) if command else None
            return ui.icon_button(icon, action, disabled=not enabled, selected=selected, tooltip=tr(tip), keys=keys,
                                  theme=t)

        def group(*items: Any) -> Any:
            return _core.row([i for i in items if i is not None], spacing=2, align="center")

        sep = _core.container(ui.divider(vertical=True, theme=t), height=16, padding=(0, 6))
        groups = [
            group(tool("file-plus", self.new, "New form, component or shader…", command="new"),
                  tool("undo-2", self.undo, "Undo", enabled=doc.history.can_undo, command="undo"),
                  tool("redo-2", self.redo, "Redo", enabled=doc.history.can_redo, command="redo")),
        ]
        if count:
            groups += [
                group(tool("align-start-vertical", lambda: self.align("left"), "Align left"),
                      tool("align-center-vertical", lambda: self.align("center"), "Align centers"),
                      tool("align-end-vertical", lambda: self.align("right"), "Align right"),
                      tool("align-start-horizontal", lambda: self.align("top"), "Align top"),
                      tool("align-center-horizontal", lambda: self.align("middle"), "Align middles"),
                      tool("align-end-horizontal", lambda: self.align("bottom"), "Align bottom")),
                group(tool("move-horizontal", lambda: self.center("horizontal"), "Center in form horizontally"),
                      tool("move-vertical", lambda: self.center("vertical"), "Center in form vertically"),
                      tool("align-horizontal-distribute-center", lambda: self.distribute("horizontal"),
                           "Distribute horizontally") if count > 2 else None,
                      tool("align-vertical-distribute-center", lambda: self.distribute("vertical"),
                           "Distribute vertically") if count > 2 else None,
                      tool("stretch-horizontal", lambda: self.same_size("width"), "Same width") if count > 1 else None,
                      tool("stretch-vertical", lambda: self.same_size("height"), "Same height") if count > 1 else None),
                group(tool("bring-to-front", lambda: self.reorder("front"), "Bring to front", command="bring_to_front"),
                      tool("send-to-back", lambda: self.reorder("back"), "Send to back", command="send_to_back"),
                      tool("trash-2", self.delete, "Delete", command="delete")),
            ]
        else:
            groups.append(ui.label(tr("Select controls to align, size and order them"), size="xs",
                                   color="text_muted", wrap=False, theme=t))
        start: List[Any] = []
        for g in groups:
            start += [sep, g] if start else [g]
        def switch(label: str, key: str, tip: str, command: Optional[str] = None) -> Any:
            keys = _keymap.shown_keys(command) if command else None
            return ui.led_toggle(tr(label), getattr(self, key), lambda _on: self.toggle(key)(), tooltip=tr(tip),
                                 keys=keys, theme=t)

        end = [
            _core.row([switch("Snap", "snap", "Snap to grid"), switch("Guides", "smart_guides", "Smart guides"),
                       switch("Grid", "show_grid", "Show grid", "grid")], spacing=4, align="center"),
            _core.space(width=6),
            group(tool("anchor", self.toggle_follow_anchors, "Resize contents with their anchors",
                       selected=doc.follow_anchors),
                  tool("scaling", doc.snap_to_grid, "Fit selection to grid", enabled=bool(count))),
            sep,
            tool("list-ordered", self.toggle_tab_order, "Edit tab order", selected=self.tab_order_mode,
                 enabled=not getattr(doc, "is_scene", False)),
            tool("code", self.edit_whole_file, "Edit code file", command="code_file"),
        ]
        # The editing tools scroll sideways when the window is too narrow; the canvas toggles stay at the end.
        tools = _core.row([
            _core.scrollable(_core.row(start, spacing=0, align="center"), direction="horizontal", scrollbar_width=2,
                             width="fill"),
            sep,
            *end,
        ], spacing=0, align="center", width="fill")
        return _core.container(tools, padding=(0, spacing.GUTTER - 4), height=36, width="fill", align_y="center",
                               bg=t.editor)

    def logs_status_item(self, t) -> Any:
        """The errors and warnings logged so far, in the status bar (a click opens the Logs panel); ``None``
        while there are none."""
        errors, warnings = _logs.summary(self.logs.log.entries)
        if not errors and not warnings:
            return None
        tip = tr("Errors and warnings: open the Logs panel")
        return _core.row([
            ui.status_item(str(errors), self.logs.show_panel, icon="circle-x", icon_color="error", tooltip=tip, theme=t)
            if errors else None,
            ui.status_item(str(warnings), self.logs.show_panel, icon="triangle-alert", icon_color="warning",
                           tooltip=tip, theme=t) if warnings else None,
        ], spacing=2, align="center")

    def status_bar(self, t) -> Any:
        """Returns the status bar: pointer position, selection, tool hint, control count, grid and snap.

        While editing code it also shows the cursor position and the language servers.
        """
        doc = self.doc
        problems = self.logs_status_item(t)
        if shader_editor.is_shader(self):
            return ui.status_bar([*shader_editor.status_items(self, t), problems], [], theme=t)
        x, y = self.pointer
        primary = doc.primary
        if len(doc.selection) > 1:
            info = tr("{count} selected", count=len(doc.selection))
        elif primary is not None and not _components.spec(primary.type).visual:
            info = f"{primary.name}  " + tr("Non-visual")
        elif primary is not None:
            info = f"{primary.name}  {primary.width:g}×{primary.height:g} " + tr(
                "at {x}, {y}", x=f"{primary.x:g}", y=f"{primary.y:g}")
        elif self.nothing_open:
            info = tr("No open files")
        else:
            info = f"{doc.form.name}  {doc.form.width:g}×{doc.form.height:g}"
        tool = tr(_components.get(self.tool).label) if self.tool else None
        start = [
            ui.status_item(tr("Form running"), self.stop_form, led="success",
                           tooltip=tr("The form is running: click to stop it"), keys=_keymap.shown_keys("stop"),
                           theme=t) if self.console.running is not None else None,
            ui.status_item(f"{x:.0f}, {y:.0f}", icon="mouse-pointer-2"),
            ui.status_item(info, icon="square-dashed"),
            ui.status_item(tr("Placing {tool}: click or drag on the form", tool=tool), icon="plus",
                           color="accent") if tool else None,
            problems,
        ]
        end = [
            ui.status_item(self.preview_theme, lambda: self.open_preview_picker("theme"), icon="palette",
                           color="accent") if self.preview_theme else None,
            ui.status_item(self.preview_language, lambda: self.open_preview_picker("language"), icon="languages",
                           color="accent") if self.preview_language else None,
            ui.status_item(ui_frame.PLATFORM_LABELS[surface.frame_style(self)], lambda: self.open_preview_picker("frame"),
                           icon="app-window", tooltip=tr("Window frame shown around the form")),
            ui.status_item(tr("{count} controls", count=len(doc.form.controls)), icon="layers")
            if not self.nothing_open else None,
            ui.status_item(tr("Grid {size}px", size=doc.form.grid), self.toggle("show_grid"), icon="grid-3x3",
                           selected=self.show_grid),
            ui.status_item(tr("Snap"), self.toggle("snap"), icon="magnet", selected=self.snap),
        ]
        if self.buffers.current is not None:
            line, column = self.assist.cursor
            end = [ui.status_item(tr("Ln {line}, Col {column}", line=line, column=column), theme=t), *end]
        elif self.editing is not None:
            line, column = self.assist.cursor
            end = [ui.status_item(tr("Ln {line}, Col {column}", line=line, column=column), theme=t),
                   *code_panel.server_status_items(self.assist, t, self.open_editor_settings), *end]
        return ui.status_bar(start, end, theme=t)

    def dialog_view(self, t) -> Any:
        """Returns the widget of the open dialog, or ``None`` when no dialog is open."""
        if self.dialog == "trust" and self.trust.asking is not None:
            return _trust.dialog(self, t)
        if self.dialog == "error":
            return _logs.error_dialog(self, t)
        if self.dialog and self.dialog.split(":", 1)[0] == "welcome":
            return _welcome.dialog(self, t)
        if self.dialog and self.dialog.startswith("project:"):
            return project_panel.dialog(self, t)
        if self.dialog == "file:unsaved" and self.buffers.closing is not None:
            b = self.buffers
            return ui.unsaved_changes(b.items[b.closing].name, b.confirm_save, b.confirm_discard, b.cancel_close,
                                      theme=t)
        if self.dialog == "save_layout":
            return ui.prompt(tr("Save layout"), self.layout_name_buffer, self.set_layout_name, self.save_layout_as,
                             self.close_dialog, message=tr("Where every panel is, the dock sizes and the panel windows."),
                             placeholder=tr("Layout name"), submit_label=tr("Save"), id="layout-name", theme=t)
        if self.dialog == "confirm":
            return ui.unsaved_changes(self.doc.display_name, self.confirm_save, self.confirm_discard,
                                      self.close_dialog, theme=t)
        if self.dialog == "save_as":
            return ui.modal(
                ui.field(tr("File"), ui.input(self.dialog_path, self.set_dialog_path,
                                          on_submit=lambda: self.save_as(self.dialog_path), mono=True, width=280,
                                          theme=t),
                         description=tr("Relative to {folder}. The code goes next to it as .py.", folder=Path.cwd()),
                         theme=t),
                title=tr("Save form"), on_close=self.close_dialog, width=520, theme=t,
                footer=[ui.button(tr("Cancel"), self.close_dialog, variant="ghost", theme=t),
                        ui.button(tr("Save"), lambda: self.save_as(self.dialog_path), variant="solid", theme=t)])
        if self.dialog == "open":
            rows = []
            for p in self.pyzed_files():
                if self.dialog_path and self.dialog_path.lower() not in p.as_posix().lower():
                    continue
                kind, icon = FILE_KINDS.get(p.suffix, ("File", "file"))
                rows.append(ui.list_item(p.as_posix(), lambda p=p: self.open_path(p), icon=icon,
                                         end=ui.label(tr(kind), size="xs", color="text_muted", theme=t), inset=True,
                                         theme=t))
            if not rows:
                rows = [ui.label(tr("No Pyzed files here; type a path above or browse."), size="sm",
                                 color="text_muted", theme=t)]
            return ui.modal(
                _core.column([
                    ui.input(self.dialog_path, self.set_dialog_path, placeholder=tr("Filter or type a path…"),
                             icon="search", on_submit=lambda: self.open_path(self.dialog_path), theme=t),
                    _core.container(_core.scrollable(_core.column(rows, width="fill")), height=300),
                ], spacing=10),
                title=tr("Open file"), on_close=self.close_dialog, width=560, theme=t,
                footer=[ui.label(".pzform  .pzcomp  .pzshad  .pzanim", size="xs", mono=True, color="text_muted",
                                 theme=t),
                        _core.space(width="fill"),
                        ui.button(tr("Browse…"), self.browse_open, icon="folder-search", variant="ghost", theme=t),
                        ui.button(tr("Cancel"), self.close_dialog, variant="ghost", theme=t)])
        if self.dialog == "icon_picker":
            return ui.icon_picker_dialog(self.icon_value, self.pick_icon, on_close=self.close_dialog,
                                         theme=t)
        if self.dialog == "editor_settings":  # the old name of the editor's pages
            self.dialog = "settings"
            return code_panel.settings_dialog(self, t)
        if self.dialog == "export":
            return _export.dialog(self, t)
        if self.dialog == "keymap":
            return keymap_editor.dialog(self, t)
        named = {"settings": dialogs.settings, "shortcuts": dialogs.shortcuts, "about": dialogs.about,
                 "new": dialogs.new_form, "add_control": dialogs.add_control, "palette": dialogs.palette,
                 "preview_theme": dialogs.preview_theme, "preview_language": dialogs.preview_language,
                 "preview_frame": dialogs.preview_frame}
        if self.dialog in named:
            return named[self.dialog](self, t)
        return None


#: Set while Pyzed Design starts again after its renderer could not open the windows (see ``design``).
RENDERING_FALLBACK = "PYZED_RENDERING_FALLBACK"


def _restart_with_auto_renderer(designer: "Designer", err: RuntimeError, folder: Path) -> bool:
    """When the renderer of Settings → Rendering cannot open the designer's windows (GPU forced on a machine
    without one, a graphics API it lacks), puts it back to Auto and starts Pyzed Design again, once; ``False``
    when that is not what failed."""
    if "graphics" not in str(err) or not designer.prefs.rendering().custom or os.environ.get(RENDERING_FALLBACK):
        return False
    for key in settings_ui.RESTART_KEYS:
        designer.profile_store.reset("designer", key)
    env = dict(os.environ)
    _rendering.forget_inherited(env)
    env[RENDERING_FALLBACK] = "1"
    _logs.event("designer", "The renderer %s could not open the windows: back to Auto", designer.rendering)
    try:
        frozen = getattr(sys, "frozen", False)  # the compiled app: its program, without Python's own options
        subprocess.Popen([sys.executable, *sys.argv[1:]] if frozen else list(sys.orig_argv), cwd=folder, env=env)
    except OSError:
        return False
    return True


def design(path: Optional[Union[str, Path]] = None, *, theme: Any = None) -> None:
    """Opens the designer (on ``path`` if given; it is created on first save if missing)."""
    started = time.perf_counter()
    before = _platform.process_age()  # the time the process took to get here (None where it can't be told)
    # opened from the desktop's menu, the app lacks the PATH of the user's shell (Node from nvm, ~/.local/bin...)
    threading.Thread(target=_platform.use_user_path, daemon=True, name="pyzed-user-path").start()
    first_folder = Path.cwd()
    if not _workspace.usable(Path.cwd()):
        # The installed app starts in its own folder (C:\\Program Files\\Pyzed Design), where new files must not
        # go: what falls back on the current folder (a form saved without a project...) uses the home folder.
        path = Path(path).resolve() if path is not None else None
        os.chdir(Path.home())
    designer = Designer(path, theme=theme)
    designer.startup.update(started=started, system=before)
    # Settings → Rendering: the designer's own windows (a variable set by hand still wins). The apps it starts
    # drop these variables and follow their own project (see ``rendering.forget_inherited``).
    designer.rendering = designer.prefs.rendering()
    _rendering.keep_to_self(designer.rendering.apply())
    designer.rendering_started = designer.rendering.env()
    if os.environ.pop(RENDERING_FALLBACK, None):
        designer.notify(tr("Rendering"), tr("The renderer chosen in Settings could not open the windows: it is back "
                                            "to Auto"), kind="warning", seconds=10)
    if path is None and designer.prefs.show_welcome:
        designer.welcome.open()
    telemetry = _telemetry.get()
    if telemetry.active:
        designer.view = telemetry.wrap("render", designer.view)  # type: ignore[method-assign]
    telemetry.session_started(started)
    designer.logs.install(file=designer.prefs.log_file)  # catches the errors of callbacks and threads
    try:
        designer.run()
    except RuntimeError as err:
        if not _restart_with_auto_renderer(designer, err, first_folder):
            raise
    finally:
        _logs.event("designer", "Pyzed Design closed")
        designer.logs.uninstall()
        telemetry.session_ended()
    if designer.updates.restart_pending:
        # The update swaps the app folder once this process is gone. A child process still running from it (the
        # bundled uv behind the language servers, a run, an export, an agent) would keep the folder in use and,
        # on Windows, make the swap fail: stop them all first.
        designer.stop_children()
        # A background task still running (a download, a sign-in) must not keep the old version alive either.
        for stream in (sys.stdout, sys.stderr):  # None in an app without a console (Windows)
            if stream is not None:
                stream.flush()
        os._exit(0)
