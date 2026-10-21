"""The example projects of Pyzed Design: a catalog of the demos in ``examples/``, where to find
them (inside the app, in a checkout, or downloaded once from the release), and how to turn
one into a project of your own.

Each ``Sample`` is a script (or a folder) of ``examples/`` with a title, a description, a
thumbnail in ``examples/thumbnails`` and the packages it needs besides ``pyzed-ui``. ``create``
copies it into a new uv project whose ``[tool.pyzed] script`` is what Run (F5) starts.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .. import __version__
from ..project import prebuilt

#: Categories in the order the gallery shows them.
CATEGORIES = ("Apps", "Tutorial", "Audio", "Games", "Animation", "Styling", "Shading", "Showcase", "Blocks",
              "Patterns", "AI", "Designer", "Integrations")
THUMBNAILS = "thumbnails"
#: Where releases keep their sources (the examples come from the tag of this version).
ARCHIVE_URL = "https://github.com/albakore/pyzed/archive/refs/tags/v{version}.zip"


@dataclass(frozen=True)
class Sample:
    """An example the gallery offers."""

    id: str
    title: str
    description: str
    category: str
    #: The script or folder inside ``examples/``.
    path: str
    #: Packages besides ``pyzed-ui`` (folders with a ``pyproject.toml`` bring their own).
    dependencies: Tuple[str, ...] = ()
    #: The script Run starts, inside the new project (a single script keeps its name); for a Designer
    #: example, the form it opens, inside its folder.
    entry: str = ""
    #: Extra files or folders the example reads, inside ``examples/`` (copied next to the script).
    extra: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_folder(self) -> bool:
        return not self.path.endswith((".py", ".pzform"))

    @property
    def script(self) -> str:
        return self.entry or Path(self.path).name

    @property
    def thumbnail(self) -> str:
        return f"{THUMBNAILS}/{self.id}.png"


CATALOG: Tuple[Sample, ...] = (
    # -- apps --
    Sample("counter", "Counter", "The smallest Pyzed app: state, update and view in a few lines.", "Apps",
           "counter.py"),
    Sample("todo", "To-do list", "Text input, list items, filters and keyboard shortcuts.", "Apps", "todo.py"),
    Sample("todos", "Todos", "Add, edit, complete, filter and keep tasks, after Iced's todos demo.", "Apps",
           "todos.py"),
    Sample("pomodoro", "Pomodoro", "A focus timer with work and break sessions, built step by step in the AI guide.",
           "Apps", "pomodoro.py"),
    Sample("markdown_viewer", "Markdown viewer", "Write Markdown on the left and read it rendered on the right.",
           "Apps", "markdown_viewer.py"),
    Sample("game_of_life", "Game of Life", "Conway's cellular automaton drawn on a canvas, with patterns.", "Apps",
           "game_of_life.py"),
    Sample("clock", "Analog clock", "A clock drawn on a canvas that ticks every second.", "Apps", "clock.py"),
    Sample("stopwatch", "Stopwatch", "Start, stop, laps and a reset, after Iced's stopwatch demo.", "Apps",
           "stopwatch.py"),
    Sample("qr_code", "QR code", "Type something and get its QR code as you write.", "Apps", "qr_code.py"),
    Sample("color_picker", "Color picker", "A color with alpha, a linear gradient or a fill with an opacity mask.",
           "Apps", "color_picker.py"),
    Sample("image_viewer", "Image viewer", "Bitmap images, and a viewer you zoom and pan with the mouse.", "Apps",
           "image_viewer.py"),
    Sample("multi_window", "Several windows", "Open, name and close windows of one app, after Iced's demo.", "Apps",
           "multi_window.py"),
    Sample("window_frame", "Custom window frame", "A title bar drawn by Pyzed, with menus like Zed and the window "
           "buttons.", "Apps", "window_frame.py"),
    Sample("gallery", "Component gallery", "A tour of the ready-made components in pyzed.ui.", "Apps",
           "gallery.py"),
    Sample("mini_editor", "Mini editor", "A Zed-like editor in about 150 lines: tree, tabs, code, docks and palette.",
           "Apps", "mini_editor.py"),
    Sample("zed_editor", "Zed-like editor",
           "Zed recreated: project panel, tabs, a highlighted editor, git colors and the palette.", "Apps",
           "zed_editor.py"),
    # -- tutorial --
    Sample("step1_hello", "1. Hello", "Tutorial, step 1: a window with some text.", "Tutorial",
           "tutorial/step1_hello.py"),
    Sample("step2_state", "2. State", "Tutorial, step 2: state, messages and callbacks.", "Tutorial",
           "tutorial/step2_state.py"),
    Sample("step3_layout", "3. Layout", "Tutorial, step 3: layout, ready-made components and themes.", "Tutorial",
           "tutorial/step3_layout.py"),
    Sample("step4_async", "4. Async work", "Tutorial, step 4: slow work without freezing the window.", "Tutorial",
           "tutorial/step4_async.py"),
    Sample("step5_notes", "5. Notes app", "Tutorial, step 5: a small notes app that puts it all together.",
           "Tutorial", "tutorial/step5_notes.py"),
    Sample("layout_basics", "Layout basics", "Rows, columns, fill, spacing, padding, alignment and grids.",
           "Tutorial", "tutorial/layout_basics.py"),
    Sample("lists_tables", "Lists and tables", "Search, sort, select a row and show its details.", "Tutorial",
           "tutorial/lists_tables.py"),
    Sample("navigation", "Navigation", "A sidebar that switches pages, and tabs inside a page.", "Tutorial",
           "tutorial/navigation.py"),
    Sample("feedback", "Talking to the user", "Validation messages, a confirmation dialog and toasts.", "Tutorial",
           "tutorial/feedback.py"),
    Sample("theme_switcher", "Theme switcher", "A bundled theme, an accent color, the system's theme or your own.",
           "Tutorial", "tutorial/theme_switcher.py"),
    Sample("contacts_backend", "Contacts with SQLite", "A contacts app whose data lives in SQLite, behind a "
           "repository class.", "Tutorial", "tutorial/contacts_backend.py"),
    # -- audio --
    Sample("synth", "Synthesizer", "Two oscillators, a filter, an envelope and effects, played with a piano.",
           "Audio", "audio/synth.py"),
    Sample("drum_machine", "Drum machine", "A step grid like FL Studio's channel rack, with tempo and swing.",
           "Audio", "audio/drum_machine.py"),
    Sample("modular", "Modular rack", "Modules on rails patched with cables you drag, like VCV Rack.", "Audio",
           "audio/modular.py"),
    Sample("visualizer", "Music visualizer", "Spectrum analyzers, a spectrogram, an oscilloscope and meters.",
           "Audio", "audio/visualizer.py"),
    Sample("midi_controller", "MIDI controller", "Channel strips, velocity pads, wheels and a keyboard that sends "
           "MIDI.", "Audio", "audio/midi_controller.py"),
    Sample("webcam", "Webcam", "The camera's live picture, a snapshot button and its frame rate.", "Audio",
           "audio/webcam.py"),
    # -- games --
    Sample("snake", "Snake", "The classic in about 150 lines: a fixed-rate game loop, keys and a canvas.", "Games",
           "games/snake.py"),
    Sample("breakout", "Breakout", "A paddle, a ball and a wall of bricks at the display's frame rate.", "Games",
           "games/breakout.py"),
    Sample("neon_invaders", "Neon Invaders", "A space shooter with a glowing HUD, particles, bloom and screen shake.",
           "Games", "games/neon_invaders.py"),
    Sample("asteroids", "Rock Storm", "An Asteroids-style shooter with thrust, wrap-around space and particles.",
           "Games", "games/asteroids.py"),
    Sample("platformer", "Pixel Run", "A side-scrolling platformer with a tile map, a camera, enemies and coins.",
           "Games", "games/platformer.py"),
    Sample("game_2048", "2048", "The sliding-tiles puzzle, with smooth moves and merges that pop.", "Games",
           "games/game_2048.py"),
    Sample("coin_chase", "Coin Chase", "Your first game: a frame loop, keys held down and a 30-second timer.",
           "Games", "games/coin_chase.py"),
    Sample("jump_lab", "Jump Lab", "Velocity, gravity, box collisions and a jump that feels good.", "Games",
           "games/jump_lab.py"),
    Sample("walker", "Walker", "Sprites, frame animation and tweening.", "Games", "games/walker.py"),
    Sample("menus", "Orb Rush", "A title screen, a HUD, a pause menu and settings around a small game.", "Games",
           "games/menus.py"),
    Sample("high_scores", "Target Rush", "A 20-second clicking game that keeps a top-10 table on disk.", "Games",
           "games/high_scores.py"),
    Sample("dodge", "Dodge", "A tiny real-time game built with the game loop of pyzed.game.", "Games",
           "tutorial/dodge.py"),
    # -- animation --
    Sample("animations", "Animations", "Presets, hover and press motion, transitions, presence and glass.",
           "Animation", "animations.py"),
    Sample("effects", "Effects", "Rotation, blur, backdrop blur, glass and bloom, animated by the renderer.",
           "Animation", "effects.py"),
    Sample("timeline", "Timeline", "Keyframed animations with pz.AnimationPlayer, like Godot's.", "Animation",
           "timeline.py"),
    # -- styling --
    Sample("styles", "Styles", "CSS-like properties, named styles, gradients, masks and a global style.", "Styling",
           "styles.py"),
    Sample("web_layout", "Web-style layout", "Boxes, a stylesheet with states, media queries and nested components.",
           "Styling", "web_layout.py"),
    Sample("styling", "Theming playground", "Every theme on the same controls, after Iced's styling demo.",
           "Styling", "styling.py"),
    Sample("theme_brand", "Brand theme", "A brand theme in light and dark that follows the operating system.",
           "Styling", "theming/brand.py", extra=("theming/preview.py",)),
    Sample("theme_glassy", "Glassy dark", "A gradient behind the window and a frosted panel on top.", "Styling",
           "theming/glassy_dark.py", extra=("theming/preview.py",)),
    Sample("theme_pastel", "Pastel", "Cream background, candy colors and very round corners.", "Styling",
           "theming/pastel.py", extra=("theming/preview.py",)),
    Sample("theme_retro", "Retro terminal", "Green phosphor on black, monospaced and square.", "Styling",
           "theming/retro_terminal.py", extra=("theming/preview.py",)),
    Sample("theme_contrast", "High contrast", "Strong colors and clear edges for readers who need them.", "Styling",
           "theming/high_contrast.py", extra=("theming/preview.py",)),
    Sample("theme_mixed", "Two themes", "Two themes in one window, and a theme picker that remembers your choice.",
           "Styling", "theming/mixed.py", extra=("theming/preview.py",)),
    # -- shading --
    Sample("shaders", "Shader gallery", "Plasma, a ripple under the pointer, a tunnel, a CRT, Voronoi and fire.",
           "Shading", "showcase/shaders.py", extra=("showcase/shaders",)),
    Sample("aurora_graph", "Aurora shader", "A shader graph built in Python, with sliders for its variables.",
           "Shading", "tutorial/aurora_graph.py"),
    # -- showcase --
    Sample("glass_dashboard", "Glass dashboard", "A frosted-glass control center over a moving shader background.",
           "Showcase", "showcase/glass_dashboard.py"),
    Sample("hud", "Game HUD", "Health and mana bars, a radar minimap and an ability bar.", "Showcase",
           "showcase/hud.py"),
    Sample("main_menu", "Game main menu", "A synthwave shader backdrop, a glowing title and glass buttons.", "Showcase",
           "showcase/main_menu.py"),
    Sample("inventory", "Inventory", "An RPG item grid whose rarity glows, with a glass details panel.", "Showcase",
           "showcase/inventory.py"),
    # -- blocks --
    Sample("dashboard", "Dashboard", "Sidebar navigation, KPI cards, a revenue chart and recent orders.", "Blocks",
           "blocks/dashboard.py"),
    Sample("kanban", "Kanban board", "A project board with columns, labelled cards, assignees and progress.",
           "Blocks", "blocks/kanban.py"),
    Sample("music_player", "Music player", "A library sidebar, an album page and a player bar with live progress.",
           "Blocks", "blocks/music_player.py"),
    Sample("chat", "Chat", "A team messenger with channels, direct messages, a thread and a composer.",
           "Blocks", "blocks/chat.py"),
    Sample("settings", "Settings", "A sectioned settings page: profile, appearance, notifications, danger zone.",
           "Blocks", "blocks/settings.py"),
    Sample("data_table", "Data table", "A members table with search, status filters, sorting, selection and paging.",
           "Blocks", "blocks/data_table.py"),
    Sample("file_explorer", "IDE layout", "A project tree, editor tabs, a terminal, an outline and a status bar.",
           "Blocks", "blocks/file_explorer.py"),
    Sample("login", "Sign-in screen", "A split sign-in screen with a brand panel, single sign-on and passkeys.",
           "Blocks", "blocks/login.py"),
    Sample("onboarding", "Onboarding wizard", "A setup wizard with a stepper, choice cards, validation and a summary.",
           "Blocks", "blocks/onboarding.py"),
    # -- patterns --
    Sample("services", "Services", "A timer, a background worker, a process, the clipboard and saved settings.",
           "Patterns", "services.py"),
    Sample("components", "Custom components", "A star rating, a tag editor and a draggable note with their own "
           "events.", "Patterns", "components.py"),
    Sample("layout", "Docks and grids", "Track grids, flex rows and a Zed-style dock with movable panels.",
           "Patterns", "layout.py"),
    Sample("panes", "Resizable panes", "Split, resize and close panes, after Iced's pane_grid demo.", "Patterns",
           "panes.py"),
    Sample("context_menu", "Context menu", "A right-click menu built from a popover and a menu.", "Patterns",
           "context_menu.py"),
    Sample("dialogs", "Dialogs and languages", "Ready-made dialogs, and switching the app's language as it runs.",
           "Patterns", "dialogs.py"),
    Sample("downloads", "Background work", "Commands, pz.post from threads, progress bars and toasts.", "Patterns",
           "downloads.py"),
    Sample("download_progress", "Download progress", "Concurrent downloads with live progress, after Iced's demo.",
           "Patterns", "download_progress.py"),
    Sample("websocket_stream", "Live data", "A subscription fed by an async generator with pz.listen.", "Patterns",
           "websocket_stream.py"),
    # -- AI --
    Sample("agent_chat", "Pyzed agent", "An agent that calls tools to answer, drawn like Zed's Agent panel.", "AI",
           "agent_chat.py", dependencies=("pyzed-ui[agents]",)),
    Sample("ai_chat", "AI chat", "A streaming chat with any OpenAI-compatible server, or a built-in demo.", "AI",
           "ai_chat.py", dependencies=("httpx",)),
    # -- designer --
    Sample("designer_login", "Login form", "A sign-in form made in Pyzed Design, with its event code and components.",
           "Designer", "designer", entry="login.pzform"),
    Sample("designer_tasks", "Task runner", "Non-visual components at work: a timer, a process, a worker, settings.",
           "Designer", "designer", entry="tasks.pzform"),
    Sample("designer_explorer", "Project explorer", "A tree, breadcrumbs, closable tabs, a sortable table and the other "
           "toolbox controls, with their events.", "Designer", "designer", entry="explorer.pzform"),
    Sample("designer_reviews", "Component cards", "A form of cards made in the component mode, that grow with the "
           "window.", "Designer", "designer", entry="components/reviews.pzform"),
    Sample("designer_signup", "Bound sign-up form", "Controls bound to data, with validation rules.", "Designer",
           "tutorial/designer", entry="signup.pzform"),
    Sample("designer_welcome", "Form over a shader", "A welcome form drawn over a shader made of nodes.", "Designer",
           "tutorial/designer", entry="welcome.pzform"),
    # -- integrations --
    Sample("sqlmodel_heroes", "SQLModel heroes", "SQLModel's tutorial: teams, heroes, filters and a validated form.",
           "Integrations", "integrations/sqlmodel_heroes", entry="main.py"),
    Sample("sqlmodel_inventory", "SQLModel inventory", "One model validates the form and defines the table.",
           "Integrations", "integrations/sqlmodel_inventory", entry="main.py"),
    Sample("pydantic_signup", "Pydantic sign-up", "A sign-up form validated by a model, saved as JSON.",
           "Integrations", "integrations/pydantic_signup", entry="main.py"),
    Sample("httpx_pypi", "PyPI with httpx", "Concurrent requests streamed into the window and parsed into models.",
           "Integrations", "integrations/httpx_pypi", entry="main.py"),
    Sample("httpx_download", "Downloads with httpx", "Streaming downloads with progress bars and cancel.",
           "Integrations", "integrations/httpx_download", entry="main.py"),
    Sample("sqlalchemy_contacts", "SQLAlchemy contacts", "20,000 rows in a virtual table, searched and sorted in SQL.",
           "Integrations", "integrations/sqlalchemy_contacts", entry="main.py"),
    Sample("sqlalchemy_quickstart", "SQLAlchemy quick start", "The ORM quick start's users and addresses, sync or "
           "async.", "Integrations", "integrations/sqlalchemy_quickstart", entry="main.py"),
    Sample("aiosqlite_journal", "Async SQLite journal", "An async SQLite connection on Pyzed's event loop.",
           "Integrations", "integrations/aiosqlite_journal", entry="main.py"),
    Sample("fastapi_heroes", "FastAPI heroes", "FastAPI's SQL tutorial and a desktop client for it, in one process.",
           "Integrations", "integrations/fastapi_heroes", entry="in_process.py"),
)

BY_ID: Dict[str, Sample] = {s.id: s for s in CATALOG}


# -- where the examples are ------------------------------------------------------------------


def cache_dir() -> Path:
    """Where downloaded examples are kept (one folder per version)."""
    from .settings import config_dir

    return config_dir() / "examples" / __version__


def _candidates() -> List[Path]:
    found: List[Path] = []
    if os.environ.get("PYZED_EXAMPLES"):
        found.append(Path(os.environ["PYZED_EXAMPLES"]))
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        found.append(Path(bundle) / "examples")  # the standalone app
    found.append(Path(__file__).resolve().parents[3] / "examples")  # a checkout of the repository
    found.append(cache_dir())
    return found


def examples_root() -> Optional[Path]:
    """The ``examples`` folder this designer can read, or ``None`` until they are downloaded."""
    for folder in _candidates():
        if (folder / BY_ID["counter"].path).is_file():
            return folder
    return None


def download(progress: Optional[Callable[[str], None]] = None, url: Optional[str] = None) -> Path:
    """Downloads this version's examples (and their thumbnails) from the release; returns the folder."""
    url = url or ARCHIVE_URL.format(version=__version__)
    if progress:
        progress(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - a fixed https address
        data = response.read()
    dest = cache_dir()
    tmp = dest.with_name(dest.name + ".part")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            parts = name.split("/", 2)  # pyzed-<version>/examples/...
            if len(parts) < 3 or parts[1] != "examples" or not parts[2] or name.endswith("/"):
                continue
            target = tmp / parts[2]
            if ".." in Path(parts[2]).parts:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    shutil.rmtree(dest, ignore_errors=True)
    tmp.rename(dest)
    return dest


def stage(dest: Path, root: Optional[Path] = None) -> List[Path]:
    """Copies what the gallery needs (each sample and its thumbnail) to ``dest``, for the standalone app."""
    root = root or Path(__file__).resolve().parents[3] / "examples"
    copied: List[Path] = []
    for sample in CATALOG:
        for rel in (sample.path, sample.thumbnail, *sample.extra):
            source = root / rel
            if not source.exists():
                continue
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True, ignore=_ignore)
            else:
                shutil.copy2(source, target)
            copied.append(target)
    return copied


def _ignore(folder: str, names: Sequence[str]) -> List[str]:
    return [n for n in names if n in ("__pycache__", ".venv", "uv.lock") or n.endswith((".db", ".sqlite"))]


# -- making a project of one ---------------------------------------------------------------------


def slug(text: str) -> str:
    """A project name from ``text`` (``"Game HUD"`` → ``game-hud``)."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "example"


def _pyproject(name: str, sample: Sample, script: str, dependencies: Sequence[str], extra: str = "") -> str:
    deps = ", ".join(f'"{d}"' for d in ("pyzed-ui", *dependencies))
    description = sample.description.replace('"', "'")
    text = (f'[project]\nname = "{name}"\nversion = "0.1.0"\ndescription = "{description}"\n'
            f'requires-python = ">=3.10"\ndependencies = [{deps}]\n')
    return prebuilt(text + extra) + f'\n[tool.pyzed]\nui = "ui"\nscript = "{script}"\n'


def _strip_sources(text: str) -> str:
    """Drops the ``[tool.uv.sources]`` that point a demo at the repository's Pyzed."""
    text = re.sub(r"(?m)^# Runs against this checkout.*\n", "", text)
    return re.sub(r"(?m)^\[tool\.uv\.sources\]\n(?:(?!\[).*\n?)*", "", text).rstrip() + "\n"


def create(sample: Sample, folder: Path, name: Optional[str] = None, root: Optional[Path] = None) -> Path:
    """Copies ``sample`` into the new project ``folder`` (which must not exist or be empty) and returns it.

    A single script becomes the project's ``script``; a folder keeps its own ``pyproject.toml``
    (pointed at ``pyzed-ui`` from PyPI) and gets ``[tool.pyzed]``; the Designer example becomes a
    project whose ``ui/`` holds the form and its components.
    """
    root = root or examples_root()
    if root is None:
        raise FileNotFoundError("The examples are not downloaded yet")
    source = root / sample.path
    if not source.exists():
        raise FileNotFoundError(f"{sample.path} is missing from {root}")
    folder = Path(folder).expanduser()
    if folder.exists() and any(folder.iterdir()):
        raise FileExistsError(f"{folder} is not empty")
    folder.mkdir(parents=True, exist_ok=True)
    name = slug(name or folder.name)
    if sample.category == "Designer":
        shutil.copytree(source, folder / "ui", dirs_exist_ok=True, ignore=_ignore)
        readme = folder / "ui" / "README.md"
        if readme.exists():
            readme.rename(folder / "README.md")
        form = folder / "ui" / sample.entry if sample.entry else \
            next(iter(sorted((folder / "ui").glob("*.pzform"))), None)
        text = _pyproject(name, sample, "", sample.dependencies).replace('script = ""\n', "")
        if form is not None and form.is_file():
            text += f'main = "{form.relative_to(folder).as_posix()}"\n'
        (folder / "pyproject.toml").write_text(text, encoding="utf-8")
    elif sample.is_folder:
        shutil.copytree(source, folder, dirs_exist_ok=True, ignore=_ignore)
        pyproject = folder / "pyproject.toml"
        text = _strip_sources(pyproject.read_text(encoding="utf-8")) if pyproject.exists() else \
            _pyproject(name, sample, sample.script, sample.dependencies)
        text = re.sub(r'(?m)^name = ".*"$', f'name = "{name}"', text, count=1)
        if "[tool.pyzed]" not in text:
            text += f'\n[tool.pyzed]\nui = "ui"\nscript = "{sample.script}"\n'
        pyproject.write_text(prebuilt(text), encoding="utf-8")
    else:
        shutil.copy2(source, folder / sample.script)
        for rel in sample.extra:
            source, target = root / rel, folder / Path(rel).name
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True, ignore=_ignore)
            else:
                shutil.copy2(source, target)
        (folder / "pyproject.toml").write_text(_pyproject(name, sample, sample.script, sample.dependencies),
                                               encoding="utf-8")
        (folder / "README.md").write_text(
            f"# {sample.title}\n\n{sample.description}\n\nRun it with **Run** (F5) in Pyzed Design, or:\n\n"
            f"```bash\nuv run {sample.script}\n```\n", encoding="utf-8")
    if not (folder / "README.md").exists():
        (folder / "README.md").write_text(f"# {sample.title}\n\n{sample.description}\n", encoding="utf-8")
    if not (folder / ".gitignore").exists():
        (folder / ".gitignore").write_text(".venv/\n__pycache__/\n*.db\n", encoding="utf-8")
    return folder
