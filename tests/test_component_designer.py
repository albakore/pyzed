"""Tests for the designer's component mode: pz.state, the class code, scenes, SceneComponent and the UI."""

import textwrap
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import designer
from pyzed.component import render_pass
from pyzed.designer import components, scene_code
from pyzed.designer.scene import Scene, SceneDocument, discover, load, load_component, new_component, open_document


# -- pz.state ----------------------------------------------------------------------


def test_state_is_private_and_copied_per_instance():
    class Basket(pz.Component):
        designer = False
        owner: str = "me"
        items: list = pz.state([])
        count = pz.state(0, doc="How many")

        def render(self):
            return pz.text(f"{self.owner}: {len(self.items)}")

    assert list(Basket.__props__) == ["owner"]
    assert list(Basket.__state__) == ["items", "count"]
    assert Basket.__state__["count"].doc == "How many"
    a, b = Basket.create(), Basket.create()
    a.items.append(1)
    assert b.items == [] and a.count == 0
    with pytest.raises(TypeError):
        Basket(items=[1])  # state is not a prop


# -- the class code ------------------------------------------------------------------

SOURCE = textwrap.dedent('''\
    """A module."""

    import pyzed as pz
    from pyzed.designer import SceneComponent


    def helper():
        return 1


    class Rating(SceneComponent, scene="rating.pzcomp"):
        """Stars."""

        value: int = 3  # the rating
        hover: int = pz.state(0)
        events = {"change": "Picked"}

        def star1_click(self, event):
            return self.emit("change", 1)
    ''')


def test_read_class():
    info = scene_code.read(SOURCE)
    assert info.name == "Rating" and info.doc == "Stars."
    assert [(m.name, m.type, m.default, m.public) for m in info.members] == [
        ("value", "int", 3, True), ("hover", "int", 0, False)]
    assert info.members[0].description == "the rating"
    assert info.events == {"change": "Picked"}
    assert info.methods == ["star1_click"]


def test_rewrite_members_and_events_keeps_the_rest():
    members = scene_code.read(SOURCE).members
    members.append(scene_code.Member("tags", "list", ["a"], public=False))
    members[0].default = 5
    out = scene_code.set_members(SOURCE, members)
    out = scene_code.set_events(out, {"change": "Picked", "hovered": ""})
    info = scene_code.read(out)
    assert [(m.name, m.default) for m in info.members] == [("value", 5), ("hover", 0), ("tags", ["a"])]
    assert info.events == {"change": "Picked", "hovered": ""}
    assert "def helper():" in out and "return self.emit(\"change\", 1)" in out
    compile(out, "x.py", "exec")
    # removing everything leaves a valid class
    empty = scene_code.set_events(scene_code.set_members(out, []), {})
    assert scene_code.read(empty).members == [] and "events" not in empty.split("class Rating")[1].split("def")[0]
    compile(empty, "x.py", "exec")


def test_methods():
    out, created = scene_code.ensure_method(SOURCE, "setup", "Once.", "self")
    assert created
    assert scene_code.get_method(out, "setup").startswith("def setup(self):")
    out = scene_code.replace_method(out, "setup", "def setup(self):\n    self.hover = 1\n")
    assert "        self.hover = 1\n" in out
    with pytest.raises(SyntaxError):
        scene_code.replace_method(out, "setup", "def setup(self):\n    pass\nx = 1\n")
    out = scene_code.rename_method(out, "star1_click", "star_click")
    assert scene_code.read(out).methods == ["star_click", "setup"]
    out = scene_code.remove_method(out, "setup")
    assert scene_code.read(out).methods == ["star_click"]
    compile(out, "x.py", "exec")


def test_new_module_is_valid_and_methods_can_be_added():
    source = scene_code.new_module("Card", "card.pzcomp")
    out, _ = scene_code.ensure_method(source, "ok_click")
    out = scene_code.set_members(out, [scene_code.Member("title", "str", "Hi")])
    info = scene_code.read(out)
    assert info.name == "Card" and info.methods == ["ok_click"] and info.members[0].default == "Hi"
    compile(out, "card.py", "exec")


def test_identifiers():
    assert scene_code.class_identifier("star rating") == "StarRating"
    assert scene_code.class_identifier("3d view") == "C3dView"
    assert scene_code.member_identifier("Max Value") == "max_value"
    assert scene_code.member_identifier("class") == "class_"


# -- scenes and documents -------------------------------------------------------------


def make_rating(tmp_path: Path) -> SceneDocument:
    doc = new_component("Rating", tmp_path / "rating.pzcomp", width=200, height=60, icon="star")
    doc.add("label", 8, 8, 120, 24)
    doc.add("button", 8, 32, 80, 24)
    doc.add_member("value", "int", 3)
    doc.add_member("hover", "int", public=False)
    doc.add_event("change", "A star was picked")
    doc.set_binding("label1", "text", 'f"{value} stars"')
    method = doc.wire("button1", "click")
    doc.set_handler_source(method, 'def button1_click(self, event):\n    self.value += 1\n'
                                   '    return self.emit("change", self.value)\n')
    doc.wire(None, "setup")
    return doc


def test_scene_roundtrip(tmp_path):
    doc = make_rating(tmp_path)
    path = doc.save()
    scene = load(path)
    assert isinstance(scene, Scene) and scene.name == "Rating" and scene.icon == "star"
    assert scene.bindings == {"label1": {"text": 'f"{value} stars"'}}
    assert scene["button1"].events == {"click": "button1_click"}
    assert scene.events == {"setup": "setup"}
    with pytest.raises(ValueError):
        designer.load(path)  # a component is not a form
    reopened = open_document(path)
    assert isinstance(reopened, SceneDocument)
    assert [m.name for m in reopened.members] == ["value", "hover"]
    assert reopened.custom_events == {"change": "A star was picked"}
    assert "def setup(self):" in reopened.code


def test_document_undo_keeps_the_scene(tmp_path):
    doc = make_rating(tmp_path)
    doc.add("label", 100, 8)
    assert doc.undo()
    assert isinstance(doc.form, Scene) and doc.scene.bindings


def test_rename_control_and_member(tmp_path):
    doc = make_rating(tmp_path)
    doc.rename("button1", "plus")
    assert "def plus_click(self, event):" in doc.code and doc.scene["plus"].events["click"] == "plus_click"
    doc.set_binding("plus", "text", "value")
    doc.update_member("value", name="stars")
    assert doc.scene.bindings["plus"] == {"text": "stars"}
    assert [m.name for m in doc.members] == ["stars", "hover"]
    doc.update_member("stars", type="str")
    assert doc.member("stars").default == "3"
    doc.update_member("hover", public=True)
    assert doc.member("hover").public
    assert doc.set_class_name("star rating") == "StarRating"
    assert "class StarRating(SceneComponent" in doc.code and doc.scene.name == "StarRating"
    compile(doc.code, "x.py", "exec")


def test_events_and_unwire(tmp_path):
    doc = make_rating(tmp_path)
    assert doc.events_of(None) == ("setup", "mount", "unmount")
    assert doc.update_event("change", new_name="picked") == "picked"
    doc.remove_event("picked")
    assert doc.custom_events == {}
    doc.wire("label1", "click")
    assert "def label1_click(self, event):" in doc.code
    doc.unwire("label1", "click", delete_code=True)
    assert "label1_click" not in doc.code


# -- SceneComponent at run time ---------------------------------------------------------


def test_component_runs_its_scene(tmp_path):
    doc = make_rating(tmp_path)
    path = doc.save()
    cls = load_component(path)
    assert cls is not None and issubclass(cls, designer.SceneComponent)
    assert cls.size == (200, 60) and cls.icon == "star" and list(cls.__props__) == ["value"]
    assert "rating" in {c.type for c in components.all_components()}  # in the toolbox

    got = []
    instance = cls.create(value=4, on_change=lambda e: got.append(e.value))
    assert isinstance(instance.render(), pz.Widget)
    assert instance.label1.text == "4 stars"  # the binding ran
    instance._dispatch(instance._controls()["button1"], "click")
    assert instance.value == 5 and got == [5]
    instance.label1.text = "custom"
    assert instance._controls()["label1"].props["text"] == "custom"
    other = cls.create()
    assert other._controls()["label1"] is not instance._controls()["label1"]


def test_nested_components_and_discover(tmp_path):
    make_rating(tmp_path).save()
    card = new_component("Card", tmp_path / "card.pzcomp")
    card.add("rating", 8, 8)
    card.add_member("stars", "int", 2)
    card.set_binding("rating1", "value", "stars")
    card.save()
    loaded = discover(tmp_path)
    assert {c.__name__ for c in loaded} == {"Rating", "Card"}
    cls = next(c for c in loaded if c.__name__ == "Card")
    owner = type("Owner", (), {})()
    with render_pass(owner):
        widget = cls(stars=4)
    assert isinstance(widget, pz.Widget)
    # a form using the component runs it
    form = designer.Form(width=300, height=200)
    form.add(components.get("card").create("card1", 10, 10))
    designer.save(form, tmp_path / "main.pzform")
    app = designer.open_form(tmp_path / "main.pzform")
    app.screenshot(tmp_path / "run.png", scale=1)
    assert (tmp_path / "run.png").exists()


def test_component_written_by_hand(tmp_path):
    (tmp_path / "badge.pzcomp").write_text(Scene(name="Badge", width=80, height=24).to_json(), encoding="utf-8")
    (tmp_path / "badge.py").write_text(textwrap.dedent('''\
        import pyzed as pz
        from pyzed.designer import SceneComponent

        class Badge(SceneComponent, scene="badge.pzcomp"):
            text: str = "New"
            seen: bool = pz.state(False)
        '''), encoding="utf-8")
    doc = open_document(tmp_path / "badge.pzcomp")
    assert [(m.name, m.public) for m in doc.members] == [("text", True), ("seen", False)]


# -- the designer UI ------------------------------------------------------------------


def test_designer_component_mode(tmp_path):
    from pyzed.designer import scene_panel

    path = make_rating(tmp_path).save()
    app = designer.Designer(path, language_servers=False)
    assert scene_panel.is_scene(app)
    app.view()
    app.select_from_outline("label1")
    app.view()  # bindings section
    app.select_form()
    scene_panel.open_method(app, "button1_click")
    assert app.editing[0] == "button1_click"
    app.view()
    app.close_code()
    commands = app.run_form()
    assert commands and isinstance(app.preview, scene_panel.ComponentPreview)
    app.preview.view()
    app.new()
    assert app.dialog == "new"
    app.view()
    app._new(new_component)
    assert isinstance(app.doc, SceneDocument) and app.doc.path is None
    app.save()
    assert app.dialog == "save_as" and app.dialog_path == "component1.pzcomp"
    app.save_as(str(tmp_path / "widgets" / "my_card"))
    assert (tmp_path / "widgets" / "my_card.pzcomp").exists()
    assert 'scene="my_card.pzcomp"' in (tmp_path / "widgets" / "my_card.py").read_text()
    app.screenshot(tmp_path / "designer.png", size=(1280, 800), scale=1)


def test_designed_component_keeps_the_values_it_changes(tmp_path):
    cls = load_component(make_rating(tmp_path).save())
    owner = type("Owner", (), {})()
    with render_pass(owner):
        cls(value=2)
    (instance,) = owner._pyzed_components.values()
    instance._dispatch(instance._controls()["button1"], "click")  # the component sets self.value = 3
    with render_pass(owner):
        cls(value=2)  # the parent passes the same value: the component's own value stays
    assert instance.value == 3
    with render_pass(owner):
        cls(value=5)  # a new value from the parent wins
    assert instance.value == 5
