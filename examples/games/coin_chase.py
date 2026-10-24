"""Coin Chase: your first game. A frame loop, keys held down and a 30-second timer.

    python examples/games/coin_chase.py

Arrows or WASD move the orb, collect as many coins as you can in 30 seconds. Space pauses,
Enter plays again. Shows the three parts of every real-time game:

1. **State**: plain attributes on the app (position, score, time left).
2. **Update**: ``tick(dt)``, called by ``pz.frames`` once per displayed frame, moves things by
   *speed x dt* and checks what happened.
3. **Draw**: ``view()`` turns the state into a canvas, with the HUD as ordinary widgets.

Tutorial: https://albakore.github.io/pyzed/games/first-game/
"""

import math
import random

import pyzed as pz
from pyzed import draw, game, ui

W, H = 560, 380
SPEED = 260          # pixels per second
PLAYER_R = 14
COIN_R = 9
ROUND = 30.0         # seconds per round


class CoinChase(pz.App):
    title = "Coin Chase"
    size = (W + 32, H + 92)
    theme = "Pyzed Dark"

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        #: The keys held down; ``None`` reads the keyboard. Tests and demos set it to steer.
        self.held = None
        self.best = 0
        self.reset()

    # -- 1. state ---------------------------------------------------------------------------
    def reset(self):
        self.x, self.y = W / 2, H / 2
        self.score = 0
        self.time_left = ROUND
        self.paused = self.over = False
        self.pops = []          # [x, y, age]: rings that grow and fade where a coin was taken
        self.clock = 0.0        # seconds since the round started (for the coin's spin)
        self.coin = self.new_coin()

    def new_coin(self):
        """A coin somewhere not too close to the player."""
        while True:
            x = self.random.uniform(30, W - 30)
            y = self.random.uniform(30, H - 30)
            if math.hypot(x - self.x, y - self.y) > 120:
                return (x, y)

    # -- 2. update --------------------------------------------------------------------------
    def subscriptions(self):
        # No frames while paused or over: the game stops and so does the CPU.
        if self.paused or self.over:
            return []
        return [pz.frames(self.tick)]

    def tick(self, dt):
        self.clock += dt
        self.time_left = max(0.0, self.time_left - dt)

        # Move by speed x dt: the same speed at 60, 120 or 144 frames per second.
        dx, dy = game.vector(held=self.held)          # arrows / WASD, diagonals normalized
        self.x = game.clamp(self.x + dx * SPEED * dt, PLAYER_R, W - PLAYER_R)
        self.y = game.clamp(self.y + dy * SPEED * dt, PLAYER_R, H - PLAYER_R)

        # Two circles touch when the distance between centers is less than the radii added.
        cx, cy = self.coin
        if math.hypot(cx - self.x, cy - self.y) < PLAYER_R + COIN_R:
            self.score += 1
            self.pops.append([cx, cy, 0.0])
            self.coin = self.new_coin()

        for pop in self.pops:
            pop[2] += dt
        self.pops = [p for p in self.pops if p[2] < 0.4]

        if self.time_left <= 0:
            self.over = True
            self.best = max(self.best, self.score)

    def on_key(self, combo):
        if combo == "space" and not self.over:
            self.paused = not self.paused
        elif combo == "enter" and self.over:
            self.reset()

    # -- 3. draw ----------------------------------------------------------------------------
    def board(self):
        shapes = [draw.background("#0b0e14")]
        for gx in range(0, W, 40):                    # a faint grid, to feel the motion
            shapes.append(draw.line(gx, 0, gx, H, stroke="#ffffff08"))
        for gy in range(0, H, 40):
            shapes.append(draw.line(0, gy, W, gy, stroke="#ffffff08"))

        cx, cy = self.coin
        spin = abs(math.cos(self.clock * 4))         # squash the coin's width: it seems to spin
        shapes += game.glow(cx, cy, COIN_R * 0.6, "#fbbf24", layers=3, strength=0.5, core=False)
        shapes.append(draw.path([("M", cx, cy - COIN_R)] + [
            ("L", cx + math.sin(a) * COIN_R * max(spin, 0.15), cy - math.cos(a) * COIN_R)
            for a in (i * math.pi / 8 for i in range(1, 17))], fill="#fbbf24", stroke="#fde68a", width=1.5))

        for x, y, age in self.pops:
            k = age / 0.4                             # 0 -> 1 over the ring's life
            shapes.append(draw.circle(x, y, COIN_R + k * 26, stroke=game.rgba("#fde68a", 1 - k), width=3))

        shapes += game.glow(self.x, self.y, PLAYER_R, "#22d3ee", layers=4, strength=0.5)
        return pz.canvas(shapes, width=W, height=H)

    def overlay(self):
        if self.over:
            title, lines = "Time!", [f"{self.score} coins  ·  best {self.best}", "Enter plays again"]
        elif self.paused:
            title, lines = "Paused", ["Space continues"]
        else:
            return None
        card = pz.container(pz.column([ui.heading(title, level=2), *[ui.muted(t) for t in lines]],
                                      spacing=8, align="center"), padding=(20, 32)).style(glass=True, radius=14)
        return pz.container(card, width="fill", height="fill", align_x="center", align_y="center")

    def view(self):
        t = self.resolved_theme()
        hud = pz.row([
            ui.label("Coin Chase", weight="semibold"),
            pz.hspace(),
            ui.badge(f"{self.score} coins", icon="circle-dollar-sign", tint="warning"),
            ui.badge(f"{math.ceil(self.time_left)} s", icon="timer",
                     tint="error" if self.time_left < 5 else "accent"),
            ui.badge(f"Best {self.best}", icon="trophy", tint="text_muted"),
        ], spacing=8, align="center")
        play = pz.stack([self.board(), self.overlay()], width=W, height=H)
        return pz.container(pz.column([hud, pz.container(play, radius=10, clip=True),
                                       ui.muted("Arrows / WASD move · Space pauses · Enter restarts", size="sm")],
                                      spacing=10),
                            padding=16, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(CoinChase)
