"""The project picker of the title bar, like Zed's: pressing the project's name lists the projects open in
this window and the recent ones, with a search field, and "Open local folder…" / "New project…" below.
The branch menu next to it switches the git branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from .. import _core, ui
from .. import project as _project
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

INPUT_ID = "project-picker"
WIDTH = 360
RECENT = 20


@dataclass
class Entry:
    """A row of the picker: a project open in this window or a recent one."""

    root: Path
    section: str  # "window" or "recent"
    active: bool = False

    @property
    def label(self) -> str:
        env = _project.environment(self.root)
        here = _project.environment()
        return f"{self.root.name} ({env.name})" if env.is_wsl and env != here else self.root.name


class ProjectPicker:
    """The search text and highlighted row of the picker (``Designer.app_menu == "projects"``)."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.query = ""
        self.index = 0

    def open(self) -> Any:
        """Opens the picker (or closes it when open); returns the command that focuses its search field."""
        if self.d.app_menu == "projects":
            self.d.app_menu = None
            return None
        self.query, self.index = "", 0
        self.d.app_menu = "projects"
        self.d.layout.menu = None
        return _core.Command.focus(INPUT_ID)

    def set_query(self, text: str) -> None:
        self.query = text
        self.index = 0

    def move(self, step: int) -> None:
        """Moves the highlight ``step`` rows (the arrow keys)."""
        self.index = max(0, min(self.index + step, len(self.entries()) - 1))

    def entries(self) -> List[Entry]:
        """The projects of this window, then the recent ones not open here, filtered by the search."""
        p = self.d.projects
        active = p.project.root if p.project is not None else None
        rows = [Entry(root, "window", root == active) for root in p.window]
        rows += [Entry(root, "recent") for root in _project.recent_projects(RECENT) if root not in p.window]
        q = self.query.strip()
        if not q:
            return rows
        matched = ui.fuzzy_filter(q, rows, key=lambda e: e.label)
        return [entry for entry, _ in matched]

    def choose(self, entry: Entry) -> Any:
        """Makes ``entry`` the active project of this window."""
        return self.d.projects.switch(entry.root)

    def submit(self) -> Any:
        """Opens the highlighted row (Enter)."""
        rows = self.entries()
        return self.choose(rows[min(self.index, len(rows) - 1)]) if rows else None

    def action(self, run: Callable[[], Any]) -> Callable[[], Any]:
        def press() -> Any:
            self.d.app_menu = None
            return run()

        return press


# -- views -------------------------------------------------------------------------------------


def _header(text: str, t: Theme) -> Any:
    return _core.container(ui.label(tr(text), size="xs", weight="medium", color="text_muted", theme=t),
                           padding=(6, 8, 2, 8), width="fill")


def _row(pk: ProjectPicker, entry: Entry, highlighted: bool, t: Theme) -> Any:
    env = _project.environment(entry.root)
    end: Any = None
    if entry.active:
        end = _icon("check", size=14, color=t.text_accent)
    elif entry.section == "window":
        end = ui.icon_button("x", lambda: pk.d.projects.close_project(entry.root), size="sm",
                             tooltip=tr("Close in this window"), theme=t)
    content = _core.row([
        _icon("server" if env.is_wsl else "folder", size=14, color=t.icon_muted),
        _core.text(entry.label, size=13.5, color=t.text, wrap=False),
        _core.space(width="fill"),
        end,
    ], spacing=8, align="center")
    row = _core.button(_core.container(content, height="fill", align_y="center"), lambda: pk.choose(entry),
                       padding=(0, 8), width="fill", height=28,
                       bg=t.ghost_selected if highlighted else "transparent",
                       hover_bg=t.ghost_selected if highlighted else t.ghost_hover, radius=t.radius_sm)
    return ui.tooltip(row, str(entry.root), theme=t)


def _footer_item(text: str, on_press: Any, icon: str, t: Theme) -> Any:
    return ui.list_item(tr(text), on_press, icon=icon, height=28, theme=t)


def view(d: "Designer", t: Theme) -> Any:
    """The picker's card, shown under the project's name in the title bar."""
    pk = d.picker_projects
    p = d.projects
    rows = pk.entries()
    index = min(pk.index, max(len(rows) - 1, 0))
    body: List[Any] = []
    for section, title in (("window", "This window"), ("recent", "Recent projects")):
        shown = [(i, e) for i, e in enumerate(rows) if e.section == section]
        if not shown:
            continue
        if body:
            body.append(_core.container(_core.rule(thickness=1, color=t.border_variant), padding=(4, 0)))
        body.append(_header(title, t))
        body += [_row(pk, e, i == index, t) for i, e in shown]
    if not body:
        body.append(_core.container(ui.label(tr("No projects match") if pk.query else tr("No recent projects"),
                                             size="sm", color="text_muted", theme=t), padding=(8, 10)))
    search = _core.container(ui.input(pk.query, pk.set_query, placeholder=tr("Search projects…"), id=INPUT_ID,
                                      on_submit=pk.submit, borderless=True, theme=t), padding=(4, 6), width="fill")
    footer = _core.column([
        _footer_item("Open local folder…", pk.action(p.show("open")), "folder-open", t),
        _footer_item("New project…", pk.action(p.show("new")), "folder-plus", t),
    ], width="fill")
    return _core.container(_core.column([
        search,
        _core.rule(thickness=1, color=t.border_variant),
        _core.container(_core.scrollable(_core.column(body, width="fill", spacing=1), height="shrink",
                                         scrollbar_width=6), max_height=360, padding=4, width="fill"),
        _core.rule(thickness=1, color=t.border_variant),
        _core.container(footer, padding=4, width="fill"),
    ]), width=WIDTH, bg=t.elevated, border_color=t.border, border_width=1.0, radius=t.radius + 2,
        shadow=(alpha("#000000", 0.35 if t.is_dark else 0.15), (0, 8), 32), clip=True)


def branch_menu(d: "Designer", t: Theme) -> Any:
    """The branch menu: the local branches, the current one checked."""
    p = d.projects
    items: List[Any] = [tr("Branches")]
    items += [ui.MenuItem(name, lambda name=name: p.switch_branch(name), icon=None if name == p.branch else "git-branch",
                          checked=True if name == p.branch else None) for name in p.branches]
    if len(items) == 1:
        items.append(ui.MenuItem(tr("No branches yet"), None, disabled=True))
    return ui.menu(items, width=240, theme=t)


def title_items(d: "Designer", t: Theme) -> List[Any]:
    """The title bar's start, after the menu: the environment (WSL), the project's name (the picker), and the
    git branch and worktree, like Zed's."""
    p = d.projects
    env = p.environment
    project = p.project
    items: List[Any] = []
    if env.is_wsl:
        items.append(ui.tooltip(ui.title_button(env.name, d.picker_projects.open, icon="server", muted=True, theme=t),
                                env.describe(), theme=t))
    if project is None:
        items.append(ui.title_button(tr("No project"), d.picker_projects.open, muted=True, chevron=True, theme=t))
        return items
    items.append(ui.title_button(project.name, d.picker_projects.open, chevron=len(p.window) > 1, theme=t))
    if project.is_git:
        items.append(ui.title_button(p.branch or tr("detached"), p.open_branches, icon="git-branch", muted=True,
                                     theme=t))
    if p.worktree:
        items.append(ui.tooltip(ui.title_button(p.worktree, None, icon="git-fork", muted=True, theme=t),
                                tr("Git worktree"), theme=t))
    return items


def _width(text: str, *, icon: bool = False, chevron: bool = False) -> float:
    """About how wide a ``ui.title_button`` is (to open a menu under it)."""
    return 16 + len(text) * 7.4 + (20 if icon else 0) + (18 if chevron else 0) + 2


def anchor(d: "Designer", which: str) -> float:
    """How far right of the first title bar item the picker (``"projects"``) or branch menu opens."""
    p = d.projects
    x = 28 + 2 + 24 + 2  # the menu button and Pyzed's mark
    env = p.environment
    if env.is_wsl:
        x += _width(env.name, icon=True)
    if which == "projects" or p.project is None:
        return x
    return x + _width(p.project.name, chevron=len(p.window) > 1)
