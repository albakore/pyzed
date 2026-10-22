"""The designer's keymap (like Zed's): contexts, keymap.json, conflicts, resets and the keymap editor."""

import json

from pyzed.designer import commands, keymap
from pyzed.designer.app import Designer
from pyzed.designer.keymap import Binding


def test_every_action_has_a_label_and_the_defaults_resolve():
    km = keymap.get()
    ids = keymap.actions()
    assert {"workspace::save", "canvas::nudge_left", "project_panel::rename", "code_panel::find",
            "editor::delete_line"} <= set(ids)
    assert all(b.action in ids for b in km.defaults)
    assert km.conflicts() == {}
    assert km.resolve("ctrl-s", ("Canvas", "Workspace")) == "workspace::save"
    assert km.resolve("ctrl-n", ("ProjectPanel", "Workspace")) == "project_panel::new_file"  # the deepest wins
    assert km.resolve("ctrl-n", ("Canvas", "Workspace")) == "workspace::new"
    assert km.resolve("ctrl-z", ("Workspace",)) is None  # undo is the canvas's
    assert km.keys_for("workspace::open_keymap") == "ctrl-k ctrl-s"


def test_names_and_keys_are_written_like_zed():
    assert keymap.display_name("workspace::save_as") == "workspace::SaveAs"
    assert keymap.action_id("workspace::SaveAs") == "workspace::save_as"
    assert keymap.action_id("editor::delete_line") == "editor::delete_line"
    assert keymap.action_id("DeleteLine") == "editor::delete_line"
    assert keymap.action_id("workspace::Nope") is None
    assert keymap.normalize("Ctrl+Shift+K") == "ctrl-shift-k"
    assert keymap.normalize("cmd-shift-p") == "ctrl-shift-p"
    assert keymap.normalize("ctrl- ") == "ctrl-space"
    assert keymap.normalize("ctrl-k ctrl-s") == "ctrl-k ctrl-s"
    assert keymap.normalize("ctrl-j ctrl-s") == "ctrl-j ctrl-s"
    assert keymap.normalize("ctrl-j ctrl-s", "Editor") is None  # editor chords start with ctrl-k
    assert keymap.normalize("hyper-k") is None and keymap.normalize("a b c") is None


def test_the_users_file_overrides_and_removes_defaults():
    km = keymap.get()
    km.path.parent.mkdir(parents=True, exist_ok=True)
    km.path.write_text("""// my keys
    [
      {"context": "Workspace", "bindings": {"ctrl-alt-s": "workspace::SaveAs", "ctrl-s": null,}},
      {"context": "Editor", "bindings": {"ctrl-alt-d": ["editor::DuplicateLineDown", {}], "ctrl-d": null}},
      {"context": "Canvas", "bindings": {"ctrl-d": "workspace::Save", "x": "nope::Nothing", "bad-key": "Undo"}},
      {"context": "Nowhere", "bindings": {}}
    ]""", encoding="utf-8")
    km.load()
    assert km.resolve("ctrl-alt-s", ("Workspace",)) == "workspace::save_as"
    assert km.resolve("ctrl-s", ("Canvas", "Workspace")) is None
    assert km.editor_keymap() == {"ctrl-alt-d": "duplicate_line_down", "ctrl-d": None}
    assert km.resolve("ctrl-d", ("Canvas",)) == "workspace::save"  # the user's binding wins...
    assert km.conflicts() == {("Canvas", "ctrl-d"): [Binding("ctrl-d", "workspace::duplicate", "Canvas"),
                                                     Binding("ctrl-d", "workspace::save", "Canvas", True)]}
    assert len(km.errors) == 3  # ...and the unknown action, keys and context are reported
    assert km.is_changed("workspace::save") and km.is_changed("editor::select_next")
    assert not km.is_changed("workspace::undo")


def test_changes_are_saved_in_zeds_format_and_reset():
    km = keymap.get()
    [save] = km.bindings_for("workspace::save")
    assert km.change(save, "ctrl-alt-w") is None
    assert km.add("canvas::open_main_event", "f4") is None
    assert km.add("editor::delete_line", "ctrl-j ctrl-d", "Editor")  # an error: not an editor chord
    [enter] = km.bindings_for("project_panel::open")
    km.remove(enter)
    km.save()
    text = km.path.read_text(encoding="utf-8")
    assert text.startswith("//")
    blocks = json.loads(keymap._strip_comments(text))
    assert blocks == [{"context": "Workspace", "bindings": {"ctrl-s": None, "ctrl-alt-w": "workspace::Save"}},
                      {"context": "Canvas", "bindings": {"f4": "canvas::OpenMainEvent"}},
                      {"context": "ProjectPanel", "bindings": {"enter": None}}]
    again = keymap.Keymap(km.path)
    assert again.user == km.user and again.errors == []
    assert again.keys_for("workspace::save") == "ctrl-alt-w" and again.keys_for("project_panel::open") is None
    km.reset("workspace::save")
    assert km.keys_for("workspace::save") == "ctrl-s" and km.is_changed("canvas::open_main_event")
    km.reset_all()
    assert km.user == [] and km.keys_for("project_panel::open") == "enter"


def test_the_designer_runs_keys_through_the_keymap(tmp_path):
    d = Designer(tmp_path / "x.pzform")
    km = keymap.get()
    d.focus = "canvas"
    km.add("workspace::grid", "ctrl-alt-g")
    shown = d.show_grid
    d.on_key("ctrl-alt-g")
    assert d.show_grid != shown
    km.add("workspace::grid", "ctrl-j ctrl-g", "Canvas")  # a chord: the first key waits for the second
    d.on_key("ctrl-j")
    assert d.key_prefix == "ctrl-j"
    d.on_key("ctrl-g")
    assert d.key_prefix is None and d.show_grid == shown
    km.reset_all()
    d.on_key("f1")
    assert d.dialog == "shortcuts"
    groups = dict(commands.shortcut_groups())
    assert ("Grid", "g") in groups["View"]


def test_the_keymap_editor_records_keys_and_marks_conflicts(tmp_path):
    d = Designer(tmp_path / "x.pzform")
    t = d.theme_obj
    d.on_key("ctrl-k")
    d.on_key("ctrl-s")
    assert d.dialog == "keymap"
    ke = d.keymap_editor
    assert d.dialog_view(t) is not None
    ke.set_query("save as")
    assert [info.id for info, _ in ke.rows()] == ["workspace::save_as"]
    [save_as] = keymap.get().bindings_for("workspace::save_as")
    ke.start("workspace::save_as", save_as)
    assert d.dialog_view(t) is not None
    d.on_key("shift")  # a modifier alone is not recorded
    d.on_key("ctrl-d")
    assert ke.keys == "ctrl-d" and ke.clash() is None  # Duplicate is the canvas's, not the workspace's
    ke.set_context("Canvas")
    assert ke.clash()
    d.on_key("enter")
    assert ke.recording is None and keymap.get().resolve("ctrl-d", ("Canvas",)) == "workspace::save_as"
    ke.set_filter("conflicts")
    ke.set_query("")
    assert {info.id for info, _ in ke.rows()} == {"workspace::duplicate", "workspace::save_as"}
    assert ke.conflict_note(keymap.get().bindings_for("workspace::duplicate")[0])
    assert d.dialog_view(t) is not None
    ke.start("workspace::save_as")
    d.on_key("escape")
    assert ke.recording is None and d.dialog == "keymap"
    ke.reset("workspace::save_as")
    assert keymap.get().conflicts() == {}
    d.on_key("escape")
    assert d.dialog is None
    ke.edit_file()
    assert d.buffers.current is not None and d.buffers.current.path == keymap.get().path


def test_tooltips_show_the_keys_in_force():
    km = keymap.get()
    assert keymap.shown_keys("new") == "ctrl-n" and keymap.shown_keys("workspace::stop") == "shift-f5"
    assert keymap.shown_keys("nope", "f9") == "f9"  # keys outside the keymap
    [run] = km.bindings_for("workspace::run")
    km.change(run, "ctrl-r")
    assert keymap.shown_keys("run") == "ctrl-r"
    km.remove(km.bindings_for("workspace::run")[0])
    assert keymap.shown_keys("run") is None  # unbound: the tooltip shows no keys
    km.reset_all()


def test_no_tooltip_writes_its_keys_into_the_text():
    """Tooltips take ``keys=`` (drawn as key caps from the keymap); text like "Stop (Shift+F5)" goes stale when
    the user changes the keys, and ``format_keys`` in an f-string printed "([['Ctrl', 'N']])"."""
    import re
    from pathlib import Path

    root = Path(keymap.__file__).parent
    pattern = re.compile(r"\{ui\.format_keys\(|tooltip=[^,\n]*(\((Ctrl|Shift|Alt|F\d)|\+ \"  )")
    found = [f"{path.name}:{n}" for path in root.glob("*.py")
             for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1) if pattern.search(line)]
    assert found == []
