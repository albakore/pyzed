"""Tests for the code editor's IDE features: hover, go to definition, references, rename, quick fixes and the
language servers' environment."""

import sys
from pathlib import Path

import pytest

from pyzed.designer import intellisense as intel
from pyzed.designer import code_panel, lsp
from pyzed.designer.app import Designer
from pyzed.designer.intellisense import CodeAction, Diagnostic

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PYZED_CONFIG_DIR", str(tmp_path / "config"))


def login_designer(tmp_path):
    path = tmp_path / "login.pzform"
    path.write_text((ROOT / "examples" / "designer" / "login.pzform").read_text())
    (tmp_path / "login.py").write_text((ROOT / "examples" / "designer" / "login.py").read_text())
    return Designer(path, language_servers=False)


# -- positions and LSP answers --------------------------------------------------------


def test_columns_convert_between_bytes_and_utf16():
    line = 'x = "ñ😀" + y'
    assert intel.utf16_column(line, 1) == 0
    after = len('x = "ñ😀'.encode("utf-8")) + 1
    assert intel.utf16_column(line, after) == len('x = "ñ') + 2  # the emoji is two UTF-16 units
    assert intel.byte_column(line, intel.utf16_column(line, after)) == after
    assert intel.byte_column(line, 999) == len(line.encode("utf-8")) + 1
    assert intel.apply_edits(line, [{"range": {"start": {"line": 0, "character": 12}, "end": {
        "line": 0, "character": 13}}, "newText": "z"}]) == 'x = "ñ😀" + z'


def test_locations_and_hover_from_lsp(tmp_path):
    uri = lsp.uri(tmp_path / "a.py")
    rng = {"start": {"line": 3, "character": 4}, "end": {"line": 3, "character": 9}}
    locs = intel.locations_from_lsp([{"uri": uri, "range": rng}, {"targetUri": uri, "targetSelectionRange": rng},
                                     {"uri": "untitled:x", "range": rng}])
    assert [(loc.path.name, loc.line, loc.character) for loc in locs] == [("a.py", 3, 4), ("a.py", 3, 4)]
    assert intel.locations_from_lsp(None) == []
    text = intel.hover_text({"contents": {"kind": "markdown", "value": "```xml\nmodule os\n```\n---\nDocs"}})
    assert text.startswith("```python\nmodule os") and text.endswith("Docs")
    assert intel.hover_text({"contents": [{"language": "python", "value": "x: int"}, "more"]}) == \
        "```python\nx: int\n```\n\nmore"
    assert intel.hover_text(None) == ""


def test_workspace_edits_by_file(tmp_path):
    a, b = lsp.uri(tmp_path / "a.py"), lsp.uri(tmp_path / "b.py")
    edit = {"changes": {a: [{"newText": "x"}]},
            "documentChanges": [{"textDocument": {"uri": b, "version": 1}, "edits": [{"newText": "y"}]},
                                {"kind": "create", "uri": b}]}
    out = intel.edits_by_path(edit)
    assert {p.name: [e["newText"] for e in edits] for p, edits in out.items()} == {"a.py": ["x"], "b.py": ["y"]}
    assert intel.edits_by_path(None) == {}


def test_missing_packages_are_named_like_on_pypi():
    def diag(message, code="unresolved-import"):
        return Diagnostic(1, 1, 1, 2, 1, message, "ty", code)

    assert intel.missing_package(diag("Cannot resolve imported module `httpx`")) == "httpx"
    assert intel.missing_package(diag("Cannot resolve imported module `cv2.data`")) == "opencv-python"
    assert intel.missing_package(diag("Cannot resolve imported module `my_tools`")) == "my-tools"
    assert intel.missing_package(diag("Name `x` used when not defined", "unresolved-reference")) is None


def test_designer_hover_knows_the_form(tmp_path):
    form = login_designer(tmp_path).doc.form
    line = "    form.email.text"
    text = intel.designer_hover(form, line, 10, 15)
    assert "email" in text and "(control)" in text
    assert "text" in intel.designer_hover(form, line, 16, 20)
    assert intel.designer_hover(form, "    other = 1", 5, 10) == ""


def test_designer_fallback_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    env = lsp.find_environment(tmp_path / "form.py")
    assert env.venv is None
    # Without a project environment ty uses the designer's Python, so `import pyzed` resolves.
    assert env.settings()["environment"]["python"] == sys.prefix


# -- the designer flows without language servers ------------------------------------------


def test_go_to_definition_and_back_without_servers(tmp_path):
    d = login_designer(tmp_path)
    d.edit_whole_file()
    a = d.assist
    lines = a._text.split("\n")
    use = next(i for i, text in enumerate(lines, 1) if "return sign_in_click" in text)
    target = next(i for i, text in enumerate(lines, 1) if text.startswith("def sign_in_click"))
    a.cursor = (use, lines[use - 1].index("sign_in_click") + 3)
    a.go_to_definition()
    assert a.cursor == (target, 5) and a.back
    a.go_back()
    assert a.cursor[0] == use
    a.go_back(-1)
    assert a.cursor[0] == target
    a.cursor = (target + 2, lines[target + 1].index("email") + 2)
    a.go_to_definition()  # form.email: selects the control
    assert d.doc.selection == ["email"]


def test_rename_without_servers_keeps_the_event_wiring(tmp_path):
    d = login_designer(tmp_path)
    d.edit_event("sign_in", "click")
    a = d.assist
    handler = d.editing[0]
    first = a._text.split("\n")[0]
    a.cursor = (1, first.index(handler) + 2)
    assert a.start_rename() is not None and a.rename.old == handler
    a.set_rename_text("class")
    a.submit_rename()  # a keyword: refused
    assert d.doc.form.get("sign_in").events.get("click") == handler
    a.start_rename()
    a.set_rename_text("log_in")
    assert a.submit_rename() is not None and a.rename is None
    assert d.doc.form.get("sign_in").events.get("click") == "log_in"


def test_quick_fixes_offer_installing_a_missing_package(tmp_path):
    d = login_designer(tmp_path)
    d.edit_whole_file()
    a = d.assist
    a.intel._raw["ty"] = [{"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 4}},
                           "severity": 1, "message": "Cannot resolve imported module `httpx`", "source": "ty",
                           "code": "unresolved-import"}]
    a.d.projects.project = object()  # a project to add it to
    a.open_actions(1)
    assert a.actions is not None and "httpx" in a.actions.items[0].title and a.actions.items[0].run is not None
    assert d.view() is not None
    a.close_actions()
    assert a.actions is None


def test_workspace_edit_to_an_open_tab(tmp_path):
    d = login_designer(tmp_path)
    other = tmp_path / "helpers.py"
    other.write_text("def greet():\n    pass\n")
    d.edit_whole_file()
    a = d.assist
    edit = {"changes": {lsp.uri(other): [{"range": {"start": {"line": 0, "character": 4},
                                                    "end": {"line": 0, "character": 9}}, "newText": "hello"}]}}
    a.apply_workspace_edit(edit)
    buffer = d.buffers.items[d.buffers.index_of(other)]
    assert buffer.text.startswith("def hello():") and other.read_text().startswith("def greet():")


def test_cursor_stays_on_the_word_after_a_rename():
    ranges = [((3, 1, 3, 5), "ab"), ((3, 8, 3, 12), "xyz123")]
    assert code_panel._shifted((3, 10), ranges) == (3, 8)
    assert code_panel._shifted((3, 20), ranges) == (3, 20)  # -2 + 2
    assert code_panel._shifted((4, 3), ranges) == (4, 3)


def test_actions_menu_marks_one_preferred(tmp_path):
    d = login_designer(tmp_path)
    d.edit_whole_file()
    menu = code_panel.ActionMenu(1, 1)
    menu.items = [CodeAction("a", preferred=True), CodeAction("b", preferred=True), CodeAction("c")]
    assert code_panel.actions_menu(d.assist, menu, d.theme_obj) is not None


def test_rename_handler_updates_the_form(tmp_path):
    d = login_designer(tmp_path)
    handler = d.doc.form.get("sign_in").events["click"]
    d.doc.rename_handler(handler, "go")
    assert d.doc.form.get("sign_in").events["click"] == "go"
