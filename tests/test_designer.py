"""Tests for the visual designer: form model, geometry, undo, handler code, document and runtime."""

import struct
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import designer
from pyzed.designer import code, geometry
from pyzed.designer.document import Document
from pyzed.designer.model import Control, Form
from pyzed.designer.runtime import FormApp, open_form, theme_for

ROOT = Path(__file__).resolve().parent.parent


def png_size(path):
    with open(path, "rb") as f:
        header = f.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", header[16:24])


def sample_form():
    form = Form(title="Sample", width=400, height=300)
    form.add(designer.component("label").create("status", 16, 16))
    form.add(designer.component("input").create("user", 16, 48))
    form.add(designer.component("button").create("greet", 232, 48))
    return form


# -- model -------------------------------------------------------------------


def test_form_json_roundtrip(tmp_path):
    form = sample_form()
    form["greet"].events["click"] = "greet_click"
    form["user"].anchor = ("left", "top", "right")
    path = designer.save(form, tmp_path / "sample")
    assert path.suffix == ".pzform"
    loaded = designer.load(path)
    assert loaded == form
    assert loaded["user"].anchor == ("left", "top", "right")


def test_unique_names_and_rename():
    form = sample_form()
    assert form.unique_name("button") == "button1"
    form.add(Control("button1", "button"))
    assert form.unique_name("button") == "button2"
    assert form.rename("button1", "OK button") == "oK_button"
    assert form.rename("oK_button", "greet") != "greet"  # taken, so it gets a fresh name
    assert form.add(Control("title", "label")).name == "title1"  # reserved for form.title


def test_rejects_foreign_json():
    with pytest.raises(ValueError):
        Form.from_dict({"format": "something/1"})
    with pytest.raises(ValueError, match="newer Pyzed"):
        Form.from_dict({"format": "pyzed.form/2"})
    assert Form.from_dict({"format": "pyzed.form/1"}).controls == []


def test_every_component_has_defaults_and_renders():
    ctx = designer.RenderContext(pz.themes.ONE_DARK)
    for spec in designer.all_components():
        control = spec.create(spec.type, 0, 0)
        assert set(control.props) == {p.name for p in spec.props}
        assert isinstance(designer.render(control, ctx), pz.Widget)
        assert spec.default_event is None or spec.default_event in spec.all_events


def test_register_custom_component():
    spec = designer.Component("rating", "Rating", "star", "Custom", lambda c, ctx: pz.text("★" * c.props["value"]),
                              props=(designer.Prop("value", "number", 3),))
    designer.register(spec)
    assert designer.component("rating") is spec
    assert "Custom" in designer.categories()


# -- geometry ----------------------------------------------------------------


def test_snap_and_resize():
    assert geometry.snap(13, 8) == 16
    assert geometry.snap(13, 8, enabled=False) == 13
    assert geometry.resize((10, 10, 100, 40), "se", 21, 3, grid=8, snapping=True) == (10, 10, 118, 46)
    assert geometry.resize((10, 10, 100, 40), "nw", 200, 0) == (102, 10, 8, 40)  # never below MIN_SIZE


def test_align_distribute_and_same_size():
    a, b, c = Control("a", "button", 10, 10, 50, 20), Control("b", "button", 40, 60, 80, 30), \
        Control("c", "button", 200, 100, 20, 20)
    geometry.align([a, b, c], "left")
    assert a.x == b.x == c.x == 10
    geometry.align([a, b, c], "bottom")
    assert a.y + a.height == b.y + b.height == c.y + c.height == 120
    a.x, b.x, c.x = 0, 30, 200
    geometry.distribute([a, b, c], "horizontal")
    assert b.x - (a.x + a.width) == c.x - (b.x + b.width)
    geometry.same_size([a, b, c], "width")
    assert a.width == b.width == c.width == 50
    geometry.align([a], "center", to=(0, 0, 400, 300))
    assert a.x == 175


def test_locked_controls_do_not_move():
    a = Control("a", "button", 10, 10, locked=True)
    geometry.move([a], 50, 50)
    geometry.align([a], "right", to=(0, 0, 400, 300))
    assert (a.x, a.y) == (10, 10)


def test_anchors():
    c = Control("c", "button", 10, 10, 100, 20, anchor=("left", "top", "right"))
    assert geometry.anchored(c, (400, 300), (500, 300)) == (10, 10, 200, 20)
    c.anchor = ("right", "bottom")
    assert geometry.anchored(c, (400, 300), (500, 350)) == (110, 60, 100, 20)
    c.anchor = ()
    assert geometry.anchored(c, (400, 300), (500, 300)) == (60, 10 + 0, 100, 20)


def test_smart_guides_snap_to_neighbours():
    dx, dy, lines = geometry.smart_guides((102, 50, 40, 20), [(100, 200, 60, 20)], (400, 300))
    assert dx == -2 and dy == 0
    assert lines and lines[0][0] == 100


# -- history -----------------------------------------------------------------


def test_history_undo_redo_and_grouping():
    form = sample_form()
    history = designer.History(form)
    form["status"].props["text"] = "a"
    history.push(form, group="text")
    form["status"].props["text"] = "ab"
    history.push(form, group="text")
    form["status"].x = 99
    history.push(form)
    assert history.undo()["status"].x == 16
    undone = history.undo()
    assert undone["status"].props["text"] == "Label"  # both keystrokes were one step
    assert history.redo()["status"].props["text"] == "ab"


# -- handler code ------------------------------------------------------------


def test_code_stubs_and_replacement():
    source = code.new_module("Main")
    source, created = code.ensure_function(source, "greet_click", "Says hi.")
    assert created and "def greet_click(form, event):" in source
    source, created = code.ensure_function(source, "greet_click")
    assert not created
    source = code.replace_function(source, "greet_click", "def greet_click(form, event):\n    return 42\n")
    assert "return 42" in code.get_function(source, "greet_click")
    assert source.startswith('"""Event handlers for the Main form.')
    with pytest.raises(SyntaxError):
        code.replace_function(source, "greet_click", "def greet_click(form, event:\n")
    with pytest.raises(SyntaxError):  # an unindented line would escape the function
        code.replace_function(source, "greet_click", "def greet_click(form, event):\n    pass\nx = 1\n")
    renamed = code.rename_function(source, "greet_click", "hello_click")
    assert code.functions(renamed) == ["hello_click"]
    assert code.body_is_empty(code.stub("x"))


def test_load_module_picks_up_edits(tmp_path):
    path = tmp_path / "handlers.py"
    path.write_text("def f(form, event):\n    return 1\n")
    assert code.handlers(code.load_module(path))["f"](None, None) == 1
    path.write_text("def f(form, event):\n    return 2\n")
    assert code.handlers(code.load_module(path))["f"](None, None) == 2


# -- document ----------------------------------------------------------------


def test_document_editing_commands():
    doc = Document(Form(width=400, height=300))
    button = doc.add("button", 13, 13)
    assert (button.x, button.y) == (16, 16) and doc.selection == [button.name]
    doc.copy()
    pasted = doc.paste()
    assert len(pasted) == 1 and doc.form[pasted[0]].x == 32
    doc.select_all()
    doc.align("top")
    assert {c.y for c in doc.form.controls} == {16}
    doc.nudge(0, 8)
    doc.nudge(0, 8)
    assert {c.y for c in doc.form.controls} == {32}
    doc.undo()  # both nudges are one step
    assert {c.y for c in doc.form.controls} == {16}
    doc.delete()
    assert doc.form.controls == []
    doc.undo()
    assert len(doc.form.controls) == 2


def test_document_events_and_rename(tmp_path):
    doc = Document(Form(name="main", width=400, height=300))
    doc.add("button", 0, 0)
    handler = doc.wire("button1", "click")
    assert handler == "button1_click" and doc.form["button1"].events == {"click": "button1_click"}
    doc.set_handler_source(handler, "def button1_click(form, event):\n    form.button1.text = 'Hi'\n")
    assert doc.rename("button1", "ok") == "ok"
    assert doc.form["ok"].events == {"click": "ok_click"}
    assert "def ok_click(form, event):" in doc.code
    assert doc.wire(None, "load") == "form_load"
    doc.unwire(None, "load", delete_code=True)
    assert "form_load" not in doc.code  # untouched stubs are cleaned up
    path = doc.save(tmp_path / "main")
    assert path.read_text().startswith("{") and (tmp_path / "main.py").exists()
    reopened = Document.open(path)
    assert reopened.form == doc.form and reopened.code == doc.code


# -- runtime -----------------------------------------------------------------


def write_app(tmp_path):
    doc = Document(sample_form())
    doc.wire("greet", "click")
    doc.set_handler_source("greet_click", "def greet_click(form, event):\n"
                                          "    form.status.text = 'Hello, ' + form.user.text\n"
                                          "    form.greet.enabled = False\n")
    doc.wire("user", "change")
    doc.set_handler_source("user_change", "def user_change(form, event):\n"
                                          "    form.status.text = event.value.upper()\n")
    doc.wire(None, "load")
    doc.set_handler_source("form_load", "def form_load(form, event):\n    form.title = 'Loaded'\n")
    return doc.save(tmp_path / "app")


def test_runtime_runs_handlers(tmp_path):
    app = open_form(write_app(tmp_path))
    rt = app.runtime
    rt.load()
    assert app.form.title == "Loaded" and app.title == "Loaded"
    name = rt.form["user"]
    rt.ctx.on(name, "change", "text")("kev")
    assert rt.form["status"].props["text"] == "KEV"
    # callbacks built for a drawing copy still update the form's own control
    copy = Control(**{**name.__dict__, "props": dict(name.props)})
    rt.ctx.on(copy, "change", "text")("ana")
    assert name.props["text"] == "ana"
    rt.dispatch(rt.form["greet"], "click")
    assert rt.form["status"].props["text"] == "Hello, ana"
    assert app.form.greet.enabled is False
    assert rt.error is None


def test_runtime_hot_reload_keeps_values(tmp_path):
    path = write_app(tmp_path)
    app = open_form(path)
    rt = app.runtime
    rt.ctx.on(rt.form["user"], "change", "text")("kev")
    doc = Document.open(path)
    doc.form["greet"].props["text"] = "Say hello"
    doc.set_handler_source("greet_click", "def greet_click(form, event):\n    form.status.text = 'v2'\n")
    doc.save()
    assert rt.reload(path)
    assert rt.form["greet"].props["text"] == "Say hello"
    assert rt.form["user"].props["text"] == "kev"  # what the user typed survives
    rt.dispatch(rt.form["greet"], "click")
    assert rt.form["status"].props["text"] == "v2"
    (tmp_path / "app.py").write_text("def broken(:\n")
    assert not rt.reload(path) and "SyntaxError" in rt.error
    assert rt.form["greet"].props["text"] == "Say hello"  # the running form is untouched


def test_runtime_reports_handler_errors():
    form = sample_form()
    form["greet"].events["click"] = "boom"
    app = FormApp(form, {"boom": lambda form, event: 1 / 0})
    app.runtime.dispatch(app.runtime.form["greet"], "click")
    assert "ZeroDivisionError" in app.runtime.error
    form["greet"].events["click"] = "missing"
    app = FormApp(form, {})
    app.runtime.dispatch(app.runtime.form["greet"], "click")
    assert "not found" in app.runtime.error


def test_form_theme_tweaks():
    form = Form(theme="One Light", accent="#ff8a65", radius=12)
    theme = theme_for(form)
    assert theme.appearance == "light" and theme.accent == "#ff8a65" and theme.radius == 12


def test_runtime_and_designer_screenshots(tmp_path):
    path = write_app(tmp_path)
    open_form(path).screenshot(tmp_path / "run.png", scale=1)
    assert png_size(tmp_path / "run.png") == (400, 300)
    app = designer.Designer(path)
    app.doc.select("greet")
    app.open_default_event("greet")
    assert app.editing and app.editing[0] == "greet_click"
    app.screenshot(tmp_path / "designer.png", size=(1280, 800), scale=1)
    assert png_size(tmp_path / "designer.png") == (1280, 800)


def test_designer_gestures():
    app = designer.Designer()
    app.tool = "button"
    app.pointer = app.view_pointer = (40, 40)
    app.press_empty()
    app.pointer_moved_view(140, 80)
    app.release()
    button = app.doc.form["button1"]
    assert (button.x, button.y, button.width, button.height) == (40, 40, 104, 40)
    assert app.tool is None and app.doc.selection == ["button1"]
    # drag it 20px right: snaps to the grid
    app.view_pointer = (60, 60)
    app.press_control("button1")
    app.pointer_moved_view(81, 60)
    app.release()
    assert button.x == 64
    app.undo()
    assert app.doc.form["button1"].x == 40
    # rubber band selection
    app.pointer = app.view_pointer = (0, 0)
    app.press_empty()
    app.pointer_moved_view(300, 300)
    app.release()
    assert app.doc.selection == ["button1"]


def test_example_form_runs():
    path = ROOT / "examples" / "designer" / "login.pzform"
    app = open_form(path)
    app.runtime.load()
    assert app.runtime.error is None
