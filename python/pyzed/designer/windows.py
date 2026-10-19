"""Document tabs in more than one window.

Every window of the designer shows a *pane*: its own row of document tabs above the toolbar
and the canvas. The main window's pane sits between the docks. A tab dragged out of its window
(or **Move tab to new window**) opens in a window of its own; dragging a tab onto another
window stacks it among that window's tabs, and dragging it along a tab row reorders it.

The panels (Properties, Outline, Code...) stay in the main window and follow the pane used
last, like the tool windows of an IDE. A pane that is not the active one shows its document
but its canvas only wakes up on the first click, so a click never edits a form you were not
looking at. Closing a document window moves its tabs back to the main window.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, List, Optional, Tuple

from .. import _core, ui
from ..app import Window
from .document import Document
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Size of a new document window when the main window's size is not known yet.
WINDOW_SIZE = (1100.0, 760.0)
#: Where the pointer ends up inside a new window: over its first tab.
GRAB_OFFSET = (90.0, 14.0)
#: What a pane that is not the active one should not show: the gestures of the active pane.
TRANSIENT = {"drag": None, "guides": [], "drop_name": None, "menu": None}


class Pane:
    """The documents shown as tabs in one window, and which one is in front."""

    __slots__ = ("docs", "active", "window")

    def __init__(self, docs: Optional[List[Document]] = None, active: int = 0,
                 window: Optional["DocWindow"] = None) -> None:
        self.docs: List[Document] = docs if docs is not None else []
        self.active = active
        self.window = window

    @property
    def doc(self) -> Document:
        """The document in front."""
        return self.docs[self.active]

    def __repr__(self) -> str:
        return f"<Pane {[d.display_name for d in self.docs]} active={self.active}>"


class DocWindow(Window):
    """A window with its own document tabs, toolbar and canvas."""

    min_size = (480.0, 360.0)

    def __init__(self, designer: "Designer", pane: Pane, *, size: Optional[Tuple[float, float]] = None,
                 position: Optional[Tuple[float, float]] = None) -> None:
        self.designer = designer
        self.app = designer
        self.pane = pane
        pane.window = self
        self.size = size or WINDOW_SIZE
        if position is not None:
            self.position = position
        self.title = self.window_title

    def window_title(self) -> str:
        """The document in front, after a ``●`` when it has unsaved changes."""
        doc = self.pane.doc if self.pane.docs else None
        if doc is None:
            return "Pyzed Design"
        return f"{'● ' if doc.dirty else ''}{doc.display_name} — Pyzed Design"

    def view(self) -> Any:
        return self.designer.panes.window_view(self.pane)

    def on_close(self) -> None:
        """Closing the window keeps its documents: they go back to the main window."""
        self.designer.panes.closed(self.pane)


class TabDrag:
    """A document tab being dragged: from which pane, which tab, and where it would land in its row."""

    __slots__ = ("pane", "index", "over")

    def __init__(self, pane: Pane, index: int) -> None:
        self.pane, self.index = pane, index
        self.over: Optional[int] = None


class PaneController:
    """The panes of the designer (one per window) and the tab drags between them."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.main = Pane()
        self.panes: List[Pane] = [self.main]
        #: The pane the panels, the menus and the keyboard work on.
        self.active = self.main
        #: The pane whose window was used last: menus, dialogs and toasts open there.
        self.here = self.main
        self.drag: Optional[TabDrag] = None

    # -- lookups ----------------------------------------------------------------
    def all_docs(self) -> List[Document]:
        """Every open document, in every window."""
        return [doc for pane in self.panes for doc in pane.docs]

    def find(self, doc: Document) -> Optional[Tuple[Pane, int]]:
        """The pane and tab index of ``doc``."""
        for pane in self.panes:
            for i, other in enumerate(pane.docs):
                if other is doc:
                    return pane, i
        return None

    def find_path(self, path: Any) -> Optional[Tuple[Pane, int]]:
        """The pane and tab index of the document saved at ``path``."""
        target = path.resolve()
        for pane in self.panes:
            for i, other in enumerate(pane.docs):
                if other.path is not None and other.path.resolve() == target:
                    return pane, i
        return None

    def window_size(self, pane: Optional[Pane] = None) -> Tuple[float, float]:
        """The size of the window that shows ``pane`` (the one used last by default)."""
        pane = pane or self.here
        host: Any = pane.window if pane.window is not None else self.d
        return host.window_size or host.size

    # -- switching --------------------------------------------------------------
    def activate(self, pane: Pane) -> bool:
        """Makes ``pane`` the one the panels follow; ``False`` when the code editor cannot be left yet."""
        self.here = pane
        if pane is self.active:
            return True
        if not self.d._leave_doc():
            self.d.notify("Fix the code first", self.d.code_error, kind="error", seconds=4)
            return False
        self.active = pane
        self.d.help_active = False
        self.d.code_revision += 1
        self.d._selection_changed()
        return True

    def select(self, pane: Pane, tab_id: str) -> Any:
        """A tab of ``pane`` was pressed."""
        if not self.activate(pane):
            return None
        return self.d._select_tab(tab_id)

    def close(self, pane: Pane, tab_id: str) -> Any:
        """The close button of a tab of ``pane`` was pressed."""
        if not self.activate(pane):
            return None
        return self.d._close_tab(tab_id)

    def used(self, pane: Pane) -> None:
        """A press anywhere in the window of ``pane``: menus and dialogs open there from now on."""
        self.here = pane

    @contextmanager
    def showing(self, pane: Pane) -> Iterator[None]:
        """Builds the view of ``pane`` as if it were the active one, without the active pane's gestures."""
        if pane is self.active:
            yield
            return
        d = self.d
        saved = {key: getattr(d, key) for key in TRANSIENT}
        active = self.active
        try:
            for key, value in TRANSIENT.items():
                setattr(d, key, list(value) if isinstance(value, list) else value)
            self.active = pane
            yield
        finally:
            self.active = active
            for key, value in saved.items():
                setattr(d, key, value)

    # -- moving tabs ------------------------------------------------------------
    def emptied(self, pane: Pane) -> Any:
        """``pane`` lost its last tab: the main window gets an empty form, another window closes."""
        if pane.docs:
            return None
        if pane is self.main:
            pane.docs.append(Document())
            pane.active = 0
            return None
        self.panes.remove(pane)
        if self.active is pane:
            self.active = self.main
        if self.here is pane:
            self.here = self.main
        window, pane.window = pane.window, None
        return window.close() if window is not None and window.is_open else None

    def move(self, source: Pane, index: int, target: Pane, at: Optional[int] = None) -> Any:
        """Moves the tab ``index`` of ``source`` to ``target`` (at ``at``, else last) and shows it there."""
        if not 0 <= index < len(source.docs) or not self.d._leave_doc():
            return None
        doc = source.docs.pop(index)
        if source.active > index or source.active >= len(source.docs):
            source.active = max(source.active - 1, 0)
        at = len(target.docs) if at is None else max(0, min(at, len(target.docs)))
        target.docs.insert(at, doc)
        target.active = at
        self.active = self.here = target
        self.d.help_active = False
        self.d.code_revision += 1
        self.d._selection_changed()
        return self.emptied(source)

    def reorder(self, pane: Pane, index: int, at: int) -> None:
        """Moves the tab ``index`` of ``pane`` to the insertion point ``at`` of the same row."""
        if not 0 <= index < len(pane.docs):
            return
        front = pane.doc
        if at > index:
            at -= 1
        doc = pane.docs.pop(index)
        pane.docs.insert(max(0, min(at, len(pane.docs))), doc)
        pane.active = pane.docs.index(front)

    def detach(self, source: Pane, index: int, screen: Optional[Tuple[float, float]] = None) -> Any:
        """Opens the tab ``index`` of ``source`` in a new window (under the pointer at ``screen``)."""
        if not 0 <= index < len(source.docs):
            return None
        if source is not self.main and len(source.docs) == 1:  # already alone: just move its window
            if screen is None or source.window is None:
                return None
            return _core.Command.move_window(screen[0] - GRAB_OFFSET[0], screen[1] - GRAB_OFFSET[1],
                                             source.window)
        pane = Pane()
        position = (screen[0] - GRAB_OFFSET[0], screen[1] - GRAB_OFFSET[1]) if screen is not None else None
        width, height = self.window_size(self.main)
        window = DocWindow(self.d, pane, size=(min(width, WINDOW_SIZE[0]), min(height, WINDOW_SIZE[1])),
                           position=position)
        self.panes.append(pane)
        closing = self.move(source, index, pane)
        if not pane.docs:  # the code editor could not be left
            self.panes.remove(pane)
            pane.window = None
            return None
        return [c for c in (window.open(), closing) if c is not None]

    def detach_active(self) -> Any:
        """**Move tab to new window**: the document in front gets a window of its own."""
        return self.detach(self.active, self.active.active)

    def to_main(self) -> Any:
        """**Move tab to main window**: the document in front goes back among the main window's tabs."""
        if self.active is self.main:
            return None
        return [c for c in (self.move(self.active, self.active.active, self.main),
                            _core.Command.focus_window(self.d)) if c is not None]

    def closed(self, pane: Pane) -> None:
        """The window of ``pane`` is closing: its tabs join the main window's (nothing is lost)."""
        if pane not in self.panes or pane is self.main:
            return
        front = pane.doc if pane.docs else None
        if self.active is pane and not self.d._flush_code():
            self.d.editing = None  # its text did not parse: keep the document, drop the edit
        self.panes.remove(pane)
        self.main.docs.extend(pane.docs)
        pane.docs, pane.window = [], None
        if self.active is pane:
            self.active = self.main
            if front is not None:
                self.main.active = self.main.docs.index(front)
            self.d.code_revision += 1
            self.d._selection_changed()
        if self.here is pane:
            self.here = self.main

    # -- dragging tabs ----------------------------------------------------------
    def start_drag(self, pane: Pane, tab_id: str) -> None:
        """A tab started moving (only documents move; Reference and What's new stay put)."""
        if tab_id.isdigit():
            self.drag = TabDrag(pane, int(tab_id))
            self.here = pane

    def drag_over(self, index: Optional[int]) -> None:
        """The dragged tab is over its own row at the insertion point ``index`` (``None``: off the row)."""
        if self.drag is not None:
            self.drag.over = index

    def window_at(self, screen: Tuple[float, float], exclude: Pane) -> Optional[Pane]:
        """The pane whose window is under the screen point ``screen``, if the platform says where windows are."""
        x, y = screen
        for pane in self.panes:
            if pane is exclude:
                continue
            host: Any = pane.window if pane.window is not None else self.d
            position, size = host.window_position, host.window_size
            if position is None or size is None:
                continue
            if position[0] <= x < position[0] + size[0] and position[1] <= y < position[1] + size[1]:
                return pane
        return None

    def drop(self, pane: Pane, tab_id: str, event: Any) -> Any:
        """The dragged tab was released: reorders it, stacks it on another window or opens a new one."""
        drag, self.drag = self.drag, None
        if drag is None or drag.pane is not pane or not tab_id.isdigit():
            return None
        index = int(tab_id)
        if drag.over is not None:
            return self.reorder(pane, index, drag.over)
        width, height = self.window_size(pane)
        x, y = getattr(event, "window_x", 0.0), getattr(event, "window_y", 0.0)
        if 0 <= x < width and 0 <= y < height:
            return None  # released inside its own window, off the tab row: nothing moves
        screen = getattr(event, "screen", None)
        target = self.window_at(screen, pane) if screen is not None else None
        if target is not None:
            host = target.window if target.window is not None else self.d
            return [c for c in (self.move(pane, index, target), _core.Command.focus_window(host)) if c is not None]
        return self.detach(pane, index, screen)

    # -- view -------------------------------------------------------------------
    def tab_bar(self, pane: Pane, tabs: List[Any], active: Optional[str], end: List[Any], t: Any) -> Any:
        """The row of tabs of ``pane``: its documents can be dragged within it and out of the window."""
        drag = self.drag if self.drag is not None and self.drag.pane is pane else None
        return ui.tab_bar(
            tabs, active,
            on_select=lambda tab_id: self.select(pane, tab_id),
            on_close=lambda tab_id: self.close(pane, tab_id),
            on_drag=lambda tab_id: self.start_drag(pane, tab_id),
            on_drop=lambda tab_id, event: self.drop(pane, tab_id, event),
            on_drag_over=self.drag_over,
            dragging=str(drag.index) if drag is not None else None,
            drop_index=drag.over if drag is not None else None,
            end=end, height=30, theme=t,
        )

    def asleep(self, pane: Pane, content: Any) -> Any:
        """``content`` of a pane that is not the active one: the first press only makes it active."""
        if pane is self.active:
            return content
        wake = _core.mouse_area(_core.space(width="fill", height="fill"), on_press=lambda: self.activate(pane),
                                on_right_press=lambda: self.activate(pane))
        return _core.stack([content, wake], width="fill", height="fill")

    def window_view(self, pane: Pane) -> Any:
        """The whole view of a document window: tabs, toolbar and canvas, with menus and dialogs used there."""
        d = self.d
        t = d.theme_obj
        if not pane.docs:
            return _core.container(width="fill", height="fill", bg=t.background)
        if pane is self.active:
            d.sync_code()
        body = _core.container(d.center_view(pane, t), width="fill", height="fill", bg=t.background)
        return d.window_overlays(body, pane, t)
