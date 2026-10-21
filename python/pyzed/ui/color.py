"""A color picker with alpha, linear gradients and opacity masks.

    ui.ColorPicker(value=self.fill, on_change=lambda e: setattr(self, "fill", e.value))

``value`` is a color (``"#3b82f6"``, ``"#3b82f680"``, a theme token...), a ``pz.Gradient`` or a
``pz.Paint``; ``on_change`` gets the same kinds back: a ``"#rrggbb[aa]"`` string for a plain
color, a ``pz.Gradient``, or a ``pz.Paint`` when a mask is on. Any of them works as a
``background`` in ``widget.style``.
"""

from __future__ import annotations

import colorsys
import inspect
from typing import Any, List, Optional, Tuple

from .. import _core
from ..component import Component
from ..i18n import t as _t
from ..icons import icon as _icon
from ..style import Gradient, Mask, Paint, _rgba, to_hex
from ..theme import alpha as _alpha
from ..theme import current as _current_theme
from .base import icon_button, label
from .controls import number_field
from .inputs import input as _input
from .inputs import segmented, slider, switch

WIDTH = 248
SV_HEIGHT = 150
BAR = 12
HANDLE = 14
HUES = ["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff", "#ff0000"]


def _hsva(color: Any) -> Tuple[float, float, float, float]:
    r, g, b, a = _rgba(color)
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return h, s, v, a


def _from_hsva(h: float, s: float, v: float, a: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return to_hex((r * 255, g * 255, b * 255, a))


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def checkerboard(width: float, height: float, size: float = 6) -> _core.Widget:
    """A light/dark checkerboard, drawn under translucent colors."""
    from .. import draw

    cells = [(x * size, y * size, size, size)
             for y in range(int(height // size) + 1) for x in range(int(width // size) + 1) if (x + y) % 2]
    return _core.canvas([draw.background("#e5e5e5"), draw.rects(cells, fill="#b5b5b5")], width=width, height=height)


class ColorPicker(Component):
    """Picks a color with alpha, a linear gradient or a masked fill.

    Events:
        ``on_change(event)``: Receives ``event.value``.
    """

    value: Any = "#3b82f6"
    alpha: bool = True
    gradients: bool = True
    masks: bool = True
    swatches: list = None
    events = {"change": "A new color, gradient or paint was picked (``event.value``)."}
    icon = "palette"
    category = "Input"
    designer = False

    def setup(self) -> None:
        self.hue: Optional[float] = None
        self.stop = 0
        self.mask_stop = 0
        self.hex_text: Optional[str] = None

    # -- the value as parts ----------------------------------------------------
    def parts(self) -> Tuple[List[Tuple[float, str]], Optional[float], Optional[Mask], float]:
        """``(stops, angle, mask, opacity)``: one stop and no angle for a plain color."""
        value, mask, opacity = self.value, None, 1.0
        if isinstance(value, Paint):
            value, mask, opacity = value.fill, value.mask, value.opacity
        if isinstance(value, Gradient):
            return [(o, to_hex(c)) for o, c in value.stops], value.angle, mask, opacity
        return [(0.0, to_hex(value if value is not None else "#000000"))], None, mask, opacity

    def build(self, stops: List[Tuple[float, str]], angle: Optional[float], mask: Optional[Mask],
              opacity: float) -> Any:
        """Turns ``(stops, angle, mask, opacity)`` back into a color, ``Gradient`` or ``Paint``."""
        fill: Any = Gradient(stops, angle=angle or 0.0) if angle is not None else stops[0][1]
        if mask is None and opacity >= 1.0:
            return fill
        return Paint(fill, opacity=opacity, mask=mask)

    def publish(self, *parts: Any) -> Any:
        """Sets the value from parts, drops any half-typed hex text and emits ``change``."""
        self.value = self.build(*parts)
        self.hex_text = None
        return self.emit("change", self.value)

    def current(self) -> str:
        """Returns the hex color being edited (the selected stop's color)."""
        stops = self.parts()[0]
        return stops[min(self.stop, len(stops) - 1)][1]

    def set_color(self, color: str) -> Any:
        """Replaces the selected stop's color with ``color`` and publishes the result."""
        stops, angle, mask, opacity = self.parts()
        i = min(self.stop, len(stops) - 1)
        stops[i] = (stops[i][0], color)
        return self.publish(stops, angle, mask, opacity)

    # -- editing ---------------------------------------------------------------
    def hsva(self) -> Tuple[float, float, float, float]:
        """Returns the edited color as ``(h, s, v, a)``, each 0 to 1.

        Grays keep the hue last picked so the hue marker does not jump.
        """
        h, s, v, a = _hsva(self.current())
        if self.hue is not None and (s == 0 or v == 0):
            h = self.hue  # grays have no hue of their own: keep the one picked
        return h, s, v, a

    def pick_sv(self, event: Any) -> Any:
        """Sets saturation and value from a press or drag on the saturation/value area."""
        h, _s, _v, a = self.hsva()
        s = _clamp(event.x / max(event.width, 1))
        v = 1 - _clamp(event.y / max(event.height, 1))
        self.hue = h
        return self.set_color(_from_hsva(h, s, v, a))

    def pick_hue(self, event: Any) -> Any:
        """Sets the hue from a press or drag on the hue bar."""
        _h, s, v, a = self.hsva()
        self.hue = min(_clamp(event.x / max(event.width, 1)), 0.9999)
        return self.set_color(_from_hsva(self.hue, s, v, a))

    def pick_alpha(self, event: Any) -> Any:
        """Sets the alpha from a press or drag on the alpha bar."""
        h, s, v, _a = self.hsva()
        return self.set_color(_from_hsva(h, s, v, _clamp(event.x / max(event.width, 1))))

    def type_hex(self, text: str) -> Any:
        """Handles typing in the hex field: applies the text once it is a valid hex color.

        The ``#`` is optional; incomplete or invalid text is kept in the field without changing the value.
        """
        self.hex_text = text
        candidate = text.strip()
        if not candidate.startswith("#"):
            candidate = "#" + candidate
        if len(candidate) in (4, 5, 7, 9):
            try:
                color = to_hex(candidate)
            except ValueError:
                return None
            self.hue = None
            result = self.set_color(color)
            self.hex_text = text
            return result
        return None

    def set_alpha_percent(self, value: float) -> Any:
        """Sets the alpha from the percent field (0 to 100)."""
        h, s, v, _a = self.hsva()
        return self.set_color(_from_hsva(h, s, v, _clamp(value / 100)))

    def set_mode(self, mode: str) -> Any:
        """Switches between ``"Solid"`` and ``"Gradient"``.

        A new gradient runs at 90 degrees from the current color to a lighter tint;
        going solid keeps the edited color.
        """
        stops, angle, mask, opacity = self.parts()
        if mode == "Gradient" and angle is None:
            first = stops[0][1]
            h, s, v, a = _hsva(first)
            stops, angle = [(0.0, first), (1.0, _from_hsva(h, s * 0.4, min(v + 0.3, 1), a))], 90.0
        elif mode == "Solid" and angle is not None:
            stops, angle = [(0.0, self.current())], None
        self.stop = 0
        return self.publish(stops, angle, mask, opacity)

    def set_angle(self, value: float) -> Any:
        """Sets the gradient's angle in degrees (or the mask's, on a plain color).

        Does nothing on a plain color without a mask.
        """
        stops, angle, mask, opacity = self.parts()
        if angle is None:
            if mask is None:
                return None
            mask = Mask(mask.stops, angle=value % 360)
            return self.publish(stops, angle, mask, opacity)
        return self.publish(stops, value % 360, mask, opacity)

    # -- gradient and mask stops ----------------------------------------------------
    def select_stop(self, index: int) -> None:
        """Selects the gradient stop at ``index`` for editing."""
        self.stop = index
        self.hue = None
        self.hex_text = None

    def move_stop(self, index: int, event: Any) -> Any:
        """Moves a gradient stop to where the bar is pressed or by a drag's ``dx``.

        Stops are kept sorted by offset and the moved one stays selected.
        """
        stops, angle, mask, opacity = self.parts()
        offset = _clamp(event.x / max(event.width, 1)) if event.type != "drag" else \
            _clamp(stops[index][0] + event.dx / WIDTH)
        stops[index] = (round(offset, 3), stops[index][1])
        order = sorted(range(len(stops)), key=lambda i: stops[i][0])
        self.stop = order.index(index)
        return self.publish([stops[i] for i in order], angle, mask, opacity)

    def add_stop(self, event: Any) -> Any:
        """Adds a gradient stop where the bar is clicked, with the color the gradient has there.

        Gradients only, and at most 8 stops; the new stop is selected.
        """
        stops, angle, mask, opacity = self.parts()
        if angle is None or len(stops) >= 8:
            return None
        offset = round(_clamp(event.x / max(event.width, 1)), 3)
        color = to_hex(_sample(stops, offset))
        stops.append((offset, color))
        stops.sort(key=lambda s: s[0])
        self.stop = [o for o, _ in stops].index(offset)
        return self.publish(stops, angle, mask, opacity)

    def remove_stop(self) -> Any:
        """Removes the selected gradient stop (a gradient keeps at least two)."""
        stops, angle, mask, opacity = self.parts()
        if angle is None or len(stops) <= 2:
            return None
        stops.pop(min(self.stop, len(stops) - 1))
        self.stop = max(self.stop - 1, 0)
        return self.publish(stops, angle, mask, opacity)

    def toggle_mask(self, on: bool) -> Any:
        """Adds a mask fading from opaque to transparent when ``on``, or removes the mask."""
        stops, angle, mask, opacity = self.parts()
        self.mask_stop = 0
        return self.publish(stops, angle, Mask([1.0, 0.0], angle=angle or 180.0) if on else None, opacity)

    def select_mask_stop(self, index: int) -> None:
        """Selects the mask stop at ``index`` for editing."""
        self.mask_stop = index

    def move_mask_stop(self, index: int, event: Any) -> Any:
        """Moves a mask stop to where the bar is pressed or by a drag's ``dx``, keeping stops sorted."""
        stops, angle, mask, opacity = self.parts()
        points = list(mask.stops)
        offset = _clamp(points[index][0] + event.dx / WIDTH) if event.type == "drag" else \
            _clamp(event.x / max(event.width, 1))
        points[index] = (round(offset, 3), points[index][1])
        order = sorted(range(len(points)), key=lambda i: points[i][0])
        self.mask_stop = order.index(index)
        return self.publish(stops, angle, Mask([points[i] for i in order], angle=mask.angle), opacity)

    def add_mask_stop(self, event: Any) -> Any:
        """Adds a mask stop where the bar is clicked, with the opacity the mask has there (at most 8)."""
        stops, angle, mask, opacity = self.parts()
        if len(mask.stops) >= 8:
            return None
        offset = round(_clamp(event.x / max(event.width, 1)), 3)
        points = sorted([*mask.stops, (offset, mask.at(offset))])
        self.mask_stop = [o for o, _ in points].index(offset)
        return self.publish(stops, angle, Mask(points, angle=mask.angle), opacity)

    def set_mask_opacity(self, value: float) -> Any:
        """Sets the selected mask stop's opacity (0 to 1)."""
        stops, angle, mask, opacity = self.parts()
        points = list(mask.stops)
        i = min(self.mask_stop, len(points) - 1)
        points[i] = (points[i][0], _clamp(value))
        return self.publish(stops, angle, Mask(points, angle=mask.angle), opacity)

    def remove_mask_stop(self) -> Any:
        """Removes the selected mask stop (a mask keeps at least two)."""
        stops, angle, mask, opacity = self.parts()
        if len(mask.stops) <= 2:
            return None
        points = list(mask.stops)
        points.pop(min(self.mask_stop, len(points) - 1))
        self.mask_stop = max(self.mask_stop - 1, 0)
        return self.publish(stops, angle, Mask(points, angle=mask.angle), opacity)

    # -- view -------------------------------------------------------------------
    def marker(self, x: float, y: float, color: str, *, size: float = HANDLE, selected: bool = True,
               **events: Any) -> Any:
        """A round handle of ``color`` centered on ``(x, y)``.

        A white ring marks it ``selected``; ``events`` are attached to it (e.g. ``drag``).
        """
        ring = "#ffffff" if selected else "#9ca3af"
        dot = _core.container(None, width=size, height=size, bg=color, radius=size / 2,
                              border_color=ring, border_width=2, shadow=("#00000080", (0, 1), 3))
        if events:
            dot = dot.on(**events)
        return _core.pin(dot, x=x - size / 2, y=y - size / 2)

    def area(self, layers: List[Any], height: float, markers: List[Any], on_pick: Any, *, width: float = WIDTH) -> Any:
        """A rounded strip of stacked layers that reports where it is pressed and dragged."""
        base = _core.container(_core.stack(layers, width=width, height=height), width=width, height=height,
                               radius=4, clip=True)
        area = base.on(mouse_down=on_pick, drag=on_pick, cursor="crosshair").style(margin=HANDLE / 2)
        return _core.stack([area, *markers], width=width + HANDLE, height=height + HANDLE)

    def sv_area(self) -> Any:
        """The saturation/value square for the current hue, with a marker on the current color."""
        h, s, v, _a = self.hsva()
        hue = _from_hsva(h, 1, 1, 1)
        layers = [
            _core.container(None, width="fill", height="fill", gradient=(90, ["#ffffff", hue])),
            _core.container(None, width="fill", height="fill", gradient=(180, ["#00000000", "#000000"])),
        ]
        marker = self.marker(s * WIDTH + HANDLE / 2, (1 - v) * SV_HEIGHT + HANDLE / 2, _from_hsva(h, s, v, 1))
        return self.area(layers, SV_HEIGHT, [marker], self.pick_sv)

    def hue_bar(self) -> Any:
        """The rainbow hue bar with a marker on the current hue."""
        h = self.hsva()[0]
        layers = [_core.container(None, width="fill", height="fill", gradient=(90, HUES))]
        marker = self.marker(h * WIDTH + HANDLE / 2, BAR / 2 + HANDLE / 2, _from_hsva(h, 1, 1, 1))
        return self.area(layers, BAR, [marker], self.pick_hue)

    def alpha_bar(self) -> Any:
        """The alpha bar (over a checkerboard) with a marker on the current alpha."""
        h, s, v, a = self.hsva()
        solid = _from_hsva(h, s, v, 1)
        layers = [checkerboard(WIDTH, BAR, 4),
                  _core.container(None, width="fill", height="fill", gradient=(90, [solid + "00", solid]))]
        marker = self.marker(a * WIDTH + HANDLE / 2, BAR / 2 + HANDLE / 2, _from_hsva(h, s, v, a))
        return self.area(layers, BAR, [marker], self.pick_alpha)

    def stops_bar(self, points: List[Tuple[float, Any]], preview: Tuple[float, list], selected: int,
                  on_select: Any, on_move: Any, on_add: Any, *, colors: bool = True) -> Any:
        """A bar previewing ``preview`` with a draggable handle per ``(offset, value)`` point.

        Used for gradient stops (``colors``) and mask stops (opacities shown as grays). ``on_select(i)``,
        ``on_move(i, event)`` and ``on_add(event)`` are called on a handle press, a handle drag
        and a bar press.
        """
        layers = [checkerboard(WIDTH, BAR + 4, 4),
                  _core.container(None, width="fill", height="fill", gradient=(90, preview[1]))]
        handles = []
        for i, (offset, value) in enumerate(points):
            color = value if colors else _from_hsva(0, 0, value, 1)
            handles.append(self.marker(offset * WIDTH + HANDLE / 2, (BAR + 4) / 2 + HANDLE / 2, color,
                                       selected=i == selected, mouse_down=lambda i=i: on_select(i),
                                       drag=lambda e, i=i: on_move(i, e), cursor="grab"))
        return self.area(layers, BAR + 4, handles, on_add)

    def render(self) -> Any:
        t = _current_theme()
        stops, angle, mask, opacity = self.parts()
        h, s, v, a = self.hsva()
        color = self.current()
        rows: List[Any] = []
        if self.gradients:
            modes = {_t("pyzed.color.solid"): "Solid", _t("pyzed.color.gradient"): "Gradient"}
            rows.append(segmented(list(modes), list(modes)[1 if angle is not None else 0],
                                  lambda name: self.set_mode(modes[name])))
        if angle is not None:
            rows.append(self.stops_bar(stops, (90, [(o, c) for o, c in stops]), self.stop,
                                       self.select_stop, self.move_stop, self.add_stop))
            rows.append(_core.row([
                label(_t("pyzed.color.angle"), size="sm", color="text_muted"),
                number_field(angle, self.set_angle, min=0, max=359, step=15, width=96, suffix="°"),
                _core.space(width="fill"),
                icon_button("trash-2", self.remove_stop if len(stops) > 2 else None, size="sm",
                            tooltip=_t("pyzed.color.remove_stop"), disabled=len(stops) <= 2),
            ], spacing=8, align="center"))
        rows += [self.sv_area(), self.hue_bar()]
        if self.alpha:
            rows.append(self.alpha_bar())
        preview = _core.stack([checkerboard(28, 28, 7), _core.container(None, width=28, height=28, bg=color)],
                              width=28, height=28)
        fields = [
            _core.container(preview, width=28, height=28, radius=4, clip=True, border_color=t.border, border_width=1),
            _input(self.hex_text if self.hex_text is not None else color.upper(), self.type_hex, mono=True,
                   size="sm"),
        ]
        if self.alpha:
            fields.append(number_field(round(a * 100), self.set_alpha_percent, min=0, max=100, step=5, width=104,
                                       suffix="%"))
        rows.append(_core.row(fields, spacing=8, align="center"))
        swatches = self.swatches if self.swatches is not None else [
            t.accent, t.success, t.warning, t.error, t.info, t.text, t.text_muted, t.background]
        rows.append(_core.row([
            _core.container(None, width=20, height=20, bg=c, radius=4, border_color=t.border, border_width=1)
            .on(click=lambda c=c: self.set_color(to_hex(c)), cursor="pointer")
            for c in swatches[:10]
        ], spacing=4))
        if self.masks:
            rows.append(_core.row([_icon("blend", size=14, color=t.icon_muted), label(_t("pyzed.color.mask"), size="sm"),
                                   _core.space(width="fill"), switch(mask is not None, self.toggle_mask)],
                                  spacing=6, align="center"))
            if mask is not None:
                rows.append(self.stops_bar(mask.stops, (90, [(o, to_hex((255, 255, 255, a_))) for o, a_ in mask.stops]),
                                           self.mask_stop, self.select_mask_stop, self.move_mask_stop,
                                           self.add_mask_stop, colors=False))
                selected = mask.stops[min(self.mask_stop, len(mask.stops) - 1)][1]
                rows.append(_core.row([
                    label(_t("pyzed.color.opacity"), size="sm", color="text_muted"),
                    slider(selected, self.set_mask_opacity, width="fill"),
                    icon_button("trash-2", self.remove_mask_stop if len(mask.stops) > 2 else None, size="sm",
                                tooltip=_t("pyzed.color.remove_stop"), disabled=len(mask.stops) <= 2),
                ], spacing=8, align="center"))
                if angle is None:
                    rows.append(_core.row([
                        label(_t("pyzed.color.angle"), size="sm", color="text_muted"),
                        number_field(mask.angle, self.set_angle, min=0, max=359, step=15, width=96, suffix="°"),
                    ], spacing=8, align="center"))
        return _core.container(
            _core.column(rows, spacing=10, width=WIDTH + HANDLE),
            padding=10, bg=t.elevated, border_color=t.border, border_width=1, radius=t.radius + 2,
        )


_P = inspect.Parameter
ColorPicker.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
    [_P("value", _P.POSITIONAL_OR_KEYWORD, default="#3b82f6")]
    + [_P(n, _P.KEYWORD_ONLY, default=d) for n, d in
       [("alpha", True), ("gradients", True), ("masks", True), ("swatches", None), ("on_change", None)]])


def _sample(stops: List[Tuple[float, str]], offset: float) -> Tuple[float, float, float, float]:
    """The color of a gradient at ``offset``."""
    rgba = [(o, _rgba(c)) for o, c in stops]
    if offset <= rgba[0][0]:
        return rgba[0][1]
    for (o1, c1), (o2, c2) in zip(rgba, rgba[1:]):
        if offset <= o2:
            t = 0.0 if o2 == o1 else (offset - o1) / (o2 - o1)
            return tuple(x + (y - x) * t for x, y in zip(c1, c2))  # type: ignore[return-value]
    return rgba[-1][1]


def color_swatch(value: Any, *, size: float = 20, on_press: Any = None) -> _core.Widget:
    """A small square showing a color, gradient or paint over a checkerboard.

    Events:
        ``on_press()``: Makes it clickable.
    """
    t = _current_theme()
    fill = _core.container(None, width=size, height=size).style(background=value)
    box = _core.container(_core.stack([checkerboard(size, size, max(size / 4, 3)), fill], width=size, height=size),
                          width=size, height=size, radius=4, clip=True, border_color=_alpha(t.border, 1), border_width=1)
    return box.on(click=on_press, cursor="pointer") if on_press is not None else box
