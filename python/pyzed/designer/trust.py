"""Restricted mode: a project from somewhere else does not run anything until you trust it.

Opening a project can run its code: ``uv sync`` installs its packages (and builds them, running
their build scripts), the toolbox imports its components, and Run starts its forms. Like Zed and
VS Code, Pyzed Design asks first. A folder you did not create opens in **restricted mode**: you can
read and edit every file, but the designer does not prepare its environment, import its modules,
run it, export it or use the tools of its ``.venv`` until you choose **Trust this project**.

The folders you trust are saved in ``trusted.json`` in the Pyzed config folder (a folder inside a
trusted one is trusted too). Projects created by the designer (New project, an example of the
gallery) are trusted from the start. **Settings → Running → Restricted mode** turns it off, and
``PYZED_TRUST_ALL=1`` does the same for scripts and CI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha
from . import logs as _logs
from .locale import tr
from .settings import config_dir

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: Turns restricted mode off for every folder (scripts, CI, the tests).
ENV = "PYZED_TRUST_ALL"

#: Whether restricted mode is on when a caller does not say: off outside the designer (``pyzed run``, the
#: MCP server), which sets it from its settings.
_enabled: Callable[[], bool] = lambda: False


def trust_path() -> Path:
    """The list of trusted folders: ``trusted.json`` in the Pyzed config folder."""
    return config_dir() / "trusted.json"


def _resolve(folder: Union[str, Path]) -> Path:
    try:
        return Path(folder).expanduser().resolve()
    except OSError:
        return Path(folder).expanduser().absolute()


def trusted_folders() -> List[Path]:
    """The folders the user trusts (``[]`` when the list is missing or broken)."""
    try:
        data = json.loads(trust_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    folders = data.get("folders") if isinstance(data, dict) else None
    return [Path(f) for f in folders or () if isinstance(f, str) and f]


def _write(folders: List[Path]) -> bool:
    path = trust_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"folders": [str(f) for f in folders]}, indent=2) + "\n", encoding="utf-8")
    except OSError as err:
        _logs.log("trust").warning("Could not save the trusted folders: %s", err)
        return False
    return True


def _bundled() -> List[Path]:
    """Pyzed's own folders (its examples and templates), always trusted."""
    import pyzed

    return [_resolve(Path(pyzed.__file__).parent)]


def is_trusted(folder: Union[str, Path, None], *, enabled: Optional[bool] = None) -> bool:
    """Whether the code of ``folder`` may run: it, or a folder holding it, was trusted (always ``True`` with
    restricted mode off, ``enabled=False``, or ``PYZED_TRUST_ALL=1``)."""
    if enabled is None:
        enabled = _enabled()
    if folder is None or not enabled or os.environ.get(ENV, "").strip() not in ("", "0"):
        return True
    here = _resolve(folder)
    return any(here == f or f in here.parents for f in (*trusted_folders(), *_bundled()))


def trust(folder: Union[str, Path]) -> bool:
    """Adds ``folder`` to the trusted folders (and saves the list); ``False`` if it could not be saved."""
    here = _resolve(folder)
    folders = trusted_folders()
    if here in folders:
        return True
    _logs.event("trust", "Trusted %s", here)
    return _write([*folders, here])


def forget(folder: Union[str, Path]) -> bool:
    """Takes ``folder`` out of the trusted folders."""
    here = _resolve(folder)
    folders = trusted_folders()
    if here not in folders:
        return True
    _logs.event("trust", "No longer trusts %s", here)
    return _write([f for f in folders if f != here])


class TrustController:
    """Restricted mode in a ``Designer``: whether the active project (or the folder of the open form) is
    trusted, the question asked when it is not, and what happens when the user trusts it."""

    def __init__(self, designer: "Designer") -> None:
        global _enabled
        self.d = designer
        _enabled = lambda: self.enabled  # noqa: E731 - the code editor's servers ask too (``lsp``)
        #: The folder the trust dialog asks about.
        self.asking: Optional[Path] = None
        #: What the user tried to do when the dialog opened (run, export...), done once trusted.
        self.pending: Optional[Any] = None

    @property
    def enabled(self) -> bool:
        """Whether restricted mode is on (Settings → Running). Only the user's own settings count: a project
        cannot turn it off for itself."""
        store = getattr(self.d, "profile_store", None)
        try:
            return bool(store.value("designer", "restricted_mode", "user")) if store is not None else True
        except (KeyError, AttributeError):
            return bool(getattr(self.d.prefs, "restricted_mode", True))

    def folder(self) -> Optional[Path]:
        """The folder whose code the designer would run: the active project's, else the open form's."""
        project = self.d.projects.project
        if project is not None:
            return project.root
        path = getattr(self.d.doc, "path", None)
        return Path(path).resolve().parent if path else None

    def trusted(self, folder: Union[str, Path, None] = None) -> bool:
        """Whether ``folder`` (by default the active project's) may run code."""
        return is_trusted(folder if folder is not None else self.folder(), enabled=self.enabled)

    @property
    def restricted(self) -> bool:
        """Whether the active project is open in restricted mode."""
        return not self.trusted()

    def allow(self, then: Optional[Any] = None) -> bool:
        """``True`` when the active project may run code; otherwise opens the trust dialog (and keeps ``then``,
        a callable, to run once the user trusts it) and returns ``False``."""
        if self.trusted():
            return True
        self.ask(self.folder(), then)
        return False

    def ask(self, folder: Optional[Path], then: Optional[Any] = None) -> None:
        """Shows the trust dialog for ``folder``."""
        if folder is None:
            return
        self.asking, self.pending = folder, then
        self.d.dialog = "trust"

    def opened(self, folder: Path) -> None:
        """A project or form of ``folder`` was opened: asks once whether to trust it when it is not trusted."""
        if not self.trusted(folder) and self.d.dialog in (None, "trust"):
            self.ask(folder)

    def accept(self) -> Any:
        """Trusts the folder asked about and does what restricted mode held back: prepares the environment,
        imports the project's components and runs the pending action."""
        folder, pending = self.asking, self.pending
        self.asking = self.pending = None
        if self.d.dialog == "trust":
            self.d.dialog = None
        if folder is None:
            return None
        if not trust(folder):
            self.d.notify(tr("Could not save the trusted folders"), str(trust_path()), kind="error", seconds=5)
            return None
        self.d.notify(tr("{name} is trusted", name=folder.name), str(folder), kind="success", seconds=3)
        return self.d.trust_changed(pending)

    def decline(self) -> None:
        """Keeps the folder in restricted mode (the banner stays, the dialog closes)."""
        self.asking = self.pending = None
        if self.d.dialog == "trust":
            self.d.dialog = None

    def revoke(self) -> None:
        """Stops trusting the active project's folder (Project panel menu)."""
        folder = self.folder()
        if folder is not None:
            forget(folder)
            self.d.notify(tr("{name} is in restricted mode", name=folder.name), kind="info", seconds=3)


def dialog(d: "Designer", t: Theme) -> Any:
    """The question asked about a folder that is not trusted."""
    c = d.trust
    folder = c.asking
    held = [tr("Install its packages (uv sync), which can run their build scripts"),
            tr("Import its components into the toolbox"),
            tr("Run, build or export it, and use the tools of its .venv")]
    body = _core.column([
        ui.label(tr("Do you trust the authors of the files in this folder?"), size="md", weight="medium", theme=t),
        ui.label(str(folder) if folder else "", size="sm", mono=True, color="text_muted", theme=t),
        ui.label(tr("In restricted mode you can read and edit every file, but Pyzed Design does not:"), size="sm",
                 theme=t),
        _core.column([_core.row([_icon("shield-alert", size=13, color=t.color("warning")),
                                 ui.label(item, size="sm", theme=t)], spacing=8, align="center") for item in held],
                     spacing=4),
        ui.label(tr("Trust it only if you know where it comes from: its code can do anything your user can."),
                 size="xs", color="text_muted", theme=t),
    ], spacing=10)
    return ui.modal(body, title=tr("Restricted mode"), icon="shield-alert", on_close=c.decline, width=520, theme=t,
                    footer=[_core.space(width="fill"),
                            ui.button(tr("Stay in restricted mode"), c.decline, variant="ghost", theme=t),
                            ui.button(tr("Trust this project"), c.accept, icon="shield-check", variant="solid",
                                      theme=t)])


def banner(d: "Designer", t: Theme) -> Optional[Any]:
    """The box over the Project panel while the project is in restricted mode (stacked: the dock is narrow)."""
    if not d.trust.restricted:
        return None
    box = _core.container(_core.column([
        _core.row([_icon("shield-alert", size=14, color=t.warning),
                   ui.label(tr("Restricted mode"), size="sm", weight="medium", theme=t)], spacing=8, align="center"),
        ui.label(tr("This project's code does not run until you trust it."), size="xs", color="text_muted",
                 theme=t),
        ui.button(tr("Trust…"), lambda: d.trust.ask(d.trust.folder()), icon="shield-check", size="sm", theme=t),
    ], spacing=6, width="fill"), padding=(8, 10), width="fill", bg=alpha(t.warning, 0.1), radius=t.radius,
        border_color=alpha(t.warning, 0.35), border_width=1.0)
    return _core.container(box, padding=(6, 8), width="fill")
