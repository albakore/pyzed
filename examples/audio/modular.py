"""A modular synthesizer like VCV Rack: modules on rails, patched with cables you drag.

    python examples/audio/modular.py [patch.json]

It opens with a small patch (a sequencer playing a bass line through a filter, an envelope, a
delay and a scope). Add modules from the browser, drag cables between jacks (outputs are on the
dark plates), right-click a jack to unplug it, drag a module by its title to move it. Ctrl+S saves
the patch and Ctrl+O opens the last one saved (modular.json next to this file).
"""

import sys
from pathlib import Path

import pyzed as pz
from pyzed import audio, ui

PATCH = Path(__file__).with_name("modular.json")


def starter_patch(engine: audio.Engine) -> None:
    """A sequenced acid bass with a delay, a scope and the output."""
    e = engine
    seq = e.add("sequencer", bpm=126, steps=16, gate_length=0.45)
    for i, semis in enumerate([0, 0, 12, 0, 3, 0, 10, 0, -2, -2, 10, -2, 5, 3, 15, 7], start=1):
        e.set(seq, f"pitch_{i}", semis)
    osc = e.add("oscillator", wave="saw", freq=65.41)
    lfo = e.add("lfo", rate=0.15, amount=0.5)
    vcf = e.add("filter", cutoff=420, resonance=0.7, cv_amount=0.5)
    env = e.add("adsr", attack=0.002, decay=0.2, sustain=0.15, release=0.1)
    vca = e.add("vca", gain=1.0)
    dly = e.add("delay", time=0.36, feedback=0.45, mix=0.3)
    scope = e.add("scope")
    out = e.add("audio_out", volume=0.7)
    e.connect(seq, "pitch", osc, "pitch")
    e.connect(seq, "gate", env, "gate")
    e.connect(osc, "saw", vcf, "in")
    e.connect(env, "out", vcf, "cutoff")
    e.connect(lfo, "out", vcf, "resonance")
    e.connect(vcf, "lowpass", vca, "in")
    e.connect(env, "out", vca, "cv")
    e.connect(vca, "out", dly, "in")
    e.connect(dly, "out", scope, "in")
    e.connect(scope, "out", out, "left")
    e.connect(scope, "out", out, "right")


class Modular(pz.App):
    title = "Modular"
    size = (1400, 860)

    def __init__(self, engine=None, path=None):
        self.engine = engine or audio.Engine()
        self.layout = {}
        self.dirty = False
        if path:
            self.layout = ui.rack.load(self.engine, path)
        else:
            starter_patch(self.engine)

    def on_start(self):
        if self.engine.backend != "offline":
            self.engine.start()

    def subscriptions(self):
        return [pz.frames(lambda dt: None)]  # cables sway and carry signal, scopes and LEDs move

    def on_key(self, combo):
        if combo == "ctrl-s":
            ui.rack.save(self.engine, self.layout, PATCH)
            self.dirty = False
        elif combo == "ctrl-o" and PATCH.exists():
            self.layout = ui.rack.load(self.engine, PATCH)
            self.dirty = False

    def view(self):
        th = self.resolved_theme()
        info = self.engine.info
        status = pz.container(pz.row([
            pz.text(f"{len(self.engine.nodes)} modules · {len(self.engine.cables)} cables", size=11,
                    color=th.text_muted),
            pz.space(width="fill"),
            pz.text(f"{info.get('backend')} · {info.get('sample_rate')} Hz · {info.get('latency_ms') or 0:.1f} ms"
                    f" · CPU {100 * (info.get('load') or 0):.0f}%" + (" · unsaved (Ctrl+S)" if self.dirty else ""),
                    size=11, color=th.text_muted, font="mono"),
        ]), padding=(4, 10), bg=th.status_bar)
        rack = ui.rack.Rack(engine=self.engine, layout=self.layout, rows=2,
                            on_change=lambda e: setattr(self, "dirty", True))
        return pz.column([rack, status], width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Modular(path=sys.argv[1] if len(sys.argv) > 1 else None))
