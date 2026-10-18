"""Components: reusable pieces of UI with their own props, state, logic and events.

A component is a class, like a React component. Props are annotated class attributes
(with their defaults), state is any other attribute you set, ``render()`` returns
widgets, and ``events`` declares the custom events it can ``emit``::

    class Rating(pz.Component):
        \"\"\"Stars the user can click.\"\"\"

        value: int = 0            # props: passed by the parent on every render
        max: int = 5
        events = {"change": "A star was picked (``event.value`` is the rating)."}
        icon = "star"             # how it shows in the designer's library

        def setup(self):          # once, when the component first appears
            self.hover = None     # state: kept between renders

        def pick(self, stars):
            return self.emit("change", stars)

        def render(self):
            shown = self.hover or self.value
            return pz.row([
                pz.text("★" if i <= shown else "☆", size=20).on(
                    click=lambda i=i: self.pick(i),
                    mouse_enter=lambda i=i: setattr(self, "hover", i),
                    mouse_leave=lambda: setattr(self, "hover", None),
                )
                for i in range(1, self.max + 1)
            ], spacing=2)

    # In a view: a component call returns a widget, so it goes anywhere a widget does.
    Rating(value=self.stars, on_change=lambda e: setattr(self, "stars", e.value))

Every component also accepts the common events (``on_click``, ``on_drag``...; see
``pyzed.events``) and the lifecycle events ``on_mount`` / ``on_unmount``.

State is kept per position in the parent's ``view()``: the second ``Rating`` in a view
keeps its own state, as long as the order does not change. When components are
created in a loop whose items move, give each one a stable ``key=``.

Lifecycle hooks: ``setup()`` (before the first render, props already set),
``on_mount()`` (after the first render) and ``on_unmount()`` (when it stops being
rendered). ``on_mount`` may return a ``Command`` or a message.

Components show up in the designer's toolbox automatically (see ``label``, ``icon``,
``category``, ``size`` and ``designer``).
"""

from __future__ import annotations

import re
import sys
import typing
from contextlib import contextmanager
from typing import Any, Callable, ClassVar, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from . import _core
from . import events as _events

__all__ = ["LIFECYCLE_EVENTS", "Component", "PropInfo", "find", "registered", "render_pass"]

_MISSING: Any = object()

#: Class attributes that configure a component and are never props.
_RESERVED = {"events", "label", "icon", "category", "size", "designer", "type_name", "description"}

#: Events every component emits on its own.
LIFECYCLE_EVENTS = {
    "mount": "The component appeared (after its first render).",
    "unmount": "The component stopped being rendered.",
}


class PropInfo(typing.NamedTuple):
    """A prop: its name, type annotation (may be a string) and default."""

    name: str
    annotation: Any
    default: Any

    @property
    def required(self) -> bool:
        return self.default is _MISSING


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _is_classvar(annotation: Any) -> bool:
    if isinstance(annotation, str):
        return annotation.replace("typing.", "").startswith("ClassVar")
    return typing.get_origin(annotation) is ClassVar


class _Pass:
    """One ``view()`` call: which components were rendered, and where."""

    def __init__(self, store: Dict[tuple, "Component"]) -> None:
        self.store = store
        self.seen: set = set()
        self.counters: Dict[tuple, int] = {}
        self.path: tuple = ()

    def key_for(self, cls: type, key: Any) -> tuple:
        if key is not None:
            return self.path + (cls.__qualname__, "key", key)
        slot = self.path + (cls.__qualname__,)
        index = self.counters.get(slot, 0)
        self.counters[slot] = index + 1
        return slot + (index,)


_passes: List[_Pass] = []


@contextmanager
def render_pass(owner: Any) -> Iterator[None]:
    """Tracks the components rendered while ``owner`` (a window) runs its ``view()``.

    Components not rendered again are unmounted at the end. The runtime does this for
    every window; use it yourself only to render components outside a window.
    """
    store = owner.__dict__.setdefault("_pyzed_components", {})
    current = _Pass(store)
    _passes.append(current)
    try:
        yield
    except BaseException:
        _passes.pop()
        raise  # keep every component alive: the view failed half way
    _passes.pop()
    for key in [k for k in store if k not in current.seen]:
        store.pop(key)._unmount()


def _defer(callback: Callable[[], Any]) -> None:
    """Runs ``callback`` on the UI thread right after the current ``view()``.

    Lifecycle hooks must not run in the middle of drawing; posted, they run like any
    other callback (their result, a command or a message, is handled and the window
    redraws). Without a running app (tests) they run at once.
    """
    try:
        _core.post(callback)
    except RuntimeError:
        callback()


class Component:
    """Base class for components; see the module documentation for a full example.

    Class attributes:
        ``events``     custom events, as a tuple of names or a ``{name: description}`` dict.
        ``label``      name shown in the designer's toolbox (defaults to the class name).
        ``icon``       Lucide icon for the toolbox (``"component"``).
        ``category``   toolbox section (``"Custom"``).
        ``size``       default size when placed on a form, ``(width, height)``.
        ``designer``   ``False`` keeps the component out of the toolbox.
        ``type_name``  id used in saved forms (defaults to the class name in snake case).
    """

    events: ClassVar[Any] = ()
    label: ClassVar[str] = ""
    icon: ClassVar[str] = "component"
    category: ClassVar[str] = "Custom"
    size: ClassVar[Tuple[float, float]] = (160, 40)
    designer: ClassVar[bool] = True
    type_name: ClassVar[str] = ""

    #: The props of this class, in declaration order (filled in for each subclass).
    __props__: ClassVar[Dict[str, PropInfo]] = {}
    #: Custom and lifecycle events with their descriptions (filled in for each subclass).
    __events__: ClassVar[Dict[str, str]] = {}

    _pyzed_handlers: Dict[str, Any]
    _pyzed_mounted: bool

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        props: Dict[str, PropInfo] = {}
        for klass in reversed(cls.__mro__):
            if klass is Component or not issubclass(klass, Component):
                continue
            for name, annotation in vars(klass).get("__annotations__", {}).items():
                if name.startswith("_") or name in _RESERVED or _is_classvar(annotation):
                    continue
                props[name] = PropInfo(name, annotation, vars(klass).get(name, _MISSING))
        cls.__props__ = props
        declared = cls.events
        if isinstance(declared, Mapping):
            custom = {str(k): str(v) for k, v in declared.items()}
        else:
            custom = {str(name): "" for name in declared}
        cls.__events__ = {**custom, **LIFECYCLE_EVENTS}
        if not cls.type_name:
            cls.type_name = _snake(cls.__name__)
        if not cls.label:
            cls.label = re.sub(r"(?<!^)(?=[A-Z])", " ", cls.__name__)
        if cls.designer and not cls.__name__.startswith("_"):
            _REGISTRY[cls.type_name] = cls
            designer = sys.modules.get("pyzed.designer.components")
            if designer is not None:
                designer.register(cls.designer_spec())

    # -- creating -------------------------------------------------------------
    def __new__(cls, *args: Any, key: Any = None, **kwargs: Any) -> Any:
        """``MyComponent(prop=..., on_event=...)`` renders the component and returns a widget."""
        props, custom, common = cls._split(args, kwargs)
        current = _passes[-1] if _passes else None
        slot = current.key_for(cls, key) if current is not None else None
        instance = current.store.get(slot) if current is not None else None
        if instance is not None and type(instance) is not cls:
            instance = None  # a different component now sits at this position
        fresh = instance is None
        if fresh:
            instance = object.__new__(cls)
            instance._pyzed_mounted = False
        instance._pyzed_handlers = custom
        for name, info in cls.__props__.items():
            setattr(instance, name, props.get(name, info.default))
        if fresh:
            instance.setup()
        if current is not None:
            current.seen.add(slot)
            current.store[slot] = instance
            parent, current.path = current.path, slot
            try:
                widget = instance.render()
            finally:
                current.path = parent
        else:
            widget = instance.render()
        if not isinstance(widget, _core.Widget):
            widget = _core.container(widget)
        if not instance._pyzed_mounted and current is not None:
            instance._pyzed_mounted = True
            _defer(instance._mount)
        if common:
            widget = widget.on(**common)
        return widget

    @classmethod
    def create(cls, *args: Any, **kwargs: Any) -> "Component":
        """A standalone instance (not rendered, no lifecycle), handy in tests: ``c.render()``."""
        props, custom, _common = cls._split(args, kwargs)
        instance = object.__new__(cls)
        instance._pyzed_mounted = False
        instance._pyzed_handlers = custom
        for name, info in cls.__props__.items():
            setattr(instance, name, props.get(name, info.default))
        instance.setup()
        return instance

    @classmethod
    def _split(cls, args: Sequence[Any], kwargs: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        names = list(cls.__props__)
        if len(args) > len(names):
            raise TypeError(f"{cls.__name__} takes at most {len(names)} positional props ({', '.join(names)})")
        props: Dict[str, Any] = dict(zip(names, args))
        custom: Dict[str, Any] = {}
        common: Dict[str, Any] = {}
        for name, value in kwargs.items():
            if name in cls.__props__:
                if name in props:
                    raise TypeError(f"{cls.__name__} got prop {name!r} twice")
                props[name] = value
            elif name.startswith("on_") and name[3:] in cls.__events__:
                custom[name[3:]] = value
            elif name.startswith("on_") and name[3:] in _events.CATALOG:
                common[name[3:]] = value
            else:
                raise TypeError(
                    f"{cls.__name__} has no prop or event {name!r}. Props: {', '.join(names) or 'none'}; "
                    f"events: {', '.join('on_' + e for e in [*cls.__events__, *_events.COMMON])}"
                )
        missing = [n for n, info in cls.__props__.items() if info.required and n not in props]
        if missing:
            raise TypeError(f"{cls.__name__} is missing required props: {', '.join(missing)}")
        return props, custom, common

    # -- what subclasses write ---------------------------------------------------
    def setup(self) -> None:
        """Called once before the first render (props are already set): initialize state here."""

    def render(self) -> Any:  # pragma: no cover - meant to be overridden
        """Returns the widgets of this component (called on every render)."""
        raise NotImplementedError(f"{type(self).__name__}.render() must return a widget")

    def on_mount(self) -> Any:
        """Called after the first render; may return a ``Command`` or a message."""
        return None

    def on_unmount(self) -> None:
        """Called when the component is no longer rendered."""

    # -- events -------------------------------------------------------------------
    def emit(self, name: str, value: Any = None) -> Any:
        """Raises the custom event ``name``: calls the handler the parent passed as ``on_<name>``.

        The handler gets a ``pyzed.Event`` with ``value`` and ``source`` (this component).
        Return the result from your callback so commands and messages reach the runtime::

            def pick(self, stars):
                return self.emit("change", stars)
        """
        if name not in self.__events__:
            raise ValueError(f"{type(self).__name__} does not declare the event {name!r}; "
                             f"add it to `events` ({', '.join(self.__events__)})")
        handler = self._pyzed_handlers.get(name)
        return _events.call(handler, _events.Event(name, value=value, source=self))

    def handles(self, name: str) -> bool:
        """Whether the parent passed a handler for the custom event ``name``."""
        return self._pyzed_handlers.get(name) is not None

    def _mount(self) -> Any:
        results = [self.on_mount(), self.emit("mount")]
        results = [r for r in results if r is not None]
        return results[0] if len(results) == 1 else (results or None)

    def _unmount(self) -> None:
        def run() -> Any:
            self.on_unmount()
            return self.emit("unmount")

        _defer(run)

    # -- the designer ----------------------------------------------------------------
    @classmethod
    def describe(cls) -> str:
        """The first paragraph of the docstring (shown in the designer)."""
        doc = (cls.__doc__ or "").strip()
        return doc.split("\n\n")[0].replace("\n", " ") if doc else ""

    @classmethod
    def designer_spec(cls) -> Any:
        """This component as an entry of the designer's toolbox (``pyzed.designer.Component``)."""
        from .designer import components as designer

        props = tuple(_designer_prop(info, designer.Prop) for info in cls.__props__.values())
        list_props = {p.name for p in props if p.kind == "list"}
        custom_events = tuple(e for e in cls.__events__ if e not in LIFECYCLE_EVENTS)

        def render(control: Any, ctx: Any) -> Any:
            values = {name: control.props.get(name) for name in cls.__props__}
            for name in list_props:
                value = values[name]
                if isinstance(value, str):
                    values[name] = [line for line in value.splitlines() if line.strip()]
            values = {k: v for k, v in values.items() if v is not None or not cls.__props__[k].required}
            handlers = {}
            for event in custom_events:
                if control.events.get(event):
                    callback = ctx.on(control, event)
                    handlers[f"on_{event}"] = lambda e, callback=callback: callback(e.value)
            return cls(key=ctx.key(control), **values, **handlers)

        return designer.Component(
            type=cls.type_name,
            label=cls.label,
            icon=cls.icon,
            category=cls.category,
            render=render,
            size=tuple(cls.size),
            props=props,
            events=custom_events,
            description=cls.describe(),
        )


def _designer_prop(info: PropInfo, prop_class: Callable[..., Any]) -> Any:
    """Maps a prop's annotation to a designer property editor."""
    annotation = info.annotation
    text = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", str(annotation))
    default = None if info.required else info.default
    origin = typing.get_origin(annotation)
    if origin is typing.Literal or (isinstance(annotation, str) and annotation.startswith(("Literal[", "typing.Literal["))):
        choices = typing.get_args(annotation) if origin is typing.Literal else tuple(
            re.findall(r"['\"]([^'\"]*)['\"]", annotation))
        return prop_class(info.name, "choice", default, choices=tuple(str(c) for c in choices))
    base = text.split("[")[0].replace("typing.", "").lower()
    if base == "bool":
        return prop_class(info.name, "bool", bool(default))
    if base in ("int", "float"):
        return prop_class(info.name, "number", default, step=1.0 if base == "int" else 0.1)
    if base in ("list", "tuple", "sequence"):
        return prop_class(info.name, "list", "\n".join(map(str, default or ())), group="Data")
    if info.name in ("color", "background", "tint_color") or info.name.endswith("_color"):
        return prop_class(info.name, "color", default or "")
    if info.name == "icon" or info.name.endswith("_icon"):
        return prop_class(info.name, "icon", default or "")
    return prop_class(info.name, "text", "" if default is None else default)


_REGISTRY: Dict[str, type] = {}


def registered() -> List[type]:
    """Every ``Component`` subclass defined so far that should appear in the designer."""
    return list(_REGISTRY.values())


def find(type_name: str) -> Optional[type]:
    """The component class registered as ``type_name`` (see ``Component.type_name``)."""
    return _REGISTRY.get(type_name)
