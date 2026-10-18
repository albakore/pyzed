"""Tutorial, step 4: async work without freezing the window.

    python examples/tutorial/step4_async.py
"""

import asyncio
import random

import pyzed as pz
from pyzed import ui


async def fetch_quote():
    await asyncio.sleep(1.2)  # pretend this is a network request (aiohttp, httpx...)
    return random.choice(["Simple is better than complex.", "Readability counts.", "Now is better than never."])


class Quotes(pz.App):
    title = "Quotes"
    size = (480, 260)

    def __init__(self):
        self.quote = "Press the button."
        self.loading = False

    def load(self):
        self.loading = True
        # Return a Command.perform: fetch_quote runs on Pyzed's asyncio loop and its
        # result is passed to self.loaded on the UI thread.
        return pz.Command.perform(fetch_quote, self.loaded)

    def loaded(self, quote):
        self.quote, self.loading = quote, False

    def subscriptions(self):
        # Redraw ~30 times per second while loading so the spinner turns.
        return [pz.every(1 / 30, lambda: None)] if self.loading else []

    def view(self):
        return pz.container(
            pz.column([
                ui.label(self.quote, size="lg"),
                pz.row([ui.button("New quote", self.load, disabled=self.loading, variant="solid"),
                        ui.spinner() if self.loading else None], spacing=10, align="center"),
            ], spacing=16),
            padding=24,
        )


if __name__ == "__main__":
    pz.run(Quotes)
