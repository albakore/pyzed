"""The package managers Pyzed knows: which of each one's executables runs, how to install or update it, and the
defaults it gets.

Each package manager is a ``PackageManager`` in a registry. uv comes first: Pyzed's projects are uv projects
(``pyproject.toml`` and ``uv.lock``), so ``default()`` is uv while no other one can run them. A manager can have
more than one executable (``SOURCES``): the one included with Pyzed Design, the one installed on this computer
(it updates on its own, apart from the editor) and one at a path of your choice. Its ``fields`` are its settings
(which executable, the package index...), shown in Pyzed Design's Settings → Package managers, and ``env`` turns
them into the environment variables every command gets::

    from pyzed import package_managers as pm

    pm.configure("uv", source="system", prerelease=True)
    pm.find("uv")            # the uv on this computer (the included one while there is none)
    pm.get("uv").installations(pm.values("uv"))   # every uv found, with its version

Adding a manager is a subclass with its ``name``, ``executable`` and ``fields`` (and ``env``, ``install``,
``update`` when it has them) given to ``register``; the Settings page shows it without more code.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from .project import Result

#: Where an executable comes from: "auto" (this computer's, else the included one), "bundled" (included with
#: Pyzed), "system" (installed on this computer) or "custom" (the manager's ``path`` setting).
SOURCES = ("auto", "bundled", "system", "custom")
#: How uv puts packages in an environment ("" lets uv choose; see ``UV_LINK_MODE``).
LINK_MODES = ("", "copy", "hardlink", "symlink", "clone")


@dataclass(frozen=True)
class Field:
    """A setting of a package manager. ``kind`` is "text", "switch" or "select" (``options`` lists
    ``(value, label)`` pairs); ``placeholder`` is the hint of an empty "text"; ``shown_when`` = ``(key, value)``
    shows it only while that other setting has that value."""

    key: str
    title: str
    description: str = ""
    kind: str = "text"
    default: Any = ""
    options: Tuple[Tuple[Any, str], ...] = ()
    placeholder: str = ""
    shown_when: Optional[Tuple[str, Any]] = None

    def clean(self, value: Any) -> Any:
        """``value`` made valid for this field (its default if it can't be)."""
        if self.kind == "switch":
            return bool(value) if isinstance(value, (bool, int)) else self.default
        if self.kind == "select":
            return value if value in [v for v, _ in self.options] else self.default
        return value if isinstance(value, str) else self.default


@dataclass(frozen=True)
class Installation:
    """An executable of a package manager: where it comes from (one of ``SOURCES`` but "auto"), its path
    (``None`` when there is none) and its version."""

    source: str
    path: Optional[str]
    version: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.path is not None


#: The settings every package manager has: which executable runs, and its path when it is a custom one.
SOURCE_FIELDS = (
    Field("source", "Executable to use", "Automatic: this computer's when it is installed, else the one included "
          "with Pyzed", kind="select", default="auto",
          options=(("auto", "Automatic"), ("bundled", "Included with Pyzed"), ("system", "This computer's"),
                   ("custom", "Custom path"))),
    Field("path", "Path of the custom executable", "Enter saves it", placeholder="/path/to/executable",
          shown_when=("source", "custom")),
)


class PackageManager:
    """A package manager. Subclasses set the class attributes and override what the manager has."""

    #: Its id in the registry and the settings ("uv").
    name = ""
    #: How it is shown.
    title = ""
    #: One line on what it does.
    description = ""
    #: The executable's name, without ".exe".
    executable = ""
    #: Whether it can create and run Pyzed's projects (``pyproject.toml`` with a lock file).
    projects = False
    #: Its settings: ``SOURCE_FIELDS`` and its own.
    fields: Tuple[Field, ...] = SOURCE_FIELDS

    def field(self, key: str) -> Field:
        return next(f for f in self.fields if f.key == key)

    def defaults(self) -> Dict[str, Any]:
        return {f.key: f.default for f in self.fields}

    def clean(self, values: Any) -> Dict[str, Any]:
        """The known settings of ``values``, each made valid (only those given)."""
        if not isinstance(values, dict):
            return {}
        return {f.key: f.clean(values[f.key]) for f in self.fields if f.key in values}

    # -- its executables ------------------------------------------------------------------------
    def bundled(self) -> Optional[str]:
        """The executable included with Pyzed (``None``: it includes none)."""
        return None

    def system(self) -> Optional[str]:
        """The executable installed on this computer (on ``PATH``, not the included one)."""
        found = shutil.which(self.executable)
        return found if found and not _same(found, self.bundled()) else None

    def custom(self, values: Dict[str, Any]) -> Optional[str]:
        """The executable at the ``path`` setting, if that file exists."""
        path = str(values.get("path") or "").strip()
        return str(Path(path).expanduser()) if path and Path(path).expanduser().is_file() else None

    def find(self, values: Dict[str, Any]) -> Optional[str]:
        """The executable of the ``source`` setting. One that isn't there falls back to "auto": this computer's,
        else the included one, so projects keep working."""
        chosen = {"bundled": self.bundled, "system": self.system,
                  "custom": lambda: self.custom(values)}.get(values.get("source", "auto"))
        return (chosen() if chosen else None) or self.system() or self.bundled()

    def source_of(self, path: Optional[str], values: Dict[str, Any]) -> Optional[str]:
        """Where the executable at ``path`` comes from ("bundled", "system" or "custom"), if any of them."""
        for source, where in (("custom", lambda: self.custom(values)), ("bundled", self.bundled),
                              ("system", self.system)):
            if _same(path, where()):
                return source
        return None

    def installations(self, values: Dict[str, Any]) -> List[Installation]:
        """The included executable, this computer's and the custom one (when a path is set), with versions."""
        found = [Installation("bundled", self.bundled()), Installation("system", self.system())]
        if str(values.get("path") or "").strip():
            found.append(Installation("custom", self.custom(values)))
        return [replace(i, version=version(i.path)) for i in found]

    # -- installing and updating ----------------------------------------------------------------
    @property
    def can_install(self) -> bool:
        """Whether Pyzed can install it on this computer (``install``)."""
        return type(self).install is not PackageManager.install

    @property
    def can_update(self) -> bool:
        """Whether Pyzed can update this computer's (``update``)."""
        return type(self).update is not PackageManager.update

    def install(self) -> "Result":
        """Installs it on this computer."""
        from . import project as _project

        return _project.Result([self.executable], 127, f"Pyzed can't install {self.title}")

    def update(self) -> "Result":
        """Updates this computer's."""
        from . import project as _project

        return _project.Result([self.executable], 127, f"Pyzed can't update {self.title}")

    # -- its defaults ---------------------------------------------------------------------------
    def env(self, values: Dict[str, Any]) -> Dict[str, str]:
        """The environment variables that give it the defaults of ``values``."""
        return {}


class Uv(PackageManager):
    """uv: Python, the packages, the virtual environments and the tools of Pyzed's projects."""

    name = "uv"
    title = "uv"
    description = ("Pyzed's projects are uv projects (pyproject.toml and uv.lock): uv installs Python, the packages "
                   "and the tools")
    executable = "uv"
    projects = True
    fields = SOURCE_FIELDS + (
        Field("python", "Python of new projects", "Such as 3.13; empty: the newest uv finds or installs",
              placeholder="3.13"),
        Field("index_url", "Package index", "Instead of PyPI, such as a company mirror",
              placeholder="https://pypi.org/simple"),
        Field("extra_index_url", "More package indexes", "Looked in too, separated by spaces"),
        Field("prerelease", "Allow pre-releases", "Of every package, not only the ones asked with a pre-release "
              "version", kind="switch", default=False),
        Field("offline", "Offline", "Only the packages already downloaded", kind="switch", default=False),
        Field("link_mode", "How packages are installed", "Copy is the safest across drives; links save space",
              kind="select", options=(("", "Automatic"), ("copy", "Copy"), ("hardlink", "Hard link"),
                                      ("symlink", "Symbolic link"), ("clone", "Clone"))),
    )

    def bundled(self) -> Optional[str]:
        """The uv next to Pyzed Design's executable, or the ``uv`` package of its Python."""
        from . import project as _project

        found = _project._bundled("uv")
        if found:
            return found
        try:
            from uv import find_uv_bin  # type: ignore[import-not-found]

            return find_uv_bin()
        except Exception:  # noqa: BLE001 - not installed, or installed without its binary
            return None

    def system(self) -> Optional[str]:
        """On ``PATH``, or where uv's installer puts it (``~/.local/bin``), which may not be on this process's
        ``PATH`` yet."""
        from . import project as _project

        return super().system() or _project._installed_uv()

    def install(self) -> "Result":
        """uv's official installer (needs the network)."""
        from . import project as _project

        return _project.install_uv()

    def update(self) -> "Result":
        """``uv self update`` (a uv installed by pip, Homebrew or winget updates with them instead, and says so)."""
        from . import project as _project

        uv = self.system()
        if uv is None:
            return _project.Result(["uv", "self", "update"], 127, "uv is not installed on this computer")
        return _project.execute([uv, "self", "update"], timeout=300)

    def env(self, values: Dict[str, Any]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        if str(values.get("index_url") or "").strip():
            out["UV_DEFAULT_INDEX"] = values["index_url"].strip()
        if str(values.get("extra_index_url") or "").split():
            out["UV_INDEX"] = " ".join(values["extra_index_url"].split())
        if values.get("prerelease"):
            out["UV_PRERELEASE"] = "allow"
        if values.get("offline"):
            out["UV_OFFLINE"] = "1"
        if values.get("link_mode"):
            out["UV_LINK_MODE"] = values["link_mode"]
        return out


# -- the registry and the settings in use ----------------------------------------------------------

_managers: Dict[str, PackageManager] = {}
#: Each manager's settings, only those that differ from its defaults.
_values: Dict[str, Dict[str, Any]] = {}
#: The manager of Pyzed's projects (see ``default``).
_default = "uv"
#: ``--version`` by path and modification time, so the Settings page doesn't run them on every frame.
_versions: Dict[Tuple[str, float], Optional[str]] = {}
#: Called when the settings change.
_listeners: List[Callable[[], None]] = []


def register(manager: PackageManager) -> PackageManager:
    """Adds ``manager`` to the registry (replacing one with its name); returns it."""
    _managers[manager.name] = manager
    return manager


def get(name: str) -> PackageManager:
    """The manager called ``name`` (``KeyError`` if there is none)."""
    return _managers[name]


def managers() -> List[PackageManager]:
    """Every registered manager, in the order they were added."""
    return list(_managers.values())


def project_managers() -> List[PackageManager]:
    """The managers that can create and run Pyzed's projects."""
    return [m for m in _managers.values() if m.projects]


def default() -> PackageManager:
    """The manager of Pyzed's projects: the chosen one, if it can run them, else uv."""
    chosen = _managers.get(_default)
    return chosen if chosen is not None and chosen.projects else _managers["uv"]


def values(name: str) -> Dict[str, Any]:
    """The settings of manager ``name``: its defaults with the configured ones over them."""
    return {**get(name).defaults(), **_values.get(name, {})}


def configure(name: str, **changes: Any) -> Dict[str, Any]:
    """Changes settings of manager ``name``; returns all of them."""
    manager = get(name)
    merged = {**_values.get(name, {}), **manager.clean(changes)}
    _values[name] = {k: v for k, v in merged.items() if v != manager.field(k).default}
    return values(name)


def load(table: Any = None, default_name: str = "uv") -> None:
    """Uses the settings of ``table`` (``{manager: {setting: value}}``, unknown ones are left out) and
    ``default_name`` as the manager of projects; nothing given puts every default back."""
    global _default
    _values.clear()
    if isinstance(table, dict):
        for name, given in table.items():
            if name in _managers:
                configure(name, **(given if isinstance(given, dict) else {}))
    _default = default_name if isinstance(default_name, str) else "uv"


def clean(table: Any) -> Dict[str, Dict[str, Any]]:
    """``table`` with only known managers and the valid settings that differ from their defaults (as saved by the
    designer)."""
    if not isinstance(table, dict):
        return {}
    out = {}
    for name, given in table.items():
        if name in _managers:
            manager = _managers[name]
            settings = {k: v for k, v in manager.clean(given).items() if v != manager.field(k).default}
            if settings:
                out[name] = settings
    return out


def find(name: str = "uv") -> Optional[str]:
    """The executable of manager ``name`` that runs its commands (see ``PackageManager.find``)."""
    return get(name).find(values(name))


def source_of(path: Optional[str], name: str = "uv") -> Optional[str]:
    """Where the executable of ``name`` at ``path`` comes from ("bundled", "system" or "custom")."""
    return get(name).source_of(path, values(name))


def environment() -> Dict[str, str]:
    """The environment variables of every manager's settings (each one sets only its own)."""
    out: Dict[str, str] = {}
    for manager in _managers.values():
        out.update(manager.env(values(manager.name)))
    return out


def version(path: Optional[str]) -> Optional[str]:
    """``<path> --version`` (remembered until the file changes)."""
    if path is None:
        return None
    try:
        key = (path, os.path.getmtime(path))
    except OSError:
        return None
    if key not in _versions:
        from . import project as _project

        _versions[key] = _project._version(path)
    return _versions[key]


def _same(a: Optional[str], b: Optional[str]) -> bool:
    return a is not None and b is not None and os.path.normcase(os.path.abspath(a)) == \
        os.path.normcase(os.path.abspath(b))


def labels(fields: Sequence[Field]) -> List[str]:
    """Every text of ``fields`` that is shown (titles, descriptions and option labels), to translate them."""
    out: List[str] = []
    for f in fields:
        out += [f.title, f.description, *[label for _, label in f.options]]
    return [text for text in out if text]


UV = register(Uv())
