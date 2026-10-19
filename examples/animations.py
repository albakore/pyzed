"""Animations and effects: presets, hover and press motion, transitions, presence and glass.

    python examples/animations.py

- ``widget.animate("fade_in_up")`` plays a preset when the widget appears; ``on="hover"``,
  ``"press"``, ``"focus"``, ``"click"`` and ``"active"`` play it on events.
- ``widget.transition(opacity=...)`` animates a value whenever it changes, like CSS.
- ``pz.presence(content, key=...)`` animates content out and in when ``key`` changes.
- ``style(glass=True)``, ``glow=``, ``bloom=`` and ``opacity=`` are visual effects.
"""

import pyzed as pz
from pyzed import ui

AURORA = pz.Gradient(["#0f172a", "#312e81", "#0e7490"], angle=135)
PAGES = ("Overview", "Activity", "Settings")


class Animations(pz.App):
    title = "Animations"
    size = (980, 700)
    transition = "zoom"

    def __init__(self):
        self.page = 0
        self.panel = True
        self.errors = 0
        self.recording = False

    def toggle_panel(self):
        self.panel = not self.panel

    def next_page(self):
        self.page = (self.page + 1) % len(PAGES)

    def fail(self):
        self.errors += 1

    def toggle_recording(self):
        self.recording = not self.recording

    def tile(self, name):
        preset = pz.animation.PRESETS[name]
        on = preset.on if preset.on != "mount" else "click"
        repeat = 1 if preset.category == "loop" and on == "click" else None
        return pz.column([
            pz.text(name.replace("_", " ")).style(weight="semibold"),
            pz.text(f"{preset.category} · {on}").style(size=11, color="text_muted"),
        ], spacing=2).style(background="elevated", border=(1, "border"), radius=8, padding=(10, 12),
                           width=150).animate(name, on=on, repeat=repeat)

    def effects(self):
        card = lambda label, **style: pz.column([  # noqa: E731
            pz.text(label).style(weight="semibold", color="#ffffff"),
            pz.text(", ".join(f"{k}={v!r}" for k, v in style.items())).style(size=11, color="#ffffffaa"),
        ], spacing=4).style(padding=14, width=200, radius=12, **style)
        return pz.row([
            card("Glass", glass=True),
            card("Glow", glow=("#22d3ee", 18), background="#0b1220"),
            card("Bloom", bloom=("#f472b6", 0.8), background="#1a0b16"),
            card("Opacity", opacity=0.55, background="#0b1220", border=(1, "#ffffff33")),
        ], spacing=18).style(padding=24, background=AURORA, radius=14, width="fill")

    def view(self):
        tiles = [self.tile(n) for n in ("pulse", "shake", "bounce", "tada", "lift", "grow", "glow", "bloom",
                                        "float", "glow_pulse")]
        side = pz.column([
            pz.text("Side panel").style(weight="semibold"),
            pz.text("transition(x=..., opacity=...)").style(size=11, color="text_muted"),
        ], spacing=4).style(background="elevated", radius=8, padding=12, width=220).transition(
            x=0 if self.panel else -24, opacity=1 if self.panel else 0, duration=220, easing="ease_out_cubic")
        page = pz.presence(
            pz.text(PAGES[self.page]).style(size=20, weight="bold"),
            key=self.page, enter="fade_in_right", exit="fade_out_left", id="pages")
        controls = pz.row([
            ui.button("Toggle panel", self.toggle_panel),
            ui.button("Next page", self.next_page),
            ui.button("Wrong password", self.fail).animate("shake", key=self.errors),
            ui.button("Record" if not self.recording else "Stop", self.toggle_recording).animate(
                "glow_pulse", active=self.recording).animate("shrink"),
        ], spacing=10)
        return pz.column([
            pz.text("Animations").style(size=24, weight="bold").animate("fade_in_down"),
            pz.row(pz.stagger(tiles, "fade_in_up", step=40), spacing=10, wrap=True, line_spacing=10),
            self.effects().animate("fade_in_up", delay=200),
            controls,
            pz.row([side, page], spacing=20),
        ], spacing=18).style(padding=24, background="background", width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Animations)
