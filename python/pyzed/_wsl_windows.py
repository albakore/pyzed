"""Native Windows windows for apps started in WSL.

Under WSL, a Linux window goes through WSLg: XWayland, a Wayland compositor and a remote desktop connection
that shows it on the Windows desktop. It works, but every frame crosses those layers, the GPU is reached
through a translation layer, and the window is not a real Windows window (snapping, the taskbar, high-DPI
scaling and the title bar behave differently).

So when Pyzed runs in WSL and finds uv (or Python) on Windows, everything that opens a window runs as a native
Windows program instead: ``pyzed design``, ``pyzed run``, ``pyzed dev``, scripts that call ``pz.run``, Run in
Pyzed Design and the MCP server's live previews. How it works:

1. The code and the project stay in WSL. Windows reads them through ``\\\\wsl.localhost\\<distro>\\...`` and
   starts in the same folder, so relative paths, imports and hot reload (which polls the files) work as usual.
2. Windows gets an environment of its own in ``%LOCALAPPDATA%\\pyzed\\wsl\\<distro>-<project>-<hash>-py3XX``,
   made with uv (or with ``py.exe`` and pip): the same Python version, the project's dependencies (exported
   from ``uv.lock``), what the editor's extras need (agents, MCP, language servers) and the ``pyzed-ui`` wheel
   of the same version, always a prebuilt wheel, never compiled on Windows. The project's ``.venv`` stays the
   Linux one. It is made the first time and again only when the dependencies change.
   From a checkout of Pyzed (its version may not be released, and its Rust may have changed), Windows imports
   the checkout's own Python sources instead, with the native core cross-compiled for Windows in WSL
   (``maturin build --target x86_64-pc-windows-gnu``, or ``-msvc``) once per version of the Rust sources.
3. The Linux process waits for the Windows one and passes its output and exit code along. When it is
   stopped (Stop in the designer, Ctrl+C, the MCP server closing the preview), the Windows app ends too: it
   watches a pipe from the Linux side and exits when the pipe closes.

Without uv or Python on Windows, windows open through WSLg as before, with a note on how to set it up
(``pyzed windows setup`` installs uv on Windows with its official installer).

Environment variables (all optional):

* ``PYZED_WINDOWS=0`` opens windows through WSLg (the ``--wslg`` option of ``design``, ``run`` and ``dev``
  sets it for the command and everything it starts).
* ``PYZED_WINDOWS_WHEEL`` is the path or URL of the ``pyzed-ui`` wheel for Windows to use instead (a checkout
  then uses it instead of building its core).
* ``PYZED_WINDOWS_TARGET`` picks the Rust target a checkout's core is built for (default: MSVC when clang and
  lld are installed, else MinGW).
* ``PYZED_WINDOWS_ENV=NAME,NAME`` passes more variables to the Windows app (API keys...). ``PYZED_*`` ones
  always cross, and so does anything already listed in ``WSLENV``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from . import _platform

__all__ = ["Host", "WindowsEnv", "enabled", "handoff", "handoff_script", "host", "to_linux", "to_windows"]

SETTING = "PYZED_WINDOWS"
WHEEL = "PYZED_WINDOWS_WHEEL"
PASS_ENV = "PYZED_WINDOWS_ENV"
PACKAGE = "pyzed-ui"
_OFF = {"0", "false", "no", "off", "wslg"}
#: Variables of this module: they configure the Linux side and do not cross.
_OWN = {SETTING, WHEEL, PASS_ENV}

NO_PYTHON = ("Pyzed: no uv or Python found on Windows, so the window opens through WSLg. Run `pyzed windows "
             "setup` to install uv on Windows and open windows as native Windows windows, or set "
             "PYZED_WINDOWS=0 to hide this note.")

def enabled() -> bool:
    """Whether windows opened here should open on Windows: under WSL, unless ``PYZED_WINDOWS`` says no."""
    return os.environ.get(SETTING, "").strip().lower() not in _OFF and _platform.is_wsl()


def disable() -> None:
    """Opens windows through WSLg from now on, in this process and the ones it starts."""
    os.environ[SETTING] = "0"


_warned: set = set()


def _note(text: str) -> None:
    """Prints ``text`` to stderr once per process."""
    if text not in _warned:
        _warned.add(text)
        print(text, file=sys.stderr, flush=True)


# -- paths ----------------------------------------------------------------------------------------------

_DRIVE = re.compile(r"^/mnt/([a-zA-Z])(?:/(.*))?$")
_WINDOWS_DRIVE = re.compile(r"^([a-zA-Z]):[\\/]*(.*)$")


def _wslpath(flag: str, path: str) -> Optional[str]:
    tool = shutil.which("wslpath")
    if tool is None:
        return None
    try:
        done = subprocess.run([tool, flag, path], capture_output=True, text=True, timeout=10,  # noqa: S603
                              stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    out = done.stdout.strip()
    return out if done.returncode == 0 and out else None


def windows_form(path: str, distro: Optional[str] = None) -> str:
    """``/mnt/c/Users`` as ``C:\\Users`` and ``/home/me`` as ``\\\\wsl.localhost\\<distro>\\home\\me``."""
    found = _DRIVE.match(path)
    if found:
        return f"{found.group(1).upper()}:\\" + (found.group(2) or "").replace("/", "\\")
    distro = distro or os.environ.get("WSL_DISTRO_NAME") or "Ubuntu"
    return "\\\\wsl.localhost\\" + distro + path.replace("/", "\\")


def linux_form(path: str) -> Optional[str]:
    """``C:\\Users`` as ``/mnt/c/Users`` (``None`` for anything that is not on a drive)."""
    found = _WINDOWS_DRIVE.match(path)
    if not found:
        return None
    rest = "/".join(part for part in re.split(r"[\\/]+", found.group(2)) if part)
    return f"/mnt/{found.group(1).lower()}" + (f"/{rest}" if rest else "")


def to_windows(path) -> str:
    """The Windows path of a file seen from WSL (``wslpath -w``, which knows custom mount points)."""
    text = os.path.abspath(str(path))
    return _wslpath("-w", text) or windows_form(text)


def to_linux(path: str) -> Optional[str]:
    """The WSL path of a Windows path (``wslpath -u``), or ``None``."""
    return _wslpath("-u", path) or linux_form(path)


# -- what Windows has ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Host:
    """The Windows side: its folders (Linux paths, under ``/mnt``) and its uv or Python launcher."""

    local_app_data: str
    user_profile: str
    uv: Optional[str] = None
    py: Optional[str] = None

    @property
    def ready(self) -> bool:
        """Whether there is something to make the Windows environment with."""
        return bool(self.uv or self.py)

    @property
    def envs(self) -> Path:
        """Where the Windows environments of WSL projects live."""
        return Path(self.local_app_data) / "pyzed" / "wsl"


def _windows_variables(*names: str) -> Optional[List[str]]:
    """Windows' environment variables (as Windows paths), asked to ``cmd.exe``, which prints UTF-16 with /u."""
    cmd = _platform.windows_command("cmd.exe")
    if cmd is None:
        return None
    try:  # started in C:\ so cmd.exe does not complain about a \\wsl.localhost working folder
        done = subprocess.run([cmd, "/u", "/d", "/c", "echo", ";".join(f"%{n}%" for n in names)],  # noqa: S603
                              capture_output=True, timeout=20, stdin=subprocess.DEVNULL, check=False,
                              cwd="/mnt/c" if os.path.isdir("/mnt/c") else None)
    except (OSError, subprocess.SubprocessError):
        return None  # WSL's interop is off: .exe files cannot run
    raw = done.stdout
    try:
        text = raw.decode("utf-16-le") if len(raw) % 2 == 0 and b"\x00" in raw else raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", "replace")
    values = text.strip().split(";")
    if done.returncode != 0 or len(values) != len(names) or any("%" in v or not v for v in values):
        return None
    return values


def _first_file(*paths: Optional[str]) -> Optional[str]:
    return next((p for p in paths if p and os.path.isfile(p)), None)


_host: Optional[Host] = None
_HOST_LOCK = threading.Lock()


def host(refresh: bool = False) -> Optional[Host]:
    """What Windows has, worked out once per process (``None`` when Windows programs cannot run from here)."""
    global _host
    with _HOST_LOCK:
        if _host is not None and not refresh:
            return _host
        values = _windows_variables("LOCALAPPDATA", "USERPROFILE")
        if values is None:
            return None
        lad, profile = (to_linux(v) for v in values)
        if lad is None or profile is None:
            return None
        uv = _first_file(shutil.which("uv.exe"), f"{profile}/.local/bin/uv.exe", f"{profile}/.cargo/bin/uv.exe",
                         f"{lad}/Microsoft/WinGet/Links/uv.exe", f"{profile}/scoop/shims/uv.exe")
        py = _first_file(shutil.which("py.exe"), "/mnt/c/Windows/py.exe", f"{lad}/Programs/Python/Launcher/py.exe")
        _host = Host(lad, profile, uv, py)
        return _host


def install_uv(on_output: Callable[[str], None] = print) -> bool:
    """Installs uv on Windows with its official installer (PowerShell; needs network). Whether it worked."""
    from .project import UV_INSTALL

    shell = _platform.windows_command("powershell.exe")
    if shell is None:
        on_output("powershell.exe was not found: install uv on Windows by hand "
                  "(https://docs.astral.sh/uv/getting-started/installation/)")
        return False
    try:
        done = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "ByPass", "-Command", UV_INSTALL["nt"]],  # noqa: S603
                              capture_output=True, text=True, errors="replace", timeout=600, check=False,
                              stdin=subprocess.DEVNULL, cwd="/mnt/c" if os.path.isdir("/mnt/c") else None)
    except (OSError, subprocess.SubprocessError) as err:
        on_output(str(err))
        return False
    output = (done.stdout + done.stderr).strip()
    if output:
        on_output(output)
    found = host(refresh=True)
    return done.returncode == 0 and found is not None and found.uv is not None


# -- what the Windows environment needs -----------------------------------------------------------------


def _name(spec: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    return re.sub(r"[-_.]+", "-", match.group(1)).lower() if match else ""


_REQUIREMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\s*(\[[^\]]*\])?\s*($|[<>=!~;@(])")


def keep_requirement(line: str) -> bool:
    """Whether a line of an exported requirements file belongs in the Windows environment: not Pyzed itself
    (it comes as a wheel), not local folders (the project and workspace members are imported from WSL), no
    comments and no options."""
    line = line.strip()
    if not _REQUIREMENT.match(line):  # also leaves out uv's warnings, which share its output
        return False
    if re.match(r"^[A-Za-z0-9._-]+\s*@\s*(file:|\.|/)", line):
        return False
    return _name(line) != PACKAGE


_SCRIPT_BLOCK = re.compile(r"(?m)^# /// script$\s(?P<content>(^#(| .*)$\s)+)^# ///$")


def script_requirements(script: Path) -> List[str]:
    """The dependencies of a single-file app: its inline metadata (PEP 723) and a ``requirements.txt`` next to
    it (``pyzed new --script`` makes one)."""
    from .project import _loads_toml

    found: List[str] = []
    try:
        block = _SCRIPT_BLOCK.search(script.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        block = None
    if block:
        toml = "\n".join(line[2:] if line.startswith("# ") else line[1:]
                         for line in block.group("content").splitlines())
        try:
            found += [d for d in _loads_toml(toml).get("dependencies", []) if isinstance(d, str)]
        except Exception:  # noqa: BLE001 - a broken block is the script's problem, reported when it runs
            pass
    requirements = script.parent / "requirements.txt"
    if requirements.is_file():
        found += requirements.read_text(encoding="utf-8", errors="replace").splitlines()
    return [line.strip() for line in found if keep_requirement(line)]


def project_requirements(project) -> List[str]:
    """The project's dependencies with the versions of ``uv.lock`` (``uv export``), else ``pyproject.toml``'s."""
    from . import project as _project

    uv = _project.find_uv()
    if uv and (project.root / "uv.lock").is_file():
        result = _project.execute([uv, "export", "--frozen", "--no-hashes", "--no-emit-project", "--no-header",
                                   "--no-annotate", "--format", "requirements-txt"], project.root, timeout=120)
        if result.ok:
            return [line.strip() for line in result.output.splitlines() if keep_requirement(line)]
    specs = project.data.get("project", {}).get("dependencies", [])
    return [s.strip() for s in specs if isinstance(s, str) and keep_requirement(s)]


def pyzed_requirement() -> tuple:
    """``(requirement, exact)``: the ``pyzed-ui`` to install on Windows and whether it is this same version.

    ``PYZED_WINDOWS_WHEEL`` wins. A release installed from the package index gives ``pyzed-ui==<version>``; a
    checkout (an editable or local install, whose version may not be published) gives the latest release."""
    wheel = os.environ.get(WHEEL, "").strip()
    if wheel:
        return (to_windows(wheel) if os.path.exists(wheel) else wheel), True
    from importlib import metadata

    try:
        dist = metadata.distribution(PACKAGE)
    except metadata.PackageNotFoundError:
        return PACKAGE, False
    direct = dist.read_text("direct_url.json")
    if direct:
        try:
            url = json.loads(direct)
        except ValueError:
            url = {}
        if "dir_info" in url or str(url.get("url", "")).startswith("file:"):
            return PACKAGE, False
    return f"{PACKAGE}=={dist.version}", True


def editor_requirements() -> List[str]:
    """What the editor's extras need (the agents, the MCP server, the code editor's language servers): the
    dependencies of this pyzed's ``agents``, ``designer`` and ``mcp`` extras, so ``pyzed design`` on Windows can
    do all it does here."""
    from importlib import metadata

    try:
        requires = metadata.requires(PACKAGE) or []
    except metadata.PackageNotFoundError:
        requires = []
    found = []
    for spec in requires:
        requirement, _, marker = spec.partition(";")
        if "extra" in marker and keep_requirement(requirement):
            found.append(requirement.strip())
    return found


def checkout() -> Optional[Path]:
    """The Pyzed checkout this pyzed runs from (an editable install of the repository), or ``None``."""
    here = Path(__file__).resolve().parents[2]
    if (here / "Cargo.toml").is_file() and (here / "python" / "pyzed").is_dir():
        return here
    return None


#: What makes up the native core: a change to any of them needs a new Windows build.
_CORE_SOURCES = ("Cargo.toml", "Cargo.lock", "build.rs", "pyproject.toml", "src", "vendor")


def core_hash(root: Path) -> str:
    """A fingerprint of the checkout's Rust sources (names, sizes and modification times)."""
    digest = hashlib.sha1()  # noqa: S324 - a cache key, not security
    for name in _CORE_SOURCES:
        path = root / name
        files = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
        for file in files:
            try:
                info = file.stat()
            except OSError:
                continue
            digest.update(f"{file.relative_to(root).as_posix()}:{info.st_size}:{info.st_mtime_ns}\n".encode())
    return digest.hexdigest()[:12]


#: The Windows targets a checkout's core can be built for: MSVC like the released wheels (needs clang and lld;
#: maturin downloads Microsoft's libraries the first time) and MinGW (needs the mingw-w64 package). Both give a
#: core that only uses Windows' own DLLs.
TARGETS = {"x86_64-pc-windows-msvc": ("clang", "lld-link"), "x86_64-pc-windows-gnu": ("x86_64-w64-mingw32-gcc",)}
TOOLCHAIN_HELP = ("To build Pyzed's core for Windows from WSL, install a cross compiler once:\n"
                  "  sudo apt install mingw-w64\n"
                  "then run the command again (or set PYZED_WINDOWS=0 to keep using WSLg).")


def targets() -> List[str]:
    """The Windows targets whose cross compiler is installed, best first (``PYZED_WINDOWS_TARGET`` picks one)."""
    wanted = os.environ.get("PYZED_WINDOWS_TARGET", "").strip()
    if wanted:
        return [wanted]
    return [t for t, tools in TARGETS.items() if all(shutil.which(tool) for tool in tools)]


def _maturin() -> Optional[List[str]]:
    try:
        import maturin  # type: ignore[import-not-found]  # noqa: F401

        return [sys.executable, "-m", "maturin"]
    except ImportError:
        pass
    found = shutil.which("maturin")
    if found:
        return [found]
    from .project import find_uv

    uv = find_uv()
    return [uv, "tool", "run", "maturin"] if uv else None


def _rustup() -> Optional[str]:
    found = shutil.which("rustup") or str(Path.home() / ".cargo" / "bin" / "rustup")
    return found if os.path.isfile(found) else None


def _stream(args: Sequence[str], cwd: Path, log: Callable[[str], None]) -> tuple:
    """Runs ``args``, passing its output on line by line; ``(ok, last lines)``."""
    tail: List[str] = []
    try:
        process = subprocess.Popen([str(a) for a in args], cwd=str(cwd), stdout=subprocess.PIPE,  # noqa: S603
                                   stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, errors="replace")
    except OSError as err:
        return False, str(err)
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip()
        log(line)
        tail = [*tail[-29:], line]
    return process.wait() == 0, "\n".join(tail)


def build_core(root: Path, out: Path, log: Callable[[str], None] = print) -> Optional[str]:
    """Cross-compiles the checkout's native core for Windows (``maturin build --target``, in WSL: nothing is
    compiled on Windows) and puts ``_core.pyd`` in ``out``; the error, or ``None``."""
    import tempfile
    import zipfile

    maturin = _maturin()
    if maturin is None:
        return "maturin is not installed (uv sync installs it)"
    found = targets()
    if not found:
        return TOOLCHAIN_HELP
    rustup = _rustup()
    errors = []
    for target in found:
        if rustup is not None:
            subprocess.run([rustup, "target", "add", target], capture_output=True, check=False,  # noqa: S603
                           stdin=subprocess.DEVNULL, timeout=600)
        log(f"Pyzed: building the native core for Windows ({target}); the first build takes a few minutes…")
        with tempfile.TemporaryDirectory(prefix="pyzed-core-") as tmp:
            ok, tail = _stream([*maturin, "build", "--release", "--target", target, "--out", tmp], root, log)
            wheels = list(Path(tmp).glob("*.whl"))
            if ok and wheels:
                with zipfile.ZipFile(wheels[0]) as wheel:
                    member = next((n for n in wheel.namelist() if re.fullmatch(r"pyzed/_core[^/]*\.pyd", n)), None)
                    if member is not None:
                        out.mkdir(parents=True, exist_ok=True)
                        (out / "_core.pyd").write_bytes(wheel.read(member))
                        return None
            errors.append(f"{target}:\n{tail}")
    return "\n\n".join([*errors, TOOLCHAIN_HELP])


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower() or "app"


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]  # noqa: S324 - a folder name, not security


BOOTSTRAP = '''"""Started by Pyzed in WSL: runs a script or module on Windows and ends when the WSL side stops."""
import os
import runpy
import sys
import threading

try:
    _parent = os.dup(sys.stdin.fileno())
except (AttributeError, OSError, ValueError):
    _parent = None


def _follow_parent():
    # The WSL side holds the other end of stdin; it closes when Pyzed there stops (Stop, Ctrl+C...). The raw
    # descriptor, not sys.stdin: a thread blocked inside a buffered read would stop the interpreter from exiting.
    try:
        while os.read(_parent, 65536):
            pass
    except OSError:
        pass
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if _parent is not None:
    threading.Thread(target=_follow_parent, name="pyzed-wsl-parent", daemon=True).start()
sys.stdin = open(os.devnull, encoding="utf-8")
if os.environ.get("PYZED_WSL_CWD"):  # the WSL folder it was started from
    os.chdir(os.environ.pop("PYZED_WSL_CWD"))
_crossed = set(os.environ.pop("PYZED_WSL_CROSSED", "").split(":"))
os.environ["WSLENV"] = ":".join(i for i in os.environ.get("WSLENV", "").split(":") if i and i.split("/")[0] not in _crossed)
_args = sys.argv[1:]
if _args[:1] == ["-m"]:
    sys.argv = _args[1:]
    sys.path[0] = os.getcwd()
    runpy.run_module(_args[1], run_name="__main__", alter_sys=True)
else:
    sys.argv = _args
    sys.path[0] = os.path.dirname(os.path.abspath(_args[0]))
    runpy.run_path(_args[0], run_name="__main__")
'''


@dataclass
class WindowsEnv:
    """The Windows environment of a project (or of single-file apps), and how to run Python in it."""

    host: Host
    name: str
    requirements: List[str]
    pyzed: str
    exact: bool = True
    paths: List[str] = field(default_factory=list)
    python_version: str = f"{sys.version_info[0]}.{sys.version_info[1]}"
    #: The project this environment is for (its Linux path), so Pyzed Design on Windows runs its forms itself.
    project_root: Optional[str] = None
    #: Running from a checkout: its root, whose Python sources Windows imports with a core built for Windows.
    source: Optional[Path] = None

    @classmethod
    def for_target(cls, host: Host, project=None, script: Optional[Path] = None) -> "WindowsEnv":
        """The environment for ``project`` (its dependencies, its folders importable) or, without one, for the
        single-file app ``script``."""
        source = None if os.environ.get(WHEEL) else checkout()
        pyzed, exact = pyzed_requirement() if source is None else ("", True)
        distro = _slug(os.environ.get("WSL_DISTRO_NAME") or "wsl")
        version = f"{sys.version_info[0]}{sys.version_info[1]}"
        paths = [to_windows(source / "python")] if source is not None else []
        if project is not None:
            requirements = project_requirements(project)
            name = f"{distro}-{_slug(project.name)}-{_digest(str(project.root))}-py{version}"
            paths += [to_windows(p) for p in project.paths()]
        else:
            requirements = script_requirements(script) if script is not None else []
            name = f"{distro}-scripts-{_digest(chr(10).join(sorted(requirements)))}-py{version}"
        requirements += [r for r in editor_requirements() if r not in requirements]
        return cls(host, name, requirements, pyzed, exact, paths,
                   project_root=str(project.root) if project is not None else None, source=source)

    # -- where things are (Linux paths) --
    @property
    def base(self) -> Path:
        return self.host.envs / self.name

    @property
    def venv(self) -> Path:
        return self.base / "venv"

    @property
    def python(self) -> Path:
        return self.venv / "Scripts" / "python.exe"

    @property
    def bootstrap(self) -> Path:
        return self.host.envs / "bootstrap.py"

    @property
    def core(self) -> Optional[Path]:
        """For a checkout, the folder with its native core built for Windows (one per version of the sources)."""
        return self.host.envs / "core" / core_hash(self.source) if self.source is not None else None

    def wanted(self, pyzed: Optional[str] = None) -> str:
        """The requirements file this environment installs (also its stamp once installed)."""
        what = f"# Pyzed from {self.source}" if self.source is not None else (pyzed or self.pyzed)
        lines = [f"# Python {self.python_version}", what, *self.requirements]
        return "\n".join(lines) + "\n"

    @property
    def ready(self) -> bool:
        stamp = self.base / "installed.txt"
        try:
            return self.python.is_file() and stamp.read_text(encoding="utf-8") in (
                self.wanted(), self.wanted(PACKAGE))
        except OSError:
            return False

    # -- making it --
    def _run(self, args: Sequence[str], timeout: float = 1800) -> tuple:
        try:  # from C:\, so neither uv nor cmd reads a pyproject.toml or .python-version of the WSL folder
            done = subprocess.run([str(a) for a in args], capture_output=True, text=True, errors="replace",  # noqa: S603
                                  timeout=timeout, check=False, stdin=subprocess.DEVNULL,
                                  cwd="/mnt/c" if os.path.isdir("/mnt/c") else None,
                                  env={**os.environ, "UV_NO_PROGRESS": "1", "NO_COLOR": "1"})
        except (OSError, subprocess.SubprocessError) as err:
            return False, str(err)
        return done.returncode == 0, (done.stdout + done.stderr).strip()

    def _create(self) -> tuple:
        venv = to_windows(self.venv)
        if self.host.uv:
            return self._run([self.host.uv, "venv", "--allow-existing", "--python", self.python_version, venv])
        assert self.host.py is not None
        ok, output = self._run([self.host.py, f"-{self.python_version}", "-m", "venv", venv])
        return (ok, output) if ok else self._run([self.host.py, "-3", "-m", "venv", venv])

    def _install(self, requirements: Path) -> tuple:
        file = to_windows(requirements)
        if self.host.uv:
            return self._run([self.host.uv, "pip", "install", "--python", to_windows(self.python),
                              "--only-binary", PACKAGE, "-r", file])
        return self._run([str(self.python), "-m", "pip", "install", "--disable-pip-version-check",
                          "--only-binary", PACKAGE, "-r", file])

    def prepare(self, log: Callable[[str], None] = lambda text: _note(text)) -> Optional[str]:
        """Makes the environment (only when it is missing or its requirements changed); the error, or ``None``."""
        self.base.mkdir(parents=True, exist_ok=True)
        if not self.bootstrap.is_file() or self.bootstrap.read_text(encoding="utf-8") != BOOTSTRAP:
            self.bootstrap.write_text(BOOTSTRAP, encoding="utf-8")
        core = self.core
        if core is not None and not (core / "_core.pyd").is_file():
            error = build_core(self.source, core, log)
            if error:
                return error
        if self.ready:
            return None
        log(f"Pyzed: preparing the Windows environment in {to_windows(self.base)} (the first time, and when the "
            "dependencies change)…")
        if not self.python.is_file():
            ok, output = self._create()
            if not ok or not self.python.is_file():
                return output or "could not create the virtual environment"
        requirements = self.base / "requirements.txt"
        attempts = [self.pyzed] + ([PACKAGE] if self.exact and self.pyzed not in ("", PACKAGE) and
                                   not os.environ.get(WHEEL) else [])
        output = ""
        for pyzed in attempts:
            requirements.write_text(self.wanted(pyzed), encoding="utf-8")
            ok, output = self._install(requirements)
            if ok:
                if pyzed != self.pyzed:
                    log(f"Pyzed: {self.pyzed} has no Windows wheel yet; using the latest release.")
                (self.base / "installed.txt").write_text(self.wanted(pyzed), encoding="utf-8")
                return None
        return output or "could not install the dependencies"

    # -- running --
    def environ(self, cwd: Optional[str] = None) -> Dict[str, str]:
        """This process's variables plus what the Windows app needs, listed in ``WSLENV`` so they cross."""
        env = dict(os.environ)
        crossing: Dict[str, str] = {}
        for key, value in os.environ.items():
            if key.startswith("PYZED_") and key not in _OWN:
                crossing[key] = value
        for key in filter(None, (k.strip() for k in os.environ.get(PASS_ENV, "").split(","))):
            if key in os.environ:
                crossing[key] = os.environ[key]
        if crossing.get("PYZED_WATCH"):
            crossing["PYZED_WATCH"] = ";".join(to_windows(p) for p in crossing["PYZED_WATCH"].split(os.pathsep) if p)
        if crossing.get("PYZED_CONFIG_DIR"):
            crossing["PYZED_CONFIG_DIR"] = to_windows(crossing["PYZED_CONFIG_DIR"])
        own = self.variables()
        own["PYZED_WSL_CWD"] = to_windows(cwd or os.getcwd())
        # The Windows side takes these back out of WSLENV, so programs it starts in WSL do not get them.
        own["PYZED_WSL_CROSSED"] = ":".join([*own, "PYZED_WSL_CROSSED"])
        crossing.update(own)
        env.update(crossing)
        if "PYTHONPATH" not in crossing:
            env.pop("PYTHONPATH", None)
        listed = [item for item in os.environ.get("WSLENV", "").split(":")
                  if item and item.split("/")[0] not in crossing]
        env["WSLENV"] = ":".join([*listed, *crossing])
        return env

    def variables(self) -> Dict[str, str]:
        """The variables Python needs on Windows for this environment (Windows values)."""
        found = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1",
                 "PYZED_WSL_DISTRO": os.environ.get("WSL_DISTRO_NAME", "")}
        if self.paths:
            found["PYTHONPATH"] = ";".join(self.paths)
        if self.core is not None:
            from importlib import metadata

            found["PYZED_CORE_DIR"] = to_windows(self.core)
            try:
                found["PYZED_VERSION"] = metadata.version(PACKAGE)
            except metadata.PackageNotFoundError:
                pass
        if self.project_root:
            found["PYZED_WSL_PROJECT"] = self.project_root
        return found

    def command(self, args: Sequence[str]) -> List[str]:
        """``python.exe bootstrap.py <args>``, with the paths among ``args`` turned into Windows paths."""
        return [str(self.python), to_windows(self.bootstrap), *(windows_arg(a) for a in args)]

    def launch(self, args: Sequence[str], cwd: Optional[str] = None) -> int:
        """Runs Python on Windows with ``args`` and waits; returns its exit code. Stopping this process (a
        signal, Ctrl+C) ends the Windows app too."""
        process = subprocess.Popen(self.command(args), cwd=cwd, env=self.environ(cwd),  # noqa: S603
                                   stdin=subprocess.PIPE)
        previous = None

        def on_term(signum, _frame):
            _end(process)
            raise SystemExit(128 + signum)

        if threading.current_thread() is threading.main_thread():
            previous = signal.signal(signal.SIGTERM, on_term)
        try:
            return process.wait()
        except KeyboardInterrupt:
            _end(process)
            return 130
        finally:
            if previous is not None:
                signal.signal(signal.SIGTERM, previous)


def windows_arg(arg: str) -> str:
    """A command-line argument for the Windows side: an absolute path that exists becomes a Windows path
    (relative ones work as they are: the app starts in the same folder)."""
    return to_windows(arg) if arg.startswith("/") and os.path.exists(arg) else arg


def _end(process: "subprocess.Popen[bytes]") -> None:
    """Ends the Windows app: closing its stdin is the signal it watches; then its WSL side is stopped."""
    try:
        if process.stdin is not None:
            process.stdin.close()
    except OSError:
        pass
    try:
        process.wait(3)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(2)
        except subprocess.TimeoutExpired:
            process.kill()


# -- handing off ----------------------------------------------------------------------------------------


#: Set once this process has fallen back to WSLg, so a later ``pz.run`` does not try (and fail) again.
_fell_back = False


def environment_for(project=None, script: Optional[Path] = None) -> Optional[WindowsEnv]:
    """The Windows environment for ``project`` or ``script``, ready to run (``None``, after printing why, when
    the window has to open through WSLg)."""
    global _fell_back
    found = host()
    if found is None or not found.ready:
        _fell_back = True
        _note(NO_PYTHON)
        return None
    try:
        env = WindowsEnv.for_target(found, project, script)
        error = env.prepare()
    except OSError as err:
        error = str(err)
    if error:
        _fell_back = True
        tail = "\n".join(error.strip().splitlines()[-15:])
        _note(f"Pyzed: could not prepare the Windows environment, so the window opens through WSLg:\n{tail}")
        return None
    return env


def handoff(args: Sequence[str], *, project=None, script: Optional[Path] = None,
            cwd: Optional[str] = None) -> Optional[int]:
    """Runs ``python <args>`` on Windows when windows should open there; returns its exit code, or ``None``
    when this process should open the window itself (not WSL, turned off, or nothing to run it with)."""
    if _fell_back or not enabled():
        return None
    env = environment_for(project, script)
    if env is None:
        return None
    try:
        return env.launch(args, cwd)
    except OSError as err:  # interop turned off between the checks and now
        _note(f"Pyzed: could not start Python on Windows ({err}); the window opens through WSLg.")
        return None


def script_args(argv: Optional[Sequence[str]] = None, orig_argv: Optional[Sequence[str]] = None) -> Optional[List[str]]:
    """How this process was started, to start it again on Windows: ``[script, *args]`` or
    ``["-m", module, *args]``; ``None`` for ``python -c``, the REPL and anything else that cannot be."""
    argv = list(sys.argv if argv is None else argv)
    orig = list(getattr(sys, "orig_argv", []) if orig_argv is None else orig_argv)
    i = 1
    while i < len(orig):  # the interpreter's own options come before the script or -m
        arg = orig[i]
        if arg == "-m" and i + 1 < len(orig):
            return ["-m", orig[i + 1], *argv[1:]]
        if arg in ("-c", "-"):
            return None
        if arg in ("-X", "-W", "--check-hash-based-pycs"):
            i += 2
            continue
        if not arg.startswith("-"):
            break
        i += 1
    first = argv[0] if argv else ""
    return [first, *argv[1:]] if first and os.path.isfile(first) else None


def handoff_script() -> Optional[int]:
    """``handoff`` for a script that calls ``pz.run``: the same script (or module) with the same arguments."""
    if not enabled():
        return None
    args = script_args()
    if args is None:
        return None
    script = Path(args[0]).resolve() if args[0] != "-m" else None
    from .project import Project

    project = Project.find(script.parent if script is not None else Path.cwd())
    return handoff(args, project=project, script=script)


# -- pyzed windows ------------------------------------------------------------------------------------------


def status(project=None) -> List[str]:
    """What ``pyzed windows`` prints: whether windows open on Windows, with what, and where."""
    if not _platform.is_wsl():
        return ["This is not WSL: windows open here as usual."]
    lines = ["Native Windows windows: " + ("on" if enabled() else f"off ({SETTING}=0): windows open through WSLg")]
    found = host()
    if found is None:
        return [*lines, "Windows programs cannot run from this WSL (interop is off): windows open through WSLg."]
    lines += [f"uv on Windows: {found.uv or 'not found'}", f"Python launcher (py.exe): {found.py or 'not found'}"]
    if not found.ready:
        return [*lines, "Run `pyzed windows setup` to install uv on Windows."]
    env = WindowsEnv.for_target(found, project)
    if env.source is not None:
        core = env.core
        built = core is not None and (core / "_core.pyd").is_file()
        lines.append(f"Pyzed on Windows: this checkout ({env.source}), its core cross-compiled for Windows "
                     f"({'built' if built else 'built on first run'})")
    else:
        lines.append(f"Pyzed on Windows: {env.pyzed}" + ("" if env.exact else " (the latest release)"))
    where = f"for {project.name}" if project is not None else "for single-file apps"
    lines.append(f"Environment {where}: {to_windows(env.base)} ({'ready' if env.ready else 'made on first run'})")
    return lines


def setup(project=None, on_output: Callable[[str], None] = print) -> int:
    """``pyzed windows setup``: installs uv on Windows if there is no uv or Python there, then makes the
    Windows environment of ``project`` (or of single-file apps). Returns the exit code."""
    if not _platform.is_wsl():
        on_output("This is not WSL: there is nothing to set up.")
        return 1
    found = host()
    if found is None:
        on_output("Windows programs cannot run from this WSL: turn on interop ([interop] enabled=true in "
                  "/etc/wsl.conf) and restart WSL.")
        return 1
    if not found.ready:
        on_output("Installing uv on Windows…")
        if not install_uv(on_output):
            return 1
        found = host()
        assert found is not None
    env = WindowsEnv.for_target(found, project)
    error = env.prepare(on_output)
    if error:
        on_output(error)
        return 1
    on_output(f"Ready: windows open on Windows, with the environment in {to_windows(env.base)}")
    return 0


def reset(project=None, on_output: Callable[[str], None] = print) -> int:
    """``pyzed windows reset``: deletes the Windows environment of ``project`` (made again on the next run)."""
    found = host()
    if found is None or not found.ready:
        on_output("There is no Windows environment to delete.")
        return 0
    env = WindowsEnv.for_target(found, project)
    if env.base.is_dir():
        shutil.rmtree(env.base, ignore_errors=True)
        on_output(f"Deleted {to_windows(env.base)}")
    else:
        on_output("There is no Windows environment to delete.")
    return 0
