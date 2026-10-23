"""Restricted mode: a project from somewhere else runs nothing until the user trusts it."""

import json
from pathlib import Path

import pytest

from pyzed.designer import commands, lsp, profiles, scene, trust
from pyzed.designer.app import Designer


@pytest.fixture(autouse=True)
def _restricted(monkeypatch):
    monkeypatch.delenv(trust.ENV, raising=False)  # conftest trusts everything


def _project(tmp_path: Path, name: str = "shop") -> Path:
    root = tmp_path / name
    (root / "ui").mkdir(parents=True)
    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n\n[tool.pyzed]\nui = "ui"\n')
    (root / ".venv").mkdir()
    (root / ".venv" / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (root / ".pyzed").mkdir()
    # a project cannot turn restricted mode off for itself
    (root / ".pyzed" / "settings.json").write_text(json.dumps({"designer": {"restricted_mode": False}}))
    return root


def test_trusted_folders_are_saved_and_cover_their_subfolders(tmp_path):
    root = tmp_path / "app"
    (root / "ui").mkdir(parents=True)
    assert not trust.is_trusted(root, enabled=True)
    assert trust.is_trusted(root, enabled=False)
    assert trust.trust(root)
    assert trust.is_trusted(root / "ui", enabled=True)
    assert json.loads(trust.trust_path().read_text())["folders"] == [str(root.resolve())]
    assert not trust.is_trusted(tmp_path, enabled=True)
    assert trust.forget(root) and not trust.is_trusted(root, enabled=True)
    import pyzed

    assert trust.is_trusted(Path(pyzed.__file__).parent / "designer" / "templates", enabled=True)


def test_opening_a_project_from_elsewhere_asks_and_holds_its_code_back(tmp_path, monkeypatch):
    root = _project(tmp_path)
    found, synced = [], []
    monkeypatch.setattr(scene, "discover_project", lambda path=None, **_: found.append(path) or [])
    d = Designer(language_servers=False)
    monkeypatch.setattr(type(d.projects), "_task", lambda self, label, work, done=None, **_: synced.append(label))
    d.projects.open(str(root))
    assert d.trust.restricted and d.trust.enabled  # the project's own settings do not count
    assert d.dialog == "trust" and d.trust.asking == root.resolve()
    assert found == [] and synced == ["Checking tools"]  # no uv sync, no imports
    d.dialog_view(d.theme_obj)
    d.trust.decline()
    assert d.dialog is None
    assert lsp.find_environment(root / "ui" / "main.pzform").venv is None  # nor the tools of its .venv

    commands.run("run", d)  # Run asks again
    assert d.dialog == "trust"
    d.trust.accept()
    assert not d.trust.restricted and trust.is_trusted(root, enabled=True)
    assert found == [root.resolve()] and synced.count("Checking tools") == 2  # and what Run waited for ran
    assert lsp.find_environment(root / "ui" / "main.pzform").venv == (root / ".venv").resolve()


def test_projects_made_in_the_designer_are_trusted(tmp_path, monkeypatch):
    root = _project(tmp_path, "mine")
    trust.trust(root)
    d = Designer(language_servers=False)
    monkeypatch.setattr(type(d.projects), "_task", lambda self, label, work, done=None, **_: None)
    d.projects.open(str(root))
    assert not d.trust.restricted and d.dialog is None


def test_restricted_mode_is_a_user_setting(tmp_path):
    d = Designer(language_servers=False)
    assert "restricted_mode" in profiles.USER_ONLY
    d.profile_store.set("designer", "restricted_mode", False)
    assert not d.trust.enabled and d.trust.trusted(tmp_path)
