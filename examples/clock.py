"""An analog clock drawn on a canvas, after Iced's ``clock`` demo.

    python examples/clock.py

``pz.every(1, ...)`` redraws it every second; the hands are rotated paths.
"""

import math
import time

import pyzed as pz
from pyzed import draw

SIZE = 320


def hand(cx, cy, angle, length, width, color):
    a = math.radians(angle - 90)
    return draw.line(cx, cy, cx + length * math.cos(a), cy + length * math.sin(a), stroke=color, width=width,
                     cap="round")


class Clock(pz.App):
    title = "Clock"
    size = (SIZE + 40, SIZE + 80)

    def __init__(self):
        self.now = time.localtime()

    def subscriptions(self):
        return [pz.every(1.0, lambda: setattr(self, "now", time.localtime()))]

    def view(self):
        t = self.resolved_theme()
        c = SIZE / 2
        r = c - 8
        shapes = [draw.circle(c, c, r, fill=t.surface, stroke=t.border, width=2)]
        for i in range(60):
            a = math.radians(i * 6)
            outer, inner = r - 6, r - (18 if i % 5 == 0 else 11)
            shapes.append(draw.line(c + inner * math.sin(a), c - inner * math.cos(a),
                                    c + outer * math.sin(a), c - outer * math.cos(a),
                                    stroke=t.text if i % 5 == 0 else t.text_muted, width=2.5 if i % 5 == 0 else 1))
        for h in range(1, 13):
            a = math.radians(h * 30)
            shapes.append(draw.text(c + (r - 38) * math.sin(a), c - (r - 38) * math.cos(a), h, color=t.text,
                                    size=16, align_x="center", align_y="center"))
        hours, minutes, seconds = self.now.tm_hour % 12, self.now.tm_min, self.now.tm_sec
        shapes += [
            hand(c, c, hours * 30 + minutes / 2, r * 0.5, 6, t.text),
            hand(c, c, minutes * 6 + seconds / 10, r * 0.75, 4, t.text),
            hand(c, c, seconds * 6, r * 0.82, 2, t.error),
            draw.circle(c, c, 5, fill=t.error),
        ]
        return pz.container(
            pz.column([pz.canvas(shapes, width=SIZE, height=SIZE),
                       pz.text(time.strftime("%H:%M:%S", self.now), size=20, font="mono", color=t.text)],
                      spacing=12, align="center"),
            center=True, bg=t.background,
        )


if __name__ == "__main__":
    pz.run(Clock)
