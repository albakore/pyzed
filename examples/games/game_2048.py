"""2048: the sliding-tiles puzzle, with smooth moves, merges that pop and a widget overlay.

    python examples/games/game_2048.py

Arrows or WASD (or a swipe with the mouse) slide every tile; two equal tiles that meet
merge into one. Reach 2048. Shows how a turn-based game differs from an action game:

- **The rules are plain functions** (``slide_line``), easy to read and to test without a
  window.
- **Animation only between turns**: ``pz.frames`` runs while tiles slide and pop, and
  ``subscriptions()`` returns nothing the rest of the time, so the game uses no CPU while
  you think.
- **Tweens** for sliding (each tile remembers where it came from), popping merges and the
  "+points" that float up.
- **UI on top of the game**: score boxes, a New game button and a glass card with buttons
  when you win or lose.

Tutorial: https://albakore.github.io/pyzed/games/puzzle-2048/
"""

import random

import pyzed as pz
from pyzed import draw, game, ui

SIZE = 4
CELL, GAP = 96, 12
BOARD = SIZE * CELL + (SIZE + 1) * GAP
SLIDE_TIME = 0.11
POP_TIME = 0.16
DIRECTIONS = {"left": (0, -1), "a": (0, -1), "right": (0, 1), "d": (0, 1),
              "up": (-1, 0), "w": (-1, 0), "down": (1, 0), "s": (1, 0)}
COLORS = {2: ("#3b4252", "#e5e9f0"), 4: ("#434c5e", "#e5e9f0"), 8: ("#d08770", "#ffffff"),
          16: ("#e07a5f", "#ffffff"), 32: ("#e76f51", "#ffffff"), 64: ("#ef4444", "#ffffff"),
          128: ("#e9c46a", "#1f2937"), 256: ("#f4d35e", "#1f2937"), 512: ("#facc15", "#1f2937"),
          1024: ("#a3e635", "#1f2937"), 2048: ("#22d3ee", "#0b1220")}


# -- the rules: plain functions -----------------------------------------------------------------
def slide_line(values):
    """Slides one row toward its start and merges equal neighbours once.

    ``[2, 2, 4, 0] -> ([4, 4, 0, 0], 4)``: the new row and the points gained.
    """
    tiles = [v for v in values if v]
    out, gained, i = [], 0, 0
    while i < len(tiles):
        if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
            out.append(tiles[i] * 2)
            gained += tiles[i] * 2
            i += 2                       # both tiles are used up: a tile merges only once per move
        else:
            out.append(tiles[i])
            i += 1
    return out + [0] * (len(values) - len(out)), gained


def lines(direction):
    """The cells of each row (or column) in the order tiles slide, the leading edge first."""
    dr, dc = direction
    out = []
    for i in range(SIZE):
        cells = [(i, j) if dr == 0 else (j, i) for j in range(SIZE)]
        if dr == 1 or dc == 1:
            cells.reverse()
        out.append(cells)
    return out


def can_move(values):
    """Whether any move changes the board (``values`` maps ``(row, col)`` to a number)."""
    for r in range(SIZE):
        for c in range(SIZE):
            v = values.get((r, c), 0)
            if not v or (c + 1 < SIZE and values.get((r, c + 1)) == v) or (r + 1 < SIZE and values.get((r + 1, c)) == v):
                return True
    return False


class Tile:
    def __init__(self, value, cell):
        self.value = value
        self.cell = self.came_from = cell
        self.merged = False          # doubled in the last move: shows the old value while sliding
        self.new = True              # just appeared: grows from nothing


class Game2048(pz.App):
    title = "2048"
    size = (BOARD + 48, BOARD + 150)
    theme = "One Dark"

    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.best = 0
        self.new_game()

    # -- state ------------------------------------------------------------------------------
    def new_game(self):
        self.tiles = {}              # (row, col) -> Tile
        self.ghosts = []             # tiles that merged into another: they slide, then vanish
        self.score = 0
        self.won = self.keep_going = False
        self.anim = 1.0              # seconds since the last move (animations end at SLIDE + POP)
        self.floats = []             # [text, age]: "+8" rising from the score
        self.swipe = None
        self.add_tile()
        self.add_tile()

    def add_tile(self):
        free = [(r, c) for r in range(SIZE) for c in range(SIZE) if (r, c) not in self.tiles]
        if free:
            cell = self.random.choice(free)
            self.tiles[cell] = Tile(4 if self.random.random() < 0.1 else 2, cell)

    @property
    def values(self):
        return {cell: tile.value for cell, tile in self.tiles.items()}

    @property
    def over(self):
        return not can_move(self.values)

    @property
    def animating(self):
        return self.anim < SLIDE_TIME + POP_TIME or bool(self.floats)

    # -- a move -----------------------------------------------------------------------------
    def move(self, direction):
        if self.over or (self.won and not self.keep_going):
            return False
        for tile in self.tiles.values():
            tile.came_from, tile.merged, tile.new = tile.cell, False, False
        self.ghosts = []
        moved, gained, new_tiles = False, 0, {}
        for cells in lines(direction):
            row = [self.tiles[c] for c in cells if c in self.tiles]
            new_values, points = slide_line([self.tiles[c].value if c in self.tiles else 0 for c in cells])
            gained += points
            # Walk the row the same way slide_line did, to know where each tile goes.
            k = 0
            i = 0
            while i < len(row):
                target = cells[k]
                tile = row[i]
                if i + 1 < len(row) and row[i + 1].value == tile.value:
                    other = row[i + 1]
                    other.cell = target                # it slides to the same cell, then disappears
                    self.ghosts.append(other)
                    tile.value *= 2
                    tile.merged = True
                    i += 2
                else:
                    i += 1
                moved |= tile.cell != target or tile.merged
                tile.cell = target
                new_tiles[target] = tile
                k += 1
            assert [new_tiles[c].value if c in new_tiles else 0 for c in cells] == new_values
        if not moved:
            return False
        self.tiles = new_tiles
        self.score += gained
        self.best = max(self.best, self.score)
        if gained:
            self.floats.append([f"+{gained}", 0.0])
        if any(t.value >= 2048 for t in self.tiles.values()) and not self.keep_going:
            self.won = True
        self.add_tile()
        self.anim = 0.0
        return True

    # -- input ------------------------------------------------------------------------------
    def on_key(self, combo):
        if combo in DIRECTIONS:
            self.move(DIRECTIONS[combo])

    def press(self, x, y):
        self.swipe = (x, y, x, y)

    def drag(self, x, y):
        if self.swipe:
            self.swipe = (*self.swipe[:2], x, y)

    def release(self):
        if not self.swipe:
            return
        x0, y0, x1, y1 = self.swipe
        self.swipe = None
        dx, dy = x1 - x0, y1 - y0
        if max(abs(dx), abs(dy)) > 30:                  # a short click is not a swipe
            self.move((0, 1 if dx > 0 else -1) if abs(dx) > abs(dy) else (1 if dy > 0 else -1, 0))

    def continue_playing(self):
        self.keep_going = True

    # -- animation --------------------------------------------------------------------------
    def subscriptions(self):
        return [pz.frames(self.tick)] if self.animating else []     # idle between moves

    def tick(self, dt):
        self.anim += dt
        for f in self.floats:
            f[1] += dt
        self.floats = [f for f in self.floats if f[1] < 0.8]
        if self.anim >= SLIDE_TIME:
            self.ghosts = []

    # -- draw -------------------------------------------------------------------------------
    @staticmethod
    def cell_xy(cell):
        r, c = cell
        return GAP + c * (CELL + GAP), GAP + r * (CELL + GAP)

    def tile_shapes(self, tile, value):
        slide = game.clamp(self.anim / SLIDE_TIME, 0, 1)
        ease = 1 - (1 - slide) ** 3
        (x0, y0), (x1, y1) = self.cell_xy(tile.came_from), self.cell_xy(tile.cell)
        x, y = game.lerp(x0, x1, ease), game.lerp(y0, y1, ease)
        scale = 1.0
        pop = (self.anim - SLIDE_TIME) / POP_TIME            # 0 -> 1 after the slide
        if tile.new:
            scale = 0.0 if pop < 0 else min(1.0, 0.3 + pop * 0.9)
        elif tile.merged and 0 <= pop < 1:
            scale = 1 + 0.18 * (1 - abs(2 * pop - 1))         # up and back down
        if scale <= 0:
            return []
        bg, fg = COLORS.get(value, ("#22d3ee", "#0b1220"))
        size = CELL * scale
        cx, cy = x + CELL / 2, y + CELL / 2
        shapes = []
        if value >= 128:
            shapes += game.glow(cx, cy, CELL * 0.42, bg, layers=2, strength=0.2, core=False)
        shapes.append(draw.rect(cx - size / 2, cy - size / 2, size, size, radius=10 * scale, fill=bg))
        font = (40 if value < 100 else 34 if value < 1000 else 28) * scale
        shapes.append(draw.text(cx, cy, value, size=font, weight="bold", color=fg, align_x="center",
                                align_y="center"))
        return shapes

    def board(self):
        shapes = [draw.background("#1b1f27")]
        for r in range(SIZE):
            for c in range(SIZE):
                x, y = self.cell_xy((r, c))
                shapes.append(draw.rect(x, y, CELL, CELL, radius=10, fill="#262b35"))
        sliding = self.anim < SLIDE_TIME
        for ghost in self.ghosts:
            shapes += self.tile_shapes(ghost, ghost.value)
        for tile in self.tiles.values():
            shown = tile.value // 2 if tile.merged and sliding else tile.value
            shapes += self.tile_shapes(tile, shown)
        return pz.canvas(shapes, width=BOARD, height=BOARD, on_press=self.press, on_move=self.drag,
                         on_release=self.release, cursor="grab")

    def score_box(self, label, value, floats=()):
        texts = [pz.text(f"{value:,}", size=20, weight="bold")]
        box = pz.container(pz.column([ui.muted(label, size="sm"), *texts], spacing=0, align="center"),
                           padding=(6, 16)).style(background="surface", radius=8)
        risers = [pz.container(pz.text(text, size=14, weight="bold", color="#fbbf24"),
                               padding=(0, 0, 0, 0)).style(opacity=1 - age / 0.8, translate=(0, -28 * age / 0.8))
                  for text, age in floats]
        return pz.stack([box, *[pz.container(r, width="fill", align_x="center") for r in risers]])

    def overlay(self):
        if self.won and not self.keep_going:
            title, line = "You made 2048!", f"Score {self.score:,}"
            buttons = [ui.button("Keep going", self.continue_playing, variant="solid", icon="play"),
                       ui.button("New game", self.new_game, icon="rotate-ccw")]
        elif self.over and not self.animating:
            title, line = "No more moves", f"Score {self.score:,}  ·  best {self.best:,}"
            buttons = [ui.button("Try again", self.new_game, variant="solid", icon="rotate-ccw")]
        else:
            return None
        card = pz.container(pz.column([ui.heading(title, level=2), ui.muted(line), pz.row(buttons, spacing=8)],
                                      spacing=10, align="center"), padding=(22, 30))
        card = card.style(glass=True, radius=14).animate("zoom_in", duration=250)
        return pz.container(card, width="fill", height="fill", align_x="center", align_y="center")

    def view(self):
        t = self.resolved_theme()
        header = pz.row([
            pz.text("2048", size=40, weight="bold"), pz.hspace(),
            self.score_box("SCORE", self.score, self.floats), self.score_box("BEST", self.best),
            ui.button("New game", self.new_game, icon="rotate-ccw"),
        ], spacing=10, align="center")
        play = pz.stack([self.board(), self.overlay()], width=BOARD, height=BOARD)
        return pz.container(pz.column([header, pz.container(play, radius=12, clip=True),
                                       ui.muted("Arrows / WASD or swipe with the mouse · join the numbers to get to 2048",
                                                size="sm")], spacing=12),
                            padding=24, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(Game2048)
