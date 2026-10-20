"""A drum machine like FL Studio's channel rack: a step grid, a pad per sound, tempo and swing.

    python examples/audio/drum_machine.py

The rhythm runs inside the audio engine, not in Python: a clock module drives one sequencer per
row, whose gates strike that row's drum, so the timing is sample-accurate however busy the window
is. The grid only switches the sequencers' gates; the playhead reads the step they are on.
"""

import pyzed as pz
from pyzed import audio, ui

au = ui.audio

ROWS = [
    ("Kick", "kick", 0, "#ff9f3d", "x...x...x...x.x."),
    ("Snare", "snare", 0, "#ff6b9d", "....x.......x..."),
    ("Clap", "clap", 0, "#f5d547", "....x.......x..x"),
    ("Closed hat", "hihat", 0, "#3dd68c", "x.x.x.x.x.x.x.x."),
    ("Open hat", "hihat", -5, "#2fd3d3", "..x...x...x...x."),
    ("Tom", "tom", 0, "#4fc3f7", "...........x.x.."),
]


class DrumMachine(pz.App):
    title = "Drum machine"
    size = (980, 520)

    def __init__(self, engine=None):
        self.engine = engine or audio.Engine()
        e = self.engine
        self.clock = e.add("clock", bpm=124, division="1/16")
        self.mix = [e.add("mixer"), e.add("mixer")]
        self.master = e.add("mixer", level_1=1.0, level_2=1.0)
        self.comp = e.add("compressor", threshold=-14, ratio=3, makeup=3)
        self.out = e.add("audio_out", volume=0.8)
        self.drums, self.seqs = [], []
        self.pattern = []
        for i, (_name, sound, tune, _color, steps) in enumerate(ROWS):
            drum = e.add("drum", sound=sound, tune=tune)
            seq = e.add("sequencer", steps=16, gate_length=0.25)
            e.connect(self.clock, "clock", seq, "clock")
            e.connect(seq, "trigger", drum, "trigger")
            e.connect(drum, "out", self.mix[i // 4], f"in_{i % 4 + 1}")
            self.drums.append(drum)
            self.seqs.append(seq)
            self.pattern.append([c == "x" for c in steps])
        e.connect(self.mix[0], "left", self.master, "in_1")
        e.connect(self.mix[1], "left", self.master, "in_2")
        e.connect(self.master, "left", self.comp, "in")
        e.connect(self.comp, "out", self.out, "left")
        e.connect(self.comp, "out", self.out, "right")
        self.volumes = [0.8] * len(ROWS)
        self.lit = [0.0] * len(ROWS)
        self.last_step = -1
        self.write_pattern(self.pattern)
        self.set_running(True)

    def on_start(self):
        if self.engine.backend != "offline":
            self.engine.start()

    def subscriptions(self):
        return [pz.frames(self.tick)]

    def tick(self, dt):
        step = self.current()
        self.lit = [max(0.0, v - dt * 4) for v in self.lit]
        if step != self.last_step and step >= 0:
            self.last_step = step
            for r, row in enumerate(self.pattern):
                if row[step]:
                    self.lit[r] = 1.0

    # -- the engine ---------------------------------------------------------------------------------
    def write_pattern(self, pattern):
        self.pattern = [list(map(bool, row)) for row in pattern]
        for seq, row in zip(self.seqs, self.pattern):
            for i, on in enumerate(row, start=1):
                self.engine.set(seq, f"gate_{i}", 1.0 if on else 0.0)

    def current(self):
        return int(self.seqs[0].state.get("step", -1))

    def set_running(self, on):
        self.running = on
        self.engine.set(self.clock, "run", 1 if on else 0)

    def set_volume(self, row, value):
        self.volumes[row] = value
        self.engine.set(self.mix[row // 4], f"level_{row % 4 + 1}", value)

    def hit(self, row):
        self.drums[row].trigger()
        self.lit[row] = 1.0

    # -- view ---------------------------------------------------------------------------------------
    def view(self):
        th = self.resolved_theme()
        bpm = self.engine.get(self.clock, "bpm")
        swing = self.engine.get(self.clock, "swing")
        top = pz.row([
            pz.text("DRUM MACHINE", size=18, weight="bold"),
            pz.space(width="fill"),
            au.LedButton(text="PLAY" if not self.running else "STOP", on=self.running, color="success",
                         icon_name="play" if not self.running else "square",
                         on_toggle=lambda e: self.set_running(e.value)),
            au.Knob(value=bpm, min=60, max=180, step=1, caption="Tempo", unit="BPM", variant="fl", diameter=40,
                    color="#ff9f3d", on_change=lambda e: self.engine.set(self.clock, "bpm", e.value), key="bpm"),
            au.Knob(value=swing, min=0, max=0.5, caption="Swing", unit="%", variant="fl", diameter=40,
                    color="#ff9f3d", on_change=lambda e: self.engine.set(self.clock, "swing", e.value),
                    key="swing"),
        ], spacing=14, align="center")
        volumes = pz.column([
            au.Knob(value=self.volumes[r], caption="", show_value=False, variant="fl", diameter=26,
                    color=ROWS[r][3], on_change=lambda e, r=r: self.set_volume(r, e.value), key=f"vol{r}")
            for r in range(len(ROWS))
        ], spacing=4)
        grid = au.StepSequencer(pattern=self.pattern, labels=[r[0] for r in ROWS], current=self.current(),
                                color="#ff9f3d", cell=30, on_change=lambda e: self.write_pattern(e.value))
        pads = pz.row([au.Pad(text=name.upper(), color=color, lit=self.lit[r] > 0.4, width=86, height=64,
                              on_press=lambda e, r=r: self.hit(r), key=f"pad{r}")
                       for r, (name, _s, _t, color, _p) in enumerate(ROWS)], spacing=8)
        rms, peak = self.engine.level()
        body = pz.row([volumes, grid, au.VuMeter(level=[rms, peak], length=180, thickness=10)], spacing=10,
                      align="center")
        return pz.container(pz.column([top, body, pads,
                                       pz.text("Click or drag on the grid to write the beat; the pads play "
                                               "each sound.", size=11, color=th.text_muted)], spacing=16),
                            padding=18, bg="#1b1c20", width="fill", height="fill")


if __name__ == "__main__":
    pz.run(DrumMachine)
