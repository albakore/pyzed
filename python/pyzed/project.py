"""Pyzed projects: a standard ``uv`` project with the UI in its own folder.

    my-app/
    ├── pyproject.toml        # uv project, plus a [tool.pyzed] table
    ├── AGENTS.md             # how AI agents should build, design and check it
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
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Union

from . import package_managers as _package_managers

PathLike = Union[str, Path]

PYPROJECT = "pyproject.toml"
#: Folders ``startup_choices`` does not look into.
_SKIP_DIRS = {"venv", "node_modules", "target", "__pycache__", "dist", "build", "tests"}
DEFAULT_UI = "ui"
DEFAULT_MAIN = "main"
PACKAGE = "pyzed-ui"
DEV_TOOLS = ("ruff", "ty")
#: Seconds a git command may take before it is given up (so a stuck one cannot hang the editor).
GIT_TIMEOUT = 60
#: uv only installs ``pyzed-ui`` from the wheels the release pipeline builds: it never compiles the Rust
#: core on the user's machine, and says so when a platform has no wheel instead of building for minutes.
PREBUILT = f'no-build-package = ["{PACKAGE}"]\n'
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
    #: Where the uv in use comes from: "bundled", "system" or "custom" (see ``package_managers``).
    source: Optional[str] = None

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


def _installed_uv() -> Optional[str]:
    """``uv`` where its installer puts it (``~/.local/bin``), which may not be on this process's ``PATH`` yet."""
    exe = "uv" + (".exe" if os.name == "nt" else "")
    for folder in (Path.home() / ".local" / "bin", Path.home() / ".cargo" / "bin"):
        if (folder / exe).is_file():
            return str(folder / exe)
    return None


def find_uv() -> Optional[str]:
    """The ``uv`` executable chosen in ``package_managers`` (by default this computer's, on ``PATH`` or where its
    installer puts it, else the one included with Pyzed Design or its Python)."""
    return _package_managers.find("uv")


#: uv's official installers (they put ``uv`` in ``~/.local/bin``).
UV_INSTALL = {
    "posix": "curl -LsSf https://astral.sh/uv/install.sh | sh || wget -qO- https://astral.sh/uv/install.sh | sh",
    "nt": "irm https://astral.sh/uv/install.ps1 | iex",
}


def install_uv() -> Result:
    """Installs ``uv`` with its official installer (needs network); a ``Result`` like every command here."""
    if os.name == "nt":
        return execute(["powershell", "-NoProfile", "-ExecutionPolicy", "ByPass", "-Command", UV_INSTALL["nt"]],
                       timeout=300)
    return execute(["sh", "-c", UV_INSTALL["posix"]], timeout=300)


#: Windows' ``ERROR_UNTRUSTED_MOUNT_POINT``. Recent Windows 11 builds refuse to follow some junctions, such as the
#: one uv makes for each Python minor version in ``%APPDATA%\uv\python`` (``cpython-3.12-windows-x86_64-none``) and
#: the ``python3.13.exe`` uv puts in ``~/.local/bin``, which runs the Python behind that junction: then every uv
#: command that needs one of them fails with this error.
UNTRUSTED_MOUNT = "os error 448"

#: The junction uv makes for a Python minor version (``cpython-3.13-windows-x86_64-none``), next to the real folder
#: of its latest patch version (``cpython-3.13.5-windows-x86_64-none``).
_MINOR_LINK = re.compile(r"cpython-\d+\.\d+-", re.IGNORECASE)


def python_install_dir() -> Path:
    """Where uv keeps its Pythons for Pyzed once uv's own folder failed with ``UNTRUSTED_MOUNT`` (Windows only):
    a folder of this app, without uv's minor version junctions (see ``execute_uv``). It is used from then on while
    it exists, and then uv uses only the Pythons in it."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "pyzed" / "python"


def _clean_env() -> Dict[str, str]:
    env = dict(os.environ)
    # uv warns when an unrelated environment is active; the project's own .venv is used anyway.
    env.pop("VIRTUAL_ENV", None)
    env.setdefault("UV_NO_PROGRESS", "1")
    env.setdefault("NO_COLOR", "1")
    if sys.platform == "win32" and python_install_dir().is_dir():
        env["UV_PYTHON_INSTALL_DIR"] = str(python_install_dir())
        # only those Pythons: the ones on PATH may be uv's ``python3.13.exe`` of ``~/.local/bin``, which still
        # goes through the junction of the old folder (and a broken first one on PATH stops uv's search)
        env.setdefault("UV_PYTHON_PREFERENCE", "only-managed")
    env.update(_package_managers.environment())  # the package index, pre-releases... of the settings
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
        done = subprocess.run(args, cwd=str(cwd) if cwd else None, env=_clean_env(), stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, check=False, creationflags=NO_WINDOW)
    except FileNotFoundError:
        return Result(args, 127, f"{args[0]}: command not found")
    except subprocess.TimeoutExpired as err:
        return Result(args, 124, f"{err.output or ''}timed out after {timeout:g}s")
    except OSError as err:
        return Result(args, 126, str(err))
    return Result(args, done.returncode, done.stdout.strip())


def _is_link(path: Path) -> bool:
    """Whether ``path`` is a symbolic link or a junction (``os.path.isjunction`` is Python 3.12+)."""
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)  # REPARSE_POINT


def _remove_minor_links() -> bool:
    """Removes the minor version junctions uv made in ``python_install_dir()`` (the Pythons stay): without them
    uv runs each Python from its real folder. uv only makes them again when it downloads a Python."""
    removed = False
    for link in python_install_dir().glob("cpython-*"):
        if _MINOR_LINK.match(link.name) and _is_link(link):
            try:
                os.unlink(link)
            except OSError:
                try:
                    os.rmdir(link)  # a junction is removed like an empty folder; the Python it points to stays
                except OSError:
                    continue
            removed = True
    return removed


def _stale_venv(venv: Path) -> bool:
    """Whether ``venv`` was made with a uv Python Windows won't open: one outside ``python_install_dir()`` (the
    folder of uv or the ``python3.13.exe`` of ``~/.local/bin``) or one reached through a minor version junction."""
    try:
        cfg = (venv / "pyvenv.cfg").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    found = re.search(r"^home\s*=\s*(.+?)\s*$", cfg, re.M)
    if not found:
        return False
    def parts(path: str) -> List[str]:
        return [part.lower() for part in re.split(r"[\\/]+", path) if part]

    home = parts(found.group(1))
    if home[-2:] == [".local", "bin"]:
        return True
    if not any(part.startswith("cpython-") for part in home):
        return False
    pythons = parts(str(python_install_dir()))
    return home[:len(pythons)] != pythons or any(_MINOR_LINK.match(part) for part in home)


def _repair_pythons(venv: Optional[Path]) -> bool:
    """What ``execute_uv`` changes when uv can't open a Python (``UNTRUSTED_MOUNT``); whether anything changed."""
    changed = False
    if not python_install_dir().is_dir():
        try:
            python_install_dir().mkdir(parents=True)
            changed = True
        except OSError:
            return False
    changed = _remove_minor_links() or changed
    if venv is not None and _stale_venv(venv):
        shutil.rmtree(venv, ignore_errors=True)  # uv sync makes it again with a Python Windows opens
        changed = not venv.exists() or changed
    return changed


#: Added to uv's output when Pyzed could not get around ``UNTRUSTED_MOUNT``.
UNTRUSTED_MOUNT_HINT = ("Windows won't let uv open a Python through a folder link (os error 448). Pyzed keeps its "
                        "Pythons in {folder}: delete that folder and try again, or run "
                        "`uv python uninstall --all` in a terminal and remove the python*.exe of ~/.local/bin.")


def execute_uv(args: Sequence[str], cwd: Optional[PathLike] = None, *, timeout: Optional[float] = None,
               venv: Optional[Path] = None) -> Result:
    """Runs uv (``args[0]``) like ``execute``. On Windows, when uv can't open a Python (``UNTRUSTED_MOUNT``):
    uv's Pythons move to ``python_install_dir()`` and only those are used (not the ``python3.13.exe`` of
    ``~/.local/bin``), the minor version junctions uv makes there are removed, the project's ``venv`` made with an
    unreadable Python is made again, and the command runs again."""
    result = execute(args, cwd, timeout=timeout)
    if sys.platform != "win32":
        return result
    # a download makes the junction again: up to three tries (move, then remove the new junction)
    for _ in range(3):
        if UNTRUSTED_MOUNT not in result.output or not _repair_pythons(venv):
            break
        result = execute(args, cwd, timeout=timeout)
    if UNTRUSTED_MOUNT in result.output:
        hint = UNTRUSTED_MOUNT_HINT.format(folder=python_install_dir())
        return Result(result.args, result.code, f"{result.output}\n{hint}")
    return result


def _version(path: Optional[str]) -> Optional[str]:
    if path is None:
        return None
    result = execute([path, "--version"], timeout=10)
    match = re.search(r"\d+\.\d+(?:\.\d+)?\S*", result.output) if result.ok else None
    return match.group(0) if match else None


def tools(project: Optional["Project"] = None) -> Dict[str, Tool]:
    """``uv``, ``ruff``, ``ty`` and ``git`` with their paths and versions (``path=None`` if missing)."""
    if project is not None and project.environment.remote:  # the Linux tools of a WSL project
        remote: Dict[str, Tool] = {}
        for name in ("uv", "git", *DEV_TOOLS):
            path = project.tool_path(name) if name in DEV_TOOLS else None
            result = project._exec([path or name, "--version"], timeout=30)
            match = re.search(r"\d+\.\d+(?:\.\d+)?\S*", result.output) if result.ok else None
            remote[name] = Tool(name, (path or name) if result.ok else None, match.group(0) if match else None)
        return remote
    found = {"uv": find_uv(), "git": shutil.which("git")}
    for name in DEV_TOOLS:
        found[name] = project.tool_path(name) if project else shutil.which(name)
    out = {name: Tool(name, path, _version(path)) for name, path in found.items()}
    out["uv"].source = _package_managers.source_of(found["uv"])
    return out


def _uv() -> str:
    uv = find_uv()
    if uv is None:
        raise FileNotFoundError("uv is not installed: https://docs.astral.sh/uv/getting-started/installation/")
    return uv


# -- environments ----------------------------------------------------------------------

#: ``\\wsl$\Ubuntu\home\me`` or ``//wsl.localhost/Ubuntu/home/me``: a folder of a WSL distribution seen from Windows.
_WSL_UNC = re.compile(r"^(?:\\\\|//)wsl(?:\$|\.localhost)[\\/]+([^\\/]+)", re.IGNORECASE)
_SYSTEMS = {"win32": "Windows", "darwin": "macOS"}


@dataclass(frozen=True)
class Environment:
    """Where a project lives and its commands run, like the remote indicator of Zed's title bar.

    ``kind`` is ``"local"`` (this computer) or ``"wsl"`` (a Linux distribution of the Windows Subsystem
    for Linux, named ``name``, such as ``"Ubuntu"``).
    """

    kind: str
    name: str

    @property
    def is_wsl(self) -> bool:
        return self.kind == "wsl"

    @property
    def remote(self) -> bool:
        """Whether the project's commands must cross into WSL: a WSL project opened from Windows, like Zed's
        remote WSL projects. Its uv, git, ruff and ty are the Linux ones, run through ``wsl.exe``."""
        return self.is_wsl and sys.platform == "win32"

    def command(self, args: Sequence[str], cwd: PathLike, env: Optional[Dict[str, str]] = None) -> List[str]:
        """``args`` as they run in this environment from here: for a ``remote`` one, through
        ``wsl.exe -d <distro> --cd <folder>`` in a login shell (so ``~/.local/bin``, where uv installs, is on
        the ``PATH``), with paths of the distribution turned into Linux paths and ``env`` passed along."""
        if not self.remote:
            return [str(a) for a in args]
        extra = [f"{k}={v}" for k, v in (env or {}).items()]
        return ["wsl.exe", "-d", self.name, "--cd", linux_path(cwd), "--", "sh", "-lc", 'exec "$@"', "sh",
                *(["env", *extra] if extra else []), *(linux_path(a) for a in args)]

    def describe(self) -> str:
        """One sentence for people and agents about what working here means."""
        if self.remote:
            return (f"WSL ({self.name}), opened from Windows: the project's files and its uv, git, ruff and ty "
                    "are in Linux and run through wsl.exe, with Linux paths; its windows open as Windows windows.")
        if self.is_wsl:
            from . import _wsl_windows

            windows = ("as native Windows windows" if _wsl_windows.enabled() and sys.platform != "win32"
                       else "through WSLg")
            return (f"WSL ({self.name}): Linux running on Windows. Commands run in Linux with Linux paths; "
                    f"windows open {windows} and web pages in Windows' browser.")
        return f"This computer ({self.name})."


def linux_path(path: PathLike) -> str:
    """``\\\\wsl$\\Ubuntu\\home\\me`` as the distribution sees it (``/home/me``); anything else as it is."""
    text = str(path)
    found = _WSL_UNC.match(text)
    if not found:
        return text
    return "/" + "/".join(part for part in re.split(r"[\\/]+", text[found.end():]) if part)


def environment(path: Optional[PathLike] = None) -> Environment:
    """The environment of the folder ``path`` (default: where this process runs)."""
    if path is not None:
        found = _WSL_UNC.match(str(path))
        if found:
            return Environment("wsl", found.group(1))
    from ._platform import is_wsl

    if is_wsl():
        return Environment("wsl", os.environ.get("WSL_DISTRO_NAME") or "WSL")
    return Environment("local", _SYSTEMS.get(sys.platform, "Linux"))


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
    installed: Optional[str] = None  # the version in ``.venv`` (``None`` when it is not installed there)

    @property
    def dev(self) -> bool:
        """Whether the dependency belongs to a dependency group rather than the main dependencies."""
        return self.group != "main"

    @property
    def outdated(self) -> bool:
        """Whether a newer release than the locked version is known."""
        return bool(self.latest and self.locked and self.latest != self.locked)


@dataclass
class Problem:
    """Something in a project's dependencies that keeps it from running as this Pyzed expects.

    ``title`` and ``detail`` are English templates filled from ``values`` (a UI can translate them first);
    ``kind`` is ``"pyzed-missing"``, ``"pyzed-old"``, ``"no-environment"`` or ``"not-installed"``.
    """

    kind: str
    title: str
    detail: str = ""
    values: Dict[str, str] = field(default_factory=dict)

    @property
    def message(self) -> str:
        """``title`` and ``detail`` with their values, in English."""
        return " ".join(x.format(**self.values) for x in (self.title, self.detail) if x)


def editor_version() -> str:
    """The version of the running Pyzed (``"0+unknown"`` in a source tree without metadata)."""
    from . import __version__

    return str(__version__)


def is_older(version: str, than: str) -> bool:
    """Whether ``version`` is an older release than ``than`` (``False`` when either is unknown)."""
    from .updater import is_newer

    if not version or not than or than.startswith("0+"):
        return False
    return is_newer(than, version)


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
        """The script Run starts when no form is open (``script`` in ``[tool.pyzed]``), if the project has one.
        Without it, a project whose main form is gone (an app written in code) starts from its ``main.py``."""
        script = self.config.get("script")
        if script:
            return self.root / str(script)
        main = self.root / "main.py"
        return main if main.is_file() and not self.main_form.exists() else None

    @property
    def startup(self) -> Path:
        """The file the app starts from: the ``script`` when the project has one, else the main form."""
        return self.script if self.script is not None else self.main_form

    def set_startup(self, path: PathLike) -> None:
        """Makes ``path`` (a ``.pzform`` or ``.py`` file of the project) the file the app starts from: a form becomes
        ``main`` in ``[tool.pyzed]`` (and the ``script`` is dropped), a script becomes ``script``."""
        path = Path(path)
        rel = (path if not path.is_absolute() else path.resolve().relative_to(self.root.resolve())).as_posix()
        if path.suffix == ".py":
            _set_pyzed_keys(self, script=rel)
        elif path.suffix == ".pzform":
            _set_pyzed_keys(self, main=rel, script=None)
        else:
            raise ValueError(f"{path.name} is not a form (.pzform) or a script (.py)")

    def startup_choices(self, limit: int = 300) -> List[Path]:
        """The files the app can start from (``set_startup``): the project's forms and its Python scripts, the
        code of forms and components left out, sorted with the forms first."""
        forms: List[Path] = []
        scripts: List[Path] = []
        for folder, dirs, files in os.walk(self.root):
            dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS and not d.startswith("."))
            here = Path(folder)
            for name in sorted(files):
                path = here / name
                if name.endswith(".pzform"):
                    forms.append(path)
                elif name.endswith(".py") and not any(path.with_suffix(s).exists() for s in (".pzform", ".pzcomp")):
                    scripts.append(path)
            if len(forms) + len(scripts) >= limit:
                break
        return (forms + scripts)[:limit]

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

    @property
    def _windows_venv(self) -> bool:
        """Whether ``.venv`` has Windows' layout (``Scripts\\*.exe``); a WSL project's is a Linux one."""
        return os.name == "nt" and not self.environment.is_wsl

    def python_executable(self) -> Optional[Path]:
        """The project's interpreter (``.venv``), or ``None`` before the first ``uv sync``."""
        exe = self.venv / ("Scripts/python.exe" if self._windows_venv else "bin/python")
        return exe if exe.exists() else None

    def tool_path(self, name: str) -> Optional[str]:
        """``ruff``/``ty`` installed in the project's ``.venv``, else on ``PATH``."""
        windows = self._windows_venv
        exe = self.venv / ("Scripts" if windows else "bin") / (name + (".exe" if windows else ""))
        try:
            if exe.is_file():
                return str(exe)
        except OSError:  # a WSL project whose distro is stopped or missing: Windows can't reach \\wsl.localhost
            pass
        return None if self.environment.remote else shutil.which(name)

    def site_packages(self) -> Optional[Path]:
        """``.venv``'s site-packages folder, if it exists."""
        if self._windows_venv:
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
        """Whether this interpreter *is* the project's ``.venv`` (e.g. under ``uv run``), or the Windows
        environment Pyzed made for this WSL project when it started this process from WSL."""
        if self.served_from_wsl:
            return True
        try:
            return Path(sys.prefix).resolve() == self.venv.resolve()
        except OSError:
            return False

    @property
    def served_from_wsl(self) -> bool:
        """On Windows, whether this process was started from WSL for this WSL project (``pyzed design`` there):
        it runs in a Windows environment with the project's dependencies, so its forms and scripts run here, as
        Windows programs, instead of going back into WSL (see ``pyzed._wsl_windows``)."""
        served = os.environ.get("PYZED_WSL_PROJECT")
        env = self.environment
        return (bool(served) and env.remote and linux_path(self.root) == served
                and os.environ.get("PYZED_WSL_DISTRO", env.name).lower() == env.name.lower())

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
        packages = None if self.environment.remote else self.site_packages()  # Linux packages: not for Windows
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

    def installed_versions(self) -> Dict[str, str]:
        """``{normalized name: version}`` of the packages installed in ``.venv`` (read from its ``*.dist-info``
        folders; empty before the first ``uv sync``)."""
        packages = self.site_packages()
        try:
            entries = os.listdir(packages) if packages is not None else []
        except OSError:
            return {}
        found: Dict[str, str] = {}
        for entry in entries:
            if entry.endswith(".dist-info"):
                name, _, version = entry[:-len(".dist-info")].partition("-")
                if version:
                    found[normalize(name)] = version
        return found

    def stamp(self) -> tuple:
        """When ``pyproject.toml``, ``uv.lock`` and the packages of ``.venv`` last changed: compare two stamps
        to notice that something else (a terminal, the agent) added, removed or upgraded a package."""
        stamps = []
        for path in (self.root / PYPROJECT, self.root / "uv.lock", self.site_packages() or self.venv):
            try:
                stamps.append(path.stat().st_mtime_ns)
            except OSError:
                stamps.append(None)
        return tuple(stamps)

    def dependencies(self) -> List[Dependency]:
        """Direct dependencies: ``[project.dependencies]`` then each ``[dependency-groups]`` table."""
        locked = self.locked_versions()
        installed = self.installed_versions()
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
                key = normalize(name)
                deps.append(Dependency(name, spec, group, locked.get(key), installed=installed.get(key)))
        return deps

    @property
    def pyzed_from_source(self) -> bool:
        """Whether ``pyzed-ui`` comes from a local checkout (``[tool.uv.sources]``) rather than a release."""
        sources = self.data.get("tool", {}).get("uv", {}).get("sources", {})
        return isinstance(sources, dict) and any(normalize(k) == PACKAGE for k in sources)

    def problems(self, editor: Optional[str] = None) -> List[Problem]:
        """What keeps the project from running with the Pyzed ``editor`` (default: this one): ``pyzed-ui``
        missing or older than it, no ``.venv`` yet, or packages not installed as ``uv.lock`` says.

        Only reads files, so it is cheap enough for the UI thread; ``update_pyzed`` and ``sync`` fix them.
        """
        editor = editor or editor_version()
        deps = self.dependencies()
        found: List[Problem] = []
        pyzed = next((d for d in deps if normalize(d.name) == PACKAGE and d.group == "main"), None)
        if not self.pyzed_from_source:
            if pyzed is None and self.is_pyzed:
                found.append(Problem("pyzed-missing", "pyzed-ui is not a dependency of the project",
                                     "Its forms need it to run outside the editor."))
            elif pyzed is not None:
                have = pyzed.installed or pyzed.locked
                if have and is_older(have, editor):
                    found.append(Problem("pyzed-old", "The project uses pyzed-ui {have}",
                                         "The editor is {editor}: controls and properties added since may not run. "
                                         "Update it to the editor's version.", {"have": have, "editor": editor}))
        if not self.venv.is_dir():
            found.append(Problem("no-environment", "The project's environment is not created",
                                 "Sync creates .venv with the packages of uv.lock."))
        else:
            stale = [d.name for d in deps if d.group in ("main", "dev") and ";" not in d.spec  # no platform markers
                     and (d.installed is None or (d.locked is not None and d.installed != d.locked))]
            if stale:
                found.append(Problem("not-installed", "Not installed as uv.lock says: {names}",
                                     "Sync the environment to install them.",
                                     {"count": str(len(stale)), "names": ", ".join(stale)}))
        return found

    def update_pyzed(self, version: Optional[str] = None) -> Result:
        """Brings ``pyzed-ui`` up to ``version`` (default: this Pyzed's): raises its lowest version in
        ``pyproject.toml`` with ``uv add`` (which locks and syncs), or, when that release is not published,
        upgrades it as far as the package index goes."""
        version = version or editor_version()
        if version.startswith("0+"):
            return self.upgrade(PACKAGE)
        result = self.add(f"{PACKAGE}>={version}")
        if result.ok:
            return result
        upgraded = self.upgrade(PACKAGE)
        return Result(upgraded.args, upgraded.code, "\n".join(x for x in (result.output, upgraded.output) if x))

    # -- preparing -------------------------------------------------------------------------------
    @property
    def environment(self) -> Environment:
        """Where the project lives and its commands run (this computer or WSL)."""
        return environment(self.root)

    def _exec(self, args: Sequence[str], *, timeout: Optional[float] = None) -> Result:
        """Runs ``args`` in the project folder, inside WSL for a WSL project opened from Windows."""
        env = self.environment
        if env.remote:
            extra = {"UV_NO_PROGRESS": "1", "NO_COLOR": "1", **_package_managers.environment()}
            return execute(env.command(args, self.root, extra), timeout=timeout)
        return execute(args, self.root, timeout=timeout)

    def _uv_command(self) -> str:
        """The ``uv`` that runs this project's commands (the Linux one, by name, for a remote WSL project)."""
        return "uv" if self.environment.remote else _uv()

    def has_uv(self) -> bool:
        """Whether ``uv`` is installed where the project's commands run."""
        if self.environment.remote:
            return self._exec(["uv", "--version"], timeout=30).ok
        return find_uv() is not None

    def install_uv(self) -> Result:
        """Installs ``uv`` where the project's commands run (inside WSL for a remote WSL project)."""
        if self.environment.remote:
            return self._exec(["sh", "-c", UV_INSTALL["posix"]], timeout=300)
        return install_uv()

    def needs_prepare(self) -> bool:
        """Whether opening the project has work to do first: install ``uv``, or create ``.venv``. Cheap enough for
        the UI thread: a WSL project from Windows with a ``.venv`` already has its uv."""
        if not self.venv.is_dir():
            return True
        return not self.environment.remote and find_uv() is None

    def prepare(self) -> Result:
        """Gets the project ready to work on, like Zed loading a project's environment: installs ``uv`` when it
        is missing, then creates ``.venv`` with the project's packages and tools (``uv sync``)."""
        steps: List[Result] = []
        if not self.has_uv():
            steps.append(self.install_uv())
            if not steps[-1].ok:
                return steps[-1]
        if not self.venv.is_dir():
            steps.append(self.sync())
        if not steps:
            return Result(["uv", "sync"], 0, "Ready")
        return Result(steps[-1].args, steps[-1].code, "\n".join(r.output for r in steps if r.output))

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
            if self.environment.remote:
                return self._exec([self._uv_command(), *args], timeout=timeout)
            return execute_uv([self._uv_command(), *args], self.root, timeout=timeout, venv=self.venv)
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
            return self._exec([path, *args])
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

    def git(self, *args: str, timeout: Optional[float] = GIT_TIMEOUT) -> Result:
        """Runs ``git`` with ``args`` in the project folder (exit code 127 if git is not installed, 124 when it
        takes longer than ``timeout`` seconds)."""
        git = "git" if self.environment.remote else shutil.which("git")
        if git is None:
            return Result(["git", *args], 127, "git is not installed")
        return self._exec([git, *args], timeout=timeout)

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

    def git_worktree(self) -> Optional[str]:
        """The name of the linked git worktree the project is in (``git worktree add``), or ``None`` in the
        repository's main folder or outside git."""
        if not self.is_git:
            return None
        result = self.git("rev-parse", "--git-dir", "--git-common-dir")
        lines = result.output.splitlines() if result.ok else []
        if len(lines) != 2:
            return None
        git_dir, common = ((self.root / line).resolve() for line in lines)
        return git_dir.name if git_dir != common else None

    def git_branches(self) -> List[str]:
        """The local branches, sorted by name (empty outside a repository)."""
        result = self.git("branch", "--format=%(refname:short)") if self.is_git else None
        return sorted(line.strip() for line in result.output.splitlines() if line.strip()) \
            if result and result.ok else []

    def switch_branch(self, name: str) -> Result:
        """``git switch name``."""
        return self.git("switch", name)

    # -- running ---------------------------------------------------------------------------------
    def run_args(self, form: Optional[PathLike] = None, *, reload: bool = False) -> List[str]:
        """The command that runs ``form`` (default: the main form) with the project's environment."""
        form = Path(form) if form else self.main_form
        args = ["pyzed", "run", str(form)]
        if reload:
            args.append("--reload")
        if self.served_from_wsl:  # this Windows environment has the project's dependencies
            return [sys.executable, "-m", *args]
        return [self._uv_command(), "run", *args]

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
        if self.served_from_wsl:
            return self._popen([sys.executable, str(script)], capture, env)
        return self._popen([self._uv_command(), "run", str(script)], capture, env)

    def _popen(self, args: List[str], capture: bool, env: Optional[Dict[str, str]]) -> "subprocess.Popen[bytes]":
        pipes = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT} if capture else {}
        env = {**_clean_env(), **(env or {})}
        if capture:
            env["PYTHONUNBUFFERED"] = "1"  # lines reach the designer's console as they are printed
        # No console window on Windows (the output goes to the designer), and a process group of its own
        # elsewhere, so ``terminate`` stops uv and the Python it starts together.
        where = self.environment
        if where.remote and not self.served_from_wsl:  # the variables cross into WSL on the command line
            extra = {k: v for k, v in env.items() if k in ("PYTHONUNBUFFERED", "UV_NO_PROGRESS", "NO_COLOR")
                     or k.startswith("PYZED") or os.environ.get(k) != v and k != "UV_PYTHON_INSTALL_DIR"}
            return subprocess.Popen(where.command(args, self.root, extra), env=_clean_env(), creationflags=NO_WINDOW,
                                    **pipes)
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


def _set_pyzed_keys(project: Project, **values: Optional[str]) -> None:
    """Sets (or, with ``None``, removes) keys of the ``[tool.pyzed]`` table in ``pyproject.toml``, keeping the
    rest of the file as it is."""
    file = project.root / PYPROJECT
    text = file.read_text(encoding="utf-8")
    table = re.search(r"^\[tool\.pyzed\][ \t]*\n((?:(?!\[).*\n?)*)", text, re.M)
    if table is None:
        text = text.rstrip() + "\n\n[tool.pyzed]\n"
        table = re.search(r"^\[tool\.pyzed\][ \t]*\n((?:(?!\[).*\n?)*)", text, re.M)
        assert table is not None
    body = table.group(1)
    for key, value in values.items():
        line = re.compile(rf"^{key}[ \t]*=.*\n?", re.M)
        new = f"{key} = {json.dumps(value)}\n" if value is not None else ""
        if line.search(body):
            body = line.sub(lambda _: new, body, count=1)
        elif new:
            body = body.rstrip("\n") + ("\n" if body.strip() else "") + new + ("\n" if body.endswith("\n\n") else "")
    text = text[:table.start(1)] + body + text[table.end(1):]
    file.write_text(text, encoding="utf-8")
    project.reload()


def prebuilt(text: str) -> str:
    """``pyproject.toml`` text whose ``[tool.uv]`` installs ``pyzed-ui`` from wheels only (``no-build-package``).

    Left as is when it already sets ``no-build-package`` or takes ``pyzed-ui`` from a local source
    (a checkout of Pyzed, which has to be built)."""
    if re.search(r"^no-build-package\s*=", text, re.M) or re.search(r"^pyzed-ui\s*=\s*\{", text, re.M):
        return text
    table = re.search(r"^\[tool\.uv\][ \t]*\n", text, re.M)
    if table:
        return text[:table.end()] + PREBUILT + text[table.end():]
    return text.rstrip() + "\n\n[tool.uv]\n" + PREBUILT


def _ensure_config(project: Project, ui: str) -> None:
    file = project.root / PYPROJECT
    text = original = file.read_text(encoding="utf-8")
    if not re.search(r"^\[tool\.pyzed\]", text, re.M):
        text = text.rstrip() + "\n" + f'\n[tool.pyzed]\nui = "{ui}"\nmain = "{ui}/{DEFAULT_MAIN}.pzform"\n'
    text = prebuilt(text)
    if text != original:
        file.write_text(text, encoding="utf-8")
    project.reload()


def init(path: PathLike = ".", *, name: Optional[str] = None, ui: str = DEFAULT_UI, package: bool = True,
         git: bool = True, python: Optional[str] = None, sync: bool = True,
         dev_tools: Sequence[str] = DEV_TOOLS) -> Project:
    """Creates a Pyzed project at ``path``, or adds Pyzed to the ``uv`` project already there.

    - No ``pyproject.toml`` yet: runs ``uv init`` (``--package`` puts the backend in
      ``src/<name>`` so the UI can import it from anywhere).
    - Adds ``[tool.pyzed]``, ``[tool.uv] no-build-package`` (see ``PREBUILT``), the ``ui/`` folder with a starter form, ``pyzed-ui`` as a
      dependency and ``ruff``/``ty`` as dev dependencies (``sync=False`` only edits
      ``pyproject.toml``, without resolving or installing anything).
    - ``git=True`` creates a git repository unless the folder is already inside one.
    - A new project gets an ``AGENTS.md``: how AI agents should build, design and check it.

    Raises ``RuntimeError`` with uv's message when ``uv init`` fails.
    """
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    fresh = not (root / PYPROJECT).exists()
    python = python or _package_managers.values("uv")["python"].strip() or None
    if fresh:
        args = ["init", "--name", name or root.name, "--vcs", "git" if git else "none"]
        args.append("--package" if package else "--app")
        if python:
            args += ["--python", python]
        where = environment(root)
        if where.remote:  # a folder of WSL opened from Windows: the project is made by Linux's uv, like its .venv
            extra = {"UV_NO_PROGRESS": "1", **_package_managers.environment()}
            result = execute(where.command(["uv", *args, str(root)], root, extra), timeout=300)
        else:
            result = execute_uv([_uv(), *args, str(root)], root)
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
    agents = root / "AGENTS.md"
    if fresh and not agents.exists():  # how AI coding agents should work on the project
        template = (Path(__file__).parent / "templates" / "AGENTS.md").read_text(encoding="utf-8")
        backend = f"`src/{module}/`" if package else "The modules next to `pyproject.toml`"
        agents.write_text(template.replace("{backend}", backend), encoding="utf-8")
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
    path = Path(form) if form else project.main_form
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist: open the app from its own code (pz.run) or make a form "
                                "the project's startup file")
    designer.run(path, reload=reload)


def clone(url: str, target: PathLike) -> Result:
    """``git clone url target``; into a folder of WSL opened from Windows, with Linux's git."""
    target = Path(target)
    where = environment(target)
    if where.remote:
        target.parent.mkdir(parents=True, exist_ok=True)
        return execute(where.command(["git", "clone", url, str(target)], target.parent), timeout=600)
    return execute([shutil.which("git") or "git", "clone", url, str(target)], timeout=600)


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
    """Where Pyzed keeps per-user settings (``$PYZED_CONFIG_DIR`` overrides it, like the designer's)."""
    if os.environ.get("PYZED_CONFIG_DIR"):
        return Path(os.environ["PYZED_CONFIG_DIR"])
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
