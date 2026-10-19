"""The self-updater: versions, releases, downloads, unpacking and the swap script."""

import hashlib
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
            info.external_attr = mode << 16
            zf.writestr(info, "#!/bin/sh\n")
    return path


def test_download_checks_the_sha256_and_extracts(tmp_path):
    archive = _zip(tmp_path / "pyzed-design-linux-x86_64.zip", [("Pyzed Design/pyzed-design", 0o755)])
    good = hashlib.sha256(archive.read_bytes()).hexdigest()
    seen = []
    asset = updater.Asset(archive.name, archive.as_uri(), archive.stat().st_size, good)
    got = updater.download(asset, tmp_path / "dl", progress=seen.append)
    assert got.read_bytes() == archive.read_bytes() and seen[-1] == 1.0
    app = updater.extract(got)
    assert app.name == "Pyzed Design" and (app / "pyzed-design").is_file()
    if updater.os.name != "nt":  # Windows has no executable bit
        assert (app / "pyzed-design").stat().st_mode & 0o111

    bad = updater.Asset(archive.name, archive.as_uri(), 0, "0" * 64)
    with pytest.raises(updater.UpdateError, match="SHA-256"):
        updater.download(bad, tmp_path / "bad")
    assert not list((tmp_path / "bad").iterdir())


def test_extract_needs_one_app(tmp_path):
    archive = _zip(tmp_path / "two.zip", [("a/x", 0o644), ("b/y", 0o644)])
    with pytest.raises(updater.UpdateError, match="exactly one"):
        updater.extract(archive)


@pytest.mark.skipif(updater.os.name == "nt", reason="POSIX swap script")
def test_replace_on_exit_writes_a_swap_script(tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(updater.subprocess, "Popen", lambda args, **kw: started.append(args))
    (tmp_path / "app").mkdir()
    (tmp_path / "new").mkdir()
    script = updater.replace_on_exit(tmp_path / "new", tmp_path / "app")
    text = script.read_text()
    assert f"kill -0 {updater.os.getpid()}" in text and str(tmp_path / "app.old") in text
    assert started == [["/bin/sh", str(script)]]
    script.unlink()
    with pytest.raises(updater.UpdateError):
        updater.replace_on_exit(tmp_path / "new")  # not a packaged app


def test_state_and_due():
    assert updater.due() and updater.load_state() == {}
    updater.save_state(last_check=updater.time.time(), skipped="0.5.0")
    assert not updater.due() and updater.load_state()["skipped"] == "0.5.0"
    assert updater.due(every=0)


def test_designer_whats_new_tab_and_status(tmp_path):
    from pyzed.designer.app import Designer
    from pyzed.designer.updates import TAB_ID

    updater.save_state(last_seen="0.0.1", last_check=updater.time.time())
    app = Designer(language_servers=False)
    commands = app.updates.on_start()  # updated since last launch: opens What's new
    assert app.updates.notes is not None and app.updates.notes_active and len(commands) == 1
    commands[0].close()
    assert updater.load_state()["last_seen"] == app.updates.current
    tab = app.updates.tab()
    assert tab.id == TAB_ID and app.updates.notes_view(app.theme_obj) is not None

    app.updates.close_notes()
    app.updates.latest = updater.Release.from_api(API_RELEASE)
    app.updates.status = "available"
    items = app.updates.status_items(app.theme_obj)
    assert len(items) == 1
    app.updates.show_notes()  # the newest release, no download needed
    assert app.updates.notes.version == "0.5.0" and app.view() is not None
    app.updates.skip()
    assert updater.load_state()["skipped"] == "0.5.0" and app.updates.notes is None
