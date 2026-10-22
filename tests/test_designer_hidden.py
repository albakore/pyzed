"""Hidden controls on the canvas: dialogs and drawers stay out of the way until one is selected, then it is drawn
in front of the dimmed form and can be edited like any other control."""

from pyzed.designer import layout, preferences, surface
from pyzed.designer.app import Designer
from pyzed.designer.document import Document
from pyzed.designer.model import Control, Form


def _form() -> Form:
    form = Form(width=400, height=300)
    form.add(Control(name="heading", type="label", x=10, y=10, width=200, height=24))
    form.add(Control(name="dialog", type="panel", x=100, y=60, width=200, height=160, visible=False))
    form.add(Control(name="ok", type="button", x=20, y=100, width=80, height=32, parent="dialog"))
    form.add(Control(name="advanced", type="panel", x=10, y=10, width=100, height=60, parent="dialog",
                     visible=False))
    form.add(Control(name="drawer", type="panel", x=0, y=0, width=120, height=300, visible=False))
    return form


def _designer() -> Designer:
    app = Designer(language_servers=False)
    app.doc = Document(_form())
    app.show_all_hidden = False
    return app


def test_reveal_names_the_hidden_controls_holding_the_selection():
    form = _form()
    assert layout.reveal(form, []) == (None, set())
    assert layout.reveal(form, ["heading"]) == (None, set())
    assert layout.reveal(form, ["ok"]) == ("dialog", {"dialog"})
    assert layout.reveal(form, ["advanced"]) == ("dialog", {"dialog", "advanced"})
    assert layout.reveal(form, ["heading", "drawer"]) == (None, {"drawer"})  # only the first one goes in front
    assert layout.visible(form, form["ok"], {"dialog"}) and not layout.visible(form, form["ok"])


def test_hidden_controls_appear_only_while_selected():
    app = _designer()
    form = app.doc.form
    assert app.on_canvas(form["heading"])
    assert not any(app.on_canvas(form[n]) for n in ("dialog", "ok", "advanced", "drawer"))
    surface.form_surface(app, app.theme_obj)

    app.select_from_outline("ok")
    assert app.revealed[0] == "dialog"
    assert app.on_canvas(form["dialog"]) and app.on_canvas(form["ok"])
    assert not app.on_canvas(form["advanced"]) and not app.on_canvas(form["drawer"])
    surface.form_surface(app, app.theme_obj)

    app.show_all_hidden = True  # View → Show all hidden controls: every one, dimmed
    assert all(app.on_canvas(c) for c in form.controls)
    surface.form_surface(app, app.theme_obj)


def test_new_controls_drop_into_the_revealed_dialog():
    app = _designer()
    app.tool = "button"
    assert app._container_under(150, 120) is None  # hidden: not a place to drop
    app.select_from_outline("dialog")
    assert app._container_under(150, 120) == "dialog"


def test_band_selection_skips_hidden_controls():
    app = _designer()
    app.pointer = app.view_pointer = (0, 0)
    app.press_empty()
    app.pointer_moved_view(399, 299)
    app.release()
    assert app.doc.selection == ["heading"]


def test_escape_goes_back_to_the_whole_form():
    app = _designer()
    app.select_from_outline("ok")
    app.on_key("escape")
    assert app.doc.selection == [] and app.revealed == (None, set())


def test_the_old_preference_does_not_bring_back_the_pile():
    prefs = preferences.DesignerSettings.from_dict({"show_hidden": True})
    assert prefs.show_all_hidden is False
    assert preferences.DesignerSettings.from_dict({"show_all_hidden": True}).show_all_hidden is True


def test_the_eye_can_hide_controls_in_the_editor_only():
    app = _designer()
    app.prefs.outline_eye = "editor"
    form = app.doc.form
    # hidden when running is not hidden here: the dialogs are drawn, ready to edit
    assert all(app.on_canvas(c) for c in form.controls)
    assert app._container_under(250, 200) == "dialog"
    app.toggle_eye("dialog")
    assert form["dialog"].hidden_in_editor and not form["dialog"].visible  # Visible is left alone
    assert not app.on_canvas(form["dialog"]) and not app.on_canvas(form["ok"])
    app.select_from_outline("ok")  # selecting it does not bring it back
    assert app.revealed == (None, set()) and not app.on_canvas(form["ok"])
    surface.form_surface(app, app.theme_obj)
    assert app._container_under(250, 200) is None
    # saved with the form, and left out of the file when off
    data = form["dialog"].to_dict()
    assert data["hidden_in_editor"] is True and "hidden_in_editor" not in form["ok"].to_dict()
    assert Control.from_dict(data).hidden_in_editor
    app.toggle_eye("dialog")
    assert not form["dialog"].hidden_in_editor


def test_the_eye_mode_is_a_setting():
    assert preferences.DesignerSettings().outline_eye == "visible"
    assert preferences.DesignerSettings.from_dict({"outline_eye": "editor"}).outline_eye == "editor"
    assert preferences.DesignerSettings.from_dict({"outline_eye": "nope"}).outline_eye == "visible"
    app = _designer()
    app.toggle_eye("heading")
    assert not app.doc.form["heading"].visible and not app.doc.form["heading"].hidden_in_editor
