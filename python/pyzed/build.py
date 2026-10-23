"""``pyzed build``: package a Pyzed project as a standalone app, with PyInstaller or Nuitka.

The project's ``.venv`` (Python, ``pyzed-ui`` and every dependency) is frozen next to a
small launcher that opens the main form. Two backends do the freezing:

- **PyInstaller** (the default) bundles the Python files as they are: quick builds that
  work everywhere.
- **Nuitka** compiles them to C first: slower builds (it needs a C compiler) for faster code
  and a smaller single file.

Builds are native: run it on Windows for a ``.exe``, on macOS for a ``.app`` and on Linux
for an ELF executable. Every platform and architecture builds on its own machine, so
``workflow()`` writes a GitHub Actions workflow that builds the chosen ``TARGETS``. Android is the
exception: ``build_android`` packs an APK or AAB on any computer (see ``pyzed.android``).

Form handlers are loaded from their ``.py`` files at runtime, so the backends cannot see
what they import. This module reads them with ``ast`` and passes every imported module as
a hidden import, ships the UI folder as data and adds ``ui/``, ``src/`` and the project
root to the search path, so code outside the UI folder is bundled too.

A build runs in three steps: ``prepare`` writes the launcher, the icons (``.ico``, ``.icns``
and a PNG made from one picture), the Windows version file and the splash image to
``build/pyzed/`` and returns a ``Plan`` with the command line; the command runs in the
project's environment (``uv run --with <backend>``); ``finish`` puts the app in
``dist/``, fills in the macOS ``Info.plist`` and packs it in a zip if asked.

Settings come from ``[tool.pyzed.build]`` in ``pyproject.toml``::

    [tool.pyzed.build]
    name = "My App"               # executable / bundle name (default: the project name)
    backend = "pyinstaller"       # or "nuitka"
    onefile = false               # one self-extracting file instead of a folder
    windowed = true               # no console window (Windows, macOS)
    icon = "assets/icon.png"      # one square PNG; .ico and .icns are made from it
    version = "1.2.0"             # default: [project] version
    publisher = "Acme"            # the company in the Windows file properties
    identifier = "com.acme.myapp" # macOS bundle id and Linux app id
    copyright = "© 2026 Acme"
    optimize = 0                  # 1 drops asserts, 2 also docstrings
    slim = true                   # leave out tkinter, test, idlelib... (unused by Pyzed apps)
    exclude = ["numpy.tests"]     # more modules to leave out
    include = ["assets", "data/config.toml"]   # extra files and folders to ship
    hidden-imports = ["mypkg.plugins.csv"]     # modules imported dynamically
    collect = ["mypkg"]           # packages to ship whole (code, data and binaries)
    archive = "zip"               # also pack the app (zip, or tar.gz on Linux and macOS)
    targets = ["windows-x64", "macos-arm64", "linux-x64"]   # what the CI workflow builds
    args = ["--noupx"]            # anything else, passed to the backend as is

    [tool.pyzed.build.splash]
    image = "assets/splash.png"
    duration = 1.5                # seconds, at least
    text = "Loading…"
    native = true                 # also the backend's own splash while the app unpacks

    [tool.pyzed.build.nuitka]     # options for one backend only
    args = ["--lto=yes"]
"""

from __future__ import annotations

import ast
import json
import os
import platform
import plistlib
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .project import Project, Result, _uv, execute, iter_python_files, linux_path, module_name
from . import rendering as _rendering

PYINSTALLER = "pyinstaller>=6.10"
NUITKA = "nuitka>=2.6"
BACKENDS = ("pyinstaller", "nuitka")
BACKEND_LABELS = {"pyinstaller": "PyInstaller", "nuitka": "Nuitka"}
ARCHIVES = ("zip", "tar.gz")
#: Standard library modules a Pyzed app does not use, left out with ``slim``.
#: The icons made from ``icon`` (``app-icon.ico``, ``.icns`` and ``.png``, shipped for the windows).
ICON_NAME = "app-icon"
SLIM_EXCLUDES = ("tkinter", "test", "idlelib", "lib2to3", "ensurepip", "pydoc_data", "turtledemo", "turtle")
#: Parts of Pyzed only Pyzed Design and the command line use, also left out with ``slim`` (unless the UI imports
#: them): the designer's own window and panels, the AI agents, the MCP server and the packager itself.
EDITOR_ONLY = ("pyzed.agents", "pyzed.mcp", "pyzed.cli", "pyzed.build", "pyzed.designer.app",
               "pyzed.designer.agent_panel", "pyzed.designer.agent_tools", "pyzed.designer.lsp",
               "pyzed.designer.intellisense", "pyzed.designer.export_panel", "pyzed.designer.updates",
               "pyzed.designer.welcome", "pyzed.designer.project_panel", "pyzed.designer.project_picker",
               "pyzed.designer.keymap_editor")
#: Modules ``pyzed`` imports by name when they are first used (``pz.game``, ``pz.Dock``...).
LAZY_MODULES = ("pyzed.designer", "pyzed.reference", "pyzed.dock", "pyzed.game", "pyzed.services")


@dataclass(frozen=True)
class Target:
    """A platform and architecture an app can be built for, and the GitHub runner that builds it."""

    id: str
    os: str
    arch: str
    label: str
    runner: str

    @property
    def exe_suffix(self) -> str:
        return ".exe" if self.os == "windows" else ""

    @property
    def machine(self) -> str:
        """The architecture as ``pyzed.updater`` names it: ``x86_64``, ``arm64`` (``aarch64`` on Linux)."""
        if self.arch == "x64":
            return "x86_64"
        return "aarch64" if self.os == "linux" else "arm64"


TARGETS: Tuple[Target, ...] = (
    Target("windows-x64", "windows", "x64", "Windows x64", "windows-latest"),
    Target("windows-arm64", "windows", "arm64", "Windows ARM64", "windows-11-arm"),
    Target("macos-arm64", "macos", "arm64", "macOS Apple silicon", "macos-latest"),
    Target("macos-x64", "macos", "x64", "macOS Intel", "macos-15-intel"),
    # The oldest Ubuntu runners: an app built against an older glibc runs on more distributions.
    Target("linux-x64", "linux", "x64", "Linux x64", "ubuntu-22.04"),
    Target("linux-arm64", "linux", "arm64", "Linux ARM64", "ubuntu-22.04-arm"),
    # Android builds on any computer (``pyzed.android``): an APK or AAB for each processor.
    Target("android-arm64", "android", "arm64", "Android (phones and tablets)", "ubuntu-latest"),
    Target("android-x64", "android", "x64", "Android x86_64 (emulators)", "ubuntu-latest"),
)
BY_TARGET: Dict[str, Target] = {t.id: t for t in TARGETS}


def _arch(machine: str) -> str:
    return "arm64" if machine.lower() in ("arm64", "aarch64", "armv8l", "arm64e") else "x64"


def host_target(project: Optional[Project] = None) -> Target:
    """The target this computer builds: its system and architecture (Linux for a WSL project opened from
    Windows, whose build runs inside WSL)."""
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    if project is not None and project.environment.remote:
        system = "linux"
    return BY_TARGET[f"{system}-{_arch(platform.machine())}"]


LAUNCHER = '''"""Generated by `pyzed build`: opens {name} from the bundled UI folder."""

import os
import sys
from pathlib import Path

if hasattr(sys, "_MEIPASS"):  # PyInstaller
    ROOT = Path(sys._MEIPASS)
elif "__compiled__" in globals():  # Nuitka
    ROOT = Path(__file__).resolve().parent
else:  # not packaged: the project itself
    ROOT = Path(r"{root}")
UI = ROOT / {ui!r}
# Handlers may import helper modules that live next to them, at any time.
sys.path.insert(0, str(UI))

import pyzed as pz  # noqa: E402
from pyzed import designer  # noqa: E402

{setup}{close_splash}
designer.run(ROOT / {main!r}{run_args})
'''

CLOSE_NATIVE_SPLASH = '''
def close_native_splash():
    """Closes the splash the bootloader shows while the app unpacks (PyInstaller, Nuitka onefile)."""
    if "_PYI_SPLASH_IPC" in os.environ:
        import pyi_splash  # type: ignore[import-not-found]

        pyi_splash.close()
    if "NUITKA_ONEFILE_PARENT" in os.environ:
        import tempfile

        flag = os.path.join(tempfile.gettempdir(),
                            "onefile_%d_splash_feedback.tmp" % int(os.environ["NUITKA_ONEFILE_PARENT"]))
        if os.path.exists(flag):
            os.unlink(flag)


close_native_splash()
'''

WORKFLOW = """\
name: Build

# Builds the app for each target with `pyzed build` and keeps the result as an
# artifact (Actions -> this run -> Artifacts). The backends cannot cross-compile, so
# every platform and architecture builds on its own runner.
on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build:
    name: Build ${{ matrix.target }}
    runs-on: ${{ matrix.runner }}
    strategy:
      fail-fast: false
      matrix:
        include:
{matrix}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --locked
      - run: uv run pyzed build --target ${{ matrix.target }}
      - uses: actions/upload-artifact@v4
        with:
          name: {name}-${{ matrix.target }}
          path: dist/
"""

#: With ``archive``: the job may create the release, and each build attaches its archive to it.
RELEASE_PERMISSIONS = """    permissions:
      contents: write
"""
RELEASE_STEP = """      - name: Attach to the GitHub Release
        if: startsWith(github.ref, 'refs/tags/v')
        shell: bash
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # the first build to get here creates the release; the others only upload
          gh release create "$GITHUB_REF_NAME" --title "$GITHUB_REF_NAME" --verify-tag || true
          gh release upload "$GITHUB_REF_NAME" dist/*.{ext} --clobber
"""


@dataclass
class Splash:
    """A splash screen for the packaged app (``[tool.pyzed.build.splash]``)."""

    image: str
    duration: float = 1.5
    text: Optional[str] = None
    #: Also the backend's own splash, shown by the bootloader while the app unpacks (PyInstaller on Windows
    #: and Linux, Nuitka for a single file on Windows); the Pyzed splash follows it.
    native: bool = True

    def to_table(self) -> Dict[str, Any]:
        table: Dict[str, Any] = {"image": self.image, "duration": self.duration}
        if self.text:
            table["text"] = self.text
        if not self.native:
            table["native"] = False
        return table


@dataclass
class BuildOptions:
    """What ``pyzed build`` packages and how (defaults come from ``[tool.pyzed.build]``)."""

    name: Optional[str] = None
    backend: str = "pyinstaller"
    onefile: bool = False
    windowed: bool = True
    icon: Optional[str] = None
    version: Optional[str] = None
    publisher: Optional[str] = None
    identifier: Optional[str] = None
    description: Optional[str] = None
    copyright: Optional[str] = None
    splash: Optional[Splash] = None
    optimize: int = 0
    slim: bool = True
    strip: bool = True
    upx: bool = False
    exclude: List[str] = field(default_factory=list)
    include: List[str] = field(default_factory=list)
    hidden_imports: List[str] = field(default_factory=list)
    collect: List[str] = field(default_factory=list)
    archive: Optional[str] = None
    targets: List[str] = field(default_factory=list)
    args: List[str] = field(default_factory=list)
    #: Options for one backend only: ``{"nuitka": {"args": [...]}}``.
    backend_options: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    clean: bool = True
    #: Keys of ``[tool.pyzed.build]`` this module does not know, written back as they were.
    extra: Dict[str, Any] = field(default_factory=dict)

    KEYS = ("name", "backend", "onefile", "windowed", "icon", "version", "publisher", "identifier", "description",
            "copyright", "splash", "optimize", "slim", "strip", "upx", "exclude", "include", "hidden-imports",
            "collect", "archive", "targets", "args", *BACKENDS)

    @classmethod
    def from_table(cls, table: Dict[str, Any], **overrides: Any) -> "BuildOptions":
        """Options from a ``[tool.pyzed.build]`` table; keyword ``overrides`` that are not ``None`` win."""
        table = dict(table)
        splash = table.get("splash")
        backend = str(table.get("backend", "pyinstaller")).lower()
        opts = cls(
            name=table.get("name"),
            backend=backend if backend in BACKENDS else "pyinstaller",
            onefile=bool(table.get("onefile", False)),
            windowed=bool(table.get("windowed", True)),
            icon=table.get("icon"),
            version=table.get("version"),
            publisher=table.get("publisher"),
            identifier=table.get("identifier"),
            description=table.get("description"),
            copyright=table.get("copyright"),
            splash=Splash(str(splash["image"]), float(splash.get("duration", 1.5)), splash.get("text"),
                          bool(splash.get("native", True)))
            if isinstance(splash, dict) and splash.get("image") else None,
            optimize=max(0, min(2, int(table.get("optimize", 0)))),
            slim=bool(table.get("slim", True)),
            strip=bool(table.get("strip", True)),
            upx=bool(table.get("upx", False)),
            exclude=list(table.get("exclude", [])),
            include=list(table.get("include", [])),
            hidden_imports=list(table.get("hidden-imports", [])),
            collect=list(table.get("collect", [])),
            archive=table.get("archive") if table.get("archive") in ARCHIVES else None,
            targets=[t for t in table.get("targets", []) if t in BY_TARGET],
            args=list(table.get("args", [])),
            backend_options={b: dict(table[b]) for b in BACKENDS if isinstance(table.get(b), dict)},
            extra={k: v for k, v in table.items() if k not in cls.KEYS},
        )
        for key, value in overrides.items():
            if value is not None:
                setattr(opts, key, value)
        return opts

    @classmethod
    def from_project(cls, project: Project, **overrides: Any) -> "BuildOptions":
        """Reads the options from the project's ``[tool.pyzed.build]`` table.

        Keyword ``overrides`` that are not ``None`` replace the values found there.
        """
        return cls.from_table(dict(project.config.get("build", {})), **overrides)

    def to_table(self) -> Dict[str, Any]:
        """The ``[tool.pyzed.build]`` table for these options, without the values left at their default."""
        table: Dict[str, Any] = {}
        default = BuildOptions()
        for key in self.KEYS:
            attr = key.replace("-", "_")
            if key in BACKENDS:
                if self.backend_options.get(key):
                    table[key] = dict(self.backend_options[key])
                continue
            value = getattr(self, attr)
            if key == "splash":
                if value is not None:
                    table[key] = value.to_table()
                continue
            if value != getattr(default, attr) and value not in (None, "", []):
                table[key] = value
        table.update(self.extra)
        return table

    def backend_args(self) -> List[str]:
        """``args`` and the ``args`` of the backend in use."""
        return [*self.args, *self.backend_options.get(self.backend, {}).get("args", [])]

    def excluded(self, used: Sequence[str] = ()) -> List[str]:
        """The modules left out of the app: ``exclude`` and, with ``slim``, unused standard modules (``tkinter``
        stays for PyInstaller's native splash, which draws with Tk) and the editor-only parts of Pyzed that none of
        the modules ``used`` by the UI is in."""
        slim: List[str] = []
        if self.slim:
            slim = [m for m in SLIM_EXCLUDES if not (m == "tkinter" and self.backend == "pyinstaller" and self.splash
                                                      and self.splash.native)]
            slim += [m for m in EDITOR_ONLY if not any(u == m or u.startswith(m + ".") for u in used)]
        return list(dict.fromkeys([*slim, *self.exclude]))


# -- reading and writing pyproject.toml ---------------------------------------------------

def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{_toml_key(k)} = {_toml_value(v)}" for k, v in value.items()) + " }"
    return json.dumps(str(value), ensure_ascii=False)


def _toml_key(key: str) -> str:
    return key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else json.dumps(key)


def toml_table(table: Dict[str, Any], name: str = "tool.pyzed.build") -> str:
    """``table`` as TOML: its values under ``[name]``, then each sub-table under ``[name.key]``."""
    lines = [f"[{name}]"]
    subtables = []
    for key, value in table.items():
        if isinstance(value, dict):
            subtables.append((key, value))
        else:
            lines.append(f"{_toml_key(key)} = {_toml_value(value)}")
    text = "\n".join(lines) + "\n"
    for key, value in subtables:
        text += "\n" + toml_table(value, f"{name}.{_toml_key(key)}")
    return text


def save_options(project: Project, opts: BuildOptions) -> None:
    """Writes ``opts`` to ``[tool.pyzed.build]`` (and its sub-tables) of the project's ``pyproject.toml``,
    replacing those tables and keeping the rest of the file as it is."""
    file = project.root / "pyproject.toml"
    text = file.read_text(encoding="utf-8")
    header = re.compile(r"^\[(?:tool\.pyzed\.build)(?:\.[^\]]+)?\][ \t]*$", re.M)
    any_header = re.compile(r"^\[", re.M)
    spans = []
    for found in header.finditer(text):
        end = any_header.search(text, found.end())
        spans.append((found.start(), end.start() if end else len(text)))
    new = toml_table(opts.to_table())
    if spans:
        start = spans[0][0]
        for begin, end in reversed(spans):
            text = text[:begin] + text[end:]
        text = text[:start] + new + ("\n" if text[start:].strip() else "") + text[start:]
    else:
        text = text.rstrip() + "\n\n" + new
    file.write_text(re.sub(r"\n{3,}", "\n\n", text), encoding="utf-8")
    project.reload()


# -- what the UI imports --------------------------------------------------------------------

def imported_modules(folder: Path) -> Set[str]:
    """Modules imported by the ``.py`` files under ``folder`` (not counting the files themselves)."""
    local = {p.stem for p in iter_python_files(folder)} if folder.is_dir() else set()
    found: Set[str] = set()
    for path in iter_python_files(folder) if folder.is_dir() else ():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.add(node.module)
    return {m for m in found if m.split(".")[0] not in local and m != "__future__"}


# -- the build plan -----------------------------------------------------------------------------

@dataclass
class Plan:
    """A prepared build: the command to run in the project and where its result goes."""

    project: Project
    opts: BuildOptions
    target: Target
    #: ``build/pyzed/``: the launcher, icons, version file and the backend's own files.
    work: Path
    #: ``dist/``.
    dist: Path
    command: List[str] = field(default_factory=list)
    #: Generated icon files by kind (``ico``, ``icns``, ``png``).
    icons: Dict[str, Path] = field(default_factory=dict)
    #: Problems found while preparing that do not stop the build.
    warnings: List[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return app_name(self.project, self.opts)

    @property
    def output(self) -> Path:
        """Where the app ends up: ``dist/<name>/``, ``dist/<name>.exe``, ``dist/<name>.app``..."""
        if self.target.os == "macos" and self.opts.windowed:
            return self.dist / f"{self.name}.app"
        if self.opts.onefile:
            return self.dist / (self.name + self.target.exe_suffix)
        return self.dist / self.name

    @property
    def archive_path(self) -> Optional[Path]:
        if not self.opts.archive:
            return None
        # the name the self-updater looks for (``pyzed.updater.asset_name``): shop-windows-x86_64.zip
        return self.dist / f"{module_name(self.name)}-{self.target.os}-{self.target.machine}.{self.opts.archive}"

    @property
    def version(self) -> str:
        return app_version(self.project, self.opts)


def app_name(project: Project, opts: BuildOptions) -> str:
    return opts.name or project.name


def app_version(project: Project, opts: BuildOptions) -> str:
    return str(opts.version or project.data.get("project", {}).get("version") or "0.1.0")


def app_identifier(project: Project, opts: BuildOptions) -> str:
    """``identifier``, or one made from the publisher and the name (``com.acme.shop``)."""
    if opts.identifier:
        return opts.identifier
    owner = re.sub(r"[^a-z0-9]+", "", (opts.publisher or "pyzed").lower()) or "pyzed"
    return f"com.{owner}.{re.sub(r'[^a-z0-9]+', '', app_name(project, opts).lower()) or 'app'}"


def _numbers(version: str) -> Tuple[int, int, int, int]:
    parts = [int(n) for n in re.findall(r"\d+", version)[:4]]
    return tuple(parts + [0] * (4 - len(parts)))  # type: ignore[return-value]


def windows_version_file(project: Project, opts: BuildOptions) -> str:
    """The ``VSVersionInfo`` PyInstaller writes into the ``.exe``: the Details tab of its properties."""
    name = app_name(project, opts)
    version = app_version(project, opts)
    numbers = _numbers(version)
    strings = {
        "CompanyName": opts.publisher or "",
        "FileDescription": opts.description or project.data.get("project", {}).get("description") or name,
        "FileVersion": version,
        "InternalName": name,
        "LegalCopyright": opts.copyright or "",
        "OriginalFilename": f"{name}.exe",
        "ProductName": name,
        "ProductVersion": version,
    }
    table = ",\n".join(f"          StringStruct({k!r}, {v!r})" for k, v in strings.items())
    return f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
{table}
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def launcher(project: Project, folder: Path, opts: Optional[BuildOptions] = None, *,
             icon: Optional[str] = None) -> Path:
    """Writes the entry script the backend starts from; returns its path.

    ``icon`` is the window icon's file name inside the bundle; ``opts`` adds the splash.
    """
    opts = opts or BuildOptions()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{module_name(project.name)}_launcher.py"
    setup: List[str] = []
    if icon:
        setup.append(f"pz.Window.icon = str(ROOT / {icon!r})")
    if opts.identifier or icon:
        setup.append(f"pz.Window.app_id = {app_identifier(project, opts)!r}")
    for name, value in _rendering.find(project.root).env().items():  # [tool.pyzed.rendering]
        setup.append(f"os.environ.setdefault({name!r}, {value!r})")
    run_args = ""
    splash = opts.splash
    if splash is not None:
        text = f", text={splash.text!r}" if splash.text else ""
        run_args = f", splash=pz.Splash(ROOT / {_splash_name(splash)!r}, duration={splash.duration!r}{text})"
    text = LAUNCHER.format(name=project.name, root=project.root,
                           ui=project.ui_dir.relative_to(project.root).as_posix(),
                           main=project.main_form.relative_to(project.root).as_posix(),
                           setup="".join(line + "\n" for line in setup),
                           close_splash=CLOSE_NATIVE_SPLASH if splash is not None and splash.native else "",
                           run_args=run_args)
    path.write_text(text, encoding="utf-8")
    return path


def _splash_name(splash: Splash) -> str:
    return "splash" + (Path(splash.image).suffix.lower() or ".png")


def has_tkinter(project: Project) -> bool:
    """Whether the project's Python has ``tkinter`` (PyInstaller's native splash needs Tcl/Tk)."""
    python = project.python_executable()
    return python is not None and project._exec([str(python), "-c", "import tkinter"], timeout=30).ok


def native_splash(opts: BuildOptions, target: Target) -> bool:
    """Whether the backend shows its own splash for ``target``: PyInstaller on Windows and Linux (it draws
    with Tk; not on macOS), Nuitka only for a single file on Windows."""
    if opts.splash is None or not opts.splash.native:
        return False
    if opts.backend == "pyinstaller":
        return target.os != "macos"
    return target.os == "windows" and opts.onefile


class _Paths:
    """Turns paths into command line arguments for where the build runs (Linux paths inside WSL)."""

    def __init__(self, project: Project, target: Target) -> None:
        self.remote = project.environment.remote
        self.sep = ";" if target.os == "windows" else ":"

    def __call__(self, path: Path) -> str:
        return linux_path(path) if self.remote else str(path)

    def data(self, source: Path, dest: str) -> str:
        return f"{self(source)}{self.sep}{dest}"


def _assets(project: Project, opts: BuildOptions, plan: Plan) -> List[Tuple[Path, str]]:
    """Writes the icons, the version file and the splash image to the plan's work folder; returns the files to
    ship in the app as ``(source, name inside the app)``."""
    shipped: List[Tuple[Path, str]] = []
    root = project.root
    if opts.icon:
        source = root / opts.icon
        if not source.is_file():
            plan.warnings.append(f"The icon {opts.icon} does not exist; the app keeps the default icon")
        elif source.suffix.lower() in (".ico", ".icns"):
            plan.icons[source.suffix.lower()[1:]] = source
        else:
            from . import _appicon

            try:
                plan.icons = _appicon.write_all(source, plan.work, ICON_NAME)
            except (OSError, ValueError) as err:
                plan.warnings.append(f"Could not make the icons from {opts.icon}: {err}")
            if "png" in plan.icons:
                shipped.append((plan.icons["png"], plan.icons["png"].name))
    if opts.splash is not None:
        source = root / opts.splash.image
        if source.is_file():
            copy = plan.work / _splash_name(opts.splash)
            shutil.copyfile(source, copy)
            shipped.append((copy, copy.name))
        else:
            plan.warnings.append(f"The splash image {opts.splash.image} does not exist; the app starts without it")
            opts.splash = None
    return shipped


def pyzed_modules(project: Project) -> List[str]:
    """The modules of the ``pyzed`` package installed in the project's ``.venv`` (empty if it is not found)."""
    venv = project.venv
    for site in [venv / "Lib" / "site-packages", *sorted(venv.glob("lib/python3*/site-packages"))]:
        package = site / "pyzed"
        if (package / "__init__.py").is_file():
            return sorted(".".join(path.relative_to(site).with_suffix("").parts).removesuffix(".__init__")
                          for path in package.rglob("*.py") if "__pycache__" not in path.parts)
    return []


def _common_modules(project: Project, opts: BuildOptions) -> List[str]:
    return sorted(imported_modules(project.ui_dir) | set(opts.hidden_imports))


def pyinstaller_args(project: Project, opts: BuildOptions, plan: Optional[Plan] = None) -> List[str]:
    """The PyInstaller command line for ``project`` (without the ``pyinstaller`` itself)."""
    plan = plan or _plan(project, opts)
    target, work, p = plan.target, plan.work, _Paths(project, plan.target)
    shipped = _assets(project, opts, plan)
    entry = launcher(project, work, opts, icon=f"{ICON_NAME}.png" if "png" in plan.icons else None)
    root = project.root
    args: List[str] = [p(entry), "--name", plan.name, "--noconfirm",
                       "--distpath", p(plan.dist), "--workpath", p(work / "pyinstaller"), "--specpath", p(work)]
    if opts.clean:
        args.append("--clean")
    args.append("--onefile" if opts.onefile else "--onedir")
    if opts.windowed:
        args.append("--windowed")
    icon = plan.icons.get("ico" if target.os == "windows" else "icns" if target.os == "macos" else "png")
    if icon is not None and target.os != "linux":
        args += ["--icon", p(icon)]
    if target.os == "windows" and (opts.version or opts.publisher or opts.copyright or opts.description
                                   or project.data.get("project", {}).get("version")):
        version_file = work / "version.txt"
        version_file.write_text(windows_version_file(project, opts), encoding="utf-8")
        args += ["--version-file", p(version_file)]
    if target.os == "macos":
        args += ["--osx-bundle-identifier", app_identifier(project, opts)]
    if native_splash(opts, target):
        assert opts.splash is not None
        if has_tkinter(project):
            args += ["--splash", p(work / _splash_name(opts.splash))]
        else:
            plan.warnings.append("PyInstaller's early splash draws with Tk, which the project's Python lacks: the "
                                 "app shows only the Pyzed splash. Use a Python with tkinter (uv python install, or "
                                 "the python3-tk package of your system)")
    if opts.optimize:
        args += ["--optimize", str(opts.optimize)]
    if opts.strip and target.os != "windows":
        args.append("--strip")
    if not opts.upx:
        args.append("--noupx")
    for folder in project.paths():
        args += ["--paths", p(folder)]
    ui_rel = project.ui_dir.relative_to(root).as_posix()
    args += ["--add-data", p.data(project.ui_dir, ui_rel)]
    for source, _ in shipped:  # at the root of the bundle, with their own names
        args += ["--add-data", p.data(source, ".")]
    for item in opts.include:
        source = root / item
        dest = Path(item).as_posix() if source.is_dir() else (Path(item).parent.as_posix() or ".")
        args += ["--add-data", p.data(source, dest)]
    # pyzed's themes and templates are data files; its designer is loaded by the launcher.
    args += ["--collect-data", "pyzed"]
    excluded = opts.excluded(_common_modules(project, opts))
    found = pyzed_modules(project)
    if found:  # every module of the project's pyzed but the ones left out
        for module in found:
            if not any(module == m or module.startswith(m + ".") for m in excluded):
                args += ["--hidden-import", module]
    else:
        args += ["--collect-submodules", "pyzed"]
    own = module_name(project.name)
    if project.src_dir is not None and (project.src_dir / own).is_dir():
        args += ["--collect-submodules", own]
    for module in _common_modules(project, opts):
        args += ["--hidden-import", module]
    for package in opts.collect:
        args += ["--collect-all", package]
    args += ["--copy-metadata", "pyzed-ui"]  # pz.__version__
    for module in excluded:
        args += ["--exclude-module", module]
    return args + opts.backend_args()


def nuitka_args(project: Project, opts: BuildOptions, plan: Optional[Plan] = None) -> List[str]:
    """The Nuitka command line for ``project`` (without ``python -m nuitka``)."""
    plan = plan or _plan(project, opts)
    target, work, p = plan.target, plan.work, _Paths(project, plan.target)
    shipped = _assets(project, opts, plan)
    entry = launcher(project, work, opts, icon=f"{ICON_NAME}.png" if "png" in plan.icons else None)
    root = project.root
    bundle = target.os == "macos" and opts.windowed
    mode = ("app" if bundle else "onefile") if opts.onefile else ("app-dist" if bundle else "standalone")
    name = plan.name
    args: List[str] = [p(entry), f"--mode={mode}", f"--output-dir={p(work / 'nuitka')}",
                       f"--output-filename={name}", "--assume-yes-for-downloads"]
    if not opts.onefile or bundle:
        args.append(f"--output-folder-name={name}")
    if opts.clean:
        args.append("--remove-output")
    if target.os == "windows":
        args.append(f"--windows-console-mode={'disable' if opts.windowed else 'force'}")
        if "ico" in plan.icons:
            args.append(f"--windows-icon-from-ico={p(plan.icons['ico'])}")
        version = app_version(project, opts)
        args += [f"--product-name={name}", f"--file-version={'.'.join(map(str, _numbers(version)))}",
                 f"--product-version={'.'.join(map(str, _numbers(version)))}",
                 f"--file-description={opts.description or project.data.get('project', {}).get('description') or name}"]
        if opts.publisher:
            args.append(f"--company-name={opts.publisher}")
        if opts.copyright:
            args.append(f"--copyright={opts.copyright}")
        if native_splash(opts, target):
            assert opts.splash is not None
            args.append(f"--onefile-windows-splash-screen-image={p(work / _splash_name(opts.splash))}")
    elif target.os == "macos":
        if "icns" in plan.icons:
            args.append(f"--macos-app-icon={p(plan.icons['icns'])}")
        if bundle:
            args += [f"--macos-app-name={name}", f"--macos-signed-app-name={app_identifier(project, opts)}",
                     f"--macos-app-version={app_version(project, opts)}"]
            if not opts.windowed:
                args.append("--macos-app-console-mode=force")
    # Linux: Nuitka's --linux-app-icon only applies to its app modes; the launcher sets the window icon.
    if opts.optimize >= 1:
        args.append("--python-flag=no_asserts")
    if opts.optimize >= 2:
        args.append("--python-flag=no_docstrings")
    if opts.upx:
        args.append("--enable-plugins=upx")
    if not opts.strip:
        args.append("--unstripped")
    ui_rel = project.ui_dir.relative_to(root).as_posix()
    args.append(f"--include-data-dir={p(project.ui_dir)}={ui_rel}")
    # The handlers' .py files are data: Nuitka leaves .py files out of data folders unless told.
    args.append(f"--include-data-files={p(project.ui_dir)}={ui_rel}/=**/*.py")
    for source, inside in shipped:
        args.append(f"--include-data-files={p(source)}={inside}")
    for item in opts.include:
        source = root / item
        if source.is_dir():
            args.append(f"--include-data-dir={p(source)}={Path(item).as_posix()}")
        else:
            args.append(f"--include-data-files={p(source)}={Path(item).as_posix()}")
    # pyzed's data files, the modules it imports by name and its version (pz.__version__)
    args += ["--include-package-data=pyzed", *(f"--include-module={m}" for m in LAZY_MODULES),
             "--include-package=pyzed.shading", "--include-distribution-metadata=pyzed-ui"]
    own = module_name(project.name)
    if project.src_dir is not None and (project.src_dir / own).is_dir():
        args.append(f"--include-package={own}")
    for module in _common_modules(project, opts):
        args.append(f"--include-module={module}")
    for package in opts.collect:
        args += [f"--include-package={package}", f"--include-package-data={package}"]
    excluded = opts.excluded(_common_modules(project, opts))
    if excluded:
        args.append(f"--nofollow-import-to={','.join(excluded)}")
    return args + opts.backend_args()


def _plan(project: Project, opts: BuildOptions, target: Optional[Target] = None) -> Plan:
    target = target or host_target(project)
    work = project.root / "build" / "pyzed"
    work.mkdir(parents=True, exist_ok=True)
    return Plan(project, opts, target, work, project.root / "dist")


def prepare(project: Project, opts: Optional[BuildOptions] = None) -> Plan:
    """Writes what the build needs to ``build/pyzed/`` and returns the plan with its command line."""
    opts = opts or BuildOptions.from_project(project)
    plan = _plan(project, opts)
    plan.command = command(project, opts, plan)
    return plan


def command(project: Project, opts: BuildOptions, plan: Optional[Plan] = None) -> List[str]:
    """The backend's command line, run with ``uv run --with <backend>`` inside the project's environment."""
    plan = plan or _plan(project, opts)
    uv = project._uv_command() if project.environment.remote else _uv()
    if opts.backend == "nuitka":
        extra = ["--with", "zstandard"] if opts.onefile else []
        if plan.target.os == "linux":
            extra += ["--with", "patchelf"]  # Nuitka fixes the libraries' paths with it
        return [uv, "run", "--with", NUITKA, *extra, "python", "-m", "nuitka", *nuitka_args(project, opts, plan)]
    return [uv, "run", "--with", PYINSTALLER, "pyinstaller", *pyinstaller_args(project, opts, plan)]


def environment(plan: Plan) -> Dict[str, str]:
    """Variables the build command needs: Nuitka finds the project's folders on ``PYTHONPATH``."""
    if plan.opts.backend != "nuitka":
        return {}
    p = _Paths(plan.project, plan.target)
    sep = ":" if p.remote else os.pathsep
    return {"PYTHONPATH": sep.join(p(folder) for folder in plan.project.paths())}


def finish(plan: Plan) -> List[str]:
    """After the backend: moves Nuitka's result to ``dist/``, fills in the macOS ``Info.plist`` and
    packs the archive; returns a line for each thing done."""
    done: List[str] = []
    opts, target = plan.opts, plan.target
    plan.dist.mkdir(parents=True, exist_ok=True)
    if opts.backend == "nuitka":
        built = plan.work / "nuitka"
        if target.os == "macos" and opts.windowed:
            source = built / f"{plan.name}.app"
        elif opts.onefile:
            source = built / (plan.name + target.exe_suffix)
        else:
            source = built / plan.name
            if not source.exists():
                source = built / f"{plan.name}.dist"
        if source.exists():
            if plan.output.exists():
                shutil.rmtree(plan.output) if plan.output.is_dir() else plan.output.unlink()
            shutil.move(str(source), str(plan.output))
    if target.os == "macos" and plan.output.suffix == ".app":
        info = plan.output / "Contents" / "Info.plist"
        if info.is_file():
            with info.open("rb") as file:
                data = plistlib.load(file)
            data.update({"CFBundleShortVersionString": plan.version, "CFBundleVersion": plan.version,
                         "CFBundleDisplayName": plan.name, "CFBundleIdentifier": app_identifier(plan.project, opts),
                         "NSHighResolutionCapable": True})
            if opts.copyright:
                data["NSHumanReadableCopyright"] = opts.copyright
            with info.open("wb") as file:
                plistlib.dump(data, file)
            done.append(f"Info.plist: {plan.version}")
    if plan.archive_path is not None and plan.output.exists():
        archive = plan.archive_path
        if archive.exists():
            archive.unlink()
        base = str(archive)[: -len("." + opts.archive)] if opts.archive else str(archive)
        if opts.archive == "zip" and target.os == "macos" and shutil.which("ditto"):
            # keeps the bundle's symlinks and signature, which a plain zip would break
            execute(["ditto", "-c", "-k", "--keepParent", str(plan.output), str(archive)])
        else:
            shutil.make_archive(base, "gztar" if opts.archive == "tar.gz" else "zip", root_dir=plan.dist,
                                base_dir=plan.output.name)
        done.append(f"Packed {archive.name}")
    return done


def size_of(path: Path) -> int:
    """The size of a file, or of everything in a folder, in bytes."""
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file() and not f.is_symlink())


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def output(project: Project, opts: BuildOptions) -> Path:
    """Where the app ends up for this computer (``dist/<name>/``, ``dist/<name>.exe``, ``dist/<name>.app``...)."""
    return Plan(project, opts, host_target(project), project.root / "build" / "pyzed", project.root / "dist").output


def build(project: Project, opts: Optional[BuildOptions] = None) -> Result:
    """Packages ``project`` for this computer and returns the backend's output."""
    opts = opts or BuildOptions.from_project(project)
    if not project.main_form.exists():
        return Result([], 1, f"{project.main_form} does not exist; set [tool.pyzed] main in pyproject.toml")
    plan = prepare(project, opts)
    env = environment(plan)
    if project.environment.remote:
        result = execute(project.environment.command(plan.command, project.root, env))
    else:
        result = _execute_with(plan.command, project.root, env)
    if not result.ok:
        return result
    notes = [*plan.warnings, *finish(plan)]
    return Result(result.args, result.code, "\n".join(filter(None, [result.output, *notes])))


def android_options(opts: BuildOptions):
    """``[tool.pyzed.build.android]`` as ``pyzed.android.AndroidOptions``."""
    from . import android

    return android.AndroidOptions.from_table(dict(opts.extra.get("android") or {}))


def android_output(project: Project, opts: BuildOptions) -> Path:
    """Where the Android app ends up: ``dist/<name>.apk`` (or ``.aab``)."""
    return project.root / "dist" / f"{module_name(app_name(project, opts))}.{android_options(opts).format}"


def site_packages(project: Project) -> Optional[Path]:
    """The ``site-packages`` of the project's ``.venv``, if it has one."""
    venv = project.venv
    for site in [venv / "Lib" / "site-packages", *sorted(venv.glob("lib/python3*/site-packages"))]:
        if site.is_dir():
            return site
    return None


def build_android(project: Project, opts: Optional[BuildOptions] = None, abis: Optional[Sequence[str]] = None, *,
                  report=print) -> Result:
    """Packs ``project`` as an Android app (``dist/<name>.apk`` or ``.aab``) for ``abis`` (default: the project's)."""
    from . import android

    opts = opts or BuildOptions.from_project(project)
    settings = android_options(opts)
    if project.script is None and not project.main_form.exists():
        return Result([], 1, f"{project.main_form} does not exist; set [tool.pyzed] main in pyproject.toml")
    notes: List[str] = []
    site = site_packages(project)
    if site is not None:
        compiled = android.binary_packages(site)
        if compiled:
            notes.append("Left out (compiled for this computer, not for Android): " + ", ".join(compiled))
    icon = project.root / opts.icon if opts.icon else None
    if icon is not None and (icon.suffix.lower() != ".png" or not icon.is_file()):
        notes.append(f"The icon {opts.icon} is not a PNG file; the app keeps Android's default icon")
        icon = None
    out = android_output(project, opts)
    try:
        signing = (android.Signing.release(project.root / settings.keystore, settings.key_alias)
                   if settings.keystore else None)
        app = android.project_app(project, project.root / "build" / "pyzed" / "android" / "app")
        android.package(app, out, name=app_name(project, opts),
                        package=android.package_name(settings.package or app_identifier(project, opts)),
                        version=app_version(project, opts), code=settings.version_code, icon=icon,
                        abis=list(abis or settings.abis), fmt=settings.format, signing=signing,
                        min_sdk=settings.min_sdk, site_packages=site, forms=project.script is None, report=report)
    except android.AndroidError as err:
        return Result([], 1, str(err))
    notes.append(f"Signed with {settings.keystore}" if settings.keystore else
                 "Signed with the debug key: fine for trying it on a phone; set keystore in "
                 "[tool.pyzed.build.android] for Google Play")
    return Result([], 0, "\n".join(notes))


def _execute_with(args: Sequence[str], cwd: Path, env: Dict[str, str]) -> Result:
    if not env:
        return execute(args, cwd)
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        return execute(args, cwd)
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def workflow(project: Project, path: Optional[Path] = None, targets: Optional[Sequence[str]] = None) -> Path:
    """Writes a GitHub Actions workflow that builds the app for ``targets`` (default: the project's ``targets``,
    or Windows, macOS and Linux on x64 and Apple silicon). With ``archive``, a version tag also attaches each
    archive to the tag's GitHub Release."""
    path = path or project.root / ".github" / "workflows" / "build.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    opts = BuildOptions.from_project(project)
    chosen = list(targets or opts.targets or ("windows-x64", "macos-arm64", "linux-x64"))
    matrix = "\n".join(f"          - {{ target: {t}, runner: {BY_TARGET[t].runner} }}"
                       for t in chosen if t in BY_TARGET)
    text = WORKFLOW.replace("{matrix}", matrix).replace("{name}", module_name(project.name))
    if opts.archive:
        text = text.replace("    runs-on: ${{ matrix.runner }}\n", "    runs-on: ${{ matrix.runner }}\n" + RELEASE_PERMISSIONS)
        text += RELEASE_STEP.replace("{ext}", opts.archive)
    path.write_text(text, encoding="utf-8")
    return path


def describe(args: Sequence[str]) -> str:
    """A copy-pasteable form of ``args``."""
    import shlex

    return " ".join(shlex.quote(str(a)) for a in args)
