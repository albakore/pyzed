"""Ready-made dialogs: alerts, confirmations, text prompts and "unsaved changes".

Each function returns the dialog surface; show it on top of your view with
``ui.dialog_layer`` (a dimmed backdrop, centered)::

    def view(self):
        dialog = None
        if self.asking:
            dialog = ui.confirm("Delete 3 files?", self.delete, self.cancel, danger=True)
        return ui.dialog_layer(self.main_view(), dialog, on_dismiss=self.cancel)

Button labels follow the current language (see ``pyzed.i18n``) unless you pass your own.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from .. import _core
from ..i18n import t as _t
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import _theme, button, label
from .inputs import input as _input
from .overlays import layer, modal

_KIND_ICONS = {"info": "info", "success": "circle-check", "warning": "triangle-alert", "error": "circle-x"}


def dialog_layer(base: Any, dialog: Any = None, *, on_dismiss: Any = None, theme: Optional[Theme] = None) -> _core.Widget:
    """Shows ``dialog`` centered over ``base`` with a dimmed backdrop; clicking the backdrop sends ``on_dismiss``.

    With ``dialog=None`` it returns ``base`` unchanged, so it can always wrap the view.

    Events:
        ``on_dismiss()``: Sent when the backdrop is clicked.
    """
    if dialog is None:
        return base
    return layer(base, dialog, on_dismiss=on_dismiss, backdrop=alpha("#000000", 0.4), align_y="center")


def _message(message: Any, kind: Optional[str], t: Theme) -> Any:
    body = label(message, theme=t) if isinstance(message, str) else message
    if kind is None:
        return body
    return _core.row([_icon(_KIND_ICONS.get(kind, "info"), size=18, color=t.color(kind)), body],
                     spacing=10, align="center")


def alert(
    message: Any,
    on_close: Any,
    *,
    title: Optional[str] = None,
    kind: Optional[str] = None,
    ok_label: Optional[str] = None,
    width: float = 400,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A message with one button. ``kind`` (``"info"``, ``"success"``, ``"warning"``, ``"error"``) adds an icon.

    Events:
        ``on_close()``: The button and the close icon.
    """
    t = _theme(theme)
    return modal(
        _message(message, kind, t),
        title=title,
        on_close=on_close,
        width=width,
        footer=[button(ok_label or _t("pyzed.ok"), on_close, variant="solid", theme=t)],
        theme=t,
    )


def confirm(
    message: Any,
    on_confirm: Any,
    on_cancel: Any,
    *,
    title: Optional[str] = None,
    confirm_label: Optional[str] = None,
    cancel_label: Optional[str] = None,
    danger: bool = False,
    kind: Optional[str] = None,
    width: float = 420,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Asks a yes/no question. ``danger=True`` paints the confirm button red (deleting, discarding...).

    Events:
        ``on_confirm()``: The confirm button.
        ``on_cancel()``: Cancel, the close icon.
    """
    t = _theme(theme)
    return modal(
        _message(message, kind, t),
        title=title or _t("pyzed.confirm"),
        on_close=on_cancel,
        width=width,
        footer=[
            button(cancel_label or _t("pyzed.cancel"), on_cancel, variant="ghost", theme=t),
            button(confirm_label or (_t("pyzed.delete") if danger else _t("pyzed.ok")), on_confirm,
                   variant="solid", tint="error" if danger else None, theme=t),
        ],
        theme=t,
    )


def prompt(
    title: str,
    value: str,
    on_input: Any,
    on_submit: Any,
    on_cancel: Any,
    *,
    message: Any = None,
    placeholder: str = "",
    submit_label: Optional[str] = None,
    cancel_label: Optional[str] = None,
    id: Optional[str] = None,  # noqa: A002 - mirrors ui.input
    width: float = 440,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """Asks for a line of text. ``on_input`` gets each edit; Enter or the submit button calls ``on_submit``.

    Events:
        ``on_input(text)``: Receives each edit.
        ``on_submit()``: Enter or the submit button.
        ``on_cancel()``: Cancel, the close icon.
    """
    t = _theme(theme)
    body = _core.column(
        [
            label(message, color="text_muted", theme=t) if isinstance(message, str) else message,
            _input(value, on_input, placeholder=placeholder, on_submit=on_submit, id=id, theme=t),
        ],
        spacing=8,
    )
    return modal(
        body,
        title=title,
        on_close=on_cancel,
        width=width,
        footer=[
            button(cancel_label or _t("pyzed.cancel"), on_cancel, variant="ghost", theme=t),
            button(submit_label or _t("pyzed.ok"), on_submit, variant="solid", theme=t),
        ],
        theme=t,
    )


def choice(
    message: Any,
    options: Iterable[Any],
    on_cancel: Any,
    *,
    title: Optional[str] = None,
    width: float = 440,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A message with your own buttons: ``options`` are ``(label, on_press)`` pairs (the last is the main one).

    Events:
        ``on_cancel()``: The close icon.
    """
    t = _theme(theme)
    options = list(options)
    footer = [button(text, action, variant="solid" if i == len(options) - 1 else "ghost", theme=t)
              for i, (text, action) in enumerate(options)]
    return modal(_message(message, None, t), title=title, on_close=on_cancel, width=width, footer=footer, theme=t)


def unsaved_changes(
    name: str,
    on_save: Any,
    on_discard: Any,
    on_cancel: Any,
    *,
    width: float = 440,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """"Save your changes to <name> before closing?" with Don't save / Cancel / Save.

    Events:
        ``on_save()``: Save.
        ``on_discard()``: Don't save.
        ``on_cancel()``: Cancel.
    """
    t = _theme(theme)
    return modal(
        _message(_t("pyzed.unsaved.message", name=name), "warning", t),
        title=_t("pyzed.unsaved.title"),
        on_close=on_cancel,
        width=width,
        footer=[
            button(_t("pyzed.dont_save"), on_discard, variant="ghost", theme=t),
            button(_t("pyzed.cancel"), on_cancel, variant="ghost", theme=t),
            button(_t("pyzed.save"), on_save, variant="solid", theme=t),
        ],
        theme=t,
    )
