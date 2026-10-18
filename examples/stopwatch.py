"""A stopwatch with laps, after Iced's ``stopwatch`` demo.

    python examples/stopwatch.py

The timer subscription only exists while the watch runs, so an idle app uses no CPU.
Space starts/stops, ``l`` records a lap, ``r`` resets.
"""

import time

import pyzed as pz
from pyzed import ui


def fmt(seconds):
    minutes, rest = divmod(seconds, 60)
    return f"{int(minutes):02d}:{rest:05.2f}"


class Stopwatch(pz.App):
    title = "Stopwatch"
    size = (420, 520)

    def __init__(self):
        self.elapsed = 0.0
        self.started = None
        self.laps = []

    @property
    def running(self):
        return self.started is not None

    def now(self):
        return self.elapsed + (time.monotonic() - self.started if self.running else 0.0)

    def toggle(self):
        if self.running:
            self.elapsed = self.now()
            self.started = None
        else:
            self.started = time.monotonic()

    def reset(self):
        self.elapsed, self.started, self.laps = 0.0, None, []

    def lap(self):
        if self.running:
            self.laps.insert(0, self.now())

    def subscriptions(self):
        # An empty message still triggers a redraw; ``now()`` does the rest.
        return [pz.every(0.03, lambda: None)] if self.running else []

    def on_key(self, combo):
        {"space": self.toggle, "l": self.lap, "r": self.reset}.get(combo, lambda: None)()

    def view(self):
        t = self.resolved_theme()
        laps = [
            pz.row([ui.muted(f"Lap {len(self.laps) - i}"), pz.hspace(), pz.text(fmt(v), font="mono", color=t.text)])
            for i, v in enumerate(self.laps)
        ]
        return pz.container(
            pz.column([
                pz.text(fmt(self.now()), size=56, font="mono", color=t.text),
                pz.row([
                    ui.button("Stop" if self.running else "Start", self.toggle, variant="solid",
                              tint="error" if self.running else "success", keys="space"),
                    ui.button("Lap", self.lap, disabled=not self.running, keys="l"),
                    ui.button("Reset", self.reset, variant="ghost", keys="r"),
                ], spacing=8),
                pz.scrollable(pz.column(laps, spacing=6, width="fill"), height="fill"),
            ], spacing=20, align="center", max_width=340),
            padding=28, width="fill", height="fill", align_x="center", bg=t.editor,
        )


if __name__ == "__main__":
    pz.run(Stopwatch)
