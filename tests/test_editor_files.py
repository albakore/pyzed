"""The designer's files and indentation: the startup file, opening every Pyzed format, tabs or spaces and the
pace of Backspace held down."""

import json
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import cli, designer, project
from pyzed.designer import code, commands, files, indentation, scene_code, settings
from pyzed.designer.app import Designer, PYZED_SUFFIXES
from pyzed.designer.scene import SceneDocument
from pyzed.designer.shader_doc import ShaderDocument, new_shader


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("PYZED_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.setattr("pyzed._platform.is_wsl", lambda release=None: False)
    monkeypatch.chdir(tmp_path)


def _project(tmp_path):
    root = tmp_path / "shop"
    (root / "ui").mkdir(parents=True)
    (root / ".venv").mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "shop"\nversion = "0.1.0"\n\n[tool.pyzed]\nui = "ui"\n')
    designer.new_form(root / "ui" / "main")
    designer.new_form(root / "ui" / "settings")
    (root / "run.py").write_text("print('hi')\n")
    return root.resolve()


def _close(result):
    for command in result if isinstance(result, list) else [result]:
        getattr(command, "close", lambda: None)()


# -- tabs and spaces ---------------------------------------------------------------------


def test_convert_indentation_leaves_strings_alone():
    source = 'class A:\n    def f(self):\n        doc = """\n    kept\n"""\n        return 1\n'
    tabbed = indentation.to_tabs(source)
    assert tabbed == 'class A:\n\tdef f(self):\n\t\tdoc = """\n    kept\n"""\n\t\treturn 1\n'
    assert indentation.detect(tabbed) == "\t" and indentation.detect(source) == "    "
    assert indentation.to_spaces(tabbed) == source
    assert indentation.convert("  x\n", True, 4) == "  x\n"  # less than a tab stays as spaces
    assert indentation.width("\t  \t", 4) == 8 and indentation.detect("x = 1\n") is None


def test_generated_code_follows_the_file():
    tabbed = "def ok_click(form, event):\n\tpass\n"
    source, created = code.ensure_function(tabbed, "cancel_click")
    assert created and "def cancel_click(form, event):\n\t\"\"\"Event handler.\"\"\"\n\tpass" in source
    # a handler typed with tabs into a file indented with spaces becomes spaces
    spaced = code.replace_function("def a(form, event):\n    pass\n", "a", "def a(form, event):\n\treturn 1\n")
    assert "\t" not in spaced and "    return 1" in spaced
    cls = "class Card(pz.Component):\n\tdef build(self):\n\t\treturn None\n"
    source, _ = scene_code.ensure_method(cls, "on_click", cls_name="Card")
    assert "\tdef on_click(self, event):\n\t\t" in source and "    " not in source
    compile(source, "card.py", "exec")


def test_editor_settings_for_tabs_and_key_repeat():
    s = settings.EditorSettings.from_dict({"hard_tabs": True, "repeat_delay": 99999, "repeat_rate": -3})
    assert s.hard_tabs and s.repeat_delay == settings.MAX_REPEAT_DELAY and s.repeat_rate == 0
    assert s.key_repeat == {"repeat_delay": settings.MAX_REPEAT_DELAY, "repeat_rate": None}
    assert settings.EditorSettings().key_repeat == {"repeat_delay": 500.0, "repeat_rate": 20.0}
    widget = pz.ui.editor("e", "x", tab_size=4, hard_tabs=True, backspace_unindent=False, repeat_delay=300,
                          repeat_rate=10)
    assert widget is not None


def test_convert_indentation_command_and_on_save(tmp_path):
    d = Designer(language_servers=False)
    path = tmp_path / "tool.py"
    path.write_text("def f():\n    return 1\n")
    d.projects.files.root = tmp_path
    assert d.buffers.open(path)
    assert commands.BY_ID["convert_to_tabs"].enabled(d)
    assert commands.run("convert_to_tabs", d) is not None
    assert d.buffers.current.text == "def f():\n\treturn 1\n"
    assert d.convert_indentation(True) is None  # already tabs
    commands.run("convert_to_spaces", d)
    assert d.buffers.current.text == "def f():\n    return 1\n"
    # "Convert indentation on save" with tabs
    d.assist.set("hard_tabs", True)
    d.assist.set("convert_indentation", True)
    d.focus = "code"
    assert d.save() is not None  # the editor gets the converted text
    assert path.read_text() == "def f():\n\treturn 1\n"
    data = json.loads(settings.settings_path().read_text())["editor"]
    assert data["hard_tabs"] and data["convert_indentation"]
    d.dialog = "editor_settings"
    assert d.view() is not None


def test_saving_a_form_converts_its_code(tmp_path):
    path = designer.new_form(tmp_path / "login", template="dialog")
    d = Designer(path, language_servers=False)
    d.assist.set("hard_tabs", True)
    d.assist.set("convert_indentation", True)
    d.doc.wire("ok", "click")
    d.save()
    text = path.with_suffix(".py").read_text()
    assert "\n\t" in text and "\n    " not in text.split('"""', 2)[-1]


# -- the startup file ---------------------------------------------------------------------


def test_startup_choices_and_picker(tmp_path):
    root = _project(tmp_path)
    app = project.Project.open(root)
    rels = [p.relative_to(root).as_posix() for p in app.startup_choices()]
    assert rels == ["ui/main.pzform", "ui/settings.pzform", "run.py"]  # the forms' handlers are left out
    d = Designer(language_servers=False)
    _close(d.projects.open(str(root)))
    p = d.projects
    assert p.startup_label() == "ui/main.pzform"
    commands.run("set_startup", d)
    assert d.dialog == "project:startup" and d.view() is not None
    p.startup_query = "run"
    assert p.startup_choices() == ["run.py"]
    assert p.set_startup("run.py") and d.dialog is None
    assert p.project.script == root / "run.py" and p.startup_label() == "run.py"
    # the open form becomes the startup file again
    d.open_path(root / "ui" / "settings.pzform")
    assert commands.BY_ID["use_as_startup"].enabled(d)
    commands.run("use_as_startup", d)
    assert p.project.script is None and p.project.main_form == root / "ui" / "settings.pzform"
    assert not d.can_use_as_startup()


def test_run_with_nothing_open_starts_the_startup_form(tmp_path):
    root = _project(tmp_path)
    d = Designer(language_servers=False)
    _close(d.projects.open(str(root)))
    started = []
    d.projects.run_form = lambda form, **kwargs: started.append(form)
    d.run_form()
    assert started == [root / "ui" / "main.pzform"] and d.doc.path == root / "ui" / "main.pzform"


def test_pyzed_run_starts_the_startup_script(tmp_path, monkeypatch):
    root = _project(tmp_path)
    (root / "run.py").write_text("import pathlib\npathlib.Path('ran.txt').write_text('yes')\n")
    project.Project.open(root).set_startup("run.py")
    monkeypatch.chdir(root)
    assert cli.run_form() == 0 and (root / "ran.txt").read_text() == "yes"


# -- opening every Pyzed file --------------------------------------------------------------------


def test_open_dialog_lists_every_format(tmp_path):
    root = _project(tmp_path)
    pz.AnimationLibrary([pz.Clip("intro", length=1)]).save(root / "ui" / "motion.pzanim")
    designer.new_component("Card", root / "ui" / "card.pzcomp").save()
    new_shader("glow", root / "ui" / "glow.pzshad").save()
    d = Designer(language_servers=False)
    _close(d.projects.open(str(root)))
    suffixes = {p.suffix for p in d.pyzed_files()}
    assert suffixes == set(PYZED_SUFFIXES) == {".pzform", ".pzcomp", ".pzshad", ".pzanim"}
    commands.run("open", d)
    assert d.dialog == "open" and d.view() is not None
    assert d.browse_open() is not None  # the system's file dialog
    # an animation library opens as JSON in the code editor
    assert d.open_path(root / "ui" / "motion.pzanim") is not None
    assert d.buffers.current.path.name == "motion.pzanim" and d.buffers.current.language == "json"
    assert any("intro" in (t.message or "") for t in d.toasts)
    # the project tree opens shaders and components in their editors
    d.projects.files.open("ui/glow.pzshad")
    assert isinstance(d.doc, ShaderDocument)
    d.projects.files.open("ui/card.pzcomp")
    assert isinstance(d.doc, SceneDocument)


def test_designer_opens_a_file_that_is_not_a_document(tmp_path):
    path = tmp_path / "motion.pzanim"
    pz.AnimationLibrary([pz.Clip("spin", length=1)]).save(path)
    d = Designer(path, language_servers=False)
    assert d.doc.path is None and d.buffers.current.path == path
    assert files.language_of(Path("x.pzform")) == "json" and files.language_of(Path("x.pyi")) == "py"
