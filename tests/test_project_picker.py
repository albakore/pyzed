"""Projects in the title bar, like Zed: the environment, the project picker (this window and recent ones),
the branch and worktree, getting a project's environment ready, and what the agent is told."""

import asyncio
import shutil
import pathlib
import subprocess
import sys

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


def test_an_app_written_in_code_starts_from_main_py(tmp_path, monkeypatch):
    root = _make(tmp_path, "chat")
    (root / "ui" / "main.pzform").write_text("{}")
    (root / "main.py").write_text("import pyzed as pz\n")
    app = project.Project.open(root)
    assert app.script is None and app.startup == root / "ui" / "main.pzform"
    (root / "ui" / "main.pzform").unlink()  # the agent wrote the app in code and took the example form out
    assert app.script == root / "main.py" and app.startup == root / "main.py"

    from pyzed import cli

    opened = []
    monkeypatch.setattr("pyzed.designer.design", lambda path=None, **_: opened.append(path))
    monkeypatch.chdir(root)
    cli.design()
    (root / "main.py").unlink()
    monkeypatch.chdir(tmp_path)
    cli.design(str(root))
    assert opened == [root / "main.py", None]  # never a new, empty ui/main.pzform
    assert pathlib.Path.cwd() == root and not (root / "ui" / "main.pzform").exists()
    with pytest.raises(FileNotFoundError, match="main.pzform does not exist"):
        project.run()


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
    p.clone_url = "C:\\Users\\me\\repos\\remote-app\\"
    assert p.clone_target() == tmp_path / "work" / "remote-app"
    p.clone_url = str(source)
    task = p.clone()
    assert d.dialog is None and p.busy == "Cloning remote-app"
    finish = asyncio.run(task)  # the clone, then opening it on the UI side
    _close(finish())
    cloned = (tmp_path / "work" / "remote-app").resolve()
    assert (cloned / "pyproject.toml").is_file() and p.project.root == cloned


def test_wsl_project_opened_from_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    root = r"\\wsl.localhost\Ubuntu\home\me\shop"
    env = project.environment(root)
    assert env.remote and "wsl.exe" in env.describe()
    assert project.linux_path(root + r"\ui\main.pzform") == "/home/me/shop/ui/main.pzform"
    command = env.command(["uv", "run", root + r"\main.py"], root, {"PYZED_DESIGNER_RUN": "1"})
    assert command == ["wsl.exe", "-d", "Ubuntu", "--cd", "/home/me/shop", "--", "sh", "-lc", 'exec "$@"', "sh",
                       "env", "PYZED_DESIGNER_RUN=1", "uv", "run", "/home/me/shop/main.py"]
    app = project.Project(pathlib.Path(root), {})
    ran = []
    monkeypatch.setattr(project, "execute", lambda args, cwd=None, timeout=None: ran.append((list(args), cwd))
                        or project.Result(list(args), 0, "uv 0.9.0"))
    monkeypatch.setattr(project, "find_uv", lambda: None)  # Windows' own uv does not matter
    assert app.uv("sync").ok and app.git("status").ok
    (uv_args, cwd), (git_args, _) = ran
    assert cwd is None and uv_args[:5] == ["wsl.exe", "-d", "Ubuntu", "--cd", "/home/me/shop"]
    assert uv_args[-2:] == ["uv", "sync"] and git_args[-2:] == ["git", "status"]
    assert app.run_args()[0] == "uv" and app.has_uv()
    assert project.tools(app)["uv"].version == "0.9.0"


def test_wsl_tools_survive_an_unreachable_distro(monkeypatch):
    """Windows can answer a look into a stopped or missing WSL distro with an error (WinError 64) instead of
    "not found": the tools are still listed, run inside WSL by name."""
    monkeypatch.setattr(sys, "platform", "win32")
    app = project.Project(pathlib.Path(r"\\wsl.localhost\Ubuntu\home\me\shop"), {})

    def unreachable(path):
        raise OSError(22, "The specified network name is no longer available", str(path))

    monkeypatch.setattr(pathlib.Path, "is_file", unreachable)
    monkeypatch.setattr(project, "execute",
                        lambda args, cwd=None, timeout=None: project.Result(list(args), 0, "ruff 0.9.0"))
    assert app.tool_path("ruff") is None
    assert project.tools(app)["ruff"].path == "ruff"


def test_local_projects_run_commands_directly(tmp_path, monkeypatch):
    app = project.Project.open(_make(tmp_path, "shop"))
    assert not app.environment.remote
    assert project.Environment("local", "Linux").command(["uv", "sync"], tmp_path) == ["uv", "sync"]


def test_opening_a_wsl_project_from_windows_does_not_wait_for_git(tmp_path, monkeypatch):
    """Each look at a WSL project opened from Windows crosses into Linux (wsl.exe, 9P), and a stuck git froze the
    window while the project opened: its branch, branches and files are read on worker threads."""
    import threading
    import time

    from pyzed.designer import workspace

    root = _make(tmp_path, "shop")
    (root / "app.py").write_text("")
    d = Designer(language_servers=False)
    release = threading.Event()

    def later(value):
        return lambda *args: (release.wait(10), value)[1]

    monkeypatch.setattr(project.Environment, "remote", property(lambda self: True))
    monkeypatch.setattr(project.Project, "git_branch", later("main"))
    monkeypatch.setattr(project.Project, "git_worktree", lambda self: None)
    monkeypatch.setattr(project.Project, "git_branches", later(["dev", "main"]))
    monkeypatch.setattr(workspace, "git_status", later({"app.py": "modified"}))
    started = time.monotonic()
    _close(d.projects.open(str(root)))
    d.projects.open_branches()
    assert time.monotonic() - started < 5
    assert d.projects.loading and d.projects.branch is None and d.view() is not None
    release.set()
    deadline = time.monotonic() + 10
    while d.projects.loading and time.monotonic() < deadline:
        time.sleep(0.01)
    assert d.projects.branch == "main" and d.projects.branches == ["dev", "main"]
    assert d.projects.files.status == {"app.py": "modified"} and "app.py" in d.projects.files.entries
    assert "ui" in d.projects.files.expanded


def test_commands_never_share_the_editors_stdin(monkeypatch):
    seen = {}

    def run(args, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(args, 0, "ok")

    monkeypatch.setattr(project.subprocess, "run", run)
    assert project.execute(["git", "--version"]).ok and seen["stdin"] is subprocess.DEVNULL
