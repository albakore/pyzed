"""The example gallery: the catalog, copying an example into a new project, the welcome window and
running a project's script."""

import io
import zipfile

import pytest

from pyzed import project
from pyzed.designer import commands, preferences, samples, welcome
from pyzed.designer.app import Designer


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    monkeypatch.chdir(tmp_path)


def test_every_sample_and_thumbnail_is_in_the_repository():
    root = samples.examples_root()
    assert root is not None
    assert len({s.id for s in samples.CATALOG}) == len(samples.CATALOG)
    for sample in samples.CATALOG:
        assert sample.category in samples.CATEGORIES
        assert (root / sample.path).exists(), sample.path
        assert (root / sample.thumbnail).is_file(), sample.thumbnail


@pytest.mark.parametrize("sample_id", [s.id for s in samples.CATALOG])
def test_create_makes_a_project(tmp_path, sample_id):
    sample = samples.BY_ID[sample_id]
    folder = samples.create(sample, tmp_path / "out" / "my-app")
    created = project.Project.open(folder)
    data = created.data
    assert data["project"]["name"] == "my-app"
    assert any(d.startswith("pyzed-ui") for d in data["project"]["dependencies"])
    assert "sources" not in data.get("tool", {}).get("uv", {})  # no path to this checkout
    if sample.category == "Designer":
        assert created.main_form.is_file() and created.script is None
    else:
        assert created.script is not None and created.script.is_file()
    assert (folder / "README.md").is_file() and (folder / ".gitignore").is_file()


def test_create_refuses_a_folder_that_is_not_empty(tmp_path):
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "file.txt").write_text("x")
    with pytest.raises(FileExistsError):
        samples.create(samples.BY_ID["counter"], tmp_path / "taken")


def test_strip_sources():
    text = ('[project]\nname = "demo"\n\n# Runs against this checkout of Pyzed.\n'
            '[tool.uv.sources]\npyzed-ui = { path = "../.." }\n\n[tool.pyzed]\nui = "ui"\n')
    out = samples._strip_sources(text)
    assert "tool.uv.sources" not in out and "checkout" not in out and "[tool.pyzed]" in out


def test_examples_root_order(tmp_path, monkeypatch):
    own = tmp_path / "own"
    (own / "counter.py").parent.mkdir(parents=True)
    (own / "counter.py").write_text("")
    monkeypatch.setenv("PYZED_EXAMPLES", str(own))
    assert samples.examples_root() == own


def test_stage_copies_samples_and_thumbnails(tmp_path):
    copied = samples.stage(tmp_path / "staged")
    assert (tmp_path / "staged" / "counter.py").is_file()
    assert (tmp_path / "staged" / "thumbnails" / "counter.png").is_file()
    assert (tmp_path / "staged" / "integrations" / "sqlmodel_heroes" / "main.py").is_file()
    assert not list((tmp_path / "staged").rglob("__pycache__"))
    assert len(copied) >= len(samples.CATALOG)


def test_download_extracts_the_examples(tmp_path, monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("pyzed-1.0.0/examples/counter.py", "print('hi')")
        archive.writestr("pyzed-1.0.0/examples/thumbnails/counter.png", b"png")
        archive.writestr("pyzed-1.0.0/README.md", "not an example")

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setenv("PYZED_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(samples.urllib.request, "urlopen", lambda url, timeout: Response(buffer.getvalue()))
    dest = samples.download()
    assert (dest / "counter.py").read_text() == "print('hi')"
    assert (dest / "thumbnails" / "counter.png").is_file() and not (dest / "README.md").exists()


def test_welcome_window_and_gallery(tmp_path):
    d = Designer(language_servers=False)
    assert d.dialog is None  # only design() opens it at startup
    commands.run("welcome", d)
    assert d.dialog == "welcome"
    assert d.view() is not None and welcome.dialog(d, d.theme_obj) is not None
    d.welcome.set_category("Games")
    assert {s.id for s in d.welcome.shown()} == {"snake", "breakout", "neon_invaders"}
    d.welcome.set_query("bricks")
    assert [s.id for s in d.welcome.shown()] == ["breakout"]
    commands.run("examples", d)
    assert d.welcome.category == welcome.ALL and len(d.welcome.shown()) == len(samples.CATALOG)


def test_show_at_startup_is_saved():
    d = Designer(language_servers=False)
    assert d.prefs.show_welcome
    d.welcome.toggle_startup(False)
    assert preferences.load().show_welcome is False


def test_create_from_example_opens_the_project(tmp_path):
    d = Designer(language_servers=False)
    d.welcome.folder = str(tmp_path / "projects")
    d.welcome.pick(samples.BY_ID["counter"])
    assert d.dialog == "welcome:create" and d.welcome.name == "counter"
    for command in d.welcome.create():
        getattr(command, "close", lambda: None)()  # the background uv sync and tool lookup
    assert d.dialog is None
    root = tmp_path / "projects" / "counter"
    assert d.projects.project is not None and d.projects.project.root.resolve() == root.resolve()
    assert d.buffers.current is not None and d.buffers.current.path.name == "counter.py"
    # a second copy gets a free name
    d.welcome.pick(samples.BY_ID["counter"])
    assert d.welcome.name == "counter-2"


def test_run_starts_the_project_script(tmp_path, monkeypatch):
    folder = samples.create(samples.BY_ID["counter"], tmp_path / "counter")
    d = Designer(language_servers=False)
    d.projects.attach(project.Project.open(folder))
    started = []

    class Process:
        stdout = None

        def poll(self):
            return None

        def terminate(self):
            pass

    def spawn(self, script=None, **kwargs):
        started.append(self.script)
        return Process()

    monkeypatch.setattr(project.Project, "spawn_script", spawn)
    d.run_form()
    assert started == [folder / "counter.py"]
    assert d.console.running == "counter.py"
