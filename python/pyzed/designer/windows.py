"""Document tabs in every tab area of the designer, and in more than one window.

Every tab area holds a *pane*: the main window's center, each dock (left, right, bottom, top) and
each window of its own. A pane keeps its document tabs (forms, components, shaders); the panels
placed in the same area (Code, Console, Properties...) show as tabs in the same row, so a form, the
code editor and the console can share one place. A tab dragged out of its window (or **Move tab
to new window**) opens in a window of its own; dragging a tab onto another place stacks it there,
and dragging it along a tab row reorders it (see ``dock_windows``).

The panels follow the pane with a document that was used last, like the tool windows of an IDE.
A pane that is not the active one shows its document but its canvas only wakes up on the first
click, so a click never edits a form you were not looking at. Closing a window moves its
documents back to the main window and its panels back to their docks.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Optional, Tuple

from .. import _core, ui
from ..app import Window
from ..ui import frame as ui_frame
from .document import Document
from .locale import tr
from .preferences import DOCKS

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Size of a new document window when the main window's size is not known yet.
WINDOW_SIZE = (1100.0, 760.0)
#: Size of a new window that only holds panels.
PANEL_WINDOW_SIZE = (440.0, 600.0)
#: The place of the main window's center; the other windows are "window:1", "window:2"...
MAIN = "main"
WINDOW = "window:"

#: Where the pointer ends up inside a new window: over its first tab.
GRAB_OFFSET = (90.0, 14.0)
#: What a pane that is not the active one should not show: the gestures of the active pane.
TRANSIENT = {"drag": None, "guides": [], "drop_name": None, "menu": None}


def is_blank(doc: Document) -> bool:
    """Whether ``doc`` stands for "nothing open": the main window shows an empty area and no tab until a
    document opens (or it gets a control, which makes it a new untitled form)."""
    return getattr(doc, "blank", False) and not doc.dirty and not doc.form.controls


class Pane:
    """The documents shown as tabs in one tab area (the main window's center, a dock or a window of its
    own), which one is in front, and whether a panel of the same area is in front of them."""

    __slots__ = ("docs", "active", "window", "place", "front")

    def __init__(self, docs: Optional[List[Document]] = None, active: int = 0,
                 window: Optional["DocWindow"] = None, place: str = MAIN) -> None:
        self.docs: List[Document] = docs if docs is not None else []
        self.active = active
        self.window = window
        #: "main", a dock ("left"...) or a window of its own ("window:1"...)
        self.place = place
        #: the panel in front of the documents (its tab was picked last), or ``None`` for the document
        self.front: Optional[str] = None

    @property
    def doc(self) -> Document:
        """The document in front."""
        return self.docs[self.active]

    @property
    def docked(self) -> bool:
        """Whether the pane is one of the main window's docks."""
        return self.place in DOCKS

    def __repr__(self) -> str:
        return f"<Pane {self.place} {[d.display_name for d in self.docs]} active={self.active}>"


class DocWindow(Window):
    """A window of its own: its document and panel tabs, and the toolbar and canvas or the panel in front."""

    min_size = (280.0, 220.0)

    def __init__(self, designer: "Designer", pane: Pane, *, size: Optional[Tuple[float, float]] = None,
                 position: Optional[Tuple[float, float]] = None) -> None:
        self.designer = designer
        self.app = designer
        self.pane = pane
        pane.window = self
        self.size = size or WINDOW_SIZE
        self.frame = designer.frame  # the same frame as the main window, with the document as its title
        if position is not None:
            self.position = position
        self.title = self.window_title

    @property
    def scale(self) -> float:  # type: ignore[override]
        """Windows of their own follow the designer's interface scale."""
        return self.designer.scale

    @scale.setter
    def scale(self, _value: float) -> None:
        pass

    def window_title(self) -> str:
        """The document in front, after a ``●`` when it has unsaved changes, or the panel in front."""
        from .docks import front

        shown = front(self.designer, self.pane.place)
        if shown is None:
            return "Pyzed Design"
        if shown[0] == "panel":
            return f"{shown[1].title} — Pyzed Design"
        doc = self.pane.doc
        return f"{'● ' if doc.dirty else ''}{doc.display_name} — Pyzed Design"

    def view(self) -> Any:
        return self.designer.panes.window_view(self.pane)

    def on_close(self) -> None:
        """Closing the window keeps its tabs: documents go back to the main window, panels to their docks."""
        self.designer.panes.closed(self.pane)


class PaneController:
    """The panes of the designer (one per window) and the tab drags between them."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.main = Pane()
        #: One pane per window: the main window's, then those of the windows of their own.
        self.panes: List[Pane] = [self.main]
        #: The pane of each dock of the main window.
        self.docked: Dict[str, Pane] = {dock: Pane(place=dock) for dock in DOCKS}
        #: The pane the panels, the menus and the keyboard work on (always one with documents).
        self.active = self.main
        #: The pane used last: menus, dialogs and toasts open in its window.
        self.here = self.main

    # -- lookups ----------------------------------------------------------------
    def every(self) -> List[Pane]:
        """Every pane: the windows' and the docks'."""
        return [*self.panes, *self.docked.values()]

    def all_docs(self) -> List[Document]:
        """Every open document, in every window and dock."""
        return [doc for pane in self.every() for doc in pane.docs]

    def at(self, place: str) -> Optional[Pane]:
        """The pane of ``place`` ("main", a dock or "window:N"), if there is one."""
        if place in self.docked:
            return self.docked[place]
        return next((pane for pane in self.panes if pane.place == place), None)

    def windows(self) -> List[Pane]:
        """The panes of the windows of their own."""
        return [pane for pane in self.panes if pane is not self.main]

    def host(self, pane: Pane) -> Any:
        """The window that shows ``pane``: its own, or the designer's main window."""
        return pane.window if pane.window is not None else self.d

    def is_here(self, pane: Pane) -> bool:
        """Whether ``pane`` is in the window used last (where menus and dialogs open)."""
        return self.host(pane) is self.host(self.here)

    def new_place(self) -> str:
        """A free "window:N" place for a new window."""
        layout = self.d.layout
        used = {p.place for p in self.panes} | set(layout.docks.values()) | set(layout.windows)
        n = 1
        while f"{WINDOW}{n}" in used:
            n += 1
        return f"{WINDOW}{n}"

    def find(self, doc: Document) -> Optional[Tuple[Pane, int]]:
        """The pane and tab index of ``doc``."""
        for pane in self.every():
            for i, other in enumerate(pane.docs):
                if other is doc:
                    return pane, i
        return None

    def find_path(self, path: Any) -> Optional[Tuple[Pane, int]]:
        """The pane and tab index of the document saved at ``path``."""
        target = path.resolve()
        for pane in self.every():
            for i, other in enumerate(pane.docs):
                if other.path is not None and other.path.resolve() == target:
                    return pane, i
        return None

    def window_size(self, pane: Optional[Pane] = None) -> Tuple[float, float]:
        """The size of the window that shows ``pane`` (the one used last by default)."""
        host = self.host(pane or self.here)
        return host.window_size or host.size

    # -- switching --------------------------------------------------------------
    def activate(self, pane: Pane) -> bool:
        """Makes ``pane`` the one the panels follow; ``False`` when the code editor cannot be left yet (or
        ``pane`` has no document)."""
        self.here = pane
        if not pane.docs:
            return False
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
        """A document tab of ``pane`` was pressed: it comes in front of the panels there."""
        if not self.activate(pane):
            return None
        pane.front = None
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
        """``pane`` lost its last document: the main window gets an empty form, a dock just shows its
        panels, and a window closes unless it still holds panels."""
        if pane.docs:
            return None
        if pane is self.main:  # nothing open: an empty area (a hidden form takes the place of the tabs)
            blank = Document()
            blank.blank = True
            pane.docs.append(blank)
            pane.active = 0
            return None
        if self.active is pane:
            self.active = self.main
            self.d.code_revision += 1
        if self.here is pane:
            self.here = self.main
        if pane.docked or self.d.layout.all_in(pane.place):
            return None
        self.panes.remove(pane)
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
        target.front = None
        if target.docked:
            self.d.layout.closed[target.place] = False
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

    def new_window(self, size: Optional[Tuple[float, float]] = None,
                   screen: Optional[Tuple[float, float]] = None,
                   position: Optional[Tuple[float, float]] = None, place: Optional[str] = None) -> Pane:
        """A new pane in a window of its own (not open yet), under the pointer at ``screen`` when given."""
        pane = Pane(place=place or self.new_place())
        if screen is not None:
            dx, dy = self.grab_offset()
            position = (screen[0] - dx, screen[1] - dy)
        DocWindow(self.d, pane, size=size, position=position)
        self.panes.append(pane)
        return pane

    def detach(self, source: Pane, index: int, screen: Optional[Tuple[float, float]] = None) -> Any:
        """Opens the tab ``index`` of ``source`` in a new window (under the pointer at ``screen``)."""
        if not 0 <= index < len(source.docs):
            return None
        alone = len(source.docs) == 1 and not self.d.layout.all_in(source.place)
        if source.window is not None and alone:  # already alone in its window: just move the window
            if screen is None:
                return None
            dx, dy = self.grab_offset()
            return _core.Command.move_window(screen[0] - dx, screen[1] - dy, source.window)
        width, height = self.window_size(self.main)
        pane = self.new_window((min(width, WINDOW_SIZE[0]), min(height, WINDOW_SIZE[1])), screen)
        closing = self.move(source, index, pane)
        if not pane.docs:  # the code editor could not be left
            self.panes.remove(pane)
            pane.window = None
            return None
        return [c for c in (pane.window.open(), closing) if c is not None]

    def grab_offset(self) -> Tuple[float, float]:
        """Where the pointer ends up inside a new window: over its first tab, under the title bar when the
        designer draws its own frame."""
        style = ui_frame.resolve(self.d.frame)
        return GRAB_OFFSET[0], GRAB_OFFSET[1] + (ui_frame.HEIGHTS[style] if style else 0.0)

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
        """The window of ``pane`` is closing: its documents join the main window's tabs and its panels go back
        to their docks (nothing is lost)."""
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
                self.main.front = None
            self.d.code_revision += 1
            self.d._selection_changed()
        if self.here is pane:
            self.here = self.main
        if self.d.layout.all_in(pane.place):
            self.d.layout.send_home(pane.place)
            self.d._save_layout()

    # -- view -------------------------------------------------------------------
    def asleep(self, pane: Pane, content: Any) -> Any:
        """``content`` of a pane that is not the active one: the first press only makes it active."""
        if pane is self.active:
            return content
        wake = _core.mouse_area(_core.space(width="fill", height="fill"), on_press=lambda: self.activate(pane),
                                on_right_press=lambda: self.activate(pane))
        return _core.stack([content, wake], width="fill", height="fill")

    def window_view(self, pane: Pane) -> Any:
        """The whole view of a window of its own: its tabs and what is in front (a document's toolbar and
        canvas, or a panel), with the menus and dialogs used there."""
        d = self.d
        t = d.theme_obj
        if pane is self.active:
            d.sync_code()
        body = d.center_view(pane, t)
        if body is None:
            body = ui.empty_state(tr("Nothing to show yet"), "", icon="panels-top-left", theme=t)
        body = _core.container(body, width="fill", height="fill", bg=t.background)
        body = _core.stack([body, d.dock_windows.drag_layer(pane, t)], width="fill", height="fill")
        return d.window_overlays(body, pane, t)
