"""Tests for tabs anywhere: panels and documents dragged between docks, the center and windows, and work layouts."""

from types import SimpleNamespace

from pyzed import _core
from pyzed.designer import docks, preferences
from pyzed.designer.app import Designer
from pyzed.designer.document import Document
from pyzed.designer.windows import DocWindow
from pyzed.designer.docks import DockLayout


def designer():
    d = Designer(language_servers=False)
    d.window_size, d.window_position = (1400.0, 900.0), (0.0, 0.0)
    return d


def released(x, y, screen=None):
    return SimpleNamespace(window_x=x, window_y=y, screen=screen)


def ids(d, place):
    return d.layout.all_in(place)


def test_layout_moves_reorders_and_round_trips():
    layout = DockLayout()
    layout.move("events", "left", before="design")
    assert layout.all_in("left")[0] == "events" and layout.home["events"] == "left"
    place = layout.new_window()
    layout.move("console", place)
    assert place == "window:1" and layout.window_places() == ["window:1"]
    assert layout.place_label("console") == "Window"
    copy = DockLayout.from_snapshot(layout.snapshot())
    assert copy.docks == layout.docks and copy.order == layout.order
    assert copy.send_home("window:1") == ["console"] and copy.docks["console"] == "bottom"
    assert copy.window_places() == [] and copy.windows == {}


def test_a_panel_detaches_into_its_own_window_and_docks_back():
    d = designer()
    commands = d.dock_windows.detach("console", (700.0, 400.0))
    assert isinstance(commands[0], _core.Command)
    window = d.dock_windows.open["window:1"]
    assert isinstance(window, DocWindow) and d.layout.docks["console"] == "window:1"
    assert window.position[0] == 700.0 - 90.0
    window.view()
    d.view()
    # another panel stacks in that window, from the dock menu, and the window comes to the front
    window._pyzed_window_open = True
    assert any(isinstance(c, _core.Command) for c in d.move_panel("code", "window:1"))
    assert d.show_panel("code") is not None
    assert ids(d, "window:1") == ["code", "console"] or ids(d, "window:1") == ["console", "code"]
    window._pyzed_window_open = True
    closing = d.dock_windows.dock_back("window:1")
    assert isinstance(closing, _core.Command)
    assert d.layout.docks["console"] == "bottom" and d.layout.docks["code"] == "bottom"
    assert d.dock_windows.open == {}


def test_closing_a_panel_window_sends_its_panels_home():
    d = designer()
    d.layout.move("properties", "left")
    d.dock_windows.detach("properties")
    d.dock_windows.open["window:1"].on_close()
    assert d.layout.docks["properties"] == "left"  # the last dock it was in
    assert d.dock_windows.open == {} and d.layout.window_places() == []


def test_dragging_a_tab_along_a_row_reorders_it():
    d = designer()
    d.dock_windows.start_drag("right", "agent")
    d.dock_windows.drag_over("right", 0)
    d.dock_windows.drop("right", "agent", released(1300, 50))
    assert ids(d, "right")[0] == "agent"
    # dropped where it already is: nothing moves
    d.dock_windows.start_drag("right", "agent")
    d.dock_windows.drag_over("right", 1)
    assert d.dock_windows.drop("right", "agent", released(1300, 50)) is None


def test_dragging_a_tab_onto_another_dock_row_or_zone_moves_it():
    d = designer()
    d.dock_windows.start_drag("right", "events")
    d.dock_windows.drag_over("left", 1)
    d.dock_windows.drag_over("right", None)  # leaving the source row does not forget the target row
    d.dock_windows.drop("right", "events", released(100, 50))
    assert d.layout.docks["events"] == "left" and ids(d, "left").index("events") == 1
    # released over the bottom dock's zone, off any tab row
    d.dock_windows.start_drag("left", "events")
    assert d.dock_windows.dock_at(700, 800) == "bottom"
    d.dock_windows.drop("left", "events", released(700, 800))
    assert d.layout.docks["events"] == "bottom"
    # released over the bottom dock again: nothing moves
    d.dock_windows.start_drag("bottom", "events")
    assert d.dock_windows.drop("bottom", "events", released(700, 800)) is None


def test_dragging_a_tab_out_and_onto_windows():
    d = designer()
    d.dock_windows.start_drag("bottom", "console")
    d.dock_windows.drop("bottom", "console", released(1500, 300, (1500.0, 300.0)))
    assert d.layout.docks["console"] == "window:1"
    window = d.dock_windows.open["window:1"]
    window.window_size, window.window_position = (440.0, 600.0), (1450.0, 250.0)
    # the Agent panel dropped onto that window stacks there
    d.dock_windows.start_drag("right", "agent")
    d.dock_windows.drop("right", "agent", released(1600, 400, (1600.0, 400.0)))
    assert d.layout.docks["agent"] == "window:1"
    # and the console dropped over the main window's left side docks there
    d.dock_windows.start_drag("window:1", "console")
    d.dock_windows.drop("window:1", "console", released(-1400, 200, (50.0, 450.0)))
    assert d.layout.docks["console"] == "left"


def test_the_drag_layer_shows_the_target_and_a_copy_of_the_tab():
    d = designer()
    t = d.theme_obj
    main = d.panes.main
    assert isinstance(d.dock_windows.drag_layer(main, t), _core.Widget)
    d.dock_windows.start_drag("right", "events")
    d.window_pointer = (60.0, 400.0)
    assert d.dock_windows.zone_at(60, 400) == "left"
    assert isinstance(d.dock_windows.ghost(t), _core.Widget)
    assert isinstance(d.dock_windows.drag_layer(main, t), _core.Widget)
    d.view()
    d.dock_windows.drag_over("left", 0)
    d.view()
    d.dock_windows.drag = None
    d.dock_windows.start_drag("main", "0")  # a form tab
    assert isinstance(d.dock_windows.ghost(t), _core.Widget)
    d.view()


def test_a_panel_joins_the_form_tabs_in_the_center():
    d = designer()
    # dropped over the canvas: the Events panel becomes a tab next to the forms, in front
    d.dock_windows.start_drag("right", "events")
    assert d.dock_windows.zone_at(700, 300) == "main"
    d.dock_windows.drop("right", "events", released(700, 300))
    assert d.layout.docks["events"] == "main" and docks.front(d, "main")[0] == "panel"
    d.view()
    # the form's tab brings the form back; the panel's tab the panel
    d.panes.select(d.panes.main, "0")
    assert docks.front(d, "main") == ("doc", d.panes.main)
    d.show_panel("events")
    assert docks.front(d, "main")[1].id == "events"
    # its × sends it back to the dock it came from
    d.dock_windows.send_back("main", "events")
    assert d.layout.docks["events"] == "right"
    # the dock menu has the center too
    d.move_panel("code", "main")
    assert d.layout.place_label("code") == "Center"


def test_a_panel_tab_dropped_on_the_form_row_and_reordered():
    d = designer()
    d.dock_windows.start_drag("right", "agent")
    d.dock_windows.drag_over("main", 1)
    d.dock_windows.drop("right", "agent", released(500, 40))
    assert d.layout.docks["agent"] == "main"
    assert d.dock_windows._row("main") == ["0", "agent"]


def test_a_form_goes_into_a_dock_and_back():
    d = designer()
    doc = Document()
    doc.form.name = "second"
    doc.add("button", 10, 10)
    d.doc.add("button", 10, 10)  # not an empty untitled form, so the new one gets its own tab
    d.doc = doc  # two forms in the center
    d.dock_windows.start_drag("main", "1")
    d.dock_windows.drop("main", "1", released(60, 400))  # over the left dock
    left = d.panes.docked["left"]
    assert [x.form.name for x in left.docs] == ["second"] and d.panes.active is left
    assert docks.front(d, "left") == ("doc", left) and d.dock_visible("left")
    assert d.dock_windows._row("left")[0] == "0"
    d.view()
    # the panels of that dock stay as tabs; one picked comes in front, the form's tab brings it back
    d.show_panel("design")
    assert docks.front(d, "left")[0] == "panel"
    d.panes.select(left, "0")
    assert docks.front(d, "left") == ("doc", left)
    # hiding the dock gives the panels back to the main window's form
    d.toggle_dock("left")
    assert d.panes.active is d.panes.main
    d.toggle_dock("left")
    # dragged onto the center's tab row, it goes back among the forms
    d.dock_windows.start_drag("left", "0")
    d.dock_windows.drag_over("main", 0)
    d.dock_windows.drop("left", "0", released(500, 40))
    assert [x.form.name for x in d.panes.main.docs][0] == "second" and not left.docs


def test_a_panel_stacks_with_the_forms_of_another_window():
    d = designer()
    doc = Document()
    doc.form.name = "second"
    doc.add("button", 10, 10)
    d.doc.add("button", 10, 10)  # not an empty untitled form, so the new one gets its own tab
    d.doc = doc
    d.panes.detach(d.panes.main, 1, (1600.0, 300.0))
    pane = d.panes.panes[1]
    pane.window.window_size, pane.window.window_position = (900.0, 700.0), (1500.0, 200.0)
    d.dock_windows.start_drag("right", "properties")
    d.dock_windows.drop("right", "properties", released(1700, 400, (1700.0, 400.0)))
    assert d.layout.docks["properties"] == pane.place and docks.front(d, pane.place)[0] == "panel"
    assert d.dock_windows._row(pane.place) == ["0", "properties"]
    pane.window.view()
    # closing the window: the form goes to the main window and the panel back to its dock
    pane.window.on_close()
    assert d.layout.docks["properties"] == "right" and len(d.panes.main.docs) == 2


def test_work_layouts_save_switch_and_delete():
    d = designer()
    assert d.dock_windows.names()[:2] == ["Default", "Coding"] and "Code with the forms" in d.dock_windows.names()
    d.use_layout("Coding")
    assert d.layout.docks["code"] == "right" and d.prefs.layout_name == "Coding"
    d.dock_windows.detach("console")
    d.ask_layout_name()
    assert d.dialog == "save_layout" and d.dialog_view(d.theme_obj) is not None
    d.set_layout_name("Mine")
    d.save_layout_as()
    assert d.dialog is None and "Mine" in d.dock_windows.names()
    d.dock_windows.open["window:1"]._pyzed_window_open = True
    commands = d.use_layout("Default")
    assert isinstance(commands[0], _core.Command) and d.dock_windows.open == {}
    d.use_layout("Mine")
    assert d.layout.docks["console"] == "window:1" and "window:1" in d.dock_windows.open
    d.delete_layout()
    assert "Mine" not in d.prefs.layouts
    d.use_layout("Code with the forms")
    assert d.layout.docks["code"] == "main"


def test_panel_windows_are_saved_and_restored():
    d = designer()
    d.dock_windows.detach("agent")
    window = d.dock_windows.open["window:1"]
    window.window_size, window.window_position = (500.0, 700.0), (1500.0, 100.0)
    d._save_layout()
    prefs = preferences.load()
    assert prefs.docks["agent"] == "window:1" and prefs.windows["window:1"]["position"] == [1500.0, 100.0]
    again = Designer(language_servers=False)
    commands = again.dock_windows.restore()
    reopened = again.dock_windows.open["window:1"]
    assert reopened.size == (500.0, 700.0) and reopened.position == (1500.0, 100.0)
    assert any(isinstance(c, _core.Command) for c in commands)


def test_preferences_keep_only_valid_places():
    prefs = preferences.DesignerSettings.from_dict({"docks": {"code": "window:2", "agent": "nowhere",
                                                              "console": "window:x"}})
    assert prefs.docks == {"code": "window:2"}
    assert docks.valid_place("window:3") and docks.valid_place("main") and not docks.valid_place("window:")
    assert preferences.DesignerSettings.from_dict({"docks": {"code": "main"}}).docks == {"code": "main"}
