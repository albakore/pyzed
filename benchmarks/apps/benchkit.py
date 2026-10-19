"""Shared plumbing for the bench apps (not part of the line counts).

Every bench app shows ROWS rows (a label and a button each, one real widget per row,
no virtualization) in a scrollable area, above a 40 px footer bar painted in a sentinel
color. The harness (benchmarks/run.py) watches the screen for that color to detect the
first frame, then writes "go" on stdin. From then on, on each 250 ms timer tick the app
rewrites all ROWS labels and flips the footer color in the same update, after printing
"T <k> <time.monotonic()>". The harness measures how long the new color takes to reach
the screen.
"""

import os
import sys
import threading
import time

ROWS = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 1000
UPDATES = int(os.environ.get("BENCH_UPDATES", "10"))
W, H, FOOTER = 640, 480, 40
TICK = 0.25
A = (0x12, 0x34, 0x56)
B = (0xD2, 0x7A, 0x1E)


def color(k):
    return B if k % 2 else A


def hexc(c):
    return "#%02x%02x%02x" % c


def label(i, k):
    return f"Row {i}" if k == 0 else f"Row {i} - {k}"


class Driver:
    def __init__(self):
        self.go = False
        self.k = 0
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in sys.stdin:
            if line.strip() == "go":
                self.go = True

    def next(self):
        """Called on every timer tick: the number of the update to make now, or None."""
        if not self.go or self.k >= UPDATES:
            return None
        self.k += 1
        print(f"T {self.k} {time.monotonic()}", flush=True)
        return self.k
