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

    assert os.environ["EGL_LOG_LEVEL"] == "fatal" and os.environ["MESA_LOG"] == "null"


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


@pytest.fixture
def wsl(env, tmp_path):
    import webbrowser

    system32 = tmp_path / "System32"
    (system32 / "WindowsPowerShell" / "v1.0").mkdir(parents=True)
    (system32 / "rundll32.exe").write_text("")
    (system32 / "WindowsPowerShell" / "v1.0" / "powershell.exe").write_text("")
    env.setattr(_platform, "is_wsl", lambda release=None: True)
    env.setattr(_platform, "_SYSTEM32", str(system32))
    env.setattr(_platform.shutil, "which", lambda name: None)
    env.setattr(_platform, "_windows_browser", None)
    env.setattr(webbrowser, "_tryorder", [])  # a registry of its own, put back after the test
    env.setattr(webbrowser, "_browsers", {})
    env.delenv("BROWSER", raising=False)
    started = []
    env.setattr(_platform.subprocess, "Popen", lambda command, **kw: started.append(command))
    return system32, started


def test_wsl_opens_pages_in_the_windows_browser(wsl):
    import webbrowser

    system32, started = wsl
    assert _platform.use_windows_browser() and _platform.use_windows_browser()  # once is enough
    url = "http://127.0.0.1:8123/callback/x?code=a&state=b%20c"
    assert webbrowser.open(url)
    assert started == [[str(system32 / "rundll32.exe"), "url.dll,FileProtocolHandler", url]]
    powershell = _platform.windows_open_commands("https://x.test/?q=it's")[-1]
    assert powershell[0].endswith("powershell.exe") and powershell[-1] == "Start-Process 'https://x.test/?q=it''s'"


def test_wsl_keeps_the_browser_you_pick(wsl):
    wsl[0].joinpath("rundll32.exe").unlink()
    wsl[0].joinpath("WindowsPowerShell", "v1.0", "powershell.exe").unlink()
    assert not _platform.use_windows_browser()  # no way to reach Windows
    import os

    os.environ["BROWSER"] = "firefox"
    try:
        assert not _platform.use_windows_browser()
    finally:
        del os.environ["BROWSER"]


def test_wsl_runs_terminal_commands_in_windows_terminal(wsl, tmp_path, monkeypatch):
    from pyzed.designer import file_ops

    monkeypatch.delenv("TERMINAL", raising=False)
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.setattr(file_ops.sys, "platform", "linux")
    with pytest.raises(OSError):  # neither a Windows nor a Linux terminal
        file_ops.run_in_terminal_command(["claude"], tmp_path)
    wsl[0].joinpath("cmd.exe").write_text("")
    command = file_ops.run_in_terminal_command(["npx", "-y", "@anthropic-ai/claude-code"], tmp_path)
    assert command[1:5] == ["/c", "start", "", "wsl.exe"]
    assert command[5:] == ["-d", "Ubuntu", "--cd", str(tmp_path), "--", "/bin/zsh", "-lic",
                           "npx -y @anthropic-ai/claude-code"]
    wsl[0].joinpath("wt.exe").write_text("")
    command = file_ops.run_in_terminal_command(["claude"], tmp_path)
    assert command[0].endswith("wt.exe") and command[1] == "wsl.exe"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows process tree")
def test_descendants_finds_grandchildren_after_their_parent_ends():
    """Windows does not end what a process started when it ends (``npx`` -> ``node`` -> an MCP server): found
    before, the grandchild can still be ended after its parent is gone."""
    import subprocess
    import time

    code = ("import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
            "print('ready', flush=True); time.sleep(60)")
    parent = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert parent.stdout.readline().strip() == "ready"
        assert parent.pid in [pid for pid, _ in _platform.descendants()]
        assert parent.pid not in [pid for pid, _ in _platform.descendants(skip=(parent.pid,))]
        found = _platform.descendants(parent.pid)
        assert found and parent.pid not in [pid for pid, _ in found]
        parent.kill()
        parent.wait()
        assert _platform.stop(found) >= 1  # the grandchild, still running
        time.sleep(0.5)
        assert all(_platform._windows_started(pid) is None for pid, _ in found)
    finally:
        if parent.poll() is None:
            parent.kill()
