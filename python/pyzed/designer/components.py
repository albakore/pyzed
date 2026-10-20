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

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .. import _core, ui
from ..icons import icon as _icon
from ..theme import Theme, current
from .model import Control

#: Property editors the designer knows how to show.
PROP_KINDS = ("text", "multiline", "number", "bool", "color", "choice", "list", "rows", "icon")

#: Mouse events every visible control supports (in addition to its own).
COMMON_EVENTS = ("mouse_enter", "mouse_leave", "right_click")

#: Events of the form itself.
FORM_EVENTS = ("load", "close", "key", "resize")

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
}


@dataclass(frozen=True)
class Prop:
    """A property shown in the designer's property grid.

    ``kind`` picks the editor: text, multiline, number, bool, color, choice (from
    ``choices``), list (one item per line), rows (comma-separated rows, the first one the
    header), icon (a Lucide icon name) or typed (any annotation in ``type``: unions, optionals,
    dicts, tuples...).
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

    def __init__(self, theme: Optional[Theme] = None, form_name: str = "form") -> None:
        self.theme = theme or current()
        self.form_name = form_name

    def on(self, control: Control, event: str, prop: Optional[str] = None) -> Callable[..., Any]:
        """A callback for ``event``; when ``prop`` is given the value is also stored there."""
        return _inert

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
    #: ``"free"``, ``"flex"`` or ``"grid"`` when other controls can be placed inside (see ``layout``).
    container: Optional[str] = None
    #: Layout options given to new controls of this type (``(("grow", 1),)`` for a spacer).
    child_layout: Tuple[Tuple[str, Any], ...] = ()

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


def all_components() -> List[Component]:
    """Returns every registered component, in registration order."""
    return list(_REGISTRY.values())


def categories() -> Dict[str, List[Component]]:
    """Returns the registered components grouped by ``category`` (toolbox sections), in registration order."""
    out: Dict[str, List[Component]] = {}
    for c in _REGISTRY.values():
        out.setdefault(c.category, []).append(c)
    return out


def render(control: Control, ctx: RenderContext) -> Any:
    """Draws ``control`` at its size (its own props, falling back to the component defaults)."""
    from .binding import translate

    spec = get(control.type)
    props = {k: translate(v, ctx.language) for k, v in {**spec.defaults(), **control.props}.items()}
    merged = Control(**{**control.__dict__, "props": props})
    widget = styled(spec.render(merged, ctx), control, ctx)
    widget = animated(widget, control, ctx)
    # shadows, glows and motion are drawn outside the box: clipping would cut them off
    from . import motion

    return _core.container(widget, width=control.width, height=control.height,
                           clip=not motion.moves(control.animations, control.style))


def animated(widget: Any, control: Control, ctx: RenderContext) -> Any:
    """``widget`` with the control's animations: always in a running form, and in the designer only
    while its Preview plays (``ctx.preview`` maps control names to a restart counter)."""
    if not control.animations:
        return widget
    from . import motion

    if ctx.live:
        return motion.apply(widget, control.animations)
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


def _label(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    text = ui.label(p["text"], size=p["size"], color=p["color"] or "text",
                    weight=None if p["weight"] == "normal" else p["weight"], wrap=p["wrap"], theme=ctx.theme)
    widget = _fill(text, c, align_x=_align(p["align"]))
    if c.events.get("click") or c.events.get("double_click"):
        widget = _core.mouse_area(widget, on_press=ctx.on(c, "click") if c.events.get("click") else None,
                                  on_double_click=ctx.on(c, "double_click") if c.events.get("double_click") else None,
                                  cursor="pointer" if ctx.live else None)
    return widget


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
    return _fill(ui.slider(value, ctx.on(c, "change", "value") if c.enabled else None, min=lo, max=hi,
                           step=_num(p["step"], 1) or 1, theme=ctx.theme), c)


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
    return _core.image(source, width="fill", height="fill", content_fit=c.props["fit"],
                       radius=_num(c.props["radius"]))


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
    return _core.container(_icon(p["name"] or "star", size=_num(p["size"], 20), color=color), width="fill",
                           height="fill", center=True)


def _list_box(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    p = c.props
    on_select = ctx.on(c, "change", "selected")
    rows = [ui.list_item(item, (lambda item=item: on_select(item)) if ctx.live else None,
                         selected=item == p["selected"], theme=t)
            for item in _lines(p["items"])]
    return _core.container(
        _core.scrollable(_core.column(rows, width="fill", padding=4)),
        width="fill", height="fill", bg=t.editor, border_color=t.border_variant, border_width=1,
        radius=t.radius_sm)


def _markdown(c: Control, ctx: RenderContext) -> Any:
    return _core.scrollable(ui.markdown(c.props["text"], width="fill", theme=ctx.theme))


def _spinner(c: Control, ctx: RenderContext) -> Any:
    return _core.container(ui.spinner(size=min(c.width, c.height) * 0.8, tint=c.props["tint"], theme=ctx.theme),
                           width="fill", height="fill", center=True)


def _timer(c: Control, ctx: RenderContext) -> Any:
    t = ctx.theme
    return _core.container(
        _core.row([_icon("timer", size=14, color=t.icon_muted),
                   ui.label(c.name, size="sm", color="text_muted", theme=t)], spacing=6, align="center"),
        width="fill", height="fill", center=True, bg=t.element, radius=t.radius_sm,
        border_color=t.border_variant, border_width=1)


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
    return _core.container(ui.tab_bar(tabs, selected, on_select=ctx.on(c, "change", "selected"),
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
    return _core.container(ui.avatar(p["initials"] or "?", color=p["color"] or None, size=size, theme=ctx.theme),
                           width="fill", height="fill", center=True)


def _chip(c: Control, ctx: RenderContext) -> Any:
    p = c.props
    return _fill(ui.chip(p["text"], on_press=ctx.on(c, "click") if ctx.live else None, selected=bool(p["selected"]),
                         icon=p["icon"] or None, theme=ctx.theme), c)


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
    return _core.container(
        ui.table(header, rows, striped=bool(p["striped"]), height="fill",
                 on_row_press=(lambda row: on_row(rows.index(row) if row in rows else row)) if ctx.live else None,
                 selected=rows[int(selected)] if isinstance(selected, int) and 0 <= selected < len(rows) else None,
                 theme=ctx.theme),
        width="fill", height="fill", border_color=ctx.theme.border_variant, border_width=1,
        radius=ctx.theme.radius_sm, clip=True)


ALIGN = Prop("align", "choice", "left", choices=("left", "center", "right"))

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
    Component("input", "Text box", "text-cursor-input", "Common", _input, (200, 28),
              (Prop("text", "text", "", group="Data"), Prop("placeholder", "text", "Type here…"),
               Prop("icon", "icon", ""), Prop("secure", "bool", False, label="Password")),
              ("change", "submit"), "Single-line text entry."),
    Component("text_area", "Text area", "file-text", "Common", _text_area, (280, 120),
              (Prop("text", "multiline", "", group="Data"), Prop("placeholder", "text", "Write something…"),
               Prop("language", "choice", "txt", choices=("txt", "py", "md", "json", "toml", "rs", "js", "sql")),
               Prop("line_numbers", "bool", False), Prop("wrap", "bool", True)),
              ("change",), "Multi-line text, with optional syntax highlighting."),
    Component("checkbox", "Check box", "square-check", "Common", _checkbox, (140, 24),
              (Prop("text", "text", "Check box"), Prop("checked", "bool", False, group="Data")),
              ("change",), "An on/off option."),
    Component("switch", "Switch", "toggle-right", "Common", _switch, (140, 24),
              (Prop("text", "text", "Switch"), Prop("checked", "bool", False, group="Data")),
              ("change",), "A toggle, like Zed's settings switches."),
    Component("radio", "Radio group", "circle-dot", "Common", _radio, (160, 72),
              (Prop("options", "list", "Option A\nOption B\nOption C", group="Data"),
               Prop("selected", "text", "Option A", group="Data"), Prop("horizontal", "bool", False)),
              ("change",), "Pick one of several options."),
    Component("select", "Drop-down", "chevron-down", "Common", _select, (180, 28),
              (Prop("options", "list", "One\nTwo\nThree", group="Data"), Prop("selected", "text", "", group="Data"),
               Prop("placeholder", "text", "Select…")),
              ("change",), "A drop-down list."),
    Component("slider", "Slider", "sliders-horizontal", "Common", _slider, (200, 24),
              (Prop("value", "number", 50, group="Data"), Prop("min", "number", 0, group="Data"),
               Prop("max", "number", 100, group="Data"), Prop("step", "number", 1, group="Data")),
              ("change",), "Choose a number by dragging."),
    Component("number", "Number box", "hash", "Common", _number, (128, 28),
              (Prop("value", "number", 0, group="Data"), Prop("min", "number", None, group="Data"),
               Prop("max", "number", None, group="Data"), Prop("step", "number", 1, group="Data")),
              ("change",), "A numeric field with steppers."),
    Component("list_box", "List box", "list", "Common", _list_box, (180, 140),
              (Prop("items", "list", "First\nSecond\nThird", group="Data"),
               Prop("selected", "text", "", group="Data")),
              ("change",), "A scrollable list of items."),
    Component("progress", "Progress bar", "loader", "Display", _progress, (200, 8),
              (Prop("value", "number", 40, group="Data"), Prop("max", "number", 100, group="Data"),
               Prop("tint", "choice", "accent", choices=TINTS)),
              (), "Shows how far a task has got."),
    Component("badge", "Badge", "tag", "Display", _badge, (80, 22),
              (Prop("text", "text", "New"), Prop("tint", "choice", "accent", choices=TINTS), Prop("icon", "icon", "")),
              (), "A small status label."),
    Component("image", "Image", "image", "Display", _image, (160, 120),
              (Prop("source", "text", "", label="File"),
               Prop("fit", "choice", "cover", choices=("contain", "cover", "fill", "none", "scale-down")),
               Prop("radius", "number", 0)),
              (), "A picture from a file."),
    Component("shader", "Shader", "blend", "Display", _shader, (240, 160),
              (Prop("file", "text", "", label="Shader file"),
               Prop("variables", "typed", {}, type="dict[str, float | str]", group="Data")),
              (), "A shader made of nodes (.pzshad) drawn on the GPU; set its variables to animate it."),
    Component("icon", "Icon", "star", "Display", _icon_control, (24, 24),
              (Prop("name", "icon", "star"), Prop("size", "number", 20), Prop("color", "color", "")),
              (), "A Lucide icon."),
    Component("markdown", "Markdown", "file-text", "Display", _markdown, (280, 120),
              (Prop("text", "multiline", "## Title\n\nSome **rich** text."),),
              (), "Formatted text."),
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
    Component("search", "Search box", "search", "Common", _search, (220, 28),
              (Prop("text", "text", "", group="Data"), Prop("placeholder", "text", "Search…")),
              ("change", "submit"), "A text box with a search icon."),
    Component("segmented", "Segmented", "toggle-left", "Common", _segmented, (240, 28),
              (Prop("options", "list", "Day\nWeek\nMonth", group="Data"),
               Prop("selected", "text", "Day", group="Data")),
              ("change",), "Pick one of a few options, side by side."),
    Component("tabs", "Tab bar", "panels-top-left", "Navigation", _tabs, (320, 32),
              (Prop("tabs", "list", "General\nAdvanced\nAbout", group="Data"),
               Prop("selected", "text", "General", group="Data")),
              ("change",), "Tabs; show or hide panels from its change event."),
    Component("chip", "Chip", "tag", "Display", _chip, (90, 26),
              (Prop("text", "text", "Filter"), Prop("icon", "icon", ""), Prop("selected", "bool", False, group="Data")),
              ("click",), "A compact, clickable tag."),
    Component("callout", "Callout", "info", "Display", _callout, (320, 64),
              (Prop("title", "text", "Heads up"), Prop("text", "text", "Something worth knowing."),
               Prop("tint", "choice", "info", choices=TINTS), Prop("icon", "icon", "")),
              (), "A highlighted message."),
    Component("avatar", "Avatar", "circle-user", "Display", _avatar, (32, 32),
              (Prop("initials", "text", "PZ"), Prop("color", "color", "")),
              (), "Initials in a circle."),
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
               Prop("selected", "number", None, group="Data"), Prop("striped", "bool", True)),
              ("change",), "Rows and columns from comma-separated text; change gives the row index."),
    Component("timer", "Timer", "timer", "Components", _timer, (88, 24),
              (Prop("interval", "number", 1000, label="Interval (ms)", min=10, group="Behavior"),
               Prop("running", "bool", True, group="Behavior")),
              ("tick",), "Runs its tick event periodically. Invisible at run time.", visual=False),
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
