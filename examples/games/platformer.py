"""Pixel Run: a side-scrolling platformer with a tile map, a camera, enemies and coins.

    python examples/games/platformer.py

Arrows or A/D run, Space (or Up/W) jumps, hold it to jump higher. Stomp the slimes, grab
the coins, avoid the spikes and reach the flag. Enter plays again. Builds on the physics of
Jump Lab and adds what turns it into a level:

- **A tile map written as text**: ``#`` ground, ``=`` platforms, ``o`` coins, ``E`` enemies,
  ``^`` spikes, ``P`` the start and ``F`` the flag. Only the tiles near the player are
  checked for collisions, and only the ones on screen are drawn.
- **A camera** that follows the player smoothly and stops at the edges of the level, with
  hills that scroll slower than the ground (parallax).
- **Enemies** that patrol and turn at walls and ledges, and can be stomped from above.
- **Lives, respawn, a win screen** and a HUD made of ordinary widgets.

Tutorial: https://albakore.github.io/pyzed/games/platformer/
"""

import math

import pyzed as pz
from pyzed import draw, game, ui

TILE = 32
LEVEL = [
    "................................................................................................",
    "................................................................................................",
    "................................................................................................",
    "................................................................................................",
    "....................................ooo.........................................................",
    "...................................=====........................................................",
    ".........ooo.............................................................ooo....................",
    "........=====...........................................................=====...................",
    "...................oo.....................oo........##.............oo...........................",
    "...............................###..................##..........................................",
    "...P.ooo......ooo.......Eoo.######............Eoo...##...^^.ooE...............E.ooo.......F.....",
    "##################...####################...######################...###########################",
    "##################...####################...######################...###########################",
]
COLS, ROWS = len(LEVEL[0]), len(LEVEL)
LEVEL_W, LEVEL_H = COLS * TILE, ROWS * TILE
W, H = 704, LEVEL_H          # the window shows 22 of the 96 columns

RUN, ACCEL, AIR_ACCEL = 240, 2200, 1400
GRAVITY, JUMP_SPEED, LOW_JUMP, MAX_FALL = 1900, 680, 2.6, 900
COYOTE, BUFFER = 0.1, 0.12
JUMP_KEYS = ("space", "up", "w")
ENEMY_SPEED = 55
SOLID = "#="

SLIME = ["..####..", ".######.", "##w##w##", "##k##k##", "########", "########", ".#.##.#."]
SLIME_FLAT = ["........", "........", "........", "..####..", "##w##w##", "########", "########"]


def solid(col, row):
    """Whether the tile at ``(col, row)`` blocks; outside the map, the sides block and the bottom is open."""
    if col < 0 or col >= COLS:
        return True
    if row < 0 or row >= ROWS:
        return False
    return LEVEL[row][col] in SOLID


def tiles_near(rect):
    """The solid tiles ``rect`` could touch: only the few cells under it, never the whole map."""
    out = []
    for row in range(int(rect.top // TILE), int(rect.bottom // TILE) + 1):
        for col in range(int(rect.left // TILE), int(rect.right // TILE) + 1):
            if solid(col, row):
                out.append(game.Rect(col * TILE, row * TILE, TILE, TILE))
    return out


class Enemy:
    def __init__(self, x, y):
        self.rect = game.Rect(x + 2, y + TILE - 24, 28, 24)
        self.vx = -ENEMY_SPEED
        self.squashed = 0.0      # seconds since it was stomped (0 while alive)


class Platformer(pz.App):
    title = "Pixel Run"
    size = (W + 32, H + 92)
    theme = "One Dark"

    def __init__(self, seed=None):
        self.held = None             # the keys held down; None reads the keyboard
        self.sparks = game.Particles(gravity=600, seed=seed)
        self.shake = game.Shake(seed=seed)
        self.best_time = None
        self.new_game()

    # -- state ------------------------------------------------------------------------------
    def new_game(self):
        self.coins, self.enemies = set(), []
        for row, line in enumerate(LEVEL):
            for col, ch in enumerate(line):
                if ch == "o":
                    self.coins.add((col, row))
                elif ch == "E":
                    self.enemies.append(Enemy(col * TILE, row * TILE))
                elif ch == "P":
                    self.start = (col * TILE + 4, row * TILE + TILE - 30)
                elif ch == "F":
                    self.flag = game.Rect(col * TILE + 10, row * TILE - 4 * TILE, 12, 5 * TILE)
        self.total_coins = len(self.coins)
        self.lives, self.time = 3, 0.0
        self.won = self.over = False
        self.camera = 0.0
        self.respawn()

    def respawn(self):
        self.player = game.Rect(*self.start, 22, 30)
        self.vx = self.vy = 0.0
        self.on_ground = False
        self.coyote = self.buffer = 0.0
        self.facing = 1
        self.invincible = 1.0        # a second of blinking after (re)spawning

    @property
    def collected(self):
        return self.total_coins - len(self.coins)

    # -- input ------------------------------------------------------------------------------
    def on_key(self, combo):
        if combo in JUMP_KEYS:
            self.buffer = BUFFER
        elif combo == "enter" and (self.won or self.over):
            self.new_game()

    # -- update -----------------------------------------------------------------------------
    def subscriptions(self):
        return [pz.frames(self.tick)]

    def tick(self, dt):
        dt = min(dt, 1 / 30)
        self.sparks.update(dt)
        self.shake.update(dt)
        if self.won or self.over:
            return
        self.time += dt
        self.invincible = max(0.0, self.invincible - dt)
        self.move_player(dt)
        self.move_enemies(dt)
        self.pick_coins()
        self.check_dangers()
        # The camera looks a little ahead of the player and eases toward it.
        target = game.clamp(self.player.center[0] - W * 0.4, 0, LEVEL_W - W)
        self.camera = game.lerp(self.camera, target, min(1.0, 8 * dt))

    def move_player(self, dt):
        move = game.axis(("left", "a"), ("right", "d"), held=self.held)
        if move:
            self.facing = move
        accel = (ACCEL if self.on_ground else AIR_ACCEL) * dt
        self.vx += game.clamp(move * RUN - self.vx, -accel, accel)
        rising_without_key = self.vy < 0 and not game.is_pressed(*JUMP_KEYS, held=self.held)
        self.vy = min(self.vy + GRAVITY * (LOW_JUMP if rising_without_key else 1) * dt, MAX_FALL)
        self.coyote = COYOTE if self.on_ground else max(0.0, self.coyote - dt)
        self.buffer = max(0.0, self.buffer - dt)
        if self.buffer > 0 and self.coyote > 0:
            self.vy, self.buffer, self.coyote = -JUMP_SPEED, 0.0, 0.0

        p = self.player
        p.x += self.vx * dt
        for tile in tiles_near(p):
            if p.overlaps(tile):
                p.x = tile.left - p.w if self.vx > 0 else tile.right
                self.vx = 0.0
        p.y += self.vy * dt
        self.on_ground = False
        for tile in tiles_near(p):
            if p.overlaps(tile):
                if self.vy > 0:
                    p.y, self.on_ground = tile.top - p.h, True
                else:
                    p.y = tile.bottom
                self.vy = 0.0

    def move_enemies(self, dt):
        for e in self.enemies:
            if e.squashed:
                e.squashed += dt
                continue
            r = e.rect
            r.x += e.vx * dt
            ahead = r.right if e.vx > 0 else r.left
            col = int(ahead // TILE)
            row = int((r.bottom - 1) // TILE)
            if solid(col, row) or not solid(col, row + 1):   # a wall, or no floor ahead:
                r.x -= e.vx * dt                              # step back and turn around
                e.vx = -e.vx
        self.enemies = [e for e in self.enemies if e.squashed < 0.6]

    def pick_coins(self):
        p = self.player
        for col, row in list(self.coins):
            if p.overlaps(game.Rect(col * TILE + 8, row * TILE + 8, 16, 16)):
                self.coins.discard((col, row))
                self.sparks.burst(col * TILE + 16, row * TILE + 16, count=12, color=["#fde68a", "#fbbf24"],
                                  speed=(40, 160), life=(0.2, 0.5))

    def check_dangers(self):
        p = self.player
        for e in self.enemies:
            if e.squashed or not p.overlaps(e.rect):
                continue
            if self.vy > 0 and p.bottom - self.vy / 60 <= e.rect.top + 8:   # coming down on it: stomp
                e.squashed = 0.001
                self.vy = -JUMP_SPEED * 0.6
                self.sparks.burst(e.rect.center[0], e.rect.bottom, count=14, color="#a3e635", angle=-90, spread=160)
                self.shake.kick(3)
            elif not self.invincible:
                return self.hurt()
        for row in range(int(p.top // TILE), int(p.bottom // TILE) + 1):
            for col in range(int(p.left // TILE), int(p.right // TILE) + 1):
                if 0 <= row < ROWS and 0 <= col < COLS and LEVEL[row][col] == "^":
                    spike = game.Rect(col * TILE + 4, row * TILE + 14, TILE - 8, TILE - 14)
                    if p.overlaps(spike) and not self.invincible:
                        return self.hurt()
        if p.top > LEVEL_H + 40:
            return self.hurt()
        if p.overlaps(self.flag):
            self.won = True
            self.best_time = self.time if self.best_time is None else min(self.best_time, self.time)
            self.sparks.burst(self.flag.center[0], self.flag.top + 20, count=60,
                              color=["#f472b6", "#fbbf24", "#22d3ee", "#a3e635"], speed=(80, 320))

    def hurt(self):
        self.lives -= 1
        self.shake.kick(10)
        self.sparks.burst(*self.player.center, count=30, color=["#f87171", "#fecaca"], speed=(80, 260))
        if self.lives <= 0:
            self.over = True
        else:
            self.respawn()

    # -- draw -------------------------------------------------------------------------------
    def board(self):
        cam = round(self.camera)
        shapes = [draw.background("#1e1b3a")]
        for i, color in enumerate(("#2a2550", "#352d63", "#43367a")):       # sky bands
            shapes.append(draw.rect(0, 70 + i * 60, W, 60, fill=color))
        shapes.append(draw.circle(560, 90, 34, fill="#fde68a"))
        for layer, (speed, color, base) in enumerate(((0.2, "#2c2a55", 300), (0.45, "#24344d", 340))):
            off = -(cam * speed) % 240                                       # parallax hills
            for i in range(-1, W // 240 + 2):
                cx = i * 240 + off + layer * 120
                shapes.append(draw.circle(cx, base, 150 - layer * 30, fill=color))

        shapes += [draw.save(), *self.shake.shapes(), draw.translate(-cam, 0)]
        first, last = cam // TILE, (cam + W) // TILE + 1
        dirt, grass, stone = [], [], []
        for row, line in enumerate(LEVEL):
            for col in range(max(0, first), min(COLS, last + 1)):       # only the visible columns
                ch = line[col]
                x, y = col * TILE, row * TILE
                if ch == "#":
                    dirt.append((x, y, TILE, TILE))
                    if row == 0 or LEVEL[row - 1][col] not in SOLID:
                        grass.append((x, y, TILE, 8))
                elif ch == "=":
                    stone.append((x, y, TILE, TILE / 2))
                elif ch == "^":
                    for k in range(2):
                        sx = x + 2 + k * 14
                        shapes.append(draw.polygon([(sx, y + TILE), (sx + 7, y + 12), (sx + 14, y + TILE)],
                                                   fill="#cbd5e1"))
        shapes += [draw.rects(dirt, fill="#5b3a29"), draw.rects(grass, fill="#65a30d"),
                   draw.rects(stone, fill="#64748b")]

        for col, row in self.coins:
            cx, cy = col * TILE + 16, row * TILE + 16 + math.sin(self.time * 4 + col) * 3
            spin = 0.35 + 0.65 * abs(math.cos(self.time * 3 + col * 0.7))
            shapes += game.glow(cx, cy, 6, "#fbbf24", layers=2, strength=0.35, core=False)
            shapes.append(draw.rect(cx - 7 * spin, cy - 8, 14 * spin, 16, radius=7 * spin, fill="#fbbf24"))

        fx, fy = self.flag.x, self.flag.y
        shapes.append(draw.rect(fx + 4, fy, 4, self.flag.h, fill="#e2e8f0"))
        wave = math.sin(self.time * 5) * 4
        shapes.append(draw.polygon([(fx + 8, fy + 2), (fx + 52, fy + 14 + wave), (fx + 8, fy + 28)], fill="#f472b6"))

        for e in self.enemies:
            frame = SLIME_FLAT if e.squashed else SLIME
            bob = 0 if e.squashed else abs(math.sin(self.time * 8 + e.rect.x * 0.1)) * -2
            shapes += game.sprite(frame, {"#": "#84cc16", "w": "#f8fafc", "k": "#111827"},
                                  e.rect.x - 2, e.rect.y - 4 + bob, scale=4, flip=e.vx > 0)

        if not self.over and (not self.invincible or int(self.time * 14) % 2):
            p = self.player
            shapes.append(p.shape(fill="#22d3ee", radius=5))
            ex = p.center[0] + self.facing * 4
            shapes.append(draw.rect(ex - 2, p.y + 8, 4, 7, radius=2, fill="#0b0e14"))
        shapes += self.sparks.shapes(glow=True)
        shapes.append(draw.restore())
        return pz.canvas(shapes, width=W, height=H)

    def overlay(self):
        if self.won:
            title, lines = "Level clear!", [f"{self.collected}/{self.total_coins} coins in {self.time:.1f} s",
                                            "Enter plays again"]
        elif self.over:
            title, lines = "Game over", [f"{self.collected}/{self.total_coins} coins", "Enter plays again"]
        else:
            return None
        card = pz.container(pz.column([ui.heading(title, level=2), *[ui.muted(t) for t in lines]],
                                      spacing=8, align="center"), padding=(20, 32)).style(glass=True, radius=14)
        return pz.container(card, width="fill", height="fill", align_x="center", align_y="center")

    def view(self):
        t = self.resolved_theme()
        hearts = pz.row([pz.icon("heart", size=15, color="#f87171" if i < self.lives else t.border)
                         for i in range(3)], spacing=3)
        hud = pz.row([
            ui.label("Pixel Run", weight="semibold"), pz.hspace(),
            ui.badge(f"{self.collected}/{self.total_coins}", icon="coins", tint="warning"),
            ui.badge(f"{self.time:.1f} s", icon="timer", tint="accent"),
            ui.badge(f"Best {self.best_time:.1f} s", icon="trophy", tint="text_muted") if self.best_time else None,
            hearts,
        ], spacing=8, align="center")
        play = pz.stack([self.board(), self.overlay()], width=W, height=H)
        return pz.container(pz.column([hud, pz.container(play, radius=10, clip=True),
                                       ui.muted("←/→ run · Space jumps · stomp the slimes · reach the flag",
                                                size="sm")], spacing=10),
                            padding=16, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(Platformer)
