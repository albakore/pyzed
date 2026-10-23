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
    dx, dy = d.panes.grab_offset()
    assert isinstance(pane.window, DocWindow) and pane.window.position == (500.0 - dx, 300.0 - dy)
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
    d.dock_windows.start_drag(main.place, "0")
    d.dock_windows.drag_over("main", 3)  # past the last tab
    d.dock_windows.drop(main.place, "0", released(40, 10))
    assert names(main) == ["b", "c", "a"]
    assert main.doc.form.name == "c"  # the tab in front stays in front


def test_drop_inside_the_window_moves_nothing():
    d = designer_with("a", "b")
    d.window_size = (1000, 700)
    d.dock_windows.start_drag("main", "1")
    d.dock_windows.drag_over("main", None)
    assert d.dock_windows.drop("main", "1", released(500, 400)) is None
    assert len(d.panes.panes) == 1 and names(d.panes.main) == ["a", "b"]


def test_drop_outside_opens_a_window_and_onto_a_window_stacks():
    d = designer_with("a", "b", "c")
    d.window_size, d.window_position = (1000, 700), (0, 0)
    d.dock_windows.start_drag("main", "2")
    d.dock_windows.drop("main", "2", released(1200, 300, (1200, 300)))
    pane = d.panes.panes[1]
    assert names(pane) == ["c"]
    pane.window.window_size, pane.window.window_position = (800, 600), (1100, 280)
    # drag "b" from the main window onto the new window: it joins its tabs
    d.dock_windows.start_drag("main", "1")
    d.dock_windows.drop("main", "1", released(1300, 400, (1300, 400)))
    assert names(pane) == ["c", "b"] and names(d.panes.main) == ["a"]
    assert d.panes.active is pane and pane.doc.form.name == "b"
    # and back: drop "c" over the main window
    d.dock_windows.start_drag(pane.place, "0")
    d.dock_windows.drop(pane.place, "0", released(-600, 100, (500, 380)))
    assert names(d.panes.main) == ["a", "c"] and names(pane) == ["b"]


def test_last_tab_dragged_off_moves_its_window():
    d = designer_with("a", "b")
    d.panes.detach(d.panes.main, 1)
    pane = d.panes.panes[1]
    pane.window.window_size = (800, 600)
    d.dock_windows.start_drag(pane.place, "0")
    command = d.dock_windows.drop(pane.place, "0", released(900, 50, (2000, 400)))
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


def test_closing_every_tab_leaves_the_main_window_empty():
    d = designer_with("a", "b")
    for doc in d.docs:
        doc.dirty = False
    d.close_doc()
    d.close_doc()
    assert d.nothing_open and len(d.panes.main.docs) == 1  # a hidden blank form stands in
    tabs, _, _ = d.doc_tab_items(d.panes.main, d.theme_obj)
    assert tabs == [] and d.window_title() == "Pyzed Design"
    assert d.close_doc() is None and d.nothing_open  # nothing left to close
    assert d.save() is None and d.dialog is None  # nothing to save
    assert d.run_form() is None and d.toasts[-1].title == "Nothing to run"
    d.view()  # the empty area and the form panels' empty states draw

    doc = Document()
    doc.form.name = "c"
    d.doc = doc  # opening a document takes the blank one's place
    assert not d.nothing_open and names(d.panes.main) == ["c"]


def test_a_control_added_with_nothing_open_makes_a_new_form():
    d = designer_with("a")
    d.doc.dirty = False
    d.close_doc()
    assert d.nothing_open
    d.doc.add("button", 10, 10)
    d.doc.dirty = True
    assert not d.nothing_open and len(d.doc_tab_items(d.panes.main, d.theme_obj)[0]) == 1


def test_closing_the_designer_asks_about_each_unsaved_form():
    d = designer_with("a", "b")
    assert all(doc.dirty for doc in d.docs)
    assert d.on_close() is False and d.dialog == "confirm" and d.doc.form.name == "b"  # the one in front first
    assert d.confirm_discard() is None and d.dialog == "confirm" and d.doc.form.name == "a"
    d.close_dialog()  # Cancel: the window stays open
    assert d.dialog is None and d.on_close() is False
    command = d.confirm_discard()
    assert isinstance(command, _core.Command) and not any(doc.dirty for doc in d.docs)


def test_closing_the_designer_asks_about_unsaved_files(tmp_path):
    d = Designer(language_servers=False)
    path = tmp_path / "notes.txt"
    path.write_text("hi")
    d.buffers.open(path)
    assert d.on_close() is None  # nothing unsaved
    d.set_code_buffer("changed")
    assert d.on_close() is False and d.dialog == "file:unsaved"
    d.buffers.cancel_close()
    assert d.dialog is None and d.buffers.items and d.buffers.then is None
    d.on_close()
    assert isinstance(d.buffers.confirm_save(), _core.Command) and path.read_text() == "changed"
