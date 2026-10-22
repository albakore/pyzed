"""Form controls styled with the current theme."""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple

from .. import _core
from ..icons import glyph
from ..icons import icon as _icon
from ..theme import Theme, alpha
from .base import CHOICE_KEYS, _theme, key_focus, label, send, step_choice


SIZES = {"sm": (12.5, (3, 6)), "md": (13.5, (5, 8)), "lg": (15.0, (8, 10))}
TOGGLE_SIZES = {"sm": (14, 12.5), "md": (16, 13.5), "lg": (18, 15.0)}


def input(  # noqa: A001 - mirrors HTML naming
    value: str,
    on_input: Any = None,
    *,
    placeholder: str = "",
    icon: Optional[str] = None,
    on_submit: Any = None,
    on_clear: Any = None,
    id: Optional[str] = None,  # noqa: A002
    size: str = "md",
    secure: bool = False,
    width: Any = "fill",
    borderless: bool = False,
    mono: bool = False,
    disabled: bool = False,
    readonly: bool = False,
    invalid: bool = False,
    max_length: Optional[int] = None,
    align: str = "start",
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A text field. ``on_input`` receives the new text and returns a message (or ``None``).

    ``disabled`` greys it out and ignores input; ``readonly`` keeps it selectable and
    copyable but unchangeable; ``invalid`` paints the border in the error color;
    ``max_length`` drops edits longer than that; ``on_clear`` shows an ``x`` while there
    is text. Focus, blur and keys come from the common events: ``.on(focus=..., blur=...)``.

    Events:
        ``on_input(text)``: Callable that receives the new text on every keystroke.
        ``on_submit()``: Message or callable sent when Enter is pressed.
        ``on_clear()``: Shows an ✕ while there is text; sent when it is clicked.
    """
    t = _theme(theme)
    font_size, pad = SIZES[size]
    handler = on_input
    if disabled:
        handler = None
    elif readonly:
        handler = _ignore
    elif max_length is not None and on_input is not None:
        handler = _limited(on_input, max_length)
    border = t.error if invalid else t.border
    field = _core.text_input(
        value,
        placeholder=placeholder,
        on_input=handler,
        on_submit=None if disabled or readonly else on_submit,
        id=id,
        size=font_size,
        font="mono" if mono else None,
        padding=pad,
        width=width,
        secure=secure,
        icon=glyph(icon) if icon else None,
        icon_size=font_size,
        bg="transparent" if borderless else (t.element if disabled else t.editor),
        border_color="transparent" if borderless else border,
        hover_border_color="transparent" if borderless else border,
        focus_border_color="transparent" if borderless else (t.error if invalid else t.border_focused),
        border_width=0.0 if borderless else 1.0,
        radius=t.radius_sm,
        color=t.text_disabled if disabled else t.text,
        placeholder_color=t.text_placeholder,
        selection_color=t.selection,
        icon_color=t.icon_muted,
        align_x=align,
    )
    if on_clear is None or not value or disabled or readonly:
        return field
    clear = _core.button(_icon("x", size=font_size - 1, color=t.icon_muted), on_clear, padding=2,
                         bg="transparent", hover_bg=t.ghost_hover, radius=999)
    return _core.stack([field, _core.container(clear, width="fill", height="fill", align_x="end",
                                               align_y="center", padding=(0, pad[1] - 2))], width=width)


def _ignore(_text: str) -> None:
    return None


def _limited(on_input: Any, max_length: int) -> Any:
    def handler(text: str) -> Any:
        return on_input(text) if len(text) <= max_length else None

    return handler


def search_input(value: str, on_input: Any = None, *, placeholder: str = "Search…", **kwargs) -> _core.Widget:
    """An ``input`` with a search icon and a "Search…" placeholder.

    Events:
        ``on_input(text)``: Callable that receives the new text on every keystroke.
    """
    return input(value, on_input, placeholder=placeholder, icon="search", **kwargs)


#: File dialog filters ``path_input`` offers for common kinds of files (``kind="image"``...).
PATH_FILTERS = {
    "image": [("Images", ["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "ico"])],
    "audio": [("Audio", ["wav", "mp3", "ogg", "flac", "aiff"])],
    "video": [("Video", ["mp4", "webm", "mov", "mkv"])],
    "font": [("Fonts", ["ttf", "otf"])],
    "shader": [("Shaders", ["wgsl", "pzshad"])],
    "data": [("Data", ["json", "csv", "toml", "yaml", "yml"])],
}


def path_input(
    value: Any,
    on_change: Any = None,
    *,
    folder: bool = False,
    save: bool = False,
    filters: Optional[Sequence[Tuple[str, Sequence[str]]]] = None,
    kind: Optional[str] = None,
    directory: Optional[str] = None,
    relative_to: Optional[str] = None,
    title: Optional[str] = None,
    placeholder: Optional[str] = None,
    size: str = "md",
    mono: bool = True,
    disabled: bool = False,
    invalid: bool = False,
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A text field for a file or folder path with a button that opens the system's file dialog, so the path
    never has to be typed (it still can be).

    ``folder=True`` picks a folder and ``save=True`` shows the "Save as" dialog. ``filters`` are
    ``(name, extensions)`` pairs, or ``kind`` picks common ones (``"image"``, ``"audio"``, ``"video"``,
    ``"font"``, ``"shader"``, ``"data"``). The dialog opens in ``directory`` (by default the folder of the
    current path); with ``relative_to``, a chosen path inside that folder is given relative to it.

    Events:
        ``on_change(path)``: Callable that receives the typed or chosen path (a string).
    """
    t = _theme(theme)
    text = "" if value is None else str(value)
    handler = None if disabled else on_change
    browse = None if handler is None else (lambda: browse_path(
        handler, folder=folder, save=save, filters=filters if filters is not None else PATH_FILTERS.get(kind or ""),
        directory=directory or _start_folder(text, relative_to), relative_to=relative_to, title=title,
        file_name=text.replace("\\", "/").rsplit("/", 1)[-1] if save else None))
    hint = placeholder if placeholder is not None else ("Choose a folder…" if folder else "Choose a file…")
    font_size, _pad = SIZES[size]
    button = _core.button(
        _core.container(_icon("folder-open", size=font_size + 0.5, color=t.icon_muted if browse else t.text_disabled),
                        center=True, width="fill", height="fill"),
        browse, padding=0, width=font_size * 2 + 2, height="fill", bg=t.element, hover_bg=t.element_hover,
        border_color=t.border, border_width=1.0, radius=t.radius_sm)
    field = input(text, handler, placeholder=hint, size=size, mono=mono, disabled=disabled, invalid=invalid,
                  theme=t)
    from .base import tooltip_text

    return _core.row([_core.container(field, width="fill"),
                      tooltip_text(button, "Choose a folder…" if folder else "Choose a file…", theme=t)],
                     spacing=4, align="center", width="fill", height="shrink")


def _start_folder(text: str, relative_to: Optional[str]) -> Optional[str]:
    """The folder a path field's dialog opens in: where its current path is, else ``relative_to``."""
    import os

    if text:
        path = text if os.path.isabs(text) or not relative_to else os.path.join(relative_to, text)
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if folder and os.path.isdir(folder):
            return folder
    return relative_to if relative_to and os.path.isdir(relative_to) else None


def browse_path(on_change: Any, *, folder: bool = False, save: bool = False, filters: Any = None,
                directory: Optional[str] = None, relative_to: Optional[str] = None, title: Optional[str] = None,
                file_name: Optional[str] = None) -> Any:
    """The command that opens the file dialog and hands ``on_change`` the chosen path (relative to
    ``relative_to`` when it is inside it); nothing happens when it is cancelled."""
    import os

    def chosen(paths: List[str]) -> Any:
        if not paths:
            return None
        path = str(paths[0])
        if relative_to:
            try:
                rel = os.path.relpath(path, relative_to)
            except ValueError:  # another drive on Windows
                rel = path
            if not rel.startswith(".."):
                path = rel.replace(os.sep, "/")
        return on_change(path)

    options: dict = {"title": title or ("Choose a folder" if folder else "Save as" if save else "Choose a file")}
    if filters:
        options["filters"] = [(name, list(exts)) for name, exts in filters]
    if directory:
        options["directory"] = directory
    if save:
        return _core.Command.save_file(chosen, file_name=file_name or None, **options)
    return _core.Command.pick_files(chosen, multiple=False, folder=folder, **options)


def switch(
    checked: bool,
    on_toggle: Any = None,
    *,
    label: Optional[str] = None,  # noqa: F811
    size: str = "md",
    disabled: bool = False,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """An on/off toggle. ``on_toggle`` receives the new ``bool``; ``size`` is ``"sm"``, ``"md"`` or ``"lg"``.

    A click or Tab gives it the keyboard focus; then Space or Enter flips it. ``id`` lets
    ``Command.focus(id)`` focus it.

    Events:
        ``on_toggle(checked)``: Callable that receives the new ``bool`` (or a message to send).
    """
    t = _theme(theme)
    box, text = TOGGLE_SIZES[size]
    widget = _core.toggler(
        checked,
        label,
        on_toggle=None if disabled else on_toggle,
        size=box + 2,
        text_size=text,
        accent=alpha(t.accent, 0.4) if disabled else t.accent,
        bg=t.element if disabled else t.element_active,
        knob_color=t.text_disabled if disabled else (t.text if t.is_dark else "#ffffff"),
        color=t.text_disabled if disabled else t.text,
    )
    flip = None if disabled or on_toggle is None else (lambda _combo: send(on_toggle, not checked))
    return key_focus(widget, flip, keys=("space", "enter"), id=id, theme=t)


def checkbox(
    checked: Optional[bool],
    on_toggle: Any = None,
    *,
    label: Optional[str] = None,  # noqa: F811
    size: str = "md",
    disabled: bool = False,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A themed checkbox with an optional ``label``; ``on_toggle`` receives the new state.

    ``checked=None`` shows the mixed state (some of a group checked); toggling it checks it.
    A click or Tab gives it the keyboard focus; then Space toggles it. ``id`` lets
    ``Command.focus(id)`` focus it.

    Events:
        ``on_toggle(checked)``: Callable that receives the new ``bool`` (or a message to send).
    """
    t = _theme(theme)
    box, text = TOGGLE_SIZES[size]
    accent = alpha(t.accent, 0.4) if disabled else t.accent
    handler = None if disabled else on_toggle
    toggle = None if handler is None else (lambda _combo: send(handler, checked is None or not checked))
    if checked is None:
        mark = _core.container(_core.container(None, width=box / 2, height=2, bg=t.on_accent, radius=1),
                               width=box, height=box, align_x="center", align_y="center", bg=accent,
                               radius=t.radius_sm - 1)
        parts = [mark, _core.text(label, size=text, color=t.text_disabled if disabled else t.text) if label else None]
        body = _core.row(parts, spacing=8, align="center")
        if handler is None:
            return body
        body = body.on(click=lambda: send(handler, True), cursor="pointer")
        return key_focus(body, toggle, keys=("space",), id=id, theme=t)
    widget = _core.checkbox(
        checked,
        label,
        on_toggle=handler,
        size=box,
        text_size=text,
        accent=accent,
        bg=t.element if disabled else t.editor,
        border_color=t.border_variant if disabled else t.border,
        check_color=t.on_accent,
        color=t.text_disabled if disabled else t.text,
    )
    return key_focus(widget, toggle, keys=("space",), id=id, theme=t)


def slider(
    value: float,
    on_change: Any = None,
    *,
    min: float = 0.0,  # noqa: A002
    max: float = 1.0,  # noqa: A002
    step: float = 0.01,
    on_release: Any = None,
    vertical: bool = False,
    width: Any = None,
    height: Any = None,
    disabled: bool = False,
    show_value: Any = False,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A themed slider from ``min`` to ``max`` in ``step`` increments; ``on_change`` receives the value.

    ``on_release`` runs when the drag ends (save or apply there); ``vertical`` stands it
    up; ``show_value`` adds the number next to it (``True``, or a format like ``"{:.0%}"``).
    A click or Tab gives it the keyboard focus; then the arrows move it a step (ten with
    Shift, or Page Up/Down) and Home/End jump to ``min``/``max``. ``id`` lets
    ``Command.focus(id)`` focus it.

    Events:
        ``on_change(value)``: Callable that receives the new value.
        ``on_release()``: Sent when the drag ends (save or apply there).
    """
    t = _theme(theme)
    if width is None and not vertical:
        width = "fill"
    if height is None:
        height = "fill" if vertical else None
    bar = _core.slider(
        min, max, value, step=step, on_change=None if disabled else on_change,
        on_release=None if disabled else on_release, width=width, height=height, vertical=vertical,
        accent=alpha(t.accent, 0.4) if disabled else t.accent,
        bg=t.element if disabled else t.element_active,
        knob_color=t.text_disabled if disabled else t.text, border_color=t.border,
    )

    def nudge(combo: str) -> Any:
        big = combo.startswith("shift-") or combo in ("pageup", "pagedown")
        key = combo.removeprefix("shift-")
        if key == "home":
            new = min
        elif key == "end":
            new = max
        else:
            sign = 1 if key in ("right", "up", "pageup") else -1
            new = round(value + sign * step * (10 if big else 1), 10)
        new = min if new < min else max if new > max else new
        if new == value:
            return None
        result = send(on_change, new)
        if callable(on_release):
            on_release()
        return result

    keys = ("left", "right", "up", "down", "home", "end", "pageup", "pagedown",
            "shift-left", "shift-right", "shift-up", "shift-down")
    bar = key_focus(bar, None if disabled or on_change is None else nudge, keys=keys, id=id, radius=4, theme=t)
    if not show_value:
        return bar
    text = show_value.format(value) if isinstance(show_value, str) else _number(value, step)
    shown = label(text, size="sm", color="text_muted", mono=True, wrap=False, theme=t)
    if vertical:
        return _core.column([shown, bar], spacing=6, align="center", height=height)
    return _core.row([bar, shown], spacing=8, align="center", width="fill" if width == "fill" else None)


def _number(value: float, step: float) -> str:
    if float(step).is_integer() and float(value).is_integer():
        return str(int(value))
    decimals = max(0, len(repr(float(step)).split(".")[1].rstrip("0")))
    return f"{value:.{decimals}f}"


def progress(value: Optional[float], *, max: float = 1.0, tint: str = "accent", height: float = 4,  # noqa: A002
             width: Any = "fill", label: Optional[str] = None, show_value: bool = False,  # noqa: F811
             theme: Optional[Theme] = None) -> _core.Widget:
    """A thin rounded progress bar filled to ``value`` out of ``max``, in the ``tint`` color.

    ``value=None`` is indeterminate: a segment sweeps along the bar (keep a
    ``pz.every(1/30, ...)`` subscription while it shows). ``label`` goes above the bar and
    ``show_value`` adds the percentage at its right.
    """
    t = _theme(theme)
    if value is None:
        import time

        phase = (time.monotonic() * 0.8) % 1.4 - 0.4  # the segment enters and leaves the bar
        before = round(_clamp01(phase) * 100)
        segment = round(_clamp01(phase + 0.4) * 100) - before
        parts = [_core.space(width=f"fill:{before}") if before else None,
                 _core.container(None, width=f"fill:{segment}", height="fill", bg=t.color(tint), radius=height / 2)
                 if segment else None,
                 _core.space(width=f"fill:{100 - before - segment}") if before + segment < 100 else None]
        bar = _core.container(_core.row(parts, height="fill", width="fill"), width=width, height=height,
                              bg=alpha(t.text, 0.1), radius=height / 2, clip=True)
    else:
        bar = _core.progress_bar(value, min=0.0, max=max, width=width, height=height,
                                 accent=t.color(tint), bg=alpha(t.text, 0.1), radius=height / 2)
    if show_value and value is not None:
        percent = _core.text(f"{value / max:.0%}" if max else "", size=12, color=t.text_muted, wrap=False)
        bar = _core.row([bar, percent], spacing=8, align="center", width=width)
    if label:
        bar = _core.column([_core.text(label, size=12.5, color=t.text_muted), bar], spacing=4, width=width)
    return bar


def _clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def _options(options: Sequence[Any]) -> List[Tuple[Any, str, Optional[str]]]:
    """``(value, label, icon)`` for options given as strings, ``(value, label)`` or ``(value, label, icon)``."""
    out = []
    for option in options:
        if isinstance(option, tuple):
            value, text, *rest = option
            out.append((value, text, rest[0] if rest else None))
        else:
            out.append((option, str(option), None))
    return out


def segmented(
    options: Sequence[Any],
    selected: Any,
    on_select: Any = None,
    *,
    size: str = "md",
    width: Any = None,
    disabled: Any = False,
    id: Optional[str] = None,  # noqa: A002
    theme: Optional[Theme] = None,
) -> _core.Widget:
    """A group of mutually exclusive toggle buttons (Zed's ``ToggleButtonGroup``).

    ``options`` are strings, ``(value, label)`` or ``(value, label, icon)``; ``on_select``
    is called with the chosen value. ``width="fill"`` stretches the buttons evenly.
    ``disabled`` is ``True`` for all of them or a collection of the values to disable.
    A click or Tab gives it the keyboard focus; then the arrows pick the previous or next
    option and Home/End the first and last. ``id`` lets ``Command.focus(id)`` focus it.

    Events:
        ``on_select(item)``: Callable that receives the chosen item.
    """
    t = _theme(theme)
    height = {"sm": 20, "md": 24, "lg": 28}[size]
    text_size = "sm" if size != "lg" else "md"
    buttons = []
    enabled = []
    for value, text, icon_name in _options(options):
        is_selected = value == selected
        off = disabled is True or (not isinstance(disabled, bool) and value in disabled)
        if not off:
            enabled.append(value)
        color = "text_disabled" if off else ("text" if is_selected else "text_muted")
        content = _core.row([
            _icon(icon_name, size=13, color=t.color(color)) if icon_name else None,
            label(text, size=text_size, color=color, wrap=False, theme=t) if text else None,
        ], spacing=5, align="center")
        buttons.append(
            _core.button(
                _core.container(content, height="fill", align_y="center",
                                align_x="center" if width is not None else None, width="fill" if width else None),
                None if off or on_select is None else (lambda v=value: on_select(v)),
                padding=(0, 10),
                height=height,
                width="fill" if width is not None else None,
                bg=t.element_selected if is_selected else "transparent",
                hover_bg=t.element_selected if is_selected else t.ghost_hover,
                radius=t.radius_sm - 1,
            )
        )
    group = _core.container(
        _core.row(buttons, spacing=2, width="fill" if width is not None else None),
        padding=2,
        width=width,
        bg=t.element,
        border_color=t.border_variant,
        border_width=1.0,
        radius=t.radius_sm + 1,
    )

    def move(combo: str) -> Any:
        target = step_choice(enabled, selected, combo)
        return None if target is None else send(on_select, target)

    return key_focus(group, move if on_select is not None and enabled else None, keys=CHOICE_KEYS, id=id,
                     radius=t.radius_sm + 1, theme=t)


def field(title: str, control: Any, *, description: Optional[str] = None, error: Optional[str] = None,
          required: bool = False, vertical: bool = False, theme: Optional[Theme] = None) -> _core.Widget:
    """A labelled form row: title + optional description on the left, control on the right.

    ``error`` shows a validation message in the theme's error color under the title (see
    ``pz.validation_errors`` to get them from Pydantic, SQLModel, Django or a FastAPI 422).
    ``required`` adds a red ``*`` after the title; ``vertical`` puts the control under it.
    """
    t = _theme(theme)
    heading = _core.row([label(title, theme=t), label("*", color="error", theme=t) if required else None],
                        spacing=2)
    if vertical:
        return _core.column([
            heading,
            label(description, size="sm", color="text_muted", theme=t) if description else None,
            control,
            label(error, size="sm", color="error", theme=t) if error else None,
        ], spacing=4, width="fill")
    return _core.row(
        [
            _core.column(
                [
                    heading,
                    label(description, size="sm", color="text_muted", theme=t) if description else None,
                    label(error, size="sm", color="error", theme=t) if error else None,
                ],
                spacing=2,
                width="fill",
            ),
            control,
        ],
        spacing=16,
        align="center",
    )
