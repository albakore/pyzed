"""Web-like components: children, context, class stylesheets and animate=."""

import pytest

import pyzed as pz
from pyzed import style as pzstyle


@pytest.fixture(autouse=True)
def clean():
    yield
    pz.clear_stylesheet()


def test_positional_arguments_are_the_children():
    class Card(pz.Component):
        designer = False  # keeps the test class out of the designer's toolbox

        title: str = ""
        children: list = ()

        def render(self):
            return pz.column(list(self.children))

    card = Card.create(pz.text("a"), [pz.text("b"), None, False], title="T")
    assert [repr(c) for c in card.children] == ['<Widget text "a">', '<Widget text "b">']
    assert card.title == "T"
    with pytest.raises(TypeError, match="children both"):
        Card(pz.text("a"), children=[])
    assert repr(Card(pz.text("a"))) == "<Widget column [1]>"


def test_context_reaches_the_components_rendered_inside():
    seen = []

    class Leaf(pz.Component):
        designer = False  # keeps the test class out of the designer's toolbox

        def render(self):
            seen.append((self.context("user"), pz.use_context("compact", "no"), pz.use_context("depth")))
            return pz.text("leaf")

    class Panel(pz.Component):
        designer = False  # keeps the test class out of the designer's toolbox

        def provide(self):
            return {"compact": True, "depth": 2}

        def render(self):
            return pz.column([Leaf()])

    with pz.provide(user="kev", depth=1):
        Panel()
        Leaf()
    Leaf()
    assert seen == [("kev", True, 2), ("kev", "no", 1), (None, "no", None)]


def test_class_stylesheet_and_animate():
    class Badge(pz.Component):
        designer = False  # keeps the test class out of the designer's toolbox

        stylesheet = {"&": {"padding": 4}, "&:hover": {"opacity": 0.8}, "&.big": {"size": 20}}

        def render(self):
            return pz.text("x")

    assert {r.selector for r in pzstyle.stylesheet_rules()} >= {"Badge", "Badge:hover", "Badge.big"}
    assert Badge(class_="big").style_props() == {"padding": 4, "hover": {"opacity": 0.8}, "size": 20}
    assert repr(Badge(animate="fade_in")).endswith(".animate(1 animation(s))")
    assert repr(Badge(animate=["fade_in", "pulse"])).endswith(".animate(2 animation(s))")
    assert "stylesheet" not in Badge.__props__

    class Boxed(pz.Component):
        designer = False

        def render(self):
            return pz.text("x").style(padding=9)

    pz.stylesheet({"Boxed": {"padding": 1, "radius": 3}, ".tight": {"padding": 0}})
    # rules for the name are defaults under what render() sets; the caller's classes go on top
    assert Boxed().style_props() == {"padding": 9, "radius": 3}
    assert Boxed(class_="tight").style_props() == {"padding": 0, "radius": 3}
