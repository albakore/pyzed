"""The design surface: the form being edited, its dot grid, selection, handles and rubber band.

Layers, bottom to top (one ``stack`` sized like the form):

1. the form background and the dot grid (a cached ``canvas``);
2. every control, drawn by its component exactly as it will run, but inert;
3. one transparent hit box per control that selects, drags and double-clicks;
4. selection outlines, resize handles and the rubber band / new-control preview;
5. a grip tab on containers that hold controls, to select and drag the container itself
   (its own area is mostly covered by its children's hit boxes).

Non-visual components (timers, file watchers, processes...) are not drawn on the form: they sit in
the component tray under it, as in Visual Basic and Qt Designer (``tray``).

The stack sits in a ``mouse_area`` whose ``on_move`` reports the pointer in form
coordinates (where a click lands); the scroll view around it has another one that
reports view coordinates, whose deltas drive drags even past the form's edges.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Tuple

from .. import _core, draw, ui
from ..icons import icon as _icon
from ..theme import Theme, alpha
from . import components as _components
from . import layout as _layout
from . import styling
from .geometry import HANDLES
from .locale import tr
from .model import Control
from .binding import translate
from .runtime import theme_for

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

CHROME_HEIGHT = 30.0
MARGIN = 48.0
HANDLE = 7.0
GRIP_HEIGHT = 16.0
#: Width of a chip in the component tray, and the gap between chips.
TRAY_CHIP = 150.0
TRAY_GAP = 6.0

_grid_cache: dict = {}


def dot_grid(width: float, height: float, step: int, color: str) -> List[Any]:
    """Canvas shapes for a grid of dots every ``step`` pixels (memoized: forms rarely change size)."""
    key = (width, height, step, color)
    shapes = _grid_cache.get(key)
    if shapes is None:
        step = max(int(step), 4)
        dots = [(x - 0.75, y - 0.75, 1.5, 1.5)
                for y in range(step, int(height), step) for x in range(step, int(width), step)]
        shapes = [draw.rects(dots, fill=color)]
        _grid_cache.clear()
        _grid_cache[key] = shapes
    return shapes


def frame_style(d: "Designer") -> str:
    """The platform whose window frame the canvas shows around the form: the one picked in the designer, or
    this system's."""
    return d.preview_frame or ui.system_platform()


def _chrome(title: str, width: float, t: Theme, component: bool = False, style: str = "macos") -> Any:
    if component:  # not a window: no window buttons, and the bar says what it is
        return _core.container(
            _core.row([_icon("component", size=13, color=t.accent),
                       ui.label(f"{tr('Component')} · {title}", size="sm", color="accent", theme=t, wrap=False)],
                      spacing=6, align="center"),
            width=width, height=CHROME_HEIGHT, padding=(0, 10), align_y="center", bg=alpha(t.accent, 0.12),
        )
    # the title bar the form gets on that platform, drawn but inert
    return ui.window_title_bar(title, style=style, width=width, theme=t)


def _handles(d: "Designer", rect: Tuple[float, float, float, float], t: Theme) -> List[Any]:
    x, y, w, h = rect
    spots = {
        "nw": (x, y), "n": (x + w / 2, y), "ne": (x + w, y), "e": (x + w, y + h / 2),
        "se": (x + w, y + h), "s": (x + w / 2, y + h), "sw": (x, y + h), "w": (x, y + h / 2),
    }
    cursors = {"n": "resize-vertical", "s": "resize-vertical", "e": "resize-horizontal", "w": "resize-horizontal"}
    out = []
    for name in HANDLES:
        hx, hy = spots[name]
        box = _core.container(width=HANDLE, height=HANDLE, bg=t.background, border_color=t.accent,
                              border_width=1.5, radius=1.5)
        out.append(_core.pin(_core.mouse_area(box, on_press=lambda n=name: d.press_handle(n),
                                              cursor=cursors.get(name, "crosshair")),
                             x=hx - HANDLE / 2, y=hy - HANDLE / 2))
    return out


def grips(d: "Designer") -> List[Tuple[str, float, float]]:
    """``(name, x, y)`` of the grip tab for each container that holds controls and is selected,
    holds the selection or is under the pointer. The tab sits just above the container's top-left
    corner, or inside it when the container touches the top of the form, clear of the corner's
    resize handle."""
    doc = d.doc
    form = doc.form
    if d.tool or (d.drag is not None and d.drag.mode != "band") or d.carry is not None:
        return []
    rects = d.rects
    wanted = set()
    for c in doc.selected:
        wanted.add(c.name)
        wanted.update(a.name for a in form.ancestors(c.name))
    if d.over_form:
        px, py = d.pointer
        for name, (x, y, w, h) in rects.items():
            if x <= px <= x + w and y - GRIP_HEIGHT <= py <= y + h:
                wanted.add(name)
    out = []
    for c, _depth in form.walk():
        if c.name not in wanted or c.name not in rects or _layout.kind(c) is None or not form.children(c.name):
            continue
        if not c.visible and not d.show_hidden:
            continue
        x, y, _w, _h = rects[c.name]
        out.append((c.name, x + HANDLE, y - GRIP_HEIGHT - 1 if y >= GRIP_HEIGHT + 1 else y + 1))
    return out


def _grip(d: "Designer", name: str, t: Theme) -> Any:
    selected = d.doc.is_selected(name)
    chip = _core.container(
        _core.row([_icon("grip-vertical", size=11, color=t.background if selected else t.accent),
                   ui.label(name, size="xs", color=t.background if selected else t.accent, theme=t, wrap=False)],
                  spacing=3, align="center"),
        height=GRIP_HEIGHT, padding=(0, 5, 0, 3), align_y="center", radius=3,
        bg=t.accent if selected else t.background, border_color=t.accent, border_width=1,
    )
    return _core.mouse_area(chip, on_press=lambda: d.press_control(name),
                            on_right_press=lambda: d.open_context_menu(name), cursor="move")


def form_surface(d: "Designer", t: Theme) -> Any:
    """The form frame (title bar + client area) with every designer layer on top."""
    doc = d.doc
    form = doc.form
    ft = theme_for(form, d.preview_theme)
    ctx = _components.RenderContext(ft, form.name)
    ctx.preview = d.motion_preview
    ctx.language = d.preview_language
    ctx.form = form
    w, h = form.width, form.height

    layers: List[Any] = [_core.container(width="fill", height="fill", bg=ft.background)]
    painted = styling.background_layer(form.style, ft)
    if painted is not None:
        layers.append(painted)
    if d.show_grid:
        layers.append(_core.canvas(dot_grid(w, h, form.grid, alpha(ft.text_muted, 0.35)), width=w, height=h,
                                   id="designer-grid"))

    # 2. the controls, as they will look, containers before what they hold
    rects = d.rects
    # the Animation panel's playhead: control properties its tracks change, and the player of the rest
    animated = d.timeline.canvas_overrides()
    shown = []
    drawn: List[Any] = []
    hidden: set = set()
    for c, _depth in form.walk():
        if not _components.get(c.type).visual:
            continue  # in the tray under the form
        if not c.visible or (c.parent and c.parent in hidden):
            hidden.add(c.name)
            if not d.show_hidden:
                continue
        x, y, cw, ch = rects[c.name]
        placed = Control(**{**c.__dict__, "width": cw, "height": ch})
        if c.name in animated:
            placed.props = {**placed.props, **animated[c.name]}
        widget = _components.render(placed, ctx)
        played = d.timeline.targets(c.name)
        if played:
            widget = widget.animate(*played)
        if c.name in hidden:
            widget = _core.container(widget, width=cw, height=ch, bg=alpha(ft.background, 0.5))
        drawn.append(_core.pin(widget, x=x, y=y))
        shown.append(c)
    # the form's global style: texts inside take its font, color and size
    layers.append(styling.apply_global(_core.stack(drawn, width=w, height=h), form.style, ft, background=False))

    # the container a dragged control (or the one being placed) will drop into
    target = d.drop_target
    if target is not None and target.name in rects:
        tx, ty, tw, th = rects[target.name]
        layers.append(_core.pin(_core.container(width=tw, height=th, bg=alpha(t.accent, 0.06),
                                                border_color=t.accent, border_width=2, radius=2), x=tx, y=ty))

    # 3. hit boxes: select, drag, double-click to open the default event, right-click menu
    for c in shown:
        x, y, cw, ch = rects[c.name]
        box = _core.container(width=cw, height=ch)
        layers.append(_core.pin(_core.mouse_area(
            box,
            on_press=lambda n=c.name: d.press_control(n),
            on_double_click=lambda n=c.name: d.open_default_event(n),
            on_right_press=lambda n=c.name: d.open_context_menu(n),
            cursor="crosshair" if d.tool else ("default" if c.locked else "move"),
        ), x=x, y=y))

    # 4. selection, handles, rubber band
    selected = [c for c in doc.selected if _components.get(c.type).visual]
    for c in selected:
        primary = c is doc.primary
        x, y, cw, ch = rects.get(c.name, c.rect)
        layers.append(_core.pin(_core.container(
            width=cw + 2, height=ch + 2,
            border_color=t.accent if primary else alpha(t.accent, 0.6), border_width=1.5 if primary else 1,
        ), x=x - 1, y=y - 1))
        if c.locked:
            layers.append(_core.pin(_icon("lock", size=11, color=t.accent), x=x + cw - 12, y=y - 14))
    if len(selected) == 1 and selected[0] is doc.primary and not doc.primary.locked:  # type: ignore[union-attr]
        layers.extend(_handles(d, rects.get(doc.primary.name, doc.primary.rect), t))  # type: ignore[union-attr]
    # 5. grip tabs on containers, above everything they hold
    for name, gx, gy in grips(d):
        layers.append(_core.pin(_grip(d, name, t), x=gx, y=gy))
    band = d.band_rect
    if band is not None:
        bx, by, bw, bh = band
        creating = d.drag is not None and d.drag.mode == "create"
        layers.append(_core.pin(_core.container(
            width=max(bw, 1), height=max(bh, 1), bg=alpha(t.accent, 0.08 if creating else 0.12),
            border_color=t.accent, border_width=1,
        ), x=bx, y=by))
    for guide in d.guides:
        gx1, gy1, gx2, gy2 = guide
        layers.append(_core.pin(_core.container(width=max(gx2 - gx1, 1), height=max(gy2 - gy1, 1),
                                                bg=t.color("error")), x=gx1, y=gy1))

    client = _core.mouse_area(
        _core.container(_core.stack(layers, width=w, height=h), width=w, height=h, clip=True, color=ft.text),
        on_move=d.pointer_moved,
        on_enter=d.enter_form,
        on_exit=d.exit_form,
        on_press=d.press_empty,
        on_right_press=d.close_menu,
        cursor="crosshair" if d.tool else None,
    )
    # A soft outline instead of a blurred shadow: wgpu redraws blurred shadows of a scrolled
    # layer over its content while a later layer (the code editor's completion list) is shown.
    frame = _core.container(
        _core.container(_core.column([_chrome(translate(form.title, d.preview_language), w, ft,
                                              getattr(d.doc, "is_scene", False), frame_style(d)), client]),
                        border_color=t.accent if getattr(d.doc, "is_scene", False) else t.border, border_width=1,
                        radius=t.radius, clip=True),
        padding=3, radius=t.radius + 3, border_color=alpha(t.shadow, 0.5), border_width=3,
    )
    # A size grip under the bottom-right corner resizes the form itself.
    grip = _core.mouse_area(
        _core.container(_icon("move-diagonal-2", size=12, color=t.icon_muted), width=16, height=16, center=True),
        on_press=d.press_form_grip, cursor="crosshair",
    )
    sized = _core.column([frame, _core.row([_core.space(width=w + 2), grip]), tray(d, w, t)], spacing=0)
    return _core.mouse_area(
        _core.scrollable(_core.container(sized, padding=MARGIN), direction="both", width="fill", height="fill"),
        on_release=d.release,
        on_move=d.pointer_moved_view,
    )


def tray_rows(names: List[str], width: float) -> List[List[str]]:
    """``names`` split into the rows of chips that fit in ``width``."""
    per_row = max(int((width + TRAY_GAP) // (TRAY_CHIP + TRAY_GAP)), 1)
    return [names[i:i + per_row] for i in range(0, len(names), per_row)]


def tray(d: "Designer", width: float, t: Theme) -> Any:
    """The component tray under the form: a chip for each non-visual component (press to select it,
    double-click to open its main event, right-click for its menu). ``None`` when there is none."""
    doc = d.doc
    names = [c.name for c in doc.form.controls if not _components.get(c.type).visual]
    if not names:
        return None

    def chip(name: str) -> Any:
        control = doc.form[name]
        spec = _components.get(control.type)
        selected = doc.is_selected(name)
        hovered = d.hovered_row == f"tray:{name}"
        color = t.text if control.enabled else t.text_muted
        body = _core.container(
            _core.row([_icon(spec.icon, size=14, color=t.accent if selected else t.icon_muted),
                       _core.container(_core.text(name, size=12.5, color=color, wrap=False), width="fill", clip=True)],
                      spacing=6, align="center"),
            width=TRAY_CHIP, height=28, padding=(0, 8), align_y="center", radius=t.radius_sm,
            bg=t.ghost_selected if selected else (t.ghost_hover if hovered else t.element),
            border_color=t.accent if selected else t.border_variant, border_width=1.5 if selected else 1)
        return ui.tooltip(_core.mouse_area(
            body, on_press=lambda: d.press_tray(name), on_double_click=lambda: d.open_default_event(name),
            on_right_press=lambda: d.open_context_menu(name), on_enter=lambda: d.enter_row(f"tray:{name}"),
            on_exit=lambda: d.leave_row(f"tray:{name}")), tr(spec.label), position="bottom", theme=t)

    rows = [_core.row([chip(n) for n in row], spacing=TRAY_GAP) for row in tray_rows(names, width)]
    return _core.container(_core.column([
        _core.row([_icon("box", size=12, color=t.icon_muted),
                   ui.label(tr("Non-visual components"), size="xs", color="text_muted", theme=t)],
                  spacing=6, align="center"),
        *rows,
    ], spacing=TRAY_GAP), width=width + 8, padding=(10, 8), bg=alpha(t.panel, 0.6), radius=t.radius,
        border_color=t.border_variant, border_width=1)
