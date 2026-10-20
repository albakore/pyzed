"""Walker: sprites, frame animation and tweening.

    python examples/games/walker.py

Arrows or A/D walk, Space jumps, F shows or hides the sprite sheet. A pixel-art hero
walks, blinks, jumps and squashes when it lands; coins bob and pop with a "+1" that
eases up and fades. Shows:

- **Sprites from text** with ``game.sprite`` (one string per row, one character per pixel),
  flipped with ``flip=True`` when the hero faces left.
- **Frame animation**: a list of frames (a sprite sheet) played at a few frames per second
  by ``FrameAnimation``, which only counts time.
- **Tweening**: a value going from A to B over a duration with an easing curve (``Tween``),
  for the jump, the landing squash, the "+1" and the title that slides in.

Tutorial: https://albakore.github.io/pyzed/games/sprites-animation/
"""

import math

import pyzed as pz
from pyzed import draw, game, ui

W, H = 640, 300
GROUND = 236
PIXEL = 4
WALK_SPEED = 170
JUMP_HEIGHT = 70
JUMP_TIME = 0.55

PALETTE = {"h": "#7c4a2d", "s": "#f5c99b", "S": "#e9b385", "e": "#1b1f27", "b": "#3b82f6", "B": "#60a5fa",
           "p": "#334155", "k": "#111827"}   # "." (or any character not here) is transparent

# -- the sprite sheet: every frame is a list of rows, every character a pixel ---------------
HEAD = [
    "...hhhh...",
    "..hhhhhh..",
    "..hhssss..",
    "..hsssess.",
    "..hsssssS.",
    "...ssss...",
]
BLINK = HEAD[:3] + ["..hsssshs."] + HEAD[4:]       # the eye closed for a frame
BODY = [
    "..bbBBbb..",
    ".sbbBBbbs.",
    ".sbbbbbbs.",
    "..bbbbbb..",
]
LEGS = {
    "stand": ["..pp..pp..", "..pp..pp..", "..kk..kk.."],
    "apart": ["..pp..pp..", ".pp....pp.", ".kk.....kk"],
    "pass": ["...pp.pp..", "...pp.pp..", "...kkkkk.."],
    "air": ["..pp..pp..", "..ppp.ppp.", "....k...k."],
}
IDLE = [HEAD + BODY + LEGS["stand"]] * 6 + [BLINK + BODY + LEGS["stand"]]  # blink once in a while
WALK = [HEAD + BODY + LEGS["apart"], HEAD + BODY + LEGS["pass"],
        HEAD + BODY + LEGS["apart"], HEAD + BODY + LEGS["pass"]]
JUMP = [HEAD + BODY + LEGS["air"]]
SPRITE_W = len(HEAD[0]) * PIXEL
SPRITE_H = len(IDLE[0]) * PIXEL


# -- easing: how a value moves from 0 to 1 ----------------------------------------------------
def linear(t):
    return t


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_out_back(t):
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def ease_in_out_sine(t):
    return -(math.cos(math.pi * t) - 1) / 2


class Tween:
    """A number going from ``start`` to ``end`` in ``duration`` seconds, shaped by ``ease``."""

    def __init__(self, start, end, duration, ease=ease_out_cubic, delay=0.0):
        self.start, self.end, self.duration, self.ease = start, end, duration, ease
        self.time = -delay

    def update(self, dt):
        self.time += dt

    @property
    def progress(self):
        return game.clamp(self.time / self.duration, 0.0, 1.0)

    @property
    def done(self):
        return self.time >= self.duration

    @property
    def value(self):
        return game.lerp(self.start, self.end, self.ease(self.progress))


class FrameAnimation:
    """Plays a list of frames at ``fps`` frames per second, looping or not."""

    def __init__(self, frames, fps, loop=True):
        self.frames, self.fps, self.loop = frames, fps, loop
        self.time = 0.0

    def update(self, dt):
        self.time += dt

    @property
    def index(self):
        i = int(self.time * self.fps)
        return i % len(self.frames) if self.loop else min(i, len(self.frames) - 1)

    @property
    def frame(self):
        return self.frames[self.index]


class Walker(pz.App):
    title = "Walker"
    size = (W + 32, H + 92)
    theme = "One Dark"

    def __init__(self, seed=None):
        self.held = None            # the keys held down; None reads the keyboard
        self.show_sheet = True
        self.x = 120.0
        self.facing = 1             # 1 right, -1 left
        self.clock = 0.0
        self.animations = {"idle": FrameAnimation(IDLE, 3), "walk": FrameAnimation(WALK, 10),
                           "jump": FrameAnimation(JUMP, 1)}
        self.state = "idle"
        self.jump = None            # a Tween from 0 to 1 while in the air
        self.squash = None          # a Tween from 1 back to 0 after landing
        self.coins = [{"x": 260 + i * 70, "high": i % 2 == 1, "taken": None} for i in range(5)]
        self.popups = []            # [x, y, Tween] "+1" labels
        self.title_in = Tween(-80, 18, 0.8, ease_out_back, delay=0.2)
        self.score = 0

    @property
    def animation(self):
        return self.animations[self.state]

    def set_state(self, state):
        if state != self.state:
            self.state = state
            self.animations[state].time = 0.0   # start the new animation from its first frame

    # -- update -------------------------------------------------------------------------------
    def subscriptions(self):
        return [pz.frames(self.tick)]

    def tick(self, dt):
        self.clock += dt
        self.title_in.update(dt)
        move = game.axis(("left", "a"), ("right", "d"), held=self.held)
        if move:
            self.facing = move
        self.x = game.clamp(self.x + move * WALK_SPEED * dt, 10, W - SPRITE_W - 10)

        if self.held is not None and "space" in self.held:
            self.start_jump()
        if self.jump:
            self.jump.update(dt)
            if self.jump.done:
                self.jump = None
                self.squash = Tween(1.0, 0.0, 0.25, ease_out_cubic)   # land: squash, then recover
        if self.squash:
            self.squash.update(dt)
            if self.squash.done:
                self.squash = None

        self.set_state("jump" if self.jump else "walk" if move else "idle")
        self.animation.update(dt)
        self.collect()
        for popup in self.popups:
            popup[2].update(dt)
        self.popups = [p for p in self.popups if not p[2].done]

    def start_jump(self):
        if not self.jump:
            self.jump = Tween(0.0, 1.0, JUMP_TIME, linear)

    @property
    def height(self):
        """How high the hero is: a parabola, 4t(1-t), peaks at JUMP_HEIGHT halfway through."""
        if not self.jump:
            return 0.0
        t = self.jump.value
        return 4 * t * (1 - t) * JUMP_HEIGHT

    def collect(self):
        hero = game.Rect(self.x + 8, GROUND - SPRITE_H - self.height, SPRITE_W - 16, SPRITE_H)
        for coin in self.coins:
            if coin["taken"] is not None:
                if self.clock - coin["taken"] > 3:     # coins come back after three seconds
                    coin["taken"] = None
                continue
            cx, cy = coin["x"], self.coin_y(coin)
            if hero.overlaps(game.Rect(cx - 9, cy - 9, 18, 18)):
                coin["taken"] = self.clock
                self.score += 1
                self.popups.append([cx, cy, Tween(0.0, 1.0, 0.7, ease_out_cubic)])

    def coin_y(self, coin):
        base = GROUND - (110 if coin["high"] else 40)
        return base + math.sin(self.clock * 3 + coin["x"] * 0.05) * 5   # bob with a sine wave

    def on_key(self, combo):
        if combo in ("space", "up", "w"):
            self.start_jump()
        elif combo == "f":
            self.show_sheet = not self.show_sheet

    # -- draw ---------------------------------------------------------------------------------
    def board(self):
        shapes = [draw.background("#101521")]
        for i, (color, y) in enumerate((("#1a2236", 170), ("#202a40", 196))):   # far hills
            shapes += [draw.circle(80 + j * 190 + i * 90, y + 70, 110, fill=color) for j in range(4)]
        shapes.append(draw.rect(0, GROUND, W, H - GROUND, fill="#1f2a1d"))
        shapes.append(draw.rect(0, GROUND, W, 6, fill="#4d7c3a"))

        for coin in self.coins:
            if coin["taken"] is None:
                cx, cy = coin["x"], self.coin_y(coin)
                shapes += game.glow(cx, cy, 8, "#fbbf24", layers=3, strength=0.45)
                shapes.append(draw.circle(cx, cy, 4, fill="#fde68a"))

        # shadow: smaller and fainter the higher the hero is
        k = 1 - self.height / JUMP_HEIGHT * 0.5
        shapes.append(draw.rect(self.x + SPRITE_W / 2 - 18 * k, GROUND - 3, 36 * k, 6, radius=3,
                                fill=game.rgba("#000000", 0.35 * k)))

        # squash and stretch: wider and shorter right after landing, around the feet
        s = self.squash.value if self.squash else 0.0
        sx, sy = 1 + 0.25 * s, 1 - 0.2 * s
        feet_x, feet_y = self.x + SPRITE_W / 2, GROUND - self.height
        shapes += [draw.save(), draw.translate(feet_x, feet_y), draw.scale(sx, sy),
                   *game.sprite(self.animation.frame, PALETTE, -SPRITE_W / 2, -SPRITE_H, scale=PIXEL,
                                flip=self.facing < 0),
                   draw.restore()]

        for x, y, tween in self.popups:
            shapes.append(draw.text(x, y - 40 * tween.value, "+1", size=18, weight="bold",
                                    color=game.rgba("#fde68a", 1 - tween.progress), align_x="center"))

        shapes.append(draw.text(W / 2, self.title_in.value, "WALKER", size=26, weight="bold", color="#e2e8f0",
                                align_x="center"))
        if self.show_sheet:
            shapes += self.sheet()
        return pz.canvas(shapes, width=W, height=H)

    def sheet(self):
        """The current animation's frames, small, with the one on screen highlighted."""
        frames = self.animation.frames
        unique = []
        for f in frames:
            if not unique or unique[-1] is not f:
                unique.append(f)
        scale, gap = 2, 6
        fw, fh = len(HEAD[0]) * scale, len(IDLE[0]) * scale
        x0, y0 = 12, 12
        shapes = [draw.rect(x0 - 6, y0 - 6, max(len(frames) * (fw + gap) + 6, 160), fh + 30, radius=8,
                            fill="#00000066")]
        for i, frame in enumerate(frames):
            x = x0 + i * (fw + gap)
            current = i == self.animation.index
            shapes.append(draw.rect(x - 2, y0 - 2, fw + 4, fh + 4, radius=3,
                                    stroke="#fbbf24" if current else "#ffffff22", width=1.5 if current else 1))
            shapes += game.sprite(frame, PALETTE, x, y0, scale=scale)
        shapes.append(draw.text(x0, y0 + fh + 8, f"{self.state} · frame {self.animation.index + 1}/{len(frames)}",
                                size=11, color="#cbd5e1", font="mono"))
        return shapes

    def view(self):
        t = self.resolved_theme()
        hud = pz.row([ui.label("Walker", weight="semibold"), pz.hspace(),
                      ui.badge(self.state, icon="film", tint="accent"),
                      ui.badge(f"{self.score} coins", icon="coins", tint="warning")], spacing=8, align="center")
        return pz.container(pz.column([hud, pz.container(self.board(), radius=10, clip=True),
                                       ui.muted("←/→ or A/D walk · Space jumps · F shows the sprite sheet",
                                                size="sm")], spacing=10),
                            padding=16, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(Walker)
