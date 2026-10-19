"""Memoization of view subtrees: build a part of the UI once and reuse it while its inputs
don't change.

``view()`` runs after every message, so a big sidebar, a long settings form or a chart
legend is rebuilt in Python even when nothing in it changed. ``@pz.memo`` caches what a
function returns by its arguments, so the next ``view()`` reuses the same widget tree::

    @pz.memo
    def sidebar(files: tuple, selected: str):
        return pz.column([pz.ui.list_item(f, selected=f == selected) for f in files])

    def view(self):
        return pz.row([sidebar(tuple(self.files), self.selected), self.editor()])

Pass everything the subtree depends on as arguments: a memoized function that reads
``self`` or a global sees their old values until its arguments change. Callbacks inside a
cached subtree are cached too, so they should take what they need from arguments
(``lambda: self.open(name)``), not from state captured when the subtree was built.

Arguments are compared by value when they can be hashed (numbers, strings, tuples,
frozen dataclasses...) and lists, dicts and sets are compared by their contents. Any other
object is compared by identity, so mutating it in place doesn't refresh the cache: replace
it, or pass a version number next to it. The current theme and language are always part
of the key, so switching them rebuilds every memoized subtree.
"""

from __future__ import annotations

import functools
from collections import OrderedDict
from typing import Any, Callable, Dict, Hashable, Optional, Tuple, TypeVar, overload

from . import i18n, theme as _theme

__all__ = ["memo", "clear_memos", "memo_stats"]

F = TypeVar("F", bound=Callable[..., Any])

_caches: Dict[Callable[..., Any], "OrderedDict[Hashable, Any]"] = {}
_stats = {"hits": 0, "misses": 0}


class _Identity:
    """A key part that compares an unhashable object by identity (and keeps it alive)."""

    __slots__ = ("obj",)

    def __init__(self, obj: Any):
        self.obj = obj

    def __hash__(self) -> int:
        return id(self.obj)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Identity) and other.obj is self.obj


def _freeze(value: Any) -> Hashable:
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(_freeze(v) for v in value))
    if isinstance(value, dict):
        return ("dict", tuple((_freeze(k), _freeze(v)) for k, v in value.items()))
    if isinstance(value, (set, frozenset)):
        return ("set", frozenset(_freeze(v) for v in value))
    try:
        hash(value)
    except TypeError:
        return _Identity(value)
    return value


def _key(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Hashable:
    return (
        id(_theme.current()),
        i18n.language(),
        _freeze(args),
        tuple(sorted((k, _freeze(v)) for k, v in kwargs.items())),
    )


@overload
def memo(function: F) -> F: ...
@overload
def memo(function: None = None, *, maxsize: int = 64) -> Callable[[F], F]: ...


def memo(function: Optional[F] = None, *, maxsize: int = 64) -> Any:
    """Caches what ``function`` returns by its arguments (a decorator).

    ``@pz.memo`` or ``@pz.memo(maxsize=256)``. The last ``maxsize`` results are kept, so a
    function called once per row (``row(item)``) can cache a whole visible page. Methods
    work too: ``self`` is compared by identity. ``function.cache_clear()`` empties the
    cache of one function; ``pz.clear_memos()`` empties them all.
    """
    if function is None:
        return lambda f: memo(f, maxsize=maxsize)
    if maxsize < 1:
        raise ValueError("maxsize must be at least 1")

    cache: "OrderedDict[Hashable, Any]" = OrderedDict()

    @functools.wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        key = _key(args, kwargs)
        try:
            result = cache[key]
        except KeyError:
            _stats["misses"] += 1
            result = cache[key] = function(*args, **kwargs)
            if len(cache) > maxsize:
                cache.popitem(last=False)
            return result
        _stats["hits"] += 1
        cache.move_to_end(key)
        return result

    setattr(wrapper, "cache_clear", cache.clear)
    _caches[wrapper] = cache
    return wrapper


def clear_memos() -> None:
    """Empties the cache of every ``@pz.memo`` function (for example after reloading data
    that memoized functions read without taking it as an argument)."""
    for cache in _caches.values():
        cache.clear()


def memo_stats() -> Dict[str, int]:
    """How many calls of memoized functions were answered from the cache (``hits``) and
    how many built their result (``misses``), since the program started. Handy to check
    that a subtree really is reused."""
    return dict(_stats)
