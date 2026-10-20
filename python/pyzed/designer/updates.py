"""Updates of Pyzed Design, like Zed's: a quiet daily check, a download in the background,
"Restart to update", and a What's new tab with the release notes after an update.
The stable channel follows the latest release; the preview channel also takes pre-releases
(``vX.Y.Z-rc.N``), like Zed Preview.

``UpdateController`` keeps the state and runs the slow parts off the UI thread (see
``pyzed.updater`` for the checking, downloading and swapping itself); ``status_items``
and ``notes_view`` draw it. The compiled app replaces itself; when the designer runs
from Python (``pip``/``uv``), the tab shows the command that upgrades the package.
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional

from .. import __version__, _core, ui
from .. import updater
from ..theme import Theme, alpha
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

REPO = "albakore/pyzed"
APP = "pyzed-design"
#: The id of the What's new tab in the designer's tab bar.
TAB_ID = "whats-new"
#: Update channels: "stable" takes final releases only, "preview" pre-releases too.
CHANNELS = ("stable", "preview")
#: The uninstall entry the Windows installer writes (``installer/windows/pyzed-design.iss``, its AppId).
WINDOWS_UNINSTALL_KEY = ("Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
                         "{8F4C2E6B-3A1D-4F7E-9B2C-5D6E7F8A9B0C}_is1")
#: The installer's files in the app folder, carried over when an update replaces it.
INSTALLER_FILES = ("unins*",)


def sync_windows_registration(version: str) -> bool:
    """Shows ``version`` in Windows' Settings → Apps after a self-update; ``True`` when it changed it.

    Only for copies installed with the setup program (the portable zip has no entry).
    """
    if sys.platform != "win32" or not updater.is_frozen():
        return False
    import winreg  # type: ignore[import-not-found]

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_UNINSTALL_KEY, 0,
                            winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            if winreg.QueryValueEx(key, "DisplayVersion")[0] == version:
                return False
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, version)
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "Pyzed Design")
            return True
    except OSError:
        return False


class UpdateController:
    """Checks for, downloads and installs new versions of the designer."""

    def __init__(self, designer: "Designer", *, current: str = __version__) -> None:
        self.d = designer
        self.current = current
        #: "idle" | "checking" | "up_to_date" | "available" | "downloading" | "ready" | "error"
        self.status = "idle"
        self.latest: Optional[updater.Release] = None
        self.progress = 0.0
        self.error: Optional[str] = None
        self.bundle: Optional[Path] = None
        #: The release shown in the What's new tab (``None`` when the tab is closed) and whether it is active.
        self.notes: Optional[updater.Release] = None
        self.notes_active = False
        #: Set by ``restart``: the process must end right after the window closes so the swap can run.
        self.restart_pending = False

    # -- state ----------------------------------------------------------------------------
    @property
    def can_install(self) -> bool:
        """Whether this copy can replace itself (the compiled app in a writable folder)."""
        return updater.can_update_in_place()

    @property
    def busy(self) -> bool:
        return self.status in ("checking", "downloading")

    @property
    def available(self) -> bool:
        return self.status in ("available", "downloading", "ready")

    def _run(self, work: Callable[[], Any], done: Callable[[Any], Any],
             failed: Optional[Callable[[str], Any]] = None) -> Any:
        """Runs ``work`` in a worker thread; ``done(result)`` or ``failed(message)`` then run on the UI thread."""

        async def task() -> Callable[[], Any]:
            try:
                result = await asyncio.get_running_loop().run_in_executor(None, work)
            except updater.UpdateError as err:
                message = str(err)
                return lambda: (failed or self._failed)(message)
            except Exception as err:  # noqa: BLE001 - never let an update break the designer
                message = f"{type(err).__name__}: {err}"
                return lambda: (failed or self._failed)(message)
            return lambda: done(result)

        return task()

    def _failed(self, message: str) -> None:
        self.status, self.error = "error", message

    # -- start up ---------------------------------------------------------------------------
    def on_start(self) -> List[Any]:
        """At launch: shows What's new after an update and checks for a newer version once a day."""
        commands: List[Any] = []
        state = updater.load_state()
        seen = state.get("last_seen")
        if seen and updater.is_newer(self.current, str(seen)):
            commands.append(self.show_notes(self.current))
        if seen != self.current:
            updater.save_state(last_seen=self.current)
            sync_windows_registration(self.current)
        if self.d.prefs.check_updates and updater.due():
            commands.append(self.check(quiet=True))
        return [c for c in commands if c is not None]

    # -- actions ----------------------------------------------------------------------------
    @property
    def channel(self) -> str:
        """The update channel in the preferences: ``"stable"`` or ``"preview"``."""
        channel = getattr(self.d.prefs, "update_channel", "stable")
        return channel if channel in CHANNELS else "stable"

    def check(self, quiet: bool = False) -> Any:
        """Asks GitHub for the latest release of the channel; ``quiet`` only speaks up when there is one."""
        if self.busy:
            return None
        self.status, self.error = "checking", None

        def done(release: updater.Release) -> None:
            updater.save_state(last_check=time.time())
            self.latest = release
            # A release counts once its builds are attached: the tag publishes it before the pipeline ends.
            built = release.asset_for(updater.asset_name(APP)) is not None if self.can_install else release.has_wheels
            if built and updater.is_newer(release.version, self.current) and \
                    updater.load_state().get("skipped") != release.version:
                self.status = "available"
                self.d.notify(tr("Pyzed Design {version} is available", version=release.version),
                              tr("Open What's new to see the changes and update."), kind="info", seconds=6)
            else:
                self.status = "up_to_date"
                if not quiet:
                    self.d.notify(tr("Pyzed Design is up to date"), f"{self.current}", kind="success", seconds=3)

        def failed(message: str) -> None:
            self._failed(message)
            if not quiet:
                self.d.notify(tr("Could not check for updates"), message, kind="error", seconds=5)
            else:
                self.status = "idle"

        preview = self.channel == "preview"
        return self._run(lambda: updater.latest(REPO, prerelease=preview), done, failed)

    def install(self) -> Any:
        """Downloads the new version for this platform and unpacks it next to the download."""
        release = self.latest
        if release is None or self.busy:
            return None
        asset = release.asset_for(updater.asset_name(APP))
        if asset is None:
            self.d.notify(tr("No build for this platform"), updater.asset_name(APP), kind="error", seconds=5)
            return None
        self.status, self.progress, self.error = "downloading", 0.0, None

        def set_progress(value: float) -> None:
            self.progress = value  # read by the view; the subscription redraws it

        def work() -> Path:
            from ..project import config_dir

            folder = config_dir() / "updates" / release.version
            archive = updater.download(asset, folder, progress=set_progress)
            return updater.extract(archive)

        def done(bundle: Path) -> None:
            self.bundle, self.status = bundle, "ready"
            self.d.notify(tr("Update downloaded"), tr("Restart Pyzed Design to finish."), kind="success", seconds=5)

        def failed(message: str) -> None:
            self.status, self.error = "available", message
            self.d.notify(tr("The update failed"), message, kind="error", seconds=6)

        return self._run(work, done, failed)

    def restart(self) -> Any:
        """Swaps in the downloaded version when the designer exits, and exits (asking to save first)."""
        if self.bundle is None:
            return None
        try:
            updater.replace_on_exit(self.bundle, keep=INSTALLER_FILES)
        except (updater.UpdateError, OSError) as err:
            self.d.notify(tr("The update failed"), str(err), kind="error", seconds=6)
            return None
        updater.save_state(last_seen=self.current)
        self.restart_pending = True
        return _core.Command.exit()

    def skip(self) -> None:
        """Hides this version until a newer one comes out."""
        if self.latest is not None:
            updater.save_state(skipped=self.latest.version)
        self.status = "up_to_date"
        self.close_notes()

    def toggle_auto(self) -> None:
        """Turns the daily automatic check on or off."""
        self.d.set_pref("check_updates", not self.d.prefs.check_updates)

    def toggle_preview(self) -> Any:
        """Switches between the stable and the preview channel, and checks the new one."""
        self.d.set_pref("update_channel", "stable" if self.channel == "preview" else "preview")
        updater.save_state(skipped=None)
        return self.check(quiet=True)

    # -- What's new tab -------------------------------------------------------------------------
    def show_notes(self, version: Optional[str] = None) -> Any:
        """Opens the What's new tab with the notes of ``version`` (the newest one found, else this one)."""
        if version is None and self.latest is not None and self.available:
            self.notes, self.notes_active = self.latest, True
            return None
        version = version or self.current
        self.notes = updater.Release(version=version, tag=f"v{version}", notes=tr("Loading the release notes…"))
        self.notes_active = True

        def done(release: updater.Release) -> None:
            if self.notes is not None and self.notes.version == release.version:
                self.notes = release

        def failed(message: str) -> None:
            if self.notes is not None:
                self.notes = updater.Release(version=version, tag=f"v{version}",
                                             notes=tr("Could not load the release notes: {error}", 
                                                 error=message),
                                             url=f"https://github.com/{REPO}/releases/tag/v{version}")

        return self._run(lambda: updater.release(REPO, version), done, failed)

    def close_notes(self) -> None:
        self.notes, self.notes_active = None, False

    def activate_notes(self, active: bool = True) -> None:
        self.notes_active = active and self.notes is not None

    # -- views ----------------------------------------------------------------------------------
    def tab(self) -> Optional[ui.Tab]:
        """The What's new tab for the tab bar, while it is open."""
        if self.notes is None:
            return None
        return ui.Tab(id=TAB_ID, label=tr("What's new in {version}", version=self.notes.version),
                      icon="sparkles", icon_color="accent")

    def status_items(self, t: Theme) -> List[Any]:
        """The status bar item announcing an update (none while up to date)."""
        if self.status == "available" and self.latest is not None:
            return [ui.status_item(tr("Update to {version}", version=self.latest.version),
                                   self.show_notes, icon="circle-arrow-up", color="accent")]
        if self.status == "downloading":
            return [ui.status_item(tr("Downloading update… {percent}%", percent=int(self.progress * 100)),
                                   self.show_notes, icon="download", color="accent")]
        if self.status == "ready":
            return [ui.status_item(tr("Restart to update"), self.restart, icon="refresh-cw", color="success")]
        return []

    def _actions(self, release: updater.Release, t: Theme) -> List[Any]:
        newer = updater.is_newer(release.version, self.current)
        if not newer:
            return [ui.badge(tr("Installed"), icon="check", tint="success", theme=t)]
        if self.status == "ready":
            return [ui.button(tr("Restart to update"), self.restart, icon="refresh-cw", variant="solid",
                              tint="success", theme=t)]
        if self.status == "downloading":
            return [_core.container(ui.progress(self.progress, theme=t), width=180),
                    ui.label(f"{int(self.progress * 100)}%", size="sm", color="text_muted", theme=t)]
        if self.can_install:
            return [ui.button(tr("Download and install"), self.install, icon="download", variant="solid", theme=t),
                    ui.button(tr("Skip this version"), self.skip, variant="ghost", theme=t)]
        return [ui.badge(tr("New"), icon="sparkles", tint="accent", theme=t)]

    def _upgrade_hint(self, release: updater.Release, t: Theme) -> Any:
        """How to upgrade when the designer runs from Python and cannot replace itself."""
        if self.can_install or not updater.is_newer(release.version, self.current):
            return None
        command = (f"uv add pyzed-ui=={release.version}   "
                   f"# {tr('or')}: pip install -U --only-binary pyzed-ui pyzed-ui")
        return ui.callout(tr("Upgrade the package to get it:"), command, tint="accent", theme=t)

    def notes_view(self, t: Theme) -> Any:
        """The content of the What's new tab: version, date, actions and the notes in Markdown."""
        release = self.notes
        if release is None:
            return None
        header = _core.row([
            _core.column([
                ui.heading(f"Pyzed Design {release.version}", level=1, theme=t),
                ui.label(" · ".join(x for x in (release.published, tr("you have {version}", 
                    version=self.current)) if x), size="sm", color="text_muted", theme=t),
            ], spacing=4),
            _core.space(width="fill"),
            _core.row(self._actions(release, t), spacing=8, align="center"),
        ], align="center", width="fill")
        error = None
        if self.error and self.status != "error":
            error = ui.callout(tr("The update failed"), self.error, tint="error", theme=t)
        links = _core.row([
            ui.button(tr("Open on GitHub"), lambda: self.d.open_url(release.url), icon="external-link",
                      variant="ghost", size="sm", theme=t) if release.url else None,
            ui.button(tr("Check for updates"), lambda: self.check(), icon="refresh-cw", variant="ghost", size="sm",
                      theme=t),
        ], spacing=6)
        body = _core.column([
            header,
            self._upgrade_hint(release, t),
            error,
            _core.container(None, height=1, width="fill", bg=alpha(t.border, 1.0)),
            ui.markdown(release.notes or tr("No notes for this version."), on_link=self.d.open_url, width="fill",
                        theme=t),
            links,
        ], spacing=16, width="fill", max_width=820)
        return _core.container(_core.scrollable(_core.container(body, padding=(28, 36), width="fill",
                                                                align_x="center"), height="fill"),
                               width="fill", height="fill", bg=t.editor)
