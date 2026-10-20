"""A modular synthesizer rack, like VCV Rack: modules on rails, patched with animated cables.

    from pyzed import audio, ui

    class Synth(pz.App):
        def __init__(self):
            self.engine = audio.Engine()
            self.layout = {}                    # where each module sits: {node id: {"row", "x"}}
            self.engine.start()

        def subscriptions(self):
            return [pz.frames(lambda dt: None)]  # redraw every frame: cables sway, scopes move

        def view(self):
            return ui.rack.Rack(engine=self.engine, layout=self.layout)

``Rack`` reads the engine's modules (``engine.nodes``), their description (``audio.modules()``:
ports and parameters) and its cables (``engine.cables``), and changes them through the engine
(``engine.add``, ``engine.connect``, ``engine.set``...). Each module's panel is laid out from its
description: knobs for parameters, jacks for inputs and outputs (outputs on a darker plate),
plus a screen, step LEDs or meters for modules that have them.

Drag from a jack to another to patch a cable (an output to an input), drag a patched input to
move its cable, right-click a jack to unplug it. Drag a module by its title to move it, and add
modules from the browser on the left. ``save``/``load`` keep the patch and the layout in one file.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .. import _core, draw
from ..component import Component
from ..icons import icon as _icon
from ..theme import alpha as _alpha
from ..theme import current as _current_theme
from ..theme import mix as _mix
from . import audio as _audio

__all__ = [
    "CABLE_COLORS",
    "HP",
    "MODULE_HEIGHT",
    "Panel",
    "Rack",
    "cable_path",
    "load",
    "panel_layout",
    "place",
    "save",
]

#: Width of one rack unit (Eurorack "HP"), in pixels.
HP = 15
#: Height of a module (and of a row of the rack), in pixels.
MODULE_HEIGHT = 380
#: Colors of new cables, used in turn (like VCV Rack's).
CABLE_COLORS = ["#f5c542", "#e2463c", "#3dd68c", "#4f8ff7", "#b26cf0", "#ff8a3d", "#2fd3d3", "#f06bb0"]

_TITLE = 32
_KNOB = 30
_KNOB_CELL = (48, 58)
_JACK = 22
_JACK_CELL = (36, 40)
_RAIL = 12
_STEP_KNOB = 20
_STEP_CELL = (27, 34)
_SWITCH_CELL = (27, 18)

_CATEGORY_COLORS = {
    "source": "#ff9f3d", "sources": "#ff9f3d", "oscillator": "#ff9f3d", "oscillators": "#ff9f3d",
    "filter": "#4fc3f7", "filters": "#4fc3f7",
    "envelope": "#f5d547", "envelopes": "#f5d547", "modulation": "#f5d547", "modulators": "#f5d547",
    "effect": "#ff6b9d", "effects": "#ff6b9d",
    "mixer": "#9aa5b1", "mixers": "#9aa5b1", "utility": "#9aa5b1", "utilities": "#9aa5b1",
    "sequencer": "#3dd68c", "sequencers": "#3dd68c", "clock": "#3dd68c",
    "visual": "#2fd3d3", "visualizer": "#2fd3d3", "analysis": "#2fd3d3",
    "io": "#b26cf0", "i/o": "#b26cf0", "input": "#b26cf0", "output": "#b26cf0", "midi": "#b26cf0",
    "sampler": "#ff8a3d", "drums": "#ff8a3d", "sequencing": "#3dd68c", "mixing": "#9aa5b1",
}


# -- reading the engine's descriptions (objects or dicts) ------------------------------------------
def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _nodes(engine: Any) -> List[Any]:
    nodes = _get(engine, "nodes", None) or []
    if isinstance(nodes, dict):
        nodes = list(nodes.values())
    return list(nodes)


def _node_id(node: Any) -> str:
    return str(_get(node, "id"))


def _cables(engine: Any) -> List[Tuple[str, str, str, str]]:
    out = []
    for cable in _get(engine, "cables", None) or []:
        src, port, dst, inp = cable
        out.append((src if isinstance(src, str) else _node_id(src), port,
                    dst if isinstance(dst, str) else _node_id(dst), inp))
    return out


def _catalog(catalog: Any) -> Dict[str, Any]:
    if catalog is None:
        try:
            from .. import audio as _engine  # the engine package (it may be missing in a slim install)
        except ImportError:
            return {}
        catalog = _engine.modules()
    if isinstance(catalog, dict):
        return dict(catalog)
    return {str(_get(info, "kind")): info for info in catalog}


def _category_color(category: str) -> str:
    key = (category or "").lower()
    if key in _CATEGORY_COLORS:
        return _CATEGORY_COLORS[key]
    return CABLE_COLORS[sum(map(ord, key)) % len(CABLE_COLORS)]


# -- panel layout ----------------------------------------------------------------------------------
class Panel:
    """Where everything on a module's panel goes, computed from its description.

    ``width`` is in pixels (a whole number of ``HP``); ``knobs`` maps a parameter's name to the
    top-left of its knob, ``inputs``/``outputs`` map a port's name to its jack's center, and
    ``display`` is the box ``(x, y, w, h)`` left for a screen (or ``None``). Numbered
    parameters that come in eights or more (a sequencer's ``pitch_1`` ... ``pitch_16``) go in a
    grid of small knobs (``step_knobs``) or switches (``switches``, for on/off ones), one
    column per step.
    """

    def __init__(self, info: Any) -> None:
        self.info = info
        params = list(_get(info, "params", None) or [])
        inputs = list(_get(info, "inputs", None) or [])
        outputs = list(_get(info, "outputs", None) or [])
        kind = str(_get(info, "kind", ""))
        self.display_kind = _display_kind(kind)
        groups: Dict[str, List[Any]] = {}
        for p in params:
            match = re.fullmatch(r"(.+?)_(\d+)", str(_get(p, "name")))
            if match:
                groups.setdefault(match.group(1), []).append(p)
        stepped = {prefix: items for prefix, items in groups.items() if len(items) >= 8}
        in_steps = {str(_get(p, "name")) for items in stepped.values() for p in items}
        plain = [p for p in params if str(_get(p, "name")) not in in_steps]
        steps = max((len(items) for items in stepped.values()), default=0)
        step_cols = min(steps, 8)
        step_rows_each = math.ceil(steps / 8) if steps else 0

        ports = len(inputs) + len(outputs)
        jack_cols = 2 if ports <= 6 else 3 if ports <= 12 else 4
        in_rows = math.ceil(len(inputs) / jack_cols)
        out_rows = math.ceil(len(outputs) / jack_cols)
        jacks_h = (in_rows + out_rows) * _JACK_CELL[1] + (10 if out_rows else 0)
        display_h = {"scope": 110, "spectrum": 90, "meter": 0}.get(self.display_kind, 0)
        if self.display_kind == "steps":
            display_h = 22 if steps else 44
        grid_h = 0.0
        for prefix, items in stepped.items():
            grid_h += step_rows_each * (_STEP_CELL[1] if not _is_switch(items[0]) else _SWITCH_CELL[1]) + 14
        knob_h = MODULE_HEIGHT - _TITLE - _RAIL - jacks_h - display_h - grid_h - 8
        knob_rows = max(1, int(knob_h // _KNOB_CELL[1]))
        knob_cols = max(1, math.ceil(len(plain) / knob_rows)) if plain else 0
        if self.display_kind == "meter":
            knob_cols += 1  # room for the meter
        inner = max(knob_cols * _KNOB_CELL[0], jack_cols * _JACK_CELL[0], step_cols * _STEP_CELL[0],
                    64 if not display_h else 150)
        self.hp = max(4, math.ceil((inner + 12) / HP))
        self.width = self.hp * HP
        left = (self.width - inner) / 2
        y = _TITLE + 4
        self.display: Optional[Tuple[float, float, float, float]] = None
        self.steps = steps
        self.step_columns: List[float] = []
        if display_h:
            self.display = (8.0, float(y), self.width - 16.0, display_h - 8.0)
            y += display_h
        self.step_knobs: Dict[str, Tuple[float, float]] = {}
        self.switches: Dict[str, Tuple[float, float]] = {}
        self.step_labels: List[Tuple[str, float]] = []
        if steps:
            gx = (self.width - step_cols * _STEP_CELL[0]) / 2
            self.step_columns = [gx + c * _STEP_CELL[0] + _STEP_CELL[0] / 2 for c in range(step_cols)]
            for prefix, items in stepped.items():
                switch = _is_switch(items[0])
                cell = _SWITCH_CELL if switch else _STEP_CELL
                self.step_labels.append((prefix, y))
                y += 12
                ordered = sorted(items, key=lambda p: int(str(_get(p, "name")).rsplit("_", 1)[1]))
                for i, p in enumerate(ordered):
                    c, r = i % 8, i // 8
                    cx = self.step_columns[c]
                    spot = (cx, y + r * cell[1] + cell[1] / 2)
                    (self.switches if switch else self.step_knobs)[str(_get(p, "name"))] = spot
                y += step_rows_each * cell[1] + 2
        self.knobs: Dict[str, Tuple[float, float]] = {}
        if plain:
            cols = knob_cols - (1 if self.display_kind == "meter" else 0)
            rows_used = math.ceil(len(plain) / max(cols, 1))
            area_w = cols * _KNOB_CELL[0]
            for i, p in enumerate(plain):
                c, r = i // rows_used, i % rows_used
                x = left + (inner - area_w) / 2 + c * _KNOB_CELL[0] + (_KNOB_CELL[0] - _KNOB) / 2
                self.knobs[str(_get(p, "name"))] = (x, y + r * _KNOB_CELL[1])
        if self.display_kind == "meter":
            self.display = (self.width - 34.0, float(y), 22.0, max(80.0, knob_h - 12.0))
        bottom = MODULE_HEIGHT - _RAIL - 6 - jacks_h
        self.inputs: Dict[str, Tuple[float, float]] = {}
        self.outputs: Dict[str, Tuple[float, float]] = {}
        jx = (self.width - jack_cols * _JACK_CELL[0]) / 2

        def place_jacks(ports: Sequence[Any], top: float, into: Dict[str, Tuple[float, float]]) -> None:
            for i, port in enumerate(ports):
                c, r = i % jack_cols, i // jack_cols
                into[str(_get(port, "name"))] = (jx + c * _JACK_CELL[0] + _JACK_CELL[0] / 2,
                                                 top + r * _JACK_CELL[1] + _JACK / 2 + 2)

        place_jacks(inputs, bottom, self.inputs)
        self.output_plate: Optional[Tuple[float, float, float, float]] = None
        if outputs:
            top = bottom + in_rows * _JACK_CELL[1] + 10
            self.output_plate = (jx - 3, top - 4, jack_cols * _JACK_CELL[0] + 6, out_rows * _JACK_CELL[1] + 2)
            place_jacks(outputs, top, self.outputs)


def _is_switch(param: Any) -> bool:
    """Whether a parameter is an on/off switch (0..1 in two steps, or named like a gate)."""
    lo, hi = float(_get(param, "min", 0.0)), float(_get(param, "max", 1.0))
    steps = _get(param, "steps", None)
    name = str(_get(param, "name", ""))
    return (lo, hi) == (0.0, 1.0) and (steps == 2 or name.startswith(("gate_", "on_", "mute_")))


_PANELS: Dict[int, Panel] = {}


def panel_layout(info: Any) -> Panel:
    """The ``Panel`` of a module description (cached)."""
    key = id(info)
    panel = _PANELS.get(key)
    if panel is None or panel.info is not info:
        panel = _PANELS[key] = Panel(info)
    return panel


def _display_kind(kind: str) -> str:
    if kind in ("scope", "oscilloscope"):
        return "scope"
    if kind in ("spectrum", "analyzer"):
        return "spectrum"
    if kind in ("sequencer", "drum_sequencer"):
        return "steps"
    if kind in ("audio_out", "mixer", "vca", "compressor"):
        return "meter"
    return ""


# -- placing modules -------------------------------------------------------------------------------
def place(layout: Dict[str, Dict[str, int]], node_id: str, hp: int, *, row: Optional[int] = None,
          x: Optional[int] = None, widths: Optional[Dict[str, int]] = None, rows: int = 0) -> Dict[str, int]:
    """Puts module ``node_id`` (``hp`` wide) in ``layout``: at ``(row, x)`` if given (moved right
    past any module in the way), else at the end of the first row with room. ``widths`` gives the
    other modules' widths in HP. Returns its new ``{"row", "x"}``."""
    widths = widths or {}

    def taken(r: int) -> List[Tuple[int, int]]:
        return sorted((pos["x"], pos["x"] + widths.get(other, 8)) for other, pos in layout.items()
                      if other != node_id and pos.get("row") == r)

    def fit(r: int, start: int) -> int:
        x0 = max(0, start)
        for a, b in taken(r):
            if x0 + hp <= a:
                break
            if x0 < b:
                x0 = b
        return x0

    if row is None:
        row = 0
        x = fit(0, max((b for _a, b in taken(0)), default=0))
        if rows and x + hp > 120:
            row = min(r for r in range(rows + 1) if max((b for _a, b in taken(r)), default=0) + hp <= 120 or r == rows)
            x = max((b for _a, b in taken(row)), default=0)
    else:
        x = fit(row, x or 0)
    layout[node_id] = {"row": int(row), "x": int(x)}
    return layout[node_id]


# -- cables ----------------------------------------------------------------------------------------
def _bezier(p0: Tuple[float, float], c0: Tuple[float, float], c1: Tuple[float, float], p1: Tuple[float, float],
            t: float) -> Tuple[float, float]:
    u = 1 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * p0[0] + b * c0[0] + c * c1[0] + d * p1[0], a * p0[1] + b * c0[1] + c * c1[1] + d * p1[1])


def _sag(p0: Tuple[float, float], p1: Tuple[float, float], tension: float) -> float:
    dist = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    return (18 + dist * 0.3) * (1.15 - _audio._clamp(tension))


def cable_path(p0: Tuple[float, float], p1: Tuple[float, float], *, tension: float = 0.5,
               drop: float = 1.0) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """The two control points of a cable hanging from ``p0`` to ``p1`` (a cubic Bézier).

    ``tension`` 0 hangs loose and 1 pulls it almost straight; ``drop`` (0..1+) scales the sag
    and animates a cable falling into place.
    """
    sag = _sag(p0, p1, tension) * drop
    return (p0[0] + (p1[0] - p0[0]) * 0.15, p0[1] + sag), (p1[0] - (p1[0] - p0[0]) * 0.15, p1[1] + sag)


def _drop(age: float) -> float:
    """A cable's sag over time after it is plugged: it falls, overshoots and settles (a damped spring)."""
    if age >= 2.5:
        return 1.0
    return 1 - math.exp(-age * 5.5) * math.cos(age * 13.0)


def _cable_shapes(p0: Tuple[float, float], p1: Tuple[float, float], color: str, *, tension: float, drop: float,
                  opacity: float, flow: Optional[float], plug1: bool = True) -> List[Dict[str, Any]]:
    c0, c1 = cable_path(p0, p1, tension=tension, drop=drop)
    ops = [("M", *p0), ("C", *c0, *c1, *p1)]
    shadow = [("M", p0[0] + 3, p0[1] + 5), ("C", c0[0] + 3, c0[1] + 6, c1[0] + 3, c1[1] + 6, p1[0] + 3, p1[1] + 5)]
    out: List[Dict[str, Any]] = [
        draw.path(shadow, stroke=_alpha("#000000", 0.22 * opacity), width=6, cap="round"),
        draw.path(ops, stroke=_alpha(_mix(color, "#000000", 0.35), opacity), width=6.5, cap="round"),
        draw.path(ops, stroke=_alpha(color, opacity), width=4.5, cap="round"),
    ]
    shine = [("M", p0[0] - 1, p0[1] - 1), ("C", c0[0] - 1, c0[1] - 1.5, c1[0] - 1, c1[1] - 1.5, p1[0] - 1, p1[1] - 1)]
    out.append(draw.path(shine, stroke=_alpha("#ffffff", 0.28 * opacity), width=1.2, cap="round"))
    if flow is not None:
        length = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + _sag(p0, p1, tension)
        count = max(2, int(length / 38))
        for i in range(count):
            t = ((i + flow) / count) % 1.0
            x, y = _bezier(p0, c0, c1, p1, t)
            out.append(draw.circle(x, y, 2.2, fill=_alpha(_mix(color, "#ffffff", 0.6), 0.9 * opacity)))
    for (x, y), show in ((p0, True), (p1, plug1)):
        if show:
            out.append(draw.circle(x + 1, y + 2, 8.5, fill=_alpha("#000000", 0.3)))
            out.append(draw.circle(x, y, 8.5, fill=_mix(color, "#000000", 0.25), stroke=_mix(color, "#000000", 0.55),
                                   width=1))
            out.append(draw.circle(x, y, 4.5, fill=_mix(color, "#ffffff", 0.25)))
            out.append(draw.circle(x - 1.5, y - 1.5, 1.6, fill=_alpha("#ffffff", 0.6)))
    return out


def _jack_shapes(hot: bool, light: bool) -> List[Dict[str, Any]]:
    r = _JACK / 2
    ring = "#c3c7cd" if light else "#9aa1ab"
    out = [
        draw.circle(r, r + 1, r - 0.5, fill=_alpha("#000000", 0.35)),
        draw.circle(r, r, r - 1, fill=ring, stroke="#5f6670", width=1),
        draw.circle(r, r, r - 4, fill="#3a3f46"),
        draw.circle(r, r, r - 6.5, fill="#0b0c0e"),
    ]
    if hot:
        out.append(draw.circle(r, r, r - 0.5, stroke="#ffffff", width=1.5))
    return out


# -- the rack --------------------------------------------------------------------------------------
class Rack(Component):
    """A modular rack bound to an audio ``engine`` (see the module docstring).

    ``layout`` is a dict the app keeps (and saves): the rack writes each module's place in it
    as ``{node id: {"row": r, "x": hp}}``. ``catalog`` is the list of module descriptions
    (``audio.modules()`` by default). ``rows`` is how many rows of rails to draw; ``browser``
    shows the module browser. ``tension``, ``cable_opacity`` and ``flow`` (signal dots moving
    along the cables) set how cables look; ``light`` uses light panels like VCV Rack's.
    """

    engine: Any = None
    layout: dict = None
    catalog: Any = None
    rows: int = 2
    browser: bool = True
    tension: float = 0.45
    cable_opacity: float = 0.9
    flow: bool = True
    light: bool = False
    events = {"change": "The patch changed: a module, cable or knob (``event.value`` is what: "
                        "``\"add\"``, ``\"remove\"``, ``\"move\"``, ``\"connect\"``, ``\"disconnect\"`` or ``\"set\"``)."}
    icon = "cable"
    category = "Audio"
    size = (720, 420)
    designer = False

    def setup(self) -> None:
        self.wire: Optional[Dict[str, Any]] = None
        self.moving: Optional[Dict[str, Any]] = None
        self.born: Dict[Tuple[str, str, str, str], float] = {}
        self.colors: Dict[Tuple[str, str, str, str], str] = {}
        self.next_color = 0
        self.search = ""
        self.hover_jack: Optional[Tuple[str, str, bool]] = None
        self.started = _audio._now()
        if self.layout is None:
            self.layout = {}

    def _set_props(self, props: Dict[str, Any]) -> None:
        own = getattr(self, "layout", None)
        super()._set_props(props)
        if self.layout is None:
            self.layout = own if own is not None else {}

    # -- geometry ----------------------------------------------------------------------------------
    def modules(self) -> List[Tuple[Any, Any, Panel]]:
        """``(node, description, panel)`` for each module with a known description."""
        catalog = self._catalog()
        out = []
        for node in _nodes(self.engine):
            info = catalog.get(str(_get(node, "kind")))
            if info is not None:
                out.append((node, info, panel_layout(info)))
        return out

    def _catalog(self) -> Dict[str, Any]:
        if not hasattr(self, "_catalog_cache") or self._catalog_source is not self.catalog:
            self._catalog_source = self.catalog
            self._catalog_cache = _catalog(self.catalog)
        return self._catalog_cache

    def origin(self, node_id: str) -> Tuple[float, float]:
        """The top-left of a module in the rack, in pixels (following a module being dragged)."""
        if self.moving and self.moving["id"] == node_id:
            return self.moving["x"], self.moving["y"]
        pos = self.layout.get(node_id) or {"row": 0, "x": 0}
        return pos["x"] * HP, pos["row"] * MODULE_HEIGHT

    def jack_at(self, node_id: str, port: str, output: bool) -> Optional[Tuple[float, float]]:
        """The center of a jack in the rack, in pixels."""
        for node, _info, panel in self.modules():
            if _node_id(node) == node_id:
                spot = (panel.outputs if output else panel.inputs).get(port)
                if spot is None:
                    return None
                ox, oy = self.origin(node_id)
                return ox + spot[0], oy + spot[1]
        return None

    def nearest_jack(self, x: float, y: float, *, output: Optional[bool] = None,
                     radius: float = 18) -> Optional[Tuple[str, str, bool]]:
        """The jack within ``radius`` pixels of ``(x, y)`` (only outputs or inputs if ``output`` is given)."""
        best, best_d = None, radius
        for node, _info, panel in self.modules():
            nid = _node_id(node)
            ox, oy = self.origin(nid)
            for is_out, jacks in ((True, panel.outputs), (False, panel.inputs)):
                if output is not None and is_out != output:
                    continue
                for port, (jx, jy) in jacks.items():
                    d = math.hypot(ox + jx - x, oy + jy - y)
                    if d < best_d:
                        best, best_d = (nid, port, is_out), d
        return best

    def _arrange(self) -> List[Tuple[Any, Any, Panel]]:
        modules = self.modules()
        widths = {_node_id(n): p.hp for n, _i, p in modules}
        for node, _info, panel in modules:
            nid = _node_id(node)
            if nid not in self.layout:
                place(self.layout, nid, panel.hp, widths=widths, rows=self.rows)
        for gone in [k for k in self.layout if k not in widths]:  # modules removed from the engine
            del self.layout[gone]
        return modules

    # -- engine changes ----------------------------------------------------------------------------
    def _changed(self, what: str) -> Any:
        return self.emit("change", what)

    def add(self, kind: str) -> Any:
        """Adds a module of ``kind`` to the engine and puts it at the end of the rack."""
        node = self.engine.add(kind)
        info = self._catalog().get(kind)
        widths = {_node_id(n): p.hp for n, _i, p in self.modules()}
        place(self.layout, _node_id(node), panel_layout(info).hp if info is not None else 8, widths=widths,
              rows=self.rows)
        return self._changed("add")

    def remove(self, node_id: str) -> Any:
        """Removes a module (and its cables)."""
        self.engine.remove(node_id)
        self.layout.pop(node_id, None)
        return self._changed("remove")

    def _set(self, node_id: str, param: str, value: float) -> Any:
        self.engine.set(node_id, param, value)
        return self._changed("set")

    def _color_for(self, key: Tuple[str, str, str, str]) -> str:
        color = self.colors.get(key)
        if color is None:
            color = self.colors[key] = CABLE_COLORS[self.next_color % len(CABLE_COLORS)]
            self.next_color += 1
        return color

    def _unplug(self, node_id: str, port: str, output: bool) -> Any:
        hit = [c for c in _cables(self.engine) if (c[0], c[1]) == (node_id, port) and output
               or (c[2], c[3]) == (node_id, port) and not output]
        for cable in hit:
            self.engine.disconnect(*cable)
        return self._changed("disconnect") if hit else None

    # -- cable dragging ------------------------------------------------------------------------------
    def _wire_start(self, node_id: str, port: str, output: bool, e: Any) -> Any:
        start = self.jack_at(node_id, port, output)
        if start is None:
            return None
        pointer = (start[0] - _JACK / 2 + e.x, start[1] - _JACK / 2 + e.y)
        if not output:  # an input with a cable: pick that cable up by its plug, like VCV Rack
            for cable in _cables(self.engine):
                if (cable[2], cable[3]) == (node_id, port):
                    color = self._color_for(cable)
                    self.engine.disconnect(*cable)
                    self.wire = {"from": (cable[0], cable[1], True), "pointer": pointer, "color": color}
                    return self._changed("disconnect")
        self.wire = {"from": (node_id, port, output), "pointer": pointer,
                     "color": CABLE_COLORS[self.next_color % len(CABLE_COLORS)]}
        return None

    def _wire_move(self, node_id: str, port: str, output: bool, e: Any) -> None:
        if self.wire is None:
            return
        start = self.jack_at(node_id, port, output)
        if start is not None:
            self.wire["pointer"] = (start[0] - _JACK / 2 + e.x, start[1] - _JACK / 2 + e.y)

    def _wire_end(self, _e: Any = None) -> Any:
        wire, self.wire = self.wire, None
        if wire is None:
            return None
        src_id, src_port, src_out = wire["from"]
        target = self.nearest_jack(*wire["pointer"], output=not src_out)
        if target is None:
            return None
        dst_id, dst_port, _ = target
        if src_out:
            cable = (src_id, src_port, dst_id, dst_port)
        else:
            cable = (dst_id, dst_port, src_id, src_port)
        for old in _cables(self.engine):  # an input takes one cable
            if (old[2], old[3]) == (cable[2], cable[3]):
                self.engine.disconnect(*old)
        self.engine.connect(*cable)
        self.colors[cable] = wire["color"]
        if cable not in self.born:
            self.next_color += 1
        self.born[cable] = _audio._now()
        return self._changed("connect")

    # -- moving modules ------------------------------------------------------------------------------
    def _move_start(self, node_id: str) -> None:
        x, y = self.origin(node_id)
        self.moving = {"id": node_id, "x": x, "y": y}

    def _move(self, e: Any) -> None:
        if self.moving is not None:
            self.moving["x"] = max(0.0, self.moving["x"] + e.dx)
            self.moving["y"] = min(max(0.0, self.moving["y"] + e.dy), (self.rows - 1) * MODULE_HEIGHT)

    def _move_end(self, _e: Any = None) -> Any:
        moving, self.moving = self.moving, None
        if moving is None:
            return None
        widths = {_node_id(n): p.hp for n, _i, p in self.modules()}
        row = int(round(moving["y"] / MODULE_HEIGHT))
        x = int(round(moving["x"] / HP))
        place(self.layout, moving["id"], widths.get(moving["id"], 8), row=row, x=x, widths=widths)
        return self._changed("move")

    # -- drawing ---------------------------------------------------------------------------------------
    def _rails(self, width: float) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = [draw.rect(0, 0, width, self.rows * MODULE_HEIGHT, fill="#17181b")]
        for r in range(self.rows):
            y = r * MODULE_HEIGHT
            for top in (y, y + MODULE_HEIGHT - _RAIL):
                out.append(draw.rect(0, top, width, _RAIL, fill="#8d939b"))
                out.append(draw.rect(0, top + 2, width, 2, fill="#b9bec5"))
                out.append(draw.rect(0, top + _RAIL - 2, width, 2, fill="#5d6269"))
                out.append(draw.rects([(x, top + 4, 8, 4) for x in range(4, int(width), HP)], fill="#4a4f55"))
        return out

    def _jack(self, node_id: str, port: Any, output: bool, x: float, y: float, light: bool) -> List[Any]:
        name = str(_get(port, "name"))
        label = str(_get(port, "label", None) or name).split(" (")[0]
        hot = self.hover_jack == (node_id, name, output)
        jack = _core.canvas(_jack_shapes(hot, light), width=_JACK, height=_JACK).on(
            drag_start=lambda e: self._wire_start(node_id, name, output, e),
            drag=lambda e: self._wire_move(node_id, name, output, e),
            drag_end=self._wire_end,
            right_click=lambda: self._unplug(node_id, name, output),
            mouse_enter=lambda: setattr(self, "hover_jack", (node_id, name, output)),
            mouse_leave=lambda: setattr(self, "hover_jack", None),
            cursor="crosshair",
        )
        text_color = "#f2f2f2" if output else ("#2b2d31" if light else "#c8ccd2")
        caption = _core.text(label[:8].upper(), size=7, color=text_color, align_x="center", width=_JACK_CELL[0],
                             font="mono")
        return [_core.pin(jack, x=x - _JACK / 2, y=y - _JACK / 2),
                _core.pin(caption, x=x - _JACK_CELL[0] / 2, y=y + _JACK / 2 + 1)]

    def _display(self, node: Any, panel: Panel) -> List[Any]:
        if panel.display is None:
            return []
        x, y, w, h = panel.display
        kind = panel.display_kind
        widget: Any = None
        if kind == "scope" and hasattr(node, "scope"):
            widget = _audio.Scope(traces=[node.scope(512)], width=w, height=h, window=256, glow=True,
                                  key=f"scope-{_node_id(node)}")
        elif kind == "spectrum" and hasattr(node, "spectrum"):
            widget = _audio.Spectrum(magnitudes=node.spectrum(256), width=w, height=h, bands=24,
                                     key=f"spectrum-{_node_id(node)}")
        elif kind == "steps":
            state = _get(node, "state", None) or {}
            params = _get(node, "params", None) or {}
            steps = int(params.get("steps", 16) or 16)
            current = int(state.get("step", -1)) if isinstance(state, dict) else -1
            gates = [bool(params.get(f"gate_{i + 1}", 1)) for i in range(steps)]
            size = min(12.0, (w - 4) / 8 - 3)
            shapes = [draw.rect(0, 0, w, h, fill="#0d0e10", radius=4)]
            if panel.step_columns:  # one LED over each column of step knobs, lit on the current step
                for i, cx in enumerate(panel.step_columns):
                    lit = current >= 0 and current % len(panel.step_columns) == i
                    if lit:
                        shapes.append(draw.circle(cx - x, h / 2, 7, fill=_alpha("#f5d547", 0.3)))
                    shapes.append(draw.circle(cx - x, h / 2, 3.5, fill="#f5d547" if lit else "#3b4048"))
                return [_core.pin(_core.canvas(shapes, width=w, height=h), x=x, y=y)]
            for i in range(steps):
                cx = 6 + (i % 8) * ((w - 12) / 8) + size / 2
                cy = 10 + (i // 8) * 18 + size / 2
                on = i == current
                color = "#3dd68c" if gates[i] else "#3b4048"
                if on:
                    shapes.append(draw.circle(cx, cy, size * 0.9, fill=_alpha("#f5d547", 0.35)))
                shapes.append(draw.circle(cx, cy, size / 2, fill="#f5d547" if on else color))
            widget = _core.canvas(shapes, width=w, height=h)
        elif kind == "meter" and hasattr(node, "level"):
            rms, peak = node.level()
            widget = _audio.VuMeter(level=[rms, peak], length=h, thickness=9, segments=20,
                                    key=f"meter-{_node_id(node)}")
        return [_core.pin(widget, x=x, y=y)] if widget is not None else []

    def _module(self, node: Any, info: Any, panel: Panel) -> Any:
        nid = _node_id(node)
        light = self.light
        accent = _category_color(str(_get(info, "category", "")))
        face = "#e4e5e7" if light else "#2a2c31"
        ink = "#202226" if light else "#e6e8eb"
        w, h = panel.width, MODULE_HEIGHT
        title = str(_get(info, "label", None) or _get(info, "kind", "Module"))
        shapes = [
            draw.rect(0, 0, w, h, fill=face, stroke=_mix(face, "#000000", 0.45), width=1, radius=2),
            draw.rect(0, 0, w, 4, fill=accent),
            draw.rect(1, h - _RAIL - 1, w - 2, 1, fill=_alpha("#000000", 0.2)),
        ]
        for sx in (HP / 2, w - HP / 2):
            for sy in (_RAIL / 2 + 2, h - _RAIL / 2 - 2):
                shapes.append(draw.circle(sx, sy, 3.5, fill="#9aa1ab", stroke="#5f6670", width=0.8))
                shapes.append(draw.line(sx - 2, sy, sx + 2, sy, stroke="#4a4f55", width=1))
        if panel.output_plate:
            x, y, pw, ph = panel.output_plate
            shapes.append(draw.rect(x, y, pw, ph, fill="#1d1f23" if not light else "#3a3d43", radius=4))
        layers: List[Any] = [_core.canvas(shapes, width=w, height=h)]
        header = _core.container(
            _core.text(title, size=11, weight="bold", color=ink, align_x="center", width="fill"),
            width=w, height=22, align_y="center",
        ).on(drag_start=lambda: self._move_start(nid), drag=self._move, drag_end=self._move_end, cursor="grab")
        layers.append(_core.pin(header, x=0, y=8))
        close = _core.container(_icon("x", size=10, color=_alpha(ink, 0.5)), width=14, height=14, center=True,
                                radius=7).on(click=lambda: self.remove(nid), cursor="pointer")
        layers.append(_core.pin(close, x=w - 16, y=_TITLE - 10))
        params = {str(_get(p, "name")): p for p in (_get(info, "params", None) or [])}
        values = _get(node, "params", None) or {}
        for name, (kx, ky) in panel.knobs.items():
            p = params[name]
            options = _get(p, "options", None)
            knob = _audio.Knob(
                value=float(values.get(name, _get(p, "default", 0.0)) or 0.0),
                min=float(_get(p, "min", 0.0)), max=float(_get(p, "max", 1.0)),
                default=_get(p, "default", None), step=_get(p, "steps", None) and (
                    (float(_get(p, "max", 1.0)) - float(_get(p, "min", 0.0))) / max(int(_get(p, "steps")) - 1, 1)),
                curve=str(_get(p, "curve", "lin") or "lin"), unit=str(_get(p, "unit", "") or ""),
                caption=str(_get(p, "label", None) or name)[:9], options=list(options) if options else None,
                diameter=_KNOB, variant="rack", color=accent, show_value=False,
                on_change=lambda e, name=name: self._set(nid, name, e.value),
                key=f"{nid}:{name}",
            )
            layers.append(_core.pin(knob, x=kx - (_KNOB_CELL[0] - _KNOB) / 2 - 4, y=ky))
        for prefix, y in panel.step_labels:
            layers.append(_core.pin(_core.text(prefix.replace("_", " ").upper(), size=7, color=_alpha(ink, 0.6),
                                               font="mono"), x=8, y=y))
        for name, (cx, cy) in panel.step_knobs.items():
            p = params[name]
            knob = _audio.Knob(
                value=float(values.get(name, _get(p, "default", 0.0)) or 0.0), min=float(_get(p, "min", 0.0)),
                max=float(_get(p, "max", 1.0)), default=_get(p, "default", None),
                curve=str(_get(p, "curve", "lin") or "lin"), diameter=_STEP_KNOB, variant="rack", color=accent,
                show_value=False, on_change=lambda e, name=name: self._set(nid, name, e.value), key=f"{nid}:{name}",
            )
            layers.append(_core.pin(knob, x=cx - _STEP_KNOB / 2, y=cy - _STEP_KNOB / 2))
        for name, (cx, cy) in panel.switches.items():
            on = float(values.get(name, _get(params[name], "default", 0.0)) or 0.0) >= 0.5
            led = _core.canvas([
                draw.rect(0, 0, 16, 11, fill="#15161a", radius=2),
                draw.rect(2, 2, 12, 7, fill=accent if on else _mix(accent, "#000000", 0.75), radius=1.5),
            ], width=16, height=11).on(click=lambda name=name, on=on: self._set(nid, name, 0.0 if on else 1.0),
                                       cursor="pointer")
            layers.append(_core.pin(led, x=cx - 8, y=cy - 5.5))
        for output, ports, spots in ((False, _get(info, "inputs", None) or [], panel.inputs),
                                     (True, _get(info, "outputs", None) or [], panel.outputs)):
            for port in ports:
                x, y = spots[str(_get(port, "name"))]
                layers.extend(self._jack(nid, port, output, x, y, light))
        layers.extend(self._display(node, panel))
        return _core.stack(layers, width=w, height=h)

    def _cables_layer(self, width: float, height: float) -> Any:
        now = _audio._now()
        shapes: List[Dict[str, Any]] = []
        live = set()
        for cable in _cables(self.engine):
            p0 = self.jack_at(cable[0], cable[1], True)
            p1 = self.jack_at(cable[2], cable[3], False)
            if p0 is None or p1 is None:
                continue
            live.add(cable)
            born = self.born.setdefault(cable, now - 10)
            flow = None
            if self.flow:
                flow = ((now - self.started) * 0.6) % 1.0
            shapes += _cable_shapes(p0, p1, self._color_for(cable), tension=self.tension, drop=_drop(now - born),
                                    opacity=self.cable_opacity, flow=flow)
        for gone in [k for k in self.born if k not in live]:
            del self.born[gone]
        if self.wire is not None:
            src = self.jack_at(*self.wire["from"])
            if src is not None:
                target = self.nearest_jack(*self.wire["pointer"], output=not self.wire["from"][2])
                end = self.jack_at(*target) if target else self.wire["pointer"]
                shapes += _cable_shapes(src, end, self.wire["color"], tension=0.75, drop=0.6, opacity=1.0, flow=None)
        return _core.canvas(shapes, width=width, height=height)

    def _browser(self) -> Any:
        th = _current_theme()
        from .inputs import search_input

        groups: Dict[str, List[Any]] = {}
        query = self.search.lower().strip()
        for kind, info in self._catalog().items():
            label = str(_get(info, "label", None) or kind)
            text = f"{kind} {label} {_get(info, 'category', '')} {_get(info, 'description', '')}".lower()
            if query and query not in text:
                continue
            groups.setdefault(str(_get(info, "category", "Other") or "Other"), []).append((kind, label, info))
        items: List[Any] = []
        for category in sorted(groups):
            items.append(_core.text(category.upper(), size=10, color=th.text_muted, weight="bold"))
            for kind, label, info in sorted(groups[category], key=lambda g: g[1]):
                dot = _core.container(None, width=8, height=8, radius=4, bg=_category_color(category))
                row = _core.row([dot, _core.text(label, size=12, color=th.text)], spacing=8, align="center")
                items.append(_core.container(row, padding=(4, 8), width="fill", radius=4).on(
                    click=lambda kind=kind: self.add(kind), cursor="pointer"))
        listing = _core.scrollable(_core.column(items, spacing=2, width="fill"), height="fill")
        top = search_input(self.search, on_input=lambda v: setattr(self, "search", v), placeholder="Modules…")
        return _core.container(_core.column([top, listing], spacing=8, height="fill"), width=190, height="fill",
                               padding=8, bg=th.panel, border_color=th.border, border_width=1)

    def render(self) -> Any:
        modules = self._arrange()
        end = max((self.origin(_node_id(n))[0] + p.width for n, _i, p in modules), default=0)
        width = max(end + 30 * HP, 60 * HP)
        height = self.rows * MODULE_HEIGHT
        layers: List[Any] = [_core.canvas(self._rails(width), width=width, height=height)]
        for node, info, panel in modules:
            x, y = self.origin(_node_id(node))
            layers.append(_core.pin(self._module(node, info, panel), x=x, y=y))
        layers.append(self._cables_layer(width, height))
        rack = _core.scrollable(_core.stack(layers, width=width, height=height), direction="both",
                                width="fill", height="fill")
        if not self.browser:
            return rack
        return _core.row([self._browser(), rack], width="fill", height="fill")


# -- saving ------------------------------------------------------------------------------------------
def save(engine: Any, layout: Dict[str, Any], path: Any) -> None:
    """Writes the patch (``engine.to_dict()``) and the rack layout to a JSON file."""
    data = engine.to_dict()
    ui = dict(data.get("ui") or {})
    ui["rack"] = layout
    data["ui"] = ui
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load(engine: Any, path: Any) -> Dict[str, Any]:
    """Loads a patch saved with ``save`` into ``engine`` and returns its rack layout."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    engine.load(data)
    return dict((data.get("ui") or {}).get("rack") or {})

