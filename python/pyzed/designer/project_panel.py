"""The designer's Project tab: create and open uv projects, manage their dependencies,
run ruff and ty, and create the git repository.

``ProjectController`` holds the state and the actions (each slow command runs on a
worker thread and reports back on the UI thread); ``view`` and ``dialog`` draw it.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .. import _core, ui
from .. import project as _project
from ..project import Dependency, Project, Result, Tool
from ..theme import Theme, alpha

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

OUTPUT_LINES = 60


class ProjectController:
    """The project open in a ``Designer`` and what can be done with it."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.project: Optional[Project] = None
        self.deps: List[Dependency] = []
        self.latest: Dict[str, str] = {}
        self.tools: Dict[str, Tool] = {}
        self.branch: Optional[str] = None
        self.busy: Optional[str] = None
        self.last: Optional[Result] = None
        self.process: Optional[subprocess.Popen] = None
        # inputs
        self.add_text = ""
        self.add_dev = False
        self.change_target: Optional[Dependency] = None
        self.change_text = ""
        self.new_name = "my-app"
        self.new_folder = str(Path.cwd())
        self.new_git = True
        self.new_package = True
        self.open_text = ""

    # -- opening ------------------------------------------------------------------------
    def attach(self, project: Optional[Project]) -> Any:
        """Makes ``project`` the open one (activated, remembered, its folder the working one)."""
        self.project = project
        if project is None:
            return None
        project.activate()
        _project.remember(project)
        try:
            os.chdir(project.root)
        except OSError:
            pass
        self.refresh()
        return None

    def load_tools(self) -> Any:
        """Looks up uv, ruff, ty and git (their versions) in the background."""
        project = self.project
        if project is None:
            return None
        return self._task("Checking tools", lambda: _project.tools(project), self._got_tools, quiet=True)

    def refresh(self) -> None:
        if self.project is None:
            return
        self.project.reload()
        self.deps = self.project.dependencies()
        self.branch = self.project.git_branch()

    def _got_tools(self, found: Dict[str, Tool]) -> None:
        self.tools = found

    def open(self, path: str) -> Any:
        path = path.strip()
        if not path:
            return None
        try:
            project = Project.open(path)
        except (OSError, ValueError) as err:
            self.d.notify("Could not open the project", str(err), kind="error", seconds=5)
            return None
        self.d.dialog = None
        self.attach(project)
        self.d.left_tab = "project"
        self.d.notify(f"Opened {project.name}", str(project.root))
        if project.main_form.exists():
            self.d._guard(lambda: self.d.open_path(project.main_form))
        return self.load_tools()

    def create(self) -> Any:
        name = self.new_name.strip()
        if not name:
            return None
        target = Path(self.new_folder.strip() or ".").expanduser() / name
        if target.exists() and any(target.iterdir()) and not (target / "pyproject.toml").exists():
            self.d.notify("The folder is not empty", str(target), kind="error", seconds=5)
            return None
        self.d.dialog = None
        git, package = self.new_git, self.new_package

        def work() -> Any:
            try:
                return _project.init(target, git=git, package=package)
            except (RuntimeError, FileNotFoundError) as err:
                return Result(["uv", "init"], 1, str(err))

        def done(result: Any) -> Any:
            if isinstance(result, Result):
                self.last = result
                self.d.notify("Could not create the project", result.output, kind="error", seconds=6)
                return None
            return self.open(str(result.root))

        return self._task(f"Creating {name} with uv", work, done)

    # -- background commands -------------------------------------------------------------
    def _task(self, label: str, work: Callable[[], Any], done: Optional[Callable[[Any], Any]] = None,
              *, quiet: bool = False) -> Any:
        """Runs ``work`` off the UI thread; ``done(result)`` then runs on it."""
        if not quiet:
            self.busy = label

        async def run() -> Callable[[], Any]:
            result = await asyncio.get_running_loop().run_in_executor(None, work)

            def finish() -> Any:
                if not quiet:
                    self.busy = None
                if isinstance(result, Result):
                    self.last = result
                    if not result.ok:
                        self.d.notify(f"{label} failed", result.output.splitlines()[-1] if result.output else None,
                                      kind="error", seconds=5)
                self.refresh()
                return done(result) if done else None

            return finish

        return run()

    def _uv(self, label: str, work: Callable[[Project], Result]) -> Any:
        project = self.project
        if project is None or self.busy:
            return None
        return self._task(label, lambda: work(project),
                          lambda r: self.d.notify(label, kind="success", seconds=2) if r.ok else None)

    def add(self) -> Any:
        specs = self.add_text.split()
        if not specs:
            return None
        dev = self.add_dev
        self.add_text = ""
        return self._uv(f"Adding {' '.join(specs)}", lambda p: p.add(*specs, dev=dev))

    def remove(self, dep: Dependency) -> Any:
        return self._uv(f"Removing {dep.name}", lambda p: p.remove(dep.name, dev=dep.group == "dev",
                                                                    group=None if dep.group in ("main", "dev")
                                                                    else dep.group))

    def upgrade(self, dep: Optional[Dependency] = None) -> Any:
        if dep is None:
            return self._uv("Upgrading every package", lambda p: p.upgrade())
        return self._uv(f"Upgrading {dep.name}", lambda p: p.upgrade(dep.name))

    def start_change(self, dep: Dependency) -> None:
        self.change_target = dep
        self.change_text = dep.spec
        self.d.dialog = "project:change"

    def change(self) -> Any:
        dep, spec = self.change_target, self.change_text.strip()
        self.d.dialog = None
        if dep is None or not spec:
            return None
        dev = dep.group == "dev"
        group = None if dep.group in ("main", "dev") else dep.group
        return self._uv(f"Changing {dep.name}", lambda p: p.change(spec, dev=dev, group=group))

    def sync(self) -> Any:
        return self._uv("Syncing the environment", lambda p: p.sync())

    def check_updates(self) -> Any:
        project = self.project
        if project is None or self.busy:
            return None

        def found(outdated: List[Dependency]) -> None:
            self.latest = {d.name: d.latest or "" for d in outdated}
            self.d.notify(f"{len(outdated)} updates available" if outdated else "Everything is up to date",
                          kind="info", seconds=3)

        return self._task("Checking for updates", project.outdated, found)

    def lint(self) -> Any:
        return self._uv("ruff check", lambda p: p.check())

    def format(self) -> Any:
        return self._uv("ruff format", lambda p: p.format())

    def typecheck(self) -> Any:
        return self._uv("ty check", lambda p: p.typecheck())

    def git_init(self) -> Any:
        return self._uv("Creating the git repository", lambda p: p.git_init())

    # -- running forms -------------------------------------------------------------------
    @property
    def runs_outside(self) -> bool:
        """Forms of this project run through ``uv run`` (the designer lacks its dependencies)."""
        return self.project is not None and not self.project.can_run_in_process

    def run_form(self, form: Path) -> None:
        """Starts ``form`` with ``uv run pyzed run --reload`` in the project."""
        assert self.project is not None
        self.stop()
        try:
            self.process = self.project.spawn(form, reload=True)
        except (OSError, FileNotFoundError) as err:
            self.d.notify("Could not start the form", str(err), kind="error", seconds=5)
            return
        self.d.notify(f"Running {form.name}", "With uv run; saving updates the window", seconds=3)

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
        self.process = None

    # -- input setters ---------------------------------------------------------------------
    def setter(self, attr: str) -> Callable[[Any], None]:
        def set_value(value: Any) -> None:
            setattr(self, attr, value)

        return set_value

    def show(self, dialog: str) -> Callable[[], None]:
        def open_dialog() -> None:
            self.d.dialog = f"project:{dialog}"

        return open_dialog


# -- views -----------------------------------------------------------------------------------


def _section(title: str, t: Theme, end: Any = None) -> Any:
    return _core.container(
        _core.row([ui.label(title.upper(), size="xs", weight="semibold", color="text_muted", theme=t),
                   _core.space(width="fill"), end], align="center"),
        padding=(12, 12, 4, 12), width="fill")


def _empty(p: ProjectController, t: Theme) -> Any:
    recent = [ui.list_item(path.name, lambda path=path: p.open(str(path)), icon="folder-git-2", inset=True,
                           end=ui.label(str(path.parent), size="xs", color="text_muted", wrap=False, theme=t),
                           theme=t) for path in _project.recent_projects(8)]
    parts: List[Any] = [
        ui.empty_state("No project open", "Projects use uv for dependencies, ruff and ty for checks and git.",
                       icon="package", theme=t, actions=[
                           ui.button("New project", p.show("new"), icon="folder-plus", variant="solid", size="sm",
                                     theme=t),
                           ui.button("Open…", p.show("open"), icon="folder-open", size="sm", theme=t)]),
    ]
    if recent:
        parts += [_section("Recent", t), *recent]
    return _core.scrollable(_core.container(_core.column(parts, width="fill"), padding=(16, 4), width="fill"),
                            height="fill")


def _dep_row(p: ProjectController, dep: Dependency, t: Theme) -> Any:
    newer = p.latest.get(dep.name)
    version = ui.label(f"↑{newer}" if newer else dep.locked or "—", size="xs", mono=True,
                       color="success" if newer else "text_muted", theme=t)
    if newer:
        version = ui.tooltip(version, f"{dep.locked} → {newer}: press Upgrade", theme=t)
    end = _core.row([
        version,
        ui.icon_button("pencil", lambda: p.start_change(dep), size="sm", tooltip="Change version", theme=t),
        ui.icon_button("arrow-up-circle", lambda: p.upgrade(dep), size="sm", tooltip="Upgrade", theme=t),
        ui.icon_button("trash-2", lambda: p.remove(dep), size="sm", tooltip="Remove", theme=t),
    ], spacing=2, align="center")
    name = _core.row([ui.label(dep.name, size="sm", wrap=False, theme=t),
                      ui.badge(dep.group, tint="info", theme=t) if dep.dev else None], spacing=6, align="center")
    return ui.list_item(name, icon="package", inset=True, end=end, theme=t)


def _tool_row(tool: Tool, t: Theme) -> Any:
    state = ui.label(tool.version or "found", size="xs", mono=True, color="text_muted", theme=t) \
        if tool.available else ui.badge("missing", tint="error", theme=t)
    return ui.list_item(tool.name, icon="circle-check" if tool.available else "circle-alert",
                        icon_color="success" if tool.available else "error", inset=True, end=state, theme=t)


def _output(p: ProjectController, t: Theme) -> Any:
    if p.last is None:
        return None
    lines = (p.last.output or "(no output)").splitlines()[-OUTPUT_LINES:]
    color = "text" if p.last.ok else "error"
    return _core.column([
        _section("Output", t, ui.label(f"$ {p.last.command}", size="xs", mono=True, color="text_muted", wrap=False,
                                       theme=t)),
        _core.container(ui.label("\n".join(lines), size="xs", mono=True, color=color, theme=t),
                        padding=(6, 12), width="fill", bg=alpha(t.text, 0.04)),
    ], width="fill")


def view(d: "Designer", t: Theme) -> Any:
    """The Project tab of the left dock."""
    p = d.projects
    project = p.project
    if project is None:
        return _empty(p, t)
    forms = [ui.list_item(form.relative_to(project.root).as_posix(), lambda f=form: d._guard(lambda: d.open_path(f)),
                          icon="layout-template", inset=True,
                          selected=d.doc.path is not None and Path(d.doc.path).resolve() == form.resolve(), theme=t)
             for form in project.forms()]
    git = (ui.badge(p.branch or "git", icon="git-branch", tint="accent", theme=t) if project.is_git else
           ui.button("Create repository", p.git_init, icon="git-branch-plus", size="sm", variant="ghost", theme=t))
    header = _core.container(_core.column([
        _core.row([ui.label(project.name, weight="semibold", theme=t),
                   ui.label(project.version, size="xs", mono=True, color="text_muted", theme=t),
                   _core.space(width="fill"), git], spacing=8, align="center"),
        ui.label(str(project.root), size="xs", color="text_muted", wrap=False, theme=t),
    ], spacing=2), padding=(10, 12, 4, 12), width="fill")
    busy = None
    if p.busy:
        busy = _core.container(_core.row([ui.spinner(size=12, theme=t), ui.label(p.busy, size="sm", theme=t)],
                                         spacing=8, align="center"), padding=(4, 12), width="fill",
                               bg=alpha(t.accent, 0.08))
    add = _core.container(_core.row([
        ui.input(p.add_text, p.setter("add_text"), placeholder="Add package, e.g. httpx", size="sm",
                 on_submit=p.add, theme=t),
        ui.checkbox(p.add_dev, p.setter("add_dev"), label="dev", theme=t),
        ui.icon_button("plus", p.add, size="sm", tooltip="Add (uv add)", theme=t),
    ], spacing=6, align="center"), padding=(2, 12), width="fill")
    dep_actions = _core.row([
        ui.icon_button("refresh-cw", p.sync, size="sm", tooltip="Sync (uv sync)", theme=t),
        ui.icon_button("search-check", p.check_updates, size="sm", tooltip="Check for updates", theme=t),
        ui.icon_button("arrow-up-circle", lambda: p.upgrade(), size="sm", tooltip="Upgrade all", theme=t),
    ], spacing=2)
    checks = _core.container(_core.row([
        ui.tooltip(ui.button("Lint", p.lint, icon="list-checks", size="sm", theme=t), "ruff check", theme=t),
        ui.tooltip(ui.button("Format", p.format, icon="wand-sparkles", size="sm", theme=t), "ruff format", theme=t),
        ui.tooltip(ui.button("Types", p.typecheck, icon="shield-check", size="sm", theme=t), "ty check", theme=t),
    ], spacing=4), padding=(4, 8), width="fill")
    body = _core.column([
        header,
        busy,
        _section("Forms", t, ui.icon_button("folder-open", p.show("open"), size="sm", tooltip="Open another project",
                                            theme=t)),
        *(forms or [ui.label("No forms in the UI folder yet.", size="sm", color="text_muted", theme=t)]),
        _section("Dependencies", t, dep_actions),
        add,
        *[_dep_row(p, dep, t) for dep in p.deps],
        _section("Tools", t),
        *[_tool_row(tool, t) for tool in p.tools.values()],
        checks,
        _output(p, t),
    ], width="fill")
    return _core.scrollable(body, height="fill")


def dialog(d: "Designer", t: Theme) -> Any:
    """The ``project:*`` dialogs: new project, open project and change a dependency."""
    p = d.projects
    which = (d.dialog or "").split(":", 1)[-1]
    if which == "new":
        target = Path(p.new_folder or ".").expanduser() / (p.new_name or "…")
        return ui.modal(_core.column([
            ui.field("Name", ui.input(p.new_name, p.setter("new_name"), on_submit=p.create, width=260, theme=t),
                     theme=t),
            ui.field("Location", ui.input(p.new_folder, p.setter("new_folder"), mono=True, width=260, theme=t),
                     description=f"Creates {target}", theme=t),
            ui.field("Backend in src/", ui.switch(p.new_package, p.setter("new_package"), theme=t),
                     description="uv init --package: importable from the UI and from tests", theme=t),
            ui.field("Git repository", ui.switch(p.new_git, p.setter("new_git"), theme=t), theme=t),
        ], spacing=12), title="New project", on_close=d.close_dialog, width=560, theme=t, footer=[
            ui.button("Cancel", d.close_dialog, variant="ghost", theme=t),
            ui.button("Create", p.create, icon="folder-plus", variant="solid", theme=t)])
    if which == "open":
        recent = [ui.list_item(str(path), lambda path=path: p.open(str(path)), icon="folder-git-2", inset=True,
                               theme=t) for path in _project.recent_projects()]
        return ui.modal(_core.column([
            ui.input(p.open_text, p.setter("open_text"), placeholder="Folder with a pyproject.toml", icon="folder",
                     on_submit=lambda: p.open(p.open_text), mono=True, theme=t),
            _core.container(_core.scrollable(_core.column(recent, width="fill")), height=220) if recent else None,
        ], spacing=10), title="Open project", on_close=d.close_dialog, width=560, theme=t, footer=[
            ui.button("Cancel", d.close_dialog, variant="ghost", theme=t),
            ui.button("Open", lambda: p.open(p.open_text), variant="solid", theme=t)])
    if which == "change" and p.change_target is not None:
        return ui.modal(
            ui.field("Requirement", ui.input(p.change_text, p.setter("change_text"), on_submit=p.change, mono=True,
                                             width=260, theme=t),
                     description='A version constraint, e.g. "httpx==0.27.2" or "httpx>=0.28,<1"', theme=t),
            title=f"Change {p.change_target.name}", on_close=d.close_dialog, width=520, theme=t, footer=[
                ui.button("Cancel", d.close_dialog, variant="ghost", theme=t),
                ui.button("Apply", p.change, variant="solid", theme=t)])
    return None
