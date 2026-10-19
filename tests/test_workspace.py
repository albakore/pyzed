"""The Project tab's file tree, file search and actions, the Dependencies tab and the folder browser."""

import shutil
import subprocess

import pytest

from pyzed import project, ui
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
    assert (tmp_path / "shop/ui/forms/todo.md").is_file() and not opened
    assert d.buffers.current.path.resolve() == (tmp_path / "shop/ui/forms/todo.md").resolve()
    w.start_naming("rename", "ui/forms/todo.md")
    assert w.name_text == "todo.md"
    w.set_name("done.md")
    w.finish_naming()
    assert (tmp_path / "shop/ui/forms/done.md").is_file() and "ui/forms/done.md" in w.entries
    assert d.buffers.current.name == "done.md"  # the open file follows the rename
    w.ask_delete("ui/forms/")
    assert d.dialog_view(d.theme_obj) is not None
    w.delete()
    assert not (tmp_path / "shop/ui/forms").exists() and "ui/forms/" not in w.entries
    assert d.buffers.items == []  # and closes with its folder
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
    assert d.dialog is None and not opened and d.buffers.current.name == "notes.txt"


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


def test_text_files_open_in_the_code_editor(tmp_path, monkeypatch):
    d = _designer(tmp_path)
    w = d.projects.files
    root = tmp_path / "shop"
    (root / "logo.png").write_bytes(b"\x89PNG\r\n\x00\x00")
    opened = []
    monkeypatch.setattr(workspace, "open_with_system", opened.append)
    w.refresh()
    w.open("logo.png")  # binary: the system's app
    assert [o.name for o in opened] == ["logo.png"] and d.buffers.items == []
    w.open("ui/notes.txt")
    b = d.buffers.current
    assert b.text == "hi" and b.language == "txt" and d.layout.is_showing("code", d) and d.focus == "code"
    assert d.editor_id.startswith("file:") and d.view() is not None
    d.set_code_buffer("hello\n")
    assert b.dirty and d.assist.diagnostics() == []
    d.save()  # Ctrl+S with the file focused saves the file, not the form
    assert (root / "ui/notes.txt").read_text() == "hello\n" and not b.dirty and d.doc.path is None
    w.open("ui/notes.txt")  # already open: same tab
    assert len(d.buffers.items) == 1
    w.edit("pyproject.toml")
    assert d.buffers.current.language == "toml" and d.buffers.active == 1
    d.set_code_buffer("changed")
    d.close_code()
    assert d.dialog == "file:unsaved" and d.dialog_view(d.theme_obj) is not None
    d.buffers.confirm_discard()
    assert [x.name for x in d.buffers.items] == ["notes.txt"] and d.buffers.current.name == "notes.txt"
    assert "changed" not in (root / "pyproject.toml").read_text()
    d.close_code()
    assert d.buffers.items == [] and not d.layout.is_showing("code", d)


def test_file_tabs_next_to_the_form_code(tmp_path):
    d = _designer(tmp_path)
    d.edit_whole_file()
    d.projects.files.open("ui/notes.txt")
    from pyzed.designer import code_panel

    tabs = code_panel.code_tabs(d, d.theme_obj)
    assert tabs is not None and d.buffers.current is not None
    d.show_form_code()
    assert d.buffers.current is None and d.editing[0] == "*" and d.editor_id.startswith("code:")
    assert docks.PANELS["code"].view(d, d.theme_obj) is not None
    d.buffers.select(0)
    d.set_code_buffer("typed")
    assert d.editing[1] != "typed" and d.buffers.current.text == "typed"
    d.buffers.select(None)
    d.close_code()  # closing the form's code shows the file again
    assert d.editing is None and d.buffers.current.name == "notes.txt"


def test_read_text(tmp_path):
    from pyzed.designer import files

    (tmp_path / "a.txt").write_bytes(b"\xef\xbb\xbfone\r\ntwo")
    (tmp_path / "b.bin").write_bytes(b"ab\x00cd")
    (tmp_path / "c.txt").write_bytes(b"\xff\xfe")
    assert files.read_text(tmp_path / "a.txt") == "one\ntwo"
    assert files.read_text(tmp_path / "b.bin") is None and files.read_text(tmp_path / "c.txt") is None
    assert files.language_of(tmp_path / "Makefile") == "makefile" and files.language_of(tmp_path / "x.RS") == "rs"


def test_cut_copy_paste_duplicate_undo(tmp_path):
    d = _designer(tmp_path)
    w = d.projects.files
    root = tmp_path / "shop"
    (root / "src").mkdir()
    w.refresh()
    w.copy("ui/notes.txt")
    w.paste("ui/notes.txt")  # into its own folder: a copy with a free name
    assert (root / "ui/notes copy.txt").read_text() == "hi"
    w.paste("src/")
    assert (root / "src/notes.txt").is_file()
    w.cut("ui/notes copy.txt")
    w.paste("src/")
    assert (root / "src/notes copy.txt").is_file() and not (root / "ui/notes copy.txt").exists() and w.clipboard is None
    w.undo()  # the move goes back
    assert (root / "ui/notes copy.txt").is_file() and not (root / "src/notes copy.txt").exists()
    w.redo()
    assert (root / "src/notes copy.txt").is_file()
    w.undo()
    w.undo()  # the copy into src/ is removed
    assert not (root / "src/notes.txt").exists()
    w.duplicate("ui/notes.txt")
    assert (root / "ui/notes copy 2.txt").is_file() and d.dialog == "project:name"
    assert w.naming == ("rename", "ui/notes copy 2.txt")
    w.cut("ui/")
    w.paste("ui/")  # a folder cannot go inside itself
    assert (root / "ui").is_dir()


def test_tree_keys_and_menu(tmp_path, monkeypatch):
    d = _designer(tmp_path)
    w = d.projects.files
    root = tmp_path / "shop"
    trashed = []
    monkeypatch.setattr(workspace._ops, "send_to_trash", trashed.append)
    w.toggle("ui")
    w.toggle("ui")  # a click gives the tree the keyboard
    assert d.focus == "files" and "ui" in w.expanded
    d.on_key("down")
    assert w.selected_rel() == "ui/notes.txt"
    d.on_key("ctrl-c")
    assert w.clipboard == ("copy", ["ui/notes.txt"])
    d.on_key("ctrl-v")
    assert (root / "ui/notes copy.txt").is_file()
    d.on_key("ctrl-z")
    assert not (root / "ui/notes copy.txt").exists() and w.selected is None
    w.selected = "ui/notes.txt"
    d.on_key("ctrl-n")  # a new file here, not a new form
    assert d.dialog == "project:name" and w.naming == ("file", "ui/")
    d.close_dialog()
    d.on_key("f2")
    assert w.naming == ("rename", "ui/notes.txt")
    d.close_dialog()
    d.on_key("delete")
    assert [p.name for p in trashed] == ["notes.txt"] and w.selected is None
    w.selected = "ui/notes.txt"
    d.on_key("ctrl-delete")
    assert d.dialog == "project:delete"
    d.close_dialog()
    d.on_key("left")
    assert w.selected == "ui"
    d.on_key("left")
    assert "ui" not in w.expanded
    labels = [i.label for i in w.menu_items("ui/notes.txt") if isinstance(i, ui.MenuItem)]
    assert labels[:3] == ["New File", "New Folder", "Reveal in File Manager"]
    assert {"Cut", "Copy", "Duplicate", "Paste", "Undo", "Redo", "Copy Path", "Copy Relative Path",
            "Add to .gitignore", "Rename", "Trash", "Delete", "Open in Terminal"} <= set(labels)
    root_labels = [i.label for i in w.menu_items("") if isinstance(i, ui.MenuItem)]
    assert "Cut" not in root_labels and "Paste" in root_labels
    d.focus_panel("project")  # the pointer coming back keeps the tree's keyboard
    assert d.focus == "files"
    d.focus_panel("properties")
    assert d.focus == "panel"


def test_ignore_files_and_permalinks(tmp_path):
    from pyzed.designer import file_ops

    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(".venv/")
    assert file_ops.add_ignore(gitignore, "build/") and not file_ops.add_ignore(gitignore, "build/")
    assert gitignore.read_text() == ".venv/\n/build/\n"
    assert file_ops.web_url("git@github.com:me/app.git") == "https://github.com/me/app"
    assert file_ops.web_url("https://token@gitlab.com/me/app.git") == "https://gitlab.com/me/app"
    assert file_ops.web_url("ssh://git@codeberg.org/me/app") == "https://codeberg.org/me/app"
    assert file_ops.web_url("/some/local/path") is None


def test_free_names_and_freedesktop_trash(tmp_path):
    from pyzed.designer import file_ops

    (tmp_path / "a.txt").write_text("1")
    assert file_ops.free_name(tmp_path / "a.txt").name == "a copy.txt"
    (tmp_path / "a copy.txt").write_text("2")
    assert file_ops.free_name(tmp_path / "a copy.txt").name == "a copy 2.txt"
    (tmp_path / "pkg").mkdir()
    assert file_ops.free_name(tmp_path / "pkg").name == "pkg copy"
    went = file_ops.freedesktop_trash(tmp_path / "a.txt", data_home=tmp_path / "data")
    assert went.read_text() == "1" and not (tmp_path / "a.txt").exists()
    info = (tmp_path / "data/Trash/info/a.txt.trashinfo").read_text()
    assert info.startswith("[Trash Info]\nPath=") and "DeletionDate=" in info
    (tmp_path / "a.txt").write_text("3")
    assert file_ops.freedesktop_trash(tmp_path / "a.txt", data_home=tmp_path / "data").name == "a.2.txt"
