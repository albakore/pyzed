"""The route tree: folders (or a dict) turned into segments, and URLs matched against them.

A folder of the ``app/`` directory is a :class:`Segment`. Its name decides what it matches:

- ``products``: that exact text,
- ``[id]``: any one part of the path (``params["id"]``),
- ``[...slug]``: one or more parts (``params["slug"]`` is a list),
- ``[[...slug]]``: zero or more parts (the list may be empty),
- ``(group)``: nothing, it only groups routes (and can hold a layout of its own),
- ``_private``: skipped, for code next to the routes that is not a route.

The special files of a segment (``page``, ``layout``, ``template``, ``loading``, ``error``,
``not_found``) are kept as :class:`RouteFile` objects and imported on first use.
"""

from __future__ import annotations

import itertools
import os
import re
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple, Union

#: The files a segment can have, in the order Next.js nests them (outermost first).
FILES = ("layout", "template", "error", "loading", "not_found", "page")

#: Names of the components each file may define instead of a function (``class Page(pz.Component)``).
COMPONENT_NAMES = {"page": "Page", "layout": "Layout", "template": "Template", "loading": "Loading",
                   "error": "Error", "not_found": "NotFound"}

_counter = itertools.count()
_PARAM = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RouteError(ValueError):
    """A route folder or pattern that can't be used (a bad name, two params with the same name...)."""


def parse_name(name: str) -> Tuple[str, Optional[str]]:
    """The kind of a segment named ``name`` and its parameter: ``("dynamic", "id")`` for ``[id]``.

    Kinds: ``static``, ``dynamic``, ``catch_all``, ``optional_catch_all`` and ``group``.
    """
    if name.startswith("(") and name.endswith(")") and len(name) > 2:
        return "group", None
    for kind, start, end in (("optional_catch_all", "[[...", "]]"), ("catch_all", "[...", "]"), ("dynamic", "[", "]")):
        if name.startswith(start) and name.endswith(end):
            param = name[len(start):-len(end)]
            if not _PARAM.match(param):
                raise RouteError(f"{name!r}: the parameter must be a Python name (letters, digits and _), "
                                 f"like [id] or [...slug]")
            return kind, param
    if "[" in name or "]" in name:
        raise RouteError(f"{name!r} is not a valid segment: use [name], [...name] or [[...name]]")
    return "static", None


def load_module(path: Path, name: str, extra: Tuple[Path, ...] = ()) -> types.ModuleType:
    """Executes the route file at ``path`` as a fresh module (folders like ``[id]`` can't be imported).

    The module has no import spec, so hot reload runs it again in place when it is saved (the
    route's functions get the new code). Its folder and ``extra`` (the folder that holds ``app/``)
    are importable while it runs, for helpers next to them.
    """
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module  # dataclasses and typing look the module up while it runs
    added = [str(f) for f in (path.parent, *extra) if str(f) not in sys.path]
    sys.path[:0] = added
    try:
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)  # noqa: S102
    except BaseException:
        sys.modules.pop(name, None)
        raise
    finally:
        for folder in added:
            if folder in sys.path:
                sys.path.remove(folder)
    return module


class RouteFile:
    """One special file of a segment: ``page.py``, a ``page.pzform``, or a value given in code.

    ``target()`` is what renders it (a function or a ``pz.Component`` class) and ``attr(name)``
    any other value it defines (``load``, ``title``, ``metadata``, ``provide``...).
    """

    def __init__(self, kind: str, source: Any, segment: "Segment") -> None:
        self.kind = kind
        self.segment = segment
        self.path: Optional[Path] = source if isinstance(source, Path) else None
        self._value = None if self.path is not None else source
        self._module: Optional[types.ModuleType] = None

    def __repr__(self) -> str:
        return f"<RouteFile {self.segment.id or '/'} {self.kind}>"

    @property
    def is_form(self) -> bool:
        """Whether this is a form made in Pyzed Design (``page.pzform``)."""
        return self.path is not None and self.path.suffix == ".pzform"

    @property
    def module(self) -> Any:
        """The module (or the object given in code) holding this file's values."""
        if self.path is None or self.is_form:
            return self._value
        if self._module is None:
            slug = re.sub(r"\W+", "_", f"{self.segment.id}_{self.kind}").strip("_")
            root = self.segment.chain()[0].folder
            self._module = load_module(self.path, f"pyzed_route_{slug}_{next(_counter)}",
                                       (root.parent,) if root is not None else ())
        return self._module

    def target(self) -> Any:
        """The function or component class that renders this file."""
        if self.is_form:
            return self.path
        value = self.module
        if callable(value) and not isinstance(value, types.ModuleType):
            return value
        for name in (self.kind, COMPONENT_NAMES[self.kind], "default"):
            found = getattr(value, name, None)
            if callable(found):
                return found
        where = self.path or "the value given"
        raise RouteError(f"{where}: define a function {self.kind}(...) or a component class "
                         f"{COMPONENT_NAMES[self.kind]}(pz.Component)")

    def attr(self, name: str, default: Any = None) -> Any:
        """A value the file defines next to its function (``load``, ``title``...), or ``default``."""
        if self.is_form:
            return default
        value = self.module
        if callable(value) and not isinstance(value, types.ModuleType):  # a function or a class given in code
            return getattr(self, "_extra", {}).get(name, default)
        return getattr(value, name, default)


@dataclass(eq=False)
class Segment:
    """A folder of the route tree."""

    name: str
    kind: str = "static"
    param: Optional[str] = None
    parent: Optional["Segment"] = field(default=None, repr=False)
    children: List["Segment"] = field(default_factory=list, repr=False)
    files: Dict[str, RouteFile] = field(default_factory=dict, repr=False)
    folder: Optional[Path] = field(default=None, repr=False)

    @property
    def id(self) -> str:
        """The segment's path in the tree with its folder names: ``/(shop)/products/[id]``."""
        names: List[str] = []
        segment: Optional[Segment] = self
        while segment is not None and segment.parent is not None:
            names.append(segment.name)
            segment = segment.parent
        return "/" + "/".join(reversed(names)) if names else ""

    @property
    def pattern(self) -> str:
        """The URL pattern the segment answers, without groups: ``/products/[id]``."""
        names: List[str] = []
        segment: Optional[Segment] = self
        while segment is not None and segment.parent is not None:
            if segment.kind != "group":
                names.append(segment.name)
            segment = segment.parent
        return "/" + "/".join(reversed(names))

    def child(self, name: str) -> "Segment":
        """The child folder called ``name``, created if missing."""
        for child in self.children:
            if child.name == name:
                return child
        kind, param = parse_name(name)
        child = Segment(name, kind, param, parent=self)
        self.children.append(child)
        return child

    def walk(self) -> Iterator["Segment"]:
        """This segment and every segment under it, depth first."""
        yield self
        for child in self.children:
            yield from child.walk()

    def chain(self) -> List["Segment"]:
        """The segments from the root down to this one."""
        found: List[Segment] = []
        segment: Optional[Segment] = self
        while segment is not None:
            found.append(segment)
            segment = segment.parent
        return list(reversed(found))


def is_route_file(path: Union[str, Path], root: Union[str, Path]) -> bool:
    """Whether ``path`` looks like a special file of a route folder (``app/**/page.py``...) under ``root``:
    tools that import a project's modules (the designer's toolbox) leave them to the router."""
    path, root = Path(path), Path(root)
    if path.suffix != ".py" or path.stem not in FILES:
        return False
    try:
        folders = path.parent.relative_to(root).parts
    except ValueError:
        return False
    return any(f == "app" or f.startswith(("[", "(")) for f in folders)


# -- building ------------------------------------------------------------------------------------------
_SKIP = {"__pycache__", "node_modules"}


def scan(folder: Union[str, Path]) -> Segment:
    """The route tree of the ``app/`` folder at ``folder``."""
    root_dir = Path(folder)
    if not root_dir.is_dir():
        raise RouteError(f"{root_dir} is not a folder: create it with a page.py inside, or give the routes as a dict")
    root = Segment("", folder=root_dir)

    def fill(segment: Segment, here: Path) -> None:
        names = sorted(os.listdir(here))
        for kind in FILES:
            for suffix in (".py", ".pzform") if kind == "page" else (".py",):
                if kind + suffix in names and (here / (kind + suffix)).is_file():
                    segment.files.setdefault(kind, RouteFile(kind, here / (kind + suffix), segment))
        for name in names:
            path = here / name
            if not path.is_dir() or name in _SKIP or name.startswith((".", "_")):
                continue
            child = segment.child(name)
            child.folder = path
            fill(child, path)

    fill(root, root_dir)
    check(root)
    return root


def from_mapping(routes: Mapping[str, Any]) -> Segment:
    """The route tree of routes given in code: ``{"/": home, "/users/[id]": {"page": user, "loading": wait}}``.

    A value is the page (a function or component class), or a dict of the segment's files
    (``page``, ``layout``, ``template``, ``loading``, ``error``, ``not_found``) plus the page's
    ``load``, ``title`` and ``metadata``. A module (or any object) with those attributes works too.
    """
    root = Segment("")
    for pattern, value in routes.items():
        if not isinstance(pattern, str) or not pattern.startswith("/"):
            raise RouteError(f"route {pattern!r} must start with /")
        segment = root
        for name in (p for p in pattern.split("/") if p):
            segment = segment.child(name)
        entries = _entries(value)
        extra = {k: v for k, v in entries.items() if k not in FILES}
        for kind, target in entries.items():
            if kind not in FILES:
                continue
            route_file = RouteFile(kind, target, segment)
            if kind == "page":
                route_file._extra = extra  # type: ignore[attr-defined]
            segment.files[kind] = route_file
    check(root)
    return root


def _entries(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        unknown = [k for k in value if k not in FILES and k not in ("load", "title", "metadata", "provide")]
        if unknown:
            raise RouteError(f"unknown route entries {unknown}: use {', '.join(FILES)}, load, title, metadata")
        return dict(value)
    return {"page": value}


def check(root: Segment) -> None:
    """Raises ``RouteError`` for trees that can't work: a param used twice in one route, a catch-all
    with folders inside, or two pages answering the same URL."""
    seen: Dict[str, str] = {}
    for segment in root.walk():
        params = [s.param for s in segment.chain() if s.param]
        if len(params) != len(set(params)):
            raise RouteError(f"{segment.id}: a route can't use the same parameter name twice ({params})")
        if segment.kind in ("catch_all", "optional_catch_all") and any(c.kind != "group" for c in segment.children):
            raise RouteError(f"{segment.id}: a catch-all segment must be the last one of its route")
        if "page" in segment.files:
            shape = re.sub(r"\[\[?(\.\.\.)?\w+\]?\]", lambda m: "[[...]]" if m.group(0).startswith("[[") else
                           ("[...]" if m.group(1) else "[]"), segment.pattern)
            if shape in seen:
                raise RouteError(f"{segment.id} and {seen[shape]} both answer {segment.pattern}")
            seen[shape] = segment.id


# -- matching ------------------------------------------------------------------------------------------
@dataclass
class Match:
    """A URL matched to a page: the segments from the root to it and the parameters it read."""

    segments: List[Segment]
    params: Dict[str, Union[str, List[str]]]
    #: How specific the match is (lower wins): one entry per URL part, static before dynamic.
    score: Tuple[int, ...] = ()

    @property
    def page(self) -> Segment:
        return self.segments[-1]


_RANK = {"static": 0, "dynamic": 1, "catch_all": 2, "optional_catch_all": 3}


def match(root: Segment, parts: List[str]) -> Optional[Match]:
    """The most specific page for the URL ``parts`` (already split and decoded), or ``None``.

    Like Next.js: a static folder wins over ``[param]``, which wins over ``[...catch_all]``,
    which wins over ``[[...optional]]``; groups don't count.
    """
    found: List[Match] = []

    def visit(segment: Segment, rest: List[str], chain: List[Segment], params: Dict[str, Any],
              score: Tuple[int, ...]) -> None:
        chain = chain + [segment]
        if not rest and "page" in segment.files:
            found.append(Match(chain, dict(params), score))
        for child in segment.children:
            kind = child.kind
            if kind == "group":
                visit(child, rest, chain, params, score)
            elif kind == "static":
                if rest and rest[0] == child.name:
                    visit(child, rest[1:], chain, params, score + (0,))
            elif kind == "dynamic":
                if rest:
                    visit(child, rest[1:], chain, {**params, child.param: rest[0]}, score + (1,))
            elif kind == "catch_all":
                if rest:
                    visit(child, [], chain, {**params, child.param: list(rest)}, score + (2,) * len(rest))
            elif kind == "optional_catch_all":
                visit(child, [], chain, {**params, child.param: list(rest)}, score + (3,) * max(len(rest), 1))

    visit(root, list(parts), [], {}, ())
    if not found:
        return None
    return min(found, key=lambda m: (m.score, len(m.segments)))


def patterns(root: Segment) -> List[str]:
    """Every page's URL pattern, sorted: ``["/", "/products", "/products/[id]"]``."""
    return sorted({s.pattern for s in root.walk() if "page" in s.files})


def build_href(pattern: str, params: Optional[Mapping[str, Any]] = None) -> str:
    """The URL of ``pattern`` with ``params`` filled in: ``build_href("/users/[id]", {"id": 7})`` is ``/users/7``."""
    from urllib.parse import quote

    params = dict(params or {})
    parts: List[str] = []
    for name in (p for p in pattern.split("/") if p):
        kind, param = parse_name(name)
        if kind == "group":
            continue
        if kind == "static":
            parts.append(name)
            continue
        if param not in params:
            if kind == "optional_catch_all":
                continue
            raise KeyError(f"{pattern}: missing the parameter {param!r}")
        value = params.pop(param)
        if kind == "dynamic":
            parts.append(quote(str(value), safe=""))
        else:
            values = [value] if isinstance(value, str) else list(value)
            parts.extend(quote(str(v), safe="") for v in values)
    return "/" + "/".join(parts)

