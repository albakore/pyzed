"""Services (pyzed.services) and the non-visual components of Pyzed Design built on them."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import pyzed as pz
from pyzed import designer, services
from pyzed.designer import components, nonvisual, surface
from pyzed.designer.model import Control, Form, save
from pyzed.designer.runtime import FormApp, open_form


# -- services on their own ---------------------------------------------------------------------------------------------
def test_timer_counts_and_stops_when_it_does_not_repeat():
    ticks = []
    timer = pz.Timer(250, repeat=False, on_tick=ticks.append)
    assert len(timer.subscriptions()) == 1
    timer.tick()
    assert ticks == [1] and not timer.running and timer.subscriptions() == []
    timer.tick()
    assert ticks == [1]
    timer.start()
    assert timer.running and timer.count == 0


def test_handlers_with_and_without_a_value():
    seen = []
    timer = pz.Timer(on_tick=lambda: seen.append("called"))
    timer.tick()
    assert seen == ["called"]
    timer.enabled = False
    timer.tick()
    assert seen == ["called"]
    with pytest.raises(ValueError):
        timer.on("nope", print)
    with pytest.raises(TypeError):
        pz.Timer(tick=print)


def test_shortcut_matches_combos_in_any_spelling():
    fired = []
    save = pz.Shortcut("Ctrl+S, cmd-s", on_activate=fired.append)
    assert save.matches("ctrl-s") and save.matches("cmd-s")
    assert not save.matches("ctrl-shift-s") and not save.matches("s")
    save.handle("ctrl-s")
    save.handle("ctrl-o")
    assert fired == ["ctrl-s"]
    assert pz.Shortcut("ctrl-shift-p").matches("ctrl-shift-p")
    assert pz.Shortcut("alt-enter").matches("alt-enter")


def test_file_watcher_reports_created_modified_and_deleted(tmp_path):
    events = []
    watcher = pz.FileWatcher(tmp_path, pattern="*.txt", on_created=lambda p: events.append(("created", p)),
                             on_modified=lambda p: events.append(("modified", p)),
                             on_deleted=lambda p: events.append(("deleted", p)),
                             on_change=lambda paths: events.append(("change", len(paths))))
    watcher._seen = watcher.snapshot()
    note = tmp_path / "a.txt"
    note.write_text("1")
    (tmp_path / "ignored.csv").write_text("x")
    watcher.check()
    assert events == [("created", str(note)), ("change", 1)]
    events.clear()
    note.write_text("longer")
    watcher.check()
    assert events == [("modified", str(note)), ("change", 1)]
    events.clear()
    note.unlink()
    watcher.check()
    assert events == [("deleted", str(note)), ("change", 1)]
    events.clear()
    assert watcher.check() == [] and events == []


def test_file_watcher_thread_starts_and_stops(tmp_path):
    seen = threading.Event()
    watcher = pz.FileWatcher(tmp_path, interval=20, on_created=lambda p: seen.set())
    watcher.running = True
    assert watcher.running
    (tmp_path / "new.txt").write_text("hi")
    assert seen.wait(3)
    watcher.running = False
    assert not watcher.running


def test_process_streams_lines_and_exit_code():
    lines, codes = [], []
    process = pz.Process(["python", "-c", "print('one'); print('two'); import sys; sys.exit(3)"],
                         on_output=lines.append, on_finished=codes.append)
    assert process.start()
    assert process.wait(10) == 3
    assert lines == ["one", "two"] and codes == [3] and not process.running


def test_process_input_and_failures():
    lines = []
    process = pz.Process(["python", "-c", "print(input().upper())"], on_output=lines.append)
    process.start()
    process.write("hola\n")
    process.wait(10)
    assert lines == ["HOLA"]
    failed = []
    assert not pz.Process("no-such-program-pyzed", on_failed=failed.append).start()
    assert failed and pz.Process(on_failed=failed.append).start() is False


def test_worker_reports_progress_and_result():
    progress, done = [], []
    worker = pz.Worker(on_progress=progress.append, on_done=done.append)

    def work(n):
        for i in range(n):
            worker.report(i)
        return n * 2

    worker.work = work
    assert worker.run(3)
    assert worker.wait(5) == 6
    assert progress == [0, 1, 2] and done == [6] and not worker.busy


def test_worker_failure_and_cancel():
    errors = []
    worker = pz.Worker(lambda: 1 / 0, on_failed=errors.append)
    worker.run()
    worker.wait(5)
    assert isinstance(errors[0], ZeroDivisionError)
    gate = threading.Event()
    slow = pz.Worker(lambda: gate.wait(5) and slow.cancelled)
    slow.run()
    assert not slow.run()  # still busy
    slow.cancel()
    gate.set()
    assert slow.wait(5) is True


class _Echo(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"path": self.path, "agent": self.headers.get("User-Agent")}).encode()
        self.send_response(404 if self.path == "/missing" else 200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        size = int(self.headers.get("Content-Length", 0))
        self.send_response(201)
        self.end_headers()
        self.wfile.write(self.rfile.read(size))

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), _Echo)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_http_request_answers(server):
    answers = []
    api = pz.HttpRequest(server + "/hello", on_response=answers.append)
    assert api.send()
    response = api.wait(10)
    assert response.ok and response.json() == {"path": "/hello", "agent": "Pyzed"} and answers == [response]
    api.send(server + "/missing")
    assert api.wait(10).status == 404 and not api.response.ok
    api.send(server, json={"a": 1})
    assert api.wait(10).status == 201 and api.response.json() == {"a": 1}
    failed = []
    broken = pz.HttpRequest("http://127.0.0.1:9/", timeout=2, on_failed=failed.append)
    broken.send()
    broken.wait(10)
    assert failed and broken.response is None


def test_settings_persist_between_runs(tmp_path):
    changes = []
    settings = pz.Settings("app", folder=tmp_path, defaults={"volume": 5}, on_change=changes.append)
    assert settings["volume"] == 5 and "volume" in settings and settings.get("missing", 1) == 1
    settings["volume"] = 7
    settings["volume"] = 7  # unchanged: no event
    assert changes == [("volume", 7)]
    again = pz.Settings("app", folder=tmp_path)
    assert again["volume"] == 7 and again.keys() == ["volume"] and len(again) == 1
    del again["volume"]
    assert "volume" not in pz.Settings("app", folder=tmp_path)
    with pytest.raises(KeyError):
        again["volume"]


def test_file_dialog_answers_and_filters():
    chosen, cancelled = [], []
    dialog = pz.FileDialog("open_many", filters="Images: png, *.jpg\nText: txt", on_chosen=chosen.append,
                           on_cancelled=lambda: cancelled.append(True))
    assert isinstance(dialog.show(), pz.Command) and repr(dialog.show()) == "Command.pick_files(...)"
    assert repr(pz.FileDialog("save").show()) == "Command.save_file(...)"
    dialog.chose(["/a.png", "/b.png"])
    dialog.chose([])
    assert chosen == [["/a.png", "/b.png"]] and cancelled == [True] and dialog.path is None
    assert services.parse_filters("Images: png, *.jpg; Text: txt") == [("Images", ["png", "jpg"]), ("Text", ["txt"])]
    assert services.parse_filters({"Data": "csv tsv"}) == [("Data", ["csv", "tsv"])]
    with pytest.raises(ValueError):
        pz.FileDialog("delete")


def test_clipboard_notices_new_text():
    changes = []
    clipboard = pz.Clipboard(watch=True, on_change=changes.append)
    assert len(clipboard.subscriptions()) == 1 and pz.Clipboard().subscriptions() == []
    clipboard.seen("first")  # what was there when it started is not a change
    clipboard.seen("first")
    clipboard.seen("second")
    assert changes == ["second"]
    assert repr(clipboard.copy("hi")) == "Command.copy(...)" and clipboard.text == "hi"


def test_events_from_threads_run_without_an_app():
    got = []
    worker = pz.Worker(lambda: threading.current_thread().name, on_done=got.append)
    worker.run()
    worker.wait(5)
    assert got == ["pyzed-worker"]  # no app running: called where it was raised


class FakeTray:
    """``_core``'s tray functions, recording what the service asks for."""

    def __init__(self, fail=None):
        self.shown, self.fail = {}, fail

    def tray_set(self, id, on_event, tooltip="", title="", icon=None, menu=None):
        if self.fail:
            raise RuntimeError(self.fail)
        self.shown[id] = {"on_event": on_event, "tooltip": tooltip, "title": title, "icon": icon, "menu": menu}

    def tray_remove(self, id):
        self.shown.pop(id, None)

    def post(self, call):
        raise RuntimeError("no app")


@pytest.fixture
def tray(monkeypatch):
    fake = FakeTray()
    for name in ("tray_set", "tray_remove", "post"):
        monkeypatch.setattr(services._core, name, getattr(fake, name))
    return fake


def test_tray_menu_from_text_and_lists():
    menu = services.parse_tray_menu("Open\n[x] Pause\n---\nSpeed\n  Slow\n  [ ] Fast\nQuit")
    assert [getattr(e, "text", e) for e in menu] == ["Open", "Pause", "-", "Speed", "Quit"]
    assert menu[1].checked is True and menu[0].checked is None
    assert [i.text for i in menu[3].items] == ["Slow", "Fast"] and menu[3].items[1].checked is False
    item = services.TrayItem("Exit", id="quit")
    assert services.parse_tray_menu(["A", "-", item]) == [services.TrayItem("A"), "-", item]
    assert item.key == "quit" and services.parse_tray_menu(None) == []


def test_tray_icon_shows_updates_and_hides(tray):
    icon = pz.TrayIcon(tooltip="Backups", menu="Open\n-\n[x] Pause\nMore\n  Logs")
    assert not tray.shown and icon.show() and icon.visible
    shown = tray.shown[icon._number]
    assert shown["tooltip"] == "Backups" and shown["icon"] is None
    assert shown["menu"] == [("item", "Open", "Open", True, False, []), ("separator", "", "", True, False, []),
                             ("check", "Pause", "Pause", True, True, []),
                             ("submenu", "More", "More", True, False, [("item", "Logs", "Logs", True, False, [])])]
    icon.tooltip = "Backing up"  # shown at once
    assert tray.shown[icon._number]["tooltip"] == "Backing up"
    assert icon.item("Logs").text == "Logs" and icon.item("nope") is None
    icon.set_checked("Pause", False)
    assert not icon.checked("Pause") and tray.shown[icon._number]["menu"][2][4] is False
    icon.hide()
    assert not icon.visible and icon._number not in tray.shown


def test_tray_icon_events_flip_checks(tray):
    got = []
    icon = pz.TrayIcon(menu=["Open", services.TrayItem("Pause", checked=False)], on_click=lambda: got.append("click"),
                       on_menu=got.append)
    icon.show()
    on_event = tray.shown[icon._number]["on_event"]
    for event, value in (("click", None), ("menu", "Pause"), ("menu", "Open")):
        on_event(event, value)
    for _ in range(100):  # no app: handled on a thread of its own
        if len(got) == 3:
            break
        threading.Event().wait(0.02)
    assert got == ["click", "Pause", "Open"] and icon.checked("Pause")


def test_tray_icon_reports_why_it_cannot_show(tray):
    tray.fail = "the desktop shows no tray icons"
    got = []
    icon = pz.TrayIcon(on_failed=got.append)
    assert icon.show() is False and not icon.visible
    assert got == [tray.fail] and icon.error == tray.fail


# -- the designer's non-visual components ------------------------------------------------------------------------------
NON_VISUAL = ("timer", "shortcut", "file_watcher", "process", "worker", "http_request", "clipboard", "settings",
              "file_dialog", "notification", "tray_icon", "system_info", "launcher", "network_monitor",
              "power_monitor")
#: The ones that reach the operating system share the System category with the file picker and the drop zone.
SYSTEM = ("shortcut", "file_watcher", "process", "clipboard", "file_dialog", "notification", "tray_icon", "system_info",
          "launcher", "network_monitor", "power_monitor")


def test_every_non_visual_component_has_a_service():
    for type_ in NON_VISUAL:
        spec = components.get(type_)
        assert not spec.visual
        assert spec.category == (components.SYSTEM if type_ in SYSTEM else components.NON_VISUAL)
        assert type_ in nonvisual.FACTORIES
        service = nonvisual.FACTORIES[type_](spec.create(type_ + "1", 0, 0, 10, 10))
        for prop in spec.props:  # each property is the service's attribute or read when the form opens
            attr = nonvisual.ALIASES.get((type_, prop.name), prop.name)
            assert hasattr(service, attr) or prop.name in ("autostart", "send_on_load", "remember",
                                                                                   "show_on_load"), (type_, prop)
        for event in spec.events:
            assert event in service.events or event == "work", (type_, event)
        assert spec.all_events == spec.events  # no mouse events: they are never on screen


def test_non_visual_components_stay_out_of_the_form():
    app = designer.Designer()
    app.doc.add("panel", 20, 20, 200, 120)
    app.pick_tool("timer")()  # a click in the toolbox puts it in the tray at once
    timer = app.doc.form["timer1"]
    assert app.tool is None and app.doc.selection == ["timer1"] and timer.parent is None
    app.drop_tool("process", (40, 40))  # dropped on the panel: still the form's
    assert app.doc.form["process1"].parent is None
    assert not app.doc.can_contain("panel1", "timer1")
    # a rubber band over everything selects only what is on the form
    app.pointer = app.view_pointer = (0, 0)
    app.press_empty()
    app.pointer_moved_view(600, 400)
    app.release()
    assert app.doc.selection == ["panel1"]
    assert surface.tray_rows(["a", "b", "c"], 320) == [["a", "b"], ["c"]]
    assert surface.tray(app, 640, app.theme) is not None
    app.press_tray("timer1")
    assert app.doc.selection == ["timer1"]
    app.open_context_menu("timer1")
    labels = [getattr(i, "label", None) for i in app._context_items()]
    assert "Group in a row" not in labels and "Delete" in labels


def test_designer_screenshot_with_the_tray(tmp_path):
    app = designer.Designer()
    for type_ in ("timer", "file_watcher", "http_request"):
        app.add_non_visual(type_)
    app.screenshot(tmp_path / "tray.png", size=(1280, 800), scale=1)
    assert (tmp_path / "tray.png").exists()


def _form(*controls):
    form = Form(width=300, height=200)
    for control in controls:
        form.add(control)
    return form


def test_runtime_timer_and_shortcut():
    calls = []
    form = _form(Control("ticker", "timer", props={"interval": 100, "repeat": False}, events={"tick": "on_tick"}),
                 Control("save", "shortcut", props={"keys": "ctrl-s"}, events={"activate": "on_save"}))
    form.events["key"] = "on_key"
    app = FormApp(form, {"on_tick": lambda f, e: calls.append(("tick", e.value)),
                         "on_save": lambda f, e: calls.append(("save", e.value)),
                         "on_key": lambda f, e: calls.append(("key", e.value))})
    runtime = app.runtime
    assert runtime.subscriptions() == []  # nothing ticks before the form opens
    runtime.load()
    assert len(runtime.subscriptions()) == 1
    proxy = app.form
    assert proxy.ticker.running and proxy.ticker.interval == 100
    proxy.ticker.tick()
    assert calls == [("tick", 1)] and not proxy.ticker.running and runtime.subscriptions() == []
    proxy.ticker.start()
    assert proxy.ticker.running
    proxy.ticker.enabled = False
    assert runtime.subscriptions() == []
    app.on_key("ctrl-s")
    assert calls[-2:] == [("save", "ctrl-s"), ("key", "ctrl-s")]
    proxy.save.keys = "ctrl-o"
    assert runtime.form["save"].props["keys"] == "ctrl-o"
    app.on_key("ctrl-s")
    assert calls.count(("save", "ctrl-s")) == 1 and calls[-1] == ("key", "ctrl-s")


def test_runtime_worker_and_process():
    done = threading.Event()
    seen = {}

    def work(form, event):
        event.sender.report(50)
        return event.value * 2

    form = _form(Control("job", "worker", events={"work": "job_work", "progress": "job_progress",
                                                   "done": "job_done"}),
                 Control("cmd", "process", props={"command": "python -c \"print('hi')\""},
                         events={"output": "cmd_output", "finished": "cmd_finished"}))
    handlers = {
        "job_work": work,
        "job_progress": lambda f, e: seen.setdefault("progress", e.value),
        "job_done": lambda f, e: seen.setdefault("done", e.value),
        "cmd_output": lambda f, e: seen.setdefault("output", e.value),
        "cmd_finished": lambda f, e: (seen.setdefault("code", e.value), done.set()),
    }
    app = FormApp(form, handlers)
    app.runtime.load()
    assert app.form.job.run(21)
    assert app.form.job.wait(5) == 42
    assert app.form.cmd.start()
    assert done.wait(10)
    assert seen == {"progress": 50, "done": 42, "output": "hi", "code": 0}
    assert app.form.cmd.exit_code == 0 and not app.form.cmd.running


def test_settings_remember_controls_between_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("PYZED_CONFIG_DIR", str(tmp_path))

    def make():
        return _form(Control("name_box", "input", props={"text": ""}),
                     Control("prefs", "settings", props={"remember": "name_box"}))

    app = FormApp(make(), {})
    app.runtime.load()
    app.form.prefs["theme"] = "dark"
    assert app.form.prefs["theme"] == "dark" and "theme" in app.form.prefs
    app.runtime.ctx.on(app.runtime.form["name_box"], "change", "text")("Ada")
    app.on_close()
    saved = json.loads((tmp_path / "settings" / "Form1.prefs.json").read_text())
    assert saved["controls"] == {"name_box": "Ada"} and saved["theme"] == "dark"
    again = FormApp(make(), {})
    again.runtime.load()
    assert again.form.name_box.text == "Ada"


def test_runtime_tray_icon_shows_when_the_form_opens(tray):
    form = _form(Control("tray", "tray_icon", props={"tooltip": "Hi", "menu": "Open\n-\nQuit"},
                         events={"menu": "on_menu"}),
                 Control("quiet", "tray_icon", props={"show_on_load": False}))
    app = FormApp(form, {})
    app.runtime.load()
    tray_icon, quiet = app.runtime.services["tray"], app.runtime.services["quiet"]
    assert tray_icon.visible and tray.shown[tray_icon._number]["tooltip"] == "Hi"
    assert tray_icon.icon is None and [getattr(e, "text", e) for e in tray_icon.menu] == ["Open", "-", "Quit"]
    assert not quiet.visible
    app.form.tray.hide()
    assert not tray_icon.visible


def test_reload_rebuilds_the_services(tmp_path):
    path = tmp_path / "f.pzform"
    form = _form(Control("ticker", "timer", events={"tick": "on_tick"}))
    save(form, path)
    (tmp_path / "f.py").write_text("def on_tick(form, event):\n    pass\n")
    app = open_form(path)
    app.runtime.load()
    first = app.runtime.services["ticker"]
    assert app.runtime.reload(path)
    assert app.runtime.services["ticker"] is not first and app.runtime.services["ticker"].running


def test_form_screenshot_draws_no_non_visual_component(tmp_path):
    form = _form(Control("ticker", "timer", x=10, y=10, width=120, height=24))
    FormApp(form, {}).screenshot(tmp_path / "run.png", scale=1)
    assert (tmp_path / "run.png").exists()
