"""The Settings dialog: every preference of the designer and its code editor in one place, like Zed's.

Each preference is a ``Setting`` of ``SETTINGS`` (its page, title, help and control), so the dialog builds the
rows, the search and the Reset buttons from one table. At the top, the scope says where a change goes: the
user's settings (in the active profile) or this project's own (``.pyzed/settings.json``, see ``profiles``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from .. import _core, ui
from .. import rendering as _rendering
from ..icons import icon as _icon
from ..theme import Theme, themes
from . import profiles as _profiles
from . import settings as _settings
from .locale import tr

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

SEARCH_ID = "designer-settings-search"
NAME_ID = "designer-settings-profile-name"

Options = Union[Sequence[Tuple[Any, str]], Callable[[], Sequence[Tuple[Any, str]]]]


@dataclass(frozen=True)
class Setting:
    """One preference: ``section`` ("designer" or "editor") and ``key`` name its field, ``page`` where it shows.

    ``kind`` is the control: "switch", "select", "segmented", "number" (``low``, ``high``, ``step``), "font"
    (``default`` names the default font) or "theme" (the rack of every theme, under the title). ``options`` lists
    ``(value, label)`` pairs, or returns them.
    ``project`` says whether a project can set its own value.
    """

    section: str
    key: str
    page: str
    title: str
    description: str = ""
    kind: str = "switch"
    options: Options = ()
    low: float = 0
    high: float = 100
    step: float = 1
    default: str = ""
    project: bool = True

    def choices(self) -> List[Tuple[Any, str]]:
        """The ``(value, label)`` pairs, labels translated."""
        options = self.options() if callable(self.options) else self.options
        return [(value, tr(label)) for value, label in options]


def _themes() -> List[Tuple[str, str]]:
    return [(name, name) for name in themes.names()]


def _editor_themes() -> List[Tuple[str, str]]:
    return [("", "Same as the designer"), *_themes()]


def _languages() -> List[Tuple[str, str]]:
    from .dialogs import LANGUAGES

    return list(LANGUAGES)


def _scales() -> List[Tuple[float, str]]:
    from .dialogs import UI_SCALES

    return [(v, f"{round(v * 100)}%") for v in UI_SCALES]


def _frames() -> List[Tuple[str, str]]:
    labels = ui.frame.PLATFORM_LABELS
    return [("", tr("This system ({name})", name=labels[ui.system_platform()])), *labels.items()]


_LINE_HEIGHTS = tuple((name, name.capitalize()) for name in _settings.LINE_HEIGHTS)
_CURSORS = tuple((shape, shape.capitalize()) for shape in _settings.CURSOR_SHAPES)
_EYES = (("visible", "Hidden when running"), ("editor", "Hidden in the editor only"))
_CHANNELS = (("stable", "Stable"), ("preview", "Preview"))
_RENDERERS = (("auto", "Auto"), ("gpu", "GPU"), ("cpu", "CPU"))
_GPU_APIS = (("auto", "Auto"), ("vulkan", "Vulkan"), ("metal", "Metal"), ("dx12", "DirectX 12"), ("gl", "OpenGL"))
_POWER = (("auto", "Auto"), ("high", "Fast"), ("low", "Saves battery"))
#: The designer's own renderer: read when it starts, so a change asks for a restart.
RESTART_KEYS = frozenset({"renderer", "gpu_api", "gpu_power"})

#: Every preference the dialog shows, page by page.
SETTINGS: Tuple[Setting, ...] = (
    # general
    Setting("designer", "theme", "general", "Theme", kind="theme", options=_themes),
    Setting("designer", "language", "general", "Language", "Language of the designer's menus and panels",
            kind="select", options=_languages),
    Setting("designer", "show_toolbar", "general", "Toolbar"),
    Setting("designer", "show_status_bar", "general", "Status bar"),
    Setting("designer", "show_welcome", "general", "Welcome window",
            "Opens at startup with the example projects (also in Help → Welcome)", project=False),
    Setting("designer", "window_frame", "general", "Custom window frame",
            "Pyzed's own title bar and window buttons; off uses the system's frame (applies on restart)",
            project=False),
    Setting("designer", "preview_frame", "general", "Form preview frame",
            "The window frame the canvas shows around the form", kind="select", options=_frames),
    Setting("designer", "check_updates", "general", "Check for updates", "Once a day, in the background",
            project=False),
    Setting("designer", "update_channel", "general", "Update channel",
            "Preview also offers pre-releases, like Zed Preview", kind="segmented", options=_CHANNELS, project=False),
    # fonts and size
    Setting("designer", "ui_font", "fonts", "Interface font", "Menus, panels, dialogs and the properties",
            kind="font", default="IBM Plex Sans"),
    Setting("designer", "ui_scale", "fonts", "Interface size",
            "Zooms every window, like View → Zoom in and Zoom out", kind="select", options=_scales),
    Setting("editor", "font_family", "fonts", "Code font", "The code editor, the console and other code",
            kind="font", default="IBM Plex Mono"),
    Setting("editor", "font_size", "fonts", "Code font size", "Ctrl+= and Ctrl+- (or Ctrl+wheel); Ctrl+0 resets",
            kind="number", low=8, high=32),
    Setting("editor", "line_height", "fonts", "Code line height", kind="segmented", options=_LINE_HEIGHTS),
    # form canvas
    Setting("designer", "show_grid", "canvas", "Show grid"),
    Setting("designer", "snap", "canvas", "Snap to grid"),
    Setting("designer", "smart_guides", "canvas", "Smart guides", "Align to other controls while dragging"),
    Setting("designer", "show_all_hidden", "canvas", "Show all hidden controls",
            "Off: a hidden dialog or drawer shows only while it is selected"),
    Setting("designer", "outline_eye", "canvas", "Outline eye",
            "Hidden when running: also off the canvas, shown while selected. "
            "Editor only: hides it on the canvas, the running form still shows it", kind="select", options=_EYES),
    Setting("designer", "grid", "canvas", "Grid size for new forms", kind="number", low=2, high=64),
    # running
    Setting("designer", "save_on_run", "running", "Save before running"),
    Setting("designer", "console_on_run", "running", "Open the console on Run"),
    Setting("designer", "log_events", "running", "Log events in the console",
            "Every event the running form handles, with its value"),
    Setting("designer", "restricted_mode", "running", "Restricted mode",
            "Asks before installing the packages of a project you did not create, importing its components or "
            "running it", project=False),
    # logs
    Setting("designer", "error_dialogs", "logs", "Show a dialog on errors",
            "With buttons to copy the error and go to its line; errors are always in View → Logs"),
    Setting("designer", "log_file", "logs", "Write a log file",
            "pyzed-design.log in the Pyzed config folder, for bug reports (applies on restart)", project=False),
    # the designer's own rendering
    Setting("designer", "renderer", "rendering", "Renderer",
            "How Pyzed Design draws its windows. Auto: the GPU when there is a real one, else the CPU. CPU works "
            "without a GPU but shader previews need the GPU (applies on restart)", kind="segmented",
            options=_RENDERERS, project=False),
    Setting("designer", "gpu_api", "rendering", "Graphics API",
            "Auto tries Vulkan, Metal or DirectX 12, then OpenGL (applies on restart)", kind="select",
            options=_GPU_APIS, project=False),
    Setting("designer", "gpu_power", "rendering", "GPU",
            "On laptops with two: the dedicated GPU or the integrated one (applies on restart)", kind="segmented",
            options=_POWER, project=False),
    # code editor
    Setting("editor", "theme", "editor.appearance", "Editor theme", kind="select", options=_editor_themes),
    Setting("editor", "font_family", "editor.appearance", "Font", kind="font", default="IBM Plex Mono"),
    Setting("editor", "font_size", "editor.appearance", "Font size",
            "Ctrl+= and Ctrl+- (or Ctrl+wheel); Ctrl+0 resets", kind="number", low=8, high=32),
    Setting("editor", "line_height", "editor.appearance", "Line height", kind="segmented", options=_LINE_HEIGHTS),
    Setting("editor", "line_numbers", "editor.appearance", "Line numbers"),
    Setting("editor", "highlight_line", "editor.appearance", "Highlight current line"),
    Setting("editor", "show_whitespace", "editor.appearance", "Show whitespace", "Spaces as · and tabs as →"),
    Setting("editor", "cursor_shape", "editor.cursor", "Shape", kind="segmented", options=_CURSORS),
    Setting("editor", "cursor_blink", "editor.cursor", "Blink"),
    Setting("editor", "cursor_width", "editor.cursor", "Width", "Of the bar cursor, in pixels", kind="number",
            low=1, high=4),
    Setting("editor", "tab_size", "editor.editing", "Tab size",
            "Columns of a level of indentation and of a tab; Enter keeps the indentation", kind="number", low=1,
            high=8),
    Setting("editor", "hard_tabs", "editor.editing", "Indent with tabs",
            "Tab, Enter and Ctrl+] indent with tab characters instead of spaces"),
    Setting("editor", "convert_indentation", "editor.editing", "Convert indentation on save",
            "Saving a Python file rewrites its indentation as set above, so they never mix"),
    Setting("editor", "backspace_unindent", "editor.editing", "Backspace removes a whole level",
            "In the indentation; off: one space at a time"),
    Setting("editor", "autocomplete", "editor.editing", "Autocomplete while typing", "Ctrl+Space opens it anytime"),
    Setting("editor", "auto_close", "editor.editing", "Auto-close brackets and quotes",
            "Also wraps the selection and steps over the closing one"),
    Setting("editor", "folding", "editor.editing", "Code folding", "Chevrons in the gutter; Ctrl+Shift+[ and ]"),
    Setting("editor", "match_brackets", "editor.editing", "Match brackets",
            "Outline the bracket that pairs with the one at the cursor; Ctrl+M jumps to it"),
    Setting("editor", "selection_highlight", "editor.editing", "Highlight selection matches",
            "Ctrl+D adds the next one as a cursor, Ctrl+Shift+L all of them"),
    Setting("editor", "format_on_apply", "editor.editing", "Format with ruff on Apply"),
    Setting("editor", "repeat_delay", "editor.deleting", "Delay before repeating",
            "Milliseconds Backspace and Delete wait before repeating (0: the system's)", kind="number", low=0,
            high=_settings.MAX_REPEAT_DELAY, step=50),
    Setting("editor", "repeat_rate", "editor.deleting", "Deletions per second",
            "At most, while held down (0: the system's pace, the fastest)", kind="number", low=0,
            high=_settings.MAX_REPEAT_RATE),
    Setting("editor", "wrap", "editor.scrolling", "Wrap long lines",
            "Off: long lines scroll sideways (Shift+wheel). Alt+Z toggles it"),
    Setting("editor", "scrollbar", "editor.scrolling", "Scrollbars"),
    Setting("editor", "minimap", "editor.scrolling", "Minimap", "Click or drag it to scroll"),
    Setting("editor", "sticky_scroll", "editor.scrolling", "Sticky scroll",
            "Keeps the class and def you are scrolling through at the top; click one to go there"),
    Setting("editor", "code_lens", "editor.diagnostics", "Code lens", "References, implementations and wired events"),
    Setting("editor", "inline_diagnostics", "editor.diagnostics", "Inline diagnostics",
            "Problems at the end of the line"),
    Setting("editor", "hover", "editor.diagnostics", "Information on hover",
            "Resting the mouse on a name shows what it is, its documentation and its problems"),
    Setting("editor", "ty", "editor.servers", "ty", "Types, completion and references"),
    Setting("editor", "ruff", "editor.servers", "ruff", "Linting"),
)

#: The pages of the dialog: ``(key, title, icon)`` by group, in the order of the index.
PAGES: Tuple[Tuple[str, Tuple[Tuple[str, str, str], ...]], ...] = (
    ("Designer", (
        ("general", "General", "settings"),
        ("fonts", "Fonts and size", "type"),
        ("canvas", "Form canvas", "layout-grid"),
        ("running", "Running", "play"),
        ("logs", "Logs and errors", "scroll-text"),
        ("rendering", "Rendering", "monitor-cog"),
        ("telemetry", "Telemetry", "chart-no-axes-column"),
    )),
    ("Code editor", (
        ("editor.appearance", "Appearance", "palette"),
        ("editor.cursor", "Cursor", "text-cursor"),
        ("editor.editing", "Editing", "pencil"),
        ("editor.deleting", "Deleting", "delete"),
        ("editor.scrolling", "Scrolling and wrapping", "wrap-text"),
        ("editor.diagnostics", "Code lens and diagnostics", "circle-alert"),
        ("editor.servers", "Language servers", "server"),
    )),
    ("Project", (
        ("project.rendering", "App rendering", "app-window"),
    )),
)


def page_titles() -> Dict[str, Tuple[str, str]]:
    """``{page: (title, icon)}`` of every page."""
    return {key: (title, icon) for _, pages in PAGES for key, title, icon in pages}


def matches(setting: Setting, query: str) -> bool:
    """Whether ``query`` is in the setting's title, help or name (in English or translated)."""
    words = query.casefold().split()
    text = " ".join((setting.title, tr(setting.title), setting.description, tr(setting.description) if
                     setting.description else "", setting.key.replace("_", " "))).casefold()
    return all(word in text for word in words)


def search(query: str) -> List[Setting]:
    """The settings ``query`` finds, each preference once."""
    seen, out = set(), []
    for s in SETTINGS:
        if (s.section, s.key) not in seen and matches(s, query):
            seen.add((s.section, s.key))
            out.append(s)
    return out


# -- the controller -----------------------------------------------------------------------------------------

class SettingsController:
    """The dialog's state: the page, the search, the scope and the profile being named."""

    def __init__(self, designer: "Designer") -> None:
        self.d = designer
        self.page = "general"
        self.query = ""
        #: Where changes go: "user" (the active profile) or "project" (``.pyzed/settings.json``).
        self.scope = "user"
        #: "new" or "rename" while the profile name field shows, with its text.
        self.naming: Optional[str] = None
        self.name = ""
        #: The moment Reset all was pressed once; a second press within a few seconds resets.
        self.reset_armed = 0.0
        self._rendering: Optional[Tuple[Path, float, _rendering.Rendering]] = None
        #: The GPU name being typed in the rendering page (saved with Enter).
        self.gpu_draft: Optional[str] = None

    @property
    def store(self) -> _profiles.Store:
        return self.d.profile_store

    @property
    def project_root(self) -> Optional[Path]:
        project = self.d.projects.project
        return project.root if project is not None else None

    def open(self, page: Optional[str] = None) -> None:
        if page:
            self.page = page
        self.naming = None
        self.reset_armed = 0.0
        if self.scope == "project" and self.project_root is None:
            self.scope = "user"

    def show(self, page: str) -> None:
        self.page = page
        self.query = ""

    def set_query(self, text: str) -> None:
        self.query = text

    def set_scope(self, scope: str) -> None:
        self.scope = scope if scope == "user" or self.project_root is not None else "user"
        self.reset_armed = 0.0

    # -- values ---------------------------------------------------------------------------------
    def value(self, s: Setting) -> Any:
        return self.store.value(s.section, s.key, "user" if self.scope == "user" else "effective")

    def change(self, s: Setting, value: Any) -> None:
        scope = self.scope if s.project else "user"
        self.d.change_setting(s.section, s.key, value, scope)

    def reset(self, s: Setting) -> None:
        self.d.reset_setting(s.section, s.key, self.scope if s.project else "user")

    def reset_all(self) -> None:
        """Arms Reset all; the second press within five seconds puts every setting of the scope back."""
        now = time.monotonic()
        if now - self.reset_armed > 5:
            self.reset_armed = now
            return
        self.reset_armed = 0.0
        self.d.reset_all_settings(self.scope)

    # -- profiles -------------------------------------------------------------------------------
    def start_naming(self, mode: str) -> Any:
        self.naming = mode
        self.name = self.store.active if mode == "rename" else ""
        return _core.Command.focus(NAME_ID)

    def set_name(self, text: str) -> None:
        self.name = text

    def finish_naming(self) -> None:
        mode, self.naming = self.naming, None
        name = self.name.strip()
        if not name:
            return
        if mode == "new":
            self.d.create_profile(name)
        elif mode == "rename" and not self.store.rename(self.store.active, name):
            self.d.notify(tr("Could not rename the profile"), tr("That name is taken"), kind="error", seconds=4)

    def cancel_naming(self) -> None:
        self.naming = None

    # -- rendering ------------------------------------------------------------------------------
    def rendering(self) -> Optional[_rendering.Rendering]:
        """The project's ``[tool.pyzed.rendering]``, read again only when ``pyproject.toml`` changes."""
        root = self.project_root
        if root is None:
            return None
        file = root / "pyproject.toml"
        try:
            stamp = file.stat().st_mtime
        except OSError:
            return None
        if self._rendering is None or self._rendering[:2] != (root, stamp):
            self._rendering = (root, stamp, _rendering.find(root))
        return self._rendering[2]

    def edit_gpu(self, value: str) -> None:
        self.gpu_draft = value

    def save_gpu(self, *_: Any) -> None:
        if self.gpu_draft is not None:
            self.set_rendering("gpu", self.gpu_draft.strip())
        self.gpu_draft = None

    def set_rendering(self, key: str, value: Any) -> None:
        current = self.rendering()
        root = self.project_root
        if current is None or root is None:
            return
        values = current.to_table()
        values[key] = value
        try:
            _rendering.save(root, _rendering.Rendering.from_table(values))
        except OSError as err:
            self.d.notify(tr("Could not save the rendering settings"), str(err), kind="error", seconds=5)
            return
        self._rendering = None
        project = self.d.projects.project
        if project is not None:
            project.reload()


# -- the view -----------------------------------------------------------------------------------------------

def _control(c: SettingsController, s: Setting, t: Theme) -> Any:
    value = c.value(s)

    def change(v: Any) -> None:
        c.change(s, v)

    if s.kind == "switch":
        return ui.switch(bool(value), change, theme=t)
    if s.kind == "number":
        integer = isinstance(_profiles.defaults(s.section)[s.key], int)
        return ui.number_field(float(value), (lambda v: change(int(v))) if integer else change, min=s.low,
                               max=s.high, step=s.step, width=110, theme=t)
    if s.kind == "font":
        from .dialogs import font_select

        return font_select(str(value), s.default, change, t)
    choices = s.choices()
    labels = [label for _, label in choices]
    current = next((label for v, label in choices if v == value), None)
    if current is None:  # a value outside the list (a scale set by zooming...)
        current = f"{round(value * 100)}%" if s.key == "ui_scale" else str(value)
        labels.append(current)
        choices.append((value, current))

    def pick(label: str) -> None:
        change(next(v for v, name in choices if name == label))

    if s.kind == "segmented":
        return ui.segmented(labels, current, pick, theme=t)
    return ui.select(labels, current, pick, width=220, theme=t)


def row(c: SettingsController, s: Setting, t: Theme) -> Any:
    """A setting's row: its title and help, a dot when it is changed, its control and a Reset button."""
    store, scope = c.store, (c.scope if s.project else "user")
    modified = store.modified(s.section, s.key, scope)
    note = None
    if c.scope == "user" and store.overridden(s.section, s.key):
        note = ui.badge(tr("This project sets its own"), tint="warning", size="sm", theme=t)
    elif c.scope == "project" and not s.project:
        note = ui.badge(tr("User only"), size="sm", tint="text_muted", theme=t)
    heading = _core.row([
        ui.label(tr(s.title), theme=t),
        _core.container(width=6, height=6, radius=3, bg=t.accent) if modified else None,
        note,
    ], spacing=6, align="center")
    reset_tip = tr("Use the user's value") if scope == "project" else tr("Reset to default")
    reset = ui.icon_button("rotate-ccw", lambda: c.reset(s), size="sm", tooltip=reset_tip, theme=t) if modified \
        else _core.space(width=24)
    if s.kind == "theme":  # the rack of themes, under its title
        value = c.value(s) or t.name
        return _core.column([
            _core.row([_core.column([heading], width="fill"), reset], spacing=12, align="center"),
            ui.theme_rack(themes.all(), value, lambda name: c.change(s, name), theme=t),
        ], spacing=8)
    return _core.row([
        _core.column([heading, ui.label(tr(s.description), size="sm", color="text_muted", theme=t)
                      if s.description else None], spacing=2, width="fill"),
        _control(c, s, t),
        reset,
    ], spacing=12, align="center")


def _group(c: SettingsController, title: str, settings: Sequence[Setting], t: Theme) -> Any:
    return ui.settings_group(title, [row(c, s, t) for s in settings], theme=t)


def _servers(c: SettingsController, t: Theme) -> List[Any]:
    a = c.d.assist
    rows = []
    for name, status, detail in a.intel.statuses():
        from .code_panel import STATUS_COLORS

        rows.append(_core.row([
            _core.container(width=10, height=10, radius=5, bg=t.color(STATUS_COLORS.get(status, "text_muted"))),
            ui.label(f"{name}  ·  {status}", size="sm", theme=t),
            ui.label(detail, size="sm", color="text_muted", theme=t) if detail else None,
        ], spacing=8, align="center"))
    env = a.intel.env
    if env is not None:
        rows.append(ui.label(f"{tr('Project')}  {env.root}\nPython   {env.python}", size="sm", color="text_muted",
                             mono=True, theme=t))
    return [ui.settings_group(tr("Status"), rows, theme=t,
                              end=ui.button(tr("Restart servers"), a.restart_servers, icon="refresh-cw",
                                            variant="ghost", size="sm", theme=t))] if rows else []


def rendering_page(c: SettingsController, t: Theme) -> List[Any]:
    """The project's renderer: GPU or CPU, the graphics API, the GPU to use and vsync."""
    r = c.rendering()
    designer = ui.button(tr("Pyzed Design's renderer"), lambda: c.show("rendering"), icon="monitor-cog",
                         variant="ghost", size="sm", theme=t)
    if r is None:
        return [ui.callout(tr("Open a project"), tr("How the project's app draws is saved in its pyproject.toml: "
                                                   "open a project to change it. Pyzed Design's own renderer is "
                                                   "in Designer → Rendering."), tint="info", theme=t),
                _core.row([designer])]

    def seg(key: str, options: Sequence[Tuple[str, str]], disabled: bool = False) -> Any:
        labels = {tr(label): value for value, label in options}
        current = next(label for label, value in labels.items() if value == getattr(r, key))
        if disabled:
            return ui.label(tr("Not used by the CPU renderer"), size="sm", color="text_muted", theme=t)
        return ui.segmented(list(labels), current, lambda label: c.set_rendering(key, labels[label]), theme=t)

    apis = (("auto", "Auto"), ("vulkan", "Vulkan"), ("metal", "Metal"), ("dx12", "DirectX 12"), ("gl", "OpenGL"))
    cpu = r.renderer == "cpu"
    rows = [
        ui.field(tr("Renderer"), seg("renderer", (("auto", "Auto"), ("gpu", "GPU"), ("cpu", "CPU"))),
                 description=tr("Auto: the GPU when there is a real one, else the CPU (virtual machines, remote "
                                "desktops). GPU is needed by shaders; CPU starts faster and uses less memory"),
                 theme=t),
        ui.field(tr("Graphics API"), seg("gpu_api", apis, cpu) if cpu else ui.select(
            [tr(label) for _, label in apis], tr(dict(apis)[r.gpu_api]),
            lambda label: c.set_rendering("gpu_api", next(v for v, n in apis if tr(n) == label)), width=160, theme=t),
                 description=tr("Auto tries Vulkan, Metal or DirectX 12, then OpenGL"), theme=t),
        ui.field(tr("GPU"), seg("power", (("auto", "Auto"), ("high", "Fast"), ("low", "Saves battery")), cpu),
                 description=tr("On laptops with two: the dedicated GPU or the integrated one"), theme=t),
        ui.field(tr("GPU name"), ui.label(tr("Not used by the CPU renderer"), size="sm", color="text_muted",
                                          theme=t) if cpu else ui.input(
            c.gpu_draft if c.gpu_draft is not None else r.gpu, c.edit_gpu, placeholder=tr("Any"),
            on_submit=c.save_gpu, width=200, theme=t),
                 description=tr("Part of the name of the GPU to use (nvidia, intel, radeon); Enter saves it"),
                 theme=t),
        ui.field(tr("Vsync"), seg("vsync", (("auto", "Auto"), ("on", "On"), ("off", "Off")), cpu),
                 description=tr("On waits for the screen (no tearing); off draws as fast as it can"), theme=t),
        ui.field(tr("Present mode"), seg("present", (("auto", "Auto"), ("fifo", "Fifo"), ("fifo_relaxed", "Relaxed"),
                                                   ("mailbox", "Mailbox"), ("immediate", "Immediate")), cpu),
                 description=tr("Wins over vsync. Mailbox: low latency without tearing; Immediate: lowest latency, "
                                "may tear; Fifo: least power"), theme=t),
    ]
    fps = (("auto", "Screen"), ("30", "30"), ("60", "60"), ("90", "90"), ("120", "120"), ("144", "144"))
    background = (("auto", "Same"), ("pause", "Pause"), ("5", "5"), ("15", "15"), ("30", "30"))

    def fps_seg(key: str, options: Sequence[Tuple[str, str]], value: Optional[int]) -> Any:
        current = "auto" if value is None or (key == "max_fps" and value == 0) else (
            "pause" if value == 0 else str(value))
        if current not in dict(options):
            options = (*options, (current, current))
        labels = {tr(label): v for v, label in options}
        selected = next(label for label, v in labels.items() if v == current)
        return ui.segmented(list(labels), selected, lambda label: c.set_rendering(key, labels[label]), theme=t)

    quality = [
        ui.field(tr("Antialiasing"), seg("antialiasing", (("auto", "Auto"), ("off", "Off"), ("2x", "2x"),
                                                        ("4x", "4x"), ("8x", "8x"), ("16x", "16x")), cpu),
                 description=tr("Smooth edges of canvas drawings, charts and curves; Auto is 4x"), theme=t),
        ui.field(tr("Frame latency"), seg("frame_latency", (("auto", "Auto"), ("1", "1"), ("2", "2"), ("3", "3")), cpu),
                 description=tr("Frames the GPU may prepare ahead: 1 answers input soonest, 2 or 3 smooth heavy "
                                "scenes"), theme=t),
        ui.field(tr("GPU memory"), seg("memory", (("auto", "Auto"), ("low", "Low"), ("performance", "Performance")),
                                       cpu),
                 description=tr("Low frees memory soon; Performance keeps large blocks for fewer allocations"),
                 theme=t),
        ui.field(tr("Max frame rate"), fps_seg("max_fps", fps, r.max_fps),
                 description=tr("The most frames per second animations draw; input is always drawn at once"),
                 theme=t),
        ui.field(tr("Background frame rate"), fps_seg("background_fps", background, r.background_fps),
                 description=tr("For windows without the focus: Pause stops their animations until they get it "
                                "back"), theme=t),
    ]
    env = "  ".join(f"{k}={v}" for k, v in r.env().items()) or tr("Nothing: Pyzed decides")
    return [
        ui.settings_group(tr("App rendering"), rows, theme=t, end=designer,
                          description=tr("Saved in pyproject.toml ([tool.pyzed.rendering]): used by Run, pz.run and "
                                         "the exported app, not by Pyzed Design itself")),
        ui.settings_group(tr("Quality and frame rate"), quality, theme=t,
                          description=tr("Lower them on touch panels, phones and laptops on battery")),
        ui.label(f"{tr('Environment')}: {env}", size="xs", mono=True, color="text_muted", theme=t),
    ]


def designer_rendering_page(c: SettingsController, t: Theme) -> List[Any]:
    """Pyzed Design's own renderer (its settings, read when it starts) and what draws its windows now."""
    from ..app import renderer_info

    settings = [s for s in SETTINGS if s.page == "rendering"]
    if c.value(settings[0]) == "cpu":
        settings = settings[:1]  # the GPU's settings mean nothing to the CPU renderer
    info = renderer_info()
    now = (f"{info[0]} · {info[1]}" if info else tr("Unknown"))
    wanted = c.d.prefs.rendering().env()
    pending = c.d.rendering_started is not None and wanted != c.d.rendering_started
    return [
        _group(c, tr("Rendering"), settings, t),
        ui.callout(tr("Restart Pyzed Design to apply the change"), tr("The renderer is chosen when Pyzed Design "
                                                                     "starts."), tint="warning", theme=t)
        if pending else None,
        ui.label(f"{tr('Drawing now with')}: {now}", size="sm", color="text_muted", theme=t),
        ui.label(tr("Each project's app has its own renderer: Project → App rendering"), size="sm",
                 color="text_muted", theme=t),
    ]


def page_content(c: SettingsController, page: str, t: Theme) -> List[Any]:
    """The groups of ``page``."""
    from .dialogs import telemetry_group

    if page == "project.rendering":
        return rendering_page(c, t)
    if page == "telemetry":
        return [telemetry_group(c.d, t)]
    if page == "rendering":
        return designer_rendering_page(c, t)
    title = tr(page_titles().get(page, (page, ""))[0])
    out: List[Any] = [_group(c, title, [s for s in SETTINGS if s.page == page], t)]
    if page == "editor.servers":
        out += _servers(c, t)
    return out


def search_content(c: SettingsController, t: Theme) -> List[Any]:
    found = search(c.query)
    if not found:
        return [ui.label(tr("No settings match “{query}”", query=c.query), color="text_muted", theme=t)]
    titles = page_titles()
    groups: Dict[str, List[Setting]] = {}
    for s in found:
        groups.setdefault(s.page, []).append(s)
    return [_group(c, tr(titles[page][0]), items, t) for page, items in groups.items()]


def _index(c: SettingsController, t: Theme) -> Any:
    items: List[Any] = []
    for group, pages in PAGES:
        items.append(_core.container(ui.label(tr(group).upper(), size="xs", mono=True, color="text_muted", theme=t),
                                     padding=(8, 8, 2, 8)))
        for key, title, icon in pages:
            count = sum(1 for s in SETTINGS if s.page == key and c.store.modified(
                s.section, s.key, c.scope if s.project else "user"))
            items.append(ui.list_item(tr(title), lambda k=key: c.show(k), icon=icon,
                                      selected=key == c.page and not c.query, inset=True, height=28,
                                      end=ui.label(str(count), size="xs", color="accent", theme=t) if count else None,
                                      theme=t))
    d = c.d
    items += [
        _core.container(ui.label(tr("More").upper(), size="xs", mono=True, color="text_muted", theme=t),
                        padding=(8, 8, 2, 8)),
        ui.list_item(tr("Key bindings"), d.open_keymap, icon="keyboard", inset=True, height=28,
                     end=_icon("arrow-up-right", size=12, color=t.icon_muted), theme=t),
        ui.list_item(tr("AI agents"), d.agent.open_settings, icon="sparkles", inset=True, height=28,
                     end=_icon("arrow-up-right", size=12, color=t.icon_muted), theme=t),
        ui.list_item(tr("Reset panel layout"), d.reset_layout, icon="layout-dashboard", inset=True, height=28,
                     theme=t),
    ]
    return _core.scrollable(_core.column(items, spacing=1, width=210), height=500, scrollbar_width=4)


def _top(c: SettingsController, t: Theme) -> Any:
    """The search field, the scope and the profile."""
    store = c.store
    parts: List[Any] = [ui.search_input(c.query, c.set_query, placeholder=tr("Search settings…"), id=SEARCH_ID,
                                        size="sm", width=240, theme=t)]
    if c.project_root is not None:
        scopes = {tr("User"): "user", tr("Project"): "project"}
        parts.append(ui.segmented(list(scopes), next(k for k, v in scopes.items() if v == c.scope),
                                  lambda name: c.set_scope(scopes[name]), size="sm", theme=t))
    parts.append(_core.space(width="fill"))
    if c.scope == "project":
        parts.append(ui.label(tr("Saved in {file}", file=_profiles.PROJECT_FILE.as_posix()), size="sm",
                              color="text_muted", theme=t))
    elif c.naming is not None:
        parts += [
            ui.input(c.name, c.set_name, placeholder=tr("Profile name"), id=NAME_ID, size="sm", width=170,
                     on_submit=c.finish_naming, theme=t),
            ui.icon_button("check", c.finish_naming, size="sm", tooltip=tr("Save"), theme=t),
            ui.icon_button("x", c.cancel_naming, size="sm", tooltip=tr("Cancel"), theme=t),
        ]
    else:
        names = store.profile_names()
        shown = {(tr(n) if n == _profiles.DEFAULT_PROFILE else n): n for n in names}
        current = next(k for k, v in shown.items() if v == store.active)
        default = store.active == _profiles.DEFAULT_PROFILE
        parts += [
            ui.label(tr("Profile"), size="sm", color="text_muted", theme=t),
            ui.select(list(shown), current, lambda name: c.d.switch_profile(shown[name]), size="sm", width=160,
                      theme=t),
            ui.icon_button("plus", lambda: c.start_naming("new"), size="sm",
                           tooltip=tr("New profile (a copy of this one)"), theme=t),
            ui.icon_button("pencil", lambda: c.start_naming("rename"), size="sm", tooltip=tr("Rename profile"),
                           disabled=default, theme=t),
            ui.icon_button("trash-2", lambda: c.d.delete_profile(store.active), size="sm",
                           tooltip=tr("Delete profile"), disabled=default, theme=t),
        ]
    return _core.row(parts, spacing=6, align="center")


def dialog(d: "Designer", t: Theme) -> Any:
    """The Settings dialog: search, scope and profile on top, the index of pages on the left and the chosen page
    (or the search results) on the right; Reset all and the settings file in the footer."""
    c = d.settings_ui
    content = search_content(c, t) if c.query.strip() else page_content(c, c.page, t)
    if c.scope == "project":
        content.insert(0, ui.callout(tr("Project settings"),
                                     tr("Changes here apply to this project only, for everyone who opens it, and "
                                        "win over the user's settings."), tint="info", theme=t))
    if c.store.project_error:
        content.insert(0, ui.callout(tr("The project settings could not be read"), c.store.project_error,
                                     tint="error", theme=t))
    body = _core.column([
        _top(c, t),
        _core.row([
            _index(c, t),
            _core.rule(vertical=True, thickness=1, color=t.border_variant),
            _core.scrollable(_core.column(content, spacing=14, padding=(0, 10, 0, 0)), height=500,
                             scrollbar_width=4, width="fill"),
        ], spacing=14, height=500),
    ], spacing=12)
    changed = c.store.changed_count(c.scope)
    armed = time.monotonic() - c.reset_armed <= 5
    label = tr("Press again to reset {count}", count=changed) if armed else (
        tr("Remove project settings") if c.scope == "project" else tr("Reset all"))
    file = (_profiles.project_path(c.project_root) if c.scope == "project" and c.project_root is not None
            else _settings.settings_path())
    footer = [
        ui.button(label, c.reset_all, icon="rotate-ccw", variant="solid" if armed else "ghost",
                  tint="error" if armed else None, disabled=not changed, theme=t),
        ui.button(tr("Open settings file"), lambda: d.open_url(file.as_uri()), icon="file-json", variant="ghost",
                  disabled=not file.is_file(), theme=t),
        _core.space(width="fill"),
        ui.button(tr("Done"), d.close_dialog, variant="solid", theme=t),
    ]
    return ui.modal(body, title=tr("Settings"), on_close=d.close_dialog, width=900, footer=footer, theme=t)
