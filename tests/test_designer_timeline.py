"""Timeline animations in Pyzed Design: clips saved in the .pzform, the Animation panel and the running form."""

import pytest

import pyzed as pz
from pyzed.designer import timeline
from pyzed.designer.app import Designer
from pyzed.designer.document import Document
from pyzed.designer.model import Control, Form
from pyzed.designer.runtime import FormRuntime


@pytest.fixture(autouse=True)
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("PYZED_CONFIG_DIR", str(tmp_path / "config"))


def _form():
    form = Form(name="Login")
    form.add(Control("card", "panel", 10, 10, 300, 200))
    form.add(Control("email", "input", 20, 20, 200, 28, parent="card"))
    form.add(Control("status", "label", 20, 60, 200, 24, props={"text": "Hi"}))
    return form


INTRO = pz.Clip("intro", length=1, tracks=[
    pz.Track("card:opacity", {0: 0, 1: 1}),
    pz.Track("card:scale", {0: 0.9, 1: 1}),
    pz.Track(":status.text", {0: "Loading", 0.5: "Ready"}),
], calls=[pz.Call(0.75, "intro_done", 7)])


def test_forms_save_their_clips_and_autoplay():
    form = _form()
    assert "animations" not in form.to_dict()["form"] and "autoplay" not in form.to_dict()["form"]
    timeline.put(form, INTRO)
    form.autoplay = "intro"
    loaded = Form.from_json(form.to_json())
    assert timeline.clips(loaded) == [INTRO] and loaded.autoplay == "intro"
    timeline.put(loaded, pz.Clip("intro2", length=2), old="intro")
    assert [c.name for c in timeline.clips(loaded)] == ["intro2"] and loaded.autoplay == "intro2"
    timeline.remove(loaded, "intro2")
    assert loaded.animations == [] and loaded.autoplay == ""
    loaded.animations.append({"name": ""})  # unreadable entries are skipped
    assert timeline.clips(loaded) == []
    assert timeline.unique_name(form, "intro") == "intro2"


def test_renaming_and_deleting_controls_update_the_tracks():
    doc = Document(_form())
    doc.set_clip(INTRO)
    doc.rename("status", "message")
    clip = timeline.get(doc.form, "intro")
    assert clip.track(":message.text") is not None and clip.track(":status.text") is None
    doc.rename("card", "box")
    assert timeline.get(doc.form, "intro").targets == ("box",)
    doc.select("box")
    doc.delete()
    assert [t.path for t in timeline.get(doc.form, "intro").tracks] == [":message.text"]
    doc.undo()
    assert timeline.get(doc.form, "intro").targets == ("box",)
    doc.set_autoplay("intro")
    doc.remove_clip("intro")
    assert doc.form.autoplay == "" and doc.form.animations == []
    doc.undo()
    assert doc.form.autoplay == "intro"


def test_track_paths_labels_and_starting_values():
    form = _form()
    paths = dict(timeline.track_paths(form["status"]))
    assert "status:opacity" in paths and ":status.text" in paths
    assert timeline.label("card:border_color") == "card · border color"
    assert timeline.label(":status.text") == "status.text"
    assert timeline.control_of(":status.text") == "status"
    assert timeline.current_value(form, "card:opacity") == 1.0
    assert timeline.current_value(form, "card:width") == 300
    assert timeline.current_value(form, ":status.text") == "Hi"
    assert timeline.current_value(form, "card:background") == "#ffffff"
    assert timeline.overrides(INTRO, 0.6) == {"status": {"text": "Ready"}}


def test_the_animation_panel_edits_clips_with_undo():
    d = Designer(None, language_servers=False)
    d.doc = Document(_form())
    e = d.timeline
    assert e.clip is None
    e.add_track("card:opacity")  # makes a clip first
    clip = e.clip
    assert clip.name == "animation" and clip.track("card:opacity").keys[0].value == 1.0
    e.select_key("card:opacity", 0.0)
    e.set_key_value(0.0)
    e.seek(0.5)
    e.add_key("card:opacity")
    assert [k.time for k in e.clip.track("card:opacity").keys] == [0.0, 0.5]
    e.set_key_value(1.0)
    e.set_key_easing("ease_out")
    assert e.key().easing == "ease_out"
    e.set_key_easing("track")
    assert e.key().easing is None
    e.set_key_time(2.0)  # past the end: the clip grows
    assert e.clip.length == 2.0 and e.selected == ("card:opacity", 2.0)
    e.start_drag("card:opacity", 2.0)
    e.drag_to(0.8 * e.px)
    e.end_drag()
    assert [k.time for k in e.clip.track("card:opacity").keys] == [0.0, 0.8]
    e.delete_key()
    assert len(e.clip.track("card:opacity").keys) == 1
    e.set_interpolation("card:opacity", "discrete")
    e.toggle_track("card:opacity")
    track = e.clip.track("card:opacity")
    assert track.interpolation == "discrete" and not track.enabled
    e.set_loop("pingpong")
    e.set_length(3)
    e.toggle_autoplay()
    e.edit_name("fade in")
    e.submit_name()
    assert e.clip.name == "fade_in" and d.doc.form.autoplay == "fade_in" and e.clip.loop == "pingpong"
    e.edit_call("ready")
    e.submit_call()
    assert [c.method for c in e.clip.calls] == ["ready"]
    e.remove_call(0)
    e.duplicate_clip()
    assert [c.name for c in e.clips] == ["fade_in", "fade_in2"]
    e.delete_clip()
    e.remove_track("card:opacity")
    assert e.clip.tracks == ()
    for _ in range(2):
        d.doc.undo()
    assert [c.name for c in e.clips] == ["fade_in", "fade_in2"]


def test_the_canvas_follows_the_playhead_and_containers_move_their_controls():
    d = Designer(None, language_servers=False)
    d.doc = Document(_form())
    e = d.timeline
    d.doc.set_clip(INTRO)
    e.seek(0.4)
    assert e.player().position == pytest.approx(0.4) and not e.playing
    assert len(e.targets("card")) == 1
    inherited = e.targets("email")  # inside the card: follows its opacity, not its scale
    assert len(inherited) == 1 and dict(inherited[0]._pyzed_compiled()[0]["tracks"]).keys() == {"opacity"}
    assert e.targets("status") == []
    assert e.canvas_overrides() == {"status": {"text": "Loading"}}
    e.play()
    assert e.playing and len(e.subscriptions()) == 1
    e.pause()
    assert not e.playing and e.subscriptions() == []
    e.stop()
    assert e.position == 0
    e.scrub_move(0.25 * e.px)
    e.scrub_press()
    e.scrub_move(0.5 * e.px)
    e.scrub_release()
    assert e.position == pytest.approx(0.5)
    assert e.ticks(400)[0] == (0.0, "0s")


def test_the_panel_renders(tmp_path):
    d = Designer(None, language_servers=False)
    d.doc = Document(_form())
    d.doc.set_clip(INTRO)
    d.timeline.show()
    d.timeline.select_key("card:opacity", 1.0)
    d.toasts.clear()
    d.screenshot(tmp_path / "panel.png", size=(1280, 800), scale=1)
    assert (tmp_path / "panel.png").stat().st_size > 0


def test_a_running_form_plays_its_clips_and_runs_calls():
    form = _form()
    timeline.put(form, INTRO)
    form.autoplay = "intro"
    calls = []

    def intro_done(f, event):
        calls.append(event.value)

    window = pz.Window()
    runtime = FormRuntime(form, {"intro_done": intro_done}, window=window)
    player = runtime.proxy.animations
    assert player is runtime.player and player.current == "intro" and player.playing
    player.pause()
    player.seek(0.6)
    assert runtime.form["status"].props["text"] == "Ready"
    player.advance(0.3)
    assert calls == [7]
    assert len(timeline.targets(player, runtime.form, "email")) == 1
    runtime.view()  # draws with the animations attached
    player.pause()
    reloaded = timeline.reload_player(player, runtime.form)
    assert reloaded.current == "intro" and reloaded.position == pytest.approx(player.position)
