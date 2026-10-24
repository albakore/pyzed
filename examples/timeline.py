"""Timeline animations with ``pz.AnimationPlayer``, like Godot's AnimationPlayer.

    python examples/timeline.py

- ``pz.Clip`` is a timeline: ``pz.Track("card:y", {0: 40, 0.5: 0})`` changes one property
  of the widgets that play the ``card`` target, key by key; ``":score"`` changes an
  attribute of the app, so the score counts up as the clip plays.
- ``pz.Call(1.6, "chime")`` calls a method at that time.
- ``self.player["card"]`` gives a widget its target; the player plays, pauses, seeks,
  plays backwards, changes speed and queues clips (``idle`` loops after ``intro``).
- The clips could live in a ``.pzanim`` file: ``pz.AnimationLibrary(CLIPS).save(path)``
  and ``pz.AnimationPlayer("level.pzanim")``.
"""

import pyzed as pz
from pyzed import ui

GOLD = "#fbbf24"

INTRO = pz.Clip("intro", length=2.2, tracks=[
    pz.Track("card:opacity", {0: 0, 0.35: 1}),
    pz.Track("card:y", [(0, 40, "ease_out_back"), (0.5, 0)]),
    pz.Track("title:scale", [(0.3, 0.6, "ease_out_back"), (0.7, 1)]),
    pz.Track("title:opacity", {0.3: 0, 0.5: 1}),
    *(pz.Track(f"star{i}:scale", [(0.7 + i * 0.25, 0, "ease_out_back"), (1.0 + i * 0.25, 1)]) for i in range(3)),
    *(pz.Track(f"star{i}:rotate", [(0.7 + i * 0.25, -120, "ease_out_cubic"), (1.0 + i * 0.25, 0)]) for i in range(3)),
    pz.Track(":score", [(0.7, 0, "ease_out_cubic"), (1.9, 12_480)]),
    pz.Track("button:opacity", {1.8: 0, 2.2: 1}),
], calls=[pz.Call(1.6, "chime")])

IDLE = pz.Clip("idle", length=1.2, loop="pingpong", tracks=[
    pz.Track("button:scale", [(0, 1, "ease_in_out_sine"), (1.2, 1.06)]),
    pz.Track("button:glow", [(0, 6, "ease_in_out_sine"), (1.2, 22)]),
])


class Timeline(pz.App):
    title = "Timeline"
    size = (760, 560)
    theme = pz.themes.PYZED_DARK

    def __init__(self):
        self.score = 0
        self.message = ""
        self.player = pz.AnimationPlayer(INTRO, IDLE, on_finished=self.finished)
        self.replay()

    def replay(self):
        self.message = ""
        self.player.play("intro", restart=True)
        self.player.queue("idle")

    def chime(self):
        self.message = "New record!"

    def finished(self, name):
        if name == "intro":
            self.message = "New record! Press Next to continue"

    def star(self, i):
        return pz.icon("star", size=44, color=GOLD).style(bloom=(GOLD, 0.7)).animate(self.player[f"star{i}"])

    def card(self):
        content = pz.column([
            pz.text("LEVEL COMPLETE", size=30, weight="black", color="#ffffff").animate(self.player["title"]),
            pz.row([self.star(i) for i in range(3)], spacing=18),
            pz.text(f"{self.score:,.0f}", size=40, weight="bold", color=GOLD, font="mono"),
            pz.text(self.message or " ", size=13, color="#ffffffaa"),
            ui.button("Next level", self.replay, variant="accent").style(glow=("#6366f1", 6)).animate(
                self.player["button"]),
        ], spacing=16, align="center")
        return pz.container(content, width=420, align_x="center").style(
            background="#161b2e", border=(1, "#ffffff1a"), radius=20, padding=32).animate(self.player["card"])

    def controls(self):
        p = self.player
        clip = p.current or "intro"
        return pz.column([
            pz.row([
                ui.icon_button("rewind", lambda: p.play_backwards(), tooltip="Play backwards"),
                ui.icon_button("pause" if p.playing else "play", p.toggle, tooltip="Play or pause"),
                ui.icon_button("square", p.stop, tooltip="Stop"),
                ui.icon_button("rotate-ccw", self.replay, tooltip="Replay"),
                pz.text(f"{clip} · {p.position:.2f} / {p.length:.2f} s", size=12, font="mono",
                        color="#ffffff88", width=170),
                ui.slider(p.position, p.seek, min=0, max=max(p.length, 0.01), step=0.01, width="fill"),
                ui.segmented(["0.25×", "1×", "2×"], f"{p.speed:g}×", self.set_speed),
            ], spacing=8, align="center"),
        ]).style(background="#161b2e", radius=12, padding=(8, 12), width=700)

    def set_speed(self, label):
        self.player.speed = float(label.rstrip("×"))

    def view(self):
        return pz.column([
            pz.container(self.card(), width="fill", height="fill", align_x="center", align_y="center"),
            self.controls(),
        ], spacing=16, align="center", padding=24).style(background="#0b0e1a", width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Timeline)
