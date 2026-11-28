"""Routes in folders, like Next.js' App Router: each folder of ``app/`` is a part of the URL.

::

    app/
        layout.py            # wraps every page; keeps its state while you navigate
        page.py              # /
        loading.py           # shown while a page's `load` runs
        error.py             # shown when a page fails (with a "try again")
        not_found.py         # unknown URLs and pz.not_found()
        about/page.py        # /about
        (shop)/              # a group: not part of the URL
            products/
                page.py      # /products
                [id]/page.py # /products/3  -> params["id"] == "3"
        docs/[...slug]/page.py   # /docs/a/b  -> params["slug"] == ["a", "b"]

Each file defines a function named like it (or a ``pz.Component`` subclass: ``Page``, ``Layout``...).
Functions take only the arguments they name: ``params``, ``query``, ``data``, ``children`` (layouts and
templates), ``error`` and ``reset`` (error files), ``router`` and ``pathname``::

    # app/(shop)/products/[id]/page.py
    import pyzed as pz
    from pyzed import ui

    async def load(params):                 # runs off the UI thread; loading.py shows meanwhile
        product = await api.product(params["id"])
        if product is None:
            pz.not_found()
        return product

    def title(data):
        return data.name

    def page(data, query):
        return pz.column([ui.heading(data.name), pz.link("/products", "← All products")])

Start the app with ``pz.run(pz.RouterApp("app"))``, or keep a ``pz.Router`` in your own app and return
``self.router.view()`` from its ``view()``. Navigate with ``pz.link(href, content)`` and
``pz.use_router()`` (``push``, ``replace``, ``back``, ``forward``, ``refresh``, ``prefetch``); read
where you are with ``use_pathname()``, ``use_params()`` and ``use_search_params()``.

Locations are URLs (``/products/3?tab=reviews#top``), so a route maps to the same address on the web.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .. import _core
from .. import component as _component
from .. import i18n as _i18n
from ..app import App
from .router import (Location, NotFound, Redirect, Router, SearchParams, not_found, redirect,  # noqa: F401
                     resolve_href)
from .tree import FILES, Match, RouteError, RouteFile, Segment, build_href, from_mapping, parse_name, scan  # noqa: F401
from . import router as _router

__all__ = ["Location", "NotFound", "Redirect", "Router", "RouterApp", "SearchParams", "RouteError", "FILES",
           "build_href", "link", "nav_link", "not_found", "redirect", "use_params", "use_pathname", "use_router",
           "use_search_params"]

_i18n.add("en", {"pyzed": {"routing": {
    "not_found": "Page not found", "not_found_description": "There is nothing at this address.",
    "try_again": "Try again", "back": "Back", "forward": "Forward"}}})
_i18n.add("es", {"pyzed": {"routing": {
    "not_found": "Página no encontrada", "not_found_description": "No hay nada en esta dirección.",
    "try_again": "Reintentar", "back": "Atrás", "forward": "Adelante"}}})


# -- hooks -------------------------------------------------------------------------------------------------
def use_router() -> Router:
    """The router drawing this view (``useRouter()``): ``use_router().push("/cart")``.

    Outside a view (a callback, a form's handler) it is the router that drew last.
    """
    found = _component.use_context(_router._ROUTER)
    _component.use_context(_router._LOCATION)  # a component that reads it draws again when the location changes
    found = found or _router._current
    if found is None:
        raise RuntimeError("no router is drawing: start the app with pz.RouterApp(...) or draw a pz.Router")
    return found


def use_pathname() -> str:
    """The current path, like ``/products/3`` (``usePathname()``)."""
    return use_router().pathname


def use_params() -> Dict[str, Union[str, List[str]]]:
    """The parameters of the current page: ``{"id": "3"}`` for ``/products/[id]`` (``useParams()``)."""
    return use_router().params


def use_search_params() -> SearchParams:
    """The current query as a dict, ``get_all(key)`` for repeated keys (``useSearchParams()``)."""
    return use_router().query


# -- links -------------------------------------------------------------------------------------------------
def link(href: Any, content: Any = None, *, replace: bool = False, prefetch: bool = True,
         router: Optional[Router] = None, size: Optional[float] = None) -> Any:
    """A link to ``href`` (``<Link>`` in Next.js): text in the accent color, or any widget, that navigates
    when clicked.

    ``href`` is a path (``"/products/3"``), relative to the current page (``"../"``, ``"reviews"``), a
    query (``"?page=2"``) or ``("/users/[id]", {"id": 7})``. ``replace`` replaces the history entry
    instead of adding one; ``prefetch`` starts the page's ``load`` when the mouse is over the link.
    """
    from ..theme import current

    found = router or use_router()
    target = resolve_href(href, found.location)
    if content is None:
        content = target.href
    if isinstance(content, str):
        t = current()
        text = _core.text(content, color=t.text_accent, size=size) if size else _core.text(content, color=t.text_accent)
        widget = text.style(hover={"color": t.accent}, transition=120)
    else:
        widget = content if isinstance(content, _core.Widget) else _core.container(content)

    def go() -> None:
        (found.replace if replace else found.push)(target)

    handlers: Dict[str, Any] = {"click": go}
    if prefetch:
        handlers["mouse_enter"] = lambda: found.prefetch(target)
    return widget.on(cursor="pointer", **handlers)


def nav_link(href: Any, label: str, *, icon: Optional[str] = None, exact: Optional[bool] = None,
             router: Optional[Router] = None, description: Optional[str] = None) -> Any:
    """A row for a sidebar or a menu (``ui.list_item``) that goes to ``href`` and shows as selected while
    that page, or a page under it, is open (``exact=True``: only that page; the root ``/`` is exact)."""
    from .. import ui

    found = router or use_router()
    target = resolve_href(href, found.location)
    exact = target.pathname == "/" if exact is None else exact
    return ui.list_item(label, lambda: found.push(target), icon=icon, height=30,
                        selected=found.is_active(target, exact=exact), description=description)


# -- the app ---------------------------------------------------------------------------------------------
class RouterApp(App):
    """An app whose window shows its routes::

        pz.run(pz.RouterApp("app", title="Shop"))

        class Shop(pz.RouterApp):           # or subclass it
            routes = "app"
            title = "Shop"
            size = (1100, 720)

    The window's title follows the page (its ``title`` or ``metadata``, with the root layout's
    ``title_template``); the app's own ``title`` is used when the page has none. Alt+Left/Right,
    the mouse's back and forward buttons and Android's back button move in the history.
    ``on_navigate(location)`` runs after every navigation.
    """

    routes: Any = "app"
    initial: str = "/"
    _pyzed_defined_in: Optional[str] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        try:  # the file whose body defines the class: a relative ``routes`` folder is next to it
            cls._pyzed_defined_in = sys._getframe(1).f_globals.get("__file__")
        except ValueError:  # pragma: no cover
            cls._pyzed_defined_in = None

    def __init__(self, routes: Any = None, *, title: Optional[str] = None, initial: Optional[str] = None,
                 **options: Any) -> None:
        source = routes if routes is not None else type(self).routes
        if isinstance(source, str) and not Path(source).is_absolute():
            defined = type(self)._pyzed_defined_in if type(self) is not RouterApp else None
            where = Path(defined).resolve().parent / source if defined else None
            if where is not None and where.is_dir():
                source = where
        self.router = Router(source, initial=initial or type(self).initial, _depth=2, **options)
        self.router.window = self
        self.router.listen(self._navigated)
        declared = getattr(type(self), "title", None)
        self.app_title = title if title is not None else (declared if isinstance(declared, str) else "Pyzed")
        self.title = self._window_title  # type: ignore[assignment]

    def _window_title(self) -> str:
        return self.router.title or self.app_title

    def _navigated(self, location: Location) -> None:
        hook = getattr(self, "on_navigate", None)
        if callable(hook):
            hook(location)

    def view(self) -> Any:
        return self.router.view()

    def on_key(self, combo: str) -> Any:
        return True if self.router.handle_key(combo) else None

    def on_back(self) -> Any:
        """Android's back button goes back in the history; on the first page the app goes to the background."""
        return True if self.router.back() else False
