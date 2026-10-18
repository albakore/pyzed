"""Live data with ``pz.listen``: a subscription backed by an async generator.

    python examples/websocket_stream.py

``listen`` runs the generator for as long as it is returned from ``subscriptions()``
and sends every value it yields to ``update``. Here it simulates a price feed; replace
the body with ``async for message in websocket:`` to consume a real socket.
"""

import asyncio
import random

import pyzed as pz
from pyzed import ui

SYMBOLS = ["PYZ", "ICE", "ZED", "RST"]


async def feed():
    prices = {s: random.uniform(50, 150) for s in SYMBOLS}
    while True:
        await asyncio.sleep(0.25)
        symbol = random.choice(SYMBOLS)
        prices[symbol] *= 1 + random.gauss(0, 0.01)
        yield symbol, prices[symbol]


class Ticker(pz.App):
    title = "Live feed"
    size = (720, 460)

    def __init__(self):
        self.connected = True
        self.history = {s: [] for s in SYMBOLS}

    def subscriptions(self):
        return [pz.listen(feed)] if self.connected else []

    def update(self, message):
        symbol, price = message
        self.history[symbol] = (self.history[symbol] + [price])[-60:]

    def view(self):
        t = self.resolved_theme()
        cards = []
        for symbol, values in self.history.items():
            if len(values) < 2:
                cards.append(ui.stat(symbol, "…", width="fill"))
                continue
            delta = (values[-1] / values[0] - 1) * 100
            cards.append(ui.stat(symbol, f"{values[-1]:.2f}", delta=delta, trend=values, width="fill"))
        return pz.container(
            pz.column([
                pz.row([ui.heading("Live feed", level=2), pz.hspace(),
                        ui.switch(self.connected, lambda v: setattr(self, "connected", v)),
                        ui.muted("connected" if self.connected else "paused")], spacing=8, align="center"),
                pz.row(cards[:2], spacing=12),
                pz.row(cards[2:], spacing=12),
            ], spacing=16),
            padding=24, width="fill", height="fill", bg=t.background,
        )


if __name__ == "__main__":
    pz.run(Ticker)
