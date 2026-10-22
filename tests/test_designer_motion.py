"""The designer's Effects and Animation sections: editing, saving, previewing and running animations."""

from pyzed.designer import components, motion, motion_panel, new, panels
from pyzed.designer.app import Designer
from pyzed.designer.model import Control, Form
from pyzed.designer.runtime import FormApp


def sidebar_app(tmp_path):
    app = Designer(new.new_form(tmp_path / "shell", template="sidebar"), language_servers=False)
    app.window_size = (1440, 900)
    return app


def test_entries_describe_their_timing():
    entry = {"preset": "fade_in_up"}
    assert motion.timing(entry)["duration"] == 280 and motion.timing(entry)["on"] == "mount"
    assert motion.summary(entry) == "Fade in up · 280 ms"
    loop = {"preset": "pulse", "on": "hover", "duration": 900, "delay": 100, "repeat": "infinite"}
    assert motion.summary(loop) == "Pulse · 900 ms · +100 ms · ∞"
    assert motion.options(loop) == {"on": "hover", "duration": 900, "delay": 100, "repeat": "infinite"}
    assert motion.preset_of({"preset": "nope"}) is None
    assert motion.presets_for("hover")[0] in ("lift", "grow") and len(motion.presets_for("mount")) > 40
    assert motion.new_entry("press") == {"preset": "shrink", "on": "press"}
    assert motion.repeat_text(float("inf")) == "infinite" and motion.repeat_text(2.0) == "2"


def test_effect_values():
    assert motion.glow_parts(["#ff0000", 20], 12) == ("#ff0000", 20.0)
    assert motion.glow_parts("accent", 12) == ("accent", 12)
    assert motion.glow_parts(None, 0.6) == ("", 0.6)
    assert motion.glow_value("", 4) is None and motion.glow_value("#fff", 4.0) == ["#fff", 4]
    assert motion.glass_value(False, "#fff", 0.1) is None and motion.glass_value(True, "#ffffff", 0.08) is True
    assert motion.glass_value(True, "#000", 0.3) == {"tint": "#000", "strength": 0.3}
    assert motion.glass_parts({"tint": "#000", "strength": 0.3}) == (True, "#000", 0.3)
    assert motion.moves([], {"glow": ["#fff", 4]}) and not motion.moves([], {"radius": 4})


def test_apply_skips_invalid_entries_and_previews_as_mount():
    from pyzed import _core

    widget = _core.text("x")
    out = motion.apply(widget, [{"preset": "lift"}, {"preset": "nope"}, {"preset": "fade_in", "easing": "bad"}])
    assert repr(out).endswith("animate(1 animation(s))")
    assert motion.apply(widget, []) is widget
    assert "animate" in repr(motion.apply(widget, [{"preset": "lift"}], preview=3))


def test_animation_section_edits_saves_and_undoes(tmp_path):
    app = sidebar_app(tmp_path)
    app.doc.select("nav1")
    app._selection_changed()
    app.add_animation("nav1", "hover")
    assert app.doc.form["nav1"].animations == [{"preset": "lift", "on": "hover"}]
    assert app.motion_open == ("nav1", 0) and "nav1" in app.motion_preview
    app.set_animation("nav1", 0, "duration", 250.0)
    app.set_animation("nav1", 0, "repeat", "2")
    assert app.doc.form["nav1"].animations[0] == {"preset": "lift", "on": "hover", "duration": 250, "repeat": "2"}
    app.set_animation("nav1", 0, "preset", "grow")  # a new preset brings its own timing
    assert app.doc.form["nav1"].animations[0] == {"preset": "grow", "on": "hover"}
    app.set_animation("nav1", 0, "duration", "")
    app.add_animation("nav1")
    rows = panels.control_properties(app, app.theme_obj)
    titles = [r.title for r in rows if isinstance(r, panels.Group)]
    assert titles.index("Style") < titles.index("Effects") < titles.index("Animation")
    assert app.view() is not None
    app.open_animation("nav1", 1)
    assert app.motion_open is None
    app.set_style_value("nav1", "glow", motion.glow_value("accent", 16))
    app.set_style_value("nav1", "glass", True)
    app.toggle_color_picker("nav1", "glow")
    assert app.view() is not None
    app.save()
    saved = Form.from_json(app.doc.path.read_text())
    assert [a["preset"] for a in saved["nav1"].animations] == ["grow", "fade_in_up"]
    assert saved["nav1"].style["glow"] == ["accent", 16] and saved["nav1"].style["glass"] is True
    assert "animations" not in saved["nav2"].to_dict()
    app.remove_animation("nav1", 1)
    app.remove_animation("nav1", 0)
    assert app.doc.form["nav1"].animations == [] and "nav1" not in app.motion_preview
    app.undo()
    assert len(app.doc.form["nav1"].animations) == 1


def test_canvas_plays_only_previews_and_the_running_form_plays_all():
    form = Form()
    form.add(Control(name="b", type="button", animations=[{"preset": "fade_in"}]))
    ctx = components.RenderContext()
    still = components.animated(_text(), form["b"], ctx)
    assert "animate" not in repr(still)
    ctx.preview = {"b": 1}
    assert "animate" in repr(components.animated(_text(), form["b"], ctx))
    app = FormApp(form)
    assert app.view() is not None
    assert "animate" in repr(components.animated(_text(), form["b"], app.runtime.ctx))
    assert Control.from_dict(form["b"].to_dict()).animations == [{"preset": "fade_in"}]


class _Recorder:
    """Stands in for a widget: records what ``motion.apply`` animates it with."""

    def __init__(self):
        self.calls = []

    def animate(self, animation, **options):
        self.calls.append((getattr(animation, "description", animation), options))
        return self


def test_code_plays_a_controls_animations():
    entries = [{"preset": "fade_in"}, {"preset": "pulse", "on": "manual"}, {"preset": "lift", "on": "hover"}]
    still = motion.apply(_Recorder(), entries).calls
    assert [o.get("key") for _, o in still] == [None, None, None]
    played = motion.Played()
    played.play()
    calls = motion.apply(_Recorder(), entries, played=played).calls
    assert [o.get("key") for _, o in calls] == [1, 1, None]  # appear and from-code entries replay; hover doesn't
    played.play("shake", repeat=2)
    calls = motion.apply(_Recorder(), entries, played=played).calls
    assert calls[-1] == ("shake", {"repeat": 2, "on": "mount", "key": 2})
    played.stop()
    calls = motion.apply(_Recorder(), entries, played=played).calls
    assert len(calls) == 2 and all(o.get("on") != "manual" for _, o in calls)
    assert motion.new_entry("manual") == {"preset": "pulse", "on": "manual"}
    assert motion.TRIGGER_LABELS["manual"] == "When played from code"


def test_handlers_play_animations_on_controls():
    import pytest

    form = Form()
    form.add(Control(name="heading", type="label", animations=[{"preset": "pulse", "on": "manual"}]))
    form.add(Control(name="plain", type="label"))
    app = FormApp(form)
    proxy = app.runtime.proxy
    assert "animate" in repr(components.animated(_text(), form["heading"], app.runtime.ctx))
    assert repr(components.animated(_text(), form["plain"], app.runtime.ctx)) == repr(_text())
    proxy.heading.play_animation()
    proxy.plain.play_animation("shake", duration=300)
    proxy.plain.play_animation(scale=1.1)
    played = app.runtime.played
    assert played["heading"].count == 1 and played["plain"].count == 2
    assert "animate" in repr(components.animated(_text(), app.runtime.form["plain"], app.runtime.ctx))
    with pytest.raises(KeyError, match="no animation named 'nope'"):
        proxy.plain.play_animation("nope")
    with pytest.raises(TypeError, match="unknown animate"):
        proxy.plain.play_animation("shake", speed=2)
    proxy.plain.stop_animation()
    assert played["plain"].stopped and played["plain"].extra == []
    assert app.view() is not None


def test_the_open_row_says_how_its_animation_starts(tmp_path):
    app = sidebar_app(tmp_path)
    app.add_animation("nav1", "manual")
    assert app.doc.form["nav1"].animations == [{"preset": "pulse", "on": "manual"}]
    assert motion_panel.code_line("nav1") == "form.nav1.play_animation()"
    assert app.view() is not None
    for trigger in motion_panel.TRIGGER_HINTS:
        app.set_animation("nav1", 0, "on", trigger)
        assert motion_panel.animation_rows(app, app.doc.form["nav1"], app.theme_obj)


def test_effect_rows_show_sub_fields_only_when_on(tmp_path):
    app = sidebar_app(tmp_path)
    control = app.doc.form["nav1"]
    plain = motion_panel.effect_rows(app, control, app.theme_obj)
    control.style.update(glow=["#ff0000", 8], bloom="accent", glass={"tint": "#000", "strength": 0.2})
    rich = motion_panel.effect_rows(app, control, app.theme_obj)
    assert len(rich) == len(plain) + 4  # glow size, bloom intensity, glass tint and strength


def _text():
    from pyzed import _core

    return _core.text("x")
