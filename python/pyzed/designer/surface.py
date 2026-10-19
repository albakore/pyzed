"""The design surface: the form being edited, its dot grid, selection, handles and rubber band.

Layers, bottom to top (one ``stack`` sized like the form):

1. the form background and the dot grid (a cached ``canvas``);
2. every control, drawn by its component exactly as it will run, but inert;
3. one transparent hit box per control that selects, drags and double-clicks;
4. selection outlines, resize handles and the rubber band / new-control preview.

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
from .geometry import HANDLES
from .locale import tr
from .model import Control
from .runtime import theme_for

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

CHROME_HEIGHT = 30.0
MARGIN = 48.0
HANDLE = 7.0

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


def _chrome(title: str, width: float, t: Theme, component: bool = False) -> Any:
    if component:  # not a window: no window buttons, and the bar says what it is
        return _core.container(
            _core.row([_icon("component", size=13, color=t.accent),
                       ui.label(f"{tr('Component')} · {title}", size="sm", color="accent", theme=t, wrap=False)],
                      spacing=6, align="center"),
            width=width, height=CHROME_HEIGHT, padding=(0, 10), align_y="center", bg=alpha(t.accent, 0.12),
        )
    dots = _core.row([_core.container(width=10, height=10, bg=color, radius=5)
                      for color in ("#ff5f57", "#febc2e", "#28c840")], spacing=6)
    return _core.container(
        _core.stack([
            _core.container(dots, width="fill", height="fill", align_y="center", padding=(0, 10)),
            _core.container(ui.label(title, size="sm", color="text_muted", theme=t, wrap=False),
                            width="fill", height="fill", center=True),
        ]),
        width=width, height=CHROME_HEIGHT, bg=t.title_bar,
    )


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


def form_surface(d: "Designer", t: Theme) -> Any:
    """The form frame (title bar + client area) with every designer layer on top."""
    doc = d.doc
    form = doc.form
    ft = theme_for(form)
    ctx = _components.RenderContext(ft, form.name)
    w, h = form.width, form.height

    layers: List[Any] = [_core.container(width="fill", height="fill", bg=ft.background)]
    if d.show_grid:
        layers.append(_core.canvas(dot_grid(w, h, form.grid, alpha(ft.text_muted, 0.35)), width=w, height=h,
                                   id="designer-grid"))

    # 2. the controls, as they will look, containers before what they hold
    rects = d.rects
    shown = []
    hidden: set = set()
    for c, _depth in form.walk():
        if not c.visible or (c.parent and c.parent in hidden):
            hidden.add(c.name)
            if not d.show_hidden:
                continue
        x, y, cw, ch = rects[c.name]
        placed = Control(**{**c.__dict__, "width": cw, "height": ch})
        widget = _components.render(placed, ctx)
        if c.name in hidden:
            widget = _core.container(widget, width=cw, height=ch, bg=alpha(ft.background, 0.5))
        layers.append(_core.pin(widget, x=x, y=y))
        shown.append(c)

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
    for c in doc.selected:
        primary = c is doc.primary
        x, y, cw, ch = rects.get(c.name, c.rect)
        layers.append(_core.pin(_core.container(
            width=cw + 2, height=ch + 2,
            border_color=t.accent if primary else alpha(t.accent, 0.6), border_width=1.5 if primary else 1,
        ), x=x - 1, y=y - 1))
        if c.locked:
            layers.append(_core.pin(_icon("lock", size=11, color=t.accent), x=x + cw - 12, y=y - 14))
    if len(doc.selected) == 1 and not doc.primary.locked:  # type: ignore[union-attr]
        layers.extend(_handles(d, rects.get(doc.primary.name, doc.primary.rect), t))  # type: ignore[union-attr]
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
    if d.menu is not None:
        layers.append(_core.mouse_area(_core.container(width="fill", height="fill"),
                                       on_press=d.close_menu, on_right_press=d.close_menu))
        layers.append(_core.pin(_core.opaque(d.context_menu(t)), x=d.menu[1], y=d.menu[2]))

    client = _core.mouse_area(
        _core.container(_core.stack(layers, width=w, height=h), width=w, height=h, clip=True, color=ft.text),
        on_move=d.pointer_moved,
        on_press=d.press_empty,
        on_right_press=d.close_menu,
        cursor="crosshair" if d.tool else None,
    )
    # A soft outline instead of a blurred shadow: wgpu redraws blurred shadows of a scrolled
    # layer over its content while a later layer (the code editor's completion list) is shown.
    frame = _core.container(
        _core.container(_core.column([_chrome(form.title, w, ft, getattr(d.doc, "is_scene", False)), client]),
                        border_color=t.accent if getattr(d.doc, "is_scene", False) else t.border, border_width=1,
                        radius=t.radius, clip=True),
        padding=3, radius=t.radius + 3, border_color=alpha(t.shadow, 0.5), border_width=3,
    )
    # A size grip under the bottom-right corner resizes the form itself.
    grip = _core.mouse_area(
        _core.container(_icon("move-diagonal-2", size=12, color=t.icon_muted), width=16, height=16, center=True),
        on_press=d.press_form_grip, cursor="crosshair",
    )
    sized = _core.column([frame, _core.row([_core.space(width=w + 2), grip])], spacing=0)
    return _core.mouse_area(
        _core.scrollable(_core.container(sized, padding=MARGIN), direction="both", width="fill", height="fill"),
        on_release=d.release,
        on_move=d.pointer_moved_view,
    )
