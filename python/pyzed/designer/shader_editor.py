"""The Shader view of Pyzed Design: a node graph editor for ``.pzshad`` files, like Godot's visual shaders.

* **Graph** tab: nodes on a pannable, zoomable canvas. Each node shows a live preview of what
  it makes; drag from an output to an input to wire them, drop a wire on empty space to add
  a node already wired, double-click (or right-click) the canvas to search for a node.
* **Preview** tab: the finished shader, large, with a slider for every mutable variable.
* **WGSL** tab: the code the graph compiles to, with the compiler's messages on their lines.

The left dock lists the nodes to add (the Shading sidebar, by category) and the shader's
variables (constants and mutable ones that apps change from code); the right dock edits
the selected node, the selected variable or the shader itself.

``ShaderEditor`` (``designer.shading``) keeps what is being dragged; ``ShaderDocument`` holds
the graph and every editing command.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .. import _core, draw, shading, ui
from ..icons import icon as _icon
from ..shading import layout as L
from ..shading import nodes as N
from ..shading.locale import tr as str_
from ..shading.types import COLORS, LABELS, SIZE, components, describe, to_hex
from ..theme import Theme, alpha
from . import spacing
from .locale import tr
from .shader_doc import ShaderDocument

if TYPE_CHECKING:  # pragma: no cover
    from .app import Designer

#: The icon of shader documents (tabs, the New dialog, the project tree).
ICON = "blend"
#: How far the pointer moves before a press in the sidebar becomes a drag.
CARRY_THRESHOLD = 4
#: The size of the floating preview in the corner of the graph.
MINI_PREVIEW = (240.0, 150.0)
#: Grid spacing of the canvas, in graph pixels.
GRID = 24.0
TOOLBAR_HEIGHT = 36.0


def is_shader(d: "Designer") -> bool:
    """Whether the active document is a shader graph."""
    return isinstance(d.doc, ShaderDocument)


def doc_of(d: "Designer") -> ShaderDocument:
    doc = d.doc
    assert isinstance(doc, ShaderDocument)
    return doc


class ShaderEditor:
    """What the shader view is doing right now: a drag, a node search, a menu, the sidebar's search."""

    def __init__(self, d: "Designer") -> None:
        self.d = d
        #: The gesture in progress on the canvas: ``{"mode": "move" | "wire" | "band" | "pan", ...}``.
        self.drag: Optional[Dict[str, Any]] = None
        #: The pointer on the canvas, in canvas pixels.
        self.pointer: Tuple[float, float] = (0.0, 0.0)
        self.over = False
        #: Something pressed in the sidebar: ``("node", preset key)`` or ``("variable", name)``.
        self.carry: Optional[Tuple[str, str]] = None
        self.carry_origin: Tuple[float, float] = (0.0, 0.0)
        self.carry_moved = False
        #: The node search: where it opens (canvas pixels), what is typed, and the wire it continues.
        self.search: Optional[Dict[str, Any]] = None
        #: The node context menu: ``(node id, x, y)`` in canvas pixels.
        self.menu: Optional[Tuple[str, float, float]] = None
        #: The sidebar's search text, and the categories folded in it.
        self.query = ""
        self.folded: set = set()
        #: Whether the small preview shows in the corner of the graph.
        self.mini = True
        #: Time stopped at this many seconds (``None``: running).
        self.paused: Optional[float] = None
        self.started = time.monotonic()
        #: The last message shown about a wire that couldn't connect.
        self.hint: Optional[str] = None
        #: The Run window (F5).
        self.window: Any = None

    # -- helpers ---------------------------------------------------------------------------
    @property
    def doc(self) -> ShaderDocument:
        return doc_of(self.d)

    def graph_pointer(self) -> Tuple[float, float]:
        return self.doc.to_graph(*self.pointer)

    def time(self) -> Optional[float]:
        """The time shaders are drawn at: ``None`` while running."""
        return self.paused

    def toggle_time(self) -> None:
        """Stops or restarts time in every preview."""
        self.paused = None if self.paused is not None else round(time.monotonic() - self.started, 2)

    # -- canvas gestures ----------------------------------------------------------------------
    def moved(self, x: float, y: float) -> None:
        """The pointer moved over the canvas (canvas pixels)."""
        px, py = self.pointer
        self.pointer = (x, y)
        drag = self.drag
        if drag is None:
            return
        doc = self.doc
        dx, dy = x - px, y - py
        if drag["mode"] == "move":
            if abs(x - drag["origin"][0]) + abs(y - drag["origin"][1]) > 2:
                drag["moved"] = True
            doc.move(drag["ids"], dx / doc.zoom, dy / doc.zoom)
        elif drag["mode"] == "pan":
            doc.scroll(dx, dy)
        elif drag["mode"] == "band":
            drag["to"] = (x, y)

    def enter(self) -> None:
        self.over = True

    def exit(self) -> None:
        self.over = False

    def _focus(self) -> None:
        self.d.focus = "canvas"
        self.d.menu = None
        self.menu = None

    def press_node(self, node_id: str) -> None:
        """Press on a node: selects it (keeping a selection it belongs to) and starts moving the selection."""
        self._focus()
        self.search = None
        doc = self.doc
        if node_id not in doc.selection:
            doc.select(node_id)
        else:
            doc.selection.remove(node_id)
            doc.selection.insert(0, node_id)
            doc.variable = None
        self.drag = {"mode": "move", "ids": list(doc.selection), "origin": self.pointer, "moved": False}

    def press_port(self, node_id: str, port: str, output: bool) -> None:
        """Press on a port: drags a new wire out of it; on a connected input it picks up that wire instead."""
        self._focus()
        self.search = None
        doc = self.doc
        if not output:
            link = doc.graph.link_into(node_id, port)
            if link is not None:
                doc.disconnect(node_id, port)
                self.drag = {"mode": "wire", "from": (link.src, link.out, True)}
                return
        self.drag = {"mode": "wire", "from": (node_id, port, output)}

    def press_empty(self) -> None:
        """Press on the empty canvas: clears the selection and starts a selection box (or pans while Space is held)."""
        self._focus()
        if self.search is not None:
            self.search = None
            return
        if "space" in _held():
            self.drag = {"mode": "pan"}
            return
        self.doc.select(None)
        self.doc.variable = None
        self.drag = {"mode": "band", "from": self.pointer, "to": self.pointer}

    def press_middle(self) -> None:
        """Middle button: pans until it is released."""
        self._focus()
        self.drag = {"mode": "pan"}

    def release_middle(self) -> None:
        if self.drag is not None and self.drag["mode"] == "pan":
            self.drag = None

    def release(self) -> None:
        """The button went up: ends the gesture (moves get an undo step, wires connect or open the search)."""
        drag, self.drag = self.drag, None
        if drag is None:
            return
        doc = self.doc
        mode = drag["mode"]
        if mode == "move":
            if drag.get("moved"):
                doc.commit("move")
        elif mode == "band":
            (x0, y0), (x1, y1) = drag["from"], drag["to"]
            if abs(x1 - x0) + abs(y1 - y0) < 4:
                return
            gx0, gy0 = doc.to_graph(min(x0, x1), min(y0, y1))
            gx1, gy1 = doc.to_graph(max(x0, x1), max(y0, y1))
            hits = []
            for node in doc.graph.nodes.values():
                w, h = L.size(doc.graph, node)
                if node.x < gx1 and node.x + w > gx0 and node.y < gy1 and node.y + h > gy0:
                    hits.append(node.id)
            doc.select(hits)
        elif mode == "wire":
            self.finish_wire(drag["from"])

    def finish_wire(self, start: Tuple[str, str, bool]) -> None:
        doc = self.doc
        gx, gy = self.graph_pointer()
        hit = doc.port_at(gx, gy, radius=16)
        node_id, port, output = start
        if hit is None:
            target = doc.node_at(gx, gy)
            if target is not None and target != node_id:
                hit = _first_port(doc, target, start)
        if hit is not None and hit[2] != output and hit[0] != node_id:
            if output:
                error = doc.connect(node_id, port, hit[0], hit[1])
            else:
                error = doc.connect(hit[0], hit[1], node_id, port)
            if error:
                self.d.notify(tr("Can't connect"), error, kind="warning")
            return
        if hit is None and self.over:
            self.open_search(self.pointer, start)

    def double_click(self) -> None:
        """Double-click on the empty canvas: the node search, right there."""
        self.open_search(self.pointer)

    def right_press_empty(self) -> None:
        self._focus()
        self.open_search(self.pointer)

    def scroll(self, dx: float, dy: float) -> None:
        """The wheel zooms around the pointer (sideways scrolling pans)."""
        doc = self.doc
        if dy:
            doc.set_zoom(doc.zoom * (1.1 ** dy), around=self.pointer)
        if dx:
            doc.scroll(dx * 40, 0)

    def cancel(self) -> bool:
        """Escape: closes the search or menu, or drops the gesture. Returns whether there was something."""
        if self.search is not None or self.menu is not None or self.drag is not None:
            self.search = None
            self.menu = None
            if self.drag is not None and self.drag["mode"] == "move" and self.drag.get("moved"):
                self.doc.undo()
            self.drag = None
            return True
        return False

    # -- node search -------------------------------------------------------------------------
    def open_search(self, at: Tuple[float, float], wire: Optional[Tuple[str, str, bool]] = None) -> Any:
        self.menu = None
        self.search = {"at": at, "query": "", "wire": wire, "index": 0}
        return _core.Command.focus("shader-node-search")

    def set_search(self, text: str) -> None:
        if self.search is not None:
            self.search["query"] = text
            self.search["index"] = 0

    def search_results(self) -> List[N.Preset]:
        """What the search lists: entries matching the text (and able to take the wire being continued)."""
        if self.search is None:
            return []
        query = self.search["query"].strip().lower()
        wire = self.search.get("wire")
        out = []
        for p in N.PRESETS:
            if p.type in ("parameter",):
                continue
            title = str_(p.title).lower()
            hay = f"{p.title.lower()} {title} {p.category.lower()} {str_(p.category).lower()} {p.keywords}"
            if query and not all(w in hay for w in query.split()):
                continue
            if wire is not None and not _accepts(self.doc, p, wire):
                continue
            out.append(p)
        if query:
            out.sort(key=lambda p: (not str_(p.title).lower().startswith(query) and not p.title.lower().startswith(query),
                                    len(p.title)))
        return out

    def pick(self, preset: N.Preset) -> None:
        """Adds the picked node where the search opened (wired to the wire it continues)."""
        search, self.search = self.search, None
        if search is None:
            return
        doc = self.doc
        gx, gy = doc.to_graph(*search["at"])
        wire = search.get("wire")
        if wire is not None and wire[2] is False:  # dragged from an input: the new node sits to the left
            gx -= L.WIDTH
        node_id = doc.add_node(preset.key, (gx, gy - 20))
        if wire is not None:
            src, port, output = wire
            hit = _first_port(doc, node_id, wire)
            if hit is not None:
                if output:
                    doc.connect(src, port, hit[0], hit[1])
                else:
                    doc.connect(hit[0], hit[1], src, port)

    def search_key(self, combo: str) -> bool:
        """Arrows and Enter in the node search."""
        if self.search is None:
            return False
        results = self.search_results()
        if combo in ("up", "down"):
            self.search["index"] = max(0, min(len(results) - 1, self.search["index"] + (1 if combo == "down" else -1)))
            return True
        if combo == "enter" and results:
            self.pick(results[min(self.search["index"], len(results) - 1)])
            return True
        return False

    # -- the sidebar ---------------------------------------------------------------------------
    def press_preset(self, key: str) -> None:
        """Press on a node in the sidebar: a click adds it in the middle of the canvas, a drag drops it."""
        self.d.focus = "canvas"
        self.carry = ("node", key)
        self.carry_origin = self.d.window_pointer
        self.carry_moved = False

    def press_variable(self, name: str) -> None:
        """Press on a variable: a click shows it in Properties, a drag drops a node that reads it."""
        self.d.focus = "canvas"
        self.doc.select_variable(name)
        self.carry = ("variable", name)
        self.carry_origin = self.d.window_pointer
        self.carry_moved = False

    def window_moved(self, x: float, y: float) -> None:
        if self.carry is not None and not self.carry_moved:
            ox, oy = self.carry_origin
            self.carry_moved = abs(x - ox) + abs(y - oy) > CARRY_THRESHOLD

    def window_release(self) -> None:
        """The button went up anywhere: drops what was carried out of the sidebar, ends a canvas gesture."""
        carry, self.carry = self.carry, None
        if self.drag is not None:
            self.release()
        if carry is None:
            return
        doc = self.doc
        kind, value = carry
        at = None
        if self.carry_moved:
            if not self.over:
                return
            gx, gy = self.graph_pointer()
            at = (gx - L.WIDTH / 2, gy - 15)
        if kind == "node":
            doc.add_node(value, at)
        elif at is not None:  # a variable dropped on the graph: a node that reads it
            doc.add_parameter(value, at)

    def toggle_category(self, category: str) -> None:
        self.folded ^= {category}

    def set_query(self, text: str) -> None:
        self.query = text

    # -- node menu ------------------------------------------------------------------------------
    def open_menu(self, node_id: str) -> None:
        self._focus()
        if node_id not in self.doc.selection:
            self.doc.select(node_id)
        self.search = None
        self.menu = (node_id, *self.pointer)

    def menu_action(self, action: Callable[[], Any]) -> Callable[[], Any]:
        def run() -> Any:
            self.menu = None
            return action()

        return run

    # -- keys ---------------------------------------------------------------------------------------
    def on_key(self, combo: str) -> Tuple[bool, Any]:
        """Keys while the canvas has the keyboard: ``(handled, result)``."""
        d = self.d
        doc = self.doc
        if combo == "escape":
            return self.cancel(), None
        if self.search is not None and self.search_key(combo):
            return True, None
        if self.search is not None:
            return False, None
        actions: Dict[str, Callable[[], Any]] = {
            "ctrl-z": d.undo,
            "ctrl-shift-z": d.redo,
            "ctrl-y": d.redo,
            "delete": d.delete,
            "backspace": d.delete,
            "ctrl-c": d.copy,
            "ctrl-x": d.cut,
            "ctrl-v": d.paste,
            "ctrl-d": d.duplicate,
            "ctrl-a": doc.select_all,
            "left": lambda: doc.nudge(-1, 0),
            "right": lambda: doc.nudge(1, 0),
            "up": lambda: doc.nudge(0, -1),
            "down": lambda: doc.nudge(0, 1),
            "f": lambda: doc.fit(whole=True),
            "home": lambda: doc.fit(whole=True),
            "ctrl-=": lambda: doc.set_zoom(doc.zoom * 1.2),
            "ctrl-+": lambda: doc.set_zoom(doc.zoom * 1.2),
            "ctrl-shift-=": lambda: doc.set_zoom(doc.zoom * 1.2),
            "ctrl--": lambda: doc.set_zoom(doc.zoom / 1.2),
            "ctrl-minus": lambda: doc.set_zoom(doc.zoom / 1.2),
            "ctrl-0": lambda: doc.set_zoom(1.0),
            "shift-a": lambda: self.open_search(self.pointer),
            "space": lambda: None,
            "p": lambda: [doc.toggle_preview(n) for n in list(doc.selection)],
            "ctrl-l": doc.arrange,
        }
        action = actions.get(combo)
        if action is None:
            return False, None
        return True, action()

    # -- run (F5) -----------------------------------------------------------------------------------
    def run(self) -> Any:
        """Opens the shader in a window of its own that follows the edits."""
        if self.window is not None and getattr(self.window, "is_open", False):
            return self.window.focus()
        self.window = _window_class()(self.d)
        return self.window.open()


def _held() -> frozenset:
    try:
        return frozenset(_core.pressed_keys())
    except Exception:  # noqa: BLE001 - no app running (tests)
        return frozenset()


def _accepts(doc: ShaderDocument, preset: N.Preset, wire: Tuple[str, str, bool]) -> bool:
    """Whether a node from ``preset`` has a port the wire being dragged can connect to."""
    nt = N.TYPES.get(preset.type)
    if nt is None:
        return False
    src, port, output = wire
    node = doc.graph.nodes.get(src)
    if node is None:
        return False
    probe = shading.Node("probe", preset.type, params={**{p.name: p.default for p in nt.params}, **preset.params})
    inputs, outputs = doc.graph.ports(probe)
    if output:
        have = doc.graph.output_type(src, port)
        return any(_compatible(have, p.type) for p in inputs)
    want = doc.graph.input_type(src, port)
    target = doc.graph.input_port(node, port)
    want = target.type if target is not None and target.type in ("T", "any") else want
    return any(_compatible(o.type if o.type != "T" else "float", want) for o in outputs)


def _compatible(have: str, want: str) -> bool:
    if want in ("T", "any"):
        return have != "texture"
    if have in ("T",):
        return want != "texture"
    return (have == "texture") == (want == "texture")


def _first_port(doc: ShaderDocument, node_id: str, wire: Tuple[str, str, bool]) -> Optional[Tuple[str, str, bool]]:
    """The first port of ``node_id`` the wire can take: an input for a wire from an output (an unconnected one
    first), an output for a wire from an input."""
    g = doc.graph
    node = g.nodes.get(node_id)
    if node is None:
        return None
    src, port, output = wire
    inputs, outputs = g.ports(node)
    if output:
        have = g.output_type(src, port)
        fits = [p for p in inputs if _compatible(have, p.type)]
        free = [p for p in fits if g.link_into(node_id, p.name) is None]
        best = (free or fits)[:1]
        return (node_id, best[0].name, False) if best else None
    target = g.input_port(g.nodes[src], port)
    want = target.type if target is not None else "float"
    for o in outputs:
        if _compatible(g.output_type(node_id, o.name), want):
            return (node_id, o.name, True)
    return None


# -- thumbnails ------------------------------------------------------------------------------------

_bad: Dict[int, str] = {}


def shader_widget(code: str, uniforms: Dict[str, Any], textures: Dict[str, str], width: Any, height: Any,
                  t: Theme, *, time_: Optional[float] = None, animate: bool = True) -> Any:
    """A ``pz.shader`` that shows a small error instead of raising when the code doesn't compile."""
    key = hash((code, tuple(sorted(textures.items()))))
    if key in _bad:
        return _error_box(_bad[key], width, height, t)
    try:
        return _core.shader(code, uniforms=uniforms or None, textures=textures or None, width=width, height=height,
                            animate=animate, time=time_, fallback=alpha(t.text_muted, 0.25))
    except (ValueError, TypeError) as err:
        message = str(err).replace("invalid shader:\n", "")
        if len(_bad) > 256:
            _bad.clear()
        _bad[key] = message
        return _error_box(message, width, height, t)


def _error_box(message: str, width: Any, height: Any, t: Theme) -> Any:
    first = next((l.strip()[6:].strip() for l in message.splitlines() if l.strip().startswith("error:")),
                 message.splitlines()[0] if message else "")
    return _core.container(
        _core.column([_icon("triangle-alert", size=14, color=t.color("error")),
                      _core.text(first, size=10, color=t.text_muted, wrap=True)], spacing=4, align="center"),
        width=width, height=height, center=True, padding=6, bg=alpha(t.color("error"), 0.08))


def node_preview(d: "Designer", node: shading.Node, width: float, height: float, t: Theme) -> Any:
    """The live preview of a node's first output."""
    doc = doc_of(d)
    g = doc.graph
    outputs = g.ports(node)[1]
    if not outputs:
        return None
    compiled = shading.compile(g, (node.id, outputs[0].name))
    return shader_widget(compiled.code, compiled.uniforms, compiled.textures, width, height, t,
                         time_=d.shading.time(), animate=compiled.uses_time)


# -- the canvas ----------------------------------------------------------------------------------------


def _category_color(type_: str) -> str:
    return N.CATEGORIES.get(N.category_of(type_), ("", "#9ca3af"))[1]


def _wire(x1: float, y1: float, x2: float, y2: float, color: str, width: float, dash: Any = None) -> Any:
    dx = max(abs(x2 - x1) * 0.5, 40.0)
    return draw.path([("M", x1, y1), ("C", x1 + dx, y1, x2 - dx, y2, x2, y2)], stroke=color, width=width, dash=dash)


def _grid_shapes(doc: ShaderDocument, w: float, h: float, t: Theme) -> List[Any]:
    step = GRID * doc.zoom
    while step < 12:
        step *= 2
    px, py = doc.pan
    ox, oy = px % step, py % step
    minor = alpha(t.border_variant, 0.5)
    major = alpha(t.border_variant, 1.0)
    thin: List[Tuple[float, float, float, float]] = []
    thick: List[Tuple[float, float, float, float]] = []
    i = math.floor(-px / step)
    x = ox
    while x < w:
        (thick if i % 5 == 0 else thin).append((round(x), 0, 1, h))
        x += step
        i += 1
    j = math.floor(-py / step)
    y = oy
    while y < h:
        (thick if j % 5 == 0 else thin).append((0, round(y), w, 1))
        y += step
        j += 1
    return [draw.rects(thin, fill=minor), draw.rects(thick, fill=major)]


def _wire_shapes(d: "Designer", t: Theme) -> List[Any]:
    doc = doc_of(d)
    g = doc.graph
    z = doc.zoom
    shapes: List[Any] = []
    selected = set(doc.selection)
    errors = doc.diagnostics()
    for link in g.links:
        src, dst = g.nodes.get(link.src), g.nodes.get(link.dst)
        if src is None or dst is None:
            continue
        x1, y1 = doc.to_view(*L.port_position(g, src, link.out, True))
        x2, y2 = doc.to_view(*L.port_position(g, dst, link.inp, False))
        color = COLORS.get(g.output_type(link.src, link.out), "#a1a1aa")
        hot = link.src in selected or link.dst in selected
        if hot:
            shapes.append(_wire(x1, y1, x2, y2, alpha(color, 0.35), max(6.0 * z, 4.0)))
        shapes.append(_wire(x1, y1, x2, y2, color if not errors.get(link.dst) else t.color("error"),
                            max((2.6 if hot else 2.0) * z, 1.2)))
    return shapes


def _overlay_shapes(d: "Designer", t: Theme) -> List[Any]:
    """The wire being dragged and the selection box."""
    ed = d.shading
    doc = doc_of(d)
    g = doc.graph
    drag = ed.drag
    shapes: List[Any] = []
    if drag is not None and drag["mode"] == "wire":
        node_id, port, output = drag["from"]
        node = g.nodes.get(node_id)
        if node is not None:
            x1, y1 = doc.to_view(*L.port_position(g, node, port, output))
            x2, y2 = ed.pointer
            if output:
                color = COLORS.get(g.output_type(node_id, port), "#a1a1aa")
            else:
                color = COLORS.get(g.input_type(node_id, port), "#a1a1aa")
            if not output:
                x1, y1, x2, y2 = x2, y2, x1, y1
            shapes.append(_wire(x1, y1, x2, y2, color, max(2.2 * doc.zoom, 1.4), dash=[6, 4]))
    if drag is not None and drag["mode"] == "band":
        (x0, y0), (x1, y1) = drag["from"], drag["to"]
        shapes.append(draw.rect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), fill=alpha(t.accent, 0.1),
                                stroke=t.accent, width=1))
    return shapes


def _value_text(value: Any, type_: str) -> str:
    if isinstance(value, str) and value in N.CONTEXT_LABELS:
        return str_(N.CONTEXT_LABELS[value])
    if value is None:
        return ""
    return describe(value, type_)


def _inline_input(d: "Designer", node: shading.Node, port: N.Input, type_: str, width: float, t: Theme) -> Any:
    """The editor of an unconnected input, inside the node: a number, a switch, a color swatch, or its value."""
    doc = doc_of(d)
    value = node.inputs.get(port.name, port.default)
    if isinstance(value, str) and value in N.CONTEXT:
        return _core.text(str_(N.CONTEXT_LABELS[value]), size=11, color=t.text_muted, italic=True, wrap=False)
    if port.type == "texture":
        return _core.text(tr("white"), size=11, color=t.text_muted, italic=True, wrap=False)
    if value is None:
        return None
    if doc.zoom < 0.85:
        return _core.text(_value_text(value, type_), size=11, color=t.text_muted, wrap=False)

    def change(v: Any, name: str = port.name, node_id: str = node.id) -> None:
        doc.set_input(node_id, name, v)

    if type_ == "bool":
        return ui.checkbox(bool(value), lambda v: change(bool(v)), theme=t)
    if type_ in ("float", "int"):
        number = float(components(value, 1)[0]) if not isinstance(value, bool) else float(value)
        step = 1.0 if type_ == "int" else 0.1
        return ui.number_field(number, lambda v: change(int(v) if type_ == "int" else v), step=step,
                               width=max(width, 60), theme=t)
    if port.hint == "color" or (type_ in ("vec3", "vec4") and isinstance(value, str)):
        key = f"shader-input:{node.id}:{port.name}"
        hexed = value if isinstance(value, str) else to_hex(value)
        d.picker_targets[_picker_key(key)] = (hexed, lambda v: change(v or hexed))
        return _core.row([ui.color_swatch(hexed, size=14, on_press=lambda: d.toggle_color_picker(None, _picker_key(key))),
                          _core.text(hexed, size=11, color=t.text_muted, font="mono", wrap=False)],
                         spacing=4, align="center")
    return _core.text(_value_text(value, type_), size=11, color=t.text_muted, font="mono", wrap=False)


def _picker_key(key: str) -> str:
    from .panels import PROP_PICKER

    return PROP_PICKER + key


def _body_row(d: "Designer", node: shading.Node, width: float, t: Theme) -> Any:
    """The setting shown under a node's title: its operation, variable, value, code or gradient."""
    doc = doc_of(d)
    g = doc.graph
    nt = N.TYPES.get(node.type)
    if nt is None or not nt.params:
        return None
    small = doc.zoom < 0.85
    p = nt.params[0]
    value = node.params.get(p.name, p.default)

    def change(v: Any, name: str = p.name) -> None:
        error = doc.set_param(node.id, name, v)
        if error:
            d.notify(tr("Can't change that"), error, kind="warning")

    if node.type == "gradient":
        stops = N.gradient_stops(value)
        return _core.container(width="fill", height=12, radius=3,
                               gradient=(90, [(pos, c) for pos, c in stops]) if len(stops) > 1 else None,
                               bg=stops[0][1], border_color=t.border, border_width=1)
    if p.kind == "enum" and not small:
        labels = {_option_label(node.type, o): o for o in p.options}
        current = _option_label(node.type, str(value))
        return ui.select(list(labels), current, lambda label: change(labels.get(label, label)), width="fill", size="sm",
                         theme=t)
    if p.kind == "variable":
        names = [v.name for v in g.variables]
        if small or not names:
            return _core.text(str(value or tr("pick a variable")), size=11, color=t.text_muted, wrap=False)
        return ui.select(names, str(value) if value in names else None, change, width="fill", size="sm",
                         placeholder=tr("Variable…"), theme=t)
    if p.kind == "local":
        names = g.locals()
        if small or not names:
            return _core.text(str(value), size=11, color=t.text_muted, wrap=False)
        return ui.select(names, str(value) if value in names else None, change, width="fill", size="sm", theme=t)
    if p.kind in ("float", "int") and not small:
        return ui.number_field(float(value or 0), lambda v: change(int(v) if p.kind == "int" else v),
                               step=1.0 if p.kind == "int" else 0.1, width=width, theme=t)
    if p.kind == "bool":
        return ui.checkbox(bool(value), change, theme=t)
    if p.kind == "color":
        key = _picker_key(f"shader-param:{node.id}:{p.name}")
        d.picker_targets[key] = (value, lambda v: change(v or value))
        return _core.row([ui.color_swatch(value, size=14, on_press=lambda: d.toggle_color_picker(None, key)),
                          _core.text(str(value), size=11, color=t.text_muted, font="mono", wrap=False)],
                         spacing=4, align="center")
    if p.kind == "code":
        first = str(value).strip().splitlines()[0] if str(value).strip() else ""
        return _core.text(first, size=11, color=t.text_accent, font="mono", wrap=False)
    if p.kind == "text" and node.type in ("set_var", "swizzle") and not small:
        return ui.input(str(value), change, size="sm", mono=True, theme=t)
    if p.kind == "file":
        return _core.text(str(value or tr("pick a .pzshad")).replace("\\", "/").rsplit("/", 1)[-1], size=11,
                          color=t.text_muted, wrap=False)
    return _core.text(describe(value, p.kind) if p.kind in SIZE else str(value), size=11, color=t.text_muted,
                      font="mono", wrap=False)


def _option_label(type_: str, option: str) -> str:
    if type_ == "math" and option in N.BINARY:
        return str_(N.BINARY[option][0])
    if type_ == "func" and option in N.UNARY:
        return str_(N.UNARY[option][0])
    return str_(option.replace("_", " ").capitalize()) if option.isalpha() or "_" in option else option


def node_card(d: "Designer", node: shading.Node, t: Theme) -> Any:
    """A node as drawn on the canvas (its ports are drawn on top of it by ``_ports``)."""
    doc = doc_of(d)
    g = doc.graph
    z = doc.zoom
    w, h = L.size(g, node)
    vw, vh = w * z, h * z
    nt = N.TYPES.get(node.type)
    color = _category_color(node.type)
    selected = node.id in doc.selection
    errors = doc.diagnostics()
    error = errors.get(node.id)
    title = g.title(node)
    shown_title = node.title or str_(title)
    font = max(8.0, 12.5 * z)
    if node.type == "comment":
        text = str(node.params.get("text", ""))
        return _core.container(
            _core.column([_core.text(shown_title if node.title else tr("Comment"), size=font * 0.9,
                                     color=t.text_muted, weight="semibold", wrap=False),
                          _core.text(text, size=font, color=t.text, wrap=True)], spacing=4 * z),
            width=vw, height=vh, padding=8 * z, radius=6 * z, bg=alpha(t.text_muted, 0.08),
            border_color=t.accent if selected else alpha(t.text_muted, 0.3), border_width=1.5 if selected else 1)
    if node.type == "reroute":
        return _core.container(width=vw, height=vh, radius=vw / 2, bg=alpha(t.text_muted, 0.2),
                               border_color=t.accent if selected else t.border, border_width=1.5)
    icon = (nt.icon if nt and nt.icon else N.CATEGORIES.get(N.category_of(node.type), ("circle",))[0])
    header = _core.container(
        _core.row([
            _icon(icon, size=max(9.0, 13 * z), color=color),
            _core.container(_core.text(shown_title, size=font, color=t.text, weight="semibold", wrap=False),
                            width="fill", clip=True),
            _core.tooltip(_icon("triangle-alert", size=max(9.0, 13 * z), color=t.color("error")), error,
                          position="top") if error else None,
        ], spacing=6 * z, align="center"),
        width="fill", height=L.HEADER * z, padding=(0, 8 * z), align_y="center",
        bg=alpha(color, 0.22), radius=(6 * z, 6 * z, 0, 0))
    inputs, outputs = g.ports(node)
    types = shading.resolve_types(g).get(node.id, {})
    rows: List[Any] = []
    body = _body_row(d, node, (w - 20) * z, t) if L.has_body(g, node) else None
    if L.has_body(g, node):
        rows.append(_core.container(body, width="fill", height=L.ROW * z, padding=(0, 10 * z), align_y="center"))
    small = max(7.5, 11 * z)
    for i in range(max(len(inputs), len(outputs))):
        left = right = None
        if i < len(inputs):
            p = inputs[i]
            linked = g.link_into(node.id, p.name) is not None
            label = _core.text(str_(p.title), size=small, color=t.text if linked else t.text_muted, wrap=False)
            if linked or (len(outputs) > i and z < 0.85):
                left = label
            else:
                editor = _inline_input(d, node, p, types.get(f"in:{p.name}", p.type), (w * 0.5 - 20) * z, t)
                left = _core.row([label, editor], spacing=6 * z, align="center") if editor is not None else label
        if i < len(outputs):
            o = outputs[i]
            right = _core.text(str_(o.title), size=small, color=t.text, wrap=False)
        rows.append(_core.container(
            _core.row([_core.container(left, width="fill", clip=True), right], spacing=6 * z, align="center"),
            width="fill", height=L.ROW * z, padding=(0, 12 * z), align_y="center"))
    preview = None
    if L.shows_preview(g, node):
        pw, ph = (w - 16) * z, L.PREVIEW * z
        preview = _core.container(
            _core.container(node_preview(d, node, pw, ph, t), width=pw, height=ph, radius=4 * z, clip=True),
            padding=(4 * z, 8 * z, 8 * z, 8 * z))
    card = _core.column([header, _core.column(rows, width="fill", padding=(2 * z, 0)), preview], width=vw)
    border = t.color("error") if error else (t.accent if selected else t.border)
    return _core.container(card, width=vw, height=vh, bg=t.elevated, radius=6 * z, border_color=border,
                           border_width=2 if selected or error else 1, clip=True,
                           shadow=(alpha("#000000", 0.35), (0, 3 * z), 10 * z) if selected else None)


def _ports(d: "Designer", node: shading.Node, t: Theme) -> List[Any]:
    """The ports of a node as small circles to press (a wire starts there) with their types' colors."""
    doc = doc_of(d)
    g = doc.graph
    z = doc.zoom
    r = max(4.0, 5.5 * z)
    types = shading.resolve_types(g).get(node.id, {})
    out: List[Any] = []
    inputs, outputs = g.ports(node)
    hover = d.shading.drag is not None and d.shading.drag["mode"] == "wire"
    for output, ports in ((False, inputs), (True, outputs)):
        for p in ports:
            x, y = doc.to_view(*L.port_position(g, node, p.name, output))
            type_ = types.get(p.name if output else f"in:{p.name}", p.type)
            color = COLORS.get(type_, "#a1a1aa")
            linked = (g.links_from(node.id, p.name) if output else g.link_into(node.id, p.name)) not in ([], None)
            dot = _core.container(width=2 * r, height=2 * r, radius=r, bg=color if linked else t.elevated,
                                  border_color=color, border_width=2)
            hit = 2 * r + 8
            box = _core.container(dot, width=hit, height=hit, center=True)
            tip = f"{str_(p.title)} · {LABELS.get(type_, type_)}"
            area = _core.mouse_area(box, on_press=lambda n=node.id, name=p.name, o=output: d.shading.press_port(n, name, o),
                                    cursor="crosshair")
            out.append(_core.pin(area if hover else ui.tooltip(area, tip, position="top", theme=t),
                                 x=x - hit / 2, y=y - hit / 2))
    return out


def canvas(d: "Designer", t: Theme) -> Any:
    """The Graph tab: grid, wires, nodes, ports, the dragged wire, the small preview and the node search."""

    def build(width: float, height: float) -> Any:
        doc = doc_of(d)
        doc.view_size = (width, height)
        if doc.fit_pending:
            doc.fit_pending = False
            doc.fit()
        g = doc.graph
        z = doc.zoom
        layers: List[Any] = [_core.canvas(_grid_shapes(doc, width, height, t), width=width, height=height)]
        layers.append(_core.canvas(_wire_shapes(d, t), width=width, height=height))
        ordered = sorted(g.nodes.values(), key=lambda n: (n.type != "comment", n.id in doc.selection))
        for node in ordered:
            x, y = doc.to_view(node.x, node.y)
            w, h = L.size(g, node)
            if x > width or y > height or x + w * z < 0 or y + h * z < 0:
                continue
            card = _core.mouse_area(node_card(d, node, t), on_press=lambda n=node.id: d.shading.press_node(n),
                                    on_right_press=lambda n=node.id: d.shading.open_menu(n),
                                    on_double_click=lambda n=node.id: _open_node(d, n))
            layers.append(_core.pin(card, x=x, y=y))
        for node in ordered:
            if node.type == "comment":
                continue
            x, y = doc.to_view(node.x, node.y)
            w, h = L.size(g, node)
            if x > width + 20 or y > height or x + w * z < -20 or y + h * z < 0:
                continue
            layers.extend(_ports(d, node, t))
        overlay = _overlay_shapes(d, t)
        if overlay:
            layers.append(_core.canvas(overlay, width=width, height=height))
        if not g.nodes:
            layers.append(_core.container(ui.empty_state(tr("An empty shader"),
                                                         tr("Double-click to add a node, or drag one from the "
                                                            "Shading sidebar."), icon=ICON, theme=t),
                                          width="fill", height="fill", center=True))
        ed = d.shading
        if ed.mini and doc.tab == "graph" and width > 520:
            mw, mh = MINI_PREVIEW
            layers.append(_core.pin(_mini_preview(d, t), x=width - mw - 16, y=height - mh - 44))
        layers.append(_core.pin(_zoom_badge(d, t), x=12, y=height - 34))
        if ed.search is not None:
            sx, sy = ed.search["at"]
            sx = min(max(sx, 8), max(width - 300, 8))
            sy = min(max(sy, 8), max(height - 360, 8))
            layers.append(_core.pin(_search_popup(d, t), x=sx, y=sy))
        if ed.menu is not None:
            node_id, mx, my = ed.menu
            if node_id in g.nodes:
                layers.append(_core.pin(_node_menu(d, node_id, t), x=min(mx, width - 230), y=min(my, height - 260)))
        stack = _core.stack(layers, width=width, height=height)
        return _core.mouse_area(
            _core.container(stack, width=width, height=height, clip=True, bg=t.editor),
            on_move=ed.moved, on_press=ed.press_empty, on_release=ed.release, on_double_click=ed.double_click,
            on_right_press=ed.right_press_empty, on_scroll=ed.scroll, on_enter=ed.enter, on_exit=ed.exit,
            on_middle_press=ed.press_middle, on_middle_release=ed.release_middle,
            cursor="grabbing" if ed.drag is not None and ed.drag["mode"] == "pan" else None)

    return _core.responsive(build)


def _open_node(d: "Designer", node_id: str) -> None:
    """Double-click on a node: a Shader function opens its .pzshad; others show their settings."""
    doc = doc_of(d)
    node = doc.graph.nodes.get(node_id)
    if node is None:
        return
    if node.type == "subgraph" and node.params.get("path"):
        sub = doc.graph._subgraph(node.params["path"])
        if sub is not None and sub.path is not None:
            d.open_path(sub.path)
            return
    d.show_panel("properties")


def _zoom_badge(d: "Designer", t: Theme) -> Any:
    doc = doc_of(d)
    return _core.container(
        _core.row([
            ui.icon_button("minus", lambda: doc.set_zoom(doc.zoom / 1.2), size="xs", tooltip=tr("Zoom out"), theme=t),
            _core.button(_core.text(f"{doc.zoom * 100:.0f}%", size=11, color=t.text_muted, font="mono"),
                         lambda: doc.set_zoom(1.0), padding=(2, 4), bg="transparent", hover_bg=t.ghost_hover),
            ui.icon_button("plus", lambda: doc.set_zoom(doc.zoom * 1.2), size="xs", tooltip=tr("Zoom in"), theme=t),
            ui.icon_button("maximize", lambda: doc.fit(whole=True), size="xs", tooltip=tr("Fit everything (F)"),
                           theme=t),
        ], spacing=2, align="center"),
        padding=(2, 4), bg=t.elevated, radius=t.radius, border_color=t.border, border_width=1)


def _mini_preview(d: "Designer", t: Theme) -> Any:
    doc = doc_of(d)
    mw, mh = MINI_PREVIEW
    compiled = shading.compile(doc.graph)
    head = _core.row([_icon("monitor", size=12, color=t.icon_muted),
                      _core.text(tr("Output"), size=11, color=t.text_muted, width="fill"),
                      ui.icon_button("expand", lambda: set_tab(d, "preview"), size="xs", tooltip=tr("Open the Preview tab"),
                                     theme=t),
                      ui.icon_button("x", lambda: setattr(d.shading, "mini", False), size="xs", tooltip=tr("Hide"),
                                     theme=t)], spacing=4, align="center")
    art = shader_widget(compiled.code, compiled.uniforms, compiled.textures, mw - 12, mh - 34, t,
                        time_=d.shading.time(), animate=compiled.uses_time)
    return _core.mouse_area(_core.container(
        _core.column([head, _core.container(art, radius=4, clip=True)], spacing=4),
        width=mw, height=mh, padding=6, bg=t.elevated, radius=t.radius, border_color=t.border, border_width=1,
        shadow=(alpha("#000000", 0.3), (0, 4), 14)), on_press=lambda: None)


def _search_popup(d: "Designer", t: Theme) -> Any:
    ed = d.shading
    assert ed.search is not None
    results = ed.search_results()
    index = min(ed.search["index"], max(len(results) - 1, 0))
    rows: List[Any] = []
    start = max(0, index - 8)
    for i, p in enumerate(results[start:start + 14], start):
        color = N.CATEGORIES.get(p.category, ("", "#9ca3af"))[1]
        rows.append(_core.button(
            _core.row([_core.container(width=8, height=8, radius=4, bg=color),
                       _core.text(str_(p.title), size=13, color=t.text, width="fill", wrap=False),
                       _core.text(str_(p.category), size=11, color=t.text_muted, wrap=False)], spacing=8,
                      align="center"),
            lambda p=p: ed.pick(p), padding=(4, 8), width="fill", radius=t.radius_sm,
            bg=t.ghost_selected if i == index else "transparent", hover_bg=t.ghost_hover))
    if not rows:
        rows.append(_core.container(ui.label(tr("No node matches"), size="sm", color="text_muted", theme=t),
                                    padding=8))
    hint = None
    if results:
        hint = _core.container(_core.text(str_(results[index].description), size=11, color=t.text_muted, wrap=True),
                               padding=(6, 8), width="fill")
    title = tr("Add a node") if ed.search.get("wire") is None else tr("Add a node and wire it")
    return _core.mouse_area(_core.container(
        _core.column([
            ui.label(title, size="xs", color="text_muted", theme=t),
            ui.input(ed.search["query"], ed.set_search, placeholder=tr("Search nodes…"), id="shader-node-search",
                     size="sm", on_submit=lambda: ed.search_key("enter"), theme=t),
            _core.column(rows, spacing=1, width="fill"),
            hint,
        ], spacing=6, width="fill"),
        width=290, padding=8, bg=t.elevated, radius=t.radius, border_color=t.border, border_width=1,
        shadow=(alpha("#000000", 0.35), (0, 6), 18)), on_press=lambda: None)


def _node_menu(d: "Designer", node_id: str, t: Theme) -> Any:
    ed = d.shading
    doc = doc_of(d)
    node = doc.graph.nodes[node_id]
    items: List[Any] = [
        ui.MenuItem(tr("Duplicate"), ed.menu_action(d.duplicate), icon="copy", keys="ctrl-d"),
        ui.MenuItem(tr("Copy"), ed.menu_action(d.copy), icon="clipboard-copy", keys="ctrl-c"),
        ui.MenuItem(tr("Hide preview") if node.preview else tr("Show preview"),
                    ed.menu_action(lambda: doc.toggle_preview(node_id)), icon="eye-off" if node.preview else "eye",
                    keys="p"),
        ui.MenuItem(tr("Disconnect all"), ed.menu_action(lambda: doc.disconnect_all(node_id)), icon="unlink"),
        ui.SEPARATOR,
        ui.MenuItem(tr("Delete"), ed.menu_action(d.delete), icon="trash-2", keys="delete"),
    ]
    menu = ui.menu(items, width=220, theme=t)
    return _core.mouse_area(menu, on_press=lambda: None)


# -- toolbar and tabs ------------------------------------------------------------------------------------------


def set_tab(d: "Designer", tab: str) -> None:
    doc_of(d).tab = tab
    d.shading.search = None
    d.shading.menu = None


TABS = (("graph", "Graph", "workflow"), ("preview", "Preview", "monitor-play"), ("code", "WGSL", "file-code"))


def toolbar(d: "Designer", t: Theme) -> Any:
    doc = doc_of(d)
    ed = d.shading

    def tool(icon: str, action: Any, tip: str, *, enabled: bool = True, selected: bool = False,
             keys: Optional[str] = None) -> Any:
        tip = tr(tip)
        label = f"{tip} ({ui.format_keys(keys)})" if keys else tip
        return ui.icon_button(icon, action, disabled=not enabled, selected=selected, tooltip=label, theme=t)

    sep = _core.container(ui.divider(vertical=True, theme=t), height=18, padding=(0, 4))
    tabs = _core.row([ui.button(tr(label), lambda key=key: set_tab(d, key), icon=icon, size="sm",
                                variant="tinted" if doc.tab == key else "ghost", tint="accent" if doc.tab == key else None,
                                theme=t) for key, label, icon in TABS], spacing=2)
    errors = {k: v for k, v in doc.diagnostics().items() if k != "wgsl"}
    status = (ui.tooltip(ui.badge(tr("{count} problems", count=len(errors)) if len(errors) != 1 else tr("1 problem"),
                                  tint="error", icon="triangle-alert", theme=t),
                         "\n".join(f"{_where(doc, k)}: {v}" for k, v in errors.items()), theme=t)
              if errors else ui.badge(tr("Compiles"), tint="success", icon="check", theme=t))
    start = [
        tool("file-plus", lambda: d.new("shader"), "New shader"),
        tool("folder-open", d.open_dialog, "Open", keys="ctrl-o"),
        tool("save", d.save, "Save", keys="ctrl-s"),
        sep,
        tool("undo-2", d.undo, "Undo", enabled=doc.history.can_undo, keys="ctrl-z"),
        tool("redo-2", d.redo, "Redo", enabled=doc.history.can_redo, keys="ctrl-shift-z"),
        sep,
        tabs,
        sep,
        tool("plus", lambda: ed.open_search((doc.view_size[0] / 2 - 140, 80)), "Add a node", keys="shift-a"),
        tool("trash-2", d.delete, "Delete", enabled=bool(doc.selection), keys="delete"),
        tool("layout-grid", doc.arrange, "Arrange nodes in columns", keys="ctrl-l"),
        tool("maximize", lambda: doc.fit(whole=True), "Fit everything", keys="f"),
        sep,
        tool("pause" if ed.paused is None else "play", ed.toggle_time,
             "Stop time" if ed.paused is None else "Start time"),
        tool("picture-in-picture-2", lambda: setattr(ed, "mini", not ed.mini), "Small preview", selected=ed.mini),
    ]
    end = [status, sep, ui.button(tr("Run"), ed.run, icon="play", size="sm", variant="tinted", tint="accent",
                                  keys="f5", theme=t)]
    tools = _core.row([*start, _core.space(width="fill"), *end], spacing=4, align="center")
    return _core.container(_core.scrollable(tools, direction="horizontal", scrollbar_width=2, width="fill"),
                           padding=(0, 8), height=TOOLBAR_HEIGHT, width="fill", align_y="center", bg=t.editor)


def _where(doc: ShaderDocument, key: str) -> str:
    node = doc.graph.nodes.get(key)
    if node is None:
        return tr("Shader")
    return node.title or str_(doc.graph.title(node))


def view(d: "Designer", t: Theme) -> Any:
    """What the Shader view shows under the document tabs."""
    doc = doc_of(d)
    if doc.tab == "preview":
        body = preview_tab(d, t)
    elif doc.tab == "code":
        body = code_tab(d, t)
    else:
        body = canvas(d, t)
    return _core.column([toolbar(d, t) if d.prefs.show_toolbar else None, body], width="fill", height="fill")


def _checker(width: float, height: float, size: float = 12) -> Any:
    cells = [(x * size, y * size, size, size)
             for y in range(int(height // size) + 1) for x in range(int(width // size) + 1) if (x + y) % 2]
    return _core.canvas([draw.background("#2a2a2e"), draw.rects(cells, fill="#3a3a40")], width=width, height=height)


def preview_tab(d: "Designer", t: Theme) -> Any:
    """The finished shader, big, over a checkerboard, with a slider for every mutable variable."""
    doc = doc_of(d)
    g = doc.graph
    compiled = shading.compile(g)
    pw = float(g.preview.get("width") or 320)
    ph = float(g.preview.get("height") or 200)

    def build(width: float, height: float) -> Any:
        scale = min((width - 48) / pw, (height - 48) / ph)
        scale = max(0.25, scale)
        w, h = pw * scale, ph * scale
        art = shader_widget(compiled.code, compiled.uniforms, compiled.textures, w, h, t, time_=d.shading.time(),
                            animate=compiled.uses_time)
        framed = _core.stack([_checker(w, h), art], width=w, height=h)
        return _core.container(_core.container(framed, radius=t.radius, clip=True, border_color=t.border,
                                               border_width=1),
                               width="fill", height="fill", center=True)

    side = variables_panel(d, t, compact=True)
    return _core.row([
        _core.container(_core.responsive(build), width="fill", height="fill", bg=t.editor),
        _core.container(side, width=300, height="fill", bg=t.panel, border_color=t.border, border_width=1),
    ], width="fill", height="fill")


def code_tab(d: "Designer", t: Theme) -> Any:
    """The WGSL the graph compiles to (read only), with the compiler's messages on their lines."""
    doc = doc_of(d)
    compiled = shading.compile(doc.graph)
    notes: Dict[int, Any] = {}
    errors = doc.diagnostics()
    for line, node_id in compiled.lines.items():
        if node_id in errors and line not in notes and node_id != "wgsl":
            notes[line] = (errors[node_id], t.color("error"))
    head = _core.container(_core.row([
        _icon("info", size=13, color=t.icon_muted),
        ui.label(tr("Generated from the graph: edit the nodes, not this code. pz.shader runs it on the GPU."),
                 size="sm", color="text_muted", theme=t),
        _core.space(width="fill"),
        ui.button(tr("Copy"), lambda: _core.Command.copy(compiled.code), icon="copy", size="sm", variant="ghost",
                  theme=t),
    ], spacing=8, align="center"), padding=(6, 12), width="fill", bg=t.panel)
    editor = ui.editor(f"shader-wgsl:{id(doc)}:{doc.graph.revision}", compiled.code, language="rust",
                       annotations=notes, active_line=False, minimap=False, theme=t)
    return _core.column([head, editor], width="fill", height="fill")


# -- left dock: nodes and variables ----------------------------------------------------------------------------


def toolbox(d: "Designer", t: Theme) -> Any:
    """The Shading sidebar: every node to add, by category; press to add, drag onto the graph."""
    from .panels import press_row, scroll_panel, section

    ed = d.shading
    query = ed.query.strip().lower()
    rows: List[Any] = []
    by_category: Dict[str, List[N.Preset]] = {}
    for p in N.PRESETS:
        if p.type == "parameter":
            continue
        if query:
            hay = f"{p.title} {str_(p.title)} {p.category} {str_(p.category)} {p.keywords}".lower()
            if not all(w in hay for w in query.split()):
                continue
        by_category.setdefault(p.category, []).append(p)
    for category, (icon, color) in N.CATEGORIES.items():
        items = by_category.get(category)
        if not items:
            continue
        folded = category in ed.folded and not query
        head = _core.button(
            _core.row([_icon("chevron-right" if folded else "chevron-down", size=12, color=t.icon_muted),
                       _icon(icon, size=13, color=color),
                       ui.label(str_(category).upper(), size="xs", weight="semibold", color="text_muted", theme=t),
                       _core.space(width="fill"),
                       ui.label(str(len(items)), size="xs", color="text_muted", theme=t)], spacing=6, align="center"),
            lambda c=category: ed.toggle_category(c), padding=(8, spacing.GUTTER, 4, spacing.GUTTER), width="fill",
            bg="transparent", hover_bg=t.ghost_hover)
        rows.append(head)
        if folded:
            continue
        for p in items:
            dot = _core.container(width=8, height=8, radius=4, bg=color)
            rows.append(ui.tooltip(
                press_row(d, f"shade:{p.key}", str_(p.title), lambda k=p.key: ed.press_preset(k), t, start=dot,
                          height=26, indent=10),
                str_(p.description), position="right", theme=t))
    if not rows:
        rows.append(section(tr("No node matches"), t))
    return _core.column([
        _core.container(ui.search_input(ed.query, ed.set_query, placeholder=tr("Search nodes…"), size="sm", theme=t),
                        padding=(spacing.BLOCK, spacing.GUTTER)),
        scroll_panel(_core.column(rows, width="fill", padding=(0, 0, spacing.BLOCK, 0))),
    ], width="fill", height="fill")


VAR_ICONS = {"float": "hash", "int": "binary", "bool": "toggle-left", "vec2": "move", "vec3": "box", "vec4": "boxes",
             "color": "palette", "texture": "image"}


def _add_variable_menu(d: "Designer", t: Theme) -> Any:
    doc = doc_of(d)
    items = [ui.MenuItem(tr("{type} variable", type=v), lambda v=v: (doc.add_variable(v), d.show_panel("properties")),
                         icon=VAR_ICONS[v]) for v in shading.VAR_TYPES]
    return items


def outline(d: "Designer", t: Theme) -> Any:
    """The shader's variables (mutable ones and constants), its named values and its nodes."""
    from .panels import press_row, scroll_panel, section

    doc = doc_of(d)
    g = doc.graph
    ed = d.shading
    adder = ui.split_button(tr("Add"), lambda: (doc.add_variable("float"), d.show_panel("properties")),
                            _add_variable_menu(d, t), size="xs", theme=t) if hasattr(ui, "split_button") else None
    rows: List[Any] = [press_row(d, "shader:", g.name, lambda: (doc.select(None), doc.select_variable(None)), t,
                                 icon=ICON, selected=not doc.selection and doc.variable is None, height=24)]
    rows.append(section(tr("Variables"), t, end=adder))
    if not g.variables:
        rows.append(_core.container(ui.label(tr("Mutable variables change from code without recompiling; constants "
                                                "are built in. Add one, then drag it onto the graph."),
                                             size="xs", color="text_muted", theme=t), padding=(4, spacing.GUTTER)))
    for v in g.variables:
        color = COLORS.get(v.port_type, "#a1a1aa")
        dot = _core.container(width=8, height=8, radius=4, bg=v.value if v.type == "color" else color)
        kind = ui.badge(tr("const") if not v.mutable else tr("mutable"), tint="neutral" if not v.mutable else "accent",
                        theme=t)
        value = _core.text(describe(v.value, v.port_type if v.type != "color" else "texture")
                           if v.type != "color" else str(v.value), size=11, color=t.text_muted, font="mono", wrap=False)
        rows.append(ui.tooltip(
            press_row(d, f"var:{v.name}", v.name, lambda n=v.name: ed.press_variable(n), t, start=dot,
                      selected=doc.variable == v.name, height=24, end=_core.row([value, kind], spacing=6, align="center")),
            v.description or tr("Drag onto the graph to read it"), position="right", theme=t))
    names = g.locals()
    if names:
        rows.append(section(tr("Named values"), t))
        for name in names:
            setter = next(n for n in g.nodes.values() if n.type == "set_var" and n.params.get("name") == name)
            rows.append(press_row(d, f"local:{name}", name, lambda i=setter.id: _select_and_show(d, i), t,
                                  icon="arrow-down-to-line", height=24,
                                  end=ui.icon_button("arrow-up-from-line",
                                                     lambda n=name: doc.add_node("get_var", None, name=n), size="xs",
                                                     tooltip=tr("Add a Get value node"), theme=t)))
    rows.append(section(tr("Nodes"), t, end=ui.label(str(len(g.nodes)), size="xs", color="text_muted", theme=t)))
    errors = doc.diagnostics()
    for node in sorted(g.nodes.values(), key=lambda n: (n.x, n.y)):
        nt = N.TYPES.get(node.type)
        icon = nt.icon if nt and nt.icon else N.CATEGORIES.get(N.category_of(node.type), ("circle",))[0]
        rows.append(press_row(d, f"node:{node.id}", node.title or str_(g.title(node)),
                              lambda i=node.id: _select_and_show(d, i), t, icon=icon,
                              selected=node.id in doc.selection, height=24,
                              color="error" if node.id in errors else None))
    return scroll_panel(_core.column(rows, width="fill"))


def _select_and_show(d: "Designer", node_id: str) -> None:
    """Selects a node from the outline and scrolls the graph to it."""
    doc = doc_of(d)
    doc.select(node_id)
    node = doc.graph.nodes.get(node_id)
    if node is None:
        return
    x, y = doc.to_view(node.x, node.y)
    vw, vh = doc.view_size
    if not (0 <= x <= vw - 100 and 0 <= y <= vh - 80):
        w, h = L.size(doc.graph, node)
        doc.pan = (vw / 2 - (node.x + w / 2) * doc.zoom, vh / 2 - (node.y + h / 2) * doc.zoom)
    d.focus = "canvas"


def design_panel(d: "Designer", t: Theme) -> Any:
    """The left dock's Design panel for a shader: the node sidebar over the outline."""
    top = _core.column([ui.panel_header(tr("Shading"), icon=ICON, theme=t), toolbox(d, t)], width="fill", height="fill")
    bottom = _core.column([ui.panel_header(tr("Outline"), icon="layers", theme=t), outline(d, t)], width="fill",
                          height="fill")
    return ui.split(top, bottom, vertical=True, ratio=d.left_ratio, on_resize=d.resize_left, min_size=120, theme=t)


# -- right dock: properties -----------------------------------------------------------------------------------


def _value_editor(d: "Designer", key: str, type_: str, value: Any, on_change: Callable[[Any], Any], t: Theme, *,
                  hint: str = "", vmin: Optional[float] = None, vmax: Optional[float] = None,
                  step: Optional[float] = None) -> Any:
    """An editor for a value of ``type_``: number (with a slider when it has a range), switch, components, color."""
    from .panels import prop_color_editor

    if type_ == "bool":
        return _core.container(ui.switch(bool(value), on_change, theme=t), width="fill", align_x="end")
    if type_ == "color" or hint == "color" and type_ in ("vec3", "vec4"):
        hexed = value if isinstance(value, str) else to_hex(value)
        return prop_color_editor(d, hexed, lambda v: on_change(v) if v else None, key, t)
    if type_ in ("float", "int"):
        number = float(components(value, 1)[0]) if not isinstance(value, (int, float)) else float(value)
        integer = type_ == "int"
        rng = None
        if hint.startswith("range:"):
            parts = hint.split(":")
            rng = (float(parts[1]), float(parts[2]))
        elif vmin is not None and vmax is not None and vmax > vmin:
            rng = (float(vmin), float(vmax))
        field = ui.number_field(number, lambda v: on_change(int(v) if integer else v), step=step or (1 if integer else 0.1),
                                width=96, theme=t)
        if rng is None:
            return _core.container(field, width="fill", align_x="start")
        slider = ui.slider(number, lambda v: on_change(int(round(v)) if integer else round(v, 4)), min=rng[0], max=rng[1],
                           step=step or (1 if integer else (rng[1] - rng[0]) / 200), theme=t)
        return _core.row([slider, field], spacing=8, align="center")
    if type_ in ("vec2", "vec3", "vec4"):
        n = SIZE[type_]
        parts = list(components(value, n))

        def set_part(i: int, v: float) -> None:
            new = list(parts)
            new[i] = v
            on_change(new)

        cells = [_core.row([_core.text("xyzw"[i], size=11, color=t.text_muted, font="mono"),
                            ui.number_field(round(parts[i], 4), lambda v, i=i: set_part(i, v), step=step or 0.01,
                                            width=112, theme=t)], spacing=4, align="center") for i in range(n)]
        return _core.grid(cells, columns="1fr 1fr", spacing=4)
    if type_ == "texture":
        return ui.input(str(value or ""), on_change, placeholder=tr("image path"), size="sm", mono=True, theme=t)
    return ui.input(str(value), on_change, size="sm", theme=t)


def _prop(title: str, editor: Any, t: Theme, *, tip: Optional[str] = None, tall: bool = False) -> Any:
    from .panels import prop_row

    return prop_row(title, editor, t, tip=tip, tall=tall)


def properties(d: "Designer", t: Theme) -> Any:
    """The Properties panel for a shader: the selected node, the selected variable, or the shader itself."""
    from .panels import scroll_panel

    doc = doc_of(d)
    if doc.variable is not None and doc.graph.variable(doc.variable) is not None:
        body = variable_properties(d, t)
    elif len(doc.selection) == 1:
        body = node_properties(d, doc.selection[0], t)
    elif len(doc.selection) > 1:
        body = _core.column([ui.empty_state(tr("{count} nodes selected", count=len(doc.selection)),
                                            tr("Select one node to see its settings."), icon="layers", theme=t)])
    else:
        body = shader_properties(d, t)
    return scroll_panel(_core.container(body, padding=(8, 0, 16, spacing.GUTTER), width="fill"))


def _header(icon: str, color: str, title: str, subtitle: str, t: Theme, end: Any = None) -> Any:
    return _core.container(_core.row([
        _icon(icon, size=16, color=color),
        _core.column([ui.label(title, weight="semibold", wrap=False, theme=t),
                      ui.label(subtitle, size="xs", color="text_muted", theme=t)], width="fill"),
        end,
    ], spacing=10, align="center"), padding=(4, 0, 8, 0), width="fill")


def node_properties(d: "Designer", node_id: str, t: Theme) -> Any:
    doc = doc_of(d)
    g = doc.graph
    node = g.nodes[node_id]
    nt = N.TYPES.get(node.type)
    types = shading.resolve_types(g).get(node.id, {})
    title = str_(g.title(node))
    icon = nt.icon if nt and nt.icon else N.CATEGORIES.get(N.category_of(node.type), ("circle",))[0]
    rows: List[Any] = [_header(icon, _category_color(node.type), node.title or title,
                               f"{str_(nt.title) if nt else node.type} · {str_(N.category_of(node.type))}", t,
                               end=ui.icon_button("trash-2", d.delete, size="sm", tooltip=tr("Delete"), theme=t))]
    if nt is not None:
        rows.append(_core.container(ui.label(str_(nt.description), size="sm", color="text_muted", theme=t),
                                    padding=(0, 0, 8, 0), width="fill"))
    error = doc.diagnostics().get(node.id)
    if error:
        rows.append(ui.callout(tr("Problem"), error, tint="error", theme=t))
    rows.append(_prop("Title", ui.input(node.title, lambda v: doc.set_title(node.id, v), placeholder=title, size="sm",
                                        theme=t), t))
    if nt is not None and nt.params:
        rows.append(_section(tr("Settings"), t))
        for p in nt.params:
            rows.append(_param_editor(d, node, p, t))
    inputs, outputs = g.ports(node)
    if inputs:
        rows.append(_section(tr("Inputs"), t))
    for p in inputs:
        type_ = types.get(f"in:{p.name}", p.type)
        link = g.link_into(node.id, p.name)
        badge = _core.text(LABELS.get(type_, type_), size=10, color=COLORS.get(type_, t.text_muted), font="mono")
        label = _core.row([_core.text(str_(p.title), size=13, color=t.text_muted, wrap=False), badge], spacing=6,
                          align="center")
        if link is not None:
            src = g.nodes.get(link.src)
            name = (src.title or str_(g.title(src))) if src else link.src
            editor = _core.row([
                _icon("link", size=12, color=t.icon_muted),
                _core.text(f"{name} · {str_(link.out)}", size=12, color=t.text_accent, width="fill", wrap=False),
                ui.icon_button("unlink", lambda n=p.name: doc.disconnect(node.id, n), size="xs", tooltip=tr("Disconnect"),
                               theme=t),
            ], spacing=6, align="center")
        else:
            editor = _input_editor(d, node, p, type_, t)
        rows.append(_core.container(_core.column([label, editor], spacing=4, width="fill"), padding=(4, 0),
                                    width="fill"))
    if outputs:
        rows.append(_section(tr("Outputs"), t))
        for o in outputs:
            type_ = types.get(o.name, o.type)
            rows.append(_core.row([
                _core.container(width=8, height=8, radius=4, bg=COLORS.get(type_, "#a1a1aa")),
                _core.text(str_(o.title), size=13, color=t.text, width="fill"),
                _core.text(LABELS.get(type_, type_), size=11, color=t.text_muted, font="mono"),
            ], spacing=8, align="center", padding=(3, 0)))
    if outputs:
        rows.append(_prop("Preview", _core.container(ui.switch(node.preview, lambda _v: doc.toggle_preview(node.id),
                                                               theme=t), width="fill", align_x="end"), t))
    return _core.column(rows, spacing=spacing.ROW_GAP, width="fill")


def _section(title: str, t: Theme) -> Any:
    return _core.container(ui.label(title.upper(), size="xs", weight="semibold", color="text_muted", theme=t),
                           padding=(12, 0, 2, 0), width="fill")


def _input_editor(d: "Designer", node: shading.Node, p: N.Input, type_: str, t: Theme) -> Any:
    doc = doc_of(d)
    value = node.inputs.get(p.name, p.default)
    key = f"shader-in:{node.id}:{p.name}"

    def change(v: Any) -> None:
        doc.set_input(node.id, p.name, v)

    if p.type == "texture":
        return ui.label(tr("Connect a texture variable"), size="sm", color="text_muted", theme=t)
    if isinstance(p.default, str) and p.default in N.CONTEXT:
        current = isinstance(value, str) and value in N.CONTEXT
        choice = ui.segmented([str_(N.CONTEXT_LABELS[p.default]), tr("Value")],
                              str_(N.CONTEXT_LABELS[p.default]) if current else tr("Value"),
                              lambda label: change(p.default if label != tr("Value")
                                                   else list(components(0.0, SIZE.get(type_, 1)))
                                                   if SIZE.get(type_, 1) > 1 else 0.0), theme=t)
        if current:
            return choice
        return _core.column([choice, _value_editor(d, key, type_, value, change, t, hint=p.hint)], spacing=4)
    if value is None:
        return ui.label(tr("Not used until connected"), size="sm", color="text_muted", theme=t)
    return _value_editor(d, key, type_, value, change, t, hint=p.hint)


def _param_editor(d: "Designer", node: shading.Node, p: N.Param, t: Theme) -> Any:
    from .panels import text_area

    doc = doc_of(d)
    g = doc.graph
    value = node.params.get(p.name, p.default)

    def change(v: Any) -> None:
        error = doc.set_param(node.id, p.name, v)
        if error:
            d.notify(tr("Can't change that"), error, kind="warning")

    if p.kind == "enum":
        labels = {_option_label(node.type, o): o for o in p.options}
        editor = ui.select(list(labels), _option_label(node.type, str(value)),
                           lambda label: change(labels.get(label, label)), width="fill", size="sm", theme=t)
        return _prop(str_(p.title), editor, t)
    if p.kind == "variable":
        names = [v.name for v in g.variables]
        editor = ui.select(names, value if value in names else None, change, width="fill", size="sm",
                           placeholder=tr("Variable…"), theme=t) if names else \
            ui.label(tr("Add a variable in the Outline first"), size="sm", color="text_muted", theme=t)
        return _prop("Variable", editor, t)
    if p.kind == "local":
        names = g.locals()
        editor = ui.select(names, value if value in names else None, change, width="fill", size="sm", theme=t) if names \
            else ui.input(str(value), change, size="sm", mono=True, theme=t)
        return _prop("Name", editor, t)
    if p.kind == "code":
        return _prop(str_(p.title), text_area(d, f"shader-code:{node.id}", value, change, t, height=120), t, tall=True,
                     tip=tr("An expression of a, b, c and d, or statements ending in return"))
    if p.kind == "stops":
        return _prop(str_(p.title), _stops_editor(d, node, value, change, t), t, tall=True)
    if p.kind == "file":
        files = _shader_files(d)
        editor = _core.column([
            ui.input(str(value), change, placeholder="shaders/other.pzshad", size="sm", mono=True, theme=t),
            ui.select(files, value if value in files else None, change, width="fill", size="sm",
                      placeholder=tr("Shaders in this project…"), theme=t) if files else None,
        ], spacing=4)
        return _prop(str_(p.title), editor, t, tall=True)
    if p.kind == "text":
        return _prop(str_(p.title), ui.input(str(value), change, size="sm", mono=True, theme=t), t)
    return _prop(str_(p.title), _value_editor(d, f"shader-param:{node.id}:{p.name}", p.kind, value, change, t), t)


def _shader_files(d: "Designer") -> List[str]:
    """The other ``.pzshad`` files next to the open one (and below it), relative to it."""
    doc = doc_of(d)
    base = doc.path.parent if doc.path else None
    root = d.projects.project.root if d.projects.project is not None else base
    if root is None:
        return []
    out = []
    try:
        for p in sorted(root.rglob(f"*{shading.SUFFIX}"))[:200]:
            if doc.path is not None and p.resolve() == doc.path.resolve():
                continue
            if any(part.startswith(".") or part in ("node_modules", ".venv", "target") for part in p.parts):
                continue
            try:
                out.append(str(p.relative_to(base)).replace("\\", "/") if base else str(p))
            except ValueError:
                import os

                out.append(os.path.relpath(p, base).replace("\\", "/") if base else str(p))
    except OSError:
        return out
    return out


def _stops_editor(d: "Designer", node: shading.Node, value: Any, change: Callable[[Any], Any], t: Theme) -> Any:
    stops = [list(s) for s in N.gradient_stops(value)]

    def set_stop(i: int, pos: Optional[float] = None, color: Optional[str] = None) -> None:
        new = [list(s) for s in stops]
        if pos is not None:
            new[i][0] = max(0.0, min(1.0, pos))
        if color:
            new[i][1] = color
        change(new)

    def remove(i: int) -> None:
        if len(stops) > 2:
            change([s for j, s in enumerate(stops) if j != i])

    def add() -> None:
        last = stops[-1]
        change([*stops, [min(1.0, last[0] + 0.1) if last[0] < 1 else 1.0, last[1]]])

    from .panels import prop_color_editor

    rows = [_core.container(width="fill", height=14, radius=3,
                            gradient=(90, [(p, c) for p, c in stops]), border_color=t.border, border_width=1)]
    for i, (pos, color) in enumerate(stops):
        rows.append(_core.row([
            ui.number_field(float(pos), lambda v, i=i: set_stop(i, pos=v), min=0, max=1, step=0.05, width=88, theme=t),
            _core.container(prop_color_editor(d, color, lambda v, i=i: set_stop(i, color=v),
                                              f"shader-stop:{node.id}:{i}", t), width="fill"),
            ui.icon_button("x", lambda i=i: remove(i), size="xs", disabled=len(stops) <= 2, tooltip=tr("Remove"), theme=t),
        ], spacing=6, align="center"))
    rows.append(ui.button(tr("Add a color"), add, icon="plus", size="sm", variant="ghost", theme=t))
    return _core.column(rows, spacing=6, width="fill")


def variable_properties(d: "Designer", t: Theme) -> Any:
    doc = doc_of(d)
    g = doc.graph
    var = g.variable(doc.variable or "")
    assert var is not None

    def change(**values: Any) -> None:
        error = doc.set_variable(var.name, **values)
        if error:
            d.notify(tr("Can't change the variable"), error, kind="warning")

    rows: List[Any] = [_header(VAR_ICONS.get(var.type, "variable"), COLORS.get(var.port_type, t.accent), var.name,
                               tr("Mutable variable (uniform)") if var.mutable else tr("Constant"), t,
                               end=ui.icon_button("trash-2", lambda: doc.remove_variable(var.name), size="sm",
                                                  tooltip=tr("Delete the variable and its nodes"), theme=t))]
    rows.append(_prop("Name", ui.input(var.name, lambda v: change(name=v) if shading.valid_name(v) else None,
                                       size="sm", mono=True, theme=t), t, tip=tr("How code and nodes read it")))
    rows.append(_prop("Type", ui.select(list(shading.VAR_TYPES), var.type, lambda v: change(type=v), width="fill",
                                        size="sm", theme=t), t))
    if var.type != "texture":
        rows.append(_prop("Mutable", _core.container(ui.switch(var.mutable, lambda v: change(mutable=v), theme=t),
                                                     width="fill", align_x="end"), t,
                          tip=tr("Mutable variables change without recompiling (shader.set, sliders); constants are "
                                 "written into the code")))
    rows.append(_prop("Value", _value_editor(d, f"shader-var:{var.name}", var.type, var.value,
                                             lambda v: change(value=v), t, vmin=var.min, vmax=var.max,
                                             step=var.step), t, tall=var.type in ("vec2", "vec3", "vec4", "texture")))
    if var.type in ("float", "int"):
        rows.append(_prop("Min", ui.number_field(float(var.min if var.min is not None else 0), lambda v: change(min=v),
                                                 step=0.1, width=96, theme=t), t))
        rows.append(_prop("Max", ui.number_field(float(var.max if var.max is not None else 1), lambda v: change(max=v),
                                                 step=0.1, width=96, theme=t), t))
    rows.append(_prop("Description", ui.input(var.description, lambda v: change(description=v), size="sm",
                                              placeholder=tr("What it does"), theme=t), t))
    rows.append(_core.container(ui.button(tr("Add a node that reads it"), lambda: doc.add_parameter(var.name),
                                          icon="plus", size="sm", variant="tinted", tint="accent", theme=t),
                                padding=(8, 0)))
    code = (f'shader = shading.load("{doc.display_name}")\nshader["{var.name}"] = …'
            if var.mutable else f'shader.set({var.name}=…)  # rebuilds the code')
    rows.append(_section(tr("From code"), t))
    rows.append(_core.container(_core.text(code, size=11.5, color=t.text_accent, font="mono"), padding=8,
                                width="fill", bg=t.editor, radius=t.radius_sm))
    return _core.column(rows, spacing=spacing.ROW_GAP, width="fill")


def shader_properties(d: "Designer", t: Theme) -> Any:
    doc = doc_of(d)
    g = doc.graph
    compiled = shading.compile(g)
    rows: List[Any] = [_header(ICON, t.accent, g.name, tr("Shader · {count} nodes", count=len(g.nodes)), t)]
    rows.append(_prop("Name", ui.input(g.name, doc.set_name, size="sm", mono=True, theme=t), t))
    rows.append(_prop("Description", ui.input(g.description, doc.set_description, size="sm",
                                              placeholder=tr("What it draws"), theme=t), t))
    rows.append(_section(tr("Drawing"), t))
    rows.append(_prop("Width", ui.number_field(float(g.preview.get("width") or 320),
                                               lambda v: doc.set_preview("width", int(v)), min=16, step=10, width=96,
                                               theme=t), t, tip=tr("The size of the Preview tab and of Run")))
    rows.append(_prop("Height", ui.number_field(float(g.preview.get("height") or 200),
                                                lambda v: doc.set_preview("height", int(v)), min=16, step=10, width=96,
                                                theme=t), t))
    from .panels import prop_color_editor

    rows.append(_prop("Fallback", prop_color_editor(d, g.preview.get("fallback") or "",
                                                    lambda v: doc.set_preview("fallback", v), "shader-fallback", t), t,
                      tip=tr("What draws instead on computers without a GPU")))
    rows.append(_prop("Animate", _core.container(ui.switch(g.preview.get("animate", True) is not False,
                                                           lambda v: doc.set_preview("animate", bool(v)), theme=t),
                                                 width="fill", align_x="end"), t,
                      tip=tr("Redraw every frame while it uses Time")))
    rows.append(_section(tr("Uses"), t))
    rows.append(_core.column([
        ui.label(tr("{count} mutable variables", count=len(compiled.uniforms)), size="sm", color="text_muted", theme=t),
        ui.label(tr("{count} textures", count=len(compiled.textures)), size="sm", color="text_muted", theme=t),
        ui.label(tr("Changes with time") if compiled.uses_time else tr("Still image"), size="sm", color="text_muted",
                 theme=t),
    ], spacing=2))
    name = doc.display_name
    rows.append(_section(tr("From code"), t))
    rows.append(_core.container(_core.text(f'pz.shader("{name}", width=320, height=200)', size=11.5,
                                           color=t.text_accent, font="mono"), padding=8, width="fill", bg=t.editor,
                                radius=t.radius_sm))
    return _core.column(rows, spacing=spacing.ROW_GAP, width="fill")


def variables_panel(d: "Designer", t: Theme, compact: bool = False) -> Any:
    """Sliders for the shader's variables (the Preview tab's side panel)."""
    from .panels import scroll_panel

    doc = doc_of(d)
    g = doc.graph
    rows: List[Any] = [_core.container(_core.row([
        _icon("sliders-horizontal", size=14, color=t.accent),
        ui.label(tr("Variables"), weight="semibold", theme=t, width="fill"),
        ui.icon_button("pause" if d.shading.paused is None else "play", d.shading.toggle_time, size="sm",
                       tooltip=tr("Stop time") if d.shading.paused is None else tr("Start time"), theme=t),
    ], spacing=8, align="center"), padding=(10, 12), width="fill")]
    if not g.variables:
        rows.append(_core.container(ui.label(tr("This shader has no variables. Add them in the Outline to tune it "
                                                "here and from code."), size="sm", color="text_muted", theme=t),
                                    padding=(0, 12)))
    for var in g.variables:
        def change(v: Any, name: str = var.name) -> None:
            doc.set_variable(name, value=v)

        editor = _value_editor(d, f"shader-preview:{var.name}", var.type, var.value, change, t, vmin=var.min,
                               vmax=var.max, step=var.step)
        head = _core.row([_core.text(var.name, size=13, color=t.text, font="mono", width="fill"),
                          ui.badge(tr("const") if not var.mutable else tr("mutable"),
                                   tint="neutral" if not var.mutable else "accent", theme=t)], align="center")
        rows.append(_core.container(_core.column([head, editor], spacing=6, width="fill"), padding=(6, 12),
                                    width="fill"))
    return scroll_panel(_core.column(rows, width="fill"))


def events(d: "Designer", t: Theme) -> Any:
    """The Events panel has nothing for a shader: say how it is used instead."""
    return ui.empty_state(tr("Shaders have no events"),
                          tr("Use it from code with pz.shader(\"{name}\") or place a Shader control on a form; "
                             "change its mutable variables to animate it.", name=doc_of(d).display_name),
                          icon=ICON, theme=t)


def status_items(d: "Designer", t: Theme) -> List[Any]:
    doc = doc_of(d)
    gx, gy = d.shading.graph_pointer()
    g = doc.graph
    info = tr("{count} selected", count=len(doc.selection)) if doc.selection else \
        tr("{nodes} nodes · {links} wires", nodes=len(g.nodes), links=len(g.links))
    return [ui.status_item(f"{gx:.0f}, {gy:.0f}", icon="mouse-pointer-2"),
            ui.status_item(info, icon=ICON),
            ui.status_item(f"{doc.zoom * 100:.0f}%", lambda: doc.set_zoom(1.0), icon="zoom-in")]


# -- Run: the shader in a window of its own ------------------------------------------------------------------------


def _window_class():
    from ..app import Window

    class _ShaderWindow(Window):
        """The shader filling a window (F5), redrawn as the graph changes."""

        def __init__(self, d: "Designer") -> None:
            doc = doc_of(d)
            self.d = d
            self.doc = doc
            self.title = f"{doc.graph.name} — {tr('Shader')}"
            self.size = (int(doc.graph.preview.get("width") or 320) + 40, int(doc.graph.preview.get("height") or 200) + 40)
            super().__init__()

        def view(self) -> Any:
            compiled = shading.compile(self.doc.graph)
            t = self.d.theme_obj
            return _core.container(
                shader_widget(compiled.code, compiled.uniforms, compiled.textures, "fill", "fill", t,
                              time_=self.d.shading.time(), animate=compiled.uses_time),
                width="fill", height="fill", bg="#000000")

    return _ShaderWindow


def __getattr__(name: str) -> Any:  # ShaderWindow is built lazily (it needs pyzed.app)
    if name == "ShaderWindow":
        return _window_class()
    raise AttributeError(name)
