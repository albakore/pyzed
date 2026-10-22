"""The Properties panel laid out like Figma's: Position first, auto layout, style sections, number fields you
drag, path fields with a file dialog, groups."""

import os

from pyzed import _core, ui
from pyzed.designer import anchor_panel, layout, layout_panel, panels, prop_editors, style_panel
from pyzed.designer.app import Designer
from pyzed.designer.components import Prop
from pyzed.designer.model import Control, Form


def _titles(rows):
    return [r.title for r in rows if isinstance(r, panels.Group)]


def test_position_comes_first_and_style_is_split_in_sections():
    app = Designer(language_servers=False)
    app.doc.add("button", 10, 10)
    app.doc.select("button1")
    titles = _titles(panels.control_properties(app, app.theme_obj))
    assert titles[0] == "Position"
    assert titles.index("Position") < titles.index("Appearance") < titles.index("Behavior") < titles.index("Text")
    assert [t for t in titles if t in ("Text", "Fill", "Border", "Spacing")] == ["Text", "Fill", "Border", "Spacing"]
    assert app.view() is not None
    # the form's global style shows only what makes sense for a window
    rows = style_panel.sections(app, None, {}, app.theme_obj, panels.prop_row, panels.Group,
                                keys={"color", "font", "padding"})
    assert _titles(rows) == ["Text", "Spacing"]


def test_more_options_and_align_in_parent():
    app = Designer(language_servers=False)
    app.doc.add("button", 10, 10)
    button = app.doc.form["button1"]
    t = app.theme_obj
    fewer = anchor_panel.position_rows(app, button, t, panels.prop_row)
    app.__dict__.setdefault("_more_options", set()).add("position:button1")
    assert len(anchor_panel.position_rows(app, button, t, panels.prop_row)) == len(fewer) + 3
    anchor_panel.align_in_parent(app, "button1", "right")
    assert button.x == app.doc.form.width - button.width
    anchor_panel.align_in_parent(app, "button1", "middle")
    assert button.y == round((app.doc.form.height - button.height) / 2)


def test_flex_padding_takes_two_or_four_numbers_and_children_fill_their_own_way():
    row = Control(name="row", type="row", width=200, height=100, props={"padding": [10, 20], "gap": 0})
    assert layout.padding(layout.props(row)) == (10, 20, 10, 20)
    assert layout.content_box(row, (0, 0, 200, 100)) == (20, 10, 160, 80)
    row.props["padding"] = (1, 2, 3, 4)
    assert layout.content_box(row, (0, 0, 200, 100)) == (4, 1, 194, 96)
    boxes = layout.flex((0, 0, 200, 100), [(50, 20, 0, None), (50, 20, 0, "center"), (50, 20, 1, "end")],
                        align="stretch")
    assert boxes[0] == (0, 0, 50, 100)  # the container stretches it
    assert boxes[1] == (50, 40, 50, 20)  # centered on its own
    assert boxes[2] == (100, 80, 100, 20)  # grows along the row, at the end across it


def test_auto_layout_section_edits_the_container():
    app = Designer(language_servers=False)
    app.doc.add("row", 10, 10)
    app.doc.add("button", 20, 20)
    app.doc.reparent(["button1"], "row1")
    app.doc.select("row1")
    t = app.theme_obj
    titles = _titles(panels.control_properties(app, t))
    assert "Auto layout" in titles and "Layout" not in titles  # the plain gap/padding rows are replaced
    rows = layout_panel.auto_layout_rows(app, app.doc.form["row1"], t, panels.prop_row)
    assert len(rows) == 5
    # the alignment box: in a row, x is the main axis (justify) and y the cross axis (align)
    box = layout_panel._align_editor(app, app.doc.form["row1"], layout.props(app.doc.form["row1"]), False, t)
    assert box is not None
    app.doc.set_prop("row1", "justify", "center")
    app.doc.set_prop("row1", "align", "end")
    row = app.doc.form["row1"]
    assert (row.props["justify"], row.props["align"]) == ("center", "end")
    # a child picks Fixed or Fill per axis
    app.doc.select("button1")
    child = panels.control_properties(app, t)
    assert child and app.view() is not None
    app.set_layout("button1", "grow", 1)
    app.set_layout("button1", "align_self", "stretch")
    rects = app.doc.rects()
    assert rects["button1"][2] > 100  # fills the row


def test_group_ungroup_and_auto_layout_commands():
    app = Designer(language_servers=False)
    app.doc.add("button", 40, 40)
    app.doc.add("button", 40, 120)
    app.doc.selection = ["button1", "button2"]
    before = {n: app.doc.rects()[n][:2] for n in ("button1", "button2")}
    app.run_action("group")
    group = app.doc.form[app.doc.selection[0]]
    assert group.type == "panel" and group.props["border"] is False and group.props["background"] == "transparent"
    app.run_action("ungroup")
    assert app.doc.form.get(group.name) is None
    assert sorted(app.doc.selection) == ["button1", "button2"]
    assert {n: app.doc.rects()[n][:2] for n in ("button1", "button2")} == before
    app.run_action("auto_layout")  # stacked one over the other: a column
    column = app.doc.form[app.doc.selection[0]]
    assert column.type == "column"


def test_ungrouping_a_flex_keeps_the_sizes_it_gave():
    form = Form()
    form.add(Control(name="row", type="row", x=0, y=0, width=300, height=40, props={"gap": 0}))
    form.add(Control(name="a", type="button", width=50, height=20, parent="row", layout={"grow": 1}))
    app = Designer(language_servers=False)
    app.doc.form = form
    app.doc.selection = ["row"]
    app.run_action("ungroup")
    assert (form["a"].width, form["a"].height) == (300, 40) and form["a"].parent is None


def test_number_fields_drag_and_compact_ones():
    got = []
    scrub = ui.controls._scrubber(10.0, got.append, lambda v: max(0.0, min(v, 100.0)), 1, None, None)
    ui.controls._SCRUB.update(start=10.0, dx=0.0)
    scrub(5)
    scrub(2.5)
    assert got == [15.0, 17.0]
    small = []
    scrub = ui.controls._scrubber(0.5, small.append, lambda v: v, 0.05, None, None)
    ui.controls._SCRUB.update(start=0.5, dx=0.0)
    scrub(9)  # three pixels per step for steps under 1
    assert small == [0.65]
    assert ui.number_field(3, print, steppers=False, prefix="X") is not None
    assert prop_editors.compact((0, 0, 0, 0)) is None
    assert prop_editors.compact((4, 4, 4, 4)) == 4
    assert prop_editors.compact((1, 2, 3, 4.5)) == (1, 2, 3, 4.5)


def test_path_properties_get_a_browse_button(tmp_path):
    assert panels.is_path_prop(Prop("source", "file", ""))
    assert panels.is_path_prop(Prop("output_dir", "text", ""))
    assert panels.is_path_prop(Prop("x", "text", "", label="Log file"))
    assert not panels.is_path_prop(Prop("title", "text", ""))
    assert panels._is_folder(Prop("cwd", "text", ""))
    app = Designer(language_servers=False)
    app.doc.add("image", 10, 10)
    app.doc.select("image1")
    assert app.view() is not None
    picked = []
    command = ui.inputs.browse_path(picked.append, relative_to=str(tmp_path))
    assert isinstance(command, _core.Command)
    assert ui.inputs._start_folder("missing/a.png", str(tmp_path)) == str(tmp_path)
    (tmp_path / "img").mkdir()
    assert ui.inputs._start_folder("img/a.png", str(tmp_path)) == os.path.join(str(tmp_path), "img")
    assert ui.path_input("a.png", print, kind="image") is not None
