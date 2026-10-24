"""Snake: the classic, in about 150 lines of Pyzed.

    python examples/games/snake.py

Arrows or WASD steer, Space pauses, Enter starts again. Shows a fixed-rate game loop
with ``pz.every``, steering from ``on_key`` (with a queue so quick turns are not lost),
a ``pz.canvas`` board and a HUD made of ordinary widgets stacked on top of it.
Tutorial: https://albakore.github.io/pyzed/games/snake/
"""

import random

import pyzed as pz
from pyzed import draw, ui

CELL = 22
COLS, ROWS = 24, 18
DIRECTIONS = {
    "up": (0, -1), "w": (0, -1),
    "down": (0, 1), "s": (0, 1),
    "left": (-1, 0), "a": (-1, 0),
    "right": (1, 0), "d": (1, 0),
}


class Snake(pz.App):
    title = "Snake"
    size = (COLS * CELL + 32, ROWS * CELL + 96)
    theme = "Pyzed Dark"

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.best = 0
        self.reset()

    # -- game state -----------------------------------------------------------
    def reset(self):
        middle = (COLS // 2, ROWS // 2)
        self.body = [middle, (middle[0] - 1, middle[1]), (middle[0] - 2, middle[1])]
        self.direction = (1, 0)
        self.turns = []  # key presses waiting for the next step
        self.food = self.free_cell()
        self.score = 0
        self.paused = False
        self.over = False

    def free_cell(self):
        while True:
            cell = (self.random.randrange(COLS), self.random.randrange(ROWS))
            if cell not in self.body:
                return cell

    @property
    def speed(self):
        """Steps per second: starts at 8 and speeds up as the snake grows."""
        return min(8 + self.score // 3, 20)

    def step(self):
        if self.turns:
            self.direction = self.turns.pop(0)
        dx, dy = self.direction
        x, y = self.body[0]
        head = ((x + dx) % COLS, (y + dy) % ROWS)  # walls wrap around
        if head in self.body[:-1]:
            self.over = True
            self.best = max(self.best, self.score)
            return
        self.body.insert(0, head)
        if head == self.food:
            self.score += 1
            self.food = self.free_cell()
        else:
            self.body.pop()

    # -- input and timing -----------------------------------------------------
    def subscriptions(self):
        if self.over or self.paused:
            return []
        # The key includes the speed so the timer restarts when it changes.
        return [pz.every(1 / self.speed, self.step, key=f"snake-{self.speed}")]

    def on_key(self, combo):
        if combo in DIRECTIONS:
            last = self.turns[-1] if self.turns else self.direction
            new = DIRECTIONS[combo]
            # Ignore turning back on itself and repeated presses.
            if new != last and (new[0] + last[0], new[1] + last[1]) != (0, 0) and len(self.turns) < 3:
                self.turns.append(new)
        elif combo == "space" and not self.over:
            self.paused = not self.paused
        elif combo == "enter" and self.over:
            self.reset()

    # -- drawing --------------------------------------------------------------
    def board(self, t):
        shapes = [draw.background(t.editor)]
        # A subtle checkerboard makes the grid readable without lines.
        shapes.append(draw.rects(((x * CELL, y * CELL, CELL, CELL) for x in range(COLS)
                                  for y in range(ROWS) if (x + y) % 2), fill=t.surface))
        fx, fy = self.food
        shapes.append(draw.circle(fx * CELL + CELL / 2, fy * CELL + CELL / 2, CELL * 0.62,
                                  fill=(0.82, 0.45, 0.47, 0.18)))
        shapes.append(draw.circle(fx * CELL + CELL / 2, fy * CELL + CELL / 2, CELL / 2 - 3, fill="#d07277"))
        for i, (x, y) in enumerate(self.body):
            inset = 2 if i else 1
            shapes.append(draw.rect(x * CELL + inset, y * CELL + inset, CELL - 2 * inset, CELL - 2 * inset,
                                    radius=6 if i else 7, fill=t.accent if i == 0 else "#a1c181"))
        # Eyes looking where the snake goes.
        hx, hy = self.body[0]
        dx, dy = self.direction
        cx, cy = hx * CELL + CELL / 2 + dx * 4, hy * CELL + CELL / 2 + dy * 4
        for side in (-1, 1):
            shapes.append(draw.circle(cx + dy * 5 * side, cy + dx * 5 * side, 2.2, fill=t.editor))
        return pz.canvas(shapes, width=COLS * CELL, height=ROWS * CELL)

    def overlay(self, t):
        if self.over:
            title, hint = "Game over", "Press Enter to play again"
        elif self.paused:
            title, hint = "Paused", "Press Space to continue"
        else:
            return None
        card = pz.container(pz.column([
            ui.heading(title, level=2),
            ui.muted(f"Score {self.score}  ·  Best {self.best}"),
            ui.button(hint.split(" to ")[1].capitalize(),
                      self.reset if self.over else (lambda: setattr(self, "paused", False)),
                      variant="solid", icon="rotate-ccw" if self.over else "play"),
            ui.muted(hint, size="sm"),
        ], spacing=10, align="center"), padding=24).style(glass=True, radius=14, border=(1, "border"))
        return pz.container(card, width="fill", height="fill", align_x="center", align_y="center")

    def view(self):
        t = self.resolved_theme()
        hud = pz.row([
            pz.icon("worm", size=18, color=t.accent),
            ui.label("Snake", weight="semibold"),
            pz.hspace(),
            ui.badge(f"Score {self.score}", icon="apple"),
            ui.badge(f"Best {self.best}", tint="warning", icon="trophy"),
            ui.badge(f"{self.speed}/s", tint="text_muted", icon="gauge"),
        ], spacing=8, align="center")
        game = pz.stack([self.board(t), self.overlay(t)], width=COLS * CELL, height=ROWS * CELL)
        return pz.container(
            pz.column([hud, pz.container(game, radius=10, clip=True), ui.muted(
                "Arrows / WASD steer · Space pauses · Enter restarts", size="sm")], spacing=10),
            padding=16, width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(Snake)
