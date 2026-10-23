"""The component library: what can be placed on a form, its properties, events and look.

Each ``Component`` describes one toolbox entry. The same ``render`` function draws a
control in the designer (inert) and in the running app (live), so what you design is
exactly what runs. Add your own with ``register``::

    from pyzed import ui
    from pyzed.designer import Component, Prop, register

    register(Component(
        type="rating", label="Rating", icon="star", category="Custom", size=(120, 24),
        props=(Prop("value", "number", 3, min=0, max=5),),
        events=("change",),
        render=lambda c, ctx: ui.label("★" * int(c.props["value"])),
    ))
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import _core, component as _components_api, ui
from ..icons import icon as _icon
from ..theme import Theme, current
from . import roles as _roles
from .model import Control

#: Property editors the designer knows how to show.
PROP_KINDS = ("text", "multiline", "number", "bool", "color", "choice", "list", "rows", "icon")

#: Mouse events every visible control supports (in addition to its own).
COMMON_EVENTS = ("mouse_enter", "mouse_leave", "right_click")

#: Events of the form itself.
FORM_EVENTS = ("load", "close", "key", "resize")

#: The toolbox category of the non-visual components (timers, watchers...), drawn in the tray under the form.
NON_VISUAL = "Components"
#: The toolbox category of the controls and components that reach the operating system (files, the clipboard...).
SYSTEM = "System"
#: The size a non-visual component is given (it has no place on the form; the tray sizes its chip itself).
TRAY_SIZE = (120, 24)

EVENT_DOCS = {
    "click": "Runs when {name} is clicked.",
    "double_click": "Runs when {name} is double-clicked.",
    "change": "Runs when the value of {name} changes (``event.value``).",
    "submit": "Runs when Enter is pressed in {name}.",
    "release": "Runs when the user lets go of {name}.",
    "tick": "Runs every ``interval`` milliseconds while {name} is enabled.",
    "mouse_enter": "Runs when the pointer enters {name}.",
    "mouse_leave": "Runs when the pointer leaves {name}.",
    "right_click": "Runs when {name} is right-clicked.",
    "load": "Runs once when {name} opens.",
    "close": "Runs when {name} is closing; return False to keep it open.",
    "key": "Runs on every key press (``event.value`` is a combo such as ``\"ctrl-s\"``).",
    "resize": "Runs when {name} is resized (``event.value`` is ``(width, height)``).",
    "open": "Runs when an item of {name} is double-clicked (``event.value`` is the item).",
    ("table", "open"): "Runs when a row of {name} is double-clicked (``event.value`` is its index).",
    ("table", "sort"): "Runs when a column header of {name} is clicked to sort it (``event.value`` is its title; "
                       "``sort_by`` and ``descending`` already changed).",
    ("tabs", "close"): "Runs after a tab of {name} is closed with its x (``event.value`` is its name).",
    ("chip", "remove"): "Runs when the x of {name} is clicked (``event.value`` is ``None``).",
    ("split_button", "click"): "Runs when the main part of {name} is clicked.",
    ("split_button", "choose"): "Runs when an item of the menu of {name} is chosen (``event.value`` is its text).",
    ("split_button", "menu"): "Runs when the menu of {name} opens.",
    ("toggle_group", "change"): "Runs when a button of {name} is pressed (``event.value`` is its value, or the "
                                "list of pressed values when ``multiple``).",
    ("tree", "change"): "Runs when an item of {name} is selected (``event.value`` is its path, such as "
                        "``\"Documents/Notes.md\"``).",
    ("tree", "open"): "Runs when an item without children of {name} is double-clicked (``event.value`` is its path).",
    ("tree", "toggle"): "Runs when an item of {name} is folded or unfolded (``event.value`` is its path; "
                        "``expanded`` already changed).",
    ("breadcrumbs", "click"): "Runs when a part of {name} is clicked (``event.value`` is its index, 0 for the first).",
    ("dock", "layout"): "Runs when a panel of {name} is moved, resized or switched (``event.value`` is the layout: "
                        "``positions``, ``sizes``, ``active`` and ``hidden``; it is kept in ``layout``).",
    "link": "Runs when a link in {name} is clicked (``event.value`` is the address); without it the link opens in "
            "the browser.",
    # non-visual components; ``(type, event)`` keys describe an event that means something else on one of them
    ("timer", "tick"): "Runs every ``interval`` milliseconds while {name} is running (``event.value`` counts the "
                       "ticks).",
    "activate": "Runs when the keys of {name} are pressed anywhere in the window (``event.value`` is the combo).",
    ("file_watcher", "change"): "Runs after {name} finds changes (``event.value`` lists the changed paths).",
    "created": "Runs when {name} sees a new file (``event.value`` is its path).",
    "modified": "Runs when {name} sees a file change (``event.value`` is its path).",
    "deleted": "Runs when {name} sees a file disappear (``event.value`` is its path).",
    "output": "Runs for every line the program of {name} prints (``event.value`` is the line).",
    "error_output": "Runs for every line the program of {name} prints to its error output (``event.value``).",
    "finished": "Runs when the program of {name} ends (``event.value`` is its exit code, 0 when it went well).",
    "started": "Runs when the program of {name} starts (``event.value`` is its process id).",
    "failed": "Runs when {name} fails (``event.value`` says why).",
    ("process", "failed"): "Runs when the program of {name} cannot start (``event.value`` is the message).",
    "work": "Runs in a background thread when ``form.{name}.run(value)`` is called (``event.value``); return the "
            "result. Change controls in progress and done, not here.",
    "progress": "Runs when the work calls ``event.sender.report(value)`` (``event.value``).",
    "done": "Runs when the work of {name} ends (``event.value`` is what it returned).",
    ("worker", "failed"): "Runs when the work of {name} raises an exception (``event.value``).",
    "response": "Runs when the server answers {name} (``event.value`` is the response: ``.status``, ``.ok``, "
                "``.text``, ``.json()``).",
    ("http_request", "failed"): "Runs when {name} got no answer (``event.value`` is the reason).",
    ("clipboard", "change"): "Runs when new text is copied, in this app or another one (``event.value`` is the "
                             "text).",
    "paste": "Runs after ``form.{name}.paste()`` reads the clipboard (``event.value`` is the text).",
    ("settings", "change"): "Runs when a setting of {name} changes (``event.value`` is ``(key, value)``).",
    "chosen": "Runs when something is chosen in {name} (``event.value`` is the path, or a list of paths).",
    "cancelled": "Runs when {name} is closed without choosing.",
    "shown": "Runs after {name} is shown (``event.value`` is the text).",
    ("notification", "failed"): "Runs when this system cannot show {name}.",
    ("tray_icon", "click"): "Runs when {name} is clicked in the tray (its menu opens with the right button).",
    ("tray_icon", "double_click"): "Runs when {name} is double-clicked (Windows only).",
    ("tray_icon", "menu"): "Runs when an item of the menu of {name} is chosen (``event.value`` is its text).",
    ("tray_icon", "failed"): "Runs when {name} cannot be shown (``event.value`` says why; on GNOME, the "
                             "AppIndicator extension adds tray icons).",
    ("date_picker", "change"): "Runs when the date of {name} changes (``event.value`` is its text, such as "
                               "``\"2026-10-22\"``, or ``\"\"``).",
    ("date_range", "change"): "Runs when the range of {name} changes (``event.value`` is ``(start, end)`` as text; "
                              "``start`` and ``end`` already changed).",
    ("time_picker", "change"): "Runs when the time of {name} changes (``event.value`` is its text, such as "
                               "``\"14:30\"``).",
    ("calendar", "change"): "Runs when a day of {name} is picked (``event.value``: ``\"2026-10-22\"``, "
                            "``\"start / end\"`` in a range, one date per line with several).",
    "month": "Runs when {name} shows another month (``event.value`` is ``(year, month)``).",
    ("date_picker", "open"): "Runs when the calendar of {name} opens.",
    ("date_picker", "close"): "Runs when the calendar of {name} closes.",
    ("date_range", "open"): "Runs when the calendar of {name} opens.",
    ("date_range", "close"): "Runs when the calendar of {name} closes.",
    ("time_picker", "open"): "Runs when the list of {name} opens.",
    ("time_picker", "close"): "Runs when the list of {name} closes.",
    ("file_input", "change"): "Runs when a path is chosen or typed in {name} (``event.value``).",
    "drop": "Runs for each file dropped on {name} (``event.value`` is its path).",
    "files": "Runs when the files of {name} change (``event.value`` is the list; ``files`` already changed).",
    "reject": "Runs when a file {name} does not accept is dropped (``event.value`` is its path).",
    "enter": "Runs when files are dragged over the window of {name} (``event.value`` is the first path).",
    "leave": "Runs when the files dragged over the window of {name} leave without being dropped.",
    "update": "Runs when {name} reads the system (``event.value`` is a dict: ``os``, ``memory_available``, "
              "``disk_free``...).",
    "opened": "Runs when {name} opened something (``event.value`` is what).",
    ("launcher", "failed"): "Runs when {name} could not open something (``event.value`` says why).",
    ("network_monitor", "change"): "Runs when the connection of {name} changes (``event.value`` is ``True`` "
                                   "online, ``False`` offline).",
    "online": "Runs when the connection comes back.",
    "offline": "Runs when the connection is lost.",
    ("power_monitor", "change"): "Runs when the battery changes (``event.value`` is ``(percent, plugged)``).",
    "low": "Runs when the battery drops under ``low_level`` while unplugged (``event.value`` is the percent).",
    "plugged": "Runs when the charger is connected.",
    "unplugged": "Runs when the charger is disconnected.",
}


def event_text(type_: Optional[str], event: str, default: str = "") -> str:
    """The English description of ``event`` on a control of ``type_`` (``None``: the form), with ``{name}``."""
    return EVENT_DOCS.get((type_, event)) or EVENT_DOCS.get(event) or default


@dataclass(frozen=True)
class Prop:
    """A property shown in the designer's property grid.

    ``kind`` picks the editor: text, multiline, number, bool, color, choice (from
    ``choices``), list (one item per line), rows (comma-separated rows, the first one the
    header), icon (a Lucide icon name), file or folder (a path with a button that opens the
    system's dialog; ``accept`` names the kind of file, like ``"image"``, or its extensions,
    like ``"wgsl pzshad"``) or typed (any annotation in ``type``: unions, optionals, dicts,
    tuples...).
    """

    name: str
    kind: str
    default: Any = None
    label: str = ""
    choices: Sequence[str] = ()
    min: Optional[float] = None  # noqa: A003
    max: Optional[float] = None  # noqa: A003
    step: float = 1.0
    group: str = "Appearance"
    #: The annotation of a ``typed`` property (``int | None``, ``dict[str, int]``...), edited by its type.
    type: str = ""
    #: The files a ``file`` property takes: a kind (``"image"``, ``"audio"``...) or extensions (``"png jpg"``).
    accept: str = ""

    @property
    def title(self) -> str:
        """The label shown in the property grid: ``label``, or the name with underscores as spaces."""
        return self.label or self.name.replace("_", " ").capitalize()


class RenderContext:
    """What a component's ``render`` needs: the theme and a way to raise events.

    ``live`` is ``False`` in the designer, where callbacks are inert placeholders so
    controls look enabled but do nothing.
    """

    live = False
    #: The language ``@key`` texts are shown in (``None``: the current one).
    language: Optional[str] = None
    #: The form being drawn, for controls that look at what is inside them (a Dock's tabs).
    form: Any = None
    #: What a running form's code played on each control (``form.title.play_animation()``), by name.
    played: Optional[Dict[str, Any]] = None

    def __init__(self, theme: Optional[Theme] = None, form_name: str = "form") -> None:
        self.theme = theme or current()
        self.form_name = form_name

    def on(self, control: Control, event: str, prop: Optional[str] = None) -> Callable[..., Any]:
        """A callback for ``event``; when ``prop`` is given the value is also stored there."""
        return _inert

    def set(self, control: Control, prop: str, value: Any) -> None:  # noqa: A003
        """Stores ``value`` in ``prop`` of a running control without raising an event (a tree's open folders)."""

    def key(self, control: Control) -> str:
        """A stable id for widgets with internal state (editors, inputs)."""
        return f"{self.form_name}:{control.name}"


def _inert(*_args: Any) -> None:
    return None


@dataclass(frozen=True)
class Component:
    """A toolbox entry: how a control of this ``type`` looks, behaves and is configured."""

    type: str
    label: str
    icon: str
    category: str
    render: Callable[[Control, RenderContext], Any]
    size: Tuple[float, float] = (120, 28)
    props: Tuple[Prop, ...] = ()
    events: Tuple[str, ...] = ()
    description: str = ""
    visual: bool = True
    #: ``"free"``, ``"flex"``, ``"grid"`` or ``"dock"`` when other controls can be placed inside (see ``layout``).
    container: Optional[str] = None
    #: Layout options given to new controls of this type (``(("grow", 1),)`` for a spacer).
    child_layout: Tuple[Tuple[str, Any], ...] = ()
    #: Controls placed inside a new control of this type, as ``(type, props)`` (a Dock's first panels).
    children: Tuple[Tuple[str, Tuple[Tuple[str, Any], ...]], ...] = ()
    #: The role that colors its icon in the designer (``"input"``, ``"layout"``...; see ``roles``); worked out
    #: from the component when ``None``.
    role: Optional[str] = None

    @property
    def default_event(self) -> Optional[str]:
        """The event opened by double-clicking the control in the designer."""
        events = self.all_events
        return events[0] if events else None

    @property
    def all_events(self) -> Tuple[str, ...]:
        """The control's own events followed, for visual components, by the common mouse events."""
        return self.events + (COMMON_EVENTS if self.visual else ())

    def defaults(self) -> Dict[str, Any]:
        """Returns a new dict of the default value of each property, by name."""
        return {p.name: p.default for p in self.props}

    def prop(self, name: str) -> Optional[Prop]:
        """Returns the property called ``name``, or ``None`` if the component has none."""
        for p in self.props:
            if p.name == name:
                return p
        return None

    def create(self, name: str, x: float = 0, y: float = 0, width: Optional[float] = None,
               height: Optional[float] = None) -> Control:
        """A new control of this type with default properties."""
        w, h = self.size
        return Control(name=name, type=self.type, x=x, y=y, width=width or w, height=height or h,
                       props=self.defaults(), layout=dict(self.child_layout))


_REGISTRY: Dict[str, Component] = {}


def register(component: Component) -> Component:
    """Adds (or replaces) a component in the toolbox."""
    _REGISTRY[component.type] = component
    return component


def get(type_: str) -> Component:
    """Returns the registered component for ``type_``; raises ``KeyError`` listing the known types."""
    try:
        return _REGISTRY[type_]
    except KeyError:
        raise KeyError(f"unknown component type {type_!r}; registered: {sorted(_REGISTRY)}") from None


#: The toolbox category of the stand-ins drawn for controls whose component is not registered.
MISSING = "Missing"
#: Stand-ins for unknown types (see ``spec``), by type.
_missing: Dict[str, Component] = {}


def spec(type_: str) -> Component:
    """Returns the registered component for ``type_``, or a stand-in when nobody registered it.

    A control whose component is gone (a project class that failed to import, or a form saved by a newer
    Pyzed) is drawn as a warning box with its type and keeps its properties and events untouched, so the
    rest of the form still opens, runs and saves.
    """
    found = _REGISTRY.get(type_)
    if found is not None:
        return found
    stand_in = _missing.get(type_)
    if stand_in is None:
        label = type_.replace("_", " ").capitalize()
        stand_in = _missing[type_] = Component(
            type_, label, "puzzle", MISSING, _missing_render, (160, 60),
            description=f"The component {type_!r} is not available: its code was not found or failed to import.")
    return stand_in


def is_known(type_: str) -> bool:
    """Whether a component is registered for ``type_`` (``spec`` draws a stand-in when it is not)."""
    return type_ in _REGISTRY


def _missing_render(c: Control, ctx: RenderContext) -> Any:
    """The stand-in of an unknown component: a warning box with its type."""
    from ..theme import alpha

    t = ctx.theme
    return _core.container(
        _core.column([
            _core.row([_icon("triangle-alert", size=14, color=t.warning),
                       _core.text(c.type, size=12, font="mono", color=t.text, wrap=False)], spacing=6,
                      align="center"),
            _core.text("Component not found", size=11, color=t.text_muted, wrap=False),
        ], spacing=2, align="center"),
        width="fill", height="fill", center=True, clip=True, bg=alpha(t.warning, 0.08), radius=t.radius_sm,
        border_color=alpha(t.warning, 0.6), border_width=1)


def all_components() -> List[Component]:
    """Returns every registered component, in registration order."""
    return list(_REGISTRY.values())


def categories() -> Dict[str, List[Component]]:
    """Returns the registered components grouped by ``category`` (toolbox sections), in registration order."""
    out: Dict[str, List[Component]] = {}
    for c in _REGISTRY.values():
        out.setdefault(c.category, []).append(c)
    return out


#: The last drawing of each control, reused while nothing it is drawn from changes (see ``render``).
_drawn: "OrderedDict[tuple, Tuple[Any, Any]]" = OrderedDict()
_DRAWN_SIZE = 4096
#: Controls drawn every time: they read the form (a dock's tabs) or files that can change on disk.
_UNCACHED = frozenset({"dock", "shader", "image", "image_viewer"})


def render(control: Control, ctx: RenderContext) -> Any:
    """Draws ``control`` at its size (its own props, falling back to the component defaults).

    A control whose fields, theme, language and animations are the same as last time gets its
    last drawing back, so a form with hundreds of controls only rebuilds the ones that changed.
    Controls made from a ``pz.Component`` keep their own cache (see ``pyzed.component``).
    """
    if control.type in _UNCACHED or control.type not in _REGISTRY or _components_api.find(control.type) is not None:
        return _render_now(control, ctx)
    plain = type(ctx) is RenderContext  # the designer's: inert callbacks, nothing tied to the context
    try:
        key = (_components_api._token(), ctx.theme, ctx.form_name, ctx.language, ctx.live,
               _components_api._snapshot((control.__dict__, (ctx.played or {}).get(control.name),
                                         (getattr(ctx, "preview", None) or {}).get(control.name))))
    except _components_api._Uncomparable:
        return _render_now(control, ctx)
    slot = (None if plain else ctx, ctx.form_name, control.name)
    entry = _drawn.get(slot)
    if entry is not None and entry[0] == key:
        _drawn.move_to_end(slot)
        return entry[1]
    widget = _render_now(control, ctx)
    _drawn[slot] = (key, widget)
    if len(_drawn) > _DRAWN_SIZE:
        _drawn.popitem(last=False)
    return widget


def _render_now(control: Control, ctx: RenderContext) -> Any:
    from .binding import translate

    component = spec(control.type)
    props = {k: translate(v, ctx.language) for k, v in {**component.defaults(), **control.props}.items()}
    merged = Control(**{**control.__dict__, "props": props})
    widget = styled(component.render(merged, ctx), control, ctx)
    widget = animated(widget, control, ctx)
    # shadows, glows and motion are drawn outside the box: clipping would cut them off
    from . import motion

    played = (ctx.played or {}).get(control.name)
    return _core.container(widget, width=control.width, height=control.height,
                           clip=not (motion.moves(control.animations, control.style) or (played and played.extra)))


def animated(widget: Any, control: Control, ctx: RenderContext) -> Any:
    """``widget`` with the control's animations: always in a running form (with what its code played,
    ``ctx.played``), and in the designer only while its Preview plays (``ctx.preview`` maps control
    names to a restart counter)."""
    from . import motion

    if ctx.live:
        played = (ctx.played or {}).get(control.name)
        if not control.animations and played is None:
            return widget
        return motion.apply(widget, control.animations, played=played)
    if not control.animations:
        return widget
    generation = (getattr(ctx, "preview", None) or {}).get(control.name)
    if generation is None:
        return widget
    return motion.apply(widget, control.animations, preview=generation)


def styled(widget: Any, control: Control, ctx: RenderContext) -> Any:
    """``widget`` with the control's own style (see ``designer.styling``)."""
    if not control.style:
        return widget
    from . import styling

    return styling.apply(widget, styling.pivoted(control.style, control.pivot, (control.width, control.height)),
                         ctx.theme)


# -- helpers -------------------------------------------------------------------


def _lines(value: Any) -> List[str]:
    if isinstance(value, str):
        return [line for line in value.splitlines() if line.strip()]
    return [str(v) for v in (value or [])]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _align(value: str) -> str:
    return {"left": "start", "right": "end"}.get(value, value)


def _fill(widget: Any, c: Control, align_x: str = "start", align_y: str = "center") -> Any:
    return _core.container(widget, width="fill", height="fill", align_x=align_x, align_y=align_y)


TEXT_SIZES = ("xs", "sm", "md", "lg", "xl", "2xl")
WEIGHTS = ("normal", "medium", "semibold", "bold")
TINTS = ("accent", "success", "warning", "error", "info")
VARIANTS = ("filled", "solid", "ghost", "outline", "subtle", "tinted")


# -- built-in components -------------------------------------------------------


def _clickable(widget: Any, c: Control, ctx: RenderContext) -> Any:
    """``widget`` raising the ``click`` and ``double_click`` events of ``c`` when they have handlers."""
    if not (c.events.get("click") or c.events.get("double_click")) or not c.enabled:
        return widget
    return _core.mouse_area(widget, on_press=ctx.on(c, "click") if c.events.get("click") else None,
                            on_double_click=ctx.on(c, "double_click") if c.events.get("double_click") else None,
                            cursor="pointer" if ctx.live else None)


def _label(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    text = ui.label(p["text"], size=p["size"], color=p["color"] or "text",
                    weight=None if p["weight"] == "normal" else p["weight"], wrap=p["wrap"], theme=ctx.theme)
    return _clickable(_fill(text, c, align_x=_align(p["align"])), c, ctx)


def _heading(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.heading(p["text"], level=int(_num(p["level"], 1)), theme=ctx.theme), c,
                 align_x=_align(p["align"]))


def _button(c: Control, ctx: RenderContext) -> Any:
    from ..ui.base import _button_colors

    t = ctx.theme
    p = c.props
    colors = _button_colors(t, p["variant"], None, False)
    border = colors.pop("border_color", None)
    parts = [_icon(p["icon"], size=14) if p["icon"] else None,
             _core.text(p["text"], size=13.5, wrap=False) if p["text"] else None]
    parts = [w for w in parts if w is not None]
    return _core.button(
        _core.container(_core.row(parts, spacing=6, align="center"), width="fill", height="fill", center=True),
        ctx.on(c, "click") if c.enabled else None,
        # an icon-only button has no side padding, so the icon stays centered in small buttons
        padding=(0, 10) if p["text"] else 0, width="fill", height="fill", radius=t.radius_sm, border_color=border,
        border_width=1.0 if border else 0.0, disabled_color=t.text_disabled, **colors)


def _input(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.input(str(p["text"]), ctx.on(c, "change", "text") if c.enabled else None,
                          placeholder=p["placeholder"], icon=p["icon"] or None, secure=p["secure"],
                          on_submit=ctx.on(c, "submit"), id=ctx.key(c), theme=ctx.theme), c)


def _text_area(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return ui.editor(ctx.key(c), str(p["text"]), language=p["language"] or "txt",
                     on_change=ctx.on(c, "change", "text"), gutter=p["line_numbers"], wrap=p["wrap"],
                     active_line=False, placeholder=p["placeholder"] or None, theme=ctx.theme)


def _checkbox(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.checkbox(bool(p["checked"]), ctx.on(c, "change", "checked") if c.enabled else None,
                             label=p["text"] or None, theme=ctx.theme), c)


def _switch(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.switch(bool(p["checked"]), ctx.on(c, "change", "checked") if c.enabled else None,
                           label=p["text"] or None, theme=ctx.theme), c)


def _radio(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    options = _lines(p["options"])
    return _core.container(
        ui.radio_group(options, p["selected"], ctx.on(c, "change", "selected") if c.enabled else None,
                       horizontal=p["horizontal"], theme=ctx.theme),
        width="fill", height="fill")


def _select(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    options = _lines(p["options"])
    selected = p["selected"] if p["selected"] in options else None
    return _fill(ui.select(options, selected, ctx.on(c, "change", "selected") if c.enabled else None,
                           placeholder=p["placeholder"], width="fill", theme=ctx.theme), c)


def _slider(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    lo, hi = _num(p["min"]), _num(p["max"], 100)
    value = min(max(_num(p["value"]), lo), hi)
    vertical = bool(p["vertical"])
    widget = ui.slider(value, ctx.on(c, "change", "value") if c.enabled else None, min=lo, max=hi,
                       step=_num(p["step"], 1) or 1, on_release=ctx.on(c, "release") if c.enabled else None,
                       vertical=vertical, show_value=bool(p["show_value"]), disabled=not c.enabled,
                       theme=ctx.theme)
    if vertical:
        return _core.container(widget, width="fill", height="fill", align_x="center")
    return _fill(widget, c)


def _number(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.number_field(_num(p["value"]), ctx.on(c, "change", "value") if c.enabled else None,
                                 min=None if p["min"] in (None, "") else _num(p["min"]),
                                 max=None if p["max"] in (None, "") else _num(p["max"]),
                                 step=_num(p["step"], 1) or 1, width=c.width, theme=ctx.theme), c)


def _progress(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.progress(_num(p["value"]), max=_num(p["max"], 100) or 1, tint=p["tint"],
                             height=max(2, min(c.height, 8)), theme=ctx.theme), c)


def _panel(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    header = None
    if p["title"]:
        header = _core.container(ui.label(p["title"], size="sm", weight="semibold", color="text_muted", theme=t),
                                 padding=(8, 12), width="fill")
    return _core.container(
        _core.column([w for w in (header,) if w is not None], width="fill"),
        width="fill",
        height="fill",
        bg=t.color(p["background"]) if p["background"] else t.surface,
        border_color=t.border_variant if p["border"] else None,
        border_width=1 if p["border"] else 0,
        radius=t.radius,
    )


def _divider(c: Control, ctx: RenderContext) -> Any:
    vertical = c.props["vertical"]
    return _core.container(ui.divider(vertical=vertical, theme=ctx.theme), width="fill", height="fill",
                           align_x="center", align_y="center")


def _badge(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.badge(p["text"], tint=p["tint"], icon=p["icon"] or None, theme=ctx.theme), c)


def _image(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    source = c.props["source"]
    if not source:
        return _core.container(_icon("image", size=24, color=t.icon_muted), width="fill", height="fill",
                               center=True, bg=t.element, radius=t.radius_sm)
    return _clickable(_core.image(source, width="fill", height="fill", content_fit=c.props["fit"],
                                  radius=_num(c.props["radius"])), c, ctx)


def _shader(c: Control, ctx: RenderContext) -> Any:
    """A ``.pzshad`` made in the Shader view, drawn live (still in the designer); ``variables`` sets its
    variables by name (``{"speed": 2}``), from the Properties panel or from code."""
    t = ctx.theme
    source = str(c.props.get("file") or "")
    message = None
    if source:
        from .. import shader as _shader_widget
        from ..shading import GraphError

        variables = c.props.get("variables") or {}
        try:
            options = {} if ctx.live else {"time": 1.0}
            return _shader_widget(source, uniforms=dict(variables) if isinstance(variables, dict) else None,
                                  width="fill", height="fill", **options)
        except (OSError, ValueError, TypeError, KeyError, GraphError) as err:
            message = str(err).splitlines()[0]
    return _core.container(_core.column([_icon("blend", size=24, color=t.icon_muted),
                                         _core.text(message, size=11, color=t.text_muted, wrap=True)
                                         if message else None], spacing=4, align="center"),
                           width="fill", height="fill", center=True, padding=6, bg=t.element, radius=t.radius_sm)


def _icon_control(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    color = ctx.theme.color(p["color"]) if p["color"] else None
    return _clickable(_core.container(_icon(p["name"] or "star", size=_num(p["size"], 20), color=color),
                                      width="fill", height="fill", center=True), c, ctx)


#: Rows from which a List box builds only the rows in view.
VIRTUAL_ROWS = 50


def _list_box(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    on_select = ctx.on(c, "change", "selected")
    on_open = ctx.on(c, "open") if c.events.get("open") else None
    def row(item: str) -> Any:
        return ui.list_item(item, (lambda: on_select(item)) if ctx.live and c.enabled else None,
                            selected=item == p["selected"],
                            on_double_press=(lambda: on_open(item)) if on_open and c.enabled else None, theme=t)

    items = _lines(p["items"])
    if len(items) > VIRTUAL_ROWS:  # long lists only build the rows in view
        body = ui.virtual_list(items, row, padding=4, theme=t)
    else:
        body = _core.scrollable(_core.column([row(item) for item in items], width="fill", padding=4))
    return _core.container(body, width="fill", height="fill", bg=t.editor, border_color=t.border_variant,
                           border_width=1, radius=t.radius_sm)


def _markdown(c: Control, ctx: RenderContext) -> Any:
    # a link opens in the browser unless the form handles it in its link event
    on_link = ctx.on(c, "link") if c.events.get("link") else (_open_url if ctx.live else None)
    return _core.scrollable(ui.markdown(c.props["text"], width="fill", on_link=on_link, theme=ctx.theme))


def _open_url(url: str) -> None:
    import webbrowser

    webbrowser.open(url)


def _spinner(c: Control, ctx: RenderContext) -> Any:
    return _core.container(ui.spinner(size=min(c.width, c.height) * 0.8, tint=c.props["tint"], theme=ctx.theme),
                           width="fill", height="fill", center=True)


def _non_visual(c: Control, ctx: RenderContext) -> Any:
    """How a non-visual component looks in the designer's component tray: its icon and name."""
    t = ctx.theme
    spec = _REGISTRY.get(c.type)
    return _core.container(
        _core.row([_icon(spec.icon if spec is not None else "box", size=14, color=_roles.icon_color(spec, t)),
                   ui.label(c.name, size="sm", color="text_muted", theme=t)], spacing=6, align="center"),
        width="fill", height="fill", center=True, bg=t.element, radius=t.radius_sm,
        border_color=t.border_variant, border_width=1)


_timer = _non_visual


def _outline(ctx: RenderContext, widget: Any, background: Any = None) -> Any:
    """A layout container: invisible when running, a faint dashed-looking frame while designing."""
    t = ctx.theme
    bg = t.color(background) if background else None
    if ctx.live:
        return _core.container(widget, width="fill", height="fill", bg=bg)
    from ..theme import alpha

    return _core.container(widget, width="fill", height="fill", bg=bg or alpha(t.accent, 0.03),
                           border_color=alpha(t.accent, 0.35), border_width=1, radius=2)


def _flex(c: Control, ctx: RenderContext) -> Any:
    return _outline(ctx, None, c.props["background"])


def _grid(c: Control, ctx: RenderContext) -> Any:
    return _outline(ctx, None, c.props["background"])


def _spacer(c: Control, ctx: RenderContext) -> Any:
    if ctx.live:
        return _core.space(width="fill", height="fill")
    t = ctx.theme
    from ..theme import alpha

    return _core.container(_icon("move-horizontal", size=12, color=alpha(t.text_muted, 0.6)), width="fill",
                           height="fill", center=True, border_color=alpha(t.text_muted, 0.25), border_width=1,
                           radius=2)


def _group_box(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    title = _core.container(ui.label(p["title"], size="sm", weight="medium", color="text_muted", wrap=False, theme=t),
                            padding=(0, 6), bg=t.background)
    frame = _core.container(None, width="fill", height="fill", border_color=t.border, border_width=1,
                            radius=t.radius_sm)
    return _core.stack([_core.container(frame, width="fill", height="fill", padding=(9, 0, 0, 0)),
                        _core.pin(title, x=10, y=0)] if p["title"] else [frame], width="fill", height="fill")


def _card(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    header = None
    if p["title"]:
        header = _core.container(ui.label(p["title"], weight="semibold", theme=t), padding=(12, 16, 0, 16),
                                 width="fill")
    return _core.container(
        _core.column([w for w in (header,) if w is not None], width="fill"),
        width="fill", height="fill", bg=t.elevated, border_color=t.border_variant, border_width=1,
        # No blurred shadow while designing: wgpu redraws it over later layers of the scrolled surface.
        radius=t.radius + 2, shadow=(t.shadow, (0, 2), 8) if p["shadow"] and ctx.live else None)


def _link(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    text = ui.label(p["text"], size="sm", color="text_accent", wrap=False, theme=t)
    return _fill(_core.mouse_area(text, on_press=ctx.on(c, "click") if c.enabled else None,
                                  cursor="pointer" if ctx.live else None), c, align_x=_align(p["align"]))


def _segmented(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    options = _lines(p["options"])
    selected = p["selected"] if p["selected"] in options else (options[0] if options else "")
    return _fill(ui.segmented(options, selected, ctx.on(c, "change", "selected") if c.enabled else None,
                              theme=ctx.theme), c)


def _tabs(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    names = _lines(p["tabs"])
    tabs = [ui.Tab(n, n) for n in names]
    selected = p["selected"] if p["selected"] in names else (names[0] if names else None)
    on_close = None
    if p["closable"]:
        def on_close(name: str) -> Any:
            # the tab leaves the bar (its neighbour is selected), then the close event runs
            left = [n for n in names if n != name]
            ctx.set(c, "tabs", "\n".join(left))
            if selected == name and left:
                ctx.on(c, "change", "selected")(left[min(names.index(name), len(left) - 1)])
            return ctx.on(c, "close")(name)

        if not ctx.live:
            on_close = _inert
    return _core.container(ui.tab_bar(tabs, selected, on_select=ctx.on(c, "change", "selected"), on_close=on_close,
                                      height=max(c.height, 24), theme=ctx.theme),
                           width="fill", height="fill", align_y="center")


def _search(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.search_input(str(p["text"]), ctx.on(c, "change", "text") if c.enabled else None,
                                 placeholder=p["placeholder"], on_submit=ctx.on(c, "submit"), id=ctx.key(c),
                                 theme=ctx.theme), c)


def _callout(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _core.container(ui.callout(p["title"], p["text"] or None, tint=p["tint"], icon=p["icon"] or None,
                                      theme=ctx.theme), width="fill", height="fill")


def _avatar(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    size = min(c.width, c.height)
    return _clickable(_core.container(ui.avatar(p["initials"] or "?", color=p["color"] or None, size=size,
                                                theme=ctx.theme), width="fill", height="fill", center=True), c, ctx)


def _chip(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.chip(p["text"], on_press=ctx.on(c, "click") if ctx.live else None, selected=bool(p["selected"]),
                         on_remove=(ctx.on(c, "remove") if ctx.live else _inert) if p["removable"] else None,
                         icon=p["icon"] or None, tint=p["tint"], disabled=not c.enabled, theme=ctx.theme), c)


def _kbd(c: Control, ctx: RenderContext) -> Any:
    return _fill(ui.kbd(c.props["keys"] or "ctrl-s", theme=ctx.theme), c)


def _stat(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    delta = None if p["delta"] in (None, "") else _num(p["delta"])
    trend = [_num(v) for v in _lines(p["trend"])] or None
    return ui.stat(p["title"], p["value"], delta=delta, trend=trend, width="fill", theme=ctx.theme)


def _values(value: Any) -> List[float]:
    return [_num(v) for v in str(value or "").replace(",", " ").split()]


def _chart(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    values = _values(p["values"])
    t = ctx.theme
    if p["kind"] == "line":
        return ui.sparkline(values, width=c.width, height=c.height, tint=p["tint"], theme=t)
    if p["kind"] == "donut":
        size = min(c.width, c.height)
        return _core.container(ui.donut(values, size=size, thickness=max(size / 7, 4), theme=t), width="fill",
                               height="fill", center=True)
    labels = _lines(p["labels"]) or None
    return ui.bar_chart(values, labels=labels, width=c.width, height=c.height, tint=p["tint"], theme=t)


def _table(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    lines = _lines(p["data"])
    if not lines:
        return _core.space()
    header = [h.strip() for h in lines[0].split(",")]
    rows = [dict(zip(header, (v.strip() for v in line.split(",")))) for line in lines[1:]]
    selected = p["selected"]
    on_row = ctx.on(c, "change", "selected")
    live = ctx.live and c.enabled

    def index(row: Any) -> Any:
        return next((i for i, r in enumerate(rows) if r is row), row)

    on_open = ctx.on(c, "open") if c.events.get("open") else None
    on_sort = None
    if p["sortable"]:
        def on_sort(title: str) -> Any:
            # a click on the sorted column flips the order; on another one sorts by it, ascending
            ctx.set(c, "descending", not p["descending"] if p["sort_by"] == title else False)
            ctx.set(c, "sort_by", title)
            return ctx.on(c, "sort")(title)

    return _core.container(
        ui.table(header, rows, striped=bool(p["striped"]), height="fill",
                 sort_by=(p["sort_by"] or None) if p["sortable"] else None, descending=bool(p["descending"]),
                 on_sort=on_sort if live else (_inert if on_sort else None),
                 on_row_press=(lambda row: on_row(index(row))) if live else None,
                 on_row_double_press=(lambda row: on_open(index(row))) if live and on_open else None,
                 selected=rows[int(selected)] if isinstance(selected, int) and 0 <= selected < len(rows) else None,
                 theme=ctx.theme),
        width="fill", height="fill", border_color=ctx.theme.border_variant, border_width=1,
        radius=ctx.theme.radius_sm, clip=True)


def _fields(line: str) -> List[str]:
    return [part.strip() for part in line.split(",")]


def _toggle_group(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    # one option per line: "value, icon, tooltip" (the icon defaults to the value, the tooltip is optional)
    options = []
    for line in _lines(p["options"]):
        value, *rest = _fields(line)
        options.append((value, rest[0] if rest and rest[0] else value, *(rest[1:2] if len(rest) > 1 else ())))
    multiple = bool(p["multiple"])
    chosen = _lines(p["selected"]) if multiple else p["selected"]
    on_change = ctx.on(c, "change", "selected")

    def pick(value: str) -> Any:
        if not multiple:
            return on_change(value)
        values = [v for v in chosen if v != value] if value in chosen else [*chosen, value]
        # the property keeps the values one per line; the event gets them as a list
        ctx.set(c, "selected", "\n".join(values))
        return ctx.on(c, "change")(values)

    return _fill(ui.toggle_group(options, chosen, pick if ctx.live else None, multiple=multiple,
                                 disabled=not c.enabled, theme=ctx.theme), c)


def _split_button(c: Control, ctx: RenderContext) -> Any:
    from ..icons import glyph
    from ..ui.base import _button_colors

    t = ctx.theme
    p = c.props
    main = _button(c, ctx)
    colors = _button_colors(t, p["variant"], None, False)
    items = _lines(p["items"])
    # the chevron is a drop-down without text, so its menu opens over the rest of the form
    menu = _core.pick_list(items, None, ctx.on(c, "choose") if c.enabled and ctx.live else None,
                           on_open=ctx.on(c, "menu") if c.enabled else None, placeholder="", width=28,
                           padding=(0, 0, 0, 6), handle=glyph("chevron-down"), handle_size=12, text_size=13,
                           bg=colors.get("bg", t.element), handle_color=colors.get("color", t.icon),
                           border_color=colors.get("border_color") or "transparent",
                           hover_border_color=t.border_focused, radius=t.radius_sm, menu_bg=t.elevated,
                           menu_color=t.text, menu_border_color=t.border, selected_bg=t.ghost_selected,
                           selected_color=t.text)
    return _core.row([_core.container(main, width="fill", height="fill"),
                      _core.container(menu, height="fill", align_y="center")], spacing=1, width="fill",
                     height="fill")


def _tree_nodes(text: Any) -> List[Any]:
    """Tree nodes from indented lines (two spaces or a tab per level); ids are paths such as ``"src/main.py"``."""
    lines = text.splitlines() if isinstance(text, str) else [str(v) for v in (text or [])]
    root: List[Any] = []
    stack: List[Tuple[int, Any]] = []
    for raw in lines:
        if not raw.strip():
            continue
        depth = len(raw.expandtabs(2)) - len(raw.expandtabs(2).lstrip())
        name = raw.strip()
        folder = name.endswith("/")
        name = name.rstrip("/").strip()
        while stack and stack[-1][0] >= depth:
            stack.pop()
        parent = stack[-1][1] if stack else None
        if parent is not None and parent.children is None:
            parent.children = []  # an item with items under it is a folder
        node = ui.TreeNode(name, children=[] if folder else None,
                           id=f"{parent.id}/{name}" if parent is not None else name)
        (parent.children if parent is not None else root).append(node)
        stack.append((depth, node))
    return root


def _tree(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    nodes = _tree_nodes(p["items"])
    expanded = set(_lines(p["expanded"]))
    live = ctx.live and c.enabled

    def toggle(node_id: str) -> Any:
        ctx.set(c, "expanded", "\n".join(sorted(expanded ^ {node_id})))
        return ctx.on(c, "toggle")(node_id)

    on_open = ctx.on(c, "open") if c.events.get("open") else None
    return _core.container(
        _core.scrollable(_core.container(
            ui.tree(nodes, expanded=expanded, selected=p["selected"] or None, on_toggle=toggle if live else None,
                    on_select=ctx.on(c, "change", "selected") if live else None,
                    on_open=on_open if live else None, theme=t),
            width="fill", padding=4)),
        width="fill", height="fill", bg=t.editor if p["border"] else None,
        border_color=t.border_variant if p["border"] else None, border_width=1 if p["border"] else 0,
        radius=t.radius_sm)


def _breadcrumbs(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    parts = _lines(p["parts"])
    return _fill(ui.breadcrumbs(parts, separator=p["separator"] or "›",
                                on_press=ctx.on(c, "click") if c.enabled else None, theme=ctx.theme), c)


def _empty_state(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return ui.empty_state(p["title"], p["text"] or None, icon=p["icon"] or "inbox", size=p["size"],
                          theme=ctx.theme)


def _counter(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _clickable(_core.container(ui.count_badge(int(_num(p["count"])), tint=p["tint"],
                                                     max=int(_num(p["max"], 99)) or 99,
                                                     show_zero=bool(p["show_zero"]), theme=ctx.theme),
                                      width="fill", height="fill", center=True), c, ctx)


def _status_dot(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    dot = ui.indicator(p["color"] or "accent", size=max(min(c.width, c.height) - 2, 2) if not p["text"] else 8,
                       theme=ctx.theme)
    if p["text"]:
        dot = _core.row([dot, ui.label(p["text"], size="sm", wrap=False, theme=ctx.theme)], spacing=6,
                        align="center")
        return _clickable(_fill(dot, c), c, ctx)
    return _clickable(_core.container(dot, width="fill", height="fill", center=True), c, ctx)


def _facepile(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _clickable(_fill(ui.facepile(_lines(p["people"]), size=max(min(c.height, 64), 12),
                                        max_shown=int(_num(p["max_shown"], 5)) or 5, theme=ctx.theme), c),
                      c, ctx)


def _diff_stat(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.diff_stat(int(_num(p["added"])), int(_num(p["removed"])), theme=ctx.theme), c)


def _qr_code(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    data = str(p["data"] or " ")
    try:
        code = _core.qr_code(data, cell_size=max(_num(p["cell_size"], 4), 1), color=t.color(p["color"] or "text"),
                             bg=t.color(p["background"]) if p["background"] else "transparent")
    except Exception as err:  # noqa: BLE001 - too much data for a QR code
        code = _core.text(str(err).splitlines()[0], size=11, color=t.text_muted, wrap=True)
    return _clickable(_core.container(code, width="fill", height="fill", center=True), c, ctx)


def _svg(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    if not p["source"]:
        return _core.container(_icon("shapes", size=24, color=t.icon_muted), width="fill", height="fill",
                               center=True, bg=t.element, radius=t.radius_sm)
    return _clickable(_core.svg(p["source"], width="fill", height="fill", content_fit=p["fit"],
                                color=t.color(p["color"]) if p["color"] else None,
                                opacity=min(max(_num(p["opacity"], 1), 0), 1), rotation=_num(p["rotation"])),
                      c, ctx)


def _image_viewer(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    if not p["source"]:
        return _core.container(_icon("zoom-in", size=24, color=t.icon_muted), width="fill", height="fill",
                               center=True, bg=t.element, radius=t.radius_sm)
    return _core.container(
        _core.image_viewer(p["source"], width="fill", height="fill", min_scale=max(_num(p["min_zoom"], 0.25), 0.01),
                           max_scale=max(_num(p["max_zoom"], 10), 0.01)),
        width="fill", height="fill", bg=t.editor, radius=t.radius_sm, clip=True)


def _terminal(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    return _core.container(
        # it follows the last line while new output arrives, as terminals do
        _core.scrollable(_core.container(ui.terminal(str(p["text"] or ""), font_size=_num(p["font_size"], 13) or 13,
                                                     theme=t), padding=(6, 10)),
                         width="fill", height="fill", anchor_bottom=bool(p["follow"])),
        width="fill", height="fill", bg=t.terminal,
        border_color=t.border_variant, border_width=1, radius=t.radius_sm)


def _dock(c: Control, ctx: RenderContext) -> Any:
    """The frame of a dock: each side's tabs over its panels (drawn on top as controls). A running form swaps
    it for a live ``pz.Dock`` whose tabs switch, move and resize (see ``FormRuntime``)."""
    from . import layout as _layout

    t = ctx.theme
    panels = [p for p in (ctx.form.children(c.name) if ctx.form is not None else []) if p.visible]
    rect = (0.0, 0.0, c.width, c.height)
    layers = [_core.container(width="fill", height="fill", bg=t.editor)]
    for side, (x, y, w, h) in _layout.dock_areas(c, rect, panels).items():
        if side == "center" or w <= 0 or h <= 0:
            continue
        group = [p for p in panels if _layout.dock_side(p) == side]
        tabs = []
        for p in group:
            active = p is group[-1]  # the top-most panel of a side is its tab shown
            title = str(p.props.get("title") or p.name)
            icon = p.props.get("icon")
            tabs.append(_core.container(_core.row([
                _icon(icon, size=13, color=t.icon if active else t.icon_muted) if icon else None,
                _core.text(title, size=12.5, color=t.text if active else t.text_muted, wrap=False),
            ], spacing=5, align="center"), padding=(4, 8), radius=t.radius, height=26, align_y="center",
                bg=t.element_selected if active else None))
        edge = {"left": (w - 1, 0, 1, h), "right": (0, 0, 1, h), "top": (0, h - 1, w, 1), "bottom": (0, 0, w, 1)}[side]
        layers.append(_core.pin(_core.stack([
            _core.container(_core.column([_core.container(_core.row(tabs, spacing=2, align="center"),
                                                          padding=(3, 6), width="fill",
                                                          height=_layout.DOCK_HEADER, align_y="center")]),
                            width=w, height=h, bg=t.panel, clip=True),
            _core.pin(_core.container(width=edge[2], height=edge[3], bg=t.border), x=edge[0], y=edge[1]),
        ], width=w, height=h), x=x, y=y))
    return _core.stack(layers, width="fill", height="fill")


def _dock_panel(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    bg = t.color(p["background"]) if p["background"] else (t.editor if p["side"] == "center" else t.panel)
    return _core.container(width="fill", height="fill", bg=bg)


# -- dates and times ------------------------------------------------------------


def _iso(value: Any) -> str:
    """A date or time as the text a form keeps (``"2026-10-22"``, ``"14:30"``); ``""`` for none."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        text = value.isoformat()
        return text[:5] if len(text) == 8 and text.endswith(":00") else text
    return str(value)


def _changed(c: Control, ctx: RenderContext, prop: str, convert: Callable[[Any], Any] = _iso) -> Any:
    """``on_change`` for a component: keeps the converted value in ``prop`` and raises ``change`` with it."""
    if not c.enabled:
        return None
    callback = ctx.on(c, "change", prop)
    return lambda e: callback(convert(e.value))


def _raise(c: Control, ctx: RenderContext, event: str) -> Any:
    callback = ctx.on(c, event)
    return (lambda e: callback(e.value)) if c.events.get(event) else None


def _calendar(c: Control, ctx: RenderContext) -> Any:
    from ..ui import dates

    p = c.props
    mode = p["mode"]
    if mode == "range":
        def convert(v: Any) -> str:
            return " / ".join(_iso(d) for d in v)
    elif mode == "multiple":
        def convert(v: Any) -> str:
            return "\n".join(_iso(d) for d in v)
    else:
        convert = _iso
    return dates.Calendar(p["value"], mode=mode, min=p["min"] or None, max=p["max"] or None,
                          disabled=_lines(p["disabled"]), first_weekday=p["first_weekday"],
                          months=max(1, int(_num(p["months"], 1))), week_numbers=p["week_numbers"],
                          today_button=p["today_button"], key=ctx.key(c),
                          on_change=_changed(c, ctx, "value", convert), on_month=_raise(c, ctx, "month"))


def _date_picker(c: Control, ctx: RenderContext) -> Any:
    from ..ui import dates

    p = c.props
    return _fill(dates.DatePicker(p["value"], format=p["format"] or "YYYY-MM-DD", placeholder=p["placeholder"],
                                  min=p["min"] or None, max=p["max"] or None, disabled_dates=_lines(p["disabled_dates"]),
                                  first_weekday=p["first_weekday"], week_numbers=p["week_numbers"],
                                  clearable=p["clearable"], today_button=p["today_button"], disabled=not c.enabled,
                                  key=ctx.key(c), on_change=_changed(c, ctx, "value"),
                                  on_open=_raise(c, ctx, "open"), on_close=_raise(c, ctx, "close")), c)


def _date_range(c: Control, ctx: RenderContext) -> Any:
    from ..ui import dates

    p = c.props
    callback = ctx.on(c, "change") if c.enabled else None

    def change(e: Any) -> Any:
        start, end = (_iso(d) for d in e.value)
        ctx.set(c, "start", start)
        ctx.set(c, "end", end)
        return callback((start, end)) if callback else None

    return _fill(dates.DateRangePicker((p["start"], p["end"]), format=p["format"] or "YYYY-MM-DD",
                                       separator=p["separator"] or " – ", placeholder=p["placeholder"],
                                       min=p["min"] or None, max=p["max"] or None, first_weekday=p["first_weekday"],
                                       months=max(1, int(_num(p["months"], 2))), presets=p["presets"],
                                       clearable=p["clearable"], disabled=not c.enabled, key=ctx.key(c),
                                       on_change=change if c.enabled else None, on_open=_raise(c, ctx, "open"),
                                       on_close=_raise(c, ctx, "close")), c)


def _time_picker(c: Control, ctx: RenderContext) -> Any:
    from ..ui import dates

    p = c.props
    return _fill(dates.TimePicker(p["value"], format=p["format"] or "HH:mm", placeholder=p["placeholder"],
                                  minute_step=max(1, int(_num(p["minute_step"], 5))), min=p["min"] or None,
                                  max=p["max"] or None, clearable=p["clearable"], disabled=not c.enabled,
                                  key=ctx.key(c), on_change=_changed(c, ctx, "value"),
                                  on_open=_raise(c, ctx, "open"), on_close=_raise(c, ctx, "close")), c)


# -- the operating system --------------------------------------------------------


def _file_input(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    mode = p["mode"]
    store = ctx.on(c, "change", "path") if c.enabled else None
    on_change = (lambda v: store("; ".join(v) if isinstance(v, list) else v)) if store else None
    return _fill(ui.file_input(p["path"], on_change, mode=mode, filters=p["filters"], title=p["title"] or None,
                               directory=p["directory"] or None, file_name=p["file_name"],
                               placeholder=p["placeholder"] or None, button=p["button"] or None,
                               disabled=not c.enabled, id=ctx.key(c), theme=ctx.theme), c)


def _drop_zone(c: Control, ctx: RenderContext) -> Any:
    from ..ui import system

    p = c.props

    def files(e: Any) -> Any:
        ctx.set(c, "files", "\n".join(e.value))
        return ctx.on(c, "files")(e.value) if c.events.get("files") else None

    return system.DropZone(text=p["text"], hint=p["hint"], icon_name=p["icon"] or "upload",
                           accept=_lines(p["accept"]), multiple=p["multiple"], browse=p["browse"],
                           show_files=p["show_files"], files=_lines(p["files"]), disabled=not c.enabled,
                           live=ctx.live, key=ctx.key(c), on_files=files if ctx.live else None,
                           on_drop=_raise(c, ctx, "drop"), on_reject=_raise(c, ctx, "reject"),
                           on_enter=_raise(c, ctx, "enter"), on_leave=_raise(c, ctx, "leave"))


ALIGN = Prop("align", "choice", "left", choices=("left", "center", "right"))

WEEK_START = Prop("first_weekday", "choice", "monday", choices=("monday", "sunday", "saturday"), label="Week starts on",
                  group="Behavior")
DATE_LIMITS = (Prop("min", "text", "", label="Earliest (YYYY-MM-DD)", group="Behavior"),
               Prop("max", "text", "", label="Latest (YYYY-MM-DD)", group="Behavior"))
DATE_FORMATS = ("YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD.MM.YYYY", "D MMM YYYY", "MMM D, YYYY",
                "ddd, D MMM YYYY", "dddd, D MMMM YYYY")

for _component in (
    Component("label", "Label", "type", "Common", _label, (120, 24),
              (Prop("text", "text", "Label"), Prop("size", "choice", "md", choices=TEXT_SIZES),
               Prop("color", "color", "text"), Prop("weight", "choice", "normal", choices=WEIGHTS), ALIGN,
               Prop("wrap", "bool", True)),
              ("click", "double_click"), "Static text."),
    Component("heading", "Heading", "heading", "Common", _heading, (240, 36),
              (Prop("text", "text", "Heading"), Prop("level", "choice", "1", choices=("1", "2", "3")), ALIGN),
              (), "A title."),
    Component("button", "Button", "mouse-pointer-click", "Common", _button, (112, 28),
              (Prop("text", "text", "Button"), Prop("variant", "choice", "filled", choices=VARIANTS),
               Prop("icon", "icon", "")),
              ("click",), "Runs code when pressed."),
    Component("input", "Text box", "text-cursor-input", "Forms", _input, (200, 28),
              (Prop("text", "text", "", group="Data"), Prop("placeholder", "text", "Type here…"),
               Prop("icon", "icon", ""), Prop("secure", "bool", False, label="Password")),
              ("change", "submit"), "Single-line text entry."),
    Component("text_area", "Text area", "file-text", "Forms", _text_area, (280, 120),
              (Prop("text", "multiline", "", group="Data"), Prop("placeholder", "text", "Write something…"),
               Prop("language", "choice", "txt", choices=("txt", "py", "md", "json", "toml", "rs", "js", "sql")),
               Prop("line_numbers", "bool", False), Prop("wrap", "bool", True)),
              ("change",), "Multi-line text, with optional syntax highlighting."),
    Component("checkbox", "Check box", "square-check", "Forms", _checkbox, (140, 24),
              (Prop("text", "text", "Check box"), Prop("checked", "bool", False, group="Data")),
              ("change",), "An on/off option."),
    Component("switch", "Switch", "toggle-right", "Forms", _switch, (140, 24),
              (Prop("text", "text", "Switch"), Prop("checked", "bool", False, group="Data")),
              ("change",), "A toggle, like Zed's settings switches."),
    Component("radio", "Radio group", "circle-dot", "Forms", _radio, (160, 72),
              (Prop("options", "list", "Option A\nOption B\nOption C", group="Data"),
               Prop("selected", "text", "Option A", group="Data"), Prop("horizontal", "bool", False)),
              ("change",), "Pick one of several options."),
    Component("select", "Drop-down", "chevron-down", "Forms", _select, (180, 28),
              (Prop("options", "list", "One\nTwo\nThree", group="Data"), Prop("selected", "text", "", group="Data"),
               Prop("placeholder", "text", "Select…")),
              ("change",), "A drop-down list."),
    Component("slider", "Slider", "sliders-horizontal", "Forms", _slider, (200, 24),
              (Prop("value", "number", 50, group="Data"), Prop("min", "number", 0, group="Data"),
               Prop("max", "number", 100, group="Data"), Prop("step", "number", 1, group="Data"),
               Prop("vertical", "bool", False), Prop("show_value", "bool", False, label="Show value")),
              ("change", "release"), "Choose a number by dragging."),
    Component("number", "Number box", "hash", "Forms", _number, (128, 28),
              (Prop("value", "number", 0, group="Data"), Prop("min", "number", None, group="Data"),
               Prop("max", "number", None, group="Data"), Prop("step", "number", 1, group="Data")),
              ("change",), "A numeric field with steppers."),
    Component("list_box", "List box", "list", "Forms", _list_box, (180, 140),
              (Prop("items", "list", "First\nSecond\nThird", group="Data"),
               Prop("selected", "text", "", group="Data")),
              ("change", "open"), "A scrollable list of items."),
    # -- dates and times
    Component("date_picker", "Date picker", "calendar-days", "Date & time", _date_picker, (180, 30),
              (Prop("value", "text", "", label="Date (YYYY-MM-DD)", group="Data"),
               Prop("format", "choice", "YYYY-MM-DD", choices=DATE_FORMATS), Prop("placeholder", "text", ""),
               *DATE_LIMITS, Prop("disabled_dates", "list", "", label="Days off", group="Behavior"), WEEK_START,
               Prop("week_numbers", "bool", False, label="Week numbers"), Prop("clearable", "bool", True),
               Prop("today_button", "bool", True, label="Today button")),
              ("change", "open", "close"), "A date field that opens a calendar; it can also be typed in the chosen "
              "format, and ↑/↓ change the day."),
    Component("date_range", "Date range", "calendar-range", "Date & time", _date_range, (240, 30),
              (Prop("start", "text", "", label="From (YYYY-MM-DD)", group="Data"),
               Prop("end", "text", "", label="To (YYYY-MM-DD)", group="Data"),
               Prop("format", "choice", "YYYY-MM-DD", choices=DATE_FORMATS), Prop("separator", "text", " – "),
               Prop("placeholder", "text", ""), *DATE_LIMITS, WEEK_START,
               Prop("months", "number", 2, min=1, max=3, label="Months shown"),
               Prop("presets", "bool", True, label="Quick ranges"), Prop("clearable", "bool", True)),
              ("change", "open", "close"), "A start and an end date picked on two months, with quick ranges such "
              "as \"Last 7 days\"."),
    Component("time_picker", "Time picker", "clock", "Date & time", _time_picker, (140, 30),
              (Prop("value", "text", "", label="Time (HH:MM)", group="Data"),
               Prop("format", "choice", "HH:mm", choices=("HH:mm", "HH:mm:ss", "h:mm A", "h:mm:ss A")),
               Prop("placeholder", "text", ""), Prop("minute_step", "number", 5, min=1, max=30, label="Minute step"),
               Prop("min", "text", "", label="Earliest (HH:MM)", group="Behavior"),
               Prop("max", "text", "", label="Latest (HH:MM)", group="Behavior"), Prop("clearable", "bool", True)),
              ("change", "open", "close"), "A time field with lists of hours and minutes, in 24 or 12 hours."),
    Component("calendar", "Calendar", "calendar", "Date & time", _calendar, (252, 296),
              (Prop("value", "text", "", label="Date (YYYY-MM-DD)", group="Data"),
               Prop("mode", "choice", "single", choices=("single", "range", "multiple"), group="Behavior"),
               *DATE_LIMITS, Prop("disabled", "list", "", label="Days off", group="Behavior"), WEEK_START,
               Prop("months", "number", 1, min=1, max=3, label="Months shown"),
               Prop("week_numbers", "bool", False, label="Week numbers"),
               Prop("today_button", "bool", False, label="Today button")),
              ("change", "month"), "A month to pick a day, a range of days or several days on."),
    Component("progress", "Progress bar", "loader", "Display", _progress, (200, 8),
              (Prop("value", "number", 40, group="Data"), Prop("max", "number", 100, group="Data"),
               Prop("tint", "choice", "accent", choices=TINTS)),
              (), "Shows how far a task has got."),
    Component("badge", "Badge", "tag", "Display", _badge, (80, 22),
              (Prop("text", "text", "New"), Prop("tint", "choice", "accent", choices=TINTS), Prop("icon", "icon", "")),
              (), "A small status label."),
    Component("image", "Image", "image", "Display", _image, (160, 120),
              (Prop("source", "file", "", label="File", accept="image"),
               Prop("fit", "choice", "cover", choices=("contain", "cover", "fill", "none", "scale-down")),
               Prop("radius", "number", 0)),
              ("click", "double_click"), "A picture from a file."),
    Component("shader", "Shader", "blend", "Display", _shader, (240, 160),
              (Prop("file", "file", "", label="Shader file", accept="shader"),
               Prop("variables", "typed", {}, type="dict[str, float | str]", group="Data")),
              (), "A shader made of nodes (.pzshad) drawn on the GPU; set its variables to animate it."),
    Component("icon", "Icon", "star", "Display", _icon_control, (24, 24),
              (Prop("name", "icon", "star"), Prop("size", "number", 20), Prop("color", "color", "")),
              ("click", "double_click"), "A Lucide icon."),
    Component("markdown", "Markdown", "file-text", "Display", _markdown, (280, 120),
              (Prop("text", "multiline", "## Title\n\nSome **rich** text."),),
              ("link",), "Formatted text; links open in the browser unless its link event is handled."),
    Component("spinner", "Spinner", "loader-circle", "Display", _spinner, (24, 24),
              (Prop("tint", "choice", "accent", choices=TINTS),),
              (), "An activity indicator."),
    Component("panel", "Panel", "panel-top", "Containers", _panel, (240, 160),
              (Prop("title", "text", ""), Prop("background", "color", ""), Prop("border", "bool", True)),
              (), "A surface to group related controls; drop controls on it to put them inside.",
              container="free"),
    Component("divider", "Divider", "minus", "Containers", _divider, (200, 8),
              (Prop("vertical", "bool", False),),
              (), "A separator line."),
    Component("row", "Flex row", "columns-3", "Layout", _flex, (320, 48),
              (Prop("direction", "choice", "row", choices=("row", "column"), group="Layout"),
               Prop("gap", "number", 8, min=0, group="Layout"), Prop("padding", "number", 0, min=0, group="Layout"),
               Prop("justify", "choice", "start",
                    choices=("start", "center", "end", "space-between", "space-around", "space-evenly"),
                    group="Layout"),
               Prop("align", "choice", "stretch", choices=("stretch", "start", "center", "end"), group="Layout"),
               Prop("background", "color", "")),
              (), "Lines up the controls inside it side by side, like CSS flexbox.", container="flex"),
    Component("column", "Flex column", "rows-3", "Layout", _flex, (200, 200),
              (Prop("direction", "choice", "column", choices=("row", "column"), group="Layout"),
               Prop("gap", "number", 8, min=0, group="Layout"), Prop("padding", "number", 0, min=0, group="Layout"),
               Prop("justify", "choice", "start",
                    choices=("start", "center", "end", "space-between", "space-around", "space-evenly"),
                    group="Layout"),
               Prop("align", "choice", "stretch", choices=("stretch", "start", "center", "end"), group="Layout"),
               Prop("background", "color", "")),
              (), "Stacks the controls inside it from top to bottom.", container="flex"),
    Component("grid", "Grid", "layout-grid", "Layout", _grid, (320, 160),
              (Prop("columns", "number", 2, min=1, max=24, group="Layout"),
               Prop("gap", "number", 8, min=0, group="Layout"), Prop("padding", "number", 0, min=0, group="Layout"),
               Prop("row_height", "number", 0, min=0, label="Row height (0 = share)", group="Layout"),
               Prop("align", "choice", "stretch", choices=("stretch", "start", "center", "end"), group="Layout"),
               Prop("background", "color", "")),
              (), "Places the controls inside it in cells, left to right.", container="grid"),
    Component("dock", "Dock", "layout-dashboard", "Layout", _dock, (640, 400),
              (Prop("left_size", "number", 220, min=0, label="Left width", group="Layout"),
               Prop("right_size", "number", 260, min=0, label="Right width", group="Layout"),
               Prop("top_size", "number", 140, min=0, label="Top height", group="Layout"),
               Prop("bottom_size", "number", 160, min=0, label="Bottom height", group="Layout"),
               Prop("layout", "typed", {}, type="dict", group="Data", label="Saved layout")),
              ("layout",), "Panels docked to the sides of a center area, like Zed: their tabs switch them, "
              "dragging a tab moves it to another side and dragging the inner edge resizes it.", container="dock",
              children=(("dock_panel", (("title", "Explorer"), ("icon", "folder"), ("side", "left"))),
                        ("dock_panel", (("title", "Terminal"), ("icon", "square-terminal"), ("side", "bottom"))),
                        ("dock_panel", (("title", "Editor"), ("icon", ""), ("side", "center"))))),
    Component("dock_panel", "Dock panel", "panel-left", "Layout", _dock_panel, (220, 240),
              (Prop("title", "text", "Panel"), Prop("icon", "icon", ""),
               Prop("side", "choice", "left", choices=("left", "right", "top", "bottom", "center"), group="Layout"),
               Prop("background", "color", "")),
              (), "A panel of a Dock: put it inside a Dock, pick its side and drop controls on it.", container="free"),
    Component("spacer", "Spacer", "move-horizontal", "Layout", _spacer, (24, 24), (),
              (), "Empty space that grows to push its neighbours apart in a flex row or column.",
              child_layout=(("grow", 1),)),
    Component("group_box", "Group box", "square-dashed", "Containers", _group_box, (240, 140),
              (Prop("title", "text", "Group"),),
              (), "A titled frame around related controls.", container="free"),
    Component("card", "Card", "square", "Containers", _card, (260, 160),
              (Prop("title", "text", "Card"), Prop("shadow", "bool", True)),
              (), "A raised surface holding other controls.", container="free"),
    Component("link", "Link", "link", "Common", _link, (100, 22),
              (Prop("text", "text", "Learn more"), ALIGN),
              ("click",), "Clickable text."),
    Component("search", "Search box", "search", "Forms", _search, (220, 28),
              (Prop("text", "text", "", group="Data"), Prop("placeholder", "text", "Search…")),
              ("change", "submit"), "A text box with a search icon."),
    Component("segmented", "Segmented", "toggle-left", "Forms", _segmented, (240, 28),
              (Prop("options", "list", "Day\nWeek\nMonth", group="Data"),
               Prop("selected", "text", "Day", group="Data")),
              ("change",), "Pick one of a few options, side by side."),
    Component("tabs", "Tab bar", "panels-top-left", "Navigation", _tabs, (320, 32),
              (Prop("tabs", "list", "General\nAdvanced\nAbout", group="Data"),
               Prop("selected", "text", "General", group="Data"), Prop("closable", "bool", False)),
              ("change", "close"), "Tabs; show or hide panels from its change event."),
    Component("chip", "Chip", "tag", "Display", _chip, (90, 26),
              (Prop("text", "text", "Filter"), Prop("icon", "icon", ""), Prop("selected", "bool", False, group="Data"),
               Prop("tint", "choice", "accent", choices=TINTS), Prop("removable", "bool", False)),
              ("click", "remove"), "A compact, clickable tag; removable ones have an x."),
    Component("callout", "Callout", "info", "Display", _callout, (320, 64),
              (Prop("title", "text", "Heads up"), Prop("text", "text", "Something worth knowing."),
               Prop("tint", "choice", "info", choices=TINTS), Prop("icon", "icon", "")),
              (), "A highlighted message."),
    Component("avatar", "Avatar", "circle-user", "Display", _avatar, (32, 32),
              (Prop("initials", "text", "PZ"), Prop("color", "color", "")),
              ("click", "double_click"), "Initials in a circle."),
    Component("kbd", "Key binding", "keyboard", "Display", _kbd, (80, 22),
              (Prop("keys", "text", "ctrl-s"),),
              (), "Keys shown as key caps."),
    Component("stat", "Stat", "trending-up", "Display", _stat, (180, 84),
              (Prop("title", "text", "Revenue"), Prop("value", "text", "$12.4k"), Prop("delta", "number", 4.2),
               Prop("trend", "list", "", label="Trend values")),
              (), "A figure with its change and trend."),
    Component("chart", "Chart", "chart-column", "Display", _chart, (280, 140),
              (Prop("kind", "choice", "bar", choices=("bar", "line", "donut")),
               Prop("values", "text", "3 5 2 8 6 9", group="Data"), Prop("labels", "list", "", group="Data"),
               Prop("tint", "choice", "accent", choices=TINTS)),
              (), "A bar, line or donut chart."),
    Component("table", "Table", "table", "Display", _table, (360, 160),
              (Prop("data", "rows", "Name, Role\nAda, Engineer\nGrace, Admiral", group="Data", label="Rows"),
               Prop("selected", "number", None, group="Data"), Prop("striped", "bool", True),
               Prop("sortable", "bool", False, group="Behavior"), Prop("sort_by", "text", "", group="Behavior"),
               Prop("descending", "bool", False, group="Behavior")),
              ("change", "open", "sort"), "Rows and columns from comma-separated text; change gives the row index."),
    Component("toggle_group", "Toggle group", "toggle-left", "Forms", _toggle_group, (96, 30),
              (Prop("options", "list", "left, align-left, Left\ncenter, align-center, Center\nright, align-right, Right",
                    group="Data"),
               Prop("selected", "list", "left", group="Data"), Prop("multiple", "bool", False, group="Behavior")),
              ("change",), "Icon buttons where one (or several) stay pressed, like text alignment in a toolbar."),
    Component("split_button", "Split button", "square-chevron-down", "Common", _split_button, (148, 28),
              (Prop("text", "text", "Save"), Prop("variant", "choice", "filled", choices=VARIANTS),
               Prop("icon", "icon", ""), Prop("items", "list", "Save as…\nSave all", group="Data")),
              ("click", "choose", "menu"), "A button with a menu of related actions next to it."),
    Component("tree", "Tree view", "list-tree", "Navigation", _tree, (220, 200),
              (Prop("items", "multiline", "Documents\n  Notes.md\n  Plans\n    2026.md\nPictures\n  cat.png",
                    group="Data"),
               Prop("selected", "text", "", group="Data"), Prop("expanded", "list", "Documents", group="Data"),
               Prop("border", "bool", True)),
              ("change", "open", "toggle"), "A folding tree of items; indent an item to put it inside the one above."),
    Component("breadcrumbs", "Breadcrumbs", "chevrons-right", "Navigation", _breadcrumbs, (240, 24),
              (Prop("parts", "list", "Home\nProjects\nPyzed", group="Data"), Prop("separator", "text", "›")),
              ("click",), "Where you are, such as Home › Projects › Pyzed; each part can be clicked."),
    Component("empty_state", "Empty state", "inbox", "Display", _empty_state, (280, 160),
              (Prop("title", "text", "Nothing here yet"), Prop("text", "text", "Items you add show up here."),
               Prop("icon", "icon", "inbox"), Prop("size", "choice", "md", choices=("sm", "md", "lg"))),
              (), "A friendly placeholder for an empty list or a search without results."),
    Component("counter", "Counter badge", "circle-dot", "Display", _counter, (28, 20),
              (Prop("count", "number", 3, group="Data"), Prop("max", "number", 99, min=1),
               Prop("tint", "choice", "accent", choices=TINTS), Prop("show_zero", "bool", True, label="Show zero")),
              ("click", "double_click"), "A small round number, such as unread messages (99+ past the maximum)."),
    Component("status_dot", "Status dot", "circle", "Display", _status_dot, (12, 12),
              (Prop("color", "color", "success"), Prop("text", "text", "")),
              ("click", "double_click"), "A colored dot, with an optional label: online, busy, failed..."),
    Component("facepile", "Facepile", "users", "Display", _facepile, (120, 24),
              (Prop("people", "list", "Ada Lovelace\nGrace Hopper\nAlan Turing", group="Data"),
               Prop("max_shown", "number", 5, min=1, label="Most shown")),
              ("click", "double_click"), "Overlapping avatars of people, with +N for the rest."),
    Component("diff_stat", "Diff stat", "diff", "Display", _diff_stat, (120, 20),
              (Prop("added", "number", 12, min=0, group="Data"), Prop("removed", "number", 3, min=0, group="Data")),
              (), "Lines added and removed, with colored blocks like GitHub."),
    Component("qr_code", "QR code", "qr-code", "Display", _qr_code, (120, 120),
              (Prop("data", "text", "https://github.com/albakore/pyzed", group="Data", label="Text or link"),
               Prop("cell_size", "number", 4, min=1, max=32), Prop("color", "color", "text"),
               Prop("background", "color", "")),
              ("click", "double_click"), "A QR code that phones can scan."),
    Component("svg", "SVG image", "shapes", "Display", _svg, (96, 96),
              (Prop("source", "file", "", label="File", accept="image"),
               Prop("fit", "choice", "contain", choices=("contain", "cover", "fill", "none", "scale-down")),
               Prop("color", "color", "", label="Tint"), Prop("opacity", "number", 1, min=0, max=1, step=0.1),
               Prop("rotation", "number", 0, label="Rotation (degrees)")),
              ("click", "double_click"), "A vector drawing from an .svg file, sharp at any size and tintable."),
    Component("image_viewer", "Image viewer", "zoom-in", "Display", _image_viewer, (280, 200),
              (Prop("source", "file", "", label="File", accept="image"), Prop("min_zoom", "number", 0.25, min=0.01, step=0.25),
               Prop("max_zoom", "number", 10, min=0.01, step=0.5)),
              (), "A picture you can zoom with the wheel and pan by dragging."),
    Component("terminal", "Terminal output", "square-terminal", "Display", _terminal, (360, 160),
              (Prop("text", "multiline", "$ pyzed run\n\x1b[32m✓ Ready\x1b[0m", group="Data"),
               Prop("font_size", "number", 13, min=8, max=32), Prop("follow", "bool", True, label="Follow output")),
              (), "Monospace output with ANSI colors, such as what a Process prints."),
    # -- the operating system
    Component("file_input", "File picker", "folder-open", SYSTEM, _file_input, (260, 30),
              (Prop("path", "text", "", group="Data"),
               Prop("mode", "choice", "open", choices=("open", "open_many", "save", "folder"), group="Behavior"),
               Prop("filters", "multiline", "", group="Behavior"), Prop("title", "text", "", label="Dialog title",
                                                                       group="Behavior"),
               Prop("directory", "text", "", label="Start folder", group="Behavior"),
               Prop("file_name", "text", "", label="Suggested name", group="Behavior"),
               Prop("placeholder", "text", ""), Prop("button", "text", "", label="Button text")),
              ("change",), "A path field with a button that opens the system's file dialog."),
    Component("drop_zone", "Drop zone", "upload", SYSTEM, _drop_zone, (260, 140),
              (Prop("text", "text", ""), Prop("hint", "text", ""), Prop("icon", "icon", "upload"),
               Prop("accept", "list", "", label="Accepted types", group="Behavior"),
               Prop("multiple", "bool", True, group="Behavior"),
               Prop("browse", "bool", True, label="Click to browse", group="Behavior"),
               Prop("show_files", "bool", False, label="List the files"), Prop("files", "list", "", group="Data")),
              ("drop", "files", "reject", "enter", "leave"),
              "Takes files dragged from the file manager onto the window; a click opens the file dialog."),
    # -- non-visual components: they sit in the tray under the form and draw nothing at run time
    Component("timer", "Timer", "timer", NON_VISUAL, _non_visual, TRAY_SIZE,
              (Prop("interval", "number", 1000, label="Interval (ms)", min=10, group="Behavior"),
               Prop("running", "bool", True, group="Behavior"), Prop("repeat", "bool", True, group="Behavior")),
              ("tick",), "Runs its tick event periodically. Invisible at run time.", visual=False),
    Component("shortcut", "Shortcut", "command", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("keys", "text", "ctrl-s", group="Behavior"),),
              ("activate",), "A keyboard shortcut for the whole window, such as ctrl-s.", visual=False),
    Component("file_watcher", "File watcher", "folder-search", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("path", "folder", ".", label="Path", group="Behavior"), Prop("pattern", "text", "*", group="Behavior"),
               Prop("recursive", "bool", False, label="Subfolders", group="Behavior"),
               Prop("interval", "number", 500, label="Interval (ms)", min=50, group="Behavior"),
               Prop("running", "bool", True, group="Behavior")),
              ("change", "created", "modified", "deleted"),
              "Raises events when files are created, modified or deleted in a folder.", visual=False),
    Component("process", "Process", "square-terminal", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("command", "text", "", group="Behavior"), Prop("directory", "folder", "", label="Folder", group="Behavior"),
               Prop("shell", "bool", False, label="Run in shell", group="Behavior"),
               Prop("autostart", "bool", False, label="Start on load", group="Behavior")),
              ("output", "error_output", "finished", "started", "failed"),
              "Runs a program or command and streams what it prints, line by line.", visual=False),
    Component("worker", "Background worker", "cpu", NON_VISUAL, _non_visual, TRAY_SIZE, (),
              ("work", "progress", "done", "failed"),
              "Runs slow work in a background thread so the window stays responsive.", visual=False),
    Component("http_request", "Web request", "globe", NON_VISUAL, _non_visual, TRAY_SIZE,
              (Prop("url", "text", "https://", label="Address", group="Behavior"),
               Prop("method", "choice", "GET", choices=("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"), group="Behavior"),
               Prop("headers", "multiline", "", group="Behavior"), Prop("body", "multiline", "", group="Behavior"),
               Prop("timeout", "number", 30, label="Timeout (s)", min=1, group="Behavior"),
               Prop("send_on_load", "bool", False, label="Send on load", group="Behavior")),
              ("response", "failed"), "Calls a web address or API in the background.", visual=False),
    Component("clipboard", "Clipboard", "clipboard", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("watch", "bool", False, label="Watch changes", group="Behavior"),
               Prop("interval", "number", 500, label="Interval (ms)", min=100, group="Behavior")),
              ("change", "paste"), "Copies and pastes text, and notices what is copied.", visual=False),
    Component("settings", "Settings", "settings-2", NON_VISUAL, _non_visual, TRAY_SIZE,
              (Prop("file", "file", "", label="File", group="Behavior", accept="data"),
               Prop("remember", "list", "", label="Remember", group="Behavior")),
              ("change",), "Keeps values between runs, and the values of the controls you list.", visual=False),
    Component("file_dialog", "File dialog", "folder-open", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("mode", "choice", "open", choices=("open", "open_many", "save", "folder"), group="Behavior"),
               Prop("title", "text", "", group="Behavior"), Prop("filters", "multiline", "", group="Behavior"),
               Prop("directory", "folder", "", label="Start folder", group="Behavior"),
               Prop("file_name", "text", "", label="Suggested name", group="Behavior")),
              ("chosen", "cancelled"), "The system's open, save and folder dialogs.", visual=False),
    Component("notification", "Notification", "bell", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("title", "text", "", group="Behavior"), Prop("text", "text", "", group="Behavior")),
              ("shown", "failed"), "A desktop notification.", visual=False),
    Component("tray_icon", "Tray icon", "monitor-dot", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("icon", "file", "", group="Behavior", accept="image"),
               Prop("tooltip", "text", "", group="Behavior"),
               Prop("menu", "multiline", "Open\n-\nQuit", group="Behavior"),
               Prop("show_on_load", "bool", True, label="Show when the form opens", group="Behavior")),
              ("click", "double_click", "menu", "failed"),
              "An icon in the system tray with a menu: one item per line, - for a separator, [x] for a check.",
              visual=False),
    Component("system_info", "System info", "monitor", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("interval", "number", 0, label="Check every (ms, 0 = once)", min=0, group="Behavior"),
               Prop("disk_path", "folder", "", label="Disk of", group="Behavior")),
              ("update",), "The system, user, folders, processors, memory and free disk space.", visual=False),
    Component("launcher", "Launcher", "external-link", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("target", "text", "", label="File, folder or link", group="Behavior"),),
              ("opened", "failed"), "Opens files, folders and links with the app the system uses for them.",
              visual=False),
    Component("network_monitor", "Network monitor", "wifi", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("host", "text", "1.1.1.1", group="Behavior"), Prop("port", "number", 53, group="Behavior"),
               Prop("interval", "number", 5000, label="Interval (ms)", min=500, group="Behavior"),
               Prop("running", "bool", True, group="Behavior")),
              ("change", "online", "offline"), "Notices when the computer goes online or offline.", visual=False),
    Component("power_monitor", "Battery monitor", "battery-medium", SYSTEM, _non_visual, TRAY_SIZE,
              (Prop("interval", "number", 30000, label="Interval (ms)", min=1000, group="Behavior"),
               Prop("low_level", "number", 20, label="Low below (%)", min=1, max=99, group="Behavior"),
               Prop("running", "bool", True, group="Behavior")),
              ("change", "low", "plugged", "unplugged"), "The battery's charge and whether it is plugged in.",
              visual=False),
):
    register(_component)


# -- components made with pyzed.Component ------------------------------------
# They join the toolbox as they are defined (see `Component.__init_subclass__`);
# this picks up the ones defined before the designer was imported.
def _register_user_components() -> None:
    from ..component import registered

    for cls in registered():
        register(cls.designer_spec())


_register_user_components()
