"""Middleware: code that runs before every navigation, like Next.js' ``middleware.ts``.

A ``middleware.py`` in a folder of ``app/`` runs for every address below that folder, outer folders
first; middleware given to the router in code (``Router(..., middleware=[auth])``) runs before them.
Each one gets a :class:`Request` and decides::

    # app/middleware.py
    import pyzed as pz

    import session

    matcher = ["/account/:path*", "/orders/:path*"]     # optional: only these addresses


    def middleware(request):
        if session.user is None:
            return request.redirect(f"/login?next={request.pathname}")
        request.locals["user"] = session.user           # pages and loads can take `locals`

What it returns:

- ``None`` (or nothing): go on to the next middleware, then show the page,
- ``request.redirect(href)`` or ``pz.redirect(href)``: go to another address instead,
- ``request.rewrite(href)`` or ``pz.rewrite(href)``: keep the address but show another route,
- ``False``: stay where you are (an unsaved form, say); ``pz.not_found()`` shows the not found page.

``async def middleware`` runs on Pyzed's loop: the current page stays until it answers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Pattern, Sequence, Union

if TYPE_CHECKING:  # pragma: no cover
    from .router import Location, Router, SearchParams

__all__ = ["Request", "Rewrite", "compile_matcher", "middleware", "rewrite"]

#: What a navigation was: the first location, a push, a replace, moving in the history or a refresh.
ACTIONS = ("start", "push", "replace", "back", "forward", "refresh")


class Rewrite(Exception):
    """Raised (or returned) by middleware to show the route at ``href`` while the address stays."""

    def __init__(self, href: str) -> None:
        super().__init__(href)
        self.href = href


def rewrite(href: str) -> "Rewrite":
    """In middleware: keeps the address but shows the route at ``href`` (``NextResponse.rewrite``).

    Return it, or raise it: ``return pz.rewrite("/maintenance")``.
    """
    return Rewrite(href)


@dataclass
class Request:
    """A navigation that middleware can let through, send elsewhere or stop.

    ``location`` is where it goes (``pathname``, ``query``, ``hash`` and ``href`` are its parts),
    ``previous`` where the router is now (``None`` at the start), ``action`` what started it (``"start"``,
    ``"push"``, ``"replace"``, ``"back"``, ``"forward"`` or ``"refresh"``), ``route`` the pattern that
    answers it (``"/products/[id]"``, ``None`` when no page does) and ``params`` its values.
    ``locals`` is a dict the pages, layouts and ``load`` functions of that location receive as ``locals``.
    """

    location: "Location"
    previous: Optional["Location"]
    action: str
    router: "Router"
    route: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    locals: Dict[str, Any] = field(default_factory=dict)

    @property
    def pathname(self) -> str:
        """The path it goes to: ``/products/3``."""
        return self.location.pathname

    @property
    def query(self) -> "SearchParams":
        """The query of the address as a dict."""
        return self.location.query

    search_params = query

    @property
    def hash(self) -> str:
        """The part after ``#``."""
        return self.location.hash

    @property
    def href(self) -> str:
        """The whole address: ``/products/3?tab=reviews``."""
        return self.location.href

    url = href

    def redirect(self, href: str, *, push: bool = False) -> Any:
        """Goes to ``href`` instead (return it). ``push=True`` keeps the address it came from in the history."""
        from .router import Redirect

        return Redirect(href, push=push)

    def rewrite(self, href: str) -> Rewrite:
        """Shows the route at ``href`` while the address stays (return it)."""
        return Rewrite(href)

    def matches(self, *patterns: str) -> bool:
        """Whether the address matches one of ``patterns`` (same syntax as ``matcher``)."""
        return any(compile_matcher(p).match(self.pathname) for p in patterns)


_TOKEN = re.compile(r"^:(\w+)([*+?]?)$")


def compile_matcher(pattern: str) -> Pattern[str]:
    """A regular expression for a ``matcher`` pattern.

    Patterns use Next.js' syntax or the folders' own: ``/about`` (that address), ``/products/:id``
    or ``/products/[id]`` (one part), ``/docs/:path*`` or ``/docs/[[...path]]`` (zero or more parts),
    ``/docs/:path+`` or ``/docs/[...path]`` (one or more), ``*`` (any one part) and ``**`` (anything
    below). A pattern that starts with ``^`` is a regular expression for the whole path.
    """
    if pattern.startswith("^"):
        return re.compile(pattern)
    out = ""
    for part in (p for p in pattern.split("/") if p):
        token = _TOKEN.match(part)
        if token is not None:
            mode = token.group(2)
        elif part.startswith("[[...") and part.endswith("]]"):
            mode = "*"
        elif part.startswith("[...") and part.endswith("]"):
            mode = "+"
        elif part.startswith("[") and part.endswith("]"):
            mode = ""
        elif part == "**":
            mode = "*"
        elif part == "*":
            out += "/[^/]+"
            continue
        else:
            out += "/" + re.escape(part)
            continue
        out += {"": "/[^/]+", "?": "(?:/[^/]+)?", "+": "(?:/[^/]+)+", "*": "(?:/[^/]+)*"}[mode]
    return re.compile("^" + out + "/?$" if out else "^/?$")


Matcher = Union[str, Sequence[str], Callable[[Request], bool], None]


def applies(matcher: Matcher, request: Request) -> bool:
    """Whether middleware with ``matcher`` runs for ``request`` (no matcher: always)."""
    if matcher is None:
        return True
    if callable(matcher):
        return bool(matcher(request))
    patterns: List[str] = [matcher] if isinstance(matcher, str) else list(matcher)
    return any(compile_matcher(p).match(request.pathname) for p in patterns)


def middleware(function: Optional[Callable[..., Any]] = None, *, matcher: Matcher = None) -> Any:
    """Marks a function as middleware for ``Router(middleware=[...])``, with the addresses it runs for::

        @pz.middleware(matcher="/admin/:path*")
        def admins_only(request):
            if not session.is_admin:
                return request.redirect("/")

    A plain function works too; ``matcher`` only narrows where it runs.
    """
    def mark(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.matcher = matcher  # type: ignore[attr-defined]
        return fn

    return mark(function) if function is not None else mark
