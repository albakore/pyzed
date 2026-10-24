"""Layers and profiles of the designer's preferences: defaults, the user's (one profile at a time) and a project's.

The values the designer uses are the defaults, overlaid with the user's settings, overlaid with the open
project's ``.pyzed/settings.json`` (like Zed's ``.zed/settings.json``), which only holds the settings that
project changes::

    {"editor": {"tab_size": 2, "hard_tabs": true}, "designer": {"grid": 4}}

The user's settings live in ``designer.json`` (see ``settings``): its ``"editor"`` and ``"designer"`` sections
hold the active profile, and ``"profiles"`` keeps the others (only what differs from the defaults), so switching
profile swaps the sections. Only preferences take part: the window layout, the recent files and the keymap
stay as they are.
"""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import preferences as _preferences
from . import settings as _settings

#: The sections of the preferences: the code editor's and the designer's own.
SECTIONS = ("editor", "designer")
#: Where a project keeps its settings, relative to its folder.
PROJECT_FILE = Path(".pyzed") / "settings.json"
#: The profile every user starts with.
DEFAULT_PROFILE = "Default"
#: Fields of ``DesignerSettings`` that are the designer's state, not preferences (profiles leave them alone).
STATE = frozenset({"recent", "docks", "order", "active", "windows", "layouts", "layout_name", "panels", "sizes"})

#: Preferences a project's own settings never change: what keeps a project from running code by itself (such as
#: the package managers' executables to run).
USER_ONLY = frozenset({"restricted_mode", "package_manager", "package_managers"})

_CLASSES = {"editor": _settings.EditorSettings, "designer": _preferences.DesignerSettings}


def keys(section: str) -> Tuple[str, ...]:
    """The preference names of ``section`` ("editor" or "designer")."""
    skip = {"keymap"} if section == "editor" else STATE
    return tuple(f.name for f in fields(_CLASSES[section]) if f.name not in skip)


def defaults(section: str) -> Dict[str, Any]:
    """The default value of each preference of ``section``."""
    values = _CLASSES[section]().to_dict()
    return {k: values[k] for k in keys(section)}


def clean(section: str, values: Any) -> Dict[str, Any]:
    """The known preferences of ``values``, each made valid (like loading them from the file)."""
    if not isinstance(values, dict):
        return {}
    known = {k: v for k, v in values.items() if k in keys(section)}
    valid = _CLASSES[section].from_dict(known).to_dict()
    return {k: valid[k] for k in known}


def _diff(section: str, values: Dict[str, Any]) -> Dict[str, Any]:
    base = defaults(section)
    return {k: v for k, v in values.items() if k in base and base[k] != v}


def project_path(root: Path) -> Path:
    """The settings file of the project in ``root``."""
    return Path(root) / PROJECT_FILE


class Store:
    """The user's and the project's preferences, and the user's profiles.

    ``user[section]`` holds every preference of the active profile; ``project[section]`` only the ones the
    project overrides. ``effective(section)`` is what the designer uses.
    """

    def __init__(self, root: Optional[Path] = None, *, user: bool = True) -> None:
        """Reads the user's preferences (with ``user=False``, only the project's: the user's are the defaults)
        and the settings of the project in ``root``."""
        data = _settings._read() if user else {}
        self.user: Dict[str, Dict[str, Any]] = {}
        for section in SECTIONS:
            saved = data.get(section) if isinstance(data.get(section), dict) else {}
            self.user[section] = {**defaults(section), **clean(section, saved)}
        profiles = data.get("profiles")
        self.profiles: Dict[str, Dict[str, Dict[str, Any]]] = {
            str(name): {s: _diff(s, clean(s, p.get(s))) for s in SECTIONS}
            for name, p in (profiles.items() if isinstance(profiles, dict) else ()) if isinstance(p, dict)}
        active = data.get("profile")
        self.active: str = str(active) if isinstance(active, str) and active else DEFAULT_PROFILE
        self.profiles.pop(self.active, None)  # the active one lives in the sections
        self.root: Optional[Path] = None
        self.project: Dict[str, Dict[str, Any]] = {s: {} for s in SECTIONS}
        self.project_error: Optional[str] = None
        self.open_project(root)

    # -- the project layer ------------------------------------------------------------------
    def open_project(self, root: Optional[Path]) -> None:
        """Reads the settings of the project in ``root`` (``None``: no project, so no overrides)."""
        self.root = Path(root) if root is not None else None
        self.project = {s: {} for s in SECTIONS}
        self.project_error = None
        if self.root is None:
            return
        file = project_path(self.root)
        if not file.is_file():
            return
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            self.project_error = f"{file.name}: {err}"
            return
        if isinstance(data, dict):
            self.project = {s: clean(s, data.get(s)) for s in SECTIONS}

    def save_project(self) -> Optional[Path]:
        """Writes the project's overrides (deleting the file when there are none); ``None`` without a project or
        when the folder is not writable."""
        if self.root is None:
            return None
        file = project_path(self.root)
        data = {s: dict(sorted(v.items())) for s, v in self.project.items() if v}
        try:
            if not data:
                if file.is_file():
                    file.unlink()
                    try:
                        file.parent.rmdir()  # only when nothing else is in .pyzed
                    except OSError:
                        pass
                return file
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            return None
        return file

    # -- values -------------------------------------------------------------------------------
    def effective(self, section: str) -> Dict[str, Any]:
        """The value of each preference of ``section`` the designer uses (the project's win)."""
        return {**self.user[section], **{k: v for k, v in self.project[section].items() if k not in USER_ONLY}}

    def value(self, section: str, key: str, scope: str = "effective") -> Any:
        """The value of ``key`` in ``scope``: "user", "project" (the user's when the project leaves it) or
        "effective"."""
        if scope == "user" or key in USER_ONLY:
            return self.user[section][key]
        return self.project[section].get(key, self.user[section][key])

    def overridden(self, section: str, key: str) -> bool:
        """Whether the project sets ``key``."""
        return key in self.project[section] and key not in USER_ONLY

    def modified(self, section: str, key: str, scope: str = "user") -> bool:
        """In "user" scope, whether ``key`` differs from its default; in "project", whether the project sets it."""
        if scope == "project":
            return self.overridden(section, key)
        return self.user[section][key] != defaults(section)[key]

    def set(self, section: str, key: str, value: Any, scope: str = "user") -> Any:
        """Sets ``key`` in ``scope`` (made valid like a loaded value) and saves it; returns the value kept."""
        value = clean(section, {key: value}).get(key, defaults(section)[key])
        if scope == "project":
            self.project[section][key] = value
            self.save_project()
        else:
            self.user[section][key] = value
            self.save_user()
        return value

    def reset(self, section: str, key: str, scope: str = "user") -> None:
        """Back to the default ("user") or to the user's value ("project": the override is removed)."""
        if scope == "project":
            self.project[section].pop(key, None)
            self.save_project()
        else:
            self.user[section][key] = defaults(section)[key]
            self.save_user()

    def reset_all(self, scope: str = "user", section: Optional[str] = None) -> None:
        """Every preference (of ``section``, or both) back to the defaults, or every project override removed."""
        for s in (section,) if section else SECTIONS:
            if scope == "project":
                self.project[s] = {}
            else:
                self.user[s] = defaults(s)
        self.save_project() if scope == "project" else self.save_user()

    def changed_count(self, scope: str = "user") -> int:
        """How many preferences differ from the defaults ("user") or the project overrides ("project")."""
        return sum(1 for s in SECTIONS for k in keys(s) if self.modified(s, k, scope))

    def absorb(self, section: str, values: Dict[str, Any]) -> Dict[str, Any]:
        """``values`` (every field of ``section``, as the designer uses them) saved the old way: the preferences the
        project overrides go to the project, the rest to the user. Returns what the user's file keeps."""
        out = dict(values)
        project_changed = False
        for key in keys(section):
            if key not in values:
                continue
            if key in self.project[section]:
                if values[key] != self.project[section][key]:
                    self.project[section][key] = values[key]
                    project_changed = True
                out[key] = self.user[section][key]
            else:
                self.user[section][key] = values[key]
        if project_changed:
            self.save_project()
        return out

    # -- profiles -----------------------------------------------------------------------------
    def profile_names(self) -> List[str]:
        """Every profile, the default first and the others in alphabetical order."""
        names = {DEFAULT_PROFILE, self.active, *self.profiles}
        return [DEFAULT_PROFILE] + sorted(n for n in names if n != DEFAULT_PROFILE)

    def switch(self, name: str) -> None:
        """Makes ``name`` the active profile (keeping the current one's values), creating it with the defaults if
        it does not exist."""
        if name == self.active:
            return
        self.profiles[self.active] = {s: _diff(s, self.user[s]) for s in SECTIONS}
        saved = self.profiles.pop(name, {})
        self.user = {s: {**defaults(s), **clean(s, saved.get(s))} for s in SECTIONS}
        self.active = name
        self.save_user()

    def create(self, name: str, *, copy: bool = True) -> str:
        """Adds a profile (a copy of the active one, or the defaults) and switches to it; returns its name, made
        unique ("Work 2")."""
        base = name.strip() or "Profile"
        name, n = base, 2
        while name in self.profile_names():
            name, n = f"{base} {n}", n + 1
        current = {s: dict(self.user[s]) for s in SECTIONS}
        self.switch(name)
        if copy:
            self.user = current
            self.save_user()
        return name

    def rename(self, old: str, new: str) -> bool:
        """Renames profile ``old`` (not the default one); ``False`` if ``new`` is empty or taken."""
        new = new.strip()
        if old == DEFAULT_PROFILE or not new or new in self.profile_names():
            return False
        if old == self.active:
            self.active = new
        elif old in self.profiles:
            self.profiles[new] = self.profiles.pop(old)
        else:
            return False
        self.save_user()
        return True

    def delete(self, name: str) -> bool:
        """Deletes profile ``name`` (not the default one); deleting the active one switches to the default."""
        if name == DEFAULT_PROFILE:
            return False
        if name == self.active:
            saved = self.profiles.pop(DEFAULT_PROFILE, {})
            self.user = {s: {**defaults(s), **clean(s, saved.get(s))} for s in SECTIONS}
            self.active = DEFAULT_PROFILE
        elif self.profiles.pop(name, None) is None:
            return False
        self.save_user()
        return True

    def export(self) -> Dict[str, Any]:
        """The active profile as JSON-ready data (what differs from the defaults), to share it."""
        return {"profile": self.active, **{s: _diff(s, self.user[s]) for s in SECTIONS}}

    def save_user(self) -> Optional[Path]:
        """Writes the user's preferences and profiles to ``designer.json``, keeping the rest of the file (the
        layout, the recent files, the keymap...)."""
        path = _settings.settings_path()
        data = _settings._read()
        for section in SECTIONS:
            current = data.get(section) if isinstance(data.get(section), dict) else {}
            data[section] = {**current, **self.user[section]}
        data["profile"] = self.active
        data["profiles"] = {name: {s: v for s, v in p.items() if v} for name, p in sorted(self.profiles.items())}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except OSError:
            return None
        return path


_store: Optional[Store] = None


def use(store: Optional[Store]) -> Optional[Store]:
    """Makes ``store`` the one ``settings.save`` and ``preferences.save`` go through (``None``: none)."""
    global _store
    _store = store
    return store


def current() -> Optional[Store]:
    """The store in use (the designer's), if any."""
    return _store


def absorb(section: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """What ``settings.save`` and ``preferences.save`` write for ``section``: ``values`` as they are without a
    store, else with the project's overrides kept out of the user's file (see ``Store.absorb``)."""
    return _store.absorb(section, values) if _store is not None else values
