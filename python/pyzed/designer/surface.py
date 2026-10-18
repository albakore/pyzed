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


def _chrome(title: str, width: float, t: Theme) -> Any:
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

    # 2. the controls, as they will look
    for c in form.controls:
        if not c.visible and not d.show_hidden:
            continue
        widget = _components.render(c, ctx)
        if not c.visible:
            widget = _core.container(widget, width=c.width, height=c.height, bg=alpha(ft.background, 0.5))
        layers.append(_core.pin(widget, x=c.x, y=c.y))

    # 3. hit boxes: select, drag, double-click to open the default event, right-click menu
    for c in form.controls:
        if not c.visible and not d.show_hidden:
            continue
        box = _core.container(width=c.width, height=c.height)
        layers.append(_core.pin(_core.mouse_area(
            box,
            on_press=lambda n=c.name: d.press_control(n),
            on_double_click=lambda n=c.name: d.open_default_event(n),
            on_right_press=lambda n=c.name: d.open_context_menu(n),
            cursor="crosshair" if d.tool else ("default" if c.locked else "move"),
        ), x=c.x, y=c.y))

    # 4. selection, handles, rubber band
    for c in doc.selected:
        primary = c is doc.primary
        layers.append(_core.pin(_core.container(
            width=c.width + 2, height=c.height + 2,
            border_color=t.accent if primary else alpha(t.accent, 0.6), border_width=1.5 if primary else 1,
        ), x=c.x - 1, y=c.y - 1))
        if c.locked:
            layers.append(_core.pin(_icon("lock", size=11, color=t.accent), x=c.x + c.width - 12, y=c.y - 14))
    if len(doc.selected) == 1 and not doc.primary.locked:  # type: ignore[union-attr]
        layers.extend(_handles(d, doc.primary.rect, t))  # type: ignore[union-attr]
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
    frame = _core.container(
        _core.column([_chrome(form.title, w, ft), client]),
        border_color=t.border, border_width=1, radius=t.radius, clip=True,
        shadow=(t.shadow, (0, 8), 24),
    )
    # A size grip under the bottom-right corner resizes the form itself.
    grip = _core.mouse_area(
        _core.container(_icon("move-diagonal-2", size=12, color=t.icon_muted), width=16, height=16, center=True),
        on_press=d.press_form_grip, cursor="crosshair",
    )
    sized = _core.column([frame, _core.row([_core.space(width=w - 4), grip])], spacing=0)
    return _core.mouse_area(
        _core.scrollable(_core.container(sized, padding=MARGIN), direction="both", width="fill", height="fill"),
        on_release=d.release,
        on_move=d.pointer_moved_view,
    )
