"""Routes in folders (``pyzed.routing``): matching, history, layouts, loading, errors and the CLI template."""

from __future__ import annotations

import asyncio
import sys
import textwrap
import threading
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import component, routing
from pyzed.routing import Location, RouteError, Router, resolve_href
from pyzed.routing import tree as rtree


class Owner:
    """Stands for the window a router draws in (components keep their state on it)."""


def draw(router, owner=None):
    """One ``view()`` like the runtime does: inside a render pass, so components keep their state."""
    owner = owner if owner is not None else Owner()
    with component.render_pass(owner):
        return router.view()


def settle(router, owner):
    draw(router, owner)
    assert router.wait(5)
    return draw(router, owner)


# -- names and matching -----------------------------------------------------------------------------------
def test_segment_names():
    assert rtree.parse_name("products") == ("static", None)
    assert rtree.parse_name("[id]") == ("dynamic", "id")
    assert rtree.parse_name("[...slug]") == ("catch_all", "slug")
    assert rtree.parse_name("[[...slug]]") == ("optional_catch_all", "slug")
    assert rtree.parse_name("(shop)") == ("group", None)
    for bad in ("[a-b]", "[x", "a]b", "[...]"):
        with pytest.raises(RouteError):
            rtree.parse_name(bad)


def page_named(name):
    return lambda: pz.text(name)


def test_static_wins_over_dynamic_over_catch_all():
    root = rtree.from_mapping({
        "/": page_named("home"),
        "/blog/new": page_named("new"),
        "/blog/[slug]": page_named("post"),
        "/blog/[slug]/[...rest]": page_named("rest"),
        "/(marketing)/about": page_named("about"),
        "/shop/[[...path]]": page_named("shop"),
    })
    def where(path):
        found = rtree.match(root, [p for p in path.split("/") if p])
        return (found.page.pattern, found.params) if found else None

    assert where("/") == ("/", {})
    assert where("/blog/new") == ("/blog/new", {})
    assert where("/blog/hello") == ("/blog/[slug]", {"slug": "hello"})
    assert where("/blog/hello/a/b") == ("/blog/[slug]/[...rest]", {"slug": "hello", "rest": ["a", "b"]})
    assert where("/about") == ("/about", {})  # groups are not part of the URL
    assert where("/shop") == ("/shop/[[...path]]", {"path": []})
    assert where("/shop/a/b") == ("/shop/[[...path]]", {"path": ["a", "b"]})
    assert where("/blog") is None
    assert where("/marketing/about") is None


def test_conflicting_trees_are_refused():
    with pytest.raises(RouteError, match="both answer"):
        rtree.from_mapping({"/(a)/about": page_named("a"), "/(b)/about": page_named("b")})
    with pytest.raises(RouteError, match="both answer"):
        rtree.from_mapping({"/u/[id]": page_named("a"), "/u/[name]": page_named("b")})
    with pytest.raises(RouteError, match="same parameter"):
        rtree.from_mapping({"/[id]/x/[id]": page_named("a")})
    with pytest.raises(RouteError, match="last one"):
        rtree.from_mapping({"/[...all]/edit": page_named("a")})
    with pytest.raises(RouteError, match="must start with /"):
        rtree.from_mapping({"about": page_named("a")})


def test_build_href():
    assert rtree.build_href("/users/[id]", {"id": 7}) == "/users/7"
    assert rtree.build_href("/(shop)/docs/[...slug]", {"slug": ["a", "b c"]}) == "/docs/a/b%20c"
    assert rtree.build_href("/docs/[[...slug]]") == "/docs"
    with pytest.raises(KeyError):
        rtree.build_href("/users/[id]", {})


# -- locations -------------------------------------------------------------------------------------------
def test_resolve_href_like_a_browser():
    here = Location("/products/3", "tab=reviews")
    assert resolve_href("/cart", here) == Location("/cart")
    assert resolve_href("reviews", here) == Location("/products/reviews")
    assert resolve_href("../about", here) == Location("/about")
    assert resolve_href("?page=2", here) == Location("/products/3", "page=2")
    assert resolve_href("#top", here) == Location("/products/3", "tab=reviews", "top")
    assert resolve_href("/a//b/./c/", here).pathname == "/a/b/c"
    assert resolve_href(("/users/[id]", {"id": "x y"}), here).pathname == "/users/x%20y"
    assert resolve_href("/files/x y").parts == ["files", "x y"]
    with pytest.raises(ValueError):
        resolve_href("https://example.com")


def test_search_params():
    query = Location("/", "tag=a&tag=b&q=hi&empty=").query
    assert query["tag"] == "a" and query.get_all("tag") == ["a", "b"]
    assert query["empty"] == "" and str(query) == "tag=a&tag=b&q=hi&empty="


# -- history ---------------------------------------------------------------------------------------------
def test_history_push_replace_back_forward():
    router = Router({"/": page_named("home"), "/a": page_named("a"), "/b": page_named("b")})
    moves = []
    stop = router.listen(lambda loc: moves.append(loc.href))
    assert not router.can_go_back and router.back() is False
    router.push("/a")
    router.push("/b")
    assert router.history == ["/", "/a", "/b"] and router.index == 2
    assert router.back() and router.pathname == "/a" and router.can_go_forward
    router.push("/b?x=1")  # pushing drops the forward entries, like a browser
    assert router.history == ["/", "/a", "/b?x=1"] and not router.can_go_forward
    router.replace("/a")
    assert router.history == ["/", "/a", "/a"]
    assert router.go(-2) and router.pathname == "/"
    assert router.forward() and router.index == 1
    router.push("/a")  # the same location: nothing happens
    assert len(router.history) == 3
    stop()
    router.push("/b")
    assert moves == ["/a", "/b", "/a", "/b?x=1", "/a", "/", "/a"]


def test_keys_and_mouse_buttons_move_in_history():
    router = Router({"/": page_named("home"), "/a": page_named("a")})
    router.push("/a")
    assert router.handle_key("alt-left") and router.pathname == "/"
    assert router.handle_key("alt-right") and router.pathname == "/a"
    assert router.handle_key("ctrl-s") is False
    router._mouse(type("E", (), {"button": "back"})())
    assert router.pathname == "/"
    router._mouse(type("E", (), {"button": "forward"})())
    assert router.pathname == "/a"


def test_is_active_and_params():
    router = Router({"/": page_named("h"), "/docs/[...slug]": page_named("d")}, initial="/docs/intro/start")
    assert router.params == {"slug": ["intro", "start"]}
    assert router.is_active("/docs") and not router.is_active("/docs", exact=True)
    assert router.is_active("/docs/intro/start", exact=True)
    assert not router.is_active("/")  # the root is only active on itself
    assert router.routes() == ["/", "/docs/[...slug]"]


# -- drawing ---------------------------------------------------------------------------------------------
def test_page_inside_layouts_with_only_the_arguments_it_asks_for():
    calls = []

    def root_layout(children):
        calls.append(("root", children))
        return pz.column([children])

    def user_layout(children, params):
        calls.append(("user", dict(params)))
        return children

    def user_page(params, query, pathname):
        calls.append(("page", dict(params), dict(query), pathname))
        return "plain text becomes a text widget"

    router = Router({"/": {"layout": root_layout, "page": page_named("home")},
                     "/users/[id]": {"layout": user_layout},
                     "/users/[id]/posts": user_page}, initial="/users/7/posts?sort=new")
    widget = draw(router)
    assert isinstance(widget, pz.Widget)
    assert [c[0] for c in calls] == ["page", "user", "root"]  # drawn from the inside out
    assert calls[0] == ("page", {"id": "7"}, {"sort": "new"}, "/users/7/posts")
    assert calls[1] == ("user", {"id": "7"})


def test_layout_keeps_its_state_template_and_page_start_over():
    made = []

    class Layout(pz.Component):
        designer = False
        children: list = ()
        clicks = pz.state(0)

        def setup(self):
            made.append("layout")

        def render(self):
            return pz.column(self.children)

    class Template(pz.Component):
        designer = False
        children: list = ()

        def setup(self):
            made.append("template")

        def render(self):
            return pz.column(self.children)

    class Page(pz.Component):
        designer = False
        params: dict = {}

        def setup(self):
            made.append("page " + self.params["id"])

        def render(self):
            return pz.text(self.params["id"])

    router = Router({"/": {"layout": Layout, "page": page_named("home")},
                     "/items": {"template": Template, "page": page_named("list")},
                     "/items/[id]": Page}, initial="/items/1")
    owner = Owner()
    draw(router, owner)
    assert made == ["page 1", "template", "layout"]
    layout = next(c for c in owner._pyzed_components.values() if isinstance(c, Layout))
    layout.clicks = 5
    draw(router, owner)  # drawing again creates nothing
    assert made == ["page 1", "template", "layout"]
    router.push("/items/2")
    draw(router, owner)
    assert made[3:] == ["page 2", "template"]  # a new page and template; the layout is the same
    assert next(c for c in owner._pyzed_components.values() if isinstance(c, Layout)) is layout
    assert layout.clicks == 5
    router.push("/items/2?view=grid")  # only the query changed: same page, same template
    draw(router, owner)
    assert made[5:] == []


def test_async_load_shows_loading_then_the_page():
    gate = threading.Event()
    seen = []

    async def load(params):
        await asyncio.get_running_loop().run_in_executor(None, gate.wait)
        return {"name": f"Product {params['id']}"}

    def loading():
        seen.append("loading")
        return pz.text("…")

    def page(data):
        seen.append(("page", data["name"]))
        return pz.text(data["name"])

    router = Router({"/": page_named("home"), "/p/[id]": {"page": page, "load": load, "loading": loading}},
                    initial="/p/3")
    owner = Owner()
    draw(router, owner)
    assert seen == ["loading"] and router.pending
    gate.set()
    settle(router, owner)
    assert seen[-1] == ("page", "Product 3") and not router.pending


def test_sync_load_runs_off_the_ui_thread():
    threads = []

    def load(params):
        threads.append(threading.current_thread().name)
        return params["id"].upper()

    router = Router({"/[id]": {"page": lambda data: pz.text(data), "load": load}}, initial="/abc")
    settle(router, Owner())
    assert threads and threads[0].startswith("pyzed-route-load")


def test_without_loading_file_the_previous_page_stays_while_loading():
    seen = []
    gate = threading.Event()

    def slow(params):
        gate.wait(5)
        return params["id"]

    router = Router({"/": lambda: seen.append("home") or pz.text("home"),
                     "/p/[id]": {"page": lambda data: seen.append(("p", data)) or pz.text(data), "load": slow}})
    owner = Owner()
    draw(router, owner)
    router.push("/p/1")
    draw(router, owner)
    assert seen == ["home", "home"]  # the old page while the new one loads, like Next.js
    gate.set()
    settle(router, owner)
    assert seen[-1] == ("p", "1")


def test_errors_go_to_the_closest_error_file_and_reset_retries():
    attempts = []
    shown = []

    def load():
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("offline")
        return "ok"

    def error(error, reset):
        shown.append((type(error).__name__, str(error)))
        shown.append(reset)
        return pz.text("error")

    router = Router({"/": {"page": page_named("home"), "error": lambda error: pz.text("root error")},
                     "/shop": {"error": error},
                     "/shop/cart": {"page": lambda data: shown.append(data) or pz.text(data), "load": load}},
                    initial="/shop/cart")
    owner = Owner()
    settle(router, owner)
    assert shown[0] == ("ConnectionError", "offline")
    shown[1]()  # "try again"
    settle(router, owner)
    assert shown[-1] == "ok" and len(attempts) == 2


def test_render_errors_and_the_default_error():
    def broken():
        raise ValueError("boom")

    router = Router({"/": broken})
    assert isinstance(draw(router), pz.Widget)  # the built-in error card, not a crash


def test_not_found_from_load_and_unknown_urls():
    shown = []

    async def load(params):
        pz.not_found()

    router = Router({
        "/": {"page": page_named("home"),
              "not_found": lambda pathname: shown.append(("root", pathname)) or pz.text("404")},
        "/p": {"not_found": lambda: shown.append("p") or pz.text("no product")},
        "/p/[id]": {"page": page_named("x"), "load": load},
    }, initial="/p/9")
    owner = Owner()
    settle(router, owner)
    assert shown == ["p"]
    router.push("/nowhere/at/all")
    draw(router, owner)
    assert shown[-1] == ("root", "/nowhere/at/all")
    assert router.title is None


def test_default_not_found_without_files():
    router = Router({"/": page_named("home")}, initial="/missing")
    assert isinstance(draw(router), pz.Widget)
    assert router.title == "Page not found"


def test_redirect_replaces_the_entry():
    def old():
        pz.redirect("/new")

    router = Router({"/": page_named("home"), "/old": old, "/new": page_named("new")})
    router.push("/old")
    draw(router)
    assert router.pathname == "/new" and router.history == ["/", "/new"]


def test_async_page_is_explained():
    async def page():
        return pz.text("x")

    router = Router({"/": page})
    draw(router)  # the default error card says what to do
    with pytest.raises(TypeError, match="load"):
        router._render(router.root.files["page"], "page", {}, router.location)


def test_titles_metadata_and_template():
    router = Router({
        "/": {"page": page_named("home"), "title": "Home"},
        "/p/[id]": {"page": page_named("p"), "load": lambda params: {"name": "Lamp"},
                    "metadata": lambda data: {"title": data["name"]}},
    })
    draw(router)
    assert router.title == "Home"
    router.push("/p/1")
    settle(router, Owner())
    assert router.title == "Lamp"


def test_refresh_keeps_the_old_data_while_loading_again():
    count = []
    gate = threading.Event()
    gate.set()

    def load():
        gate.wait(5)
        count.append(1)
        return len(count)

    seen = []
    router = Router({"/": {"page": lambda data: seen.append(data) or pz.text(str(data)), "load": load}})
    owner = Owner()
    settle(router, owner)
    gate.clear()
    router.refresh()
    draw(router, owner)
    assert seen[-1] == 1  # still the old data, no loading flash
    gate.set()
    settle(router, owner)
    assert seen[-1] == 2


def test_prefetch_starts_the_load():
    started = []
    router = Router({"/": page_named("home"), "/p/[id]": {"page": page_named("p"),
                                                          "load": lambda params: started.append(params["id"])}})
    router.prefetch("/p/5")
    router.wait(5)
    assert started == ["5"]
    router.push("/p/5")
    draw(router)
    router.wait(5)
    assert started == ["5"]  # still fresh: not loaded again


def test_hooks_read_the_router():
    seen = {}

    def page():
        seen["router"] = routing.use_router()
        seen["pathname"] = pz.use_pathname()
        seen["params"] = pz.use_params()
        seen["query"] = pz.use_search_params()
        return pz.text("x")

    router = Router({"/u/[name]": page}, initial="/u/ada?tab=1")
    draw(router)
    assert seen["router"] is router and seen["pathname"] == "/u/ada"
    assert seen["params"] == {"name": "ada"} and seen["query"] == {"tab": "1"}
    assert routing.use_router() is router  # outside a view: the router that drew last


def test_link_navigates_and_prefetches(monkeypatch):
    class Fake:
        def __init__(self, *args, **props):
            self.handlers = {}

        def style(self, *args, **props):
            return self

        def on(self, cursor=None, **handlers):
            self.cursor, self.handlers = cursor, handlers
            return self

    class FakeCore:
        Widget = Fake
        text = Fake
        container = Fake

    monkeypatch.setattr(routing, "_core", FakeCore)
    loaded = []
    router = Router({"/": page_named("home"), "/p/[id]": {"page": page_named("p"),
                                                          "load": lambda params: loaded.append(params["id"])}})
    widget = routing.link("/p/1", "Product", router=router)
    assert widget.cursor == "pointer"
    widget.handlers["mouse_enter"]()
    router.wait(5)
    assert loaded == ["1"]
    widget.handlers["click"]()
    assert router.pathname == "/p/1"
    routing.link("/", "Home", router=router, replace=True).handlers["click"]()
    assert router.history == ["/", "/"]


# -- folders ---------------------------------------------------------------------------------------------
def write(root: Path, files: dict) -> None:
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(source), encoding="utf-8")


def test_routes_from_folders(tmp_path):
    write(tmp_path, {
        "helpers.py": "GREETING = 'hi'\n",
        "app/layout.py": """
            import pyzed as pz
            title_template = "%s | Test"
            def layout(children):
                return pz.column([children])
        """,
        "app/page.py": """
            import pyzed as pz
            import helpers                     # next to app/, like Next.js' @/ imports
            title = "Home"
            def page():
                return pz.text(helpers.GREETING)
        """,
        "app/(shop)/products/[id]/page.py": """
            import pyzed as pz
            class Page(pz.Component):
                designer = False
                params: dict = {}
                def render(self):
                    return pz.text(self.params["id"])
        """,
        "app/docs/[...slug]/page.py": "import pyzed as pz\ndef default(params):\n    return pz.text('/'.join(params['slug']))\n",
        "app/_private/page.py": "raise RuntimeError('never imported')\n",
        "app/__pycache__/page.py": "",
        "app/empty/notes.txt": "",
    })
    router = Router(tmp_path / "app")
    assert router.routes() == ["/", "/docs/[...slug]", "/products/[id]"]
    draw(router)
    assert router.title == "Home | Test"
    for url in ("/products/3", "/docs/a/b"):
        router.push(url)
        assert isinstance(draw(router), pz.Widget)
    assert not any(p.endswith("app") for p in sys.path if p.startswith(str(tmp_path)))  # sys.path left as it was


def test_relative_folder_is_found_next_to_the_caller(tmp_path, monkeypatch):
    write(tmp_path, {"app/page.py": "def page():\n    return 'x'\n", "make.py": "import pyzed as pz\nr = pz.Router('app')\n"})
    monkeypatch.chdir(Path(__file__).parent)  # somewhere else
    namespace = {"__file__": str(tmp_path / "make.py")}
    exec(compile((tmp_path / "make.py").read_text(), str(tmp_path / "make.py"), "exec"), namespace)
    assert namespace["r"].source == tmp_path / "app"


def test_missing_function_is_explained(tmp_path):
    write(tmp_path, {"app/page.py": "x = 1\n"})
    router = Router(tmp_path / "app")
    with pytest.raises(RouteError, match="function page"):
        router.root.files["page"].target()


def test_router_app(tmp_path):
    write(tmp_path, {"app/page.py": "title = 'Start'\ndef page():\n    return 'x'\n",
                     "app/about/page.py": "def page():\n    return 'about'\n"})
    app = pz.RouterApp(tmp_path / "app", title="Demo")
    draw(app.router, app)
    assert app.title() == "Start"
    app.router.push("/about")
    draw(app.router, app)
    assert app.title() == "Demo"
    assert app.on_key("alt-left") is True and app.router.pathname == "/"
    assert app.on_key("x") is None
    assert app.on_back() is False  # the first page: Android sends the app to the background

    class Sub(pz.RouterApp):
        routes = tmp_path / "app"
        title = "Sub"

    assert Sub().app_title == "Sub" and Sub().title() == "Start"


# -- the CLI template ------------------------------------------------------------------------------------
def test_router_template_runs(tmp_path):
    from pyzed import cli

    assert cli.new_script(str(tmp_path / "web"), router=True) == 0
    app_dir = tmp_path / "web" / "app"
    assert (app_dir / "layout.py").is_file() and (app_dir / "page.py").is_file()
    router = Router(app_dir)
    assert "/" in router.routes() and len(router.routes()) >= 3
    owner = Owner()
    for url in router.routes():
        if "[" in url:
            url = rtree.build_href(url, {"id": "1"})
        router.push(url)
        settle(router, owner)
    router.push("/missing")
    draw(router, owner)


@pytest.mark.skipif(__import__("shutil").which("uv") is None, reason="needs uv")
def test_uv_project_with_routes(tmp_path):
    from pyzed import project

    created = project.init(tmp_path / "shop", sync=False, git=False, template="router")
    assert created.script == created.root / "main.py" and not created.main_form.exists()
    assert created.startup == created.root / "main.py"
    assert "class App(pz.RouterApp)" in (created.root / "main.py").read_text()
    assert 'title_template = "%s · Shop"' in (created.root / "app" / "layout.py").read_text()
    assert Router(created.root / "app").routes() == ["/", "/about", "/items", "/items/[id]"]


def test_form_from_the_designer_as_a_page(tmp_path):
    from pyzed.designer import Form, component as control, save

    form = Form(name="Contact", title="Contact", width=300, height=120)
    label = control("label").create("hello", 16, 16, 200)
    label.props["text"] = "Made in Pyzed Design"
    form.add(label)
    (tmp_path / "app" / "contact").mkdir(parents=True)
    (tmp_path / "app" / "page.py").write_text("def page():\n    return 'home'\n")
    save(form, tmp_path / "app" / "contact" / "page.pzform")
    (tmp_path / "app" / "contact" / "page.py").unlink(missing_ok=True)  # the form's handlers file is optional
    router = Router(tmp_path / "app", initial="/contact")
    assert router.routes() == ["/", "/contact"]
    assert router.root.children[0].files["page"].is_form
    assert isinstance(draw(router), pz.Widget)
    hosted = next(iter(router._forms.values()))
    assert hosted.runtime.form.name == "Contact" and hosted.runtime.loaded


def test_route_components_stay_out_of_the_toolbox(tmp_path):
    from pyzed import component as comp
    from pyzed.designer.scene import _route_file

    write(tmp_path, {"app/page.py": "import pyzed as pz\nclass Page(pz.Component):\n    def render(self):\n"
                                    "        return pz.text('x')\n"})
    before = dict(comp._REGISTRY)
    draw(Router(tmp_path / "app"))
    assert comp._REGISTRY == before
    assert _route_file(tmp_path / "app" / "page.py", tmp_path)
    assert _route_file(tmp_path / "x" / "(g)" / "layout.py", tmp_path)
    assert not _route_file(tmp_path / "ui" / "layout.py", tmp_path)
