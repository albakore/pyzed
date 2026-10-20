"""Audio components (pyzed.ui.audio), the webcam view and the modular rack."""

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import pyzed as pz
from pyzed import camera, ui
from pyzed.ui import audio as au
from pyzed.ui import rack

sys.path.insert(0, str(Path(__file__).parent))
from fake_engine import CATALOG, FakeEngine  # noqa: E402


def event(**kw):
    base = dict(x=0.0, y=0.0, dx=0.0, dy=0.0, width=0.0, height=0.0, shift=False)
    base.update(kw)
    return SimpleNamespace(**base)


def collect():
    got = []
    return got, (lambda e: got.append(e.value))


# -- helpers ----------------------------------------------------------------------------------------
def test_format_and_note_names():
    assert au.format_value(1250, "Hz") == "1.2 kHz"
    assert au.format_value(440, "Hz") == "440 Hz"
    assert au.format_value(0.75, "%") == "75%"
    assert au.format_value(-6, "dB", 1) == "-6.0 dB"
    assert au.format_value(1500, "ms") == "1.50 s"
    assert au.note_name(60) == "C4" and au.note_name(69) == "A4" and au.note_name(61) == "C#4"
    assert au.KEYBOARD["a"] == 0 and au.KEYBOARD["k"] == 12


def test_bands_regroup_log_spectra_and_fft_bins():
    assert au.bands([-60.0, -10.0, -50.0, -40.0], 2) == [-10.0, -40.0]  # already log-spaced (the engine's)
    assert len(au.bands([-60.0, -10.0], 5)) == 5
    mags = [-100.0] * 512
    mags[5] = -10.0  # a low tone in raw FFT bins
    out = au.bands(mags, 32, spacing="linear", sample_rate=48000)
    assert len(out) == 32 and max(out) == -10.0
    assert out.index(-10.0) < 12  # low frequencies get many bands
    assert au.bands([], 8) == [-120.0] * 8
    assert au.bands(["-3", "x", "-6"], 1) == [-3.0]  # text from the designer


# -- controls ---------------------------------------------------------------------------------------
def test_knob_drags_scrolls_resets_and_keeps_its_value():
    got, on_change = collect()
    k = au.Knob.create(value=0.5, on_change=on_change)
    k._start()
    k._move(-(-40) / k.travel, False)  # dragged 40 px up
    assert k.shown() == pytest.approx(0.7) and got[-1] == pytest.approx(0.7)
    k._move(1.0, True)  # fine: a tenth as much
    assert k.shown() == pytest.approx(0.8)
    k._end()
    k.reset()
    assert k.shown() == 0.0  # no default: back to min
    k._wheel(event(dy=-1))
    assert k.shown() == pytest.approx(0.02)
    k.value = 0.25  # the parent passes a new value: it wins
    assert k.shown() == 0.25


def test_knob_curves_steps_options_and_shapes():
    k = au.Knob.create(value=1000, min=20, max=20000, curve="log", unit="Hz")
    assert k.unit_value() == pytest.approx(math.log(50) / math.log(1000))
    assert k.display() == "1.0 kHz"
    k.put_unit(1.0)
    assert k.shown() == 20000
    s = au.Knob.create(value=1, options=["Sine", "Saw", "Square"])
    assert (s.min, s.max, s.step) == (0, 2, 1) and s.display() == "Saw"
    s.put(1.6)
    assert s.shown() == 2 and s.display() == "Square"
    for variant in ("arc", "fl", "vintage", "rack", "minimal"):
        shapes = au.Knob.create(value=0.3, variant=variant, bipolar=True, min=-1, max=1).shapes()
        assert shapes and all(isinstance(x, dict) for x in shapes)


def test_fader_jumps_on_the_track_and_drags():
    got, on_change = collect()
    f = au.Fader.create(value=0.5, length=126, on_change=on_change)  # travel 100
    f._press(event(y=13 + 10))  # near the top
    assert f.shown() == pytest.approx(0.9)
    f._move(-(-10) / 100, False)
    assert f.shown() == pytest.approx(1.0)
    h = au.Fader.create(value=0.0, vertical=False, length=126, level=0.5, variant="fl")
    h._press(event(x=13 + 25))
    assert h.shown() == pytest.approx(0.25)
    assert h.shapes()


def test_pad_velocity_and_led_button_toggle():
    got, on_press = collect()
    p = au.Pad.create(text="KICK", on_press=on_press)
    p._press(event(y=72, height=72))
    assert got == [127] and p.down
    p._release()
    assert not p.down
    toggles, on_toggle = collect()
    b = au.LedButton.create(text="MUTE", on_toggle=on_toggle)
    b._press()
    assert toggles == [True] and not b.is_on()  # controlled: lit when the parent passes on=True
    b.on = True
    assert b.is_on()
    b._release()
    b._press()
    assert toggles == [True, False]
    free = au.LedButton.create(text="SOLO")  # uncontrolled: it remembers by itself
    free._press()
    assert free.is_on()
    m = au.LedButton.create(momentary=True)
    m._press()
    assert m.is_on()
    m._release()
    assert not m.is_on()


def test_step_sequencer_paints_steps():
    got, on_change = collect()
    s = au.StepSequencer.create(pattern=["x...x...", "........"], on_change=on_change, cell=20)
    assert s.rows()[0][:5] == [True, False, False, False, True]
    s._put(25, 5, True)  # row 0, step 1: switches it on and paints "on"
    s._put(45, 5, False)  # dragging over step 2
    assert got[-1][0][:4] == [True, True, True, False]
    assert s.shapes()


def test_piano_hit_testing_and_glissando():
    on, on_note_on = collect()
    off, on_note_off = collect()
    p = au.Piano.create(start=60, octaves=1, on_note_on=on_note_on, on_note_off=on_note_off)
    assert p.notes()[0] == 60 and p.notes()[-1] == 72
    assert p.note_at(p.key_width * 0.5, 100)[0] == 60  # low on the first white key: C
    assert p.note_at(p.key_width * 0.95, 10)[0] == 61  # on the black key: C#
    p._down(event(x=5, y=100))
    p._drag(event(x=p.key_width + 5, y=100))
    p._up()
    assert [n.note for n in on] == [60, 62] and off == [60, 62]
    assert on[0].velocity > 100
    assert p.shapes()


# -- meters and displays ----------------------------------------------------------------------------
def test_vu_meter_scales_and_holds_peaks(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(au, "_now", lambda: clock[0])
    m = au.VuMeter.create(level=[1.0, 0.001])
    assert m.position(1.0) == 1.0 and m.position(0.001) == pytest.approx(0.0)
    m.shapes()
    m.level = [0.0, 0.0]
    clock[0] = 0.5
    m.shapes()
    assert m.peaks[0][0] == 1.0  # held
    clock[0] = 3.0
    m.shapes()
    assert m.peaks[0][0] < 1.0  # falling
    for variant in ("led", "bar", "analog"):
        assert au.VuMeter.create(level="0.5", variant=variant).shapes()


def test_spectrum_falls_off_over_time(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(au, "_now", lambda: clock[0])
    s = au.Spectrum.create(magnitudes=[0.0] * 64, bands=8, falloff=90, min_db=-90)
    assert s.values() == [1.0] * 8
    s.magnitudes = [-90.0] * 64
    clock[0] = 0.1  # 9 dB of 90
    assert s.values()[0] == pytest.approx(0.9)
    for variant in ("bars", "blocks", "line", "filled", "mirror", "radial"):
        assert au.Spectrum.create(magnitudes=[-20.0] * 64, variant=variant, labels=True).shapes()


def test_spectrogram_waveform_and_scope():
    g = au.Spectrogram.create(magnitudes=[-10.0] * 32, history=4, bands=4)
    for _ in range(6):
        g.magnitudes = list(g.magnitudes)  # a new list each frame adds a column
        g.shapes()
    assert len(g.columns) == 4
    sine = [math.sin(i / 5) for i in range(4000)]
    for variant in ("mirror", "filled", "line", "bars", "dots"):
        assert au.Waveform.create(samples=sine, variant=variant, playhead=0.3, selection=(0.1, 0.2)).shapes()
    assert len(au._columns(sine, 10)) == 10
    triggered = au._trigger([-0.5, -0.1, 0.2, 0.5, 0.1, -0.2], 3)
    assert triggered == [0.2, 0.5, 0.1]
    for xy in (False, True):
        assert au.Scope.create(traces=[sine[:600], sine[100:700]], xy=xy, persistence=2).shapes()


def test_components_render_in_an_app(tmp_path):
    sig = [math.sin(i / 7) for i in range(512)]

    class Demo(pz.App):
        def view(self):
            return pz.column([
                pz.row([au.Knob(value=0.4, caption="Cutoff"), au.Fader(value=0.6, level=0.5), au.VuMeter(level=0.5),
                        au.Pad(text="A"), au.LedButton(text="REC", on=True)]),
                au.Piano(pressed=[60]),
                au.StepSequencer(pattern=[[True, False] * 8], current=2),
                au.Waveform(samples=sig), au.Scope(traces=[sig]), au.Spectrum(magnitudes=[-30.0] * 128),
                au.Spectrogram(magnitudes=[-30.0] * 128),
            ])

    pz.screenshot(Demo, tmp_path / "audio.png", size=(800, 900), scale=1)
    assert (tmp_path / "audio.png").stat().st_size > 1000


def test_audio_components_join_the_designer_toolbox():
    from pyzed.designer import components as designer

    names = {c.type for c in designer.all_components() if c.category == "Audio"}
    assert {"knob", "fader", "pad", "led_button", "piano", "vu_meter", "spectrum", "waveform"} <= names


# -- camera -----------------------------------------------------------------------------------------
def test_camera_test_backend_snapshot_and_sharing(tmp_path):
    frame = camera.test_pattern(64, 48, 3)
    assert len(frame) == 64 * 48 * 4
    png = camera.png(2, 1, bytes([255, 0, 0, 255, 0, 255, 0, 255]))
    assert png.startswith(b"\x89PNG")
    cam = camera.open_camera("x", width=32, height=24, fps=60, backend="test")
    assert camera.open_camera("x", width=32, height=24, fps=60, backend="test") is cam
    got = cam.read(timeout=2)
    assert got is not None and (got.width, got.height) == (32, 24)
    assert cam.snapshot(tmp_path / "snap.png") and (tmp_path / "snap.png").read_bytes().startswith(b"\x89PNG")
    camera.release_camera(cam)
    assert cam.running
    camera.release_camera(cam)
    assert not cam.running
    with pytest.raises(ValueError):
        camera.Camera(backend="nope")


def test_webcam_renders_a_camera(tmp_path):
    cam = camera.Camera(backend="test", width=64, height=48)
    cam.read(timeout=2)

    class View(pz.App):
        def view(self):
            return ui.camera.Webcam(camera=cam, width=160, height=120)

    pz.screenshot(View, tmp_path / "cam.png", size=(200, 160), scale=1)
    cam.stop()
    assert (tmp_path / "cam.png").exists()


# -- rack -------------------------------------------------------------------------------------------
def patch():
    e = FakeEngine()
    for kind in ("oscillator", "filter", "audio_out"):
        e.add(kind)
    return e


def test_panels_are_laid_out_from_the_description():
    osc = next(m for m in CATALOG if m.kind == "oscillator")
    p = rack.panel_layout(osc)
    assert p.width == p.hp * rack.HP and p.hp >= 4
    assert set(p.knobs) == {"frequency", "fine", "pw", "fm_amount"}
    assert set(p.inputs) == {"pitch", "fm", "pwm", "sync"} and set(p.outputs) == {"sine", "triangle", "saw", "square"}
    assert min(y for _x, y in p.outputs.values()) > max(y for _x, y in p.inputs.values())  # outputs at the bottom
    for x, y in [*p.inputs.values(), *p.outputs.values(), *p.knobs.values()]:
        assert 0 <= x <= p.width and 0 <= y <= rack.MODULE_HEIGHT
    scope = rack.panel_layout(next(m for m in CATALOG if m.kind == "scope"))
    assert scope.display is not None and scope.display_kind == "scope"


def test_place_finds_room():
    layout = {}
    rack.place(layout, "a", 10)
    rack.place(layout, "b", 6, widths={"a": 10})
    assert layout == {"a": {"row": 0, "x": 0}, "b": {"row": 0, "x": 10}}
    rack.place(layout, "c", 4, row=0, x=3, widths={"a": 10, "b": 6})  # in the way: moved past them
    assert layout["c"] == {"row": 0, "x": 16}


def test_cable_path_sags_and_drops():
    c0, c1 = rack.cable_path((0, 0), (100, 0), tension=0.5)
    assert c0[1] > 0 and c1[1] > 0
    loose = rack.cable_path((0, 0), (100, 0), tension=0.0)[0][1]
    tight = rack.cable_path((0, 0), (100, 0), tension=1.0)[0][1]
    assert loose > tight
    assert rack._drop(0) == 0 and rack._drop(5) == 1 and max(rack._drop(t / 50) for t in range(100)) > 1  # overshoots


def test_rack_patches_moves_and_removes():
    e = patch()
    changes, on_change = collect()
    r = rack.Rack.create(engine=e, catalog=CATALOG, on_change=on_change)
    r._arrange()
    assert set(r.layout) == {"oscillator1", "filter1", "audio_out1"}
    # drag a cable from the oscillator's saw output onto the filter's input
    saw = r.jack_at("oscillator1", "saw", True)
    target = r.jack_at("filter1", "in", False)
    r._wire_start("oscillator1", "saw", True, event(x=11, y=11))
    r._wire_move("oscillator1", "saw", True, event(x=11 + target[0] - saw[0], y=11 + target[1] - saw[1]))
    r._wire_end()
    assert e.cables == [("oscillator1", "saw", "filter1", "in")] and changes[-1] == "connect"
    # picking up the patched input moves its cable to another input
    other = r.jack_at("audio_out1", "left", False)
    r._wire_start("filter1", "in", False, event(x=11, y=11))
    assert e.cables == [] and r.wire["from"] == ("oscillator1", "saw", True)
    r._wire_move("filter1", "in", False, event(x=11 + other[0] - target[0], y=11 + other[1] - target[1]))
    r._wire_end()
    assert e.cables == [("oscillator1", "saw", "audio_out1", "left")]
    # dropped nowhere: nothing changes
    r._wire_start("oscillator1", "sine", True, event(x=11, y=11))
    r._wire_move("oscillator1", "sine", True, event(x=-400, y=-400))
    r._wire_end()
    assert len(e.cables) == 1
    r._unplug("audio_out1", "left", False)
    assert e.cables == []
    # move a module into another's place: it lands after it
    r._move_start("audio_out1")
    r._move(event(dx=-1000, dy=0))
    r._move_end()
    assert r.layout["audio_out1"]["x"] >= 0 and changes[-1] == "move"
    xs = sorted((p["x"], n) for n, p in r.layout.items())
    assert len({x for x, _ in xs}) == 3
    r.add("delay")
    assert "delay1" in r.layout
    r.remove("delay1")
    assert "delay1" not in r.layout and all(n.id != "delay1" for n in e.nodes)


def test_rack_renders_and_saves(tmp_path):
    e = patch()
    e.add("scope")
    e.add("sequencer")
    e.connect("oscillator1", "saw", "filter1", "in")
    e.connect("filter1", "lowpass", "scope1", "in")
    layout = {}

    class App(pz.App):
        def view(self):
            return rack.Rack(engine=e, layout=layout, catalog=CATALOG, rows=1)

    pz.screenshot(App, tmp_path / "rack.png", size=(1200, 420), scale=1)
    assert set(layout) == {"oscillator1", "filter1", "audio_out1", "scope1", "sequencer1"}
    rack.save(e, layout, tmp_path / "patch.json")
    e2 = FakeEngine()
    assert rack.load(e2, tmp_path / "patch.json") == layout
    assert e2.cables == e.cables


# -- demos ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("module, name", [("synth", "Synth"), ("visualizer", "Visualizer"),
                                          ("midi_controller", "Controller"), ("drum_machine", "DrumMachine"),
                                          ("modular", "Modular")])
def test_audio_demos_play_offline(tmp_path, module, name):
    audio = pytest.importorskip("pyzed.audio")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples" / "audio"))
    cls = getattr(__import__(module), name)
    engine = audio.Engine("offline")
    app = cls(engine)
    assert app.subscriptions()  # they redraw every frame
    if hasattr(app, "note_on"):
        app.note_on(57)  # the synths only sound while a key is held
    for _ in range(5):
        engine.render(0.05)
        if hasattr(app, "tick"):
            app.tick(0.05)
    pz.screenshot(app, tmp_path / f"{module}.png", size=cls.size, scale=1)
    assert (tmp_path / f"{module}.png").stat().st_size > 1000
    assert max(map(abs, engine.render(0.5)[0])) > 0.001  # it makes sound
