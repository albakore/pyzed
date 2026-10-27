"""Ratings, ranges, tags, steps, pages, loading placeholders and data views: the library and the toolbox."""

import pytest

import pyzed as pz
from pyzed import _core, ui
from pyzed.designer import components
from pyzed.designer.model import Form
from pyzed.designer.runtime import FormApp
from pyzed.events import Event
from pyzed.ui import controls, display, inputs, navigation

NEW = ("rating", "range_slider", "tag_input", "stepper", "pagination", "skeleton", "progress_ring", "gauge",
       "line_chart", "timeline", "description_list")
#: The built-in entries, kept before other tests define components with the same names (a ``Rating``...).
BUILT_IN = {type_: components.get(type_) for type_ in NEW}


@pytest.fixture(autouse=True)
def _built_in_toolbox(monkeypatch):
    for type_, spec in BUILT_IN.items():
        monkeypatch.setitem(components._REGISTRY, type_, spec)


def test_every_new_component_draws():
    widgets = [
        ui.rating(3, print), ui.rating(4.4), ui.rating(2, print, disabled=True),
        ui.range_slider((20, 80), print, min=0, max=100, show_value="{:.0f} €"),
        ui.range_slider((0.5, 0.5), print, disabled=True),
        ui.tag_input(["a", "b"], print), ui.tag_input(["a"], print, text="p", on_input=print, suggestions=["py"]),
        ui.tag_input(["a"], None), ui.tag_input(["a", "b"], print, max_tags=2),
        ui.stepper(["A", ("B", "b"), "C"], 1, print, errors=[2]), ui.stepper(["A", "B"], 2, vertical=True),
        ui.pagination(5, 20, print), ui.pagination(1, 1, print, compact=True, size="lg"),
        ui.skeleton(), ui.skeleton(lines=3, animated=False), ui.skeleton(height=32, circle=True),
        ui.progress_ring(0.4, show_value=True), ui.progress_ring(None), ui.progress_ring(2, max=2),
        ui.gauge(95, thresholds=[(70, "warning"), (90, "error")], label="CPU", unit="%"),
        ui.line_chart([1, 2, 3]), ui.line_chart({"a": [1, 5], "b": [2, 4]}, labels=["x", "y"], fill=True, points=True),
        ui.line_chart([[1, 2], [3, 4]], min=0, max=10), ui.line_chart([]), ui.line_chart([7]),
        ui.timeline(["one", {"title": "two", "time": "9:00"}, ui.TimelineItem("three", icon="check")], on_press=print),
        ui.timeline(["a", "b"], dense=True),
        ui.description_list({"Name": "x", "Size": None, "Badge": ui.badge("ok")}),
        ui.description_list([("a", 1)], vertical=True, mono_values=True, dividers=False),
    ]
    assert all(isinstance(w, _core.Widget) for w in widgets)


def test_page_numbers_collapse_into_gaps():
    assert navigation._page_items(5, 20, 1, 1) == [1, None, 4, 5, 6, None, 20]
    assert navigation._page_items(1, 3, 1, 1) == [1, 2, 3]
    assert navigation._page_items(3, 9, 1, 1) == [1, 2, 3, 4, None, 9]  # a gap of one page shows the page
    assert navigation._page_items(10, 40, 2, 2) == [1, 2, None, 8, 9, 10, 11, 12, None, 39, 40]


def test_chart_steps_are_round():
    assert [display._nice_step(v) for v in (0.7, 2.75, 9, 2400 / 4)] == [1, 5, 10, 1000]
    assert display._nice_step(0.2) == pytest.approx(0.2)
    assert display._short(1260) == "1.3k" and display._short(2.5) == "2.5" and display._short(40) == "40"


def _captured(monkeypatch, module, name):
    """Calls to ``module.<name>`` keep their arguments in the returned list."""
    calls = []
    real = getattr(module, name)

    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, fake)
    return calls


def test_rating_sends_the_star_and_clears_on_the_lit_one(monkeypatch):
    buttons = _captured(monkeypatch, controls._core, "button")
    got = []
    ui.rating(3, got.append, max=4)
    presses = [args[1] for args, _ in buttons]
    assert len(presses) == 4
    for press in presses:
        press()
    assert got == [1, 2, 0, 4]
    buttons.clear()
    ui.rating(3, got.append, clearable=False)
    buttons[2][0][1]()
    assert got[-1] == 3
    buttons.clear()
    ui.rating(3)  # read only: no buttons
    assert not buttons


def test_range_slider_moves_the_nearer_knob(monkeypatch):
    attached = []
    real_on = _core.Widget.on

    def on(self, **events):
        attached.append(events)
        return real_on(self, **events)

    monkeypatch.setattr(_core.Widget, "on", on)
    got = []
    ui.range_slider((20, 80), got.append, min=0, max=100, step=10, on_release=lambda: got.append("released"))
    press = attached[-1]["mouse_down"]
    width = 232  # 200 pixels of travel between both knobs
    press(Event("mouse_down", x=8 + 0.3 * 200, width=width))   # near the low knob
    press(Event("drag", x=24 + 0.9 * 200, width=width))        # near the high knob
    assert got == [(30, 80), (20, 90)]
    assert attached[-1]["drag_end"] is attached[-1]["click"]  # on_release once, after a click or a drag
    ui.range_slider((20, 30), got.append, min=0, max=100, step=10)
    attached[-1]["drag"](Event("drag", x=70, width=width))     # the high knob stops at the low one
    assert got[-1] == (20, 20)


def test_tag_input_adds_on_enter_and_comma_and_removes(monkeypatch):
    fields = _captured(monkeypatch, inputs, "input")
    chips = _captured(monkeypatch, controls, "chip")
    got, typed = [], []
    ui.tag_input(["a"], got.append, text="b", on_input=typed.append, suggestions=["bee", "a"], id="tags")
    args, field = fields[-1]
    field["on_input"] = args[1]
    field["on_submit"]()  # adds the tag, clears the text and gives the field its focus back
    assert got[-1] == ["a", "b"] and typed[-1] == ""
    field["on_input"]("c, d,")
    assert got[-1] == ["a", "c", "d"]
    field["on_input"]("x")
    assert typed[-1] == "x"
    # the suggestion chips offer what matches and is not there yet
    offered = [args[0] for args, kwargs in chips if kwargs.get("icon") == "plus"]
    assert offered == ["bee"]
    removable = [kwargs["on_remove"] for args, kwargs in chips if args[0] == "a"]
    removable[0]()
    assert got[-1] == []


def test_tag_input_keeps_unique_tags_and_a_limit(monkeypatch):
    fields = _captured(monkeypatch, inputs, "input")
    got = []
    ui.tag_input(["a"], got.append, text="a, b, c", on_input=lambda _t: None, max_tags=2)
    fields[-1][1]["on_submit"]()
    assert got == [["a", "b"]]
    fields.clear()
    ui.tag_input(["a", "b"], got.append, text="", on_input=lambda _t: None, max_tags=2)
    assert not fields  # full: no field


def test_tag_input_without_text_state_keeps_its_own():
    class App(pz.App):
        tags = ["a"]

        def view(self):
            return ui.tag_input(self.tags, lambda tags: setattr(self, "tags", tags))

    assert isinstance(App().view(), _core.Widget)


def test_stepper_lets_go_back_only_to_done_steps(monkeypatch):
    buttons = _captured(monkeypatch, navigation._core, "button")
    got = []
    ui.stepper(["A", "B", "C", "D"], 1, got.append)
    assert len(buttons) == 2
    for args, _ in buttons:
        args[1]()
    assert got == [0, 1]
    buttons.clear()
    ui.stepper(["A", "B", "C"], 0, got.append, linear=False)
    assert len(buttons) == 3


def test_pagination_arrows_and_numbers(monkeypatch):
    got = []
    numbers = _captured(monkeypatch, navigation._core, "button")
    arrows = _captured(monkeypatch, navigation, "icon_button")
    ui.pagination(1, 5, got.append)
    assert arrows[0][0][1] is None and arrows[0][1]["disabled"]  # no page before the first
    arrows[1][0][1]()
    for args, _ in numbers:
        if args[1] is not None:
            args[1]()
    assert got[0] == 2 and set(got) == {2, 5}  # 1 2 … 5: the next arrow and the other pages


def test_timeline_entries_are_clickable(monkeypatch):
    attached = []
    real_on = _core.Widget.on

    def on(self, **events):
        attached.append(events)
        return real_on(self, **events)

    monkeypatch.setattr(_core.Widget, "on", on)
    got = []
    ui.timeline(["a", "b"], on_press=got.append)
    for events in attached:
        events["click"]()
    assert got == [0, 1]


# -- the toolbox -----------------------------------------------------------------------------------

def _app(type_, events=(), **props):
    form = Form(name="f")
    control = components.get(type_).create("c1", 10, 10)
    control.props.update(props)
    control.events = {e: f"c1_{e}" for e in events}
    form.controls.append(control)
    seen = []
    app = FormApp(form, {f"c1_{e}": (lambda form, event: seen.append((event.name, event.value))) for e in events})
    app.seen = seen
    return app, app.runtime.form["c1"]


def _capture(monkeypatch, name):
    got = {}
    real = getattr(ui, name)

    def fake(*args, **kwargs):
        got.update(kwargs, args=args)
        return real(*args, **kwargs)

    monkeypatch.setattr(ui, name, fake)
    return got


def test_new_components_are_in_the_toolbox():
    for type_ in NEW:
        spec = components.get(type_)
        assert spec.description, type_
        for event in spec.events:
            assert components.event_text(type_, event), (type_, event)
        components.get(type_).render(spec.create("c1"), components.RenderContext())


def test_toolbox_rating_pagination_and_stepper_keep_their_value(monkeypatch):
    app, rating = _app("rating", ("change",))
    got = _capture(monkeypatch, "rating")
    app.runtime.view()
    got["args"][1](5)
    assert rating.props["value"] == 5
    app, pages = _app("pagination", ("change",))
    got = _capture(monkeypatch, "pagination")
    app.runtime.view()
    got["args"][2](4)
    app2, steps = _app("stepper", ("change",))
    got2 = _capture(monkeypatch, "stepper")
    app2.runtime.view()
    got2["args"][2](0)
    assert pages.props["page"] == 4 and steps.props["current"] == 0
    assert app.seen == [("change", 4)] and app2.seen == [("change", 0)]


def test_toolbox_range_slider_and_tags(monkeypatch):
    app, slider = _app("range_slider", ("change",))
    got = _capture(monkeypatch, "range_slider")
    app.runtime.view()
    got["args"][1]((30, 60))
    assert (slider.props["low"], slider.props["high"]) == (30, 60) and app.seen == [("change", (30, 60))]
    app, tags = _app("tag_input", ("change", "input"))
    got = _capture(monkeypatch, "tag_input")
    app.runtime.view()
    got["on_input"]("py")
    got["args"][1](["design", "rust", "py"])
    assert tags.props["tags"] == "design\nrust\npy" and tags.props["text"] == "py"
    assert app.seen == [("input", "py"), ("change", ["design", "rust", "py"])]


def test_toolbox_line_chart_reads_named_series(monkeypatch):
    got = _capture(monkeypatch, "line_chart")
    spec = components.get("line_chart")
    spec.render(spec.create("c1"), components.RenderContext())
    assert got["args"][0] == {"Visits": [12, 18, 15, 24, 30, 28, 36], "Sales": [4, 6, 5, 9, 11, 10, 14]}
    control = spec.create("c2")
    control.props["series"] = "1 2 3"
    spec.render(control, components.RenderContext())
    assert got["args"][0] == [[1, 2, 3]]
