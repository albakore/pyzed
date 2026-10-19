"""Breakout: a paddle, a ball and a wall of bricks, running at the display's frame rate.

    python examples/games/breakout.py

Move with the mouse or the arrows/A-D, Space launches the ball, P pauses, Enter starts
again. Shows ``pz.frames`` (a callback per frame with the elapsed time), ``pz.pressed``
for keys held down, ball-against-box collisions with ``game.circle_rect``, particles and
screen shake from ``pyzed.game``.
Tutorial: https://albakore.github.io/pyzed/games/breakout/
"""

import math
import random

import pyzed as pz
from pyzed import draw, game, ui

W, H = 640, 480
PADDLE_W, PADDLE_H, PADDLE_Y = 96, 12, H - 40
BALL_R = 7
BRICK_COLS, BRICK_ROWS = 10, 6
BRICK_W, BRICK_H, BRICK_GAP, BRICK_TOP = 58, 20, 4, 56
ROW_COLORS = ["#d07277", "#dfa067", "#e5c07b", "#a1c181", "#6eb4bf", "#74ade8"]


class Breakout(pz.App):
    title = "Breakout"
    size = (W + 32, H + 92)
    theme = "One Dark"

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.sparks = game.Particles(gravity=420, drag=1.5, seed=seed)
        self.shake = game.Shake(seed=seed)
        self.best = 0
        self.new_game()

    # -- state ----------------------------------------------------------------
    def new_game(self):
        self.level, self.score, self.lives = 1, 0, 3
        self.over = self.won = self.paused = False
        self.build_level()

    def build_level(self):
        left = (W - (BRICK_COLS * (BRICK_W + BRICK_GAP) - BRICK_GAP)) / 2
        self.bricks = []
        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                rect = game.Rect(left + col * (BRICK_W + BRICK_GAP), BRICK_TOP + row * (BRICK_H + BRICK_GAP),
                                 BRICK_W, BRICK_H)
                # Top rows are worth more and, from level 2, take two hits.
                hits = 2 if self.level > 1 and row < self.level - 1 else 1
                self.bricks.append({"rect": rect, "color": ROW_COLORS[row], "hits": hits,
                                    "points": (BRICK_ROWS - row) * 10})
        self.paddle_x = W / 2
        self.reset_ball()

    def reset_ball(self):
        self.stuck = True  # the ball rides on the paddle until Space
        self.ball_x, self.ball_y = self.paddle_x, PADDLE_Y - BALL_R - 1
        self.vx = self.vy = 0.0
        self.speed = 330 + 30 * self.level
        self.combo = 0

    def launch(self):
        if self.stuck and not (self.over or self.won):
            angle = math.radians(self.random.uniform(-120, -60))
            self.vx, self.vy = math.cos(angle) * self.speed, math.sin(angle) * self.speed
            self.stuck = False

    @property
    def paddle(self):
        return game.Rect(self.paddle_x - PADDLE_W / 2, PADDLE_Y, PADDLE_W, PADDLE_H)

    # -- the loop -------------------------------------------------------------
    def subscriptions(self):
        return [pz.frames(self.tick)]  # particles keep moving even when paused

    def tick(self, dt):
        self.sparks.update(dt)
        self.shake.update(dt)
        if self.paused or self.over or self.won:
            return
        move = game.axis(("left", "a"), ("right", "d"))
        self.paddle_x = game.clamp(self.paddle_x + move * 520 * dt, PADDLE_W / 2, W - PADDLE_W / 2)
        if self.stuck:
            self.ball_x = self.paddle_x
            return
        # Small sub-steps so a fast ball can't jump through a brick in one frame.
        steps = max(1, math.ceil(self.speed * dt / BALL_R))
        for _ in range(steps):
            if self.advance(dt / steps):
                break

    def advance(self, dt):
        """Moves the ball once; returns True when it was lost."""
        self.ball_x += self.vx * dt
        self.ball_y += self.vy * dt
        if self.ball_x < BALL_R or self.ball_x > W - BALL_R:
            self.vx = -self.vx
            self.ball_x = game.clamp(self.ball_x, BALL_R, W - BALL_R)
        if self.ball_y < BALL_R:
            self.vy = abs(self.vy)
        if self.ball_y > H + BALL_R:
            self.lose_life()
            return True
        if self.vy > 0 and game.circle_rect(self.ball_x, self.ball_y, BALL_R, self.paddle):
            # Where it hits the paddle decides the angle: the edges send it sideways.
            offset = (self.ball_x - self.paddle_x) / (PADDLE_W / 2)
            angle = math.radians(-90 + 60 * game.clamp(offset, -1, 1))
            self.vx, self.vy = math.cos(angle) * self.speed, math.sin(angle) * self.speed
            self.combo = 0
            self.sparks.burst(self.ball_x, PADDLE_Y, count=6, color="#dce0e5", speed=(40, 120),
                              angle=-90, spread=120, life=(0.15, 0.3))
        for brick in self.bricks:
            normal = game.circle_rect(self.ball_x, self.ball_y, BALL_R, brick["rect"])
            if normal:
                self.hit(brick, normal)
                break
        return False

    def hit(self, brick, normal):
        nx, ny = normal
        if nx:
            self.vx = abs(self.vx) * nx
        if ny:
            self.vy = abs(self.vy) * ny
        brick["hits"] -= 1
        cx, cy = brick["rect"].center
        if brick["hits"] > 0:
            self.sparks.burst(cx, cy, count=8, color="#ffffff", speed=(40, 120), life=(0.15, 0.35))
            return
        self.bricks.remove(brick)
        self.combo += 1
        self.score += brick["points"] * self.combo
        self.sparks.burst(cx, cy, count=22, color=[brick["color"], "#ffffff"], life=(0.4, 0.9))
        self.shake.kick(2 + min(self.combo, 6))
        self.speed = min(self.speed + 4, 640)
        if not self.bricks:
            self.level += 1
            if self.level > 3:
                self.won = True
                self.best = max(self.best, self.score)
            else:
                self.build_level()

    def lose_life(self):
        self.lives -= 1
        self.shake.kick(14)
        self.sparks.burst(self.ball_x, H - 4, count=40, color=["#d07277", "#dfa067"], angle=-90, spread=90,
                          speed=(120, 380))
        if self.lives <= 0:
            self.over = True
            self.best = max(self.best, self.score)
        self.reset_ball()

    # -- input ----------------------------------------------------------------
    def on_key(self, combo):
        if combo == "space":
            self.launch()
        elif combo == "p" and not (self.over or self.won):
            self.paused = not self.paused
        elif combo == "enter" and (self.over or self.won):
            self.new_game()

    def mouse(self, x, y):
        if not self.paused:
            self.paddle_x = game.clamp(x, PADDLE_W / 2, W - PADDLE_W / 2)

    # -- drawing --------------------------------------------------------------
    def scene(self, t):
        shapes = [draw.background("#101216"), *self.shake.shapes()]
        for brick in self.bricks:
            r = brick["rect"]
            shapes.append(r.shape(fill=brick["color"], radius=4))
            if brick["hits"] > 1:  # armored: a lighter inner plate
                shapes.append(draw.rect(r.x + 4, r.y + 4, r.w - 8, r.h - 8, radius=3, fill="#ffffff55"))
            shapes.append(draw.rect(r.x, r.y, r.w, 4, radius=2, fill="#ffffff33"))  # highlight
        p = self.paddle
        shapes += game.glow(p.center[0], p.center[1], 10, t.accent, layers=3, strength=0.35, core=False)
        shapes.append(p.shape(fill=t.accent, radius=PADDLE_H / 2))
        shapes += self.sparks.shapes(glow=True)
        shapes += game.glow(self.ball_x, self.ball_y, BALL_R, "#ffffff", layers=3, strength=0.6)
        return pz.canvas(shapes, width=W, height=H, on_move=self.mouse, on_press=lambda x, y: self.launch(),
                         cursor="crosshair")

    def banner(self):
        if self.over:
            text, hint = "Game over", "Enter plays again"
        elif self.won:
            text, hint = "You cleared every level!", "Enter plays again"
        elif self.paused:
            text, hint = "Paused", "P continues"
        elif self.stuck:
            text, hint = f"Level {self.level}", "Space or click to launch"
        else:
            return None
        card = pz.container(pz.column([ui.heading(text, level=2), ui.muted(hint)], spacing=6, align="center"),
                            padding=(16, 28)).style(glass=True, radius=12, border=(1, "border"))
        return pz.container(card, width="fill", height="fill", align_x="center", align_y="center",
                            padding=(220, 0, 0, 0))

    def view(self):
        t = self.resolved_theme()
        hearts = pz.row([pz.icon("heart", size=15, color="#d07277" if i < self.lives else t.border)
                         for i in range(3)], spacing=3)
        hud = pz.row([
            ui.label("Breakout", weight="semibold"),
            ui.badge(f"Level {self.level}", tint="text_muted"),
            pz.hspace(),
            ui.badge(f"x{self.combo} combo", tint="warning", icon="zap") if self.combo > 1 else None,
            ui.badge(f"{self.score:,}", icon="star"),
            ui.badge(f"Best {self.best:,}", tint="text_muted", icon="trophy"),
            hearts,
        ], spacing=8, align="center")
        board = pz.stack([self.scene(t), self.banner()], width=W, height=H)
        return pz.container(pz.column([hud, pz.container(board, radius=10, clip=True),
                                       ui.muted("Mouse or ←/→ moves · Space launches · P pauses", size="sm")],
                                      spacing=10),
                            padding=16, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(Breakout)
