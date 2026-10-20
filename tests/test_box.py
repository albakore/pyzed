"""pz.box: a div-like container with block, flex, grid and stack layouts, positions and overflow."""

import pytest

import pyzed as pz
from test_layout import _png_column


@pytest.fixture(autouse=True)
def clean_styles():
    yield
    pz.clear_stylesheet()


def _at(path, x, y):
    return _png_column(path, x)[y]


def test_box_checks_its_options_and_takes_styles():
    with pytest.raises(ValueError, match="display"):
        pz.box(display="inline")
    with pytest.raises(ValueError, match="overflow"):
        pz.box(overflow="auto")
    with pytest.raises(ValueError, match="align"):
        pz.box(align="baseline")
    with pytest.raises(ValueError, match="position"):
        pz.text("x").style(position="fixed")
    pz.stylesheet({".card": {"padding": 16, "radius": 8}, "box": {"color": "#ff0000"}})
    w = pz.box("a", [pz.text("b"), None], False, class_="card", style={"radius": 2}, gap=4, padding=6)
    assert w.style_props() == {"color": "#ff0000", "padding": 6, "radius": 2}
    assert pz.box(overflow="hidden").style_props()["clip"] is True


def test_style_props_reads_through_events_and_animations():
    w = pz.text("x").style(position="absolute", top=4).on(click=lambda: None).animate("fade_in")
    assert w.style_props() == {"position": "absolute", "top": 4}


def test_box_layouts_render(tmp_path):
    red, green = "#ff0000", "#00ff00"

    class Demo(pz.App):
        def view(self):
            return pz.box(
                # block: children as wide as the box
                pz.box(pz.text("").style(background=red, height=10), width=100),
                # grid: two equal columns
                pz.box(pz.container(None, height=10).style(background=red),
                       pz.container(None, height=10).style(background=green),
                       display="grid", columns=2, width=100),
                # an absolute child in the bottom right corner, out of the flow
                pz.box(pz.container(None, width=100, height=30),
                       pz.container(None, width=10, height=10).style(background=red, position="absolute",
                                                                      right=0, bottom=0),
                       width=100),
                # flex: justify end
                pz.box(pz.container(None, width=10, height=10).style(background=green), display="flex",
                       justify="end", width=100),
            ).style(background="#000000", width="fill", height="fill")

    out = tmp_path / "box.png"
    pz.screenshot(Demo, out, size=(120, 80), scale=1)
    assert _at(out, 1, 5)[0] > 200 and _at(out, 98, 5)[0] > 200 and _at(out, 105, 5)[0] < 20  # block
    assert _at(out, 10, 15)[0] > 200 and _at(out, 60, 15)[1] > 200 and _at(out, 60, 15)[0] < 20  # grid
    # the absolute child: bottom right of the 30 px tall box (20 to 50), out of the flow
    assert _at(out, 85, 45)[0] < 20 and _at(out, 95, 45)[0] > 200 and _at(out, 95, 25)[0] < 20
    assert _at(out, 50, 55)[1] < 20 and _at(out, 95, 55)[1] > 200  # flex, justify end


def test_widgets_report_the_size_they_were_given():
    assert pz.container(None, width=20)._length("width") == 20
    assert pz.container(None, width=20)._length("height") is None
    assert pz.text("x").style(width="shrink").on(click=lambda: None)._length("width") == "shrink"
    assert pz.container(None, height="fill:2").style(padding=1)._length("height") == "fill:2"
    assert pz.text("x")._length("width") is None
    with pytest.raises(ValueError, match="axis"):
        pz.text("x")._length("depth")


def test_box_keeps_sizes_and_centers(tmp_path):
    red, green = "#ff0000", "#00ff00"
    square = lambda: pz.container(None, width=20, height=20).style(background=red)

    class Demo(pz.App):
        def view(self):
            return pz.box(
                # a shrinking box keeps its content (it used to collapse to nothing)
                pz.box(pz.container(None, width=30, height=10), width="shrink", background=green),
                # a fixed width child stays fixed in a block box, centered by align_x
                pz.box(pz.text("").style(height=10), square(), align_x="center", width=200),
                # flex column centered on both axes
                pz.box(square(), display="flex", direction="column", justify="center", align="center",
                       width=200, height=60),
            ).style(background="#000000", width="fill", height="fill")

    out = tmp_path / "sizes.png"
    pz.screenshot(Demo, out, size=(200, 120), scale=1)
    assert _at(out, 15, 5)[1] > 200 and _at(out, 35, 5)[1] < 20  # the shrinking box: 30 px wide
    assert _at(out, 5, 25)[0] < 20 and _at(out, 100, 25)[0] > 200 and _at(out, 115, 25)[0] < 20  # 90 to 110
    # the flex box spans 40 to 100: its square sits in the middle, 60 to 80
    assert _at(out, 100, 55)[0] < 20 and _at(out, 100, 70)[0] > 200 and _at(out, 100, 85)[0] < 20
    assert _at(out, 85, 70)[0] < 20 and _at(out, 115, 70)[0] < 20
