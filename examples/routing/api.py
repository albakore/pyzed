"""A pretend backend: async functions that take a moment, like a web API would.

The pages read with `load` and change data with `pz.action`; swap these bodies for your HTTP client
(httpx, aiohttp) or your database and nothing else changes."""

import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    id: int
    name: str
    price: float
    icon: str
    description: str


PRODUCTS = [
    Product(1, "Mechanical keyboard", 129.0, "keyboard", "Hot-swappable switches and a solid aluminium case."),
    Product(2, "Wireless mouse", 59.0, "mouse", "Light, quiet and with side buttons that go back and forward."),
    Product(3, "4K monitor", 399.0, "monitor", "27 inches, 144 Hz, calibrated colors out of the box."),
    Product(4, "Headphones", 179.0, "headphones", "Noise cancelling that keeps the music in and the office out."),
    Product(5, "USB-C dock", 89.0, "usb", "One cable for power, two screens, network and every gadget."),
    Product(6, "Desk lamp", 45.0, "lamp-desk", "Warm or cold light, dimmable, with a wireless charger in its base."),
]

#: How long the pretend network takes, in seconds (the tests make it 0).
DELAY = 0.6


async def products(sort: str = "name") -> list:
    await asyncio.sleep(DELAY)
    key = {"price": lambda p: p.price, "name": lambda p: p.name}.get(sort, lambda p: p.name)
    return sorted(PRODUCTS, key=key)


async def product(product_id: str):
    await asyncio.sleep(DELAY)
    return next((p for p in PRODUCTS if str(p.id) == product_id), None)


#: Products that fail the first time they load, to show error.py and its "Try again".
FLAKY = {"6"}


async def product_or_fail(product_id: str):
    """Like ``product``, but the desk lamp fails once, as a real network sometimes does."""
    if product_id in FLAKY:
        FLAKY.discard(product_id)
        await asyncio.sleep(DELAY)
        raise ConnectionError("the store didn't answer (it works the next time)")
    return await product(product_id)


async def sign_in(name: str) -> dict:
    await asyncio.sleep(DELAY)
    return {"name": name or "Ada", "email": f"{(name or 'ada').lower()}@example.com"}


async def place_order(items: list) -> int:
    await asyncio.sleep(DELAY)
    return 1000 + len(items)
