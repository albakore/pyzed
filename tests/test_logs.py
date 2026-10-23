"""The designer's logs and error handling: ``ui.Log`` sources and selection, ``ui.console``'s line menu,
``ui.ErrorInfo`` and the error boundaries, and the Logs panel, error dialog and hooks of the designer."""

import logging
import sys
import threading
from dataclasses import replace
from types import SimpleNamespace

import pytest

import pyzed as pz
from pyzed import _core, ui
from pyzed.designer import commands, docks, logs
from pyzed.designer.app import Designer
from ui_tree import install

T = pz.themes.ONE_DARK


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


@pytest.fixture
def app():
    d = Designer(language_servers=False)
    yield d
    d.logs.uninstall()


def _raise(exc: BaseException):
    try:
        raise exc
    except BaseException as err:  # noqa: BLE001
        return err


# -- ui.Log and ui.console -----------------------------------------------------------------------------


def test_log_entries_keep_source_detail_and_origin():
    log = ui.Log()
    first = log.write("error", "boom", source="run", detail="Traceback...", origin=("/x.py", 3))
    again = log.write("error", "boom", source="run", detail="Traceback...")
    other = log.write("error", "boom", source="project")
    assert first is again and first.count == 2 and other.id != first.id
    assert log.find(first.id) is first and log.find(999) is None
    assert first.origin == ("/x.py", 3)
    assert log.text([first.id]).endswith("[error] [run] boom (×2)\nTraceback...")
    assert "[project] boom" in log.text() and log.text([]) == ""


def test_capture_without_a_console(monkeypatch):
    # In an app without a console (pythonw, a windowed bundle on Windows) sys.stdout/stderr are None.
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    log = ui.Log().capture()
    print("hello")
    sys.stderr.write("partial")
    assert not sys.stdout.isatty()
    log.release()
    assert sys.stdout is None and sys.stderr is None
    assert [(e.level, e.text) for e in log.entries] == [("stdout", "hello"), ("stderr", "partial")]


def test_log_selection_click_shift_ctrl_and_keep():
    log = ui.Log()
    ids = [log.write("info", f"line {i}").id for i in range(5)]
    sel = ui.LogSelection()
    sel.click(ids[1], ids)
    sel.click(ids[3], ids, shift=True)
    assert sel.ids == set(ids[1:4])
    sel.click(ids[0], ids, ctrl=True)
    assert ids[0] in sel and len(sel) == 4
    sel.click(ids[0], ids, ctrl=True)
    assert ids[0] not in sel
    sel.select(ids)
    log.clear()
    sel.keep(log.entries)
    assert len(sel) == 0 and sel.anchor is None


def test_console_selects_lines_shows_details_and_filters_by_source(tree):
    log = ui.Log()
    log.write("info", "opened", source="document")
    err = log.write("error", "ZeroDivisionError: division by zero", source="run", detail="Traceback (most recent...)")
    sel = ui.LogSelection()
    menus = []
    view = ui.console(log.entries, selection=sel, on_context=menus.append, sources=[("run", "Run")],
                      show_source=True, theme=T)
    assert "Traceback (most recent...)" not in view.texts() and "run" in view.texts()
    rows = view.find_all("events", lambda n: n.props.get("click") is not None and n.props.get("right_click"))
    assert len(rows) == 3  # the two lines and the empty space under them
    rows[2].props["right_click"]()
    assert menus == [None]
    rows[1].props["click"](SimpleNamespace(shift=False, ctrl=False, logo=False))
    assert sel.ids == {err.id}
    view = ui.console(log.entries, selection=sel, on_context=menus.append, theme=T)
    assert "Traceback (most recent...)" in view.texts()  # a selected line shows its detail
    rows = view.find_all("events", lambda n: n.props.get("right_click") is not None and n.props.get("click"))
    rows[0].props["right_click"](None)
    assert menus[-1].text == "opened" and sel.ids == {log.entries[0].id}  # right click selects the line first
    only_run = ui.console(log.entries, source="run", sources=[("run", "Run")], theme=T)
    assert "opened" not in only_run.texts() and "ZeroDivisionError: division by zero" in only_run.texts()


# -- errors ----------------------------------------------------------------------------------------------


def test_error_info_finds_the_origin_outside_libraries(tmp_path):
    user = tmp_path / "handlers.py"
    user.write_text("def go():\n    return {}['missing']\n")
    namespace = {}
    exec(compile(user.read_text(), str(user), "exec"), namespace)
    err = _raise_from(namespace["go"])
    info = ui.ErrorInfo.from_exception(err, where="go()")
    assert info.kind == "KeyError" and info.summary == "KeyError: 'missing'"
    assert info.origin == (str(user), 2) and info.location == "handlers.py:2"
    report = info.report()
    assert report.startswith("go(): KeyError: 'missing'") and "Traceback (most recent call last)" in report
    assert ui.ErrorInfo.from_exception(ValueError()).summary == "ValueError"


def _raise_from(fn):
    try:
        fn()
    except Exception as err:  # noqa: BLE001
        return err
    raise AssertionError("did not raise")


def test_error_boundary_returns_a_card_and_reports(tree):
    assert ui.error_boundary(lambda: "fine") == "fine"
    seen = []

    def broken():
        raise RuntimeError("panel broke")

    card = ui.error_boundary(broken, on_error=seen.append, title="The panel", on_details=seen.append, theme=T)
    assert seen[0].summary == "RuntimeError: panel broke" and seen[0].where == "The panel"
    assert "The panel" in card.texts() and "RuntimeError: panel broke" in card.texts()
    card.button_with("Details").args[1]()
    assert seen[-1] is seen[0]
    assert ui.error_boundary(broken, fallback=lambda info: info.kind) == "RuntimeError"
    # a failing on_error never hides the card
    assert ui.error_boundary(broken, on_error=lambda info: 1 / 0, theme=T).kind == "container"


def test_error_dialog_has_copy_go_to_and_logs(tree):
    info = ui.ErrorInfo.from_exception(_raise(ValueError("bad")), where="save()")
    hits = []
    dialog = ui.error_dialog(info, lambda: hits.append("close"), on_go_to=lambda: hits.append("go"),
                             go_to_label="Go to x.py:3", on_logs=lambda: hits.append("logs"), more=2, theme=T)
    editor = dialog.find("code_editor")
    assert editor.props["readonly"] is True and "ValueError: bad" in editor.args[1]
    dialog.button_with("Go to x.py:3").args[1]()
    dialog.button_with("Show in Logs").args[1]()
    assert hits == ["go", "logs"]
    assert any("2 more errors" in text for text in dialog.texts())


def test_readonly_editor_flag_reaches_the_core(tree):
    assert ui.editor("e", "text", readonly=True, theme=T).props["readonly"] is True
    assert ui.editor("e", "text", theme=T).props["readonly"] is False


# -- the designer ------------------------------------------------------------------------------------------


def test_designer_logs_events_and_commands(app):
    logs.event("document", "Saved %s", "a.pzform")
    logs.log("project").warning("uv is missing")
    commands.run("logs", app)
    entries = [(e.level, e.source, e.text) for e in app.logs.log.entries]
    assert ("event", "document", "Saved a.pzform") in entries
    assert ("warning", "project", "uv is missing") in entries
    assert ("event", "command", "Logs") in entries
    assert app.layout.is_showing("logs", app)
    logging.getLogger("other.library").warning("not ours")  # only pyzed's loggers come in
    assert all(e.text != "not ours" for e in app.logs.log.entries)
    app.view()


def test_logs_panel_filters_by_type_and_level(app):
    logs.event("document", "Opened a")
    logs.event("project", "Synced")
    app.logs.set_source("project")
    assert [e.text for e in logs.shown_entries(app.logs)] == ["Synced"]
    app.logs.set_source(None)
    app.logs.toggle_level("event")
    assert logs.shown_entries(app.logs) == []
    app.logs.toggle_level("event")
    assert logs.type_of("pyzed.designer.project") == "project" and logs.type_of("py.warnings") == "system"
    assert logs.level_name(logs.EVENT) == "event" and logs.level_name(logging.DEBUG) == "debug"


def test_report_opens_the_error_dialog_once(app):
    info = ui.ErrorInfo.from_exception(_raise(ValueError("bad")), where="save()")
    app.logs.report(info)
    assert app.dialog == "error" and app.logs.error is info
    app.logs.report(info)  # the same error again is not logged twice
    assert sum(1 for e in app.logs.log.entries if e.level == "error") == 1
    other = ui.ErrorInfo.from_exception(_raise(KeyError("k")), where="open()")
    app.logs.report(other)
    assert app.logs.error is info and app.logs.more == 1
    app.view()
    app.close_dialog()
    assert app.dialog is None and app.logs.error is None
    app.dialog = "settings"  # another dialog is open: a toast instead
    app.logs.report(ui.ErrorInfo.from_exception(_raise(OSError("disk")), where="x()"))
    assert app.dialog == "settings" and app.toasts[-1].kind == "error"
    app.prefs.error_dialogs = False
    app.dialog = None
    app.logs.report(ui.ErrorInfo.from_exception(_raise(OSError("quiet")), where="y()"))
    assert app.dialog is None and app.logs.log.entries[-1].text == "y(): OSError: quiet"


def test_a_broken_panel_shows_an_error_card(app, monkeypatch):
    def broken(d, t):
        raise RuntimeError("properties broke")

    monkeypatch.setitem(docks.PANELS, "properties", replace(docks.PANELS["properties"], view=broken))
    app.view()
    app.view()
    errors = [e for e in app.logs.log.entries if e.level == "error"]
    assert len(errors) == 1 and "properties broke" in errors[0].text and errors[0].detail
    assert app.dialog is None  # the card is in the panel; no dialog for drawing errors


def test_the_window_survives_a_view_that_fails(app, monkeypatch):
    monkeypatch.setattr(app, "_view", lambda: 1 / 0)
    assert app.view() is not None
    assert "ZeroDivisionError" in app.logs.log.entries[-1].text


def test_a_dialog_that_fails_shows_the_error_dialog(app, monkeypatch):
    def broken(d, t):
        raise RuntimeError("settings broke")

    monkeypatch.setattr("pyzed.designer.dialogs.settings", broken)
    app.dialog = "settings"
    app.view()
    assert app.dialog == "error" and app.logs.error.summary == "RuntimeError: settings broke"


def test_go_to_opens_the_file_at_the_line(app, tmp_path):
    path = tmp_path / "handlers.py"
    path.write_text("a = 1\nb = 1 / 0\n")
    command = app.logs.go_to((str(path), 2))
    assert command is not None and app.buffers.current.path == path and app.assist.cursor == (2, 1)
    assert app.logs.go_to((str(tmp_path / "missing.py"), 1)) is None


def test_line_menu_and_keys(app, tmp_path):
    path = tmp_path / "x.py"
    path.write_text("boom\n")
    app.show_panel("logs")
    app.logs.log.write("error", "boom", source="run", detail=f'  File "{path}", line 1', origin=(str(path), 1))
    entry = app.logs.log.entries[-1]
    app.logs.selection.click(entry.id, [entry.id])
    app.window_pointer = (300, 400)
    app.logs.open_menu("logs", entry)
    labels = [i.label for i in app.logs.menu_items() if isinstance(i, ui.MenuItem)]
    assert "Copy line" in labels and "Go to x.py:1" in labels and "Only Run" in labels
    app.view()
    app.focus_panel("logs")
    handled, result = app.logs.on_key("logs", "ctrl-c")
    assert handled and result is not None
    app.on_key("escape")
    assert app.logs.menu is None
    app.on_key("ctrl-a")
    assert len(app.logs.selection) == len(logs.shown_entries(app.logs))
    app.logs.open_menu("console", None)
    assert [i.label for i in app.logs.menu_items() if isinstance(i, ui.MenuItem)][0] == "Copy all"


def test_running_form_errors_reach_the_logs(app, tmp_path):
    path = tmp_path / "handlers.py"
    path.write_text("x\n")
    app.console.event("error", f'go.click: go() raised\n  File "{path}", line 1, in go\nNameError: x')
    line = app.console.log.entries[-1]
    assert line.origin == (str(path), 1)
    logged = app.logs.log.entries[-1]
    assert logged.source == "run" and logged.text == "go.click: go() raised" and "NameError" in logged.detail


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_hooks_catch_callback_and_thread_errors(app):
    app.logs.install(file=False)
    try:
        assert sys.excepthook == app.logs._excepthook
        err = _raise(ValueError("from a click"))
        sys.excepthook(type(err), err, err.__traceback__)
        assert app.dialog == "error" and app.logs.error.summary == "ValueError: from a click"
        app.close_dialog()
        thread = threading.Thread(target=lambda: 1 / 0, name="worker")
        thread.start()
        thread.join()
        assert any("ZeroDivisionError" in e.text and "worker" in e.text for e in app.logs.log.entries)
    finally:
        app.logs.uninstall()
    assert sys.excepthook is not app.logs._excepthook


def test_log_file_is_written(app, tmp_path):
    app.logs.install(file=True)
    try:
        logs.event("document", "Saved file.pzform")
        app.logs._file.flush()
        text = app.logs.file.read_text(encoding="utf-8")
        assert "Saved file.pzform" in text and "pyzed.designer.document" in text
    finally:
        app.logs.uninstall()
    assert app.logs.file is None


def test_status_bar_counts_errors(app):
    assert app.logs_status_item(app.theme_obj) is None
    app.logs.log.write("error", "bad")
    assert app.logs_status_item(app.theme_obj) is not None
    assert logs.summary(app.logs.log.entries) == (1, 0)


def test_readonly_editor_in_the_core():
    assert _core.code_editor("ro", "text", readonly=True) is not None
