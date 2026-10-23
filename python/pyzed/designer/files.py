"""Text files opened from the Project tab in the code editor, like Zed's buffers.

Each ``Buffer`` is one file with the text being edited and the text last saved; ``Buffers``
keeps the open ones (as tabs in the Code panel), which one is shown, and saves and closes
them. The form's own code is not a buffer: it stays in ``Designer.editing``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from . import indentation as _indentation
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Bigger files open in the system's app instead (the editor keeps the whole text in memory).
MAX_SIZE = 4_000_000
#: Bytes read to tell text from binary files.
SNIFF = 8192
#: Editor languages of files whose name says it all (the others use their extension).
NAMES = {"Makefile": "makefile", "Dockerfile": "dockerfile", "CMakeLists.txt": "cmake", ".gitignore": "sh",
         ".env": "sh", "uv.lock": "toml"}
#: Editor languages of suffixes that are another format underneath (Pyzed's files are JSON).
SUFFIXES = {".pzform": "json", ".pzcomp": "json", ".pzshad": "json", ".pzanim": "json", ".pyi": "py"}


def read_text(path: Path) -> Optional[str]:
    """Returns the text of ``path``, or ``None`` when it is binary, not UTF-8 or too big to edit."""
    try:
        if path.stat().st_size > MAX_SIZE:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:SNIFF]:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n")


def language_of(path: Path) -> str:
    """The editor language of ``path`` (its highlighting and comment prefix)."""
    if path.name in NAMES:
        return NAMES[path.name]
    if path.suffix.lower() in SUFFIXES:
        return SUFFIXES[path.suffix.lower()]
    return path.suffix.lstrip(".").lower() or "txt"


@dataclass
class Buffer:
    """A file open in the code editor."""

    path: Path
    text: str
    #: The text as it is on the disk.
    saved: str
    #: Bumped when the text changes from outside the editor (a reload), so the editor gets a new buffer.
    revision: int = 0

    @property
    def dirty(self) -> bool:
        return self.text != self.saved

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def language(self) -> str:
        return language_of(self.path)


class Buffers:
    """The files open in the Code panel and the one it shows (``None`` shows the form's code)."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.items: List[Buffer] = []
        self.active: Optional[int] = None
        #: The buffer waiting for the "unsaved changes" answer before it closes.
        self.closing: Optional[int] = None
        #: What runs once the buffer being closed is closed (the designer's window closing, for one).
        self.then: Optional[Callable[[], Any]] = None

    @property
    def current(self) -> Optional[Buffer]:
        """The buffer the Code panel shows, if any."""
        if self.active is not None and 0 <= self.active < len(self.items):
            return self.items[self.active]
        return None

    @property
    def dirty(self) -> List[Buffer]:
        return [b for b in self.items if b.dirty]

    def index_of(self, path: Path) -> Optional[int]:
        target = path.resolve()
        return next((i for i, b in enumerate(self.items) if b.path.resolve() == target), None)

    def open(self, path: Path) -> bool:
        """Opens ``path`` (or brings it to the front); ``False`` when it is not a text file."""
        path = Path(path)
        index = self.index_of(path)
        if index is None:
            text = read_text(path)
            if text is None:
                return False
            self.items.append(Buffer(path, text, text))
            index = len(self.items) - 1
        self.select(index)
        return True

    def select(self, index: Optional[int]) -> None:
        """Shows buffer ``index`` (``None``: the form's code) in the Code panel and gives it the keyboard."""
        if index is not None and not 0 <= index < len(self.items):
            return
        self.active = index
        self.d.code_revision += 1
        self.d.layout.show("code")
        self.d.focus = "code"
        self.d.assist.opened()

    def set_text(self, text: str) -> None:
        if self.current is not None:
            self.current.text = text

    def save(self, index: Optional[int] = None) -> bool:
        """Writes buffer ``index`` (the shown one by default) to the disk."""
        index = self.active if index is None else index
        if index is None or not 0 <= index < len(self.items):
            return False
        buffer = self.items[index]
        settings = self.d.assist.settings
        if settings.convert_indentation and buffer.language == "py":
            converted = _indentation.convert(buffer.text, settings.hard_tabs, settings.tab_size)
            if converted != buffer.text:
                buffer.text = converted
                if index != self.active:
                    buffer.revision += 1  # its editor gets the new text when it is shown again
        try:
            buffer.path.parent.mkdir(parents=True, exist_ok=True)
            buffer.path.write_text(buffer.text, encoding="utf-8", newline="\n")
        except OSError as err:
            self.d.notify(tr("Could not save {name}", name=buffer.name), str(err), kind="error", seconds=5)
            return False
        buffer.saved = buffer.text
        self.d.notify(tr("Saved {name}", name=buffer.name), kind="success", seconds=2)
        self.d.projects.files.refresh()
        return True

    def save_all(self) -> bool:
        return all(self.save(i) for i, b in enumerate(self.items) if b.dirty)

    def close(self, index: Optional[int] = None, then: Optional[Callable[[], Any]] = None) -> Any:
        """Closes buffer ``index`` (the shown one by default), asking first when it has unsaved changes;
        ``then`` runs once it is closed (not if the user cancels)."""
        index = self.active if index is None else index
        if index is None or not 0 <= index < len(self.items):
            return
        if self.items[index].dirty:
            self.closing, self.then = index, then
            self.d.dialog = "file:unsaved"
            return None
        self._drop(index)
        return then() if then else None

    def _drop(self, index: int) -> None:
        self.items.pop(index)
        self.closing = None
        if self.active is not None:
            if self.active > index or self.active >= len(self.items):
                self.active -= 1
            if self.active is not None and self.active < 0:
                self.active = None
        if self.active is None and self.items and self.d.editing is None:
            self.active = len(self.items) - 1
        self.d.code_revision += 1
        self.d.assist.opened()

    def confirm_save(self) -> Any:
        """"Save" in the unsaved-changes dialog: saves the buffer, then closes it."""
        index, then, self.then, self.d.dialog = self.closing, self.then, None, None
        if index is not None and self.save(index):
            self._drop(index)
            return then() if then else None
        return None

    def confirm_discard(self) -> Any:
        """"Don't save" in the unsaved-changes dialog: closes the buffer and drops its changes."""
        index, then, self.then, self.d.dialog = self.closing, self.then, None, None
        if index is not None:
            self._drop(index)
            return then() if then else None
        return None

    def cancel_close(self) -> None:
        self.closing, self.then = None, None
        self.d.dialog = None

    # -- the files changed on the disk --------------------------------------------------------
    def moved(self, source: Path, dest: Path) -> None:
        """``source`` (a file or a folder) was renamed to ``dest``: open buffers follow it."""
        source = source.resolve()
        for b in self.items:
            path = b.path.resolve()
            if path == source or source in path.parents:
                b.path = dest / path.relative_to(source) if path != source else dest

    def deleted(self, path: Path) -> None:
        """``path`` (a file or a folder) was deleted: closes its buffers, keeping unsaved text open."""
        path = path.resolve()
        for i in reversed(range(len(self.items))):
            b = self.items[i]
            mine = b.path.resolve()
            if (mine == path or path in mine.parents) and not b.dirty:
                self._drop(i)
