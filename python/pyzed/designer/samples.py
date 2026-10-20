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
CATEGORIES = ("Apps", "Games", "Showcase", "Blocks", "Designer", "Integrations")
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
    #: The script Run starts, inside the new project (a single script keeps its name).
    entry: str = ""
    #: Extra files the example reads, inside ``examples/``.
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
    Sample("counter", "Counter", "The smallest Pyzed app: state, update and view in a few lines.", "Apps",
           "counter.py"),
    Sample("todo", "To-do list", "Text input, list items, filters and keyboard shortcuts.", "Apps", "todo.py"),
    Sample("pomodoro", "Pomodoro", "A focus timer with work and break sessions, built step by step in the AI guide.",
           "Apps", "pomodoro.py"),
    Sample("markdown_viewer", "Markdown viewer", "Write Markdown on the left and read it rendered on the right.",
           "Apps", "markdown_viewer.py"),
    Sample("game_of_life", "Game of Life", "Conway's cellular automaton drawn on a canvas, with patterns.", "Apps",
           "game_of_life.py"),
    Sample("gallery", "Component gallery", "A tour of the ready-made components in pyzed.ui.", "Apps",
           "gallery.py"),
    Sample("zed_editor", "Zed-like editor",
           "Zed recreated: project panel, tabs, a highlighted editor, git colors and the palette.", "Apps",
           "zed_editor.py"),
    Sample("snake", "Snake", "The classic in about 150 lines: a fixed-rate game loop, keys and a canvas.", "Games",
           "games/snake.py"),
    Sample("breakout", "Breakout", "A paddle, a ball and a wall of bricks at the display's frame rate.", "Games",
           "games/breakout.py"),
    Sample("neon_invaders", "Neon Invaders", "A space shooter with a glowing HUD, particles, bloom and screen shake.",
           "Games", "games/neon_invaders.py"),
    Sample("glass_dashboard", "Glass dashboard", "A frosted-glass control center over a moving shader background.",
           "Showcase", "showcase/glass_dashboard.py"),
    Sample("hud", "Game HUD", "Health and mana bars, a radar minimap and an ability bar.", "Showcase",
           "showcase/hud.py"),
    Sample("main_menu", "Game main menu", "A synthwave shader backdrop, a glowing title and glass buttons.", "Showcase",
           "showcase/main_menu.py"),
    Sample("inventory", "Inventory", "An RPG item grid whose rarity glows, with a glass details panel.", "Showcase",
           "showcase/inventory.py"),
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
    Sample("designer_login", "Login form", "A sign-in form made in Pyzed Design, with its event code and components.",
           "Designer", "designer"),
    Sample("sqlmodel_heroes", "SQLModel heroes", "SQLModel's tutorial: teams, heroes, filters and a validated form.",
           "Integrations", "integrations/sqlmodel_heroes", entry="main.py"),
    Sample("pydantic_signup", "Pydantic sign-up", "A sign-up form validated by a model, saved as JSON.",
           "Integrations", "integrations/pydantic_signup", entry="main.py"),
    Sample("httpx_pypi", "PyPI with httpx", "Concurrent requests streamed into the window and parsed into models.",
           "Integrations", "integrations/httpx_pypi", entry="main.py"),
    Sample("sqlalchemy_contacts", "SQLAlchemy contacts", "20,000 rows in a virtual table, searched and sorted in SQL.",
           "Integrations", "integrations/sqlalchemy_contacts", entry="main.py"),
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
        form = next(iter(sorted((folder / "ui").glob("*.pzform"))), None)
        text = _pyproject(name, sample, "", sample.dependencies).replace('script = ""\n', "")
        if form is not None:
            text += f'main = "ui/{form.name}"\n'
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
        for readme in ("README.md",):
            if not (folder / readme).exists():
                (folder / readme).write_text(f"# {sample.title}\n\n{sample.description}\n", encoding="utf-8")
    else:
        shutil.copy2(source, folder / sample.script)
        for rel in sample.extra:
            target = folder / Path(rel).name
            shutil.copy2(root / rel, target)
        (folder / "pyproject.toml").write_text(_pyproject(name, sample, sample.script, sample.dependencies),
                                               encoding="utf-8")
        (folder / "README.md").write_text(
            f"# {sample.title}\n\n{sample.description}\n\nRun it with **Run** (F5) in Pyzed Design, or:\n\n"
            f"```bash\nuv run {sample.script}\n```\n", encoding="utf-8")
    if not (folder / ".gitignore").exists():
        (folder / ".gitignore").write_text(".venv/\n__pycache__/\n*.db\n", encoding="utf-8")
    return folder
