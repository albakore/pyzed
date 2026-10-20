"""Tests for containers and layouts, new forms, the console, docks, menus and preferences of the designer."""

import io
import subprocess
import sys

import pytest

from pyzed import designer, ui
from pyzed.designer import commands, docks, layout, new, preferences
from pyzed.designer.app import Designer
from pyzed.designer.document import Document
from pyzed.designer.model import Form
from pyzed.designer.runtime import FormApp, open_form


def place(form, type_, name, x=0, y=0, w=None, h=None, parent=None, **props):
    control = designer.component(type_).create(name, x, y, w, h)
    control.parent = parent
    control.props.update(props)
    return form.add(control)


def row_form():
    form = Form(width=400, height=300)
    place(form, "row", "row1", 10, 10, 300, 40, gap=10)
    for i in range(3):
        place(form, "button", f"b{i}", w=60, h=28, parent="row1")
    return form


# -- model -------------------------------------------------------------------------


def test_hierarchy_and_json(tmp_path):
    form = row_form()
    place(form, "panel", "panel1", 0, 100, 200, 100)
    place(form, "label", "inner", 8, 8, parent="panel1")
    assert [c.name for c in form.children("row1")] == ["b0", "b1", "b2"]
    assert [a.name for a in form.ancestors("inner")] == ["panel1"]
    assert [c.name for c, depth in form.walk()][:4] == ["row1", "b0", "b1", "b2"]
    data = form.to_dict()
    assert "parent" not in data["controls"][0] and data["controls"][1]["parent"] == "row1"
    loaded = designer.load(designer.save(form, tmp_path / "f"))
    assert loaded == form
    form.rename("panel1", "box")
    assert form["inner"].parent == "box"
    assert {c.name for c in form.remove(["box"])} == {"box", "inner"}


def test_broken_parents_are_repaired():
    data = row_form().to_dict()
    data["controls"][1]["parent"] = "missing"
    data["controls"][0]["parent"] = "b1"  # row1 inside its own child: a cycle
    data["controls"][2]["parent"] = "b2"
    form = Form.from_dict(data)
    assert form["b0"].parent is None and form["b1"].parent is None or form["row1"].parent is None
    assert form["b1"].parent != "b1"


# -- layout -------------------------------------------------------------------------


def test_flex_math():
    items = [(50, 20, 0), (50, 20, 1), (50, 20, 0)]
    rects = layout.flex((0, 0, 300, 40), items, gap=10)
    assert [r[0] for r in rects] == [0, 60, 250] and rects[1][2] == 180  # the middle one grows
    assert all(r[3] == 40 for r in rects)  # stretched
    rects = layout.flex((0, 0, 300, 40), [(50, 20, 0)] * 2, justify="center", align="center")
    assert rects[0] == (100, 10, 50, 20)
    rects = layout.flex((0, 0, 300, 40), [(50, 20, 0)] * 3, justify="space-between")
    assert [r[0] for r in rects] == [0, 125, 250]
    rects = layout.flex((0, 0, 100, 300), [(40, 50, 0)] * 2, direction="column", gap=5, align="start")
    assert rects[1] == (0, 55, 40, 50)


def test_grid_math():
    rects = layout.grid((0, 0, 210, 110), [(10, 10, 1)] * 3 + [(10, 10, 2)], columns=2, gap=10)
    assert rects[0] == (0, 0, 100, 30) and rects[1][0] == 110
    assert rects[2][1] == 40  # second row
    assert rects[3] == (0, 80, 210, 30)  # spans both columns on the third row


def test_resolve_nested_and_anchored():
    form = row_form()
    place(form, "panel", "panel1", 0, 100, 200, 100)
    inner = place(form, "label", "inner", 8, 8, 180, 20, parent="panel1")
    inner.anchor = ("left", "top", "right")
    form["panel1"].anchor = ("left", "top", "right")
    rects = layout.resolve(form)
    assert rects["b1"] == (80, 10, 60, 40)
    assert rects["inner"] == (8, 108, 180, 20)
    wider = layout.resolve(form, (500, 300))
    assert wider["panel1"][2] == 300 and wider["inner"][2] == 280  # both stretch with the window
    assert layout.resolve(form, free={"b1"})["b1"][2] == 60  # a dragged control keeps its own size


def test_container_at_and_drop_index():
    form = row_form()
    rects = layout.resolve(form)
    assert layout.container_at(form, rects, 15, 15).name == "row1"
    assert layout.container_at(form, rects, 15, 15, exclude=["row1"]) is None
    assert layout.drop_index(form, rects, form["row1"], 75, 20) == 1


# -- document -------------------------------------------------------------------------


def test_add_reparent_wrap_and_move_out():
    doc = Document(row_form())
    label = doc.add("label", 8, 8, parent="row1")
    assert label.parent == "row1"
    doc.add("panel", 0, 120, 200, 120)
    rects = doc.rects()
    before = rects["b2"]
    doc.reparent(["b2"], "panel1")
    assert doc.form["b2"].parent == "panel1"
    assert doc.rects()["b2"][:2] == before[:2]  # stays where it was
    doc.reparent(["b2"], "row1", index=0)
    assert [c.name for c in doc.form.children("row1")][0] == "b2"
    assert not doc.can_contain("b0", "row1")  # not a container
    doc.move_out("b2")
    assert doc.form["b2"].parent is None
    doc.form["b2"].x, doc.form["b2"].y = 20, 250
    doc.add("button", 120, 250)
    doc.select(["b2", "button1"])
    box = doc.wrap("row")
    assert box is not None and [c.name for c in doc.form.children(box.name)] == ["b2", "button1"]
    assert doc.undo() and doc.form.get(box.name) is None


def test_copy_paste_container_with_children():
    doc = Document(row_form())
    doc.select("row1")
    doc.copy()
    pasted = doc.paste()
    assert pasted == ["row2"]
    assert len(doc.form.children("row2")) == 3


def test_layout_options():
    doc = Document(row_form())
    doc.set_layout("b1", "grow", 1)
    assert doc.form["b1"].layout == {"grow": 1}
    assert doc.rects()["b1"][2] > 60
    doc.set_layout("b1", "grow", 0)
    assert doc.form["b1"].layout == {}


def test_drag_into_a_flex_row():
    app = Designer(language_servers=False)
    app.doc = Document(row_form())
    app.doc.add("button", 40, 200)
    # drag button1 onto the row, between b0 and b1
    app.pointer = app.view_pointer = (50, 210)
    app.press_control("button1")
    app.pointer_moved_view(85, 25)
    assert app.drop_target is not None and app.drop_target.name == "row1"
    app.release()
    assert app.doc.form["button1"].parent == "row1"
    assert [c.name for c in app.doc.form.children("row1")].index("button1") in (1, 2)
    # and out again, onto the form
    rects = app.rects
    x, y = rects["button1"][:2]
    app.pointer = app.view_pointer = (x + 5, y + 5)
    app.press_control("button1")
    app.pointer_moved_view(x + 5, 250)
    app.release()
    assert app.doc.form["button1"].parent is None


def test_placing_a_tool_inside_a_container():
    app = Designer(language_servers=False)
    app.doc = Document(row_form())
    app.tool = "label"
    app.pointer = app.view_pointer = (300, 20)
    app.press_empty()
    app.release()
    assert app.doc.form["label1"].parent == "row1"


# -- new forms -------------------------------------------------------------------------


def test_templates_and_new_form(tmp_path):
    for template in new.templates():
        path = designer.new_form(tmp_path / template.name, template=template.name, title="T")
        form = designer.load(path)
        assert form.title == "T" and path.with_suffix(".py").exists()
        layout.resolve(form)
    with pytest.raises(FileExistsError):
        designer.new_form(tmp_path / "blank")
    app = open_form(tmp_path / "dialog.pzform")
    result = app.runtime.dispatch(app.runtime.form["ok"], "click")
    assert result is not None and app.runtime.error is None  # the template's handler closes the window


def test_new_form_dialog(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = Designer(language_servers=False)
    app.new()
    assert app.dialog == "new" and app.new_state["name"] == "form1"
    app.set_new("name", "settings")
    app.set_new("template", "settings")
    assert app.dialog_view(app.theme_obj) is not None
    app.create_new_form()
    assert (tmp_path / "settings.pzform").exists() and app.doc.form.name == "Settings"
    assert app.prefs.recent and app.prefs.recent[0].endswith("settings.pzform")


def test_running_forms_open_other_forms(tmp_path):
    designer.new_form(tmp_path / "main")
    designer.new_form(tmp_path / "other", template="login")
    app = open_form(tmp_path / "main.pzform")
    logged = []
    app.runtime.log = lambda level, text: logged.append(level)
    assert app.form.open("other", data={"email": "ada@example.com"}) is not None
    window = app.runtime.opened[0]
    assert window.form.data == {"email": "ada@example.com"} and window.runtime.log is app.runtime.log
    assert app.form.windows == []  # not open until the command runs


# -- console -------------------------------------------------------------------------


def test_log_capture_folding_and_pipe():
    log = ui.Log()
    with log:
        print("hello")
        print("hello")
        print("oops", file=sys.stderr)
    assert [(e.level, e.text, e.count) for e in log.entries] == [("stdout", "hello", 2), ("stderr", "oops", 1)]
    assert not log.capturing and "×2" in log.text()
    thread = log.pipe(io.BytesIO(b"one\nTraceback (most recent call last):\n"), "auto")
    thread.join(2)
    assert [e.level for e in log.entries[-2:]] == ["stdout", "stderr"]
    assert ui.console(log.entries, query="one", hidden={"stderr"}) is not None


def test_runtime_logs_events_and_errors():
    form = Form()
    place(form, "button", "go")
    form["go"].events["click"] = "go_click"
    form["go"].events["double_click"] = "boom"
    app = FormApp(form, {"go_click": lambda f, e: None, "boom": lambda f, e: 1 / 0})
    lines = []
    app.runtime.log = lambda level, text: lines.append((level, text))
    app.runtime.dispatch(app.runtime.form["go"], "click")
    app.runtime.dispatch(app.runtime.form["go"], "double_click")
    assert lines[0] == ("event", "go.click → go_click()")
    assert lines[-1][0] == "error" and "ZeroDivisionError" in lines[-1][1] and "runtime.py" not in lines[-1][1]


def test_designer_run_fills_the_console(tmp_path):
    path = designer.new_form(tmp_path / "hello", template="dialog")
    doc = Document.open(path)
    doc.set_handler_source("ok_click", "def ok_click(form, event):\n    print('pressed')\n")
    doc.save()
    app = Designer(path, language_servers=False)
    app.run_form()
    assert app.console.running and app.layout.is_showing("console", app)
    app.preview.runtime.dispatch(app.preview.runtime.form["ok"], "click")
    texts = [e.text for e in app.console.log.entries]
    assert "ok.click → ok_click()" in texts and "pressed" in texts
    app.stop_form()
    assert app.console.running is None and not app.console.log.capturing
    assert app.console.log.entries[-1].text.endswith("stopped")


def test_uv_run_output_is_piped(tmp_path):
    app = Designer(language_servers=False)
    process = subprocess.Popen([sys.executable, "-c", "print('from the child')"], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    app.console.pipe(process)
    process.wait(5)
    for _ in range(100):
        if any(e.text == "■ process ended" for e in app.console.log.entries):
            break
        import time

        time.sleep(0.02)
    assert "from the child" in [e.text for e in app.console.log.entries]


# -- docks, menus, commands and preferences ----------------------------------------------


def test_dock_layout():
    app = Designer(language_servers=False)
    lay = app.layout
    assert lay.shown("left", app).id == "design" and lay.shown("bottom", app) is None
    app.show_panel("console")
    assert lay.shown("bottom", app).id == "console"
    app.move_panel("console", "left")
    assert lay.shown("left", app).id == "console" and lay.shown("bottom", app) is None
    app.toggle_dock("left")
    assert not app.dock_visible("left")
    app.resize_dock("right", 50)
    assert lay.sizes["right"] == docks.MIN_SIZE["right"]
    again = preferences.load()
    assert again.docks["console"] == "left"
    app.reset_layout()
    assert app.layout.docks["console"] == "bottom"
    app.right_tab = "events"
    assert app.right_tab == "events"
    assert app.view() is not None


def test_every_command_runs(monkeypatch):
    app = Designer(language_servers=False)
    monkeypatch.setattr(app, "open_url", lambda url: None)
    app.doc.add("button", 10, 10)
    for action in commands.ACTIONS:
        if action.id in ("run", "stop"):
            continue
        app.dialog = None
        app.run_action(action.id)
        app.view()
        if app.dialog:
            assert app.dialog_view(app.theme_obj) is not None, action.id
    assert commands.by_keys("ctrl-shift-p", global_only=True).id == "palette"
    assert commands.by_keys("cmd-s", global_only=True).id == "save"
    assert commands.by_keys("delete", global_only=True) is None
    assert any(group == "Canvas" for group, _ in commands.shortcut_groups())


def test_menus_and_keys():
    app = Designer(language_servers=False)
    t = app.theme_obj
    for name in ("file", "view", "help"):
        app.toggle_app_menu(name)
        assert app.app_menu == name and app.view() is not None and app.title_menu(name, t) is not None
    app.on_key("escape")
    assert app.app_menu is None
    app.on_key("ctrl-shift-p")
    assert app.dialog == "palette"
    app.set_picker_query("grid")
    app.on_key("down")
    assert app.picker_index == 1
    app.on_key("escape")
    app.on_key("ctrl-shift-a")
    assert app.dialog == "add_control"
    app.add_child("switch")
    assert app.doc.form.get("switch1") is not None and app.dialog is None


def test_add_child_from_the_outline():
    app = Designer(language_servers=False)
    app.doc = Document(row_form())
    app.open_add_child("row1")
    app.add_child("checkbox")
    assert app.doc.form["checkbox1"].parent == "row1"
    app.toggle_folded("row1")
    assert "row1" in app.folded and app.view() is not None
    app.open_outline_menu("checkbox1")
    assert app.menu is not None and app.context_menu(app.theme_obj) is not None


def test_preferences_roundtrip():
    app = Designer(language_servers=False)
    app.set_pref("show_grid", False)
    app.set_designer_theme("Ayu Dark")
    app.set_language("es")
    prefs = preferences.load()
    assert prefs.show_grid is False and prefs.theme == "Ayu Dark" and prefs.language == "es"
    assert Designer(language_servers=False).show_grid is False
    assert preferences.DesignerSettings.from_dict({"grid": 999, "docks": {"x": "nowhere"}}).grid == 64


def test_language_switch_translates_the_designer(tmp_path):
    from pyzed import i18n

    app = Designer(tmp_path / "a.pzform", language_servers=False)
    try:
        app.set_language("es")
        assert commands.BY_ID["save_as"].label == "Guardar como…" and docks.PANELS["properties"].title == "Propiedades"
        assert app.title_menu("file", app.theme_obj) is not None and app.dialog_view(app.theme_obj) is None
        app.open_settings()
        assert app.dialog_view(app.theme_obj) is not None
        assert preferences.load().language == "es"
    finally:
        i18n.set_language("en")
    assert commands.BY_ID["save_as"].label == "Save as…"


def test_unsaved_changes_save_then_continue(tmp_path):
    app = Designer(tmp_path / "a.pzform", language_servers=False)
    app.doc.dirty = True
    app.close_doc()  # closing a tab with unsaved changes asks first
    assert app.dialog == "confirm" and app.dialog_view(app.theme_obj) is not None
    app.confirm_save()
    assert (tmp_path / "a.pzform").exists() and app.doc.path is None and len(app.docs) == 1


# -- context menu and dragging out of the panels -------------------------------------


def sidebar_app(tmp_path):
    path = new.new_form(tmp_path / "shell", template="sidebar")
    app = Designer(path, language_servers=False)
    app.window_size = (1440, 900)
    return app


def test_context_menu_opens_at_the_pointer_and_stays_in_the_window(tmp_path):
    app = sidebar_app(tmp_path)
    app.window_moved(300, 200)
    app.open_context_menu("nav1")
    assert app.menu == ("nav1", 300, 200)
    _, x, y = app.context_menu_at(app.theme_obj)
    assert (x, y) == (300, 200) and app.view() is not None
    app.window_moved(1400, 880)  # near the bottom-right corner: it opens up and to the left
    app.open_outline_menu("body")
    _, x, y = app.context_menu_at(app.theme_obj)
    assert x + 220 <= 1440 and 0 < y < 880 and app.doc.selection == ["body"]


def test_drag_a_component_from_the_toolbox_into_a_container(tmp_path):
    app = sidebar_app(tmp_path)
    app.window_moved(40, 250)
    app.press_tool("button")
    app.window_moved(600, 400)
    app.enter_form()
    app.pointer_moved(400, 300)  # inside "content", a flex column
    assert app.drop_name == "content" and app.carry_ghost(app.theme_obj) is not None
    app.window_release()
    button = app.doc.form["button1"]
    assert button.parent == "content" and app.carry is None and app.tool is None
    assert [c.name for c in app.doc.form.children("content")][-1] == "button1"


def test_a_click_in_the_toolbox_still_picks_the_tool(tmp_path):
    app = sidebar_app(tmp_path)
    app.press_tool("label")
    app.window_release()
    assert app.tool == "label" and app.doc.form.get("label1") is None


def test_dropping_a_component_outside_the_form_does_nothing(tmp_path):
    app = sidebar_app(tmp_path)
    app.press_tool("label")
    app.window_moved(200, 200)
    app.window_release()
    assert app.tool is None and app.doc.form.get("label1") is None


def test_drag_in_the_outline_reorders_and_moves_into_containers(tmp_path):
    app = sidebar_app(tmp_path)
    form = app.doc.form

    def drag(name, target, y):
        app.window_moved(10, 10)
        app.press_outline(name)
        app.window_moved(300, 300)
        app.hover_outline(target, y, 24)
        app.window_release()

    drag("nav3", "nav1", 2)  # before nav1, in a flex column: first
    assert [c.name for c in form.children("sidebar")] == ["nav3", "nav1", "nav2"]
    drag("nav3", "nav2", 22)  # after nav2: last again
    assert [c.name for c in form.children("sidebar")] == ["nav1", "nav2", "nav3"]
    drag("nav1", "content", 12)  # the middle of a container: inside it, at the end
    assert form["nav1"].parent == "content" and form.children("content")[-1].name == "nav1"
    app.window_moved(10, 10)
    app.press_outline("sidebar")
    app.window_moved(300, 300)
    app.hover_outline("nav2", 12, 24)  # a container cannot go inside itself
    assert app.outline_target in (None, ("nav2", "after"))
    app.hover_outline("content", 12, 24)
    app.window_release()
    assert form["sidebar"].parent == "content"


def test_drag_from_the_outline_onto_the_form(tmp_path):
    app = sidebar_app(tmp_path)
    app.press_outline("nav2")
    app.window_moved(600, 400)
    app.enter_form()
    app.pointer_moved(500, 300)
    assert app.drop_name == "content"
    app.window_release()
    assert app.doc.form["nav2"].parent == "content"
    app.press_outline("nav2")
    app.window_moved(620, 420)
    app.exit_form()
    app.window_release()  # released over a panel: nothing changes
    assert app.doc.form["nav2"].parent == "content"


def test_containers_show_a_grip_that_selects_and_drags_them(tmp_path):
    from pyzed.designer import surface

    app = sidebar_app(tmp_path)
    assert surface.grips(app) == []
    app.enter_form()
    app.pointer_moved(100, 20)  # over nav1, inside the sidebar
    assert surface.grips(app) == [("sidebar", 7.0, 1.0)]  # touches the top: the tab goes inside
    app.press_control("nav1")  # a press on the child still picks the child
    assert [c.name for c in app.doc.selected] == ["nav1"]
    app.release()
    app.exit_form()
    assert [g[0] for g in surface.grips(app)] == ["sidebar"]  # the parent of the selection keeps its tab
    app.window_moved(50, 50)
    app.pointer_moved_view(50, 50)
    app.press_control("sidebar")  # what the grip does
    assert [c.name for c in app.doc.selected] == ["sidebar"] and app.drag.mode == "move"
    assert surface.grips(app) == []  # hidden while dragging
    app.pointer_moved_view(90, 70)
    app.release()
    assert app.doc.form.get("sidebar").x != 0 or app.doc.form.get("sidebar").y != 0
    assert app.view() is not None


def test_empty_containers_and_plain_controls_have_no_grip(tmp_path):
    from pyzed.designer import surface

    app = sidebar_app(tmp_path)
    app.doc.select("title1")
    assert [g[0] for g in surface.grips(app)] == ["content"]
    empty = app.doc.add("row", 300, 300, 200, 48)
    app.doc.select(empty.name)
    assert surface.grips(app) == []
    app.doc.select("title1")
    app.tool = "button"
    assert surface.grips(app) == []


def test_the_toolbar_shows_selection_tools_only_with_a_selection():
    from pyzed import Widget
    from pyzed.designer.app import Designer

    app = Designer(language_servers=False)
    assert isinstance(app.toolbar(app.theme_obj), Widget)  # a hint instead of the align tools
    app.doc.add("button", 10, 10)
    app.doc.select("button1")
    assert isinstance(app.toolbar(app.theme_obj), Widget)
    app.new()  # "New…" opens the dialog with the form, component and shader cards
    assert app.dialog == "new" and app.new_state["kind"] == "form"
    app.close_dialog()
    app.new_component()  # the toolbox's "New component…" row
    assert app.new_state["kind"] == "component"
