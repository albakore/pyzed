"""Projects in the title bar, like Zed: the environment, the project picker (this window and recent ones),
the branch and worktree, getting a project's environment ready, and what the agent is told."""

import asyncio
import shutil
import subprocess

import pytest

from pyzed import project
from pyzed.designer import agent_tools, commands, project_picker
from pyzed.designer.app import Designer


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    monkeypatch.setattr("pyzed._platform.is_wsl", lambda release=None: False)
    monkeypatch.chdir(tmp_path)


def _make(tmp_path, name):
    root = tmp_path / name
    (root / "ui").mkdir(parents=True)
    (root / ".venv").mkdir()  # ready: opening it has nothing to prepare
    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n\n[tool.pyzed]\nui = "ui"\n')
    return root.resolve()


def _close(commands_):
    for command in commands_ if isinstance(commands_, list) else [commands_]:
        getattr(command, "close", lambda: None)()


def test_environment_of_a_folder(monkeypatch):
    assert project.environment(r"\\wsl$\Ubuntu\home\me\app") == project.Environment("wsl", "Ubuntu")
    assert project.environment("//wsl.localhost/Debian/home/me") == project.Environment("wsl", "Debian")
    here = project.environment("/home/me/app")
    assert here.kind == "local" and not here.is_wsl
    monkeypatch.setattr("pyzed._platform.is_wsl", lambda release=None: True)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu-24.04")
    wsl = project.environment("/home/me/app")
    assert wsl == project.Environment("wsl", "Ubuntu-24.04") and "Linux" in wsl.describe()


def test_prepare_installs_uv_and_syncs(tmp_path, monkeypatch):
    root = tmp_path / "app"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "app"\nversion = "0.1.0"\n')
    app = project.Project.open(root)
    calls = []
    found = {"uv": None}
    monkeypatch.setattr(project, "find_uv", lambda: found["uv"])

    def install():
        calls.append("install")
        found["uv"] = "uv"
        return project.Result(["sh"], 0, "installed uv")

    monkeypatch.setattr(project, "install_uv", install)
    monkeypatch.setattr(project.Project, "sync", lambda self: calls.append("sync") or project.Result(["uv"], 0, "ok"))
    assert app.needs_prepare()
    result = app.prepare()
    assert result.ok and calls == ["install", "sync"] and "installed uv" in result.output
    (root / ".venv").mkdir()
    assert not app.needs_prepare()


def test_prepare_stops_when_uv_cannot_be_installed(tmp_path, monkeypatch):
    root = _make(tmp_path, "app")
    monkeypatch.setattr(project, "find_uv", lambda: None)
    monkeypatch.setattr(project, "install_uv", lambda: project.Result(["sh"], 1, "no network"))
    result = project.Project.open(root).prepare()
    assert not result.ok and result.output == "no network"


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_branches_and_worktrees(tmp_path):
    root = _make(tmp_path, "repo")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main"]
    subprocess.run([*git, "init", "-q"], cwd=root, check=True)
    subprocess.run([*git, "add", "pyproject.toml"], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "start"], cwd=root, check=True)
    subprocess.run([*git, "branch", "feature"], cwd=root, check=True)
    app = project.Project.open(root)
    assert app.git_branches() == ["feature", "main"] and app.git_worktree() is None
    assert app.switch_branch("feature").ok and app.git_branch() == "feature"
    linked = tmp_path / "repo-fix"
    subprocess.run([*git, "worktree", "add", "-q", "-b", "fix", str(linked)], cwd=root, check=True)
    assert project.Project.open(linked).git_worktree() == "repo-fix"


def test_title_bar_and_picker(tmp_path):
    first, second = _make(tmp_path, "shop"), _make(tmp_path, "blog")
    d = Designer(language_servers=False)
    t = d.theme_obj
    changes = []
    d.projects.on_change(lambda p: changes.append(p.name if p else None))
    assert d.projects.window == [] and project_picker.title_items(d, t)  # "No project"
    _close(d.projects.open(str(first)))
    _close(d.projects.open(str(second)))
    assert d.projects.window == [first, second] and d.projects.project.root == second
    # the picker: this window first (the active one checked), then the recent projects not open here
    d.picker_projects.open()
    assert d.app_menu == "projects"
    rows = d.picker_projects.entries()
    assert [(r.root.name, r.section, r.active) for r in rows] == [("shop", "window", False), ("blog", "window", True)]
    assert d.view() is not None
    d.picker_projects.set_query("sh")
    assert [r.root.name for r in d.picker_projects.entries()] == ["shop"]
    _close(d.picker_projects.submit())
    assert d.projects.project.root == first and d.app_menu is None
    # closing the active project in this window goes back to the other one
    _close(d.projects.close_project(first))
    assert d.projects.window == [second] and d.projects.project.root == second
    _close(d.projects.close_project(second))
    assert d.projects.project is None
    assert changes == ["shop", "blog", "shop", "blog", None]
    d.picker_projects.open()
    assert {r.root for r in d.picker_projects.entries()} == {first, second}  # both are recent now
    d.on_key("down")
    assert d.picker_projects.index == 1


def test_open_recent_command_toggles_the_picker():
    d = Designer(language_servers=False)
    commands.run("open_recent", d)
    assert d.app_menu == "projects"
    commands.run("open_recent", d)
    assert d.app_menu is None


def test_opening_a_project_that_is_not_ready_prepares_it(tmp_path, monkeypatch):
    root = _make(tmp_path, "fresh")
    (root / ".venv").rmdir()
    d = Designer(language_servers=False)
    tasks = d.projects.open(str(root))
    assert d.projects.busy == "Preparing the environment"
    _close(tasks)


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_branch_menu(tmp_path):
    root = _make(tmp_path, "repo")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main"]
    subprocess.run([*git, "init", "-q"], cwd=root, check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "start"], cwd=root, check=True)
    d = Designer(language_servers=False)
    _close(d.projects.open(str(root)))
    assert d.projects.branch == "main"
    d.projects.open_branches()
    assert d.app_menu == "branches" and d.projects.branches == ["main"] and d.view() is not None


def test_agent_knows_the_environment_and_the_other_projects(tmp_path):
    first, second = _make(tmp_path, "shop"), _make(tmp_path, "blog")
    d = Designer(language_servers=False)
    _close(d.projects.open(str(first)))
    _close(d.projects.open(str(second)))
    note = agent_tools.context_note(d)
    assert "Project: blog" in note and "Environment: This computer" in note and "shop" in note
    assert agent_tools.project_info(d)["environment"].startswith("This computer")


def test_startup_file(tmp_path):
    root = _make(tmp_path, "shop")
    (root / "ui" / "main.pzform").write_text("{}")
    (root / "run.py").write_text("print('hi')\n")
    app = project.Project.open(root)
    assert app.startup == root / "ui" / "main.pzform"
    app.set_startup("run.py")
    assert app.startup == root / "run.py" and 'script = "run.py"' in (root / "pyproject.toml").read_text()
    app.set_startup(root / "ui" / "other.pzform")
    text = (root / "pyproject.toml").read_text()
    assert app.startup == root / "ui" / "other.pzform" and "script" not in text and 'ui = "ui"' in text
    with pytest.raises(ValueError):
        app.set_startup("notes.txt")


def test_startup_file_in_the_tree(tmp_path):
    root = _make(tmp_path, "shop")
    (root / "run.py").write_text("print('hi')\n")
    d = Designer(language_servers=False)
    _close(d.projects.open(str(root)))
    w = d.projects.files
    assert w.startup() == "ui/main.pzform"
    labels = [getattr(i, "label", None) for i in w.menu_items("run.py")]
    assert "Set as Startup File" in labels
    w.set_startup("run.py")
    assert w.startup() == "run.py" and d.projects.project.script == root / "run.py"
    assert "Set as Startup File" not in [getattr(i, "label", None) for i in w.menu_items("run.py")]
    assert d.view() is not None


def test_new_forms_are_saved_in_the_project(tmp_path):
    root = _make(tmp_path, "shop")
    d = Designer(language_servers=False)
    _close(d.projects.open(str(root)))
    d.show_save_as()
    assert d.dialog_path == "ui/form1.pzform"


@pytest.mark.skipif(shutil.which("git") is None, reason="needs git")
def test_clone_repository(tmp_path):
    source = _make(tmp_path, "remote-app")
    (source / ".venv").rmdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main"]
    subprocess.run([*git, "init", "-q"], cwd=source, check=True)
    subprocess.run([*git, "add", "-A"], cwd=source, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "start"], cwd=source, check=True)
    d = Designer(language_servers=False)
    p = d.projects
    p.show("clone")()
    assert d.dialog == "project:clone" and d.view() is not None
    p.clone_url, p.clone_folder = str(source) + "/", str(tmp_path / "work")
    assert p.clone_target() == tmp_path / "work" / "remote-app"
    p.clone_url = "git@github.com:user/app.git"
    assert p.clone_target() == tmp_path / "work" / "app"
    p.clone_url = str(source)
    task = p.clone()
    assert d.dialog is None and p.busy == "Cloning remote-app"
    finish = asyncio.run(task)  # the clone, then opening it on the UI side
    _close(finish())
    cloned = (tmp_path / "work" / "remote-app").resolve()
    assert (cloned / "pyproject.toml").is_file() and p.project.root == cloned
