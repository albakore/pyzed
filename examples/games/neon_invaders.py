"""Neon Invaders: a space shooter with a glowing HUD, particles, bloom and screen shake.

    python examples/games/neon_invaders.py

Arrows/WASD fly, hold Space to fire, P pauses, Enter starts. Waves of pixel-art invaders
march and dive; shoot the purple capsules for a triple shot. Shows a complete game
built from Pyzed parts: ``pz.frames`` for the loop, ``pz.pressed`` for flying and
auto-fire, ``game.sprite`` pixel art, ``game.glow`` neon lights, ``game.Particles``
explosions, ``game.Shake``, and a HUD of regular widgets with ``glass`` panels,
``bloom`` and animations stacked over the canvas.
Tutorial: https://albakore.github.io/pyzed/games/neon-invaders/
"""

import math
import random

import pyzed as pz
from pyzed import draw, game, ui

W, H = 760, 560
PLAYER_SPEED = 330
FIRE_DELAY = 0.16
NEON = {"cyan": "#22d3ee", "pink": "#f472b6", "lime": "#a3e635", "amber": "#fbbf24", "violet": "#a78bfa"}

SHIP = [
    "....#....",
    "...###...",
    "...#@#...",
    "..#####..",
    ".##.#.##.",
    "###.#.###",
    "#.......#",
]
INVADERS = [
    ["..#.....#..", "...#...#...", "..#######..", ".##.###.##.", "###########", "#.#######.#", "#.#.....#.#",
     "...##.##..."],
    ["...####...", ".########.", "##########", "###..##..#", "##########", "..##..##..", ".##.##.##.",
     "##......##"],
    ["...##...", "..####..", ".######.", "##.##.##", "########", "..#..#..", ".#.##.#.", "#.#..#.#"],
]
INVADER_COLORS = [NEON["lime"], NEON["pink"], NEON["amber"]]
PIXEL = 3


def neon(widget, color, intensity=1.0):
    """Bloom on the bright parts only: no lit edge or box shadow, so text glows by itself."""
    return pz.container(widget, padding=(4, 12)).style(bloom=(color, intensity), border_width=0,
                                                        shadow=("#00000000", (0, 0), 0))


class Invader:
    def __init__(self, kind, col, row):
        self.kind, self.col, self.row = kind, col, row
        self.hp = 1 + (kind == 0)
        self.diving = False
        self.flash = 0.0  # seconds left of the white flash after a hit
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0

    @property
    def w(self):
        return len(INVADERS[self.kind][0]) * PIXEL

    @property
    def rect(self):
        return game.Rect(self.x, self.y, self.w, 8 * PIXEL)


class NeonInvaders(pz.App):
    title = "Neon Invaders"
    size = (W + 32, H + 32)
    theme = "One Dark"

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.sparks = game.Particles(drag=2.2, seed=seed)
        self.shake = game.Shake(seed=seed)
        self.stars = [(self.random.uniform(0, W), self.random.uniform(0, H), layer)
                      for layer in (1, 2, 3) for _ in range(40 // layer)]
        self.best = 0
        self.started = False  # the title screen until Enter
        self.time = 0.0
        self.new_game()

    # -- state ----------------------------------------------------------------
    def new_game(self):
        self.x, self.y = W / 2, H - 60
        self.shield, self.score, self.wave = 3, 0, 0
        self.shots, self.enemy_shots, self.powerups = [], [], []
        self.cooldown = 0.0
        self.triple = 0.0  # seconds of triple shot left
        self.hurt = 0.0  # invulnerability after a hit
        self.over = self.paused = False
        self.next_wave()

    def next_wave(self):
        self.wave += 1
        self.invaders = [Invader(min(row // 2, 2), col, row) for row in range(4) for col in range(9)]
        self.march, self.direction, self.drop = 0.0, 1, 0.0
        self.banner = 2.0  # "Wave N" shown for two seconds
        self.place_formation()

    def place_formation(self):
        left = 70 + self.march
        for inv in self.invaders:
            if not inv.diving:
                inv.x = left + inv.col * 64 + (33 - inv.w) / 2
                inv.y = 70 + inv.row * 44 + self.drop

    # -- the loop -------------------------------------------------------------
    def subscriptions(self):
        return [pz.frames(self.tick)]

    def tick(self, dt):
        self.time += dt
        self.sparks.update(dt)
        self.shake.update(dt)
        self.stars = [(x, (y + 20 * layer * dt) % H, layer) for x, y, layer in self.stars]
        if not self.started or self.paused or self.over:
            return
        self.banner = max(0.0, self.banner - dt)
        self.hurt = max(0.0, self.hurt - dt)
        self.triple = max(0.0, self.triple - dt)
        self.fly(dt)
        self.move_invaders(dt)
        self.move_shots(dt)
        if not self.invaders:
            self.next_wave()

    def fly(self, dt):
        dx, dy = game.vector()
        self.x = game.clamp(self.x + dx * PLAYER_SPEED * dt, 20, W - 20)
        self.y = game.clamp(self.y + dy * PLAYER_SPEED * dt, H * 0.55, H - 30)
        self.cooldown -= dt
        if game.is_pressed("space") and self.cooldown <= 0:
            self.fire()

    def fire(self):
        self.cooldown = FIRE_DELAY
        angles = (-12, 0, 12) if self.triple else (0,)
        for a in angles:
            r = math.radians(a - 90)
            self.shots.append([self.x, self.y - 14, math.cos(r) * 640, math.sin(r) * 640])

    def move_invaders(self, dt):
        speed = 40 + 10 * self.wave + (36 - len(self.invaders)) * 3
        self.march += self.direction * speed * dt
        if abs(self.march) > 60:
            self.direction = -self.direction
            self.march = game.clamp(self.march, -60, 60)
            self.drop = min(self.drop + 10, 140)
        self.place_formation()
        for inv in self.invaders:
            inv.flash = max(0.0, inv.flash - dt)
            if inv.diving:
                inv.vx += (self.x - inv.x) * 1.4 * dt  # home in on the ship
                inv.x += inv.vx * dt
                inv.y += inv.vy * dt
                if inv.y > H + 30:
                    inv.diving = False  # back to the formation from the top
            elif self.random.random() < dt * (0.02 + 0.01 * self.wave):
                inv.diving, inv.vx, inv.vy = True, 0.0, 170 + 20 * self.wave
            if self.random.random() < dt * (0.06 + 0.02 * self.wave):
                cx, cy = inv.rect.center
                self.enemy_shots.append([cx, cy + 12, 0, 230 + 15 * self.wave])
            if self.hurt <= 0 and inv.rect.overlaps(self.ship_rect):
                self.invaders.remove(inv)
                self.explode(inv, big=True)
                self.damage()
                break

    def move_shots(self, dt):
        for shot in self.shots[:]:
            shot[0] += shot[2] * dt
            shot[1] += shot[3] * dt
            if shot[1] < -10:
                self.shots.remove(shot)
                continue
            for inv in self.invaders:
                if inv.rect.contains(shot[0], shot[1]):
                    self.shots.remove(shot)
                    inv.hp -= 1
                    if inv.hp <= 0:
                        self.invaders.remove(inv)
                        self.score += (30 - 10 * inv.kind) * (2 if inv.diving else 1)
                        self.explode(inv)
                        if self.random.random() < 0.06:
                            self.powerups.append(list(inv.rect.center))
                    else:
                        inv.flash = 0.08
                        self.sparks.burst(shot[0], shot[1], count=6, color="#ffffff", speed=(40, 140))
                    break
        for shot in self.enemy_shots[:]:
            shot[1] += shot[3] * dt
            if shot[1] > H + 10:
                self.enemy_shots.remove(shot)
            elif self.hurt <= 0 and self.ship_rect.contains(shot[0], shot[1]):
                self.enemy_shots.remove(shot)
                self.damage()
        for p in self.powerups[:]:
            p[1] += 90 * dt
            if self.ship_rect.contains(*p) or self.ship_rect.moved(-8, -8).contains(*p):
                self.powerups.remove(p)
                self.triple = 8.0
                self.sparks.burst(p[0], p[1], count=30, color=NEON["violet"], speed=(60, 200))
            elif p[1] > H + 10:
                self.powerups.remove(p)

    @property
    def ship_rect(self):
        return game.Rect(self.x - 13, self.y - 10, 27, 21)

    def explode(self, inv, big=False):
        cx, cy = inv.rect.center
        color = INVADER_COLORS[inv.kind]
        self.sparks.burst(cx, cy, count=40 if big else 26, color=[color, "#ffffff", color], speed=(60, 300),
                          life=(0.3, 0.8), size=(1.5, 3.2))
        self.shake.kick(10 if big else 3)

    def damage(self):
        self.shield -= 1
        self.hurt = 1.5
        self.shake.kick(16)
        self.sparks.burst(self.x, self.y, count=50, color=[NEON["cyan"], "#ffffff"], speed=(80, 320))
        if self.shield <= 0:
            self.over = True
            self.best = max(self.best, self.score)

    # -- input ----------------------------------------------------------------
    def on_key(self, combo):
        if combo == "enter" and (not self.started or self.over):
            self.started = True
            self.new_game()
        elif combo == "p" and self.started and not self.over:
            self.paused = not self.paused

    # -- drawing --------------------------------------------------------------
    def scene(self):
        shapes = [draw.background("#05060d"), *self.shake.shapes()]
        for x, y, layer in self.stars:
            shapes.append(draw.circle(x, y, 0.5 * layer, fill=game.rgba("#c7d2fe", 0.25 * layer)))
        # A neon horizon grid at the bottom.
        for i in range(9):
            y = H - 120 + i * i * 1.6
            shapes.append(draw.line(0, y, W, y, stroke=game.rgba(NEON["violet"], 0.05 + i * 0.012)))
        for i in range(-8, 9):
            shapes.append(draw.line(W / 2 + i * 30, H - 120, W / 2 + i * 120, H,
                                    stroke=game.rgba(NEON["violet"], 0.08)))
        bob = math.sin(self.time * 6)
        for inv in self.invaders:
            color = "#ffffff" if inv.flash > 0 else INVADER_COLORS[inv.kind]
            cx, cy = inv.rect.center
            shapes += game.glow(cx, cy, 10, color, layers=2, strength=0.25, core=False)
            shapes += game.sprite(INVADERS[inv.kind], {"#": color}, inv.x, inv.y + bob * (0 if inv.diving else 1.5),
                                  scale=PIXEL)
        for x, y in self.powerups:
            shapes += game.glow(x, y, 7, NEON["violet"], layers=3, strength=0.7)
            shapes.append(draw.text(x, y, "3", color="#05060d", size=10, weight="bold", align_x="center",
                                    align_y="center"))
        for x, y, *_ in self.shots:
            shapes.append(draw.line(x, y, x, y + 12, stroke=game.rgba(NEON["cyan"], 0.3), width=7, cap="round"))
            shapes.append(draw.line(x, y, x, y + 12, stroke="#e0fbff", width=2.5, cap="round"))
        for x, y, *_ in self.enemy_shots:
            shapes += game.glow(x, y, 3.5, NEON["pink"], layers=2, strength=0.6)
        if self.started and not self.over and (self.hurt <= 0 or int(self.time * 12) % 2):
            flame = 6 + 3 * math.sin(self.time * 40)
            shapes += game.glow(self.x, self.y + 14, 4, NEON["amber"], layers=2, strength=0.8)
            shapes.append(draw.polygon([(self.x - 4, self.y + 11), (self.x + 4, self.y + 11),
                                        (self.x, self.y + 11 + flame)], fill=NEON["amber"]))
            shapes += game.glow(self.x, self.y, 16, NEON["cyan"], layers=3, strength=0.22, core=False)
            shapes += game.sprite(SHIP, {"#": NEON["cyan"], "@": "#ffffff"}, self.x - 13.5, self.y - 10.5, scale=PIXEL)
        shapes += self.sparks.shapes(glow=True)
        return pz.canvas(shapes, width=W, height=H)

    def hud(self, t):
        shield = pz.row([
            pz.icon("shield", size=14, color=NEON["cyan"]),
            pz.container(ui.progress(self.shield, max=3, tint=NEON["cyan"], height=6), width=90),
        ], spacing=6, align="center")
        score = neon(pz.text(f"{self.score:06d}", size=22, font="mono", color="#ffffff"), NEON["cyan"], 0.8)
        chips = [
            ui.badge(f"Wave {self.wave}", tint=NEON["pink"], icon="crosshair"),
            ui.badge(f"Triple {self.triple:.0f}s", tint=NEON["violet"], icon="sparkles") if self.triple else None,
            ui.badge(f"Best {self.best:,}", tint="text_muted", icon="trophy"),
        ]
        bar = pz.row([score, pz.hspace(), *chips, shield], spacing=10, align="center")
        return pz.container(bar, padding=(8, 14)).style(glass=True, radius=12, border=(1, "#ffffff22"))

    def center_card(self, title, lines, color):
        heading = neon(pz.text(title, size=40, weight="bold", color="#ffffff"), color).animate("pulse")
        body = [ui.muted(line) for line in lines]
        card = pz.container(pz.column([heading, *body], spacing=10, align="center"),
                            padding=(28, 40)).style(glass=True, radius=16, border=(1, "#ffffff26"))
        return pz.container(card, width="fill", height="fill", align_x="center", align_y="center")

    def overlay(self):
        if not self.started:
            return self.center_card("NEON INVADERS", ["Arrows / WASD fly · hold Space to fire",
                                                      "Press Enter to start"], NEON["pink"])
        if self.over:
            return self.center_card("GAME OVER", [f"Score {self.score:,} · wave {self.wave}",
                                                  "Press Enter to play again"], NEON["pink"])
        if self.paused:
            return self.center_card("PAUSED", ["Press P to continue"], NEON["cyan"])
        if self.banner:
            text = neon(pz.text(f"WAVE {self.wave}", size=30, weight="bold", color="#ffffff"),
                        NEON["lime"]).animate("zoom_in")
            return pz.container(text, width="fill", height="fill", align_x="center", align_y="center")
        return None

    def view(self):
        t = self.resolved_theme()
        hud = pz.container(self.hud(t), padding=12, width="fill") if self.started else None
        board = pz.stack([self.scene(), self.overlay(), hud], width=W, height=H)
        return pz.container(pz.container(board, radius=12, clip=True), padding=16, width="fill", height="fill",
                            bg="#0b0d14", align_x="center", align_y="center")


if __name__ == "__main__":
    pz.run(NeonInvaders)
