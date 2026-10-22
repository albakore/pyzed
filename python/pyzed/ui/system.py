"""Controls that reach the operating system: a file path field and a zone to drop files on.

``file_input`` is a text box for a path with a button that opens the system's file dialog
(open, save, folder or several files), so nobody has to type a path by hand::

    ui.file_input(self.path, self.set_path, mode="open", filters={"Images": "png jpg"})

``DropZone`` takes files dragged from the file manager (Explorer, Finder, Nautilus...) and
dropped on the window. A click on it opens the file dialog too, so it also works where
dragging from the system is not available::

    ui.DropZone(text="Drop your photos here", accept=["png", "jpg"],
                on_drop=lambda e: self.photos.append(e.value))

Dropped files reach the window's ``on_file_drop`` hook; the one ``pz.Window`` has hands them
to the drop zone under the pointer, else to one whose ``accept`` lists their type, else to
one that takes any file. A window that defines its own hook gets them first (call
``super().on_file_drop(path)`` to pass them on).
"""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any, List, Optional, Sequence

from .. import _core
from ..component import Component
from ..i18n import add as _add, t as _t
from ..icons import icon as _icon
from ..theme import Theme, alpha as _alpha, current as _current_theme
from .base import _theme
from .dates import _signature

__all__ = ["DropZone", "accepts", "deliver", "file_input", "pick"]

MODES = ("open", "open_many", "save", "folder")

_add("en", {"pyzed": {"files": {
    "browse": "Browse…", "drop": "Drop files here", "drop_hint": "or click to choose them",
    "drop_one": "Drop a file here", "release": "Release to drop", "choose_file": "Choose a file",
    "choose_folder": "Choose a folder", "save_as": "Save as…", "not_accepted": "This kind of file is not accepted",
}}})
_add("es", {"pyzed": {"files": {
    "browse": "Examinar…", "drop": "Suelta archivos aquí", "drop_hint": "o haz clic para elegirlos",
    "drop_one": "Suelta un archivo aquí", "release": "Suelta para añadir", "choose_file": "Elige un archivo",
    "choose_folder": "Elige una carpeta", "save_as": "Guardar como…", "not_accepted": "Este tipo de archivo no se acepta",
}}})


def _filters(value: Any) -> List[Any]:
    from ..services import parse_filters

    return parse_filters(value)


def pick(then: Any, *, mode: str = "open", title: Optional[str] = None, filters: Any = None,
         directory: Optional[str] = None, file_name: str = "") -> _core.Command:
    """The command that opens the system's file dialog and calls ``then(path)`` with the choice.

    ``mode`` is ``"open"``, ``"save"``, ``"folder"`` (``then`` gets a path) or ``"open_many"``
    (a list of paths). Nothing is called when the dialog is cancelled.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}, not {mode!r}")

    def chose(paths: Sequence[str]) -> Any:
        if not paths:
            return None
        return then(list(paths) if mode == "open_many" else str(paths[0]))

    options = {"title": title or None, "filters": _filters(filters) or None,
               "directory": str(Path(directory).expanduser()) if directory else None}
    if mode == "save":
        return _core.Command.save_file(chose, file_name=file_name or "", **options)
    return _core.Command.pick_files(chose, multiple=mode == "open_many", folder=mode == "folder", **options)


def file_input(
    value: Any,
    on_change: Any = None,
    *,
    mode: str = "open",
    filters: Any = None,
    title: Optional[str] = None,
    directory: Optional[str] = None,
    file_name: str = "",
    placeholder: Optional[str] = None,
    button: Optional[str] = None,
    editable: bool = True,
    disabled: bool = False,
    invalid: bool = False,
    id: Optional[str] = None,  # noqa: A002
    width: Any = "fill",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A path field with a button that opens the system's file dialog.

    ``mode`` is ``"open"`` (a file), ``"save"`` (where to save, suggesting ``file_name``),
    ``"folder"`` or ``"open_many"`` (``value`` is then a list, shown separated by ``;``).
    ``filters`` limits the files shown (``{"Images": "png jpg"}`` or ``"Images: png, jpg"``),
    ``directory`` is where the dialog opens (by default the folder of the current value).
    ``button`` puts text on the button instead of a folder icon; ``editable=False`` keeps
    the path from being typed.

    Events:
        ``on_change(path)``: Callable that receives the new path (a list with ``"open_many"``).
    """
    t = _theme(theme)
    many = mode == "open_many"
    shown = "; ".join(map(str, value)) if many and isinstance(value, (list, tuple)) else str(value or "")
    if directory is None and shown and not many:
        here = Path(shown).expanduser()
        directory = str(here if mode == "folder" else here.parent) if str(here.parent) not in ("", ".") else None

    def typed(text: str) -> Any:
        if on_change is None:
            return None
        return on_change([p.strip() for p in text.split(";") if p.strip()] if many else text)

    def browse() -> Any:
        return pick(on_change, mode=mode, title=title, filters=filters, directory=directory, file_name=file_name)

    if placeholder is None:
        placeholder = {"folder": _t("pyzed.files.choose_folder"), "save": _t("pyzed.files.save_as")}.get(
            mode, _t("pyzed.files.choose_file"))
    off = disabled or on_change is None
    entry = _core.text_input(
        shown, placeholder=placeholder, on_input=typed if editable and not off else None, id=id, size=13.5,
        padding=(5, 8), width="fill", bg="transparent", border_width=0.0,
        color=t.text_disabled if disabled else t.text, placeholder_color=t.text_placeholder,
        selection_color=t.selection)
    icon = "folder-open" if mode in ("open", "open_many", "folder") else "save"
    inner = _core.text(button, size=12.5, color=t.text_disabled if off else t.text, wrap=False) if button else \
        _icon(icon, size=14, color=t.text_disabled if off else t.icon_muted)
    action = _core.button(inner, None if off else browse, padding=(4, 8) if button else (4, 6),
                          bg=t.element if button else "transparent", hover_bg=t.ghost_hover, radius=t.radius_sm - 1)
    return _core.container(_core.row([entry, action], align="center", spacing=2), width=width, padding=(0, 2, 0, 0),
                           bg=t.element if disabled else t.editor, border_color=t.error if invalid else t.border,
                           border_width=1, radius=t.radius_sm)


def accepts(path: str, accept: Sequence[str]) -> bool:
    """Whether ``path`` matches ``accept``: extensions (``"png"``, ``".png"``), patterns (``"*.tar.gz"``),
    ``"folder"`` or ``"file"``. An empty ``accept`` takes everything."""
    if not accept:
        return True
    name = Path(path).name.lower()
    for rule in accept:
        rule = str(rule).strip().lower()
        if not rule:
            continue
        if rule in ("folder", "folders", "dir", "directory"):
            if Path(path).is_dir():
                return True
        elif rule in ("file", "files"):
            if not Path(path).is_dir():
                return True
        elif any(ch in rule for ch in "*?["):
            if fnmatch.fnmatch(name, rule):
                return True
        elif name.endswith("." + rule.lstrip(".")):
            return True
    return False


#: The drop zones shown right now, oldest first (they add themselves when they appear).
_zones: List["DropZone"] = []


def _target(path: Optional[str]) -> Optional["DropZone"]:
    """The zone a file goes to: the one under the pointer, else the last shown that lists its type, else the
    last shown that takes any file (a zone that takes none of them still gets it, to say it rejects it)."""
    live = [z for z in _zones if not z.disabled]
    pointed = [z for z in live if z.pointer]
    if pointed:
        return pointed[-1]
    if path is not None:
        named = [z for z in live if z.accept and accepts(path, z.accept)]
        anything = [z for z in live if not z.accept]
        live = named or anything or live
    return live[-1] if live else None


def deliver(kind: str, path: Optional[str] = None) -> Any:
    """Hands a file dragged from the system to a drop zone (``kind``: ``"hover"``, ``"drop"`` or ``"leave"``).

    ``pz.Window`` calls it from ``on_file_hover``, ``on_file_drop`` and ``on_file_leave``.
    """
    if kind == "leave":
        results = [z.leave() for z in list(_zones)]
        return next((r for r in results if r is not None), None)
    zone = _target(path)
    if zone is None:
        return None
    for other in _zones:
        if other is not zone and other.hovering:
            other.leave()
    return zone.hover(path) if kind == "hover" else zone.drop(path)


class DropZone(Component):
    """An area that takes files dragged from the system's file manager and dropped on the window.

    ``accept`` lists the extensions (``["png", "jpg"]``), patterns (``"*.tar.gz"``) or
    ``"folder"`` it takes; other files raise ``reject``. ``multiple=False`` keeps only the
    last file. It lights up while files are dragged over the window, and a click opens the
    file dialog (``browse``). ``files`` keeps the dropped paths (``clear()`` forgets them);
    ``show_files`` lists them under the text.

    Events:
        ``on_drop(event)``: A file was dropped (``event.value`` is its path; once per file).
        ``on_files(event)``: The list of files changed (``event.value`` is the list).
        ``on_reject(event)``: A dropped file was not accepted (``event.value`` is its path).
        ``on_enter(event)``: Files are dragged over the window (``event.value``: the first path).
        ``on_leave(event)``: The drag left without dropping.
    """

    text: str = ""
    hint: str = ""
    icon_name: str = "upload"
    accept: list = ()
    multiple: bool = True
    browse: bool = True
    show_files: bool = False
    files: list = ()
    disabled: bool = False
    live: bool = True
    events = {"drop": "A file was dropped (``event.value`` is its path).",
              "files": "The list of dropped files changed (``event.value``).",
              "reject": "A dropped file was not accepted (``event.value``).",
              "enter": "Files are dragged over the window (``event.value``).",
              "leave": "The drag left without dropping."}
    icon = "upload"
    label = "Drop zone"
    category = "System"
    size = (260, 140)
    designer = False

    def setup(self) -> None:
        self.hovering = False
        self.pointer = False
        self.rejected = False
        self._batch = False  # files of one drop arrive one by one

    def on_mount(self) -> Any:
        if self.live and self not in _zones:
            _zones.append(self)
        return None

    def on_unmount(self) -> None:
        if self in _zones:
            _zones.remove(self)

    def hover(self, path: Optional[str]) -> Any:
        """Files are dragged over the window."""
        if self.hovering:
            return None
        self.hovering, self._batch = True, False
        self.rejected = bool(path) and not accepts(path, self.accept)
        return self.emit("enter", path)

    def leave(self) -> Any:
        """The drag left the window."""
        if not self.hovering:
            return None
        self.hovering = self.rejected = False
        return self.emit("leave")

    def drop(self, path: Optional[str]) -> Any:
        """A file was dropped: kept in ``files`` (when accepted) and raised as ``drop``."""
        self.hovering = self.rejected = False
        if not path:
            return None
        if not accepts(path, self.accept):
            return self.emit("reject", path)
        files = list(self.files or ())
        if not self.multiple:
            files = []
        elif not self._batch and not self.show_files:
            files = []  # a new drop replaces what was dropped before unless the list is shown
        self._batch = True
        if path not in files:
            files.append(path)
        self.files = files
        results = [self.emit("drop", path), self.emit("files", list(files))]
        return next((r for r in results if r is not None), None)

    def chosen(self, paths: Any) -> Any:
        """What the file dialog of a click returns, handled like dropped files."""
        self._batch = False
        results = [self.drop(p) for p in (paths if isinstance(paths, list) else [paths])]
        self._batch = False
        return next((r for r in results if r is not None), None)

    def clear(self) -> Any:
        """Forgets the dropped files."""
        self.files = []
        return self.emit("files", [])

    def remove(self, path: str) -> Any:
        self.files = [p for p in self.files or () if p != path]
        return self.emit("files", list(self.files))

    def set_pointer(self, inside: bool) -> None:
        self.pointer = inside

    def open_dialog(self) -> Any:
        if self.disabled:
            return None
        exts = [a.lstrip(".") for a in self.accept or () if a and not any(c in a for c in "*?[") and
                a.lower() not in ("folder", "folders", "file", "files", "dir", "directory")]
        folder = any(str(a).lower() in ("folder", "folders", "dir", "directory") for a in self.accept or ())
        mode = "folder" if folder and not exts else ("open_many" if self.multiple else "open")
        return pick(self.chosen, mode=mode, filters=[("", exts)] if exts else None)

    def render(self) -> Any:
        t = _current_theme()
        active = self.hovering and not self.rejected
        tint = t.error if self.rejected else t.accent
        title = self.text or (_t("pyzed.files.drop") if self.multiple else _t("pyzed.files.drop_one"))
        if self.hovering:
            title = _t("pyzed.files.not_accepted") if self.rejected else _t("pyzed.files.release")
        hint = self.hint or (_t("pyzed.files.drop_hint") if self.browse else "")
        parts: List[Any] = [
            _icon(self.icon_name or "upload", size=22, color=tint if self.hovering else
                  (t.text_disabled if self.disabled else t.icon_muted)),
            _core.text(title, size=13.5, weight="medium", wrap=True, align_x="center",
                       color=t.text_disabled if self.disabled else t.text),
        ]
        if hint and not self.hovering:
            parts.append(_core.text(hint, size=12, color=t.text_muted, wrap=True, align_x="center"))
        if self.show_files and self.files:
            parts.append(_core.column([
                _core.row([_icon("file", size=12, color=t.icon_muted),
                           _core.text(Path(str(p)).name, size=12, color=t.text, wrap=False, width="fill"),
                           _core.button(_icon("x", size=11, color=t.icon_muted), lambda p=p: self.remove(p),
                                        padding=2, bg="transparent", hover_bg=t.ghost_hover, radius=999)],
                          spacing=6, align="center", width="fill")
                for p in list(self.files)[:8]], spacing=2, width="fill", padding=(4, 12)))
        box = _core.container(
            _core.column(parts, spacing=4, align="center", width="fill"),
            width="fill", height="fill", center=True, padding=12,
            bg=_alpha(tint, 0.12) if self.hovering else (t.element if self.disabled else _alpha(t.element, 0.5)),
            border_color=tint if self.hovering else t.border, border_width=1.5 if active else 1.0,
            radius=t.radius + 2)
        box = box.on(mouse_enter=lambda: self.set_pointer(True), mouse_leave=lambda: self.set_pointer(False))
        if self.browse and not self.disabled:
            box = box.on(click=self.open_dialog, cursor="pointer")
        return box


_signature(DropZone, positional=0)
