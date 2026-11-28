"""Global state (``pz.Store``) and actions that change data (``pz.action``)."""

from __future__ import annotations

import asyncio
import json
import threading

import pytest

import pyzed as pz
from pyzed import component
from pyzed.routing import Router


class Owner:
    """Stands for the window components draw in."""


class Cart(pz.Store):
    items: list = []
    coupon: str = ""

    @property
    def total(self):
        return sum(self.items)

    def add(self, price):
        self.items = [*self.items, price]


def test_fields_defaults_and_copies():
    a, b = Cart(), Cart(coupon="HALF")
    a.items.append(3)
    assert b.items == [] and b.coupon == "HALF" and a.total == 3
    assert Cart.__fields__ == {"items": [], "coupon": ""}
    with pytest.raises(TypeError, match="no field"):
        Cart(price=1)
    with pytest.raises(AttributeError, match="computed"):
        a.total = 4
    assert a.to_dict() == {"items": [3], "coupon": ""}
    a.reset()
    assert a.items == [] and repr(a) == "Cart(items=[], coupon='')"


def test_subscribe_batch_and_update():
    cart, seen = Cart(), []
    stop = cart.subscribe(lambda store: seen.append(list(store.items)))
    cart.add(2)
    with cart.batch():
        cart.add(3)
        cart.coupon = "X"
    cart.update(coupon="Y", items=[])
    stop()
    cart.add(9)
    assert seen == [[2], [2, 3], []]


def test_components_that_read_a_store_draw_again_and_only_those():
    cart = Cart()
    drawn = []

    class Badge(pz.Component):
        def render(self):
            drawn.append("badge")
            return pz.text(str(len(cart.items)))

    class Static(pz.Component):
        def render(self):
            drawn.append("static")
            return pz.text("hello")

    owner = Owner()

    def view():
        with component.render_pass(owner):
            return pz.column([Badge(), Static()])

    view()
    view()
    assert drawn == ["badge", "static"]  # nothing changed: both reused
    cart.add(5)
    view()
    assert drawn == ["badge", "static", "badge"]
    cart.items.append(1)  # in place: seen too
    view()
    assert drawn[-1] == "badge" and drawn.count("static") == 1


def test_changes_from_another_thread_redraw(monkeypatch):
    posted = []
    monkeypatch.setattr(pz._core, "post", lambda message: posted.append(message))
    cart = Cart()
    worker = threading.Thread(target=lambda: cart.add(1))
    worker.start()
    worker.join()
    assert posted and cart.items == [1]
    posted.clear()
    cart.add(2)  # on the main thread the app redraws after the handler anyway
    assert posted == []


def test_persist(tmp_path, monkeypatch):
    monkeypatch.setattr("pyzed.project.config_dir", lambda: tmp_path)

    class Prefs(pz.Store):
        persist = "prefs"
        theme: str = "dark"
        recent: list = []
        handle: object = None

    prefs = Prefs()
    prefs.theme = "light"
    prefs.handle = object()  # not JSON: left out
    saved = json.loads((tmp_path / "settings" / "prefs.store.json").read_text())
    assert saved == {"theme": "light", "recent": []}
    assert Prefs().theme == "light"


def test_action_runs_off_the_ui_thread_and_keeps_its_state():
    threads = []

    @pz.action(refresh=False)
    def save(value):
        threads.append(threading.current_thread() is threading.main_thread())
        return value * 2

    assert save.pending is False and save.calls == 0 and save.__name__ == "save"
    assert save.run(21) == 42
    assert threads == [False] and save.result == 42 and save.error is None and not save.pending
    assert save.calls == 1


def test_async_action_errors_and_on_error():
    errors = []

    @pz.action(refresh=False, on_error=errors.append)
    async def fail():
        await asyncio.sleep(0.01)
        raise ValueError("server said no")

    future = fail()
    with pytest.raises(ValueError):
        future.result(5)
    assert isinstance(fail.error, ValueError) and errors and not fail.pending
    fail.reset()
    assert fail.error is None


def test_action_refreshes_and_invalidates_the_router():
    loads = []

    def load(params):
        loads.append(params.get("id", "list"))
        return len(loads)

    router = Router({"/products": {"page": lambda data: str(data), "load": load},
                     "/products/[id]": {"page": lambda data: str(data), "load": load}}, initial="/products")
    owner = Owner()

    def draw():
        with component.render_pass(owner):
            return router.view()

    draw()
    router.wait(5)
    router.push("/products/3")
    draw()
    router.wait(5)
    assert loads == ["list", "3"]

    @pz.action(invalidate="/products")
    def buy():
        return "ok"

    buy.run()
    draw()
    router.wait(5)
    assert loads == ["list", "3", "3"]  # refresh: the page shown loads again
    router.back()
    draw()
    router.wait(5)
    assert loads[-1] == "list"  # invalidated: loads again when shown


def test_invalidate_by_pattern():
    loads = []
    router = Router({"/p/[id]": {"page": lambda data: str(data), "load": lambda params: loads.append(1)}},
                    initial="/p/1")
    owner = Owner()
    with component.render_pass(owner):
        router.view()
    router.wait(5)
    router.invalidate("/p/[id]")
    with component.render_pass(owner):
        router.view()
    router.wait(5)
    assert len(loads) == 2
