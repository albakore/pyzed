"""Animations, transitions, presence, window transitions and visual effects (glow, bloom, glass, opacity)."""

import json
import math

import pytest

import pyzed as pz
from pyzed import animation as anim
from pyzed import style as pzstyle
from test_layout import _png_column


@pytest.fixture(autouse=True)
def motion_on():
    pz.set_reduced_motion(False)
    yield
    pz.set_reduced_motion(False)


# -- compiling animate() and transition() ---------------------------------------------------


def test_presets_compile_with_their_timing_and_options_override_it():
    (fade,) = anim._compile(["fade_in_up"], {})
    assert fade["trigger"] == "mount" and fade["duration"] == 280 and fade["easing"] == "ease_out_cubic"
    assert dict(fade["tracks"]) == {"opacity": [(0.0, 0.0, None), (1.0, 1.0, None)],
                                    "y": [(0.0, 16.0, None), (1.0, 0.0, None)]}
    (lift,) = anim._compile(["lift"], {"duration": "0.5s", "easing": (0.2, 0, 0, 1), "on": "press"})
    assert lift["trigger"] == "press" and lift["duration"] == 500
    assert lift["easing"] == ("cubic_bezier", 0.2, 0.0, 0.0, 1.0)
    (loop,) = anim._compile(["pulse"], {"repeat": "infinite", "key": 3})
    assert math.isinf(loop["iterations"]) and loop["key"] == "3"
    assert anim._compile(["glow_pulse"], {"active": True})[0]["trigger"] == "active"
    two = anim._compile([["fade_in", "pulse"], None], {})
    assert [len(a["tracks"]) for a in two] == [1, 1]


def test_property_values_make_an_animation_for_the_trigger():
    (mount,) = anim._compile([], {"opacity": 0, "x": "-50%"})
    assert dict(mount["tracks"]) == {"opacity": [(0.0, 0.0, None), (1.0, None, None)],
                                     "x": [(0.0, ("pct", -0.5), None), (1.0, None, None)]}
    (hover,) = anim._compile([], {"on": "hover", "scale": 1.05, "background": "#ff0000"})
    assert hover["trigger"] == "hover" and hover["duration"] == 150
    assert dict(hover["tracks"])["background"] == [(0.0, None, None), (1.0, "#ff0000", None)]
    (click,) = anim._compile([], {"on": "click", "y": -4})
    assert [f[1] for f in dict(click["tracks"])["y"]] == [None, -4.0, None]
    with pytest.raises(TypeError, match="presets or property values"):
        anim._compile(["fade_in"], {"opacity": 0})


def test_triggers_start_animations_from_code():
    shake = pz.Trigger()
    (manual,) = anim._compile(["shake"], {"on": shake})
    assert manual["trigger"] == "manual" and manual["key"] == "0"
    shake.fire()
    shake.fire("ignored", "arguments")  # usable as any callback
    assert shake.count == 2 and repr(shake) == "Trigger(count=2)"
    assert anim._compile(["shake"], {"on": shake})[0]["key"] == "2"
    assert anim._compile(["shake"], {"on": shake, "key": "a"})[0]["key"] == repr(("a", 2))
    (back,) = anim._compile([], {"on": shake, "scale": 1.2})  # values: there and back, like a click
    assert back["trigger"] == "manual" and [f[1] for f in dict(back["tracks"])["scale"]] == [None, 1.2, None]
    assert anim._compile(["pulse"], {"on": "manual", "key": 1})[0]["trigger"] == "manual"
    assert "manual" in anim.TRIGGERS and pz.Animation([{"x": 0}, {"x": 4}], on="manual").on == "manual"
    assert "animate" in repr(pz.text("x").animate("shake", on=shake))


def test_invalid_options_explain_what_is_valid():
    with pytest.raises(TypeError, match="unknown animate\\(\\) option 'speed'"):
        anim._compile(["fade_in"], {"speed": 2})
    with pytest.raises(ValueError, match="unknown trigger 'hovering'"):
        anim._compile(["fade_in"], {"on": "hovering"})
    with pytest.raises(ValueError, match="unknown easing 'bouncy'"):
        anim._compile(["fade_in"], {"easing": "bouncy"})
    with pytest.raises(ValueError, match="invalid repeat"):
        anim._compile(["fade_in"], {"repeat": -1})
    with pytest.raises(KeyError, match="no animation named 'nope'"):
        anim._compile(["nope"], {})
    with pytest.raises(TypeError, match="unknown animated property 'skew'"):
        pz.Animation([{"skew": 0}, {"skew": 90}])
    with pytest.raises(ValueError, match="offsets go from 0 to 1"):
        pz.Animation({2: {"opacity": 0}})


def test_keyframe_formats_and_round_trip_through_json():
    a = pz.Animation({"from": {"opacity": 0}, "40%": {"opacity": 1, "easing": "ease_in"}, "to": {"scale": 1.2}},
                     duration=500, easing="steps(4)", repeat=3, direction="alternate")
    assert a.properties == ("opacity", "scale") and a.total == 1500
    compiled = a.compile()
    assert compiled["easing"] == ("steps", 4) and compiled["direction"] == "alternate"
    assert dict(compiled["tracks"])["opacity"] == [(0.0, 0.0, None), (0.4, 1.0, "ease_in")]
    data = json.loads(json.dumps(a.to_dict()))
    assert pz.Animation.from_dict(data) == a
    listed = pz.Animation([{"x": 0}, {"x": 10, "offset": 0.25}, {"x": 0}])
    assert [f[0] for f in listed.compile()["tracks"][0][1]] == [0.0, 0.25, 1.0]


def test_define_animation_and_preset_catalog():
    try:
        wiggle = pz.define_animation("wiggle_test", [{"x": 0}, {"x": 4}, {"x": 0}], duration=200)
        assert anim.animation("wiggle_test") is wiggle
        assert pz.text("x").animate("wiggle_test")
    finally:
        anim._presets.pop("wiggle_test", None)
    assert set(anim.CATEGORIES) == {a.category for a in anim.PRESETS.values()}
    assert all(a.description for a in anim.PRESETS.values())
    assert "fade_in" in anim.presets("entrance") and "fade_in" not in anim.presets("exit")
    for name, (enter, exit_) in anim.WINDOW_TRANSITIONS.items():
        assert enter in anim.PRESETS and exit_ in anim.PRESETS, name


def test_transitions_compile_per_property():
    out = anim._compile_transition({"opacity": 0.5, "x": "10%", "color": "#00ff00", "duration": 400,
                                    "scale": {"value": 2, "duration": 100, "easing": "linear"}})
    by = {t["prop"]: t for t in out}
    assert by["opacity"]["duration"] == 400 and by["opacity"]["easing"] == "ease_out"
    assert by["x"]["value"] == ("pct", 0.1) and by["color"]["value"] == "#00ff00"
    assert by["scale"]["value"] == 2.0 and by["scale"]["duration"] == 100 and by["scale"]["easing"] == "linear"
    with pytest.raises(TypeError, match="unknown animated property"):
        anim._compile_transition({"rotation": 3})


def test_easings_match_css():
    assert anim.ease("linear", 0.3) == pytest.approx(0.3)
    assert anim.ease("ease_in_out", 0.5) == pytest.approx(0.5, abs=1e-3)
    assert anim.ease((0.42, 0, 1, 1), 0.5) == pytest.approx(anim.ease("ease_in", 0.5), abs=1e-4)
    assert anim.ease("steps(4)", 0.3) == pytest.approx(0.25)
    for name in anim.EASINGS:
        assert anim.ease(name, 0) == pytest.approx(0, abs=1e-3), name
        assert anim.ease(name, 1) == pytest.approx(1, abs=1e-3), name
    assert anim.ease("ease_out_back", 0.6) > 1  # overshoots on purpose


# -- widgets ----------------------------------------------------------------------


def test_animate_and_transition_wrap_once_and_merge():
    w = pz.text("hi").animate("fade_in").animate("lift")
    assert repr(w) == '<Widget text "hi">.animate(2 animation(s))'
    w = w.transition(opacity=1).transition(opacity=0.5, x=4)
    assert repr(w) == '<Widget text "hi">.animate(2 animation(s), 2 transition(s))'
    styled = pz.text("x").style(color="#ff0000").animate("pulse")
    assert repr(styled) == '<Widget text "x">.style().animate(1 animation(s))'


def test_stagger_delays_each_item_and_presence_builds():
    items = pz.stagger([pz.text("a"), "b", pz.text("c")], "fade_in", step=50, delay=100)
    assert len(items) == 3 and all("animate(1 animation(s))" in repr(i) for i in items)
    assert repr(pz.presence(pz.text("page"), key=1)) == "<Widget presence>"
    assert repr(pz.presence(pz.text("page"), key="a", enter=None, exit="fade_out", id="x")) == "<Widget presence>"


def test_reduced_motion_switch():
    assert pz.animation.reduced_motion() is False
    pz.set_reduced_motion(True)
    assert pz.animation.reduced_motion() is True


# -- style effects ----------------------------------------------------------------


def test_effects_expand_into_box_properties():
    pz.theme.use(pz.themes.ONE_DARK)
    _, out = pzstyle._resolve(None, (), {"glow": ("#ff0000", 20)})
    assert out["shadow"] == ("#ff0000d9", (0, 0), 20.0)
    _, out = pzstyle._resolve(None, (), {"glow": 8})
    assert out["shadow"][1:] == ((0, 0), 8.0) and out["shadow"][0].startswith(pz.themes.ONE_DARK.accent.lower()[:7])
    _, out = pzstyle._resolve(None, (), {"bloom": ("#00ff00", 1.0)})
    assert out == {"bloom_light": ("#00ff00", 1.0)}  # a bare text or icon only glows
    _, out = pzstyle._resolve(None, (), {"bloom": ("#00ff00", 1.0), "background": "#000000"})
    assert out["shadow"][2] == 28.0 and out["border_width"] == 1
    assert out["bloom_light"] == ("#00ff00", 1.0)
    _, out = pzstyle._resolve(None, (), {"glass": True, "radius": 4})
    assert "gradient" in out and out["radius"] == 4 and out["border_width"] == 1  # given properties win
    assert out["backdrop_blur"] == 20.0
    _, out = pzstyle._resolve(None, (), {"glass": {"blur": 6}})
    assert out["backdrop_blur"] == 6.0
    _, out = pzstyle._resolve(None, (), {"rotate": "0.25turn", "blur": 3})
    assert out == {"rotate": 90.0, "blur": 3.0}
    _, out = pzstyle._resolve(None, (), {"glass": {"tint": "#000000", "strength": 0.5}})
    assert out["border_color"].startswith("#000000")
    _, out = pzstyle._resolve(None, (), {"opacity": 0.5, "translate": (4, "50%"), "scale": 2})
    assert out == {"opacity": 0.5, "translate": (4.0, ("pct", 0.5)), "scale": 2.0}
    assert pz.Style(glass=True, glow="#fff").to_dict() == {"glass": True, "glow": "#fff"}


def test_opacity_and_animations_render_their_resting_state(tmp_path):
    class Demo(pz.App):
        size = (60, 60)
        theme = pz.themes.ONE_DARK

        def view(self):
            box = lambda **s: pz.container(None, width=60, height=20).style(background="#ff0000", **s)  # noqa: E731
            return pz.column([
                box(),
                box(opacity=0.5),
                box().animate("fade_in", delay=5000).animate("pulse", repeat="infinite"),
            ], spacing=0).style(background="#000000", width="fill", height="fill")

    out = tmp_path / "shot.png"
    pz.screenshot(Demo, out, size=(60, 60), scale=1)
    column = _png_column(out, 30)
    assert column[10][0] > 240  # opaque
    assert 110 < column[30][0] < 145  # half transparent over black
    assert column[50][0] > 240  # screenshots show where the fade in ends


def test_manual_animations_wait_for_their_trigger(tmp_path):
    class Demo(pz.App):
        size = (60, 40)
        theme = pz.themes.ONE_DARK

        def __init__(self):
            self.go = pz.Trigger()

        def view(self):
            box = lambda: pz.container(None, width=60, height=20).style(background="#ff0000")  # noqa: E731
            return pz.column([
                box().animate("fade_out", on=self.go),  # not fired: stays as it is
                box().animate("fade_out"),  # plays when it appears (screenshots show its end)
            ], spacing=0).style(background="#000000", width="fill", height="fill")

    out = tmp_path / "shot.png"
    pz.screenshot(Demo, out, size=(60, 40), scale=1)
    column = _png_column(out, 30)
    assert column[10][0] > 240 and column[30][0] < 20


def test_transforms_move_the_drawing(tmp_path):
    class Demo(pz.App):
        size = (60, 60)
        theme = pz.themes.ONE_DARK

        def view(self):
            return pz.column([
                pz.container(None, width=60, height=20).style(background="#ff0000", translate=(0, 20)),
            ]).style(background="#000000", width="fill", height="fill")

    out = tmp_path / "shot.png"
    pz.screenshot(Demo, out, size=(60, 60), scale=1)
    column = _png_column(out, 30)
    assert column[10][0] < 20 and column[30][0] > 240  # drawn 20 px lower than laid out


def _shot(tmp_path, view, size=(60, 60)):
    class Demo(pz.App):
        theme = pz.themes.ONE_DARK

        def view(self):
            return pz.container(view(), width="fill", height="fill").style(background="#000000")

    Demo.size = size
    out = tmp_path / f"shot{len(list(tmp_path.iterdir()))}.png"
    pz.screenshot(Demo, out, size=size, scale=1)
    return lambda x, y: _png_column(out, x)[y]


def _centered(child):
    return pz.container(child, width="fill", height="fill", align_x="center", align_y="center")


def test_rotation_turns_the_drawing(tmp_path):
    bar = lambda **s: _centered(pz.container(None, width=40, height=8).style(background="#ff0000", **s))  # noqa: E731
    flat = _shot(tmp_path, bar)
    assert flat(12, 30)[0] > 240 and flat(30, 12)[0] < 20
    turned = _shot(tmp_path, lambda: bar(rotate=90))
    assert turned(12, 30)[0] < 20 and turned(30, 12)[0] > 240  # now a vertical bar
    turned = _shot(tmp_path, lambda: _centered(pz.container(None, width=40, height=8).style(background="#ff0000")
                                               .transition(rotate="0.25turn")))
    assert turned(30, 12)[0] > 240  # animated rotation rests on its value


def test_blur_spreads_the_drawing(tmp_path):
    square = lambda **s: _centered(pz.container(None, width=20, height=20).style(background="#ff0000", **s))  # noqa: E731
    sharp = _shot(tmp_path, square)
    soft = _shot(tmp_path, lambda: square(blur=6))
    assert sharp(17, 30)[0] < 20 and 20 < soft(17, 30)[0] < 200  # light leaks past the edge
    assert soft(30, 30)[0] > 200 and soft(30, 30)[0] <= sharp(30, 30)[0]


def test_backdrop_blur_blurs_what_is_behind(tmp_path):
    def view(**s):
        stripes = pz.row([pz.container(None, width=30, height=60).style(background=c) for c in ("#ff0000", "#0000ff")],
                         spacing=0)
        panel = pz.container(None, width=60, height=60).style(**s)
        return pz.stack([stripes, panel])

    sharp = _shot(tmp_path, view)
    frosted = _shot(tmp_path, lambda: view(backdrop_blur=10))
    assert sharp(28, 30)[2] < 20 and sharp(31, 30)[0] < 20
    assert frosted(28, 30)[2] > 40 and frosted(31, 30)[0] > 40  # the colors mix across the edge
    assert frosted(5, 5)[0] > 200  # far from the edge it stays red


def test_bloom_lights_around_bright_parts(tmp_path):
    def view(**s):
        return _centered(pz.container(None, width=16, height=16).style(background="#ffffff", **s))

    plain = _shot(tmp_path, view)
    lit = _shot(tmp_path, lambda: view(bloom=("#00ff00", 1.0)))
    assert plain(30, 4)[1] < 10 and lit(30, 4)[1] > plain(30, 4)[1]  # light spills far out of the box
    assert lit(30, 30)[1] > 240


def test_layout_properties_resize_and_push_neighbors(tmp_path):
    def view(**t):
        box = pz.container(None, width=20, height=20).style(background="#ff0000")
        if t:
            box = box.transition(**t)
        after = pz.container(None, width=10, height=20).style(background="#00ff00")
        return pz.row([box, after], spacing=0)

    plain = _shot(tmp_path, view)
    assert plain(25, 10)[1] > 240  # the green box starts at x = 20
    wide = _shot(tmp_path, lambda: view(width=40))
    assert wide(25, 10)[0] > 240 and wide(45, 10)[1] > 240  # the red box is 40 wide and pushes it
    tall = _shot(tmp_path, lambda: view(height=40))
    assert tall(10, 35)[0] > 240


def test_padding_and_font_size_animate(tmp_path):
    def view(**t):
        inner = pz.container(None, width=10, height=10).style(background="#ff0000")
        box = pz.container(inner).style(background="#0000ff", padding=2)
        return box.transition(**t) if t else box

    plain = _shot(tmp_path, view)
    assert plain(4, 4)[0] > 240
    padded = _shot(tmp_path, lambda: view(padding=10))
    assert padded(4, 4)[2] > 240 and padded(15, 15)[0] > 240  # padding grows inside the blue box

    def text(**t):
        label = pz.text("MMMM").style(color="#ffffff", size=10)
        return pz.row([(label.transition(**t) if t else label),
                       pz.container(None, width=4, height=4).style(background="#00ff00")], spacing=0)

    def green_x(px):
        return next(x for x in range(120) if px(x, 2)[1] > 240 and px(x, 2)[0] < 20)

    small = green_x(_shot(tmp_path, text, size=(120, 40)))
    big = green_x(_shot(tmp_path, lambda: text(font_size=20), size=(120, 40)))
    assert big > small * 1.6  # the text got wider and pushed the green box


def test_presence_shows_the_current_content(tmp_path):
    class Demo(pz.App):
        size = (60, 40)
        theme = pz.themes.ONE_DARK
        page = 0

        def view(self):
            color = ("#ff0000", "#00ff00")[self.page]
            return pz.container(pz.presence(pz.container(None, width=60, height=40).style(background=color),
                                            key=self.page, id="t"))

    out = tmp_path / "shot.png"
    app = Demo()
    app.page = 1
    pz.screenshot(app, out, size=(60, 40), scale=1)
    red, green = _png_column(out, 30)[20][:2]
    assert green > 240 and red < 20


def test_window_transitions():
    class Plain(pz.Window):
        pass

    class Fading(pz.Window):
        transition = "fade"

    class Custom(pz.Window):
        transition = pz.Animation([{"opacity": 0}, {"opacity": 1}], duration=100)
        exit_transition = "zoom_out"

    assert anim.window_animations(Plain()) == [] and anim.window_animations(Plain(), True) == []
    assert anim.window_animations(Fading()) == ["fade_in"] and anim.window_animations(Fading(), True) == ["fade_out"]
    w = Custom()
    assert anim.window_animations(w, True) == ["zoom_out"]
    root = pz.text("x")
    assert "animate" in repr(anim._window_root(w, root))
    assert anim._window_exit(w) == pytest.approx(0.22)
    assert w._pyzed_closing and anim._window_exit(w) == 0.0  # already closing
    assert repr(anim._window_root(w, root)).endswith("animate(1 animation(s))")
    assert Plain().__pyzed_exit__() == 0.0
