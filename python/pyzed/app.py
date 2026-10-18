"""The application model: state lives in your object, ``update`` changes it, ``view`` draws it."""

from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union

from . import _core
from . import theme as _theme

ThemeLike = Union[_theme.Theme, _theme.AutoTheme, str, None]


class Window:
    """A window with its own ``view()``, title, size and (optionally) theme.

    The main window is your ``App``; open more with ``Command.open_window``::

        class Settings(pz.Window):
            title = "Settings"
            size = (480, 360)

            def view(self):
                return ui.button("Close", self.close)

        class Main(pz.App):
            def open_settings(self):
                return pz.Command.open_window(Settings())

    Messages produced inside a window go to its ``update()``, which forwards them to
    the app by default, so callbacks such as ``self.app.save`` work out of the box.
    ``self.app`` is set when the window is opened (unless you set it yourself).

    Window options (class or instance attributes): ``title`` (str or callable), ``size``,
    ``min_size``, ``max_size``, ``position`` (``"center"`` or ``(x, y)``), ``resizable``,
    ``decorations`` (``False`` for a custom title bar, see ``Command.drag_window``),
    ``transparent``, ``maximized``, ``fullscreen``, ``scale`` and ``theme`` (``None``
    uses the app's theme).

    Optional hooks: ``on_open()``, ``on_close()`` (return ``False`` to keep the window
    open), ``on_resize(width, height)``, ``on_key(combo)`` and ``subscriptions()``.
    """

    title: Union[str, Any] = "Pyzed"
    size: Tuple[float, float] = (800, 600)
    min_size: Optional[Tuple[float, float]] = None
    max_size: Optional[Tuple[float, float]] = None
    position: Union[str, Tuple[float, float], None] = None
    resizable: bool = True
    decorations: bool = True
    transparent: bool = False
    maximized: bool = False
    fullscreen: bool = False
    scale: float = 1.0
    theme: ThemeLike = None

    #: The app that owns this window (set when the window is opened).
    app: Optional["App"] = None
    #: The current size of the window in logical pixels (updated by the runtime).
    window_size: Optional[Tuple[float, float]] = None
    _pyzed_window_open: bool = False

    def view(self) -> _core.Widget:  # pragma: no cover - meant to be overridden
        raise NotImplementedError(f"{type(self).__name__}.view() must return a widget")

    def update(self, message: Any) -> Any:
        """Handles a message produced in this window (forwards to the app by default)."""
        if self.app is not None and self.app is not self:
            return self.app.update(message)
        return None

    def on_close(self) -> Optional[bool]:
        """Called when the user asks to close the window. Return ``False`` to keep it open."""
        return None

    # -- conveniences -------------------------------------------------------
    @property
    def is_open(self) -> bool:
        """Whether the window is currently open."""
        return bool(self._pyzed_window_open)

    def open(self) -> _core.Command:
        """A command that opens this window: ``return settings.open()``."""
        return _core.Command.open_window(self)

    def close(self) -> _core.Command:
        """A command that closes this window: ``on_press=self.close``."""
        return _core.Command.close_window(self)

    def drag(self) -> _core.Command:
        """A command that starts moving the window (for custom title bars)."""
        return _core.Command.drag_window(self)

    def resolved_theme(self) -> _theme.Theme:
        """The concrete theme this window uses right now."""
        dark = getattr(self.app, "system_dark", True) if self.app is not None else True
        if self.theme is None and self.app is not None and self.app is not self:
            return self.app.resolved_theme()
        return _theme.resolve(self.theme, dark=dark)

    # -- hooks used by the native runtime ---------------------------------
    def __pyzed_view__(self):
        _theme.use(self.resolved_theme())
        return self.view()

    def __pyzed_palette__(self):
        return self.resolved_theme().palette()


class App(Window):
    """Base class for Pyzed applications (the Elm architecture, like Iced).

    Override ``view()`` and, if you use message values, ``update(message)``.
    Widgets accept either a message (any Python value, sent to ``update``) or a
    plain callable such as ``self.increment``, which is called directly. Callbacks and
    ``update`` may return a ``Command``, a list of commands, a coroutine (``async def``),
    a generator or an async generator; values they produce are sent back to ``update``.

    Optional hooks:
        ``on_start()``         runs once; may return a ``Command`` or a coroutine.
        ``on_key(combo)``      receives key presses as Zed-style strings like
                               ``"ctrl-shift-p"`` or ``"escape"``.
        ``subscriptions()``    returns timers and streams (``pz.every``, ``pz.listen``).

    ``theme`` may be a ``Theme``, a theme name (``"Ayu Dark"``) or
    ``themes.auto(light, dark)`` to follow the operating system's appearance.
    """

    size: Tuple[float, float] = (1280, 800)
    font_size: float = 14
    theme: ThemeLike = _theme.ONE_DARK
    #: Whether the OS is in dark mode (updated by the runtime).
    system_dark: bool = True

    def subscriptions(self) -> List[Any]:
        """Timers and streams that should run right now (re-evaluated after every update)."""
        return []

    # -- conveniences -------------------------------------------------------
    def run(self) -> None:
        """Opens the window and blocks until the app exits."""
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
    """Renders ``app`` (instance or class) off-screen into a PNG file."""
    if isinstance(app, type):
        app = app()
    _core.screenshot(app, str(path), size=size, scale=scale, wait=wait)
