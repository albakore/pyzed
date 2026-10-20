"""A music visualizer: spectrum analyzers, a spectrogram, an oscilloscope and meters, with the
look of each one changed live (variant, palette, bands, falloff).

    python examples/audio/visualizer.py

It plays a short groove made with pyzed.audio (drums, bass and chords); switch the source to the
microphone to see your own voice. Every display reads the engine's analysis (spectrum, scope and
levels of a "scope" module the signal goes through), so nothing is computed in Python.
"""

import pyzed as pz
from pyzed import audio, ui

au = ui.audio

BASS = [0, 0, 12, 0, 3, 0, 15, 3, -2, -2, 10, -2, 5, 5, 17, 7]
CHORDS = [(0, 3, 7), (-2, 2, 5), (-4, 0, 3), (-5, -1, 2)]


def demo_song(engine: audio.Engine, bpm: float = 118):
    """Builds a small groove in ``engine`` (kick, snare, hats, a sequenced bass and chords) and
    returns the module everything goes through before the speakers (to analyze it)."""
    e = engine
    clock = e.add("clock", bpm=bpm, division="1/16")  # 16ths on "clock", quarter notes on "beat"
    seq = e.add("sequencer", steps=16, gate_length=0.4)
    for i, semis in enumerate(BASS, start=1):
        e.set(seq, f"pitch_{i}", semis)
        e.set(seq, f"gate_{i}", 0 if i in (6, 14) else 1)
    e.connect(clock, "clock", seq, "clock")
    bass = e.add("oscillator", wave="saw", freq=65.41, level=0.7)
    e.connect(seq, "pitch", bass, "pitch")
    env = e.add("adsr", attack=0.002, decay=0.18, sustain=0.2, release=0.08)
    e.connect(seq, "gate", env, "gate")
    lpf = e.add("filter", cutoff=380, resonance=0.55, cv_amount=0.6)
    e.connect(bass, "out", lpf, "in")
    e.connect(env, "out", lpf, "cutoff")
    amp = e.add("vca", gain=1.0)
    e.connect(lpf, "lowpass", amp, "in")
    e.connect(env, "out", amp, "cv")
    kick = e.add("drum", sound="kick", decay=0.45, level=1.0)
    e.connect(clock, "beat", kick, "trigger")
    backbeat = e.add("sequencer", steps=16)  # only its gates: the snare on beats 2 and 4
    for i in range(1, 17):
        e.set(backbeat, f"gate_{i}", 1 if i in (5, 13) else 0)
    e.connect(clock, "clock", backbeat, "clock")
    snare = e.add("drum", sound="snare", level=0.55)
    e.connect(backbeat, "gate", snare, "trigger")
    hats = e.add("drum", sound="hihat", decay=0.05, level=0.25)
    e.connect(clock, "clock", hats, "trigger")
    pad = e.add("mixer", level_1=0.25, level_2=0.25, level_3=0.25)
    chord = []
    for k, semis in enumerate(CHORDS[0]):
        osc = e.add("oscillator", wave="triangle", freq=261.63 * 2 ** (semis / 12), level=0.4)
        e.connect(osc, "out", pad, f"in_{k + 1}")
        chord.append(osc)
    mix = e.add("mixer", level_1=0.9, level_2=1.0, level_3=0.7, level_4=0.5)
    e.connect(amp, "out", mix, "in_1")
    e.connect(kick, "out", mix, "in_2")
    e.connect(snare, "out", mix, "in_3")
    e.connect(pad, "left", mix, "in_4")
    hat_mix = e.add("mixer", level_1=1.0, level_2=1.0)
    e.connect(mix, "left", hat_mix, "in_1")
    e.connect(hats, "out", hat_mix, "in_2")
    verb = e.add("reverb", size=0.5, mix=0.18)
    e.connect(hat_mix, "left", verb, "left")
    e.connect(hat_mix, "right", verb, "right")
    tap = e.add("scope")
    e.connect(verb, "left", tap, "in")
    out = e.add("audio_out", volume=0.7)
    e.connect(tap, "out", out, "left")
    e.connect(verb, "right", out, "right")
    e.ui = {"chord": chord, "bpm": bpm, "out": out}
    return tap


def change_chord(engine: audio.Engine, seconds: float) -> None:
    """Moves the pad to the chord of the bar playing at ``seconds``."""
    bpm = engine.ui["bpm"]
    bar = int(seconds * bpm / 60 / 4) % len(CHORDS)
    for osc, semis in zip(engine.ui["chord"], CHORDS[bar]):
        engine.set(osc, "freq", 261.63 * 2 ** (semis / 12))


class Visualizer(pz.App):
    title = "Visualizer"
    size = (1180, 760)

    def __init__(self, engine=None):
        self.engine = engine or audio.Engine(input=True)
        self.song = demo_song(self.engine)
        self.mic = self.engine.add("audio_in", gain=2.0)
        self.mic_tap = self.engine.add("scope")
        self.engine.connect(self.mic, "left", self.mic_tap, "in")
        self.source = "song"
        self.variant = "blocks"
        self.palette = "fl"
        self.bands = 56
        self.falloff = 48.0
        self.peaks = True
        self.radial_palette = "neon"
        self.time = 0.0

    def on_start(self):
        if self.engine.backend != "offline":
            self.engine.start()

    def subscriptions(self):
        return [pz.frames(self.tick)]

    def tick(self, dt):
        self.time += dt
        change_chord(self.engine, self.time)

    def tap(self):
        return self.song if self.source == "song" else self.mic_tap

    def set_source(self, source):
        self.source = source
        self.engine.set(self.engine.ui["out"], "volume", 0.7 if source == "song" else 0.0)  # no feedback

    def controls(self):
        th = self.resolved_theme()
        variants = ["bars", "blocks", "line", "filled", "mirror"]

        def label(text):
            return pz.text(text, size=11, color=th.text_muted)

        return pz.container(pz.column([
            label("SOURCE"),
            ui.segmented([("song", "Song"), ("mic", "Microphone")], self.source, self.set_source),
            label("LOOK"),
            ui.segmented(variants, self.variant, lambda v: setattr(self, "variant", v)),
            label("PALETTE"),
            pz.row([au.LedButton(text=name, on=name == self.palette, color=au.PALETTES[name][-1],
                                 on_toggle=lambda e, name=name: setattr(self, "palette", name), key=f"p-{name}")
                    for name in ("fl", "neon", "fire", "ice", "viridis")], spacing=6, wrap=True),
            pz.row([
                au.Knob(value=self.bands, min=8, max=96, step=1, caption="Bands", decimals=0, variant="fl", diameter=42,
                        on_change=lambda e: setattr(self, "bands", int(e.value)), key="bands"),
                au.Knob(value=self.falloff, min=0, max=200, caption="Falloff", unit="dB", decimals=0, variant="fl",
                        diameter=42, on_change=lambda e: setattr(self, "falloff", e.value), key="falloff"),
                pz.column([label("PEAKS"), au.LedButton(text="ON" if self.peaks else "OFF", on=self.peaks,
                                                         on_toggle=lambda e: setattr(self, "peaks", e.value))],
                          spacing=6),
            ], spacing=10, align="center"),
        ], spacing=10), padding=14, width=300, bg="#24262b", radius=8)

    def view(self):
        tap = self.tap()
        mags = tap.spectrum(512)
        rms, peak = tap.level()
        wave = tap.scope(2048)
        main = au.Spectrum(magnitudes=mags, variant=self.variant, colors=self.palette, bands=self.bands,
                           falloff=self.falloff, peaks=self.peaks, width=760, height=300, labels=True,
                           key="main")
        lower = pz.row([
            au.Spectrum(magnitudes=mags, variant="radial", colors=self.radial_palette, color_by="frequency",
                        bands=72, width=220, height=220, key="radial"),
            pz.column([
                au.Spectrogram(magnitudes=mags, width=380, height=104, history=150, bands=56, key="sgram"),
                au.Scope(traces=[wave], width=380, height=104, window=900, key="scope"),
            ], spacing=12),
            au.VuMeter(level=rms * 1.4, variant="analog", length=200, key="vu"),
        ], spacing=14, align="center")
        meters = au.VuMeter(level=[rms, peak], length=300, thickness=12, segments=32, key="leds")
        return pz.container(pz.row([
            self.controls(),
            pz.column([pz.row([main, meters], spacing=12), lower], spacing=14),
        ], spacing=16), padding=18, bg="#1b1c20", width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Visualizer)
