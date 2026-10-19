"""A Pomodoro timer: the app built step by step in the AI prompting guide."""

import pyzed as pz
from pyzed import ui

WORK, BREAK = 25 * 60, 5 * 60


class Pomodoro(pz.App):
    title = "Pomodoro"
    size = (420, 380)

    def __init__(self):
        self.mode = "Focus"
        self.left = WORK
        self.running = False
        self.done = 0

    def subscriptions(self):
        return [pz.every(1, self.tick, key="timer")] if self.running else []

    def tick(self):
        self.left -= 1
        if self.left <= 0:
            if self.mode == "Focus":
                self.done += 1
            self.mode = "Break" if self.mode == "Focus" else "Focus"
            self.left = BREAK if self.mode == "Break" else WORK

    def switch(self, mode):
        self.mode, self.running = mode, False
        self.left = WORK if mode == "Focus" else BREAK

    def toggle(self):
        self.running = not self.running

    def reset(self):
        self.running, self.left = False, WORK if self.mode == "Focus" else BREAK

    def view(self):
        total = WORK if self.mode == "Focus" else BREAK
        return pz.center(pz.column([
            ui.segmented(["Focus", "Break"], self.mode, self.switch),
            pz.text(f"{self.left // 60:02d}:{self.left % 60:02d}", size=64, weight="bold"),
            ui.progress(1 - self.left / total, height=8, width=280),
            pz.row([
                ui.button("Pause" if self.running else "Start", self.toggle,
                          icon="pause" if self.running else "play", variant="solid", size="lg"),
                ui.icon_button("rotate-ccw", self.reset, tooltip="Reset"),
            ], spacing=8, align="center"),
            ui.muted(f"{self.done} sessions today", size="sm"),
        ], spacing=18, align="center")).style(background="editor")


if __name__ == "__main__":
    pz.run(Pomodoro)
