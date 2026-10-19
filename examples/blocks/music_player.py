"""Music player block: a library sidebar, an album page with a track list and a player bar with live progress."""

import math

import pyzed as pz
from pyzed import ui

COVER = pz.Gradient([(0.0, "#f97316"), (0.5, "#db2777"), (1.0, "#4f46e5")], angle=135)
PLAYLISTS = [("Synthwave nights", "#8b5cf6"), ("Deep focus", "#14b8a6"), ("Morning run", "#f59e0b"),
             ("Lo-fi beats", "#ec4899"), ("Jazz classics", "#3b82f6")]
TRACKS = [
    ("Neon Skyline", "The Midnight Arcade", 214),
    ("Afterglow", "The Midnight Arcade", 187),
    ("Chrome Hearts", "The Midnight Arcade feat. Vela", 242),
    ("Pixel Rain", "The Midnight Arcade", 201),
    ("Overdrive", "The Midnight Arcade", 229),
    ("Last Arcade", "The Midnight Arcade", 263),
    ("Slow Fade", "The Midnight Arcade", 198),
]


def clock(seconds):
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


class MusicPlayer(pz.App):
    title = "Music"
    size = (1200, 760)

    def __init__(self):
        self.current = 2
        self.elapsed = 96.0
        self.playing = True
        self.volume = 0.7
        self.shuffle, self.repeat = False, True
        self.liked = {0, 2, 4}

    def subscriptions(self):
        return [pz.every(0.25, self.tick, key="clock")] if self.playing else []

    # -- actions ---------------------------------------------------------------------------
    def tick(self):
        self.elapsed += 0.25
        if self.elapsed >= TRACKS[self.current][2]:
            self.skip(1)

    def play(self, index):
        self.current, self.elapsed, self.playing = index, 0.0, True

    def skip(self, step):
        self.play((self.current + step) % len(TRACKS))

    def toggle_like(self, index):
        self.liked ^= {index}

    # -- pieces ----------------------------------------------------------------------------
    def sidebar(self):
        lists = [ui.list_item(name, None, height=34, start=pz.container(width=22, height=22).style(
                     background=pz.Gradient([color, "#111827"], angle=135), radius=5))
                 for name, color in PLAYLISTS]
        return pz.column([
            pz.column([ui.list_item("Home", None, icon="house", height=32),
                       ui.list_item("Search", None, icon="search", height=32),
                       ui.list_item("Library", None, icon="library", selected=True, height=32)], spacing=2),
            ui.list_header("Playlists", end=ui.icon_button("plus", None, size="sm")),
            pz.column(lists, spacing=2),
        ], spacing=12, width=230, height="fill", padding=(16, 10)).style(background="panel")

    def equalizer(self):
        """Animated bars next to the playing track (they move with the position)."""
        bars = []
        for i in range(4):
            level = 0.35 + 0.65 * abs(math.sin(self.elapsed * 3.1 + i * 1.7)) if self.playing else 0.3
            bars.append(pz.container(width=3, height=4 + 10 * level).style(background="accent", radius=1))
        return pz.container(pz.row(bars, spacing=2, align="end"), width=24, height=16, align_y="end")

    def header(self):
        return pz.row([
            pz.container(pz.icon("disc-3", size=72, color="#ffffffcc"), width=190, height=190, center=True).style(
                background=COVER, radius=14, shadow=("#00000066", (0, 12), 30)),
            pz.column([
                ui.label("ALBUM", size="xs", weight="semibold", color="text_muted"),
                pz.text("Midnight Arcade", size=44, weight="bold"),
                ui.muted("The Midnight Arcade · 2026 · 7 songs, 25 min"),
                pz.space(height=8),
                pz.row([
                    ui.button("Play" if not self.playing else "Pause", lambda: setattr(self, "playing", not self.playing),
                              icon="pause" if self.playing else "play", variant="solid", size="lg"),
                    ui.icon_button("shuffle", lambda: setattr(self, "shuffle", not self.shuffle),
                                   selected=self.shuffle, tooltip="Shuffle"),
                    ui.icon_button("heart", None, tooltip="Save to library"),
                    ui.icon_button("ellipsis", None),
                ], spacing=8, align="center"),
            ], spacing=6),
        ], spacing=28, align="end")

    def tracks(self):
        rows = []
        for i, (title, artist, length) in enumerate(TRACKS):
            playing = i == self.current
            number = self.equalizer() if playing else ui.muted(str(i + 1))
            rows.append(pz.button(
                pz.row([
                    pz.container(number, width=28),
                    pz.column([ui.label(title, weight="medium", color="accent" if playing else "text"),
                               ui.muted(artist, size="sm")], spacing=1, width="fill"),
                    ui.icon_button("heart", lambda i=i: self.toggle_like(i), size="sm",
                                   color=self.resolved_theme().accent if i in self.liked else None),
                    pz.container(ui.muted(clock(length)), width=50, align_x="end"),
                ], spacing=12, align="center"),
                lambda i=i: self.play(i), width="fill", padding=(6, 12), radius=8,
                bg=self.resolved_theme().ghost_selected if playing else "#00000000",
                hover_bg=self.resolved_theme().ghost_hover))
        return pz.column(rows, spacing=2)

    def player(self):
        title, artist, length = TRACKS[self.current]
        now = pz.row([
            pz.container(pz.icon("disc-3", size=22, color="#ffffffcc"), width=48, height=48, center=True).style(
                background=COVER, radius=8),
            pz.column([ui.label(title, weight="semibold"), ui.muted(artist, size="sm")], spacing=2),
            ui.icon_button("heart", lambda: self.toggle_like(self.current), size="sm",
                           color=self.resolved_theme().accent if self.current in self.liked else None),
        ], spacing=12, align="center", width=300)
        controls = pz.column([
            pz.row([
                ui.icon_button("shuffle", lambda: setattr(self, "shuffle", not self.shuffle), selected=self.shuffle),
                ui.icon_button("skip-back", lambda: self.skip(-1)),
                pz.button(pz.icon("pause" if self.playing else "play", size=18, color="#111111"),
                          lambda: setattr(self, "playing", not self.playing), width=40, height=40, padding=11,
                          radius=20, bg="#ffffff", hover_bg="#e5e5e5"),
                ui.icon_button("skip-forward", lambda: self.skip(1)),
                ui.icon_button("repeat", lambda: setattr(self, "repeat", not self.repeat), selected=self.repeat),
            ], spacing=14, align="center"),
            pz.row([
                ui.muted(clock(self.elapsed), size="xs"),
                ui.slider(self.elapsed, lambda v: setattr(self, "position", v), min=0, max=length, step=1,
                          width=340),
                ui.muted(clock(length), size="xs"),
            ], spacing=10, align="center"),
        ], spacing=6, align="center", width="fill")
        volume = pz.row([
            ui.icon_button("list-music", None, size="sm"),
            ui.icon_button("volume-2" if self.volume else "volume-x",
                           lambda: setattr(self, "volume", 0 if self.volume else 0.7), size="sm"),
            ui.slider(self.volume, lambda v: setattr(self, "volume", v), width=110),
        ], spacing=6, align="center", width=300)
        return pz.container(pz.row([now, controls, pz.row([pz.hspace(), volume])], align="center"),
                            padding=(12, 20), width="fill").style(background="title_bar")

    def view(self):
        main = pz.scrollable(pz.column([
            pz.container(self.header(), padding=32, width="fill").style(
                background=pz.Paint(COVER, opacity=0.28, mask=pz.Mask([1, 0]))),
            pz.container(self.tracks(), padding=(0, 24, 24, 24)),
        ], spacing=8), height="fill")
        return pz.column([
            pz.row([self.sidebar(), ui.divider(vertical=True), pz.container(main, width="fill", height="fill").style(
                background="editor")], height="fill"),
            ui.divider(),
            self.player(),
        ], height="fill")


if __name__ == "__main__":
    pz.run(MusicPlayer)
