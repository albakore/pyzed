"""Responsive styles: media queries in styles and stylesheets, breakpoints and pz.viewport()."""

import pytest

import pyzed as pz
from pyzed import style as pzstyle
from test_layout import _png_column


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setattr(pzstyle, "_viewport", (500.0, 800.0))
    yield
    pz.clear_stylesheet()


def test_media_queries_and_breakpoints():
    assert pz.viewport() == (500.0, 800.0)
    assert pz.media("max_width: 600") and pz.media("(max_width: 600px) and (orientation: portrait)")
    assert not pz.media("md") and pz.media(min_width=400, max_height=900)
    assert not pz.media(orientation="landscape")
    assert pz.current_breakpoint() == "xs"
    pzstyle._viewport = (1100.0, 700.0)
    assert pz.current_breakpoint() == "lg" and pz.media("md") and pz.media(orientation="landscape")
    assert pz.media(theme="dark") != pz.media(theme="light")
    for bad in ("width: 3", "max_width 600", "orientation: sideways", "huge"):
        with pytest.raises(ValueError):
            pz.media(bad)


def test_style_media_applies_when_it_matches_and_stays_in_the_source():
    w = pz.text("x").style(padding=24, media={"max_width: 600": {"padding": 8}, "lg": {"padding": 40}})
    assert w.style_props() == {"padding": 24, "media": {"max_width: 600": {"padding": 8}, "lg": {"padding": 40}}}
    _, out = pzstyle._resolve(None, [w.style_props()], None)
    assert out["padding"] == 8 and "media" not in out
    pzstyle._viewport = (1300.0, 800.0)
    assert pzstyle._resolve(None, [w.style_props()], None)[1]["padding"] == 40
    both = pz.Style(media={"md": {"padding": 1}}) | pz.Style(media={"lg": {"padding": 2}})
    assert both["media"] == {"md": {"padding": 1}, "lg": {"padding": 2}}
    assert pz.Style.from_dict(both.to_dict()) == both
    with pytest.raises(ValueError, match="media query"):
        pz.Style(media={"wide": {"padding": 1}})


def test_stylesheet_media_rules():
    pz.stylesheet({
        ".side": {"width": 260},
        "@media (max_width: 700)": {".side": {"width": 64}, ".side:hover": {"opacity": 0.5}},
        "@md": {".side": {"padding": 3}},
    })
    assert pzstyle.matching(classes="side").props == {"width": 64, "hover": {"opacity": 0.5}}
    pzstyle._viewport = (900.0, 800.0)
    assert pzstyle.matching(classes="side").props == {"width": 260, "padding": 3}
    with pytest.raises(TypeError, match="rules"):
        pz.stylesheet({"@md": 3})


def test_media_follows_the_screenshot_size(tmp_path):
    pz.stylesheet({".box": {"background": "#00ff00", "width": 20, "height": 20},
                   "@media (max_width: 400)": {".box": {"background": "#ff0000"}}})

    class Demo(pz.App):
        def view(self):
            return pz.container(None).classes("box")

    for width, red in ((300, True), (500, False)):
        out = tmp_path / f"media{width}.png"
        pz.screenshot(Demo, out, size=(width, 100), scale=1)
        assert (_png_column(out, 5)[5][0] > 200) is red
    assert pzstyle._screen is None
