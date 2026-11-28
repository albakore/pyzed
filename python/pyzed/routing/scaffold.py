"""``pyzed route``: create route files and list the routes of an ``app/`` folder.

::

    pyzed route add /products/[id] --load --loading     # app/products/[id]/page.py and loading.py
    pyzed route add "/(shop)/cart" --layout             # a group: not part of the address
    pyzed route list                                    # every address and the files that answer it
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import tree as _tree

__all__ = ["KINDS", "add", "find_app", "folder_for", "routes_table", "source_for"]

#: The files ``pyzed route add`` can write, in the order it lists them.
KINDS = ("page", "layout", "template", "loading", "error", "not_found", "middleware")


def _title(route: str) -> str:
    parts = [p for p in route.strip("/").split("/") if p and not p.startswith(("(", "["))]
    return parts[-1].replace("-", " ").replace("_", " ").capitalize() if parts else "Home"


def _params(route: str) -> List[Tuple[str, str]]:
    """``(name, kind)`` of each dynamic part: kind is ``dynamic``, ``catch_all`` or ``optional_catch_all``."""
    out = []
    for part in (p for p in route.strip("/").split("/") if p):
        kind, param = _tree.parse_name(part)
        if param:
            out.append((param, kind))
    return out


def source_for(kind: str, route: str, *, load: Optional[str] = None) -> str:
    """The starting code of a ``kind`` file for ``route`` (``load`` is ``"async"``, ``"sync"`` or ``None``)."""
    title = _title(route)
    names = [name for name, _kind in _params(route)]
    if kind == "page":
        return _page(route, title, names, load)
    if kind not in _SOURCES:
        raise ValueError(f"unknown route file {kind!r}: use {', '.join(KINDS)}")
    if kind == "middleware":
        here = "/".join(p for p in route.strip("/").split("/") if p and not p.startswith("("))
        return _SOURCES[kind].replace("{matcher}", f"/{here}/:path*" if here else "/:path*")
    return _SOURCES[kind]


def _q(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _page(route: str, title: str, names: List[str], load: Optional[str]) -> str:
    lines: List[str] = []
    if load == "async":
        lines += ["import asyncio", ""]
    elif load == "sync":
        lines += ["import time", ""]
    lines += ["import pyzed as pz", "from pyzed import ui", "", f"title = {_q(title)}", ""]
    if load:
        fetch = ("await asyncio.sleep(0.3)  # await your API or database here" if load == "async" else
                 "time.sleep(0.3)  # call your API or database here: this runs in a worker thread")
        values = ", ".join(f"{_q(n)}: params[{_q(n)}]" for n in names)
        lines += ["", f"{'async ' if load == 'async' else ''}def load({'params' if names else ''}):",
                  '    """Runs off the UI thread before the page shows (loading.py shows meanwhile)."""',
                  f"    {fetch}", f"    return {{{values}}}", ""]
    args = ", ".join((["data"] if load else []) + (["params"] if names else []))
    heading = _q(title) if not names else "f" + _q(title + " " + " / ".join("{params[%r]}" % n for n in names))
    lines += ["", f"def page({args}):", "    return pz.column([", f"        ui.heading({heading}),"]
    if load:
        lines.append('        ui.label(f"Loaded: {data}"),')
    lines += [f"        ui.label({_q('Edit ' + route_file(route, 'page') + ' to change this page.')}, "
              f"color=\"text_muted\"),",
              "    ], spacing=12)", ""]
    return "\n".join(lines)


_SOURCES = {
    "layout": '''import pyzed as pz


def layout(children):
    """Wraps every page below this folder and keeps its state while you move between them."""
    return pz.column([children], width="fill", height="fill")
''',
    "template": '''import pyzed as pz


def template(children):
    """Like a layout, but drawn from scratch on every navigation (an entrance animation plays again)."""
    return pz.column([children], width="fill").animate("fade_in")
''',
    "loading": '''from pyzed import ui


def loading():
    """Shown while a `load` below this folder runs."""
    return ui.skeleton(lines=4)
''',
    "error": '''import pyzed as pz
from pyzed import ui


def error(error, reset):
    """Shown when a page, a layout or a `load` below this folder fails; `reset` tries again."""
    return pz.column([
        ui.heading("Something went wrong", level=2),
        ui.label(str(error), color="text_muted"),
        ui.button("Try again", reset, icon="rotate-ccw"),
    ], spacing=12)
''',
    "not_found": '''from pyzed import ui


def not_found():
    """Shown for addresses no page answers, and where a page or a `load` calls pz.not_found()."""
    return ui.empty_state("Not found", "There is nothing at this address.", icon="search-x")
''',
    "middleware": '''matcher = ["{matcher}"]  # the addresses it runs for


def middleware(request):
    """Runs before every navigation below this folder. Return request.redirect(href),
    request.rewrite(href), False to stay where you are, or nothing to go on."""
    request.locals["checked"] = True  # pages and loads can take `locals`
''',
}


def route_file(route: str, kind: str) -> str:
    """Where the file goes, relative to the project: ``app/products/[id]/page.py``."""
    parts = [p for p in route.strip("/").split("/") if p]
    return "/".join(["app", *parts, f"{kind}.py"])


def find_app(start: Optional[Path] = None) -> Path:
    """The ``app/`` folder of the project at ``start`` (the current folder): ``./app``, or the
    ``app`` next to a parent's ``pyproject.toml``."""
    here = Path(start or Path.cwd()).resolve()
    for folder in (here, *here.parents):
        if (folder / "app").is_dir() and (folder.name == here.name or (folder / "pyproject.toml").exists()
                                          or folder == here):
            return folder / "app"
        if (folder / "pyproject.toml").exists():
            break
    return here / "app"


def folder_for(route: str, app: Path) -> Path:
    """The folder of ``route`` inside ``app``: ``/products/[id]`` is ``app/products/[id]``."""
    if not route.startswith("/"):
        route = "/" + route
    parts = [p for p in route.split("/") if p]
    for part in parts:
        if part.startswith("_"):
            raise _tree.RouteError(f"{part!r} starts with _: such folders are private, not routes")
        _tree.parse_name(part)  # raises for bad names
    return app.joinpath(*parts) if parts else app


def add(route: str, kinds: Sequence[str] = ("page",), *, app: Optional[Path] = None, load: Optional[str] = None,
        force: bool = False) -> List[Path]:
    """Writes the ``kinds`` files of ``route`` (a ``page.py`` by default) and returns their paths.

    Files that exist are kept unless ``force``; ``load`` adds an ``async`` (or ``"sync"``) ``load``
    function to the page. Raises ``RouteError`` for names that can't be routes.
    """
    app = Path(app) if app is not None else find_app()
    folder = folder_for(route, app)
    written = []
    for kind in kinds:
        path = folder / f"{kind}.py"
        if path.exists() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source_for(kind, route, load=load if kind == "page" else None), encoding="utf-8")
        written.append(path)
    if written:
        try:
            root = _tree.scan(app)
        except _tree.RouteError:
            for path in written:
                path.unlink()
            raise
        del root
    return written


def routes_table(app: Path) -> List[Tuple[str, List[str], str]]:
    """``(pattern, files, kind)`` of every address of ``app``: kind is ``static`` or ``dynamic``,
    files the special files that take part (its own and its layouts')."""
    root = _tree.scan(app)
    rows = []
    for segment in root.walk():
        if "page" not in segment.files:
            continue
        files: Dict[str, None] = {}
        for part in segment.chain():
            for kind in part.files:
                if kind != "page" or part is segment:
                    files[kind] = None
        dynamic = any(s.param for s in segment.chain())
        rows.append((segment.pattern, sorted(files, key=_tree.FILES.index), "dynamic" if dynamic else "static"))
    rows.sort(key=lambda r: (re.sub(r"\[", "~", r[0]), r[0]))
    return rows


def format_table(app: Path) -> str:
    """The routes as text, like Next.js' build output."""
    rows = routes_table(app)
    if not rows:
        return f"no pages in {app}: add one with `pyzed route add /`"
    width = max(len(r[0]) for r in rows)
    lines = [f"{'Route':<{width}}  Type     Files"]
    for pattern, files, kind in rows:
        mark = "λ" if kind == "dynamic" else "○"
        lines.append(f"{pattern:<{width}}  {mark} {kind:<7} {', '.join(files)}")
    lines += ["", "○ static: one address   λ dynamic: [params] in the address"]
    return "\n".join(lines)
