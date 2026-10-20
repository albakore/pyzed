"""The audio engine (pyzed.audio), rendered offline or on the null clock: CI has no sound card."""

import json
import math
import time
import wave

import pytest

from pyzed import audio

SR = 48000


def engine():
    return audio.Engine("offline", sample_rate=SR)


def rms(xs):
    return math.sqrt(sum(x * x for x in xs) / max(1, len(xs)))


def frequency(xs, sr=SR):
    """The frequency of a periodic signal, from its upward zero crossings."""
    crossings = [i for i in range(1, len(xs)) if xs[i - 1] < 0 <= xs[i]]
    return (len(crossings) - 1) * sr / (crossings[-1] - crossings[0])


def test_catalog_describes_every_module():
    kinds = [m.kind for m in audio.modules()]
    for kind in ["oscillator", "lfo", "noise", "sampler", "drum", "audio_in", "midi_in", "constant", "clock",
                 "filter", "vca", "adsr", "mixer", "delay", "reverb", "distortion", "chorus", "bitcrusher",
                 "compressor", "sequencer", "scope", "audio_out", "midi_out"]:
        assert kind in kinds
    osc = audio.module("oscillator")
    assert [p.name for p in osc.inputs] == ["pitch", "fm", "pwm", "sync"]
    assert osc.outputs[0] == audio.Port("out", "Out", "audio")
    wave_param = osc.param("wave")
    assert wave_param.options == ("sine", "triangle", "saw", "square")
    freq = osc.param("freq")
    assert freq.curve == "log" and freq.unit == "Hz"
    assert freq.from_unit(freq.to_unit(1000)) == pytest.approx(1000)
    assert freq.format(1500) == "1.50 kHz"
    assert audio.module("adsr").param("attack").format(0.25) == "250 ms"
    for m in audio.modules():
        for p in m.params:
            assert p.min <= p.default <= p.max, (m.kind, p.name)
    with pytest.raises(ValueError, match="unknown module"):
        audio.module("theremin")


def test_oscillator_plays_its_frequency_and_the_output_mixes_it():
    e = engine()
    osc = e.add("oscillator", freq=440, wave="sine", level=0.5)
    out = e.add("audio_out", volume=1.0)
    e.chain(osc, out)
    left, right = e.render(0.5)
    assert len(left) == len(right) == SR // 2
    assert frequency(left) == pytest.approx(440, rel=0.01)
    assert left == right  # nothing on `right`: the left side plays on both
    assert rms(left) == pytest.approx(0.5 / math.sqrt(2), rel=0.02)
    assert osc["freq"] == pytest.approx(440)
    assert osc.params["wave"] == 0


def test_pitch_input_follows_volts_per_octave():
    e = engine()
    pitch = e.add("constant", value=1.0)
    osc = e.add("oscillator", wave="sine")
    e.connect(pitch, "out", osc, "pitch")
    e.chain(osc, e.add("audio_out", volume=1))
    left, _ = e.render(0.5)
    assert frequency(left) == pytest.approx(261.63 * 2, rel=0.01)
    assert audio.volts("C5") == 1.0
    assert audio.note_number("A4") == 69 and audio.note_name(60) == "C4"


def test_filter_removes_highs_and_the_spectrum_shows_it():
    e = engine()
    noise = e.add("noise", level=0.5)
    lpf = e.add("filter", cutoff=300, mode="lowpass")
    out = e.add("audio_out", volume=1)
    e.chain(noise, lpf, out)
    e.render(0.3)
    spectrum = lpf.spectrum(bins=64)
    assert len(spectrum) == 64 and all(-120 <= x <= 0 for x in spectrum)
    low, high = max(spectrum[:20]), max(spectrum[-10:])
    assert low - high > 30
    raw = noise.spectrum(bins=64)
    assert raw[-5] - spectrum[-5] > 30
    assert len(lpf.scope(512)) == 512


def test_envelope_follows_the_gate_from_midi():
    e = engine()
    keys = e.add("midi_in")
    env = e.add("adsr", attack=0.01, decay=0.05, sustain=0.5, release=0.05)
    e.connect(keys, "gate", env, "gate")
    e.render(0.05)
    assert env.state["level"] == 0
    e.note_on("A4", 127)
    e.render(0.2)
    assert keys.state == {"note": 69.0, "gate": 1.0}
    assert keys.probe("pitch") == pytest.approx(0.75)
    assert keys.probe("velocity") == pytest.approx(1.0)
    assert env.state["level"] == pytest.approx(0.5, abs=0.01)
    e.note_off("A4")
    e.render(0.5)
    assert env.state["level"] < 0.001
    assert keys.state["gate"] == 0


def test_a_little_synth_voice_renders_without_clipping_or_errors():
    e = engine()
    keys = e.add("midi_in")
    osc = e.add("oscillator", wave="saw")
    lpf = e.add("filter", cutoff=900, resonance=0.6)
    env = e.add("adsr")
    vca = e.add("vca")
    dly = e.add("delay", time=0.2)
    rev = e.add("reverb")
    out = e.add("audio_out")
    e.connect(keys, "pitch", osc, "pitch")
    e.connect(keys, "gate", env, "gate")
    e.connect(env, "out", vca, "cv")
    e.connect(env, "out", lpf, "cutoff")
    e.chain(osc, lpf, vca, dly, rev, out)
    for note in ["C3", "E3", "G3"]:
        e.note_on(note)
        e.render(0.15)
        e.note_off(note)
    left, right = e.render(1.0)
    assert 0.001 < rms(left) and max(map(abs, left + right)) <= 1.5
    assert all(math.isfinite(x) for x in left)
    assert left != right  # the reverb spreads the sound
    peak_rms, peak = e.level()
    assert 0 < peak_rms <= peak


def test_sequencer_steps_through_its_pitches_on_the_clock():
    e = engine()
    clock = e.add("clock", bpm=120, division="1/16")
    seq = e.add("sequencer", steps=4, pitch_1=0, pitch_2=12, pitch_3=7, pitch_4=-12)
    e.connect(clock, "clock", seq, "clock")
    seen = []
    e.render(0.06)  # sample in the middle of each step
    for _ in range(8):
        e.render(0.125)  # one sixteenth at 120 BPM
        seen.append((seq.state["step"], round(seq.probe("pitch"), 3)))
    steps = [s for s, _ in seen]
    assert set(steps) == {0, 1, 2, 3}
    pitches = {s: p for s, p in seen}
    assert pitches[1] == 1.0 and pitches[2] == round(7 / 12, 3) and pitches[3] == -1.0
    assert clock.state["tick"] >= 7


def test_sequencer_runs_on_its_own_tempo_without_a_clock():
    e = engine()
    seq = e.add("sequencer", steps=8, bpm=240)  # sixteenths at 240 BPM: 16 steps a second
    e.render(0.26)
    assert seq.state["step"] == 4


def test_drums_and_sampler_play_when_triggered():
    e = engine()
    kick = e.add("drum", sound="kick", decay=0.3)
    smp = e.add("sampler")
    tone = [math.sin(2 * math.pi * 1000 * i / SR) for i in range(SR // 10)]
    smp.load(tone, sample_rate=SR)
    mix = e.add("mixer")
    e.connect(kick, "out", mix, "in_1")
    e.connect(smp, "left", mix, "in_2")
    e.chain(mix, e.add("audio_out"))
    silent, _ = e.render(0.05)
    assert rms(silent) == 0
    kick.trigger()
    smp.trigger()
    hit, _ = e.render(0.05)
    assert rms(hit) > 0.05
    assert kick.state["hit"] == 1
    assert smp.state["playing"] == 1
    e.render(0.2)
    assert smp.state["playing"] == 0


def test_sampler_reads_wav_files(tmp_path):
    path = tmp_path / "beep.wav"
    e = engine()
    osc = e.add("oscillator", freq=880, wave="sine")
    e.chain(osc, e.add("audio_out", volume=1))
    e.render_wav(path, 0.25)
    with wave.open(str(path)) as f:
        assert (f.getnchannels(), f.getframerate(), f.getnframes()) == (2, SR, SR // 4)

    e2 = engine()
    smp = e2.add("sampler", mode="loop")
    smp.load(path)
    e2.chain(smp, e2.add("audio_out", volume=1))
    smp.trigger()
    left, right = e2.render(0.5)
    assert frequency(left[1000:]) == pytest.approx(880, rel=0.02)
    assert e2.to_dict()["nodes"][0]["sample"] == str(path)


@pytest.mark.parametrize("kind", ["delay", "reverb", "distortion", "chorus", "bitcrusher", "compressor"])
def test_every_effect_processes_a_tone(kind):
    e = engine()
    osc = e.add("oscillator", freq=220, wave="saw", level=0.5)
    fx = e.add(kind)
    e.chain(osc, fx, e.add("audio_out", volume=1))
    left, right = e.render(0.5)
    assert all(math.isfinite(x) for x in left + right)
    assert rms(left[SR // 4:]) > 0.01


def test_compressor_reduces_loud_signals():
    e = engine()
    osc = e.add("oscillator", freq=220, wave="square", level=1.0)
    comp = e.add("compressor", threshold=-30, ratio=10, attack=1, release=50)
    e.chain(osc, comp, e.add("audio_out", volume=1))
    left, _ = e.render(0.5)
    assert comp.state["reduction"] < -15
    assert rms(left[SR // 4:]) < 0.3


def test_lfo_modulates_and_feedback_loops_are_allowed():
    e = engine()
    lfo = e.add("lfo", rate=5, wave="square", amount=1)
    vca = e.add("vca")
    osc = e.add("oscillator", wave="sine")
    e.connect(lfo, "unipolar", vca, "cv")
    e.chain(osc, vca)
    # A loop through a delay: allowed, with one block of delay.
    dly = e.add("delay", feedback=0.2)
    e.connect(vca, "out", dly, "in")
    e.connect(dly, "out", vca, "in")
    e.chain(dly, e.add("audio_out"))
    left, _ = e.render(0.5)
    assert all(math.isfinite(x) for x in left)
    assert 0 <= lfo.state["phase"] < 1


def test_patch_editing_errors_are_clear():
    e = engine()
    osc = e.add("oscillator", id="osc")
    vcf = e.add("filter")
    with pytest.raises(ValueError, match="no parameter .cutof.; its parameters are .*cutoff"):
        vcf["cutof"] = 1
    with pytest.raises(ValueError, match="has no output .output.; its outputs are out"):
        e.connect(osc, "output", vcf, "in")
    with pytest.raises(ValueError, match="takes sine, triangle, saw, square"):
        osc["wave"] = "noise"
    with pytest.raises(ValueError, match="already a module"):
        e.add("filter", id="osc")
    assert vcf.set(cutoff=1e9)["cutoff"] == 20000  # clamped to its range
    assert e.connect(osc, "out", vcf, "in") is True
    assert e.connect(osc, "out", vcf, "in") is False
    assert e.cables == [("osc", "out", "filter1", "in")]
    assert e.disconnect(osc, "out", vcf, "in") is True
    assert e.cables == []
    e.connect(osc, "out", vcf, "in")
    osc.remove()
    assert e.cables == [] and [n.id for n in e.nodes] == ["filter1"]
    with pytest.raises(KeyError):
        e.node("osc")


def test_patches_round_trip_through_json_and_keep_the_ui():
    e = engine()
    osc = e.add("oscillator", id="vco", freq=110, wave="square")
    lpf = e.add("filter", id="vcf", cutoff=500)
    out = e.add("audio_out", id="out")
    e.chain(osc, lpf, out)
    osc.ui = {"x": 10, "y": 0, "color": "#f80"}
    e.ui = {"zoom": 1.5}
    data = json.loads(json.dumps(e.to_dict()))
    copy = audio.Engine.from_dict(data, "offline", sample_rate=SR)
    assert copy.to_dict() == data
    assert copy.node("vco").ui == {"x": 10, "y": 0, "color": "#f80"}
    assert copy.ui == {"zoom": 1.5}
    assert copy.node("vco")["wave"] == 3
    a, _ = e.render(0.1)
    b, _ = copy.render(0.1)
    assert a == pytest.approx(b, abs=1e-6)


def test_null_backend_plays_in_real_time_and_takes_changes_live():
    e = audio.Engine("null", sample_rate=SR, buffer_size=128)
    osc = e.add("oscillator", freq=440, wave="sine")
    e.chain(osc, e.add("audio_out", volume=1))
    with e:
        info = e.info
        assert info["running"] and info["backend"] == "null"
        assert info["buffer_size"] == 128
        assert info["latency_ms"] == pytest.approx(128 / SR * 1000, rel=1e-3)
        time.sleep(0.3)
        assert 0.15 < e.info["time"] < 1.0
        assert frequency(e.scope(4096)) == pytest.approx(440, rel=0.02)
        for _ in range(200):  # a burst of knob turns while playing
            osc["freq"] = 880
        time.sleep(0.15)
        assert frequency(e.scope(4096)) == pytest.approx(880, rel=0.02)
        with pytest.raises(RuntimeError, match="stop"):
            e.render(0.1)
    assert not e.running


def test_auto_backend_falls_back_to_silence_without_a_device():
    e = audio.Engine("auto", sample_rate=SR, device="no such device anywhere")
    info = e.start()
    try:
        assert info["running"]
        assert info["backend"] == "null"
        assert "no audio output device" in info["error"]
    finally:
        e.stop()
    with pytest.raises(RuntimeError, match="no audio output device"):
        audio.Engine("device", device="no such device anywhere").start()


def test_hosts_devices_and_midi_ports_can_be_listed():
    assert audio.default_host() in audio.hosts()
    assert audio.recommended_settings()["host"] == audio.default_host()
    try:
        devices = audio.devices()
    except RuntimeError:
        devices = []  # a machine without an audio system at all
    assert all(isinstance(d, audio.Device) for d in devices)
    assert isinstance(audio.midi_inputs(), list) and isinstance(audio.midi_outputs(), list)


def test_offline_engine_never_plays():
    e = engine()
    with pytest.raises(RuntimeError, match="offline"):
        e.start()
    assert e.info["backend"] == "offline" and not e.running


ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("name", ["engine_synth", "engine_drum_machine", "engine_microphone"])
def test_audio_examples_build_and_render(name):
    import importlib.util

    path = ROOT / "examples" / "audio" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    example = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(example)
    e = engine()
    example.patch(e)
    if name == "engine_synth":
        example.play_melody(e, step=0.1, render=e.render)
    left, right = e.render(1.0)
    assert all(math.isfinite(x) for x in left + right)
    if name != "engine_microphone":  # no microphone offline: silence is right
        assert rms(left) > 0.005
    assert max(map(abs, left + right)) < 1.0


def test_module_catalog_page_is_up_to_date():
    import subprocess
    import sys

    script = ROOT / "docs" / "scripts" / "gen_audio_modules.py"
    result = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
