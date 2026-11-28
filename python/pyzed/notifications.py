"""Native desktop notifications: ``pz.notify(title, body)``.

They are the system's own: the notification server over D-Bus on Linux (GNOME, KDE, Cinnamon,
XFCE, dunst, mako...), toasts on Windows 10 and 11 and the Notification Center on macOS. They can
have buttons, and a click can open a page of the app's routes::

    pz.notify("Order shipped", "Your monitor is on its way", href="/orders/3")

    pz.notify("New message", "Ana: are we still on for today?",
              actions={"reply": "Reply", "/inbox": "Open inbox"},
              on_action=lambda action: print("pressed", action))

A click brings the window to the front (``href`` also goes to that page); a button whose id starts
with ``/``, ``?`` or ``.`` goes to that address too. The callbacks run on the UI thread, so they can
change the app's state like any event handler (or return a ``Command``).

Where there is no notification server (a bare Linux session, Android), ``notify`` falls back to
``notify-send``, ``osascript`` or PowerShell, without buttons or clicks; ``notification.native``
says which one showed it.
"""

from __future__ import annotations

import itertools
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from . import _core

__all__ = ["DesktopNotification", "app_id", "app_name", "capabilities", "notify", "supported"]

#: The name the system shows the notifications under (the window's title, or "Pyzed").
app_name: Optional[str] = None
#: The app's identity: the desktop file's name on Linux (``"shop"`` for ``shop.desktop``), the
#: AppUserModelID on Windows and the bundle identifier on macOS. Without it, Windows shows them as
#: PowerShell's and macOS as the terminal's, which works from a script with nothing installed.
app_id: Optional[str] = None

URGENCIES = {"low": 0, "normal": 1, "critical": 2}
Actions = Union[Mapping[str, str], Sequence[Union[str, Tuple[str, str]]], None]
_ids = itertools.count(1)
_by_tag: Dict[str, "DesktopNotification"] = {}
_icons: Dict[int, str] = {}
_lock = threading.Lock()


def supported() -> bool:
    """Whether this system shows native notifications (with buttons and clicks)."""
    try:
        return bool(_core.notify_supported())
    except Exception:  # noqa: BLE001 - an old core or no session bus
        return False


def capabilities() -> List[str]:
    """What the notifications can do here: ``"actions"``, ``"body"``, ``"icon"``, ``"sound"``..."""
    try:
        return list(_core.notify_capabilities())
    except Exception:  # noqa: BLE001
        return []


def _is_href(action: str) -> bool:
    return action.startswith(("/", "?", "."))


def _actions(actions: Actions) -> List[Tuple[str, str]]:
    if not actions:
        return []
    if isinstance(actions, Mapping):
        return [(str(k), str(v)) for k, v in actions.items()]
    out = []
    for item in actions:
        if isinstance(item, (tuple, list)):
            out.append((str(item[0]), str(item[1])))
        else:
            out.append((str(item), str(item)))
    return out


def _path(value: Any) -> Optional[str]:
    """An absolute path for an image given as a path or as bytes (written to a temporary file)."""
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        key = hash(bytes(value))
        with _lock:
            if key not in _icons:
                handle = tempfile.NamedTemporaryFile(prefix="pyzed-notify-", suffix=".png", delete=False)
                with handle:
                    handle.write(value)
                _icons[key] = handle.name
            return _icons[key]
    return str(Path(value).expanduser().resolve())


def _post(callback: Callable[[], Any]) -> None:
    """Runs ``callback`` on the UI thread of the running app (right here when none runs)."""
    try:
        _core.post(callback)
    except RuntimeError:
        callback()


def _open(href: Optional[str]) -> Any:
    """Goes to ``href`` in the app's router (if any) and brings the window to the front."""
    if href:
        from .routing import router as _router

        router = _router._current
        if router is not None:
            router.push(href)
    try:
        return _core.Command.focus_window()
    except Exception:  # noqa: BLE001 - no window to focus
        return None


class DesktopNotification:
    """A notification shown with ``pz.notify``: ``close()`` takes it away, ``update(...)`` changes it.

    ``native`` is ``False`` when it was shown without the system's notifications (no buttons or
    clicks then), ``closed`` once it left the screen and ``reason`` why: ``"expired"``,
    ``"dismissed"``, ``"closed"`` or ``"unknown"``.
    """

    def __init__(self, title: str, body: str = "", *, icon: Any = None, image: Any = None,
                 actions: Actions = None, href: Optional[str] = None,
                 on_click: Optional[Callable[..., Any]] = None, on_action: Optional[Callable[..., Any]] = None,
                 on_close: Optional[Callable[..., Any]] = None, urgency: str = "normal",
                 sound: Union[bool, str] = True, timeout: Optional[float] = None, tag: Optional[str] = None) -> None:
        if urgency not in URGENCIES:
            raise ValueError(f"urgency must be one of {', '.join(URGENCIES)}, not {urgency!r}")
        self.id = next(_ids)
        self.title = str(title)
        self.body = str(body)
        self.icon = icon
        self.image = image
        self.actions = _actions(actions)
        self.href = href
        self.on_click = on_click
        self.on_action = on_action
        self.on_close = on_close
        self.urgency = urgency
        self.sound = sound
        self.timeout = timeout
        self.tag = tag
        self.native = False
        self.shown = False
        self.closed = False
        self.reason: Optional[str] = None

    def __repr__(self) -> str:
        return f"<DesktopNotification {self.title!r}{' native' if self.native else ''}>"

    # -- showing -------------------------------------------------------------------------------
    def show(self) -> "DesktopNotification":
        """Shows it (again, replacing itself where the system can); returns itself."""
        self.closed, self.reason = False, None
        sound = None if self.sound is False else ("default" if self.sound is True else str(self.sound))
        timeout = -1 if self.timeout is None else int(max(self.timeout, 0) * 1000)
        try:
            _core.notify_show(self.id, self._event, self.title, self.body, icon=_path(self.icon),
                              image=_path(self.image), actions=self.actions, urgency=URGENCIES[self.urgency],
                              sound=sound, timeout_ms=timeout, app_name=app_name or _default_name(),
                              app_id=app_id)
            self.native = True
        except Exception:  # noqa: BLE001 - no notification server: the system's command instead
            from ._platform import notify as fallback

            self.native = False
            if not fallback(self.title, self.body):
                self.shown = False
                return self
        self.shown = True
        if self.tag:
            _by_tag[self.tag] = self
        return self

    def update(self, **changes: Any) -> "DesktopNotification":
        """Changes some of its values (``title``, ``body``, ``actions``...) and shows it again."""
        for name, value in changes.items():
            if not hasattr(self, name) or name.startswith("_") or name in ("id", "native", "shown", "closed"):
                raise TypeError(f"a notification has no {name!r} to change")
            setattr(self, name, _actions(value) if name == "actions" else value)
        return self.show()

    def close(self) -> None:
        """Takes it off the screen (Linux; Windows and macOS let it leave on its own)."""
        try:
            _core.notify_close(self.id)
        except Exception:  # noqa: BLE001
            pass

    # -- events --------------------------------------------------------------------------------
    def _event(self, event: str, value: Optional[str]) -> None:
        if event == "click":
            _post(self._clicked)
        elif event == "action" and value is not None:
            _post(lambda: self._pressed(value))
        elif event == "closed":
            self.closed, self.reason = True, value
            if self.tag and _by_tag.get(self.tag) is self:
                del _by_tag[self.tag]
            if self.on_close is not None:
                _post(lambda: _call(self.on_close, value))

    def _clicked(self) -> Any:
        if self.on_click is not None:
            result = _call(self.on_click, self)
            if self.href:
                _open(self.href)
            return result
        return _open(self.href)

    def _pressed(self, action: str) -> Any:
        result = _call(self.on_action, action) if self.on_action is not None else None
        if _is_href(action):
            command = _open(action)
            return result if result is not None else command
        if self.on_action is None:
            return _open(None)
        return result


def _call(callback: Callable[..., Any], value: Any) -> Any:
    """Calls ``callback(value)``, or ``callback()`` when it takes nothing."""
    import inspect

    try:
        takes = len(inspect.signature(callback).parameters)
    except (TypeError, ValueError):
        takes = 1
    return callback(value) if takes else callback()


def _default_name() -> str:
    from .routing import router as _router

    router = _router._current
    window = getattr(router, "window", None) if router is not None else None
    for name in (getattr(window, "app_title", None), getattr(window, "title", None)):
        if isinstance(name, str) and name:
            return name
    return "Pyzed"


def notify(title: str, body: str = "", *, icon: Any = None, image: Any = None, actions: Actions = None,
           href: Optional[str] = None, on_click: Optional[Callable[..., Any]] = None,
           on_action: Optional[Callable[..., Any]] = None, on_close: Optional[Callable[..., Any]] = None,
           urgency: str = "normal", sound: Union[bool, str] = True, timeout: Optional[float] = None,
           tag: Optional[str] = None) -> DesktopNotification:
    """Shows a native desktop notification and returns it (see ``pyzed.notifications``).

    ``icon`` and ``image`` are paths or PNG bytes. ``actions`` are buttons, as ``{id: label}`` or a
    list of labels; an id that starts with ``/`` (or ``?``) opens that page. ``href`` is the page a
    click opens; ``on_click(notification)``, ``on_action(id)`` and ``on_close(reason)`` run on the UI
    thread. ``urgency`` is ``"low"``, ``"normal"`` or ``"critical"`` (stays until answered),
    ``sound`` ``True`` (the system's), ``False`` or a sound's name, and ``timeout`` the seconds on
    screen (``0``: until dismissed; ``None``: the system's default). A new notification with the
    ``tag`` of one still shown replaces it, like a download's progress.
    """
    if tag and tag in _by_tag:
        return _by_tag[tag].update(title=title, body=body, icon=icon, image=image, actions=actions, href=href,
                                   on_click=on_click, on_action=on_action, on_close=on_close, urgency=urgency,
                                   sound=sound, timeout=timeout)
    return DesktopNotification(title, body, icon=icon, image=image, actions=actions, href=href,
                               on_click=on_click, on_action=on_action, on_close=on_close, urgency=urgency,
                               sound=sound, timeout=timeout, tag=tag).show()
