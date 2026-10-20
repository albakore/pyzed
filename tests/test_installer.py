"""The installers of Pyzed Design: the Linux install.sh, the Windows setup script and the update hand-off."""

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from pyzed import updater

ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = ROOT / "docs" / "public" / "install.sh"
ISS = ROOT / "installer" / "windows" / "pyzed-design.iss"

linux_only = pytest.mark.skipif(not sys.platform.startswith("linux") or not shutil.which("sh"),
                                reason="install.sh is for Linux")


def _release(folder: Path, arch: str, checksum: bool = True) -> Path:
    """A fake release folder: the app zip (as build_designer.py makes it) and its SHA256SUMS."""
    folder.mkdir()
    archive = folder / f"pyzed-design-linux-{arch}.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for name, mode in (("Pyzed Design/Pyzed Design", 0o755), ("Pyzed Design/uv", 0o755),
                           ("Pyzed Design/_internal/base_library.zip", 0o644)):
            info = zipfile.ZipInfo(name)
            info.external_attr = (stat.S_IFREG | mode) << 16
            zf.writestr(info, "#!/bin/sh\necho pyzed\n")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest() if checksum else "0" * 64
    (folder / "SHA256SUMS").write_text(f"{digest}  {archive.name}\n")
    return folder


def _run(tmp_path: Path, release: Path, *args: str) -> subprocess.CompletedProcess:
    home = tmp_path / "home"
    env = {"PATH": os.environ["PATH"], "HOME": str(home), "XDG_DATA_HOME": str(home / ".local" / "share"),
           "PYZED_DOWNLOAD_URL": release.as_uri()}
    return subprocess.run(["sh", str(INSTALL_SH), *args], env=env, capture_output=True, text=True, timeout=60)


def _arch() -> str:
    return "aarch64" if os.uname().machine in ("aarch64", "arm64") else "x86_64"


@linux_only
def test_install_sh_installs_links_and_uninstalls(tmp_path):
    if not shutil.which("curl") and not shutil.which("wget"):
        pytest.skip("needs curl or wget")
    release = _release(tmp_path / "release", _arch())
    done = _run(tmp_path, release)
    assert done.returncode == 0, done.stderr
    share = tmp_path / "home" / ".local" / "share"
    app = share / "pyzed-design" / "Pyzed Design"
    exe = app / "Pyzed Design"
    assert exe.is_file() and os.access(exe, os.X_OK) and os.access(app / "uv", os.X_OK)
    link = tmp_path / "home" / ".local" / "bin" / "pyzed-design"
    assert link.is_symlink() and link.resolve() == exe.resolve()
    desktop = (share / "applications" / "dev.pyzed.design.desktop").read_text()
    assert f'Exec="{exe}" %f' in desktop and "application/x-pyzed-form" in desktop
    assert "*.pzform" in (share / "mime" / "packages" / "dev.pyzed.design.xml").read_text()
    # the folder the app updates itself in is the user's
    assert os.access(app.parent, os.W_OK)

    again = _run(tmp_path, release)  # reinstalling replaces the app
    assert again.returncode == 0 and not (app.parent / "Pyzed Design.old").exists()

    gone = _run(tmp_path, release, "--uninstall")
    assert gone.returncode == 0 and not app.exists() and not link.exists()


@linux_only
def test_install_sh_refuses_a_corrupt_download(tmp_path):
    if not shutil.which("curl") and not shutil.which("wget"):
        pytest.skip("needs curl or wget")
    release = _release(tmp_path / "release", _arch(), checksum=False)
    done = _run(tmp_path, release)
    assert done.returncode != 0 and "corrupt" in done.stderr
    assert not (tmp_path / "home" / ".local" / "share" / "pyzed-design" / "Pyzed Design").exists()


def test_install_sh_is_valid_posix_shell():
    if not shutil.which("sh"):
        pytest.skip("needs sh")
    assert subprocess.run(["sh", "-n", str(INSTALL_SH)]).returncode == 0


def test_windows_setup_matches_the_designer():
    from pyzed.designer import updates

    text = ISS.read_text(encoding="utf-8")
    # per user, no admin rights: the app can replace its own folder when it updates
    assert "PrivilegesRequired=lowest" in text and r"DefaultDirName={autopf}\{#AppName}" in text
    # the uninstall entry the designer refreshes after a self-update is this AppId's
    app_id = text.split("AppId={{", 1)[1].split("}", 1)[0]
    assert f"{{{app_id}}}_is1" in updates.WINDOWS_UNINSTALL_KEY
    assert "unins*" in updates.INSTALLER_FILES and ".pzform" in text


@pytest.mark.skipif(os.name == "nt", reason="POSIX swap script")
def test_swap_script_keeps_the_uninstaller(tmp_path, monkeypatch):
    monkeypatch.setattr(updater.subprocess, "Popen", lambda *a, **kw: None)
    old, new = tmp_path / "app", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    (old / "unins000.exe").write_text("uninstaller")
    script = updater.replace_on_exit(new, old, relaunch=False, keep=("unins*",))
    monkeypatch.undo()
    text = script.read_text().replace(f"kill -0 {os.getpid()}", "false")
    script.write_text(text)
    subprocess.run(["/bin/sh", str(script)], check=True, timeout=30)
    assert (old / "unins000.exe").read_text() == "uninstaller" and not new.exists()
    assert not (tmp_path / "app.old").exists()
