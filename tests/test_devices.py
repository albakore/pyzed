"""Tests for device profiles, design sizes and focus with the arrow keys."""

import pytest

import pyzed as pz
from pyzed import _core, devices


@pytest.fixture(autouse=True)
def fresh_device():
    devices.set_device(None)
    yield
    devices.set_device(None)


def test_find_follows_app_env_project_and_system():
    tool = {"device": "kiosk", "platform": {"linux": {"device": "touch"}}}
    assert devices.find("tv", tool=tool, environ={"PYZED_DEVICE": "mobile"}).name == "tv"
    assert devices.find(None, tool=tool, environ={"PYZED_DEVICE": "mobile"}).name == "mobile"
    assert devices.find(None, tool=tool, environ={}, system="linux").name == "touch"
    assert devices.find(None, tool=tool, environ={}, system="windows").name == "kiosk"
    assert devices.find(None, tool={}, environ={}, system="android").name == "mobile"
    assert devices.find(None, tool={}, environ={}, system="macos").name == "desktop"
    custom = pz.Device("panel", touch=True)
    assert devices.find(custom) is custom
    with pytest.raises(ValueError):
        devices.find("toaster", tool={}, environ={})


def test_custom_profiles_extend_others():
    tool = {"device": {"dash": {"extends": "automotive", "design_size": [1920, 720], "quality": "low",
                                "unknown": 1}}}
    dash = devices.find("dash", tool=tool, environ={})
    assert dash.name == "dash" and dash.kiosk and dash.design_size == (1920.0, 720.0) and dash.quality == "low"
    # a table named like a built-in changes it
    tv = devices.find("tv", tool={"device": {"tv": {"scale": 1.5}}}, environ={})
    assert tv.scale == 1.5 and tv.arrow_focus
    with pytest.raises(ValueError):
        devices.find("x", tool={"device": {"x": {"extends": "nothing"}}}, environ={})


def test_device_validation():
    with pytest.raises(ValueError):
        pz.Device(stretch="crop")
    with pytest.raises(ValueError):
        pz.Device(quality="ultra")
    with pytest.raises(ValueError):
        pz.Device(design_size=(0, 720))


def test_quality_fills_in_only_the_defaults():
    low = pz.Device(quality="low")
    tuned = low.tune(pz.Rendering(max_fps=144))
    assert tuned.max_fps == 144 and tuned.antialiasing == "off" and tuned.background_fps == 0
    assert pz.Device().tune(pz.Rendering()) == pz.Rendering()
    assert devices.PROFILES["automotive"].tune(pz.Rendering()).background_fps == 0


class Plain(pz.Window):
    def view(self):
        return pz.text("x")


class Windowed(pz.Window):
    kiosk = False
    fullscreen = False

    def view(self):
        return pz.text("x")


def test_profiles_fill_in_the_window_options_left_alone():
    pz.set_device("kiosk")
    opts = _core.window_options(Plain())
    assert opts["fullscreen"] and opts["level"] == "top" and not opts["decorations"]
    opts = _core.window_options(Windowed())
    assert not opts["fullscreen"] and opts["level"] == "normal"
    window = Plain()
    window.app = object()  # a secondary window: no kiosk, but the same scale and pointer
    _core.window_options(window)
    assert window.kiosk is False and window.scale == devices.PROFILES["kiosk"].scale


def test_pyzed_own_apps_stay_on_the_desktop(monkeypatch):
    monkeypatch.setenv("PYZED_DEVICE", "tv")

    class Own(pz.App):
        pass

    Own.__module__ = "pyzed.designer.app"
    devices._start(Own)
    assert pz.device().name == "desktop"

    class Mine(pz.App):
        pass

    devices._start(Mine)
    assert pz.device().name == "tv"


def test_media_queries_ask_about_the_device():
    assert pz.media("pointer: fine") and not pz.media("pointer: coarse")
    pz.set_device("touch")
    assert pz.media("pointer: coarse") and pz.media("device: touch")
    pz.set_device("tv")
    assert pz.media("pointer: none") and not pz.media("device: touch")
    with pytest.raises(ValueError):
        pz.media("pointer: soft")


def test_design_size_scales_to_the_window():
    window = Plain()
    assert window.__pyzed_scale__() == 1.0
    window.design_size = (1000, 500)
    assert window.__pyzed_scale__() == 1.0  # not open yet: opens at its size
    window.window_size = (2000, 1500)
    window._pyzed_size_scale = 1.0
    assert window.__pyzed_scale__() == 2.0
    # measured while the scale was 2: the same window
    window.window_size, window._pyzed_size_scale = (1000, 750), 2.0
    assert window.__pyzed_scale__() == 2.0
    window.stretch = "none"
    assert window.__pyzed_scale__() == 1.0


def test_focus_direction_command():
    for direction in ("up", "down", "left", "right"):
        assert repr(pz.Command.focus_direction(direction)) == "Command.focus_direction(...)"
    with pytest.raises(ValueError):
        pz.Command.focus_direction("forward")
