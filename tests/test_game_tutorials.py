"""The games of the "Make games" learning path (examples/games): what each tutorial says its game does.

Every example is also imported and drawn by ``test_features.test_examples_render``; here they run
headlessly, frame by frame, with the keys they read set through their ``held`` attribute.
"""

import importlib
import json
import sys
from pathlib import Path

import pytest

import pyzed as pz

ROOT = Path(__file__).resolve().parent.parent
GAMES = ROOT / "examples" / "games"
DT = 1 / 60


@pytest.fixture
def games(monkeypatch):
    monkeypatch.syspath_prepend(str(GAMES))
    loaded = []

    def load(name):
        loaded.append(name)
        return importlib.import_module(name)

    yield load
    for name in loaded:
        sys.modules.pop(name, None)


def run(app, frames, held=None):
    if held is not None:
        app.held = set(held)
    for _ in range(frames):
        app.tick(DT)


def draws(app, tmp_path, name):
    out = tmp_path / f"{name}.png"
    app.screenshot(out, scale=1)
    assert out.stat().st_size > 0


# -- 1. Coin Chase -------------------------------------------------------------------------------
def test_coin_chase_moves_collects_and_ends(games, tmp_path):
    cc = games("coin_chase")
    app = cc.CoinChase(seed=1)
    x = app.x
    run(app, 30, {"right"})
    assert app.x == pytest.approx(x + cc.SPEED * 30 * DT)          # speed x dt
    run(app, 1, {"right", "down"})
    app.coin = (app.x, app.y)
    run(app, 1, set())
    assert app.score == 1 and app.pops and app.coin != (app.x, app.y)
    app.on_key("space")
    assert app.paused and app.subscriptions() == []
    app.on_key("space")
    run(app, int(cc.ROUND * 60) + 5)
    assert app.over and app.best == 1 and app.subscriptions() == []
    draws(app, tmp_path, "coin-chase-over")
    app.on_key("enter")
    assert not app.over and app.score == 0 and app.time_left == cc.ROUND


# -- 2. Walker -----------------------------------------------------------------------------------
def test_tween_and_easing(games):
    wk = games("walker")
    for ease in (wk.linear, wk.ease_out_cubic, wk.ease_out_back, wk.ease_in_out_sine):
        assert ease(0) == pytest.approx(0) and ease(1) == pytest.approx(1)
    assert wk.ease_out_back(0.7) > 1                                  # overshoots, then settles
    tween = wk.Tween(10, 20, 0.5, wk.linear, delay=0.1)
    tween.update(0.1)
    assert tween.value == 10 and not tween.done
    tween.update(0.25)
    assert tween.value == pytest.approx(15)
    tween.update(1)
    assert tween.value == 20 and tween.done


def test_walker_animates_frames(games, tmp_path):
    wk = games("walker")
    walk = wk.FrameAnimation(wk.WALK, 10)
    walk.update(0.25)
    assert walk.index == 2 and walk.frame is wk.WALK[2]
    walk.update(0.2)
    assert walk.index == 0                                            # loops
    once = wk.FrameAnimation(wk.WALK, 10, loop=False)
    once.update(5)
    assert once.index == len(wk.WALK) - 1

    app = wk.Walker()
    run(app, 5, set())
    assert app.state == "idle"
    run(app, 20, {"left"})
    assert app.state == "walk" and app.facing == -1
    app.on_key("space")
    run(app, int(wk.JUMP_TIME * 60 / 2), set())
    assert app.state == "jump" and app.height == pytest.approx(wk.JUMP_HEIGHT, rel=0.05)
    run(app, int(wk.JUMP_TIME * 60 / 2) + 2)
    assert app.jump is None and app.squash is not None and app.height == 0
    draws(app, tmp_path, "walker")
    coin = app.coins[0]
    app.x = coin["x"] - wk.SPRITE_W / 2
    coin["high"] = False
    run(app, 1)
    assert app.score == 1 and app.popups and coin["taken"] is not None
    app.x = 20
    run(app, 60 * 4)
    assert coin["taken"] is None                                      # it came back


# -- 3. Jump Lab ---------------------------------------------------------------------------------
def test_jump_lab_lands_jumps_and_slides_on_walls(games, tmp_path):
    jl = games("jump_lab")
    app = jl.JumpLab(seed=2)
    run(app, 30, set())
    floor = jl.PLATFORMS[0]
    assert app.on_ground and app.player.bottom == pytest.approx(floor.top)
    app.press_jump()
    run(app, 1, {"space"})
    assert app.vy < 0 and not app.on_ground
    top = app.player.y
    for _ in range(60):
        run(app, 1)
        top = min(top, app.player.y)
    assert app.on_ground
    full = floor.top - app.player.h - top
    assert full == pytest.approx(jl.JUMP_SPEED ** 2 / (2 * jl.GRAVITY), rel=0.1)   # h = v² / 2g

    app.press_jump()
    run(app, 1, set())                                                # released at once: a short hop
    top = app.player.y
    for _ in range(60):
        run(app, 1)
        top = min(top, app.player.y)
    assert floor.top - app.player.h - top < full * 0.6

    run(app, 120, {"right"})                                          # into the wall: stops there
    wall = jl.PLATFORMS[4]
    assert app.player.right == pytest.approx(wall.left) and app.vx == 0
    assert all(0 < b.x < jl.W and b.y < jl.H for b in app.balls)
    draws(app, tmp_path, "jump-lab")


def test_jump_lab_coyote_time_and_buffer(games):
    jl = games("jump_lab")
    app = jl.JumpLab()
    ledge = jl.PLATFORMS[1]
    app.player.x, app.player.y = ledge.right - app.player.w - 1, ledge.top - app.player.h
    run(app, 2, set())
    assert app.on_ground
    for _ in range(30):                                               # walks off the edge...
        run(app, 1, {"right"})
        if not app.on_ground:
            break
    assert not app.on_ground and app.coyote > 0 and app.vy >= 0
    app.press_jump()
    run(app, 1, {"right", "space"})
    assert app.vy < 0                                                 # ...and can still jump
    run(app, 200, set())                                              # falls to the floor
    app.player.y -= 20                                                # just above it
    app.on_ground, app.vy = False, 0.0
    app.press_jump()                                                  # pressed before landing
    run(app, 6, {"space"})
    assert app.vy < 0                                                 # the buffered jump fired


# -- 4. Platformer -------------------------------------------------------------------------------
def test_platformer_map_and_camera(games, tmp_path):
    pf = games("platformer")
    assert all(len(row) == pf.COLS for row in pf.LEVEL)
    assert pf.solid(-1, 3) and not pf.solid(0, pf.ROWS) and pf.solid(0, 11)
    assert pf.tiles_near(pz.game.Rect(5, 5, 10, 10)) == []
    app = pf.Platformer()
    run(app, 30, set())
    assert app.on_ground and app.camera == 0
    run(app, 60, {"right"})
    assert app.player.x > app.start[0] + 150 and app.camera > 0
    assert app.collected > 0                                          # the coins on the way
    draws(app, tmp_path, "platformer")


def test_platformer_stomps_hurts_and_wins(games):
    pf = games("platformer")
    app = pf.Platformer(seed=1)
    enemy = app.enemies[0]
    app.player.x, app.player.y = enemy.rect.x, enemy.rect.top - app.player.h + 4
    app.vy = 300
    app.held = set()
    app.check_dangers()
    assert enemy.squashed and app.vy < 0 and app.lives == 3
    app.invincible = 0
    other = app.enemies[1]
    app.player.x, app.player.y, app.vy = other.rect.x, other.rect.y, 0
    app.check_dangers()
    assert app.lives == 2 and app.player.x == app.start[0]           # hurt: back to the start
    app.player.x, app.player.y = app.flag.x, app.flag.y + 40
    app.check_dangers()
    assert app.won and app.best_time == app.time
    app.on_key("enter")
    assert not app.won and app.lives == 3


# -- 5. Rock Storm (asteroids) -------------------------------------------------------------------
def test_asteroids_fly_shoot_split_and_crash(games, tmp_path):
    ast = games("asteroids")
    assert ast.wrap(-5, 10) == (ast.W - 5, 10) and ast.wrap(ast.W + 1, ast.H + 2) == (1, 2)
    app = ast.Asteroids(seed=4)
    app.rocks = []
    run(app, 30, {"up"})
    assert app.vy < 0 and len(app.trail) > 0                          # thrust points up at first
    run(app, 30, {"right"})
    assert app.angle > -90
    run(app, 1, {"space"})
    assert len(app.bullets) == 1
    big = ast.Rock(app.random, 100, 100, 3, 0)
    app.rocks = [big]
    app.break_rock(big)
    assert [r.size for r in app.rocks] == [2, 2] and app.score == ast.POINTS[3] and len(app.sparks) > 0
    app.safe = 0
    app.rocks = [ast.Rock(app.random, app.x, app.y, 1, 0)]
    app.collide()
    assert app.lives == 2 and app.safe > 0
    draws(app, tmp_path, "asteroids")
    app.lives = 1
    app.safe = 0
    app.rocks = [ast.Rock(app.random, app.x, app.y, 2, 0)]
    app.collide()
    assert app.over and app.best == app.score
    app.on_key("enter")
    assert not app.over and app.wave == 1 and app.rocks


# -- 6. 2048 -------------------------------------------------------------------------------------
@pytest.mark.parametrize("row, expected", [
    ([2, 2, 4, 0], ([4, 4, 0, 0], 4)),
    ([2, 2, 2, 2], ([4, 4, 0, 0], 8)),
    ([0, 4, 4, 8], ([8, 8, 0, 0], 8)),
    ([2, 4, 8, 16], ([2, 4, 8, 16], 0)),
    ([0, 0, 0, 2], ([2, 0, 0, 0], 0)),
])
def test_2048_slide_line(games, row, expected):
    assert games("game_2048").slide_line(row) == expected


def test_2048_moves_animate_then_idle(games, tmp_path):
    g = games("game_2048")
    app = g.Game2048(seed=1)
    app.tiles = {(0, 0): g.Tile(2, (0, 0)), (0, 3): g.Tile(2, (0, 3)), (1, 0): g.Tile(4, (1, 0))}
    assert app.move((0, -1)) is True
    assert app.values[(0, 0)] == 4 and app.score == 4 and len(app.tiles) == 3   # merged, plus a new tile
    assert app.ghosts and app.floats and app.subscriptions()
    draws(app, tmp_path, "2048-sliding")
    run(app, 60)
    assert not app.animating and app.subscriptions() == [] and not app.ghosts
    before = dict(app.values)
    assert app.move((0, -1)) is False or app.values != before
    app.press(10, 10)
    app.drag(200, 20)
    app.release()
    assert app.anim == 0                                              # a swipe right moved the tiles
    full = {(r, c): 2 if (r + c) % 2 else 4 for r in range(4) for c in range(4)}
    assert not g.can_move(full)
    app.tiles = {cell: g.Tile(v, cell) for cell, v in full.items()}
    run(app, 60)
    assert app.over
    draws(app, tmp_path, "2048-over")
    app.tiles = {(0, 0): g.Tile(1024, (0, 0)), (0, 1): g.Tile(1024, (0, 1))}
    app.move((0, -1))
    assert app.won
    assert not app.move((0, 1))                                       # the win card waits for a choice
    app.continue_playing()
    assert app.move((0, 1))


# -- 7. Orb Rush (menus) -------------------------------------------------------------------------
def test_menus_scenes_and_settings(games, tmp_path):
    mn = games("menus")
    app = mn.OrbRush(seed=1)
    assert app.scene == "title" and app.appear() == 0
    run(app, 30)
    assert app.appear() == 1                                          # the transition finished
    app.on_key("down")
    app.on_key("down")
    assert isinstance(app.on_key("enter"), pz.Command)                # Quit closes the window
    app.selected = 0
    app.on_key("enter")
    assert app.scene == "play" and app.since == 0
    run(app, 60, {"left"})
    assert app.x < mn.W / 2 and app.time == pytest.approx(1.0)
    app.on_key("escape")
    assert app.scene == "pause"
    t = app.time
    run(app, 30)
    assert app.time == t                                              # paused: the game is frozen
    app.on_key("down")
    app.on_key("enter")
    assert app.scene == "settings" and app.came_from == "pause"
    draws(app, tmp_path, "menus-settings")
    app.settings["difficulty"] = "Hard"
    app.on_key("escape")
    assert app.scene == "pause"
    app.on_key("p")
    assert app.scene == "play"
    app.health = 1
    app.mines.append([app.x, app.y])
    run(app, 1)
    assert app.scene == "over" and app.shake.amount > 0
    app.settings["shake"] = False
    app.choose("play")
    app.mines.append([app.x, app.y])
    run(app, 1)
    assert app.health == 2 and app.shake.amount < 10                  # shake is off now
    draws(app, tmp_path, "menus-play")


# -- 8. Target Rush (high scores) ----------------------------------------------------------------
def test_high_scores_file(games, tmp_path):
    hs = games("high_scores")
    path = tmp_path / "saves" / "scores.json"
    scores = hs.HighScores(path)
    assert scores.entries == [] and scores.qualifies(1) and not scores.qualifies(0)
    for i in range(12):
        scores.add(f"P{i}", (i + 1) * 100)
    assert len(scores.entries) == hs.KEEP and scores.best == 1200
    assert not scores.qualifies(150) and scores.qualifies(301)
    assert scores.add("Ada", 650) == 7
    data = json.loads(path.read_text())
    assert data["version"] == 1 and [e["score"] for e in data["scores"]][:3] == [1200, 1100, 1000]
    assert list(path.parent.iterdir()) == [path]                      # no temporary files left behind
    assert hs.HighScores(path).entries == scores.entries              # read back
    path.write_text("{ not json")
    assert hs.HighScores(path).entries == []                          # damaged: start empty
    assert hs.data_dir("My Game").name == "My Game"


def test_target_rush_round(games, tmp_path):
    hs = games("high_scores")
    app = hs.TargetRush(seed=3, path=tmp_path / "scores.json", sound_backend="offline")
    assert app.scene == "ready" and not (tmp_path / "scores.json").exists()   # nothing written yet
    app.start()
    assert app.last_sound == "start"
    left, _ = app.sounds.engine.render(0.1)
    assert max(map(abs, left)) > 0.01                                 # the start sound plays
    run(app, 1)
    target = app.targets[0]
    app.click(target[0], target[1])
    assert app.score > 0 and app.combo == 1 and app.last_sound == "hit"
    app.click(-50, -50)
    assert app.combo == 0 and app.last_sound == "miss"
    run(app, int(hs.ROUND * 60) + 2)
    assert app.scene == "name" and app.last_sound == "record"
    draws(app, tmp_path, "target-rush-name")
    app.set_name("  Grace  ")
    app.submit_name()
    assert app.scene == "board" and app.rank == 1
    assert app.scores.entries[0]["name"] == "Grace"
    assert hs.HighScores(tmp_path / "scores.json").best == app.score
    run(app, 60)
    assert app.subscriptions() == []                                  # idle on the leaderboard
    app.on_key("enter")
    assert app.scene == "play" and app.score == 0


def test_every_path_game_has_a_tutorial_link():
    names = ["coin_chase", "walker", "jump_lab", "platformer", "asteroids", "game_2048", "menus", "high_scores"]
    for name in names:
        text = (GAMES / f"{name}.py").read_text(encoding="utf-8")
        assert "Tutorial: https://albakore.github.io/pyzed/games/" in text, name


def test_target_rush_sounds(games, tmp_path):
    hs = games("high_scores")
    sounds = hs.Sounds("offline")
    for name in hs.SOUNDS:
        sounds.play(name)
        left, _ = sounds.engine.render(0.3)
        assert max(map(abs, left)) > 0.01, name
    left, _ = sounds.engine.render(1.0)
    assert max(map(abs, left[-2400:])) < 0.001                         # silent between sounds
    muted = hs.TargetRush(seed=1, path=tmp_path / "scores.json", sound_backend=None)
    muted.sound("hit")
    assert muted.sounds is None and muted.last_sound == "hit"
