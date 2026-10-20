"""Pyzed projects: a standard ``uv`` project with the UI in its own folder.

    my-app/
    ├── pyproject.toml        # uv project, plus a [tool.pyzed] table
    ├── uv.lock
    ├── .venv/
    ├── src/my_app/           # backend: plain Python, importable from anywhere
    └── ui/                   # frontend: forms (.pzform) and their handlers (.py)
        ├── main.pzform
        └── main.py

The UI folder only holds the interface; anything else (``src/``, modules next to
``pyproject.toml``, the packages in ``.venv``) is importable from its handlers once the
project is activated, which ``pyzed run``, ``pyzed design`` and ``pyzed build`` do.

Dependencies, the lock file and the environment are managed by `uv
<https://docs.astral.sh/uv/>`_; linting and type checking use ``ruff`` and ``ty``::

    from pyzed import project

    app = project.init("my-app")          # uv init + pyzed-ui + ruff + ty + git
    app.add("httpx")                      # uv add httpx
    app.add("pytest", dev=True)           # uv add --dev pytest
    app.upgrade("httpx")                  # uv lock --upgrade-package httpx && uv sync
    app.remove("httpx")                   # uv remove httpx
    app.check()                           # ruff check
    app.typecheck()                       # ty check

Every command returns a ``Result`` with the exit code and the output instead of raising,
so a UI can show what happened.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import site
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union

PathLike = Union[str, Path]

PYPROJECT = "pyproject.toml"
DEFAULT_UI = "ui"
DEFAULT_MAIN = "main"
PACKAGE = "pyzed-ui"
DEV_TOOLS = ("ruff", "ty")
GITIGNORE = """\
# Python
__pycache__/
*.py[oc]
build/
dist/
wheels/
*.egg-info

# Virtual environments
.venv

# Pyzed builds
*.spec
"""


# -- tools --------------------------------------------------------------------------


@dataclass
class Result:
    """What a command printed and how it ended."""

    args: List[str]
    code: int
    output: str = ""

    @property
    def ok(self) -> bool:
        """Whether the command exited with code 0."""
        return self.code == 0

    def __bool__(self) -> bool:
        return self.ok

    @property
    def command(self) -> str:
        """The command line as text, with the program shown by its file name only."""
        return " ".join(Path(self.args[0]).name if i == 0 else a for i, a in enumerate(self.args)) if self.args else ""


@dataclass
class Tool:
    """A command line tool the project uses (``uv``, ``ruff``, ``ty``, ``git``)."""

    name: str
    path: Optional[str] = None
    version: Optional[str] = None

    @property
    def available(self) -> bool:
        """Whether the tool was found (``path`` is set)."""
        return self.path is not None


def _bundled(name: str) -> Optional[str]:
    """A tool shipped next to the executable (the compiled Pyzed Design bundles ``uv``)."""
    exe = name + (".exe" if os.name == "nt" else "")
    roots = [Path(getattr(sys, "_MEIPASS", "")), Path(sys.executable).parent]
    for root in roots:
        for candidate in (root / exe, root / "bin" / exe):
            if str(root) and candidate.is_file():
                return str(candidate)
    return None


def find_uv() -> Optional[str]:
    """The ``uv`` executable: on ``PATH``, from the ``uv`` Python package or bundled."""
    found = shutil.which("uv")
    if found:
        return found
    try:
        from uv import find_uv_bin  # type: ignore[import-not-found]

        return find_uv_bin()
    except Exception:  # noqa: BLE001 - not installed, or installed without its binary
        pass
    return _bundled("uv")


def _clean_env() -> Dict[str, str]:
    env = dict(os.environ)
    # uv warns when an unrelated environment is active; the project's own .venv is used anyway.
    env.pop("VIRTUAL_ENV", None)
    env.setdefault("UV_NO_PROGRESS", "1")
    env.setdefault("NO_COLOR", "1")
    return env


#: Keeps console programs (uv, git, ruff...) from opening a console window on Windows: the windowed
#: Pyzed Design has no console of its own to share with them.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def terminate(process: "subprocess.Popen[bytes]") -> None:
    """Stops ``process`` and the processes it started (stopping ``uv run`` alone leaves its Python running)."""
    if process.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True,  # noqa: S603, S607
                       creationflags=NO_WINDOW, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            process.terminate()
    if process.poll() is None:
        process.terminate()


def execute(args: Sequence[str], cwd: Optional[PathLike] = None, *, timeout: Optional[float] = None) -> Result:
    """Runs ``args`` and returns its exit code and combined output (never raises)."""
    args = [str(a) for a in args]
    try:
        done = subprocess.run(args, cwd=str(cwd) if cwd else None, env=_clean_env(), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout, check=False, creationflags=NO_WINDOW)
    except FileNotFoundError:
        return Result(args, 127, f"{args[0]}: command not found")
    except subprocess.TimeoutExpired as err:
        return Result(args, 124, f"{err.output or ''}timed out after {timeout:g}s")
    except OSError as err:
        return Result(args, 126, str(err))
    return Result(args, done.returncode, done.stdout.strip())


def _version(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    result = execute([path, "--version"], timeout=10)
    match = re.search(r"\d+\.\d+(?:\.\d+)?\S*", result.output) if result.ok else None
    return match.group(0) if match else None


def tools(project: Optional["Project"] = None) -> Dict[str, Tool]:
    """``uv``, ``ruff``, ``ty`` and ``git`` with their paths and versions (``path=None`` if missing)."""
    found = {"uv": find_uv(), "git": shutil.which("git")}
    for name in DEV_TOOLS:
        found[name] = project.tool_path(name) if project else shutil.which(name)
    return {name: Tool(name, path, _version(path)) for name, path in found.items()}


def _uv() -> str:
    uv = find_uv()
    if uv is None:
        raise FileNotFoundError("uv is not installed: https://docs.astral.sh/uv/getting-started/installation/")
    return uv


# -- pyproject.toml -------------------------------------------------------------------


def _loads_toml(text: str) -> Dict[str, Any]:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:  # Python < 3.11
        try:
            import tomli as tomllib  # type: ignore[import-not-found, no-redef]
        except ModuleNotFoundError:
            return _mini_toml(text)
    return tomllib.loads(text)


def _mini_toml(text: str) -> Dict[str, Any]:
    """Just enough TOML for pyproject.toml when ``tomllib`` is unavailable: tables, strings, arrays, bools."""
    data: Dict[str, Any] = {}
    table = data
    pending: Optional[str] = None
    buffer = ""
    for raw in text.splitlines():
        line = re.sub(r'\s#[^"]*$', "", raw).strip()
        if pending is not None:
            buffer += " " + line
            if buffer.count("[") <= buffer.count("]"):
                table[pending] = _mini_value(buffer)
                pending = None
            continue
        if not line or line.startswith("#"):
            continue
        header = re.match(r"^\[([^\[\]]+)\]$", line)
        if header:
            table = data
            for part in (p.strip().strip('"') for p in header.group(1).split(".")):
                table = table.setdefault(part, {})
            continue
        if line.startswith("[["):
            table = {}  # arrays of tables are not needed; skip their keys
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key, value = key.strip().strip('"'), value.strip()
        if value.startswith("[") and value.count("[") > value.count("]"):
            pending, buffer = key, value
        else:
            table[key] = _mini_value(value)
    return data


def _mini_value(value: str) -> Any:
    if value in ("true", "false"):
        return value == "true"
    try:
        return json.loads(re.sub(r",\s*]", "]", value.replace("'", '"')))
    except ValueError:
        return value  # inline tables and other syntax: kept as text


def normalize(name: str) -> str:
    """The canonical form of a package name (PEP 503): ``Foo_Bar`` -> ``foo-bar``."""
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_name(spec: str) -> str:
    """``"httpx[http2]>=0.27"`` -> ``"httpx"``."""
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    return match.group(1) if match else spec.strip()


def module_name(name: str) -> str:
    """The import name uv gives a project's package: ``my-app`` -> ``my_app``."""
    return re.sub(r"[^0-9a-zA-Z_]", "_", name).lower()


@dataclass
class Dependency:
    """A requirement in ``pyproject.toml`` and the version locked for it in ``uv.lock``."""

    name: str
    spec: str
    group: str = "main"  # "main" for [project.dependencies], else the dependency group ("dev", ...)
    locked: Optional[str] = None
    latest: Optional[str] = None  # filled by ``Project.outdated()``

    @property
    def dev(self) -> bool:
        """Whether the dependency belongs to a dependency group rather than the main dependencies."""
        return self.group != "main"

    @property
    def outdated(self) -> bool:
        """Whether a newer release than the locked version is known."""
        return bool(self.latest and self.locked and self.latest != self.locked)


# -- projects ---------------------------------------------------------------------------


@dataclass
class Project:
    """A folder with a ``pyproject.toml``; ``[tool.pyzed]`` says where the UI lives."""

    root: Path
    data: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def open(cls, path: PathLike) -> "Project":
        """The project at ``path`` (a folder or its ``pyproject.toml``); raises if there is none."""
        path = Path(path).expanduser().resolve()
        if path.name == PYPROJECT:
            path = path.parent
        file = path / PYPROJECT
        if not file.is_file():
            raise FileNotFoundError(f"{path} has no {PYPROJECT}; create one with `pyzed init` or `uv init`")
        return cls(path, _loads_toml(file.read_text(encoding="utf-8")))

    @classmethod
    def find(cls, start: Optional[PathLike] = None) -> Optional["Project"]:
        """The nearest project containing ``start`` (default: the current folder), or ``None``.

        A ``pyproject.toml`` with a ``[tool.pyzed]`` table wins over an outer one; when
        none has it, the nearest ``pyproject.toml`` is used.
        """
        here = Path(start or Path.cwd()).expanduser().resolve()
        if here.is_file():
            here = here.parent
        nearest: Optional[Project] = None
        for folder in (here, *here.parents):
            if (folder / PYPROJECT).is_file():
                try:
                    found = cls.open(folder)
                except (OSError, ValueError):
                    continue
                if found.is_pyzed:
                    return found
                nearest = nearest or found
        return nearest

    def reload(self) -> "Project":
        """Re-reads ``pyproject.toml`` (after ``uv add`` and friends changed it)."""
        file = self.root / PYPROJECT
        self.data = _loads_toml(file.read_text(encoding="utf-8")) if file.is_file() else {}
        return self

    # -- settings ------------------------------------------------------------------------
    @property
    def config(self) -> Dict[str, Any]:
        """The ``[tool.pyzed]`` table."""
        return self.data.get("tool", {}).get("pyzed", {})

    @property
    def is_pyzed(self) -> bool:
        """Whether ``pyproject.toml`` has a ``[tool.pyzed]`` table."""
        return "pyzed" in self.data.get("tool", {})

    @property
    def name(self) -> str:
        """The project name from ``pyproject.toml``, or the folder's name."""
        return str(self.data.get("project", {}).get("name") or self.root.name)

    @property
    def version(self) -> str:
        """The project version from ``pyproject.toml`` (``"0.0.0"`` if missing)."""
        return str(self.data.get("project", {}).get("version") or "0.0.0")

    @property
    def ui_dir(self) -> Path:
        """The folder that holds the forms (``ui`` in ``[tool.pyzed]``, by default ``ui/``)."""
        return self.root / str(self.config.get("ui", DEFAULT_UI))

    @property
    def main_form(self) -> Path:
        """The path of the main ``.pzform`` file (``main`` in ``[tool.pyzed]``)."""
        main = str(self.config.get("main", f"{DEFAULT_UI}/{DEFAULT_MAIN}.pzform"))
        return self.root / main

    @property
    def script(self) -> Optional[Path]:
        """The script Run starts when no form is open (``script`` in ``[tool.pyzed]``), if the project has one."""
        script = self.config.get("script")
        return self.root / str(script) if script else None

    @property
    def src_dir(self) -> Optional[Path]:
        """The ``src/`` folder, or ``None`` for a flat layout."""
        src = self.root / "src"
        return src if src.is_dir() else None

    def forms(self) -> List[Path]:
        """The ``.pzform`` files of the UI folder, sorted."""
        return sorted(self.ui_dir.rglob("*.pzform")) if self.ui_dir.is_dir() else []

    def new_form(self, name: str, *, title: Optional[str] = None, width: float = 480, height: float = 320) -> Path:
        """Creates ``ui/<name>.pzform`` and its handlers module; returns the form path."""
        from .designer import new_form

        return new_form(self.ui_dir / name, title=title, width=width, height=height)

    # -- environment -----------------------------------------------------------------------
    @property
    def venv(self) -> Path:
        """The project's virtual environment (``UV_PROJECT_ENVIRONMENT`` or ``.venv``)."""
        return Path(os.environ.get("UV_PROJECT_ENVIRONMENT") or self.root / ".venv")

    def python_executable(self) -> Optional[Path]:
        """The project's interpreter (``.venv``), or ``None`` before the first ``uv sync``."""
        exe = self.venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        return exe if exe.exists() else None

    def tool_path(self, name: str) -> Optional[str]:
        """``ruff``/``ty`` installed in the project's ``.venv``, else on ``PATH``."""
        exe = self.venv / ("Scripts" if os.name == "nt" else "bin") / (name + (".exe" if os.name == "nt" else ""))
        return str(exe) if exe.is_file() else shutil.which(name)

    def site_packages(self) -> Optional[Path]:
        """``.venv``'s site-packages folder, if it exists."""
        if os.name == "nt":
            folder = self.venv / "Lib" / "site-packages"
            return folder if folder.is_dir() else None
        found = sorted(self.venv.glob("lib/python*/site-packages"))
        return found[-1] if found else None

    def venv_python_version(self) -> Optional[str]:
        """``"3.12"`` read from ``.venv/pyvenv.cfg``."""
        cfg = self.venv / "pyvenv.cfg"
        if not cfg.is_file():
            return None
        match = re.search(r"^version(?:_info)?\s*=\s*(\d+\.\d+)", cfg.read_text(encoding="utf-8"), re.M)
        return match.group(1) if match else None

    @property
    def uses_own_venv(self) -> bool:
        """Whether this interpreter *is* the project's ``.venv`` (e.g. under ``uv run``)."""
        try:
            return Path(sys.prefix).resolve() == self.venv.resolve()
        except OSError:
            return False

    @property
    def can_run_in_process(self) -> bool:
        """Whether forms can run inside this process with all the project's dependencies.

        True under ``uv run`` (or with the ``.venv`` activated). Otherwise (a compiled Pyzed
        Design, another environment) forms run through ``uv run`` in their own process.
        """
        return self.uses_own_venv and not getattr(sys, "frozen", False)

    def paths(self) -> List[Path]:
        """Folders that make the project importable from the UI: ``ui/``, ``src/`` and the root."""
        return [p for p in (self.ui_dir, self.src_dir, self.root) if p is not None and p.is_dir()]

    def activate(self) -> List[str]:
        """Makes the project importable from this process; returns the entries it added to ``sys.path``.

        Adds ``ui/``, ``src/`` and the project root, and, when it was made for this same
        Python version, the ``.venv`` site-packages (with its ``.pth`` files, so editable
        installs such as the project's own package resolve too).
        """
        added: List[str] = []
        for folder in reversed(self.paths()):
            entry = str(folder)
            if entry not in sys.path:
                sys.path.insert(0, entry)
                added.append(entry)
        packages = self.site_packages()
        same_python = self.venv_python_version() == f"{sys.version_info[0]}.{sys.version_info[1]}"
        if packages is not None and same_python and str(packages) not in sys.path and not getattr(sys, "frozen", False):
            before = list(sys.path)
            site.addsitedir(str(packages))
            added.extend(p for p in sys.path if p not in before)
        return added

    # -- dependencies --------------------------------------------------------------------------
    def locked_versions(self) -> Dict[str, str]:
        """``{normalized name: version}`` from ``uv.lock``."""
        lock = self.root / "uv.lock"
        if not lock.is_file():
            return {}
        text = lock.read_text(encoding="utf-8")
        found = re.findall(r'^\[\[package\]\]\s*\nname = "([^"]+)"\s*\nversion = "([^"]+)"', text, re.M)
        return {normalize(n): v for n, v in found}

    def dependencies(self) -> List[Dependency]:
        """Direct dependencies: ``[project.dependencies]`` then each ``[dependency-groups]`` table."""
        locked = self.locked_versions()
        groups: List[tuple] = [("main", self.data.get("project", {}).get("dependencies", []))]
        groups += list(self.data.get("dependency-groups", {}).items())
        legacy = self.data.get("tool", {}).get("uv", {}).get("dev-dependencies", [])
        if legacy:
            groups.append(("dev", legacy))
        deps: List[Dependency] = []
        for group, specs in groups:
            for spec in specs:
                if not isinstance(spec, str):
                    continue  # {include-group = "..."}
                name = requirement_name(spec)
                deps.append(Dependency(name, spec, group, locked.get(normalize(name))))
        return deps

    def outdated(self) -> List[Dependency]:
        """Direct dependencies with a newer release (asks the package index; needs network)."""
        result = self.uv("tree", "--outdated", "--depth", "1", "--frozen")
        latest = {normalize(m.group(1)): m.group(2)
                  for m in re.finditer(r"([A-Za-z0-9][A-Za-z0-9._-]*) v\S+.*\(latest: v([^)\s]+)\)", result.output)}
        deps = self.dependencies()
        for dep in deps:
            dep.latest = latest.get(normalize(dep.name), dep.locked)
        return [d for d in deps if d.outdated]

    def uv(self, *args: str, timeout: Optional[float] = None) -> Result:
        """Runs ``uv <args>`` in the project folder."""
        try:
            return execute([_uv(), *args], self.root, timeout=timeout)
        except FileNotFoundError as err:
            return Result(["uv", *args], 127, str(err))

    def _changed(self, result: Result) -> Result:
        self.reload()
        return result

    @staticmethod
    def _group_args(dev: bool, group: Optional[str]) -> List[str]:
        if group:
            return ["--group", group]
        return ["--dev"] if dev else []

    def add(self, *specs: str, dev: bool = False, group: Optional[str] = None, editable: bool = False,
            sync: bool = True) -> Result:
        """``uv add``: adds packages, or changes the version of one already there (``"httpx==0.27"``).

        ``editable=True`` with a path (``"../billing"``) links code that lives outside the project.
        """
        extra = ([] if sync else ["--frozen"]) + (["--editable"] if editable else [])
        return self._changed(self.uv("add", *self._group_args(dev, group), *extra, *specs))

    change = add

    def remove(self, *names: str, dev: bool = False, group: Optional[str] = None) -> Result:
        """``uv remove``; with no group given, looks up which group each package is in."""
        if not dev and group is None:
            where = {normalize(d.name): d.group for d in self.dependencies()}
            groups = {where.get(normalize(requirement_name(n)), "main") for n in names}
            if len(groups) == 1 and groups != {"main"}:
                found = groups.pop()
                dev, group = found == "dev", None if found == "dev" else found
        return self._changed(self.uv("remove", *self._group_args(dev, group), *names))

    def upgrade(self, *names: str) -> Result:
        """Upgrades ``names`` (every package when empty) within their constraints, then syncs."""
        args = [a for n in names for a in ("--upgrade-package", requirement_name(n))] or ["--upgrade"]
        result = self.uv("lock", *args)
        if result.ok:
            synced = self.sync()
            result = Result(result.args, synced.code, "\n".join(x for x in (result.output, synced.output) if x))
        return self._changed(result)

    def sync(self) -> Result:
        """``uv sync``: creates ``.venv`` and installs exactly what ``uv.lock`` says."""
        return self.uv("sync")

    def lock(self) -> Result:
        """Runs ``uv lock`` to update ``uv.lock``."""
        return self.uv("lock")

    # -- quality -----------------------------------------------------------------------------
    def _run_tool(self, name: str, *args: str) -> Result:
        path = self.tool_path(name)
        if path is not None:
            return execute([path, *args], self.root)
        return self.uv("tool", "run", name, *args)  # not installed: uv fetches it once and caches it

    def check(self, *paths: str, fix: bool = False) -> Result:
        """``ruff check`` (lint)."""
        return self._run_tool("ruff", "check", *(["--fix"] if fix else []), *paths)

    def format(self, *paths: str) -> Result:
        """``ruff format``."""
        return self._run_tool("ruff", "format", *paths)

    def typecheck(self, *paths: str) -> Result:
        """``ty check`` with the project's ``.venv``."""
        python = self.python_executable()
        return self._run_tool("ty", "check", *(["--python", str(python)] if python else []), *paths)

    # -- git -----------------------------------------------------------------------------------
    @property
    def is_git(self) -> bool:
        """Whether the project is inside a git repository (here or in a parent folder)."""
        return any((folder / ".git").exists() for folder in (self.root, *self.root.parents))

    def git(self, *args: str) -> Result:
        """Runs ``git`` with ``args`` in the project folder (exit code 127 if git is not installed)."""
        git = shutil.which("git")
        if git is None:
            return Result(["git", *args], 127, "git is not installed")
        return execute([git, *args], self.root)

    def git_init(self, *, commit: bool = False, message: str = "Initial commit") -> Result:
        """Creates a git repository (like Zed's "Create repository"), with a ``.gitignore``.

        ``commit=True`` also commits every file; it fails, with git's message, if
        ``user.name``/``user.email`` are not configured.
        """
        ignore = self.root / ".gitignore"
        if not ignore.exists():
            ignore.write_text(GITIGNORE, encoding="utf-8")
        result = Result(["git", "init"], 0, "Already a git repository") if self.is_git else self.git("init")
        if result.ok and commit:
            added = self.git("add", "-A")
            result = added if not added.ok else self.git("commit", "-m", message)
        return result

    def git_branch(self) -> Optional[str]:
        """Returns the current git branch, or ``None`` outside a repository or on a detached HEAD."""
        result = self.git("branch", "--show-current") if self.is_git else None
        return result.output or None if result and result.ok else None

    # -- running ---------------------------------------------------------------------------------
    def run_args(self, form: Optional[PathLike] = None, *, reload: bool = False) -> List[str]:
        """The command that runs ``form`` (default: the main form) with the project's environment."""
        form = Path(form) if form else self.main_form
        args = ["run", "pyzed", "run", str(form)]
        if reload:
            args.append("--reload")
        return [_uv(), *args]

    def spawn(self, form: Optional[PathLike] = None, *, reload: bool = False,
              capture: bool = False, env: Optional[Dict[str, str]] = None) -> "subprocess.Popen[bytes]":
        """Starts the form in its own process with ``uv run`` (returns immediately).

        With ``capture`` its output (stdout and stderr together) is readable from ``.stdout``; ``env`` adds
        environment variables.
        """
        return self._popen(self.run_args(form, reload=reload), capture, env)

    def spawn_script(self, script: Optional[PathLike] = None, *, capture: bool = False,
                     env: Optional[Dict[str, str]] = None) -> "subprocess.Popen[bytes]":
        """Starts ``script`` (default: the project's ``script``) with ``uv run`` (returns immediately)."""
        script = Path(script) if script else self.script
        if script is None:
            raise FileNotFoundError("The project has no script in [tool.pyzed]")
        return self._popen([_uv(), "run", str(script)], capture, env)

    def _popen(self, args: List[str], capture: bool, env: Optional[Dict[str, str]]) -> "subprocess.Popen[bytes]":
        pipes = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT} if capture else {}
        env = {**_clean_env(), **(env or {})}
        if capture:
            env["PYTHONUNBUFFERED"] = "1"  # lines reach the designer's console as they are printed
        # No console window on Windows (the output goes to the designer), and a process group of its own
        # elsewhere, so ``terminate`` stops uv and the Python it starts together.
        return subprocess.Popen(args, cwd=str(self.root), env=env, creationflags=NO_WINDOW,
                                start_new_session=sys.platform != "win32", **pipes)


# -- creating projects --------------------------------------------------------------------------

FORM_HANDLERS = '''"""Event handlers for the Main form.

Each function receives the running ``form`` (controls are attributes: ``form.greet.text``)
and an ``event`` with ``event.sender``, ``event.name`` and ``event.value``.

The backend lives outside this folder, in ``src/{module}``; import it like any package.
"""

from {module} import greeting


def greet_click(form, event):
    """Shows the greeting computed by the backend."""
    form.message.text = greeting(form.name_input.text or "world")
'''

BACKEND = '''"""{name}: the application logic, independent from the UI in ``ui/``."""


def greeting(name: str) -> str:
    """The text shown when the Greet button is pressed."""
    return f"Hello, {{name}}!"


def main() -> None:
    """Opens the main window (``uv run {name}``)."""
    from pyzed import project

    project.run()
'''


def _write_main_form(project: Project, title: str) -> None:
    from .designer import Form, component, save

    form = Form(name="Main", title=title, width=420, height=200)
    controls = [("label", "prompt", 24, 24, None, {"text": "Your name"}),
                ("input", "name_input", 24, 48, 260, {"placeholder": "world"}),
                ("button", "greet", 296, 48, 100, {"text": "Greet", "variant": "solid"}),
                ("label", "message", 24, 104, 372, {"text": ""})]
    for type_, name, x, y, width, props in controls:
        control = component(type_).create(name, x, y, width)
        control.props.update(props)
        form.add(control)
    form["greet"].events["click"] = "greet_click"
    save(form, project.main_form)


def _ensure_config(project: Project, ui: str) -> None:
    file = project.root / PYPROJECT
    text = file.read_text(encoding="utf-8")
    if not re.search(r"^\[tool\.pyzed\]", text, re.M):
        block = f'\n[tool.pyzed]\nui = "{ui}"\nmain = "{ui}/{DEFAULT_MAIN}.pzform"\n'
        file.write_text(text.rstrip() + "\n" + block, encoding="utf-8")
    project.reload()


def init(path: PathLike = ".", *, name: Optional[str] = None, ui: str = DEFAULT_UI, package: bool = True,
         git: bool = True, python: Optional[str] = None, sync: bool = True,
         dev_tools: Sequence[str] = DEV_TOOLS) -> Project:
    """Creates a Pyzed project at ``path``, or adds Pyzed to the ``uv`` project already there.

    - No ``pyproject.toml`` yet: runs ``uv init`` (``--package`` puts the backend in
      ``src/<name>`` so the UI can import it from anywhere).
    - Adds ``[tool.pyzed]``, the ``ui/`` folder with a starter form, ``pyzed-ui`` as a
      dependency and ``ruff``/``ty`` as dev dependencies (``sync=False`` only edits
      ``pyproject.toml``, without resolving or installing anything).
    - ``git=True`` creates a git repository unless the folder is already inside one.

    Raises ``RuntimeError`` with uv's message when ``uv init`` fails.
    """
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    fresh = not (root / PYPROJECT).exists()
    if fresh:
        args = ["init", "--name", name or root.name, "--vcs", "git" if git else "none"]
        args.append("--package" if package else "--app")
        if python:
            args += ["--python", python]
        result = execute([_uv(), *args, str(root)], root)
        if not result.ok:
            raise RuntimeError(result.output or "uv init failed")
    project = Project.open(root)
    _ensure_config(project, ui)
    module = module_name(project.name)
    if fresh and package and project.src_dir is not None:
        init_py = project.src_dir / module / "__init__.py"
        if init_py.parent.is_dir():
            init_py.write_text(BACKEND.format(name=project.name), encoding="utf-8")
    elif fresh and not package:
        (root / "main.py").write_text(
            '"""Opens the main window: `uv run main.py`."""\n\nfrom pyzed import project\n\n'
            'if __name__ == "__main__":\n    project.run()\n', encoding="utf-8")
    project.ui_dir.mkdir(parents=True, exist_ok=True)
    if not project.main_form.exists():
        title = re.sub(r"[-_]+", " ", project.name).strip().title() or "My App"
        _write_main_form(project, title)
        handlers = project.main_form.with_suffix(".py")
        backend_ready = fresh and package
        handlers.write_text(FORM_HANDLERS.format(module=module) if backend_ready else
                            FORM_HANDLERS.format(module=module).replace(
                                f"from {module} import greeting\n",
                                "\ndef greeting(name):\n    return f\"Hello, {name}!\"\n"), encoding="utf-8")
    deps = {normalize(d.name) for d in project.dependencies()}
    if normalize(PACKAGE) not in deps:
        project.add(PACKAGE, sync=sync)
    missing = [t for t in dev_tools if normalize(t) not in deps]
    if missing:
        project.add(*missing, dev=True, sync=sync)
    if git and not project.is_git:
        project.git_init()
    return project.reload()


def run(form: Optional[PathLike] = None, *, reload: Optional[bool] = None) -> None:
    """Runs a form of the current project (default: its main form) with the project importable."""
    from . import designer

    project = Project.find(form or None)
    if project is None:
        raise FileNotFoundError("not inside a Pyzed project (no pyproject.toml found)")
    project.activate()
    designer.run(Path(form) if form else project.main_form, reload=reload)


def find(start: Optional[PathLike] = None) -> Optional[Project]:
    """The project containing ``start`` (a folder or file; default: the current folder), or ``None``."""
    return Project.find(start)


def activate_for(path: Optional[PathLike] = None) -> Optional[Project]:
    """Activates the project containing ``path`` (if any) and returns it."""
    project = Project.find(path)
    if project is not None:
        project.activate()
    return project


# -- recent projects (shown by Pyzed Design) ------------------------------------------------------


def config_dir() -> Path:
    """Where Pyzed keeps per-user settings."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "pyzed"


def recent_projects(limit: int = 10) -> List[Path]:
    """Projects opened lately, newest first (those that no longer exist are skipped)."""
    try:
        entries = json.loads((config_dir() / "recent.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [Path(p) for p in entries if isinstance(p, str) and (Path(p) / PYPROJECT).is_file()][:limit]


def remember(project: Project) -> None:
    """Puts ``project`` first in ``recent_projects()``."""
    entries = [str(project.root)] + [str(p) for p in recent_projects(20) if p != project.root]
    try:
        config_dir().mkdir(parents=True, exist_ok=True)
        (config_dir() / "recent.json").write_text(json.dumps(entries[:20], indent=2), encoding="utf-8")
    except OSError:
        pass


def iter_python_files(folder: Path) -> Iterator[Path]:
    """Yields the ``.py`` files under ``folder``, sorted, skipping venvs, caches, ``.git`` and builds."""
    skip = {".venv", "venv", "__pycache__", ".git", "build", "dist"}
    for path in sorted(folder.rglob("*.py")):
        if not skip.intersection(path.relative_to(folder).parts):
            yield path
