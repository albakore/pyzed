"""The router: history, data loading and drawing a route with its layouts and boundaries."""

from __future__ import annotations

import functools
import inspect
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Optional, Tuple, Union
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlsplit

from .. import _core
from .. import component as _component
from . import _middleware
from . import tree as _tree

RoutesLike = Union[str, Path, Mapping[str, Any], _tree.Segment]

# The names the router shares with what it draws (see ``use_router``).
_ROUTER = "_pyzed_router"
_LOCATION = "_pyzed_location"

#: The router that drew last: what ``use_router()`` returns outside a view (a callback, a form's handler).
_current: Optional["Router"] = None

_pool: Optional[ThreadPoolExecutor] = None
_pool_lock = threading.Lock()


def _executor() -> ThreadPoolExecutor:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="pyzed-route-load")
        return _pool


# -- what pages raise ------------------------------------------------------------------------------------
class NotFound(Exception):
    """Raised by ``pz.not_found()``: the closest ``not_found`` file is shown instead of the page."""


class Redirect(Exception):
    """Raised by ``pz.redirect(href)``: the router goes to ``href`` instead (replacing the entry)."""

    def __init__(self, href: str, *, push: bool = False) -> None:
        super().__init__(href)
        self.href = href
        self.push = push


class _Pending(Exception):
    """A ``load`` is still running: the closest ``loading`` file is shown meanwhile."""


def not_found() -> "NoReturn":  # type: ignore[name-defined]  # noqa: F821
    """Stops drawing the page (or its ``load``) and shows the closest ``not_found`` file, like Next.js'
    ``notFound()``::

        async def load(params):
            product = await shop.get(params["id"])
            if product is None:
                pz.not_found()
            return product
    """
    raise NotFound()


def redirect(href: str, *, push: bool = False) -> "NoReturn":  # type: ignore[name-defined]  # noqa: F821
    """Goes to ``href`` instead of the page being drawn (from a page, a layout or a ``load``).

    The current history entry is replaced, like Next.js' ``redirect()``; ``push=True`` adds one.
    """
    raise Redirect(href, push=push)


# -- locations -------------------------------------------------------------------------------------------
class SearchParams(dict):
    """The query of the URL (``?tab=reviews&tag=a&tag=b``) as a dict of the first values.

    ``get_all("tag")`` gives every value of a repeated key, ``str()`` the encoded query.
    """

    def __init__(self, pairs: Tuple[Tuple[str, str], ...] = ()) -> None:
        super().__init__()
        self.pairs = tuple(pairs)
        for key, value in self.pairs:
            self.setdefault(key, value)

    def get_all(self, key: str) -> List[str]:
        """Every value of ``key``, in order (an empty list if it is missing)."""
        return [v for k, v in self.pairs if k == key]

    def __str__(self) -> str:
        return urlencode(self.pairs)

    def __hash__(self) -> int:  # type: ignore[override]
        return hash(self.pairs)


@dataclass(frozen=True)
class Location:
    """Where the router is: ``pathname`` (``/products/3``), the ``search`` query without ``?`` and the
    ``hash`` without ``#``. The same parts as a browser's URL, so a route maps to a web address as is."""

    pathname: str = "/"
    search: str = ""
    hash: str = ""

    @property
    def query(self) -> SearchParams:
        """The query as a dict (see ``SearchParams``)."""
        return SearchParams(tuple(parse_qsl(self.search, keep_blank_values=True)))

    @property
    def href(self) -> str:
        """The whole location as text: ``/products/3?tab=reviews#top``."""
        return self.pathname + (f"?{self.search}" if self.search else "") + (f"#{self.hash}" if self.hash else "")

    @property
    def parts(self) -> List[str]:
        """The decoded parts of the path: ``["products", "3"]``."""
        return [unquote(p) for p in self.pathname.split("/") if p]

    def __str__(self) -> str:
        return self.href


#: What a rewrite to "not found" points at (``pz.not_found()`` in middleware).
_NOT_FOUND = Location("/\x00not-found")


def _normalize(path: str) -> str:
    parts: List[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/" + "/".join(parts)


def resolve_href(href: Any, base: Optional[Location] = None) -> Location:
    """The location ``href`` points to from ``base``: absolute (``/a/b``), relative (``../c``, ``d``),
    only a query (``?page=2``) or only a hash (``#top``). Also takes a ``Location`` or a
    ``(pattern, params)`` pair such as ``("/users/[id]", {"id": 7})``."""
    if isinstance(href, Location):
        return href
    if isinstance(href, tuple) and len(href) == 2 and isinstance(href[1], Mapping):
        href = _tree.build_href(href[0], href[1])
    if not isinstance(href, str):
        raise TypeError(f"a route is a string such as '/products/3', not {type(href).__name__}")
    base = base or Location()
    if "://" in href:
        raise ValueError(f"{href!r} is a web address: open it with pz.system.Launcher or ui.link, not the router")
    split = urlsplit(href)
    path, search, fragment = split.path, split.query, split.fragment
    if not path:
        if not search and href.startswith("#"):
            return Location(base.pathname, base.search, fragment)
        return Location(base.pathname, search, fragment)
    if not path.startswith("/"):
        folder = base.pathname if base.pathname.endswith("/") else base.pathname.rsplit("/", 1)[0] + "/"
        path = folder + path
    encoded = "/".join(quote(unquote(p), safe="@:+,;=!$&'()*~") for p in _normalize(path).split("/"))
    return Location(encoded or "/", search, fragment)


@dataclass
class _Entry:
    """The result of one ``load`` call, or the call still running."""

    state: str = "pending"  # "pending" | "ok" | "error"
    value: Any = None
    error: Optional[BaseException] = None
    started: float = 0.0
    previous: Any = None  # the value shown while a refresh runs
    has_previous: bool = False
    stale: bool = False
    kind: str = "page"
    future: Any = None


class _NoData:
    def __repr__(self) -> str:
        return "<no data>"


_NO_DATA = _NoData()


@functools.lru_cache(maxsize=512)
def _accepted(function: Any, code: Any) -> Optional[frozenset]:
    """The keyword names ``function`` takes (``None`` when it takes ``**kwargs``: all of them)."""
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return None
    names = set()
    for p in signature.parameters.values():
        if p.kind is p.VAR_KEYWORD:
            return None
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY):
            names.add(p.name)
    return frozenset(names)


def _call_with(function: Callable[..., Any], available: Mapping[str, Any]) -> Any:
    """Calls ``function`` with the values of ``available`` it asks for by name."""
    names = _accepted(function, getattr(function, "__code__", None))
    if names is None:
        return function(**available)
    return function(**{k: v for k, v in available.items() if k in names})


def _as_widget(value: Any) -> Any:
    if isinstance(value, _core.Widget):
        return value
    if value is None:
        return _core.space()
    if isinstance(value, str):
        return _core.text(value)
    if isinstance(value, (list, tuple)):
        return _core.column([_as_widget(v) for v in value], spacing=8)
    if inspect.isawaitable(value):
        if hasattr(value, "close"):
            value.close()
        raise TypeError("a page can't be `async def`: put the awaits in `async def load(params)` next to it and "
                        "take the result as `data` (the loading file shows while it runs)")
    return _core.container(value)


@contextmanager
def _scope(*key: Any) -> Iterator[None]:
    """Gives the components drawn inside a place of their own in the render pass, so they keep their state
    while ``key`` stays the same and start fresh when it changes."""
    current = _component._passes[-1] if _component._passes else None
    if current is None:
        yield
        return
    parent = current.path
    current.path = parent + (("route",) + key,)
    try:
        yield
    finally:
        current.path = parent


def _redraw() -> None:
    try:
        _core.post(lambda: None)
    except RuntimeError:
        pass  # no app running (tests, screenshots): the next view() shows the result


# -- the router --------------------------------------------------------------------------------------------
class Router:
    """Routes in folders, like Next.js' App Router, or in a dict; see ``pyzed.routing``.

    ``routes`` is the ``app/`` folder (a relative path is looked for next to the file that creates the
    router, then in the current folder), or a dict such as ``{"/": home, "/users/[id]": user}``.
    ``initial`` is the first location and ``stale_time`` how many seconds the data of a page stays
    fresh: after that, going to it again (not back or forward) loads it again. ``middleware`` is a
    function (or a list) that runs before every navigation, before the ``middleware.py`` files of the
    folders (see ``pz.middleware``).
    """

    def __init__(self, routes: RoutesLike = "app", *, initial: str = "/", stale_time: float = 30.0,
                 history_size: int = 100, cache_size: int = 64,
                 middleware: Union[Callable[..., Any], List[Callable[..., Any]], Tuple[Callable[..., Any], ...], None] = None,
                 _depth: int = 1) -> None:
        self.source: Any = routes
        if isinstance(routes, (str, Path)):
            self.source = self._find_folder(Path(routes), _depth + 1)
        self._root: Optional[_tree.Segment] = None
        self.stale_time = stale_time
        self.history_size = history_size
        self.cache_size = cache_size
        self._entries: List[Location] = [resolve_href(initial)]
        self._index = 0
        self._cache: Dict[tuple, _Entry] = {}
        self._forms: Dict[tuple, Any] = {}
        self._listeners: List[Callable[[Location], Any]] = []
        self._shown_not_found: Optional[Tuple[str, Any]] = None
        self._last_ok: Optional[Location] = None
        self._lock = threading.Lock()
        self._watched: set = set()
        #: Middleware given in code, run before the folders' ``middleware.py`` files.
        self.middleware: List[Callable[..., Any]] = (
            [] if middleware is None else [middleware] if callable(middleware) else list(middleware))
        self._started = False
        self._navigation: Optional[object] = None  # the navigation whose async middleware is running
        self._navigation_future: Any = None
        self._rewrites: Dict[Location, Location] = {}
        self._locals: Dict[Location, Dict[str, Any]] = {}
        self._failures: Dict[Location, BaseException] = {}
        #: The window the router draws in (set by ``RouterApp``; forms made in the designer use it).
        self.window: Any = None

    def __hash__(self) -> int:  # compared by identity when components note it as context
        return id(self)

    def __eq__(self, other: object) -> bool:
        return self is other

    def __repr__(self) -> str:
        return f"<Router {self.location.href}>"

    @staticmethod
    def _find_folder(path: Path, depth: int) -> Path:
        if path.is_absolute():
            return path
        try:
            caller = sys._getframe(depth).f_globals.get("__file__")
        except ValueError:
            caller = None
        main = getattr(sys.modules.get("__main__"), "__file__", None)
        for file in (caller, main):
            if file:
                beside = Path(file).resolve().parent / path
                if beside.is_dir():
                    return beside
        return Path.cwd() / path

    # -- the tree ------------------------------------------------------------------------------------
    @property
    def root(self) -> _tree.Segment:
        """The route tree (built on first use)."""
        if self._root is None:
            source = self.source
            if isinstance(source, _tree.Segment):
                self._root = source
            elif isinstance(source, Mapping):
                self._root = _tree.from_mapping(source)
            else:
                self._root = _tree.scan(source)
                self._watch()
        return self._root

    def reload(self) -> None:
        """Reads the route folder again (new or deleted pages); the data and the forms start over."""
        if not isinstance(self.source, (Mapping, _tree.Segment)):
            self._root = None
        self._cache.clear()
        self._forms.clear()

    def _watch(self) -> None:
        """With hot reload on, new and deleted route files show up without restarting."""
        from .. import hot_reload

        reloader = hot_reload.current()
        if reloader is None or not isinstance(self.source, Path):
            return
        for segment in self._root.walk() if self._root else ():
            folder = segment.folder
            if folder is not None and folder not in self._watched:
                self._watched.add(folder)
                reloader.watch(folder, lambda _path: self._tree_changed())

    def _tree_changed(self) -> None:
        self._root = None
        self._forms.clear()

    def routes(self) -> List[str]:
        """The URL pattern of every page: ``["/", "/products", "/products/[id]"]``."""
        return _tree.patterns(self.root)

    def match(self, href: Any) -> Optional[_tree.Match]:
        """The page ``href`` leads to (its segments and parameters), or ``None``."""
        location = resolve_href(href, self.location)
        return _tree.match(self.root, location.parts)

    # -- where we are --------------------------------------------------------------------------------
    @property
    def location(self) -> Location:
        """The current ``Location``."""
        return self._entries[self._index]

    @property
    def pathname(self) -> str:
        """The current path, like ``/products/3`` (``usePathname()``)."""
        return self.location.pathname

    @property
    def query(self) -> SearchParams:
        """The current query as a dict (``useSearchParams()``)."""
        return self.location.query

    search_params = query

    @property
    def params(self) -> Dict[str, Union[str, List[str]]]:
        """The parameters of the current page: ``{"id": "3"}`` for ``/products/[id]`` (``useParams()``)."""
        found = self.match(self.location)
        return dict(found.params) if found else {}

    @property
    def url(self) -> str:
        """The current location as text: ``/products/3?tab=reviews``."""
        return self.location.href

    @property
    def history(self) -> List[str]:
        """Every location of the history, oldest first (``index`` is the current one)."""
        return [entry.href for entry in self._entries]

    @property
    def index(self) -> int:
        """The position of the current location in ``history``."""
        return self._index

    @property
    def can_go_back(self) -> bool:
        return self._index > 0

    @property
    def can_go_forward(self) -> bool:
        return self._index < len(self._entries) - 1

    @property
    def title(self) -> Optional[str]:
        """The title of the current page (its ``title`` or ``metadata``, from its data once loaded), with the
        ``title_template`` of the closest layout that has one; ``None`` when no route file gives one."""
        try:
            return self._compute_title(self.location)
        except Exception:  # noqa: BLE001 - a broken route shows its error in the window, not in the title
            return None

    @property
    def pending(self) -> bool:
        """Whether a ``load`` or an ``async`` middleware is running."""
        return self._navigation is not None or any(e.state == "pending" for e in list(self._cache.values()))

    def is_active(self, href: Any, *, exact: bool = False) -> bool:
        """Whether ``href`` is the current page, or (unless ``exact``) one of its parents: ``/docs`` is active
        on ``/docs/intro``. Handy to highlight the link of a menu."""
        target = resolve_href(href, self.location).pathname.rstrip("/")
        here = self.pathname.rstrip("/")
        if exact or not target:
            return here == target
        return here == target or here.startswith(target + "/")

    def href(self, pattern: str, **params: Any) -> str:
        """The path of ``pattern`` with ``params`` filled in: ``router.href("/users/[id]", id=7)``."""
        return _tree.build_href(pattern, params)

    # -- going places ------------------------------------------------------------------------------
    def push(self, href: Any) -> None:
        """Goes to ``href`` and adds it to the history (``router.push`` in Next.js)."""
        self._go(resolve_href(href, self.location), replace=False)

    def replace(self, href: Any) -> None:
        """Goes to ``href`` in place of the current history entry."""
        self._go(resolve_href(href, self.location), replace=True)

    def back(self) -> bool:
        """Goes back one entry; ``False`` when there is none."""
        return self.go(-1)

    def forward(self) -> bool:
        """Goes forward one entry; ``False`` when there is none."""
        return self.go(1)

    def go(self, delta: int) -> bool:
        """Moves ``delta`` entries in the history (negative goes back); ``False`` when out of range.

        Middleware runs first and may stop it, so ``True`` means only that the entry exists.
        """
        target = self._index + delta
        if delta == 0 or not 0 <= target < len(self._entries):
            return False
        action = "back" if delta < 0 else "forward"
        self._navigate(self._entries[target], action, lambda final: self._commit_go(target, final))
        return True

    def refresh(self) -> None:
        """Loads the data of the current route again; the page keeps showing the old data meanwhile."""
        with self._lock:
            for entry in self._cache.values():
                if entry.state != "pending":
                    entry.stale = True
        self._forms.clear()
        if self._started and (self.middleware or any("middleware" in s.files for s in self.root.walk())):
            self._navigate(self.location, "refresh", lambda _location: None)

    def invalidate(self, *hrefs: Any) -> None:
        """Marks the data of the pages at ``hrefs`` (every page without arguments) as old: the next time
        one is shown its ``load`` runs again, showing the old data meanwhile (``revalidatePath``).
        A pattern works too: ``router.invalidate("/products/[id]")`` covers every product."""
        targets: List[Tuple[str, Optional[tuple]]] = []
        for href in hrefs:
            text = str(href)
            if "[" in text:
                segment = next((s for s in self.root.walk() if s.pattern == text.split("?")[0]), None)
                if segment is not None:
                    targets.append((segment.id, None))
                continue
            found = _tree.match(self.root, resolve_href(text, self.location).parts)
            if found is not None:
                targets.append((found.page.id, self._frozen(found.params)))
        with self._lock:
            for key, entry in self._cache.items():
                if entry.state == "pending" or entry.kind != "page":
                    continue
                if not hrefs or any(key[1] == sid and (params is None or key[2] == params) for sid, params in targets):
                    entry.stale = True
        _redraw()

    def prefetch(self, href: Any) -> None:
        """Starts the ``load`` calls of the page at ``href`` (and of its layouts) before going there."""
        location = resolve_href(href, self.location)
        found = _tree.match(self.root, location.parts)
        if found is None:
            return
        for index, segment in enumerate(found.segments):
            params = self._params_until(found, index)
            for kind in ("layout", "page"):
                route_file = segment.files.get(kind)
                if route_file is None or route_file.is_form:
                    continue
                try:
                    loader = route_file.attr("load")
                except Exception:  # noqa: BLE001 - a broken file shows its error when visited
                    continue
                if loader is None:
                    continue
                key = self._data_key(kind, segment, params, location)
                if key not in self._cache:
                    self._start(key, loader, params, location, kind)

    def wait(self, timeout: Optional[float] = 10.0) -> bool:
        """Blocks until every running ``load`` finished (for tests and screenshots); ``False`` on timeout.

        Don't call it from the UI thread of a running app: the window would freeze meanwhile.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            futures = [e.future for e in list(self._cache.values()) if e.state == "pending" and e.future is not None]
            if self._navigation is not None and self._navigation_future is not None:
                futures.append(self._navigation_future)
            if not futures:
                return True
            for future in futures:
                left = None if deadline is None else max(deadline - time.monotonic(), 0)
                try:
                    future.result(timeout=left)
                except Exception:  # noqa: BLE001 - the entry holds it
                    pass
                if deadline is not None and time.monotonic() >= deadline:
                    return not self.pending
            time.sleep(0.001)  # the done callbacks run right after the futures resolve

    def listen(self, callback: Callable[[Location], Any]) -> Callable[[], None]:
        """Calls ``callback(location)`` after every navigation; returns a function that stops it."""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback) if callback in self._listeners else None

    def _go(self, location: Location, *, replace: bool) -> None:
        if location == self.location and not replace and self._navigation is None:
            return
        if replace:
            self._navigate(location, "replace", self._commit_replace)
        else:
            self._navigate(location, "push", self._commit_push)

    def _commit_push(self, location: Location) -> None:
        if location == self.location:
            self._changed()
            return
        del self._entries[self._index + 1:]
        self._entries.append(location)
        if len(self._entries) > self.history_size:
            del self._entries[0]
        self._index = len(self._entries) - 1
        self._expire()
        self._changed()

    def _commit_replace(self, location: Location) -> None:
        self._entries[self._index] = location
        self._expire()
        self._changed()

    def _commit_go(self, index: int, location: Location) -> None:
        if 0 <= index < len(self._entries):
            self._index = index
            self._entries[index] = location
        self._changed()

    def _expire(self) -> None:
        now = time.monotonic()
        with self._lock:
            for key in [k for k, e in self._cache.items()
                        if e.kind == "page" and e.state != "pending" and now - e.started > self.stale_time]:
                del self._cache[key]

    # -- middleware ---------------------------------------------------------------------------------
    def _middleware_for(self, location: Location) -> Tuple[List[Tuple[Callable[..., Any], Any]], Optional[_tree.Match]]:
        """The middleware that runs for ``location`` with its matchers: the router's, then the folders'."""
        chain: List[Tuple[Callable[..., Any], Any]] = [(fn, getattr(fn, "matcher", None)) for fn in self.middleware]
        found = _tree.match(self.root, location.parts)
        segments = found.segments if found is not None else [self.root]
        for segment in segments:
            route_file = segment.files.get("middleware")
            if route_file is not None:
                target = route_file.target()
                matcher = route_file.attr("matcher", getattr(target, "matcher", None))
                chain.append((target, matcher))
        return chain, found

    def _navigate(self, location: Location, action: str, commit: Callable[[Location], None], *,
                  depth: int = 0) -> None:
        """Runs the middleware for ``location`` and then ``commit``s where it ended up (or nothing)."""
        if depth > 10:
            raise _tree.RouteError(f"too many redirects in middleware (last: {location.href})")
        token = object()
        self._navigation = None
        chain, found = self._middleware_for(location)
        self._rewrites.pop(location, None)
        self._failures.pop(location, None)
        if not chain:
            self._locals.pop(location, None)
            commit(location)
            return
        request = _middleware.Request(location=location, previous=self.location if self._started else None,
                                      action=action, router=self,
                                      route=found.segments[-1].pattern if found is not None else None,
                                      params=dict(found.params) if found is not None else {})
        self._step(token, request, chain, 0, commit, depth)

    def _step(self, token: object, request: _middleware.Request, chain: List[Tuple[Callable[..., Any], Any]],
              index: int, commit: Callable[[Location], None], depth: int) -> None:
        from .. import _async

        while index < len(chain):
            function, matcher = chain[index]
            index += 1
            try:
                if not _middleware.applies(matcher, request):
                    continue
                result = _call_with(function, {"request": request, "router": self, "params": request.params,
                                               "query": request.query, "pathname": request.pathname,
                                               "previous": request.previous, "action": request.action,
                                               "locals": request.locals})
            except (Redirect, _middleware.Rewrite, NotFound) as answer:
                result = answer
            except Exception as err:  # noqa: BLE001 - shown by the error file of the page
                self._fail(request, err, commit)
                return
            if _async._isawaitable(result):
                self._wait_for(token, result, request, chain, index, commit, depth)
                return
            if self._decide(result, request, commit, depth):
                return
        self._finish(request, commit)

    def _wait_for(self, token: object, awaitable: Any, request: _middleware.Request,
                  chain: List[Tuple[Callable[..., Any], Any]], index: int, commit: Callable[[Location], None],
                  depth: int) -> None:
        """Waits for an ``async`` middleware off the UI thread, then goes on with the rest of the chain."""
        from .. import _async

        self._navigation = token

        def run() -> Any:
            try:
                return _async.run(awaitable)
            except (Redirect, _middleware.Rewrite, NotFound) as answer:
                return answer

        def resume(result: Any, error: Optional[BaseException]) -> None:
            if self._navigation is not token:
                return  # a newer navigation took over
            self._navigation = None
            if error is not None:
                self._fail(request, error, commit)
            elif not self._decide(result, request, commit, depth):
                self._step(token, request, chain, index, commit, depth)
            _redraw()

        def done(future: Any) -> None:
            try:
                result, error = future.result(), None
            except BaseException as err:  # noqa: BLE001
                result, error = None, err
            try:
                _core.post(lambda: resume(result, error))
            except RuntimeError:  # no app running (tests): go on right here
                resume(result, error)

        self._navigation_future = _executor().submit(run)
        self._navigation_future.add_done_callback(done)

    def _decide(self, result: Any, request: _middleware.Request, commit: Callable[[Location], None],
                depth: int) -> bool:
        """Acts on what a middleware returned; ``True`` when the navigation ends there."""
        if result is None or result is True:
            return False
        if result is False:
            return True  # stays where it is
        if isinstance(result, Redirect):
            target = resolve_href(result.href, request.location)
            if result.push and request.action in ("push", "replace", "start"):
                if request.action == "push":
                    self._commit_push(request.location)
                self._navigate(target, "push", self._commit_push, depth=depth + 1)
            else:
                self._navigate(target, request.action if request.action != "start" else "replace", commit,
                               depth=depth + 1)
            return True
        if isinstance(result, _middleware.Rewrite):
            self._rewrites[request.location] = resolve_href(result.href, request.location)
            self._finish(request, commit)
            return True
        if isinstance(result, NotFound):
            self._rewrites[request.location] = _NOT_FOUND
            self._finish(request, commit)
            return True
        raise TypeError(f"middleware returned {result!r}: return None to go on, False to stay, "
                        f"request.redirect(href) or request.rewrite(href)")

    def _finish(self, request: _middleware.Request, commit: Callable[[Location], None]) -> None:
        if request.locals:
            self._locals[request.location] = request.locals
            shown = self._rewrites.get(request.location)
            if shown is not None and shown is not _NOT_FOUND:
                self._locals[shown] = request.locals
            while len(self._locals) > self.history_size * 2:
                del self._locals[next(iter(self._locals))]
        else:
            self._locals.pop(request.location, None)
        commit(request.location)

    def _fail(self, request: _middleware.Request, err: BaseException, commit: Callable[[Location], None]) -> None:
        self._failures[request.location] = err
        commit(request.location)

    def _start_navigation(self) -> None:
        """Runs the middleware for the first location (on the first view)."""
        if not self.middleware and not any("middleware" in s.files for s in self.root.walk()):
            self._started = True
            return

        def commit(location: Location) -> None:
            self._entries[self._index] = location

        try:
            self._navigate(self.location, "start", commit)
        finally:
            self._started = True

    def _changed(self) -> None:
        for listener in list(self._listeners):
            listener(self.location)

    # -- keys and mouse ------------------------------------------------------------------------------
    BACK_KEYS = ("alt-left", "cmd-[", "back")
    FORWARD_KEYS = ("alt-right", "cmd-]", "forward")

    def handle_key(self, combo: str) -> bool:
        """Goes back on Alt+Left (Cmd+[ on macOS, the Back key) and forward on Alt+Right; ``True`` if it moved.

        ``RouterApp`` calls it for you; a router inside your own app needs
        ``def on_key(self, combo): return self.router.handle_key(combo) or None``.
        """
        if combo in self.BACK_KEYS:
            return self.back()
        if combo in self.FORWARD_KEYS:
            return self.forward()
        return False

    def _mouse(self, event: Any) -> None:
        button = getattr(event, "button", None)
        if button == "back":
            self.back()
        elif button == "forward":
            self.forward()

    # -- data ---------------------------------------------------------------------------------------
    @staticmethod
    def _params_until(found: _tree.Match, index: int) -> Dict[str, Any]:
        names = {s.param for s in found.segments[:index + 1] if s.param}
        return {k: v for k, v in found.params.items() if k in names}

    @staticmethod
    def _frozen(params: Mapping[str, Any]) -> tuple:
        return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in params.items()))

    def _data_key(self, kind: str, segment: _tree.Segment, params: Mapping[str, Any], location: Location) -> tuple:
        # A layout's data depends on its own params; a page's also on the query.
        return (kind, segment.id, self._frozen(params), location.search if kind == "page" else None)

    def _start(self, key: tuple, loader: Callable[..., Any], params: Mapping[str, Any], location: Location,
               kind: str, previous: Any = _NO_DATA) -> _Entry:
        entry = _Entry(started=time.monotonic(), kind=kind)
        if previous is not _NO_DATA:
            entry.previous, entry.has_previous = previous, True
        available = {"params": dict(params), "query": location.query, "search_params": location.query,
                     "router": self, "locals": self._locals.get(location, {})}

        def run() -> Any:
            from .. import _async

            result = _call_with(loader, available)
            if _async._isawaitable(result):
                result = _async.run(result)
            return result

        def done(future: Any) -> None:
            try:
                entry.value = future.result()
                entry.state = "ok"
            except BaseException as err:  # noqa: BLE001 - shown by the error file
                entry.error = err
                entry.state = "error"
            _redraw()

        with self._lock:
            self._cache[key] = entry
            if len(self._cache) > self.cache_size:
                for old in [k for k, e in self._cache.items() if e.state != "pending"][: len(self._cache) - self.cache_size]:
                    del self._cache[old]
        entry.future = _executor().submit(run)
        entry.future.add_done_callback(done)
        return entry

    def _data(self, route_file: _tree.RouteFile, segment: _tree.Segment, params: Mapping[str, Any],
              location: Location) -> Any:
        loader = route_file.attr("load")
        if loader is None:
            return _NO_DATA
        key = self._data_key(route_file.kind, segment, params, location)
        entry = self._cache.get(key)
        if entry is None:
            entry = self._start(key, loader, params, location, route_file.kind)
        elif entry.stale:
            entry = self._start(key, loader, params, location, route_file.kind,
                                previous=entry.value if entry.state == "ok" else _NO_DATA)
        if entry.state == "pending":
            if entry.has_previous:
                return entry.previous
            raise _Pending(key)
        if entry.state == "error":
            raise entry.error  # type: ignore[misc]
        return entry.value

    def _forget_errors(self, segment: _tree.Segment) -> None:
        """Drops the failed loads of ``segment`` and below, so they run again (an error file's ``reset``)."""
        prefix = segment.id
        if self._failures.pop(self.location, None) is not None:
            self._navigate(self.location, "refresh", lambda _location: None)
        with self._lock:
            for key in [k for k, e in self._cache.items()
                        if e.state == "error" and (k[1] == prefix or k[1].startswith(prefix + "/") or not prefix)]:
                del self._cache[key]

    # -- drawing ------------------------------------------------------------------------------------
    def view(self) -> Any:
        """Draws the current location: the page inside its layouts, templates and boundaries."""
        global _current
        _current = self
        if not self._started:
            self._start_navigation()
        for _attempt in range(10):
            try:
                return self._draw(self.location)
            except Redirect as move:
                target = resolve_href(move.href, self.location)
                if move.push:
                    self._go(target, replace=False)
                else:
                    self._go(target, replace=True)
        raise _tree.RouteError(f"too many redirects (last: {self.location.href})")

    def __pyzed_view__(self) -> Any:  # pragma: no cover - lets a router stand where a widget is expected
        return self.view()

    def _draw(self, location: Location) -> Any:
        root = self.root
        shown = self._rewrites.get(location, location)
        found = None if shown is _NOT_FOUND else _tree.match(root, shown.parts)
        values = {_ROUTER: self, _LOCATION: (location.href, self._index)}
        with _component.provide(**values):
            if self._navigation is not None and self._last_ok is None:
                # the first location waits for an async middleware: the root's loading file, if any
                loading = root.files.get("loading")
                widget = self._render(loading, "loading", {}, location) if loading is not None else _core.space(
                    width="fill", height="fill")
                return widget.on(mouse_down=self._mouse)
            try:
                if found is None:
                    widget = self._level([root], 0, {}, location, missing=True)
                else:
                    widget = self._level(found.segments, 0, found.params, location)
            except _Pending:
                previous = self._last_ok
                if previous is not None and previous != location:
                    try:
                        widget = self._draw_previous(previous)
                    except Exception:  # noqa: BLE001 - nothing better to show
                        widget = _core.space(width="fill", height="fill")
                else:
                    widget = _core.space(width="fill", height="fill")
                return widget.on(mouse_down=self._mouse)
        self._last_ok = location
        return widget.on(mouse_down=self._mouse)

    def _draw_previous(self, location: Location) -> Any:
        shown = self._rewrites.get(location, location)
        found = None if shown is _NOT_FOUND else _tree.match(self.root, shown.parts)
        if found is None:
            return self._level([self.root], 0, {}, location, missing=True)
        return self._level(found.segments, 0, found.params, location)

    def _level(self, segments: List[_tree.Segment], index: int, params: Dict[str, Any], location: Location,
               *, missing: bool = False) -> Any:
        segment = segments[index]
        files = segment.files
        own = self._params_until(_tree.Match(segments, params), index)
        key = (segment.id, self._frozen(own))
        last = index == len(segments) - 1

        layout = files.get("layout")
        layout_data = self._data(layout, segment, own, location) if layout is not None else _NO_DATA
        provided = None
        if layout is not None and layout.attr("provide") is not None:
            provided = _call_with(layout.attr("provide"), {"params": own, "query": location.query,
                                                            "locals": self._locals.get(location, {}),
                                                            "data": None if layout_data is _NO_DATA else layout_data})

        def inner() -> Any:
            if last or missing:
                failure = self._failures.get(location)
                if failure is not None:
                    raise failure  # a middleware failed: the closest error file shows it
            if missing:
                raise NotFound()
            if last:
                return self._page(segment, params, location)
            return self._level(segments, index + 1, params, location)

        def body() -> Any:
            try:
                try:
                    try:
                        with _scope("content", key):
                            return inner()
                    except NotFound:
                        handler = files.get("not_found")
                        if handler is None and index > 0:
                            raise
                        with _scope("not_found", key):
                            self._shown_not_found = (location.href, handler)
                            if handler is None:
                                return _default_not_found()
                            return self._render(handler, "not_found", own, location)
                except _Pending:
                    loading = files.get("loading")
                    if loading is None:
                        raise
                    with _scope("loading", key):
                        return self._render(loading, "loading", own, location)
            except (Redirect, _Pending, NotFound):
                raise
            except Exception as err:  # noqa: BLE001 - shown by the error file
                handler = files.get("error")
                if handler is None and index > 0:
                    raise
                _report(err)
                reset = functools.partial(self._forget_errors, segment)
                with _scope("error", key):
                    if handler is None:
                        return _default_error(err, reset)
                    return self._render(handler, "error", own, location, error=err, reset=reset,
                                        info=_error_info(err))

        if provided:
            with _component.provide(**dict(provided)):
                content = body()
        else:
            content = body()
        template = files.get("template")
        if template is not None:
            with _scope("template", key, location.pathname):
                content = self._render(template, "template", own, location, children=content)
        if layout is not None:
            with _scope("layout", key):
                content = self._render(layout, "layout", own, location, children=content, data=layout_data)
        return content

    def _page(self, segment: _tree.Segment, params: Dict[str, Any], location: Location) -> Any:
        page = segment.files["page"]
        frozen = self._frozen(params)
        if page.is_form:
            return self._form_page(page, (segment.id, frozen))
        data = self._data(page, segment, params, location)
        with _scope("page", segment.id, frozen):
            return self._render(page, "page", params, location, data=data)

    def _render(self, route_file: _tree.RouteFile, kind: str, params: Mapping[str, Any], location: Location,
                **extra: Any) -> Any:
        target = route_file.target()
        if inspect.iscoroutinefunction(target):
            raise TypeError(f"{route_file.path or route_file}: {kind} can't be `async def`; put the awaits in "
                            f"`async def load(params)` and take its result as `data`")
        available: Dict[str, Any] = {"params": dict(params), "query": location.query,
                                     "search_params": location.query, "router": self,
                                     "pathname": location.pathname, "locals": self._locals.get(location, {}),
                                     **extra}
        if available.get("data", None) is _NO_DATA:
            available["data"] = None
        if isinstance(target, type) and issubclass(target, _component.Component):
            props = target.__props__
            kwargs = {k: v for k, v in available.items() if k in props}
            if "children" in kwargs:
                default = props["children"].default
                if isinstance(default, (list, tuple)) or default is _component._MISSING:
                    kwargs["children"] = [kwargs["children"]]
            return target(**kwargs)
        return _as_widget(_call_with(target, available))

    # -- titles ---------------------------------------------------------------------------------------
    def _cached(self, route_file: _tree.RouteFile, segment: _tree.Segment, params: Mapping[str, Any],
                location: Location) -> Tuple[Any, Optional[BaseException]]:
        """The data a ``load`` already gave (``None`` while it runs) and its error, without starting it."""
        if route_file.is_form or route_file.attr("load") is None:
            return None, None
        entry = self._cache.get(self._data_key(route_file.kind, segment, params, location))
        if entry is None:
            return None, None
        if entry.state == "ok":
            return entry.value, None
        return (entry.previous if entry.has_previous else None), entry.error

    def _compute_title(self, location: Location) -> Optional[str]:
        root = self.root
        shown = self._rewrites.get(location, location)
        found = None if shown is _NOT_FOUND else _tree.match(root, shown.parts)
        segments = found.segments if found is not None else [root]
        params = found.params if found is not None else {}
        parts: List[Tuple[str, _tree.RouteFile, Dict[str, Any], Any]] = []
        missing = found is None
        for index, segment in enumerate(segments):
            layout = segment.files.get("layout")
            if layout is not None:
                own = self._params_until(_tree.Match(segments, params), index)
                parts.append(("layout", layout, own, self._cached(layout, segment, own, location)[0]))
        if found is not None:
            page = found.page.files["page"]
            data, error = self._cached(page, found.page, params, location)
            missing = isinstance(error, NotFound)
            parts.append(("page", page, params, data))
        shown = getattr(self, "_shown_not_found", None)
        if shown is not None and shown[0] == location.href:  # the page called pz.not_found() while drawing
            missing = True
        title: Optional[str] = None
        if missing:
            handler = next((s.files["not_found"] for s in reversed(segments) if "not_found" in s.files), None)
            title = _title_of(handler, params, None) if handler is not None else _i18n_text("pyzed.routing.not_found")
            parts = [p for p in parts if p[0] == "layout"]
        template: Optional[str] = None
        for kind, route_file, own, data in reversed(parts):  # the page first, then the layouts upwards
            if title is None:
                title = _title_of(route_file, own, data)  # a layout's template applies to what is inside it
            elif template is None and kind == "layout":
                template = route_file.attr("title_template")
        if title is not None and template:
            title = template.replace("%s", title) if "%s" in template else f"{title} · {template}"
        if title is None:
            title = next((p[1].attr("default_title") for p in parts if p[0] == "layout" and
                          p[1].attr("default_title")), None)
        return title

    # -- forms made in the designer -----------------------------------------------------------------
    def _form_page(self, page: _tree.RouteFile, key: tuple) -> Any:
        hosted = self._forms.get(key)
        if hosted is None:
            hosted = self._forms[key] = _FormPage(page.path, self)  # type: ignore[arg-type]
        return hosted.view()


def _title_of(route_file: _tree.RouteFile, params: Mapping[str, Any], data: Any) -> Optional[str]:
    try:
        title = route_file.attr("title")
        if title is None:
            metadata = route_file.attr("metadata")
            if callable(metadata):
                metadata = _call_with(metadata, {"params": params, "data": data})
            title = (metadata or {}).get("title") if isinstance(metadata, Mapping) else None
        if callable(title):
            title = _call_with(title, {"params": params, "data": data})
    except Exception:  # noqa: BLE001 - a broken title doesn't break the page
        return None
    return None if title is None else str(title)


class _FormPage:
    """A ``page.pzform`` made in Pyzed Design, drawn in the space the layouts leave it."""

    def __init__(self, path: Path, router: Router) -> None:
        from ..designer import model, runtime
        from ..designer.scene import discover_project

        discover_project(path)
        form = model.load(path)
        self.area = _FormArea(router)
        self.runtime = runtime.FormRuntime(form, runtime.load_handlers(path, form), window=self.area, path=path)
        self.started = False

    def view(self) -> Any:
        if not self.started:
            self.started = True
            _component._defer(self.runtime.load)

        def draw(width: float, height: float) -> Any:
            self.area.window_size = (width, height)
            return self.runtime.view()

        return _core.responsive(draw)


class _FormArea:
    """What a form's runtime expects of its window, for a form drawn as a page."""

    def __init__(self, router: Router) -> None:
        self.router = router
        self.window_size: Optional[Tuple[float, float]] = None

    def __getattr__(self, name: str) -> Any:
        window = self.__dict__.get("router").window if "router" in self.__dict__ else None
        if window is None:
            raise AttributeError(name)
        return getattr(window, name)


# -- defaults -------------------------------------------------------------------------------------------
_reported: set = set()


def _i18n_text(key: str) -> str:
    from ..i18n import t

    return t(key)


def _report(err: BaseException) -> None:
    """Prints a page's error once (the error file shows it in the window)."""
    marker = (type(err), str(err))
    if marker in _reported:
        return
    _reported.add(marker)
    print("pyzed.routing: a route failed:\n" + "".join(traceback.format_exception(type(err), err, err.__traceback__)),
          file=sys.stderr)


def _error_info(err: BaseException) -> Any:
    from ..ui.errors import ErrorInfo

    return ErrorInfo.from_exception(err)


def _default_not_found() -> Any:
    from .. import ui
    from ..i18n import t

    return ui.empty_state(t("pyzed.routing.not_found"), t("pyzed.routing.not_found_description"), icon="map-pin-off")


def _default_error(err: BaseException, reset: Callable[[], Any]) -> Any:
    from .. import ui
    from ..i18n import t

    return ui.error_card(_error_info(err), actions=[ui.button(t("pyzed.routing.try_again"), reset, icon="rotate-ccw",
                                                              size="sm")])
