"""The designer's Project and Dependencies tabs: create and open uv projects, browse their
files, manage their dependencies, run ruff and ty, and create the git repository.

``ProjectController`` holds the state and the actions (each slow command runs on a
worker thread and reports back on the UI thread); ``view`` (the file tree, see
``workspace``), ``dependencies_view`` and ``dialog`` draw it.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .. import _core, ui
from .. import project as _project
from ..icons import icon as _icon
from ..project import Dependency, Problem, Project, Result, Tool
from ..theme import Theme, alpha
from . import logs as _logs
from . import workspace as _workspace
from .locale import tr

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
        #: What keeps the project from running with this Pyzed (an old pyzed-ui, packages not installed...).
        self.problems: List[Problem] = []
        #: The projects whose problems were dismissed for this session.
        self.dismissed: set = set()
        self._stamp: Optional[tuple] = None
        self._polled = 0.0
        self.tools: Dict[str, Tool] = {}
        self.branch: Optional[str] = None
        #: The linked git worktree the project is in (``None`` in the repository's main folder).
        self.worktree: Optional[str] = None
        #: The local branches, read when the branch menu of the title bar opens.
        self.branches: List[str] = []
        #: The projects opened in this window, in the order they were opened (the title bar's picker lists
        #: them under "This window"); ``project`` is the active one.
        self.window: List[Path] = []
        #: Called with the new active project (or ``None``) whenever it changes; see ``on_change``.
        self._listeners: List[Callable[[Optional[Project]], Any]] = []
        self.busy: Optional[str] = None
        #: Whether the git branch is being read in the background (a WSL project opened from Windows).
        self.reading_git = False
        self._git_reads = 0
        self._git_root: Optional[Path] = None
        self.reading_branches = False
        self.last: Optional[Result] = None
        self.process: Optional[subprocess.Popen] = None
        # inputs
        self.add_text = ""
        self.add_dev = False
        self.change_target: Optional[Dependency] = None
        self.change_text = ""
        self.new_name = "my-app"
        self.new_folder = str(_workspace.start_folder())
        self.new_git = True
        self.new_package = True
        self.open_text = ""
        self.clone_url = ""
        #: The filter typed in the startup file picker.
        self.startup_query = ""
        self.clone_folder = str(_workspace.start_folder())
        #: The project's file tree.
        self.files = _workspace.Workspace(designer)
        #: The folder browser of the Open project and New project dialogs.
        self.browser = _workspace.FolderBrowser(_workspace.start_folder())

    # -- opening ------------------------------------------------------------------------
    def on_change(self, callback: Callable[[Optional[Project]], Any]) -> None:
        """Calls ``callback(project)`` each time another project becomes the active one (or none is), so the
        agents and other panels can follow it."""
        self._listeners.append(callback)

    def attach(self, project: Optional[Project]) -> Any:
        """Makes ``project`` the open one (activated, remembered, its folder the working one)."""
        before = self.project.root if self.project is not None else None
        self.project = project
        changed = (project.root if project is not None else None) != before
        if changed:
            self.latest = {}
            if project is not None:
                _logs.event("project", "Opened the project %s", project.root)
            else:
                _logs.event("project", "Closed the project")
            for callback in list(self._listeners):
                callback(project)
        self.files.attach(project.root if project is not None else None)
        if project is None:
            return None
        if project.root not in self.window:
            self.window.append(project.root)
        project.activate()
        _project.remember(project)
        try:
            os.chdir(project.root)
        except OSError:
            pass
        self.refresh()
        if changed and self.problems:
            first = self.problems[0]
            self.d.notify(tr(first.title, **first.values), tr("See the Dependencies tab to fix it"), kind="warning",
                          seconds=8)
        return None

    def load_tools(self) -> Any:
        """Looks up uv, ruff, ty and git (their versions) in the background."""
        project = self.project
        if project is None:
            return None
        return self._task("Checking tools", lambda: _project.tools(project), self._got_tools, quiet=True)

    def refresh(self) -> None:
        """Rereads the open project's files: its dependencies and current git branch."""
        project = self.project
        if project is None:
            return
        project.reload()
        self._read_dependencies(project)
        self.files.refresh()
        self._git_reads += 1
        read = self._git_reads

        def work() -> None:
            branch, worktree = project.git_branch(), project.git_worktree()
            if read == self._git_reads:  # not overtaken by a newer read or another project
                self.branch, self.worktree, self.reading_git = branch, worktree, False

        if project.environment.remote:  # git crosses into Linux through wsl.exe: not on the UI thread
            if self._git_root != project.root:
                self.branch = self.worktree = None
            self._git_root = project.root
            self.reading_git = True
            threading.Thread(target=work, daemon=True, name="pyzed-git").start()
        else:
            self._git_root = project.root
            work()

    def _read_dependencies(self, project: Project) -> None:
        self.deps = project.dependencies()
        self.problems = project.problems()
        self._stamp = project.stamp()
        # a version found by Check for updates is no news once it is the locked one
        locked = {d.name: d.locked for d in self.deps}
        self.latest = {name: v for name, v in self.latest.items() if v and locked.get(name) != v}

    def poll(self, force: bool = False) -> None:
        """Rereads the dependencies when ``pyproject.toml``, ``uv.lock`` or ``.venv`` changed since they were read
        (a terminal or the agent ran uv); looks at most once a second unless ``force``."""
        project = self.project
        now = time.monotonic()
        if project is None or self.busy or (not force and now - self._polled < 1.0):
            return
        self._polled = now
        if project.stamp() != self._stamp:
            project.reload()
            self._read_dependencies(project)

    def fix(self, problem: Problem) -> Any:
        """Fixes ``problem``: updates ``pyzed-ui`` to the editor's version or syncs the environment; returns the
        background task."""
        if problem.kind in ("pyzed-old", "pyzed-missing"):
            return self._uv(tr("Updating pyzed-ui"), lambda p: p.update_pyzed())
        return self.sync()

    def dismiss_problems(self) -> None:
        """Hides the problems banner of the active project until it is opened again."""
        if self.project is not None:
            self.dismissed.add(self.project.root)

    @property
    def shown_problems(self) -> List[Problem]:
        """The problems the banner shows (none once dismissed for this project)."""
        if self.project is None or self.project.root in self.dismissed:
            return []
        return self.problems

    @property
    def loading(self) -> bool:
        """Whether the project's files or git branch are still being read in the background."""
        return self.reading_git or self.reading_branches or self.files.loading

    @property
    def environment(self) -> _project.Environment:
        """Where the active project (or, without one, the designer) lives and its commands run."""
        return self.project.environment if self.project is not None else _project.environment()

    def _got_tools(self, found: Dict[str, Tool]) -> None:
        self.tools = found

    def open(self, path: str) -> Any:
        """Opens the project at ``path`` (a notification on failure), closes the dialog, shows the Project
        panel and opens its main form if it has one; returns the task that checks its tools."""
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
        return [c for c in (self.prepare(), self.load_tools()) if c is not None]

    def prepare(self) -> Any:
        """Loads the active project's environment in the background when it is not ready, like Zed does when a
        project opens: installs uv if it is missing and creates ``.venv`` (``uv sync``) with its tools."""
        project = self.project
        if project is None or not project.needs_prepare():
            return None
        where = project.environment

        def done(result: Result) -> Any:
            if result.ok:
                self.d.notify(tr("{name} is ready", name=project.name), where.describe(), kind="success", seconds=3)
            return self.load_tools()

        return self._task(tr("Preparing the environment"), project.prepare, done)

    def switch(self, root: Path) -> Any:
        """Makes the project at ``root`` the active one of this window (it opens if it is not open yet)."""
        self.d.app_menu = None
        if self.project is not None and self.project.root == root:
            return None
        return self.open(str(root))

    def close_project(self, root: Path) -> Any:
        """Takes the project at ``root`` out of this window; when it is the active one, the previous one opened
        takes its place (or no project)."""
        if root in self.window:
            self.window.remove(root)
        if self.project is None or self.project.root != root:
            return None
        if not self.window:
            return self.attach(None)
        return self.open(str(self.window[-1]))

    def open_branches(self) -> None:
        """Opens the branch menu of the title bar with the project's local branches (read in the background for
        a WSL project opened from Windows: the menu shows the current one until they arrive)."""
        project = self.project
        self.d.app_menu = None if self.d.app_menu == "branches" else "branches"
        if project is None:
            self.branches = []
        elif not project.environment.remote:
            self.branches = project.git_branches()
        else:
            self.branches = [self.branch] if self.branch else []
            self.reading_branches = True

            def work() -> None:
                found = project.git_branches()
                if self.project is project:
                    self.branches = found
                self.reading_branches = False

            threading.Thread(target=work, daemon=True, name="pyzed-git-branches").start()

    def switch_branch(self, name: str) -> Any:
        """Checks out branch ``name`` (``git switch``) in the background; returns the task."""
        self.d.app_menu = None
        if name == self.branch:
            return None
        return self._uv(tr("Switching to {branch}", branch=name), lambda p: p.switch_branch(name))

    def create(self) -> Any:
        """Creates a project named ``new_name`` in ``new_folder`` with ``uv init`` in the background, then
        opens it; refuses a non-empty folder that is not a project. Returns the background task."""
        name = self.new_name.strip()
        if not name:
            return None
        target = Path(self.new_folder.strip() or ".").expanduser() / name
        if target.exists() and any(target.iterdir()) and not (target / "pyproject.toml").exists():
            self.d.notify("The folder is not empty", str(target), kind="error", seconds=5)
            return None
        problem = _workspace.check_writable(target)
        if problem is not None:  # the dialog stays open to choose another location
            self.d.notify(tr("Could not create the project"), problem, kind="error", seconds=8)
            return None
        self.d.dialog = None
        git, package = self.new_git, self.new_package

        def work() -> Any:
            try:
                return _project.init(target, git=git, package=package)
            except PermissionError as err:
                return Result(["uv", "init"], 1, tr("Pyzed cannot write in {folder}. Choose another location, "
                                                    "like {suggested}.", folder=err.filename or target,
                                                    suggested=_workspace.PROJECTS_FOLDER))
            except (RuntimeError, OSError) as err:
                return Result(["uv", "init"], 1, str(err))

        def done(result: Any) -> Any:
            if isinstance(result, Result):
                self.last = result
                self.d.notify("Could not create the project", result.output, kind="error", seconds=6)
                return None
            return self.open(str(result.root))

        return self._task(f"Creating {name} with uv", work, done)

    def clone_target(self) -> Optional[Path]:
        """The folder ``clone`` creates: the repository's name under ``clone_folder``."""
        # a URL, an scp-like address (git@host:user/app.git) or a local folder, with / or \ (Windows)
        name = re.split(r"[/\\]", self.clone_url.strip().rstrip("/\\"))[-1].rsplit(":", 1)[-1]
        name = name[:-4] if name.endswith(".git") else name
        return Path(self.clone_folder.strip() or ".").expanduser() / name if name else None

    def clone(self) -> Any:
        """Clones the repository at ``clone_url`` into ``clone_folder`` with git in the background, then opens it
        (and gets its environment ready); returns the task."""
        url, target = self.clone_url.strip(), self.clone_target()
        if not url or target is None:
            return None
        if target.exists() and any(target.iterdir()):
            self.d.notify(tr("The folder is not empty"), str(target), kind="error", seconds=5)
            return None
        problem = _workspace.check_writable(target)
        if problem is not None:
            self.d.notify(tr("Could not clone the repository"), problem, kind="error", seconds=8)
            return None
        self.d.dialog = None

        def done(result: Result) -> Any:
            if not result.ok:
                self.d.notify(tr("Could not clone the repository"), result.output.splitlines()[-1]
                              if result.output else None, kind="error", seconds=6)
                return None
            if not _workspace.is_project(target):
                self.d.notify(tr("The repository has no pyproject.toml"), str(target), kind="warning", seconds=6)
                return None
            return self.open(str(target))

        return self._task(tr("Cloning {name}", name=target.name), lambda: _project.clone(url, target), done)

    # -- background commands -------------------------------------------------------------
    def _task(self, label: str, work: Callable[[], Any], done: Optional[Callable[[Any], Any]] = None,
              *, quiet: bool = False) -> Any:
        """Runs ``work`` off the UI thread; ``done(result)`` then runs on it."""
        if not quiet:
            self.busy = label
        _logs.event("project", "%s…", label)

        async def run() -> Callable[[], Any]:
            result = await asyncio.get_running_loop().run_in_executor(None, work)

            def finish() -> Any:
                if not quiet:
                    self.busy = None
                if isinstance(result, Result):
                    self.last = result
                    if result.ok:
                        _logs.event("project", "%s: done", label)
                    else:
                        _logs.log("project").error("%s failed", label, extra={"detail": result.output})
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
        """Adds the packages typed in ``add_text`` (as dev dependencies with ``add_dev``) with ``uv add`` and
        clears the input; returns the background task."""
        specs = self.add_text.split()
        if not specs:
            return None
        dev = self.add_dev
        self.add_text = ""
        return self._uv(f"Adding {' '.join(specs)}", lambda p: p.add(*specs, dev=dev))

    def remove(self, dep: Dependency) -> Any:
        """Removes dependency ``dep`` from its group with ``uv remove``; returns the background task."""
        return self._uv(f"Removing {dep.name}", lambda p: p.remove(dep.name, dev=dep.group == "dev",
                                                                    group=None if dep.group in ("main", "dev")
                                                                    else dep.group))

    def upgrade(self, dep: Optional[Dependency] = None) -> Any:
        """Upgrades ``dep``, or every package when ``None``, with uv; returns the background task."""
        if dep is None:
            return self._uv("Upgrading every package", lambda p: p.upgrade())
        return self._uv(f"Upgrading {dep.name}", lambda p: p.upgrade(dep.name))

    def start_change(self, dep: Dependency) -> None:
        """Opens the dialog that changes the version spec of ``dep``, prefilled with its current one."""
        self.change_target = dep
        self.change_text = dep.spec
        self.d.dialog = "project:change"

    def change(self) -> Any:
        """Applies the spec typed in the change dialog to the dependency being changed (in its group) and
        closes the dialog; returns the background task."""
        dep, spec = self.change_target, self.change_text.strip()
        self.d.dialog = None
        if dep is None or not spec:
            return None
        dev = dep.group == "dev"
        group = None if dep.group in ("main", "dev") else dep.group
        return self._uv(f"Changing {dep.name}", lambda p: p.change(spec, dev=dev, group=group))

    def sync(self) -> Any:
        """Syncs the project's environment with ``uv sync``; returns the background task."""
        return self._uv("Syncing the environment", lambda p: p.sync())

    def check_updates(self) -> Any:
        """Looks up newer versions of the dependencies in the background, stores them in ``latest`` and
        notifies how many there are."""
        project = self.project
        if project is None or self.busy:
            return None

        def found(outdated: List[Dependency]) -> None:
            self.latest = {d.name: d.latest or "" for d in outdated}
            self.d.notify(f"{len(outdated)} updates available" if outdated else "Everything is up to date",
                          kind="info", seconds=3)

        return self._task("Checking for updates", project.outdated, found)

    def lint(self) -> Any:
        """Runs ``ruff check`` on the project; returns the background task."""
        return self._uv("ruff check", lambda p: p.check())

    def format(self) -> Any:
        """Runs ``ruff format`` on the project; returns the background task."""
        return self._uv("ruff format", lambda p: p.format())

    def typecheck(self) -> Any:
        """Runs ``ty check`` on the project; returns the background task."""
        return self._uv("ty check", lambda p: p.typecheck())

    def git_init(self) -> Any:
        """Creates a git repository in the project; returns the background task."""
        return self._uv("Creating the git repository", lambda p: p.git_init())

    # -- running forms -------------------------------------------------------------------
    @property
    def runs_outside(self) -> bool:
        """Forms of this project run through ``uv run`` (the designer lacks its dependencies)."""
        return self.project is not None and not self.project.can_run_in_process

    def run_form(self, form: Path, *, capture: bool = False, env: Optional[Dict[str, str]] = None) -> None:
        """Starts ``form`` with ``uv run pyzed run --reload`` in the project (``capture``: pipe its output;
        ``env``: extra environment variables)."""
        assert self.project is not None
        self.stop()
        try:
            self.process = self.project.spawn(form, reload=True, capture=capture, env=env)
        except (OSError, FileNotFoundError) as err:
            self.d.notify("Could not start the form", str(err), kind="error", seconds=5)
            return
        self.d.notify(f"Running {form.name}", "With uv run; saving updates the window", seconds=3)

    def run_script(self, *, capture: bool = False, env: Optional[Dict[str, str]] = None) -> bool:
        """Starts the project's ``script`` with ``uv run`` (``capture``: pipe its output); ``False`` if it
        could not start."""
        assert self.project is not None and self.project.script is not None
        self.stop()
        try:
            self.process = self.project.spawn_script(capture=capture, env=env)
        except (OSError, FileNotFoundError) as err:
            self.d.notify(tr("Could not start {name}", name=self.project.script.name), str(err), kind="error",
                          seconds=5)
            return False
        self.d.notify(tr("Running {name}", name=self.project.script.name), tr("With uv run"), seconds=3)
        return True

    def stop(self) -> None:
        """Terminates the form process started with ``run_form``, if it is still running."""
        if self.process is not None:
            _project.terminate(self.process)
        self.process = None

    # -- startup file ----------------------------------------------------------------------
    def startup_label(self) -> Optional[str]:
        """The startup file relative to the project (``ui/main.pzform``), or ``None`` without a project."""
        if self.project is None:
            return None
        try:
            return self.project.startup.resolve().relative_to(self.project.root.resolve()).as_posix()
        except ValueError:
            return str(self.project.startup)

    def open_startup(self) -> None:
        """Opens the picker of the file the app starts from (a form or a script)."""
        if self.project is None:
            self.d.notify(tr("Open a project first"), tr("The startup file is a setting of the project"),
                          kind="warning", seconds=4)
            return
        self.startup_query = ""
        self.d.app_menu = None
        self.d.dialog = "project:startup"

    def startup_choices(self) -> List[str]:
        """The forms and scripts the picker offers, relative to the project, filtered by what was typed."""
        if self.project is None:
            return []
        root = self.project.root
        query = self.startup_query.strip().lower()
        rels = [p.relative_to(root).as_posix() for p in self.project.startup_choices()]
        return [r for r in rels if query in r.lower()]

    def set_startup(self, path: Any) -> bool:
        """Makes ``path`` (a ``.pzform`` or ``.py`` file of the project) the file Run (F5 with nothing open),
        ``pyzed run`` and ``pyzed build`` start from."""
        if self.project is None:
            return False
        path = Path(path)
        try:
            self.project.set_startup(path if path.is_absolute() else self.project.root / path)
        except (OSError, ValueError) as err:
            self.d.notify(tr("Could not change the startup file"), str(err), kind="error", seconds=5)
            return False
        if self.d.dialog == "project:startup":
            self.d.dialog = None
        _logs.event("project", "Startup file: %s", path.name)
        self.d.notify(tr("{name} is the startup file", name=path.name), tr("Run (F5) starts the app from it"),
                      kind="success", seconds=3)
        return True

    # -- input setters ---------------------------------------------------------------------
    def setter(self, attr: str) -> Callable[[Any], None]:
        """Returns a callback that stores the value it receives in attribute ``attr`` (for input widgets)."""
        def set_value(value: Any) -> None:
            setattr(self, attr, value)

        return set_value

    def show(self, dialog: str) -> Callable[[], None]:
        """Returns a callback that opens the project dialog ``dialog`` (``"open"``, ``"new"``...)."""
        def open_dialog() -> None:
            if dialog == "open":
                recent = _project.recent_projects(1)
                self.browser.go(recent[0].parent if recent else _workspace.start_folder())
            elif dialog == "browse_new":
                self.browser.go(self.new_folder or _workspace.start_folder())
            elif dialog == "browse_clone":
                self.browser.go(self.clone_folder or _workspace.start_folder())
            self.d.dialog = f"project:{dialog}"

        return open_dialog

    def choose_location(self) -> None:
        """Takes the browser's folder as the New project location and goes back to that dialog."""
        self.new_folder = str(self.browser.path)
        self.d.dialog = "project:new"

    def choose_clone_location(self) -> None:
        """Takes the browser's folder as where the repository is cloned and goes back to the Clone dialog."""
        self.clone_folder = str(self.browser.path)
        self.d.dialog = "project:clone"


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
                           ui.button(tr("Open project"), p.show("open"), icon="folder-open", variant="solid",
                                     size="sm", theme=t),
                           ui.button(tr("New project"), p.show("new"), icon="folder-plus", size="sm", theme=t)]),
        _core.container(ui.button(tr("Clone repository"), p.show("clone"), icon="git-branch", variant="ghost",
                                  size="sm", theme=t), width="fill", align_x="center"),
    ]
    if recent:
        parts += [_section("Recent", t), *recent]
    return _core.scrollable(_core.container(_core.column(parts, width="fill"), padding=(16, 4), width="fill"),
                            height="fill")


def _dep_row(p: ProjectController, dep: Dependency, t: Theme) -> Any:
    newer = p.latest.get(dep.name)
    if newer and newer == dep.locked:
        newer = None
    unsynced = p.project is not None and p.project.venv.is_dir() and dep.locked is not None \
        and dep.installed != dep.locked
    version = ui.label(f"↑{newer}" if newer else dep.installed or dep.locked or "—", size="xs", mono=True,
                       color="success" if newer else "warning" if unsynced else "text_muted", theme=t)
    if newer:
        version = ui.tooltip(version, f"{dep.locked} → {newer}: press Upgrade", theme=t)
    elif unsynced:
        version = ui.tooltip(version, tr("Installed {installed}, uv.lock says {locked}: press Sync",
                                         installed=dep.installed or tr("nothing"), locked=dep.locked), theme=t)
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


def _startup_row(p: ProjectController, project: Project, t: Theme) -> Any:
    """The project's startup file under its name, with the picker to change it."""
    label = p.startup_label() or ""
    icon = "layout-template" if label.endswith(".pzform") else "file-code"
    button = ui.button(label, p.open_startup, icon=icon, variant="ghost", size="sm", theme=t)
    return _core.row([
        _icon("play", size=12, color=t.success),
        ui.label(tr("Starts from"), size="xs", color="text_muted", theme=t),
        ui.tooltip(button, tr("Choose the form or script the app starts from"), theme=t),
    ], spacing=6, align="center")


def _header(d: "Designer", p: ProjectController, project: Project, t: Theme) -> Any:
    git = (ui.badge(p.branch or "git", icon="git-branch", tint="accent", theme=t) if project.is_git else
           ui.button(tr("Create repository"), p.git_init, icon="git-branch-plus", size="sm", variant="ghost",
                     theme=t))
    return _core.container(_core.column([
        _core.row([ui.label(project.name, weight="semibold", theme=t),
                   ui.label(project.version, size="xs", mono=True, color="text_muted", theme=t),
                   _core.space(width="fill"), git,
                   ui.icon_button("folder-open", p.show("open"), size="sm", tooltip=tr("Open another project"),
                                  theme=t)], spacing=6, align="center"),
        ui.label(str(project.root), size="xs", color="text_muted", wrap=False, theme=t),
        _startup_row(p, project, t),
    ], spacing=2), padding=(10, 12, 4, 12), width="fill")


def _problems(p: ProjectController, t: Theme) -> Any:
    """The banner that says the project needs a newer pyzed-ui or a sync, with the buttons that do it."""
    problems = p.shown_problems
    if not problems:
        return None
    first = problems[0]
    details = [tr(first.detail, **first.values)] + [tr(x.title, **x.values) for x in problems[1:]]
    actions = []
    if any(x.kind in ("pyzed-old", "pyzed-missing") for x in problems):
        actions.append(ui.button(tr("Update pyzed-ui"), lambda: p.fix(first), icon="arrow-up-circle",
                                 variant="solid", size="sm", theme=t))
    elif any(x.kind in ("no-environment", "not-installed") for x in problems):
        actions.append(ui.button(tr("Sync"), p.sync, icon="refresh-cw", variant="solid", size="sm", theme=t))
    # stacked rather than a ui.callout row: the dock is too narrow for the text and the button side by side
    close = ui.icon_button("x", p.dismiss_problems, size="sm", tooltip=tr("Hide until the project opens again"),
                           theme=t)
    box = _core.container(_core.column([
        _core.row([_icon("triangle-alert", size=14, color=t.warning),
                   _core.container(ui.label(tr(first.title, **first.values), size="sm", weight="medium", theme=t),
                                   width="fill"),
                   close], spacing=8, align="center"),
        *[ui.label(detail, size="xs", color="text_muted", theme=t) for detail in details if detail],
        _core.row(actions, spacing=6) if actions else None,
    ], spacing=6, width="fill"), padding=(8, 10), width="fill", bg=alpha(t.warning, 0.1), radius=t.radius,
        border_color=alpha(t.warning, 0.35), border_width=1.0)
    return _core.container(box, padding=(6, 8), width="fill")


def _busy(p: ProjectController, t: Theme) -> Any:
    if not p.busy:
        return None
    return _core.container(_core.row([ui.spinner(size=12, theme=t), ui.label(p.busy, size="sm", theme=t)],
                                     spacing=8, align="center"), padding=(4, 12), width="fill",
                           bg=alpha(t.accent, 0.08))


def view(d: "Designer", t: Theme) -> Any:
    """The Project tab of the left dock: the project's files, like Zed's project panel."""
    p = d.projects
    project = p.project
    if project is None:
        return _empty(p, t)
    tree = _core.mouse_area(_core.container(_workspace.tree_view(p.files, t), padding=(0, 4, 24, 4), width="fill"),
                            on_press=p.files.focus, on_right_press=lambda: p.files.open_menu(""))
    return _core.column([
        _header(d, p, project, t),
        _problems(p, t),
        _busy(p, t),
        _workspace.toolbar_view(p.files, t),
        _core.scrollable(tree, height="fill"),
    ], width="fill", height="fill")


def dependencies_view(d: "Designer", t: Theme) -> Any:
    """The Dependencies tab: the packages of the open project (uv), its tools and checks."""
    p = d.projects
    if p.project is None:
        return _empty(p, t)
    add = _core.container(_core.row([
        ui.input(p.add_text, p.setter("add_text"), placeholder=tr("Add package, e.g. httpx"), size="sm",
                 on_submit=p.add, theme=t),
        ui.checkbox(p.add_dev, p.setter("add_dev"), label="dev", theme=t),
        ui.icon_button("plus", p.add, size="sm", tooltip=tr("Add (uv add)"), theme=t),
    ], spacing=6, align="center"), padding=(2, 12), width="fill")
    dep_actions = _core.row([
        ui.icon_button("refresh-cw", p.sync, size="sm", tooltip=tr("Sync (uv sync)"), theme=t),
        ui.icon_button("search-check", p.check_updates, size="sm", tooltip=tr("Check for updates"), theme=t),
        ui.icon_button("arrow-up-circle", lambda: p.upgrade(), size="sm", tooltip=tr("Upgrade all"), theme=t),
    ], spacing=2)
    checks = _core.container(_core.row([
        ui.tooltip(ui.button("Lint", p.lint, icon="list-checks", size="sm", theme=t), "ruff check", theme=t),
        ui.tooltip(ui.button("Format", p.format, icon="wand-sparkles", size="sm", theme=t), "ruff format", theme=t),
        ui.tooltip(ui.button("Types", p.typecheck, icon="shield-check", size="sm", theme=t), "ty check", theme=t),
    ], spacing=4), padding=(4, 8), width="fill")
    body = _core.column([
        _problems(p, t),
        _busy(p, t),
        _section(tr("Dependencies"), t, dep_actions),
        add,
        *[_dep_row(p, dep, t) for dep in p.deps],
        _section(tr("Tools"), t),
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
            ui.field("Location", _core.row([
                ui.input(p.new_folder, p.setter("new_folder"), mono=True, width=260, theme=t),
                ui.button(tr("Browse…"), p.show("browse_new"), icon="folder-search", size="sm", theme=t),
            ], spacing=6, align="center"), description=f"Creates {target}", theme=t),
            ui.field("Backend in src/", ui.switch(p.new_package, p.setter("new_package"), theme=t),
                     description="uv init --package: importable from the UI and from tests", theme=t),
            ui.field("Git repository", ui.switch(p.new_git, p.setter("new_git"), theme=t), theme=t),
        ], spacing=12), title="New project", on_close=d.close_dialog, width=560, theme=t, footer=[
            ui.button("Cancel", d.close_dialog, variant="ghost", theme=t),
            ui.button("Create", p.create, icon="folder-plus", variant="solid", theme=t)])
    if which == "open":
        here = p.browser.path
        ok = _workspace.is_project(here)
        hint = tr("{folder} is a uv project", folder=here.name or str(here)) if ok else \
            tr("Pick a folder with a pyproject.toml")
        return ui.modal(_workspace.browser_view(p.browser, t, open_project=lambda f: p.open(str(f)),
                                                recent=_project.recent_projects()),
                        title=tr("Open project"), on_close=d.close_dialog, width=760, theme=t, footer=[
            ui.label(hint, size="sm", color="success" if ok else "text_muted", theme=t),
            _core.space(width="fill"),
            ui.button(tr("Cancel"), d.close_dialog, variant="ghost", theme=t),
            ui.button(tr("Open"), lambda: p.open(str(here)), icon="folder-open", variant="solid", disabled=not ok,
                      theme=t)])
    if which == "browse_new":
        return ui.modal(_workspace.browser_view(p.browser, t), title=tr("Choose where to create the project"),
                        on_close=p.show("new"), width=760, theme=t, footer=[
            ui.label(str(p.browser.path / (p.new_name or "…")), size="sm", mono=True, color="text_muted", theme=t),
            _core.space(width="fill"),
            ui.button(tr("Back"), p.show("new"), variant="ghost", theme=t),
            ui.button(tr("Choose this folder"), p.choose_location, icon="check", variant="solid", theme=t)])
    if which == "clone":
        target = p.clone_target()
        return ui.modal(_core.column([
            ui.field(tr("Repository URL"), ui.input(p.clone_url, p.setter("clone_url"), on_submit=p.clone, mono=True,
                                                     placeholder="https://github.com/user/app.git", width=360,
                                                     theme=t), theme=t),
            ui.field(tr("Location"), _core.row([
                ui.input(p.clone_folder, p.setter("clone_folder"), mono=True, width=260, theme=t),
                ui.button(tr("Browse…"), p.show("browse_clone"), icon="folder-search", size="sm", theme=t),
            ], spacing=6, align="center"), description=tr("Creates {target}", target=target) if target else None,
                theme=t),
        ], spacing=12), title=tr("Clone repository"), on_close=d.close_dialog, width=560, theme=t, footer=[
            ui.button(tr("Cancel"), d.close_dialog, variant="ghost", theme=t),
            ui.button(tr("Clone"), p.clone, icon="git-branch", variant="solid", disabled=target is None, theme=t)])
    if which == "browse_clone":
        return ui.modal(_workspace.browser_view(p.browser, t), title=tr("Choose where to clone the repository"),
                        on_close=p.show("clone"), width=760, theme=t, footer=[
            _core.space(width="fill"),
            ui.button(tr("Back"), p.show("clone"), variant="ghost", theme=t),
            ui.button(tr("Choose this folder"), p.choose_clone_location, icon="check", variant="solid", theme=t)])
    if which == "startup" and p.project is not None:
        return startup_dialog(d, t)
    if which == "name" and p.files.naming is not None:
        return _workspace.name_dialog(p.files, t)
    if which == "delete" and p.files.deleting is not None:
        return _workspace.delete_dialog(p.files, t)
    if which == "find":
        return _workspace.find_dialog(p.files, t)
    if which == "change" and p.change_target is not None:
        return ui.modal(
            ui.field("Requirement", ui.input(p.change_text, p.setter("change_text"), on_submit=p.change, mono=True,
                                             width=260, theme=t),
                     description='A version constraint, e.g. "httpx==0.27.2" or "httpx>=0.28,<1"', theme=t),
            title=f"Change {p.change_target.name}", on_close=d.close_dialog, width=520, theme=t, footer=[
                ui.button("Cancel", d.close_dialog, variant="ghost", theme=t),
                ui.button("Apply", p.change, variant="solid", theme=t)])
    return None


def startup_dialog(d: "Designer", t: Theme) -> Any:
    """Picks the file the app starts from: the project's forms first, then its scripts."""
    p = d.projects
    current = p.startup_label()
    rows = []
    for rel in p.startup_choices():
        form = rel.endswith(".pzform")
        rows.append(ui.list_item(rel, lambda r=rel: p.set_startup(r), icon="layout-template" if form else "file-code",
                                 description=tr("Form") if form else tr("Python script"),
                                 end=_icon("check", size=14, color=t.text_accent) if rel == current else None,
                                 selected=rel == current, inset=True, theme=t))
    if not rows:
        rows = [ui.label(tr("No forms or scripts match"), size="sm", color="text_muted", theme=t)]
    choices = p.startup_choices()
    return ui.modal(_core.column([
        ui.label(tr("Run (F5) with nothing open, pyzed run and pyzed build start the app from this file. A form "
                    "opens as the main window; a script runs with uv run."), size="sm", color="text_muted", theme=t),
        ui.input(p.startup_query, p.setter("startup_query"), placeholder=tr("Filter forms and scripts…"),
                 icon="search", on_submit=lambda: p.set_startup(choices[0]) if choices else None, theme=t),
        _core.container(_core.scrollable(_core.column(rows, width="fill")), height=280),
    ], spacing=10), title=tr("Startup file"), on_close=d.close_dialog, width=560, theme=t)
