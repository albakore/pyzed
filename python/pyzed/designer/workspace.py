"""The project's files in the designer, like Zed's project panel: a file tree with git
colors, a search over files and folders, file actions, and a folder browser for choosing
where projects live.

``Workspace`` keeps the tree's state and does the file work; ``FolderBrowser`` walks the
disk for the Open project and New project dialogs. The ``*_view`` functions draw them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from .. import _core, ui
from ..icons import for_file
from ..icons import icon as _icon
from ..theme import Theme
from . import file_ops as _ops
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Folders that are never listed: environments, caches and build output.
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build", ".ruff_cache",
             ".pytest_cache", ".mypy_cache", ".tox", ".nox", ".hypothesis", ".eggs"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
#: Stop listing after this many entries (a huge folder must not freeze the designer).
MAX_ENTRIES = 5000
MENU_WIDTH = 290
FIND_ID = "workspace-find"
NAME_ID = "workspace-name"
#: Files the designer opens in its own tabs; text files open in the code editor, the rest in the system's app.
DESIGN_SUFFIXES = (".pzform", ".pzcomp")


# -- reading the disk -------------------------------------------------------------------------


def list_entries(root: Path, limit: int = MAX_ENTRIES) -> List[str]:
    """Every file and folder under ``root`` as relative ``a/b.py`` paths (folders end with ``/``).

    Environments, caches and build output are left out; hidden files such as ``.gitignore`` stay.
    """
    found: List[str] = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted((d for d in dirs if d not in SKIP_DIRS and not d.endswith(".egg-info")), key=str.lower)
        rel = Path(folder).relative_to(root).as_posix()
        prefix = "" if rel == "." else rel + "/"
        found.extend(prefix + d + "/" for d in dirs)
        found.extend(prefix + f for f in sorted(files, key=str.lower) if f not in SKIP_FILES)
        if len(found) >= limit:
            break
    return found[:limit]


def git_status(root: Path) -> Dict[str, str]:
    """``{relative path: "modified" | "created" | "deleted" | "conflict"}`` from ``git status`` (empty
    when ``root`` is not a repository or git is missing)."""
    git = shutil.which("git")
    if git is None or not (root / ".git").exists():
        return {}
    try:
        out = subprocess.run([git, "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=root,
                             capture_output=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    status: Dict[str, str] = {}
    items = out.stdout.decode("utf-8", "replace").split("\0")
    i = 0
    while i < len(items):
        entry = items[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":
            i += 1  # the original name of a rename or copy follows
        if "U" in code or code in ("AA", "DD"):
            kind = "conflict"
        elif code == "??" or "A" in code:
            kind = "created"
        elif "D" in code:
            kind = "deleted"
        else:
            kind = "modified"
        status[path.rstrip("/")] = kind
    return status


def fuzzy_score(query: str, path: str) -> Optional[float]:
    """How well ``query`` matches ``path`` (higher is better), or ``None`` when its letters are not all
    there in order. Matches in the file name and at word starts count more, like Zed's file finder."""
    query = query.lower().replace(" ", "")
    if not query:
        return 0.0
    text = path.rstrip("/").lower()
    name_start = text.rfind("/") + 1
    score, last, pos = 0.0, -1, 0
    for ch in query:
        found = text.find(ch, pos)
        if found < 0:
            return None
        gain = 1.0
        if found == last + 1:
            gain += 2.0  # consecutive letters
        if found == 0 or text[found - 1] in "/_-. ":
            gain += 1.5  # start of a word
        if found >= name_start:
            gain += 1.0  # in the file name
        score += gain
        last, pos = found, found + 1
    return score - len(text) * 0.01  # shorter paths first when equal


def search(paths: Iterable[str], query: str, limit: int = 60) -> List[str]:
    """The ``paths`` matching ``query``, best first."""
    scored = [(s, p) for p in paths if (s := fuzzy_score(query, p)) is not None]
    scored.sort(key=lambda sp: (-sp[0], sp[1]))
    return [p for _, p in scored[:limit]]


def open_with_system(path: Path) -> None:
    """Opens ``path`` with its default app (or the folder in the file manager)."""
    if sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.Popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,  # noqa: S603
                     start_new_session=True)


def reveal(path: Path) -> None:
    """Shows ``path`` in the system's file manager (selected, where the platform allows it)."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)])  # noqa: S603, S607
    elif sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", str(path)])  # noqa: S603, S607
    else:
        open_with_system(path if path.is_dir() else path.parent)


# -- the file tree ---------------------------------------------------------------------------


class Workspace:
    """The file tree of the open project: what is listed, expanded and selected, and the file actions."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.root: Optional[Path] = None
        self.entries: List[str] = []
        self.status: Dict[str, str] = {}
        self.expanded: Set[str] = set()
        self.selected: Optional[str] = None
        self.query = ""
        #: The right-clicked entry and where its menu opens: ``(path, x, y)``.
        self.menu: Optional[Tuple[str, float, float]] = None
        #: What the name dialog does ("file", "folder" or "rename"), in which folder or on which entry.
        self.naming: Optional[Tuple[str, str]] = None
        self.name_text = ""
        #: The entry waiting for the delete confirmation.
        self.deleting: Optional[str] = None
        #: The Go to file dialog's text.
        self.find_text = ""
        #: Entries cut or copied for Paste: ``("cut" | "copy", [relative paths])``.
        self.clipboard: Optional[Tuple[str, List[str]]] = None
        #: File changes made here, for Undo and Redo (newest last).
        self.undo_stack: List[_ops.Op] = []
        self.redo_stack: List[_ops.Op] = []
        #: The web address of the project's git remote (for permalinks), if it has one.
        self.remote: Optional[str] = None

    # -- loading ---------------------------------------------------------------------------------
    def attach(self, root: Optional[Path]) -> None:
        """Shows the files of ``root`` (``None`` empties the tree); opens the UI and source folders."""
        if root != self.root:
            self.expanded = set()
            self.selected = None
            self.query = ""
            self.clipboard = None
            self.undo_stack, self.redo_stack = [], []
            self.remote = _ops.remote_url(root) if root is not None else None
        self.root = root
        self.refresh()
        if root is not None and not self.expanded:
            self.expanded = {e.rstrip("/") for e in self.entries if e in ("ui/", "src/")}

    def refresh(self) -> None:
        """Rereads the files and their git status from the disk."""
        if self.root is None or not self.root.is_dir():
            self.entries, self.status = [], {}
            return
        self.entries = list_entries(self.root)
        self.status = git_status(self.root)

    def path_of(self, rel: str) -> Path:
        assert self.root is not None
        return self.root / rel.rstrip("/")

    def nodes(self) -> List[ui.TreeNode]:
        return ui.TreeNode.from_paths(self.entries, self.status)

    # -- tree interaction ----------------------------------------------------------------------
    def toggle(self, rel: str) -> None:
        """Opens or closes the folder ``rel``."""
        self.d.focus = "files"
        self.selected = rel
        if rel in self.expanded:
            self.expanded.discard(rel)
        else:
            self.expanded.add(rel)

    def collapse_all(self) -> None:
        self.expanded = set()

    def set_query(self, text: str) -> None:
        self.query = text

    def reveal_entry(self, rel: str) -> None:
        """Selects ``rel`` and opens the folders above it."""
        parts = rel.rstrip("/").split("/")
        for i in range(1, len(parts)):
            self.expanded.add("/".join(parts[:i]))
        self.selected = rel.rstrip("/")

    def open(self, rel: str) -> Any:
        """Opens the file ``rel``: forms and components in a designer tab, a form's code with its form,
        any other text file in the code editor and the rest (images, binaries) in the system's app. A
        folder is revealed and opened in the tree."""
        path = self.path_of(rel)
        self.menu = None
        self.d.focus = "files"
        if path.is_dir():
            self.query = ""
            self.reveal_entry(rel)
            self.expanded.add(rel.rstrip("/"))
            return None
        self.selected = rel
        if path.suffix in DESIGN_SUFFIXES:
            return self.d._guard(lambda: self.d.open_path(path))
        if path.suffix == ".py":
            design = next((path.with_suffix(s) for s in DESIGN_SUFFIXES if path.with_suffix(s).exists()), None)
            if design is not None:  # the code of a form or component: open it with the code panel
                self.d._guard(lambda: self.d.open_path(design))
                return self.d.edit_whole_file()
        if self.d.buffers.open(path):
            return _core.Command.focus(self.d.editor_id)
        try:
            open_with_system(path)
        except OSError as err:
            self.d.notify(tr("Could not open {name}", name=path.name), str(err), kind="error", seconds=5)
        return None

    def edit(self, rel: str) -> Any:
        """Opens the file ``rel`` as text in the code editor, whatever it is (a form's ``.py`` too)."""
        path = self.path_of(rel)
        self.selected = rel
        if self.d.buffers.open(path):
            return _core.Command.focus(self.d.editor_id)
        self.d.notify(tr("{name} is not a text file", name=path.name), kind="error", seconds=4)
        return None

    def pick(self, rel: str) -> Any:
        """A click on a search result: opens files, reveals folders."""
        if rel.endswith("/"):
            self.query = ""
            self.reveal_entry(rel)
            self.expanded.add(rel.rstrip("/"))
            return None
        self.query = ""
        self.reveal_entry(rel)
        return self.open(rel)

    def results(self, query: Optional[str] = None, limit: int = 60) -> List[str]:
        return search(self.entries, self.query if query is None else query, limit)

    # -- context menu --------------------------------------------------------------------------
    def open_menu(self, rel: str) -> None:
        """Right-click on ``rel``: selects it and opens its menu at the pointer."""
        self.d.focus = "files"
        self.selected = rel.rstrip("/") or None
        self.menu = (rel, *self.d.window_pointer)

    def close_menu(self) -> None:
        self.menu = None

    def _act(self, action: Callable[[], Any]) -> Callable[[], Any]:
        def run() -> Any:
            self.menu = None
            return action()
        return run

    def menu_items(self, rel: str) -> List[Any]:
        """The right-click menu of ``rel`` (``""`` for the project folder), like Zed's project panel."""
        is_dir = rel == "" or rel.endswith("/")
        path = self.path_of(rel) if rel else self.root
        assert path is not None
        folder = self._folder_for(rel)
        relative = rel.rstrip("/") or "."
        act = self._act
        items: List[Any] = [
            ui.MenuItem(tr("New File"), act(lambda: self.start_naming("file", folder)), icon="file-plus",
                        keys="ctrl-n"),
            ui.MenuItem(tr("New Folder"), act(lambda: self.start_naming("folder", folder)), icon="folder-plus",
                        keys="alt-n"),
            ui.SEPARATOR,
            ui.MenuItem(tr("Reveal in File Manager"), act(lambda: reveal(path)), icon="folder-search",
                        keys="ctrl-alt-r"),
            None if is_dir else ui.MenuItem(tr("Open in Default App"), act(lambda: self.open_default(rel)),
                                            icon="external-link", keys="ctrl-shift-enter"),
            None if is_dir or path.suffix in DESIGN_SUFFIXES else ui.MenuItem(
                tr("Open in the code editor"), act(lambda: self.edit(rel)), icon="file-code"),
            ui.MenuItem(tr("Open in Terminal"), act(lambda: self.open_terminal(rel)), icon="terminal"),
            ui.SEPARATOR,
            None if not rel else ui.MenuItem(tr("Cut"), act(lambda: self.cut(rel)), icon="scissors", keys="ctrl-x"),
            None if not rel else ui.MenuItem(tr("Copy"), act(lambda: self.copy(rel)), icon="copy", keys="ctrl-c"),
            None if not rel else ui.MenuItem(tr("Duplicate"), act(lambda: self.duplicate(rel)), icon="copy-plus"),
            ui.MenuItem(tr("Paste"), act(lambda: self.paste(rel)), icon="clipboard", keys="ctrl-v",
                        disabled=self.clipboard is None),
            ui.MenuItem(tr("Undo"), act(self.undo), icon="undo-2", keys="ctrl-z", disabled=not self.undo_stack),
            ui.MenuItem(tr("Redo"), act(self.redo), icon="redo-2", keys="ctrl-shift-z", disabled=not self.redo_stack),
            ui.SEPARATOR,
            ui.MenuItem(tr("Copy Path"), act(lambda: _core.Command.copy(str(path))), icon="copy", keys="alt-shift-c"),
            ui.MenuItem(tr("Copy Relative Path"), act(lambda: _core.Command.copy(relative)), icon="copy",
                        keys="ctrl-alt-shift-c"),
        ]
        if rel:
            git = (self.root / ".git").exists() if self.root else False
            items += [
                ui.SEPARATOR,
                ui.MenuItem(tr("Add to .gitignore"), act(lambda: self.ignore(rel)), icon="eye-off"),
                ui.MenuItem(tr("Add to .git/info/exclude"), act(lambda: self.ignore(rel, exclude=True)),
                            icon="eye-off") if git else None,
                ui.MenuItem(tr("Open File Permalink"), act(lambda: self.permalink(rel, open_it=True)), icon="link")
                if self.remote else None,
                ui.MenuItem(tr("Copy File Permalink"), act(lambda: self.permalink(rel)), icon="link")
                if self.remote else None,
                ui.SEPARATOR,
                ui.MenuItem(tr("Rename"), act(lambda: self.start_naming("rename", rel)), icon="pencil", keys="f2"),
                ui.MenuItem(tr("Trash"), act(lambda: self.trash(rel)), icon="trash", keys="delete"),
                ui.MenuItem(tr("Delete"), act(lambda: self.ask_delete(rel)), icon="trash-2", keys="ctrl-delete",
                            danger=True),
            ]
        return [i for i in items if i is not None]

    def _folder_for(self, rel: Optional[str]) -> str:
        """The folder new and pasted entries go to for ``rel``: itself if it is a folder, else its folder."""
        if not rel or rel.endswith("/"):
            return rel or ""
        return rel.rsplit("/", 1)[0] + "/" if "/" in rel else ""

    def menu_at(self, t: Theme) -> Tuple[Any, float, float]:
        """The menu and where it goes, kept inside the window."""
        assert self.menu is not None
        rel, x, y = self.menu
        items = self.menu_items(rel)
        width, height = self.d.window_size or self.d.size
        separators = sum(1 for i in items if i == ui.SEPARATOR)
        tall = (len(items) - separators) * 28 + separators * 10 + 12
        if x + MENU_WIDTH > width - 4:
            x = max(x - MENU_WIDTH, 4)
        if y + tall > height - 4:
            y = max(height - tall - 4, 4)
        return ui.menu(items, width=MENU_WIDTH, theme=t), x, y

    # -- file actions ----------------------------------------------------------------------------
    def start_naming(self, kind: str, target: str) -> Any:
        """Opens the name dialog to create a file or folder in ``target`` or to rename ``target``."""
        self.naming = (kind, target)
        self.name_text = target.rstrip("/").rsplit("/", 1)[-1] if kind == "rename" else ""
        self.d.dialog = "project:name"
        return _core.Command.focus(NAME_ID)

    def set_name(self, text: str) -> None:
        self.name_text = text

    def finish_naming(self) -> Any:
        """Creates the file or folder, or renames the entry, with the name typed in the dialog."""
        if self.naming is None or self.root is None:
            return None
        kind, target = self.naming
        name = self.name_text.strip().strip("/")
        if not name or name in (".", "..") or "\\" in name:
            self.d.notify(tr("Type a name"), kind="error")
            return None
        try:
            if kind == "rename":
                source = self.path_of(target)
                dest = source.with_name(name)
                if dest.exists():
                    raise FileExistsError(f"{dest.name} already exists")
                source.rename(dest)
                self.d.buffers.moved(source, dest)
                self._record(_ops.Op("move", dest, source))
                rel = dest.relative_to(self.root).as_posix()
            else:
                dest = self.root / target / name
                if dest.exists():
                    raise FileExistsError(f"{name} already exists")
                if kind == "folder":
                    dest.mkdir(parents=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.touch()
                self._record(_ops.Op("create", dest, folder=kind == "folder"))
                rel = dest.relative_to(self.root).as_posix()
        except OSError as err:
            self.d.notify(tr("Could not do that"), str(err), kind="error", seconds=5)
            return None
        self.naming = None
        self.d.dialog = None
        self.refresh()
        self.reveal_entry(rel)
        if kind == "file":
            return self.open(rel)
        return None

    def ask_delete(self, rel: str) -> None:
        self.deleting = rel
        self.d.dialog = "project:delete"

    def delete(self) -> None:
        """Deletes the entry waiting for confirmation (a folder with everything in it)."""
        rel, self.deleting = self.deleting, None
        self.d.dialog = None
        if not rel or self.root is None:
            return
        path = self.path_of(rel)
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError as err:
            self.d.notify(tr("Could not delete {name}", name=path.name), str(err), kind="error", seconds=5)
        else:
            self.d.buffers.deleted(path)
        self.refresh()

    # -- clipboard, undo and the rest of the menu ---------------------------------------------------
    def _rel(self, path: Path) -> str:
        assert self.root is not None
        rel = path.relative_to(self.root).as_posix()
        return rel + "/" if path.is_dir() else rel

    def _record(self, op: _ops.Op) -> None:
        self.undo_stack.append(op)
        self.redo_stack.clear()

    def _failed(self, err: OSError) -> None:
        self.d.notify(tr("Could not do that"), str(err), kind="error", seconds=5)

    def focus(self) -> None:
        """Gives the keyboard to the tree (a click in it), for its shortcuts."""
        self.d.focus = "files"

    def cut(self, rel: str) -> None:
        """Marks ``rel`` to be moved by the next Paste."""
        self.clipboard = ("cut", [rel])

    def copy(self, rel: str) -> None:
        """Marks ``rel`` to be copied by Paste."""
        self.clipboard = ("copy", [rel])

    def paste(self, rel: Optional[str] = None) -> None:
        """Moves or copies the cut or copied entries into ``rel``'s folder (a copy next to a name already
        taken is called ``name copy``)."""
        if self.clipboard is None or self.root is None:
            return
        mode, sources = self.clipboard
        folder = self.root / self._folder_for(self.selected_rel() if rel is None else rel)
        pasted = None
        for source_rel in sources:
            source = self.path_of(source_rel)
            dest = folder / source.name
            try:
                if not source.exists():
                    raise FileNotFoundError(f"{source.name} is not there anymore")
                inside = folder.resolve() == source.resolve() or source.resolve() in folder.resolve().parents
                if source.is_dir() and inside:
                    raise OSError(f"{source.name} cannot go inside itself")
                if mode == "cut":
                    if dest.resolve() == source.resolve():
                        continue
                    _ops._check_free(dest)
                    shutil.move(str(source), str(dest))
                    self.d.buffers.moved(source, dest)
                    self._record(_ops.Op("move", dest, source))
                else:
                    dest = _ops.free_name(dest)
                    _ops.copy_entry(source, dest)
                    self._record(_ops.Op("copy", dest, source, folder=dest.is_dir()))
            except OSError as err:
                self._failed(err)
                continue
            pasted = dest
        if mode == "cut":
            self.clipboard = None
        self.refresh()
        if pasted is not None:
            self.reveal_entry(self._rel(pasted))

    def duplicate(self, rel: str) -> Any:
        """Copies ``rel`` next to itself and starts renaming the copy, like Zed."""
        source = self.path_of(rel)
        dest = _ops.free_name(source)
        try:
            _ops.copy_entry(source, dest)
        except OSError as err:
            self._failed(err)
            return None
        self._record(_ops.Op("copy", dest, source, folder=dest.is_dir()))
        self.refresh()
        copy_rel = self._rel(dest)
        self.reveal_entry(copy_rel)
        return self.start_naming("rename", copy_rel.rstrip("/"))

    def undo(self) -> None:
        """Reverts the last file change made here (create, rename, move, copy)."""
        self._step(self.undo_stack, self.redo_stack, _ops.undo)

    def redo(self) -> None:
        """Does the last undone file change again."""
        self._step(self.redo_stack, self.undo_stack, _ops.redo)

    def _step(self, source: List[_ops.Op], target: List[_ops.Op], apply: Callable[[_ops.Op], Any]) -> None:
        if not source:
            return
        op = source.pop()
        try:
            paths = apply(op)
        except OSError as err:
            self._failed(err)
            return
        target.append(op)
        if len(paths) == 2:
            self.d.buffers.moved(paths[0], paths[1])
        else:
            self.d.buffers.deleted(paths[0])
        self.refresh()
        if paths[-1].exists():
            self.reveal_entry(self._rel(paths[-1]))
        elif self.selected and not self.path_of(self.selected).exists():
            self.selected = None

    def trash(self, rel: str) -> None:
        """Moves ``rel`` to the system's trash (restore it from there)."""
        path = self.path_of(rel)
        try:
            _ops.send_to_trash(path)
        except (OSError, subprocess.SubprocessError) as err:
            self.d.notify(tr("Could not move {name} to the trash", name=path.name), str(err), kind="error",
                          seconds=5)
            return
        self.d.buffers.deleted(path)
        if self.selected and self.selected.startswith(rel.rstrip("/")):
            self.selected = None
        self.refresh()

    def open_default(self, rel: str) -> None:
        path = self.path_of(rel)
        try:
            open_with_system(path)
        except OSError as err:
            self.d.notify(tr("Could not open {name}", name=path.name), str(err), kind="error", seconds=5)

    def open_terminal(self, rel: str) -> None:
        """Opens the system's terminal in ``rel``'s folder."""
        assert self.root is not None
        try:
            _ops.open_terminal(self.root / self._folder_for(rel))
        except OSError as err:
            self.d.notify(tr("Could not open a terminal"), str(err), kind="error", seconds=5)

    def ignore(self, rel: str, exclude: bool = False) -> None:
        """Adds ``rel`` to the project's ``.gitignore`` (or ``.git/info/exclude``, which is not shared)."""
        assert self.root is not None
        file = self.root / (".git/info/exclude" if exclude else ".gitignore")
        name = ".git/info/exclude" if exclude else ".gitignore"
        try:
            added = _ops.add_ignore(file, rel)
        except OSError as err:
            self._failed(err)
            return
        self.d.notify(tr("Added to {file}", file=name) if added else tr("Already in {file}", file=name),
                      kind="success" if added else "info", seconds=2)
        self.refresh()

    def permalink(self, rel: str, open_it: bool = False) -> Any:
        """Copies (or opens) the link to ``rel`` at the current commit on the project's remote."""
        assert self.root is not None
        url = _ops.permalink(self.root, rel, self.remote)
        if url is None:
            self.d.notify(tr("No permalink: the project has no remote or commit"), kind="info", seconds=3)
            return None
        if open_it:
            if sys.platform == "win32":
                os.startfile(url)  # type: ignore[attr-defined]  # noqa: S606
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", url],  # noqa: S603
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return None
        self.d.notify(tr("Permalink copied"), kind="success", seconds=2)
        return _core.Command.copy(url)

    # -- keyboard ---------------------------------------------------------------------------------
    def selected_rel(self) -> str:
        """The selected entry as a relative path (folders end with ``/``), or ``""``."""
        if not self.selected or self.root is None:
            return ""
        return self.selected + "/" if self.path_of(self.selected).is_dir() else self.selected

    def visible(self) -> List[str]:
        """The rows the tree shows, top to bottom (the search results while there is a query)."""
        if self.query.strip():
            return self.results()
        rows: List[str] = []

        def walk(nodes: List[ui.TreeNode]) -> None:
            for node in nodes:
                node_id = node.id or node.name
                rows.append(node_id + "/" if node.is_folder else node_id)
                if node.is_folder and node_id in self.expanded:
                    walk(node.children or [])
        walk(self.nodes())
        return rows

    def move_selection(self, step: int) -> None:
        rows = self.visible()
        if not rows:
            return
        current = self.selected_rel()
        index = rows.index(current) + step if current in rows else (0 if step > 0 else len(rows) - 1)
        self.selected = rows[max(0, min(index, len(rows) - 1))].rstrip("/")

    def run_action(self, name: str) -> Tuple[bool, Any]:
        """Runs the project tree's keymap action ``name`` (``project_panel::`` in the keymap, like Zed's) on
        the selected entry; returns ``(handled, result)``."""
        if self.root is None:
            return False, None
        rel = self.selected_rel()
        folder = self._folder_for(rel)
        on_entry: Dict[str, Callable[[], Any]] = {
            "open": lambda: self.toggle(rel.rstrip("/")) if rel.endswith("/") else self.open(rel),
            "open_with_system": lambda: self.open_default(rel),
            "cut": lambda: self.cut(rel),
            "copy": lambda: self.copy(rel),
            "duplicate": lambda: self.duplicate(rel),
            "rename": lambda: self.start_naming("rename", rel.rstrip("/")),
            "trash": lambda: self.trash(rel),
            "delete": lambda: self.ask_delete(rel),
            "expand_selected_entry": lambda: self.expanded.add(rel.rstrip("/")) if rel.endswith("/") else None,
            "collapse_selected_entry": lambda: self._collapse(rel),
        }
        always: Dict[str, Callable[[], Any]] = {
            "new_file": lambda: self.start_naming("file", folder),
            "new_directory": lambda: self.start_naming("folder", folder),
            "reveal_in_file_manager": lambda: reveal(self.path_of(rel) if rel else self.root),
            "paste": lambda: self.paste(rel),
            "undo": self.undo,
            "redo": self.redo,
            "copy_path": lambda: _core.Command.copy(str(self.path_of(rel) if rel else self.root)),
            "copy_relative_path": lambda: _core.Command.copy(rel.rstrip("/") or "."),
            "select_previous": lambda: self.move_selection(-1),
            "select_next": lambda: self.move_selection(1),
            "cancel": lambda: setattr(self, "clipboard", None),
        }
        if name in always:
            return True, always[name]()
        if rel and name in on_entry:
            return True, on_entry[name]()
        return False, None

    def _collapse(self, rel: str) -> None:
        """Left: closes the open folder, or goes up to the folder of the entry."""
        key = rel.rstrip("/")
        if rel.endswith("/") and key in self.expanded:
            self.expanded.discard(key)
        elif "/" in key:
            self.selected = key.rsplit("/", 1)[0]

    # -- Go to file ---------------------------------------------------------------------------------
    def open_finder(self) -> Any:
        """Opens the Go to file dialog (ctrl-p)."""
        if self.root is None:
            self.d.notify(tr("Open a project first"), kind="info")
            return None
        self.refresh()
        self.find_text = ""
        self.d.dialog = "project:find"
        return _core.Command.focus(FIND_ID)

    def set_find(self, text: str) -> None:
        self.find_text = text

    def find_first(self) -> Any:
        results = [r for r in self.results(self.find_text, 1)]
        if not results:
            return None
        self.d.dialog = None
        return self.pick(results[0])

    def find_pick(self, rel: str) -> Any:
        self.d.dialog = None
        self.d.left_tab = "project"
        return self.pick(rel)


def _entry_icon(rel: str, is_open: bool, t: Theme) -> Tuple[str, Any]:
    if rel.endswith("/"):
        return ("folder-open" if is_open else "folder"), t.icon_muted
    name, color = for_file(rel.rsplit("/", 1)[-1])
    return name, color or t.icon_muted


def tree_view(w: Workspace, t: Theme) -> Any:
    """The file tree (or the search results while there is a query)."""
    colors = {"modified": t.modified, "created": t.created, "deleted": t.deleted, "conflict": t.conflict}
    rows: List[Any] = []
    if w.query.strip():
        for rel in w.results():
            name = rel.rstrip("/").rsplit("/", 1)[-1]
            parent = rel.rstrip("/").rsplit("/", 1)[0] if "/" in rel.rstrip("/") else ""
            icon, color = _entry_icon(rel, False, t)
            label = _core.row([_core.text(name, size=13, color=colors.get(w.status.get(rel.rstrip("/"), ""), t.text),
                                          wrap=False),
                               _core.text(parent, size=11.5, color=t.text_muted, wrap=False)], spacing=6,
                              align="center")
            rows.append(ui.list_item(label, lambda r=rel: w.pick(r), icon=icon, icon_color=color, height=24,
                                     on_right_press=lambda r=rel: w.open_menu(r), theme=t))
        if not rows:
            rows.append(_core.container(ui.label(tr("No files match"), size="sm", color="text_muted", theme=t),
                                        padding=(8, 12)))
        return _core.column(rows, width="fill")

    def walk(nodes: List[ui.TreeNode], depth: int) -> None:
        for node in nodes:
            node_id = node.id or node.name
            rel = node_id + "/" if node.is_folder else node_id
            is_open = node_id in w.expanded
            icon, color = _entry_icon(rel, is_open, t)
            chevron = _icon("chevron-down" if is_open else "chevron-right", size=12, color=t.icon_muted) \
                if node.is_folder else _core.space(width=12)
            press = (lambda i=node_id: w.toggle(i)) if node.is_folder else (lambda r=rel: w.open(r))
            rows.append(ui.list_item(
                _core.text(node.name, size=13, color=colors.get(node.status or "", t.text), wrap=False),
                press, start=chevron, icon=icon, icon_color=color, indent=depth * 14, height=24,
                selected=node_id == w.selected, on_right_press=lambda r=rel: w.open_menu(r), theme=t))
            if node.is_folder and is_open:
                walk(node.children or [], depth + 1)

    walk(w.nodes(), 0)
    if not rows:
        rows.append(_core.container(ui.label(tr("The project folder is empty"), size="sm", color="text_muted",
                                             theme=t), padding=(8, 12)))
    return _core.column(rows, width="fill")


def toolbar_view(w: Workspace, t: Theme) -> Any:
    """The search field and the tree's buttons."""
    return _core.container(_core.row([
        ui.search_input(w.query, w.set_query, placeholder=tr("Search files…"), size="sm", theme=t),
        ui.icon_button("file-plus", lambda: w.start_naming("file", _folder_of(w)), size="sm",
                       tooltip=tr("New file…"), theme=t),
        ui.icon_button("folder-plus", lambda: w.start_naming("folder", _folder_of(w)), size="sm",
                       tooltip=tr("New folder…"), theme=t),
        ui.icon_button("list-collapse", w.collapse_all, size="sm", tooltip=tr("Collapse all"), theme=t),
        ui.icon_button("refresh-cw", w.refresh, size="sm", tooltip=tr("Refresh"), theme=t),
    ], spacing=2, align="center"), padding=(4, 8), width="fill")


def _folder_of(w: Workspace) -> str:
    """The folder new files go to: the selected folder, the selected file's folder or the root."""
    sel = w.selected
    if not sel or w.root is None:
        return ""
    if (w.root / sel).is_dir():
        return sel + "/"
    return sel.rsplit("/", 1)[0] + "/" if "/" in sel else ""


def name_dialog(w: Workspace, t: Theme) -> Any:
    assert w.naming is not None
    kind, target = w.naming
    title = {"file": tr("New file"), "folder": tr("New folder"), "rename": tr("Rename")}[kind]
    where = target.rstrip("/").rsplit("/", 1)[0] if kind == "rename" and "/" in target else \
        target.rstrip("/") if kind != "rename" else ""
    return ui.modal(
        ui.field(tr("Name"), ui.input(w.name_text, w.set_name, on_submit=w.finish_naming, id=NAME_ID, mono=True,
                                      theme=t),
                 description=tr("In {folder}", folder=f"{w.root.name}/{where}" if w.root else where), theme=t),
        title=title, on_close=w.d.close_dialog, width=460, theme=t, footer=[
            ui.button(tr("Cancel"), w.d.close_dialog, variant="ghost", theme=t),
            ui.button(tr("Rename") if kind == "rename" else tr("Create"), w.finish_naming, variant="solid",
                      theme=t)])


def delete_dialog(w: Workspace, t: Theme) -> Any:
    rel = w.deleting or ""
    is_dir = w.root is not None and (w.root / rel.rstrip("/")).is_dir()
    text = tr("Delete the folder {name} and everything in it? This cannot be undone.", name=rel.rstrip("/")) \
        if is_dir else tr("Delete {name}? This cannot be undone.", name=rel)
    return ui.modal(ui.label(text, theme=t), title=tr("Delete"), on_close=w.d.close_dialog, width=460, theme=t,
                    footer=[ui.button(tr("Cancel"), w.d.close_dialog, variant="ghost", theme=t),
                            ui.button(tr("Delete"), w.delete, icon="trash-2", variant="error", theme=t)])


def find_dialog(w: Workspace, t: Theme) -> Any:
    rows = []
    for rel in w.results(w.find_text, 40):
        name = rel.rstrip("/").rsplit("/", 1)[-1]
        icon, color = _entry_icon(rel, False, t)
        label = _core.row([_core.text(name, size=13.5, color=t.text, wrap=False),
                           _core.text(rel.rstrip("/"), size=12, color=t.text_muted, wrap=False)], spacing=8,
                          align="center")
        rows.append(ui.list_item(label, lambda r=rel: w.find_pick(r), icon=icon, icon_color=color, inset=True,
                                 theme=t))
    return ui.modal(_core.column([
        ui.search_input(w.find_text, w.set_find, placeholder=tr("Search files and folders"), on_submit=w.find_first,
                        id=FIND_ID, theme=t),
        _core.container(_core.scrollable(_core.column(rows, width="fill")), height=340, width="fill") if rows else
        ui.label(tr("No files match"), size="sm", color="text_muted", theme=t),
    ], spacing=8), title=tr("Go to file"), on_close=w.d.close_dialog, width=620, theme=t)


# -- the folder browser ---------------------------------------------------------------------------


def places() -> List[Tuple[str, Path, str]]:
    """``(label, folder, icon)`` of the usual places: home, desktop, documents, downloads, the disks."""
    home = Path.home()
    found: List[Tuple[str, Path, str]] = [(tr("Home"), home, "house")]
    for label, names, icon in ((tr("Desktop"), ("Desktop", "Escritorio"), "monitor"),
                               (tr("Documents"), ("Documents", "Documentos"), "file-text"),
                               (tr("Downloads"), ("Downloads", "Descargas"), "download"),
                               (tr("Projects"), ("Projects", "Proyectos", "projects", "dev", "code"), "folder-git-2")):
        folder = next((home / n for n in names if os.path.isdir(home / n)), None)
        if folder is not None:
            found.append((label, folder, icon))
    if sys.platform == "win32":
        import string

        found += [(f"{c}:", Path(f"{c}:\\"), "hard-drive") for c in string.ascii_uppercase
                  if os.path.exists(f"{c}:\\")]
    else:
        found.append((tr("Computer"), Path("/"), "hard-drive"))
    return found


# ``os.path`` answers ``False`` for folders it may not look into (``/lost+found``, another user's home),
# where ``Path.is_file`` raises ``PermissionError`` before Python 3.14.
def is_project(folder: Path) -> bool:
    return os.path.isfile(folder / "pyproject.toml")


def start_folder() -> Path:
    """Where new projects and the folder browser start: the current folder, or the home folder when the
    designer was started from the disk's root or another folder the user cannot write to (a desktop
    launcher often starts it in ``/``)."""
    cwd = Path.cwd()
    return cwd if cwd.parent != cwd and os.access(cwd, os.W_OK) else Path.home()


def readable(folder: Path) -> bool:
    """Whether the folder's contents can be listed (``False`` for folders without permission)."""
    return os.access(folder, os.R_OK | os.X_OK)


class FolderBrowser:
    """Walks the folders of the disk to pick one (Open project, the location of New project)."""

    def __init__(self, start: Optional[Path] = None) -> None:
        self.path = Path.home()
        self.show_hidden = False
        self.text = ""
        self.go(start or Path.home())

    def go(self, folder: Any) -> None:
        """Shows ``folder`` (a missing one falls back to its nearest existing parent)."""
        path = Path(str(folder).strip() or "~").expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        while not (os.path.isdir(path) and readable(path)) and path.parent != path:
            path = path.parent
        self.path = path.resolve() if os.path.isdir(path) else Path.home()
        self.text = str(self.path)

    def up(self) -> None:
        self.go(self.path.parent)

    def set_text(self, text: str) -> None:
        self.text = text

    def submit_text(self) -> None:
        self.go(self.text)

    def toggle_hidden(self) -> None:
        self.show_hidden = not self.show_hidden

    def folders(self, limit: int = 500) -> List[Path]:
        """The folders inside the current one, by name (hidden ones only when shown)."""
        try:
            items = [p for p in self.path.iterdir()
                     if os.path.isdir(p) and (self.show_hidden or not p.name.startswith("."))]
        except OSError:
            return []
        return sorted(items, key=lambda p: p.name.lower())[:limit]

    def crumbs(self) -> List[Path]:
        return [*reversed(self.path.parents), self.path]


def browser_view(b: FolderBrowser, t: Theme, *, open_project: Optional[Callable[[Path], Any]] = None,
                 recent: Iterable[Path] = ()) -> Any:
    """The browser's body: a bar with the path, the places on the side and the folders."""
    crumbs = b.crumbs()[-5:]
    bar = _core.row([
        ui.icon_button("arrow-up", b.up, size="sm", tooltip=tr("Parent folder"), disabled=b.path.parent == b.path,
                       theme=t),
        ui.icon_button("house", lambda: b.go(Path.home()), size="sm", tooltip=tr("Home"), theme=t),
        _core.container(ui.breadcrumbs([c.name or str(c) for c in crumbs], on_press=lambda i: b.go(crumbs[i]),
                                       theme=t), width="fill", clip=True),
        ui.icon_button("eye" if b.show_hidden else "eye-off", b.toggle_hidden, size="sm",
                       tooltip=tr("Show hidden folders"), selected=b.show_hidden, theme=t),
    ], spacing=4, align="center")
    path = ui.input(b.text, b.set_text, on_submit=b.submit_text, icon="folder", mono=True, size="sm", theme=t)
    side: List[Any] = [ui.list_item(label, lambda p=p: b.go(p), icon=icon, height=24, inset=True,
                                    selected=b.path == p, theme=t) for label, p, icon in places()]
    recent = [r for r in recent if os.path.isdir(r)][:6]
    if recent:
        side.append(_core.container(ui.label(tr("Recent").upper(), size="xs", weight="semibold", color="text_muted",
                                             theme=t), padding=(10, 8, 2, 8)))
        side += [ui.tooltip(ui.list_item(r.name, (lambda r=r: open_project(r)) if open_project else
                                         (lambda r=r: b.go(r.parent)), icon="folder-git-2", height=24, inset=True,
                                         theme=t), str(r), theme=t) for r in recent]
    rows: List[Any] = []
    for folder in b.folders():
        if not readable(folder):  # shown, but there is nothing to see inside
            rows.append(ui.tooltip(ui.list_item(folder.name, None, icon="folder-lock", icon_color="text_muted",
                                                height=26, inset=True, disabled=True, theme=t),
                                   tr("No permission to open it"), theme=t))
            continue
        project = is_project(folder)
        end = None
        if project:
            end = _core.row([ui.badge(tr("project"), tint="accent", theme=t),
                             ui.button(tr("Open"), lambda f=folder: open_project(f), size="sm", theme=t)
                             if open_project else None], spacing=6, align="center")
        rows.append(ui.list_item(folder.name, lambda f=folder: b.go(f), icon="folder-git-2" if project else "folder",
                                 icon_color="accent" if project else None, end=end, height=26, inset=True, theme=t))
    if not rows:
        rows.append(_core.container(ui.label(tr("No folders here"), size="sm", color="text_muted", theme=t),
                                    padding=(8, 10)))
    body = _core.row([
        _core.container(_core.scrollable(_core.column(side, width="fill")), width=170, height=320),
        _core.container(_core.rule(thickness=1, color=t.border_variant, vertical=True), height=320),
        _core.container(_core.scrollable(_core.column(rows, width="fill")), width="fill", height=320),
    ], spacing=6)
    return _core.column([bar, path, body], spacing=8, width="fill")
