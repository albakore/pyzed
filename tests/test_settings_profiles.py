"""The Settings dialog: the project's renderer, the user's profiles, a project's own settings and Reset."""

import json

import pytest

import pyzed as pz
from pyzed import rendering
from pyzed.designer import preferences, profiles, settings, settings_ui
from pyzed.designer.app import Designer
from pyzed.project import Project

PYPROJECT = '[project]\nname = "shop"\nversion = "0.1.0"\n\n[tool.pyzed]\nui = "ui"\nmain = "ui/main.pzform"\n'


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "shop"
    (root / "ui").mkdir(parents=True)
    (root / "pyproject.toml").write_text(PYPROJECT)
    return Project.open(root)


def test_rendering_settings_become_environment_variables():
    assert rendering.Rendering().env() == {} and not rendering.Rendering().custom
    gpu = rendering.Rendering(renderer="gpu", gpu_api="vulkan", power="low", vsync="off")
    assert gpu.env() == {"ICED_BACKEND": "wgpu", "WGPU_BACKEND": "vulkan", "WGPU_POWER_PREF": "low",
                         "ICED_PRESENT_MODE": "no_vsync"}
    # the CPU renderer ignores the GPU's settings
    assert rendering.Rendering(renderer="cpu", gpu_api="gl", vsync="on").env() == {"ICED_BACKEND": "tiny-skia"}
    with pytest.raises(ValueError, match="renderer"):
        rendering.Rendering(renderer="fast")
    assert rendering.Rendering.from_table({"renderer": "CPU", "vsync": "maybe", "x": 1}).to_table() == {
        "renderer": "cpu"}
    env = {"ICED_BACKEND": "wgpu"}  # what the user sets wins
    assert rendering.Rendering(renderer="cpu").apply(env) == [] and env["ICED_BACKEND"] == "wgpu"
    assert pz.Rendering is rendering.Rendering and pz.App.rendering is None


def test_rendering_is_saved_in_pyproject(project):
    root = project.root
    assert rendering.find(root) == rendering.Rendering()
    rendering.save(root, rendering.Rendering(renderer="cpu"))
    text = (root / "pyproject.toml").read_text()
    assert text.endswith('[tool.pyzed.rendering]\nrenderer = "cpu"\n') and 'main = "ui/main.pzform"' in text
    assert rendering.find(root / "ui").renderer == "cpu"  # found from a folder inside the project
    rendering.save(root, rendering.Rendering(renderer="gpu", vsync="off"))
    assert rendering.find(root).to_table() == {"renderer": "gpu", "vsync": "off"}
    assert (root / "pyproject.toml").read_text().count("[tool.pyzed.rendering]") == 1
    rendering.save(root, rendering.Rendering())  # all "auto": the table goes away
    assert "rendering" not in (root / "pyproject.toml").read_text()


def test_exported_apps_keep_the_projects_renderer(project, tmp_path):
    from pyzed import build

    rendering.save(project.root, rendering.Rendering(renderer="cpu"))
    text = build.launcher(project.reload(), tmp_path / "work").read_text()
    assert "os.environ.setdefault('ICED_BACKEND', 'tiny-skia')" in text
    compile(text, "launcher.py", "exec")


def test_profiles_keep_their_own_preferences():
    store = profiles.Store()
    assert store.profile_names() == ["Default"] and store.active == "Default"
    store.set("editor", "font_size", 18)
    assert store.create("Talk") == "Talk" and store.value("editor", "font_size") == 18  # a copy of the active
    store.set("designer", "ui_scale", 1.25)
    store.switch("Default")
    assert store.value("designer", "ui_scale") == 1.0 and store.value("editor", "font_size") == 18
    store.switch("Talk")
    assert store.value("designer", "ui_scale") == 1.25
    assert store.create("Talk") == "Talk 2" and store.rename("Talk 2", "Teaching")
    assert not store.rename("Default", "x") and not store.rename("Teaching", "Talk")
    assert store.profile_names() == ["Default", "Talk", "Teaching"]
    assert store.delete("Teaching") and store.active == "Default" and not store.delete("Default")
    data = json.loads(settings.settings_path().read_text())
    assert data["profile"] == "Default" and data["profiles"]["Talk"]["designer"] == {"ui_scale": 1.25}
    again = profiles.Store()  # read back from designer.json
    assert again.profile_names() == ["Default", "Talk"] and again.value("editor", "font_size") == 18
    assert again.changed_count() == 1
    again.reset_all()
    assert again.changed_count() == 0 and settings.load().font_size == settings.DEFAULT_FONT


def test_a_project_overrides_the_users_preferences(project):
    store = profiles.use(profiles.Store(project.root))
    try:
        store.set("editor", "tab_size", 2, "project")
        store.set("editor", "tab_size", 8)
        assert store.value("editor", "tab_size") == 2 and store.value("editor", "tab_size", "user") == 8
        assert store.modified("editor", "tab_size", "project") and store.overridden("editor", "tab_size")
        file = profiles.project_path(project.root)
        assert json.loads(file.read_text()) == {"editor": {"tab_size": 2}}
        # an old-style save of the values in use keeps the project's value in the project
        settings.save(settings.EditorSettings(tab_size=3))
        assert json.loads(file.read_text())["editor"]["tab_size"] == 3 and settings.load().tab_size == 8
        preferences.save(preferences.DesignerSettings(grid=16))
        assert preferences.load().grid == 16 and "designer" not in json.loads(file.read_text())
        store.reset("editor", "tab_size", "project")
        assert not file.exists() and store.value("editor", "tab_size") == 8
        file.parent.mkdir(exist_ok=True)
        file.write_text("{oops")
        store.open_project(project.root)
        assert store.project_error and store.value("editor", "tab_size") == 8
    finally:
        profiles.use(None)


def test_the_settings_dialog(project):
    d = Designer(language_servers=False)
    t = d.theme_obj
    d.open_settings()
    assert d.dialog == "settings" and d.dialog_view(t) is not None
    for _group, pages in settings_ui.PAGES:
        for key, _title, _icon in pages:
            d.settings_ui.show(key)
            assert d.dialog_view(t) is not None
    assert d.settings_ui.page == "general"  # the project's pages need a project
    d.settings_ui.set_query("minimap")
    assert [s.key for s in settings_ui.search("minimap")] == ["minimap"] and d.dialog_view(t) is not None
    d.settings_ui.set_query("nothing like this")
    assert d.dialog_view(t) is not None

    grid = next(s for s in settings_ui.SETTINGS if s.key == "show_grid")
    d.settings_ui.change(grid, False)
    assert d.show_grid is False and not preferences.load().show_grid
    d.settings_ui.reset(grid)
    assert d.show_grid and preferences.load().show_grid
    d.change_setting("designer", "theme", "One Light")
    assert d.theme.name == "One Light"
    d.change_setting("editor", "font_size", 20)
    assert d.assist.settings.font_size == 20
    d.settings_ui.reset_all()  # the first press only arms it
    assert d.assist.settings.font_size == 20 and d.dialog_view(t) is not None
    d.settings_ui.reset_all()
    assert d.assist.settings.font_size == settings.DEFAULT_FONT and d.theme.name != "One Light"

    d.settings_ui.start_naming("new")
    d.settings_ui.set_name("Big")
    assert d.dialog_view(t) is not None
    d.settings_ui.finish_naming()
    d.change_setting("designer", "ui_scale", 1.25)
    d.switch_profile("Default")
    assert d.scale == 1.0
    d.switch_profile("Big")
    assert d.scale == 1.25
    d.delete_profile("Big")
    assert d.scale == 1.0 and d.profile_store.profile_names() == ["Default"]

    d.open_editor_settings()
    assert d.settings_ui.page == "editor.appearance"


def test_project_scope_and_rendering_in_the_dialog(project):
    d = Designer(language_servers=False)
    t = d.theme_obj
    d.projects.attach(project)
    d.open_settings("project.rendering")
    assert d.dialog_view(t) is not None
    d.settings_ui.set_rendering("renderer", "cpu")
    assert rendering.find(project.root).renderer == "cpu" and d.projects.runs_outside
    assert d.dialog_view(t) is not None

    d.settings_ui.set_scope("project")
    tab = next(s for s in settings_ui.SETTINGS if s.key == "tab_size")
    d.settings_ui.change(tab, 2)
    assert d.assist.settings.tab_size == 2 and settings.load().tab_size == 4
    assert d.dialog_view(t) is not None
    welcome = next(s for s in settings_ui.SETTINGS if s.key == "show_welcome")
    d.settings_ui.change(welcome, False)  # a user-only setting goes to the user even from the project scope
    assert "designer" not in json.loads(profiles.project_path(project.root).read_text())
    d.projects.attach(None)  # the project's own values go with it
    assert d.assist.settings.tab_size == 4 and d.settings_ui.scope == "user"
    d.projects.attach(project)
    assert d.assist.settings.tab_size == 2
    d.reset_all_settings("project")
    assert d.assist.settings.tab_size == 4 and not profiles.project_path(project.root).exists()


def test_pz_run_reads_the_projects_renderer(project, monkeypatch):
    import os

    from pyzed import _core, app as app_module

    rendering.save(project.root, rendering.Rendering(renderer="cpu"))
    monkeypatch.chdir(project.root)
    environ = {k: v for k, v in os.environ.items() if k != "ICED_BACKEND"}
    monkeypatch.setattr(os, "environ", environ)
    monkeypatch.setattr(app_module._platform, "is_wsl", lambda: False)
    monkeypatch.setattr(_core, "run", lambda app: None)
    pz.run(pz.App())
    assert environ["ICED_BACKEND"] == "tiny-skia"

    class Gpu(pz.App):
        rendering = pz.Rendering(renderer="gpu")

    del environ["ICED_BACKEND"]
    pz.run(Gpu)
    assert environ["ICED_BACKEND"] == "wgpu"
