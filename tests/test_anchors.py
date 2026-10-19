"""Tests for anchors: the presets, placing on resize with size limits and a pivot, the designer's Position
section and ``pz.anchor_layout``."""

import pytest

import pyzed as pz
from pyzed import anchors, ui
from pyzed.designer.app import Designer
from pyzed.designer.document import Document
from pyzed.designer.layout import resolve
from pyzed.designer.model import Control, Form


def test_the_sixteen_presets_cover_every_set_of_edges():
    assert len(anchors.PRESETS) == 16
    assert anchors.PRESETS["top_left"] == ("left", "top")
    assert anchors.PRESETS["bottom_wide"] == ("left", "right", "bottom")
    assert anchors.PRESETS["center"] == ()
    assert anchors.PRESETS["full"] == anchors.EDGES
    for name, edges in anchors.PRESETS.items():
        assert anchors.preset_of(edges) == name
    assert anchors.preset("right", "top") == "top_right" and anchors.preset("wide", "tall") == "full"
    assert anchors.edges("top right") == ("top", "right") and anchors.edges("Bottom-Wide") == anchors.PRESETS[
        "bottom_wide"]
    with pytest.raises(ValueError):
        anchors.edges("upstairs")
    with pytest.raises(ValueError):
        anchors.edges(("left", "middle"))


def test_boxes_follow_their_anchors():
    rect, design, actual = (20, 20, 100, 30), (400, 300), (600, 400)
    assert anchors.place(rect, "top_left", design, actual) == (20, 20, 100, 30)
    assert anchors.place(rect, "bottom_right", design, actual) == (220, 120, 100, 30)
    assert anchors.place(rect, "center", design, actual) == (120, 70, 100, 30)
    assert anchors.place(rect, "full", design, actual) == (20, 20, 300, 130)
    assert anchors.place(rect, "full", design, (10, 10)) == (20, 20, anchors.MIN_SIZE, anchors.MIN_SIZE)


def test_size_limits_and_the_pivot():
    rect, design, actual = (20, 20, 100, 30), (400, 300), (600, 300)
    assert anchors.place(rect, "top_wide", design, actual, max_size=(200, 0)) == (70, 20, 200, 30)
    assert anchors.place(rect, "top_wide", design, actual, max_size=(200, 0), pivot=(0, 0)) == (20, 20, 200, 30)
    assert anchors.place(rect, "top_wide", design, actual, max_size=(200, 0), pivot=(1, 0)) == (120, 20, 200, 30)
    assert anchors.place(rect, "top_left", design, actual, min_size=(150, 40), pivot=(0, 0)) == (20, 20, 150, 40)
    assert anchors.place(rect, "top_wide", design, (300, 300), min_size=(80, 0), pivot=(0, 0)) == (20, 20, 80, 30)


def test_snapping_offsets_and_pivot_rotation():
    assert anchors.snap_to("bottom_right", (0, 0, 100, 30), (400, 300), margin=8) == (292, 262, 100, 30)
    assert anchors.snap_to("top_wide", (0, 0, 100, 30), (400, 300), margin=8) == (8, 8, 384, 30)
    assert anchors.snap_to("center", (0, 0, 100, 30), (400, 300)) == (150, 135, 100, 30)
    assert anchors.offsets((20, 10, 100, 30), (400, 300)) == (20, 10, 280, 260)
    assert anchors.pivot_offset((100, 50), (0.5, 0.5), 45) == (0.0, 0.0)
    assert anchors.pivot_offset((100, 50), (0, 0), 90) == (-75.0, 25.0)  # the top-left corner stays put
    assert anchors.pivot_offset((100, 50), (0, 0), 0, scale=2) == (50.0, 25.0)


def test_designed_controls_use_limits_and_pivot_when_the_window_is_resized():
    form = Form(width=400, height=300)
    form.controls.append(Control("bar", "panel", 20, 20, 360, 40, anchor=("left", "top", "right"),
                                 layout={"max_width": 500, "pivot": [0, 0]}))
    rects = resolve(form, (800, 300))
    assert rects["bar"] == (20, 20, 500, 40)
    control = form["bar"]
    assert control.max_size == (500, 0) and control.min_size == (0, 0) and control.pivot == (0, 0)
    control.layout["pivot"] = ["x", 3]
    assert control.pivot == (0.5, 1.0)


def test_the_document_sets_anchors_offsets_and_pivots():
    doc = Document(Form(width=400, height=300))
    doc.add("button", 10, 10)
    doc.set_anchor("button1", "bottom_right", move=True, margin=0)
    button = doc.form["button1"]
    assert button.anchor == ("right", "bottom")
    assert (button.x + button.width, button.y + button.height) == (400, 300)
    doc.set_anchor("button1", "top_wide", move=True)
    assert (button.x, button.y, button.width) == (0, 0, 400)
    doc.set_offset("button1", "left", 16)
    doc.set_offset("button1", "right", 24)
    assert (button.x, button.width) == (16, 360)
    doc.set_offset("button1", "top", 8)
    doc.set_offset("button1", "bottom", 250)
    assert button.y == 8 and button.y + button.height == 50
    with pytest.raises(ValueError):
        doc.set_offset("button1", "middle", 1)
    doc.set_pivot("button1", 0, 1.5)
    assert button.layout["pivot"] == [0.0, 1.0]
    doc.set_pivot("button1", 0.5, 0.5)
    assert "pivot" not in button.layout


def test_the_position_section_and_its_presets():
    from pyzed.designer import anchor_panel, panels

    app = Designer(language_servers=False)
    app.doc.add("button", 10, 10)
    app.doc.select("button1")
    t = app.theme_obj
    button = app.doc.form["button1"]
    rows = anchor_panel.position_rows(app, button, t, panels.prop_row)
    app.toggle_anchor_presets("button1")
    assert len(anchor_panel.position_rows(app, button, t, panels.prop_row)) == len(rows) + 1  # the grid
    app.anchor_move = True
    app.set_anchor("button1", "full")
    assert button.anchor == anchors.EDGES and app.anchor_presets is None
    assert (button.width, button.height) == (app.doc.form.width, app.doc.form.height)
    assert anchor_panel.preset_label("top_right") == "Top · Right"
    app.set_offset("button1", "left", 20)
    app.set_pivot("button1", 0, 0)
    app.set_style("button1", "rotate", 30)
    assert anchor_panel._rotation(button) == 30
    app.view()


def test_rotation_turns_around_the_pivot():
    from pyzed.designer import styling

    style = {"rotate": 90}
    assert styling.pivoted(style, (0.5, 0.5), (100, 50)) is style
    assert styling.pivoted(style, (0, 0), (100, 50))["translate"] == [-75.0, 25.0]
    assert styling.pivoted({"rotate": 90, "translate": [10, "10%"]}, (0, 0), (100, 50))["translate"] == [-65.0,
                                                                                                         30.0]
    assert styling.pivoted({"opacity": 0.5}, (0, 0), (100, 50)) == {"opacity": 0.5}


def test_anchor_layout_places_widgets_in_a_running_app(tmp_path):
    item = pz.anchor(ui.button("Close"), x=284, y=252, width=100, height=32, anchor="bottom_right")
    assert item.edges == ("right", "bottom") and "AnchorItem" in repr(item)

    class Report(pz.App):
        def view(self):
            return pz.anchor_layout([
                pz.anchor(ui.heading("Report"), x=16, y=12, width=368, height=28, anchor="top_wide"),
                item,
                pz.anchor(ui.badge("new"), x=180, y=120, width=40, height=20, anchor="center", rotate=20,
                          pivot=(0, 0)),
                None,
            ], design=(400, 300))

    pz.screenshot(Report(), tmp_path / "report.png", size=(600, 400))
    assert (tmp_path / "report.png").stat().st_size > 0
    assert pz.anchor_layout([item]) is not None  # design size from the children
    with pytest.raises(TypeError):
        pz.anchor_layout([ui.button("Not anchored")])


def _anchored_form():
    form = Form(width=400, height=300)
    form.controls += [
        Control("ok", "button", 290, 260, 100, 32, anchor=("right", "bottom")),
        Control("header", "panel", 10, 10, 380, 60, anchor=("left", "top", "right")),
        Control("close", "button", 340, 14, 32, 32, parent="header", anchor=("top", "right")),
        Control("title", "label", 8, 8, 100, 20, anchor=("left", "top")),
    ]
    return form


def test_resizing_the_form_in_the_designer_moves_controls_by_their_anchors():
    doc = Document(_anchored_form())
    doc.set_form("width", 600)
    form = doc.form
    assert (form["ok"].x, form["ok"].y) == (490, 260)
    assert form["header"].width == 580 and form["close"].x == 540  # the container passes it on
    assert (form["title"].x, form["title"].y) == (8, 8)
    doc.set_form("height", 400)
    assert form["ok"].y == 360
    doc.undo()
    assert doc.form["ok"].y == 260
    doc.follow_anchors = False
    doc.set_form("width", 700)
    assert doc.form["ok"].x == 490


def test_resizing_a_container_moves_its_children():
    doc = Document(_anchored_form())
    doc.set_field("header", "width", 300)
    assert doc.form["close"].x == 260
    doc.set_offset("header", "right", 10)  # width back to 380
    assert doc.form["close"].x == 340
    doc.set_anchor("header", "full", move=True, margin=0)
    assert doc.form["header"].width == 400 and doc.form["close"].x == 360


def test_dragging_the_form_grip_or_a_resize_handle_follows_anchors():
    app = Designer(language_servers=False)
    app.doc = Document(_anchored_form())
    app.pointer_moved_view(0, 0)
    app.press_form_grip()
    for x in (40, 100, 200):  # every step starts from where the drag began: no rounding drift
        app.pointer_moved_view(x, 0)
    assert app.doc.form.width == 600 and app.doc.form["ok"].x == 490
    app.release()
    assert app.doc.form["ok"].x == 490
    app.doc.select("header")
    app.pointer_moved_view(0, 0)
    app.press_handle("e")
    app.pointer_moved_view(-100, 0)
    assert app.doc.form["close"].x == app.doc.form["header"].width - 40
    app.release()
    app.toggle_follow_anchors()
    assert not app.doc.follow_anchors
    app.press_form_grip()
    app.pointer_moved_view(-200, 0)
    app.release()
    assert app.doc.form["ok"].x == 490
    app.view()
