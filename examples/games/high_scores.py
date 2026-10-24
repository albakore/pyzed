"""Target Rush: a 20-second clicking game that keeps a top-10 table on disk.

    python examples/games/high_scores.py

Click the targets before they shrink away: the sooner, the more points, and hits in a row
build a combo. A good score asks for your name and goes into the leaderboard, which is
saved as JSON in your user data folder and is still there next time. Shows:

- **Saving data** the safe way: a JSON file in the right folder for each system, written
  to a temporary file first and then swapped in, so a crash never leaves half a file.
  A missing or damaged file just means an empty table.
- **Name entry** with ``ui.input`` (Enter submits) and a leaderboard made of rows.
- **Sound effects** from one ``sound(name)`` method called wherever a sound belongs. The
  sounds are synthesized live by ``pyzed.audio`` (drum voices, no files); with no sound card
  the game simply stays silent.

Tutorial: https://albakore.github.io/pyzed/games/high-scores/
"""

import json
import math
import os
import random
import sys
import tempfile
import time
from pathlib import Path

import pyzed as pz
from pyzed import audio, draw, game, ui

W, H = 640, 420
ROUND = 20.0
TARGET_LIFE = 1.4         # seconds a target lives (it shrinks meanwhile)
TARGET_R = 34
KEEP = 10                 # entries in the leaderboard

SOUNDS = {                # effect: (drum voice, tune in semitones, decay in seconds)
    "start": ("tom", 0, 0.3),
    "hit": ("tom", 7, 0.12),
    "combo": ("clap", 0, 0.25),
    "miss": ("kick", -6, 0.25),
    "end": ("tom", -7, 0.6),
    "record": ("hihat", 5, 0.5),
}


# -- sound ----------------------------------------------------------------------------------------
class Sounds:
    """The game's sound effects, synthesized live by ``pyzed.audio``: there are no files to load.

    Four drum voices go through a mixer to the speakers, and each effect strikes one voice with
    its own tuning. Without a sound card the engine plays silently, so the game runs anywhere.
    """

    def __init__(self, backend="auto", volume=0.8):
        self.engine = audio.Engine(backend)
        mixer = self.engine.add("mixer")
        self.out = self.engine.add("audio_out", volume=volume)
        self.engine.connect(mixer, "left", self.out, "left")
        self.engine.connect(mixer, "right", self.out, "right")
        self.voices = {}
        for i, kind in enumerate(("tom", "clap", "kick", "hihat"), start=1):
            self.voices[kind] = self.engine.add("drum", sound=kind)
            self.engine.connect(self.voices[kind], "out", mixer, f"in_{i}")
        if backend != "offline":         # "offline" never plays: tests render() it instead
            self.engine.start()

    def play(self, name):
        kind, tune, decay = SOUNDS[name]
        voice = self.voices[kind]
        voice.set(tune=tune, decay=decay)
        voice.trigger()                  # returns at once: the sound plays on the audio thread


# -- saving --------------------------------------------------------------------------------------
def data_dir(app_name):
    """The folder where a game keeps its saves, following each system's convention."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / app_name


class HighScores:
    """The best ``KEEP`` scores, as a list of ``{"name", "score", "date"}`` saved as JSON."""

    def __init__(self, path):
        self.path = Path(path)
        self.entries = self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            entries = [e for e in data.get("scores", []) if isinstance(e.get("score"), int)]
        except (OSError, ValueError, AttributeError):
            return []                      # no file yet, or a damaged one: start empty
        return sorted(entries, key=lambda e: -e["score"])[:KEEP]

    def qualifies(self, score):
        return score > 0 and (len(self.entries) < KEEP or score > self.entries[-1]["score"])

    def add(self, name, score):
        """Adds a score, saves, and returns its place (1 is the best)."""
        entry = {"name": name.strip()[:16] or "Player", "score": score, "date": time.strftime("%Y-%m-%d")}
        self.entries.append(entry)
        self.entries.sort(key=lambda e: -e["score"])   # a stable sort: older equal scores stay first
        del self.entries[KEEP:]
        self.save()
        return self.entries.index(entry) + 1 if entry in self.entries else None

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write next to the real file, then replace it in one step (atomic on every system).
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".scores-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"version": 1, "scores": self.entries}, f, indent=2)
        os.replace(tmp, self.path)

    @property
    def best(self):
        return self.entries[0]["score"] if self.entries else 0


# -- the game ------------------------------------------------------------------------------------
class TargetRush(pz.App):
    title = "Target Rush"
    size = (W + 32, H + 92)
    theme = "Pyzed Dark"

    def __init__(self, seed=None, path=None, sound_backend="auto"):
        self.random = random.Random(seed)
        self.scores = HighScores(path or data_dir("Target Rush") / "scores.json")
        self.sparks = game.Particles(gravity=500, seed=seed)
        self.scene = "ready"             # ready -> play -> name (if it made the table) -> board
        self.name = ""
        self.rank = None
        self.last_sound, self.sound_age = None, 9.0
        self.sound_backend = sound_backend   # "auto", "offline" (tests) or None (muted)
        self.sounds = None                   # made on the first sound, so a menu costs nothing
        self.reset()

    def reset(self):
        self.targets = []                # [x, y, age]
        self.score, self.combo, self.hits, self.misses = 0, 0, 0, 0
        self.time_left = ROUND
        self.spawn = 0.0
        self.clock = 0.0

    def start(self):
        self.reset()
        self.scene = "play"
        self.sound("start")

    # -- sound hooks --------------------------------------------------------------------------
    def sound(self, name):
        """Called wherever a sound belongs: "start", "hit", "miss", "combo", "end", "record".

        Plays the effect and shows its name in the HUD for a moment.
        """
        self.last_sound, self.sound_age = name, 0.0
        if self.sounds is None and self.sound_backend:
            self.sounds = Sounds(self.sound_backend)
        if self.sounds:
            self.sounds.play(name)

    # -- update -------------------------------------------------------------------------------
    def subscriptions(self):
        return [pz.frames(self.tick)] if self.scene == "play" or len(self.sparks) or self.sound_age < 1 else []

    def tick(self, dt):
        dt = min(dt, 1 / 30)
        self.sparks.update(dt)
        self.sound_age += dt
        if self.scene != "play":
            return
        self.clock += dt
        self.time_left = max(0.0, self.time_left - dt)
        self.spawn -= dt
        if self.spawn <= 0:
            self.spawn = max(0.35, 0.8 - self.clock * 0.02)
            self.targets.append([self.random.uniform(50, W - 50), self.random.uniform(50, H - 50), 0.0])
        for t in self.targets:
            t[2] += dt
        expired = [t for t in self.targets if t[2] >= TARGET_LIFE]
        if expired:
            self.combo = 0
            self.misses += len(expired)
        self.targets = [t for t in self.targets if t[2] < TARGET_LIFE]
        if self.time_left <= 0:
            self.finish()

    def finish(self):
        self.targets = []
        if self.scores.qualifies(self.score):
            self.scene = "name"
            self.sound("record")
        else:
            self.scene = "board"
            self.rank = None
            self.sound("end")

    # -- input --------------------------------------------------------------------------------
    def click(self, x, y):
        if self.scene != "play":
            return
        for t in reversed(self.targets):             # the newest (on top) first
            r = self.radius(t)
            if math.hypot(x - t[0], y - t[1]) <= r:
                self.targets.remove(t)
                self.combo += 1
                self.hits += 1
                freshness = 1 - t[2] / TARGET_LIFE    # earlier clicks are worth more
                self.score += int(10 + 40 * freshness) * min(self.combo, 5)
                self.sparks.burst(t[0], t[1], count=18, color=["#f472b6", "#fbbf24", "#ffffff"], speed=(60, 260))
                self.sound("combo" if self.combo in (5, 10, 15) else "hit")
                return
        self.combo = 0
        self.misses += 1
        self.sound("miss")

    def set_name(self, value):
        self.name = value

    def submit_name(self, *_):
        self.rank = self.scores.add(self.name, self.score)
        self.scene = "board"

    def on_key(self, combo):
        if combo in ("enter", "space") and self.scene in ("ready", "board"):
            self.start()

    # -- draw ---------------------------------------------------------------------------------
    @staticmethod
    def radius(t):
        return TARGET_R * (1 - t[2] / TARGET_LIFE * 0.75)

    def board(self):
        shapes = [draw.background("#12101c")]
        for i in range(0, W, 32):
            shapes.append(draw.line(i, 0, i, H, stroke="#ffffff06"))
        for t in self.targets:
            r = self.radius(t)
            appear = min(1.0, t[2] / 0.12)              # a quick grow-in
            r *= appear
            for k, color in enumerate(("#f472b6", "#ffffff", "#f472b6")):
                shapes.append(draw.circle(t[0], t[1], r * (1 - k * 0.3), fill=color))
            # the remaining time as an arc around the target
            left = 1 - t[2] / TARGET_LIFE
            shapes.append(draw.arc(t[0], t[1], TARGET_R + 6, -90, -90 + 360 * left, stroke="#fbbf24", width=3,
                                   cap="round"))
        shapes += self.sparks.shapes(glow=True)
        return pz.canvas(shapes, width=W, height=H, on_press=self.click, cursor="crosshair")

    def leaderboard(self):
        rows = []
        for i, e in enumerate(self.scores.entries):
            mine = self.rank == i + 1
            medal = {0: "#fbbf24", 1: "#cbd5e1", 2: "#d97706"}.get(i)
            rows.append(pz.container(pz.row([
                pz.container(pz.text(f"{i + 1}", weight="bold", color=medal) if medal else ui.muted(f"{i + 1}"),
                             width=28),
                pz.text(e["name"], weight="semibold" if mine else None),
                pz.hspace(),
                ui.muted(e["date"], size="sm"),
                pz.container(pz.text(f"{e['score']:,}", font="mono"), width=70, align_x="end"),
            ], spacing=10, align="center"), padding=(4, 10)).style(background="#fbbf2430" if mine else None,
                                                                  radius=6))
        if not rows:
            rows = [ui.muted("No scores yet. Be the first!")]
        return pz.column(rows, spacing=2, width=340)

    def card(self, *children):
        card = pz.container(pz.column(list(children), spacing=10, align="center"), padding=(20, 28)).style(
            glass=True, radius=14).animate("fade_in_up", duration=260)
        return pz.container(card, width="fill", height="fill", align_x="center", align_y="center")

    def overlay(self):
        if self.scene == "ready":
            return self.card(ui.heading("Target Rush", level=2), ui.muted("Click the targets before they vanish."),
                             self.leaderboard(), ui.button("Start", self.start, variant="solid", icon="play"))
        if self.scene == "name":
            return self.card(
                ui.heading("New high score!", level=2), pz.text(f"{self.score:,}", size=28, weight="bold"),
                pz.container(ui.input(self.name, self.set_name, placeholder="Your name", icon="user",
                                      on_submit=self.submit_name, id="name", max_length=16), width=240),
                ui.button("Save", self.submit_name, variant="solid", icon="save"))
        if self.scene == "board":
            place = f"You placed #{self.rank}!" if self.rank else f"Score {self.score:,}"
            return self.card(ui.heading("Leaderboard", level=2), ui.muted(place), self.leaderboard(),
                             ui.button("Play again", self.start, variant="solid", icon="rotate-ccw"))
        return None

    def view(self):
        t = self.resolved_theme()
        sound = (ui.badge(f"♪ {self.last_sound}", icon="volume-2", tint="hint")
                 if self.sound_age < 0.8 and self.last_sound else None)
        hud = pz.row([
            ui.label("Target Rush", weight="semibold"), pz.hspace(), sound,
            ui.badge(f"x{self.combo}", icon="zap", tint="warning") if self.combo > 1 else None,
            ui.badge(f"{self.score:,}", icon="target", tint="accent"),
            ui.badge(f"{math.ceil(self.time_left)} s", icon="timer", tint="error" if self.time_left < 5 else "text_muted"),
            ui.badge(f"Best {self.scores.best:,}", icon="trophy", tint="text_muted"),
        ], spacing=8, align="center")
        play = pz.stack([self.board(), self.overlay()], width=W, height=H)
        return pz.container(pz.column([hud, pz.container(play, radius=10, clip=True),
                                       ui.muted(f"Scores are saved in {self.scores.path}", size="sm")], spacing=10),
                            padding=16, width="fill", height="fill", bg=t.background)


if __name__ == "__main__":
    pz.run(TargetRush)
