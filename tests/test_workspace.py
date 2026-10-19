"""The Project tab's file tree, file search and actions, the Dependencies tab and the folder browser."""

import shutil
import subprocess

import pytest

from pyzed import project
from pyzed.designer import docks, workspace
from pyzed.designer.app import Designer


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "app"
    for rel in ("ui/main.py", "src/app/__init__.py", "README.md", ".gitignore", ".venv/lib/x.py",
                "__pycache__/a.pyc", "build/out.txt"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text("x")
    (root / "assets").mkdir()
    return root


def test_list_entries_skips_environments_and_caches(tree):
    entries = workspace.list_entries(tree)
    assert {"ui/", "ui/main.py", "src/app/__init__.py", "README.md", ".gitignore", "assets/"} <= set(entries)
    assert not [e for e in entries if e.startswith((".venv", "__pycache__", "build"))]


def test_search_prefers_file_names():
    paths = ["src/app/main_window.py", "ui/main.py", "docs/maintenance.md", "ui/"]
    assert workspace.search(paths, "main")[0] == "ui/main.py"
    assert workspace.search(paths, "mwin") == ["src/app/main_window.py"]
    assert workspace.fuzzy_score("zzz", "ui/main.py") is None


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_git_status(tree):
    run = lambda *a: subprocess.run(["git", *a], cwd=tree, capture_output=True, check=True)  # noqa: E731
    run("init", "-q")
    run("add", "README.md")
    run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "first")
    (tree / "README.md").write_text("changed")
    status = workspace.git_status(tree)
    assert status["README.md"] == "modified" and status["ui/main.py"] == "created"


def _designer(tmp_path):
    created = project.Project.open(_project_dir(tmp_path))
    d = Designer(language_servers=False)
    d.projects.attach(created)
    return d


def _project_dir(tmp_path):
    root = tmp_path / "shop"
    (root / "ui").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "shop"\nversion = "0.1.0"\n\n[tool.pyzed]\nui = "ui"\n')
    (root / "ui" / "notes.txt").write_text("hi")
    return root


def test_tree_actions(tmp_path, monkeypatch):
    d = _designer(tmp_path)
    w = d.projects.files
    assert "ui" in w.expanded and "ui/notes.txt" in w.entries
    w.start_naming("folder", "ui/")
    w.set_name("forms")
    w.finish_naming()
    assert (tmp_path / "shop/ui/forms").is_dir() and w.selected == "ui/forms"
    opened = []
    monkeypatch.setattr(workspace, "open_with_system", opened.append)
    w.start_naming("file", "ui/forms/")
    w.set_name("todo.md")
    w.finish_naming()
    assert (tmp_path / "shop/ui/forms/todo.md").is_file() and [o.resolve() for o in opened] == [(tmp_path / "shop/ui/forms/todo.md").resolve()]
    w.start_naming("rename", "ui/forms/todo.md")
    assert w.name_text == "todo.md"
    w.set_name("done.md")
    w.finish_naming()
    assert (tmp_path / "shop/ui/forms/done.md").is_file() and "ui/forms/done.md" in w.entries
    w.ask_delete("ui/forms/")
    assert d.dialog_view(d.theme_obj) is not None
    w.delete()
    assert not (tmp_path / "shop/ui/forms").exists() and "ui/forms/" not in w.entries
    w.query = "note"
    assert w.results() == ["ui/notes.txt"]
    w.pick("ui/")
    assert w.query == "" and "ui" in w.expanded
    w.open_menu("ui/notes.txt")
    assert w.menu_at(d.theme_obj) is not None
    assert d.view() is not None


def test_dependencies_tab_needs_a_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no project around
    d = Designer(language_servers=False)
    assert "dependencies" not in [p.id for p in d.layout.panels_in("left", d)]
    d.projects.attach(project.Project.open(_project_dir(tmp_path)))
    assert "dependencies" in [p.id for p in d.layout.panels_in("left", d)]
    d.left_tab = "dependencies"
    assert d.view() is not None and docks.PANELS["dependencies"].view(d, d.theme_obj) is not None


def test_go_to_file(tmp_path, monkeypatch):
    d = _designer(tmp_path)
    opened = []
    monkeypatch.setattr(workspace, "open_with_system", opened.append)
    d.run_action("find_file")
    assert d.dialog == "project:find" and d.dialog_view(d.theme_obj) is not None
    d.projects.files.set_find("notes")
    d.projects.files.find_first()
    assert d.dialog is None and [o.resolve() for o in opened] == [(tmp_path / "shop/ui/notes.txt").resolve()]


def test_folder_browser(tmp_path):
    (tmp_path / "a" / ".hidden").mkdir(parents=True)
    (tmp_path / "a" / "b").mkdir()
    shop = _project_dir(tmp_path / "a")
    b = workspace.FolderBrowser(tmp_path / "a")
    assert [f.name for f in b.folders()] == ["b", "shop"] and workspace.is_project(shop)
    b.toggle_hidden()
    assert ".hidden" in [f.name for f in b.folders()]
    b.go(tmp_path / "a" / "missing" / "deeper")  # the nearest folder that exists
    assert b.path == (tmp_path / "a").resolve()
    b.up()
    assert b.path == tmp_path.resolve() and b.crumbs()[-1] == b.path


def test_open_and_new_project_dialogs(tmp_path):
    d = Designer(language_servers=False)
    d.projects.show("open")()
    d.projects.browser.go(tmp_path)
    assert d.dialog == "project:open" and d.dialog_view(d.theme_obj) is not None
    d.projects.open(str(_project_dir(tmp_path)))
    assert d.projects.project is not None and d.projects.project.name == "shop"
    d.projects.show("new")()
    d.projects.show("browse_new")()
    d.projects.browser.go(tmp_path)
    assert d.dialog_view(d.theme_obj) is not None
    d.projects.choose_location()
    assert d.dialog == "project:new" and d.projects.new_folder == str(tmp_path.resolve())
