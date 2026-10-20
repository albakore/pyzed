"""Records the short muted clips the docs embed (docs/public/media/): MP4 (H.264) + WebM (VP9) + a WebP
poster, and an animated WebP when it is smaller than the MP4. ``manifest.json`` there lists every clip.
Clips registered with ``anim=True`` (short illustrations: the game tutorials and their concepts) are made
as an animated WebP and its poster only, sized to stay under ``ANIM_TARGET``.

    python docs/scripts/record.py                 # every clip
    python docs/scripts/record.py snake shader    # only the clips whose name contains a word
    python docs/scripts/record.py --list          # what there is to record

Two ways of recording:

* **Off-screen** (most clips): the same renderer as the screenshot scripts draws one PNG per frame
  while the clip steps the app's state between frames (a game's ``tick``, a shader's time, a form
  being typed into, a drag in Pyzed Design). No window, display or GPU is needed, the result is the
  same on every machine, and a pointer is drawn on top where the clip moves one.
* **Live** (clips about hover and press effects, which only a real pointer triggers): the app runs in
  a virtual X display (``Xvfb``) at 2x, a script moves and clicks the pointer through XTEST, and
  ``ffmpeg -f x11grab`` films it. Linux only; needs ``Xvfb`` and ``python-xlib``::

      uv run --with python-xlib python docs/scripts/record.py hover

Needs ``ffmpeg`` (with libx264 and libvpx-vp9) and Pillow. Clips aim for 6-12 s, at most 1280 px wide
and under ~400 KB per file: the encoder raises its quality factor until the clip fits.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "public" / "media"
MANIFEST = OUT / "manifest.json"
EXAMPLES = ROOT / "examples"
SCALE = 2
#: Largest width of an encoded clip, in pixels.
MAX_WIDTH = 1280
#: Each encoded file should stay under this many bytes.
BUDGET = 400_000
#: An animated-WebP-only clip aims for this size (and never goes over BUDGET).
ANIM_TARGET = 200_000
#: Largest width of an animated-WebP-only clip, in pixels.
ANIM_WIDTH = 640

os.environ.setdefault("PYZED_CONFIG_DIR", tempfile.mkdtemp(prefix="pyzed-record-"))
for sub in ("", "games", "showcase", "tutorial"):
    sys.path.insert(0, str(EXAMPLES / sub) if sub else str(EXAMPLES))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# The pointer drawn on clips, its ease-in-out glide and the animated WebP encoder are shared with anim_webp.py.
from anim_webp import draw_pointer, fit_webp, glide, save_poster


# -- clips -----------------------------------------------------------------------------------------
@dataclass
class Frame:
    """One frame of an off-screen clip: ``app`` drawn at ``size``, with the pointer at ``pointer``
    (logical pixels, ``None`` hides it) and ``hold`` copies of it (a still moment costs one render)."""

    app: Any
    size: tuple[float, float]
    pointer: tuple[float, float] | None = None
    pressed: bool = False
    hold: int = 1


@dataclass
class Clip:
    name: str
    title: str
    description: str
    fps: int
    make: Callable[[Clip], Any]
    live: bool = False
    #: Which frame becomes the poster, as a fraction of the clip.
    poster: float = 0.5
    tags: list[str] = field(default_factory=list)
    #: Only an animated WebP (and its poster), no MP4/WebM: for short illustrations shown as images.
    anim: bool = False
    #: The largest width of the encoded clip (0: MAX_WIDTH, or ANIM_WIDTH for ``anim`` clips).
    width: int = 0


CLIPS: dict[str, Clip] = {}


def clip(name: str, title: str, description: str, *, fps: int = 24, live: bool = False, poster: float = 0.5,
         tags: list[str] | None = None, anim: bool = False, width: int = 0):
    def register(fn):
        CLIPS[name] = Clip(name, title, description, fps, fn, live, poster, tags or [], anim, width)
        return fn

    return register


# -- games -----------------------------------------------------------------------------------------
def _snake_autopilot(app) -> None:
    """Steers toward the food without biting itself (a greedy pick among the three turns)."""
    from snake import COLS, ROWS

    hx, hy = app.body[0]
    fx, fy = app.food
    options = []
    for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if (d[0] + app.direction[0], d[1] + app.direction[1]) == (0, 0):
            continue
        nx, ny = (hx + d[0]) % COLS, (hy + d[1]) % ROWS
        if (nx, ny) in app.body[:-1]:
            continue
        dist = min(abs(nx - fx), COLS - abs(nx - fx)) + min(abs(ny - fy), ROWS - abs(ny - fy))
        free = sum(((nx + e[0]) % COLS, (ny + e[1]) % ROWS) not in app.body for e in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        options.append((dist - free * 0.3, d))
    if options:
        app.direction = min(options)[1]


@clip("snake", "Snake", "The Snake game from examples/games: a fixed-rate loop steering toward the food.",
      fps=24, tags=["games"])
def snake_clip(c: Clip):
    from snake import Snake

    app = Snake(seed=3)
    size = app.size
    acc = 0.0
    for _ in range(c.fps * 9):
        acc += min(app.speed, 12) / c.fps
        while acc >= 1:
            _snake_autopilot(app)
            app.step()
            acc -= 1
            if app.over:
                app.reset()
        yield Frame(app, size)


@clip("breakout", "Breakout", "Breakout from examples/games: a ball, a paddle that follows it and bricks that break.",
      fps=30, tags=["games"])
def breakout_clip(c: Clip):
    from breakout import Breakout

    app = Breakout(3)
    app.launch()
    for _ in range(c.fps * 8):
        for _ in range(2):
            app.paddle_x = app.ball_x + 18
            app.tick(1 / 60)
            if app.stuck:
                app.launch()
        yield Frame(app, app.size)


@clip("neon-invaders", "Neon Invaders", "Neon Invaders from examples/games: waves, shots, explosions and power-ups.",
      fps=30, tags=["games"])
def invaders_clip(c: Clip):
    from neon_invaders import NeonInvaders

    random.seed(5)
    app = NeonInvaders(5)
    app.started = True
    app.new_game()
    frame = 0
    for _ in range(c.fps * 9):
        for _ in range(2):
            frame += 1
            if frame % 9 == 0:
                app.fire()
            app.x = 380 + 160 * math.sin(frame / 45)
            app.hurt = 1  # the ship is not hit while it films
            app.tick(1 / 60)
        app.hurt = 0
        yield Frame(app, app.size)


@clip("game-of-life", "Game of Life", "Conway's Game of Life drawn on a canvas, one generation every few frames.",
      fps=20, tags=["apps"])
def life_clip(c: Clip):
    from game_of_life import Life

    random.seed(4)
    app = Life()
    app.randomize()
    for i in range(c.fps * 7):
        if i % 2 == 0:
            app.tick()
        yield Frame(app, app.size)


# -- the "Make games" path: animated WebP illustrations ---------------------------------------------
def _ticks(app, n: int, dt: float = 1 / 60) -> None:
    for _ in range(n):
        app.tick(dt)


def _toward(dx: float, dy: float, dead: float = 6.0) -> set[str]:
    """The arrow keys that steer along ``(dx, dy)``."""
    keys = set()
    if dx > dead:
        keys.add("right")
    elif dx < -dead:
        keys.add("left")
    if dy > dead:
        keys.add("down")
    elif dy < -dead:
        keys.add("up")
    return keys


@clip("game-first", "Coin Chase", "examples/games/coin_chase.py: an orb steered with held keys collects coins.",
      fps=15, tags=["games"], anim=True)
def first_game_clip(c: Clip):
    from coin_chase import CoinChase

    app = CoinChase(seed=7)
    for _ in range(c.fps * 6):
        app.held = _toward(app.coin[0] - app.x, app.coin[1] - app.y)
        _ticks(app, 60 // c.fps)
        yield Frame(app, app.size)


@clip("game-sprites", "Walker", "examples/games/walker.py: frame animation, flipping, a tweened jump and coins that pop.",
      fps=15, poster=0.3, tags=["games"], anim=True)
def sprites_clip(c: Clip):
    from walker import Walker

    app = Walker()
    script = [(set(), 0.8), ({"right"}, 1.0), ({"right", "space"}, 0.1), ({"right"}, 1.2), ({"right", "space"}, 0.1),
              ({"right"}, 0.9), ({"left"}, 1.4), ({"left", "space"}, 0.1), ({"left"}, 0.8), (set(), 1.0)]
    for keys, seconds in script:
        app.held = keys
        for _ in range(max(1, round(seconds * c.fps))):
            _ticks(app, 60 // c.fps)
            yield Frame(app, app.size)


@clip("game-jump-arc", "Jump Lab", "examples/games/jump_lab.py: gravity, a jump arc traced by the debug view, "
      "box collisions and bouncing balls.", fps=15, poster=0.45, tags=["games"], anim=True)
def jump_arc_clip(c: Clip):
    from jump_lab import JumpLab

    app = JumpLab(seed=3)
    # (keys held, seconds, press jump at the start)
    script = [(set(), 0.5, False), ({"right"}, 0.35, False), ({"right", "space"}, 0.7, True),
              ({"right"}, 0.5, False), ({"right", "space"}, 0.6, True), ({"right"}, 0.3, False),
              ({"right", "space"}, 0.75, True), ({"right"}, 0.6, False), (set(), 0.5, False),
              ({"left"}, 0.4, False), ({"left", "space"}, 0.25, True), ({"left"}, 1.2, False), (set(), 0.6, False)]
    for keys, seconds, jump in script:
        app.held = keys
        if jump:
            app.press_jump()
        for _ in range(max(1, round(seconds * c.fps))):
            _ticks(app, 60 // c.fps)
            yield Frame(app, app.size)


def _platformer_bot(app, P) -> None:
    """Runs right and jumps over walls, gaps, spikes and slimes."""
    p = app.player
    held = {"right"}
    row = int((p.bottom - 1) // P.TILE)
    wall = P.solid(int((p.right + 10) // P.TILE), row) or P.solid(int((p.right + 10) // P.TILE), row - 1)
    gap = not P.solid(int((p.right + 22) // P.TILE), row + 1)
    spikes = 0 <= row < P.ROWS and any(0 <= col < P.COLS and P.LEVEL[row][col] == "^"
                                       for col in range(int(p.right // P.TILE), int((p.right + 50) // P.TILE) + 1))
    slime = any(not e.squashed and 0 < e.rect.left - p.right < 70 and abs(e.rect.bottom - p.bottom) < 20
                for e in app.enemies)
    if app.on_ground and (wall or gap or spikes or slime):
        app.buffer = P.BUFFER
    if not app.on_ground and app.vy < 0:
        held.add("space")
    app.held = held


@clip("game-platformer", "Pixel Run", "examples/games/platformer.py: a tile map, a following camera, coins and "
      "slimes to stomp.", fps=12, poster=0.4, tags=["games"], anim=True)
def platformer_clip(c: Clip):
    import platformer as P

    app = P.Platformer(seed=1)
    for _ in range(c.fps * 7):
        for _ in range(60 // c.fps):
            _platformer_bot(app, P)
            app.tick(1 / 60)
        yield Frame(app, app.size)


def _asteroids_pilot(app, A, frame: int) -> None:
    """Turns toward the nearest rock (where it will be), fires when lined up, thrusts now and then."""
    if not app.rocks:
        app.held = set()
        return
    rock = min(app.rocks, key=lambda r: math.hypot(r.x - app.x, r.y - app.y))
    lead = math.hypot(rock.x - app.x, rock.y - app.y) / A.BULLET_SPEED
    tx, ty = rock.x + rock.vx * lead, rock.y + rock.vy * lead
    want = math.degrees(math.atan2(ty - app.y, tx - app.x))
    diff = (want - app.angle + 180) % 360 - 180
    held = {"right"} if diff > 4 else {"left"} if diff < -4 else set()
    if abs(diff) < 12:
        held.add("space")
    if (frame // 40) % 3 == 0 and math.hypot(rock.x - app.x, rock.y - app.y) > 160:
        held.add("up")
    app.held = held


@clip("game-asteroids", "Rock Storm", "examples/games/asteroids.py: thrust, wrap-around space, rocks that split "
      "and particles everywhere.", fps=12, poster=0.55, tags=["games"], anim=True)
def asteroids_clip(c: Clip):
    import asteroids as A

    app = A.Asteroids(seed=11)
    app.safe = 0.0
    frame = 0
    for _ in range(c.fps * 7):
        for _ in range(60 // c.fps):
            frame += 1
            _asteroids_pilot(app, A, frame)
            app.tick(1 / 60)
        yield Frame(app, app.size)


@clip("game-2048", "2048", "examples/games/game_2048.py: tiles slide, merge with a pop, and the score floats up.",
      fps=15, poster=0.6, tags=["games"], anim=True)
def puzzle_clip(c: Clip):
    import game_2048 as G

    app = G.Game2048(seed=5)
    for i in range(12):                      # a few moves in, so the board is not empty
        for d in ((1, 0), (0, -1), (0, 1), (-1, 0)):
            if app.move(d):
                break
    _ticks(app, 60)
    order = [(1, 0), (0, -1), (1, 0), (0, 1), (0, -1), (1, 0), (0, -1), (-1, 0)]
    for i in range(c.fps * 7):
        if i % 7 == 3:
            preferred = order[(i // 7) % len(order)]
            for d in (preferred, (1, 0), (0, -1), (0, 1), (-1, 0)):
                if app.move(d):
                    break
        _ticks(app, 60 // c.fps)
        yield Frame(app, app.size)


@clip("game-menus", "Orb Rush menus", "examples/games/menus.py: the title menu slides in, the game runs with its "
      "HUD, pauses, and the settings open.", fps=12, poster=0.12, tags=["games"], anim=True)
def menus_clip(c: Clip):
    from menus import OrbRush

    app = OrbRush(seed=2)
    app.settings["fps"] = True

    def hold(seconds, steer=False):
        for _ in range(max(1, round(seconds * c.fps))):
            if steer and app.orbs:
                orb = min(app.orbs, key=lambda o: abs(o[0] - app.x) + abs(o[1] - app.y) * 0.5)
                app.held = _toward(orb[0] - app.x, orb[1] - app.y)
            _ticks(app, 60 // c.fps)
            yield Frame(app, app.size)

    yield from hold(1.1)
    for key in ("down", "up"):
        app.on_key(key)
        yield from hold(0.35)
    app.on_key("enter")
    yield from hold(2.0, steer=True)
    app.held = set()
    app.on_key("escape")
    yield from hold(1.0)
    app.on_key("down")
    yield from hold(0.3)
    app.on_key("enter")
    yield from hold(0.9)
    app.settings["difficulty"] = "Hard"
    yield from hold(0.4)
    app.settings["shake"] = False
    yield from hold(0.6)
    app.on_key("escape")
    yield from hold(0.5)
    app.on_key("escape")
    yield from hold(0.8, steer=True)


@clip("game-high-scores", "Target Rush", "examples/games/high_scores.py: click the targets, enter a name, "
      "and the leaderboard is saved.", fps=15, poster=0.95, tags=["games"], anim=True)
def high_scores_clip(c: Clip):
    import high_scores as HS

    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    scores = HS.HighScores(work / "scores.json")
    for name, score in (("Grace", 4200), ("Alan", 3100), ("Linus", 1900), ("Margaret", 1200)):
        scores.add(name, score)
    app = HS.TargetRush(seed=4, path=work / "scores.json", sound_backend=None)
    pointer = (320.0, 380.0)
    yield Frame(app, app.size, pointer, hold=c.fps)
    pointer = (336.0 + 16, 383.0 + 60)
    yield Frame(app, app.size, pointer, pressed=True, hold=3)
    app.start()
    board = (16, 60)                          # where the canvas is in the window

    for _ in range(c.fps * 4):
        _ticks(app, 60 // c.fps)
        if app.targets:
            t = max(app.targets, key=lambda t: t[2])
            goal = (t[0] + board[0], t[1] + board[1])
            step = 0.35
            pointer = (pointer[0] + (goal[0] - pointer[0]) * step, pointer[1] + (goal[1] - pointer[1]) * step)
            if math.hypot(goal[0] - pointer[0], goal[1] - pointer[1]) < 8:
                app.click(t[0], t[1])
                yield Frame(app, app.size, pointer, pressed=True)
                continue
        yield Frame(app, app.size, pointer)
    app.time_left = 0.05
    app.score = max(app.score, 3400)
    _ticks(app, 60 // c.fps)
    yield Frame(app, app.size, pointer, hold=c.fps // 2)
    for ch in "Ada":
        app.set_name(app.name + ch)
        yield Frame(app, app.size, pointer, hold=4)
    yield Frame(app, app.size, pointer, hold=c.fps // 3)
    app.submit_name()
    yield Frame(app, app.size, pointer, hold=int(c.fps * 2.5))


# -- concepts --------------------------------------------------------------------------------------
class _Concept:
    """Base for the small record-only scenes that illustrate one idea of the game tutorials."""

    W, H = 640, 300
    title = "Concept"

    def __init__(self):
        import pyzed as pz

        self.pz = pz
        self.t = 0.0

    @property
    def size(self):
        return (self.W, self.H)

    def label(self, x, y, text, color="#94a3b8", size=13, align="center"):
        from pyzed import draw

        return draw.text(x, y, text, color=color, size=size, align_x=align, font="mono")


@clip("concept-particles", "Particles", "Four ways to use game.Particles: an explosion, a fountain, glowing sparks "
      "and a trail.", fps=15, tags=["games"], anim=True)
def particles_clip(c: Clip):
    import pyzed as pz
    from pyzed import draw, game

    class Scene(_Concept, pz.App):
        def __init__(self):
            super().__init__()
            self.boom = game.Particles(drag=1.5, seed=1)
            self.fountain = game.Particles(gravity=520, seed=2)
            self.sparks = game.Particles(drag=2.5, seed=3)
            self.trail = game.Particles(drag=3, seed=4)

        def tick(self, dt):
            self.t += dt
            if int(self.t * 60) % 50 == 0:
                self.boom.burst(80, 140, count=50, color=["#f97316", "#fbbf24", "#ffffff"], speed=(40, 220),
                                life=(0.4, 1.0))
            self.fountain.burst(240, 230, count=3, angle=-90, spread=30, speed=(220, 320), life=(0.6, 1.1),
                                color=["#22d3ee", "#a5f3fc"])
            if int(self.t * 60) % 30 == 0:
                self.sparks.burst(400, 140, count=24, color=["#f472b6", "#c084fc"], speed=(60, 260),
                                  life=(0.2, 0.6), size=(1, 2.5))
            x, y = 560 + math.cos(self.t * 3) * 50, 140 + math.sin(self.t * 6) * 40
            self.trail.burst(x, y, count=4, speed=(5, 30), life=(0.3, 0.7), color=["#a3e635", "#facc15"])
            self.head = (x, y)
            for p in (self.boom, self.fountain, self.sparks, self.trail):
                p.update(dt)

        def view(self):
            shapes = [draw.background("#0b0e14")]
            for i in range(1, 4):
                shapes.append(draw.line(i * 160, 20, i * 160, 260, stroke="#ffffff10"))
            shapes += self.boom.shapes(glow=True) + self.fountain.shapes() + self.sparks.shapes(glow=True)
            shapes += self.trail.shapes(glow=True) + game.glow(*self.head, 6, "#facc15", layers=3)
            for x, text in ((80, "burst()"), (240, "fountain"), (400, "glow=True"), (560, "trail")):
                shapes.append(self.label(x, 270, text))
            return pz.canvas(shapes, width=self.W, height=self.H)

    app = Scene()
    _ticks(app, 30)
    for _ in range(c.fps * 5):
        _ticks(app, 60 // c.fps)
        yield Frame(app, app.size)


@clip("concept-collisions", "Box and circle collisions", "AABB overlap, the push-out along the shortest axis, and a "
      "ball bouncing off a box with game.circle_rect.", fps=15, tags=["games"], anim=True)
def collisions_clip(c: Clip):
    import pyzed as pz
    from pyzed import draw, game

    class Scene(_Concept, pz.App):
        def __init__(self):
            super().__init__()
            self.wall = game.Rect(110, 110, 110, 80)
            self.box = game.Rect(0, 0, 60, 46)
            self.paddle = game.Rect(410, 170, 150, 22)
            self.ball = [470.0, 60.0, 130.0, 0.0]
            self.normal = None
            self.flash = 0.0

        def tick(self, dt):
            self.t += dt
            a = self.t * 1.3
            self.box.x, self.box.y = 135 + math.cos(a) * 105 - 30, 150 + math.sin(a * 2) * 60 - 23
            bx, by, vx, vy = self.ball
            vy += 900 * dt
            bx, by = bx + vx * dt, by + vy * dt
            if bx < 340 or bx > 620:
                vx = -vx
            hit = game.circle_rect(bx, by, 12, self.paddle)
            if hit:
                nx, ny = hit
                if ny:
                    vy = abs(vy) * ny
                    by = self.paddle.top - 12 if ny < 0 else self.paddle.bottom + 12
                if nx:
                    vx = abs(vx) * nx
                self.normal, self.flash = (bx, by, nx, ny), 0.5
            self.flash = max(0.0, self.flash - dt)
            self.ball = [bx, by, vx, vy]

        def view(self):
            shapes = [draw.background("#0b0e14"), draw.line(320, 20, 320, 280, stroke="#ffffff12")]
            hit = self.box.overlaps(self.wall)
            color = "#f87171" if hit else "#34d399"
            shapes.append(self.wall.shape(fill="#1e293b", stroke="#94a3b8", width=1.5))
            shapes.append(self.box.shape(fill=game.rgba(color, 0.25), stroke=color, width=2))
            if hit:   # the overlap, and the shortest way out of it
                ox1, oy1 = max(self.box.left, self.wall.left), max(self.box.top, self.wall.top)
                ox2, oy2 = min(self.box.right, self.wall.right), min(self.box.bottom, self.wall.bottom)
                shapes.append(draw.rect(ox1, oy1, ox2 - ox1, oy2 - oy1, fill="#fbbf2466"))
                cx, cy = self.box.center
                wx, wy = self.wall.center
                w, h = ox2 - ox1, oy2 - oy1
                dx, dy = ((w if cx > wx else -w), 0) if w < h else (0, (h if cy > wy else -h))
                shapes.append(draw.line(cx, cy, cx + dx, cy + dy, stroke="#fbbf24", width=3, cap="round"))
            shapes.append(self.label(165, 24, "overlaps: " + ("yes" if hit else "no"), color))
            shapes.append(self.label(165, 270, "Rect.overlaps + push-out"))
            lit = self.flash > 0
            shapes.append(self.paddle.shape(fill="#1e293b", stroke="#fbbf24" if lit else "#94a3b8", width=1.5))
            bx, by = self.ball[:2]
            shapes += game.glow(bx, by, 12, "#22d3ee", layers=2, strength=0.3)
            if self.normal and lit:
                x, y, nx, ny = self.normal
                shapes.append(draw.line(x, y, x + nx * 40, y + ny * 40, stroke=game.rgba("#fbbf24", self.flash * 2),
                                        width=3, cap="round"))
                shapes.append(self.label(x + 50, y - 30, f"normal ({nx:+.0f}, {ny:+.0f})",
                                         game.rgba("#fbbf24", min(1, self.flash * 2)), 12))
            shapes.append(self.label(480, 270, "game.circle_rect"))
            return pz.canvas(shapes, width=self.W, height=self.H)

    app = Scene()
    for _ in range(round(c.fps * 4.8)):
        _ticks(app, 60 // c.fps)
        yield Frame(app, app.size)


@clip("concept-easing", "Easing curves", "Four tweens over the same second: linear, ease-out, ease-in-out and "
      "ease-out-back.", fps=15, tags=["games"], anim=True)
def easing_clip(c: Clip):
    import pyzed as pz
    from pyzed import draw, game
    from walker import ease_in_out_sine, ease_out_back, ease_out_cubic, linear

    curves = [("linear", linear, "#94a3b8"), ("ease_out_cubic", ease_out_cubic, "#22d3ee"),
              ("ease_in_out_sine", ease_in_out_sine, "#a3e635"), ("ease_out_back", ease_out_back, "#f472b6")]

    class Scene(_Concept, pz.App):
        def tick(self, dt):
            self.t += dt

        def view(self):
            cycle = self.t % 2.2
            k = game.clamp(cycle / 1.2, 0, 1)            # one second of motion, then a pause
            shapes = [draw.background("#0b0e14")]
            for i, (name, ease, color) in enumerate(curves):
                y = 50 + i * 62
                shapes.append(self.label(20, y - 8, name, color, 12, "start"))
                shapes.append(draw.line(190, y, 600, y, stroke="#ffffff14", width=2))
                for j in range(5, 0, -1):            # where it was a moment ago: the gaps show the speed
                    past = game.clamp((cycle - j * 0.05) / 1.2, 0, 1)
                    shapes.append(draw.circle(game.lerp(200, 590, ease(past)), y, 4,
                                              fill=game.rgba(color, 0.12 * (6 - j))))
                shapes += game.glow(game.lerp(200, 590, ease(k)), y, 10, color, layers=3, strength=0.4)
            return pz.canvas(shapes, width=self.W, height=270)

        @property
        def size(self):
            return (self.W, 270)

    app = Scene()
    for _ in range(round(c.fps * 4.4)):
        _ticks(app, 60 // c.fps)
        yield Frame(app, app.size)


@clip("concept-juice", "Juice", "The same hit, plain and with juice: hit-stop, a flash, particles, screen shake "
      "and a squash.", fps=15, tags=["games"], anim=True)
def juice_clip(c: Clip):
    import pyzed as pz
    from pyzed import draw, game

    class Scene(_Concept, pz.App):
        def __init__(self):
            super().__init__()
            self.sparks = game.Particles(gravity=400, drag=1.2, seed=3)
            self.shake = game.Shake(seed=3)
            self.reset()

        def reset(self):
            self.ball = 40.0          # the balls' x on each side, moving right
            self.hit = None           # seconds since the hit
            self.freeze = 0.0

        def tick(self, dt):
            self.sparks.update(dt)
            self.shake.update(dt)
            if self.freeze > 0:       # hit-stop: the world pauses for a few frames
                self.freeze -= dt
                return
            self.t += dt
            if self.hit is None:
                self.ball += 420 * dt
                if self.ball >= 220:
                    self.hit = 0.0
                    self.freeze = 0.07
                    self.sparks.burst(320 + 230, 150, count=40, color=["#fbbf24", "#f97316", "#ffffff"],
                                      speed=(80, 320))
                    self.shake.kick(9)
            else:
                self.hit += dt
                if self.hit > 1.4:
                    self.reset()

        def side(self, x0, juicy):
            shapes = []
            block_alive = self.hit is None
            bx = x0 + self.ball
            if block_alive:
                shapes.append(draw.rect(x0 + 230, 120, 40, 60, radius=4, fill="#64748b"))
            elif juicy and self.hit < 0.08:
                shapes.append(draw.rect(x0 + 226, 116, 48, 68, radius=6, fill="#ffffff"))   # the flash
            if block_alive:
                squash = 1.0
                if juicy:
                    shapes += game.glow(bx, 150, 12, "#22d3ee", layers=3, strength=0.3)
                shapes.append(draw.circle(bx, 150, 12 * squash, fill="#22d3ee"))
            elif juicy:
                k = min(1.0, self.hit / 0.25)
                sx = 1.4 - 0.4 * k
                shapes += [draw.save(), draw.translate(x0 + 210, 150), draw.scale(sx, 1 / sx),
                           draw.circle(0, 0, 12, fill="#22d3ee"), draw.restore()]
            else:
                shapes.append(draw.circle(x0 + 210, 150, 12, fill="#22d3ee"))
            return shapes

        def view(self):
            shapes = [draw.background("#0b0e14"), draw.line(320, 20, 320, 280, stroke="#ffffff12")]
            shapes += self.side(0, False)
            shapes += [draw.save(), *self.shake.shapes()] + self.side(320, True) + self.sparks.shapes(glow=True)
            shapes.append(draw.restore())
            shapes.append(self.label(160, 30, "plain"))
            shapes.append(self.label(480, 30, "juicy", "#fbbf24"))
            return pz.canvas(shapes, width=self.W, height=self.H)

    app = Scene()
    for _ in range(round(c.fps * 4.0)):
        _ticks(app, 60 // c.fps)
        yield Frame(app, app.size)


# -- shaders ---------------------------------------------------------------------------------------
class _ShaderWall:
    """A grid of the showcase's shader graphs, all drawn at the time ``t``."""

    title = "Shaders"

    def __init__(self):
        import pyzed as pz

        self.pz = pz
        self.t = 0.0
        folder = EXAMPLES / "showcase" / "shaders"
        self.names = ["plasma", "tunnel", "fire", "voronoi", "synthwave", "nebula"]
        self.files = [str(folder / f"{n}.pzshad") for n in self.names]
        self.theme = "One Dark"

    def view(self):
        pz = self.pz
        from pyzed import ui

        cells = []
        for name, path in zip(self.names, self.files):
            cells.append(pz.column([
                pz.container(pz.shader(path, width=300, height=180, time=self.t), radius=10, clip=True),
                ui.label(name.capitalize(), size="sm", color="text_muted"),
            ], spacing=6))
        rows = [pz.row(cells[i:i + 3], spacing=16) for i in range(0, len(cells), 3)]
        return pz.container(pz.column(rows, spacing=14), padding=24, width="fill", height="fill", center=True,
                            bg=self.pz.themes.get("One Dark").editor)


@clip("shaders", "Shader graphs", "Six node-based shaders from examples/showcase/shaders running at once.",
      fps=24, tags=["shading", "showcase"])
def shaders_clip(c: Clip):
    import pyzed as pz

    class Wall(_ShaderWall, pz.App):
        pass

    app = Wall()
    for i in range(c.fps * 8):
        app.t = i / c.fps
        yield Frame(app, (1000, 520))


# -- themes ----------------------------------------------------------------------------------------
THEMES = ["One Dark", "One Light", "Ayu Mirage", "Gruvbox Dark", "Ayu Light", "Gruvbox Light"]


@clip("themes", "One app, six themes", "The component gallery (examples/gallery.py) switching between built-in themes.",
      fps=12, poster=0.0, tags=["library", "theming"])
def themes_clip(c: Clip):
    import pyzed as pz
    from gallery import Gallery

    for name in THEMES:
        app = Gallery(pz.themes.get(name))
        yield Frame(app, (1280, 800), hold=int(c.fps * 1.3))


@clip("designer-themes", "Pyzed Design in other themes", "Pyzed Design's own look following the theme picked in Settings.",
      fps=12, poster=0.0, tags=["designer", "theming"], anim=True, width=960)
def designer_themes_clip(c: Clip):
    import pyzed as pz

    app = _designer(EXAMPLES / "designer" / "login.pzform")
    app.doc.select("sign_in")
    app._selection_changed()
    for name in THEMES:
        app.theme = pz.themes.get(name)
        yield Frame(app, DESIGNER_SIZE, hold=int(c.fps * 1.3))


# -- forms -----------------------------------------------------------------------------------------
@clip("form-validation", "A form validating as you type",
      "The login form made in Pyzed Design: a wrong email is flagged, fixed, then Sign in runs its progress.",
      fps=24, poster=0.3, tags=["designer", "forms"])
def form_clip(c: Clip):
    import pyzed as pz
    from pyzed.designer.runtime import FormWindow, load_handlers

    path = EXAMPLES / "designer" / "login.pzform"
    form = _designer(path).doc.form  # the form with its code (login.py), as Run opens it
    form["email"].bind = "email"
    form["email"].rules = {"required": True, "pattern": r"[^@]+@[^@]+\.\w+", "message": "Enter a valid email"}
    form["password"].bind = "password"
    form["password"].rules = {"required": True, "min_length": 8}
    window = FormWindow(form, load_handlers(path, form), path=path)
    rt = window.runtime
    rt.load()

    class Host(pz.App):
        def __init__(self):
            self.theme = rt.theme

        def view(self):
            return window.view()

    app = Host()
    size = (int(form.width), int(form.height))
    email, password, remember, sign_in = (rt.form[n] for n in ("email", "password", "remember", "sign_in"))
    pos = {"email": (230, 168), "password": (230, 232), "remember": (40, 277), "sign_in": (236, 321)}
    pointer = (380.0, 380.0)

    def move(to, frames=10):
        nonlocal pointer
        for p in glide(pointer, to, frames):
            pointer = p
            yield Frame(app, size, pointer)

    def type_into(control, text, start=""):
        value = start
        for ch in text:
            value += ch
            rt.ctx.on(control, "change", "text")(value)
            if control is email:
                rt.validate(["email"])
            yield Frame(app, size, pointer, hold=2)

    yield Frame(app, size, pointer, hold=12)
    yield from move(pos["email"])
    yield Frame(app, size, pointer, pressed=True, hold=3)
    yield from type_into(email, "ada.lovelace")
    yield Frame(app, size, pointer, hold=12)
    yield from type_into(email, "@analytical.dev", "ada.lovelace")
    yield Frame(app, size, pointer, hold=10)
    yield from move(pos["password"])
    yield Frame(app, size, pointer, pressed=True, hold=3)
    yield from type_into(password, "babbage1843")
    yield from move(pos["remember"])
    yield Frame(app, size, pointer, pressed=True, hold=3)
    rt.ctx.on(remember, "change", "checked")(False)
    yield Frame(app, size, pointer, hold=6)
    yield from move(pos["sign_in"])
    yield Frame(app, size, pointer, pressed=True, hold=3)
    rt.dispatch(sign_in, "click")
    ticker = rt.form["ticker"]
    for _ in range(30):
        rt.dispatch(ticker, "tick")
        yield Frame(app, size, pointer)
    yield Frame(app, size, pointer, hold=c.fps * 2)


# -- Pyzed Design ----------------------------------------------------------------------------------
def _designer(path=None):
    from pyzed.designer.app import Designer

    app = Designer(path, language_servers=False)
    app.frame = "gnome"
    app.toasts.clear()
    app.dialog = None
    return app


#: Where things are in a 1280x800 designer window (logical pixels), for the pointer the clips draw.
DESIGNER_SIZE = (1280, 800)


@clip("designer-place-controls", "Placing controls from the toolbox",
      "Pyzed Design: a button, a text box and a check box dragged from the toolbox onto an empty form.",
      fps=24, poster=0.98, tags=["designer"], anim=True, width=960)
def designer_place_clip(c: Clip):
    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    app = _designer(work / "form1.pzform")
    size = DESIGNER_SIZE
    origin = _form_origin(app)
    rows = {"label": 204, "button": 255, "input": 281, "checkbox": 333}
    pointer = (640.0, 600.0)
    yield Frame(app, size, pointer, hold=10)
    drops = [("label", (24, 20)), ("input", (24, 56)), ("checkbox", (24, 104)), ("button", (24, 146))]
    for type_, (fx, fy) in drops:
        start = (70.0, float(rows.get(type_, 255)))
        for p in glide(pointer, start, 12):
            pointer = p
            yield Frame(app, size, pointer)
        app.window_pointer = pointer
        app.press_tool(type_)
        yield Frame(app, size, pointer, pressed=True, hold=3)
        target = (origin[0] + fx + 6, origin[1] + fy + 6)
        app.enter_form()
        for p in glide(pointer, target, 16):
            pointer = p
            app.window_moved(*p)
            app.pointer_moved(p[0] - origin[0], p[1] - origin[1])
            yield Frame(app, size, pointer, pressed=True)
        app.window_release()
        app.toasts.clear()
        yield Frame(app, size, pointer, hold=8)
    yield Frame(app, size, pointer, hold=c.fps)


@clip("designer-tabs-anywhere", "Tabs anywhere",
      "Pyzed Design: the Events panel dragged next to the forms, a form dragged into the left dock and both "
      "dragged back, with the target lit up and a copy of the tab under the pointer.",
      fps=24, poster=0.3, tags=["designer"], anim=True, width=960)
def designer_tabs_clip(c: Clip):
    from types import SimpleNamespace

    from pyzed.designer.document import Document

    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    app = _designer(work / "login.pzform")
    app.doc.form.name = "login"
    for type_, y in (("heading", 20), ("input", 70), ("input", 120), ("button", 170)):
        app.doc.add(type_, 24, y)
    app.doc.select([])
    second = Document()
    second.form.name = "settings"
    second.add("switch", 24, 24)
    second.add("slider", 24, 70)
    app.doc = second
    size = DESIGNER_SIZE
    app.window_size, app.window_position = size, (0.0, 0.0)
    tabs = app.dock_windows
    pointer = (700.0, 500.0)

    def drag(place, key, start, end, row=None):
        nonlocal pointer
        for p in glide(pointer, start, 12):
            pointer = p
            yield Frame(app, size, pointer)
        app.window_moved(*start)
        tabs.start_drag(place, key)
        yield Frame(app, size, pointer, pressed=True, hold=3)
        for p in glide(start, end, 22):
            pointer = p
            app.window_moved(*p)
            if row is not None and p == end:
                tabs.drag_over(*row)
            yield Frame(app, size, pointer, pressed=True)
        yield Frame(app, size, pointer, pressed=True, hold=10)
        tabs.drop(place, key, SimpleNamespace(window_x=end[0], window_y=end[1], screen=None))
        app.toasts.clear()
        yield Frame(app, size, pointer, hold=14)

    yield Frame(app, size, pointer, hold=12)
    yield from drag("right", "events", (1098.0, 49.0), (640.0, 420.0))  # next to the forms
    yield from drag("main", "1", (528.0, 48.0), (110.0, 470.0))  # a form into the left dock
    yield from drag("main", "events", (480.0, 48.0), (1047.0, 49.0), row=("right", 1))  # back between two panels
    yield from drag("left", "0", (90.0, 49.0), (432.0, 48.0), row=("main", 1))  # the form back among the forms
    yield Frame(app, size, pointer, hold=c.fps)


@clip("designer-timer-outline", "A timer in the tray and the Outline",
      "Pyzed Design: a Timer dragged onto the login form lands in the tray under it, not on the form; then the "
      "Outline selects a control and the form's timer, listed under Non-visual.",
      fps=20, poster=0.97, tags=["designer"], anim=True, width=960)
def designer_timer_outline_clip(c: Clip):
    app = _designer(EXAMPLES / "designer" / "login.pzform")
    app.left_ratio = 0.4  # room in the Outline for every control and the Non-visual list
    app.doc.select(None)
    app._selection_changed()
    size = DESIGNER_SIZE
    origin = _form_origin(app)
    pointer = (640.0, 640.0)

    def move(to, frames=12, pressed=False):
        nonlocal pointer
        for p in glide(pointer, to, frames):
            pointer = p
            if pressed:
                app.window_moved(*p)
                app.pointer_moved(p[0] - origin[0], p[1] - origin[1])
            yield Frame(app, size, pointer, pressed=pressed)

    def outline_click(name, y):
        yield from move((90.0, y))
        app.enter_row(f"outline:{name}")
        app.window_moved(*pointer)
        app.press_outline(name)
        yield Frame(app, size, pointer, pressed=True, hold=3)
        app.window_release()
        yield Frame(app, size, pointer, hold=c.fps)
        app.leave_row(f"outline:{name}")

    yield Frame(app, size, pointer, hold=10)
    # find the Timer in the toolbox and drag it onto the form: it goes to the tray
    yield from move((110.0, 117.0), 10)
    typed = ""
    for ch in "tim":
        typed += ch
        app.set_toolbox_query(typed)
        yield Frame(app, size, pointer, hold=2)
    yield from move((60.0, 203.0), 8)
    app.window_moved(*pointer)
    app.press_tool("timer")
    yield Frame(app, size, pointer, pressed=True, hold=3)
    app.enter_form()
    yield from move((origin[0] + 220.0, origin[1] + 130.0), 18, pressed=True)
    app.window_release()
    app.toasts.clear()
    yield Frame(app, size, pointer, hold=int(c.fps * 1.6))
    app.set_toolbox_query("")
    # the Outline: a control, then the form's own timer under Non-visual
    yield from outline_click("email", 561.0)
    yield from outline_click("ticker", 703.0)
    yield Frame(app, size, pointer, hold=c.fps)


def _form_origin(app) -> tuple[float, float]:
    """Where the form's top-left corner is in the window: the left dock, the canvas's margin and the
    title bar the canvas draws around the form (GNOME's, see ``_designer``)."""
    from pyzed.designer import surface
    from pyzed.ui import frame as ui_frame

    return (240.0 + surface.MARGIN + 1, 102.0 + surface.MARGIN + ui_frame.HEIGHTS["gnome"] + 1)


@clip("shader-graph", "Building a shader graph",
      "Pyzed Design's Shader view: Voronoi and Palette nodes dragged in and wired to the Output, with live previews.",
      fps=24, poster=0.85, tags=["designer", "shading"])
def shader_graph_clip(c: Clip):
    from pyzed import shading
    from pyzed.shading import layout as L
    from pyzed.shading.nodes import PRESETS

    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    g = shading.new("cells")
    for node_id in [n.id for n in g.nodes.values() if n.type != "output"]:
        g.remove(node_id)
    path = g.save(work / "cells.pzshad")
    app = _designer(path)
    ed = app.shading
    doc = app.doc
    size = DESIGNER_SIZE
    t0 = 0.0
    frame = 0

    def tick():
        nonlocal frame
        frame += 1
        ed.paused = t0 + frame / c.fps

    out = doc.graph.output_node
    out.x, out.y = 540.0, 40.0
    doc.zoom, doc.pan = 0.78, (30.0, 130.0)
    doc.fit_pending = False
    canvas = (240.0, 101.0)  # the canvas's top-left corner in the window

    def to_window(x, y):
        vx, vy = doc.to_view(x, y)
        return (canvas[0] + vx, canvas[1] + vy)

    pointer = (700.0, 520.0)
    tick()
    yield Frame(app, size, pointer, hold=8)
    keys = {p.type: p.key for p in PRESETS}
    ed.set_query("")
    for type_, at in (("voronoi", (10.0, 40.0)), ("palette", (275.0, 40.0))):
        ed.set_query(type_[:4])
        tick()
        yield Frame(app, size, pointer, hold=6)
        start = (70.0, 176.0)  # the first match under the sidebar's search
        for p in glide(pointer, start, 12):
            pointer = p
            tick()
            yield Frame(app, size, pointer)
        app.window_pointer = pointer
        ed.press_preset(keys[type_])
        tick()
        yield Frame(app, size, pointer, pressed=True, hold=2)
        target = to_window(at[0] + L.WIDTH / 2, at[1] + 15)
        for p in glide(pointer, target, 16):
            pointer = p
            app.window_moved(*p)
            ed.enter()
            ed.moved(p[0] - canvas[0], p[1] - canvas[1])
            tick()
            yield Frame(app, size, pointer, pressed=True)
        app.window_release()
        ed.set_query("")
        tick()
        yield Frame(app, size, pointer, hold=6)
    g = doc.graph
    vor = next(n for n in g.nodes.values() if n.type == "voronoi")
    pal = next(n for n in g.nodes.values() if n.type == "palette")
    out = g.output_node
    for src, port, dst, inp in ((vor, "distance", pal, "t"), (pal, "rgb", out, "color")):
        a = to_window(*L.port_position(g, src, port, True))
        b = to_window(*L.port_position(g, dst, inp, False))
        for p in glide(pointer, a, 10):
            pointer = p
            tick()
            yield Frame(app, size, pointer)
        ed.press_port(src.id, port, True)
        ed.over = True
        for p in glide(pointer, b, 14):
            pointer = p
            ed.moved(p[0] - canvas[0], p[1] - canvas[1])
            tick()
            yield Frame(app, size, pointer, pressed=True)
        ed.release()
        tick()
        yield Frame(app, size, pointer, hold=4)
    away = (900.0, 700.0)
    for p in glide(pointer, away, 10):
        pointer = p
        tick()
        yield Frame(app, size, pointer)
    for _ in range(c.fps * 3):
        tick()
        yield Frame(app, size, None)


@clip("shader-preview", "A shader's Preview tab", "The Preview tab of the Shader view: the glow ring pulsing as time runs.",
      fps=24, tags=["designer", "shading"])
def shader_preview_clip(c: Clip):
    from pyzed.designer import shader_editor

    work = Path(tempfile.mkdtemp(prefix="pyzed-record-"))
    src = ROOT / "python" / "pyzed" / "designer" / "templates" / "shaders" / "glow_ring.pzshad"
    shutil.copy(src, work / src.name)
    app = _designer(work / src.name)
    shader_editor.set_tab(app, "preview")
    for i in range(c.fps * 6):
        app.shading.paused = i / c.fps
        yield Frame(app, DESIGNER_SIZE)


# -- live: hover and press effects -----------------------------------------------------------------
def controls_app():
    """The demo the ``hover`` clip films: buttons, a switch, a check box, a slider and tabs."""
    import pyzed as pz
    from pyzed import ui

    class Controls(pz.App):
        title = "Controls"
        size = (640, 360)
        theme = "One Dark"

        def __init__(self):
            self.on, self.checked, self.volume, self.view_ = False, False, 0.3, "Day"
            self.saved = 0
            self.toasts = []

        def save(self):
            self.saved += 1
            self.toasts = [("Saved", f"Saved {self.saved} time{'s' if self.saved > 1 else ''}")]

        def view(self):
            body = pz.container(pz.column([
                ui.heading("Controls", level=3),
                pz.row([
                    ui.button("Save", self.save, icon="save", variant="solid"),
                    ui.button("Outline", lambda: None, variant="outline"),
                    ui.button("Ghost", lambda: None, variant="ghost"),
                    ui.tooltip(ui.button(None, lambda: None, icon="settings", variant="ghost"), "Settings"),
                ], spacing=12, align="center"),
                pz.row([ui.switch(self.on, lambda v: setattr(self, "on", v), label="Wi-Fi"),
                        ui.checkbox(self.checked, lambda v: setattr(self, "checked", v), label="Remember me")],
                       spacing=32, align="center"),
                pz.row([ui.label("Volume", width=80), ui.slider(self.volume, lambda v: setattr(self, "volume", v)),
                        ui.label(f"{self.volume:.0%}", width=48)], spacing=12, align="center"),
                ui.segmented(["Day", "Week", "Month"], self.view_, lambda v: setattr(self, "view_", v)),
            ], spacing=22), padding=32, width="fill", height="fill")
            return ui.toasts(body, [ui.toast(t, m, kind="success") for t, m in self.toasts])

    return Controls


LIVE_APPS = {"controls": controls_app}


@clip("hover", "Hover, press and toggle",
      "Pyzed controls reacting to a real pointer: hover and press states, a tooltip, a switch, a check box, a slider.",
      fps=30, live=True, poster=0.35, tags=["library"])
def hover_clip(c: Clip):
    """Steps for the live recorder: ("move", x, y, seconds), ("down",), ("up",), ("wait", seconds)."""
    steps = [
        ("move", 560, 320, 0.0), ("wait", 0.6),
        ("move", 66, 89, 0.7), ("wait", 0.6), ("down",), ("wait", 0.15), ("up",), ("wait", 0.8),
        ("move", 145, 89, 0.5), ("wait", 0.5), ("move", 217, 89, 0.4), ("wait", 0.5),
        ("move", 274, 89, 0.4), ("wait", 1.2),
        ("move", 50, 134, 0.6), ("wait", 0.3), ("down",), ("up",), ("wait", 0.6),
        ("move", 147, 134, 0.6), ("wait", 0.3), ("down",), ("up",), ("wait", 0.6),
        ("move", 254, 174, 0.5), ("down",), ("move", 470, 174, 0.8), ("move", 400, 174, 0.4), ("up",), ("wait", 0.5),
        ("move", 101, 219, 0.6), ("down",), ("up",), ("wait", 0.5),
        ("move", 156, 219, 0.4), ("down",), ("up",), ("wait", 1.0),
    ]
    pace = 0.7  # a bit brisker than the numbers above, to stay near 10 s
    steps = [(k, *a[:2], a[2] * pace) if k == "move" else (k, a[0] * pace) if k == "wait" else (k,)
             for k, *a in steps]
    return "controls", (640, 360), steps


# -- rendering -------------------------------------------------------------------------------------
def render_offscreen(c: Clip, folder: Path) -> int:
    """Renders the clip's frames to ``folder/00001.png``...; returns how many there are."""
    import pyzed as pz
    from PIL import Image

    n = 0
    last: Path | None = None
    started = time.time()
    for frame in c.make(c):
        path = folder / "render.png"
        pz.screenshot(frame.app, path, size=frame.size, scale=SCALE, wait=0.0)
        with Image.open(path) as im:
            im = im.convert("RGB")
            if frame.pointer is not None:
                draw_pointer(im, (frame.pointer[0] * SCALE, frame.pointer[1] * SCALE), frame.pressed, SCALE)
            for _ in range(frame.hold):
                n += 1
                last = folder / f"{n:05d}.png"
                im.save(last, compress_level=1)
    print(f"  {n} frames in {time.time() - started:.0f}s")
    return n


def render_live(c: Clip, folder: Path) -> Path:
    """Runs the clip's app in Xvfb at 2x, plays its pointer script and films it; returns the capture."""
    from Xlib import X, display
    from Xlib.ext import xtest

    app_name, size, steps = c.make(c)
    w, h = int(size[0] * SCALE), int(size[1] * SCALE)
    num = 90 + os.getpid() % 100
    xvfb = subprocess.Popen(["Xvfb", f":{num}", "-screen", "0", f"{w}x{h}x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    env = {**os.environ, "DISPLAY": f":{num}", "WINIT_X11_SCALE_FACTOR": str(SCALE)}
    capture = folder / "capture.mkv"
    procs = [xvfb]
    try:
        time.sleep(1.0)
        app = subprocess.Popen([sys.executable, __file__, "--serve", app_name], env=env)
        procs.append(app)
        time.sleep(4.0)  # the window opens and draws its first frames
        grab = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "x11grab", "-draw_mouse", "1",
                                 "-framerate", str(c.fps), "-video_size", f"{w}x{h}", "-i", f":{num}+0,0",
                                 "-c:v", "libx264rgb", "-preset", "ultrafast", "-crf", "0", str(capture)],
                                env=env, stdin=subprocess.PIPE)
        procs.append(grab)
        dpy = display.Display(f":{num}")
        pos = [w / 2, h / 2]

        def warp(x, y):
            xtest.fake_input(dpy, X.MotionNotify, x=int(x), y=int(y))
            dpy.sync()

        time.sleep(0.3)
        for step in steps:
            kind = step[0]
            if kind == "move":
                x, y, seconds = step[1] * SCALE, step[2] * SCALE, step[3]
                frames = max(1, int(seconds * 60))
                for p in glide(tuple(pos), (x, y), frames):
                    warp(*p)
                    time.sleep(seconds / frames if seconds else 0)
                pos = [x, y]
            elif kind == "down":
                xtest.fake_input(dpy, X.ButtonPress, 1)
                dpy.sync()
                time.sleep(0.08)
            elif kind == "up":
                xtest.fake_input(dpy, X.ButtonRelease, 1)
                dpy.sync()
                time.sleep(0.05)
            elif kind == "wait":
                time.sleep(step[1])
        time.sleep(0.3)
        grab.communicate(b"q", timeout=30)
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
    return capture


# -- encoding --------------------------------------------------------------------------------------
def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def _probe_size(path: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def encode(c: Clip, source: list[str], width: int, frames: int, folder: Path) -> dict[str, Any]:
    """Encodes the frames (``source``: ffmpeg input arguments) into the clip's files in OUT."""
    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    scale = f"scale={width}:-2:flags=lanczos"
    files: dict[str, Path] = {}

    def fit(ext: str, start: int, stop: int, step: int, args: Callable[[int], list[str]]) -> Path:
        out = OUT / f"{c.name}.{ext}"
        q = start
        while True:
            _ffmpeg(*source, *args(q), str(out))
            if out.stat().st_size <= BUDGET or q >= stop:
                return out
            q += step

    files["mp4"] = fit("mp4", 26, 40, 3, lambda q: [
        "-vf", f"{scale},format=yuv420p", "-c:v", "libx264", "-preset", "veryslow", "-tune", "animation",
        "-crf", str(q), "-movflags", "+faststart", "-an"])
    files["webm"] = fit("webm", 36, 54, 4, lambda q: [
        "-vf", scale, "-c:v", "libvpx-vp9", "-crf", str(q), "-b:v", "0", "-row-mt", "1", "-deadline", "good",
        "-cpu-used", "2", "-pix_fmt", "yuv420p", "-an"])
    # the poster: one frame as a light WebP
    poster = OUT / f"{c.name}.poster.webp"
    index = max(1, min(frames, int(frames * c.poster)))
    still = folder / "poster.png"
    _ffmpeg(*source, "-vf", f"select=eq(n\\,{index - 1}),{scale}", "-frames:v", "1", str(still))
    with Image.open(still) as im:
        im.save(poster, "WEBP", quality=82, method=6)
    files["poster"] = poster
    # an animated WebP, kept only when it beats the MP4
    anim = OUT / f"{c.name}.webp"
    _ffmpeg(*source, "-vf", scale, "-c:v", "libwebp_anim", "-q:v", "60", "-compression_level", "6", "-loop", "0",
            "-an", str(anim))
    if anim.stat().st_size < files["mp4"].stat().st_size:
        files["webp"] = anim
    else:
        anim.unlink()
    w, h = _probe_size(files["mp4"])
    entry = {
        "name": c.name,
        "title": c.title,
        "description": c.description,
        "tags": c.tags,
        "width": w,
        "height": h,
        "fps": c.fps,
        "duration": round(frames / c.fps, 2),
        "recorded": "live (Xvfb)" if c.live else "off-screen",
    }
    for kind, path in files.items():
        entry[kind] = f"media/{path.name}"
        entry[f"{kind}_bytes"] = path.stat().st_size
    return entry


def encode_anim(c: Clip, width: int, frames: int, folder: Path) -> dict[str, Any]:
    """An ``anim`` clip: an animated WebP that loops forever, its quality lowered until it fits ANIM_TARGET,
    and a poster (shown before it loads and with "reduce motion"). Encoded by anim_webp.fit_webp (Pillow and
    libwebp's animation encoder, which only stores what changed between frames; identical frames are merged)."""
    from PIL import Image

    for name in (f"{c.name}.mp4", f"{c.name}.webm"):  # left over from a recording as video
        (OUT / name).unlink(missing_ok=True)
    images = []
    for path in sorted(folder.glob("[0-9]*.png")):
        with Image.open(path) as im:
            height = round(im.height * width / im.width)
            images.append(im.convert("RGB").resize((width, height), Image.LANCZOS))
    anim = OUT / f"{c.name}.webp"
    _, quality = fit_webp(images, anim, fps=c.fps, target=ANIM_TARGET, method=4)
    if anim.stat().st_size > BUDGET:
        print(f"  WARNING: {anim.stat().st_size / 1000:.0f} KB is over the {BUDGET / 1000:.0f} KB budget; make the clip "
              "shorter, smaller or slower")
    poster = OUT / f"{c.name}.poster.webp"
    save_poster(images[max(0, min(len(images) - 1, int(len(images) * c.poster)))], poster)
    w, h = images[0].size
    entry = {"name": c.name, "title": c.title, "description": c.description, "tags": c.tags, "width": w,
             "height": h, "fps": c.fps, "duration": round(frames / c.fps, 2), "recorded": "off-screen",
             "quality": quality}
    for kind, path in (("webp", anim), ("poster", poster)):
        entry[kind] = f"media/{path.name}"
        entry[f"{kind}_bytes"] = path.stat().st_size
    return entry


def record(c: Clip) -> dict[str, Any]:
    print(f"recording {c.name}")
    folder = Path(tempfile.mkdtemp(prefix=f"pyzed-{c.name}-"))
    try:
        if c.live:
            capture = render_live(c, folder)
            natural = _probe_size(capture)[0]
            count = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(capture)],
                                       capture_output=True, text=True, check=True).stdout.strip() or 0)
            source = ["-i", str(capture)]
        else:
            count = render_offscreen(c, folder)
            from PIL import Image

            with Image.open(folder / "00001.png") as im:
                natural = im.width
            source = ["-framerate", str(c.fps), "-i", str(folder / "%05d.png")]
        width = min(c.width or (ANIM_WIDTH if c.anim else MAX_WIDTH), natural)
        width -= width % 2
        entry = encode_anim(c, width, count, folder) if c.anim else encode(c, source, width, count, folder)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    sizes = ", ".join(f"{k.removesuffix('_bytes')} {v / 1000:.0f} KB" for k, v in entry.items() if k.endswith("_bytes"))
    print(f"  {entry['width']}x{entry['height']}, {entry['duration']}s: {sizes}")
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("names", nargs="*", help="record only the clips whose name contains one of these")
    parser.add_argument("--list", action="store_true", help="list the clips")
    parser.add_argument("--serve", help=argparse.SUPPRESS)  # runs a live clip's app (inside Xvfb)
    args = parser.parse_args()
    if args.serve:
        import pyzed as pz

        pz.run(LIVE_APPS[args.serve]())
        return
    if args.list:
        for c in CLIPS.values():
            print(f"{c.name:26} {'live' if c.live else 'webp' if c.anim else 'off-screen':10} {c.description}")
        return
    manifest: dict[str, Any] = {"clips": []}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    entries = {e["name"]: e for e in manifest.get("clips", [])}
    for c in CLIPS.values():
        if args.names and not any(n in c.name for n in args.names):
            continue
        if c.live and (shutil.which("Xvfb") is None or sys.platform != "linux"):
            print(f"skipping {c.name}: live clips need Linux and Xvfb")
            continue
        entries[c.name] = record(c)
    order = list(CLIPS)
    manifest = {
        "about": "Short muted looping clips for the docs, made by docs/scripts/record.py. Paths are relative to "
                 "the site's base URL (public/). Embed with <video autoplay muted loop playsinline poster=...> "
                 "and a WebM source before the MP4; a clip with only `webp` is an animated image (<img>).",
        "clips": sorted(entries.values(), key=lambda e: order.index(e["name"]) if e["name"] in order else 999),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
