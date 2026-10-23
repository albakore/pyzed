"""Find and replace in the whole project, like Zed's project search (Ctrl+Shift+F, Ctrl+Shift+H).

The Search panel (in the left dock while a search is open) takes a text or a regular expression,
the same options as the editor's find bar (match case, whole words, regex) and the files to look
in (``*.py, ui/``; empty: every text file). Its results are grouped by file with the matching lines;
clicking one opens the file in the Code panel with the match selected.

Files open in the editor, and the code of open forms, are searched as they are (with their unsaved
changes) and replaced there, so the change can still be undone or not saved. The other files are
written straight away; **Undo replace** puts back what the last replace wrote. Open forms and
components themselves (``.pzform``, ``.pzcomp``) are skipped by replace: they are edited in the
designer.
"""

from __future__ import annotations

import fnmatch
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha
from . import files as _files
from . import logs as _logs
from .code_panel import _pattern
from .file_scan import SKIP_DIRS
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

QUERY_ID = "project-search-query"
REPLACE_ID = "project-search-replace"
#: Most files read and matches listed in one search (the panel says when there were more).
MAX_FILES = 5000
MAX_MATCHES = 2000
#: Characters of a matching line shown around the match.
CONTEXT = 60


@dataclass
class Match:
    """One match: its 1-based ``line``, where it is in that line (string indices) and the line's text."""

    line: int
    start: int
    end: int
    text: str

    @property
    def column(self) -> int:
        """The editor's 1-based byte column of the match's start."""
        return len(self.text[: self.start].encode("utf-8")) + 1

    @property
    def end_column(self) -> int:
        return len(self.text[: self.end].encode("utf-8")) + 1


@dataclass
class FileMatches:
    path: Path
    matches: List[Match] = field(default_factory=list)


def _wanted(include: str) -> Callable[[Path, Path], bool]:
    """A test of ``(path, root)`` from the comma-separated patterns ``include`` (``*.py``, ``ui/``, ``app.py``)."""
    patterns = [p.strip() for p in include.split(",") if p.strip()]
    if not patterns:
        return lambda _path, _root: True

    def wanted(path: Path, root: Path) -> bool:
        rel = path.relative_to(root).as_posix()
        for p in patterns:
            if p.endswith("/") and (rel + "/").startswith(p.lstrip("./")):
                return True
            if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(path.name, p):
                return True
        return False

    return wanted


def project_files(root: Path, include: str = "", limit: int = MAX_FILES) -> List[Path]:
    """The files under ``root`` a search looks in: not in environments, caches or hidden folders, and among
    ``include`` when it names some."""
    wanted = _wanted(include)
    out: List[Path] = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(names):
            path = Path(folder) / name
            if wanted(path, root):
                out.append(path)
                if len(out) >= limit:
                    return out
    return out


def find_in_text(text: str, pattern: Any) -> List[Match]:
    """The non-empty matches of the compiled ``pattern`` in ``text``, line by line."""
    out: List[Match] = []
    for number, line in enumerate(text.split("\n"), start=1):
        for m in pattern.finditer(line):
            if m.end() > m.start():
                out.append(Match(number, m.start(), m.end(), line))
    return out


def replace_text(text: str, pattern: Any, replacement: str, regex: bool) -> Tuple[str, int]:
    """``text`` with every match replaced, line by line like the search sees them, and how many there were.
    With ``regex``, ``\\1`` and ``\\g<name>`` in ``replacement`` take the groups."""
    count = 0

    def sub(m: Any) -> str:
        nonlocal count
        if m.end() == m.start():
            return m.group(0)
        count += 1
        if not regex:
            return replacement
        try:
            return m.expand(replacement)
        except (IndexError, Exception):  # noqa: BLE001 - a bad group reference: the text as typed
            return replacement

    lines = [pattern.sub(sub, line) for line in text.split("\n")]
    return "\n".join(lines), count


class ProjectSearch:
    """The state and actions of the Search panel."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.visible = False
        self.query = ""
        self.replacement = ""
        self.include = ""
        self.case = False
        self.word = False
        self.regex = False
        self.replacing = False
        self.results: List[FileMatches] = []
        self.error = ""
        self.searching = False
        #: More files or matches than listed.
        self.truncated = False
        self.folded: set = set()
        #: What the last replace wrote to the disk: ``(path, text before)``, for Undo replace.
        self.undo: List[Tuple[Path, str]] = []
        self._generation = 0

    # -- what to search ---------------------------------------------------------------------
    @property
    def root(self) -> Optional[Path]:
        """The folder searched: the open project's, or the open form's folder without a project."""
        project = self.d.projects.project
        if project is not None:
            return project.root
        path = getattr(self.d.doc, "path", None)
        return Path(path).resolve().parent if path else None

    def live_texts(self) -> Dict[Path, Tuple[str, Callable[[str], None]]]:
        """The text being edited of each file open in the designer (buffers and the code of open forms), with
        what changes it, by resolved path."""
        d = self.d
        out: Dict[Path, Tuple[str, Callable[[str], None]]] = {}
        for doc in d.panes.all_docs():
            code = getattr(doc, "code_path", None)
            if code is not None and not doc.blank:
                out[Path(code).resolve()] = (doc.code, lambda text, doc=doc: self._set_doc_code(doc, text))
        for buffer in d.buffers.items:
            out[buffer.path.resolve()] = (buffer.text, lambda text, b=buffer: self._set_buffer(b, text))
        return out

    def documents(self) -> set:
        """The files open as documents (forms, components, shaders): replace leaves them alone."""
        return {Path(doc.path).resolve() for doc in self.d.panes.all_docs() if doc.path is not None}

    def _set_buffer(self, buffer: Any, text: str) -> None:
        buffer.text = text
        buffer.revision += 1  # its editor gets the new text
        self.d.code_revision += 1

    def _set_doc_code(self, doc: Any, text: str) -> None:
        d = self.d
        if doc is d.doc and d.editing is not None:
            d._flush_code()  # what is typed and not applied yet first; sync_code merges the rest
        doc.set_code(text)
        d.code_revision += 1

    # -- the panel --------------------------------------------------------------------------
    def open(self, replace: bool = False) -> Any:
        """Shows the Search panel (with the replace field for ``replace``), starting from the word selected in
        the editor when there is one; returns the command that focuses the query field."""
        self.visible = True
        if replace:
            self.replacing = True
        self.d.show_panel("search")
        return _core.Command.focus(REPLACE_ID if replace and self.query else QUERY_ID)

    def close(self) -> None:
        """Hides the Search panel (the search is kept for the next time)."""
        self.visible = False

    def set_query(self, text: str) -> None:
        self.query = text
        self.search()

    def set_replacement(self, text: str) -> None:
        self.replacement = text

    def set_include(self, text: str) -> None:
        self.include = text
        self.search()

    def toggle(self, name: str) -> None:
        """Toggles ``"case"``, ``"word"``, ``"regex"`` or ``"replacing"``."""
        setattr(self, name, not getattr(self, name))
        if name != "replacing":
            self.search()

    def toggle_file(self, path: Path) -> None:
        """Folds or unfolds the matches of ``path``."""
        self.folded ^= {path}

    @property
    def count(self) -> int:
        return sum(len(f.matches) for f in self.results)

    # -- searching --------------------------------------------------------------------------
    def _compiled(self) -> Any:
        return _pattern(self.query, case=self.case, word=self.word, regex=self.regex)

    def search(self, *, wait: bool = False) -> None:
        """Searches again in the background (now with ``wait``); an older search still running is dropped."""
        self._generation += 1
        generation = self._generation
        self.error = ""
        if not self.query or self.root is None:
            self.results, self.searching, self.truncated = [], False, False
            return
        pattern = self._compiled()
        if pattern is None:
            self.results, self.searching = [], False
            self.error = tr("Invalid pattern")
            return
        root, include = self.root, self.include
        live = {path: text for path, (text, _) in self.live_texts().items()}
        self.searching = True

        def work() -> None:
            found, truncated = self._scan(root, include, pattern, live)

            def done() -> None:
                if generation == self._generation:
                    self.results, self.truncated, self.searching = found, truncated, False

            if wait:
                done()
                return
            try:
                _core.post(done)
            except RuntimeError:  # no running app
                done()

        if wait:
            work()
        else:
            threading.Thread(target=work, daemon=True, name="pyzed-project-search").start()

    @staticmethod
    def _scan(root: Path, include: str, pattern: Any, live: Dict[Path, str]) -> Tuple[List[FileMatches], bool]:
        out: List[FileMatches] = []
        total = 0
        paths = project_files(root, include)
        truncated = len(paths) >= MAX_FILES
        for path in paths:
            text = live.get(path.resolve())
            if text is None:
                text = _files.read_text(path)
            if not text:
                continue
            matches = find_in_text(text, pattern)
            if matches:
                out.append(FileMatches(path, matches[: MAX_MATCHES - total]))
                total += len(matches)
                if total >= MAX_MATCHES:
                    return out, True
        return out, truncated

    # -- opening a match --------------------------------------------------------------------
    def open_match(self, path: Path, match: Match) -> Any:
        """Opens ``path`` in the Code panel with ``match`` selected."""
        d = self.d
        code = next((doc for doc in d.panes.all_docs()
                     if doc is d.doc and doc.code_path is not None and Path(doc.code_path).resolve() == path.resolve()),
                    None)
        if code is not None:  # the open form's own code: the whole file in the editor
            if not d.edit_code("*"):
                return None
        elif not d.buffers.open(path):
            d.notify(tr("Could not open {name}", name=path.name), kind="error", seconds=3)
            return None
        d.assist.cursor = (match.line, match.column)
        editor = d.editor_id
        return _core.Command.batch([
            _core.Command.select_editor_ranges(editor, [(match.line, match.column, match.line, match.end_column)]),
            _core.Command.focus(editor)])

    # -- replacing --------------------------------------------------------------------------
    def replace_all(self, only: Optional[Path] = None) -> int:
        """Replaces every match listed (only those of ``only`` when given); returns how many were replaced."""
        pattern = self._compiled()
        if pattern is None or not self.results:
            return 0
        live = self.live_texts()
        documents = self.documents()
        written: List[Tuple[Path, str]] = []
        replaced = files = skipped = 0
        for entry in self.results:
            path = entry.path.resolve()
            if only is not None and path != only.resolve():
                continue
            if path in documents:
                skipped += 1
                continue
            if path in live:
                text, apply = live[path]
            else:
                text = _files.read_text(path)
                apply = None
            if text is None:
                continue
            new, count = replace_text(text, pattern, self.replacement, self.regex)
            if not count or new == text:
                continue
            if apply is not None:
                apply(new)
            else:
                try:
                    path.write_text(new, encoding="utf-8", newline="\n")
                except OSError as err:
                    self.d.notify(tr("Could not save {name}", name=path.name), str(err), kind="error", seconds=5)
                    continue
                written.append((path, text))
            replaced += count
            files += 1
        if written:
            self.undo = written
        _logs.event("search", "Replaced %d matches in %d files", replaced, files)
        if replaced:
            self.d.notify(tr("Replaced {count} matches in {files} files", count=replaced, files=files),
                          tr("Open forms were left as they are") if skipped else None, kind="success", seconds=4)
        elif skipped:
            self.d.notify(tr("Open forms were left as they are"), kind="info", seconds=4)
        self.d.projects.files.refresh()
        self.search(wait=True)
        return replaced

    def undo_replace(self) -> int:
        """Puts back the files the last replace wrote; returns how many."""
        restored = 0
        for path, text in self.undo:
            try:
                path.write_text(text, encoding="utf-8", newline="\n")
                restored += 1
            except OSError as err:
                self.d.notify(tr("Could not save {name}", name=path.name), str(err), kind="error", seconds=5)
        self.undo = []
        self.search(wait=True)
        return restored


def _snippet(match: Match) -> Tuple[str, str, str]:
    """The line around ``match`` as ``(before, match, after)``, trimmed to fit."""
    text = match.text
    start = max(match.start - CONTEXT // 2, 0)
    before = text[start: match.start].lstrip()
    if start > 0:
        before = "…" + before
    return before, text[match.start: match.end], text[match.end: match.end + CONTEXT]


def view(d: "Designer", t: Theme) -> Any:
    """The Search panel: the query, replace and files fields, then the results by file."""
    s = d.search

    def option(name: str, icon: str, tip: str) -> Any:
        return ui.icon_button(icon, lambda: s.toggle(name), size="sm", selected=getattr(s, name), tooltip=tr(tip),
                              theme=t)

    rows: List[Any] = [_core.row([
        ui.icon_button("chevron-down" if s.replacing else "chevron-right", lambda: s.toggle("replacing"), size="sm",
                       tooltip=tr("Toggle replace"), theme=t),
        ui.input(s.query, s.set_query, placeholder=tr("Search in the project"), id=QUERY_ID, size="sm", mono=True,
                 on_submit=lambda: s.search(), theme=t),
        ui.icon_button("x", s.close, size="sm", tooltip=tr("Close"), theme=t),
    ], spacing=4, align="center"),
        _core.row([_core.space(width=26), option("case", "case-sensitive", "Match case"),
                   option("word", "whole-word", "Match whole words"),
                   option("regex", "regex", "Use regular expressions")], spacing=4, align="center")]
    if s.replacing:
        rows.append(_core.row([
            _core.space(width=26),
            ui.input(s.replacement, s.set_replacement, placeholder=tr("Replace"), id=REPLACE_ID, size="sm", mono=True,
                     on_submit=lambda: s.replace_all(), theme=t),
            ui.icon_button("replace-all", lambda: s.replace_all(), size="sm", tooltip=tr("Replace all"),
                           disabled=not s.results, theme=t),
        ], spacing=4, align="center"))
    rows.append(_core.row([
        _core.space(width=26),
        ui.input(s.include, s.set_include, placeholder=tr("Files to include: *.py, ui/"), size="sm", theme=t),
    ], spacing=4, align="center"))
    if s.error:
        status = ui.label(s.error, size="xs", color="error", theme=t)
    elif s.searching:
        status = ui.label(tr("Searching…"), size="xs", color="text_muted", theme=t)
    elif not s.query:
        status = ui.label(tr("Type to search every file of the project"), size="xs", color="text_muted", theme=t)
    elif s.results:
        more = "+" if s.truncated else ""
        status = ui.label(tr("{count} results in {files} files", count=f"{s.count}{more}", files=len(s.results)),
                          size="xs", color="text_muted", theme=t)
    else:
        status = ui.label(tr("No results"), size="xs", color="text_muted", theme=t)
    tail = [ui.button(tr("Undo replace"), s.undo_replace, variant="ghost", size="xs", theme=t)] if s.undo else []
    rows.append(_core.row([_core.space(width=26), status, _core.space(width="fill"), *tail], spacing=4,
                          align="center"))
    header = _core.container(_core.column(rows, spacing=4), padding=(6, 8), width="fill")

    root = s.root
    items: List[Any] = []
    for entry in s.results:
        try:
            rel = entry.path.relative_to(root).as_posix() if root is not None else entry.path.name
        except ValueError:
            rel = str(entry.path)
        folded = entry.path in s.folded
        actions = [ui.icon_button("replace", lambda p=entry.path: s.replace_all(only=p), size="xs",
                                  tooltip=tr("Replace in this file"), theme=t)] if s.replacing else []
        items.append(_core.row([
            ui.icon_button("chevron-right" if folded else "chevron-down", lambda p=entry.path: s.toggle_file(p),
                           size="xs", theme=t),
            _icon("file-code", size=13, color=t.icon_muted),
            ui.label(entry.path.name, size="sm", weight="medium", wrap=False, theme=t),
            ui.label(str(Path(rel).parent) if "/" in rel else "", size="xs", color="text_muted", wrap=False,
                     theme=t),
            _core.space(width="fill"),
            ui.badge(str(len(entry.matches)), size="sm", theme=t),
            *actions,
        ], spacing=4, align="center", padding=(2, 8), width="fill"))
        if folded:
            continue
        for match in entry.matches:
            before, hit, after = _snippet(match)
            line = _core.row([
                _core.container(ui.label(str(match.line), size="xs", color="text_muted", mono=True, theme=t),
                                width=40, align_x="end"),
                _core.rich_text([_core.span(before), _core.span(hit, bg=alpha(t.accent, 0.3), radius=2),
                                 _core.span(after)], size=12, font="mono", color=t.text, wrap=False),
            ], spacing=8, align="center")
            items.append(ui.list_item(line, lambda p=entry.path, m=match: s.open_match(p, m), theme=t))
    body = _core.scrollable(_core.column(items, spacing=0, width="fill"), width="fill", height="fill")
    return _core.column([header, ui.divider(theme=t), body], width="fill", height="fill")
