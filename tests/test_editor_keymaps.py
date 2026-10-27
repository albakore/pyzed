"""The code editor's base keymaps (like Zed's), Vim mode, problems in the minimap and Ctrl+Space's longer docs."""

import pytest

from pyzed import ui
from pyzed.designer import code_panel, keymap, settings
from pyzed.designer import intellisense as intel
from pyzed.designer.app import Designer
from pyzed.designer.code_panel import HoverCard, vim_command
from pyzed.designer.intellisense import CompletionItem, Diagnostic
from pyzed.theme import themes
from pyzed.ui.editor import _diagnostic_colors


@pytest.fixture(autouse=True)
def _vscode_keys():
    yield
    keymap.set_base(keymap.DEFAULT_BASE)


def test_every_base_keymap_is_valid():
    ids = keymap.actions()
    assert set(keymap.BASE_TITLES) == set(keymap.BASE_KEYMAPS) and keymap.DEFAULT_BASE in keymap.BASE_KEYMAPS
    km = keymap.get()
    for name, bindings in keymap.BASE_KEYMAPS.items():
        for context, keys, action in bindings:
            assert keymap.normalize(keys, context) == keys, (name, keys)
            assert action in ids, (name, action)
        km.set_base(name)
        # the editor takes every key and action the base keymap hands it
        ui.editor("keys", keymap=km.editor_keymap())


def test_a_base_keymap_goes_over_the_defaults_and_under_the_user():
    km = keymap.get()
    keymap.set_base("JetBrains")
    assert km.resolve("ctrl-b", ("CodePanel", "Workspace")) == "code_panel::go_to_definition"
    assert km.resolve("ctrl-d", ("Editor",)) == "editor::duplicate_selection"
    editor = km.editor_keymap()
    assert editor["ctrl-d"] == "duplicate_selection" and editor["ctrl-w"] == "select_larger_syntax_node"
    assert editor["ctrl-b"] is None  # the designer's key: the editor leaves it alone
    [duplicate] = [b for b in km.bindings_for("editor::duplicate_selection") if b.keys == "ctrl-d"]
    km.add("editor::delete_line", "ctrl-d", "Editor")
    assert km.resolve("ctrl-d", ("Editor",)) == "editor::delete_line" and duplicate.keys == "ctrl-d"
    keymap.set_base("Emacs")
    editor = km.editor_keymap()
    assert editor["ctrl-x u"] == "undo" and editor["ctrl-a"] == "move_to_beginning_of_line"
    assert editor["ctrl-x ctrl-s"] is None and km.resolve("ctrl-x ctrl-s", ("Workspace",)) == "workspace::save"
    keymap.set_base("nope")
    assert km.base_name == keymap.DEFAULT_BASE and km.base == []


def test_the_settings_choose_the_base_keymap_and_vim(tmp_path):
    s = settings.EditorSettings.from_dict({"base_keymap": "Nope", "vim_mode": True})
    assert s.base_keymap == "VSCode" and s.vim_mode and s.diagnostic_underlines
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    a = d.assist
    a.set("base_keymap", "SublimeText")
    assert keymap.get().base_name == "SublimeText" and settings.load().base_keymap == "SublimeText"
    assert keymap.get().resolve("ctrl-shift-d", ("Editor",)) == "editor::duplicate_line_down"
    d.edit_whole_file()
    a.set("vim_mode", True)
    a.action_ran("vim_insert")
    assert a.vim_mode == "vim_insert"
    item = code_panel.vim_status_item(a, d.theme_obj)
    assert item is not None
    a.set("vim_mode", False)
    assert code_panel.vim_status_item(a, d.theme_obj) is None and a.vim_mode == "vim_normal"


def test_vim_commands():
    code = "a = 1\nb = a + a\nc = 3\n"
    assert vim_command("w", code, 1) == ("write", None)
    assert vim_command("wq", code, 1) == ("write_quit", None) and vim_command("q!", code, 1) == ("quit", None)
    assert vim_command("12", code, 1) == ("line", 12) and vim_command("$", code, 1) == ("line", 4)
    assert vim_command("set nowrap", code, 1) == ("set", ("wrap", False))
    assert vim_command("s/a/x/", code, 2) == ("replace", [((2, 5, 2, 6), "x")])
    assert vim_command("s/a/x/g", code, 2) == ("replace", [((2, 5, 2, 6), "x"), ((2, 9, 2, 10), "x")])
    kind, ranges = vim_command("%s/(\\w) =/\\1:/g", code, 1)
    assert kind == "replace" and [text for _, text in ranges] == ["a:", "b:", "c:"]
    assert vim_command("1,2s/a/[&]/g", code, 3)[1][0][1] == "[a]"
    assert vim_command("frobnicate", code, 1) is None


def test_the_vim_command_line_runs_commands(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    a = d.assist
    a.action_ran("vim_command")
    assert a.command == "" and code_panel.command_bar(a, d.theme_obj) is not None
    a.set_command("set wrap")
    a.submit_command()
    assert a.command is None and a.settings.wrap
    a.action_ran("vim_command")
    d.on_key("escape")
    assert a.command is None


def test_keyword_docs():
    doc = intel.keyword_doc("for")
    assert doc.startswith('### The "for" statement') and "```python" in doc and "`break`" in doc
    assert intel.keyword_doc("with") and intel.keyword_doc("spam") == ""


def test_ctrl_space_shows_more_of_the_documentation(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    a = d.assist
    t = d.theme_obj
    long_doc = "\n\n".join(f"Paragraph {i}. " + "words " * 30 for i in range(20))
    a.hover = HoverCard(1, 1, 1, 4, 10.0, 10.0, 18.0, text=long_doc, loading=False)
    assert "ctrl-space" in a.hover_keys
    a.run_action("show_completions")
    assert a.hover.expanded and a.completion is None
    assert code_panel.hover_card(a, a.hover, t, 600, 500) is not None
    a.run_action("show_completions")
    assert not a.hover.expanded
    # the mouse moving on the same word keeps the card
    card = a.hover
    a.hovered({"line": 1, "column": 2, "start": 1, "end": 4, "x": 12.0, "y": 10.0, "height": 18.0})
    assert a.hover is card
    a.hover = None
    item = CompletionItem("print", kind="function", detail="def print(*values)", documentation=long_doc)
    a.completion = code_panel.Completion(1, 1, [item], [item])
    a.run_action("show_completions")
    assert a.completion.expanded
    assert code_panel.completion_popup(a, t) is not None


def test_hover_at_the_cursor_explains_keywords(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    a = d.assist
    a._text = "for x in range(3):\n    pass\n"
    a._line = lambda n: a._text.split("\n")[n - 1]
    a.cursor = (1, 2)
    a.run_action("hover")
    assert a.hover is not None and a.hover.at_cursor and "for" in a.hover.text
    assert (a.hover.start, a.hover.end) == (1, 4)


def test_problems_reach_the_editor(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    a = d.assist
    diags = [Diagnostic(2, 1, 2, 4, 1, "boom"), Diagnostic(5, 3, 5, 6, 2, "hm"), Diagnostic(3, 1, 3, 2, 4, "hint")]
    a.intel.diagnostics = lambda: diags
    assert a.editor_diagnostics() == [(2, 1, 2, 4, 1), (5, 3, 5, 6, 2)]  # hints left out
    a.cursor = (1, 1)
    a.go_to_diagnostic(1)
    assert a.cursor == (2, 1)
    a.go_to_diagnostic(1)
    assert a.cursor == (5, 3)
    a.go_to_diagnostic(1)
    assert a.cursor == (2, 1)  # wraps around
    a.go_to_diagnostic(-1)
    assert a.cursor == (5, 3)


def test_the_editor_takes_diagnostics_vim_and_hover_keys():
    t = themes.get("Pyzed Dark")
    colors = _diagnostic_colors(t, [(1, 1, 1, 3, "error"), (2, 1, 2, 2, 3), (3, 1, 3, 2, "hint")])
    assert [c[-1] for c in colors][-1] == t.error  # the most severe drawn last
    ui.editor("x", "a = (\n", diagnostics=[(1, 5, 1, 6, "error")], diagnostic_underlines=False,
              hover_keys=("ctrl-space", "ctrl-k ctrl-i"), vim=True)
    ui.editor("x", "", hover_keys=("hyper-x",))  # keys that are not keys are left out
