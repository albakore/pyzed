"""Find and replace in the whole project (the Search panel)."""

from pathlib import Path

from pyzed.designer import commands, docks, project_search
from pyzed.designer.app import Designer
from pyzed.designer.code_panel import _pattern
from pyzed.designer.document import Document
from pyzed.designer.model import Form


def _folder(tmp_path: Path) -> Path:
    root = tmp_path / "app"
    (root / "ui").mkdir(parents=True)
    (root / ".venv" / "lib").mkdir(parents=True)
    (root / "main.py").write_text("greeting = 'hello'\nprint(greeting)\n", encoding="utf-8")
    (root / "ui" / "home.py").write_text("def show():\n    return 'Hello world'\n", encoding="utf-8")
    (root / "README.md").write_text("Say hello\n", encoding="utf-8")
    (root / ".venv" / "lib" / "site.py").write_text("hello = 1\n", encoding="utf-8")
    (root / "logo.png").write_bytes(b"\x89PNG\0\0hello")
    return root


def _designer(root: Path, form: str = "start.pzform") -> Designer:
    """A designer with a form of ``root`` open: without a project, the search looks in the form's folder."""
    d = Designer(language_servers=False)
    d.doc = Document(Form(), path=root / form)
    return d


def test_finds_matches_with_the_editor_options(tmp_path):
    root = _folder(tmp_path)
    files = project_search.project_files(root)
    assert root / ".venv" / "lib" / "site.py" not in files
    assert project_search.project_files(root, "*.py") == [root / "main.py", root / "ui" / "home.py"]
    assert project_search.project_files(root, "ui/") == [root / "ui" / "home.py"]
    matches = project_search.find_in_text("a hello\nhello hello", _pattern("hello", case=False, word=False,
                                                                           regex=False))
    assert [(m.line, m.start, m.column) for m in matches] == [(1, 2, 3), (2, 0, 1), (2, 6, 7)]
    text, count = project_search.replace_text("x = f(1)\ny = f(2)", _pattern(r"f\((\d)\)", case=True, word=False,
                                                                                regex=True), r"g(\1)", True)
    assert (text, count) == ("x = g(1)\ny = g(2)", 2)


def test_the_panel_searches_the_project_and_opens_a_match(tmp_path):
    root = _folder(tmp_path)
    d = _designer(root)
    commands.run("find_in_project", d)
    assert d.search.visible and docks.PANELS["search"].available(d)
    d.search.query = "hello"
    d.search.search(wait=True)
    names = [f.path.name for f in d.search.results]
    assert names == ["README.md", "main.py", "home.py"]  # not the binary file or the .venv
    assert d.search.count == 3
    d.search.case = True
    d.search.search(wait=True)
    assert [f.path.name for f in d.search.results] == ["README.md", "main.py"]
    project_search.view(d, d.theme_obj)
    entry = d.search.results[1]
    d.search.open_match(entry.path, entry.matches[0])
    assert d.buffers.current is not None and d.buffers.current.path == root / "main.py"
    assert d.assist.cursor == (1, 13)
    d.search.query = "("
    d.search.regex = True
    d.search.search(wait=True)
    assert d.search.error and not d.search.results
    d.search.close()
    assert not docks.PANELS["search"].available(d)


def test_replace_all_edits_open_files_in_place_and_can_be_undone(tmp_path):
    root = _folder(tmp_path)
    d = _designer(root)
    d.buffers.open(root / "main.py")  # open in the editor, with an unsaved change
    d.buffers.current.text = "greeting = 'hello'\nprint(greeting, 'hello')\n"
    d.search.open(replace=True)
    d.search.query, d.search.replacement = "hello", "bye"
    d.search.search(wait=True)
    assert d.search.count == 4  # the unsaved text is what is searched
    assert d.search.replace_all() == 4
    assert d.buffers.current.text == "greeting = 'bye'\nprint(greeting, 'bye')\n"
    assert (root / "main.py").read_text(encoding="utf-8") == "greeting = 'hello'\nprint(greeting)\n"  # not saved
    assert (root / "README.md").read_text(encoding="utf-8") == "Say bye\n"
    assert "bye" in (root / "ui" / "home.py").read_text(encoding="utf-8").lower()
    assert d.search.results == []
    assert d.search.undo_replace() == 2  # the files written to the disk
    assert (root / "README.md").read_text(encoding="utf-8") == "Say hello\n"


def test_replace_leaves_open_forms_alone_and_changes_their_code(tmp_path):
    root = _folder(tmp_path)
    d = _designer(root, "ui/home.pzform")
    d.doc.code = "def show():\n    return 'Hello world'\n"
    (root / "ui" / "home.pzform").write_text('{"label": "hello"}', encoding="utf-8")
    d.search.query, d.search.replacement = "hello", "bye"
    d.search.search(wait=True)
    assert {f.path.name for f in d.search.results} >= {"home.pzform", "home.py"}
    d.search.replace_all()
    assert (root / "ui" / "home.pzform").read_text(encoding="utf-8") == '{"label": "hello"}'
    assert d.doc.code == "def show():\n    return 'bye world'\n" and d.doc.dirty
    assert "Hello" in (root / "ui" / "home.py").read_text(encoding="utf-8")  # saved with the form
