"""Your microphone through a chain of effects, live: distortion, chorus, delay and reverb.

    python examples/audio/engine_microphone.py
    python examples/audio/engine_microphone.py --list            # the audio devices of this system
    python examples/audio/engine_microphone.py --input "USB" --buffer 128

Use headphones: the speakers would feed back into the microphone. The lower the buffer, the
lower the delay between your voice and what you hear (until the sound starts to crackle).
"""

import argparse
import time

from pyzed import audio


def patch(engine: audio.Engine) -> None:
    mic = engine.add("audio_in", id="mic", gain=1.5)
    drive = engine.add("distortion", id="drive", type="soft", drive=0.25, mix=0.5)
    chorus = engine.add("chorus", id="chorus", rate=0.6, depth=0.4, mix=0.35)
    delay = engine.add("delay", id="delay", time=0.28, feedback=0.3, mix=0.2)
    reverb = engine.add("reverb", id="reverb", size=0.6, mix=0.25)
    out = engine.add("audio_out", id="out", volume=0.8)
    engine.connect(mic, "left", drive, "in")
    engine.chain(drive, chorus)
    for side in ("left", "right"):
        engine.connect(chorus, side, delay, "in")
    engine.connect(delay, "out", reverb, "left")
    engine.chain(reverb, out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--list", action="store_true", help="list the audio devices and exit")
    parser.add_argument("--input", help="the input device (part of its name); default: the system's")
    parser.add_argument("--buffer", type=int, help="frames per buffer (default: the recommended one)")
    args = parser.parse_args()
    if args.list:
        print("Hosts:", ", ".join(audio.hosts()), "· default:", audio.default_host())
        for d in audio.devices():
            kind = " ".join(k for k, n in (("in", d.inputs), ("out", d.outputs)) if n)
            print(f"  {d.name}  [{kind}]  {d.sample_rate} Hz")
        return
    devices = [d.name for d in audio.devices() if args.input and args.input.lower() in d.name.lower() and d.inputs]
    engine = audio.Engine("device", input=True, input_device=devices[0] if devices else None,
                          buffer_size=args.buffer)
    patch(engine)
    with engine:
        info = engine.info
        print(f"{info['input_device']} → {info['device']} · {info['host']} · "
              f"{info['buffer_size'] or 'system'} frames · {info['latency_ms'] or 0:.1f} ms")
        try:
            while True:
                level = engine.node("mic").level()[1]
                print(f"\rmic {'█' * int(level * 40):<40} load {engine.info['load']:.0%}", end="", flush=True)
                time.sleep(1 / 30)
        except KeyboardInterrupt:
            print()


if __name__ == "__main__":
    main()
