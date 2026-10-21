"""Services: the parts of an app that draw nothing but raise events, written in code.

    python examples/services.py

A clock (``pz.Timer``), a prime counter in a background thread (``pz.Worker``), a command whose
output streams in line by line (``pz.Process``), the clipboard watched for new text
(``pz.Clipboard``) and a launch counter kept between runs (``pz.Settings``). Their events reach
the handlers on the app's thread, so the handlers change the state like any callback. The same
services are the tray of Pyzed Design (see examples/designer/tasks.pzform).
"""

import sys
import time

import pyzed as pz
from pyzed import ui

COMMAND = [sys.executable, "-c", "import platform, time\n"
           "for part in ('Python ' + platform.python_version(), platform.system(), platform.machine()):\n"
           "    print(part, flush=True); time.sleep(0.4)"]


def card(icon, title, subtitle, *body):
    return ui.card(pz.column([
        pz.row([pz.icon(icon, size=16, color=pz.theme.current().accent), ui.label(title, weight="semibold"), pz.hspace(),
                ui.muted(subtitle, size="xs", mono=True)], spacing=8, align="center"),
        *body,
    ], spacing=10), width="fill")


class Services(pz.App):
    title = "Services"
    size = (860, 560)

    def __init__(self):
        self.clock = pz.Timer(1000, on_tick=self.tick)
        self.primes = pz.Worker(self.count_primes, on_progress=self.counted, on_done=self.found)
        self.process = pz.Process(COMMAND, on_output=self.printed, on_finished=self.ended)
        self.clipboard = pz.Clipboard(watch=True, on_change=self.copied)
        self.settings = pz.Settings("pyzed-services-example")
        self.launches = self.settings.get("launches", 0) + 1
        self.settings.set("launches", self.launches)
        self.now = time.strftime("%H:%M:%S")
        self.ticks = 0
        self.progress, self.result = 0.0, None
        self.output, self.exit_code = [], None
        self.copies = []

    def subscriptions(self):
        return self.clock.subscriptions() + self.clipboard.subscriptions()

    # -- Timer ------------------------------------------------------------------------------------
    def tick(self, count):
        self.now, self.ticks = time.strftime("%H:%M:%S"), count

    def toggle_clock(self):
        self.clock.stop() if self.clock.running else self.clock.start()

    # -- Worker -----------------------------------------------------------------------------------
    def count_primes(self, limit):
        """Runs in a thread: the window keeps answering while it counts."""
        found = 0
        for n in range(2, limit):
            if self.primes.cancelled:
                return None
            if all(n % d for d in range(2, int(n ** 0.5) + 1)):
                found += 1
            if n % 5000 == 0:
                self.primes.report(n / limit)
        return found

    def start_count(self):
        if self.primes.busy:
            self.primes.cancel()
        else:
            self.progress, self.result = 0.0, None
            self.primes.run(400_000)

    def counted(self, fraction):
        self.progress = fraction

    def found(self, result):
        self.progress, self.result = 1.0, result

    # -- Process ----------------------------------------------------------------------------------
    def run_command(self):
        self.output, self.exit_code = [], None
        self.process.start()

    def printed(self, line):
        self.output.append(line)

    def ended(self, code):
        self.exit_code = code

    # -- Clipboard --------------------------------------------------------------------------------
    def copied(self, text):
        self.copies = [text.strip()[:60]] + self.copies[:3]

    # -- view -------------------------------------------------------------------------------------
    def view(self):
        clock = card("timer", "Timer", "pz.Timer(1000)",
                     pz.text(self.now, size=34, font="mono"),
                     pz.row([ui.muted(f"{self.ticks} ticks", size="sm"), pz.hspace(),
                             ui.button("Stop" if self.clock.running else "Start", self.toggle_clock, size="sm",
                                       icon="pause" if self.clock.running else "play")], align="center"))
        busy = self.primes.busy
        worker = card("cpu", "Worker", "pz.Worker(count)",
                      ui.progress(self.progress, tint="success" if self.result is not None else "accent"),
                      ui.muted(f"{self.result:,} primes under 400,000" if self.result is not None else
                               f"Counting… {self.progress:.0%}" if busy else "Counts in a background thread",
                               size="sm"),
                      pz.row([pz.hspace(), ui.button("Cancel" if busy else "Count primes", self.start_count,
                                                     size="sm", icon="x" if busy else "play")]))
        lines = "\n".join(self.output) or "…"
        status = ("running" if self.process.running else "not started" if self.exit_code is None
                  else f"exit code {self.exit_code}")
        process = card("terminal", "Process", "pz.Process(command)",
                       pz.container(ui.label(lines, mono=True, size="sm"), padding=10, width="fill", height=86)
                       .style(background="editor", radius=6),
                       pz.row([ui.muted(status, size="sm"), pz.hspace(),
                               ui.button("Run", None if self.process.running else self.run_command, size="sm",
                                         icon="play")], align="center"))
        clipboard = card("clipboard", "Clipboard", "watch=True",
                         pz.column([ui.label(c, size="sm", wrap=False) for c in self.copies] or
                                   [ui.muted("Copy some text in any app: it shows up here.", size="sm")],
                                   spacing=4, height=60),
                         pz.row([pz.hspace(), ui.button("Copy the time", lambda: self.clipboard.copy(self.now),
                                                         size="sm", icon="copy")]))
        settings = card("save", "Settings", "pz.Settings",
                        pz.text(str(self.launches), size=34, font="mono"),
                        ui.muted(f"launches, kept in {self.settings.path.name}", size="sm"))
        return pz.container(pz.column([
            ui.heading("Services", level=2),
            ui.muted("Parts of an app that draw nothing but raise events.", size="sm"),
            pz.row([clock, worker, settings], spacing=12),
            pz.row([process, clipboard], spacing=12),
        ], spacing=12), padding=20, width="fill", height="fill").style(background="editor")


if __name__ == "__main__":
    pz.run(Services)
