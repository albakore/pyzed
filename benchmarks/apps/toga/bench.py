"""Bench app: ROWS rows in a ScrollContainer (see ../benchkit.py)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from benchkit import FOOTER, H, ROWS, TICK, W, A, Driver, color, hexc, label  # noqa: E402

import asyncio  # noqa: E402

import toga  # noqa: E402
from toga.style import Pack  # noqa: E402


class Bench(toga.App):
    def startup(self):
        self.driver = Driver()
        self.labels = []
        inner = toga.Box(style=Pack(direction="column"))
        for i in range(ROWS):
            text = toga.Label(label(i, 0), style=Pack(flex=1))
            inner.add(toga.Box(children=[text, toga.Button("Open")], style=Pack(direction="row")))
            self.labels.append(text)
        self.footer = toga.Box(style=Pack(height=FOOTER, background_color=hexc(A)))
        root = toga.Box(children=[toga.ScrollContainer(content=inner, style=Pack(flex=1)), self.footer],
                        style=Pack(direction="column"))
        self.main_window = toga.MainWindow(title="bench", size=(W, H), position=(0, 0))
        self.main_window.content = root
        self.main_window.show()
        asyncio.get_event_loop().create_task(self.ticker())

    async def ticker(self):
        while True:
            await asyncio.sleep(TICK)
            k = self.driver.next()
            if k:
                for i, text in enumerate(self.labels):
                    text.text = label(i, k)
                self.footer.style.background_color = hexc(color(k))


Bench("bench", "org.pyzed.bench").main_loop()
