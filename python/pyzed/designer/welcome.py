"""The welcome window of Pyzed Design (Help → Welcome): start or open a project, reopen a recent
one, or make one from an example of the gallery, each shown with a thumbnail, a title and a
description. It opens at startup until "Show at startup" is turned off.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional

from .. import __version__, _core, ui
from .. import project as _project
from ..icons import icon as _icon
from ..theme import Theme
from . import samples as _samples
from . import workspace as _workspace
from .locale import tr
from .samples import Sample

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: The gallery's first filter, before the categories of ``samples.CATEGORIES``.
ALL = "All"
#: Where examples are copied unless another folder is chosen.
DEFAULT_FOLDER = Path.home() / "Pyzed Projects"
COLUMNS = 3
THUMB_HEIGHT = 128


class Welcome:
    """The state of the welcome window and of the gallery's "Create from example" step."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.category = ALL
        self.query = ""
        self.sample: Optional[Sample] = None
        self.name = ""
        self.folder = str(DEFAULT_FOLDER)
        self.downloading = False
        self.browser = _workspace.FolderBrowser(Path.home())

    # -- opening --------------------------------------------------------------------------
    def open(self) -> None:
        """Shows the welcome window."""
        self.d.app_menu = None
        self.d.dialog = "welcome"

    def open_gallery(self) -> None:
        """Shows the welcome window with every example (Help → Example projects)."""
        self.category, self.query = ALL, ""
        self.open()

    def toggle_startup(self, *_: Any) -> None:
        """Turns the welcome window at startup on or off (saved in the preferences)."""
        self.d.toggle_pref("show_welcome")

    def set_category(self, label: str) -> None:
        self.category = next((c for c in (ALL, *_samples.CATEGORIES) if tr(c) == label), ALL)

    def set_query(self, text: str) -> None:
        self.query = text

    def shown(self) -> List[Sample]:
        """The examples the filters let through."""
        q = self.query.strip().lower()
        return [s for s in _samples.CATALOG if (self.category == ALL or s.category == self.category)
                and (not q or q in f"{s.title} {s.description} {tr(s.title)} {tr(s.description)}".lower())]

    # -- from an example --------------------------------------------------------------------
    def pick(self, sample: Sample) -> None:
        """Goes to the step that names the new project made from ``sample`` and where it goes."""
        self.sample = sample
        base = Path(self.folder or DEFAULT_FOLDER).expanduser()
        name, n = _samples.slug(sample.title), 1
        while (base / name).exists():
            n += 1
            name = f"{_samples.slug(sample.title)}-{n}"
        self.name = name
        self.d.dialog = "welcome:create"

    def back(self) -> None:
        self.d.dialog = "welcome:create" if self.d.dialog == "welcome:browse" else "welcome"

    def set_name(self, text: str) -> None:
        self.name = text

    def set_folder(self, text: str) -> None:
        self.folder = text

    def browse(self) -> None:
        self.browser.go(self.folder or DEFAULT_FOLDER)
        self.d.dialog = "welcome:browse"

    def choose_location(self) -> None:
        self.folder = str(self.browser.path)
        self.d.dialog = "welcome:create"

    @property
    def target(self) -> Path:
        return Path(self.folder.strip() or DEFAULT_FOLDER).expanduser() / (self.name.strip() or "…")

    def create(self) -> Any:
        """Copies the example into a new project and opens it (its script or main form in front), which installs
        its packages with ``uv sync`` in the background; returns the commands."""
        sample, name = self.sample, self.name.strip()
        if sample is None or not name:
            return None
        try:
            folder = _samples.create(sample, self.target, name)
        except (OSError, ValueError) as err:
            self.d.notify(tr("Could not create the project"), str(err), kind="error", seconds=5)
            return None
        self.d.dialog = None
        commands = list(self.d.projects.open(str(folder)) or [])  # it also installs the packages (uv sync)
        project = self.d.projects.project
        if project is not None and project.root.resolve() == folder.resolve():
            front = project.script if project.script is not None else folder / "README.md"
            if front.is_file() and front.suffix != ".pzform" and not project.main_form.exists():
                commands.append(self.d.projects.files.edit(front.relative_to(project.root).as_posix()))
        return [c for c in commands if c is not None]

    def download(self) -> Any:
        """Downloads the examples of this version (a designer installed with pip has none); returns the task."""
        if self.downloading:
            return None
        self.downloading = True

        def work() -> Any:
            try:
                return _samples.download()
            except OSError as err:
                return err

        def done(result: Any) -> None:
            self.downloading = False
            if isinstance(result, Exception):
                self.d.notify(tr("Could not download the examples"), str(result), kind="error", seconds=6)

        return self.d.projects._task(tr("Downloading the examples"), work, done)


# -- views -------------------------------------------------------------------------------------


def _heading(text: str, t: Theme) -> Any:
    return ui.label(tr(text).upper(), size="xs", weight="semibold", color="text_muted", theme=t)


def _thumbnail(sample: Sample, root: Optional[Path], t: Theme, height: float = THUMB_HEIGHT) -> Any:
    path = root / sample.thumbnail if root is not None else None
    if path is not None and path.is_file():
        return _core.image(str(path), width="fill", height=height, content_fit="cover", radius=t.radius)
    return _core.container(_icon("image", size=24, color=t.icon_muted), width="fill", height=height,
                           center=True, bg=t.element, radius=t.radius)


def _card(w: Welcome, sample: Sample, root: Optional[Path], t: Theme) -> Any:
    return _core.button(
        _core.column([
            _thumbnail(sample, root, t),
            ui.label(tr(sample.title), weight="semibold", size="sm", wrap=False, theme=t),
            ui.label(tr(sample.description), size="xs", color="text_muted", theme=t),
        ], spacing=6, width="fill"),
        lambda: w.pick(sample), padding=8, width="fill", height=214, bg=t.surface, hover_bg=t.element_hover,
        border_color=t.border_variant, border_width=1, radius=t.radius + 2)


def _start(d: "Designer", t: Theme) -> Any:
    p = d.projects
    items: List[Any] = [
        _core.row([_icon("layout-template", size=22, color=t.accent),
                   _core.column([ui.label("Pyzed Design", weight="semibold", theme=t),
                                 ui.label(tr("Version {version}", version=__version__), size="xs",
                                          color="text_muted", theme=t)])], spacing=10, align="center"),
        _core.space(height=8),
        _heading("Start", t),
        ui.list_item(tr("New project…"), p.show("new"), icon="folder-plus", height=28, theme=t),
        ui.list_item(tr("Open project…"), p.show("open"), icon="folder-open", height=28, theme=t),
        ui.list_item(tr("New form…"), lambda: d.run_action("new"), icon="file-plus", height=28, theme=t),
        ui.list_item(tr("Documentation"), d.open_docs, icon="globe", height=28, theme=t),
    ]
    recent = _project.recent_projects(6)
    if recent:
        items += [_core.space(height=8), _heading("Recent", t)]
        items += [ui.tooltip(ui.list_item(r.name, lambda r=r: p.open(str(r)), icon="folder-git-2", height=28,
                                          theme=t), str(r), theme=t) for r in recent]
    return _core.container(_core.column(items, spacing=2, width="fill"), width=220)


def _gallery(w: Welcome, t: Theme) -> Any:
    root = _samples.examples_root()
    tabs = ui.segmented([tr(c) for c in (ALL, *_samples.CATEGORIES)], tr(w.category), w.set_category, theme=t)
    search = ui.input(w.query, w.set_query, placeholder=tr("Search examples…"), icon="search", size="sm",
                      width=200, theme=t)
    head = _core.row([_heading("Example projects", t), _core.space(width="fill"), search], align="center")
    if root is None:
        body: Any = ui.empty_state(
            tr("The examples are not on this computer"),
            tr("Download them once from the release of this version (about 1.5 MB)."), icon="download", theme=t,
            actions=[ui.button(tr("Downloading…") if w.downloading else tr("Download examples"), w.download,
                               icon="download", variant="solid", size="sm", disabled=w.downloading, theme=t)])
    else:
        cards = [_card(w, s, root, t) for s in w.shown()]
        body = _core.grid(cards, columns=COLUMNS, spacing=10) if cards else \
            ui.empty_state(tr("No examples match"), icon="search", theme=t)
    return _core.column([head, tabs, _core.container(_core.scrollable(_core.container(body, padding=(0, 10, 0, 0),
                                                                                      width="fill")),
                                                     width="fill", height=470)], spacing=10, width="fill")


def _labelled(title: str, control: Any, t: Theme) -> Any:
    return _core.column([ui.label(title, size="sm", weight="medium", theme=t), control], spacing=4, width="fill")


def _create(w: Welcome, t: Theme) -> Any:
    sample = w.sample
    assert sample is not None
    root = _samples.examples_root()
    needs = ["pyzed-ui", *sample.dependencies]
    info = _core.column([
        _thumbnail(sample, root, t, height=200),
        ui.label(tr(sample.title), weight="semibold", theme=t),
        ui.label(tr(sample.description), size="sm", color="text_muted", theme=t),
        _core.row([ui.badge(tr(sample.category), tint="accent", theme=t),
                   *[ui.badge(n, tint="info", theme=t) for n in needs]], spacing=4, wrap=True),
    ], spacing=8, width=320)
    form = _core.column([
        _labelled(tr("Name"), ui.input(w.name, w.set_name, on_submit=w.create, theme=t), t),
        _labelled(tr("Location"), _core.row([
            ui.input(w.folder, w.set_folder, on_submit=w.create, mono=True, theme=t),
            ui.button(tr("Browse…"), w.browse, icon="folder-search", size="sm", theme=t),
        ], spacing=6, align="center"), t),
        ui.label(tr("Creates {target}", target=w.target), size="xs", mono=True, color="text_muted", theme=t),
        ui.label(tr("The project is a copy you can change freely. Its packages are installed with uv sync, "
                    "and Run (F5) starts it."), size="xs", color="text_muted", theme=t),
    ], spacing=12, width="fill")
    return ui.modal(_core.row([info, form], spacing=20), title=tr("Create from example"), on_close=w.d.close_dialog,
                    width=820, theme=t, footer=[
                        ui.button(tr("Back"), w.back, variant="ghost", theme=t),
                        ui.button(tr("Create project"), w.create, icon="folder-plus", variant="solid", theme=t)])


def dialog(d: "Designer", t: Theme) -> Any:
    """The ``welcome`` dialogs: the welcome window, and naming (and placing) a project made from an example."""
    w = d.welcome
    if d.dialog == "welcome:create" and w.sample is not None:
        return _create(w, t)
    if d.dialog == "welcome:browse":
        return ui.modal(_workspace.browser_view(w.browser, t), title=tr("Choose where to create the project"),
                        on_close=w.back, width=760, theme=t, footer=[
            ui.label(str(w.browser.path / (w.name or "…")), size="sm", mono=True, color="text_muted", theme=t),
            _core.space(width="fill"),
            ui.button(tr("Back"), w.back, variant="ghost", theme=t),
            ui.button(tr("Choose this folder"), w.choose_location, icon="check", variant="solid", theme=t)])
    body = _core.row([_start(d, t), _core.container(_core.rule(thickness=1, color=t.border_variant, vertical=True),
                                                    height=520), _gallery(w, t)], spacing=16)
    bottom = _core.row([ui.checkbox(d.prefs.show_welcome, w.toggle_startup, label=tr("Show at startup"), theme=t),
                        _core.space(width="fill"), ui.button(tr("Close"), d.close_dialog, theme=t)], align="center")
    return ui.modal(_core.column([body, bottom], spacing=14), title=tr("Welcome to Pyzed Design"),
                    on_close=d.close_dialog, width=1060, theme=t)
