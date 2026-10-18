"""Conway's Game of Life, after Iced's ``game_of_life`` demo.

    python examples/game_of_life.py

Click or drag on the grid to paint cells, Space to play/pause, ``n`` to step once.
Shows ``pz.canvas`` drawing thousands of cells in one shape and ``pz.every`` driving
the simulation.
"""

import random

import pyzed as pz
from pyzed import draw, ui

CELL = 10
COLS, ROWS = 80, 56


def step(alive):
    counts = {}
    for x, y in alive:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    key = ((x + dx) % COLS, (y + dy) % ROWS)
                    counts[key] = counts.get(key, 0) + 1
    return {cell for cell, n in counts.items() if n == 3 or (n == 2 and cell in alive)}


class Life(pz.App):
    title = "Game of Life"
    size = (COLS * CELL + 48, ROWS * CELL + 120)

    def __init__(self):
        self.alive = set()
        self.playing = False
        self.speed = 10
        self.generation = 0
        self.painting = None  # True paints cells, False erases them
        self.randomize()

    def randomize(self):
        self.alive = {(x, y) for x in range(COLS) for y in range(ROWS) if random.random() < 0.18}
        self.generation = 0

    def clear(self):
        self.alive.clear()
        self.generation = 0

    def tick(self):
        self.alive = step(self.alive)
        self.generation += 1

    def subscriptions(self):
        return [pz.every(1 / self.speed, self.tick, key="life")] if self.playing else []

    def on_key(self, combo):
        if combo == "space":
            self.playing = not self.playing
        elif combo == "n":
            self.tick()

    def cell_at(self, x, y):
        return int(x // CELL) % COLS, int(y // CELL) % ROWS

    def press(self, x, y):
        cell = self.cell_at(x, y)
        self.painting = cell not in self.alive
        self.paint(x, y)

    def paint(self, x, y):
        if self.painting is None:
            return
        cell = self.cell_at(x, y)
        (self.alive.add if self.painting else self.alive.discard)(cell)

    def view(self):
        t = self.resolved_theme()
        grid = [draw.background(t.editor)]
        grid.append(draw.rects(((x * CELL, y * CELL, CELL - 1, CELL - 1) for x, y in self.alive), fill=t.accent))
        board = pz.canvas(
            grid,
            width=COLS * CELL,
            height=ROWS * CELL,
            on_press=self.press,
            on_move=self.paint,
            on_release=lambda: setattr(self, "painting", None),
            cursor="crosshair",
        )
        controls = pz.row([
            ui.button("Pause" if self.playing else "Play", lambda: setattr(self, "playing", not self.playing),
                      icon="pause" if self.playing else "play", variant="solid", keys="space"),
            ui.button("Step", self.tick, icon="step-forward", disabled=self.playing),
            ui.button("Random", self.randomize, icon="shuffle"),
            ui.button("Clear", self.clear, icon="eraser"),
            pz.hspace(),
            ui.muted(f"Speed {self.speed}/s"),
            pz.container(ui.slider(self.speed, lambda v: setattr(self, "speed", int(v)), min=1, max=60, step=1),
                         width=160),
            ui.muted(f"Generation {self.generation} · {len(self.alive)} alive"),
        ], spacing=8, align="center")
        return pz.container(pz.column([controls, board], spacing=12), padding=16, bg=t.background,
                            width="fill", height="fill")


if __name__ == "__main__":
    pz.run(Life)
