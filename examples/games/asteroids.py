"""Rock Storm: an Asteroids-style shooter with thrust, wrap-around space and lots of particles.

    python examples/games/asteroids.py

Left/Right (or A/D) turn, Up (or W) thrusts, hold Space to fire, P pauses, Enter plays
again. Big rocks split in two when hit, small ones burst into sparks. Shows:

- **Rotation and thrust**: the ship has an angle; thrust adds ``cos``/``sin`` of it to the
  velocity, and a little drag slows it down. Everything wraps around the screen edges.
- **Circle collisions**: two circles touch when the distance between their centers is
  smaller than the sum of their radii.
- **Particles** everywhere: an engine trail emitted every frame, explosions, debris and
  sparks, with ``game.Particles`` (``burst``, ``update``, ``shapes``).
- **Screen shake**, invulnerability after a hit, waves that get harder.

Tutorial: https://albakore.github.io/pyzed/games/asteroids/
"""

import math
import random

import pyzed as pz
from pyzed import draw, game, ui

W, H = 720, 480
TURN = 260            # degrees per second
THRUST = 380          # px/s² while thrusting
DRAG = 0.6            # fraction of the speed lost per second
MAX_SPEED = 420
BULLET_SPEED = 620
BULLET_LIFE = 0.9
FIRE_DELAY = 0.18
SHIP_R = 13
SIZES = {3: 46, 2: 26, 1: 14}     # rock size -> radius
POINTS = {3: 20, 2: 50, 1: 100}


def wrap(x, y, margin=0):
    """The point moved back onto the screen when it leaves through one edge."""
    return ((x + margin) % (W + 2 * margin) - margin, (y + margin) % (H + 2 * margin) - margin)


class Rock:
    def __init__(self, rnd, x, y, size, speed):
        self.x, self.y, self.size = x, y, size
        a = rnd.uniform(0, math.tau)
        self.vx, self.vy = math.cos(a) * speed, math.sin(a) * speed
        self.angle, self.spin = rnd.uniform(0, 360), rnd.uniform(-60, 60)
        # A jagged outline: points around a circle at slightly random distances.
        n = 9 + size * 2
        self.outline = [(math.cos(i / n * math.tau), math.sin(i / n * math.tau), rnd.uniform(0.75, 1.1))
                        for i in range(n)]

    @property
    def r(self):
        return SIZES[self.size]

    def points(self):
        rad = math.radians(self.angle)
        c, s = math.cos(rad), math.sin(rad)
        return [(self.x + (ux * c - uy * s) * k * self.r, self.y + (ux * s + uy * c) * k * self.r)
                for ux, uy, k in self.outline]


class Asteroids(pz.App):
    title = "Rock Storm"
    size = (W + 32, H + 92)
    theme = "Pyzed Dark"

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.held = None                       # the keys held down; None reads the keyboard
        self.sparks = game.Particles(drag=1.2, seed=seed)                  # explosions and debris
        self.trail = game.Particles(drag=3.0, limit=400, seed=seed)       # the engine's exhaust
        self.shake = game.Shake(seed=seed)
        self.stars = [(self.random.uniform(0, W), self.random.uniform(0, H), self.random.uniform(0.4, 1.4))
                      for _ in range(90)]
        self.best = 0
        self.new_game()

    # -- state ------------------------------------------------------------------------------
    def new_game(self):
        self.score, self.lives, self.wave = 0, 3, 0
        self.over = self.paused = False
        self.clock = 0.0
        self.reset_ship()
        self.next_wave()

    def reset_ship(self):
        self.x, self.y, self.vx, self.vy = W / 2, H / 2, 0.0, 0.0
        self.angle = -90.0                     # pointing up
        self.bullets = []                      # [x, y, vx, vy, age]
        self.cooldown = 0.0
        self.safe = 2.0                        # seconds of invulnerability

    def next_wave(self):
        self.wave += 1
        self.rocks = []
        for _ in range(2 + self.wave):
            # Spawn on the edges, never on top of the ship.
            x, y = (self.random.uniform(0, W), -40) if self.random.random() < 0.5 else (-40, self.random.uniform(0, H))
            self.rocks.append(Rock(self.random, x, y, 3, self.random.uniform(30, 60) + self.wave * 8))

    # -- input ------------------------------------------------------------------------------
    def on_key(self, combo):
        if combo == "p" and not self.over:
            self.paused = not self.paused
        elif combo == "enter" and self.over:
            self.new_game()

    # -- update -----------------------------------------------------------------------------
    def subscriptions(self):
        return [] if self.paused else [pz.frames(self.tick)]

    def tick(self, dt):
        dt = min(dt, 1 / 30)
        self.clock += dt
        self.sparks.update(dt)
        self.trail.update(dt)
        self.shake.update(dt)
        for rock in self.rocks:
            rock.x, rock.y = wrap(rock.x + rock.vx * dt, rock.y + rock.vy * dt, rock.r)
            rock.angle += rock.spin * dt
        if self.over:
            return
        self.safe = max(0.0, self.safe - dt)
        self.fly(dt)
        self.move_bullets(dt)
        self.collide()
        if not self.rocks:
            self.next_wave()

    def fly(self, dt):
        self.angle += game.axis(("left", "a"), ("right", "d"), held=self.held) * TURN * dt
        rad = math.radians(self.angle)
        fx, fy = math.cos(rad), math.sin(rad)
        if game.is_pressed("up", "w", held=self.held):
            self.vx += fx * THRUST * dt
            self.vy += fy * THRUST * dt
            # Exhaust: a few particles every frame, shot backwards from the tail.
            self.trail.burst(self.x - fx * SHIP_R, self.y - fy * SHIP_R, count=3, angle=self.angle + 180, spread=30,
                             speed=(80, 180), life=(0.15, 0.4), size=(1.5, 3), color=["#fbbf24", "#f97316", "#fde68a"])
        damping = max(0.0, 1 - DRAG * dt)
        self.vx, self.vy = self.vx * damping, self.vy * damping
        speed = math.hypot(self.vx, self.vy)
        if speed > MAX_SPEED:
            self.vx, self.vy = self.vx / speed * MAX_SPEED, self.vy / speed * MAX_SPEED
        self.x, self.y = wrap(self.x + self.vx * dt, self.y + self.vy * dt)

        self.cooldown -= dt
        if game.is_pressed("space", held=self.held) and self.cooldown <= 0:
            self.fire()

    def fire(self):
        self.cooldown = FIRE_DELAY
        rad = math.radians(self.angle)
        fx, fy = math.cos(rad), math.sin(rad)
        self.bullets.append([self.x + fx * SHIP_R, self.y + fy * SHIP_R,
                             self.vx + fx * BULLET_SPEED, self.vy + fy * BULLET_SPEED, 0.0])
        self.sparks.burst(self.x + fx * SHIP_R, self.y + fy * SHIP_R, count=4, angle=self.angle, spread=40,
                          speed=(60, 140), life=(0.05, 0.15), color="#a5f3fc")

    def move_bullets(self, dt):
        for b in self.bullets:
            b[0], b[1] = wrap(b[0] + b[2] * dt, b[1] + b[3] * dt)
            b[4] += dt
        self.bullets = [b for b in self.bullets if b[4] < BULLET_LIFE]

    def collide(self):
        for b in self.bullets[:]:
            for rock in self.rocks:
                if math.hypot(b[0] - rock.x, b[1] - rock.y) < rock.r:   # a point inside a circle
                    self.bullets.remove(b)
                    self.break_rock(rock)
                    break
        if self.safe <= 0:
            for rock in self.rocks:
                if math.hypot(self.x - rock.x, self.y - rock.y) < rock.r + SHIP_R * 0.8:   # circle vs circle
                    self.crash()
                    break

    def break_rock(self, rock):
        self.rocks.remove(rock)
        self.score += POINTS[rock.size]
        self.sparks.burst(rock.x, rock.y, count=10 + rock.size * 10, color=["#cbd5e1", "#94a3b8", "#fbbf24"],
                          speed=(40, 120 + rock.size * 60), life=(0.3, 0.6 + rock.size * 0.25), size=(1, 3))
        self.shake.kick(rock.size * 2.5)
        if rock.size > 1:
            for _ in range(2):
                child = Rock(self.random, rock.x, rock.y, rock.size - 1,
                             math.hypot(rock.vx, rock.vy) * 1.3 + self.random.uniform(20, 60))
                self.rocks.append(child)

    def crash(self):
        self.lives -= 1
        self.shake.kick(16)
        self.sparks.burst(self.x, self.y, count=70, color=["#22d3ee", "#a5f3fc", "#f472b6", "#ffffff"],
                          speed=(60, 340), life=(0.4, 1.2), size=(1.5, 4))
        if self.lives <= 0:
            self.over = True
            self.best = max(self.best, self.score)
        else:
            self.reset_ship()

    # -- draw -------------------------------------------------------------------------------
    def board(self):
        shapes = [draw.background("#05060d"), *self.shake.shapes()]
        for x, y, r in self.stars:
            shapes.append(draw.circle(x, y, r, fill=game.rgba("#e2e8f0", 0.25 + r * 0.3)))
        shapes += self.trail.shapes(glow=True)
        for rock in self.rocks:
            shapes.append(draw.polygon(rock.points(), fill="#1e2433", stroke="#94a3b8", width=2))
        for x, y, vx, vy, age in self.bullets:
            speed = math.hypot(vx, vy) or 1
            tx, ty = x - vx / speed * 10, y - vy / speed * 10
            shapes.append(draw.line(tx, ty, x, y, stroke=game.rgba("#22d3ee", 0.35), width=6, cap="round"))
            shapes.append(draw.line(tx, ty, x, y, stroke="#e0fbff", width=2, cap="round"))
        if not self.over and (self.safe <= 0 or int(self.clock * 12) % 2):
            rad = math.radians(self.angle)
            pts = []
            for a, d in ((0, 1.4), (140, 1.0), (180, 0.45), (220, 1.0)):    # nose, wing, tail notch, wing
                pa = rad + math.radians(a)
                pts.append((self.x + math.cos(pa) * SHIP_R * d, self.y + math.sin(pa) * SHIP_R * d))
            shapes += game.glow(self.x, self.y, SHIP_R, "#22d3ee", layers=3, strength=0.18, core=False)
            shapes.append(draw.polygon(pts, fill="#0b1220", stroke="#22d3ee", width=2.5))
        shapes += self.sparks.shapes(glow=True)
        return pz.canvas(shapes, width=W, height=H)

    def overlay(self):
        if self.over:
            title, lines = "Game over", [f"Score {self.score:,}  ·  wave {self.wave}", "Enter plays again"]
        elif self.paused:
            title, lines = "Paused", ["P continues"]
        else:
            return None
        card = pz.container(pz.column([ui.heading(title, level=2), *[ui.muted(t) for t in lines]],
                                      spacing=8, align="center"), padding=(20, 32)).style(glass=True, radius=14)
        return pz.container(card, width="fill", height="fill", align_x="center", align_y="center")

    def view(self):
        t = self.resolved_theme()
        ships = pz.row([pz.icon("rocket", size=15, color="#22d3ee" if i < self.lives else t.border)
                        for i in range(3)], spacing=3)
        hud = pz.row([
            ui.label("Rock Storm", weight="semibold"), pz.hspace(),
            ui.badge(f"Wave {self.wave}", icon="orbit", tint="accent"),
            ui.badge(f"{self.score:,}", icon="star", tint="warning"),
            ui.badge(f"Best {self.best:,}", icon="trophy", tint="text_muted"),
            ships,
        ], spacing=8, align="center")
        play = pz.stack([self.board(), self.overlay()], width=W, height=H)
        return pz.container(pz.column([hud, pz.container(play, radius=10, clip=True),
                                       ui.muted("←/→ turn · ↑ thrust · hold Space to fire · P pauses", size="sm")],
                                      spacing=10),
                            padding=16, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(Asteroids)
