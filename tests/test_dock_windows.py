"""Tests for panels in windows of their own, dragging panel tabs between docks and work layouts."""

from types import SimpleNamespace

from pyzed import _core
from pyzed.designer import docks, preferences
from pyzed.designer.app import Designer
from pyzed.designer.dock_windows import DockWindow
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
    assert isinstance(window, DockWindow) and d.layout.docks["console"] == "window:1"
    assert window.position[0] == 700.0 - 90.0
    window.view()
    d.view()
    # another panel stacks in that window, from the dock menu, and the window comes to the front
    window._pyzed_window_open = True
    assert any(isinstance(c, _core.Command) for c in d.move_panel("code", "window:1"))
    assert d.show_panel("code") is not None
    assert ids(d, "window:1") == ["code", "console"] or ids(d, "window:1") == ["console", "code"]
    closing = d.dock_windows.dock_back("window:1")
    assert isinstance(closing[0], _core.Command)
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
    # released over the canvas: nothing moves
    d.dock_windows.start_drag("bottom", "events")
    assert d.dock_windows.drop("bottom", "events", released(700, 300)) is None


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


def test_the_drop_hint_shows_the_target_dock():
    d = designer()
    t = d.theme_obj
    assert isinstance(d.dock_windows.drop_hint(t), _core.Widget)
    d.dock_windows.start_drag("right", "events")
    d.window_pointer = (60.0, 400.0)
    assert isinstance(d.dock_windows.drop_hint(t), _core.Widget)
    d.view()


def test_work_layouts_save_switch_and_delete():
    d = designer()
    assert d.dock_windows.names()[:2] == ["Default", "Coding"]
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
    assert docks.valid_place("window:3") and not docks.valid_place("window:")
