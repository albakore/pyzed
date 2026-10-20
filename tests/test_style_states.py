"""State styles (hover, pressed, focus), transitions, min sizes and stylesheets."""

import pytest

import pyzed as pz
from pyzed import style as pzstyle, ui
from test_layout import _png_column


@pytest.fixture(autouse=True)
def clean_styles():
    yield
    pz.clear_stylesheet()
    pzstyle._named.clear()


def _tracks(anim):
    return {prop: frames for prop, frames in anim["tracks"]}


def test_states_become_animations_on_their_triggers():
    _, out = pzstyle._resolve(None, [], {
        "background": "#000000",
        "hover": {"background": "#ff0000", "translate": (0, -2)},
        "pressed": {"scale": 0.95},
        "focus": {"border_color": "accent"},
    })
    hover, pressed, focus = out["states"]
    assert [hover["trigger"], pressed["trigger"], focus["trigger"]] == ["hover", "press", "focus"]
    assert hover["duration"] == 0  # no transition: the state shows at once, like CSS
    assert _tracks(hover)["background"][-1][1] == "#ff0000"
    assert _tracks(hover)["y"][-1][1] == -2.0
    assert _tracks(pressed)["scale"][-1][1] == 0.95
    assert _tracks(focus)["border_color"][-1][1].startswith("#")  # the token, resolved
    assert "transitions" not in out and "hover" not in out


def test_transition_times_the_states_and_animates_effects():
    _, out = pzstyle._resolve(None, [], {"opacity": 0.5, "hover": {"opacity": 1}, "transition": "0.2s"})
    (hover,) = out["states"]
    assert hover["duration"] == 200
    assert _tracks(hover)["opacity"][-1][1] == 2.0  # relative to the widget's own 0.5
    moving = {t["prop"]: t["value"] for t in out["transitions"]}
    assert moving["opacity"] == 0.5 and moving["scale"] == 1.0
    assert "opacity" not in out  # set by the transition, not multiplied twice
    _, out = pzstyle._resolve(None, [], {"hover": {"scale": 1.1},
                                          "transition": {"duration": 90, "easing": "ease_in", "delay": 10}})
    assert out["states"][0]["duration"] == 90 and out["states"][0]["delay"] == 10


def test_states_merge_and_check_their_properties():
    base = pz.Style(hover={"background": "#111111"})
    both = base | pz.Style(hover={"color": "#ffffff"}, active={"scale": 0.9})
    assert both["hover"] == {"background": "#111111", "color": "#ffffff"}
    assert both["pressed"] == {"scale": 0.9}  # ``active`` is CSS's name for pressed
    assert pz.Style.from_dict(both.to_dict()) == both
    w = pz.text("x").style(hover={"color": "#ff0000"}).style(hover={"opacity": 0.5})
    assert w.style_props()["hover"] == {"color": "#ff0000", "opacity": 0.5}
    with pytest.raises(TypeError, match="hover can't set 'padding'"):
        pz.text("x").style(hover={"padding": 4})
    with pytest.raises(TypeError, match="must be a color"):
        pz.text("x").style(hover={"background": pz.Gradient(["#000000", "#ffffff"])})
    with pytest.raises(TypeError, match="unknown transition option"):
        pz.text("x").style(transition={"time": 100})


def test_stylesheet_selectors_and_specificity():
    pz.stylesheet({
        ".card": {"padding": 16, "background": "#111111"},
        ".card:hover": {"border_color": "#ff0000"},
        ".card.selected, #main": {"background": "#222222"},
        "#main": {"padding": 4},
        "Rating": {"radius": 6},
    }, pill={"radius": 99})
    assert pzstyle.matching(classes=["card"]).props == {
        "padding": 16, "background": "#111111", "hover": {"border_color": "#ff0000"}}
    assert pzstyle.matching(classes="card selected")["background"] == "#222222"  # two classes beat one
    assert pzstyle.matching(classes=["card"], id="main")["padding"] == 4  # an id beats classes
    assert pzstyle.matching("Rating", ["pill"])["radius"] == 99  # a class beats a name
    assert pzstyle.matching("Other").props == {}
    assert [r.selector for r in pzstyle.stylesheet_rules()][:3] == [".card", ".card:hover", ".card.selected"]
    pz.stylesheet({".card": {"padding": 8}})  # given again: replaced, not added
    assert pzstyle.matching(classes=["card"])["padding"] == 8
    w = pz.text("x").classes("card", None, id="main").style(padding=1)  # style() goes on top
    assert w.style_props()["padding"] == 1 and w.style_props()["background"] == "#222222"
    assert repr(pz.text("x").classes("unknown")) == '<Widget text "x">'
    pz.define_style("muted", color="#777777")  # named styles work as classes
    assert pz.text("x").classes("muted").style_props() == {"color": "#777777"}
    for bad in ("", ".a .b", ".a:visited", "#a#b"):
        with pytest.raises(ValueError):
            pz.stylesheet({bad: {"padding": 1}})


def test_components_take_classes_and_ids():
    class Badge(pz.Component):
        designer = False  # keeps the test class out of the designer's toolbox

        text: str = ""

        def render(self):
            return pz.text(self.text)

    class Tagged(pz.Component):
        designer = False  # keeps the test class out of the designer's toolbox

        id: str = ""  # a prop named ``id`` stays a prop

        def render(self):
            return pz.text(self.id)

    pz.stylesheet({"Badge": {"padding": 2}, ".big": {"size": 20}, "#hero": {"color": "#ff0000"}})
    assert Badge(text="a").style_props() == {"padding": 2}
    assert Badge(text="a", class_="big", id="hero", style={"padding": 6}).style_props() == {
        "padding": 6, "size": 20, "color": "#ff0000"}
    assert Tagged(id="hero").style_props() == {}
    assert Badge.create(text="a", class_="big").text == "a"


def test_states_min_sizes_and_transitions_render(tmp_path):
    pz.stylesheet({".box": {"background": "#ff0000", "width": 40, "height": 20, "hover": {"background": "#00ff00"}}})

    class Demo(pz.App):
        def view(self):
            return pz.column([
                pz.container(None).classes("box"),  # not hovered: its own color
                pz.text("").style(background="#ff0000", min_width=40, min_height=30),
                ui.button("b", lambda: None).style(background="#ff0000", height=20, width=40, opacity=0.5,
                                                    hover={"opacity": 1}, transition=100),
            ]).style(background="#000000", width="fill", height="fill")

    out = tmp_path / "states.png"
    pz.screenshot(Demo, out, size=(100, 100), scale=1)
    column = _png_column(out, 5)
    assert column[10][0] > 200 and column[10][1] < 60  # the box, red
    assert column[35][0] > 200 and column[49][0] > 200  # the min height: 30 px (20 to 50)
    assert 100 < column[51][0] < 160 and 100 < column[60][0] < 160  # the button at half opacity (set by its transition)
