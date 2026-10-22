"""The non-visual components of a running form: each one is a ``pyzed.services`` object.

A Timer, a File watcher, a Process... placed on a form draw nothing. ``build`` makes the
service behind each of them, gives it the control's properties and wires its events to the
handlers of the form; ``ControlProxy`` then forwards to it what handlers read, set and call
(``form.process1.start()``, ``form.http1.url = ...``). The properties a service does not have
(``autostart``, ``send_on_load``, ``remember``...) are read by the form when it opens.

Add one of your own with ``register``: a function that makes the service from the control.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .. import services as _services
from .. import system as _system
from . import components as _components
from .model import Control

if TYPE_CHECKING:
    from .runtime import FormRuntime

#: Makes the service of a non-visual control, by component type.
FACTORIES: Dict[str, Callable[[Control], _services.Service]] = {
    "timer": lambda c: _services.Timer(running=False),  # it starts when the form opens
    "shortcut": lambda c: _services.Shortcut(),
    "file_watcher": lambda c: _services.FileWatcher(),
    "process": lambda c: _services.Process(),
    "worker": lambda c: _services.Worker(),
    "http_request": lambda c: _services.HttpRequest(),
    "clipboard": lambda c: _services.Clipboard(),
    "settings": lambda c: _services.Settings(),
    "file_dialog": lambda c: _services.FileDialog(),
    "notification": lambda c: _services.Notification(),
    "system_info": lambda c: _system.SystemInfo(),
    "launcher": lambda c: _system.Launcher(),
    "network_monitor": lambda c: _system.NetworkMonitor(),
    "power_monitor": lambda c: _system.PowerMonitor(),
}

#: Properties whose service attribute has another name (``(type, property)`` -> attribute).
ALIASES: Dict[tuple, str] = {("settings", "file"): "name"}

#: Properties applied when the form opens rather than when it is built (they start something).
ON_LOAD = frozenset({"running"})


def register(type_: str, factory: Callable[[Control], _services.Service]) -> None:
    """Makes ``factory(control)`` the service behind the non-visual component ``type_``."""
    FACTORIES[type_] = factory


def attribute(control: Control, prop: str) -> str:
    """The service attribute a property of ``control`` sets."""
    return ALIASES.get((control.type, prop), prop)


def props(control: Control) -> Dict[str, Any]:
    """The control's properties, with the component's defaults for the ones it does not set."""
    return {**_components.spec(control.type).defaults(), **control.props}


def _value(control: Control, prop: str, value: Any) -> Any:
    if control.type in ("settings", "process", "file_dialog", "system_info") and prop in ("file", "directory",
                                                                                         "disk_path"):
        return value or None
    return value


def apply(service: _services.Service, control: Control, prop: str, value: Any) -> None:
    """Sets property ``prop`` of ``control`` on its service, when the service has it."""
    name = attribute(control, prop)
    if name.startswith("_") or not hasattr(service, name) or callable(getattr(service, name)):
        return
    try:
        setattr(service, name, _value(control, prop, value))
    except (AttributeError, TypeError, ValueError):
        pass  # a read-only attribute or a wrong value: the service keeps its own


def build(control: Control, runtime: "FormRuntime") -> Optional[_services.Service]:
    """The service of a non-visual ``control``, configured and wired to the form's handlers (``None`` when the
    component has no service)."""
    factory = FACTORIES.get(control.type)
    if factory is None:
        return None
    service = factory(control)
    if isinstance(service, (_services.Timer, _services.Clipboard)):
        service.key = f"{runtime.form.name}:{control.name}"
    for prop, value in props(control).items():
        if prop not in ON_LOAD:
            apply(service, control, prop, value)
    if isinstance(service, _services.Settings) and not service.name:
        service.name = f"{runtime.form.name}.{control.name}"
    service.enabled = control.enabled
    name = control.name
    for event in service.events:
        if control.events.get(event):
            service.on(event, lambda value, e=event: runtime.dispatch(runtime.form.get(name), e, value))
    if isinstance(service, _services.Worker) and control.events.get("work"):
        service.work = lambda value: runtime.call(name, "work", value)
    return service


def build_all(runtime: "FormRuntime") -> Dict[str, _services.Service]:
    """The services of every non-visual control of the running form, by control name."""
    out: Dict[str, _services.Service] = {}
    for control in runtime.form.controls:
        if not _components.spec(control.type).visual:
            service = build(control, runtime)
            if service is not None:
                out[control.name] = service
    return out


def start(runtime: "FormRuntime") -> List[Any]:
    """The form opened: restores remembered values, then starts what should run (timers, watchers, programs
    and requests marked to start). Returns the commands to run."""
    form = runtime.form
    for name, service in runtime.services.items():
        if isinstance(service, _services.Settings):
            restore(runtime, form[name], service)
    for name, service in runtime.services.items():
        control = form[name]
        values = props(control)
        for prop in ON_LOAD:
            if prop in values:
                apply(service, control, prop, values[prop])
        if isinstance(service, _services.Timer):
            service.count = 0
        if isinstance(service, _system.SystemInfo) and control.enabled:
            service.start()  # a first ``update`` with the facts, then more every ``interval``
        if isinstance(service, _services.Process) and values.get("autostart") and control.enabled:
            service.start()
        if isinstance(service, _services.HttpRequest) and values.get("send_on_load") and control.enabled:
            service.send()
    return []


def stop(runtime: "FormRuntime") -> None:
    """The form closed: saves remembered values and stops watchers, programs and workers."""
    for name, service in runtime.services.items():
        if isinstance(service, _services.Settings):
            control = runtime.form.get(name)
            if control is not None:
                remember(runtime, control, service)
        service.stop()


# -- remembering control values ---------------------------------------------------------------------------------------
def remembered(control: Control) -> List[str]:
    """The names of the controls a Settings component keeps between runs."""
    value = props(control).get("remember") or ""
    names = value if isinstance(value, (list, tuple)) else str(value).replace(",", "\n").splitlines()
    return [n.strip() for n in names if n.strip()]


def _value_prop(control: Control) -> Optional[str]:
    from . import binding

    return binding.bound_prop(control.type)


def restore(runtime: "FormRuntime", control: Control, settings: _services.Settings) -> None:
    """Gives each remembered control the value it had when the form last closed."""
    saved = settings.get("controls") or {}
    if not isinstance(saved, dict):
        return
    for name in remembered(control):
        target = runtime.form.get(name)
        prop = _value_prop(target) if target is not None else None
        if prop is not None and name in saved:
            target.props[prop] = saved[name]


def remember(runtime: "FormRuntime", control: Control, settings: _services.Settings,
             only: Optional[str] = None) -> None:
    """Saves the value of the remembered controls (or of the control ``only``)."""
    names = remembered(control)
    if only is not None:
        if only not in names:
            return
        names = [only]
    saved = dict(settings.get("controls") or {})
    for name in names:
        target = runtime.form.get(name)
        prop = _value_prop(target) if target is not None else None
        if prop is not None:
            saved[name] = target.props.get(prop, _components.spec(target.type).defaults().get(prop))
    settings.set("controls", saved)


def changed(runtime: "FormRuntime", name: str) -> None:
    """The user changed control ``name``: Settings components that remember it save it."""
    for owner, service in runtime.services.items():
        if isinstance(service, _services.Settings):
            control = runtime.form.get(owner)
            if control is not None:
                remember(runtime, control, service, only=name)
