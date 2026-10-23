"""Work off the UI thread: ``@pz.background`` turns a function into a command that runs elsewhere.

The UI thread draws the windows, so slow work there freezes them. Decorate the slow function
and return its call from a callback; it runs on a worker thread (``async def`` functions on
Pyzed's asyncio loop) and its result goes to ``then``::

    class Search(pz.App):
        def typed(self, text):
            self.query = text
            return self.search(text)

        @pz.background(then="show", latest=True)
        def search(self, text):
            return database.find(text)          # on a worker thread: don't change self here

        def show(self, rows):                    # back on the UI thread
            self.rows = rows

``latest=True`` delivers only the newest call's result: typing fast starts many searches, and
the screen never shows an older one after a newer one. A generator yields progress: ``then``
gets each value.

Python runs one thread at a time, so CPU-heavy pure Python (no NumPy, no I/O) still slows the
UI from a thread. ``process=True`` runs it in another process instead, with its own Python:
the function and its arguments must be picklable (a function at the top of a module, plain
data), and it cannot be a generator.
"""

from __future__ import annotations

import functools
import itertools
import threading
from typing import Any, Callable, Optional, Union

__all__ = ["background", "shutdown"]

_pool = None
_pool_lock = threading.Lock()


def _processes() -> Any:
    """The process pool of ``process=True`` (started on first use, with ``spawn`` everywhere so
    the workers never inherit the UI's threads)."""
    global _pool
    import concurrent.futures
    import multiprocessing

    with _pool_lock:
        if _pool is None:
            _pool = concurrent.futures.ProcessPoolExecutor(mp_context=multiprocessing.get_context("spawn"))
        return _pool


def shutdown() -> None:
    """Stops the worker processes of ``process=True`` (Pyzed does it when the app exits)."""
    global _pool
    with _pool_lock:
        pool, _pool = _pool, None
    if pool is not None:
        pool.shutdown(wait=False, cancel_futures=True)


def _run(module: str, qualname: str, args: Any, kwargs: Any) -> Any:
    """Calls the function a ``process=True`` command names, in the worker process. It goes by name
    because the module's attribute is the decorated function, which pickle cannot send."""
    import importlib
    import sys

    target: Any = sys.modules.get(module) or (sys.modules.get("__mp_main__") if module == "__main__" else None)
    if target is None:
        target = importlib.import_module(module)
    for part in qualname.split("."):
        target = getattr(target, part)
    target = getattr(target, "__wrapped__", target) if getattr(target, "__pyzed_background__", False) else target
    return target(*args, **kwargs)


def background(function: Optional[Callable[..., Any]] = None, *, then: Union[str, Callable[..., Any], None] = None,
               latest: bool = False, process: bool = False) -> Any:
    """Makes ``function`` return a command that runs it off the UI thread (see ``pyzed.workers``).

    ``then`` receives the result on the UI thread: a callable, or the name of a method of the
    object the function is a method of (``then="show"``); without it the result goes to
    ``update`` as a message. ``latest`` drops the results of calls a newer call replaced.
    ``process`` runs it in a worker process (picklable function and arguments).
    """

    def wrap(func: Callable[..., Any]) -> Callable[..., Any]:
        calls = itertools.count(1)
        newest = [0]

        @functools.wraps(func)
        def start(*args: Any, **kwargs: Any) -> Any:
            from . import _core

            call = next(calls)
            newest[0] = call
            receiver = then
            if isinstance(then, str):
                receiver = getattr(args[0], then, None) if args else None
                if not callable(receiver):
                    raise TypeError(f"then={then!r} names a method of the object {func.__qualname__} "
                                    "is a method of; pass a callable for a plain function")

            if process:
                def work() -> Any:
                    job = _processes().submit(_run, func.__module__, func.__qualname__, args, kwargs)
                    return job.result()
            else:
                def work() -> Any:
                    return func(*args, **kwargs)

            if not latest:
                return _core.Command.perform(work, receiver)

            def deliver(result: Any) -> Any:
                if newest[0] != call:
                    return _core.UNCHANGED  # a newer call replaced this one
                return receiver(result) if receiver is not None else result

            return _core.Command.perform(work, deliver)

        start.__pyzed_background__ = True  # type: ignore[attr-defined]
        return start

    return wrap(function) if function is not None else wrap
