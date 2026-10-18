"""Background work without freezing the UI: Command.perform, pz.post from threads, progress bars and toasts.

    python examples/downloads.py

The "downloads" are simulated with sleep so the example works offline.
Walkthrough: https://albakore.github.io/pyzed/tutorials/background-tasks/
"""

import random
import threading
import time

import pyzed as pz
from pyzed import Command, ui

FILES = ["iced-0.14.tar.gz", "zed-themes.json", "ibm-plex.zip", "lucide-icons.ttf"]


class Downloads(pz.App):
    title = "Descargas"
    size = (560, 460)

    def __init__(self):
        self.progress = {}       # name -> 0..1
        self.toasts = []         # (id, title, message, kind)
        self.checking = False
        self.latest = None

    # -- pz.post: a worker thread reports progress through update() -----------------
    def start(self, name):
        self.progress[name] = 0.0

        def worker():
            done = 0.0
            while done < 1.0:
                time.sleep(random.uniform(0.03, 0.12))
                done = min(1.0, done + random.uniform(0.02, 0.08))
                pz.post(("progress", name, done))
            pz.post(("finished", name))

        threading.Thread(target=worker, daemon=True).start()

    def update(self, message):
        kind, name, *rest = message
        if kind == "progress":
            self.progress[name] = rest[0]
        elif kind == "finished":
            self.notify(f"{name} descargado", kind="success")
        elif kind == "dismiss":
            self.toasts = [t for t in self.toasts if t[0] != name]

    def notify(self, title, message=None, kind="info"):
        toast_id = f"{time.monotonic()}"
        self.toasts.append((toast_id, title, message, kind))
        threading.Timer(4, pz.post, args=(("dismiss", toast_id),)).start()

    # -- Command.perform: run a blocking function and get its result back --------------
    def check_updates(self):
        self.checking = True
        return Command.perform(self.fetch_latest_version, self.got_version)

    @staticmethod
    def fetch_latest_version():
        time.sleep(1.5)  # e.g. an HTTP request
        return "0.2.0"

    def got_version(self, version):
        self.checking, self.latest = False, version
        self.notify("Hay una versión nueva", f"Pyzed {version} está disponible.")

    # -- view ----------------------------------------------------------------------------
    def row(self, name):
        value = self.progress.get(name)
        if value is None:
            action = ui.button("Descargar", lambda: self.start(name), size="sm", icon="download")
        elif value < 1:
            action = ui.muted(f"{value:.0%}", size="sm")
        else:
            action = ui.badge("listo", tint="success", icon="check")
        return pz.column([
            pz.row([pz.icon("file-archive", size=16), ui.label(name), pz.hspace(), action], spacing=8, align="center"),
            ui.progress(value or 0, tint="success" if value == 1 else "accent") if value is not None else None,
        ], spacing=6)

    def view(self):
        body = pz.container(
            pz.column([
                pz.row([ui.heading("Descargas", level=2), pz.hspace(),
                        ui.button("Buscar actualizaciones", None if self.checking else self.check_updates,
                                  icon="loader" if self.checking else "refresh-cw", variant="outline")],
                       align="center"),
                ui.card(pz.column([self.row(n) for n in FILES], spacing=14)),
                ui.muted(f"Última versión: {self.latest}" if self.latest else "Pulsa un botón: la interfaz sigue respondiendo.",
                         size="sm"),
            ], spacing=16),
            padding=24,
            width="fill",
            height="fill",
            bg=self.theme.editor,
        )
        items = [ui.toast(title, msg, kind=kind, on_dismiss=("dismiss", tid)) for tid, title, msg, kind in self.toasts]
        return ui.toasts(body, items)


if __name__ == "__main__":
    pz.run(Downloads)
