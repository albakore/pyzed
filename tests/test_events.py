"""Common events (`widget.on`), the Event object and custom components."""

import pytest

import pyzed as pz
from pyzed import component as _component
from pyzed import events


# -- common events --------------------------------------------------------------


def test_catalog_matches_the_native_list():
    assert events.COMMON == tuple(pz._core.event_names())
    assert {"click", "double_click", "drag", "key_down", "resize"} <= set(events.COMMON)
    assert all(info.doc for info in events.CATALOG.values())


def test_on_wraps_any_widget_and_merges():
    w = pz.text("hi").on(click=1, on_double_click=print)
    assert repr(w) == '<Widget text "hi">.on(click, double_click)'
    merged = w.on(click=None, drag=print, cursor="grab")
    assert repr(merged) == '<Widget text "hi">.on(double_click, drag)'
    assert repr(pz.on("text", scroll=print)).endswith(".on(scroll)")


def test_unknown_events_are_rejected():
    with pytest.raises(ValueError, match="available events: click"):
        pz.text("x").on(clik=print)
    with pytest.raises(ValueError):
        pz.text("x").on(click=print, cursor="nope")


def test_handlers_get_the_event_only_if_they_take_it():
    seen = []
    event = events.Event("click", x=3, y=4)
    assert events.call(lambda: seen.append("none"), event) is None
    events.call(lambda e: seen.append(e.position), event)
    events.call(lambda *args: seen.append(len(args)), event)
    for i in range(2):
        events.call(lambda i=i: seen.append(i), event)  # the loop-variable idiom keeps its value
    assert seen == ["none", (3, 4), 1, 0, 1]
    assert events.call("a message", event) == "a message"
    assert events.call(None, event) is None


def test_bound_methods_and_callables():
    class Target:
        def __init__(self):
            self.got = []

        def plain(self):
            self.got.append("plain")

        def with_event(self, event):
            self.got.append(event.type)

        def __call__(self, event):
            self.got.append(("call", event.key))

    t = Target()
    events.call(t.plain, events.Event("click"))
    events.call(t.with_event, events.Event("drag"))
    events.call(t, events.Event("key_down", key="ctrl-s"))
    assert t.got == ["plain", "drag", ("call", "ctrl-s")]


def test_deliver_builds_the_event():
    got = events._deliver(lambda e: e, "key_down", x=1.0, y=2.0, dx=0.0, dy=0.0, width=10.0, height=5.0,
                          button=None, key="ctrl-s", shift=False, ctrl=True, alt=False, logo=False)
    assert (got.type, got.key, got.ctrl, got.size) == ("key_down", "ctrl-s", True, (10.0, 5.0))
    assert "key='ctrl-s'" in repr(got)


def test_widgets_with_events_render(tmp_path):
    class Demo(pz.App):
        size = (120, 80)

        def view(self):
            return pz.column([
                pz.text("a").on(click=print, resize=print, cursor="pointer"),
                pz.container(pz.text("b"), padding=4).on(drag=print).on(key_down=print),
            ])

    Demo().screenshot(tmp_path / "events.png", scale=1)
    assert (tmp_path / "events.png").exists()


# -- components ---------------------------------------------------------------------


class Counter(pz.Component):
    """Counts clicks."""

    label_text: str = "Count"
    step: int = 1
    events = {"change": "The count changed."}
    designer = False

    def setup(self):
        self.count = 0
        self.mounted = 0

    def on_mount(self):
        self.mounted += 1

    def bump(self):
        self.count += self.step
        return self.emit("change", self.count)

    def render(self):
        return pz.text(f"{self.label_text}: {self.count}")


class Owner(pz.App):
    def __init__(self, keys=None, show=True):
        self.keys = keys
        self.show = show
        self.changes = []

    def view(self):
        if not self.show:
            return pz.text("empty")
        if self.keys:
            return pz.column([Counter(key=k, label_text=k) for k in self.keys])
        return pz.column([
            Counter(on_change=lambda e: self.changes.append(e.value)),
            Counter(step=10, on_click=print),
        ])


def instances(app):
    """The app's live components, keyed with short class names (no `<locals>.` prefix)."""
    short = lambda part: part.rsplit(".", 1)[-1] if isinstance(part, str) else part  # noqa: E731
    return {tuple(short(p) for p in key): c for key, c in app._pyzed_components.items()}


def test_component_call_returns_a_widget():
    assert isinstance(Counter(), pz.Widget)
    assert isinstance(Counter("Positional"), pz.Widget)


def test_state_persists_between_renders_by_position():
    app = Owner()
    app.__pyzed_view__()
    first = instances(app)
    assert list(first) == [("Counter", 0), ("Counter", 1)]
    a, b = first.values()
    assert a.mounted == 1 and b.step == 10
    a.bump()
    app.__pyzed_view__()
    assert instances(app)[("Counter", 0)] is a and a.count == 1 and a.mounted == 1
    assert app.changes == [1]


def test_keys_follow_items_and_unmount_the_rest():
    unmounted = []

    class Tracked(Counter):
        designer = False

        def on_unmount(self):
            unmounted.append(self.label_text)

    class KeyedOwner(Owner):
        def view(self):
            return pz.column([Tracked(key=k, label_text=k) for k in self.keys])

    app = KeyedOwner(keys=["a", "b", "c"])
    app.__pyzed_view__()
    b = instances(app)[("Tracked", "key", "b")]
    b.count = 5
    app.keys = ["b", "c"]
    app.__pyzed_view__()
    assert instances(app)[("Tracked", "key", "b")] is b and b.count == 5
    assert unmounted == ["a"]


def test_a_failed_view_keeps_components():
    app = Owner()
    app.__pyzed_view__()
    before = instances(app)

    class Boom(Exception):
        pass

    def broken():
        raise Boom

    app.view = broken
    with pytest.raises(Boom):
        app.__pyzed_view__()
    assert instances(app) == before


def test_emit_requires_declared_events():
    c = Counter.create()
    assert c.emit("change", 3) is None  # no handler
    with pytest.raises(ValueError, match="does not declare"):
        c.emit("nope")
    assert set(Counter.__events__) == {"change", "mount", "unmount"}


def test_props_validation():
    with pytest.raises(TypeError, match="no prop or event 'colour'"):
        Counter(colour="red")
    with pytest.raises(TypeError, match="at most 2 positional"):
        Counter("a", 1, 2)

    class Needs(pz.Component):
        title: str
        designer = False

        def render(self):
            return pz.text(self.title)

    with pytest.raises(TypeError, match="missing required props: title"):
        Needs()
    assert Needs.__props__["title"].required


def test_common_events_on_components():
    w = Counter(on_click=print, on_drag=print)
    assert repr(w).endswith(".on(click, drag)")


def test_nested_components_have_their_own_slots():
    class Inner(pz.Component):
        designer = False

        def render(self):
            return pz.text("inner")

    class Outer(pz.Component):
        designer = False

        def render(self):
            return pz.column([Inner(), Inner()])

    class App(pz.App):
        def view(self):
            return pz.row([Outer(), Outer()])

    app = App()
    app.__pyzed_view__()
    keys = list(instances(app))
    assert (("Outer", 0, "Inner", 1)) in keys and ("Outer", 1, "Inner", 0) in keys
    assert len(keys) == 6


def test_components_join_the_designer_toolbox():
    from pyzed.designer import components as designer

    class Stars(pz.Component):
        """Stars to click."""

        value: int = 3
        style: "typing.Literal['solid', 'outline']" = "solid"  # noqa: F821
        tags: list = ("a", "b")
        events = ("change",)
        icon = "star"
        size = (120, 24)

        def render(self):
            return pz.text("★" * int(self.value))

    try:
        spec = designer.get("stars")
        assert (spec.label, spec.icon, spec.category, spec.size) == ("Stars", "star", "Custom", (120, 24))
        assert spec.events == ("change",) and spec.description == "Stars to click."
        kinds = {p.name: (p.kind, p.default) for p in spec.props}
        assert kinds == {"value": ("number", 3), "style": ("choice", "solid"), "tags": ("list", "a\nb")}
        control = spec.create("stars1")
        widget = designer.render(control, designer.RenderContext())
        assert isinstance(widget, pz.Widget)
    finally:
        designer._REGISTRY.pop("stars", None)
        _component._REGISTRY.pop("stars", None)
