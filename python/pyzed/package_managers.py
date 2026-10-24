"""The package manager of Pyzed's projects, which one is used and the defaults it gets.

Pyzed's projects are uv projects (``pyproject.toml`` and ``uv.lock``), so their package manager is uv. There can be
more than one: the uv included with Pyzed Design, the one installed on this computer (it updates on its own, apart
from the editor) and one at a path of your choice. ``UvSettings`` says which one to use and the defaults every uv
command gets (the package index, pre-releases, offline...); Pyzed Design sets it from Settings → Package managers::

    from pyzed import package_managers

    package_managers.configure(package_managers.UvSettings(source="system", prerelease=True))
    package_managers.find()        # the uv on this computer (the included one while there is none)
    package_managers.managers()    # every uv found, with its version
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from .project import Result

#: Where the uv comes from: "auto" (this computer's, else the included one), "bundled" (included with Pyzed),
#: "system" (installed on this computer) or "custom" (``UvSettings.path``).
SOURCES = ("auto", "bundled", "system", "custom")
#: How uv puts packages in an environment ("" lets uv choose; see ``UV_LINK_MODE``).
LINK_MODES = ("", "copy", "hardlink", "symlink", "clone")


@dataclass(frozen=True)
class UvSettings:
    """Which uv runs the projects' commands and the defaults they get ("" or ``False``: uv's own)."""

    #: One of ``SOURCES``.
    source: str = "auto"
    #: The uv executable when ``source`` is "custom".
    path: str = ""
    #: The Python of new projects (``uv init --python``), such as "3.13".
    python: str = ""
    #: The package index instead of PyPI (``UV_DEFAULT_INDEX``).
    index_url: str = ""
    #: More indexes to look in, separated by spaces (``UV_INDEX``).
    extra_index_url: str = ""
    #: Allow pre-release versions of every package (``UV_PRERELEASE=allow``).
    prerelease: bool = False
    #: Use only the packages already downloaded, without the network (``UV_OFFLINE``).
    offline: bool = False
    #: One of ``LINK_MODES`` (``UV_LINK_MODE``).
    link_mode: str = ""

    def __post_init__(self) -> None:
        if self.source not in SOURCES:
            object.__setattr__(self, "source", "auto")
        if self.link_mode not in LINK_MODES:
            object.__setattr__(self, "link_mode", "")

    def env(self) -> Dict[str, str]:
        """The environment variables that give uv these defaults."""
        out: Dict[str, str] = {}
        if self.index_url.strip():
            out["UV_DEFAULT_INDEX"] = self.index_url.strip()
        if self.extra_index_url.split():
            out["UV_INDEX"] = " ".join(self.extra_index_url.split())
        if self.prerelease:
            out["UV_PRERELEASE"] = "allow"
        if self.offline:
            out["UV_OFFLINE"] = "1"
        if self.link_mode:
            out["UV_LINK_MODE"] = self.link_mode
        return out


@dataclass(frozen=True)
class Manager:
    """A uv Pyzed can use: where it comes from (one of ``SOURCES`` but "auto"), its path (``None`` when there is
    none) and its version."""

    source: str
    path: Optional[str]
    version: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.path is not None


_settings = UvSettings()
#: ``uv --version`` by path and modification time, so the Settings page doesn't run uv on every frame.
_versions: Dict[Tuple[str, float], Optional[str]] = {}


def settings() -> UvSettings:
    """The uv settings in use."""
    return _settings


def configure(new: Optional[UvSettings] = None, **changes: object) -> UvSettings:
    """Uses ``new`` (or the current settings with ``changes``) from now on; returns them."""
    global _settings
    _settings = new if new is not None else replace(_settings, **changes)  # type: ignore[arg-type]
    return _settings


def _same(a: Optional[str], b: Optional[str]) -> bool:
    return a is not None and b is not None and os.path.normcase(os.path.abspath(a)) == \
        os.path.normcase(os.path.abspath(b))


def bundled() -> Optional[str]:
    """The uv included with Pyzed: next to Pyzed Design's executable, or the ``uv`` package of its Python."""
    from . import project as _project

    found = _project._bundled("uv")
    if found:
        return found
    try:
        from uv import find_uv_bin  # type: ignore[import-not-found]

        return find_uv_bin()
    except Exception:  # noqa: BLE001 - not installed, or installed without its binary
        return None


def system() -> Optional[str]:
    """The uv installed on this computer: on ``PATH`` (when it is not the included one) or where uv's installer
    puts it (``~/.local/bin``), which may not be on this process's ``PATH`` yet."""
    from . import project as _project

    found = shutil.which("uv")
    if found and not _same(found, bundled()):
        return found
    return _project._installed_uv()


def custom() -> Optional[str]:
    """The uv at ``UvSettings.path``, if that file exists."""
    path = _settings.path.strip()
    return str(Path(path).expanduser()) if path and Path(path).expanduser().is_file() else None


def find(source: Optional[str] = None) -> Optional[str]:
    """The uv of ``source`` (the configured one by default). One that isn't there falls back to "auto": this
    computer's uv, else the included one, so projects keep working."""
    source = source or _settings.source
    chosen = {"bundled": bundled, "system": system, "custom": custom}.get(source)
    return (chosen() if chosen else None) or system() or bundled()


def source_of(path: Optional[str]) -> Optional[str]:
    """Where the uv at ``path`` comes from ("bundled", "system" or "custom"), ``None`` if it is none of them."""
    for source, where in (("custom", custom), ("bundled", bundled), ("system", system)):
        if _same(path, where()):
            return source
    return None


def version(path: Optional[str]) -> Optional[str]:
    """``uv --version`` of ``path`` (remembered until the file changes)."""
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


def managers() -> List[Manager]:
    """The included uv, this computer's and the custom one (when a path is set), with their versions."""
    found = [Manager("bundled", bundled()), Manager("system", system())]
    if _settings.path.strip():
        found.append(Manager("custom", custom()))
    return [replace(m, version=version(m.path)) for m in found]


def install() -> "Result":
    """Installs uv on this computer with its official installer (needs the network)."""
    from . import project as _project

    return _project.install_uv()


def update() -> "Result":
    """Updates this computer's uv (``uv self update``; a uv installed by pip, Homebrew or winget updates with
    them instead, and says so)."""
    from . import project as _project

    uv = system()
    if uv is None:
        return _project.Result(["uv", "self", "update"], 127, "uv is not installed on this computer")
    return _project.execute([uv, "self", "update"], timeout=300)
