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


def test_the_lanes_are_one_pointer_area_with_big_keys_and_snapping():
    d = Designer(None, language_servers=False)
    d.doc = Document(_form())
    d.doc.set_clip(INTRO)
    e = d.timeline
    px = e.px
    lane = lambda row: timeline.RULER + timeline.ROW * row + timeline.ROW / 2  # noqa: E731
    at = lambda time: timeline.ORIGIN + time * px  # noqa: E731
    assert e.row_at(4) == -1 and e.row_at(lane(1)) == 1 and e.row_at(lane(3)) == 3 and e.row_at(lane(9)) is None
    # a key is grabbed from a few pixels away, and the cursor says so
    e.pointer_move(at(1.0) - timeline.HIT + 2, lane(0))
    assert e.hover == ("key", "card:opacity", 1.0) and e.cursor() == "grab"
    e.pointer_press()
    assert e.dragging == ("card:opacity", 1.0) and e.cursor() == "grabbing" and d.focus == "timeline"
    e.pointer_move(at(0.6) - timeline.HIT + 2, lane(0))  # it keeps the distance it was grabbed from
    e.pointer_release()
    assert [k.time for k in e.clip.track("card:opacity").keys] == [0.0, 0.6] and e.dragging is None
    # dragging near another track's key snaps onto it
    e.pointer_move(at(1.0), lane(1))
    e.pointer_press()
    e.pointer_move(at(0.5) + timeline.SNAP - 1, lane(1))  # 0.5: the status track's key
    e.pointer_release()
    assert [k.time for k in e.clip.track("card:scale").keys] == [0.0, 0.5]
    # a press on an empty spot moves the playhead and drops the selection
    e.pointer_move(at(0.3), lane(0))
    e.pointer_press()
    e.pointer_release()
    assert e.position == pytest.approx(0.3) and e.selected is None
    # the ruler scrubs
    e.pointer_move(at(0.2), 4)
    e.pointer_press()
    e.pointer_move(at(0.8), 4)
    e.pointer_release()
    assert e.position == pytest.approx(0.8) and not e.scrubbing
    # double-click adds a key; right-click deletes it
    e.pointer_move(at(0.25), lane(0))
    e.pointer_double_click()
    assert [k.time for k in e.clip.track("card:opacity").keys] == [0.0, 0.25, 0.6]
    e.pointer_right_press()
    assert [k.time for k in e.clip.track("card:opacity").keys] == [0.0, 0.6]
    # calls drag along their lane and are removed with a right-click
    e.pointer_move(at(0.75) + 10, lane(3))
    assert e.hover == ("call", 0)
    e.pointer_press()
    e.pointer_move(at(0.4) + 10, lane(3))
    e.pointer_release()
    assert e.clip.calls[0].time == pytest.approx(0.4) and e.clip.calls[0].args == (7,)
    e.call_draft = "ready"
    e.pointer_move(at(0.9), lane(3))
    e.pointer_double_click()
    assert [c.method for c in e.clip.calls] == ["intro_done", "ready"]
    e.pointer_move(at(e.clip.calls[0].time) + 5, lane(3))
    e.pointer_right_press()
    assert [c.method for c in e.clip.calls] == ["ready"]
    d.doc.undo()
    assert len(e.clip.calls) == 2


def test_the_timeline_takes_its_keys_before_the_workspace():
    d = Designer(None, language_servers=False)
    d.doc = Document(_form())
    d.doc.set_clip(INTRO)
    d.doc.select("card")
    e = d.timeline
    d.focus_panel("animation")
    assert d.focus == "timeline"
    e.select_key("card:opacity", 1.0)
    d.on_key("right")
    assert e.selected == ("card:opacity", 1.01)
    d.on_key("shift+left")
    assert e.selected == ("card:opacity", 0.91)
    d.on_key("delete")  # the key, not the selected control
    assert [k.time for k in e.clip.track("card:opacity").keys] == [0.0] and d.doc.form.get("card") is not None
    d.on_key("end")
    assert e.position == e.clip.length == 1.01  # the key went past the end: the clip grew
    d.on_key("left")
    assert e.position == pytest.approx(1.0)
    d.on_key("home")
    assert e.position == 0.0
    d.on_key("space")
    assert e.playing
    d.on_key("space")
    assert not e.playing
