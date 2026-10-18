"""Pyzed Designer: a Visual Basic / Qt Designer style editor for Pyzed forms, built with Pyzed.

    pyzed design login.pzform        # or: python -m pyzed.designer login.pzform

Pick a component in the toolbox and click (or drag a rectangle) on the form to place
it; drag to move, use the handles to resize, and set its properties on the right.
Double-click a control to write the code of its main event. F5 runs the form in a
new window with all its logic.
"""

from __future__ import annotations

import ast
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .. import _core, ui
from ..app import App
from ..icons import icon as _icon
from ..theme import themes
from . import code as _code
from . import components as _components
from . import geometry, panels, surface
from .components import Prop
from .document import Document
from .model import SUFFIX
from .runtime import FormWindow

Rect = Tuple[float, float, float, float]
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build"}


@dataclass
class Drag:
    """A pointer gesture in progress on the design surface."""

    mode: str  # "move" | "resize" | "create" | "band" | "form"
    origin: Tuple[float, float]  # pointer in view coordinates when it started
    start: Tuple[float, float] = (0.0, 0.0)  # pointer in form coordinates when it started
    rects: Dict[str, Rect] = field(default_factory=dict)
    handle: Optional[str] = None
    moved: bool = False


@dataclass
class Toast:
    title: str
    message: Optional[str] = None
    kind: str = "info"
    expires: float = 0.0


class Designer(App):
    """The visual form editor."""

    title = "Pyzed Designer"
    size = (1440, 900)
    min_size = (960, 600)

    def __init__(self, path: Optional[Union[str, Path]] = None, *, theme: Any = None) -> None:
        if path is not None and Path(path).exists():
            self.doc = Document.open(path)
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
        self.menu: Optional[Tuple[str, float, float]] = None
        self.focus = "canvas"
        # view options
        self.show_grid = True
        self.snap = True
        self.smart_guides = True
        self.show_hidden = True
        self.right_tab = "properties"
        self.left_ratio = 0.62
        self.toolbox_query = ""
        self.name_buffer = ""
        # code editor: (handler name or "*" for the whole file, text being edited)
        self.editing: Optional[Tuple[str, str]] = None
        self.last_handler: Optional[str] = None
        self.code_error: Optional[str] = None
        self.code_revision = 0
        # dialogs, messages and the running preview
        self.dialog: Optional[str] = None
        self.dialog_path = ""
        self.pending: Optional[Callable[[], Any]] = None
        self.toasts: List[Toast] = []
        self.preview: Optional[FormWindow] = None
        self.title = self.window_title

    # -- window title ---------------------------------------------------------
    def window_title(self) -> str:
        return f"{'● ' if self.doc.dirty else ''}{self.doc.display_name} — Pyzed Designer"

    # -- messages -------------------------------------------------------------
    def notify(self, title: str, message: Optional[str] = None, kind: str = "info", seconds: float = 3.0) -> None:
        self.toasts.append(Toast(title, message, kind, time.monotonic() + seconds))
        del self.toasts[:-4]

    def _expire_toasts(self) -> None:
        now = time.monotonic()
        self.toasts = [t for t in self.toasts if t.expires > now]

    def dismiss_toast(self, toast: Toast) -> None:
        if toast in self.toasts:
            self.toasts.remove(toast)

    def subscriptions(self):
        return [_core.every(0.5, self._expire_toasts, key="designer-toasts")] if self.toasts else []

    # -- selection ------------------------------------------------------------
    def _selection_changed(self) -> None:
        primary = self.doc.primary
        self.name_buffer = primary.name if primary else ""
        self.menu = None

    def select_form(self) -> None:
        self.doc.select(None)
        self._selection_changed()

    def select_from_outline(self, name: str) -> None:
        self.doc.select(name)
        self.focus = "canvas"
        self._selection_changed()

    def pick_tool(self, type_: Optional[str]) -> Callable[[], None]:
        def pick() -> None:
            self.tool = None if self.tool == type_ else type_
            self.focus = "canvas"
        return pick

    def set_toolbox_query(self, text: str) -> None:
        self.toolbox_query = text

    # -- pointer gestures on the surface ------------------------------------
    def pointer_moved(self, x: float, y: float) -> None:
        """Pointer over the form, in form coordinates."""
        self.pointer = (x, y)

    def pointer_moved_view(self, x: float, y: float) -> None:
        """Pointer anywhere over the surface's scroll view, in view coordinates."""
        self.view_pointer = (x, y)
        if self.drag is not None:
            self._drag_to()

    def _start(self, mode: str, **kwargs: Any) -> None:
        self.drag = Drag(mode, self.view_pointer, start=self.pointer, **kwargs)

    def press_control(self, name: str) -> None:
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
        rects = {c.name: c.rect for c in doc.selected if not c.locked}
        if rects:
            self._start("move", rects=rects)

    def press_handle(self, handle: str) -> None:
        primary = self.doc.primary
        if primary is not None:
            self.focus = "canvas"
            self._start("resize", rects={primary.name: primary.rect}, handle=handle)

    def press_form_grip(self) -> None:
        self._start("form", rects={"": (0.0, 0.0, self.doc.form.width, self.doc.form.height)})

    def press_empty(self) -> None:
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
            x, y = max(x, 0), max(y, 0)
            w, h = min(w, form.width - x), min(h, form.height - y)
            control = form.get(name)
            if control is not None:
                control.x, control.y, control.width, control.height = x, y, w, h
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
        if primary is None or primary.name not in drag.rects:
            primary_rect = next(iter(drag.rects.values()))
        else:
            primary_rect = drag.rects[primary.name]
        px, py = primary_rect[0], primary_rect[1]
        nx = geometry.snap(px + dx, form.grid, self.snap)
        ny = geometry.snap(py + dy, form.grid, self.snap)
        # keep the whole group inside the form
        x1 = min(r[0] for r in drag.rects.values())
        y1 = min(r[1] for r in drag.rects.values())
        x2 = max(r[0] + r[2] for r in drag.rects.values())
        y2 = max(r[1] + r[3] for r in drag.rects.values())
        ddx = max(-x1, min(nx - px, form.width - x2))
        ddy = max(-y1, min(ny - py, form.height - y2))
        self.guides = []
        if self.smart_guides:
            moving = (x1 + ddx, y1 + ddy, x2 - x1, y2 - y1)
            others = [c.rect for c in form.controls if c.name not in drag.rects and c.visible]
            gx, gy, self.guides = geometry.smart_guides(moving, others, (form.width, form.height))
            ddx += gx
            ddy += gy
        for name, (x, y, _, _) in drag.rects.items():
            control = form.get(name)
            if control is not None:
                control.x, control.y = x + ddx, y + ddy

    @property
    def band_rect(self) -> Optional[Rect]:
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
        drag = self.drag
        if drag is None:
            return
        doc = self.doc
        band = self.band_rect
        self.drag = None
        self.guides = []
        if drag.mode == "create" and self.tool:
            if band is not None and band[2] >= 6 and band[3] >= 6:
                doc.add(self.tool, band[0], band[1], band[2], band[3], snap=self.snap)
            else:
                doc.add(self.tool, drag.start[0], drag.start[1], snap=self.snap)
            self.tool = None
            self.right_tab = "properties"
            self._selection_changed()
        elif drag.mode == "band":
            if band is not None:
                doc.select([c.name for c in geometry.in_rect(doc.form.controls, band)])
                self._selection_changed()
        elif drag.moved:
            doc.commit()

    # -- context menu ---------------------------------------------------------
    def open_context_menu(self, name: str) -> None:
        if not self.doc.is_selected(name):
            self.doc.select(name)
            self._selection_changed()
        self.menu = (name, self.pointer[0], self.pointer[1])

    def close_menu(self) -> None:
        self.menu = None

    def _menu_action(self, action: Callable[[], Any]) -> Callable[[], Any]:
        def run() -> Any:
            self.menu = None
            return action()
        return run

    def context_menu(self, t) -> Any:
        assert self.menu is not None
        name = self.menu[0]
        control = self.doc.form.get(name)
        locked = bool(control and control.locked)
        items = [
            ui.MenuItem("View code", self._menu_action(lambda: self.open_default_event(name)), icon="code"),
            ui.SEPARATOR,
            ui.MenuItem("Cut", self._menu_action(self.cut), icon="scissors", keys="ctrl-x"),
            ui.MenuItem("Copy", self._menu_action(self.copy), icon="copy", keys="ctrl-c"),
            ui.MenuItem("Paste", self._menu_action(self.paste), icon="clipboard", keys="ctrl-v",
                        disabled=not self.doc.clipboard),
            ui.MenuItem("Duplicate", self._menu_action(self.duplicate), icon="copy-plus", keys="ctrl-d"),
            ui.SEPARATOR,
            ui.MenuItem("Bring to front", self._menu_action(lambda: self.reorder("front")), icon="bring-to-front"),
            ui.MenuItem("Send to back", self._menu_action(lambda: self.reorder("back")), icon="send-to-back"),
            ui.MenuItem("Unlock" if locked else "Lock", self._menu_action(
                lambda: self.set_field(name, "locked", not locked)), icon="lock-open" if locked else "lock"),
            ui.SEPARATOR,
            ui.MenuItem("Delete", self._menu_action(self.delete), icon="trash-2", keys="delete", danger=True),
        ]
        return ui.menu(items, width=220, theme=t)

    # -- editing commands -------------------------------------------------------
    def undo(self) -> None:
        if self.doc.undo():
            self._selection_changed()

    def redo(self) -> None:
        if self.doc.redo():
            self._selection_changed()

    def delete(self) -> None:
        self.doc.delete()
        self._selection_changed()

    def cut(self) -> None:
        self.doc.cut()
        self._selection_changed()

    def copy(self) -> None:
        count = self.doc.copy()
        if count:
            self.notify(f"Copied {count} control{'s' if count > 1 else ''}")

    def paste(self) -> None:
        self.doc.paste()
        self._selection_changed()

    def duplicate(self) -> None:
        self.doc.duplicate()
        self._selection_changed()

    def align(self, edge: str) -> None:
        self.doc.align(edge)

    def distribute(self, axis: str) -> None:
        self.doc.distribute(axis)

    def same_size(self, which: str) -> None:
        self.doc.same_size(which)

    def center(self, axis: str) -> None:
        self.doc.center(axis)

    def reorder(self, where: str) -> None:
        self.doc.reorder(where)

    def set_field(self, name: str, key: str, value: Any) -> None:
        self.doc.set_field(name, key, value)

    def toggle_anchor(self, name: str, edge: str) -> None:
        self.doc.toggle_anchor(name, edge)

    def prop_setter(self, name: str, prop: Prop) -> Callable[[Any], None]:
        def setter(value: Any) -> None:
            if prop.kind == "number" and isinstance(value, float) and value.is_integer():
                value = int(value)
            self.doc.set_prop(name, prop.name, value)
        return setter

    def set_form(self, key: str, value: Any) -> None:
        self.doc.set_form(key, value)

    def set_name_buffer(self, text: str) -> None:
        self.name_buffer = text

    def commit_name(self) -> None:
        primary = self.doc.primary
        if primary is not None:
            self.name_buffer = self.doc.rename(primary.name, self.name_buffer)
            if self.editing and self.editing[0] != "*":
                self.close_code()

    def toggle(self, attr: str) -> Callable[[], None]:
        def flip() -> None:
            setattr(self, attr, not getattr(self, attr))
        return flip

    # -- docks ------------------------------------------------------------------
    def set_right_tab(self, tab: str) -> None:
        self.right_tab = tab

    def resize_left(self, ratio: float) -> None:
        self.left_ratio = ratio

    def focus_panel(self) -> None:
        self.focus = "panel"

    def focus_code(self) -> None:
        self.focus = "code"

    # -- events and code ----------------------------------------------------
    def open_default_event(self, name: str) -> None:
        self.drag = None
        control = self.doc.form.get(name)
        if control is None:
            return
        event = _components.get(control.type).default_event
        if event:
            self.edit_event(name, event)

    def edit_event(self, target: Optional[str], event: str) -> None:
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
        self.focus = "code"

    def unwire(self, target: Optional[str], event: str) -> None:
        _, events = self.doc.owner(target)
        handler = events.get(event)
        if self.editing and self.editing[0] == handler:
            self.close_code()
        self.doc.unwire(target, event, delete_code=True)

    def set_code_buffer(self, text: str) -> None:
        if self.editing is not None:
            self.editing = (self.editing[0], text)
            self.focus = "code"

    def _flush_code(self) -> bool:
        """Applies the open editor to the document; ``False`` (and an error shown) if it does not parse."""
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
        return True

    def apply_code(self) -> None:
        if self._flush_code():
            self.notify("Code applied", kind="success", seconds=1.5)

    def toggle_whole_file(self) -> None:
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

    def close_code(self) -> None:
        if self._flush_code():
            self.editing = None

    def edit_whole_file(self) -> None:
        if self._flush_code():
            self.editing = ("*", self.doc.code)
            self.code_revision += 1
            self.focus = "code"

    # -- files --------------------------------------------------------------
    def _guard(self, action: Callable[[], Any]) -> Any:
        """Runs ``action`` now, or after confirming that unsaved changes may be discarded."""
        if self.doc.dirty:
            self.pending = action
            self.dialog = "confirm"
            return None
        return action()

    def new(self) -> None:
        self._guard(self._new)

    def _new(self) -> None:
        self.doc = Document()
        self.editing = None
        self._selection_changed()

    def open_dialog(self) -> None:
        self._guard(self._show_open)

    def _show_open(self) -> None:
        self.dialog = "open"
        self.dialog_path = ""

    def open_path(self, path: Union[str, Path]) -> None:
        path = Path(path)
        if not path.suffix:
            path = path.with_suffix(SUFFIX)
        try:
            self.doc = Document.open(path)
        except (OSError, ValueError) as err:
            self.notify("Could not open the form", str(err), kind="error", seconds=5)
            return
        self.dialog = None
        self.editing = None
        self._selection_changed()
        self.notify(f"Opened {path.name}")

    def save(self) -> None:
        if self.doc.path is None:
            self.dialog = "save_as"
            self.dialog_path = f"{self.doc.form.name.lower()}{SUFFIX}"
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
        if not path.strip():
            return
        self.doc.path = Path(path.strip()) if Path(path.strip()).suffix else Path(path.strip()).with_suffix(SUFFIX)
        self.dialog = None
        self.save()

    def set_dialog_path(self, text: str) -> None:
        self.dialog_path = text

    def close_dialog(self) -> None:
        self.dialog = None
        self.pending = None

    def confirm_discard(self) -> Any:
        action, self.pending = self.pending, None
        self.dialog = None
        self.doc.dirty = False
        return action() if action else None

    def form_files(self, limit: int = 40) -> List[Path]:
        found: List[Path] = []
        root = Path.cwd()
        for path in sorted(root.rglob(f"*{SUFFIX}")):
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
        try:
            handlers = self._compile_handlers()
        except Exception as err:  # noqa: BLE001 - show any import-time error to the user
            self.notify("The code file has an error", f"{type(err).__name__}: {err}", kind="error", seconds=6)
            return None
        commands = []
        if self.preview is not None and self.preview.is_open:
            commands.append(self.preview.close())
        self.preview = FormWindow(self.doc.form, handlers)
        self.preview.app = self
        commands.append(self.preview.open())
        return commands

    def _compile_handlers(self) -> Dict[str, Any]:
        import types

        module = types.ModuleType(f"pyzed_form_{self.doc.form.name}")
        module.__file__ = str(self.doc.code_path or Path.cwd() / f"{self.doc.form.name}.py")
        exec(compile(self.doc.code, module.__file__, "exec"), module.__dict__)  # noqa: S102 - the user's own code
        return _code.handlers(module)

    def stop_form(self) -> Any:
        if self.preview is not None and self.preview.is_open:
            return self.preview.close()
        return None

    # -- keyboard -------------------------------------------------------------
    def on_key(self, combo: str) -> Any:
        commands: Dict[str, Callable[[], Any]] = {
            "ctrl-s": self.save,
            "cmd-s": self.save,
            "ctrl-o": self.open_dialog,
            "ctrl-n": self.new,
            "f5": self.run_form,
            "shift-f5": self.stop_form,
            "f7": self.edit_whole_file,
        }
        if combo in commands:
            return commands[combo]()
        if combo == "escape":
            if self.dialog:
                return self.close_dialog()
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
        form = self.doc.form
        for name, (x, y, w, h) in drag.rects.items():
            if name == "":
                form.width, form.height = w, h
            elif form.get(name) is not None:
                c = form[name]
                c.x, c.y, c.width, c.height = x, y, w, h

    # -- view -------------------------------------------------------------------
    def view(self):
        t = self.theme_obj
        center = _core.column([self.toolbar(t), _core.container(surface.form_surface(self, t), width="fill",
                                                                 height="fill", bg=t.background)],
                              width="fill", height="fill")
        if self.editing is not None:
            center = ui.split(center, _core.mouse_area(panels.code_panel(self, t), on_enter=self.focus_code),
                              vertical=True, ratio=0.6, theme=t)
        body = ui.workspace(
            center,
            title_bar=self.title_bar(t),
            left=_core.mouse_area(panels.left_dock(self, t), on_enter=self.focus_panel),
            right=_core.mouse_area(panels.right_dock(self, t), on_enter=self.focus_panel),
            status_bar=self.status_bar(t),
            left_width=230,
            right_width=320,
            theme=t,
        )
        body = ui.toasts(body, [ui.toast(x.title, x.message, kind=x.kind, on_dismiss=lambda x=x: self.dismiss_toast(x),
                                         theme=t) for x in self.toasts])
        return ui.layer(body, self.dialog_view(t), on_dismiss=self.close_dialog)

    @property
    def theme_obj(self):
        return self.resolved_theme()

    def title_bar(self, t) -> Any:
        doc = self.doc
        start = [
            _core.container(_icon("layout-template", size=14, color=t.accent), padding=(0, 4, 0, 8)),
            ui.title_button("Pyzed Designer"),
            ui.label("/", color="text_muted", size="sm", theme=t),
            ui.title_button(doc.display_name, self.open_dialog, icon="file", chevron=True),
            ui.indicator("modified", theme=t) if doc.dirty else None,
        ]
        end = [
            ui.select(themes.names(), t.name, self.set_designer_theme, size="sm", width=150, theme=t),
            _core.space(width=6),
            ui.button("Run", self.run_form, icon="play", variant="solid", tint="success", size="sm", keys="f5",
                      theme=t),
            _core.space(width=8),
        ]
        return ui.title_bar(start, end, theme=t)

    def set_designer_theme(self, name: str) -> None:
        self.theme = themes.get(name)

    def toolbar(self, t) -> Any:
        doc = self.doc
        has = bool(doc.selection)
        many = len(doc.selection) > 1

        def tool(icon: str, action: Any, tip: str, *, enabled: bool = True, selected: bool = False,
                 keys: Optional[str] = None) -> Any:
            label = f"{tip} ({ui.format_keys(keys)})" if keys else tip
            return ui.icon_button(icon, action, disabled=not enabled, selected=selected, tooltip=label, theme=t)

        sep = _core.container(ui.divider(vertical=True, theme=t), height=18, padding=(0, 4))
        start = [
            tool("file-plus", self.new, "New form", keys="ctrl-n"),
            tool("folder-open", self.open_dialog, "Open", keys="ctrl-o"),
            tool("save", self.save, "Save", keys="ctrl-s"),
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
        doc = self.doc
        x, y = self.pointer
        primary = doc.primary
        if len(doc.selection) > 1:
            info = f"{len(doc.selection)} selected"
        elif primary is not None:
            info = f"{primary.name}  {primary.width:g}×{primary.height:g} at {primary.x:g}, {primary.y:g}"
        else:
            info = f"{doc.form.name}  {doc.form.width:g}×{doc.form.height:g}"
        tool = _components.get(self.tool).label if self.tool else None
        start = [
            ui.status_item(f"{x:.0f}, {y:.0f}", icon="mouse-pointer-2"),
            ui.status_item(info, icon="square-dashed"),
            ui.status_item(f"Placing {tool}: click or drag on the form", icon="plus", color="accent") if tool else None,
        ]
        end = [
            ui.status_item(f"{len(doc.form.controls)} controls", icon="layers"),
            ui.status_item(f"Grid {doc.form.grid}px", self.toggle("show_grid"), icon="grid-3x3",
                           selected=self.show_grid),
            ui.status_item("Snap", self.toggle("snap"), icon="magnet", selected=self.snap),
        ]
        return ui.status_bar(start, end, theme=t)

    def dialog_view(self, t) -> Any:
        if self.dialog == "confirm":
            return ui.modal(
                ui.label("The current form has unsaved changes. Discard them?", theme=t),
                title="Unsaved changes", on_close=self.close_dialog, width=420, theme=t,
                footer=[ui.button("Cancel", self.close_dialog, variant="ghost", theme=t),
                        ui.button("Discard", self.confirm_discard, variant="solid", tint="error", theme=t)])
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
                rows = [ui.label("No .pzform files here; type a path above.", size="sm", color="text_muted",
                                 theme=t)]
            return ui.modal(
                _core.column([
                    ui.input(self.dialog_path, self.set_dialog_path, placeholder="Filter or type a path…",
                             icon="search", on_submit=lambda: self.open_path(self.dialog_path), theme=t),
                    _core.container(_core.scrollable(_core.column(rows, width="fill")), height=260),
                ], spacing=10),
                title="Open form", on_close=self.close_dialog, width=520, theme=t)
        return None


def design(path: Optional[Union[str, Path]] = None, *, theme: Any = None) -> None:
    """Opens the designer (on ``path`` if given; it is created on first save if missing)."""
    Designer(path, theme=theme).run()
