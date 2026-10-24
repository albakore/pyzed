"""The package managers of Pyzed's projects: the registry, which executable runs, its defaults and the Settings
page built from them."""

import pytest

from pyzed import package_managers as pm
from pyzed import project
from pyzed.designer import locale, preferences, profiles, settings_ui


@pytest.fixture(autouse=True)
def _default_settings():
    pm.load()
    yield
    pm.load()


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


class Pixi(pm.PackageManager):
    name = "pixi"
    title = "pixi"
    executable = "pixi"
    fields = pm.SOURCE_FIELDS + (pm.Field("channel", "Channel", default="conda-forge"),)

    def env(self, values):
        return {"PIXI_CHANNEL": values["channel"]}


def test_uv_settings_become_environment_variables():
    assert pm.environment() == {} and pm.values("uv")["source"] == "auto"
    pm.configure("uv", index_url=" https://mirror/simple ", extra_index_url="https://a  https://b",
                 prerelease=True, offline=True, link_mode="copy")
    assert pm.environment() == {"UV_DEFAULT_INDEX": "https://mirror/simple", "UV_INDEX": "https://a https://b",
                                "UV_PRERELEASE": "allow", "UV_OFFLINE": "1", "UV_LINK_MODE": "copy"}
    assert project._clean_env()["UV_PRERELEASE"] == "allow"
    pm.configure("uv", source="cargo", link_mode="teleport", unknown=1)  # invalid values become the defaults
    assert pm.values("uv")["source"] == "auto" and pm.values("uv")["link_mode"] == ""
    assert pm.clean({"uv": {"offline": True, "nope": 1}, "npm": {}}) == {"uv": {"offline": True}}


def test_the_chosen_uv_runs_the_projects(uvs, monkeypatch):
    assert project.find_uv() == uvs["system"]  # automatic: this computer's first
    pm.configure("uv", source="bundled")
    assert project.find_uv() == uvs["bundled"]
    pm.configure("uv", source="custom", path=uvs["custom"])
    assert project.find_uv() == uvs["custom"] and pm.source_of(uvs["custom"]) == "custom"
    assert [(i.source, i.path) for i in pm.UV.installations(pm.values("uv"))] == [
        ("bundled", uvs["bundled"]), ("system", uvs["system"]), ("custom", uvs["custom"])]
    # one that isn't there falls back to this computer's, else the included one
    pm.configure("uv", path=uvs["custom"] + ".missing")
    assert project.find_uv() == uvs["system"]
    monkeypatch.setattr(pm.shutil, "which", lambda name: None)
    monkeypatch.setattr(project, "_installed_uv", lambda: None)
    pm.configure("uv", source="system")
    assert project.find_uv() == uvs["bundled"] and pm.UV.system() is None
    assert pm.UV.update().code == 127


def test_the_included_uv_on_path_is_not_this_computers(uvs, monkeypatch):
    monkeypatch.setattr(pm.shutil, "which", lambda name: uvs["bundled"])
    monkeypatch.setattr(project, "_installed_uv", lambda: None)
    assert pm.UV.system() is None and pm.source_of(uvs["bundled"]) == "bundled"


def test_more_package_managers_join_the_registry(monkeypatch):
    monkeypatch.setattr(pm, "_managers", dict(pm._managers))
    pixi = pm.register(Pixi())
    assert pm.managers() == [pm.UV, pixi] and pm.get("pixi") is pixi
    assert not pixi.can_install and not pixi.can_update and pixi.install().code == 127
    assert pm.environment() == {"PIXI_CHANNEL": "conda-forge"}
    pm.load({"pixi": {"channel": "bioconda"}}, "pixi")
    assert pm.environment() == {"PIXI_CHANNEL": "bioconda"}
    assert pm.default() is pm.UV  # pixi can't run Pyzed's projects
    assert [s.item for s in settings_ui.every_setting() if s.item.startswith("pixi.")] == [
        "pixi.source", "pixi.path", "pixi.channel"]


def test_new_projects_get_the_python_of_the_settings(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(project, "find_uv", lambda: "uv")
    monkeypatch.setattr(project, "execute_uv", lambda args, cwd, **kw: seen.append(args) or project.Result(args, 1, "x"))
    pm.configure("uv", python="3.12")
    with pytest.raises(RuntimeError):
        project.init(tmp_path / "app", sync=False)
    assert seen[0][-3:-1] == ["--python", "3.12"]


def test_every_package_manager_text_has_a_spanish_translation():
    texts = [text for m in pm.managers() for text in pm.labels(m.fields)]
    texts += [m.description for m in pm.managers() if m.description]
    assert [text for text in texts if text not in locale._ES] == []


def test_the_preferences_and_the_package_managers_page(uvs):
    prefs = preferences.DesignerSettings.from_dict({"package_managers": {"uv": {"source": "pip", "offline": True},
                                                                          "npm": {"x": 1}}})
    assert prefs.package_managers == {"uv": {"offline": True}} and prefs.package_manager == "uv"
    assert {"package_manager", "package_managers"} <= profiles.USER_ONLY  # a project never picks what runs

    from pyzed.designer.app import Designer

    d = Designer(language_servers=False)
    t = d.theme_obj
    d.open_settings("packages")
    assert d.dialog_view(t) is not None
    c = d.settings_ui
    setting = {s.item: s for s in settings_ui.every_setting() if s.item}
    c.change(setting["uv.offline"], True)
    assert pm.values("uv")["offline"] and preferences.load().package_managers == {"uv": {"offline": True}}
    assert c.modified(setting["uv.offline"]) and not c.modified(setting["uv.prerelease"])
    c.edit(setting["uv.python"], " 3.13 ")
    assert d.dialog_view(t) is not None  # with the Save button of the text being typed
    c.save_text(setting["uv.python"])
    assert pm.values("uv")["python"] == "3.13" and not c.drafts
    c.change(setting["uv.source"], "custom")
    assert pm.values("uv")["source"] == "custom" and d.dialog_view(t) is not None
    c.reset(setting["uv.offline"])
    assert not pm.values("uv")["offline"] and preferences.load().package_managers["uv"] == {
        "python": "3.13", "source": "custom"}
    c.set_query("index")
    assert "uv.index_url" in [s.item for s in settings_ui.search("index")] and d.dialog_view(t) is not None
    c.reset_all()
    c.reset_all()
    assert pm.values("uv") == pm.UV.defaults()
