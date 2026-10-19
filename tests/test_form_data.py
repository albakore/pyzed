"""Tests for copy and paste between forms, data binding and validation, and previewing a form in another theme
or language."""

import json

from pyzed import _core, i18n
from pyzed.designer import binding
from pyzed.designer.app import Designer
from pyzed.designer.document import CLIPBOARD_FORMAT, Document
from pyzed.designer.model import Form
from pyzed.designer.runtime import FormWindow, theme_for


def signup_form():
    doc = Document(Form(name="signup", title="@signup.title"))
    doc.add("input", 10, 10)
    doc.add("label", 10, 50)
    doc.add("checkbox", 10, 90)
    doc.add("slider", 10, 130)
    form = doc.form
    form["input1"].bind = "customer.name"
    form["input1"].rules = {"required": True, "min_length": 3}
    form["label1"].bind = 'f"Hello, {customer.name}!"'
    form["checkbox1"].bind = "agree"
    form["checkbox1"].rules = {"required": True, "message": "Accept the terms"}
    form["slider1"].bind = "age"
    form["slider1"].rules = {"min": 18}
    return doc


# -- clipboard -----------------------------------------------------------------------


def test_controls_paste_into_another_form_through_the_system_clipboard():
    source = signup_form()
    source.wire("input1", "change")
    source.select(["input1", "label1"])
    source.copy()
    text = source.clipboard_text()
    assert json.loads(text)["format"] == CLIPBOARD_FORMAT

    target = Document()
    assert target.paste_text(text) == ["input1", "label1"]  # free names are kept in another form
    pasted = target.form["input1"]
    assert pasted.bind == "customer.name" and pasted.rules["min_length"] == 3
    assert pasted.events == {}  # not wired: the handlers live in the other form's code
    assert target.paste_text(text) == ["input2", "label2"]  # taken now: fresh names
    assert target.paste_text("just some text") is None
    assert target.paste_text(json.dumps({"format": "other"})) is None


def test_pasting_skips_unknown_types_and_lost_containers():
    text = json.dumps({"format": CLIPBOARD_FORMAT, "controls": [
        {"name": "ghost", "type": "no_such_control"},
        {"name": "inner", "type": "label", "parent": "missing_panel", "x": 4, "y": 4},
    ]})
    doc = Document()
    assert doc.paste_text(text) == ["inner"]
    assert doc.form["inner"].parent is None


def test_the_designer_copies_to_and_pastes_from_the_system_clipboard():
    app = Designer(language_servers=False)
    app.doc.add("button", 10, 10)
    app.doc.select("button1")
    assert isinstance(app.copy(), _core.Command)
    assert isinstance(app.paste(), _core.Command)
    app.paste_text(app.doc.clipboard_text())
    assert app.doc.selection == ["button2"]
    app.paste_text("")  # nothing from Pyzed on the system clipboard: the last copy made here
    assert len(app.doc.form.controls) == 3


# -- binding -------------------------------------------------------------------------


def test_paths_expressions_and_rules():
    data = {"customer": {"name": "Ada", "tags": ["a", "b"]}}
    assert binding.read(data, "customer.name") == "Ada"
    assert binding.read(data, "customer.tags.1") == "b"
    assert binding.read(data, "customer.city", "?") == "?"
    binding.write(data, "customer.address.city", "London")
    assert data["customer"]["address"] == {"city": "London"}
    assert binding.evaluate('f"{customer.name} ({len(customer.tags)})"', data) == "Ada (2)"
    assert binding.is_path("items.0.title") and not binding.is_path("len(items)")

    assert binding.check("", {"required": True}) == "This field is required"
    assert binding.check("ab", {"min_length": 3}) == "At least 3 characters"
    assert binding.check("abcd", {"max_length": 3}) == "At most 3 characters"
    assert binding.check("x@y", {"pattern": r"[^@]+@[^@]+\.\w+"}) == "The format is not valid"
    assert binding.check(5, {"min": 18}, "slider") == "Must be 18 or more"
    assert binding.check("", {"min_length": 3}) is None  # empty only fails "required"
    assert binding.check(False, {"required": True, "message": "Accept"}, "checkbox") == "Accept"
    assert binding.rules_for("label") == ()
    assert "pattern" in binding.rules_for("input") and "min" in binding.rules_for("number")


def test_bound_controls_show_and_edit_the_form_data():
    window = FormWindow(signup_form().form)
    runtime, form = window.runtime, window.form
    assert form.data == {"customer": {"name": ""}, "agree": False, "age": 50}  # designed values fill it
    window.view()
    assert runtime.form["label1"].props["text"] == "Hello, !"

    type_name = runtime.ctx.on(runtime.form["input1"], "change", "text")
    type_name("Al")
    assert form.data["customer"]["name"] == "Al"
    assert form.input1.error == "At least 3 characters"  # checked as the user types
    type_name("Alice")
    window.view()
    assert runtime.form["label1"].props["text"] == "Hello, Alice!"
    assert form.errors == {}

    assert form.validate() is False
    assert form.errors == {"checkbox1": "Accept the terms"}
    form.data = {"customer": {"name": "Bob"}, "agree": True, "age": 30}
    window.view()
    assert runtime.form["input1"].props["text"] == "Bob"
    assert form.validate() and form.valid

    form.input1.error = "Already registered"
    assert not form.valid and form.input1.validate() and form.input1.error is None
    form.checkbox1.hide()
    form.data = {"customer": {"name": "Bob"}, "agree": False, "age": 30}
    assert form.validate()  # hidden controls are not checked


def test_data_passed_by_the_opener_is_edited_in_place():
    class Customer:
        name = "Grace"

    doc = Document()
    doc.add("input", 0, 0)
    doc.form["input1"].bind = "name"
    record = Customer()
    window = FormWindow(doc.form, data=record)
    window.view()
    assert window.runtime.form["input1"].props["text"] == "Grace"
    window.runtime.ctx.on(window.runtime.form["input1"], "change", "text")("Hopper")
    assert record.name == "Hopper"


def test_bind_and_rules_are_saved_only_when_set(tmp_path):
    doc = signup_form()
    data = doc.form.to_dict()
    controls = {c["name"]: c for c in data["controls"]}
    assert controls["input1"]["bind"] == "customer.name" and controls["input1"]["rules"]["required"]
    doc.add("button", 0, 0)
    assert "bind" not in doc.form["button1"].to_dict() and "rules" not in doc.form["button1"].to_dict()
    doc.set_bind("button1", "  ")
    doc.set_rule("input1", "min_length", None)
    assert "min_length" not in doc.form["input1"].rules
    path = doc.save(tmp_path / "signup.pzform")
    assert Document.open(path).form["slider1"].rules == {"min": 18}


def test_the_data_section_of_the_properties_panel():
    from pyzed.designer import panels

    app = Designer(language_servers=False)
    app.doc = signup_form()
    t = app.theme_obj
    for name in ("input1", "label1", "checkbox1", "slider1"):
        app.doc.select(name)
        rows = panels.data_rows(app, app.doc.primary, t)
        assert rows
    app.doc.add("button", 0, 0)
    assert panels.data_rows(app, app.doc.form["button1"], t) == []
    app.doc.select("input1")
    app.view()


# -- preview -------------------------------------------------------------------------


def test_texts_with_at_are_translated():
    i18n.add("fr", {"signup": {"title": "Inscription"}})
    assert binding.translate("@signup.title", "fr") == "Inscription"
    assert binding.translate("@@home", "fr") == "@home"
    assert binding.translate(["@signup.title", "plain"], "fr") == ["Inscription", "plain"]
    window = FormWindow(signup_form().form, language="fr")
    assert window.title == "Inscription" and window.form.title == "Inscription"


def test_locales_next_to_the_form_are_loaded(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (tmp_path / "locales").mkdir()
    (tmp_path / "locales" / "de.json").write_text(json.dumps({"signup": {"title": "Anmeldung"}}))
    (tmp_path / "ui").mkdir()
    assert "de" in binding.load_texts(tmp_path / "ui" / "signup.pzform")
    assert i18n.t("signup.title", language="de") == "Anmeldung"


def test_the_designer_previews_another_theme_and_language():
    app = Designer(language_servers=False)
    app.doc = signup_form()
    app.open_preview_picker("theme")
    assert app.dialog == "preview_theme" and app.dialog_view(app.theme_obj) is not None
    app.set_preview("theme", "One Light")
    app.open_preview_picker("language")
    assert app.dialog_view(app.theme_obj) is not None
    app.set_preview("language", "es")
    assert (app.preview_theme, app.preview_language, app.dialog) == ("One Light", "es", None)
    app.view()
    assert theme_for(app.doc.form, "One Light").name == "One Light"
    app.set_preview("theme", None)
    assert app.preview_theme is None
