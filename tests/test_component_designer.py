"""Tests for the designer's component mode: pz.state, the class code, scenes, SceneComponent and the UI."""

import textwrap
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import designer
from pyzed.component import render_pass
from pyzed.designer import components, scene_code
from pyzed.designer.scene import Scene, SceneDocument, discover, load, load_component, new_component, open_document


@pytest.fixture(autouse=True)
def _restore_registries():
    """The components these tests load (a ``Card``, a ``Rating``...) replace the library's of the same name;
    put the library's back so later tests see them."""
    from pyzed import component as _component

    specs, classes = dict(components._REGISTRY), dict(_component._REGISTRY)
    yield
    components._REGISTRY.clear()
    components._REGISTRY.update(specs)
    _component._REGISTRY.clear()
    _component._REGISTRY.update(classes)


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


def test_component_follows_the_theme_of_its_form(tmp_path):
    cls = load_component(make_rating(tmp_path).save())  # designed in the scene's own theme
    instance = cls.create(value=4)
    assert instance.ctx.theme.name == pz.theme.current().name  # used in code: the app's theme
    form = designer.Form(width=300, height=200, theme="Pyzed Light")
    form.add(components.get("rating").create("rating1", 10, 10))
    seen = []
    original = cls._theme
    cls._theme = lambda self, model: seen.append(original(self, model)) or seen[-1]
    try:
        components.get("rating").render(form["rating1"], components.RenderContext(designer.runtime.theme_for(form)))
    finally:
        cls._theme = original
    assert seen and seen[-1].name == "Pyzed Light"


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


def test_custom_events_live_in_the_events_tab(tmp_path, monkeypatch):
    from pyzed.designer import panels, scene_panel
    from ui_tree import install

    path = make_rating(tmp_path).save()
    app = designer.Designer(path, language_servers=False)
    t = app.theme_obj
    fake = install(monkeypatch)
    for module in (panels, scene_panel):
        monkeypatch.setattr(module, "_core", fake)
    texts = " ".join(panels.events(app, t).texts())
    assert "Built-in events" in texts and "Custom events (1)" in texts and "setup" in texts
    assert not any("Custom events" in x for row in scene_panel.component_rows(app, t) if row is not None
                   for x in row.texts())
    # an instance of the component on a form: its own events apart from the built-in ones
    load_component(path)
    form = designer.Form(width=300, height=200)
    form.add(components.get("rating").create("rating1", 10, 10))
    designer.save(form, tmp_path / "main.pzform")
    app = designer.Designer(tmp_path / "main.pzform", language_servers=False)
    app.doc.select("rating1")
    texts = panels.events(app, t).texts()
    custom = texts.index("Custom events (1)")
    assert texts.index("Built-in events") < texts.index("mouse_enter") < custom < texts.index("change")
    app.doc.select(None)  # the form has built-in events only
    assert "Custom events (1)" not in panels.events(app, t).texts()


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


# -- responsive layouts -----------------------------------------------------------------


def test_designed_component_follows_its_anchors(tmp_path):
    from pyzed.designer import scene_runtime

    doc = make_rating(tmp_path)
    doc.scene["label1"].anchor = ["left", "top", "right"]
    cls = load_component(doc.save())
    instance = cls.create()
    assert repr(instance.render()) == "<Widget container>"  # from code: up to its design size
    # placed by a form: the component fills the control's rectangle instead of its design size
    scene_runtime._placed.append(cls)
    try:
        assert repr(instance.render()) == "<Widget responsive>"
    finally:
        scene_runtime._placed.pop()
    form = designer.Form(width=400, height=200)
    form.add(components.get("rating").create("r", 0, 0, 400, 60))
    designer.save(form, tmp_path / "main.pzform")
    app = designer.open_form(tmp_path / "main.pzform")
    app.screenshot(tmp_path / "wide.png", scale=1)


def test_flex_items_shrink_when_there_is_no_room():
    from pyzed.designer import layout

    rects = layout.flex((0, 0, 300, 50), [(200, 50, 1), (200, 50, 1)], gap=0)
    assert [r[2] for r in rects] == [150, 150]
    assert rects[1][0] == 150


# -- inheritance -----------------------------------------------------------------------


def test_component_inherits_from_another(tmp_path):
    from pyzed.designer.scene import load as load_scene

    make_rating(tmp_path).save()
    doc = new_component("Big rating", tmp_path / "sub" / "big.pzcomp", extends=tmp_path / "rating.pzcomp")
    assert 'Rating = import_component("../rating.pzcomp")' in doc.code
    assert "class BigRating(Rating, scene=" in doc.code and "SceneComponent" not in doc.code
    assert [c.name for c in doc.scene.controls] == ["label1", "button1"] and doc.inherited("label1")
    doc.add("button", 8, 30, 80, 24)
    doc.scene["label1"].x = 50  # an inherited control changed here
    doc.add_member("extra", "int", 1)
    doc.save()
    own = load_scene(doc.path)
    assert own.extends == "../rating.pzcomp"
    assert [c.name for c in own.controls] == ["label1", "button2"]  # only what is new or changed

    cls = load_component(doc.path)
    assert cls.__mro__[1].__name__ == "Rating"
    assert list(cls.__props__) == ["value", "extra"] and "change" in cls.__events__
    instance = cls.create(value=2)
    instance.render()
    assert instance.label1.text == "2 stars" and instance._controls()["label1"].x == 50  # inherited binding
    instance._dispatch(instance._controls()["button1"], "click")  # inherited method
    assert instance.value == 3

    reopened = open_document(doc.path)
    assert [c.name for c in reopened.scene.controls] == ["label1", "button1", "button2"]
    assert {m.name for m in reopened.all_members} == {"extra", "value", "hover"}
    reopened.select(["label1", "button2"])
    assert reopened.delete() == ["button2"]  # inherited controls stay
    assert reopened.rename("label1", "other") == "label1"
    reopened.set_base(None)
    assert "class BigRating(SceneComponent" in reopened.code and "import_component" not in reopened.code
    assert [c.name for c in reopened.scene.controls] == ["label1"]
    compile(reopened.code, "big.py", "exec")


def test_base_changes_reach_the_components_that_inherit(tmp_path):
    from pyzed.designer.scene import import_component

    rating = make_rating(tmp_path)
    rating.save()
    new_component("Big", tmp_path / "big.pzcomp", extends=tmp_path / "rating.pzcomp").save()
    assert import_component(tmp_path / "rating.pzcomp") is import_component(tmp_path / "rating.pzcomp")
    rating.add("label", 8, 40)
    rating.save()
    big = components.get("big")
    assert big is not None
    from pyzed.component import find

    cls = find("big")
    assert "label2" in cls.create()._controls()


def test_set_base_rejects_cycles(tmp_path):
    make_rating(tmp_path).save()
    new_component("Big", tmp_path / "big.pzcomp", extends=tmp_path / "rating.pzcomp").save()
    rating = open_document(tmp_path / "rating.pzcomp")
    with pytest.raises(ValueError):
        rating.set_base(tmp_path / "big.pzcomp")
    with pytest.raises(ValueError):
        rating.set_base(tmp_path / "rating.pzcomp")


def test_set_base_code_edits():
    source = scene_code.new_module("Card", "card.pzcomp")
    out = scene_code.set_base(source, "Rating", "rating.pzcomp")
    assert scene_code.base_of(out) == ("Rating", "rating.pzcomp")
    assert "from pyzed.designer import import_component\n" in out
    again = scene_code.set_base(out, "Stars", "stars.pzcomp")
    assert again.count("import_component(") == 1 and scene_code.base_of(again) == ("Stars", "stars.pzcomp")
    back = scene_code.set_base(again, None, None)
    assert scene_code.base_of(back) is None and "class Card(SceneComponent, " in back
    assert "from pyzed.designer import SceneComponent\n" in back
    compile(back, "card.py", "exec")


def test_new_component_dialog(tmp_path, monkeypatch):
    make_rating(tmp_path).save()
    monkeypatch.chdir(tmp_path)
    app = designer.Designer(tmp_path / "rating.pzcomp", language_servers=False)
    app.new_component()
    assert app.dialog == "new" and app.new_state["kind"] == "component"
    assert app.new_state["name"] == "component1"
    app.view()
    app.set_new("name", "big rating")
    app.set_new("extends", str(tmp_path / "rating.pzcomp"))
    app.view()
    app.create_new_component()
    assert (tmp_path / "big_rating.pzcomp").exists() and app.doc.path.name == "big_rating.pzcomp"
    assert app.doc.inherited("label1")
    app.select_from_outline("label1")
    app.view()  # the "inherited" note
    app.select_form()
    app.view()  # the Inherited section
    app.new()
    assert app.new_state["kind"] == "form" and app.new_state["name"] == "form1"
    app.set_new("kind", "component")
    assert app.new_state["name"] == "component1"


def test_component_draws_its_styles(tmp_path):
    doc = make_rating(tmp_path)
    doc.set_style("label1", "weight", "bold")
    doc.set_style(None, "font", "serif")
    doc.set_style(None, "background", {"type": "linear", "angle": 90, "stops": [[0, "#112233"], [1, "#334455"]]})
    cls = load_component(doc.save())
    assert cls.scene_model().style["font"] == "serif"
    assert cls.scene_model()["label1"].style == {"weight": "bold"}
    assert isinstance(cls.create(value=4).render(), pz.Widget)
    form = designer.Form(width=300, height=200)
    form.add(components.get("rating").create("rating1", 10, 10))
    designer.save(form, tmp_path / "main.pzform")
    designer.open_form(tmp_path / "main.pzform").screenshot(tmp_path / "run.png", scale=1)
    assert (tmp_path / "run.png").exists()


# -- the Component view ------------------------------------------------------------------


def test_documents_open_in_tabs_and_components_in_their_view(tmp_path):
    make_rating(tmp_path).save()
    card = new_component("Card", tmp_path / "card.pzcomp")
    card.add("rating", 8, 8)
    card.save()
    form = designer.Form(width=300, height=200)
    form.add(components.get("card").create("card1", 10, 10))
    designer.save(form, tmp_path / "main.pzform")

    app = designer.Designer(tmp_path / "main.pzform", language_servers=False)
    assert len(app.docs) == 1 and not isinstance(app.doc, SceneDocument)
    app.view()
    app.open_default_event("card1")  # double-click a placed component: its Component view
    assert len(app.docs) == 2 and isinstance(app.doc, SceneDocument) and app.doc.path.name == "card.pzcomp"
    app.open_default_event("rating1")  # and the component inside it
    assert app.doc.path.name == "rating.pzcomp" and len(app.docs) == 3
    app.view()
    app.select_doc(0)
    assert app.doc.path.name == "main.pzform"
    app.open_path(tmp_path / "card.pzcomp")  # already open: its tab
    assert len(app.docs) == 3 and app.doc.path.name == "card.pzcomp"
    app.doc.add("label", 0, 0)
    app.close_doc()
    assert app.dialog == "confirm" and len(app.docs) == 3  # unsaved: asks first
    app.confirm_discard()
    assert len(app.docs) == 2


def test_property_kinds_pick_the_editor():
    from typing import Annotated, Literal

    from pyzed.component import _designer_prop

    class Badge(pz.Component):
        designer = False
        notes: pz.Multiline = ""
        tint: pz.Color = "accent"
        mark: pz.Icon = "star"
        scale: Literal["sm", "md"] = "md"
        level: Annotated[int, pz.Range(0, 10)] = 3

        def render(self):
            return pz.text(self.notes)

    props = {p.name: p for p in (_designer_prop(i, components.Prop) for i in Badge.__props__.values())}
    assert props["notes"].kind == "multiline" and props["tint"].kind == "color" and props["mark"].kind == "icon"
    assert props["scale"].kind == "choice" and props["scale"].choices == ("sm", "md")
    assert (props["level"].kind, props["level"].min, props["level"].max) == ("number", 0, 10)


def test_member_kinds_in_the_class_code(tmp_path):
    doc = make_rating(tmp_path)
    doc.update_member("value", type=scene_code.type_for("Range"))
    assert doc.member("value").type == "Annotated[int, pz.Range(0, 100)]" and doc.member("value").default == 3
    doc.add_member("tint", scene_code.type_for("Color"))
    doc.add_member("mode", scene_code.choice_type(["fast", "slow"]))
    assert doc.member("tint").default == "accent" and doc.member("mode").default == "fast"
    assert "from typing import Annotated, Literal\n" in doc.code and "import pyzed as pz\n" in doc.code
    assert scene_code.kind_of(doc.member("mode").type) == "Choice"
    assert scene_code.choices_of(doc.member("mode").type) == ["fast", "slow"]
    doc.update_member("mode", type=scene_code.choice_type(["a", "b"]))
    assert doc.member("mode").default == "a"
    assert scene_code.range_of("Annotated[float, pz.Range(0, 1, 0.1)]") == ("float", 0, 1, 0.1)
    compile(doc.code, "rating.py", "exec")
    cls = load_component(doc.save())
    assert cls.create().value == 3


def test_reusable_methods_and_children_from_the_tree(tmp_path):
    from pyzed.designer import scene_panel

    rating = make_rating(tmp_path)
    name = rating.add_method("bump", "self, by=1")
    rating.set_handler_source(name, "def bump(self, by=1):\n    self.value += by\n")
    assert rating.add_method("bump") == "bump2"
    rating.save()
    card = new_component("Card", tmp_path / "card.pzcomp")
    card.add("rating", 8, 8)
    card.save()
    members = scene_panel.child_members("rating")
    assert members["properties"] == ["value"] and "bump" in members["methods"]
    assert "button1_click" not in members["methods"]  # handlers of its own controls are not listed

    cls = load_component(tmp_path / "card.pzcomp")
    owner = type("Owner", (), {})()
    with render_pass(owner):
        cls()
    (instance,) = [i for i in owner._pyzed_components.values() if type(i) is cls]
    instance.rating1.bump(2)  # a method of the child component, through the control
    assert instance.rating1.instance.value == 5

    app = designer.Designer(tmp_path / "card.pzcomp", language_servers=False)
    app.toggle_members("rating1")
    app.view()  # the outline lists value and bump()
    command = scene_panel.insert_snippet(app, "self.rating1.bump()")
    assert command is not None and app.editing is None  # copied: no code open
    scene_panel.add_method(app, "reset")
    assert app.editing[0] == "reset"
    app.assist.cursor = (3, 5)
    scene_panel.insert_snippet(app, "self.rating1.bump()")
    assert "    self.rating1.bump()" in app.editing[1]


def test_properties_reach_the_open_code_and_survive_saving(tmp_path):
    doc = make_rating(tmp_path)
    doc.save()
    app = designer.Designer(tmp_path / "rating.pzcomp", language_servers=False)
    app.edit_whole_file()
    app.view()
    app.doc.add_member("speed", "float", 1.5)  # from Properties, while the whole file is open
    app.view()
    assert "speed: float = 1.5" in app.editing[1]
    app.save()
    assert "speed: float = 1.5" in (tmp_path / "rating.py").read_text()

    # text typed in the editor and not applied yet is merged with the change from Properties
    typed = app.editing[1].rstrip() + "\n\n    def extra(self):\n        return 1\n"
    app.set_code_buffer(typed)
    app.doc.update_member("speed", default=2.5)
    app.view()
    assert "speed: float = 2.5" in app.editing[1] and "def extra(self)" in app.editing[1]
    app.save()
    saved = (tmp_path / "rating.py").read_text()
    assert "speed: float = 2.5" in saved and "def extra(self)" in saved


def test_merge3_keeps_both_sides():
    from pyzed.designer.code import merge3

    base = "a\nb\nc\nd\ne\n"
    assert merge3(base, "a\nB\nc\nd\ne\n", "a\nb\nc\nd\nE\n") == "a\nB\nc\nd\nE\n"
    assert merge3(base, base, "z\n" + base) == "z\n" + base
    assert merge3(base, "a\nO\nc\nd\ne\n", "a\nT\nc\nd\ne\n") == "a\nO\nc\nd\ne\n"  # the editor wins a clash


def test_any_annotation_parses_to_an_editor_type():
    from pyzed.designer import type_editor as te

    cases = {
        "int | str | list[str] | dict[str, int]": ("union", "0"),
        "Optional[float]": ("optional", "None"),
        "float | None": ("optional", "None"),
        "tuple[int, int]": ("tuple", "(0, 0)"),
        "tuple[str, ...]": ("list", "()"),
        "set[int]": ("set", "set()"),
        "dict[str, int]": ("dict", "{}"),
        "list[Point]": ("list", "[]"),
        "Point": ("class", "Point()"),
        "Literal['a', 'b']": ("choice", "'a'".replace("'", '"')),
        "Annotated[int, pz.Range(2, 5)]": ("range", "2"),
        "pz.Color": ("Color", '"accent"'),
        "Any": ("any", "None"),
    }
    for annotation, (kind, default) in cases.items():
        t = te.parse_type(annotation)
        assert (t.kind, te.default_source(t)) == (kind, default), annotation
    assert te.fits(te.parse_type("int | None"), "None") and not te.fits(te.parse_type("int"), '"x"')


def test_typed_editors_write_python_source():
    from pyzed.designer import type_editor as te

    out = []
    classes = te.class_resolver(te.module_classes("class Point:\n    x: int = 0\n    label: str = ''\n"))
    ctx = te.Context(None, pz.themes.ONE_DARK, classes)

    def build(annotation, source):
        out.clear()
        return te.build(te.parse_type(annotation), source, out.append, ctx, "k")

    head, rows = build("list[str]", '["a", "b"]')
    assert [r.label for r in rows] == ["[0]", "[1]"]
    head, rows = build("dict[str, int]", '{"a": 1}')
    assert len(rows) == 1
    head, rows = build("Point", "Point(x=3)")
    assert [r.label for r in rows] == ["x", "label"]
    head, rows = build("Point | None", "None")
    assert rows == []
    head, rows = build("Point", "Point()")
    assert [r.label for r in rows] == ["x", "label"]  # the fields show their defaults


def test_any_type_of_property_in_the_class(tmp_path):
    doc = make_rating(tmp_path)
    doc.set_code(doc.code.replace("from pyzed.designer import SceneComponent",
                                  "from dataclasses import dataclass\n\nfrom pyzed.designer import SceneComponent"
                                  "\n\n\n@dataclass\nclass Point:\n    x: int = 0\n    y: int = 0"))
    assert doc.scene.name == "Rating"  # a helper class before the component does not rename it
    doc.add_member("mixed", "int | str | list[str] | dict[str, int]")
    doc.add_member("maybe", "Optional[float]")
    doc.add_member("origin", "Point")
    doc.add_member("tags", "list[str]")
    doc.set_member_source("tags", '["red", "blue"]')
    assert doc.member("mixed").default == 0 and doc.member("maybe").default is None
    assert doc.member("origin").default_source == "Point()" and doc.member("tags").default == ["red", "blue"]
    doc.update_member("tags", type="dict[str, int]")
    assert doc.member("tags").default == {}
    assert "from typing import Optional\n" in doc.code and "origin: Point = Point()" in doc.code
    cls = load_component(doc.save())
    rating = cls.create()
    assert rating.mixed == 0 and rating.maybe is None and rating.origin.x == 0


def test_component_props_of_any_type_get_the_typed_editor():
    from typing import Optional

    from pyzed.component import _designer_prop

    class Gauge(pz.Component):
        designer = False
        limit: Optional[float] = None
        marks: dict[str, int] = {}
        names: list[str] = []

        def render(self):
            return pz.text("")

    props = {p.name: p for p in (_designer_prop(i, components.Prop) for i in Gauge.__props__.values())}
    assert (props["limit"].kind, props["limit"].type) == ("typed", "float | None")
    assert (props["marks"].kind, props["marks"].type) == ("typed", "dict[str, int]")
    assert props["names"].kind == "list"


def test_color_properties_use_the_color_picker_and_survive_half_typed_values(tmp_path):
    doc = make_rating(tmp_path)
    doc.add_member("tint", "pz.Color")
    doc.save()
    app = designer.Designer(tmp_path / "rating.pzcomp", language_servers=False)
    app.view()
    picker = next(k for k in app.picker_targets if k.endswith("member:tint"))
    app.toggle_color_picker(None, picker)  # the swatch opens the floating picker
    app.view()
    assert app.color_picker_at(app.theme_obj) is not None
    _value, change = app.picker_targets[picker]
    change("#")  # typed so far: not a color yet
    assert app.doc.member("tint").default == "#"
    app.view()  # the swatch stays empty instead of failing
    change("#3b82f6")
    assert app.doc.member("tint").default == "#3b82f6"
    from pyzed.designer.panels import valid_color

    t = app.theme_obj
    assert valid_color("#", t) is None and valid_color("nope", t) is None and valid_color("#3b8", t) == "#3b8"
    assert valid_color("accent", t) == t.accent
