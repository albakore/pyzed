"""Tests for the Component view of ``.pzcomp`` tabs: try values, Design/Live, the Members list and script links."""

import textwrap

import pytest

from pyzed import designer
from pyzed.designer import component_view, components
from pyzed.designer.scene import load_component, new_component


@pytest.fixture(autouse=True)
def _restore_registries():
    from pyzed import component as _component

    specs, classes = dict(components._REGISTRY), dict(_component._REGISTRY)
    yield
    components._REGISTRY.clear()
    components._REGISTRY.update(specs)
    _component._REGISTRY.clear()
    _component._REGISTRY.update(classes)


def make_rating(tmp_path):
    doc = new_component("Rating", tmp_path / "rating.pzcomp", width=200, height=60, icon="star")
    doc.add("label", 8, 8, 120, 24)
    doc.add("button", 8, 32, 80, 24)
    doc.add_member("value", "int", 3)
    doc.add_member("title", "str", "Stars")
    doc.add_member("hover", "int", public=False)
    doc.add_event("change", "A star was picked")
    doc.set_binding("label1", "text", 'f"{value} stars"')
    doc.set_binding("button1", "text", "title")
    method = doc.wire("button1", "click")
    doc.set_handler_source(method, 'def button1_click(self, event):\n    self.value += 1\n'
                                   '    return self.emit("change", self.value)\n')
    doc.code = doc.code.rstrip() + "\n\n\nclass Star:\n    pass\n"
    return doc


def test_tried_values_drive_the_bindings_without_touching_the_code(tmp_path):
    doc = make_rating(tmp_path)
    code = doc.code
    assert component_view.values(doc) == {"value": 3, "title": "Stars", "hover": 0}
    props, errors = component_view.bound_props(doc)
    assert props == {"label1": {"text": "3 stars"}, "button1": {"text": "Stars"}} and not errors

    component_view.set_try(doc, "value", "5")
    component_view.set_try(doc, "title", '"Rate it"')
    assert component_view.is_tried(doc, "value") and not component_view.is_tried(doc, "hover")
    props, _ = component_view.bound_props(doc)
    assert props == {"label1": {"text": "5 stars"}, "button1": {"text": "Rate it"}}
    assert doc.code == code and doc.member("value").default == 3  # only the canvas changes

    # an untrusted project: plain property bindings still follow, expressions are not evaluated
    props, _ = component_view.bound_props(doc, expressions=False)
    assert props == {"button1": {"text": "Rate it"}}

    component_view.set_try(doc, "value", "oops(")  # not a literal: the default is used
    assert component_view.values(doc)["value"] == 3
    component_view.reset_tries(doc)
    assert component_view.state(doc).tries == {}


def test_binding_errors_are_reported(tmp_path):
    doc = make_rating(tmp_path)
    doc.set_binding("label1", "text", "missing + 1")
    props, errors = component_view.bound_props(doc)
    assert "label1" not in props and "NameError" in errors["label1.text"]


def test_module_classes_and_members(tmp_path):
    doc = make_rating(tmp_path)
    doc.code = doc.code.replace("    def button1_click", "    class Item:\n        pass\n\n    def button1_click", 1)
    names = [(c.name, c.nested) for c in component_view.module_classes(doc)]
    assert ("Star", False) in names and ("Item", True) in names
    assert "Rating" not in [n for n, _ in names]


def test_component_view_in_the_designer(tmp_path):
    path = make_rating(tmp_path).save()
    app = designer.Designer(path, language_servers=False)
    t = app.theme_obj
    assert component_view.is_component(app)
    app.view()  # Design: bindings drawn with the tried values, Members under the Outline
    assert component_view.canvas_props(app)["label1"] == {"text": "3 stars"}
    component_view.members_view(app, t)
    component_view.open_member(app, "value")
    assert not app.doc.selection

    component_view.set_live(app, True)
    assert component_view.state(app.doc).live
    app.view()  # the class runs on the canvas
    cls, error = component_view._compiled(app)
    assert cls is not None and not error and cls.__name__ == "Rating"
    component_view.set_try(app.doc, "value", "7")
    app.view()
    component_view.restart(app)
    assert component_view.state(app.doc).run == 1
    app.doc.code = app.doc.code.replace("class Rating", "class Rating(", 1)  # broken: the error is shown
    app.view()
    assert component_view._compiled(app)[0] is None
    component_view.set_live(app, False)
    app.view()
    app.screenshot(tmp_path / "component.png", size=(1280, 800), scale=1)


def test_live_needs_a_trusted_project(tmp_path, monkeypatch):
    path = make_rating(tmp_path).save()
    app = designer.Designer(path, language_servers=False)
    monkeypatch.setattr(app.trust, "trusted", lambda folder=None: False)
    component_view.set_live(app, True)
    assert not component_view.state(app.doc).live and app.dialog == "trust"
    assert component_view.canvas_props(app) == {"button1": {"text": "Stars"}}


def test_script_links_in_the_outline(tmp_path):
    rating = make_rating(tmp_path)
    rating.save()
    load_component(tmp_path / "rating.pzcomp")
    form = designer.Form(width=300, height=200)
    form.add(components.get("rating").create("rating1", 10, 10))
    form.add(components.get("button").create("ok", 10, 120))
    designer.save(form, tmp_path / "main.pzform")
    app = designer.Designer(tmp_path / "main.pzform", language_servers=False)
    t = app.theme_obj
    # the form's own script, then a designed component's: library controls have none
    assert component_view.script_button(app, t) is not None
    assert component_view.script_of_type("rating") == tmp_path / "rating.py"
    assert component_view.script_of_type("button") is None
    assert component_view.script_button(app, t, "ok") is None
    assert component_view.script_button(app, t, "rating1") is not None
    app.view()


def test_code_only_components_have_no_script_link():
    import pyzed as pz

    class Badge(pz.Component):
        text: str = "New"

        def render(self):
            return pz.text(self.text)

    assert component_view.script_of_type(Badge.type_name) is None


def test_the_form_script_opens_the_whole_file(tmp_path):
    form = designer.Form(width=300, height=200)
    designer.save(form, tmp_path / "main.pzform")
    app = designer.Designer(tmp_path / "main.pzform", language_servers=False)
    app.edit_whole_file()
    assert app.editing[0] == "*"
    assert textwrap.dedent(app.editing[1]) == app.doc.code
