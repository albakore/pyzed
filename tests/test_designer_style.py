"""The designer's Style section: per-control styles and the form's global style."""

from pyzed import style as pz_style
from pyzed.designer import new, panels, styling
from pyzed.designer.app import Designer
from pyzed.designer.model import Form
from pyzed.designer.runtime import FormApp, theme_for
from pyzed.theme import themes


def sidebar_app(tmp_path):
    app = Designer(new.new_form(tmp_path / "shell", template="sidebar"), language_servers=False)
    app.window_size = (1440, 900)
    return app


def test_field_values_unset_empty_and_default_inputs():
    assert styling.field_value("color", "  ") is None
    assert styling.field_value("size", 0) is None and styling.field_value("size", 16.0) == 16
    assert styling.field_value("border_width", 0) == 0
    assert styling.field_value("weight", "") is None and styling.field_value("weight", "bold") == "bold"
    assert styling.field_value("italic", "on") is True and styling.field_value("italic", "off") is False
    assert styling.field_value("padding", "4 8") == (4, 8) and styling.field_value("padding", "x") is None
    assert styling.field_value("radius", "8") == 8 and styling.field_value("radius", "8 0") == (8, 0, 8, 0)
    assert styling.numbers_text((4, 8.5)) == "4 8.5"


def test_picker_values_are_saved_as_json_and_read_back():
    t = themes.get("One Dark")
    gradient = pz_style.Gradient(["#ff0000", "#0000ff"], angle=90)
    paint = pz_style.Paint(gradient, opacity=0.5, mask=pz_style.Mask([1, 0]))
    assert styling.picked("#ff000080") == "#ff000080" and styling.picked("") is None
    assert styling.unpicked(styling.picked(gradient), t, "#fff") == gradient
    assert styling.unpicked(styling.picked(paint), t, "#fff") == paint
    assert styling.unpicked("accent", t, "#fff").startswith(t.accent.lower()[:7])
    assert styling.unpicked(None, t, "#fff") == "#fff"
    assert [styling.describe(v) for v in (None, "#fff", gradient.to_dict(), paint.to_dict())] == [
        "None", "Color", "Gradient", "Masked"]


def test_drawing_skips_half_typed_values():
    t = themes.get("One Dark")
    style = styling.clean({"color": "#ff", "radius": [1, 2], "border_color": "acc", "size": 16, "padding": [4, 8]}, t)
    assert style == pz_style.Style(size=16, padding=(4, 8))
    assert styling.clean({}, t) is None


def test_style_section_edits_a_control_and_saves_it(tmp_path):
    app = sidebar_app(tmp_path)
    app.doc.select("nav1")
    app._selection_changed()
    app.set_style("nav1", "weight", "bold")
    app.set_style("nav1", "radius", "0 8 0 8")
    app.set_style("nav1", "color", "#ff")  # half typed: kept, not drawn
    app.toggle_color_picker("nav1", "background")  # the picker opens under the row
    assert app.view() is not None
    app.set_style_value("nav1", "background", styling.picked(pz_style.Gradient(["accent", "#c678dd"], angle=90)))
    app.toggle_color_picker("nav1", "color")
    assert app.color_picker == ("nav1", "color") and app.view() is not None
    app.set_style_value("nav1", "shadow", styling.shadow_value("#0006", 0, 4, 12))
    control = app.doc.form["nav1"]
    assert control.style["weight"] == "bold" and control.style["radius"] == (0, 8, 0, 8)
    assert app.view() is not None
    rows = panels.control_properties(app, app.theme_obj)
    assert any(isinstance(r, panels.Group) and r.title == "Style" for r in rows)
    app.save()
    saved = Form.from_json(app.doc.path.read_text())
    assert saved["nav1"].style["shadow"] == ["#0006", [0, 4], 12]
    assert "style" not in saved["nav2"].to_dict()  # unstyled controls stay as they were
    app.set_style("nav1", "weight", "")  # "Default" removes it
    assert "weight" not in app.doc.form["nav1"].style
    app.undo()
    assert app.doc.form["nav1"].style["weight"] == "bold"
    app.clear_style("nav1")
    assert app.doc.form["nav1"].style == {}


def test_global_style_reaches_the_theme_and_the_running_form(tmp_path):
    app = sidebar_app(tmp_path)
    app.set_style(None, "color", "#e5c07b")
    app.set_style(None, "font", "serif")
    app.set_style(None, "size", 16)
    app.set_style_value(None, "background", styling.picked(pz_style.Gradient(["#112233", "#334455"])))
    app.toggle_color_picker(None, "background")
    assert app.view() is not None
    form = app.doc.form
    assert form.to_dict()["form"]["style"]["font"] == "serif"
    t = theme_for(form)
    assert t.text.lower().startswith("#e5c07b") and t.ui_font_size == 16
    assert styling.background_layer(form.style, t) is not None
    assert app.view() is not None
    assert any(isinstance(r, panels.Group) and r.title == "Style" for r in panels.form_properties(app, app.theme_obj))
    assert FormApp(form).view() is not None
    assert "style" not in Form().to_dict()["form"]
