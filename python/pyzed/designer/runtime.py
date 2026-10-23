"""Runs a designed form: draws its controls and calls the handlers wired in the designer.

    from pyzed import designer
    designer.run("login.pzform")          # or: pyzed run login.pzform

Handlers get the running ``form`` and an ``Event``. Controls are attributes of the
form, and their properties are attributes of the control, so changing them updates
the window::

    def greet_click(form, event):
        form.status.text = f"Hello, {form.name.text}!"
        form.greet.enabled = False

Handlers may return anything a Pyzed callback can (a ``Command``, a coroutine...).
"""

from __future__ import annotations

import dataclasses
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Tuple, Union

from .. import _core, hot_reload, ui
from .. import animation as _animation
from .. import services as _services
from ..app import App, Window
from ..app import run as _run_app
from .. import rendering as _rendering
from ..theme import Theme, themes
from . import binding as _binding
from . import code as _code
from . import components as _components
from . import layout as _layout
from . import motion
from . import nonvisual
from . import styling
from . import timeline
from .model import SUFFIX, Control, Form, code_path, load

_FIELDS = ("x", "y", "width", "height", "visible", "enabled", "anchor")

#: Events too frequent for the designer's console log.
_QUIET_EVENTS = frozenset({"tick", "mouse_enter", "mouse_leave", "output", "error_output", "progress"})

#: Properties the user changes by interacting; hot reload keeps them.
_VALUE_PROPS = {
    "input": ("text",), "text_area": ("text",), "checkbox": ("checked",), "switch": ("checked",),
    "radio": ("selected",), "select": ("selected",), "slider": ("value",), "number": ("value",),
    "list_box": ("selected",), "search": ("text",), "segmented": ("selected",), "tabs": ("tabs", "selected"),
    "toggle_group": ("selected",), "tree": ("selected", "expanded"), "table": ("selected", "sort_by", "descending"),
    "color_picker": ("value",), "icon_picker": ("value",), "dock": ("layout",),
}


def theme_for(form: Form, theme_name: Optional[str] = None) -> Theme:
    """The theme a form runs with: its base theme (or ``theme_name``, to preview it with another one) plus
    accent, radius, font and background tweaks."""
    if theme_name:
        form = dataclasses.replace(form, theme=theme_name)
    try:
        theme = themes.get(form.theme)
    except KeyError:
        theme = themes.get("One Dark")
    if form.accent:
        theme = theme.with_accent(form.accent)
    changes: Dict[str, Any] = {}
    if form.radius is not None:
        changes.update(radius=float(form.radius), radius_sm=max(float(form.radius) - 2, 0))
    if form.background:
        changes["background"] = form.background
    if form.font_size and form.font_size != theme.ui_font_size:
        changes["ui_font_size"] = float(form.font_size)
    theme = theme.derive(**changes) if changes else theme
    if form.style:
        theme = styling.themed(theme, form.style)
    return theme


@dataclass
class Event:
    """What a handler receives besides the form: who raised it, which event and its value."""

    sender: Any
    name: str
    value: Any = None


def remember_instance(owner: Any, control: Control, ctx: Any) -> None:
    """Keeps the ``pz.Component`` just rendered for ``control``, so ``owner.control.method()`` reaches it."""
    from ..component import _passes, find

    cls = find(control.type)
    if cls is None or not _passes:
        return
    current = _passes[-1]
    instance = current.store.get(current.path + (cls.__qualname__, "key", ctx.key(control)))
    if instance is not None:
        vars(owner).setdefault("_pyzed_children", {})[control.name] = instance


class ControlProxy:
    """A control of the running form; its properties read and write like attributes."""

    __slots__ = ("_control", "_runtime")

    def __init__(self, control: Control, runtime: "FormRuntime") -> None:
        object.__setattr__(self, "_control", control)
        object.__setattr__(self, "_runtime", runtime)

    @property
    def name(self) -> str:
        """The control's name."""
        return self._control.name

    @property
    def type(self) -> str:  # noqa: A003
        """The control's component type (``"button"``, ``"textbox"``...)."""
        return self._control.type

    def __getattr__(self, key: str) -> Any:
        control = self._control
        if key in _FIELDS:
            return getattr(control, key)
        service = self.service
        if service is not None and not key.startswith("_"):
            name = nonvisual.attribute(control, key)
            if hasattr(service, name):  # what a timer, a process... has now, and its methods
                return getattr(service, name)
        if key in control.props:
            return control.props[key]
        default = _components.spec(control.type).defaults()
        if key in default:
            return default[key]
        instance = self.instance
        if instance is not None and not key.startswith("_") and hasattr(instance, key):
            return getattr(instance, key)  # a method or the state of a component placed here
        raise AttributeError(f"{control.type} {control.name!r} has no property {key!r}")

    def __setattr__(self, key: str, value: Any) -> None:
        service = self.service
        if key in _FIELDS:
            setattr(self._control, key, value)
            if service is not None and key == "enabled":
                service.enabled = bool(value)
            return
        if service is not None and not key.startswith("_") \
                and hasattr(service, nonvisual.attribute(self._control, key)):
            nonvisual.apply(service, self._control, key, value)
            if key not in _components.spec(self._control.type).defaults():
                return  # only the service has it
        if key == "error":
            self._runtime.set_error(self._control.name, value)
            return
        instance = self.instance
        if instance is not None and key in getattr(type(instance), "__state__", {}):
            setattr(instance, key, value)  # private state of a placed component
            return
        self._control.props[key] = value

    def __getitem__(self, key: str) -> Any:
        service = self.service
        if service is None or not hasattr(service, "__getitem__"):
            raise TypeError(f"{self._control.type} {self._control.name!r} is not subscriptable")
        return service[key]

    def __setitem__(self, key: str, value: Any) -> None:
        service = self.service
        if service is None or not hasattr(service, "__setitem__"):
            raise TypeError(f"{self._control.type} {self._control.name!r} does not support item assignment")
        service[key] = value

    def __contains__(self, key: object) -> bool:
        service = self.service
        return service is not None and hasattr(service, "__contains__") and key in service

    @property
    def service(self) -> Any:
        """The ``pyzed.services`` object behind a non-visual control (a Timer, a Process...), or ``None``."""
        services = getattr(self._runtime, "services", None)  # a designed component's scene has none
        return services.get(self._control.name) if services else None

    @property
    def instance(self) -> Any:
        """The ``pz.Component`` drawn for this control (a component placed here), or ``None``."""
        return vars(self._runtime).get("_pyzed_children", {}).get(self._control.name)

    @property
    def error(self) -> Optional[str]:
        """The validation message shown under the control (``None`` when it is valid). Set it to show your own
        (``form.email.error = "Already registered"``) and to ``None`` to clear it."""
        return self._runtime.errors.get(self._control.name)

    def validate(self) -> bool:
        """Checks the control's rules now, shows the message if one fails and returns whether it passed."""
        return self._runtime.validate([self._control.name])

    def show(self, *args: Any, **kwargs: Any) -> Any:
        """Makes the control visible. On a File dialog, a Notification or a Tray icon it shows them instead
        (return a dialog's ``show()`` from the handler: it is a command)."""
        service = self.service
        if service is not None and callable(getattr(service, "show", None)):
            return service.show(*args, **kwargs)
        self._control.visible = True
        return None

    def hide(self) -> None:
        """Hides the control (and whatever is inside it); a Tray icon leaves the tray."""
        service = self.service
        if service is not None and callable(getattr(service, "hide", None)):
            service.hide()
            return
        self._control.visible = False

    def focus(self) -> _core.Command:
        """A command that focuses this control (text boxes and text areas)."""
        return _core.Command.focus(self._runtime.ctx.key(self._control))

    def play_animation(self, animation: Any = None, **options: Any) -> None:
        """Plays an animation on the control now, from the start.

        Without arguments it plays the control's own animations set to **When played from code**
        in Pyzed Design (and replays the ones set to **When it appears**). With a preset name, a
        ``pz.Animation`` or property values it plays that once::

            form.title.play_animation()                       # its animations from the Animation section
            form.password.play_animation("shake")             # any preset
            form.badge.play_animation("pulse", repeat=3)      # with animate() options
            form.card.play_animation(scale=1.1, duration=200) # to these values and back
        """
        props = {k: options[k] for k in list(options) if k in _animation.PROPERTIES}
        if props and animation is None:
            animation = _animation.Animation(  # like animate(on="manual", scale=1.1): there and back
                [{k: None for k in props}, props, {k: None for k in props}], duration=300)
            options = {k: v for k, v in options.items() if k not in props}
        if animation is not None:
            _animation._compile([animation], {**options, "on": "mount"})  # raise bad names and options here
        played = self._runtime.played.setdefault(self._control.name, motion.Played())
        played.play(animation, **options)

    def stop_animation(self) -> None:
        """Stops what ``play_animation`` started (a looping "from code" animation, a preset played on it)."""
        played = self._runtime.played.get(self._control.name)
        if played is not None:
            played.stop()

    def __repr__(self) -> str:
        return f"<{self._control.type} {self._control.name}>"


class FormProxy:
    """The running form as handlers see it: ``form.button1``, ``form.title``, ``form.close()``."""

    __slots__ = ("_runtime",)

    def __init__(self, runtime: "FormRuntime") -> None:
        object.__setattr__(self, "_runtime", runtime)

    def __getattr__(self, name: str) -> Any:
        control = self._runtime.form.get(name)
        if control is None:
            raise AttributeError(f"the form has no control or attribute {name!r}")
        return ControlProxy(control, self._runtime)

    def __getitem__(self, name: str) -> ControlProxy:
        return ControlProxy(self._runtime.form[name], self._runtime)

    def __iter__(self) -> Iterator[ControlProxy]:
        return (ControlProxy(c, self._runtime) for c in self._runtime.form.controls)

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "title":
            self._runtime.form.title = value
        elif key == "data":
            self._runtime.set_data(value)
        else:
            raise AttributeError(f"cannot set {key!r} on the form; use form.<control>.<property>")

    @property
    def name(self) -> str:
        """The form's name."""
        return self._runtime.form.name

    @property
    def title(self) -> str:
        """The window's title (handlers can also set it: ``form.title = "..."``)."""
        return _binding.translate(self._runtime.form.title, self._runtime.language)

    @property
    def size(self) -> Tuple[float, float]:
        """The window's current ``(width, height)`` in pixels."""
        return self._runtime.size

    @property
    def window(self) -> Window:
        """The Pyzed window running this form (for ``Command`` helpers)."""
        return self._runtime.window

    @property
    def animations(self) -> Any:
        """The form's ``pz.AnimationPlayer``: ``form.animations.play("intro")``."""
        return self._runtime.player

    @property
    def data(self) -> Any:
        """The form's data: what the form that opened it passed as ``data=`` (a dict, a list or any object).

        Bound controls show its fields and inputs write back what the user types. When nothing was passed and
        some control is bound, it starts as a dict with the designed values. Assign ``form.data = record`` to
        show another record.
        """
        return self._runtime.data

    @property
    def errors(self) -> Dict[str, str]:
        """The validation messages on show, by control name (empty when every checked control is valid)."""
        return dict(self._runtime.errors)

    @property
    def valid(self) -> bool:
        """Whether no control shows a validation message."""
        return not self._runtime.errors

    def validate(self) -> bool:
        """Checks the rules of every visible, enabled control, shows the messages and returns whether all
        passed; call it before saving::

            def save_click(form, event):
                if form.validate():
                    store(form.data)
        """
        return self._runtime.validate()

    def close(self) -> _core.Command:
        """Returns the command that closes this form's window (return it from a handler)."""
        return self._runtime.window.close()

    def open(self, form: Union[str, Path, Form], *, data: Any = None) -> _core.Command:
        """Opens another form in a new window; return the result from a handler::

            def settings_click(form, event):
                return form.open("settings", data=form.name_input.text)

        ``form`` is a name (``"settings"``) or path, relative to this form's folder, or a
        ``Form`` built in code. The new form reads ``data`` as ``form.data``; its window is
        listed in ``form.windows`` while open.
        """
        runtime = self._runtime
        base = runtime.path.parent if runtime.path is not None else None
        window = form_window(form, data=data, folder=base)
        window.runtime.log = runtime.log
        runtime.opened.append(window)
        return _core.Command.open_window(window)

    @property
    def windows(self) -> list:
        """The other forms opened with ``open`` that are still open."""
        return [w.form for w in self._runtime.opened if w.is_open]


class LiveContext(_components.RenderContext):
    """The render context of a running form: callbacks store the new value and dispatch the event to its
    handler."""
    live = True

    def __init__(self, runtime: "FormRuntime") -> None:
        super().__init__(runtime.theme, runtime.form.name)
        self.runtime = runtime
        self.language = runtime.language

    def on(self, control: Control, event: str, prop: Optional[str] = None) -> Callable[..., Any]:
        runtime = self.runtime

        def callback(*args: Any) -> Any:
            # ``control`` may be a positioned copy made for drawing; state lives on the form's own.
            target = runtime.form.get(control.name) or control
            value = args[0] if len(args) == 1 else (args or None)
            if prop is not None:
                target.props[prop] = value
                runtime.changed(target, prop, value)
            return runtime.dispatch(target, event, value)

        return callback

    @property
    def form(self) -> Form:  # type: ignore[override]
        return self.runtime.form

    def set(self, control: Control, prop: str, value: Any) -> None:  # noqa: A003
        target = self.runtime.form.get(control.name) or control
        target.props[prop] = value
        self.runtime.changed(target, prop, value)

    @property
    def played(self) -> Optional[Dict[str, Any]]:  # type: ignore[override]
        return getattr(self.runtime, "played", None)


class FormRuntime:
    """The engine behind ``FormApp``/``FormWindow``: state, event dispatch and drawing."""

    def __init__(self, form: Form, handlers: Optional[Dict[str, Any]] = None, *, window: Window,
                 path: Optional[Union[str, Path]] = None, data: Any = None, theme: Optional[str] = None,
                 language: Optional[str] = None) -> None:
        self.form = form.copy()
        self.path: Optional[Path] = Path(path) if path else None
        #: A theme and a language to preview the form with (Pyzed Design's View menu), else the form's own.
        self.preview_theme = theme or os.environ.get("PYZED_PREVIEW_THEME") or None
        self.language = language or os.environ.get("PYZED_PREVIEW_LANGUAGE") or None
        _binding.load_texts(self.path)
        #: Validation messages on show, by control name.
        self.errors: Dict[str, str] = {}
        #: The place of each control of ``form.tab_order`` in the Tab order (from 1), by name.
        self._tab_index: Dict[str, int] = {}
        self.data = data
        self._fill_data()
        self.opened: list = []
        #: Called as ``log(level, text)`` for events and handler errors (the designer's console).
        self.log: Optional[Callable[[str, str], None]] = None
        self.design_size = (form.width, form.height)
        self.handlers = dict(handlers or {})
        self.window = window
        self.theme = theme_for(form, self.preview_theme)
        #: What handlers played on each control (``form.title.play_animation()``), by name.
        self.played: Dict[str, motion.Played] = {}
        #: The animations each event plays (``{(control, event): [(control, index)]}``, see ``motion``).
        self.listeners = self._listen()
        self.ctx = LiveContext(self)
        self.proxy = FormProxy(self)
        self.error: Optional[str] = None
        self.loaded = False
        #: Plays the form's timeline animations (``form.animations`` in handlers).
        self.player = timeline.player_for(self.form, timeline.FormOwner(self))
        #: The services behind the non-visual controls (timers, file watchers, processes...), by name.
        self.services: Dict[str, Any] = nonvisual.build_all(self)

    @property
    def size(self) -> Tuple[float, float]:
        """The window's current ``(width, height)``, or the designed size before it is known."""
        return tuple(self.window.window_size or self.design_size)  # type: ignore[return-value]

    def _listen(self) -> Dict[Tuple[str, str], list]:
        """Finds the animations that play on events and makes sure those events are raised: an event no handler
        is wired to gets ``motion.ANIMATION_ONLY``, so the controls report it (this form is a copy)."""
        found = motion.listeners(self.form.controls)
        for source, event in found:
            events = self.form.get(source).events if source and self.form.get(source) is not None else (
                None if source else self.form.events)
            if events is not None and event != "invalid" and not events.get(event):
                events[event] = motion.ANIMATION_ONLY
        return found

    def fire(self, source: str, event: str) -> bool:
        """Plays the animations waiting for ``event`` of control ``source`` (``""``: the form); returns whether
        there were any."""
        targets = self.listeners.get((source, event), ())
        for name, index in targets:
            self.played.setdefault(name, motion.Played()).fire(index)
        return bool(targets)

    def dispatch(self, control: Optional[Control], event: str, value: Any = None) -> Any:
        """Calls the handler wired to ``event`` of ``control`` (or of the form when ``None``), after playing the
        animations that wait for that event."""
        if self.listeners:
            self.fire(control.name if control is not None else "", event)
        events = control.events if control is not None else self.form.events
        name = events.get(event)
        if not name or name == motion.ANIMATION_ONLY:
            return None
        handler = self.handlers.get(name)
        owner = control.name if control is not None else self.form.name
        if handler is None:
            self.error = f"{owner}.{event}: handler {name}() not found in the code file"
            return None
        sender = ControlProxy(control, self) if control is not None else self.proxy
        if self.log is not None and event not in _QUIET_EVENTS:
            shown = "" if value is None else f" ({value!r})"[:80]
            self.log("event", f"{owner}.{event}{shown} → {name}()")
        try:
            return handler(self.proxy, Event(sender, event, value))
        except Exception:  # noqa: BLE001 - a handler bug must not kill the app
            self.error = f"{owner}.{event}: " + traceback.format_exc(limit=-1).strip().splitlines()[-1]
            if self.log is not None:
                kind, err, tb = sys.exc_info()
                frames = traceback.format_exception(kind, err, tb.tb_next if tb is not None else None)
                self.log("error", f"{owner}.{event}: {name}() raised\n" + "".join(frames).rstrip())
            else:
                traceback.print_exc()
            return None

    def call(self, name: str, event: str, value: Any = None) -> Any:
        """Calls the handler of ``event`` of control ``name`` here and now and lets its exceptions through (a
        Background worker's ``work`` runs like this, in its thread)."""
        control = self.form[name]
        handler = self.handlers.get(control.events.get(event, ""))
        if handler is None:
            raise LookupError(f"{name}.{event}: handler {control.events.get(event)}() not found in the code file")
        return handler(self.proxy, Event(ControlProxy(control, self), event, value))

    # -- data binding and validation -----------------------------------------
    def _fill_data(self) -> None:
        """Starts ``data`` as a dict when some control is bound and nothing was passed, and copies the designed
        value of each bound input whose field is missing, so ``form.data`` always holds every field."""
        bound = [c for c in self.form.controls if c.bind and _binding.two_way(c.type) and _binding.is_path(c.bind)]
        if self.data is None and any(c.bind for c in self.form.controls):
            self.data = {}
        for control in bound:
            if not _binding.has(self.data, control.bind):
                prop = _binding.bound_prop(control.type)
                spec = _components.spec(control.type)
                try:
                    _binding.write(self.data, control.bind, control.props.get(prop, spec.defaults().get(prop)))
                except (AttributeError, TypeError):
                    pass  # read-only data: the control keeps its own value

    def set_data(self, data: Any) -> None:
        """Shows ``data`` in the bound controls (``form.data = record``) and clears the validation messages."""
        self.data = data
        self.errors.clear()
        self._fill_data()

    def changed(self, control: Control, prop: str, value: Any) -> None:
        """The user changed ``prop`` of ``control``: writes it to the bound field and re-checks its rules."""
        if control.bind and prop == _binding.bound_prop(control.type) and _binding.two_way(control.type) \
                and _binding.is_path(control.bind) and self.data is not None:
            try:
                _binding.write(self.data, control.bind, value)
            except (AttributeError, TypeError) as err:
                self.error = f"{control.name}.bind = {control.bind}: {err}"
        if control.rules:
            self._check(control)
        if self.services:
            nonvisual.changed(self, control.name)

    def _check(self, control: Control) -> bool:
        prop = _binding.bound_prop(control.type)
        if prop is None:
            return True
        value = control.props.get(prop, _components.spec(control.type).defaults().get(prop))
        message = _binding.check(value, control.rules, control.type)
        if message is None:
            self.errors.pop(control.name, None)
            return True
        self.errors[control.name] = message
        if self.listeners:
            self.fire(control.name, "invalid")
        return False

    def validate(self, names: Optional[list] = None) -> bool:
        """Checks the rules of the controls ``names`` (every visible, enabled one by default); returns whether
        they all passed."""
        hidden: set = set()
        ok = True
        for control, _depth in self.form.walk():
            if not control.visible or (control.parent and control.parent in hidden):
                hidden.add(control.name)
                continue
            if names is not None and control.name not in names:
                continue
            if not control.rules or not control.enabled:
                self.errors.pop(control.name, None)
                continue
            ok = self._check(control) and ok
        return ok

    def set_error(self, name: str, message: Optional[str]) -> None:
        """Shows ``message`` under control ``name`` (``None`` or ``""`` clears it)."""
        if message:
            self.errors[name] = str(message)
        else:
            self.errors.pop(name, None)

    def _apply_binding(self, control: Control) -> None:
        """Copies the bound field (or expression) of ``data`` into the control's bound property."""
        prop = _binding.bound_prop(control.type)
        if prop is None or self.data is None:
            return
        try:
            control.props[prop] = _binding.evaluate(control.bind, self.data, form=self.proxy)
        except (KeyError, AttributeError, IndexError):
            if not _binding.is_path(control.bind):
                self.error = f"{control.name}.bind = {control.bind}: {sys.exc_info()[1]!r}"
        except Exception as err:  # noqa: BLE001 - shown in the window
            self.error = f"{control.name}.bind = {control.bind}: {type(err).__name__}: {err}"

    def load(self) -> Any:
        """Raises the form's ``load`` event the first time it is called; returns the handler's result."""
        if self.loaded:
            return None
        self.loaded = True
        nonvisual.start(self)
        return self.dispatch(None, "load")

    def key(self, combo: str) -> Any:
        """A key press: the Shortcut controls with those keys raise ``activate``, then the form its ``key``
        event. Returns the commands of the handlers."""
        results = [service.handle(combo) for service in self.services.values()
                   if isinstance(service, _services.Shortcut)]
        results.append(self.dispatch(None, "key", combo))
        results = [r for r in results if r is not None]
        if not results:
            return None
        return results[0] if len(results) == 1 else results

    def closed(self) -> None:
        """The window is closing: saves what Settings controls remember and stops the services."""
        nonvisual.stop(self)

    def subscriptions(self):
        """The subscriptions of the services that need one (running timers, watched clipboards) and have an
        event wired, and of the timeline player."""
        subs = []
        for service in self.services.values():
            if any(service.handles(e) for e in service.events):
                subs.extend(service.subscriptions())
        return subs + self.player.subscriptions()

    def _wrap_mouse(self, control: Control, widget: Any) -> Any:
        wired = {e: control.events.get(e) for e in _components.COMMON_EVENTS}
        if not any(wired.values()):
            return widget
        return _core.mouse_area(
            widget,
            on_enter=self.ctx.on(control, "mouse_enter") if wired["mouse_enter"] else None,
            on_exit=self.ctx.on(control, "mouse_leave") if wired["mouse_leave"] else None,
            on_right_press=self.ctx.on(control, "right_click") if wired["right_click"] else None,
        )

    def view(self) -> Any:
        """Draws the running form: its background, every visible control at its laid-out position and, after a
        handler error, the error callout."""
        t = self.theme
        size = self.size
        layers = [_core.container(width="fill", height="fill", bg=t.background)]
        form = self.form
        painted = styling.background_layer(form.style, t)
        if painted is not None:
            layers.append(painted)
        rects = _layout.resolve(form, size)
        bubbles: list = []  # validation messages, over every control
        # the form's tab order: each listed control (and the fields inside it) takes its place for Tab
        self._tab_index = {name: i for i, name in enumerate(form.tab_order, start=1)}
        layers.extend(self._draw(None, rects, bubbles))
        layers.extend(bubbles)
        if self.error:
            layers.append(_core.container(
                ui.callout("Event handler error", self.error, tint="error", on_dismiss=self._dismiss_error,
                           theme=t),
                width="fill", height="fill", align_y="end", padding=12))
        return styling.apply_global(_core.stack(layers, width="fill", height="fill"), form.style, t, background=False)

    def _draw(self, parent: Optional[Control], rects: Dict[str, Tuple[float, float, float, float]],
              bubbles: list) -> list:
        """The pinned widgets of every visible control inside ``parent`` (the form when ``None``) at ``rects``.
        A dock draws what is inside it itself (see ``_dock``)."""
        t = self.theme
        form = self.form
        layers = []
        hidden: set = set()
        docks: set = set()
        for control, _depth in form.walk(parent.name if parent is not None else None):
            spec = _components.spec(control.type)
            if not control.visible or (control.parent and control.parent in hidden):
                hidden.add(control.name)
                continue
            if control.parent in docks:
                docks.add(control.name)
                continue
            if not spec.visual:
                continue
            if control.bind:
                self._apply_binding(control)
            x, y, w, h = rects[control.name]
            placed = Control(**{**control.__dict__, "x": x, "y": y, "width": w, "height": h})
            if spec.container == "dock":
                docks.add(control.name)
                widget = self._wrap_mouse(control, _components.styled(self._dock(placed), control, self.ctx))
            else:
                widget = self._wrap_mouse(control, _components.render(placed, self.ctx))
            played = timeline.targets(self.player, form, control.name)
            if played:
                widget = widget.animate(*played)
            remember_instance(self, control, self.ctx)
            message = self.errors.get(control.name)
            if message:
                widget = _core.container(widget, width=w, height=h, border_color=t.error, border_width=1,
                                         radius=t.radius_sm)
            index = self._tab_index.get(control.name)
            if index is not None:
                widget = _core.focusable(widget, tab_index=index)
            layers.append(_core.pin(widget, x=x, y=y))
            if message:
                bubbles.append(_core.pin(_core.container(
                    _core.text(message, size=max(t.ui_font_size - 2, 10), color=t.error),
                    padding=(3, 8), bg=t.elevated, border_color=t.error, border_width=1, radius=t.radius_sm,
                ), x=x, y=y + h + 4))
        return layers

    def _dock(self, control: Control) -> Any:
        """A live ``pz.Dock`` for a Dock control: each Dock panel becomes a tab on its side (or the center) with
        what is inside it, laid out by its anchors at the size the dock gives it."""
        from ..dock import Dock, DockPanel

        t = self.theme
        panels = [p for p in self.form.children(control.name) if p.visible and p.type == "dock_panel"]

        def content(panel: Control) -> Any:
            def draw(width: float, height: float) -> Any:
                rects: Dict[str, Tuple[float, float, float, float]] = {}
                _layout.place(self.form, panel, (0.0, 0.0, width, height), (panel.width, panel.height), rects)
                bubbles: list = []
                body = _components.render(Control(**{**panel.__dict__, "x": 0, "y": 0, "width": width,
                                                     "height": height}), self.ctx)
                return _core.stack([_core.pin(self._wrap_mouse(panel, body), x=0, y=0),
                                    *self._draw(panel, rects, bubbles), *bubbles], width="fill", height="fill")

            return _core.responsive(draw)

        center = [p for p in panels if _layout.dock_side(p) == "center"]
        docked = [p for p in panels if _layout.dock_side(p) != "center"]
        props = {**_components.spec(control.type).defaults(), **control.props}
        saved = dict(props.get("layout") or {})
        # the top-most panel of each side is its tab shown first, as in the designer
        active = {_layout.dock_side(p): p.name for p in docked}
        layout = {**saved, "active": {**active, **saved.get("active", {})},
                  "sizes": {**{side: float(props.get(f"{side}_size") or 0) or 200.0
                               for side in ("left", "right", "top", "bottom")}, **saved.get("sizes", {})}}
        on_layout = self.ctx.on(control, "layout", "layout")
        return Dock(
            center=_core.stack([content(p) for p in center], width="fill", height="fill") if center
            else _core.container(width="fill", height="fill", bg=t.editor),
            panels=[DockPanel(p.name, str(p.props.get("title") or p.name), content(p),
                              icon=p.props.get("icon") or None, side=_layout.dock_side(p)) for p in docked],
            layout=layout, on_layout=lambda e: on_layout(e.value), key=self.ctx.key(control))

    def _dismiss_error(self) -> None:
        self.error = None

    def reload(self, path: Union[str, Path]) -> bool:
        """Swaps in the form and handlers saved at ``path``, keeping what the user typed or chose.

        Used by hot reload: layout, properties and code come from the files, while the
        value of each control that still exists (its text, check state, selection...)
        survives. On error the running form is left as it was and the error is shown.
        """
        try:
            form = load(path)
            handlers = load_handlers(path, form)
        except Exception as err:  # noqa: BLE001 - shown in the window until the next save
            self.error = f"Reload failed: {type(err).__name__}: {err}"
            return False
        for control in form.controls:
            old = self.form.get(control.name)
            if old is not None and old.type == control.type:
                for prop in _VALUE_PROPS.get(control.type, ()):
                    if prop in old.props:
                        control.props[prop] = old.props[prop]
        nonvisual.stop(self)
        self.form = form
        self.design_size = (form.width, form.height)
        self.handlers = handlers
        self.theme = theme_for(form, self.preview_theme)
        self.ctx = LiveContext(self)
        self.window.theme = self.theme
        self.player = timeline.reload_player(self.player, form)
        self.listeners = self._listen()
        self.services = nonvisual.build_all(self)
        if self.loaded:
            nonvisual.start(self)
        self.error = None
        return True


class _FormHost:
    """Shared ``Window``/``App`` plumbing for a form."""

    runtime: FormRuntime

    def _host(self, form: Form, handlers: Optional[Dict[str, Any]], path: Optional[Union[str, Path]] = None,
              data: Any = None, theme: Optional[str] = None, language: Optional[str] = None) -> None:
        self.runtime = FormRuntime(form, handlers, window=self, path=path, data=data,  # type: ignore[arg-type]
                                   theme=theme, language=language)
        self.size = (form.width, form.height)
        self.resizable = form.resizable
        self.theme = self.runtime.theme

    @property
    def form(self) -> FormProxy:
        return self.runtime.proxy

    @property  # type: ignore[override]
    def title(self) -> str:
        return _binding.translate(self.runtime.form.title, self.runtime.language)

    @title.setter
    def title(self, value: str) -> None:  # pragma: no cover - set by Window defaults
        pass

    def view(self):
        return self.runtime.view()

    def update(self, message: Any) -> Any:
        return None

    def subscriptions(self):
        return self.runtime.subscriptions()

    def on_key(self, combo: str) -> Any:
        # ``None`` when no handler took the key, so Tab still moves the focus between the fields
        return self.runtime.key(combo)

    def on_resize(self, width: float, height: float) -> Any:
        return self.runtime.dispatch(None, "resize", (width, height))

    def on_close(self) -> Optional[bool]:
        if self.runtime.dispatch(None, "close") is False:
            return False
        self.runtime.closed()
        return None


class FormApp(_FormHost, App):
    """A form as the main application window.

    ``path`` (set by ``open_form``) is the ``.pzform`` file; with hot reload on, saving it
    or its handlers module updates the running window.
    """

    path: Optional[Path] = None

    def __init__(self, form: Form, handlers: Optional[Dict[str, Any]] = None,
                 path: Optional[Union[str, Path]] = None) -> None:
        self._host(form, handlers, path)
        self.path = Path(path) if path else None

    def on_start(self) -> Any:
        """Watches the form and its handlers module for hot reload (when it is on), then raises ``load``."""
        reloader = hot_reload.current()
        if reloader is not None and self.path is not None:
            for file in (self.path, code_path(self.path, self.runtime.form)):
                reloader.watch(file, self._reload)
        return self.runtime.load()

    def _reload(self, _changed: Path) -> None:
        if self.path is not None:
            self.runtime.reload(self.path)


class FormWindow(_FormHost, Window):
    """A form in an extra window (``form.open(...)``, ``designer.open_window`` and the designer's preview)."""

    def __init__(self, form: Form, handlers: Optional[Dict[str, Any]] = None, *,
                 path: Optional[Union[str, Path]] = None, data: Any = None, theme: Optional[str] = None,
                 language: Optional[str] = None) -> None:
        self._host(form, handlers, path, data, theme, language)

    def on_open(self) -> Any:
        """Raises the form's ``load`` event when the window opens."""
        return self.runtime.load()


def load_handlers(path: Union[str, Path], form: Optional[Form] = None) -> Dict[str, Any]:
    """Imports the handlers module of the form at ``path`` (empty if it has none)."""
    module_path = code_path(path, form)
    if not module_path.exists():
        return {}
    return _code.handlers(_code.load_module(module_path))


def open_form(path: Union[str, Path]) -> FormApp:
    """Loads a ``.pzform`` and its handlers into a ``FormApp`` ready to ``run()`` or ``screenshot()``.

    If the form belongs to a project (see ``pyzed.project``), the project is activated first
    so its handlers can import the backend and the packages of its ``.venv``.
    """
    from ..project import activate_for

    from .scene import discover_project

    activate_for(path)
    discover_project(path, fresh=True)  # designed components and the project's pz.Component classes
    form = load(path)
    return FormApp(form, load_handlers(path, form), path)


def resolve(name: Union[str, Path], folder: Optional[Union[str, Path]] = None) -> Path:
    """The ``.pzform`` file for ``name``: adds the suffix and looks next to ``folder``, then in the project's UI folder."""
    path = Path(name)
    if not path.suffix:
        path = path.with_suffix(SUFFIX)
    if path.is_absolute():
        return path
    candidates = [Path(folder) / path] if folder is not None else []
    from ..project import find

    project = find(Path(folder) if folder is not None else Path.cwd())
    if project is not None:
        candidates.append(project.ui_dir / path)
    candidates.append(path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"form not found: {name} (looked in {', '.join(str(c.parent) for c in candidates)})")


def form_window(form: Union[str, Path, Form], *, data: Any = None, handlers: Optional[Dict[str, Any]] = None,
                folder: Optional[Union[str, Path]] = None) -> FormWindow:
    """A ``FormWindow`` for ``form`` (a ``.pzform`` path or name, or a ``Form``), ready to open.

    A form loaded from a file gets its handlers module; a ``Form`` built in code uses
    ``handlers`` (a dict of functions). ``data`` reaches the new form as ``form.data``.
    """
    path: Optional[Path] = None
    if not isinstance(form, Form):
        path = resolve(form, folder)
        form = load(path)
        if handlers is None:
            handlers = load_handlers(path, form)
    return FormWindow(form, handlers, path=path, data=data)


def open_window(form: Union[str, Path, Form], *, data: Any = None, handlers: Optional[Dict[str, Any]] = None,
                folder: Optional[Union[str, Path]] = None) -> _core.Command:
    """A ``Command`` that opens ``form`` in a new window (see ``form_window`` for the arguments)."""
    return _core.Command.open_window(form_window(form, data=data, handlers=handlers, folder=folder))


def run(path: Union[str, Path], *, reload: Optional[bool] = None, splash: Any = None) -> None:
    """Runs the form at ``path`` with all the logic wired in the designer.

    ``reload=True`` turns on hot reload: saving the form (from the designer or by hand)
    or its handlers module updates the running window without restarting it. ``None``
    follows ``PYZED_RELOAD``, like ``pz.run``. ``splash`` (a ``pz.Splash``) is shown before
    the form's window opens (see ``App.splash``).
    """
    if Path(path).suffix == ".pzcomp":  # a designed component on its own
        from .scene_panel import run_file

        return run_file(path)
    if Path(path).suffix == ".pzshad":  # a shader graph filling a window
        from ..shading.runtime import run_file as run_shader

        return run_shader(path)
    app = open_form(path)
    if splash is not None:
        app.splash = splash
    if app.rendering is None:  # the [tool.pyzed.rendering] of the form's project, wherever it starts from
        app.rendering = _rendering.find(Path(path).resolve().parent)
    _run_app(app, reload=reload)
    if os.environ.get("PYZED_DESIGNER_RUN"):
        # Started by Run in Pyzed Design: end when the window closes, even if a thread of the app is still
        # running, so the designer sees the run finish and can start it again.
        for stream in (sys.stdout, sys.stderr):  # None in an app without a console (Windows)
            if stream is not None:
                stream.flush()
        os._exit(0)
