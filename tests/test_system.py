"""The operating system: services (system info, launcher, network, battery), the file picker and the drop zone."""

import os
import socket

import pytest

import pyzed as pz
from pyzed import system, ui
from pyzed.designer import components, nonvisual
from pyzed.designer.model import Form
from pyzed.designer.runtime import FormApp
from pyzed.ui import system as ui_system


def test_system_info_knows_the_computer(tmp_path):
    info = pz.SystemInfo(disk_path=tmp_path)
    assert info.os in ("Windows", "macOS", "Linux") or info.os
    assert info.cpu_count >= 1 and info.python_version.count(".") == 2
    assert info.disk_free and info.disk_total and info.disk_free <= info.disk_total
    assert info.home == os.path.expanduser("~")
    assert info.env("PYZED_NOT_SET", "x") == "x"
    assert info.folder("home") == info.home and info.folder("documents")
    with pytest.raises(ValueError):
        info.folder("attic")
    seen = []
    info.on("update", seen.append)
    snapshot = info.check()
    assert seen == [snapshot] and {"os", "memory_available", "disk_free"} <= set(snapshot)


def test_launcher_opens_and_reports(monkeypatch, tmp_path):
    ran, seen = [], []
    launcher = pz.Launcher(on_opened=lambda v: seen.append(("opened", v)), on_failed=lambda v: seen.append(("failed", v)))
    monkeypatch.setattr(launcher, "_run", ran.append)
    monkeypatch.setattr(system.os, "startfile", lambda p: ran.append(["startfile", p]), raising=False)
    monkeypatch.setattr(system.webbrowser, "open", lambda url: ran.append(["browser", url]) or True)
    assert not launcher.open(str(tmp_path / "missing.txt")) and seen[-1][0] == "failed"
    file = tmp_path / "notes.txt"
    file.write_text("hi")
    assert launcher.open(str(file)) and seen[-1] == ("opened", str(file)) and str(file) in ran[-1][-1]
    assert launcher.open("https://example.com") and ran[-1] == ["browser", "https://example.com"]
    assert launcher.email("ada@example.com", subject="Hi there") and ran[-1][1].startswith("mailto:ada@example.com?")
    assert pz.Launcher.is_link("mailto:a@b.c") and not pz.Launcher.is_link("C:\\files\\a.txt")
    assert launcher.reveal(str(file)) and seen[-1] == ("opened", str(file))


def test_network_monitor_raises_changes(monkeypatch):
    seen = []
    monitor = pz.NetworkMonitor(on_change=lambda v: seen.append(("change", v)), on_online=lambda: seen.append("online"),
                                on_offline=lambda: seen.append("offline"))
    answers = iter([True, True, False, True])
    monkeypatch.setattr(monitor, "reachable", lambda: next(answers))
    for _ in range(4):
        monitor.check()
    assert seen == [("change", True), ("change", False), "offline", ("change", True), "online"]
    assert monitor.online is True


def test_network_monitor_reaches_a_local_server():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        monitor = pz.NetworkMonitor(host="127.0.0.1", port=server.getsockname()[1], timeout=1)
        assert monitor.reachable()
    finally:
        server.close()


def test_power_monitor_events(monkeypatch):
    readings = iter([(50.0, True), (50.0, False), (15.0, False), (14.0, False)])
    monkeypatch.setattr(system, "battery", lambda: next(readings))
    seen = []
    monitor = pz.PowerMonitor(on_change=lambda v: seen.append(v), on_low=lambda v: seen.append(("low", v)),
                              on_unplugged=lambda: seen.append("unplugged"))
    assert monitor.has_battery and monitor.plugged
    monitor.check()
    monitor.check()
    monitor.check()
    assert seen == [(50.0, False), "unplugged", (15.0, False), ("low", 15.0), (14.0, False)]


def test_battery_and_memory_never_raise():
    percent, plugged = system.battery()
    assert percent is None or 0 <= percent <= 100
    total, available = system.memory()
    assert total is None or total > 0


# -- the file picker and the drop zone -------------------------------------------------------------------------------
def test_pick_returns_the_dialog_command():
    got = []
    command = ui_system.pick(got.append, mode="open", filters="Images: png, jpg", directory="~")
    assert repr(command) == "Command.pick_files(...)"
    assert repr(ui_system.pick(got.append, mode="save", file_name="a.txt")) == "Command.save_file(...)"
    with pytest.raises(ValueError):
        ui_system.pick(got.append, mode="nope")


def test_file_input_builds():
    for mode in ui_system.MODES:
        assert ui.file_input("/tmp/a.txt", lambda p: None, mode=mode, button="Browse") is not None
    assert ui.file_input(["a", "b"], None, mode="open_many", disabled=True) is not None


def test_accepts_extensions_patterns_and_folders(tmp_path):
    assert ui_system.accepts("photo.PNG", ["png", ".jpg"])
    assert not ui_system.accepts("notes.txt", ["png", "jpg"])
    assert ui_system.accepts("backup.tar.gz", ["*.tar.gz"]) and ui_system.accepts("x.bin", [])
    assert ui_system.accepts(str(tmp_path), ["folder"]) and not ui_system.accepts(str(tmp_path), ["file"])


@pytest.fixture
def zones():
    ui_system._zones.clear()
    yield ui_system._zones
    ui_system._zones.clear()


def test_dropped_files_reach_the_drop_zone(zones):
    seen = []
    images = ui.DropZone.create(accept=["png"], on_drop=lambda e: seen.append(("images", e.value)),
                                on_reject=lambda e: seen.append(("rejected", e.value)),
                                on_enter=lambda e: seen.append(("enter", e.value)))
    anything = ui.DropZone.create(on_drop=lambda e: seen.append(("anything", e.value)))
    images.on_mount()
    anything.on_mount()
    window = pz.Window()
    window.on_file_hover("/a/cat.png")
    assert images.hovering and not anything.hovering and seen == [("enter", "/a/cat.png")]
    window.on_file_drop("/a/cat.png")
    window.on_file_drop("/a/dog.png")
    assert images.files == ["/a/cat.png", "/a/dog.png"] and not images.hovering
    window.on_file_drop("/a/notes.txt")  # only the zone that takes anything accepts it
    assert seen[-1] == ("anything", "/a/notes.txt")
    window.on_file_hover("/a/b.png")
    window.on_file_leave()
    assert not images.hovering
    anything.set_pointer(True)  # under the pointer: it gets the files even if another one accepts them
    window.on_file_drop("/a/e.png")
    assert seen[-1] == ("anything", "/a/e.png")
    images.on_unmount()
    anything.on_unmount()
    assert zones == [] and window.on_file_drop("/x.png") is None


def test_drop_zone_keeps_one_file_and_rejects_others(zones):
    seen = []
    zone = ui.DropZone.create(accept=["csv"], multiple=False, on_reject=lambda e: seen.append(e.value),
                              on_files=lambda e: seen.append(list(e.value)))
    zone.drop("/a/one.csv")
    zone.drop("/a/two.csv")
    zone.drop("/a/three.txt")
    assert zone.files == ["/a/two.csv"] and seen == [["/a/one.csv"], ["/a/two.csv"], "/a/three.txt"]
    zone.chosen(["/b/x.csv"])
    assert zone.files == ["/b/x.csv"]
    assert zone.render() is not None
    zone.hover("/a/x.txt")
    assert zone.rejected and zone.render() is not None


def test_a_designer_drop_zone_is_not_live(zones):
    ui.DropZone.create(live=False).on_mount()
    assert zones == []


# -- in Pyzed Design -----------------------------------------------------------------------------------------------
def test_system_section_of_the_toolbox():
    types = [c.type for c in components.categories()["System"]]
    assert types[:2] == ["file_input", "drop_zone"]
    assert {"clipboard", "file_dialog", "notification", "system_info", "launcher", "network_monitor",
            "power_monitor"} <= set(types)
    for type_ in ("system_info", "launcher", "network_monitor", "power_monitor"):
        spec = components.get(type_)
        service = nonvisual.FACTORIES[type_](spec.create(type_ + "1"))
        for prop in spec.props:
            assert hasattr(service, prop.name), (type_, prop.name)
        for event in spec.events:
            assert event in service.events and components.event_text(type_, event), (type_, event)


def _form(*types):
    form = Form(name="f")
    for i, type_ in enumerate(types):
        form.controls.append(components.get(type_).create(f"c{i}", 10, 10 + i * 160))
    return form


def test_system_controls_run_in_a_form(tmp_path, zones):
    app = FormApp(_form("file_input", "drop_zone", "launcher", "system_info"), {})
    app.screenshot(tmp_path / "system.png", size=(400, 400), scale=1.0)
    assert isinstance(app.runtime.services["c2"], pz.Launcher)
    assert isinstance(app.runtime.services["c3"], pz.SystemInfo)
