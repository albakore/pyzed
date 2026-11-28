"""Global state: a ``pz.Store`` holds the values many pages, components and windows share.

Write a class with its fields, make one instance in a module and use it anywhere::

    # state.py
    import pyzed as pz


    class Cart(pz.Store):
        items: list = []                   # each instance gets its own copy of the defaults
        coupon: str = ""

        @property
        def total(self):                   # derived values are plain properties
            return sum(item.price for item in self.items)

        def add(self, product):            # changes are plain methods
            self.items = [*self.items, product]


    cart = Cart()

    # app/(shop)/products/[id]/page.py
    from state import cart

    def page(data):
        return ui.button(f"Add to cart ({len(cart.items)})", lambda: cart.add(data))

Every component that read the store draws again when it changes, and only those: Pyzed notes
what each ``render()`` read. A change made on another thread (a ``load``, a ``pz.action``, a
worker) redraws the window too. ``persist = "cart"`` keeps the values between runs.
"""

from __future__ import annotations

import copy
import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Optional

from . import _core
from . import component as _component

__all__ = ["Store"]


def _redraw() -> None:
    try:
        _core.post(lambda: None)
    except RuntimeError:
        pass  # no app running: the next view() shows it


class Store:
    """Values shared by the whole app (see ``pyzed.store``).

    Fields are annotated class attributes with their defaults; ``Cart(items=[...])`` sets some.
    ``subscribe(callback)`` calls ``callback(store)`` after each change, ``batch()`` groups several
    changes into one, ``reset()`` goes back to the defaults and ``to_dict()`` gives the values.
    Changing a list or dict in place (``cart.items.append(x)``) is seen by the next drawing; call
    ``changed()`` after it so subscribers (and ``persist``) hear about it too.
    """

    #: A name to keep the values between runs, as JSON in Pyzed's per-user settings folder.
    persist: ClassVar[Optional[str]] = None
    __fields__: ClassVar[Dict[str, Any]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        fields: Dict[str, Any] = {}
        for klass in reversed(cls.__mro__):
            own = _component._own_annotations(klass) if klass is not object else {}
            for name, annotation in own.items():
                if name.startswith("_") or _component._is_classvar(annotation):
                    continue
                fields[name] = klass.__dict__.get(name, None)
        cls.__fields__ = fields

    def __init__(self, **values: Any) -> None:
        unknown = [k for k in values if k not in type(self).__fields__]
        if unknown:
            raise TypeError(f"{type(self).__name__} has no field {', '.join(unknown)}; "
                            f"its fields are {', '.join(type(self).__fields__) or 'none'}")
        object.__setattr__(self, "_pyzed_listeners", [])
        object.__setattr__(self, "_pyzed_batch", 0)
        object.__setattr__(self, "_pyzed_dirty", False)
        object.__setattr__(self, "_pyzed_name", f"\x00store:{id(self)}")
        object.__setattr__(self, "_pyzed_lock", threading.RLock())
        for name, default in type(self).__fields__.items():
            object.__setattr__(self, name, copy.deepcopy(default))
        if self.persist:
            for name, value in self._pyzed_saved().items():
                if name in type(self).__fields__:
                    object.__setattr__(self, name, value)
        for name, value in values.items():
            object.__setattr__(self, name, value)
        self.setup()

    def setup(self) -> None:
        """Runs once the values are set: override it to start something (a connection, a timer)."""

    def __repr__(self) -> str:
        values = ", ".join(f"{k}={v!r}" for k, v in self.to_dict().items())
        return f"{type(self).__name__}({values})"

    # -- reading: components note what they read -----------------------------------------------
    def __getattribute__(self, name: str) -> Any:
        if name[0] != "_" and _component._reads:
            _component._note_source(object.__getattribute__(self, "_pyzed_name"), self)
        return object.__getattribute__(self, name)

    # -- changing --------------------------------------------------------------------------------
    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_pyzed"):
            object.__setattr__(self, name, value)
            return
        cls_attr = getattr(type(self), name, None)
        if isinstance(cls_attr, property):
            if cls_attr.fset is None:
                raise AttributeError(f"{type(self).__name__}.{name} is computed from other fields: set those")
            cls_attr.fset(self, value)
            return
        object.__setattr__(self, name, value)
        self.changed()

    def update(self, **values: Any) -> None:
        """Sets several fields at once: subscribers hear about it once."""
        with self.batch():
            for name, value in values.items():
                setattr(self, name, value)

    def changed(self) -> None:
        """Tells subscribers (and ``persist``) that the store changed; setting a field calls it for you."""
        if self._pyzed_batch:
            object.__setattr__(self, "_pyzed_dirty", True)
            return
        if self.persist:
            self.save()
        for listener in list(self._pyzed_listeners):
            listener(self)
        if threading.current_thread() is not threading.main_thread():
            _redraw()

    @contextmanager
    def batch(self) -> Iterator["Store"]:
        """Groups changes: ``with cart.batch(): cart.items = []; cart.coupon = ""``."""
        with self._pyzed_lock:
            object.__setattr__(self, "_pyzed_batch", self._pyzed_batch + 1)
        try:
            yield self
        finally:
            with self._pyzed_lock:
                object.__setattr__(self, "_pyzed_batch", self._pyzed_batch - 1)
                done = self._pyzed_batch == 0 and self._pyzed_dirty
                if done:
                    object.__setattr__(self, "_pyzed_dirty", False)
            if done:
                self.changed()

    def subscribe(self, callback: Callable[["Store"], Any]) -> Callable[[], None]:
        """Calls ``callback(store)`` after each change; returns a function that stops it."""
        self._pyzed_listeners.append(callback)
        return lambda: self._pyzed_listeners.remove(callback) if callback in self._pyzed_listeners else None

    def reset(self) -> None:
        """Puts every field back to its default."""
        with self.batch():
            for name, default in type(self).__fields__.items():
                setattr(self, name, copy.deepcopy(default))

    def to_dict(self) -> Dict[str, Any]:
        """The fields and their values."""
        return {name: object.__getattribute__(self, name) for name in type(self).__fields__}

    # -- persist ---------------------------------------------------------------------------------
    @property
    def path(self) -> Optional[Path]:
        """The file ``persist`` keeps the values in (``None`` without ``persist``)."""
        if not self.persist:
            return None
        from .project import config_dir

        name = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in str(self.persist))
        return config_dir() / "settings" / f"{name}.store.json"

    def _pyzed_saved(self) -> Dict[str, Any]:
        path = self.path
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path is not None else {}
        except (OSError, ValueError):
            data = {}
        return data if isinstance(data, dict) else {}

    def save(self) -> None:
        """Writes the values to ``path`` (``persist`` does it after every change). Values JSON
        can't hold are left out."""
        path = self.path
        if path is None:
            return
        values: Dict[str, Any] = {}
        for name, value in self.to_dict().items():
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                continue
            values[name] = value
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass


def stores_of(value: Any) -> List[Store]:  # pragma: no cover - a helper for tools
    """The stores among ``value``'s attributes (a module, say)."""
    return [v for v in vars(value).values() if isinstance(v, Store)]
