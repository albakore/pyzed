"""Orb Rush: a title screen, a HUD, a pause menu and a settings screen around a small game.

    python examples/games/menus.py

Up/Down (or W/S) choose, Enter confirms, Escape (or P) pauses and goes back. In the game,
arrows or WASD fly; collect the blue orbs and dodge the red mines. Shows the parts of a game
that are not the game itself:

- **Scenes**: one ``scene`` attribute (``"title"``, ``"play"``, ``"pause"``, ``"settings"``,
  ``"over"``) decides what ``tick`` updates and what ``view`` shows.
- **Transitions**: every scene change restarts a clock; panels fade and slide in from it
  (``.style(opacity=..., translate=...)``) and menu items follow one after another.
- **Menus that work with the keyboard and the mouse**: a selected index for the keys,
  ``ui.button`` for clicks.
- **A HUD** of widgets (score with bloom, a health bar, a timer, an FPS counter) and a
  **settings screen** with ``ui.slider``, ``ui.switch`` and ``ui.segmented`` whose values the
  game reads.

Tutorial: https://albakore.github.io/pyzed/games/menus-hud/
"""

import math
import random

import pyzed as pz
from pyzed import draw, game, ui

W, H = 720, 460
FADE = 0.35                          # seconds a scene takes to come in
NEON = {"cyan": "#22d3ee", "pink": "#f472b6", "violet": "#a78bfa", "red": "#f87171", "amber": "#fbbf24"}
DIFFICULTY = {"Easy": 0.7, "Normal": 1.0, "Hard": 1.45}
#: The menu of each scene: (label, action) pairs.
MENUS = {
    "title": [("Play", "play"), ("Settings", "settings"), ("Quit", "quit")],
    "pause": [("Resume", "resume"), ("Settings", "settings"), ("Main menu", "menu")],
    "over": [("Play again", "play"), ("Main menu", "menu")],
    "settings": [("Back", "back")],
}


def ease_out(t):
    return 1 - (1 - t) ** 3


class OrbRush(pz.App):
    title = "Orb Rush"
    size = (W + 32, H + 32)
    theme = "Pyzed Dark"

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.held = None                    # the keys held down; None reads the keyboard
        self.settings = {"music": 0.6, "effects": 0.8, "difficulty": "Normal", "shake": True, "fps": False}
        self.stars = [(self.random.uniform(0, W), self.random.uniform(0, H), self.random.choice((1, 2, 3)))
                      for _ in range(110)]
        self.sparks = game.Particles(drag=1.5, seed=seed)
        self.shake = game.Shake(seed=seed)
        self.clock, self.fps = 0.0, 60.0
        self.best = 0
        self.reset_round()
        self.go("title")

    # -- scenes -----------------------------------------------------------------------------
    def go(self, scene):
        """Switches scene and restarts the transition clock."""
        if scene == "settings":
            self.came_from = self.scene
        self.scene = scene
        self.since = 0.0                     # seconds since this scene started: drives every transition
        self.selected = 0

    def choose(self, action):
        if action == "play":
            self.reset_round()
            self.go("play")
        elif action == "resume":
            self.go("play")
        elif action == "settings":
            self.go("settings")
        elif action == "back":
            self.go(self.came_from)
        elif action == "menu":
            self.go("title")
        elif action == "quit":
            return self.close()

    def reset_round(self):
        self.x, self.y = W / 2, H - 80
        self.orbs, self.mines = [], []
        self.score, self.health, self.time = 0, 3, 0.0
        self.spawn = 0.0

    # -- input ------------------------------------------------------------------------------
    def on_key(self, combo):
        if self.scene == "play":
            if combo in ("escape", "p"):
                self.go("pause")
            return None
        if combo in ("escape", "p") and self.scene == "pause":
            return self.go("play")
        if combo == "escape" and self.scene == "settings":
            return self.go(self.came_from)
        items = MENUS[self.scene]
        if combo in ("down", "s"):
            self.selected = (self.selected + 1) % len(items)
        elif combo in ("up", "w"):
            self.selected = (self.selected - 1) % len(items)
        elif combo in ("enter", "space"):
            return self.choose(items[self.selected][1])
        return None

    # -- update -----------------------------------------------------------------------------
    def subscriptions(self):
        return [pz.frames(self.tick)]       # the stars move in every scene

    def tick(self, dt):
        dt = min(dt, 1 / 30)
        self.clock += dt
        self.since += dt
        self.fps = game.lerp(self.fps, 1 / max(dt, 1e-3), 0.1)    # smoothed, so the number is readable
        self.stars = [(x, (y + 18 * layer * dt * (3 if self.scene == "play" else 1)) % H, layer)
                      for x, y, layer in self.stars]
        self.sparks.update(dt)
        self.shake.update(dt)
        if self.scene == "play":             # the game only runs in its scene: pausing is free
            self.play(dt)

    def play(self, dt):
        self.time += dt
        speed = DIFFICULTY[self.settings["difficulty"]]
        dx, dy = game.vector(held=self.held)
        self.x = game.clamp(self.x + dx * 320 * dt, 16, W - 16)
        self.y = game.clamp(self.y + dy * 320 * dt, 80, H - 16)
        self.spawn -= dt
        if self.spawn <= 0:
            self.spawn = 0.45 / speed
            kind = self.mines if self.random.random() < 0.35 else self.orbs
            kind.append([self.random.uniform(20, W - 20), -20.0])
        for item in self.orbs + self.mines:
            item[1] += 170 * speed * dt
        for orb in self.orbs[:]:
            if math.hypot(orb[0] - self.x, orb[1] - self.y) < 24:
                self.orbs.remove(orb)
                self.score += 10
                self.sparks.burst(orb[0], orb[1], count=14, color=[NEON["cyan"], "#e0fbff"])
        for mine in self.mines[:]:
            if math.hypot(mine[0] - self.x, mine[1] - self.y) < 24:
                self.mines.remove(mine)
                self.health -= 1
                self.sparks.burst(mine[0], mine[1], count=30, color=[NEON["red"], NEON["amber"]], speed=(80, 300))
                if self.settings["shake"]:
                    self.shake.kick(10)
                if self.health <= 0:
                    self.best = max(self.best, self.score)
                    self.go("over")
        self.orbs = [o for o in self.orbs if o[1] < H + 20]
        self.mines = [m for m in self.mines if m[1] < H + 20]

    # -- transitions ------------------------------------------------------------------------
    def appear(self, delay=0.0):
        """0 -> 1 over FADE seconds, ``delay`` seconds after the scene started."""
        return ease_out(game.clamp((self.since - delay) / FADE, 0.0, 1.0))

    def slide_in(self, widget, delay=0.0, distance=24):
        a = self.appear(delay)
        return widget.style(opacity=a, translate=(0, (1 - a) * distance))

    # -- draw -------------------------------------------------------------------------------
    def world(self):
        shapes = [draw.background("#070817"), *self.shake.shapes()]
        for x, y, layer in self.stars:
            shapes.append(draw.circle(x, y, layer * 0.6, fill=game.rgba("#c7d2fe", 0.25 * layer)))
        if self.scene != "title":
            for x, y in self.orbs:
                shapes += game.glow(x, y, 7, NEON["cyan"], layers=3, strength=0.5)
            for x, y in self.mines:
                spikes = [(x + math.cos(a) * (13 if i % 2 else 7), y + math.sin(a) * (13 if i % 2 else 7))
                          for i, a in enumerate(i * math.pi / 6 + self.clock * 3 for i in range(12))]
                shapes += game.glow(x, y, 6, NEON["red"], layers=2, strength=0.3, core=False)
                shapes.append(draw.polygon(spikes, fill=NEON["red"]))
            if self.scene != "over":
                shapes += game.glow(self.x, self.y, 12, NEON["violet"], layers=4, strength=0.4)
        shapes += self.sparks.shapes(glow=True)
        return pz.canvas(shapes, width=W, height=H)

    def title_text(self, text, color, size=48):
        return pz.container(pz.text(text, size=size, weight="bold", color="#ffffff"), padding=(4, 16)).style(
            bloom=(color, 0.9), border_width=0, shadow=("#00000000", (0, 0), 0))

    def menu(self, delay=0.15):
        """The current scene's menu: a button per item, the selected one solid, each sliding in a little later."""
        items = []
        for i, (label, action) in enumerate(MENUS[self.scene]):
            selected = i == self.selected
            button = ui.button(label, lambda a=action: self.choose(a), variant="solid" if selected else "ghost",
                               full_width=True, icon="chevron-right" if selected else None)
            items.append(self.slide_in(pz.container(button, width=220), delay + i * 0.06, 16))
        return pz.column(items, spacing=6, align="center")

    def panel(self, content, delay=0.0):
        card = pz.container(content, padding=(24, 32)).style(glass=True, radius=16, border=(1, "#ffffff22"))
        return pz.container(self.slide_in(card, delay, 30), width="fill", height="fill", align_x="center",
                            align_y="center")

    def hud(self):
        bits = [
            self.title_text(f"{self.score:05d}", NEON["cyan"], size=22),
            pz.hspace(),
            pz.row([pz.icon("heart", size=14, color=NEON["red"]),
                    pz.container(ui.progress(self.health, max=3, tint=NEON["red"], height=6), width=90)],
                   spacing=6, align="center"),
            ui.badge(f"{self.time:4.1f} s", icon="timer", tint="text_muted"),
            ui.badge(f"{self.fps:.0f} fps", icon="gauge", tint="success") if self.settings["fps"] else None,
            pz.row([ui.kbd("Esc"), ui.muted("pause", size="sm")], spacing=4, align="center"),
        ]
        bar = pz.container(pz.row(bits, spacing=10, align="center"), padding=(6, 14)).style(
            glass=True, radius=12, border=(1, "#ffffff1f"))
        a = self.appear()
        return pz.container(bar.style(opacity=a, translate=(0, -(1 - a) * 40)), padding=12, width="fill")

    def settings_panel(self):
        s = self.settings

        def setter(key):
            return lambda value: s.__setitem__(key, value)

        rows = [
            ui.field("Music", pz.container(ui.slider(s["music"], setter("music"), show_value=True), width=180)),
            ui.field("Effects", pz.container(ui.slider(s["effects"], setter("effects"), show_value=True), width=180)),
            ui.field("Difficulty", ui.segmented(list(DIFFICULTY), s["difficulty"], setter("difficulty"), size="sm")),
            ui.field("Screen shake", ui.switch(s["shake"], setter("shake"))),
            ui.field("Show FPS", ui.switch(s["fps"], setter("fps"))),
        ]
        body = pz.column([
            ui.heading("Settings", level=2),
            *[self.slide_in(r, 0.08 + i * 0.05, 12) for i, r in enumerate(rows)],
            self.menu(0.4),
        ], spacing=10, width=380)
        return self.panel(body)

    def overlay(self):
        if self.scene == "title":
            pulse = 0.85 + 0.15 * math.sin(self.clock * 2.5)
            body = pz.column([
                self.slide_in(self.title_text("ORB RUSH", NEON["violet"]).style(scale=pulse), 0.0, -30),
                self.slide_in(ui.muted("Collect the orbs. Dodge the mines."), 0.08, 12),
                pz.vspace(12),
                self.menu(),
                self.slide_in(ui.muted(f"Best {self.best}", size="sm"), 0.4, 8),
            ], spacing=6, align="center")
            return pz.container(body, width="fill", height="fill", align_x="center", align_y="center")
        if self.scene == "play":
            return self.hud()
        if self.scene == "pause":
            body = pz.column([ui.heading("Paused", level=2), ui.muted(f"Score {self.score}"), self.menu()],
                             spacing=10, align="center")
            return pz.stack([self.hud(), pz.container(width="fill", height="fill").style(
                background=game.rgba("#000000", 0.35 * self.appear())), self.panel(body)], width=W, height=H)
        if self.scene == "settings":
            return self.settings_panel()
        body = pz.column([self.title_text("GAME OVER", NEON["pink"], size=34),
                          ui.muted(f"Score {self.score}  ·  best {self.best}"), self.menu()],
                         spacing=10, align="center")
        return self.panel(body)

    def view(self):
        board = pz.stack([self.world(), self.overlay()], width=W, height=H)
        return pz.container(pz.container(board, radius=12, clip=True), padding=16, width="fill", height="fill",
                            bg="#05060d", align_x="center", align_y="center")


if __name__ == "__main__":
    pz.run(OrbRush)
