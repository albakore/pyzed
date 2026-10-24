"""The package managers of Pyzed's projects: which uv runs them, its defaults and the Settings page."""

import pytest

from pyzed import package_managers as pm
from pyzed import project
from pyzed.designer import preferences, profiles, settings_ui


@pytest.fixture(autouse=True)
def _default_settings():
    pm.configure(pm.UvSettings())
    yield
    pm.configure(pm.UvSettings())


@pytest.fixture
def uvs(tmp_path, monkeypatch):
    """An included uv, one on this computer and a custom one."""
    paths = {}
    for name in ("bundled", "system", "custom"):
        exe = tmp_path / name / "uv"
        exe.parent.mkdir()
        exe.write_text("")
        paths[name] = str(exe)
    monkeypatch.setattr(project, "_bundled", lambda name: paths["bundled"])
    monkeypatch.setattr(pm.shutil, "which", lambda name: paths["system"])
    return paths


def test_uv_settings_become_environment_variables():
    assert pm.UvSettings().env() == {}
    settings = pm.UvSettings(index_url=" https://mirror/simple ", extra_index_url="https://a  https://b",
                             prerelease=True, offline=True, link_mode="copy")
    assert settings.env() == {"UV_DEFAULT_INDEX": "https://mirror/simple", "UV_INDEX": "https://a https://b",
                              "UV_PRERELEASE": "allow", "UV_OFFLINE": "1", "UV_LINK_MODE": "copy"}
    assert pm.UvSettings(source="cargo", link_mode="teleport") == pm.UvSettings()
    pm.configure(prerelease=True)
    assert project._clean_env()["UV_PRERELEASE"] == "allow"


def test_the_chosen_uv_runs_the_projects(uvs, monkeypatch):
    assert project.find_uv() == uvs["system"]  # automatic: this computer's first
    pm.configure(source="bundled")
    assert project.find_uv() == uvs["bundled"]
    pm.configure(source="custom", path=uvs["custom"])
    assert project.find_uv() == uvs["custom"] and pm.source_of(uvs["custom"]) == "custom"
    assert [(m.source, m.path) for m in pm.managers()] == [
        ("bundled", uvs["bundled"]), ("system", uvs["system"]), ("custom", uvs["custom"])]
    # one that isn't there falls back to this computer's, else the included one
    pm.configure(source="custom", path=uvs["custom"] + ".missing")
    assert project.find_uv() == uvs["system"]
    monkeypatch.setattr(pm.shutil, "which", lambda name: None)
    monkeypatch.setattr(project, "_installed_uv", lambda: None)
    pm.configure(source="system")
    assert project.find_uv() == uvs["bundled"] and pm.system() is None
    assert pm.update().code == 127


def test_the_included_uv_on_path_is_not_this_computers(uvs, monkeypatch):
    monkeypatch.setattr(pm.shutil, "which", lambda name: uvs["bundled"])
    monkeypatch.setattr(project, "_installed_uv", lambda: None)
    assert pm.system() is None and pm.source_of(uvs["bundled"]) == "bundled"


def test_new_projects_get_the_python_of_the_settings(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(project, "find_uv", lambda: "uv")
    monkeypatch.setattr(project, "execute_uv", lambda args, cwd, **kw: seen.append(args) or project.Result(args, 1, "x"))
    pm.configure(python="3.12")
    with pytest.raises(RuntimeError):
        project.init(tmp_path / "app", sync=False)
    assert seen[0][-3:-1] == ["--python", "3.12"]


def test_the_preferences_and_the_package_managers_page(tmp_path):
    prefs = preferences.DesignerSettings.from_dict({"uv_source": "pip", "uv_link_mode": "nope", "uv_offline": True})
    assert prefs.uv_source == "auto" and prefs.uv_link_mode == "" and prefs.uv().offline
    assert {"uv_source", "uv_path"} <= profiles.USER_ONLY  # a project never picks the executable to run

    from pyzed.designer.app import Designer

    d = Designer(language_servers=False)
    t = d.theme_obj
    d.open_settings("packages")
    assert d.dialog_view(t) is not None
    offline = next(s for s in settings_ui.SETTINGS if s.key == "uv_offline")
    d.settings_ui.change(offline, True)
    assert pm.settings().offline and preferences.load().uv_offline
    python = next(s for s in settings_ui.SETTINGS if s.key == "uv_python")
    d.settings_ui.edit(python, " 3.13 ")
    assert d.dialog_view(t) is not None  # with the Save button of the text being typed
    d.settings_ui.save_text(python)
    assert pm.settings().python == "3.13" and python.key not in d.settings_ui.drafts
    source = next(s for s in settings_ui.SETTINGS if s.key == "uv_source")
    d.settings_ui.change(source, "custom")
    assert pm.settings().source == "custom" and d.dialog_view(t) is not None
    d.settings_ui.reset_all()
    d.settings_ui.reset_all()
    assert pm.settings() == pm.UvSettings()
