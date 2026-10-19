"""Tests for document tabs in more than one window: detaching, stacking, reordering and closing."""

from types import SimpleNamespace

from pyzed import _core, ui
from pyzed.designer.app import Designer
from pyzed.designer.document import Document
from pyzed.designer.windows import DocWindow
from pyzed.events import Event


def designer_with(*names):
    d = Designer(language_servers=False)
    for i, name in enumerate(names):
        doc = Document()
        doc.form.name = name
        doc.add("button", 10, 10)  # not an empty untitled form, so it gets its own tab
        if i == 0:
            d.panes.main.docs[0] = doc
        else:
            d.doc = doc
    return d


def names(pane):
    return [doc.form.name for doc in pane.docs]


def released(x, y, screen=None):
    return SimpleNamespace(window_x=x, window_y=y, screen=screen)


def test_detach_opens_a_window_with_the_tab():
    d = designer_with("a", "b", "c")
    commands = d.panes.detach(d.panes.main, 1, (500.0, 300.0))
    assert isinstance(commands[0], _core.Command)
    main, pane = d.panes.panes
    assert names(main) == ["a", "c"] and names(pane) == ["b"]
    assert isinstance(pane.window, DocWindow) and pane.window.position == (410.0, 286.0)
    # the new window is the one being worked in: the panels follow its document
    assert d.panes.active is pane and d.doc.form.name == "b"
    assert "b" in pane.window.window_title()
    d.view()
    pane.window.view()


def test_the_command_moves_the_tab_out_and_back():
    d = designer_with("a", "b")
    d.run_action("tab_to_window")
    pane = d.panes.active
    assert pane is not d.panes.main and names(pane) == ["b"]
    d.run_action("tab_to_main")
    assert d.panes.active is d.panes.main and names(d.panes.main) == ["a", "b"]
    assert d.panes.panes == [d.panes.main]  # the empty window went away


def test_drag_along_the_row_reorders():
    d = designer_with("a", "b", "c")
    main = d.panes.main
    d.panes.start_drag(main, "0")
    d.panes.drag_over(3)  # past the last tab
    d.panes.drop(main, "0", released(40, 10))
    assert names(main) == ["b", "c", "a"]
    assert main.doc.form.name == "c"  # the tab in front stays in front


def test_drop_inside_the_window_moves_nothing():
    d = designer_with("a", "b")
    d.window_size = (1000, 700)
    d.panes.start_drag(d.panes.main, "1")
    d.panes.drag_over(None)
    assert d.panes.drop(d.panes.main, "1", released(500, 400)) is None
    assert len(d.panes.panes) == 1 and names(d.panes.main) == ["a", "b"]


def test_drop_outside_opens_a_window_and_onto_a_window_stacks():
    d = designer_with("a", "b", "c")
    d.window_size, d.window_position = (1000, 700), (0, 0)
    d.panes.start_drag(d.panes.main, "2")
    d.panes.drop(d.panes.main, "2", released(1200, 300, (1200, 300)))
    pane = d.panes.panes[1]
    assert names(pane) == ["c"]
    pane.window.window_size, pane.window.window_position = (800, 600), (1100, 280)
    # drag "b" from the main window onto the new window: it joins its tabs
    d.panes.start_drag(d.panes.main, "1")
    d.panes.drop(d.panes.main, "1", released(1300, 400, (1300, 400)))
    assert names(pane) == ["c", "b"] and names(d.panes.main) == ["a"]
    assert d.panes.active is pane and pane.doc.form.name == "b"
    # and back: drop "c" over the main window
    d.panes.start_drag(pane, "0")
    d.panes.drop(pane, "0", released(-600, 100, (500, 380)))
    assert names(d.panes.main) == ["a", "c"] and names(pane) == ["b"]


def test_last_tab_dragged_off_moves_its_window():
    d = designer_with("a", "b")
    d.panes.detach(d.panes.main, 1)
    pane = d.panes.panes[1]
    pane.window.window_size = (800, 600)
    d.panes.start_drag(pane, "0")
    command = d.panes.drop(pane, "0", released(900, 50, (2000, 400)))
    assert isinstance(command, _core.Command) and names(pane) == ["b"]


def test_closing_a_window_keeps_its_tabs():
    d = designer_with("a", "b", "c")
    d.panes.detach(d.panes.main, 1)
    d.panes.move(d.panes.main, 1, d.panes.panes[1])  # "c" joins it
    pane = d.panes.panes[1]
    pane.window.on_close()
    assert d.panes.panes == [d.panes.main] and names(d.panes.main) == ["a", "b", "c"]
    assert d.panes.active is d.panes.main and d.doc.form.name == "c"


def test_closing_the_last_tab_of_a_window_closes_it():
    d = designer_with("a", "b")
    d.panes.detach(d.panes.main, 1)
    pane = d.panes.panes[1]
    pane.window._pyzed_window_open = True
    assert d.panes.close(pane, "0") is None and d.dialog == "confirm"  # it has unsaved changes
    command = d.confirm_discard()
    assert isinstance(command, _core.Command)
    assert d.panes.panes == [d.panes.main] and d.panes.active is d.panes.main


def test_opening_a_file_open_in_another_window_shows_it_there(tmp_path):
    d = designer_with("a")
    path = tmp_path / "other.pzform"
    d.doc.form.name = "other"
    d.doc.save(path)
    d.doc = Document()
    d.doc.add("button", 1, 1)
    d.panes.detach(d.panes.main, 0)
    assert d.panes.active is not d.panes.main
    d.panes.activate(d.panes.main)
    d.open_path(path)
    assert d.panes.active is d.panes.panes[1] and d.doc.path == path
    assert len(d.panes.all_docs()) == 2


def test_an_inactive_pane_wakes_up_on_the_first_press():
    d = designer_with("a", "b")
    d.panes.detach(d.panes.main, 1)
    pane = d.panes.panes[1]
    d.doc.select("button1")
    assert d.panes.activate(d.panes.main)
    assert d.doc.form.name == "a"
    with d.panes.showing(pane):
        assert d.doc.form.name == "b" and d.drag is None
    assert d.panes.active is d.panes.main
    d.view()
    pane.window.view()
    assert d.panes.select(pane, "0") is None and d.panes.active is pane


def test_tab_bar_reports_drags_and_draws_the_drop_mark():
    seen = []
    tabs = [ui.Tab("x", "x.py"), ui.Tab("y", "y.py")]
    bar = ui.tab_bar(tabs, "x", on_drag=seen.append, on_drop=lambda i, e: seen.append((i, e)),
                     on_drag_over=seen.append, dragging="x", drop_index=1)
    assert isinstance(bar, _core.Widget)
    assert isinstance(ui.tab_bar(tabs, "x"), _core.Widget)


def test_event_screen_point():
    assert Event("drag_end", window_x=5, window_y=6).screen is None
    event = Event("drag_end", window_x=5, window_y=6, screen_x=105.0, screen_y=206.0)
    assert event.screen == (105.0, 206.0) and "screen_x" in repr(event)
