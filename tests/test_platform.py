"""Platform defaults applied before a window opens."""

import sys

import pytest

from pyzed import _platform

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux only")


@pytest.fixture
def env(monkeypatch):
    for name in ("EGL_LOG_LEVEL", "MESA_LOG", "PYZED_GPU_LOGS", "PYZED_WAYLAND", "WSL_DISTRO_NAME", "WSL_INTEROP",
                 "WAYLAND_DISPLAY"):
        # setenv first so the original value (or its absence) is restored after the test,
        # even when prepare() changes it directly.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    monkeypatch.setattr(_platform, "is_wsl", lambda release=None: False)
    return monkeypatch


def test_driver_warnings_are_silenced(env):
    assert set(_platform.prepare()) == {"EGL_LOG_LEVEL", "MESA_LOG"}
    import os

    assert os.environ["EGL_LOG_LEVEL"] == "fatal" and os.environ["MESA_LOG"] == "silent"


def test_user_settings_win(env):
    env.setenv("MESA_LOG", "file")
    env.setenv("PYZED_GPU_LOGS", "1")
    assert _platform.prepare() == []


def test_wsl_uses_x11(env):
    env.setattr(_platform, "is_wsl", lambda release=None: True)
    env.setenv("DISPLAY", ":0")
    env.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert "WAYLAND_DISPLAY" in _platform.prepare()
    import os

    assert "WAYLAND_DISPLAY" not in os.environ


def test_wsl_can_keep_wayland(env):
    env.setattr(_platform, "is_wsl", lambda release=None: True)
    env.setenv("DISPLAY", ":0")
    env.setenv("WAYLAND_DISPLAY", "wayland-0")
    env.setenv("PYZED_WAYLAND", "1")
    assert "WAYLAND_DISPLAY" not in _platform.prepare()


def test_wsl_detection(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)
    assert _platform.is_wsl("6.6.87.2-microsoft-standard-WSL2")
    assert not _platform.is_wsl("6.8.0-45-generic")
