"""The self-updater: versions, releases, downloads, unpacking and the swap script."""

import hashlib
import types
import zipfile

import pytest

from pyzed import updater

API_RELEASE = {
    "tag_name": "v0.5.0",
    "body": "## Features\n- Updates",
    "html_url": "https://github.com/albakore/pyzed/releases/tag/v0.5.0",
    "published_at": "2026-10-20T12:00:00Z",
    "prerelease": False,
    "assets": [{"name": "pyzed-design-linux-x86_64.zip", "size": 3,
                "browser_download_url": "https://example.com/a.zip", "digest": "sha256:abc"}],
}


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def test_versions():
    assert updater.is_newer("0.5.0", "0.4.0") and updater.is_newer("v0.10.0", "0.9.9")
    assert updater.is_newer("1.0.0", "1.0.0-rc.1") and updater.is_newer("1.0.0-rc.2", "1.0.0-rc.1")
    assert not updater.is_newer("0.4.0", "0.4.0") and not updater.is_newer("0.3.1", "0.4")


def test_release_from_api():
    release = updater.Release.from_api(API_RELEASE)
    assert release.version == "0.5.0" and release.published == "2026-10-20"
    asset = release.asset_for("pyzed-design-linux-x86_64.zip")
    assert asset is not None and asset.sha256 == "abc" and asset.size == 3
    assert release.asset_for("pyzed-design-windows-x86_64.zip") is None


def test_asset_name_matches_the_release_builds():
    name = updater.asset_name("pyzed-design")
    assert name.startswith("pyzed-design-") and name.endswith(".zip")
    assert updater.system_name() in ("linux", "windows", "macos")


def _zip(path, files):
    with zipfile.ZipFile(path, "w") as zf:
        for name, mode in files:
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o100000 | mode) << 16  # a regular file, as zip tools write it
            zf.writestr(info, "#!/bin/sh\n")
    return path


def test_download_checks_the_sha256_and_extracts(tmp_path):
    archive = _zip(tmp_path / "pyzed-design-linux-x86_64.zip", [("Pyzed Design/pyzed-design", 0o755)])
    good = hashlib.sha256(archive.read_bytes()).hexdigest()
    seen = []
    asset = updater.Asset(archive.name, archive.as_uri(), archive.stat().st_size, good)
    got = updater.download(asset, tmp_path / "dl", progress=seen.append)
    assert got.read_bytes() == archive.read_bytes() and seen[-1] == 1.0
    offline = updater.Asset(archive.name, (tmp_path / "gone.zip").as_uri(), 0, good)
    assert updater.download(offline, tmp_path / "dl") == got  # downloaded before: reused, not fetched
    app = updater.extract(got)
    assert app.name == "Pyzed Design" and (app / "pyzed-design").is_file()
    if updater.os.name != "nt":  # Windows has no executable bit
        assert (app / "pyzed-design").stat().st_mode & 0o111

    bad = updater.Asset(archive.name, archive.as_uri(), 0, "0" * 64)
    with pytest.raises(updater.UpdateError, match="SHA-256"):
        updater.download(bad, tmp_path / "bad")
    assert not list((tmp_path / "bad").iterdir())
    unchecked = updater.Asset(archive.name, archive.as_uri(), 0, None)
    with pytest.raises(updater.UpdateError, match="cannot be checked"):
        updater.download(unchecked, tmp_path / "unchecked")
    assert not list((tmp_path / "unchecked").iterdir())


def test_extract_needs_one_app(tmp_path):
    archive = _zip(tmp_path / "two.zip", [("a/x", 0o644), ("b/y", 0o644)])
    with pytest.raises(updater.UpdateError, match="exactly one"):
        updater.extract(archive)


@pytest.mark.skipif(updater.os.name == "nt", reason="POSIX swap script")
def test_replace_on_exit_writes_a_swap_script(tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: started.append((args, kw["env"])))
    monkeypatch.setenv("_PYI_PARENT_PROCESS_LEVEL", "1")  # what PyInstaller leaves for its children
    (tmp_path / "app").mkdir()
    (tmp_path / "new").mkdir()
    script = updater.replace_on_exit(tmp_path / "new", tmp_path / "app")
    text = script.read_text()
    assert f"kill -0 {updater.os.getpid()}" in text and str(tmp_path / "app.old") in text
    [(args, env)] = started
    assert args == ["/bin/sh", str(script)]
    # the new version starts as a fresh app, not as a child of this one
    assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1" and "_PYI_PARENT_PROCESS_LEVEL" not in env
    script.unlink()
    script.with_suffix(".log").unlink()
    with pytest.raises(updater.UpdateError):
        updater.replace_on_exit(tmp_path / "new")  # not a packaged app


@pytest.mark.skipif(updater.os.name == "nt", reason="fakes Windows on another system")
def test_windows_swap_script_opens_no_console_windows(tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: started.append((args, kw["creationflags"])))
    monkeypatch.setattr(updater.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(updater.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    fake_os = types.ModuleType("os")
    fake_os.__dict__.update(vars(updater.os), name="nt")  # only the updater sees Windows; pathlib does not
    monkeypatch.setattr(updater, "os", fake_os)
    (tmp_path / "app").mkdir()
    (tmp_path / "new").mkdir()
    script = updater.replace_on_exit(tmp_path / "new", tmp_path / "app")
    # a hidden console the script's tasklist/find/ping share, instead of one window each (DETACHED_PROCESS)
    [(args, flags)] = started
    assert args == ["cmd", "/c", str(script)] and flags == 0x08000000 | 0x200
    script.unlink()
    script.with_suffix(".log").unlink()


def test_state_and_due():
    assert updater.due() and updater.load_state() == {}
    updater.save_state(last_check=updater.time.time(), skipped="0.5.0")
    assert not updater.due() and updater.load_state()["skipped"] == "0.5.0"
    assert updater.due(every=0)


def test_designer_whats_new_tab_and_status(tmp_path, monkeypatch):
    from pyzed.designer.app import Designer
    from pyzed.designer.updates import TAB_ID

    updater.save_state(last_seen="0.0.1", last_check=updater.time.time())
    app = Designer(language_servers=False)
    commands = app.updates.on_start()  # updated since last launch: opens What's new (and cleans old downloads)
    assert app.updates.notes is not None and app.updates.notes_active and len(commands) == 2
    for command in commands:
        command.close()
    assert updater.load_state()["last_seen"] == app.updates.current
    tab = app.updates.tab()
    assert tab.id == TAB_ID and app.updates.notes_view(app.theme_obj) is not None

    app.updates.close_notes()
    app.updates.latest = updater.Release.from_api(API_RELEASE)
    app.updates.status = "available"
    items = app.updates.title_items(app.theme_obj)
    assert len(items) == 1
    app.updates.show_notes()  # the newest release, no download needed
    assert app.updates.notes.version == "0.5.0" and app.view() is not None
    app.updates.bundle = tmp_path
    swaps = []
    monkeypatch.setattr(updater, "replace_on_exit", lambda bundle, **kw: swaps.append(kw) or tmp_path / "swap.sh")
    assert app.updates.restart() is not None and app.updates.restart_pending  # design() then ends the process
    assert swaps == [{"keep": ("unins*",)}]  # the Windows installer's uninstaller stays in the new folder
    app.updates.skip()
    assert updater.load_state()["skipped"] == "0.5.0" and app.updates.notes is None


def test_designer_update_channels(monkeypatch):
    from pyzed.designer.app import Designer

    asked = []
    monkeypatch.setattr(updater, "latest", lambda repo, prerelease=False, **kw: asked.append(prerelease))
    app = Designer(language_servers=False)
    assert app.updates.channel == "stable" and app.prefs.update_channel == "stable"
    app.updates.check(quiet=True).close()
    updater.save_state(skipped="0.5.0")
    app.updates.status = "idle"
    command = app.updates.toggle_preview()  # switching channel checks again, forgetting skipped versions
    assert app.updates.channel == "preview" and updater.load_state()["skipped"] is None
    app.updates._run = lambda work, done, failed=None: work()  # run the check right here
    app.updates.status = "idle"
    app.updates.check(quiet=True)
    assert asked[-1] is True
    command.close()
    app.prefs.update_channel = "nightly"  # unknown values fall back to stable
    assert app.updates.channel == "stable"


def test_designer_waits_for_the_release_builds(monkeypatch):
    """The tag publishes the release before the pipeline attaches its files: until then it is not offered."""
    from pyzed.designer.app import Designer

    app = Designer(language_servers=False)
    app.updates._run = lambda work, done, failed=None: done(work())
    building = dict(API_RELEASE, tag_name="v99.0.0", assets=[])
    monkeypatch.setattr(updater, "latest", lambda repo, prerelease=False, **kw: updater.Release.from_api(building))
    app.updates.check(quiet=True)
    assert app.updates.status == "up_to_date"
    wheel = {"name": "pyzed_ui-99.0.0-cp310-abi3-win_amd64.whl", "browser_download_url": "https://example.com/w"}
    built = dict(building, assets=[*API_RELEASE["assets"], wheel])
    monkeypatch.setattr(updater, "latest", lambda repo, prerelease=False, **kw: updater.Release.from_api(built))
    monkeypatch.setattr(updater, "asset_name", lambda app: "pyzed-design-linux-x86_64.zip")
    app.updates.check(quiet=True)
    assert app.updates.status == "available" and app.updates.latest.has_wheels


def test_designer_downloads_updates_in_the_background(tmp_path, monkeypatch):
    """Like Zed: a new version found by the automatic check downloads by itself; the title bar then offers
    "Restart to update", and the next launch deletes the downloads of installed versions."""
    from pyzed.designer import updates as updates_module
    from pyzed.designer.app import Designer
    from pyzed.project import config_dir

    app = Designer(language_servers=False)
    app.updates._run = lambda work, done, failed=None: done(work())
    monkeypatch.setattr(updates_module.updater, "can_update_in_place", lambda: True)
    monkeypatch.setattr(updater, "asset_name", lambda app: "pyzed-design-linux-x86_64.zip")
    monkeypatch.setattr(updater, "latest", lambda repo, prerelease=False, **kw: updater.Release.from_api(API_RELEASE))
    monkeypatch.setattr(updater, "download", lambda asset, folder, progress=None: folder / asset.name)
    monkeypatch.setattr(updater, "extract", lambda archive: tmp_path / "Pyzed Design")
    app.updates.current = "0.4.0"
    assert app.updates.title_items(app.theme_obj) == []  # nothing to say while up to date
    app.updates.check(quiet=True)
    assert app.updates.status == "ready" and app.updates.bundle == tmp_path / "Pyzed Design"
    assert len(app.updates.title_items(app.theme_obj)) == 1 and app.view() is not None

    app.updates.status = "downloading"  # the progress shows in the same place
    assert len(app.updates.title_items(app.theme_obj)) == 1
    app.updates.status = "up_to_date"
    assert app.updates.tick() is None  # just checked: not due yet
    updater.save_state(last_check=0)
    app.updates.status = "up_to_date"
    app.updates.tick()
    assert app.updates.status == "ready"
    app.set_pref("check_updates", False)  # without automatic checks, "Update to X" downloads on click
    app.updates.status = "idle"
    updater.save_state(last_check=0)
    assert app.updates.tick() is None and app.updates.status == "idle"

    for version in ("0.3.0", "0.4.0", "0.5.0"):
        (config_dir() / "updates" / version).mkdir(parents=True)
    app.updates._clean_downloads()
    assert sorted(p.name for p in (config_dir() / "updates").iterdir()) == ["0.5.0"]


def test_designer_tells_when_the_restart_did_not_update(tmp_path, monkeypatch):
    """"Restart to update" remembers the version it installs: starting again as the old one means the swap failed."""
    from pyzed.designer.app import Designer

    app = Designer(language_servers=False)
    app.updates.latest = updater.Release.from_api(API_RELEASE)
    app.updates.bundle = tmp_path
    monkeypatch.setattr(updater, "replace_on_exit", lambda bundle, **kw: tmp_path / "swap.cmd")
    app.updates.current = "0.4.0"
    app.updates.restart()
    assert updater.load_state()["pending"] == "0.5.0"
    (tmp_path / "swap.log").write_text("The app folder is still in use: the update was not installed.\n")

    again = Designer(language_servers=False)  # the old version started again
    again.updates.current = "0.4.0"
    for command in again.updates.on_start():
        command.close()
    assert "still in use" in again.updates.error and str(tmp_path / "swap.log") in again.updates.error
    assert updater.load_state()["pending"] is None
    updated = Designer(language_servers=False)
    updated.updates.current = "0.5.0"
    updater.save_state(pending="0.5.0")
    for command in updated.updates.on_start():
        command.close()
    assert updated.updates.error is None


def test_designer_stops_its_processes_before_an_update(monkeypatch):
    from pyzed.designer.app import Designer

    app = Designer(language_servers=False)
    stopped = []
    monkeypatch.setattr(app.assist, "shutdown", lambda: stopped.append("language servers"))
    monkeypatch.setattr(app.projects, "stop", lambda: stopped.append("run"))
    monkeypatch.setattr(app.exporter, "cancel", lambda: 1 / 0)  # one failing does not stop the others
    monkeypatch.setattr(app.agent, "shutdown", lambda: stopped.append("agents"))
    app.stop_children()
    assert stopped == ["language servers", "run", "agents"]
