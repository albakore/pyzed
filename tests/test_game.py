"""The game loop API (pz.frames, pz.pressed, draw.image), pyzed.game and the game examples."""

import importlib
import math
import sys
from pathlib import Path

import pytest

import pyzed as pz
from pyzed import draw, game

from test_features import read_png

ROOT = Path(__file__).resolve().parent.parent
GAMES = ROOT / "examples" / "games"


def test_frames_is_a_subscription():
    def tick(dt):
        pass

    sub = pz.frames(tick)
    assert isinstance(sub, pz.Subscription)
    assert "frames" in repr(sub)
    assert pz.frames(tick, key="loop").key == "frames:loop"
    with pytest.raises(TypeError):
        pz.frames("tick")


def test_pressed_is_empty_without_a_window():
    assert pz.pressed() == frozenset()
    assert not pz.is_pressed("left")
    assert pz.is_pressed("left", "a", held={"a"})


def test_axis_and_vector():
    assert game.axis("left", "right", held={"right"}) == 1
    assert game.axis(("left", "a"), ("right", "d"), held={"a"}) == -1
    assert game.axis("left", "right", held={"left", "right"}) == 0
    assert game.vector(held=set()) == (0.0, 0.0)
    assert game.vector(held={"w"}) == (0.0, -1.0)
    x, y = game.vector(held={"right", "down"})
    assert math.isclose(math.hypot(x, y), 1.0) and x > 0 and y > 0


def test_rect_collisions():
    a = game.Rect(0, 0, 10, 10)
    assert a.overlaps(game.Rect(5, 5, 10, 10))
    assert not a.overlaps(game.Rect(10, 0, 5, 5))  # touching is not overlapping
    assert a.contains(0, 0) and not a.contains(10, 5)
    assert a.moved(3, 4) == game.Rect(3, 4, 10, 10)
    assert a.center == (5, 5)
    assert a.shape(fill="#fff")["type"] == "rect"


def test_circle_rect_normals():
    box = game.Rect(100, 100, 50, 20)
    assert game.circle_rect(0, 0, 5, box) is None
    assert game.circle_rect(125, 96, 5, box) == (0.0, -1.0)  # from above
    assert game.circle_rect(125, 124, 5, box) == (0.0, 1.0)  # from below
    assert game.circle_rect(97, 110, 5, box) == (-1.0, 0.0)  # from the left
    assert game.circle_rect(153, 110, 5, box) == (1.0, 0.0)  # from the right
    assert game.circle_rect(102, 110, 5, box) == (-1.0, 0.0)  # center inside: nearest side


def test_rgba_and_glow():
    assert game.rgba("#ff0000") == (1.0, 0.0, 0.0, 1.0)
    assert game.rgba("#ff000080", 0.5)[3] == pytest.approx(128 / 255 / 2)
    assert game.rgba((255, 255, 255), 0.25) == (1.0, 1.0, 1.0, 0.25)
    shapes = game.glow(10, 10, 4, "#74ade8", layers=3)
    assert len(shapes) == 4 and shapes[-1]["fill"] == "#74ade8"
    assert len(game.glow(10, 10, 4, "#fff", layers=2, core=False)) == 2


def test_sprite_makes_one_shape_per_color():
    shapes = game.sprite(["#.@", "@#."], {"#": "#fff", "@": "#f00"}, 10, 20, scale=2)
    assert len(shapes) == 2
    white = next(s for s in shapes if s["fill"] == "#fff")
    assert white["rects"] == [(10, 20, 2, 2), (12, 22, 2, 2)]
    flipped = game.sprite(["#.."], {"#": "#fff"}, flip=True)
    assert flipped[0]["rects"] == [(2, 0, 1, 1)]


def test_particles_live_and_die():
    sparks = game.Particles(gravity=100, seed=1, limit=50)
    sparks.burst(0, 0, count=30, life=(0.5, 0.5))
    assert len(sparks) == 30
    sparks.burst(0, 0, count=30)
    assert len(sparks) == 50  # capped
    sparks.clear()
    sparks.burst(0, 0, count=10, life=(0.5, 0.5), angle=0, spread=0, speed=(100, 100))
    sparks.update(0.25)
    assert all(p.x == pytest.approx(25) for p in sparks.items)
    assert all(p.vy > 0 for p in sparks.items)  # gravity pulls down
    assert len(sparks.shapes()) == 10 and len(sparks.shapes(glow=True)) == 20
    sparks.update(0.3)
    assert len(sparks) == 0


def test_shake_settles():
    shake = game.Shake(seed=2)
    assert shake.shapes() == []
    shake.kick(10)
    dx, dy = shake.offset()
    assert abs(dx) <= 10 and abs(dy) <= 10
    assert shake.shapes()[0]["type"] == "translate"
    for _ in range(120):
        shake.update(1 / 60)
    assert shake.amount == 0 and shake.offset() == (0.0, 0.0)


def test_canvas_draws_images(tmp_path):
    red = bytes([255, 0, 0, 255]) * 4

    class Sprites(pz.App):
        size = (40, 20)

        def view(self):
            return pz.canvas([draw.background("#000000"),
                              draw.image(red, 0, 0, 20, 20, size=(2, 2), pixelated=True),
                              draw.image(red, 20, 0, 20, 20, size=(2, 2), opacity=0.0)], width=40, height=20)

    out = tmp_path / "sprites.png"
    Sprites().screenshot(out, scale=1)
    rows = read_png(out)
    assert rows[10][10][:3] == (255, 0, 0)
    assert rows[10][30][:3] == (0, 0, 0)
    assert draw.image("ship.png", 1, 2, 3, 4, rotation=90)["rotation"] == 90
    with pytest.raises(TypeError):
        pz.canvas([draw.image(42, 0, 0, 1, 1)])


@pytest.fixture
def games(monkeypatch):
    monkeypatch.syspath_prepend(str(GAMES))
    loaded = {}

    def load(name):
        loaded[name] = importlib.import_module(name)
        return loaded[name]

    yield load
    for name in loaded:
        sys.modules.pop(name, None)


def test_snake_eats_turns_and_dies(games):
    snake = games("snake").Snake(seed=1)
    head = snake.body[0]
    snake.food = (head[0] + 1, head[1])
    snake.step()
    assert snake.score == 1 and len(snake.body) == 4
    snake.on_key("left")  # straight back: ignored
    snake.on_key("down")
    snake.on_key("down")  # repeated: ignored
    assert snake.turns == [(0, 1)]
    snake.step()
    assert snake.direction == (0, 1)
    snake.body = [(5, 5), (5, 6), (6, 6), (6, 5), (6, 4)]
    snake.direction, snake.turns = (0, 1), []
    snake.step()
    assert snake.over and snake.best == 1
    assert snake.subscriptions() == []
    snake.on_key("enter")
    assert not snake.over and snake.score == 0


def test_breakout_breaks_bricks(games):
    bo = games("breakout")
    app = bo.Breakout(seed=3)
    total = len(app.bricks)
    app.launch()
    brick = app.bricks[-1]
    cx, cy = brick["rect"].center
    app.ball_x, app.ball_y, app.vx, app.vy = cx, brick["rect"].bottom + bo.BALL_R + 2, 0.0, -300.0
    for _ in range(10):
        app.tick(1 / 60)
    assert len(app.bricks) == total - 1 and app.score > 0 and app.vy > 0
    app.ball_x, app.ball_y, app.vy = 50, bo.H + 20, 300
    app.tick(1 / 60)
    assert app.lives == 2 and app.stuck


def test_neon_invaders_shoots(games):
    ni = games("neon_invaders")
    app = ni.NeonInvaders(seed=5)
    app.started = True
    app.new_game()
    target = app.invaders[-1]
    cx, cy = target.rect.center
    app.shots.append([cx, cy + 5, 0, 0])
    target.hp = 1
    app.move_shots(1 / 60)
    assert target not in app.invaders and app.score > 0
    app.shield = 1
    app.damage()
    assert app.over and app.best == app.score
