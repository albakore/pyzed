"""Bench app: ROWS rows in a scrollable column, re-rendered from state (see ../benchkit.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchkit import FOOTER, H, ROWS, TICK, W, A, Driver, color, hexc, label  # noqa: E402

import pyzed as pz  # noqa: E402
from pyzed import ui  # noqa: E402


class Bench(pz.App):
    title = "bench"
    size = (W, H)
    position = (0, 0)

    def __init__(self):
        self.k = 0
        self.driver = Driver()

    def update(self, message):
        if message == "tick":
            self.k = self.driver.next() or self.k

    def subscriptions(self):
        return [pz.every(TICK, "tick")]

    def view(self):
        rows = [pz.row([ui.label(label(i, self.k), width="fill"), ui.button("Open", "open")], align="center")
                for i in range(ROWS)]
        return pz.column([
            pz.scrollable(pz.column(rows, spacing=2, padding=8), height="fill", width="fill"),
            pz.container(width="fill", height=FOOTER, bg=hexc(color(self.k))),
        ])


pz.run(Bench)
