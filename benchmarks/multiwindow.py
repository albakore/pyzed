"""CPU cost of many open windows while one of them updates 60 times a second.

The main window shows a counter driven by a timer; the other windows show ROWS rows each and
change nothing. Without ``--isolated`` every tick rebuilds and redraws every window; with it the
quiet windows are ``isolated`` and only the main one is rebuilt::

    python benchmarks/multiwindow.py --windows 4
    python benchmarks/multiwindow.py --windows 4 --isolated

Prints one JSON line: windows, isolated, ticks handled and CPU milliseconds per tick.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import threading
import time

import pyzed as pz
from pyzed import ui

parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
parser.add_argument("--windows", type=int, default=4, help="open windows, the main one included")
parser.add_argument("--rows", type=int, default=300, help="rows in each quiet window")
parser.add_argument("--isolated", action="store_true", help="make the quiet windows isolated")
parser.add_argument("--seconds", type=float, default=5.0, help="how long to measure")
parser.add_argument("--warmup", type=float, default=2.0, help="seconds before measuring")
args = parser.parse_args()


def cpu() -> float:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    return usage.ru_utime + usage.ru_stime


class Quiet(pz.Window):
    size = (360, 480)
    isolated = args.isolated

    def __init__(self, index: int):
        self.title = f"Quiet {index}"
        self.index = index

    def view(self):
        rows = [pz.row([ui.label(f"Window {self.index}, row {i}", width="fill"), ui.button("Open", "open")],
                       align="center") for i in range(args.rows)]
        return pz.scrollable(pz.column(rows, spacing=2, padding=8), height="fill", width="fill")


class Main(pz.App):
    title = "Busy"
    size = (360, 200)

    def __init__(self):
        self.ticks = 0
        self.start = None

    def on_start(self):
        threading.Thread(target=self.measure, daemon=True).start()
        return [Quiet(i).open() for i in range(1, args.windows)]

    def measure(self):
        time.sleep(args.warmup)
        ticks, used = self.ticks, cpu()
        time.sleep(args.seconds)
        ticks, used = self.ticks - ticks, cpu() - used
        print(json.dumps({"windows": args.windows, "isolated": args.isolated, "ticks": ticks,
                          "cpu_ms_per_tick": round(1000 * used / max(ticks, 1), 3),
                          "cpu_percent": round(100 * used / args.seconds, 1),
                          "renderer": pz.renderer_info()}), flush=True)
        os._exit(0)

    def tick(self):
        self.ticks += 1

    def subscriptions(self):
        return [pz.every(1 / 60, self.tick)]

    def view(self):
        return pz.center(ui.heading(str(self.ticks)))


pz.run(Main)
