"""Tests for the Zed features of the code editor: editor actions, the designer's search and "go to line",
and the opt-in telemetry."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

import pyzed as pz
from pyzed import ui
from pyzed.designer import code_panel, commands, telemetry
from pyzed.designer.app import Designer


def test_editor_actions_are_listed_and_checked():
    names = pz.Command.editor_actions()
    for name in ("undo", "redo", "select_next", "add_selection_below", "move_line_up", "toggle_comments",
                 "duplicate_line_down", "join_lines", "select_all_matches"):
        assert name in names
    assert "editor_action" in repr(pz.Command.editor_action("ed", "undo"))
    assert "editor_action" in repr(pz.Command.editor_action("ed", "editor::SelectNext"))
    with pytest.raises(ValueError):
        pz.Command.editor_action("ed", "teleport")


def test_editor_takes_the_new_options():
    ranges = [(1, 1, 1, 4)]
    assert "Widget" in repr(ui.editor("ed", "foo", on_action=print, highlights=ranges, match_brackets=False,
                                      selection_highlight=False))
    pz.Command.select_editor_ranges("ed", ranges)
    pz.Command.replace_editor_ranges("ed", [((1, 1, 1, 4), "bar")])


# -- search -------------------------------------------------------------------------


def test_find_matches_uses_byte_columns_and_options():
    text = "ñandú = 1\nfoo Foo food\n"
    assert code_panel.find_matches(text, "ú")[0] == [(1, 6, 1, 8)]  # ñ takes two bytes
    matches, _ = code_panel.find_matches(text, "foo")
    assert matches == [(2, 1, 2, 4), (2, 5, 2, 8), (2, 9, 2, 12)]
    assert len(code_panel.find_matches(text, "foo", case=True)[0]) == 2
    assert code_panel.find_matches(text, "foo", word=True)[0] == [(2, 1, 2, 4), (2, 5, 2, 8)]
    assert code_panel.find_matches(text, r"fo+d", regex=True)[0] == [(2, 9, 2, 13)]
    assert code_panel.find_matches(text, "1\nfoo", case=True)[0] == [(1, 11, 2, 4)]
    matches, error = code_panel.find_matches(text, "(", regex=True)
    assert matches == [] and error


def test_parse_goto():
    assert code_panel.parse_goto("12", 50) == (12, 1)
    assert code_panel.parse_goto(" 7:5 ", 50) == (7, 5)
    assert code_panel.parse_goto("99", 50) == (50, 1)
    assert code_panel.parse_goto("x", 50) is None


def test_designer_search_and_replace(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    text = "count = 1\ncount += 1\nprint(count)\n"
    d.set_code_buffer(text)
    d.set_code_cursor(2, 2)
    a = d.assist
    d.on_key("ctrl-f")
    assert a.search is not None and a.search.query == "count"  # the word under the cursor
    assert len(a.search.matches) == 3
    a.set_query("count")
    assert a.search.index == 1  # the match at or after the cursor
    assert "select_editor_ranges" in repr(a.next_match())
    assert a.search.index == 2
    a.next_match()
    assert a.search.index == 0
    a.toggle_option("regex")
    a.set_replacement("total")
    assert "replace_editor_ranges" in repr(a.replace_all())
    assert "batch" in repr(a.select_all_matches())
    d.set_code_buffer(text.replace("count", "n"))
    assert a.search.matches == []
    d.on_key("escape")
    assert a.search is None
    d.on_key("ctrl-h")
    assert a.search.replacing
    d.on_key("ctrl-g")
    a.set_goto("3:7")
    a.submit_goto()
    assert a.goto is None and a.cursor == (3, 7)


def test_regex_replacement_expands_groups(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    d.set_code_buffer("a1 b2\n")
    a = d.assist
    a.open_search()
    a.toggle_option("regex")
    a.set_query(r"([a-z])(\d)")
    a.set_replacement(r"\2\1")
    assert [a._replacement(m) for m in a.search.matches] == ["1a", "2b"]


def test_search_bar_renders(tmp_path):
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    d.edit_whole_file()
    d.assist.open_search(replacing=True)
    d.assist.open_goto()
    assert "Widget" in repr(code_panel.code_panel(d, d.theme_obj))


def test_shortcut_reference_lists_the_editor_keys():
    groups = dict(commands.shortcut_groups())
    keys = {k for rows in groups.values() for _, k in rows}
    assert {"ctrl-d", "alt-shift-down", "alt-up", "ctrl-/", "ctrl-f", "ctrl-g", "ctrl-k ctrl-0"} <= keys


# -- telemetry ---------------------------------------------------------------------


def test_telemetry_is_off_until_turned_on(tmp_path):
    tel = telemetry.reset(tmp_path / "telemetry.json")
    assert not tel.active
    tel.count("command.save")
    with tel.timed("command.save"):
        pass
    assert tel.data["counters"] == {} and not (tmp_path / "telemetry.json").exists()
    tel.configure(enabled=True)
    assert tel.installation and tel.active
    tel.count("editor.undo", 2)
    tel.timing("render", 12.0)
    tel.timing("render", 400.0)
    report = tel.report()
    assert report["counters"] == {"editor.undo": 2}
    assert report["timings"]["render"]["count"] == 2 and report["timings"]["render"]["max_ms"] == 400.0
    assert report["timings"]["render"]["buckets"][-1] == 1
    tel.save()
    again = telemetry.Telemetry(tmp_path / "telemetry.json")
    assert again.enabled and again.data["counters"] == {"editor.undo": 2}
    tel.clear()
    assert tel.data["counters"] == {}


def test_telemetry_can_be_forced_off(tmp_path, monkeypatch):
    tel = telemetry.reset(tmp_path / "telemetry.json")
    tel.configure(enabled=True)
    monkeypatch.setenv("PYZED_TELEMETRY", "0")
    tel.count("x")
    assert not tel.active and tel.data["counters"] == {}


def test_commands_and_editor_actions_are_counted(tmp_path):
    tel = telemetry.reset(tmp_path / "telemetry.json")
    tel.configure(enabled=True)
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    commands.run("console", d)
    d.edit_whole_file()
    d.assist.action_ran("select_next")
    counters = tel.data["counters"]
    assert counters["command.console"] == 1 and counters["editor.select_next"] == 1
    assert tel.data["timings"]["command.console"]["count"] == 1


def test_telemetry_sends_only_to_an_endpoint(tmp_path):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(204)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        tel = telemetry.reset(tmp_path / "telemetry.json")
        tel.configure(enabled=True)
        tel.count("editor.undo")
        assert not tel.send()  # no endpoint: nothing leaves the computer
        tel.configure(endpoint=f"http://127.0.0.1:{server.server_port}/collect")
        assert tel.send()
        assert received[0]["counters"] == {"editor.undo": 1} and received[0]["app"] == "pyzed-designer"
        assert set(received[0]) >= {"installation", "version", "os", "timings", "since", "until"}
        assert tel.data["counters"] == {} and tel.last_sent
        tel.configure(endpoint="ftp://example.com")
        assert not tel.send() and "http" in tel.last_error
    finally:
        server.shutdown()


def test_telemetry_settings_render(tmp_path):
    from pyzed.designer import dialogs

    tel = telemetry.reset(tmp_path / "telemetry.json")
    d = Designer(tmp_path / "x.pzform", language_servers=False)
    assert "Widget" in repr(dialogs.telemetry_group(d, d.theme_obj))
    tel.configure(enabled=True, endpoint="https://example.com/t")
    assert "Widget" in repr(dialogs.settings(d, d.theme_obj))
