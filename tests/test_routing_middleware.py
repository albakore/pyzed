"""Middleware of ``pyzed.routing``: redirects, rewrites, guards, matchers, locals and async middleware."""

from __future__ import annotations

import asyncio
import textwrap

import pytest

import pyzed as pz
from pyzed import component
from pyzed.routing import Router
from pyzed.routing._middleware import Request, compile_matcher


class Owner:
    """Stands for the window a router draws in."""


def draw(router):
    with component.render_pass(Owner()):
        return router.view()


def shows(name, seen):
    def page():
        seen.append(name)
        return pz.text(name)

    return page


@pytest.mark.parametrize(("pattern", "yes", "no"), [
    ("/about", ["/about", "/about/"], ["/", "/about/team"]),
    ("/products/:id", ["/products/3"], ["/products", "/products/3/reviews"]),
    ("/products/[id]", ["/products/3"], ["/products"]),
    ("/docs/:path*", ["/docs", "/docs/a", "/docs/a/b"], ["/doc", "/"]),
    ("/docs/[[...path]]", ["/docs", "/docs/a/b"], ["/"]),
    ("/docs/:path+", ["/docs/a", "/docs/a/b"], ["/docs"]),
    ("/docs/[...path]", ["/docs/a"], ["/docs"]),
    ("/docs/:page?", ["/docs", "/docs/a"], ["/docs/a/b"]),
    ("/users/*/posts", ["/users/7/posts"], ["/users/posts"]),
    ("/admin/**", ["/admin", "/admin/a/b"], ["/administrator"]),
    ("/", ["/"], ["/a"]),
    ("^/(?!login).*", ["/", "/account"], ["/login"]),
])
def test_matcher_patterns(pattern, yes, no):
    regex = compile_matcher(pattern)
    assert all(regex.match(p) for p in yes), pattern
    assert not any(regex.match(p) for p in no), pattern


def test_redirect_from_middleware_and_the_request():
    seen, requests = [], []
    session = {"user": None}

    def auth(request):
        requests.append((request.pathname, request.action, request.route, dict(request.params),
                         request.previous.href if request.previous else None))
        if request.matches("/account/:path*") and session["user"] is None:
            return request.redirect(f"/login?next={request.pathname}")

    router = Router({"/": shows("home", seen), "/login": shows("login", seen),
                     "/account/[tab]": shows("account", seen)}, middleware=auth)
    draw(router)
    assert requests == [("/", "start", "/", {}, None)]
    router.push("/account/orders")
    assert router.url == "/login?next=/account/orders" and router.history == ["/", "/login?next=/account/orders"]
    assert requests[1] == ("/account/orders", "push", "/account/[tab]", {"tab": "orders"}, "/")
    session["user"] = "kev"
    router.push("/account/orders")
    assert router.pathname == "/account/orders"
    draw(router)
    assert seen[-1] == "account"


def test_redirect_at_start_replaces_the_first_entry():
    router = Router({"/": lambda: "home", "/login": lambda: "login"},
                    middleware=lambda pathname: pz.redirect("/login") if pathname == "/" else None)
    draw(router)
    assert router.history == ["/login"]


def test_returning_false_stays_and_back_can_be_stopped():
    dirty = {"form": False}

    def guard(request):
        if request.previous is not None and request.previous.pathname == "/edit" and dirty["form"]:
            return False

    router = Router({"/": lambda: "home", "/edit": lambda: "edit", "/other": lambda: "other"}, middleware=[guard])
    draw(router)
    router.push("/edit")
    dirty["form"] = True
    router.push("/other")
    assert router.pathname == "/edit"
    assert router.back() is True and router.pathname == "/edit"  # the entry exists, the guard kept it
    dirty["form"] = False
    router.back()
    assert router.pathname == "/" and router.history == ["/", "/edit"]


def test_rewrite_keeps_the_address_and_not_found():
    seen = []

    def maintenance(request):
        if request.pathname.startswith("/shop"):
            return pz.rewrite("/maintenance")
        if request.pathname == "/secret":
            pz.not_found()

    router = Router({"/": shows("home", seen), "/shop": shows("shop", seen),
                     "/maintenance": {"page": shows("maintenance", seen), "title": "Back soon"},
                     "/secret": shows("secret", seen)}, middleware=maintenance)
    draw(router)
    router.push("/shop")
    draw(router)
    assert router.pathname == "/shop" and seen[-1] == "maintenance" and router.title == "Back soon"
    router.push("/secret")
    draw(router)
    assert seen[-1] != "secret" and router.title == "Page not found"


def test_locals_reach_pages_layouts_and_loads():
    got = []

    def attach(request):
        request.locals["user"] = "kev"

    def load(locals):  # noqa: A002 - the name pages ask for
        got.append(("load", locals["user"]))
        return 1

    def layout(children, locals):  # noqa: A002
        got.append(("layout", locals["user"]))
        return children

    def page(data, locals):  # noqa: A002
        got.append(("page", locals["user"], data))
        return "ok"

    router = Router({"/": {"layout": layout, "page": page, "load": load}}, middleware=attach)
    draw(router)
    router.wait(5)
    draw(router)
    assert ("load", "kev") in got and ("layout", "kev") in got and ("page", "kev", 1) in got


def test_middleware_errors_show_the_error_file():
    errors = []

    def broken(request):
        if request.pathname == "/x":
            raise RuntimeError("no session")

    def error(error, reset):
        errors.append(str(error))
        return "error"

    router = Router({"/": {"page": lambda: "home", "error": error}, "/x": lambda: "x"}, middleware=broken)
    draw(router)
    router.push("/x")
    draw(router)
    assert errors == ["no session"]


def test_async_middleware_waits_then_goes_on():
    calls = []

    async def slow(request):
        await asyncio.sleep(0.05)
        calls.append(request.pathname)
        if request.pathname == "/private":
            return request.redirect("/")

    router = Router({"/": lambda: "home", "/a": lambda: "a", "/private": lambda: "p"}, middleware=slow)
    draw(router)
    assert router.pending
    assert router.wait(5)
    assert calls == ["/"]
    router.push("/a")
    assert router.pathname == "/" and router.pending  # the page stays until the middleware answers
    assert router.wait(5) and router.pathname == "/a"
    router.push("/private")
    router.push("/a")  # a newer navigation wins over the one still waiting
    assert router.wait(5)
    assert router.pathname == "/a"


def test_refresh_runs_middleware_again():
    calls = []
    router = Router({"/": lambda: "home"}, middleware=lambda action: calls.append(action))
    draw(router)
    router.refresh()
    assert calls == ["start", "refresh"]


def test_middleware_files_nest_and_use_their_matcher(tmp_path):
    app = tmp_path / "app"
    (app / "admin" / "users").mkdir(parents=True)
    (app / "page.py").write_text("def page():\n    return 'home'\n")
    (app / "admin" / "users" / "page.py").write_text("def page(locals):\n    return locals['who']\n")
    (app / "middleware.py").write_text(textwrap.dedent("""
        calls = []
        matcher = ["/admin/:path*"]

        def middleware(request):
            calls.append(("root", request.pathname))
            request.locals["who"] = "root"
    """))
    (app / "admin" / "middleware.py").write_text(textwrap.dedent("""
        def middleware(request, locals):
            locals["who"] += "+admin"
            if request.query.get("deny"):
                return request.redirect("/")
    """))
    router = Router(app)
    draw(router)
    router.push("/admin/users")
    draw(router)
    root = router.root.files["middleware"].module
    assert root.calls == [("root", "/admin/users")]  # the matcher skipped "/"
    assert router._locals[router.location]["who"] == "root+admin"
    router.push("/admin/users?deny=1")
    assert router.pathname == "/"


def test_decorator_and_router_app_middleware():
    seen = []

    @pz.middleware(matcher="/admin/:path*")
    def admins(request):
        seen.append(request.pathname)

    class Shop(pz.RouterApp):
        routes = {"/": lambda: "home", "/admin": lambda: "admin"}
        middleware = [admins]

    app = Shop()
    draw(app.router)
    app.router.push("/admin")
    assert seen == ["/admin"] and isinstance(Request, type)


def test_bad_return_value_is_explained():
    router = Router({"/": lambda: "home", "/a": lambda: "a"}, middleware=lambda: "/a")
    with pytest.raises(TypeError, match="request.redirect"):
        draw(router)
