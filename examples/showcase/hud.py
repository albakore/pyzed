"""A game HUD: health and mana bars, a radar minimap, an ability bar and a quest tracker.

    python examples/showcase/hud.py

- The space background and the minimap's radar sweep are shader graphs made of nodes in
  Pyzed Design (``shaders/nebula.pzshad`` and ``shaders/radar.pzshad``): ``pz.shader`` runs
  them on the GPU for every pixel, every frame.
- Panels are ``glass=True`` (a tinted panel with a real backdrop blur), the ready ability
  and the level-up banner use ``bloom``, low health pulses with ``animate("glow_pulse")``.
- Press 1 to 6 (or click a slot) to cast an ability; it goes on cooldown.
"""

from pathlib import Path

import pyzed as pz

SHADERS = Path(__file__).parent / "shaders"



ABILITIES = (
    ("sword", "Slash", 2.0),
    ("flame", "Fireball", 6.0),
    ("shield", "Ward", 10.0),
    ("zap", "Chain bolt", 8.0),
    ("wind", "Dash", 4.0),
    ("sparkles", "Ultimate", 30.0),
)
QUESTS = (
    ("Reach the Sunken Gate", True),
    ("Collect 3 star shards", False),
    ("Defeat the Warden", False),
)
GOLD = "#fbbf24"
CYAN = "#22d3ee"


class Hud(pz.App):
    title = "Game HUD"
    size = (1280, 720)
    theme = pz.themes.PYZED_DARK

    def __init__(self):
        self.health = 0.28
        self.mana = 0.72
        self.cooldowns = {1: 3.0}  # slot -> seconds left
        self.casts = 0

    def subscriptions(self):
        return [pz.every(0.1, self.tick, key="cooldowns")] if self.cooldowns else []

    def tick(self):
        self.cooldowns = {slot: left - 0.1 for slot, left in self.cooldowns.items() if left > 0.1}

    def cast(self, slot):
        if slot in self.cooldowns:
            return
        self.cooldowns[slot] = ABILITIES[slot][2]
        self.mana = max(0.0, self.mana - 0.08)
        self.casts += 1

    def on_key(self, combo):
        if combo in ("1", "2", "3", "4", "5", "6"):
            self.cast(int(combo) - 1)
            return True

    # -- pieces ---------------------------------------------------------------------

    def bar(self, value, colors, glow, width=260, height=14, label=None):
        fill = pz.container(None, width=max(height, width * value), height=height).style(
            background=pz.Gradient(colors, angle=90), radius=height / 2, glow=(glow, 10))
        track = pz.container(fill, width=width, height=height).style(
            background="#ffffff14", radius=height / 2, border=(1, "#ffffff22"))
        if label is None:
            return track
        return pz.stack([track, pz.container(pz.text(label, size=10, weight="bold", color="#ffffffdd"),
                                             width=width, height=height, align_x="center", align_y="center")])

    def player(self):
        portrait = pz.container(pz.icon("swords", size=34, color="#ffffff"), width=72, height=72,
                                align_x="center", align_y="center").style(
            background=pz.Gradient(["#7c3aed", "#db2777"], angle=135), radius=36,
            border=(2, "#ffffffaa"), bloom=("#a855f7", 0.5))
        health = self.bar(self.health, ["#991b1b", "#ef4444"], "#ef4444", label=f"{round(self.health * 1840)} / 1840")
        if self.health < 0.3:
            health = health.animate("glow_pulse", repeat="infinite")
        stats = pz.column([
            pz.row([pz.text("Aria", size=18, weight="bold", color="#ffffff"),
                    pz.text("Lv 27 · Stormblade", size=12, color="#ffffffaa")], spacing=8, align="end"),
            health,
            self.bar(self.mana, ["#1d4ed8", "#38bdf8"], "#38bdf8", label=f"{round(self.mana * 960)} / 960"),
            self.bar(0.64, ["#b45309", GOLD], GOLD, height=5),
        ], spacing=6)
        return pz.row([portrait, stats], spacing=14, align="center").style(
            glass={"tint": "#0f172a", "strength": 0.35, "blur": 18}, radius=16, padding=14)

    def minimap(self):
        radar = pz.shader(SHADERS / "radar.pzshad", uniforms={"accent": "#34d399"}, width=176, height=176)
        blips = pz.stack([
            pz.container(pz.container(None, width=8, height=8).style(background="#f87171", radius=4,
                                                                     bloom=("#f87171", 1.0)),
                         width=176, height=176, padding=(46, 0, 0, 120)),
            pz.container(pz.container(None, width=8, height=8).style(background=GOLD, radius=4,
                                                                     bloom=(GOLD, 1.0)),
                         width=176, height=176, padding=(118, 0, 0, 52)),
            pz.container(pz.icon("navigation", size=16, color="#ffffff"), width=176, height=176,
                         align_x="center", align_y="center"),
        ])
        dial = pz.stack([radar, blips], width=176, height=176).style(
            radius=88, glass={"tint": "#022c22", "strength": 0.25, "blur": 14}, clip=True)
        return pz.column([
            dial,
            pz.text("Sunken Coast · 412, -88", size=11, color="#ffffffaa"),
        ], spacing=6, align="center")

    def objective(self):
        return pz.row([
            pz.icon("compass", size=16, color=GOLD),
            pz.text("Reach the Sunken Gate", size=14, weight="semibold", color="#ffffff"),
            pz.text("120 m", size=12, color="#ffffffaa"),
        ], spacing=10, align="center").style(glass={"tint": "#0f172a", "strength": 0.3}, radius=20,
                                             padding=(8, 16)).animate("fade_in_down")

    def quests(self):
        rows = [pz.text("QUESTS", size=11, weight="bold", color=GOLD)]
        for name, done in QUESTS:
            rows.append(pz.row([
                pz.icon("circle-check" if done else "circle", size=14, color="#34d399" if done else "#ffffff88"),
                pz.text(name, size=13, color="#ffffff88" if done else "#ffffff"),
            ], spacing=8, align="center"))
        return pz.column(rows, spacing=8).style(glass={"tint": "#0f172a", "strength": 0.3}, radius=14,
                                                padding=14, width=230)

    def slot(self, index):
        icon, name, cooldown = ABILITIES[index]
        left = self.cooldowns.get(index)
        ready = left is None
        face = pz.container(pz.icon(icon, size=28, color="#ffffff" if ready else "#ffffff55"), width=64,
                            height=64, align_x="center", align_y="center")
        layers = [face]
        if not ready:
            shade = 64 * left / cooldown
            layers.append(pz.container(pz.container(None, width=64, height=shade).style(background="#000000aa"),
                                       width=64, height=64, align_y="end"))
            layers.append(pz.container(pz.text(f"{left:.0f}" if left >= 1 else f"{left:.1f}", size=18,
                                               weight="bold", color="#ffffff"),
                                       width=64, height=64, align_x="center", align_y="center"))
        layers.append(pz.container(pz.text(str(index + 1), size=10, weight="bold", color="#ffffffcc"),
                                   width=64, height=64, padding=(3, 6), align_x="end"))
        style = dict(radius=12, clip=True, border=(1, "#ffffff33"))
        if ready and index == 5:
            style.update(background=pz.Gradient(["#7c2d12", "#ea580c"], angle=135), bloom=(GOLD, 0.9),
                         border=(2, GOLD))
        elif ready:
            style.update(background=pz.Gradient(["#1e293b", "#334155"], angle=135))
        else:
            style.update(background="#0f172a")
        tile = pz.stack(layers, width=64, height=64).style(**style)
        tile = pz.mouse_area(tile, on_press=lambda: self.cast(index))
        tile = tile.animate("shrink", on="press")
        if ready and index == 5:
            tile = tile.animate("pulse", repeat="infinite", duration=1400)
        return pz.column([tile, pz.text(name, size=10, color="#ffffffaa")], spacing=4, align="center")

    def abilities(self):
        return pz.row([self.slot(i) for i in range(len(ABILITIES))], spacing=10).style(
            glass={"tint": "#020617", "strength": 0.4, "blur": 16}, radius=18, padding=(12, 16, 8, 16))

    def log(self):
        lines = (
            ("You hit Tide Wraith for 312", "#ffffff"),
            ("Critical! Chain bolt 1,204", GOLD),
            ("Tide Wraith hits you for 188", "#f87171"),
            ("Ward absorbed 140 damage", CYAN),
        )
        return pz.column([pz.text(t, size=12, color=c, font="mono") for t, c in lines], spacing=4).style(
            glass={"tint": "#020617", "strength": 0.3}, radius=12, padding=12, width=300)

    def level_up(self):
        return pz.column([
            pz.text("LEVEL UP", size=40, weight="black", color="#fff7d6").style(bloom=(GOLD, 1.0)),
            pz.text("Stormblade · Level 27", size=14, color="#fde68a"),
        ], spacing=2, align="center").animate("pop_in").animate("float", repeat="infinite")

    def view(self):
        def at(widget, x, y, pad):
            return pz.container(widget, width="fill", height="fill", align_x=x, align_y=y, padding=pad)

        return pz.stack([
            pz.shader(SHADERS / "nebula.pzshad", width="fill", height="fill", fallback=pz.Gradient(["#05040f", "#2a0c46", "#0b3a4a"], angle=135)),
            at(self.player(), "start", "start", 20),
            at(self.objective(), "center", "start", 24),
            at(self.minimap(), "end", "start", 20),
            at(self.quests(), "end", "center", 20),
            at(self.level_up(), "center", "center", (0, 0, 120, 0)),
            at(self.log(), "start", "end", 20),
            at(self.abilities(), "center", "end", 20),
        ])


if __name__ == "__main__":
    pz.run(Hud)
