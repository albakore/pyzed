"""Calls to the server. Here they only wait a little; put your HTTP client (httpx, aiohttp) or your
database here. `load` functions read with them and `pz.action` functions change data with them."""

import asyncio

ITEMS = {"1": "First item", "2": "Second item", "3": "Third item"}


async def items():
    await asyncio.sleep(0.3)  # await client.get("/items")
    return dict(ITEMS)


async def item(item_id):
    await asyncio.sleep(0.2)  # await client.get(f"/items/{item_id}")
    return ITEMS.get(item_id)


async def save_favorite(item_id):
    await asyncio.sleep(0.4)  # await client.post("/favorites", json={"id": item_id})
    return item_id
