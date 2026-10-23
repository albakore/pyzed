"""The Export dialog (File → Export app…): package the project as an app for each platform.

Like Godot's export window, its sections set what ``pyzed build`` does: the app's name and
details, the platforms and architectures, the backend (PyInstaller, or Nuitka for compiled,
faster apps), the icon, the splash screen and the files to bundle. The settings live in
``[tool.pyzed.build]`` of ``pyproject.toml``, so ``pyzed build`` and CI builds use the same.

**Build** packages the app for this computer: ``ExportController`` prepares the build off the
UI thread (``build.prepare``), runs the backend with its output in the Console, then
``build.finish`` puts the app in ``dist/``. The backends do not cross-compile, so the
other platforms are built by a GitHub Actions workflow the dialog writes. Android is built here
from any computer (``build.build_android``): an APK to try, or an AAB signed for Google Play.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .. import _core, ui
from .. import build as _build
from .. import project as _project
from ..theme import Theme
from . import logs as _logs
from . import workspace as _workspace
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

SECTIONS = ("general", "platforms", "backend", "icon", "splash", "files", "android", "command")
IMAGE_FILTERS = [("Images", ["png", "jpg", "jpeg", "webp", "bmp"])]
ICON_FILTERS = [("Images", ["png", "jpg", "jpeg", "webp", "ico", "icns"])]
KEYSTORE_FILTERS = [("Keystores", ["jks", "keystore", "p12"])]
PREVIEW_SIZES = (16, 24, 32, 48, 64, 128)


class ExportController:
    """The Export dialog's settings and the build it runs."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.opts: Optional[_build.BuildOptions] = None
        self.section = SECTIONS[0]
        #: Settings changed in the dialog and not yet written to ``pyproject.toml``.
        self.dirty = False
        #: ``None``, ``"preparing"``, ``"building"``, ``"finishing"``, ``"done"``, ``"failed"`` or ``"cancelled"``.
        self.state: Optional[str] = None
        self.plan: Optional[_build.Plan] = None
        self.process: Any = None
        self.started = 0.0
        self.elapsed = 0.0
        self.message = ""
        #: What is typed in the "add" field of each list (include, hidden imports...).
        self.adding: Dict[str, str] = {}
        #: The last app built (shown in the file manager by "Show in folder").
        self.output: Optional[Path] = None

    # -- state ------------------------------------------------------------------------
    @property
    def project(self) -> Optional[_project.Project]:
        return self.d.projects.project

    @property
    def running(self) -> bool:
        """Whether a build is being prepared, run or finished."""
        return self.state in ("preparing", "building", "finishing")

    @property
    def target(self) -> _build.Target:
        return _build.host_target(self.project)

    def open(self) -> None:
        """Opens the dialog with the project's build settings (asks to open a project if none is)."""
        self.d.app_menu = None
        project = self.project
        if project is None:
            self.d.notify(tr("Open a project to export it"), tr("Project → Open, or create one with New project"),
                          kind="warning", seconds=4)
            return
        if self.opts is None or not self.dirty:
            self.opts = _build.BuildOptions.from_project(project)
            if not self.opts.targets:
                self.opts.targets = [self.target.id]
        self.d.dialog = "export"

    def build_now(self) -> Any:
        """Builds the app for this computer with the project's export settings (Run → Build app)."""
        if self.project is None:
            return None
        if self.opts is None or not self.dirty:
            self.opts = _build.BuildOptions.from_project(self.project)
        problems = self.problems()
        if problems:
            self.d.notify(tr("Cannot build the app"), problems[0], kind="error", seconds=5)
            return None
        return self.build()

    def close(self) -> None:
        """Closes the dialog, keeping its settings in ``pyproject.toml``."""
        if self.dirty:
            self.save()
        self.d.close_dialog()

    def show(self, section: str) -> None:
        self.section = section

    def setter(self, attr: str, convert: Callable[[Any], Any] = lambda v: v) -> Callable[[Any], None]:
        """Returns a callback that sets option ``attr`` (an empty text clears it)."""
        def set_value(value: Any) -> None:
            assert self.opts is not None
            value = convert(value)
            if isinstance(value, str) and not value.strip() and attr not in ("archive",):
                value = None
            setattr(self.opts, attr, value)
            self.dirty = True

        return set_value

    def toggle_target(self, target: str, on: bool) -> None:
        assert self.opts is not None
        chosen = [t for t in self.opts.targets if t != target]
        if on:
            chosen.append(target)
        self.opts.targets = [t.id for t in _build.TARGETS if t.id in chosen]
        self.dirty = True

    def set_splash(self, on: bool) -> None:
        assert self.opts is not None
        self.opts.splash = _build.Splash(self.opts.splash.image if self.opts.splash else "") if on else None
        self.dirty = True

    def splash_setter(self, attr: str, convert: Callable[[Any], Any] = lambda v: v) -> Callable[[Any], None]:
        def set_value(value: Any) -> None:
            if self.opts is not None and self.opts.splash is not None:
                setattr(self.opts.splash, attr, convert(value))
                self.dirty = True

        return set_value

    @property
    def android(self) -> Dict[str, Any]:
        """``[tool.pyzed.build.android]`` as it is edited."""
        assert self.opts is not None
        table = self.opts.extra.get("android")
        if not isinstance(table, dict):
            table = self.opts.extra["android"] = {}
        return table

    def android_setter(self, key: str, convert: Callable[[Any], Any] = lambda v: v) -> Callable[[Any], None]:
        """Returns a callback that sets ``key`` of the Android settings (an empty value clears it)."""
        def set_value(value: Any) -> None:
            value = convert(value)
            if value in (None, "", []):
                self.android.pop(key, None)
            else:
                self.android[key] = value
            self.dirty = True

        return set_value

    def toggle_abi(self, abi: str, on: bool) -> None:
        from .. import android

        chosen = [a for a in self.android.get("abis", ["arm64-v8a"]) if a != abi] + ([abi] if on else [])
        chosen = [a for a in android.ABIS if a in chosen] or ["arm64-v8a"]
        self.android_setter("abis")(chosen if chosen != ["arm64-v8a"] else None)

    def pick_keystore(self) -> Any:
        project = self.project

        def chosen(paths: List[str]) -> None:
            if paths:
                self.android_setter("keystore")(self.relative(paths[0]))

        return _core.Command.pick_files(chosen, title=tr("Choose the keystore"), filters=KEYSTORE_FILTERS,
                                        multiple=False, directory=str(project.root) if project else None)

    def set_backend_args(self, text: str) -> None:
        assert self.opts is not None
        self.opts.backend_options.setdefault(self.opts.backend, {})["args"] = text.split()
        if not text.strip():
            self.opts.backend_options[self.opts.backend].pop("args", None)
        self.dirty = True

    def add_item(self, attr: str) -> None:
        """Adds what is typed in the "add" field of list ``attr`` to it."""
        assert self.opts is not None
        text = self.adding.get(attr, "").strip()
        if text and text not in getattr(self.opts, attr):
            getattr(self.opts, attr).append(text)
            self.dirty = True
        self.adding[attr] = ""

    def remove_item(self, attr: str, item: str) -> None:
        assert self.opts is not None
        setattr(self.opts, attr, [i for i in getattr(self.opts, attr) if i != item])
        self.dirty = True

    def relative(self, path: str) -> str:
        """``path`` relative to the project when it is inside it (as ``pyproject.toml`` keeps it)."""
        project = self.project
        if project is None:
            return path
        try:
            return Path(path).resolve().relative_to(project.root.resolve()).as_posix()
        except ValueError:
            return path

    def pick(self, attr: str, *, splash: bool = False) -> Any:
        """Returns the command that opens the system's file dialog to choose the icon (or the splash image)."""
        project = self.project

        def chosen(paths: List[str]) -> None:
            if paths:
                (self.splash_setter("image") if splash else self.setter(attr))(self.relative(paths[0]))

        return _core.Command.pick_files(chosen, title=tr("Choose the splash image") if splash else tr("Choose the icon"),
                                        filters=IMAGE_FILTERS if splash else ICON_FILTERS, multiple=False,
                                        directory=str(project.root) if project else None)

    def save(self) -> None:
        """Writes the settings to ``[tool.pyzed.build]`` of ``pyproject.toml``."""
        project = self.project
        if project is None or self.opts is None:
            return
        try:
            _build.save_options(project, self.opts)
        except OSError as err:
            self.d.notify(tr("Could not save the export settings"), str(err), kind="error", seconds=5)
            return
        self.dirty = False
        _logs.event("export", "Saved the export settings")

    # -- building -----------------------------------------------------------------------
    def problems(self) -> List[str]:
        """What stops a build now (shown in the dialog)."""
        project = self.project
        found: List[str] = []
        if project is None:
            return [tr("Open a project first")]
        if project.script is None and not project.main_form.exists():
            found.append(tr("The startup form {path} does not exist", path=project.main_form.name))
        if _project.find_uv() is None and not project.environment.remote:
            found.append(tr("uv is not installed"))
        return found

    def build(self) -> Any:
        """Saves the settings and packages the app for this computer, with the output in the Console."""
        project, opts = self.project, self.opts
        if project is None or opts is None or self.running or self.problems():
            return None
        self.save()
        self.state, self.message, self.started, self.elapsed = "preparing", "", time.monotonic(), 0.0
        self.plan = None
        _logs.event("export", "Exporting %s for %s", project.name, self.target.id)

        async def prepare() -> Callable[[], Any]:
            loop = asyncio.get_running_loop()
            try:
                plan = await loop.run_in_executor(None, lambda: _build.prepare(project, opts))
            except Exception as err:  # noqa: BLE001 - shown to the user
                return lambda: self._failed(str(err))
            return lambda: self._start(plan)

        return prepare()

    def build_android(self) -> Any:
        """Saves the settings and packs the app for Android (APK or AAB) in the background."""
        project, opts = self.project, self.opts
        if project is None or opts is None or self.running or self.problems():
            return None
        self.save()
        self.state, self.message, self.started, self.elapsed = "building", "", time.monotonic(), 0.0
        self.plan, self.output = None, None
        console = self.d.console
        console.start(tr("Export {name}", name=_build.app_name(project, opts)), "Android")
        if self.d.prefs.console_on_run:
            self.d.show_panel("console")
        _logs.event("export", "Exporting %s for Android", project.name)
        lines: List[str] = []

        async def run() -> Callable[[], Any]:
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(None, lambda: _build.build_android(project, opts,
                                                                                       report=lines.append))
            except Exception as err:  # noqa: BLE001 - shown to the user
                return lambda: self._failed(str(err))
            for line in lines:
                console.log.write("info", line)
            if self.state != "building":
                return lambda: None
            if not result.ok:
                return lambda: self._failed(result.output)
            return lambda: self._android_done(_build.android_output(project, opts), result.output.splitlines())

        return run()

    def _android_done(self, out: Path, notes: List[str]) -> None:
        self.state, self.output = "done", out
        self.elapsed = time.monotonic() - self.started
        project = self.project
        self.message = tr("{path} · {size} · {seconds} s", path=_relative(out, project.root) if project else str(out),
                          size=_build.human_size(_build.size_of(out)) if out.exists() else "",
                          seconds=round(self.elapsed))
        for note in notes:
            self.d.console.log.write("info", note)
        self.d.console.log.write("info", f"✓ {out}")
        self.d.console.stop(quiet=True)
        _logs.event("export", "Exported %s in %.0f s", out, self.elapsed)
        self.d.notify(tr("{name} is ready", name=out.name), self.message, kind="success", seconds=6)

    def _start(self, plan: _build.Plan) -> Any:
        if self.state != "preparing":  # cancelled meanwhile
            return None
        self.plan = plan
        console = self.d.console
        console.start(tr("Export {name}", name=plan.name), f"{_build.BACKEND_LABELS[plan.opts.backend]}, {plan.target.id}")
        console.log.write("info", "$ " + _build.describe(plan.command))
        for warning in plan.warnings:
            console.log.write("warning", warning)
        if self.d.prefs.console_on_run:
            self.d.show_panel("console")
        try:
            self.process = plan.project._popen(plan.command, True, _build.environment(plan))
        except (OSError, FileNotFoundError) as err:
            return self._failed(str(err))
        self.state = "building"
        console.pipe(self.process)
        process = self.process

        async def wait() -> Callable[[], Any]:
            loop = asyncio.get_running_loop()
            code = await loop.run_in_executor(None, process.wait)
            if code != 0 or self.state != "building":
                return lambda: self._failed(tr("The backend stopped with code {code}", code=code)) \
                    if self.state == "building" else None
            self.state = "finishing"
            try:
                notes = await loop.run_in_executor(None, lambda: _build.finish(plan))
            except Exception as err:  # noqa: BLE001 - shown to the user
                return lambda: self._failed(str(err))
            return lambda: self._done(plan, notes)

        return wait()

    def _done(self, plan: _build.Plan, notes: List[str]) -> None:
        self.state, self.process, self.output = "done", None, plan.output
        self.elapsed = time.monotonic() - self.started
        size = _build.human_size(_build.size_of(plan.output)) if plan.output.exists() else ""
        self.message = tr("{path} · {size} · {seconds} s", path=_relative(plan.output, plan.project.root), size=size,
                          seconds=round(self.elapsed))
        for note in notes:
            self.d.console.log.write("info", note)
        self.d.console.log.write("info", f"✓ {plan.output}")
        self.d.console.stop(quiet=True)
        _logs.event("export", "Exported %s in %.0f s", plan.output, self.elapsed)
        self.d.notify(tr("{name} is ready", name=plan.name), self.message, kind="success", seconds=6)

    def _failed(self, reason: str) -> None:
        self.state, self.process = "failed", None
        self.elapsed = time.monotonic() - self.started
        self.message = reason
        self.d.console.stop(quiet=True)
        _logs.log("export").error("Export failed: %s", reason)
        self.d.notify(tr("The export failed"), tr("{reason}. The Console has the backend's output", reason=reason),
                      kind="error", seconds=6)

    def cancel(self) -> None:
        """Stops the build that is running."""
        if self.process is not None:
            _project.terminate(self.process)
        if self.running:
            self.state, self.process = "cancelled", None
            self.message = tr("Cancelled")
            self.d.console.stop()

    def reveal(self) -> None:
        """Shows the exported app in the file manager."""
        if self.output is not None and self.output.exists():
            _workspace.reveal(self.output)

    def copy_command(self) -> Any:
        """Returns the command that copies the backend's command line to the clipboard."""
        project, opts = self.project, self.opts
        if project is None or opts is None:
            return None
        return _core.Command.copy(_build.describe(_build.prepare(project, _copy(opts)).command))

    def write_workflow(self) -> None:
        """Writes ``.github/workflows/build.yml``, which builds every chosen platform on GitHub Actions."""
        project, opts = self.project, self.opts
        if project is None or opts is None:
            return
        self.save()
        path = _build.workflow(project, targets=opts.targets or [self.target.id])
        rel = _relative(path, project.root)
        self.d.notify(tr("Wrote {path}", path=rel),
                      tr("Push it to GitHub: each tag v* builds {count} platforms", count=len(opts.targets) or 1),
                      kind="success", seconds=6)


def _copy(opts: _build.BuildOptions) -> _build.BuildOptions:
    return _build.BuildOptions.from_table(opts.to_table())


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


# -- the dialog -------------------------------------------------------------------------------

def _titles() -> Dict[str, tuple]:
    return {
        "general": (tr("General"), "info"),
        "platforms": (tr("Platforms"), "monitor-smartphone"),
        "backend": (tr("Backend"), "cpu"),
        "icon": (tr("Icon"), "image"),
        "splash": (tr("Splash screen"), "gallery-horizontal-end"),
        "files": (tr("Files and modules"), "files"),
        "android": ("Android", "smartphone"),
        "command": (tr("Command line"), "square-terminal"),
    }


def _text(e: ExportController, attr: str, t: Theme, *, placeholder: str = "", width: Any = 300,
          mono: bool = False) -> Any:
    assert e.opts is not None
    value = getattr(e.opts, attr)
    return ui.input("" if value is None else str(value), e.setter(attr), placeholder=placeholder, width=width,
                    mono=mono, theme=t)


def _switch(e: ExportController, attr: str, t: Theme) -> Any:
    assert e.opts is not None
    return ui.switch(bool(getattr(e.opts, attr)), e.setter(attr), theme=t)


def general(e: ExportController, t: Theme) -> List[Any]:
    assert e.opts is not None and e.project is not None
    project, opts = e.project, e.opts
    meta = project.data.get("project", {})
    return [ui.settings_group(tr("The app"), [
        ui.field(tr("Name"), _text(e, "name", t, placeholder=project.name),
                 description=tr("The executable, the .app and the folder in dist/"), theme=t),
        ui.field(tr("Version"), _text(e, "version", t, placeholder=str(meta.get("version", "0.1.0"))),
                 description=tr("Empty: [project] version of pyproject.toml"), theme=t),
        ui.field(tr("Publisher"), _text(e, "publisher", t, placeholder="Acme"),
                 description=tr("The company in the Windows file properties"), theme=t),
        ui.field(tr("Identifier"), _text(e, "identifier", t, placeholder=_build.app_identifier(project, opts), mono=True),
                 description=tr("Reverse domain: macOS bundle id and Linux app id. Keep it between releases"),
                 theme=t),
        ui.field(tr("Description"), _text(e, "description", t, placeholder=str(meta.get("description", ""))),
                 theme=t),
        ui.field(tr("Copyright"), _text(e, "copyright", t, placeholder="© 2026 Acme"), theme=t),
    ], theme=t)]


def platforms(e: ExportController, t: Theme) -> List[Any]:
    assert e.opts is not None
    here = e.target
    rows = []
    for target in _build.TARGETS:
        badge = ui.badge(tr("This computer"), tint="accent", theme=t) if target is here else None
        rows.append(_core.row([
            ui.checkbox(target.id in e.opts.targets, lambda on, i=target.id: e.toggle_target(i, on), theme=t),
            _core.column([
                _core.row([ui.label(tr(target.label), theme=t), badge], spacing=8, align="center"),
                ui.label(f"{target.id}  ·  GitHub: {target.runner}", size="xs", mono=True, color="text_muted",
                         theme=t),
            ], spacing=2, width="fill"),
        ], spacing=10, align="center"))
    archive = ui.select([tr("None"), *_build.ARCHIVES], e.opts.archive or tr("None"),
                        lambda v: e.setter("archive")(v if v in _build.ARCHIVES else None), width=140, theme=t)
    return [
        ui.callout(tr("Build here, or everywhere on GitHub Actions"),
                   tr("PyInstaller and Nuitka build for the system they run on. Build packages {target}; the "
                      "workflow builds every checked platform on GitHub's machines when you push a tag v*.",
                      target=tr(here.label)), tint="info", theme=t),
        ui.settings_group(tr("Platforms and architectures"), rows, theme=t,
                          end=ui.button(tr("Write CI workflow"), e.write_workflow, icon="github", variant="ghost",
                                        size="sm", theme=t)),
        ui.settings_group(tr("Distribution"), [
            ui.field(tr("Archive"), archive, description=tr("Also pack the app to upload it (zip works everywhere)"),
                     theme=t),
        ], theme=t),
    ]


def _backend_card(e: ExportController, name: str, title: str, blurb: str, t: Theme) -> Any:
    from .dialogs import _choice_card

    assert e.opts is not None
    return _choice_card(title, blurb, e.opts.backend == name, lambda: e.setter("backend")(name), t,
                        icon="package" if name == "pyinstaller" else "zap")


def backend(e: ExportController, t: Theme) -> List[Any]:
    assert e.opts is not None
    opts = e.opts
    cards = _core.row([
        _backend_card(e, "pyinstaller", "PyInstaller",
                      tr("Bundles your Python files as they are. Quick builds, works everywhere."), t),
        _backend_card(e, "nuitka", "Nuitka",
                      tr("Compiles Python to C: faster code, the smallest single file. Slower builds, needs a C compiler."), t),
    ], spacing=10)
    extra = " ".join(opts.backend_options.get(opts.backend, {}).get("args", []))
    optimize = {tr("None"): 0, tr("Drop asserts"): 1, tr("Drop asserts and docstrings"): 2}
    rows = [
        ui.field(tr("Single file"), _switch(e, "onefile", t),
                 description=tr("One executable that unpacks itself on start; a folder starts faster"), theme=t),
        ui.field(tr("Window only"), _switch(e, "windowed", t),
                 description=tr("Off shows a console next to the app, with its prints and errors"), theme=t),
        ui.field(tr("Optimization"), ui.select(list(optimize), next(k for k, v in optimize.items() if v == opts.optimize),
                                               lambda v: e.setter("optimize")(optimize[v]), width=220, theme=t),
                 description=tr("Python's -O and -OO"), theme=t),
        ui.field(tr("Slim"), _switch(e, "slim", t),
                 description=tr("Leave out standard modules apps do not use (tkinter, test, idlelib…)"), theme=t),
        ui.field(tr("Strip symbols"), _switch(e, "strip", t),
                 description=tr("Smaller binaries on Linux and macOS"), theme=t),
        ui.field(tr("Compress with UPX"), _switch(e, "upx", t),
                 description=tr("Even smaller, if UPX is installed; some antivirus programs distrust it"), theme=t),
        ui.field(tr("More options"), ui.input(extra, e.set_backend_args, placeholder="--lto=yes" if opts.backend == "nuitka"
                                              else "--noconfirm", mono=True, width=300, theme=t),
                 description=tr("Passed to {backend} as they are", backend=_build.BACKEND_LABELS[opts.backend]),
                 theme=t),
    ]
    notes = []
    if opts.backend == "nuitka":
        notes.append(ui.callout(tr("Nuitka needs a C compiler"),
                                tr("Linux: gcc (sudo apt install gcc). macOS: xcode-select --install. Windows: Visual "
                                   "Studio Build Tools, or let Nuitka download MinGW. The first build takes minutes."),
                                tint="hint", theme=t))
    return [cards, *notes, ui.settings_group(_build.BACKEND_LABELS[opts.backend], rows, theme=t)]


def _image_preview(path: Optional[Path], t: Theme, sizes=PREVIEW_SIZES) -> Any:
    if path is None or not path.is_file() or path.suffix.lower() in (".ico", ".icns"):
        return None
    tiles = [_core.column([
        _core.container(_core.image(str(path), width=s, height=s, content_fit="contain"), width=max(s, 24),
                        height=128, align_x="center", align_y="bottom"),
        ui.label(f"{s}", size="xs", color="text_muted", mono=True, theme=t),
    ], spacing=4, align="center") for s in sizes]
    return _core.container(_core.row(tiles, spacing=14, align="end"), padding=12, bg=t.surface, radius=t.radius,
                           border_color=t.border_variant, border_width=1, width="fill")


def icon(e: ExportController, t: Theme) -> List[Any]:
    assert e.opts is not None and e.project is not None
    path = e.project.root / e.opts.icon if e.opts.icon else None
    missing = path is not None and not path.is_file()
    rows = [
        ui.field(tr("Picture"), _core.row([
            _text(e, "icon", t, placeholder="assets/icon.png", width=240, mono=True),
            ui.button(tr("Browse…"), lambda: e.pick("icon"), icon="folder-search", size="sm", theme=t),
        ], spacing=6, align="center"),
            description=tr("A square PNG, 1024 × 1024 is best"), error=tr("The file does not exist") if missing else None,
            theme=t),
    ]
    return [
        ui.settings_group(tr("App icon"), rows, theme=t),
        _image_preview(path, t),
        ui.callout(tr("Made for every system"),
                   tr("The build makes an .ico (Windows, 16 to 256 px), an .icns (macOS, up to 1024 px) and a PNG "
                      "for the windows and the Linux desktop. An .ico or .icns file is used as it is."),
                   tint="hint", theme=t),
    ]


def splash(e: ExportController, t: Theme) -> List[Any]:
    assert e.opts is not None and e.project is not None
    s = e.opts.splash
    rows = [ui.field(tr("Show a splash screen"), ui.switch(s is not None, e.set_splash, theme=t),
                     description=tr("A picture in a window without a frame while the app starts"), theme=t)]
    preview = None
    if s is not None:
        path = e.project.root / s.image if s.image else None
        rows += [
            ui.field(tr("Image"), _core.row([
                ui.input(s.image, e.splash_setter("image"), placeholder="assets/splash.png", width=240, mono=True,
                         theme=t),
                ui.button(tr("Browse…"), lambda: e.pick("image", splash=True), icon="folder-search", size="sm",
                          theme=t),
            ], spacing=6, align="center"), error=tr("The file does not exist") if path and not path.is_file() else None,
                theme=t),
            ui.field(tr("Duration"), ui.number_field(float(s.duration), e.splash_setter("duration", float), min=0,
                                                     max=10, step=0.5, width=110, theme=t),
                     description=tr("Seconds at least; it stays while the startup form loads"), theme=t),
            ui.field(tr("Text"), ui.input(s.text or "", e.splash_setter("text", lambda v: v or None),
                                          placeholder=tr("Loading…"), width=240, theme=t), theme=t),
            ui.field(tr("Early splash"), ui.switch(s.native, e.splash_setter("native"), theme=t),
                     description=tr("Also the backend's own splash while the app unpacks: PyInstaller on Windows "
                                    "and Linux, Nuitka for a single file on Windows"), theme=t),
        ]
        if path is not None and path.is_file():
            preview = _core.container(_core.image(str(path), width="fill", height=180, content_fit="contain"),
                                      padding=8, bg=t.surface, radius=t.radius, border_color=t.border_variant,
                                      border_width=1, width="fill")
    return [ui.settings_group(tr("Splash screen"), rows, theme=t), preview]


def _list(e: ExportController, attr: str, title: str, description: str, placeholder: str, t: Theme) -> Any:
    assert e.opts is not None
    items = getattr(e.opts, attr)
    rows = [_core.row([
        _core.container(ui.label(item, mono=True, size="sm", theme=t), width="fill"),
        ui.icon_button("x", lambda i=item: e.remove_item(attr, i), size="xs", tooltip=tr("Remove"), theme=t),
    ], spacing=6, align="center") for item in items]
    rows.append(_core.row([
        ui.input(e.adding.get(attr, ""), lambda v: e.adding.__setitem__(attr, v), placeholder=placeholder,
                 on_submit=lambda: e.add_item(attr), size="sm", mono=True, theme=t),
        ui.button(tr("Add"), lambda: e.add_item(attr), icon="plus", variant="ghost", size="sm", theme=t),
    ], spacing=6, align="center"))
    return ui.settings_group(title, [_core.column(rows, spacing=4, width="fill")], description=description, theme=t)


def files(e: ExportController, t: Theme) -> List[Any]:
    return [
        _list(e, "include", tr("Files and folders"), tr("Shipped with the app, at the same path from the project root"),
              "assets", t),
        _list(e, "hidden_imports", tr("Hidden imports"),
              tr("Modules loaded by name (importlib); the UI's imports are found by themselves"), "mypkg.plugins", t),
        _list(e, "collect", tr("Whole packages"), tr("Packages shipped with all their code, data and libraries"),
              "babel", t),
        _list(e, "exclude", tr("Leave out"), tr("Modules not to ship, to make the app smaller"), "numpy.tests", t),
    ]


def android(e: ExportController, t: Theme) -> List[Any]:
    from .. import android as _android

    assert e.opts is not None and e.project is not None
    project, table = e.project, e.android
    abis = table.get("abis", ["arm64-v8a"])
    labels = {"arm64-v8a": tr("Phones and tablets (arm64-v8a)"), "x86_64": tr("Emulators on a PC (x86_64)")}
    formats = {tr("APK, to install on a phone"): "apk", tr("AAB, for Google Play"): "aab"}
    keystore = table.get("keystore")
    missing = keystore is not None and not (project.root / keystore).is_file()
    sdk = _android.find_sdk()
    app = ui.settings_group(tr("The app"), [
        ui.field(tr("Package"), ui.input(table.get("package", ""), e.android_setter("package"),
                                         placeholder=_android.package_name(_build.app_identifier(project, e.opts)),
                                         width=300, mono=True, theme=t),
                 description=tr("The application id on Google Play; it cannot change after the first upload"),
                 theme=t),
        ui.field(tr("Processors"), _core.column([
            _core.row([ui.checkbox(abi in abis, lambda on, a=abi: e.toggle_abi(a, on), theme=t),
                       ui.label(labels[abi], theme=t)], spacing=8, align="center") for abi in _android.ABIS
        ], spacing=6), theme=t),
        ui.field(tr("Format"), ui.select(list(formats), next(k for k, v in formats.items()
                                                             if v == table.get("format", "apk")),
                                         lambda v: e.android_setter("format")(None if formats[v] == "apk" else "aab"),
                                         width=260, theme=t), theme=t),
        ui.field(tr("Version code"), ui.input(str(table.get("version-code", "")),
                                              e.android_setter("version-code", lambda v: int(v) if v.isdigit() else None),
                                              placeholder=str(_android.version_code(_build.app_version(project, e.opts))),
                                              width=140, mono=True, theme=t),
                 description=tr("A number that grows with each upload; empty: made from the version"), theme=t),
    ], theme=t)
    signing = ui.settings_group(tr("Signing"), [
        ui.field(tr("Keystore"), _core.row([
            ui.input(keystore or "", e.android_setter("keystore"), placeholder=tr("Debug key"), width=240, mono=True,
                     theme=t),
            ui.button(tr("Browse…"), e.pick_keystore, icon="folder-search", size="sm", theme=t),
        ], spacing=6, align="center"), error=tr("The file does not exist") if missing else None,
            description=tr("Empty: the debug key, enough to try the app. Google Play needs your own key"), theme=t),
        ui.field(tr("Key alias"), ui.input(table.get("key-alias", ""), e.android_setter("key-alias"),
                                           placeholder="upload", width=200, mono=True, theme=t), theme=t),
    ], theme=t)
    notes = [ui.callout(tr("The passwords stay out of the project"),
                        tr("Set PYZED_KEYSTORE_PASSWORD (and PYZED_KEY_PASSWORD if the key has its own) before "
                           "building. Make a key with: keytool -genkeypair -keystore release.jks -alias upload "
                           "-keyalg RSA -validity 10000"), tint="hint", theme=t)] if keystore else []
    if sdk is None:
        notes.append(ui.callout(tr("The Android SDK is missing"),
                                tr("Install Android Studio (or its command line tools) and set ANDROID_HOME; the "
                                   "build needs build-tools and a platform."), tint="warning", theme=t))
    build = ui.button(tr("Build for Android"), e.build_android, icon="smartphone", variant="solid",
                      disabled=e.running or sdk is None or bool(e.problems()), theme=t)
    return [app, signing, *notes, _core.row([_core.space(width="fill"), build])]


def command(e: ExportController, t: Theme) -> List[Any]:
    project, opts = e.project, e.opts
    assert project is not None and opts is not None
    toml = _build.toml_table(opts.to_table())
    return [
        ui.settings_group(tr("From a terminal"), [
            _core.column([
                ui.label(tr("The same build, from the project folder:"), size="sm", color="text_muted", theme=t),
                ui.label("uv run pyzed build", mono=True, theme=t),
            ], spacing=6, width="fill"),
        ], end=ui.button(tr("Copy backend command"), e.copy_command, icon="copy", variant="ghost", size="sm", theme=t),
            theme=t),
        ui.settings_group(tr("In pyproject.toml"), [
            ui.label(toml.rstrip(), mono=True, size="sm", theme=t),
        ], theme=t),
    ]


BUILDERS = {"general": general, "platforms": platforms, "backend": backend, "icon": icon, "splash": splash,
            "files": files, "android": android, "command": command}


def _status(e: ExportController, t: Theme) -> Any:
    if e.state is None:
        problems = e.problems()
        if problems:
            return ui.label(problems[0], size="sm", color="error", theme=t)
        return ui.label(tr("Builds {target} into dist/", target=tr(e.target.label)), size="sm",
                        color="text_muted", theme=t)
    if e.running:
        backend = _build.BACKEND_LABELS[e.opts.backend] if e.opts and e.plan is not None else "Android"
        what = {"preparing": tr("Preparing…"), "building": tr("Building with {backend}…", backend=backend),
                "finishing": tr("Finishing…")}[e.state or "preparing"]
        return _core.row([ui.spinner(size=14, theme=t),
                          ui.label(f"{what}  {round(time.monotonic() - e.started)} s", size="sm", theme=t)],
                         spacing=8, align="center")
    color = {"done": "success", "failed": "error"}.get(e.state or "", "text_muted")
    return ui.label(e.message, size="sm", color=color, theme=t)


def dialog(d: "Designer", t: Theme) -> Any:
    """The Export dialog: an index of sections on the left, the chosen one on the right."""
    e = d.exporter
    if e.opts is None or e.project is None:
        return None
    titles = _titles()
    current = e.section if e.section in BUILDERS else SECTIONS[0]
    index = _core.column([
        ui.list_item(title, lambda k=key: e.show(k), icon=icon_name, selected=key == current, inset=True, height=28,
                     theme=t)
        for key, (title, icon_name) in titles.items()
    ], spacing=2, width=200)
    content = _core.scrollable(_core.column([w for w in BUILDERS[current](e, t) if w is not None], spacing=14,
                                            padding=(0, 10, 0, 0)), height=520, scrollbar_width=4, width="fill")
    body = _core.row([index, _core.rule(vertical=True, thickness=1, color=t.border_variant), content], spacing=14,
                     height=520)
    if e.running:
        actions = [ui.button(tr("Cancel build"), e.cancel, icon="square", variant="ghost", theme=t)]
    else:
        actions = [
            ui.button(tr("Show in folder"), e.reveal, icon="folder-open", variant="ghost", theme=t)
            if e.state == "done" else None,
            ui.button(tr("Close"), e.close, variant="ghost", theme=t),
            ui.button(tr("Build for {target}", target=tr(e.target.label)), e.build, icon="package",
                      variant="solid", disabled=bool(e.problems()), theme=t),
        ]
    return ui.modal(body, title=tr("Export {name}", name=_build.app_name(e.project, e.opts)), icon="package",
                    on_close=e.close, width=860, footer=[
        _status(e, t), _core.space(width="fill"), *[a for a in actions if a is not None]], theme=t)
