"""Components, form controls and the designer's lists are drawn again only when what they show changes."""

import threading
import time

import pyzed as pz
from pyzed import component as C
from pyzed import hot_reload, ui
from pyzed.designer import components, file_scan, panels
from pyzed.designer.model import Control
from pyzed.theme import ONE_DARK, ONE_LIGHT, current, use


class Owner:
    """Stands for a window: ``view`` runs ``build`` inside a render pass."""

    def __init__(self, build):
        self.build = build

    def view(self):
        with C.render_pass(self):
            return self.build()


class Counted(pz.Component):
    designer = False
    title: str = ""
    items: list = ()

    def setup(self):
        self.picked = []

    def render(self):
        Counted.drawn += 1
        return pz.text(f"{self.title} {len(self.picked)} {pz.use_context('tone', 'plain')}")


Counted.drawn = 0


def instance(owner, cls=Counted):
    return next(c for c in owner._pyzed_components.values() if type(c) is cls)


def test_an_unchanged_component_reuses_its_drawing():
    owner = Owner(lambda: Counted(title="a"))
    first = owner.view()
    before = Counted.drawn
    assert owner.view() is first
    assert Counted.drawn == before
    owner.build = lambda: Counted(title="b")  # a new prop
    assert owner.view() is not first
    assert Counted.drawn == before + 1


def test_state_changed_in_place_draws_again():
    owner = Owner(lambda: Counted(title="a"))
    first = owner.view()
    instance(owner).picked.append(1)  # a list mutated, not replaced
    assert owner.view() is not first


def test_context_and_theme_changes_draw_again():
    tone = ["plain"]

    def build():
        with pz.provide(tone=tone[0]):
            return Counted(title="a")

    owner = Owner(build)
    first = owner.view()
    assert owner.view() is first
    tone[0] = "loud"
    second = owner.view()
    assert second is not first
    before = current()
    try:
        use(ONE_LIGHT if before is not ONE_LIGHT else ONE_DARK)
        assert owner.view() is not second
    finally:
        use(before)


class Child(pz.Component):
    designer = False

    def setup(self):
        self.on = False

    def render(self):
        return pz.text("on" if self.on else "off")


class Parent(pz.Component):
    designer = False
    title: str = ""

    def render(self):
        Parent.drawn += 1
        return pz.column([pz.text(self.title), Child(), Child()])


Parent.drawn = 0


def test_a_child_that_changes_draws_its_parent_again_and_cached_children_stay_mounted():
    owner = Owner(lambda: Parent(title="x"))
    first = owner.view()
    slots = set(owner._pyzed_components)
    assert len(slots) == 3
    before = Parent.drawn
    assert owner.view() is first and Parent.drawn == before
    assert set(owner._pyzed_components) == slots  # the children were not unmounted
    child = instance(owner, Child)
    child.on = True
    assert owner.view() is not first and Parent.drawn == before + 1
    assert instance(owner, Child) is child  # same instance, state kept


def test_refresh_cache_false_and_reloads_draw_again():
    owner = Owner(lambda: Counted(title="a"))
    first = owner.view()
    instance(owner).refresh()
    second = owner.view()
    assert second is not first
    hot_reload.generation += 1  # a reload may have changed render()
    assert owner.view() is not second

    class Live(pz.Component):
        designer = False
        cache = False

        def render(self):
            return pz.text("now")

    live = Owner(lambda: Live())
    assert live.view() is not live.view()


def test_values_whose_changes_cannot_be_seen_turn_the_cache_off():
    class Handle(pz.Component):
        designer = False

        def setup(self):
            self.lock = threading.Lock()  # no way to know what it stands for

        def render(self):
            return pz.text("x")

    owner = Owner(lambda: Handle())
    assert owner.view() is not owner.view()


def test_callbacks_compare_by_code_and_captured_values():
    snap = C._snapshot
    make = lambda n: (lambda: n)  # noqa: E731
    assert snap(make(1)) == snap(make(1))
    assert snap(make(1)) != snap(make(2))
    target = object()
    assert snap(make(target)) == snap(make(target))  # compared by identity: the same object


def test_form_controls_reuse_their_drawing():
    ctx = components.RenderContext(ONE_DARK, "Form1")
    button = Control("ok", "button", 0, 0, 100, 30, props={"text": "OK"})
    first = components.render(button, ctx)
    assert components.render(button, components.RenderContext(ONE_DARK, "Form1")) is first
    button.props["text"] = "Cancel"
    assert components.render(button, ctx) is not first
    assert components.render(button, components.RenderContext(ONE_LIGHT, "Form1")) is not first
    picker = Control("color", "color_picker", 0, 0, 200, 200)  # a pz.Component: it caches by itself
    assert components.render(picker, ctx) is not components.render(picker, ctx)


def test_console_rows_are_reused_and_call_the_current_callbacks():
    log = ui.Log()
    for i in range(5):
        log.write("info", f"line {i}")
    calls = []
    sel = ui.LogSelection()
    ui.console(log.entries, selection=sel, on_open=lambda e: calls.append(("old", e.id)), id="cache-test")
    rows = dict(ui.console.__globals__["_consoles"]["cache-test"].rows)
    ui.console(log.entries, selection=sel, on_open=lambda e: calls.append(("new", e.id)), id="cache-test")
    live = ui.console.__globals__["_consoles"]["cache-test"]
    assert all(live.rows[k][1] is rows[k][1] for k in rows)  # no row was built again
    live.open(log.entries[0])
    assert calls == [("new", log.entries[0].id)]


def test_designer_outline_rows_are_reused(tmp_path):
    from test_quiet_updates import designer

    app = designer(tmp_path)
    t = app.theme
    panels.outline(app, t)
    first = dict(app._outline_rows)
    panels.outline(app, t)
    assert all(app._outline_rows[n][1] is first[n][1] for n in first)
    name = next(iter(first))
    app.doc.select([name])
    panels.outline(app, t)
    assert app._outline_rows[name][1] is not first[name][1]


def test_file_lists_skip_environments_and_refresh_in_the_background(tmp_path, monkeypatch):
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "hidden.pzform").write_text("{}")
    (tmp_path / "main.pzform").write_text("{}")
    monkeypatch.setattr(file_scan, "FRESH", 0.0)
    file_scan.forget()
    assert file_scan.files(tmp_path, (".pzform",)) == [tmp_path / "main.pzform"]
    (tmp_path / "other.pzform").write_text("{}")
    file_scan.files(tmp_path, (".pzform",))  # stale: read again on a worker thread
    for _ in range(100):
        if len(file_scan.files(tmp_path, (".pzform",))) == 2:
            break
        time.sleep(0.02)
    assert file_scan.files(tmp_path, (".pzform",)) == [tmp_path / "main.pzform", tmp_path / "other.pzform"]
