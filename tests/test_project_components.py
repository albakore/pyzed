"""The components of a project in the designer: found when the project opens (not only when Pyzed starts),
and a control whose component is missing drawn as a warning instead of breaking the form."""

import textwrap

import pytest

from pyzed import project
from pyzed.designer import Form, components, open_form, save
from pyzed.designer import scene as _scene
from pyzed.designer.app import Designer
from pyzed.designer.model import Control

SIDEBAR = textwrap.dedent('''\
    """The sidebar of the chat."""

    import pyzed as pz


    class SlackSidebar(pz.Component):
        """Channels and people."""

        workspace: str = "Pyzed"
        events = {"pick": "A channel was picked"}

        def render(self):
            return pz.text(self.workspace)


    if __name__ == "__main__":
        pz.run(SlackSidebar)
    ''')


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    monkeypatch.chdir(tmp_path)


def _slack(tmp_path, name="slack"):
    """An older project: a form using a pz.Component written by hand in ``ui/widgets/``."""
    root = tmp_path / name
    (root / "ui" / "widgets").mkdir(parents=True)
    (root / ".venv").mkdir()
    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n\n[tool.pyzed]\nui = "ui"\n')
    (root / "ui" / "widgets" / "sidebar.py").write_text(SIDEBAR)
    form = Form(name="main", width=600, height=400)
    form.add(Control(name="sidebar1", type="slack_sidebar", width=200, height=400, props={"workspace": "Acme"}))
    save(form, root / "ui" / "main.pzform")
    return root.resolve()


def _forget(type_):
    components._REGISTRY.pop(type_, None)
    from pyzed import component

    component._REGISTRY.pop(type_, None)


def test_a_missing_component_is_drawn_as_a_warning():
    form = Form(width=300, height=200)
    form.add(Control(name="ghost1", type="not_installed_anywhere", width=120, height=40, props={"size": 3}))
    stand_in = components.spec("not_installed_anywhere")
    assert stand_in.category == components.MISSING and not components.is_known("not_installed_anywhere")
    assert components.spec("button") is components.get("button")
    with pytest.raises(KeyError):
        components.get("not_installed_anywhere")
    assert components.render(form["ghost1"], components.RenderContext()) is not None
    assert "not_installed_anywhere" not in {c.type for c in components.all_components()}  # not in the toolbox


def test_opening_an_old_project_registers_its_components(tmp_path):
    _forget("slack_sidebar")
    root = _slack(tmp_path)
    _scene.new_component("TopBar", root / "ui" / "top_bar.pzcomp").save()  # a designed one too
    _forget("top_bar")
    d = Designer(language_servers=False)  # started somewhere else, then the project is opened
    assert not components.is_known("slack_sidebar")
    d.projects.attach(project.Project.open(root))
    assert components.is_known("slack_sidebar"), _scene.errors
    assert components.get("slack_sidebar").events[:1] == ("pick",)
    assert components.is_known("top_bar")
    d.open_path(root / "ui" / "main.pzform")
    d.view()
    assert d.doc.form["sidebar1"].props["workspace"] == "Acme"


def test_a_form_with_an_unknown_component_still_opens_and_runs(tmp_path):
    _forget("slack_sidebar")
    root = _slack(tmp_path, "broken")
    (root / "ui" / "widgets" / "sidebar.py").write_text("import not_a_module\n\nclass SlackSidebar(pz.Component):\n"
                                                        "    pass\n")
    d = Designer(root / "ui" / "main.pzform", language_servers=False)
    assert not components.is_known("slack_sidebar")
    assert any("not_a_module" in e for e in _scene.errors.values())
    d.view()  # the canvas, outline and panels draw the stand-in
    d.doc.select("sidebar1")
    d.view()
    d.save()
    assert '"slack_sidebar"' in (root / "ui" / "main.pzform").read_text()  # kept as it was
    open_form(root / "ui" / "main.pzform").screenshot(tmp_path / "run.png", scale=1)


def test_only_modules_that_just_define_things_are_imported(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    (root / "runs.py").write_text("import pyzed as pz\n\nclass Big(pz.Component):\n    pass\n\npz.run(Big)\n")
    (root / "starts.py").write_text("import pyzed as pz\n\nclass Big2(pz.Component):\n    pass\n\napp = pz.run(Big2)\n")
    (root / "plain.py").write_text("x = 1\n")
    assert _scene.discover_classes(root) == []
    (root / "fine.py").write_text("import pyzed as pz\n\nclass FineThing(pz.Component):\n    designer = False\n")
    assert _scene.discover_classes(root) == ["fine"]
    assert _scene.discover_classes(root) == []  # unchanged: not imported again
