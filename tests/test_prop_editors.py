"""Editors made for each kind of property: segmented choices and linked/unlinked boxes."""

from pyzed.designer import panels, prop_editors, styling
from pyzed.designer.app import Designer


def test_four_reads_every_saved_box_shape():
    assert prop_editors.four(None) == (0, 0, 0, 0)
    assert prop_editors.four(6) == (6, 6, 6, 6)
    assert prop_editors.four((4, 8)) == (4, 8, 4, 8)
    assert prop_editors.four([1, 2, 3, 4]) == (1, 2, 3, 4)


def test_short_choices_sit_side_by_side():
    assert prop_editors.fits_segmented(styling.TRISTATE)
    assert prop_editors.fits_segmented(("left", "center", "right"))
    assert not prop_editors.fits_segmented(("only",))
    assert not prop_editors.fits_segmented(("filled", "solid", "tinted", "outline", "ghost"))
    assert prop_editors.choice_label("") == "Default"


def test_a_box_splits_when_its_sides_differ_or_it_was_unlinked():
    app = Designer(language_servers=False)
    app.doc.add("button", 10, 10)
    assert not prop_editors.is_split(app, "button1:padding", 8)
    assert prop_editors.is_split(app, "button1:padding", (4, 12, 4, 12))
    app._split_boxes = {"button1:padding"}
    assert prop_editors.is_split(app, "button1:padding", 8)
    # the editor hands set_style numbers and tuples, which the style keeps as they are
    app.set_style("button1", "padding", (4, 12, 4, 12))
    assert app.doc.form["button1"].style["padding"] == (4, 12, 4, 12)
    app.set_style("button1", "padding", None)
    assert "padding" not in app.doc.form["button1"].style


def test_the_style_section_builds_with_the_new_editors():
    app = Designer(language_servers=False)
    app.doc.add("button", 10, 10)
    button = app.doc.form["button1"]
    app.set_style("button1", "radius", (2, 4, 6, 8))
    app.set_style("button1", "align_x", "center")
    app.set_style("button1", "italic", "on")
    assert len(panels.style_rows(app, "button1", button.style, app.theme_obj)) > 10
    app.view()
