"""A shader graph: nodes, the wires between their ports, and the shader's variables.

Build one in code or in Pyzed Design (``.pzshad`` files)::

    from pyzed import shading

    g = shading.Graph("glow")
    speed = g.uniform("speed", "float", 1.0, min=0, max=4)    # a mutable variable
    t = g.time(scale=speed)                                   # nodes are methods of the graph
    ring = g.ring(radius=0.3 + 0.05 * t["sin"])               # math on ports adds nodes
    glow = g.glow(ring, radius=0.08)
    g.output(g.rgba(g.palette(t) * glow, 1.0))
    g.save("glow.pzshad")

``g.<type>(...)`` adds a node of that type (see ``pyzed.shading.nodes.TYPES``) or a
sidebar entry such as ``g.sin(x)`` or ``g.multiply(a, b)``. Positional arguments go to
the node's inputs in order, keyword arguments to inputs or settings by name. A value
can be a constant or a port (``node["value"]``; a node stands for its first output).
"""

from __future__ import annotations

import copy as _copy
import json
import keyword
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple, Union

from . import nodes as _nodes
from .types import GENERIC, SIZE, TYPES, can_connect, coerce, default_value, to_hex

#: The ``format`` field of a ``.pzshad`` file.
FORMAT = "pyzed.shader/1"
SUFFIX = ".pzshad"

#: The types a variable can have (``color`` is a ``vec4`` edited with a color picker).
VAR_TYPES = ("float", "int", "bool", "vec2", "vec3", "vec4", "color", "texture")

#: Names a variable can't take: WGSL keywords and what every shader already defines.
RESERVED = {
    "uv", "px", "size", "time", "mouse", "shade", "fn", "let", "var", "const", "if", "else", "for", "while",
    "loop", "return", "break", "continue", "switch", "case", "default", "true", "false", "struct", "alias",
    "discard", "enable", "override", "f32", "i32", "u32", "bool", "vec2", "vec3", "vec4", "mat2x2", "mat3x3",
    "mat4x4", "array", "ptr", "texture", "sampler", "pyzed", "self", "loop", "continuing", "diagnostic",
    "requires", "const_assert", "fallthrough",
}

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_SWIZZLE = re.compile(r"[xyzw]{1,4}$|[rgba]{1,4}$")

Number = Union[int, float]


def valid_name(name: str) -> bool:
    """Whether ``name`` can name a variable: letters, digits and ``_``, not a reserved word, not ``pzs_...``."""
    return bool(_IDENT.match(name or "")) and name not in RESERVED and not name.startswith(("pzs_", "__")) \
        and not keyword.iskeyword(name)


@dataclass
class Variable:
    """A variable of the shader, listed in the outline.

    A *mutable* variable is a uniform: changing it (``shader.set(...)``, a slider) redraws
    without recompiling. A constant (``mutable=False``) is written into the shader's code.
    ``texture`` variables hold the path of an image (relative to the ``.pzshad``).
    """

    name: str
    type: str = "float"
    value: Any = None
    mutable: bool = True
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    description: str = ""

    def __post_init__(self) -> None:
        if self.type not in VAR_TYPES:
            raise ValueError(f"a variable's type is one of {', '.join(VAR_TYPES)}, not {self.type!r}")
        self.value = normalize(self.value, self.type)
        if self.type == "texture":
            self.mutable = True

    @property
    def port_type(self) -> str:
        """The type of the value in the graph (``vec4`` for colors)."""
        return "vec4" if self.type == "color" else self.type

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"name": self.name, "type": self.type, "value": self.value}
        if not self.mutable:
            out["mutable"] = False
        for key in ("min", "max", "step"):
            if getattr(self, key) is not None:
                out[key] = getattr(self, key)
        if self.description:
            out["description"] = self.description
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Variable":
        return cls(str(data["name"]), str(data.get("type", "float")), data.get("value"),
                   bool(data.get("mutable", True)), data.get("min"), data.get("max"), data.get("step"),
                   str(data.get("description", "")))


def normalize(value: Any, type_: str) -> Any:
    """``value`` the way a variable or a setting of ``type_`` is stored."""
    if type_ == "color":
        if value is None:
            return "#ffffff"
        return value if isinstance(value, str) else to_hex(value)
    if type_ == "texture":
        return str(value or "")
    if value is None:
        value = default_value(type_)
    return coerce(value, type_)


@dataclass
class Node:
    """A node placed on the graph: its type, where it is, and the values of its unconnected inputs."""

    id: str
    type: str
    x: float = 0.0
    y: float = 0.0
    #: Values of inputs while nothing is connected to them (the type's defaults otherwise).
    inputs: Dict[str, Any] = field(default_factory=dict)
    #: The node's settings (``op``, ``kind``, ``code``...).
    params: Dict[str, Any] = field(default_factory=dict)
    #: A title of your own (the type's title otherwise).
    title: str = ""
    #: Whether the node shows a preview of its first output.
    preview: bool = True

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"id": self.id, "type": self.type, "x": round(self.x, 1), "y": round(self.y, 1)}
        if self.inputs:
            out["inputs"] = self.inputs
        if self.params:
            out["params"] = self.params
        if self.title:
            out["title"] = self.title
        if not self.preview:
            out["preview"] = False
        return out

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        return cls(str(data["id"]), str(data["type"]), float(data.get("x", 0)), float(data.get("y", 0)),
                   dict(data.get("inputs") or {}), dict(data.get("params") or {}), str(data.get("title", "")),
                   bool(data.get("preview", True)))


@dataclass(frozen=True)
class Link:
    """A wire from the output ``out`` of node ``src`` to the input ``inp`` of node ``dst``."""

    src: str
    out: str
    dst: str
    inp: str

    def to_dict(self) -> Dict[str, str]:
        return {"from": self.src, "out": self.out, "to": self.dst, "in": self.inp}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Link":
        return cls(str(data["from"]), str(data["out"]), str(data["to"]), str(data["in"]))


class Socket:
    """An output port of a node, used to wire it in code. Arithmetic adds Math nodes:
    ``a * 2.0 + b``; ``.x``, ``.xy``, ``.rgb`` add a Swizzle node."""

    __slots__ = ("graph", "node", "port")

    def __init__(self, graph: "Graph", node: str, port: str) -> None:
        self.graph = graph
        self.node = node
        self.port = port

    def __repr__(self) -> str:
        return f"<Socket {self.node}.{self.port}>"

    def _math(self, op: str, a: Any, b: Any) -> "Socket":
        return self.graph.add("math", op=op, a=a, b=b)["result"]

    def __add__(self, other: Any) -> "Socket":
        return self._math("add", self, other)

    def __radd__(self, other: Any) -> "Socket":
        return self._math("add", other, self)

    def __sub__(self, other: Any) -> "Socket":
        return self._math("subtract", self, other)

    def __rsub__(self, other: Any) -> "Socket":
        return self._math("subtract", other, self)

    def __mul__(self, other: Any) -> "Socket":
        return self._math("multiply", self, other)

    def __rmul__(self, other: Any) -> "Socket":
        return self._math("multiply", other, self)

    def __truediv__(self, other: Any) -> "Socket":
        return self._math("divide", self, other)

    def __rtruediv__(self, other: Any) -> "Socket":
        return self._math("divide", other, self)

    def __mod__(self, other: Any) -> "Socket":
        return self._math("modulo", self, other)

    def __pow__(self, other: Any) -> "Socket":
        return self._math("power", self, other)

    def __neg__(self) -> "Socket":
        return self.graph.add("func", self, op="negate")["result"]

    def __getattr__(self, name: str) -> "Socket":
        if _SWIZZLE.match(name):
            return self.graph.add("swizzle", vector=self, mask=name)["result"]
        raise AttributeError(name)


class NodeRef:
    """A node of a graph, as ``Graph.add`` returns it: ``ref["port"]`` is one of its outputs,
    and the ref itself stands for its first output."""

    __slots__ = ("graph", "id")

    def __init__(self, graph: "Graph", id_: str) -> None:
        self.graph = graph
        self.id = id_

    def __repr__(self) -> str:
        node = self.node
        return f"<NodeRef {self.id} {node.type}>"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, NodeRef) and other.graph is self.graph and other.id == self.id

    def __hash__(self) -> int:
        return hash((id(self.graph), self.id))

    @property
    def node(self) -> Node:
        """The node itself."""
        return self.graph.nodes[self.id]

    def __getitem__(self, port: str) -> Socket:
        outputs = [o.name for o in self.graph.ports(self.node)[1]]
        if port not in outputs:
            raise KeyError(f"{self.node.type} has no output {port!r} (it has {', '.join(outputs) or 'none'})")
        return Socket(self.graph, self.id, port)

    def out(self, port: Optional[str] = None) -> Socket:
        """The output ``port`` (the first one by default)."""
        if port is None:
            outputs = self.graph.ports(self.node)[1]
            if not outputs:
                raise ValueError(f"{self.node.type} has no outputs")
            port = outputs[0].name
        return self[port]

    def set(self, **values: Any) -> "NodeRef":
        """Sets inputs (constants or ports) and settings by name."""
        self.graph._apply(self.id, (), values)
        return self

    def _default(self) -> Socket:
        return self.out()

    # a node in arithmetic stands for its first output
    def __add__(self, o: Any) -> Socket: return self._default() + o  # noqa: E704
    def __radd__(self, o: Any) -> Socket: return o + self._default() if isinstance(o, Socket) else self._default().__radd__(o)  # noqa: E501,E704
    def __sub__(self, o: Any) -> Socket: return self._default() - o  # noqa: E704
    def __rsub__(self, o: Any) -> Socket: return self._default().__rsub__(o)  # noqa: E704
    def __mul__(self, o: Any) -> Socket: return self._default() * o  # noqa: E704
    def __rmul__(self, o: Any) -> Socket: return self._default().__rmul__(o)  # noqa: E704
    def __truediv__(self, o: Any) -> Socket: return self._default() / o  # noqa: E704
    def __rtruediv__(self, o: Any) -> Socket: return self._default().__rtruediv__(o)  # noqa: E704
    def __mod__(self, o: Any) -> Socket: return self._default() % o  # noqa: E704
    def __pow__(self, o: Any) -> Socket: return self._default() ** o  # noqa: E704
    def __neg__(self) -> Socket: return -self._default()  # noqa: E704

    def __getattr__(self, name: str) -> Socket:
        if _SWIZZLE.match(name):
            return getattr(self._default(), name)
        raise AttributeError(name)


Value = Union[Socket, NodeRef, Number, bool, str, Tuple[Number, ...], List[Number], None]


class GraphError(ValueError):
    """A change that would break the graph (a wire between incompatible ports, a cycle, a bad name)."""


class Graph:
    """A shader made of nodes. See the module docs for building one in code."""

    def __init__(self, name: str = "shader", *, description: str = "") -> None:
        self.name = name
        self.description = description
        self.nodes: Dict[str, Node] = {}
        self.links: List[Link] = []
        self.variables: List[Variable] = []
        #: How the shader is previewed and drawn by default: size, fallback color without a GPU, animation.
        self.preview: Dict[str, Any] = {"width": 320, "height": 200, "fallback": "#1e1b4b", "animate": True}
        #: The ``.pzshad`` file (other files it uses are relative to it).
        self.path: Optional[Path] = None
        #: Goes up on every change, so compiled code can be cached.
        self.revision = 0
        self._next = 1
        self._subgraphs: Dict[str, Tuple[float, Optional["Graph"]]] = {}
        self._types_cache: Optional[Tuple[int, Dict[str, Dict[str, str]]]] = None
        self._compiled: Dict[Any, Any] = {}

    def __repr__(self) -> str:
        return f"<Graph {self.name!r}: {len(self.nodes)} nodes, {len(self.variables)} variables>"

    def touch(self) -> None:
        """Marks the graph changed (cached code is rebuilt)."""
        self.revision += 1

    # -- nodes ------------------------------------------------------------------------
    def ports(self, node: Node) -> _nodes.Ports:
        """The input and output ports of ``node`` (some depend on its settings or on the graph)."""
        nt = _nodes.TYPES.get(node.type)
        if nt is None:
            return ((), ())
        if nt.ports is not None:
            return nt.ports(node, self)
        return (nt.inputs, nt.outputs)

    def input_port(self, node: Node, name: str) -> Optional[_nodes.Input]:
        return next((p for p in self.ports(node)[0] if p.name == name), None)

    def output_port(self, node: Node, name: str) -> Optional[_nodes.Output]:
        return next((p for p in self.ports(node)[1] if p.name == name), None)

    def title(self, node: Node) -> str:
        """What the node's header says."""
        if node.title:
            return node.title
        nt = _nodes.TYPES.get(node.type)
        if nt is None:
            return node.type
        return nt.label(node, self) if nt.label else nt.title

    def new_id(self) -> str:
        """A node id not used yet."""
        while str(self._next) in self.nodes:
            self._next += 1
        out = str(self._next)
        self._next += 1
        return out

    def add(self, type_: str, *args: Value, x: Optional[float] = None, y: Optional[float] = None,
            title: str = "", **values: Value) -> NodeRef:
        """Adds a node of ``type_`` (or a sidebar entry such as ``"sin"``); positional ``args`` go to its
        inputs in order and keyword ``values`` to inputs or settings by name. Returns the new node.

        ``x`` and ``y`` place the node; a wire or a vector given as ``x``/``y`` goes to the input of that
        name instead (Compose, Smoothstep and Clamp have one); pass plain numbers to such inputs in ``args``.
        """
        if x is not None and not isinstance(x, (int, float)):
            values["x"], x = x, None
        if y is not None and not isinstance(y, (int, float)):
            values["y"], y = y, None
        type_, preset_params = _resolve_type(type_)
        nt = _nodes.get(type_)
        node = Node(self.new_id(), type_)
        for p in nt.params:
            if p.default is not None:
                node.params[p.name] = _copy.deepcopy(p.default)
        node.params.update(preset_params)
        node.title = title
        self.nodes[node.id] = node
        try:
            self._apply(node.id, args, values)
        except Exception:
            self.remove(node.id)
            raise
        if x is None or y is None:
            node.x, node.y = self._place(node)
        if x is not None:
            node.x = float(x)
        if y is not None:
            node.y = float(y)
        self.touch()
        return NodeRef(self, node.id)

    def __getattr__(self, name: str) -> Any:
        # g.noise(...), g.sin(...), g.multiply(...): add that node
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            _resolve_type(name)
        except KeyError:
            raise AttributeError(f"{type(self).__name__} has no attribute or node type {name!r}") from None
        return lambda *args, **kwargs: self.add(name, *args, **kwargs)

    def _apply(self, node_id: str, args: Iterable[Value], values: Dict[str, Value]) -> None:
        node = self.nodes[node_id]
        nt = _nodes.get(node.type)
        # settings first: they can change which ports the node has
        for key in list(values):
            if nt.param(key) is not None:
                node.params[key] = _param_value(nt.param(key), values.pop(key))  # type: ignore[arg-type]
        inputs = self.ports(node)[0]
        args = tuple(args)
        if args and not inputs and nt.params:  # g.float(0.5), g.color("#f00"): a constant's value
            for p, value in zip(nt.params, args):
                node.params[p.name] = _param_value(p, value)
            args = ()
        if len(args) > len(inputs):
            raise TypeError(f"{node.type} takes {len(inputs)} inputs")
        named = dict(zip((p.name for p in inputs), args))
        for key, value in values.items():
            if key in named:
                raise TypeError(f"{node.type} got {key!r} twice")
            named[key] = value
        known = {p.name for p in inputs}
        for key, value in named.items():
            if key not in known:
                options = sorted(known | {p.name for p in nt.params})
                raise TypeError(f"{node.type} has no input or setting {key!r} (it has {', '.join(options)})")
            if isinstance(value, NodeRef):
                value = value.out()
            if isinstance(value, Socket):
                if value.graph is not self:
                    raise GraphError("that port belongs to another graph")
                self.connect(value.node, value.port, node_id, key)
            else:
                self.disconnect(node_id, key)
                if value is None:
                    node.inputs.pop(key, None)
                else:
                    node.inputs[key] = _input_value(value)
        self.touch()

    def _place(self, node: Node) -> Tuple[float, float]:
        sources = [self.nodes[l.src] for l in self.links if l.dst == node.id and l.src in self.nodes]
        if sources:
            x = max(s.x for s in sources) + 240
            y = sum(s.y for s in sources) / len(sources)
        else:
            others = [n for n in self.nodes.values() if n.id != node.id]
            x = 0.0
            y = max((n.y for n in others if abs(n.x - x) < 120), default=-140.0) + 140
        while any(abs(n.x - x) < 120 and abs(n.y - y) < 100 for n in self.nodes.values() if n.id != node.id):
            y += 120
        return x, y

    def node(self, node: Union[str, NodeRef]) -> Node:
        """The node with id ``node``."""
        return self.nodes[node.id if isinstance(node, NodeRef) else node]

    def ref(self, node_id: str) -> NodeRef:
        """A ``NodeRef`` for the node ``node_id``."""
        if node_id not in self.nodes:
            raise KeyError(node_id)
        return NodeRef(self, node_id)

    def find(self, type_: Optional[str] = None, **params: Any) -> List[NodeRef]:
        """The nodes of ``type_`` (any type when ``None``) whose settings match ``params``."""
        return [NodeRef(self, n.id) for n in self.nodes.values()
                if (type_ is None or n.type == type_) and all(n.params.get(k) == v for k, v in params.items())]

    def remove(self, node: Union[str, NodeRef]) -> None:
        """Removes a node and its wires."""
        node_id = node.id if isinstance(node, NodeRef) else node
        self.nodes.pop(node_id, None)
        self.links = [l for l in self.links if l.src != node_id and l.dst != node_id]
        self.touch()

    def move(self, node: Union[str, NodeRef], x: float, y: float) -> None:
        """Places a node at ``(x, y)``."""
        n = self.node(node)
        n.x, n.y = float(x), float(y)
        self.touch()

    def set_input(self, node: Union[str, NodeRef], name: str, value: Any) -> None:
        """Sets the value an input takes while nothing is connected (``None`` goes back to the default)."""
        n = self.node(node)
        if self.input_port(n, name) is None:
            raise GraphError(f"{n.type} has no input {name!r}")
        if value is None:
            n.inputs.pop(name, None)
        else:
            n.inputs[name] = _input_value(value)
        self.touch()

    def set_param(self, node: Union[str, NodeRef], name: str, value: Any) -> None:
        """Changes a setting of a node; wires to ports it no longer has are removed."""
        n = self.node(node)
        p = _nodes.get(n.type).param(name)
        if p is None:
            raise GraphError(f"{n.type} has no setting {name!r}")
        n.params[name] = _param_value(p, value)
        self._prune(n)
        self.touch()

    def _prune(self, node: Node) -> None:
        inputs, outputs = self.ports(node)
        ins, outs = {p.name for p in inputs}, {p.name for p in outputs}
        self.links = [l for l in self.links if not (l.dst == node.id and l.inp not in ins)
                      and not (l.src == node.id and l.out not in outs)]

    # -- wires ------------------------------------------------------------------------
    def link_into(self, node: Union[str, NodeRef], name: str) -> Optional[Link]:
        """The wire connected to an input, or ``None``."""
        node_id = node.id if isinstance(node, NodeRef) else node
        return next((l for l in self.links if l.dst == node_id and l.inp == name), None)

    def links_from(self, node: Union[str, NodeRef], port: Optional[str] = None) -> List[Link]:
        """The wires leaving a node (from one output, or from any)."""
        node_id = node.id if isinstance(node, NodeRef) else node
        return [l for l in self.links if l.src == node_id and (port is None or l.out == port)]

    def connect(self, src: Union[str, NodeRef], out: str, dst: Union[str, NodeRef], inp: str) -> Link:
        """Wires the output ``out`` of ``src`` to the input ``inp`` of ``dst``, replacing the wire that was there.

        Raises ``GraphError`` if a port doesn't exist, the types can't connect or the wire makes a loop.
        """
        src_id = src.id if isinstance(src, NodeRef) else src
        dst_id = dst.id if isinstance(dst, NodeRef) else dst
        if src_id not in self.nodes or dst_id not in self.nodes:
            raise GraphError("both nodes must be in the graph")
        o = self.output_port(self.nodes[src_id], out)
        i = self.input_port(self.nodes[dst_id], inp)
        if o is None:
            raise GraphError(f"{self.nodes[src_id].type} has no output {out!r}")
        if i is None:
            raise GraphError(f"{self.nodes[dst_id].type} has no input {inp!r}")
        out_type = self.output_type(src_id, out)
        if i.type not in ("any",) and not can_connect(out_type, i.type):
            raise GraphError(f"a {out_type} can't connect to {i.title} ({i.type})")
        if i.type == "any" and out_type == "texture":
            raise GraphError("a texture can't connect to an expression")
        if src_id == dst_id or self._reaches(dst_id, src_id):
            raise GraphError("that wire would make a loop")
        self.links = [l for l in self.links if not (l.dst == dst_id and l.inp == inp)]
        link = Link(src_id, out, dst_id, inp)
        self.links.append(link)
        self.touch()
        return link

    def disconnect(self, dst: Union[str, NodeRef], inp: str) -> bool:
        """Removes the wire into an input; returns whether there was one."""
        dst_id = dst.id if isinstance(dst, NodeRef) else dst
        before = len(self.links)
        self.links = [l for l in self.links if not (l.dst == dst_id and l.inp == inp)]
        if len(self.links) != before:
            self.touch()
            return True
        return False

    def _reaches(self, start: str, goal: str) -> bool:
        """Whether ``goal`` is downstream of ``start`` (following wires and named values)."""
        seen = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur == goal:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(l.dst for l in self.links if l.src == cur)
            node = self.nodes.get(cur)
            if node is not None and node.type == "set_var":
                name = node.params.get("name")
                stack.extend(n.id for n in self.nodes.values() if n.type == "get_var" and n.params.get("name") == name)
        return False

    def upstream(self, node_id: str) -> List[str]:
        """``node_id`` and every node it reads from, each after the nodes it reads."""
        order: List[str] = []
        state: Dict[str, int] = {}

        def visit(nid: str) -> None:
            if state.get(nid) == 2 or nid not in self.nodes:
                return
            if state.get(nid) == 1:
                return  # a loop: the compiler reports it
            state[nid] = 1
            for dep in self.dependencies(nid):
                visit(dep)
            state[nid] = 2
            order.append(nid)

        visit(node_id)
        return order

    def dependencies(self, node_id: str) -> List[str]:
        """The nodes ``node_id`` reads from directly (wires, and the Set value of a Get value)."""
        deps = [l.src for l in self.links if l.dst == node_id]
        node = self.nodes.get(node_id)
        if node is not None and node.type == "get_var":
            name = node.params.get("name")
            deps.extend(n.id for n in self.nodes.values() if n.type == "set_var" and n.params.get("name") == name)
        return deps

    def output_type(self, node_id: str, port: str) -> str:
        """The type of an output, following what is connected (``T`` ports take their inputs' type)."""
        from .compiler import resolve_types

        return resolve_types(self).get(node_id, {}).get(port, "float")

    def input_type(self, node_id: str, port: str) -> str:
        """The type an input takes in the code (``T`` inputs take the node's resolved type)."""
        from .compiler import resolve_types

        return resolve_types(self).get(node_id, {}).get(f"in:{port}", "float")

    # -- output ------------------------------------------------------------------------
    @property
    def output_node(self) -> Optional[Node]:
        """The Output node (the first one, if there are several), or ``None``."""
        return next((n for n in self.nodes.values() if n.type == "output"), None)

    def output(self, color: Value = None, alpha: Value = None) -> NodeRef:
        """Connects ``color`` (and ``alpha``) to the Output node, adding it if the graph has none."""
        node = self.output_node
        ref = NodeRef(self, node.id) if node is not None else self.add("output")
        values: Dict[str, Value] = {}
        if color is not None:
            values["color"] = color
        if alpha is not None:
            values["alpha"] = alpha
        if values:
            self._apply(ref.id, (), values)
            ref.node.x, ref.node.y = self._place(ref.node)
        return ref

    # -- variables ----------------------------------------------------------------------
    def variable(self, name: str) -> Optional[Variable]:
        """The variable called ``name``, or ``None``."""
        return next((v for v in self.variables if v.name == name), None)

    def add_variable(self, name: str, type_: str = "float", value: Any = None, *, mutable: bool = True,
                     min: Optional[float] = None, max: Optional[float] = None,  # noqa: A002
                     step: Optional[float] = None, description: str = "") -> Variable:
        """Adds a variable to the shader (``mutable=False`` makes it a constant). Raises ``GraphError`` if the
        name is taken or not valid."""
        if not valid_name(name):
            raise GraphError(f"{name!r} can't name a variable (letters, digits and _, not a WGSL word)")
        if self.variable(name) is not None:
            raise GraphError(f"there is already a variable {name!r}")
        var = Variable(name, type_, value, mutable, min, max, step, description)
        self.variables.append(var)
        self.touch()
        return var

    def set_variable(self, name: str, /, **changes: Any) -> Variable:
        """Changes a variable: its ``value``, ``type``, ``mutable``, ``min``, ``max``, ``step``, ``description``
        or ``name`` (renaming updates the nodes that read it)."""
        var = self.variable(name)
        if var is None:
            raise GraphError(f"no variable {name!r}")
        if "name" in changes and changes["name"] != name:
            self.rename_variable(name, changes.pop("name"))
        changes.pop("name", None)
        if "type" in changes and changes["type"] != var.type:
            new = changes.pop("type")
            if new not in VAR_TYPES:
                raise GraphError(f"a variable's type is one of {', '.join(VAR_TYPES)}")
            old_value = var.value
            var.type = new
            try:
                var.value = normalize(old_value, new)
            except (TypeError, ValueError):
                var.value = normalize(None, new)
            if new == "texture":
                var.mutable = True
            for n in self.nodes.values():
                if n.type == "parameter" and n.params.get("name") == var.name:
                    self._prune(n)
        for key, value in changes.items():
            if key == "value":
                var.value = normalize(value, var.type)
            elif key == "mutable":
                var.mutable = bool(value) or var.type == "texture"
            elif key in ("min", "max", "step", "description"):
                setattr(var, key, value)
            else:
                raise GraphError(f"a variable has no {key!r}")
        self.touch()
        return var

    def rename_variable(self, old: str, new: str) -> None:
        """Renames a variable and every Parameter node that reads it."""
        var = self.variable(old)
        if var is None:
            raise GraphError(f"no variable {old!r}")
        if new == old:
            return
        if not valid_name(new):
            raise GraphError(f"{new!r} can't name a variable (letters, digits and _, not a WGSL word)")
        if self.variable(new) is not None:
            raise GraphError(f"there is already a variable {new!r}")
        var.name = new
        for n in self.nodes.values():
            if n.type == "parameter" and n.params.get("name") == old:
                n.params["name"] = new
        self.touch()

    def remove_variable(self, name: str) -> None:
        """Removes a variable and the Parameter nodes that read it."""
        self.variables = [v for v in self.variables if v.name != name]
        for n in [n for n in self.nodes.values() if n.type == "parameter" and n.params.get("name") == name]:
            self.remove(n.id)
        self.touch()

    def uniform(self, name: str, type_: str = "float", value: Any = None, **options: Any) -> NodeRef:
        """Adds a mutable variable (if there is none called ``name``) and a node that reads it."""
        if self.variable(name) is None:
            self.add_variable(name, type_, value, **options)
        return self.add("parameter", name=name)

    def constant(self, name: str, type_: str = "float", value: Any = None, **options: Any) -> NodeRef:
        """Adds a constant variable (if there is none called ``name``) and a node that reads it."""
        if self.variable(name) is None:
            self.add_variable(name, type_, value, mutable=False, **options)
        return self.add("parameter", name=name)

    def get(self, name: str) -> NodeRef:
        """A new node that reads the variable ``name``."""
        if self.variable(name) is None:
            raise GraphError(f"no variable {name!r}")
        return self.add("parameter", name=name)

    def locals(self) -> List[str]:
        """The names given by Set value nodes, in order."""
        out: List[str] = []
        for n in self.nodes.values():
            name = str(n.params.get("name", ""))
            if n.type == "set_var" and name and name not in out:
                out.append(name)
        return out

    def _local_type(self, name: str) -> str:
        setter = next((n for n in self.nodes.values() if n.type == "set_var" and n.params.get("name") == name), None)
        return self.output_type(setter.id, "value") if setter is not None else "float"

    def _subgraph(self, path: Any) -> Optional["Graph"]:
        """The graph of another ``.pzshad`` used by a Shader function node (``None`` if it can't be read)."""
        if not path:
            return None
        full = Path(str(path))
        if not full.is_absolute() and self.path is not None:
            full = self.path.parent / full
        key = str(full)
        try:
            mtime = full.stat().st_mtime
        except OSError:
            return None
        cached = self._subgraphs.get(key)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        try:
            sub: Optional[Graph] = load(full)
        except (OSError, ValueError, KeyError):
            sub = None
        self._subgraphs[key] = (mtime, sub)
        return sub

    # -- layout -------------------------------------------------------------------------------
    def arrange(self, spacing: Tuple[float, float] = (250.0, 30.0)) -> None:
        """Places the nodes in columns by how far they are from the inputs, left to right."""
        from .layout import arrange

        arrange(self, spacing)
        self.touch()

    # -- files --------------------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """The graph as the JSON data of a ``.pzshad`` file."""
        out: Dict[str, Any] = {"format": FORMAT, "name": self.name}
        if self.description:
            out["description"] = self.description
        out["preview"] = dict(self.preview)
        out["variables"] = [v.to_dict() for v in self.variables]
        out["nodes"] = [n.to_dict() for n in self.nodes.values()]
        out["links"] = [l.to_dict() for l in self.links]
        return out

    def to_json(self) -> str:
        """The text of the ``.pzshad`` file."""
        return json.dumps(self.to_dict(), indent=1, ensure_ascii=False) + "\n"

    @classmethod
    def from_dict(cls, data: Dict[str, Any], path: Optional[Union[str, Path]] = None) -> "Graph":
        """Builds a graph from ``.pzshad`` data (wires to ports that don't exist are dropped)."""
        if data.get("format", FORMAT).split("/")[0] != FORMAT.split("/")[0]:
            raise ValueError(f"not a Pyzed shader (format {data.get('format')!r})")
        g = cls(str(data.get("name", "shader")), description=str(data.get("description", "")))
        g.path = Path(path) if path else None
        g.preview.update(dict(data.get("preview") or {}))
        for v in data.get("variables") or []:
            try:
                g.variables.append(Variable.from_dict(v))
            except (KeyError, ValueError, TypeError):
                continue
        for n in data.get("nodes") or []:
            node = Node.from_dict(n)
            g.nodes[node.id] = node
        for raw in data.get("links") or []:
            try:
                link = Link.from_dict(raw)
            except KeyError:
                continue
            src, dst = g.nodes.get(link.src), g.nodes.get(link.dst)
            if src is None or dst is None or g.output_port(src, link.out) is None or g.input_port(dst, link.inp) is None:
                continue
            g.links = [l for l in g.links if not (l.dst == link.dst and l.inp == link.inp)]
            g.links.append(link)
        ids = [int(i) for i in g.nodes if i.isdigit()]
        g._next = max(ids, default=0) + 1
        return g

    @classmethod
    def from_json(cls, text: str, path: Optional[Union[str, Path]] = None) -> "Graph":
        return cls.from_dict(json.loads(text), path)

    def save(self, path: Optional[Union[str, Path]] = None) -> Path:
        """Writes the graph to ``path`` (``.pzshad`` is added when there is no suffix) or to its own file."""
        if path is not None:
            p = Path(path)
            self.path = p if p.suffix else p.with_suffix(SUFFIX)
        if self.path is None:
            raise ValueError("this shader has no file yet; pass a path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(self.to_json().encode("utf-8"))
        return self.path

    def copy(self) -> "Graph":
        """An independent copy of the graph."""
        g = Graph.from_dict(_copy.deepcopy(self.to_dict()), self.path)
        return g

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes.values())

    def __len__(self) -> int:
        return len(self.nodes)

    # -- compiling ---------------------------------------------------------------------------------
    def compile(self, target: Optional[Tuple[str, str]] = None, **options: Any):
        """The WGSL of the graph (or of one output, ``target=(node_id, port)``): see ``pyzed.shading.compile``."""
        from .compiler import compile as _compile

        return _compile(self, target, **options)

    @property
    def wgsl(self) -> str:
        """The generated WGSL code."""
        return self.compile().code


def _resolve_type(name: str) -> Tuple[str, Dict[str, Any]]:
    """A node type id, a sidebar entry's key (``"func:sin"``) or name (``"sin"``, ``"multiply"``,
    ``"value_noise"``), as ``(type, settings)``."""
    if name in _nodes.TYPES:
        return name, {}
    for p in _nodes.PRESETS:
        if p.key == name:
            return p.type, dict(p.params)
    key = name.lower().replace(" ", "_")
    if key in _nodes.BINARY:
        return "math", {"op": key}
    if key in _nodes.UNARY:
        return "func", {"op": key}
    for p in _nodes.PRESETS:
        if p.title.lower().replace(" ", "_") == key:
            return p.type, dict(p.params)
    raise KeyError(f"no node type {name!r}")


def _input_value(value: Any) -> Any:
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value  # a color or a context such as "@uv"
    if isinstance(value, (list, tuple)):
        return [float(v) for v in value]
    raise TypeError(f"an input takes a number, a tuple of numbers, a color or a port, not {type(value).__name__}")


def _param_value(param: _nodes.Param, value: Any) -> Any:
    kind = param.kind
    if kind == "enum":
        value = str(value)
        if param.options and value not in param.options:
            raise GraphError(f"{param.name} is one of {', '.join(param.options)}, not {value!r}")
        return value
    if kind in ("float", "int", "bool", "vec2", "vec3", "vec4"):
        return coerce(value, kind)
    if kind == "color":
        return normalize(value, "color")
    if kind == "stops":
        return [[float(p), normalize(c, "color")] for p, c in _nodes.gradient_stops(value)]
    return "" if value is None else str(value)


def load(path: Union[str, Path]) -> Graph:
    """Reads a ``.pzshad`` file."""
    path = Path(path)
    return Graph.from_json(path.read_text(encoding="utf-8"), path)


__all__ = ["FORMAT", "SUFFIX", "VAR_TYPES", "Graph", "GraphError", "Link", "Node", "NodeRef", "Socket", "Variable",
           "load", "valid_name", "SIZE", "TYPES", "GENERIC"]
