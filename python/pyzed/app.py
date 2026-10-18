"""The application model: state lives in your object, ``update`` changes it, ``view`` draws it."""

from __future__ import annotations

from typing import Any, Optional, Tuple, Union

from . import _core
from . import theme as _theme


class App:
    """Base class for Pyzed applications (the Elm architecture, like Iced).

    Override ``view()`` and, if you use message values, ``update(message)``.
    Widgets accept either a message (any Python value, sent to ``update``) or a
    plain callable such as ``self.increment``, which is called directly.

    Optional hooks:
        ``on_start()``      runs once; may return a ``Command``.
        ``on_key(combo)``   receives unhandled key presses as Zed-style strings
                            like ``"ctrl-shift-p"`` or ``"escape"``.
    """

    title: Union[str, Any] = "Pyzed"
    size: Tuple[float, float] = (1280, 800)
    min_size: Optional[Tuple[float, float]] = None
    resizable: bool = True
    decorations: bool = True
    scale: float = 1.0
    font_size: float = 14
    theme: _theme.Theme = _theme.ONE_DARK

    def update(self, message: Any) -> Any:  # pragma: no cover - meant to be overridden
        return None

    def view(self) -> _core.Widget:  # pragma: no cover - meant to be overridden
        raise NotImplementedError("App.view() must return a widget")

    # -- hooks used by the native runtime ---------------------------------
    def __pyzed_view__(self):
        _theme.use(self.theme)
        return self.view()

    def __pyzed_palette__(self):
        return self.theme.palette()

    # -- conveniences -------------------------------------------------------
    def run(self) -> None:
        """Opens the window and blocks until it is closed."""
        _core.run(self)

    def screenshot(self, path, *, size=None, scale: float = 2.0, wait: float = 0.1) -> None:
        """Renders the current state off-screen (no GPU or display needed) into a PNG."""
        _core.screenshot(self, str(path), size=size, scale=scale, wait=wait)


def run(app) -> None:
    """Runs an ``App`` instance (or class, which is instantiated with no arguments)."""
    if isinstance(app, type):
        app = app()
    _core.run(app)


def screenshot(app, path, *, size=None, scale: float = 2.0, wait: float = 0.1) -> None:
    if isinstance(app, type):
        app = app()
    _core.screenshot(app, str(path), size=size, scale=scale, wait=wait)
