"""Events: the common ones every widget can have, and the ``Event`` handlers receive.

Any widget gets the common events with ``.on(...)``; they are implemented once, in a
native wrapper, so no component has to repeat them::

    pz.container(card).on(
        click=self.select,                       # no argument: just called
        double_click=lambda e: self.open(e.x),   # one argument: gets an Event
        drag=self.move,                          # e.dx, e.dy since the last drag event
        key_down=lambda e: print(e.key),         # while focused (clicked), e.key == "ctrl-s"
        cursor="grab",
    )

``pz.on(widget, ...)`` is the same as ``widget.on(...)``. A handler may also be a
message (any non-callable value), which goes to ``update``. Events never stop at a
wrapper: a click on a button inside a card reaches the button and the card.

Components made with ``pz.Component`` also emit their own (custom) events with
``self.emit(name, value)``; see ``pyzed.component``.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, NamedTuple, Optional, Tuple

from . import _core

__all__ = ["CATALOG", "COMMON", "Event", "EventInfo", "accepts_argument", "on"]


class EventInfo(NamedTuple):
    """Documentation of one event: its group and what it reports."""

    name: str
    category: str
    doc: str


#: Every common event, grouped as graphical editors usually show them.
CATALOG: Dict[str, EventInfo] = {
    info.name: info
    for info in (
        EventInfo("click", "Mouse", "The widget was clicked (pressed and released with the left button)."),
        EventInfo("double_click", "Mouse", "Two clicks in quick succession."),
        EventInfo("right_click", "Mouse", "The right button was pressed (use it for context menus)."),
        EventInfo("middle_click", "Mouse", "The middle button (wheel) was pressed."),
        EventInfo("mouse_down", "Mouse", "Any button was pressed over the widget (``event.button``)."),
        EventInfo("mouse_up", "Mouse", "Any button was released over the widget (``event.button``)."),
        EventInfo("mouse_enter", "Mouse", "The pointer moved onto the widget."),
        EventInfo("mouse_leave", "Mouse", "The pointer left the widget."),
        EventInfo("mouse_move", "Mouse", "The pointer moved over the widget (``event.x``, ``event.y``)."),
        EventInfo("scroll", "Mouse", "The wheel turned over the widget (``event.dx``, ``event.dy`` in lines)."),
        EventInfo("drag_start", "Drag", "The left button was pressed and the pointer moved a few pixels."),
        EventInfo("drag", "Drag", "The pointer moved while dragging (``event.dx``, ``event.dy`` since the last one)."),
        EventInfo("drag_end", "Drag", "The button was released after a drag."),
        EventInfo("focus", "Focus", "The widget was clicked and now receives key events."),
        EventInfo("blur", "Focus", "A click elsewhere took the focus away."),
        EventInfo("key_down", "Keyboard", "A key was pressed while focused (``event.key``, e.g. ``\"ctrl-s\"``)."),
        EventInfo("key_up", "Keyboard", "A key was released while focused (``event.key``)."),
        EventInfo("resize", "Layout", "The widget got a new size, including its first one (``event.width``, ``event.height``)."),
    )
}

#: The names of the common events, in catalog order.
COMMON: Tuple[str, ...] = tuple(CATALOG)

assert COMMON == tuple(_core.event_names()), "events.py and events.rs disagree"


class Event:
    """What happened, passed to handlers that take an argument.

    ``type`` is the event name (``"click"``, ``"drag"``, or a component's custom event).
    ``x``/``y`` are the pointer position relative to the widget, ``window_x``/``window_y``
    relative to the window (outside it while a drag leaves the window) and
    ``screen_x``/``screen_y`` on the screen (``None`` where the platform does not say where
    windows are, such as Wayland), ``dx``/``dy`` the scroll
    or drag amount, ``width``/``height`` the widget's size, ``button`` the mouse button
    (``"left"``, ``"right"``...), ``key`` the key combo, ``shift``/``ctrl``/``alt``/``logo``
    the modifiers held. Custom events carry ``value`` and the emitting ``source``.
    """

    __slots__ = ("type", "x", "y", "dx", "dy", "width", "height", "button", "key",
                 "shift", "ctrl", "alt", "logo", "value", "source", "window_x", "window_y",
                 "screen_x", "screen_y")

    def __init__(self, type: str, *, x: float = 0.0, y: float = 0.0, dx: float = 0.0, dy: float = 0.0,  # noqa: A002
                 width: float = 0.0, height: float = 0.0, button: Optional[str] = None,
                 key: Optional[str] = None, shift: bool = False, ctrl: bool = False, alt: bool = False,
                 logo: bool = False, value: Any = None, source: Any = None, window_x: float = 0.0,
                 window_y: float = 0.0, screen_x: Optional[float] = None,
                 screen_y: Optional[float] = None) -> None:
        self.type = type
        self.x, self.y, self.dx, self.dy = x, y, dx, dy
        self.width, self.height = width, height
        self.button, self.key = button, key
        self.shift, self.ctrl, self.alt, self.logo = shift, ctrl, alt, logo
        self.value, self.source = value, source
        self.window_x, self.window_y = window_x, window_y
        self.screen_x, self.screen_y = screen_x, screen_y

    @property
    def position(self) -> Tuple[float, float]:
        """``(x, y)``."""
        return (self.x, self.y)

    @property
    def size(self) -> Tuple[float, float]:
        """``(width, height)``."""
        return (self.width, self.height)

    @property
    def screen(self) -> Optional[Tuple[float, float]]:
        """``(screen_x, screen_y)``, or ``None`` when the platform does not report window positions."""
        if self.screen_x is None or self.screen_y is None:
            return None
        return (self.screen_x, self.screen_y)

    def __repr__(self) -> str:
        fields = [f"{name}={getattr(self, name)!r}" for name in self.__slots__[1:]
                  if getattr(self, name) not in (None, 0.0, False)]
        return f"Event({self.type!r}{', ' if fields else ''}{', '.join(fields)})"


def on(widget: Any, *, cursor: Optional[str] = None, **handlers: Any) -> _core.Widget:
    """Attaches common event handlers to ``widget`` (same as ``widget.on(...)``)."""
    if not isinstance(widget, _core.Widget):
        widget = _core.container(widget)
    return widget.on(cursor=cursor, **handlers)


_ARITY: Dict[Any, bool] = {}


def accepts_argument(handler: Callable[..., Any]) -> bool:
    """Whether ``handler`` takes the event: it has a required positional parameter or ``*args``.

    Parameters with defaults do not count, so ``lambda i=i: ...`` is called with nothing.
    The answer is cached per function.
    """
    target = getattr(handler, "__func__", handler)
    code = getattr(target, "__code__", None)
    cache_key = code if code is not None else type(handler)
    cached = _ARITY.get(cache_key)
    if cached is not None:
        return cached
    import inspect  # only when a handler is first seen (it is slow to import)

    try:
        params = list(inspect.signature(handler).parameters.values())
    except (TypeError, ValueError):
        result = True  # builtins and C callables: assume they take the event
    else:
        # Only a required positional parameter (or *args) takes the event, so the
        # `lambda i=i: ...` idiom for loop variables keeps its captured value.
        required = [p for p in params if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                    and p.default is p.empty]
        result = any(p.kind is p.VAR_POSITIONAL for p in params) or bool(required)
    _ARITY[cache_key] = result
    return result


def call(handler: Any, event: Event) -> Any:
    """Calls ``handler`` with ``event`` (or with nothing if it takes no argument).

    A non-callable handler is a message and is returned as is, for ``update``.
    """
    if handler is None:
        return None
    if not callable(handler) or isinstance(handler, type):
        return handler
    return handler(event) if accepts_argument(handler) else handler()


def _deliver(handler: Any, type: str, **fields: Any) -> Any:  # noqa: A002
    """Called by the runtime when a common event fires."""
    return call(handler, Event(type, **fields))
