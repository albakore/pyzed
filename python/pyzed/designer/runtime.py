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

import re
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional, Tuple, Union

from .. import _core, hot_reload, ui
from ..app import App, Window
from ..app import run as _run_app
from ..theme import Theme, themes
from . import code as _code
from . import components as _components
from .geometry import anchored
from .model import SUFFIX, Control, Form, code_path, load, save

_FIELDS = ("x", "y", "width", "height", "visible", "enabled", "anchor")

#: Properties the user changes by interacting; hot reload keeps them.
_VALUE_PROPS = {
    "input": ("text",), "text_area": ("text",), "checkbox": ("checked",), "switch": ("checked",),
    "radio": ("selected",), "select": ("selected",), "slider": ("value",), "number": ("value",),
    "list_box": ("selected",),
}


def theme_for(form: Form) -> Theme:
    """The theme a form runs with: its base theme plus accent, radius, font and background tweaks."""
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
    return theme.derive(**changes) if changes else theme


@dataclass
class Event:
    """What a handler receives besides the form: who raised it, which event and its value."""

    sender: Any
    name: str
    value: Any = None


class ControlProxy:
    """A control of the running form; its properties read and write like attributes."""

    __slots__ = ("_control", "_runtime")

    def __init__(self, control: Control, runtime: "FormRuntime") -> None:
        object.__setattr__(self, "_control", control)
        object.__setattr__(self, "_runtime", runtime)

    @property
    def name(self) -> str:
        return self._control.name

    @property
    def type(self) -> str:  # noqa: A003
        return self._control.type

    def __getattr__(self, key: str) -> Any:
        control = self._control
        if key in _FIELDS:
            return getattr(control, key)
        if key in control.props:
            return control.props[key]
        default = _components.get(control.type).defaults()
        if key in default:
            return default[key]
        raise AttributeError(f"{control.type} {control.name!r} has no property {key!r}")

    def __setattr__(self, key: str, value: Any) -> None:
        if key in _FIELDS:
            setattr(self._control, key, value)
        else:
            self._control.props[key] = value

    def show(self) -> None:
        self._control.visible = True

    def hide(self) -> None:
        self._control.visible = False

    def focus(self) -> _core.Command:
        """A command that focuses this control (text boxes and text areas)."""
        return _core.Command.focus(self._runtime.ctx.key(self._control))

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
        else:
            raise AttributeError(f"cannot set {key!r} on the form; use form.<control>.<property>")

    @property
    def name(self) -> str:
        return self._runtime.form.name

    @property
    def title(self) -> str:
        return self._runtime.form.title

    @property
    def size(self) -> Tuple[float, float]:
        return self._runtime.size

    @property
    def window(self) -> Window:
        """The Pyzed window running this form (for ``Command`` helpers)."""
        return self._runtime.window

    @property
    def data(self) -> Any:
        """What the form that opened this one passed as ``data=`` (``None`` otherwise)."""
        return self._runtime.data

    def close(self) -> _core.Command:
        return self._runtime.window.close()

    def open(self, form: Union[str, Path, Form], *, data: Any = None) -> _core.Command:
        """Opens another form in a new window; return the result from a handler::

            def settings_click(form, event):
                return form.open("settings", data=form.name_input.text)

        ``form`` is a name (``"settings"``) or path, relative to this form's folder, or a
        ``Form`` built in code. The new form reads ``data`` as ``form.data``.
        """
        base = self._runtime.path.parent if self._runtime.path is not None else None
        return open_window(form, data=data, folder=base)


class LiveContext(_components.RenderContext):
    live = True

    def __init__(self, runtime: "FormRuntime") -> None:
        super().__init__(runtime.theme, runtime.form.name)
        self.runtime = runtime

    def on(self, control: Control, event: str, prop: Optional[str] = None) -> Callable[..., Any]:
        runtime = self.runtime

        def callback(*args: Any) -> Any:
            # ``control`` may be a positioned copy made for drawing; state lives on the form's own.
            target = runtime.form.get(control.name) or control
            value = args[0] if len(args) == 1 else (args or None)
            if prop is not None:
                target.props[prop] = value
            return runtime.dispatch(target, event, value)

        return callback


class FormRuntime:
    """The engine behind ``FormApp``/``FormWindow``: state, event dispatch and drawing."""

    def __init__(self, form: Form, handlers: Optional[Dict[str, Any]] = None, *, window: Window,
                 path: Optional[Union[str, Path]] = None, data: Any = None) -> None:
        self.form = form.copy()
        self.path: Optional[Path] = Path(path) if path else None
        self.data = data
        self.design_size = (form.width, form.height)
        self.handlers = dict(handlers or {})
        self.window = window
        self.theme = theme_for(form)
        self.ctx = LiveContext(self)
        self.proxy = FormProxy(self)
        self.error: Optional[str] = None
        self.loaded = False

    @property
    def size(self) -> Tuple[float, float]:
        return tuple(self.window.window_size or self.design_size)  # type: ignore[return-value]

    def dispatch(self, control: Optional[Control], event: str, value: Any = None) -> Any:
        """Calls the handler wired to ``event`` of ``control`` (or of the form when ``None``)."""
        events = control.events if control is not None else self.form.events
        name = events.get(event)
        if not name:
            return None
        handler = self.handlers.get(name)
        owner = control.name if control is not None else self.form.name
        if handler is None:
            self.error = f"{owner}.{event}: handler {name}() not found in the code file"
            return None
        sender = ControlProxy(control, self) if control is not None else self.proxy
        try:
            return handler(self.proxy, Event(sender, event, value))
        except Exception:  # noqa: BLE001 - a handler bug must not kill the app
            self.error = f"{owner}.{event}: " + traceback.format_exc(limit=-1).strip().splitlines()[-1]
            traceback.print_exc()
            return None

    def load(self) -> Any:
        if self.loaded:
            return None
        self.loaded = True
        return self.dispatch(None, "load")

    def subscriptions(self):
        subs = []
        for c in self.form.controls:
            if c.type != "timer" or not c.events.get("tick"):
                continue
            props = {**_components.get("timer").defaults(), **c.props}
            if props.get("running") and c.enabled:
                interval = max(float(props.get("interval") or 1000), 10) / 1000
                subs.append(_core.every(interval, self.ctx.on(c, "tick"), key=f"{self.form.name}:{c.name}"))
        return subs

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
        t = self.theme
        size = self.size
        layers = [_core.container(width="fill", height="fill", bg=t.background)]
        for control in self.form.controls:
            spec = _components.get(control.type)
            if not control.visible or not spec.visual:
                continue
            x, y, w, h = anchored(control, self.design_size, size)
            placed = Control(**{**control.__dict__, "x": x, "y": y, "width": w, "height": h})
            widget = self._wrap_mouse(control, _components.render(placed, self.ctx))
            layers.append(_core.pin(widget, x=x, y=y))
        if self.error:
            layers.append(_core.container(
                ui.callout("Event handler error", self.error, tint="error", on_dismiss=self._dismiss_error,
                           theme=t),
                width="fill", height="fill", align_y="end", padding=12))
        return _core.stack(layers, width="fill", height="fill")

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
        self.form = form
        self.design_size = (form.width, form.height)
        self.handlers = handlers
        self.theme = theme_for(form)
        self.ctx = LiveContext(self)
        self.window.theme = self.theme
        self.error = None
        return True


class _FormHost:
    """Shared ``Window``/``App`` plumbing for a form."""

    runtime: FormRuntime

    def _host(self, form: Form, handlers: Optional[Dict[str, Any]], path: Optional[Union[str, Path]] = None,
              data: Any = None) -> None:
        self.runtime = FormRuntime(form, handlers, window=self, path=path, data=data)  # type: ignore[arg-type]
        self.size = (form.width, form.height)
        self.resizable = form.resizable
        self.theme = self.runtime.theme

    @property
    def form(self) -> FormProxy:
        return self.runtime.proxy

    @property  # type: ignore[override]
    def title(self) -> str:
        return self.runtime.form.title

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
        result = self.runtime.dispatch(None, "key", combo)
        return [] if result is None else result

    def on_resize(self, width: float, height: float) -> Any:
        return self.runtime.dispatch(None, "resize", (width, height))

    def on_close(self) -> Optional[bool]:
        return False if self.runtime.dispatch(None, "close") is False else None


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
                 path: Optional[Union[str, Path]] = None, data: Any = None) -> None:
        self._host(form, handlers, path, data)

    def on_open(self) -> Any:
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

    activate_for(path)
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


def new_form(path: Union[str, Path], *, title: Optional[str] = None, width: float = 480, height: float = 320,
             overwrite: bool = False) -> Path:
    """Creates an empty ``.pzform`` and its handlers module; returns the form path.

    The form's name comes from the file name (``settings.pzform`` -> ``Settings``).
    """
    path = Path(path)
    if not path.suffix:
        path = path.with_suffix(SUFFIX)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists")
    name = "".join(part.capitalize() for part in re.split(r"[^0-9a-zA-Z]+", path.stem) if part) or "Form1"
    form = Form(name=name, title=title or name, width=width, height=height)
    save(form, path)
    module = code_path(path, form)
    if not module.exists():
        module.write_text(_code.new_module(name), encoding="utf-8")
    return path


def run(path: Union[str, Path], *, reload: Optional[bool] = None) -> None:
    """Runs the form at ``path`` with all the logic wired in the designer.

    ``reload=True`` turns on hot reload: saving the form (from the designer or by hand)
    or its handlers module updates the running window without restarting it. ``None``
    follows ``PYZED_RELOAD``, like ``pz.run``.
    """
    _run_app(open_form(path), reload=reload)
