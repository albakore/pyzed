"""Bench app: ROWS rows in a ScrollView + GridLayout (see ../benchkit.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchkit import FOOTER, H, ROWS, TICK, W, A, Driver, color, label  # noqa: E402

import os  # noqa: E402

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")
from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", str(W))
Config.set("graphics", "height", str(H))
Config.set("graphics", "position", "custom")
Config.set("graphics", "left", "0")
Config.set("graphics", "top", "0")
from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.graphics import Color, Rectangle  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402
from kivy.uix.button import Button  # noqa: E402
from kivy.uix.gridlayout import GridLayout  # noqa: E402
from kivy.uix.label import Label  # noqa: E402
from kivy.uix.scrollview import ScrollView  # noqa: E402
from kivy.uix.widget import Widget  # noqa: E402


class Bench(App):
    title = "bench"

    def build(self):
        self.driver = Driver()
        root = BoxLayout(orientation="vertical")
        grid = GridLayout(cols=2, size_hint_y=None, row_force_default=True, row_default_height=30)
        grid.bind(minimum_height=grid.setter("height"))
        self.labels = []
        for i in range(ROWS):
            text = Label(text=label(i, 0))
            grid.add_widget(text)
            grid.add_widget(Button(text="Open", size_hint_x=None, width=80))
            self.labels.append(text)
        scroll = ScrollView()
        scroll.add_widget(grid)
        root.add_widget(scroll)
        footer = Widget(size_hint_y=None, height=FOOTER)
        with footer.canvas:
            self.paint = Color(*[c / 255 for c in A])
            rect = Rectangle(pos=footer.pos, size=footer.size)
        footer.bind(pos=lambda w, p: setattr(rect, "pos", p), size=lambda w, s: setattr(rect, "size", s))
        root.add_widget(footer)
        Clock.schedule_interval(self.tick, TICK)
        return root

    def tick(self, _dt):
        k = self.driver.next()
        if k:
            for i, text in enumerate(self.labels):
                text.text = label(i, k)
            self.paint.rgb = [c / 255 for c in color(k)]


Bench().run()
