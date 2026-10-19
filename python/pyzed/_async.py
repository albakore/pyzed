"""Async support: one asyncio event loop, running in a background thread, shared by the app.

Coroutines returned from ``update`` (or passed to ``Command.perform``) run on this loop,
so libraries that need a single loop (aiohttp sessions, websockets...) just work.
"""

from __future__ import annotations

import sys
import threading
import types
from collections.abc import Awaitable as _Awaitable
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

if TYPE_CHECKING:
    import asyncio
    from concurrent.futures import Future

# asyncio and inspect are imported on first use: together they are a third of the time
# ``import pyzed`` would take otherwise, and many apps never run a coroutine.
_loop: Optional["asyncio.AbstractEventLoop"] = None
_lock = threading.Lock()


def _isawaitable(value: Any) -> bool:
    """Same as ``inspect``'s ``isawaitable``, without importing ``inspect``."""
    if isinstance(value, types.GeneratorType):
        return bool(value.gi_code.co_flags & 0x100)  # CO_ITERABLE_COROUTINE
    return isinstance(value, _Awaitable)


def loop() -> "asyncio.AbstractEventLoop":
    """The asyncio loop Pyzed runs coroutines on (started on first use)."""
    global _loop
    import asyncio

    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            thread = threading.Thread(target=_loop.run_forever, name="pyzed-asyncio", daemon=True)
            thread.start()
        return _loop


async def _await(awaitable: Awaitable[Any]) -> Any:
    return await awaitable


def spawn(awaitable: Awaitable[Any]) -> "Future":
    """Schedules a coroutine on Pyzed's loop and returns a ``concurrent.futures.Future``.

    Use it for fire-and-forget work; to get the result back into the UI, return the
    coroutine from ``update`` (or use ``Command.perform``) instead.
    """
    import asyncio

    return asyncio.run_coroutine_threadsafe(_await(awaitable), loop())


def run(awaitable: Awaitable[Any]) -> Any:
    """Runs a coroutine on Pyzed's loop and blocks the calling (non-UI) thread for its result."""
    if _in_loop():
        raise RuntimeError("pyzed._async.run() cannot be called from the asyncio loop itself")
    return spawn(awaitable).result()


def _in_loop() -> bool:
    asyncio = sys.modules.get("asyncio")
    if asyncio is None or _loop is None:
        return False
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
    if _isawaitable(value):
        value = run(value)
    if isinstance(value, types.AsyncGeneratorType) or hasattr(value, "__anext__"):
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
    if isinstance(value, types.GeneratorType):
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
    if _isawaitable(item):
        item = run(item)
        if item is None:
            return
    try:
        emit(item)
    except RuntimeError as err:  # the app (or the subscription) has stopped
        raise _Stop() from err
