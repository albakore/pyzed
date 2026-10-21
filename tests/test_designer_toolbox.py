"""The library components in Pyzed Design's toolbox: their properties and the events they raise when running."""

from pathlib import Path

import pyzed as pz
from pyzed import ui
from pyzed.designer import components
from pyzed.designer.model import Form
from pyzed.designer.runtime import FormApp, open_form

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "designer"

NEW = ("toggle_group", "split_button", "tree", "breadcrumbs", "empty_state", "counter", "status_dot", "facepile",
       "diff_stat", "qr_code", "svg", "image_viewer", "terminal", "color_picker", "icon_picker")


def test_library_components_are_in_the_toolbox():
    types = {c.type for c in components.all_components()}
    assert set(NEW) <= types
    for type_ in NEW:
        spec = components.get(type_)
        assert spec.description, type_
        for event in spec.events:  # every event is described in the Events panel
            assert components.event_text(type_, event) or spec.type in ("color_picker", "icon_picker"), event
    assert components.get("slider").events == ("change", "release")
    assert "close" in components.get("tabs").events and "remove" in components.get("chip").events
    assert {"open", "sort"} <= set(components.get("table").events)
    assert "link" in components.get("markdown").events


def test_tree_items_are_indented_lines():
    nodes = components._tree_nodes("Docs\n  a.md\n  Pics/\nnotes.txt\n\tdeep")
    assert [n.name for n in nodes] == ["Docs", "notes.txt"]
    docs, notes = nodes
    assert docs.is_folder and [c.id for c in docs.children] == ["Docs/a.md", "Docs/Pics"]
    assert docs.children[1].is_folder and not docs.children[0].is_folder  # "Pics/" is an empty folder
    assert notes.is_folder and notes.children[0].id == "notes.txt/deep"  # a tab is one level


def _app(type_, events=(), **props):
    """A running form with one control of ``type_`` whose events append ``(event, value)`` to ``app.seen``."""
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
    """Replaces ``ui.<name>`` by a stand-in that keeps its keyword arguments."""
    got = {}
    real = getattr(ui, name)

    def fake(*args, **kwargs):
        got.update(kwargs, args=args)
        return real(*args, **kwargs)

    monkeypatch.setattr(ui, name, fake)
    return got


def test_tree_selects_folds_and_opens(monkeypatch):
    app, tree = _app("tree", ("change", "toggle", "open"))
    got = _capture(monkeypatch, "tree")
    app.runtime.view()
    got["on_toggle"]("Pictures")
    assert set(tree.props["expanded"].splitlines()) == {"Documents", "Pictures"}
    got["on_select"]("Documents/Notes.md")
    got["on_open"]("Documents/Notes.md")
    assert tree.props["selected"] == "Documents/Notes.md"
    assert app.seen == [("toggle", "Pictures"), ("change", "Documents/Notes.md"), ("open", "Documents/Notes.md")]


def test_closable_tabs_leave_the_bar(monkeypatch):
    app, tabs = _app("tabs", ("change", "close"), closable=True)
    got = _capture(monkeypatch, "tab_bar")
    app.runtime.view()
    got["on_close"]("General")  # the selected one: its neighbour takes over
    assert tabs.props["tabs"] == "Advanced\nAbout" and tabs.props["selected"] == "Advanced"
    assert app.seen == [("change", "Advanced"), ("close", "General")]


def test_sortable_table_flips_the_order_and_opens_rows(monkeypatch):
    app, table = _app("table", ("sort", "open", "change"), sortable=True)
    got = _capture(monkeypatch, "table")
    app.runtime.view()
    got["on_sort"]("Name")
    assert (table.props["sort_by"], table.props["descending"]) == ("Name", False)
    app.runtime.view()
    got["on_sort"]("Name")
    assert table.props["descending"] is True
    rows = got["args"][1]
    got["on_row_double_press"](rows[1])
    got["on_row_press"](rows[0])
    assert table.props["selected"] == 0
    assert app.seen == [("sort", "Name"), ("sort", "Name"), ("open", 1), ("change", 0)]


def test_toggle_group_with_several_pressed(monkeypatch):
    app, group = _app("toggle_group", ("change",), multiple=True, selected="left")
    got = _capture(monkeypatch, "toggle_group")
    app.runtime.view()
    assert got["args"][0][0] == ("left", "align-left", "Left")
    got["args"][2]("center")
    assert group.props["selected"] == "left\ncenter" and app.seen == [("change", ["left", "center"])]


def test_slider_release_and_chip_remove(monkeypatch):
    app, slider = _app("slider", ("change", "release"))
    got = _capture(monkeypatch, "slider")
    app.runtime.view()
    got["args"][1](70)
    got["on_release"]()
    assert slider.props["value"] == 70 and app.seen == [("change", 70), ("release", None)]
    app, _chip = _app("chip", ("remove",), removable=True)
    got = _capture(monkeypatch, "chip")
    app.runtime.view()
    got["on_remove"]()
    assert app.seen == [("remove", None)]


def test_a_component_keeps_its_new_value_without_a_handler():
    class Dial(pz.Component):
        value: float = 0.0
        events = ("change",)
        designer = False
        last = None

        def render(self):
            Dial.last = self
            return pz.text(str(self.value))

    spec = Dial.designer_spec()
    components.register(spec)
    try:
        app, dial = _app("dial")
        app.runtime.view()
        Dial.last.emit("change", 0.75)
        assert dial.props["value"] == 0.75
        assert app.runtime.proxy.c1.value == 0.75
    finally:
        components._REGISTRY.pop("dial", None)


def test_explorer_example_runs(tmp_path):
    app = open_form(EXAMPLES / "explorer.pzform")
    rt = app.runtime
    rt.dispatch(None, "load")
    rt.dispatch(rt.form["files"], "change", "Docs/Images/cat.png")
    assert rt.form["path"].props["parts"] == ["Project", "Docs", "Images", "cat.png"]
    assert rt.form["listing"].props["selected"] == 3
    rt.dispatch(rt.form["path"], "click", 1)
    assert rt.form["files"].props["selected"] == "Docs"
    rt.dispatch(rt.form["listing"], "open", 0)
    assert rt.form["preview"].visible and not rt.form["listing"].visible
    assert rt.form["preview"].props["title"] == "README.md"
    rt.dispatch(rt.form["share"], "choose", "Show QR code")
    assert rt.form["link_qr"].visible
    rt.dispatch(rt.form["unread"], "click")
    assert rt.form["unread"].props["count"] == 0
    assert rt.error is None
    app.screenshot(tmp_path / "explorer.png", scale=1)
