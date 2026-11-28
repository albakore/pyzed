"""Native desktop notifications (``pz.notify``): what reaches the system and what comes back."""

from __future__ import annotations

import pytest

import pyzed as pz
from pyzed import _core, component, notifications
from pyzed.routing import Router
from pyzed.routing import router as _router


class Owner:
    """Stands for the window the router draws in."""


@pytest.fixture
def system(monkeypatch):
    """A fake notification server: records what is shown and lets the test click."""
    shown, closed = [], []

    def show(id, on_event, title, body="", **options):  # noqa: A002 - the core's name
        shown.append({"id": id, "on_event": on_event, "title": title, "body": body, **options})

    monkeypatch.setattr(_core, "notify_show", show, raising=False)
    monkeypatch.setattr(_core, "notify_close", closed.append, raising=False)
    monkeypatch.setattr(_core, "notify_supported", lambda: True, raising=False)
    monkeypatch.setattr(_core, "notify_capabilities", lambda: ["actions", "body"], raising=False)
    monkeypatch.setattr(_core.Command, "focus_window", staticmethod(lambda *a: "focus"), raising=False)
    monkeypatch.setattr(notifications, "_by_tag", {})
    return shown, closed


def test_what_reaches_the_system(system):
    shown, _closed = system
    note = pz.notify("Order shipped", "On its way", actions={"track": "Track", "/orders": "All orders"},
                     urgency="critical", sound=False, timeout=0, icon=b"\x89PNG fake")
    assert note.native and note.shown and notifications.supported()
    sent = shown[-1]
    assert sent["title"] == "Order shipped" and sent["body"] == "On its way"
    assert sent["actions"] == [("track", "Track"), ("/orders", "All orders")]
    assert sent["urgency"] == 2 and sent["sound"] is None and sent["timeout_ms"] == 0
    assert sent["icon"].endswith(".png") and sent["app_name"]
    pz.notify("Hi", sound="Glass", timeout=2.5, actions=["Yes", ("no", "No")])
    assert shown[-1]["sound"] == "Glass" and shown[-1]["timeout_ms"] == 2500
    assert shown[-1]["actions"] == [("Yes", "Yes"), ("no", "No")]
    with pytest.raises(ValueError):
        pz.notify("x", urgency="loud")


def test_clicks_buttons_and_close_come_back(system):
    shown, closed = system
    events = []
    note = pz.notify("New message", "Ana: hi", actions={"reply": "Reply"},
                     on_click=lambda n: events.append(("click", n.title)),
                     on_action=lambda action: events.append(("action", action)),
                     on_close=lambda reason: events.append(("close", reason)))
    on_event = shown[-1]["on_event"]
    on_event("click", None)
    on_event("action", "reply")
    on_event("closed", "dismissed")
    assert events == [("click", "New message"), ("action", "reply"), ("close", "dismissed")]
    assert note.closed and note.reason == "dismissed"
    note.close()
    assert closed == [note.id]


def test_a_click_opens_a_route_and_focuses_the_window(system):
    shown, _closed = system
    router = Router({"/": lambda: "home", "/orders/[id]": lambda params: params["id"], "/orders": lambda: "all"})
    with component.render_pass(Owner()):
        router.view()
    assert _router._current is router
    pz.notify("Order shipped", href="/orders/3", actions={"/orders": "All orders"})
    on_event = shown[-1]["on_event"]
    on_event("click", None)
    assert router.pathname == "/orders/3"
    on_event("action", "/orders")
    assert router.pathname == "/orders" and router.history == ["/", "/orders/3", "/orders"]
    assert notifications._open(None) == "focus"


def test_tag_replaces_and_update(system):
    shown, _closed = system
    first = pz.notify("Download", "10 %", tag="download")
    second = pz.notify("Download", "60 %", tag="download")
    assert first is second and [s["id"] for s in shown] == [first.id, first.id]
    second.update(body="Done")
    assert shown[-1]["body"] == "Done"
    with pytest.raises(TypeError):
        second.update(id=3)


def test_falls_back_without_a_notification_server(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("no server")

    calls = []
    monkeypatch.setattr(_core, "notify_show", fail, raising=False)
    monkeypatch.setattr("pyzed._platform.notify", lambda title, body: calls.append((title, body)) or True)
    note = pz.notify("Hello", "from the fallback")
    assert note.shown and not note.native and calls == [("Hello", "from the fallback")]


def test_the_notification_service(system):
    shown, _closed = system
    events = []
    service = pz.Notification("Backup", "Done", actions="Open\nLater", on_action=events.append,
                              on_clicked=lambda: events.append("clicked"))
    assert service.show() is True
    assert shown[-1]["actions"] == [("Open", "Open"), ("Later", "Later")]
    shown[-1]["on_event"]("action", "Later")
    shown[-1]["on_event"]("click", None)
    assert events == ["Later", "clicked"]
