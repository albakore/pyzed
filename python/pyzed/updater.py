"""Self-updates for apps distributed through GitHub Releases, like Zed's auto-updater.

Pyzed Design uses it to keep the compiled editor up to date, and any app packaged with
``pyzed build`` can too::

    from pyzed import updater

    release = updater.latest("me/my-app")            # the newest GitHub Release
    if updater.is_newer(release.version, "1.2.0"):
        asset = release.asset_for(updater.asset_name("my-app"))
        archive = updater.download(asset, progress=print)   # checks the SHA-256 GitHub publishes
        bundle = updater.extract(archive)            # the new app, unpacked next to the archive
        updater.replace_on_exit(bundle)              # swapped in when this process exits
        # ...then quit; the new version starts by itself

Releases carry one zip per platform named ``<app>-<system>-<machine>.zip`` (``system``
is ``linux``, ``windows`` or ``macos``). The zip holds the app folder (or the ``.app`` on
macOS) as PyInstaller makes it. Nothing here raises on network errors: ``latest`` and
friends raise ``UpdateError`` with a readable message instead.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

API = "https://api.github.com/repos/{repo}/releases"
USER_AGENT = "pyzed-updater"


class UpdateError(Exception):
    """A check, download or install that could not finish (the message says why)."""


# -- versions ------------------------------------------------------------------------------


def parse_version(text: str) -> Tuple[Tuple[int, ...], Tuple[Any, ...]]:
    """``"v1.2.0-rc.1"`` -> ``((1, 2, 0), (0, "rc", 1))``; final releases sort after their pre-releases."""
    text = text.strip().lstrip("vV").split("+", 1)[0]
    core, _, pre = text.partition("-")
    numbers = tuple(int(n) for n in re.findall(r"\d+", core)[:3])
    numbers = numbers + (0,) * (3 - len(numbers))
    if not pre:
        return numbers, (1,)
    parts: List[Any] = [0]
    for piece in re.split(r"[.\-]", pre):
        parts.append(int(piece) if piece.isdigit() else piece)
    return numbers, tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    """Whether version ``candidate`` is newer than ``current``."""
    try:
        return parse_version(candidate) > parse_version(current)
    except ValueError:
        return False


# -- releases ------------------------------------------------------------------------------


@dataclass
class Asset:
    """A file attached to a release."""

    name: str
    url: str
    size: int = 0
    sha256: Optional[str] = None


@dataclass
class Release:
    """A GitHub Release: its version, notes (Markdown) and files."""

    version: str
    tag: str
    notes: str = ""
    url: str = ""
    published: str = ""
    prerelease: bool = False
    assets: List[Asset] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "Release":
        tag = str(data.get("tag_name") or "")
        assets = []
        for a in data.get("assets") or []:
            digest = str(a.get("digest") or "")
            assets.append(Asset(a.get("name", ""), a.get("browser_download_url", ""), int(a.get("size") or 0),
                                digest.split(":", 1)[1] if digest.startswith("sha256:") else None))
        return cls(version=tag.lstrip("vV"), tag=tag, notes=str(data.get("body") or ""),
                   url=str(data.get("html_url") or ""), published=str(data.get("published_at") or "")[:10],
                   prerelease=bool(data.get("prerelease")), assets=assets)

    def asset_for(self, name: str) -> Optional[Asset]:
        """The asset called ``name``, or ``None`` if this release has no build for it."""
        return next((a for a in self.assets if a.name == name), None)


def _get(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https URL
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            raise UpdateError("no release found") from err
        if err.code == 403:
            raise UpdateError("GitHub refused the request (rate limit); try again later") from err
        raise UpdateError(f"GitHub answered {err.code}") from err
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise UpdateError(f"could not reach GitHub: {getattr(err, 'reason', err)}") from err


def latest(repo: str, *, prerelease: bool = False, timeout: float = 10) -> Release:
    """The newest release of ``repo`` (``"owner/name"``); pre-releases count only with ``prerelease``."""
    if not prerelease:
        return Release.from_api(_get(API.format(repo=repo) + "/latest", timeout))
    releases = [Release.from_api(r) for r in _get(API.format(repo=repo) + "?per_page=20", timeout)]
    if not releases:
        raise UpdateError("no release found")
    return max(releases, key=lambda r: parse_version(r.version))


def release(repo: str, version: str, *, timeout: float = 10) -> Release:
    """The release of ``version`` (with or without the leading ``v``)."""
    tag = version if version.startswith("v") else f"v{version}"
    return Release.from_api(_get(API.format(repo=repo) + f"/tags/{tag}", timeout))


# -- this installation ----------------------------------------------------------------------


def system_name() -> str:
    """``linux``, ``windows`` or ``macos``."""
    return {"darwin": "macos", "win32": "windows", "cygwin": "windows"}.get(sys.platform, sys.platform)


def machine_name() -> str:
    """``x86_64`` or ``arm64`` (``aarch64`` on Linux)."""
    machine = platform.machine().lower()
    return {"amd64": "x86_64", "x64": "x86_64", "aarch64": "arm64" if sys.platform == "darwin" else "aarch64"}.get(
        machine, machine)


def asset_name(app: str) -> str:
    """The zip this platform downloads: ``pyzed-design-windows-x86_64.zip``."""
    return f"{app}-{system_name()}-{machine_name()}.zip"


def is_frozen() -> bool:
    """Whether this process is a packaged app (PyInstaller or Nuitka), which can update itself."""
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def install_dir() -> Optional[Path]:
    """The folder (or ``.app`` bundle on macOS) of this packaged app; ``None`` when running from Python."""
    if not is_frozen():
        return None
    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        for parent in exe.parents:
            if parent.suffix == ".app":
                return parent
    return exe.parent


def can_update_in_place() -> bool:
    """Whether ``replace_on_exit`` can swap this app: packaged, and its folder is writable."""
    folder = install_dir()
    return folder is not None and os.access(folder.parent, os.W_OK)


# -- downloading and installing ----------------------------------------------------------------

Progress = Callable[[float], Any]


def download(asset: Asset, folder: Optional[Union[str, Path]] = None, *, progress: Optional[Progress] = None,
             timeout: float = 30) -> Path:
    """Downloads ``asset`` into ``folder`` (a temporary one by default), checking its SHA-256.

    ``progress`` receives the fraction done (0.0 to 1.0) as the file arrives.
    """
    target_dir = Path(folder) if folder else Path(tempfile.mkdtemp(prefix="pyzed-update-"))
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / asset.name
    partial = target.with_name(target.name + ".part")
    digest = hashlib.sha256()
    request = urllib.request.Request(asset.url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, open(partial, "wb") as out:  # noqa: S310
            total = int(response.headers.get("Content-Length") or asset.size or 0)
            done = 0
            while True:
                chunk = response.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(min(done / total, 1.0))
    except (urllib.error.URLError, OSError) as err:
        partial.unlink(missing_ok=True)
        raise UpdateError(f"the download failed: {getattr(err, 'reason', err)}") from err
    if asset.sha256 and digest.hexdigest() != asset.sha256.lower():
        partial.unlink(missing_ok=True)
        raise UpdateError("the download is corrupt (its SHA-256 does not match the release)")
    partial.replace(target)
    if progress:
        progress(1.0)
    return target


def extract(archive: Union[str, Path], folder: Optional[Union[str, Path]] = None) -> Path:
    """Unpacks a downloaded zip and returns the app inside (its folder, or the ``.app`` on macOS)."""
    archive = Path(archive)
    folder = Path(folder) if folder else archive.with_suffix("")
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    if sys.platform == "darwin" and shutil.which("ditto"):
        # ditto keeps the bundle's symlinks, permissions and code signature
        done = subprocess.run(["ditto", "-x", "-k", str(archive), str(folder)], capture_output=True, text=True)
        if done.returncode != 0:
            raise UpdateError(done.stderr.strip() or "could not unpack the update")
    else:
        try:
            with zipfile.ZipFile(archive) as zf:
                for info in zf.infolist():
                    path = Path(zf.extract(info, folder))
                    mode = info.external_attr >> 16
                    if mode and not info.is_dir():
                        path.chmod(mode & 0o777)  # zipfile drops the executable bit
        except (zipfile.BadZipFile, OSError) as err:
            raise UpdateError(f"could not unpack the update: {err}") from err
    entries = [p for p in folder.iterdir() if not p.name.startswith(".") and p.name != "__MACOSX"]
    if len(entries) != 1:
        raise UpdateError("the update does not contain exactly one app")
    return entries[0]


_POSIX_SCRIPT = """#!/bin/sh
# Waits for the old app to exit, swaps in the new one and starts it.
while kill -0 {pid} 2>/dev/null; do sleep 0.2; done
rm -rf {old}
mv {target} {old} && mv {new} {target} || {{ mv {old} {target} 2>/dev/null; exit 1; }}
rm -rf {old}
{launch}
rm -f "$0"
"""

_WINDOWS_SCRIPT = """@echo off
rem Waits for the old app to exit, swaps in the new one and starts it.
:wait
tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL && (timeout /t 1 /nobreak >NUL & goto wait)
if exist {old} rmdir /S /Q {old}
move {target} {old} >NUL || exit /b 1
move {new} {target} >NUL || (move {old} {target} >NUL & exit /b 1)
rmdir /S /Q {old}
{launch}
del "%~f0"
"""


def replace_on_exit(bundle: Union[str, Path], target: Optional[Union[str, Path]] = None, *,
                    relaunch: bool = True, args: Tuple[str, ...] = ()) -> Path:
    """Swaps ``target`` (this app by default) for ``bundle`` once this process exits, then restarts it.

    A small shell (or ``.cmd`` on Windows) script waits for the current process to end,
    moves the old app aside, moves the new one in and starts it; if the move fails the
    old app is put back. Returns the script's path. Quit the app right after calling it.
    """
    bundle = Path(bundle).resolve()
    target = Path(target).resolve() if target else install_dir()
    if target is None:
        raise UpdateError("only a packaged app can replace itself; update with pip or uv instead")
    old = target.with_name(target.name + ".old")
    exe_name = Path(sys.executable).name
    if os.name == "nt":
        q = lambda p: f'"{p}"'  # noqa: E731
        launch = f'start "" {q(target / exe_name)} {" ".join(q(a) for a in args)}' if relaunch else ""
        text = _WINDOWS_SCRIPT.format(pid=os.getpid(), old=q(old), target=q(target), new=q(bundle), launch=launch)
        script = Path(tempfile.gettempdir()) / f"pyzed-update-{os.getpid()}.cmd"
        script.write_text(text, encoding="utf-8")
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(["cmd", "/c", str(script)], creationflags=flags, close_fds=True)  # noqa: S603, S607
        return script
    import shlex

    if sys.platform == "darwin" and target.suffix == ".app":
        launch = f"open {shlex.quote(str(target))}" + (" --args " + " ".join(map(shlex.quote, args)) if args else "")
    else:
        launch = " ".join(shlex.quote(a) for a in (str(target / exe_name), *args)) + " >/dev/null 2>&1 &"
    text = _POSIX_SCRIPT.format(pid=os.getpid(), old=shlex.quote(str(old)), target=shlex.quote(str(target)),
                                new=shlex.quote(str(bundle)), launch=launch if relaunch else "")
    script = Path(tempfile.gettempdir()) / f"pyzed-update-{os.getpid()}.sh"
    script.write_text(text, encoding="utf-8")
    script.chmod(0o755)
    subprocess.Popen(["/bin/sh", str(script)], start_new_session=True, close_fds=True,  # noqa: S603
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return script


# -- remembering checks ---------------------------------------------------------------------------


def _state_file() -> Path:
    from .project import config_dir

    return config_dir() / "updates.json"


def load_state() -> Dict[str, Any]:
    """What the updater remembers: ``last_check`` (epoch seconds), ``last_seen`` version and ``skipped``."""
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(**values: Any) -> None:
    """Updates the remembered values (missing folders are created; errors are ignored)."""
    state = load_state()
    state.update(values)
    try:
        _state_file().parent.mkdir(parents=True, exist_ok=True)
        _state_file().write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


def due(every: float = 24 * 3600) -> bool:
    """Whether the last automatic check was more than ``every`` seconds ago."""
    return time.time() - float(load_state().get("last_check") or 0) >= every
