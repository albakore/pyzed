"""Timeline animations: clips, tracks, calls, libraries (.pzanim) and the AnimationPlayer."""

import pytest

import pyzed as pz
from pyzed import animation_player as ap
from test_layout import _png_column


@pytest.fixture(autouse=True)
def motion_on():
    pz.set_reduced_motion(False)
    yield
    pz.set_reduced_motion(False)


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def _player(*clips, owner=None, **options):
    player = pz.AnimationPlayer(*clips, owner=owner, **options)
    clock = Clock()
    player._clock = clock
    return player, clock


class Owner:
    def __init__(self):
        self.score = 0
        self.hud = type("Hud", (), {"hp": 1.0})()
        self.log = []

    def ding(self, *args):
        self.log.append(("ding", *args))
        return f"ding{len(self.log)}"


# -- clips and tracks ----------------------------------------------------------------------


def test_tracks_take_dicts_tuples_and_keys_and_interpolate():
    track = pz.Track("card:opacity", [(0.5, 1), (0, 0, "ease_in")])
    assert [k.time for k in track.keys] == [0, 0.5]
    assert track.target == "card" and track.property == "opacity"
    assert track.value_at(-1) == 0 and track.value_at(9) == 1
    assert track.value_at(0.25) == pytest.approx(pz.animation.ease("ease_in", 0.5))
    linear = pz.Track(":score", {0: 0, "1s": 100})
    assert linear.value_at(0.25) == pytest.approx(25)
    held = pz.Track(":score", {0: 0, 1: 100}, interpolation="discrete")
    assert held.value_at(0.99) == 0 and held.value_at(1) == 100


def test_track_values_mix_colors_and_sequences_and_hold_the_rest():
    assert pz.Track(":c", {0: "#000000", 1: "#ffffff"}).value_at(0.5).lower().startswith("#7f") or \
        pz.Track(":c", {0: "#000000", 1: "#ffffff"}).value_at(0.5).lower().startswith("#80")
    assert pz.Track(":p", {0: (0, 10), 1: (10, 20)}).value_at(0.5) == (5, 15)
    assert pz.Track(":s", {0: "idle", 1: "run"}).value_at(0.5) == "idle"


def test_invalid_tracks_explain_what_is_valid():
    with pytest.raises(ValueError, match="widget:property"):
        pz.Track("opacity", {0: 1})
    with pytest.raises(ValueError, match="animatable widget property"):
        pz.Track("card:bogus", {0: 1})
    with pytest.raises(ValueError, match="names separated by dots"):
        pz.Track(":not valid", {0: 1})
    with pytest.raises(ValueError, match="interpolation"):
        pz.Track(":x", {0: 1}, interpolation="cubic")
    with pytest.raises(ValueError):
        pz.Track("card:opacity", {0: "nope"})
    with pytest.raises(ValueError, match="loop"):
        pz.Clip("x", loop="forever")
    with pytest.raises(ValueError, match="clip name"):
        pz.Clip("a/b")
    with pytest.raises(ValueError, match="method"):
        pz.Call(0, "not a name")


def test_clip_length_defaults_to_the_last_key_or_call_and_edits_return_copies():
    clip = pz.Clip("intro", tracks=[pz.Track("card:x", {0: 0, 0.4: 10})], calls=[pz.Call(0.9, "ding")])
    assert clip.length == 0.9 and clip.targets == ("card",)
    edited = clip.with_key("card:x", 0.2, 30).with_key(":score", 0.5, 7)
    assert [k.value for k in edited.track("card:x").keys] == [0, 30, 10]
    assert edited.attributes == ("score",) and clip.track(":score") is None
    assert edited.without_key("card:x", 0.2).track("card:x").keys == clip.track("card:x").keys
    assert edited.without_track(":score").attributes == ()
    moved = clip.retarget({"card": "panel"}, name="intro2")
    assert moved.name == "intro2" and moved.targets == ("panel",)
    assert clip.values(0.2) == {"card:x": pytest.approx(5)}
    assert clip.values(0.2, "card") == {"x": pytest.approx(5)}


def test_a_clip_target_becomes_a_reusable_animation():
    clip = pz.Clip("pop", length=1, loop="pingpong",
                   tracks=[pz.Track("icon:scale", {0.5: 1.2}), pz.Track("icon:x", {0: "50%", 1: 0})])
    animation = clip.animation("icon")
    assert animation.duration == 1000 and animation.direction == "alternate" and animation.repeat == "infinite"
    assert set(animation.properties) == {"scale", "x"}
    compiled = animation.compile()
    scale = dict(compiled["tracks"])["scale"]
    assert [f[0] for f in scale] == [0, 0.5, 1]  # held before the first key and after the last
    assert dict(compiled["tracks"])["x"][0][1] == ("pct", 0.5)
    with pytest.raises(ValueError, match="no tracks"):
        clip.animation("other")


# -- libraries -------------------------------------------------------------------------------


def test_libraries_save_and_load_pzanim_files(tmp_path):
    intro = pz.Clip("intro", length=1.5, loop="loop", description="Title card",
                    tracks=[pz.Track("card:opacity", [(0, 0, (0.2, 0, 0.2, 1)), (1, 1)]),
                            pz.Track(":score", {0: 0, 1.5: 10}, interpolation="discrete", enabled=False)],
                    calls=[pz.Call(1.0, "ding", "a", 2)])
    lib = pz.AnimationLibrary([intro], name="ui")
    path = lib.save(tmp_path / "ui.pzanim")
    loaded = pz.load_animations(path)
    assert loaded.name == "ui" and loaded.names == ["intro"]
    assert loaded["intro"] == intro
    assert loaded.to_dict()["format"] == ap.FORMAT
    loaded.rename("intro", "start")
    assert "start" in loaded and "intro" not in loaded and len(loaded) == 1
    with pytest.raises(KeyError, match="no clip named"):
        loaded["missing"]
    (tmp_path / "bad.pzanim").write_text('{"format": "pyzed.form/1"}')
    with pytest.raises(ValueError, match="not a Pyzed animation library"):
        pz.load_animations(tmp_path / "bad.pzanim")
    with pytest.raises(ValueError, match="by name"):
        pz.Clip("x", calls=[pz.Call(0, print)]).to_dict()


def test_players_load_libraries_with_their_prefix(tmp_path):
    pz.AnimationLibrary([pz.Clip("idle", length=1)], name="hero").save(tmp_path / "hero.pzanim")
    player = pz.AnimationPlayer(tmp_path / "hero.pzanim", pz.Clip("intro", length=1),
                                pz.AnimationLibrary([pz.Clip("spin", length=1)]))
    assert player.names == ["hero/idle", "intro", "spin"]
    with pytest.raises(TypeError):
        pz.AnimationPlayer(42)


# -- the player ------------------------------------------------------------------------------


def test_play_pause_seek_and_resume_follow_the_clock():
    owner = Owner()
    clip = pz.Clip("count", length=2, tracks=[pz.Track(":score", {0: 0, 2: 200})])
    player, clock = _player(clip, owner=owner)
    assert player.current is None and player.position == 0
    player.play("count")
    clock.now += 0.5
    assert player.playing and player.position == pytest.approx(0.5)
    player.pause()
    clock.now += 5
    assert player.paused and player.position == pytest.approx(0.5)
    player.seek(1.5)
    assert owner.score == pytest.approx(150)
    player.speed = 2
    player.resume()
    clock.now += 0.1
    assert player.position == pytest.approx(1.7)
    player.toggle()
    assert player.paused
    player.stop()
    assert player.current == "count" and player.position == 0 and owner.score == 0
    player.stop(reset=True)
    assert player.current is None


def test_clips_finish_run_callbacks_and_play_the_queue():
    owner = Owner()
    events = []
    a = pz.Clip("a", length=1, calls=[pz.Call(0, "ding", "start"), pz.Call(1, "ding", "end")])
    b = pz.Clip("b", length=1, tracks=[pz.Track(":score", {0: 0, 1: 10})])
    player, clock = _player(a, b, owner=owner, on_started=events.append,
                            on_finished=lambda name: events.append(f"done {name}"))
    player.play("a")
    player.queue("b")
    assert player.queued == ["b"]
    clock.now += 1.25
    results = player._process()
    assert owner.log == [("ding", "start"), ("ding", "end")]
    assert results == ["ding1", "ding2"]
    assert events == ["a", "done a", "b"]
    assert player.current == "b" and player.playing
    clock.now += 2
    player._process()
    assert player.finished and not player.playing and owner.score == 10
    assert events[-1] == "done b"
    player.play()  # a finished clip plays again from the start
    assert player.position == pytest.approx(0) and events[-1] == "b"


def test_playing_the_same_clip_keeps_going_unless_restarted():
    player, clock = _player(pz.Clip("a", length=4))
    player.play("a")
    clock.now += 1
    player.play("a")
    assert player.position == pytest.approx(1)
    player.play("a", restart=True)
    assert player.position == pytest.approx(0)


def test_loops_pingpong_and_backwards_map_time():
    owner = Owner()
    loop = pz.Clip("loop", length=1, loop="loop", calls=[pz.Call(0.5, "ding")])
    ping = pz.Clip("ping", length=1, loop="pingpong")
    player, clock = _player(loop, ping, owner=owner)
    player.play("loop")
    clock.now += 2.75
    assert player.position == pytest.approx(0.75)
    player._process()
    assert len(owner.log) == 3  # crossed 0.5 three times
    player.play("ping")
    clock.now += 1.25
    assert player.position == pytest.approx(0.75)
    player.play_backwards("loop")
    assert player.position == pytest.approx(1)
    clock.now += 0.25
    assert player.position == pytest.approx(0.75)


def test_backwards_finishes_at_the_start_and_calls_run_in_reverse():
    owner = Owner()
    clip = pz.Clip("a", length=1, calls=[pz.Call(0.2, "ding", 1), pz.Call(0.8, "ding", 2)])
    player, clock = _player(clip, owner=owner)
    player.play_backwards("a")
    clock.now += 2
    player._process()
    assert [entry[1] for entry in owner.log] == [2, 1]
    assert player.finished and player.position == pytest.approx(0)


def test_advance_moves_time_like_a_frame():
    owner = Owner()
    player, _ = _player(pz.Clip("hp", length=1, tracks=[pz.Track(":hud.hp", {0: 1.0, 1: 0.0})]), owner=owner)
    player.play("hp")
    player.advance(0.25)
    assert owner.hud.hp == pytest.approx(0.75)
    assert player.value(":hud.hp") == pytest.approx(0.75)
    assert player.value(":missing") is None


def test_calls_need_an_owner_or_a_callable():
    seen = []
    player, clock = _player(pz.Clip("a", length=1, calls=[pz.Call(0.5, seen.append, "hi")]))
    player.play("a")
    player.advance(1)
    assert seen == ["hi"]
    named, _ = _player(pz.Clip("a", length=1, calls=[pz.Call(0.5, "ding")]))
    named.play("a")
    with pytest.raises(RuntimeError, match="no owner"):
        named.advance(1)


def test_widget_targets_compile_to_native_animations():
    clip = pz.Clip("intro", length=2, loop="pingpong", tracks=[pz.Track("card:opacity", {0: 0, 1: 1})])
    player, clock = _player(clip)
    assert player["card"]._pyzed_compiled() == []  # nothing playing
    player.play("intro")
    first = player["card"]._pyzed_compiled()
    assert len(first) == 1 and first[0]["direction"] == "alternate" and first[0]["duration"] == 2000
    assert first[0]["paused"] is False and first[0]["seek"] == 0
    assert player["other"]._pyzed_compiled() == []
    clock.now += 0.5
    assert player["card"]._pyzed_compiled() is first  # unchanged until the player changes
    player.pause()
    paused = player["card"]._pyzed_compiled()[0]
    assert paused["paused"] is True and paused["seek"] == pytest.approx(500)
    assert paused["key"] != first[0]["key"]
    widget = pz.text("hi").animate(player["card"], player["other"])
    assert "1 animation" in repr(widget)


def test_subscriptions_wake_for_calls_and_tick_for_attribute_tracks():
    owner = Owner()
    timed = pz.Clip("timed", length=2, calls=[pz.Call(0.5, "ding")])
    looping = pz.Clip("looping", length=1, loop="loop")
    stateful = pz.Clip("stateful", length=1, tracks=[pz.Track(":score", {0: 0, 1: 1})])
    player, clock = _player(timed, looping, stateful, owner=owner)
    assert player.subscriptions() == []
    player.play("timed")
    assert player._next_wake() == pytest.approx(0.5)
    assert len(player.subscriptions()) == 1
    clock.now += 0.6
    assert player._next_wake() == pytest.approx(1.4)
    player.play("looping")
    assert player._next_wake() is None and player.subscriptions() == []
    player.play("stateful")
    assert len(player.subscriptions()) == 1


def test_players_on_the_app_find_their_owner():
    class Demo(pz.App):
        def __init__(self):
            self.score = 0
            self.player = pz.AnimationPlayer(pz.Clip("a", length=1, tracks=[pz.Track(":score", {0: 5, 1: 9})]),
                                             autoplay="a")

    app = Demo()
    assert app.player.owner is None
    subs = ap._player_subscriptions(app)
    assert app.player.owner is app and app.score == pytest.approx(5, abs=0.1) and len(subs) == 1


def test_a_paused_player_renders_its_frame(tmp_path):
    clip = pz.Clip("fade", length=1, tracks=[pz.Track("box:opacity", {0: 0, 1: 1})])

    class Demo(pz.App):
        size = (60, 40)
        theme = pz.themes.ONE_DARK

        def __init__(self):
            self.player = pz.AnimationPlayer(clip, autoplay="fade")
            self.player.pause()
            self.player.seek(0.5)

        def view(self):
            box = lambda: pz.container(None, width=60, height=20).style(background="#ff0000")  # noqa: E731
            return pz.column([box(), box().animate(self.player["box"])]).style(background="#000000", width="fill",
                                                                            height="fill")

    out = tmp_path / "shot.png"
    pz.screenshot(Demo, out, size=(60, 40), scale=1)
    column = _png_column(out, 30)
    assert column[10][0] > 240
    assert 110 < column[30][0] < 145  # half way through the fade
