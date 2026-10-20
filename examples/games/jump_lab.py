"""Jump Lab: velocity, gravity, box collisions and a jump that feels good.

    python examples/games/jump_lab.py

Arrows or A/D run, Space (or Up/W) jumps, hold it to jump higher, H hides the debug view.
A box runs and jumps between platforms while three balls bounce around. The debug view
draws the hitboxes, the velocity and the trail of the last second, so you can see the jump
arc. Shows:

- **Velocity and gravity**: ``vx``/``vy`` in pixels per second; gravity adds to ``vy`` every
  frame, and the position moves by ``velocity x dt``.
- **AABB collisions** (axis-aligned bounding boxes, ``game.Rect.overlaps``), resolved one
  axis at a time so the box slides along walls and lands on floors.
- **Circle against box** with ``game.circle_rect``, which says which side was hit, to bounce.
- **Game feel**: acceleration, coyote time, jump buffering and variable jump height.

Tutorial: https://albakore.github.io/pyzed/games/collisions-physics/
"""

import random

import pyzed as pz
from pyzed import draw, game, ui

W, H = 720, 400
RUN = 250            # top running speed, px/s
ACCEL = 2200         # px/s² on the ground (how fast you reach RUN)
AIR_ACCEL = 1300     # less control in the air
GRAVITY = 1900       # px/s², added to vy every second
JUMP_SPEED = 660     # vy right after a jump (upwards, so negative)
LOW_JUMP = 2.6       # gravity multiplier while rising without the jump key: short hops
MAX_FALL = 900
COYOTE = 0.10        # seconds after leaving a ledge when a jump still works
BUFFER = 0.12        # seconds a jump press is remembered before landing
JUMP_KEYS = ("space", "up", "w")

PLATFORMS = [
    game.Rect(0, H - 36, W, 36),          # the floor
    game.Rect(120, 280, 140, 16),
    game.Rect(330, 214, 130, 16),
    game.Rect(520, 150, 150, 16),
    game.Rect(560, H - 116, 40, 80),      # a wall to bump into
    game.Rect(0, 0, 12, H), game.Rect(W - 12, 0, 12, H),   # side walls
]


class Ball:
    def __init__(self, x, y, vx, vy, r, color):
        self.x, self.y, self.vx, self.vy, self.r, self.color = x, y, vx, vy, r, color


class JumpLab(pz.App):
    title = "Jump Lab"
    size = (W + 32, H + 92)
    theme = "One Dark"

    def __init__(self, seed=None):
        rnd = random.Random(seed)
        self.held = None                     # the keys held down; None reads the keyboard
        self.debug = True
        self.player = game.Rect(60, H - 36 - 34, 26, 34)
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.coyote = 0.0                    # time left to jump after walking off a ledge
        self.buffer = 0.0                    # time left of a remembered jump press
        self.trail = []                      # the player's center, one point per frame
        self.hits = {}                       # platform index -> seconds to keep it highlighted
        self.balls = [Ball(rnd.uniform(100, 600), rnd.uniform(40, 120), rnd.choice((-1, 1)) * rnd.uniform(120, 220),
                           0.0, r, color)
                      for r, color in ((10, "#f472b6"), (14, "#a78bfa"), (8, "#34d399"))]

    # -- input ------------------------------------------------------------------------------
    def on_key(self, combo):
        if combo in JUMP_KEYS:
            self.press_jump()
        elif combo == "h":
            self.debug = not self.debug

    def press_jump(self):
        self.buffer = BUFFER                 # remember the press for a moment (jump buffering)

    # -- update -----------------------------------------------------------------------------
    def subscriptions(self):
        return [pz.frames(self.tick)]

    def tick(self, dt):
        dt = min(dt, 1 / 30)                 # big steps would let things pass through walls
        move = game.axis(("left", "a"), ("right", "d"), held=self.held)
        jump_held = game.is_pressed(*JUMP_KEYS, held=self.held)

        # Horizontal: accelerate toward the target speed instead of jumping to it.
        target = move * RUN
        accel = (ACCEL if self.on_ground else AIR_ACCEL) * dt
        self.vx += game.clamp(target - self.vx, -accel, accel)

        # Vertical: gravity, stronger while rising without the key held (variable jump height).
        g = GRAVITY * (LOW_JUMP if self.vy < 0 and not jump_held else 1)
        self.vy = min(self.vy + g * dt, MAX_FALL)

        # Coyote time and jump buffer: both are small timers counting down.
        self.coyote = COYOTE if self.on_ground else max(0.0, self.coyote - dt)
        self.buffer = max(0.0, self.buffer - dt)
        if self.buffer > 0 and self.coyote > 0:
            self.vy = -JUMP_SPEED
            self.buffer = self.coyote = 0.0

        # Move one axis at a time and push out of whatever we hit.
        self.move_x(self.vx * dt)
        self.on_ground = False
        self.move_y(self.vy * dt)

        self.trail.append(self.player.center)
        del self.trail[:-60]
        self.hits = {i: t - dt for i, t in self.hits.items() if t - dt > 0}
        for ball in self.balls:
            self.bounce(ball, dt)

    def solids_hit(self, rect):
        return [(i, p) for i, p in enumerate(PLATFORMS) if rect.overlaps(p)]

    def move_x(self, dx):
        self.player.x += dx
        for i, p in self.solids_hit(self.player):
            self.player.x = p.left - self.player.w if dx > 0 else p.right
            self.vx = 0.0
            self.hits[i] = 0.2

    def move_y(self, dy):
        self.player.y += dy
        for i, p in self.solids_hit(self.player):
            if dy > 0:                       # falling: land on top
                self.player.y = p.top - self.player.h
                self.on_ground = True
            else:                            # rising: bump the head
                self.player.y = p.bottom
            self.vy = 0.0
            self.hits[i] = 0.2

    def bounce(self, ball, dt):
        ball.vy += GRAVITY * 0.5 * dt
        ball.x += ball.vx * dt
        ball.y += ball.vy * dt
        for i, p in enumerate(PLATFORMS):
            normal = game.circle_rect(ball.x, ball.y, ball.r, p)
            if normal:
                nx, ny = normal
                if nx:
                    ball.vx = abs(ball.vx) * nx              # reflect the speed on that side
                    ball.x = (p.right + ball.r) if nx > 0 else (p.left - ball.r)
                if ny:
                    ball.vy = abs(ball.vy) * ny * 0.82       # lose a little energy on each bounce
                    ball.y = (p.bottom + ball.r) if ny > 0 else (p.top - ball.r)
                    if ny < 0 and abs(ball.vy) < 120:        # nearly still: kick it again
                        ball.vy = -620
                self.hits[i] = 0.2

    # -- draw -------------------------------------------------------------------------------
    def board(self):
        shapes = [draw.background("#0f141c")]
        for i, p in enumerate(PLATFORMS):
            lit = i in self.hits and self.debug
            shapes.append(p.shape(fill="#2a3446", radius=3))
            shapes.append(draw.rect(p.x, p.y, p.w, 3, fill="#4b5d7c" if not lit else "#fbbf24"))
            if self.debug:
                shapes.append(p.shape(stroke="#fbbf24" if lit else "#ffffff1f", width=1.5 if lit else 1))
        for ball in self.balls:
            shapes += game.glow(ball.x, ball.y, ball.r, ball.color, layers=2, strength=0.35)
            if self.debug:
                shapes.append(draw.line(ball.x, ball.y, ball.x + ball.vx * 0.08, ball.y + ball.vy * 0.08,
                                        stroke=game.rgba(ball.color, 0.7), width=1.5))

        if self.debug and len(self.trail) > 1:    # the trail: fading dots, one per frame
            n = len(self.trail)
            for i, (x, y) in enumerate(self.trail[::2]):
                a = (i * 2 + 1) / n
                shapes.append(draw.circle(x, y, 2.2, fill=game.rgba("#22d3ee", a * 0.8)))

        p = self.player
        squash = 1 + game.clamp(abs(self.vy) / MAX_FALL, 0, 1) * 0.15 if not self.on_ground else 1
        w, h = p.w / squash, p.h * squash            # stretch while flying fast
        shapes.append(draw.rect(p.center[0] - w / 2, p.bottom - h, w, h, radius=6, fill="#22d3ee"))
        eye = 1 if self.vx >= 0 else -1
        shapes.append(draw.rect(p.center[0] + eye * 4 - 3, p.bottom - h + 9, 6, 7, radius=2, fill="#0b0e14"))

        if self.debug:
            cx, cy = p.center
            shapes.append(p.shape(stroke="#34d399", width=1.5))
            shapes.append(draw.line(cx, cy, cx + self.vx * 0.15, cy + self.vy * 0.15, stroke="#f472b6", width=2.5,
                                    cap="round"))
            info = (f"vx {self.vx:6.0f}  vy {self.vy:6.0f}  ground {'yes' if self.on_ground else 'no '}  "
                    f"coyote {self.coyote:.2f}  buffer {self.buffer:.2f}")
            shapes.append(draw.rect(16, 16, 520, 24, radius=6, fill="#00000088"))
            shapes.append(draw.text(26, 21, info, size=12, font="mono", color="#cbd5e1"))
        return pz.canvas(shapes, width=W, height=H)

    def view(self):
        t = self.resolved_theme()
        hud = pz.row([ui.label("Jump Lab", weight="semibold"), pz.hspace(),
                      ui.badge("on the ground" if self.on_ground else "in the air",
                               icon="footprints" if self.on_ground else "wind",
                               tint="success" if self.on_ground else "accent"),
                      ui.badge("debug on" if self.debug else "debug off", icon="bug", tint="text_muted")],
                     spacing=8, align="center")
        return pz.container(pz.column([hud, pz.container(self.board(), radius=10, clip=True),
                                       ui.muted("←/→ run · Space jumps (hold for higher) · H toggles the debug view",
                                                size="sm")], spacing=10),
                            padding=16, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(JumpLab)
