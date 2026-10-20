"""A drum machine and an acid bass line, all modules and cables, with sidechain "pumping".

    python examples/audio/engine_drum_machine.py               # plays until Ctrl+C
    python examples/audio/engine_drum_machine.py --render beat.wav --seconds 8
"""

import argparse
import time

from pyzed import audio

BPM = 124
BASS = [0, 0, 12, 0, 3, 0, 10, 7, 0, 0, 12, 0, 5, 3, 0, -2]
HATS = [0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1]
CLAPS = [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0]


def steps(name: str, values) -> dict:
    return {f"{name}_{i + 1}": v for i, v in enumerate(values)}


def patch(engine: audio.Engine) -> None:
    clock = engine.add("clock", id="clock", bpm=BPM, division="1/16", swing=0.08)
    beat = engine.add("clock", id="beat", bpm=BPM, division="1/4")

    # Drums: the kick on every beat, hats and claps from their own 16-step gates.
    kick = engine.add("drum", id="kick", sound="kick", decay=0.4, level=0.9)
    engine.connect(beat, "clock", kick, "trigger")
    hats = engine.add("sequencer", id="hats", steps=16, bpm=0, gate_length=0.2, **steps("gate", HATS))
    hat = engine.add("drum", id="hat", sound="hihat", decay=0.06, tone=0.8, level=0.35)
    claps = engine.add("sequencer", id="claps", steps=16, bpm=0, **steps("gate", CLAPS))
    clap = engine.add("drum", id="clap", sound="clap", decay=0.3, level=0.5)
    for seq, voice in ((hats, hat), (claps, clap)):
        engine.connect(clock, "clock", seq, "clock")
        engine.connect(seq, "trigger", voice, "trigger")

    # Bass: a sequencer plays a saw through a resonant filter swept by its envelope.
    bassline = engine.add("sequencer", id="bassline", steps=16, bpm=0, gate_length=0.4,
                          **steps("pitch", BASS))
    engine.connect(clock, "clock", bassline, "clock")
    vco = engine.add("oscillator", id="vco", wave="saw", freq=55, level=0.7)
    vcf = engine.add("filter", id="vcf", cutoff=300, resonance=0.75, drive=0.3)
    env = engine.add("adsr", id="env", attack=0.002, decay=0.15, sustain=0.1, release=0.08)
    vca = engine.add("vca", id="vca")
    engine.connect(bassline, "pitch", vco, "pitch")
    engine.connect(bassline, "gate", env, "gate")
    engine.connect(env, "out", vcf, "cutoff")
    engine.connect(env, "out", vca, "cv")
    engine.chain(vco, vcf, vca)
    # The kick ducks the bass: the compressor listens to it on its sidechain.
    duck = engine.add("compressor", id="duck", threshold=-30, ratio=8, attack=1, release=150)
    engine.connect(vca, "out", duck, "in")
    engine.connect(kick, "out", duck, "sidechain")
    delay = engine.add("delay", id="delay", time=60 / BPM * 0.75, feedback=0.3, mix=0.2)
    engine.chain(duck, delay)

    mix = engine.add("mixer", id="mix", level_1=0.9, level_2=0.5, pan_2=-0.3, level_3=0.6, pan_3=0.3,
                     level_4=0.8)
    for i, voice in enumerate((kick, hat, clap, delay)):
        engine.connect(voice, "out", mix, f"in_{i + 1}")
    reverb = engine.add("reverb", id="reverb", size=0.4, mix=0.12)
    engine.chain(mix, reverb, engine.add("audio_out", id="out", volume=0.8))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--render", metavar="WAV", help="render to a WAV file instead of playing")
    parser.add_argument("--seconds", type=float, default=8.0)
    args = parser.parse_args()
    if args.render:
        engine = audio.Engine("offline")
        patch(engine)
        print("wrote", engine.render_wav(args.render, args.seconds))
        return
    engine = audio.Engine()
    patch(engine)
    with engine:
        print(f"{BPM} BPM on {engine.info['device']}. Ctrl+C to stop.")
        try:
            while True:
                rms, peak = engine.level()
                bar = "█" * int(peak * 40)
                print(f"\r{bar:<40} step {int(engine.node('bassline').state['step']) + 1:>2}", end="", flush=True)
                time.sleep(1 / 30)
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
