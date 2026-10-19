"""Async support: one asyncio event loop, running in a background thread, shared by the app.

Coroutines returned from ``update`` (or passed to ``Command.perform``) run on this loop,
so libraries that need a single loop (aiohttp sessions, websockets...) just work.
"""

from __future__ import annotations

import asyncio
import inspect
import threading
from concurrent.futures import Future
from typing import Any, Awaitable, Callable, Optional

_loop: Optional[asyncio.AbstractEventLoop] = None
_lock = threading.Lock()


def loop() -> asyncio.AbstractEventLoop:
    """The asyncio loop Pyzed runs coroutines on (started on first use)."""
    global _loop
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            thread = threading.Thread(target=_loop.run_forever, name="pyzed-asyncio", daemon=True)
            thread.start()
        return _loop


async def _await(awaitable: Awaitable[Any]) -> Any:
    return await awaitable


def spawn(awaitable: Awaitable[Any]) -> Future:
    """Schedules a coroutine on Pyzed's loop and returns a ``concurrent.futures.Future``.

    Use it for fire-and-forget work; to get the result back into the UI, return the
    coroutine from ``update`` (or use ``Command.perform``) instead.
    """
    return asyncio.run_coroutine_threadsafe(_await(awaitable), loop())


def run(awaitable: Awaitable[Any]) -> Any:
    """Runs a coroutine on Pyzed's loop and blocks the calling (non-UI) thread for its result."""
    if _in_loop():
        raise RuntimeError("pyzed._async.run() cannot be called from the asyncio loop itself")
    return spawn(awaitable).result()


def _in_loop() -> bool:
    try:
        return asyncio.get_running_loop() is _loop
    except RuntimeError:
        return False


class _Stop(Exception):
    pass


def drain(value: Any, emit: Callable[[Any], None], *, keep_none: bool = False) -> None:
    """Resolves ``value`` and passes every result to ``emit`` (called from a worker thread).

    - awaitables are awaited on the shared loop (their result is drained again),
    - async generators and generators are iterated, emitting each item,
    - anything else is emitted as is (``None`` is skipped, unless ``keep_none``: then a
      function that returns nothing still reaches ``Command.perform``'s ``then``).
    """
    if inspect.isawaitable(value):
        value = run(value)
    if inspect.isasyncgen(value) or hasattr(value, "__anext__"):
        agen = value
        try:
            while True:
                try:
                    item = run(agen.__anext__())
                except StopAsyncIteration:
                    break
                _emit(item, emit)
        except _Stop:
            if hasattr(agen, "aclose"):
                run(agen.aclose())
        return
    if inspect.isgenerator(value):
        try:
            for item in value:
                _emit(item, emit)
        except _Stop:
            value.close()
        return
    try:
        if value is None and keep_none:
            _emit_none(emit)
        else:
            _emit(value, emit)
    except _Stop:
        pass


def _emit_none(emit: Callable[[Any], None]) -> None:
    try:
        emit(None)
    except RuntimeError as err:  # the app has stopped
        raise _Stop() from err


def _emit(item: Any, emit: Callable[[Any], None]) -> None:
    if item is None:
        return
    if inspect.isawaitable(item):
        item = run(item)
        if item is None:
            return
    try:
        emit(item)
    except RuntimeError as err:  # the app (or the subscription) has stopped
        raise _Stop() from err
