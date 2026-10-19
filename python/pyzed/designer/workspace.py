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
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Folders that are never listed: environments, caches and build output.
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "__pycache__", "dist", "build", ".ruff_cache",
             ".pytest_cache", ".mypy_cache", ".tox", ".nox", ".hypothesis", ".eggs"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}
#: Stop listing after this many entries (a huge folder must not freeze the designer).
MAX_ENTRIES = 5000
MENU_WIDTH = 240
FIND_ID = "workspace-find"
NAME_ID = "workspace-name"
#: Files the designer opens itself; everything else opens in the system's app.
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
                             capture_output=True, timeout=5)
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

    # -- loading ---------------------------------------------------------------------------------
    def attach(self, root: Optional[Path]) -> None:
        """Shows the files of ``root`` (``None`` empties the tree); opens the UI and source folders."""
        if root != self.root:
            self.expanded = set()
            self.selected = None
            self.query = ""
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
        """Opens the file ``rel``: forms and components in a designer tab, a form's code in the code
        panel, any other file in the system's app. A folder is revealed and opened in the tree."""
        path = self.path_of(rel)
        self.menu = None
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
        try:
            open_with_system(path)
        except OSError as err:
            self.d.notify(tr("Could not open {name}", name=path.name), str(err), kind="error", seconds=5)
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
        is_dir = rel == "" or rel.endswith("/")
        path = self.path_of(rel) if rel else self.root
        assert path is not None
        folder = rel if is_dir else rel.rsplit("/", 1)[0] + "/" if "/" in rel else ""
        relative = rel.rstrip("/") or "."
        items = [
            None if is_dir else ui.MenuItem(tr("Open"), self._act(lambda: self.open(rel)), icon="file"),
            None if is_dir else ui.MenuItem(tr("Open with the system app"), self._act(lambda: open_with_system(path)),
                                            icon="external-link"),
            ui.MenuItem(tr("Reveal in file manager"), self._act(lambda: reveal(path)), icon="folder-search"),
            ui.SEPARATOR,
            ui.MenuItem(tr("New file…"), self._act(lambda: self.start_naming("file", folder)), icon="file-plus"),
            ui.MenuItem(tr("New folder…"), self._act(lambda: self.start_naming("folder", folder)),
                        icon="folder-plus"),
            ui.SEPARATOR,
            ui.MenuItem(tr("Copy path"), self._act(lambda: _core.Command.copy(str(path))), icon="copy"),
            ui.MenuItem(tr("Copy relative path"), self._act(lambda: _core.Command.copy(relative)), icon="copy"),
        ]
        if rel:
            items += [
                ui.SEPARATOR,
                ui.MenuItem(tr("Rename…"), self._act(lambda: self.start_naming("rename", rel)), icon="pencil"),
                ui.MenuItem(tr("Delete…"), self._act(lambda: self.ask_delete(rel)), icon="trash-2", danger=True),
            ]
        return [i for i in items if i is not None]

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
        self.refresh()

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
        folder = next((home / n for n in names if (home / n).is_dir()), None)
        if folder is not None:
            found.append((label, folder, icon))
    if sys.platform == "win32":
        import string

        found += [(f"{c}:", Path(f"{c}:\\"), "hard-drive") for c in string.ascii_uppercase if Path(f"{c}:\\").exists()]
    else:
        found.append((tr("Computer"), Path("/"), "hard-drive"))
    return found


def is_project(folder: Path) -> bool:
    return (folder / "pyproject.toml").is_file()


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
        while not path.is_dir() and path.parent != path:
            path = path.parent
        self.path = path.resolve() if path.is_dir() else Path.home()
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
            items = [p for p in self.path.iterdir() if p.is_dir() and (self.show_hidden or not p.name.startswith("."))]
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
    recent = [r for r in recent if r.is_dir()][:6]
    if recent:
        side.append(_core.container(ui.label(tr("Recent").upper(), size="xs", weight="semibold", color="text_muted",
                                             theme=t), padding=(10, 8, 2, 8)))
        side += [ui.tooltip(ui.list_item(r.name, (lambda r=r: open_project(r)) if open_project else
                                         (lambda r=r: b.go(r.parent)), icon="folder-git-2", height=24, inset=True,
                                         theme=t), str(r), theme=t) for r in recent]
    rows: List[Any] = []
    for folder in b.folders():
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
