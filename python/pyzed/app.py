"""The application model: state lives in your object, ``update`` changes it, ``view`` draws it."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple, Union

from . import _core
from . import _platform
from . import animation as _animation
from . import component as _component
from . import style as _style
from . import hot_reload as _hot_reload
from . import rendering as _rendering
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
    ``decorations`` (``False`` for no frame at all), ``frame`` (``"custom"`` draws the title bar
    in Pyzed with ``ui.window_frame``, see below), ``transparent``, ``maximized``, ``fullscreen``, ``scale``, ``theme`` (``None``
    uses the app's theme) and ``style`` (a ``pz.Style`` applied to the whole view, on top
    of ``pz.set_style``; ``None`` uses the app's).

    ``icon`` is the window's icon in the title bar and the taskbar: a path to a PNG (or other
    image) or its bytes; ``None`` keeps the system's (or the packaged app's) icon. macOS draws
    the app bundle's icon instead. ``app_id`` names the app to the Linux desktop: it should
    match the app's ``.desktop`` file, which gives Wayland the icon and groups its windows.

    On a phone, ``safe_area`` (on by default) keeps the content clear of the status bar, the
    camera cutout, the navigation bar and the soft keyboard; ``False`` draws under them (place
    things with ``pz.safe_area()``). Android's back button calls ``on_back()``: return ``False``
    (or leave it out) and the app goes to the background, as on any app's first screen.

    ``transition`` animates the window's content when it opens: a window transition
    (``"fade"``, ``"zoom"``, ``"pop"``, ``"slide_up"``, ``"slide_down"``, ``"slide_left"``,
    ``"slide_right"``), a preset or a ``pz.Animation``. ``exit_transition`` plays before it
    closes (a window transition name also gives the matching exit).

    ``frame = "custom"`` replaces the system's frame with one drawn by Pyzed: a title bar
    that moves the window (double click maximizes), the minimize, maximize and close buttons
    of this system, and borders that resize it. ``frame_menus()`` returns menus for its left
    side (``[ui.Menu("File", [...]), ...]``). A platform name (``"macos"``, ``"windows"``,
    ``"gnome"``, ``"ubuntu"``, ``"kde"``) draws that platform's buttons everywhere. Call
    ``ui.window_frame`` in ``view()`` yourself to put more in the bar. ``None`` (the
    default) keeps the system's frame.

    Optional hooks: ``on_open()``, ``on_close()`` (return ``False`` to keep the window
    open), ``on_resize(width, height)``, ``on_key(combo)`` and ``subscriptions()``. Files
    dragged from the system onto the window call ``on_file_hover(path)`` while they are over
    it, ``on_file_drop(path)`` when they are dropped (once per file) and ``on_file_leave()``
    when the drag leaves without dropping (see ``ui.drop_zone``).
    """

    title: Union[str, Any] = "Pyzed"
    size: Tuple[float, float] = (800, 600)
    min_size: Optional[Tuple[float, float]] = None
    max_size: Optional[Tuple[float, float]] = None
    position: Union[str, Tuple[float, float], None] = None
    resizable: bool = True
    decorations: bool = True
    frame: Union[str, bool, None] = None
    transparent: bool = False
    maximized: bool = False
    fullscreen: bool = False
    scale: float = 1.0
    theme: ThemeLike = None
    style: Any = None
    transition: Any = None
    exit_transition: Any = None
    icon: Any = None
    app_id: Optional[str] = None
    safe_area: bool = True

    #: The app that owns this window (set when the window is opened).
    app: Optional["App"] = None
    #: The current size of the window in logical pixels (updated by the runtime).
    window_size: Optional[Tuple[float, float]] = None
    #: Whether the window is maximized (updated by the runtime).
    window_maximized: bool = False
    #: Whether the window has the keyboard focus (updated by the runtime).
    window_focused: bool = True
    #: Where the window is on the screen (its outer top-left corner, in logical pixels), updated
    #: when it opens and moves. ``None`` until known, and always on Wayland.
    window_position: Optional[Tuple[float, float]] = None
    _pyzed_window_open: bool = False

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        if (args or kwargs) and cls.__init__ is object.__init__:
            raise TypeError(f"{cls.__name__}() takes no arguments")
        self = super().__new__(cls)
        # Hot reload runs ``__init__`` again with them on a scratch copy to find new attributes.
        self.__dict__["_pyzed_init"] = (args, kwargs)
        return self

    def view(self) -> _core.Widget:  # pragma: no cover - meant to be overridden
        """Returns the window's root widget; subclasses must override it."""
        raise NotImplementedError(f"{type(self).__name__}.view() must return a widget")

    def update(self, message: Any) -> Any:
        """Handles a message produced in this window (forwards to the app by default)."""
        if self.app is not None and self.app is not self:
            return self.app.update(message)
        return None

    def on_close(self) -> Optional[bool]:
        """Called when the user asks to close the window. Return ``False`` to keep it open."""
        return None

    def on_file_hover(self, path: str) -> Any:
        """A file dragged from the system is over the window: lights up the ``ui.DropZone`` it would land on."""
        from .ui import system

        return system.deliver("hover", path)

    def on_file_drop(self, path: str) -> Any:
        """A file was dropped on the window from the system (once per file): goes to a ``ui.DropZone``."""
        from .ui import system

        return system.deliver("drop", path)

    def on_file_leave(self) -> Any:
        """The files dragged over the window left it without being dropped."""
        from .ui import system

        return system.deliver("leave")

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

    def minimize(self) -> _core.Command:
        """A command that minimizes the window."""
        return _core.Command.minimize_window(self)

    def toggle_maximize(self) -> _core.Command:
        """A command that maximizes the window, or restores it when it is maximized."""
        return _core.Command.toggle_maximize_window(self)

    def frame_menus(self) -> Optional[Sequence[Any]]:
        """The menus on the left of a custom frame's title bar (``frame = "custom"``): a list of ``ui.Menu``."""
        return None

    def resolved_theme(self) -> _theme.Theme:
        """The concrete theme this window uses right now (with its global style's colors and sizes)."""
        dark = getattr(self.app, "system_dark", True) if self.app is not None else True
        if self.theme is None and self.app is not None and self.app is not self:
            return _style.themed(self.app.resolved_theme(), self.style)
        return _style.themed(_theme.resolve(self.theme, dark=dark), self.resolved_style())

    def resolved_style(self) -> Any:
        """The global style of this window: ``pz.set_style`` with its own (or the app's) ``style`` on top."""
        style = self.style
        if style is None and self.app is not None and self.app is not self:
            style = self.app.style
        return _style.Style(_style.global_style(), style)

    # -- hooks used by the native runtime ---------------------------------
    def __pyzed_fresh__(self) -> "Window":
        """A scratch instance of this window's class, made with the arguments it was made with (hot reload)."""
        args, kwargs = self.__dict__.get("_pyzed_init", ((), {}))
        return type(self)(*args, **kwargs)

    def __pyzed_view__(self):
        _hot_reload.note_window(self)
        _hot_reload.check()
        _theme.use(self.resolved_theme())
        _style._viewport = tuple(self.window_size or _style._screen or self.size)
        from .ui import frame as _frame

        with _component.render_pass(self), _frame.drawing(self) as drawing:
            root = self.view()
            if drawing.style is not None and not drawing.drawn:
                root = _frame.window_frame(root, menus=self.frame_menus())
            root = _style.apply_global(root, self.resolved_style())
        return _animation._window_root(self, root)

    def __pyzed_frame__(self) -> Optional[str]:
        from .ui import frame as _frame

        return _frame.resolve(self.frame)

    def __pyzed_exit__(self) -> float:
        return _animation._window_exit(self)

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
        ``on_key_up(key)``     receives key releases by name (``"left"``, ``"space"``).
        ``on_file_drop(path)`` receives each file dropped on the window from the system
                               (also ``on_file_hover(path)`` and ``on_file_leave()``).
        ``subscriptions()``    returns timers, streams and frame callbacks
                               (``pz.every``, ``pz.listen``, ``pz.frames``).

    ``theme`` may be a ``Theme``, a theme name (``"Ayu Dark"``) or
    ``themes.auto(light, dark)`` to follow the operating system's appearance.

    ``splash`` shows a window before the main one: a ``pz.Splash`` (an image without a
    frame, centered on the screen) or any ``Window``. It stays up for its ``duration`` in
    seconds, then the main window opens, ``on_start`` runs and the splash closes.

    ``rendering`` (a ``pz.Rendering``) picks the GPU or CPU renderer, the graphics API,
    the GPU and vsync; ``None`` reads ``[tool.pyzed.rendering]`` of the project's
    ``pyproject.toml`` (see ``pyzed.rendering``).
    """

    size: Tuple[float, float] = (1280, 800)
    font_size: float = 14
    theme: ThemeLike = _theme.PYZED_DARK
    #: Whether the OS is in dark mode (updated by the runtime).
    system_dark: bool = True
    #: Tab and Shift+Tab move the keyboard focus between the fields of the window
    #: (``on_key`` sees the key first; returning something from it keeps the focus).
    tab_focus: bool = True
    #: A window shown while the app starts (see ``pz.Splash``); ``None`` for none.
    splash: Optional[Window] = None
    #: How the windows are drawn (GPU or CPU...); ``None`` follows the project's ``pyproject.toml``.
    rendering: Optional[_rendering.Rendering] = None

    def subscriptions(self) -> List[Any]:
        """Timers and streams that should run right now (re-evaluated after every update)."""
        return []

    # -- conveniences -------------------------------------------------------
    def run(self, *, reload: Optional[bool] = None, watch: Sequence[Any] = ()) -> None:
        """Opens the window and blocks until the app exits.

        ``reload=True`` turns on hot reload (see ``pyzed.hot_reload``): saving a file of
        your project updates the running window and keeps its state. ``watch`` adds
        folders or files to the ones watched. When ``reload`` is ``None`` the
        ``PYZED_RELOAD`` environment variable decides (``pyzed dev`` sets it).
        """
        run(self, reload=reload, watch=watch)

    def screenshot(self, path, *, size=None, scale: float = 2.0, wait: float = 0.1) -> None:
        """Renders the current state off-screen (no GPU or display needed) into a PNG."""
        _core.screenshot(self, str(path), size=size, scale=scale, wait=wait)


def safe_area() -> Tuple[float, float, float, float]:
    """The parts of the screen the system draws over, in logical pixels: ``(top, right, bottom, left)``.

    On Android: the status and navigation bars, the camera cutout and the soft keyboard while it
    is open. Zeros on a desktop. Windows keep clear of them unless ``safe_area = False``.
    """
    return _core.safe_area()


def run(app, *, reload: Optional[bool] = None, watch: Sequence[Any] = ()) -> None:
    """Runs an ``App`` instance (or class, which is instantiated with no arguments).

    ``reload=True`` turns on hot reload: the window picks up your code changes each time
    you save a file, keeping the app's state. ``watch`` adds folders or files to watch.
    ``None`` defers to the ``PYZED_RELOAD`` environment variable (set by ``pyzed dev``).
    """
    if _hot_reload.is_reloading():
        return  # the main script is being re-executed by a reload; the app already runs
    (getattr(app, "rendering", None) or _rendering.find()).apply()
    if _platform.is_wsl():  # under WSL the window opens as a Windows program (see pyzed._wsl_windows)
        from . import _wsl_windows

        code = _wsl_windows.handoff_script()
        if code is not None:
            raise SystemExit(code)
    if isinstance(app, type):
        app = app()
    if reload is None:
        reload = _hot_reload.enabled_by_env()
    reloader = _hot_reload.enable(app, [*watch, *_hot_reload.watched_by_env()]) if reload else None
    _platform.prepare()
    _animation._follow_system(background=True)
    try:
        _core.run(app)
    finally:
        if reloader is not None:
            reloader.stop()


def screenshot(app, path, *, size=None, scale: float = 2.0, wait: float = 0.1) -> None:
    """Renders ``app`` (instance or class) off-screen into a PNG file."""
    if isinstance(app, type):
        app = app()
    _core.screenshot(app, str(path), size=size, scale=scale, wait=wait)
