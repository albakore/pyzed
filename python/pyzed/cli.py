"""The ``pyzed`` command: projects (``new``, ``init``, ``add``, ``remove``, ``upgrade``, ``sync``,
``deps``, ``check``, ``build``), running (``dev``, ``design``, ``run``), ``icons``, ``mcp`` and ``windows``
(native Windows windows under WSL)."""

from __future__ import annotations

import argparse
import os
import re
import runpy
import sys
from pathlib import Path
from typing import Optional


def new_script(name: str) -> int:
    """The single-file app of ``pyzed new --script``: ``main.py`` + ``requirements.txt``."""
    target = Path(name)
    if target.exists() and any(target.iterdir()):
        print(f"error: {target} already exists and is not empty", file=sys.stderr)
        return 1
    target.mkdir(parents=True, exist_ok=True)
    title = re.sub(r"[-_]+", " ", target.name).strip().title() or "My App"
    template = (Path(__file__).parent / "templates" / "app.py.tmpl").read_text(encoding="utf-8")
    (target / "main.py").write_text(template.format(name=title), encoding="utf-8")
    (target / "requirements.txt").write_text("--only-binary pyzed-ui\npyzed-ui\n", encoding="utf-8")
    print(f"Created {target}/main.py\n\n  cd {target}\n  python main.py\n")
    return 0


def _project(path: str = "."):
    from .project import Project

    found = Project.find(path)
    if found is None:
        print("error: no pyproject.toml here or in a parent folder; create one with `pyzed init`", file=sys.stderr)
    return found


def _report(result) -> int:
    if result.output:
        print(result.output)
    return 0 if result.ok else (result.code or 1)


def new(name: str, *, script: bool = False, app: bool = False, git: bool = True, python=None,
        sync: bool = True) -> int:
    """Creates a uv project with the UI in ``ui/`` (``--script`` keeps the old single-file app)."""
    if script:
        return new_script(name)
    target = Path(name)
    if target.exists() and any(target.iterdir()):
        print(f"error: {target} already exists and is not empty (use `pyzed init` inside it)", file=sys.stderr)
        return 1
    return init(name, app=app, git=git, python=python, sync=sync)


def init(path: str = ".", *, app: bool = False, git: bool = True, python=None, sync: bool = True) -> int:
    """Adds Pyzed to the uv project at ``path``, running ``uv init`` first if there is none."""
    from . import project

    if project.find_uv() is None:
        print("error: uv is required: https://docs.astral.sh/uv/getting-started/installation/", file=sys.stderr)
        return 1
    try:
        created = project.init(path, package=not app, git=git, python=python, sync=sync)
    except RuntimeError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1
    rel = os.path.relpath(created.root)
    cd = f"  cd {rel}\n" if rel != "." else ""
    print(f"Created the Pyzed project {created.name} in {created.root}\n\n{cd}"
          f"  uv run pyzed design     # edit {created.main_form.relative_to(created.root).as_posix()}\n"
          f"  uv run pyzed run        # run it\n")
    return 0


def deps(outdated: bool = False) -> int:
    """``pyzed deps``: prints each dependency with its locked version and group.

    With ``outdated`` only those with a newer release are listed, as ``locked -> latest``.
    Returns the exit code.
    """
    project = _project()
    if project is None:
        return 1
    items = project.outdated() if outdated else project.dependencies()
    if not items:
        print("All dependencies are up to date" if outdated else "No dependencies")
    for dep in items:
        version = f"{dep.locked} -> {dep.latest}" if outdated else (dep.locked or "not locked")
        group = "" if dep.group == "main" else f"  [{dep.group}]"
        print(f"{dep.spec:<32} {version}{group}")
    return 0


def check(fix: bool = False) -> int:
    """``pyzed check``: lints with ruff (fixing what it can when ``fix``) and type checks with ty.

    Prints both commands and their output; returns 0 only when both pass.
    """
    project = _project()
    if project is None:
        return 1
    lint = project.check(fix=fix)
    print(f"$ {lint.command}")
    _report(lint)
    types = project.typecheck()
    print(f"\n$ {types.command}")
    _report(types)
    return 0 if lint.ok and types.ok else 1


def build(*, onefile=None, console: bool = False, name=None, dry_run: bool = False, workflow: bool = False,
          backend=None, target=None, archive=None) -> int:
    """``pyzed build``: packages the project with PyInstaller or Nuitka and prints where the result is.

    ``workflow`` writes a GitHub Actions workflow instead (for the project's ``targets``), and ``dry_run``
    only prints the backend's command. ``onefile``, ``console``, ``name``, ``backend`` and ``archive``
    override the project's build settings; ``target`` must be this computer's (``linux-x64``...), since
    the backends do not cross-compile. Returns the exit code.
    """
    from . import build as _build

    project = _project()
    if project is None:
        return 1
    if workflow:
        print(f"Wrote {_build.workflow(project).relative_to(project.root).as_posix()}")
        return 0
    if target is not None and target.startswith("android"):
        return _build_android(project, target, name=name)
    here = _build.host_target(project)
    if target is not None and target != here.id:
        print(f"This computer builds {here.id}, not {target}: build {target} on its own system, or write a "
              "workflow that builds every target with `pyzed build --workflow`", file=sys.stderr)
        return 2
    opts = _build.BuildOptions.from_project(project, onefile=onefile, name=name, backend=backend, archive=archive,
                                            windowed=False if console else None)
    if dry_run:
        print(_build.describe(_build.prepare(project, opts).command))
        return 0
    print(f"Building {project.name} for {here.label} with {_build.BACKEND_LABELS[opts.backend]}…")
    code = _report(_build.build(project, opts))
    if code == 0:
        result = _build.output(project, opts)
        print(f"\nDone: {result} ({_build.human_size(_build.size_of(result))})")
    return code


def _build_android(project, target: str, *, name=None) -> int:
    """``pyzed build --target android-arm64`` (or ``android-x64``, or ``android`` for the project's ABIs)."""
    from . import android, build as _build

    abis = None
    if target != "android":
        if target not in android.TARGET_ABIS:
            print(f"Unknown target {target}: use android-arm64 (phones) or android-x64 (emulators)", file=sys.stderr)
            return 2
        abis = [android.TARGET_ABIS[target]]
    opts = _build.BuildOptions.from_project(project, name=name)
    print(f"Building {project.name} for Android…")
    result = _build.build_android(project, opts, abis)
    code = _report(result)
    if code == 0:
        out = _build.android_output(project, opts)
        print(f"\nDone: {out} ({_build.human_size(_build.size_of(out))})")
    return code


def dev(script: str, args: list, watch: list) -> int:
    """Runs ``script`` like ``python script`` with hot reload on.

    Saving any ``.py`` file next to the script (or in a ``--watch`` folder) updates the
    running window without restarting it.
    """
    path = Path(script)
    if not path.is_file():
        print(f"error: {script} not found", file=sys.stderr)
        return 1
    os.environ["PYZED_RELOAD"] = "1"
    if watch:
        os.environ["PYZED_WATCH"] = os.pathsep.join(str(Path(w).resolve()) for w in watch)
    sys.argv = [str(path), *args]
    sys.path.insert(0, str(path.resolve().parent))
    runpy.run_path(str(path), run_name="__main__")
    return 0


def icons(pattern: str = "") -> int:
    """``pyzed icons``: prints the bundled Lucide icon names that contain ``pattern``."""
    from .icons import names

    for name in names():
        if pattern in name:
            print(name)
    return 0


def design(path=None) -> int:
    """``pyzed design``: opens the form designer on ``path``.

    With no path, or a project folder, it opens the Pyzed project's main form.
    """
    from .designer import design as open_designer
    from .project import activate_for

    # With no form (or a project folder), open the project's main form.
    project = activate_for(path or ".")
    if project is not None and project.is_pyzed and (path is None or Path(path).is_dir()):
        path = project.main_form
    open_designer(path)
    return 0


def run_form(path=None, reload: bool = False) -> int:
    """``pyzed run``: runs a ``.pzform`` file (or a ``.pzcomp`` component or ``.pzshad`` shader), by default
    the current project's startup file (its main form, or the script set as startup in the designer).

    ``reload`` updates the window when the form or its code is saved. Returns 1 when there is no form to run.
    """
    from .designer import run
    from .project import Project

    if path is None or Path(path).is_dir():
        project = Project.find(path or ".")
        if project is None or not project.is_pyzed:
            print("error: give a .pzform file, or run inside a Pyzed project", file=sys.stderr)
            return 1
        if project.script is not None:
            return dev(str(project.script), [], []) if reload else _run_script(project.script)
        path = project.main_form
    if not Path(path).exists():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 1
    run(path, reload=reload or None)
    return 0


def _run_script(script: Path) -> int:
    """Runs a project's startup script like ``python script``."""
    if not script.is_file():
        print(f"error: {script} does not exist", file=sys.stderr)
        return 1
    sys.argv = [str(script)]
    sys.path.insert(0, str(script.parent))
    runpy.run_path(str(script), run_name="__main__")
    return 0


def on_windows(args, argv) -> Optional[int]:
    """Under WSL, runs ``design``, ``run`` or ``dev`` again as a Windows program, so its window is a native one
    (see ``pyzed._wsl_windows``); returns its exit code, or ``None`` to open the window here (WSLg)."""
    from . import _wsl_windows
    from .project import Project

    if args.wslg:
        _wsl_windows.disable()
    if not _wsl_windows.enabled():
        return None
    target = args.script if args.command == "dev" else args.form
    project = Project.find(target or ".")
    script = Path(args.script).resolve() if args.command == "dev" and project is None else None
    return _wsl_windows.handoff(["-m", "pyzed", *(sys.argv[1:] if argv is None else argv)], project=project,
                                script=script)


def windows(action: str, path: str = ".") -> int:
    """``pyzed windows``: under WSL, shows (``status``), prepares (``setup``) or deletes (``reset``) what opens
    the windows of the project at ``path`` as native Windows windows."""
    from . import _wsl_windows
    from .project import Project

    project = Project.find(path)
    if action == "setup":
        return _wsl_windows.setup(project)
    if action == "reset":
        return _wsl_windows.reset(project)
    print("\n".join(_wsl_windows.status(project)))
    return 0


def main(argv=None) -> int:
    """The ``pyzed`` command line: parses ``argv`` (``sys.argv`` by default) and runs the subcommand.

    Returns the process exit code.
    """
    parser = argparse.ArgumentParser(prog="pyzed", description="Pyzed: fast GUIs for Python powered by Iced")
    sub = parser.add_subparsers(dest="command", required=True)
    p_new = sub.add_parser("new", help="create a project (uv, ruff, ty, git) with the UI in ui/")
    p_new.add_argument("name")
    p_new.add_argument("--script", action="store_true", help="just a main.py, without uv")
    p_init = sub.add_parser("init", help="add Pyzed to a uv project (runs `uv init` if needed)")
    p_init.add_argument("path", nargs="?", default=".")
    for p in (p_new, p_init):
        p.add_argument("--app", action="store_true", help="backend modules next to pyproject.toml, not in src/")
        p.add_argument("--no-git", action="store_true", help="do not create a git repository")
        p.add_argument("--python", help="Python version for the project, e.g. 3.12")
        p.add_argument("--no-sync", action="store_true", help="only edit pyproject.toml; install nothing")
    p_add = sub.add_parser("add", help="add or change dependencies (uv add)")
    p_add.add_argument("packages", nargs="+", metavar="PACKAGE", help='e.g. httpx or "httpx==0.27"')
    p_add.add_argument("--editable", action="store_true", help="install a local path in editable mode")
    p_remove = sub.add_parser("remove", help="remove dependencies (uv remove)")
    p_remove.add_argument("packages", nargs="+", metavar="PACKAGE")
    for p in (p_add, p_remove):
        p.add_argument("--dev", action="store_true", help="the development group")
        p.add_argument("--group", help="another dependency group")
    p_upgrade = sub.add_parser("upgrade", help="upgrade dependencies (all when none is given)")
    p_upgrade.add_argument("packages", nargs="*", metavar="PACKAGE")
    sub.add_parser("sync", help="install exactly what uv.lock says (uv sync)")
    p_deps = sub.add_parser("deps", help="list the project's dependencies")
    p_deps.add_argument("--outdated", action="store_true", help="only those with a newer release")
    p_check = sub.add_parser("check", help="lint with ruff and type check with ty")
    p_check.add_argument("--fix", action="store_true", help="let ruff fix what it can")
    p_build = sub.add_parser("build", help="package the app for this platform (PyInstaller or Nuitka)")
    p_build.add_argument("--backend", choices=["pyinstaller", "nuitka"], help="the packager (default: pyproject.toml)")
    p_build.add_argument("--target", help="the platform to build: this computer's (e.g. linux-x64), or android-arm64 "
                                          "and android-x64 from any computer")
    p_build.add_argument("--archive", choices=["zip", "tar.gz"], help="also pack the app in an archive")
    p_build.add_argument("--onefile", action="store_true", default=None, help="a single executable file")
    p_build.add_argument("--console", action="store_true", help="keep the console window")
    p_build.add_argument("--name", help="name of the executable")
    p_build.add_argument("--dry-run", action="store_true", help="print the backend's command")
    p_build.add_argument("--workflow", action="store_true",
                         help="write a GitHub Actions workflow that builds every target of the project")
    p_dev = sub.add_parser("dev", help="run a script with hot reload (changes show up when you save)")
    p_dev.add_argument("script")
    p_dev.add_argument("--watch", action="append", default=[], metavar="PATH", help="also watch this folder or file")
    p_dev.add_argument("args", nargs=argparse.REMAINDER, help="arguments passed to the script")
    p_design = sub.add_parser("design", help="open the visual form designer")
    p_design.add_argument("form", nargs="?", help="a .pzform, .pzcomp or .pzshad file (created on first save if "
                                                   "missing) or a project")
    p_run = sub.add_parser("run", help="run a form, component or shader made with the designer (default: the "
                                         "project's main form)")
    p_run.add_argument("form", nargs="?")
    p_run.add_argument("--reload", action="store_true", help="update the window when the form or its code is saved")
    for p in (p_dev, p_design, p_run):
        p.add_argument("--wslg", action="store_true",
                       help="under WSL, open the window through WSLg instead of as a native Windows window")
    p_windows = sub.add_parser("windows", help="under WSL: native Windows windows (status, setup, reset)")
    p_windows.add_argument("action", nargs="?", choices=("status", "setup", "reset"), default="status",
                           help="setup installs uv on Windows if needed and prepares the Windows environment")
    p_windows.add_argument("path", nargs="?", default=".", help="the project (default: the current folder)")
    p_icons = sub.add_parser("icons", help="list the bundled Lucide icon names")
    p_icons.add_argument("filter", nargs="?", default="")
    p_mcp = sub.add_parser("mcp", help="run the MCP server for AI agents (stdio)")
    p_mcp.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    p_mcp.add_argument("--allow-code", action="store_true",
                       help="offer screenshot and the project tools (they run code) over streamable-http too")
    p_mcp.add_argument("--root", default=None, help="folder the project tools work in (default: the current one)")
    args = parser.parse_args(argv)
    if args.command in ("new", "init"):
        options = dict(app=args.app, git=not args.no_git, python=args.python, sync=not args.no_sync)
        if args.command == "new":
            return new(args.name, script=args.script, **options)
        return init(args.path, **options)
    if args.command in ("add", "remove", "upgrade", "sync"):
        project = _project()
        if project is None:
            return 1
        if args.command == "add":
            return _report(project.add(*args.packages, dev=args.dev, group=args.group, editable=args.editable))
        if args.command == "remove":
            return _report(project.remove(*args.packages, dev=args.dev, group=args.group))
        if args.command == "upgrade":
            return _report(project.upgrade(*args.packages))
        return _report(project.sync())
    if args.command == "deps":
        return deps(args.outdated)
    if args.command == "check":
        return check(args.fix)
    if args.command == "build":
        return build(onefile=args.onefile, console=args.console, name=args.name, dry_run=args.dry_run,
                     workflow=args.workflow, backend=args.backend, target=args.target, archive=args.archive)
    if args.command in ("dev", "design", "run"):
        code = on_windows(args, argv)
        if code is not None:
            return code
    if args.command == "dev":
        return dev(args.script, args.args, args.watch)
    if args.command == "design":
        return design(args.form)
    if args.command == "run":
        return run_form(args.form, args.reload)
    if args.command == "windows":
        return windows(args.action, args.path)
    if args.command == "mcp":
        from .mcp import main as mcp_main

        return mcp_main(args.transport, True if args.allow_code else None, args.root)
    return icons(args.filter)


if __name__ == "__main__":
    sys.exit(main())
