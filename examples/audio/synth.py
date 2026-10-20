"""A playable synthesizer with effects: two oscillators, a resonant filter, an envelope, distortion,
chorus, delay and reverb, with a piano you play with the mouse or the computer keyboard.

    python examples/audio/synth.py

Keys: A W S E D F T G Y H U J K play notes, Z and X change the octave.
The sound comes from pyzed.audio (it plays silence on a computer without a sound card); this file
is only the panel: knobs set the engine's parameters and the displays read its output.
"""

import pyzed as pz
from pyzed import audio, ui

au = ui.audio

PRESETS = {
    "Bass": dict(wave=2, sub=0.7, detune=0.08, cutoff=420, resonance=0.55, env_amount=0.55, attack=0.004,
                 decay=0.22, sustain=0.35, release=0.12, drive=0.35, chorus=0.0, delay=0.08, reverb=0.08),
    "Lead": dict(wave=3, sub=0.2, detune=0.18, cutoff=1800, resonance=0.35, env_amount=0.35, attack=0.01,
                 decay=0.3, sustain=0.7, release=0.25, drive=0.15, chorus=0.25, delay=0.3, reverb=0.2),
    "Pad": dict(wave=2, sub=0.3, detune=0.25, cutoff=900, resonance=0.15, env_amount=0.2, attack=0.9,
                decay=1.2, sustain=0.8, release=1.8, drive=0.0, chorus=0.6, delay=0.2, reverb=0.55),
}


class Synth(pz.App):
    title = "Pyzed Synth"
    size = (1120, 700)

    def __init__(self, engine=None):
        self.engine = engine or audio.Engine()
        e = self.engine
        self.midi = e.add("midi_in", glide=0.0)
        self.osc = e.add("oscillator", wave="saw", level=0.6)
        self.sub = e.add("oscillator", wave="square", freq=130.81, level=0.5)
        self.mix = e.add("mixer")
        self.vcf = e.add("filter", mode="lowpass")
        self.env = e.add("adsr")
        self.vca = e.add("vca", gain=1.0)
        self.dist = e.add("distortion", type="soft", mix=1.0)
        self.chorus = e.add("chorus")
        self.delay = e.add("delay", time=0.32)
        self.reverb = e.add("reverb")
        self.out = e.add("audio_out", volume=0.8)
        e.connect(self.midi, "pitch", self.osc, "pitch")
        e.connect(self.midi, "pitch", self.sub, "pitch")
        e.connect(self.midi, "gate", self.env, "gate")
        e.connect(self.osc, "out", self.mix, "in_1")
        e.connect(self.sub, "out", self.mix, "in_2")
        e.connect(self.mix, "left", self.vcf, "in")
        e.connect(self.env, "out", self.vcf, "cutoff")
        e.connect(self.vcf, "out", self.vca, "in")
        e.connect(self.env, "out", self.vca, "cv")
        e.connect(self.vca, "out", self.dist, "in")
        e.connect(self.dist, "out", self.chorus, "in")
        e.connect(self.chorus, "left", self.delay, "in")
        e.connect(self.delay, "out", self.reverb, "left")
        e.connect(self.chorus, "right", self.reverb, "right")
        e.connect(self.reverb, "left", self.out, "left")
        e.connect(self.reverb, "right", self.out, "right")
        self.octave = 4
        self.held = set()
        self.keys = {}
        self.preset = "Lead"
        self.values = {}
        self.load(self.preset)

    def on_start(self):
        if self.engine.backend != "offline":
            self.engine.start()

    def subscriptions(self):
        return [pz.frames(lambda dt: None)]  # the displays follow the sound

    # -- the patch, seen as a few musical parameters --------------------------------------------
    def load(self, name):
        self.preset = name
        for key, value in PRESETS[name].items():
            self.put(key, value)

    def put(self, key, value):
        """Sets one of the panel's parameters on the module(s) it controls."""
        self.values[key] = value
        e = self.engine
        if key == "wave":
            e.set(self.osc, "wave", int(value))
        elif key == "sub":
            e.set(self.mix, "level_2", value)
        elif key == "detune":
            e.set(self.osc, "fine", value)
        elif key in ("cutoff", "resonance"):
            e.set(self.vcf, key, value)
        elif key == "env_amount":
            e.set(self.vcf, "cv_amount", value)
        elif key in ("attack", "decay", "sustain", "release"):
            e.set(self.env, key, value)
        elif key == "drive":
            e.set(self.dist, "drive", value)
            e.set(self.dist, "mix", 1.0 if value > 0 else 0.0)
        elif key == "chorus":
            e.set(self.chorus, "mix", value)
        elif key == "delay":
            e.set(self.delay, "mix", value)
        elif key == "reverb":
            e.set(self.reverb, "mix", value)

    # -- playing ----------------------------------------------------------------------------------
    def note_on(self, note, velocity=100):
        self.held.add(note)
        self.engine.note_on(note, velocity)

    def note_off(self, note):
        self.held.discard(note)
        self.engine.note_off(note)

    def on_key(self, combo):
        if combo in ("z", "x"):
            self.octave = max(1, min(7, self.octave + (1 if combo == "x" else -1)))
        elif combo in au.KEYBOARD and combo not in self.keys:
            note = (self.octave + 1) * 12 + au.KEYBOARD[combo]
            self.keys[combo] = note
            self.note_on(note)

    def on_key_up(self, key):
        if key in self.keys:
            self.note_off(self.keys.pop(key))

    # -- view ---------------------------------------------------------------------------------------
    def knob(self, key, caption, lo, hi, **kw):
        return au.Knob(value=self.values[key], min=lo, max=hi, caption=caption, variant="fl", diameter=46,
                       on_change=lambda e: self.put(key, e.value), key=key, **kw)

    def section(self, title, color, children):
        th = self.resolved_theme()
        head = pz.row([pz.container(None, width=8, height=8, bg=color, radius=4),
                       pz.text(title, size=11, weight="bold", color=th.text_muted)], spacing=6, align="center")
        return pz.container(pz.column([head, pz.row(children, spacing=6)], spacing=10), padding=12,
                            bg="#24262b", radius=8, border_color="#15171a", border_width=1)

    def view(self):
        th = self.resolved_theme()
        presets = pz.row([au.LedButton(text=name.upper(), on=name == self.preset, color="#ff9f3d",
                                       on_toggle=lambda e, name=name: self.load(name), key=f"preset-{name}")
                          for name in PRESETS], spacing=6)
        header = pz.row([pz.text("PYZED SYNTH", size=18, weight="bold"), pz.space(width="fill"), presets],
                        align="center")
        osc = self.section("OSCILLATORS", "#ff9f3d", [
            au.Knob(value=self.values["wave"], options=["Sine", "Tri", "Saw", "Square"], caption="Wave",
                    variant="fl", diameter=46, color="#ff9f3d", on_change=lambda e: self.put("wave", e.value),
                    key="wave"),
            self.knob("detune", "Detune", -1, 1, unit="st", bipolar=True, color="#ff9f3d"),
            self.knob("sub", "Sub", 0, 1, unit="%", color="#ff9f3d"),
        ])
        flt = self.section("FILTER", "#4fc3f7", [
            self.knob("cutoff", "Cutoff", 40, 16000, curve="log", unit="Hz", color="#4fc3f7"),
            self.knob("resonance", "Reso", 0, 1, unit="%", color="#4fc3f7"),
            self.knob("env_amount", "Env amt", 0, 1, unit="%", color="#4fc3f7"),
        ])
        env = self.section("ENVELOPE", "#f5d547", [
            self.knob("attack", "Attack", 0.001, 4, curve="log", unit="s", color="#f5d547"),
            self.knob("decay", "Decay", 0.001, 4, curve="log", unit="s", color="#f5d547"),
            self.knob("sustain", "Sustain", 0, 1, unit="%", color="#f5d547"),
            self.knob("release", "Release", 0.001, 6, curve="log", unit="s", color="#f5d547"),
        ])
        fx = self.section("EFFECTS", "#ff6b9d", [
            self.knob("drive", "Drive", 0, 1, unit="%", color="#ff6b9d"),
            self.knob("chorus", "Chorus", 0, 1, unit="%", color="#ff6b9d"),
            self.knob("delay", "Delay", 0, 1, unit="%", color="#ff6b9d"),
            self.knob("reverb", "Reverb", 0, 1, unit="%", color="#ff6b9d"),
        ])
        rms, peak = self.engine.level()
        displays = pz.row([
            au.Scope(traces=[self.engine.scope(1024)], width=300, height=150, window=600),
            au.Spectrum(magnitudes=self.engine.spectrum(512), width=420, height=150, variant="blocks",
                        bands=56, colors="fl"),
            au.VuMeter(level=[rms, peak], length=150),
            au.Fader(value=self.engine.get(self.out, "volume"), length=150, variant="fl", color="#ff9f3d",
                     caption="Volume", show_value=False,
                     on_change=lambda e: self.engine.set(self.out, "volume", e.value)),
        ], spacing=14, align="center")
        piano = au.Piano(start=36, octaves=5, pressed=sorted(self.held), key_width=22, height=110,
                         color="#ff9f3d", on_note_on=lambda e: self.note_on(e.value.note, e.value.velocity),
                         on_note_off=lambda e: self.note_off(e.value))
        info = self.engine.info
        status = pz.text(f"{info.get('backend')} · {info.get('sample_rate')} Hz · "
                         f"{info.get('latency_ms') or 0:.1f} ms · octave {self.octave} (Z/X)", size=11,
                         color=th.text_muted, font="mono")
        return pz.container(pz.column([
            header,
            pz.row([osc, flt, env, fx], spacing=10, wrap=True),
            displays,
            piano,
            status,
        ], spacing=14), padding=18, bg="#1b1c20", width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Synth)
