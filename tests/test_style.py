"""widget.style(), pz.Style, named and global styles, gradients, paints and masks."""

import pytest

import pyzed as pz
from pyzed import style as pzstyle, ui
from test_layout import _png_column


@pytest.fixture(autouse=True)
def clean_styles():
    yield
    pz.set_style(None)
    pzstyle._named.clear()


def test_style_wraps_and_merges():
    w = pz.text("hi").style(color="#ff0000", size=20, bg="#000000", radius=4)
    assert repr(w) == '<Widget text "hi">.style()'
    assert w.style_props() == {"color": "#ff0000", "size": 20, "background": "#000000", "radius": 4}
    again = w.style(pz.Style(padding=8), size=None)  # None removes a property
    assert again.style_props() == {"color": "#ff0000", "background": "#000000", "radius": 4, "padding": 8}
    assert repr(again) == '<Widget text "hi">.style()'  # merged, not wrapped twice
    assert pz.text("x").style_props() == {}
    with pytest.raises(TypeError, match="unknown style property"):
        pz.text("x").style(colour="red")
    with pytest.raises(ValueError, match="invalid color"):
        pz.text("x").style(color="not-a-token")


def test_style_objects_named_styles_and_tokens():
    card = pz.define_style("card", padding=12, radius=8, background="panel")
    assert pz.style.named_styles()["card"] == card
    loud = pz.Style(color="error", weight="bold")
    both = card | loud
    assert both.props == {**card.props, **loud.props} and both["bg"] == "panel"
    assert both.without("color").get("color") is None and both.text() == loud
    w = pz.text("x").style("card", loud, border=(1, "border"))
    assert w.style_props() == {**both.props, "border_width": 1, "border_color": "border"}
    with pytest.raises(KeyError, match="define_style"):
        pz.text("x").style("nope")


def test_style_round_trips_through_json():
    import json

    s = pz.Style(background=pz.Paint(pz.Gradient(["#ff0000", (0.7, "#00ff00"), "#0000ff"], angle=90),
                                     opacity=0.5, mask=pz.Mask([1, 0])),
                 shadow=("#000000", (0, 2), 4), padding=(4, 8), radius=(1, 2, 3, 4), font="mono")
    assert pz.Style.from_dict(json.loads(json.dumps(s.to_dict()))) == s
    g = pz.Style(background=pz.Gradient(["#ff0000", "#0000ff"]))
    assert pz.Style.from_dict(g.to_dict()) == g


def test_gradients_paints_and_masks():
    g = pz.Gradient(["#ff0000", "#0000ff"], angle=90)
    assert g.to_value() == (90.0, [(0.0, "#ff0000"), (1.0, "#0000ff")])
    assert pz.Paint("#3b82f6", opacity=0.5).resolve() == ("#3b82f680", None)
    color, gradient = pz.Paint("#3b82f6", mask=pz.Mask([1, 0], angle=0)).resolve()
    assert color is None and gradient == (0.0, [(0.0, "#3b82f6"), (1.0, "#3b82f600")])
    # A mask on a gradient follows it and adds its own stops.
    _, gradient = pz.Paint(g, mask=pz.Mask([(0, 1), (0.5, 0.5), (1, 1)])).resolve()
    assert gradient == (90.0, [(0.0, "#ff0000"), (0.5, "#80008080"), (1.0, "#0000ff")])
    with pytest.raises(ValueError, match="at least two"):
        pz.Gradient(["#fff"])
    with pytest.raises(ValueError, match="at most 8"):
        pz.Gradient(["#fff"] * 9)
    assert pz.style.to_hex((255, 0, 0, 0.5)) == "#ff000080"
    # Gradients work as backgrounds, also the (angle, stops) tuple containers take.
    assert pz.text("x").style(background=(45, ["#fff", "#000"])).style_props()["background"] == (45, ["#fff", "#000"])


def test_component_style_kwarg(tmp_path):
    class Badge(pz.Component):
        text: str = ""

        def render(self):
            return pz.text(self.text)

    class Variant(pz.Component):
        style: str = "solid"  # a prop with that name keeps its meaning

        def render(self):
            return pz.text(self.style)

    assert repr(Badge(text="a", style={"color": "#ff0000"})) == '<Widget text "a">.style()'
    assert repr(Variant(style="outline")) == '<Widget text "outline">'


def test_scene_component_style_kwarg(tmp_path):
    from test_component_designer import make_rating

    from pyzed.designer import load_component

    cls = load_component(make_rating(tmp_path).save())
    widget = cls(value=2, style=pz.Style(background="#112233", radius=6))
    assert widget.style_props() == {"background": "#112233", "radius": 6}


def test_global_style_becomes_theme_tokens():
    class Demo(pz.App):
        style = pz.Style(color="#ff0000", size=16, radius=2, background="#101010", font="mono")

        def view(self):
            return pz.text("x")

    app = Demo()
    t = app.resolved_theme()
    assert (t.text, t.ui_font_size, t.radius, t.background) == ("#ff0000", 16.0, 2.0, "#101010")
    pz.set_style(color="#00ff00", weight="bold")
    assert app.resolved_style().props["color"] == "#ff0000"  # the window's wins
    assert app.resolved_style().props["weight"] == "bold"
    root = app.__pyzed_view__()
    assert root.style_props()["font"] == "mono" and root.style_props()["width"] == "fill"


def _reds(path, x):
    return [y for y, (r, g, b) in enumerate(_png_column(path, x)) if r > 200 and g < 60 and b < 60]


def test_styles_render(tmp_path):
    class Demo(pz.App):
        def view(self):
            return pz.column([
                # A button styled directly: its own box becomes red and square.
                ui.button("button", lambda: None).style(background="#ff0000", radius=0, height=30, width=120),
                pz.space(height=10),
                # Any other widget gets a box around it, with margin outside.
                pz.text("text").style(background="#ff0000", height=20, width=120, margin=(10, 0)),
                pz.container(None, width=120, height=40).style(
                    background=pz.Paint("#ff0000", mask=pz.Mask([1, 0]))),
            ]).style(background="#000000", width="fill", height="fill")

    out = tmp_path / "styles.png"
    pz.screenshot(Demo, out, size=(200, 200), scale=1)
    reds = _reds(out, 5)
    assert 1 in reds and 28 in reds and 31 not in reds  # the button (with its 1 px border), 30 px tall
    assert 45 not in reds and 50 in reds and 69 in reds and 75 not in reds  # the text box between margins
    column = _png_column(out, 5)
    assert column[81][0] > 200 and column[100][0] < 160 and column[118][0] < 20  # the mask fades it out
