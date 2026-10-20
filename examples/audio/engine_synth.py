"""A subtractive synthesizer with no window: oscillator, filter, envelope, delay and reverb.

    python examples/audio/engine_synth.py                 # plays a melody (and your MIDI keyboard)
    python examples/audio/engine_synth.py --render synth.wav

With a MIDI keyboard connected, play it: the `midi_in` module turns its notes into pitch and gate.
Press Ctrl+C to stop.
"""

import argparse
import time

from pyzed import audio

MELODY = ["A3", "C4", "E4", "A4", "G4", "E4", "D4", "E4"]


def patch(engine: audio.Engine) -> None:
    keys = engine.add("midi_in", id="keys", glide=0.03)
    vco = engine.add("oscillator", id="vco", wave="saw", level=0.6)
    sub = engine.add("oscillator", id="sub", wave="square", freq=130.81, level=0.3)
    vcf = engine.add("filter", id="vcf", cutoff=500, resonance=0.55, cv_amount=0.6)
    env = engine.add("adsr", id="env", attack=0.005, decay=0.25, sustain=0.5, release=0.4)
    vca = engine.add("vca", id="vca")
    lfo = engine.add("lfo", id="lfo", rate=0.3, amount=0.4)
    mix = engine.add("mixer", id="mix")
    delay = engine.add("delay", id="delay", time=0.3, feedback=0.35, mix=0.25)
    reverb = engine.add("reverb", id="reverb", size=0.7, mix=0.25)
    out = engine.add("audio_out", id="out", volume=0.7)

    # Both oscillators follow the keyboard; the sub plays an octave below.
    engine.connect(keys, "pitch", vco, "pitch")
    engine.connect(keys, "pitch", sub, "pitch")
    engine.connect(vco, "out", mix, "in_1")
    engine.connect(sub, "out", mix, "in_2")
    # The envelope opens the amplifier and the filter; the LFO slowly moves the filter too.
    engine.connect(keys, "gate", env, "gate")
    engine.connect(keys, "retrigger", env, "retrig")
    engine.connect(env, "out", vca, "cv")
    engine.connect(env, "out", vcf, "cutoff")
    engine.connect(lfo, "out", vcf, "cutoff")
    engine.connect(mix, "left", vcf, "in")
    engine.chain(vcf, vca, delay, reverb, out)


def play_melody(engine: audio.Engine, step: float = 0.25, render=None) -> None:
    """Plays MELODY once; with `render`, renders offline instead of waiting."""
    for note in MELODY:
        engine.note_on(note, 100)
        render(step * 0.7) if render else time.sleep(step * 0.7)
        engine.note_off(note)
        render(step * 0.3) if render else time.sleep(step * 0.3)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--render", metavar="WAV", help="render to a WAV file instead of playing")
    args = parser.parse_args()
    if args.render:
        engine = audio.Engine("offline")
        patch(engine)
        left, right = [], []

        def render(seconds):
            l, r = engine.render(seconds)
            left.extend(l)
            right.extend(r)

        play_melody(engine, render=render)
        render(2.0)
        print("wrote", audio.write_wav(args.render, left, right, engine.sample_rate))
        return

    engine = audio.Engine()
    patch(engine)
    with engine:
        info = engine.info
        print(f"{info['host']} · {info['device']} · {info['sample_rate']} Hz · {info['latency_ms'] or 0:.1f} ms")
        if info.get("error"):
            print(info["error"])
        try:
            print("MIDI:", engine.open_midi_input())
        except RuntimeError:
            print("No MIDI keyboard: playing the melody.")
        try:
            while True:
                play_melody(engine)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
