"""Actions: calls that change data (a POST to your API, a save to the database), like Next.js'
server actions with ``useActionState``.

Decorate the function; call it from any event handler. It runs off the UI thread (``async def``
on Pyzed's loop, a plain function in a worker thread), and while it runs ``pending`` is ``True``.
When it ends, ``result`` or ``error`` hold the outcome and the current page's ``load`` runs again
(``refresh=True``), so what it shows is up to date::

    import pyzed as pz

    import api


    @pz.action
    async def add_review(product_id, text):
        await api.post(f"/products/{product_id}/reviews", {"text": text})


    def page(params, data):
        return pz.column([
            reviews(data.reviews),
            ui.button("Sending…" if add_review.pending else "Send",
                      lambda: add_review(params["id"], "Great!"), disabled=add_review.pending),
            ui.label(str(add_review.error)) if add_review.error else None,
        ])

An action is a ``pz.Store``: components that read ``pending``, ``result`` or ``error`` draw again
when they change. ``invalidate=["/products"]`` also drops the cached data of other pages.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, List, Optional, Sequence, Union, overload

from .store import Store

__all__ = ["Action", "action"]


class Action(Store):
    """A function that changes data, with its state: ``pending``, ``result``, ``error`` and ``calls``.

    Calling it starts the function and returns a ``concurrent.futures.Future``; ``run(...)``
    calls it and waits (for tests and scripts). ``reset()`` clears ``result`` and ``error``.
    """

    pending: bool = False
    result: Any = None
    error: Optional[BaseException] = None
    calls: int = 0

    def __init__(self, function: Callable[..., Any], *, refresh: bool = True,
                 invalidate: Union[str, Sequence[str], None] = None,
                 on_done: Optional[Callable[[Any], Any]] = None,
                 on_error: Optional[Callable[[BaseException], Any]] = None) -> None:
        object.__setattr__(self, "_pyzed_function", function)
        object.__setattr__(self, "_pyzed_refresh", refresh)
        object.__setattr__(self, "_pyzed_invalidate", [invalidate] if isinstance(invalidate, str) else
                           list(invalidate or ()))
        object.__setattr__(self, "_pyzed_on_done", on_done)
        object.__setattr__(self, "_pyzed_on_error", on_error)
        object.__setattr__(self, "_pyzed_running", 0)
        super().__init__()
        functools.update_wrapper(self, function)  # type: ignore[arg-type]

    def __repr__(self) -> str:
        name = getattr(self._pyzed_function, "__qualname__", "action")
        state = "pending" if object.__getattribute__(self, "pending") else "idle"
        return f"<Action {name} {state}>"

    def __setattr__(self, name: str, value: Any) -> None:
        # update_wrapper copies __name__, __doc__... next to the fields: not changes of the store
        if name.startswith("__") or name in ("__wrapped__",):
            object.__setattr__(self, name, value)
            return
        super().__setattr__(name, value)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        from . import _async
        from .routing.router import _executor

        object.__setattr__(self, "_pyzed_running", self._pyzed_running + 1)
        self.update(pending=True, calls=self.calls + 1)

        def run() -> Any:
            result = self._pyzed_function(*args, **kwargs)
            if _async._isawaitable(result):
                result = _async.run(result)
            return result

        future = _executor().submit(run)
        future.add_done_callback(self._done)
        return future

    def run(self, *args: Any, timeout: Optional[float] = 30.0, **kwargs: Any) -> Any:
        """Calls the action and waits for it; returns its result or raises its error."""
        return self(*args, **kwargs).result(timeout=timeout)

    def _done(self, future: Any) -> None:
        try:
            result, error = future.result(), None
        except BaseException as err:  # noqa: BLE001 - kept in `error`
            result, error = None, err
        object.__setattr__(self, "_pyzed_running", max(self._pyzed_running - 1, 0))
        if error is None:
            self.update(result=result, error=None, pending=self._pyzed_running > 0)
            self._revalidate()
            if self._pyzed_on_done is not None:
                _deliver(self._pyzed_on_done, result)
        else:
            self.update(error=error, pending=self._pyzed_running > 0)
            if self._pyzed_on_error is not None:
                _deliver(self._pyzed_on_error, error)
            else:
                from .routing.router import _report

                _report(error)

    def _revalidate(self) -> None:
        from .routing import router as _router

        router = _router._current
        if router is None:
            return
        if self._pyzed_invalidate:
            router.invalidate(*self._pyzed_invalidate)
        if self._pyzed_refresh:
            router.refresh()

    def reset(self) -> None:
        """Clears ``result`` and ``error``."""
        self.update(result=None, error=None)


def _deliver(callback: Callable[[Any], Any], value: Any) -> None:
    from . import _core

    try:
        _core.post(lambda: callback(value))
    except RuntimeError:
        callback(value)


@overload
def action(function: Callable[..., Any], *, refresh: bool = True,
           invalidate: Union[str, Sequence[str], None] = None, on_done: Optional[Callable[[Any], Any]] = None,
           on_error: Optional[Callable[[BaseException], Any]] = None) -> Action: ...
@overload
def action(function: None = None, *, refresh: bool = True,
           invalidate: Union[str, Sequence[str], None] = None, on_done: Optional[Callable[[Any], Any]] = None,
           on_error: Optional[Callable[[BaseException], Any]] = None) -> Callable[[Callable[..., Any]], Action]: ...
def action(function: Optional[Callable[..., Any]] = None, *, refresh: bool = True,
           invalidate: Union[str, Sequence[str], None] = None, on_done: Optional[Callable[[Any], Any]] = None,
           on_error: Optional[Callable[[BaseException], Any]] = None) -> Any:
    """Makes ``function`` an :class:`Action` (see ``pyzed.actions``): ``@pz.action`` or
    ``@pz.action(refresh=False, invalidate="/products")``."""
    def wrap(fn: Callable[..., Any]) -> Action:
        return Action(fn, refresh=refresh, invalidate=invalidate, on_done=on_done, on_error=on_error)

    return wrap(function) if function is not None else wrap


def actions_of(value: Any) -> List[Action]:  # pragma: no cover - a helper for tools
    """The actions among ``value``'s attributes (a module, say)."""
    return [v for v in vars(value).values() if isinstance(v, Action)]
