"""A MIDI controller in the style of FL Studio's: eight channel strips (pan knob, fader with a meter,
mute and solo), sixteen velocity pads, pitch and mod wheels, transport buttons and a keyboard.

    python examples/audio/midi_controller.py

It plays a built-in drum kit and synth through pyzed.audio, so you hear every pad and key. Switch
on "MIDI OUT" to also send everything to other programs (a DAW, a hardware synth) through a
virtual MIDI port named "Pyzed Controller" (Linux and macOS) or the first MIDI output found.
"""

import pyzed as pz
from pyzed import audio, ui

au = ui.audio

SOUNDS = [("KICK", "kick", 0), ("SNARE", "snare", 0), ("HAT", "hihat", 0), ("CLAP", "clap", 0),
          ("TOM LO", "tom", -5), ("TOM HI", "tom", 4), ("RIM", "snare", 9), ("OPEN", "hihat", -4)]
#: The beat PLAY runs (pads by index -> steps of a 16-step bar).
BEAT = {0: [0, 4, 8, 10], 1: [4, 12], 2: [0, 2, 4, 6, 8, 10, 12, 14], 3: [12], 7: [14]}
COLORS = ["#ff9f3d", "#ff6b9d", "#3dd68c", "#f5d547", "#4fc3f7", "#4fc3f7", "#b26cf0", "#2fd3d3"]


class Controller(pz.App):
    title = "MIDI Controller"
    size = (1280, 660)

    def __init__(self, engine=None):
        self.engine = engine or audio.Engine()
        e = self.engine
        self.drums = []
        self.buses = [e.add("mixer", master=0.9), e.add("mixer", master=0.9)]
        for i, (_name, sound, tune) in enumerate(SOUNDS):
            drum = e.add("drum", sound=sound, tune=tune, level=0.9)
            e.connect(drum, "out", self.buses[i // 4], f"in_{i % 4 + 1}")
            self.drums.append(drum)
        self.midi = e.add("midi_in")
        self.synth = e.add("oscillator", wave="saw", level=0.5)
        self.filter = e.add("filter", cutoff=1400, resonance=0.4, cv_amount=0.4)
        self.env = e.add("adsr", attack=0.005, decay=0.25, sustain=0.5, release=0.3)
        self.amp = e.add("vca", gain=1.0)
        e.connect(self.midi, "pitch", self.synth, "pitch")
        e.connect(self.midi, "gate", self.env, "gate")
        e.connect(self.synth, "out", self.filter, "in")
        e.connect(self.env, "out", self.filter, "cutoff")
        e.connect(self.filter, "lowpass", self.amp, "in")
        e.connect(self.env, "out", self.amp, "cv")
        self.master = e.add("mixer", level_1=1.0, level_2=1.0, level_3=0.8)
        e.connect(self.buses[0], "left", self.master, "in_1")
        e.connect(self.buses[1], "left", self.master, "in_2")
        e.connect(self.amp, "out", self.master, "in_3")
        self.out = e.add("audio_out", volume=0.8)
        e.connect(self.master, "left", self.out, "left")
        e.connect(self.master, "right", self.out, "right")
        self.levels = [0.8] * 8
        self.pans = [0.0] * 8
        self.muted = [False] * 8
        self.solo = [False] * 8
        self.hit = [0.0] * 8
        self.bend = 0.0
        self.mod = 0.0
        self.playing = False
        self.clock = 0.0
        self.step = -1
        self.recording = False
        self.midi_out = False
        self.held = set()
        self.log = []

    def on_start(self):
        if self.engine.backend != "offline":
            self.engine.start()

    def subscriptions(self):
        return [pz.frames(self.tick)]

    def tick(self, dt):
        self.hit = [max(0.0, h - dt * 3) for h in self.hit]
        if self.playing:  # a simple beat at 120 BPM, sixteenth notes, played on the pads
            self.clock += dt
            step = int(self.clock * 8) % 16
            if step != self.step:
                self.step = step
                for pad, steps in BEAT.items():
                    if step in steps:
                        self.pad(pad, 110 if step % 4 == 0 else 80)

    def play(self, on):
        self.playing, self.clock, self.step = on, 0.0, -1

    # -- sending ----------------------------------------------------------------------------------
    def send(self, *message):
        self.log = ([" ".join(f"{b:02X}" for b in message)] + self.log)[:6]
        if self.midi_out:
            try:
                self.engine.send_midi(message)
            except Exception as error:  # the port went away
                self.log.insert(0, f"MIDI out: {error}")
                self.midi_out = False

    def toggle_midi_out(self, on):
        if on:
            try:
                self.engine.open_midi_output(virtual="Pyzed Controller")
            except Exception:
                try:
                    self.engine.open_midi_output()
                except Exception as error:
                    self.log.insert(0, f"no MIDI output: {error}")
                    return
        else:
            self.engine.close_midi_output()
        self.midi_out = on

    def apply_mix(self):
        any_solo = any(self.solo)
        for i in range(8):
            audible = not self.muted[i] and (self.solo[i] or not any_solo)
            bus, ch = self.buses[i // 4], i % 4 + 1
            self.engine.set(bus, f"level_{ch}", self.levels[i] if audible else 0.0)
            self.engine.set(bus, f"pan_{ch}", self.pans[i])

    def set_level(self, i, value):
        self.levels[i] = value
        self.apply_mix()
        self.send(0xB0, 70 + i, int(value * 127))  # CC 70-77: one controller per fader

    def set_pan(self, i, value):
        self.pans[i] = value
        self.apply_mix()
        self.send(0xB0, 10 + i, int((value + 1) * 63.5))  # CC 10-17: pan

    def flip(self, which, i, value):
        getattr(self, which)[i] = value
        self.apply_mix()

    def pad(self, i, velocity):
        self.drums[i].trigger()
        self.hit[i] = velocity / 127
        self.send(0x99, 36 + i, velocity)

    def note_on(self, note, velocity=100):
        self.held.add(note)
        self.engine.note_on(note, velocity)
        self.send(0x90, note, velocity)

    def note_off(self, note):
        self.held.discard(note)
        self.engine.note_off(note)
        self.send(0x80, note, 0)

    def set_bend(self, value):
        self.bend = value
        self.engine.pitch_bend(value)
        raw = int((value + 1) * 8191.5)
        self.send(0xE0, raw & 0x7F, raw >> 7)

    def set_mod(self, value):
        self.mod = value
        self.engine.set(self.filter, "cutoff", 400 + 6000 * value)
        self.send(0xB0, 1, int(value * 127))

    # -- view -------------------------------------------------------------------------------------
    def strip(self, i):
        name, _sound, _tune = SOUNDS[i]
        color = COLORS[i]
        meter = min(1.0, self.hit[i] * self.levels[i]) if not self.muted[i] else 0.0
        return pz.container(pz.column([
            pz.text(name, size=10, weight="bold", color=color),
            au.Knob(value=self.pans[i], min=-1, max=1, bipolar=True, caption="Pan", show_value=False,
                    variant="fl", diameter=34, color=color, on_change=lambda e: self.set_pan(i, e.value),
                    key=f"pan{i}"),
            au.Fader(value=self.levels[i], length=150, variant="fl", color=color, level=meter, show_value=False,
                     on_change=lambda e: self.set_level(i, e.value), key=f"fader{i}"),
            pz.row([
                au.LedButton(text="M", on=self.muted[i], color="warning",
                             on_toggle=lambda e: self.flip("muted", i, e.value), key=f"m{i}"),
                au.LedButton(text="S", on=self.solo[i], color="info",
                             on_toggle=lambda e: self.flip("solo", i, e.value), key=f"s{i}"),
            ], spacing=4),
        ], spacing=8, align="center"), padding=8, bg="#202226", radius=6)

    def view(self):
        th = self.resolved_theme()
        transport = pz.row([
            au.LedButton(text="PLAY", icon_name="play", on=self.playing, color="success",
                         on_toggle=lambda e: self.play(e.value)),
            au.LedButton(text="REC", on=self.recording, color="error", variant="round",
                         on_toggle=lambda e: setattr(self, "recording", e.value)),
            au.LedButton(text="MIDI OUT", on=self.midi_out, color="#b26cf0",
                         on_toggle=lambda e: self.toggle_midi_out(e.value)),
        ], spacing=8)
        header = pz.row([pz.text("PYZED CONTROLLER", size=18, weight="bold"), pz.space(width="fill"), transport],
                        align="center")
        strips = pz.row([self.strip(i) for i in range(8)], spacing=8)
        pads = pz.column([
            pz.row([au.Pad(text=SOUNDS[i][0], color=COLORS[i], lit=self.hit[i] > 0.5, width=70, height=58,
                           on_press=lambda e, i=i: self.pad(i, e.value), key=f"pad{i}")
                    for i in range(r * 4, r * 4 + 4)], spacing=8)
            for r in range(2)
        ], spacing=8)
        wheels = pz.row([
            au.Fader(value=self.bend, min=-1, max=1, default=0, length=140, variant="console", ticks=3,
                     caption="Pitch", show_value=False, on_change=lambda e: self.set_bend(e.value), key="bend"),
            au.Fader(value=self.mod, length=140, variant="console", ticks=5, caption="Mod", show_value=False,
                     on_change=lambda e: self.set_mod(e.value), key="mod"),
        ], spacing=6)
        log = pz.container(pz.column([pz.text("MIDI", size=10, weight="bold", color=th.text_muted)] +
                                     [pz.text(line, size=11, font="mono", color=th.text) for line in self.log],
                                     spacing=3), width=150, height=150, padding=8, bg="#0f1012", radius=6)
        right = pz.column([pads, pz.row([wheels, log], spacing=12)], spacing=12)
        piano = au.Piano(start=48, octaves=3, pressed=sorted(self.held), key_width=24, height=96, color="#ff9f3d",
                         on_note_on=lambda e: self.note_on(e.value.note, e.value.velocity),
                         on_note_off=lambda e: self.note_off(e.value))
        return pz.container(pz.column([header, pz.row([strips, right], spacing=14), piano], spacing=14),
                            padding=18, bg="#1b1c20", width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Controller)
