"""The application model: state lives in your object, ``update`` changes it, ``view`` draws it."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple, Union

from . import _core
from . import _platform
from . import animation as _animation
from . import component as _component
from . import devices as _devices
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

    ``isolated = True`` promises that only the window's own messages change what it shows (its
    callbacks, commands and subscriptions). After a message from another window, a timer of the
    app or anything else, Pyzed then skips its ``view()``, keeps its layout and does not redraw
    it, so many open windows cost what the busy one costs. Theme, language, style and code
    changes still redraw it, and so does ``pz.post`` (async results, worker threads). Call
    ``refresh()`` when it shows something that changed outside it.

    Screens and kiosks: ``monitor`` (an index of ``pz.monitors()``) opens the window on that
    screen, centered or fullscreen. ``fullscreen = "exclusive"`` takes the screen over with its
    own video mode (lower latency on Windows and X11; Wayland keeps a borderless window).
    ``always_on_top`` keeps it above the others (``always_on_bottom`` below); ``closable`` and
    ``minimizable`` remove those buttons; ``skip_taskbar`` leaves it out of the taskbar
    (Windows); ``hide_cursor`` hides the pointer over it (touch panels). ``kiosk = True`` puts it
    all together for a car display, a point of sale or an info panel: fullscreen, no frame,
    above the others, without buttons or taskbar entry, and the user cannot close it (only
    ``Command.close_window`` or ``Command.exit`` do).

    ``design_size = (1920, 720)`` lays the view out for that size and scales it to the real
    window, like Godot's stretch modes: ``stretch = "expand"`` (the default) lets it grow into
    the space left, ``"fit"`` keeps the design's size centered with bars around it. The device
    profile (``pz.device()``, see ``pyzed.devices``) fills in the options a window leaves at
    their defaults: a kiosk on a ``kiosk`` device, no pointer on a TV...

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
    fullscreen: Union[bool, str] = False
    monitor: Optional[int] = None
    always_on_top: bool = False
    always_on_bottom: bool = False
    closable: bool = True
    minimizable: bool = True
    skip_taskbar: bool = False
    hide_cursor: bool = False
    kiosk: bool = False
    scale: float = 1.0
    design_size: Optional[Tuple[float, float]] = None
    stretch: str = "expand"
    _pyzed_size_scale: float = 1.0
    theme: ThemeLike = None
    style: Any = None
    transition: Any = None
    exit_transition: Any = None
    icon: Any = None
    app_id: Optional[str] = None
    safe_area: bool = True
    isolated: bool = False

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

    def set_fullscreen(self, fullscreen: bool = True, monitor: Optional[int] = None,
                       exclusive: bool = False) -> _core.Command:
        """A command that makes the window fullscreen (on ``monitor``, an index of
        ``pz.monitors()``; ``exclusive`` takes the screen over), or windowed with ``False``."""
        return _core.Command.set_fullscreen(fullscreen, self, monitor, exclusive)

    def set_window_level(self, level: str) -> _core.Command:
        """A command that keeps the window above (``"top"``) or below (``"bottom"``) the others,
        or back to ``"normal"``."""
        return _core.Command.set_window_level(level, self)

    def refresh(self) -> None:
        """Draws an ``isolated`` window again on the next update (safe from any thread); other
        windows are drawn after every update anyway."""
        _core.refresh_window(self)

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

    def __pyzed_device__(self) -> None:
        _devices._apply_window(self)

    def _pyzed_design(self) -> Optional[Tuple[float, float]]:
        design = self.design_size
        if not design or self.stretch == "none":
            return None
        return (float(design[0]), float(design[1]))

    def __pyzed_scale__(self) -> float:
        scale = float(self.scale or 1.0)
        design = self._pyzed_design()
        if design is None:
            return scale
        if not self.window_size:
            return 1.0  # opens at ``size`` as it is, then fits the design to it
        # the window's size in the system's logical pixels, before any scale of ours
        base = float(self._pyzed_size_scale or 1.0)
        width, height = self.window_size[0] * base, self.window_size[1] * base
        return max(0.05, scale * min(width / design[0], height / design[1]))

    def __pyzed_view__(self):
        _hot_reload.note_window(self)
        _hot_reload.check()
        _theme.use(self.resolved_theme())
        design = self._pyzed_design()
        if design is not None and self.window_size:
            ratio = float(self._pyzed_size_scale or 1.0) / self.__pyzed_scale__()
            _style._viewport = (self.window_size[0] * ratio, self.window_size[1] * ratio)
        else:
            _style._viewport = tuple(self.window_size or _style._screen or self.size)
        from .ui import frame as _frame

        with _component.render_pass(self), _frame.drawing(self) as drawing:
            root = self.view()
            if drawing.style is not None and not drawing.drawn:
                root = _frame.window_frame(root, menus=self.frame_menus())
            root = _style.apply_global(root, self.resolved_style())
        if design is not None and self.stretch == "fit":
            root = _core.container(_core.container(root, width=design[0], height=design[1], clip=True),
                                   width="fill", height="fill", center=True)
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
    theme: ThemeLike = _theme.ONE_DARK
    #: Whether the OS is in dark mode (updated by the runtime).
    system_dark: bool = True
    #: Tab and Shift+Tab move the keyboard focus between the fields of the window
    #: (``on_key`` sees the key first; returning something from it keeps the focus).
    tab_focus: bool = True
    #: The arrow keys no control used move the focus to the nearest control that way (TV remotes,
    #: rotary knobs); ``on_key`` sees them first. The ``tv`` and ``automotive`` devices turn it on.
    arrow_focus: bool = False
    #: The device profile: a name (``"touch"``, ``"automotive"``, ``"mobile"``, ``"kiosk"``, ``"tv"``...)
    #: or a ``pz.Device``; ``None`` follows ``PYZED_DEVICE``, ``pyproject.toml`` or the system.
    device: Any = None
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


def renderer_info() -> Optional[Tuple[str, str]]:
    """The GPU and the graphics API drawing the windows, like ``("NVIDIA GeForce RTX 4060", "Vulkan")``,
    or ``("CPU", "tiny-skia")`` with the CPU renderer; ``None`` until the first window is open."""
    return _core.renderer_info()


@dataclass(frozen=True)
class Monitor:
    """A screen: its ``index`` (for ``Window.monitor`` and ``Command.set_fullscreen``), ``name``,
    top left corner ``x``, ``y`` and size ``width``, ``height`` on the desktop in logical pixels,
    ``scale`` (2.0 on a HiDPI screen), ``refresh_rate`` in hertz (``None`` if unknown) and
    whether it is the ``primary`` one."""

    index: int
    name: Optional[str]
    x: float
    y: float
    width: float
    height: float
    scale: float
    refresh_rate: Optional[float]
    primary: bool

    @property
    def size(self) -> Tuple[float, float]:
        """``(width, height)`` in logical pixels."""
        return (self.width, self.height)

    @property
    def position(self) -> Tuple[float, float]:
        """``(x, y)`` of its top left corner on the desktop."""
        return (self.x, self.y)


def _monitors(items: List[dict]) -> List[Monitor]:
    return [Monitor(**item) for item in items]


def monitors() -> List[Monitor]:
    """The screens connected when the first window opened (refreshed each time a window opens
    and by ``Command.list_monitors``); empty before that. ``pz.monitors()[1].index`` goes in
    ``Window.monitor``."""
    return _monitors(_core.monitors())


def _isolation_epoch() -> tuple:
    """What the view of an ``isolated`` window depends on besides its own state."""
    from . import i18n as _i18n

    return (_i18n.language(), _style._screen, _style._named_version, _style._rules_version,
            _hot_reload.generation, id(_style.global_style()))


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
    if _in_worker_process():
        return  # a ``process=True`` worker imports the main script: it must not open the app again
    _devices._start(app).apply()
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
        workers = sys.modules.get("pyzed.workers")
        if workers is not None:
            workers.shutdown()


def _in_worker_process() -> bool:
    """Whether this is a worker process started by ``multiprocessing`` (``pz.background(process=True)``)."""
    if "multiprocessing" not in sys.modules:
        return False
    import multiprocessing

    return multiprocessing.parent_process() is not None


def screenshot(app, path, *, size=None, scale: float = 2.0, wait: float = 0.1) -> None:
    """Renders ``app`` (instance or class) off-screen into a PNG file."""
    if isinstance(app, type):
        app = app()
    _core.screenshot(app, str(path), size=size, scale=scale, wait=wait)
