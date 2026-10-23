"""Tests for screens, fullscreen on a monitor, window levels and kiosk windows."""

import pytest

import pyzed as pz
from pyzed import _core


class Plain(pz.Window):
    def view(self):
        return pz.text("x")


def options(**attrs):
    window = Plain()
    for name, value in attrs.items():
        setattr(window, name, value)
    return _core.window_options(window)


def test_defaults_keep_a_normal_window():
    opts = options()
    assert opts["fullscreen"] is False and opts["exclusive"] is False
    assert opts["monitor"] is None and opts["level"] == "normal"
    assert opts["decorations"] and opts["resizable"] and opts["closable"] and opts["minimizable"]


def test_fullscreen_on_a_monitor_and_exclusive():
    assert options(fullscreen=True, monitor=1)["monitor"] == 1
    opts = options(fullscreen="exclusive", monitor=1)
    assert opts["fullscreen"] and opts["exclusive"] and opts["monitor"] == 1
    opts = options(fullscreen="borderless")
    assert opts["fullscreen"] and not opts["exclusive"]
    with pytest.raises(ValueError):
        options(fullscreen="windowed-ish")


def test_levels_and_buttons():
    assert options(always_on_top=True)["level"] == "top"
    assert options(always_on_bottom=True)["level"] == "bottom"
    opts = options(closable=False, minimizable=False)
    assert not opts["closable"] and not opts["minimizable"]


def test_kiosk_puts_it_all_together():
    opts = options(kiosk=True)
    assert opts["fullscreen"] and opts["level"] == "top"
    assert not opts["decorations"] and not opts["resizable"]
    assert not opts["closable"] and not opts["minimizable"]
    assert options(kiosk=True, always_on_bottom=True)["level"] == "bottom"


def test_commands():
    assert isinstance(pz.Command.set_fullscreen(True, None, 1, True), pz.Command)
    assert isinstance(Plain().set_fullscreen(monitor=0, exclusive=True), pz.Command)
    assert isinstance(Plain().set_window_level("bottom"), pz.Command)
    assert isinstance(pz.Command.hide_cursor(), pz.Command)
    assert repr(pz.Command.list_monitors(print)) == "Command.list_monitors(...)"
    with pytest.raises(ValueError):
        pz.Command.set_window_level("sideways")


def test_monitors_before_the_first_window():
    assert pz.monitors() == []
    monitor = pz.app._monitors([{"index": 0, "name": "DP-1", "x": 0.0, "y": 0.0, "width": 1920.0,
                                 "height": 1080.0, "scale": 1.0, "refresh_rate": 144.0,
                                 "primary": True}])[0]
    assert isinstance(monitor, pz.Monitor)
    assert monitor.size == (1920.0, 1080.0) and monitor.position == (0.0, 0.0) and monitor.primary
