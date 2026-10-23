"""Tests for the designer's code editor: project detection, completion, diagnostics, code lens and settings."""

import time
from pathlib import Path

import pytest

from pyzed import designer
from pyzed.designer import intellisense as intel
from pyzed.designer import code_panel, keymap, lsp, settings
from pyzed.designer.app import Designer
from pyzed.designer.intellisense import CodeIntel, CompletionItem

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PYZED_CONFIG_DIR", str(tmp_path / "config"))


def uv_project(tmp_path):
    """A uv-style project: pyproject at the root, a .venv, the UI in ui/ and a src/ package."""
    root = tmp_path / "app"
    (root / "ui").mkdir(parents=True)
    (root / "src" / "app").mkdir(parents=True)
    (root / ".venv").mkdir()
    (root / ".venv" / "pyvenv.cfg").write_text("home = /usr\n")
    (root / "pyproject.toml").write_text('[project]\nname = "app"\nversion = "0.1.0"\n')
    (root / "ui" / "helpers.py").write_text('def greet(name: str) -> str:\n    """Says hello."""\n    return name\n')
    return root


# -- project and environment -----------------------------------------------------


def test_environment_of_a_form_in_a_subfolder(tmp_path):
    root = uv_project(tmp_path)
    env = lsp.find_environment(root / "ui" / "login.py")
    assert env.root == root.resolve()
    assert env.venv == (root / ".venv").resolve()
    assert (root / "ui").resolve() in env.extra_paths
    assert (root / "src").resolve() in env.extra_paths
    config = env.settings()["environment"]
    assert config["python"] == str((root / ".venv").resolve())
    assert str((root / "ui").resolve()) in config["extra-paths"]


def test_environment_without_project(tmp_path, monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    folder = tmp_path / "loose"
    folder.mkdir()
    env = lsp.find_environment(folder / "form.py")
    assert env.root == folder.resolve() and env.venv is None and env.extra_paths == []


def test_uri_roundtrip(tmp_path):
    path = tmp_path / "with space" / "a.py"
    assert lsp.path_of(lsp.uri(path)) == path.resolve()


# -- text helpers ------------------------------------------------------------------


def test_word_and_trigger():
    assert intel.word_before("    form.sta", 13) == "sta"
    assert intel.should_complete("    form.", 10)
    assert intel.should_complete("    pri", 8)
    assert not intel.should_complete("    # form.", 12)
    assert not intel.should_complete('    x = "form.', 15)
    assert not intel.should_complete("    x = 1.", 11)
    assert not intel.should_complete("    ", 5)


def test_filter_puts_prefix_matches_first_and_private_last():
    items = [CompletionItem(n) for n in ("_private", "__dunder__", "value", "values_list", "avalue", "other")]
    assert [i.label for i in intel.filter_items(items, "val")] == ["value", "values_list", "avalue"]
    assert [i.label for i in intel.filter_items(items, "")][-2:] == ["_private", "__dunder__"]
    assert CompletionItem("_x").private and not CompletionItem("__init__").private


def test_apply_completion_replaces_the_word():
    text, line, column = intel.apply_completion("a\n    form.sta = 1", 2, 13, CompletionItem("status"))
    assert text == "a\n    form.status = 1" and (line, column) == (2, 16)
    text, _, column = intel.apply_completion("x = httpx.Cli", 1, 14, CompletionItem("Client"))
    assert text == "x = httpx.Client" and column == 17


def test_apply_edits():
    edit = {"range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
            "newText": "import os\n"}
    assert intel.apply_edits("x = 1\n", [edit]) == "import os\nx = 1\n"
    shifted = {"range": {"start": {"line": 5, "character": 1}, "end": {"line": 5, "character": 2}}, "newText": "y"}
    assert intel.apply_edits("a\nbxc", [shifted], line_offset=4) == "a\nbyc"


def test_item_from_lsp():
    item = intel.item_from_lsp({"label": "Client", "kind": 7, "detail": "<class 'Client'>",
                                "documentation": {"kind": "markdown", "value": "An HTTP client."},
                                "additionalTextEdits": [{"range": {}, "newText": "import x\n"}]})
    assert (item.kind, item.icon[0], item.documentation) == ("class", "component", "An HTTP client.")
    assert item.additional_edits


def test_compose_swaps_the_handler():
    module = 'import os\n\n\ndef a(form, event):\n    pass\n\n\ndef b(form, event):\n    pass\n'
    text, offset = intel.compose(module, "b", "def b(form, event):\n    form.x\n")
    assert offset == 7 and text.split("\n")[7:9] == ["def b(form, event):", "    form.x"]
    text, offset = intel.compose(module, "missing", "def missing(form, event):\n    pass\n")
    assert text.endswith("def missing(form, event):\n    pass\n") and text.split("\n")[offset] == "def missing(form, event):"
    assert intel.compose(module, None, "x") == ("x", 0)


# -- designer-aware completion ------------------------------------------------------


def login_form():
    return designer.load(ROOT / "examples" / "designer" / "login.pzform")


def test_designer_completions():
    form = login_form()
    names = [i.label for i in intel.designer_completions(form, "    form.", 10)]
    assert "email" in names and "status" in names and "close" in names
    props = {i.label: i for i in intel.designer_completions(form, "    form.email.te", 18)}
    assert "text" in props and "focus" in props and props["focus"].kind == "method"
    assert [i.label for i in intel.designer_completions(form, "    event.", 11)] == ["sender", "name", "value"]
    assert intel.designer_completions(form, "    other.", 11) is None
    assert intel.designer_completions(form, "    form.nothing.", 18) is None


# -- code lens ---------------------------------------------------------------------


def test_definitions_and_wiring():
    source = "class Base:\n    def run(self):\n        pass\n\n\nclass Child(Base):\n    pass\n\n\ndef go(form, event):\n    go(form, event)\n"
    defs = {d.name: d for d in intel.definitions(source)}
    assert defs["run"].kind == "method" and defs["Child"].bases == ("Base",)
    assert (defs["go"].line, defs["go"].column) == (10, 4)
    assert intel.name_counts(source)["go"] == 2
    form = login_form()
    assert intel.wired_to(form, "sign_in_click") == [("sign_in", "click")]
    assert ("form", "load") in intel.wired_to(form, "form_load")


def test_lenses_without_servers():
    ci = CodeIntel()
    source = "class Base:\n    pass\n\n\nclass Child(Base):\n    pass\n\n\ndef sign_in_click(form, event):\n    pass\n"
    ci.update(source, None, source)
    ci.refresh_lenses(login_form())
    lenses = {lens.name: lens.text for lens in ci.lenses}
    assert lenses["Base"] == "1 reference · 1 implementation"  # used as a base class
    assert lenses["sign_in_click"] == "0 references · on sign_in.click"


def test_diagnostics_map_to_the_editor():
    ci = CodeIntel()
    module = 'import os\n\n\ndef a(form, event):\n    pass\n'
    ci.update(module, "a", "def a(form, event):\n    undefined\n")
    ci._raw["ty"] = [
        {"range": {"start": {"line": 4, "character": 4}, "end": {"line": 4, "character": 13}}, "severity": 1,
         "message": "Name `undefined` used when not defined", "source": "ty", "code": "unresolved-reference"},
        {"range": {"start": {"line": 0, "character": 7}, "end": {"line": 0, "character": 9}}, "severity": 2,
         "message": "`os` imported but unused", "source": "ty"},
    ]
    diags = ci.diagnostics()
    assert len(diags) == 1 and (diags[0].line, diags[0].column, diags[0].level) == (2, 5, "error")
    assert diags[0].label == "[unresolved-reference] Name `undefined` used when not defined"


# -- settings ----------------------------------------------------------------------


def test_settings_roundtrip():
    s = settings.load()
    assert s.tab_size == 4 and s.ty and s.ruff
    s.show_whitespace, s.tab_size, s.theme = True, 2, "Ayu Dark"
    path = settings.save(s)
    assert path is not None and path.exists()
    again = settings.load()
    assert again.show_whitespace and again.tab_size == 2 and again.theme == "Ayu Dark"
    assert settings.EditorSettings.from_dict({"tab_size": 99, "font_size": "x"}).tab_size == 16


def test_editor_feature_settings():
    s = settings.EditorSettings()
    assert s.auto_close and s.folding and s.minimap and s.cursor_shape == "bar" and s.cursor_blink
    assert settings.EditorSettings.from_dict({"cursor_shape": "triangle"}).cursor_shape == "bar"
    assert settings.EditorSettings.from_dict({"cursor_shape": "block", "minimap": False}).cursor_shape == "block"


def test_zoom_changes_and_resets_the_font_size(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    a = d.assist
    a.zoom(1)
    a.zoom(1)
    assert a.settings.font_size == settings.DEFAULT_FONT + 2 and settings.load().font_size == a.settings.font_size
    a.zoom(-1)
    assert a.settings.font_size == settings.DEFAULT_FONT + 1
    a.zoom(0)
    assert a.settings.font_size == settings.DEFAULT_FONT
    for _ in range(40):
        a.zoom(1)
    assert a.settings.font_size == settings.MAX_FONT


# -- the designer ------------------------------------------------------------------


def test_designer_completion_flow(tmp_path):
    path = tmp_path / "login.pzform"
    path.write_text((ROOT / "examples" / "designer" / "login.pzform").read_text())
    (tmp_path / "login.py").write_text((ROOT / "examples" / "designer" / "login.py").read_text())
    d = Designer(path, language_servers=False)
    d.edit_event("sign_in", "click")
    text = d.editing[1].rstrip("\n") + "\n    form.em"
    line = text.count("\n") + 1
    d.set_code_buffer(text[:-1])
    d.set_code_cursor(line, 11)
    d.set_code_buffer(text)  # one character typed
    d.set_code_cursor(line, 12)
    assert d.assist.completion is not None
    assert "up" in d.assist.captured_keys and d.assist.completion.selected.label == "email"
    assert d.focus == "code"
    commands = d.on_key("enter")
    assert isinstance(commands, list) and len(commands) == 2
    assert d.editing[1].endswith("    form.email")
    assert d.assist.completion is None and d.assist.cursor == (line, 15)
    d.set_code_buffer(d.editing[1] + ".")
    d.set_code_cursor(line, 16)
    labels = [i.label for i in d.assist.completion.shown]
    assert "text" in labels and "placeholder" in labels
    d.on_key("escape")
    assert d.assist.completion is None and d.assist.captured_keys == ("ctrl-,", "alt-z", "ctrl-.", "alt-shift-o", "alt-left", "alt-right")


def test_designer_settings_dialog_and_status(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    d.open_editor_settings()
    t = d.theme_obj
    assert d.dialog_view(t) is not None
    d.assist.set("show_whitespace", True)
    assert settings.load().show_whitespace
    assert d.view() is not None
    for shape in settings.CURSOR_SHAPES:
        d.assist.set("cursor_shape", shape)
        assert d.view() is not None
    d.assist.set("minimap", False)
    d.assist.set("folding", False)
    assert d.view() is not None

    for key in code_panel.SETTINGS_SECTIONS:
        d.assist.show_settings_section(key)
        assert d.dialog_view(t) is not None


def test_new_editor_settings_are_sanitized():
    s = settings.EditorSettings.from_dict({"line_height": "huge", "cursor_width": 9, "keymap": {"undo": "ctrl-q", 3: "x"}})
    assert s.line_height == "standard" and s.cursor_width == 4.0 and s.keymap == {"undo": "ctrl-q"}
    assert settings.EditorSettings().scrollbar and not settings.EditorSettings().wrap


def test_key_bindings_parse_like_zed():
    from pyzed.ui.editor import DEFAULT_KEYS, keymap_for, parse_keys

    assert parse_keys("Ctrl+Shift+K") == "ctrl-shift-k"
    assert parse_keys("shift-alt-ctrl-up") == "ctrl-alt-shift-up"
    assert parse_keys("ctrl-k ctrl-c") == "ctrl-k ctrl-c"
    assert parse_keys("ctrl--") == "ctrl--" and parse_keys("esc") == "escape"
    assert parse_keys("ctrl-a ctrl-b") is None and parse_keys("hyper-x") is None and parse_keys("") is None
    keymap = keymap_for({"delete_line": "ctrl-shift-d, alt-d", "select_next": ""})
    assert keymap["ctrl-shift-d"] == "delete_line" and keymap["alt-d"] == "delete_line"
    assert all(keymap[k] is None for k in DEFAULT_KEYS["delete_line"] + DEFAULT_KEYS["select_next"])
    # The editor accepts every default binding and action name.
    from pyzed import ui

    ui.editor("keys", keymap={k: a for a, keys in DEFAULT_KEYS.items() for k in keys})
    with pytest.raises(ValueError):
        ui.editor("keys", keymap={"ctrl-d": "no_such_action"})
    with pytest.raises(ValueError):
        ui.editor("keys", keymap={"hyper-d": "undo"})


def test_designer_key_bindings(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    a = d.assist
    km = keymap.get()
    [delete_line] = km.bindings_for("editor::delete_line")
    assert km.change(delete_line, "Ctrl+Shift+")  # not keys
    assert km.change(delete_line, "Ctrl+Shift+D") is None
    assert a.editor_keymap() == {"ctrl-shift-k": None, "ctrl-shift-d": "delete_line"}
    # Alt+Z toggles wrapping, and the code panel's keys can move too.
    assert not a.settings.wrap
    d.on_key("alt-z")
    assert a.settings.wrap
    [go_to_line] = km.bindings_for("code_panel::go_to_line")
    km.change(go_to_line, "ctrl-alt-g")
    d.on_key("ctrl-g")
    assert a.goto is None
    d.on_key("ctrl-alt-g")
    assert a.goto == ""
    km.reset_all()
    assert km.keys_for("code_panel::go_to_line") == "ctrl-g" and a.editor_keymap() == {}


def test_old_editor_keys_move_to_the_keymap(tmp_path):
    settings.save(settings.EditorSettings(keymap={"delete_line": "ctrl-shift-d", "go_to_line": ""}))
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    km = keymap.get()
    assert km.path.exists() and settings.load().keymap == {} and d.assist.settings.keymap == {}
    assert km.keys_for("editor::delete_line") == "ctrl-shift-d" and km.keys_for("code_panel::go_to_line") is None


# -- real language servers ------------------------------------------------------------


def wait(predicate, timeout=15.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.mark.skipif(lsp.Environment(Path.cwd()).tool("ty") is None, reason="ty is not installed")
def test_ty_completes_and_reports_in_a_subfolder(tmp_path):
    root = uv_project(tmp_path)
    (root / ".venv" / "pyvenv.cfg").unlink()  # no real venv: ty uses the designer's Python
    handlers = root / "ui" / "login.py"
    module = "from helpers import greet\n\n\ndef ok_click(form, event):\n    pass\n"
    handlers.write_text(module)
    ci = CodeIntel(settings.EditorSettings(ruff=False))
    ci.attach(handlers)
    try:
        assert wait(lambda: ci.servers["ty"].ready)
        ci.update(module, "ok_click", "def ok_click(form, event):\n    gre\n    missing_name\n")
        assert wait(lambda: any("missing_name" in d.message for d in ci.diagnostics()))
        diags = ci.diagnostics()
        assert all(d.line in (2, 3) for d in diags if d.severity == 1)
        assert not any("helpers" in d.message for d in diags), diags  # ui/ is an import root
        got = []
        assert ci.complete(2, 8, got.append)
        assert wait(lambda: bool(got))
        greet = next(i for i in got[0] if i.label == "greet")
        assert greet.kind == "function" and "Says hello" in greet.documentation
    finally:
        ci.shutdown()
