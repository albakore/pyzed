"""The node catalog: every kind of node a shader graph can hold, and the entries of the node sidebar.

A ``NodeType`` says which inputs, outputs and settings (``params``) a node has and how it
becomes WGSL: simple nodes give one template per output (``"mix({a}, {b}, {t})"``),
the others a ``build`` function. Inputs and outputs typed ``T`` take the widest type
among the ``T`` inputs (``float + vec3`` is a ``vec3``), as Godot's visual shaders do.

``PRESETS`` are the entries of the sidebar: a node type with some settings already
chosen (``Sin`` is the ``Function`` node with ``op="sin"``), so the sidebar lists many
useful functions without the graph format having one node type per function.

Add your own node type with ``register(NodeType(...))``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from . import library
from .types import BY_SIZE, GENERIC, SIZE, WGSL, convert, literal

if TYPE_CHECKING:  # pragma: no cover
    from .compiler import Build
    from .graph import Graph, Node

#: Input defaults that read the pixel being shaded instead of a constant.
CONTEXT = {
    "@uv": ("vec2", "uv", ()),
    "@px": ("vec2", "px", ()),
    "@size": ("vec2", "size", ()),
    "@time": ("float", "time", ()),
    "@mouse": ("vec2", "pzs_mouse()", ("pzs_mouse",)),
    "@centered": ("vec2", "pzs_centered(uv, size)", ("pzs_centered",)),
    "@aspect": ("vec2", "(uv * vec2<f32>(size.x / max(size.y, 1.0), 1.0))", ()),
}
#: How an unconnected input with a context default is labelled on its node.
CONTEXT_LABELS = {"@uv": "UV", "@px": "Pixel", "@size": "Size", "@time": "Time", "@mouse": "Mouse",
                  "@centered": "Centered", "@aspect": "Aspect UV"}

#: The sidebar's categories, in order, with their icon and color.
CATEGORIES: Dict[str, Tuple[str, str]] = {
    "Input": ("log-in", "#60a5fa"),
    "Parameters": ("sliders-horizontal", "#f59e0b"),
    "Constants": ("hash", "#94a3b8"),
    "Math": ("calculator", "#34d399"),
    "Vector": ("move-3d", "#a78bfa"),
    "UV": ("scan", "#22d3ee"),
    "Noise": ("waves", "#f472b6"),
    "Patterns": ("grid-3x3", "#fb7185"),
    "Shapes": ("shapes", "#facc15"),
    "Color": ("palette", "#f97316"),
    "Effects": ("sparkles", "#e879f9"),
    "Texture": ("image", "#fbbf24"),
    "Logic": ("git-branch", "#f472b6"),
    "Variables": ("variable", "#38bdf8"),
    "Utility": ("wrench", "#9ca3af"),
    "Output": ("monitor", "#ef4444"),
}


@dataclass(frozen=True)
class Input:
    """An input port. ``default`` is the value it takes while nothing is connected (a number, a
    tuple, a ``"#rrggbb"`` color, or a context such as ``"@uv"``)."""

    name: str
    type: str
    default: Any = None
    label: str = ""
    #: How to edit the value: ``"color"``, ``"angle"``, ``"range:0:1"``...
    hint: str = ""

    @property
    def title(self) -> str:
        """What the port is called on the node."""
        return self.label or self.name.replace("_", " ")


@dataclass(frozen=True)
class Output:
    """An output port. ``hint="sdf"`` previews the value as a signed distance (inside white)."""

    name: str
    type: str
    label: str = ""
    hint: str = ""

    @property
    def title(self) -> str:
        """What the port is called on the node."""
        return self.label or self.name.replace("_", " ")


@dataclass(frozen=True)
class Param:
    """A setting of a node that is not a port: an operation, a mode, a text, a value of a constant.

    ``kind`` is ``"enum"`` (one of ``options``), ``"float"``, ``"int"``, ``"bool"``, ``"text"``,
    ``"code"``, ``"color"``, ``"vec2"``/``"vec3"``/``"vec4"``, ``"stops"`` (a gradient),
    ``"variable"`` (a variable of the graph) or ``"file"`` (another ``.pzshad``).
    """

    name: str
    kind: str
    default: Any = None
    options: Tuple[str, ...] = ()
    label: str = ""

    @property
    def title(self) -> str:
        """What the setting is called in the properties panel."""
        return self.label or self.name.replace("_", " ").capitalize()


Ports = Tuple[Tuple[Input, ...], Tuple[Output, ...]]


@dataclass(frozen=True)
class NodeType:
    """A kind of node: its ports, settings, and how it becomes WGSL."""

    id: str
    title: str
    category: str
    description: str
    inputs: Tuple[Input, ...] = ()
    outputs: Tuple[Output, ...] = ()
    params: Tuple[Param, ...] = ()
    #: One WGSL template per output: ``{name}`` is an input, ``{self}`` the node's variable prefix,
    #: ``{p_name}`` a setting.
    exprs: Mapping[str, str] = field(default_factory=dict)
    #: Library functions (``library.FUNCTIONS``) the templates call.
    functions: Tuple[str, ...] = ()
    #: The smallest type ``T`` resolves to (``"float"`` for functions like ``sin``).
    min_type: str = "bool"
    #: Builds the node when templates are not enough: ``build(ctx) -> None`` fills ``ctx``.
    build: Optional[Callable[["Build"], None]] = None
    #: The ports of one node, for nodes whose ports depend on their settings or on the graph.
    ports: Optional[Callable[["Node", "Graph"], Ports]] = None
    #: The type of each output, for outputs that depend on settings: ``(node, graph, T) -> {output: type}``.
    resolve: Optional[Callable[["Node", "Graph", str], Dict[str, str]]] = None
    #: How the title of a node reads (``"Sin"`` for the Function node with ``op="sin"``).
    label: Optional[Callable[["Node", "Graph"], str]] = None
    icon: str = ""
    #: Words the sidebar's search also matches.
    keywords: str = ""

    def param(self, name: str) -> Optional[Param]:
        """The setting called ``name``, or ``None``."""
        return next((p for p in self.params if p.name == name), None)


@dataclass(frozen=True)
class Preset:
    """An entry of the node sidebar: ``type`` with ``params`` already set."""

    type: str
    title: str
    category: str
    description: str
    params: Mapping[str, Any] = field(default_factory=dict)
    keywords: str = ""

    @property
    def key(self) -> str:
        """A unique id for the entry (``func:sin``)."""
        if not self.params:
            return self.type
        return self.type + ":" + ",".join(f"{v}" for v in self.params.values())


#: Every node type, by id.
TYPES: Dict[str, NodeType] = {}
#: The entries of the node sidebar, in order.
PRESETS: List[Preset] = []


def register(node_type: NodeType, *, preset: bool = True) -> NodeType:
    """Adds ``node_type`` to the catalog (and, with ``preset``, to the sidebar)."""
    TYPES[node_type.id] = node_type
    if preset:
        PRESETS.append(Preset(node_type.id, node_type.title, node_type.category, node_type.description,
                              keywords=node_type.keywords))
    return node_type


def preset(type_: str, title: str, description: str, keywords: str = "", category: Optional[str] = None,
           **params: Any) -> None:
    """Adds a sidebar entry for ``type_`` with ``params`` set."""
    PRESETS.append(Preset(type_, title, category or TYPES[type_].category, description, params, keywords))


def get(type_: str) -> NodeType:
    """The node type ``type_`` (raises ``KeyError`` with the known ones when it doesn't exist)."""
    try:
        return TYPES[type_]
    except KeyError:
        raise KeyError(f"no node type {type_!r}; see pyzed.shading.nodes.TYPES") from None


def search(text: str = "", category: Optional[str] = None) -> List[Preset]:
    """The sidebar entries whose title, category, description or keywords contain every word of ``text``."""
    words = text.lower().split()
    out = []
    for p in PRESETS:
        if category and p.category != category:
            continue
        hay = f"{p.title} {p.category} {p.description} {p.keywords} {p.type}".lower()
        if all(w in hay for w in words):
            out.append(p)
    return out


# -- helpers to declare nodes ---------------------------------------------------------


def _in(name: str, type_: str, default: Any = None, label: str = "", hint: str = "") -> Input:
    return Input(name, type_, default, label, hint)


def _out(name: str, type_: str, label: str = "", hint: str = "") -> Output:
    return Output(name, type_, label, hint)


def _enum(name: str, options: Sequence[str], default: Optional[str] = None, label: str = "") -> Param:
    return Param(name, "enum", default or options[0], tuple(options), label)


def _node(id_: str, title: str, category: str, description: str, inputs: Sequence[Input] = (),
          outputs: Sequence[Output] = (), *, preset: bool = True, **kwargs: Any) -> NodeType:
    return register(NodeType(id_, title, category, description, tuple(inputs), tuple(outputs), **kwargs),
                    preset=preset)


def _op_label(options: Mapping[str, Tuple[str, ...]]) -> Callable[["Node", "Graph"], str]:
    def label(node: "Node", graph: "Graph") -> str:
        op = node.params.get("op")
        return options[op][0] if op in options else node.type

    return label


# -- Input ------------------------------------------------------------------------------

_node("uv", "UV", "Input", "Where the pixel is, from (0, 0) at the top left to (1, 1) at the bottom right.",
      outputs=[_out("uv", "vec2"), _out("x", "float"), _out("y", "float")],
      exprs={"uv": "uv", "x": "uv.x", "y": "uv.y"}, icon="scan", keywords="coordinates texcoord")
_node("pixel", "Pixel", "Input", "Where the pixel is, in pixels from the top left.",
      outputs=[_out("px", "vec2", "pixel"), _out("x", "float"), _out("y", "float")],
      exprs={"px": "px", "x": "px.x", "y": "px.y"}, keywords="fragcoord position screen")
_node("size", "Size", "Input", "The size of the shaded area in pixels, and its aspect ratio (width / height).",
      outputs=[_out("size", "vec2"), _out("width", "float"), _out("height", "float"), _out("aspect", "float")],
      exprs={"size": "size", "width": "size.x", "height": "size.y", "aspect": "(size.x / max(size.y, 1.0))"},
      keywords="resolution dimensions ratio")
_node("time", "Time", "Input", "Seconds since the app started (times scale), and their sine and cosine.",
      [_in("scale", "float", 1.0)],
      [_out("time", "float"), _out("sin", "float"), _out("cos", "float")],
      exprs={"time": "(time * {scale})", "sin": "sin(time * {scale})", "cos": "cos(time * {scale})"},
      icon="clock", keywords="animate seconds clock")
_node("mouse", "Mouse", "Input", "Where the pointer is from 0 to 1 (the center while it is outside), "
      "and whether it is over the shader.",
      outputs=[_out("position", "vec2"), _out("inside", "bool")],
      exprs={"position": "pzs_mouse()", "inside": "(mouse().x >= 0.0)"}, functions=("pzs_mouse",),
      icon="mouse-pointer", keywords="pointer cursor hover")
_node("centered_uv", "Centered UV", "Input",
      "UV with (0, 0) in the middle and circles kept round: the place to draw shapes. "
      "Aspect UV goes from 0 to the aspect ratio across, so noise and cells stay square.",
      [_in("uv", "vec2", "@uv")],
      [_out("centered", "vec2"), _out("aspect_uv", "vec2", "aspect uv")],
      exprs={"centered": "pzs_centered({uv}, size)", "aspect_uv": "({uv} * vec2<f32>(size.x / max(size.y, 1.0), 1.0))"},
      functions=("pzs_centered",), keywords="center aspect square")


# -- Constants --------------------------------------------------------------------------


def _constant(id_: str, title: str, type_: str, default: Any, kind: Optional[str] = None,
              description: str = "") -> None:
    kind = kind or type_

    def build(ctx: "Build") -> None:
        value = ctx.params.get("value", default)
        if kind == "color":
            v = literal(value, "vec4")
            ctx.out("color", v)
            ctx.out("rgb", f"({v}).xyz")
            ctx.out("alpha", f"({v}).w")
        else:
            ctx.out("value", literal(value, type_))

    outputs = ([_out("color", "vec4"), _out("rgb", "vec3"), _out("alpha", "float")] if kind == "color"
               else [_out("value", type_)])
    _node(id_, title, "Constants", description or f"A fixed {title.lower()}.", outputs=outputs,
          params=(Param("value", kind, default),), build=build, keywords="constant value number literal")


_constant("float", "Float", "float", 0.5, description="A fixed number.")
_constant("int", "Int", "int", 1, description="A fixed whole number.")
_constant("bool", "Bool", "bool", True, description="A fixed true or false.")
_constant("vec2", "Vector2", "vec2", [0.5, 0.5], description="Two fixed numbers.")
_constant("vec3", "Vector3", "vec3", [1.0, 1.0, 1.0], description="Three fixed numbers.")
_constant("vec4", "Vector4", "vec4", [1.0, 1.0, 1.0, 1.0], description="Four fixed numbers.")
_constant("color", "Color", "vec4", "#7c3aed", kind="color", description="A fixed color.")
_node("math_constants", "Math constants", "Constants", "π, τ (2π), e and the golden ratio.",
      outputs=[_out("pi", "float", "π"), _out("tau", "float", "τ"), _out("e", "float"), _out("phi", "float", "φ")],
      exprs={"pi": "3.14159265", "tau": "6.28318531", "e": "2.71828183", "phi": "1.61803399"},
      keywords="pi tau euler golden")


# -- Math ---------------------------------------------------------------------------------

#: The operations of the Math node: (title, float template, int template or None, symbol).
BINARY: Dict[str, Tuple[str, str, Optional[str], str]] = {
    "add": ("Add", "({a} + {b})", "({a} + {b})", "+"),
    "subtract": ("Subtract", "({a} - {b})", "({a} - {b})", "−"),
    "multiply": ("Multiply", "({a} * {b})", "({a} * {b})", "×"),
    "divide": ("Divide", "({a} / {b})", "({a} / {b})", "÷"),
    "modulo": ("Modulo", "({a} - {b} * floor({a} / {b}))", "({a} % {b})", "mod"),
    "power": ("Power", "pow({a}, {b})", None, "^"),
    "min": ("Min", "min({a}, {b})", "min({a}, {b})", "min"),
    "max": ("Max", "max({a}, {b})", "max({a}, {b})", "max"),
    "step": ("Step", "step({a}, {b})", None, "step"),
    "atan2": ("Atan2", "atan2({a}, {b})", None, "atan2"),
    "snap": ("Snap", "(floor({a} / {b} + 0.5) * {b})", None, "snap"),
}
_BINARY_HELP = {
    "add": "a + b", "subtract": "a − b", "multiply": "a × b", "divide": "a ÷ b",
    "modulo": "The remainder of a ÷ b (always the sign of b).", "power": "a to the power of b.",
    "min": "The smaller of a and b.", "max": "The larger of a and b.",
    "step": "0 where b is below the edge a, 1 from there on.",
    "atan2": "The angle of the point (b, a) in radians: a is y, b is x.",
    "snap": "a rounded to the nearest multiple of b.",
}


def _build_math(ctx: "Build") -> None:
    op = ctx.params.get("op", "add")
    title, float_tpl, int_tpl, _symbol = BINARY.get(op, BINARY["add"])
    template = int_tpl if ctx.t == "int" and int_tpl else float_tpl
    ctx.out("result", ctx.format(template))


def _math_resolve(node: "Node", graph: "Graph", t: str) -> Dict[str, str]:
    op = node.params.get("op", "add")
    if t in ("int", "bool") and (t == "bool" or BINARY.get(op, BINARY["add"])[2] is None):
        t = "float"
    return {"result": t}


_node("math", "Math", "Math", "An arithmetic operation on two values (of any type: vectors work per component).",
      [_in("a", GENERIC, 0.0), _in("b", GENERIC, 1.0)], [_out("result", GENERIC)],
      params=(_enum("op", list(BINARY)),), build=_build_math, resolve=_math_resolve, min_type="int",
      label=lambda n, g: BINARY.get(n.params.get("op", "add"), BINARY["add"])[0], preset=False, icon="plus")
for _op, (_title, _f, _i, _sym) in BINARY.items():
    preset("math", _title, _BINARY_HELP[_op], f"{_sym} operator arithmetic", op=_op)

#: The operations of the Function node: (title, template, description).
UNARY: Dict[str, Tuple[str, str, str]] = {
    "abs": ("Abs", "abs({x})", "x without its sign."),
    "negate": ("Negate", "(-{x})", "−x"),
    "sign": ("Sign", "sign({x})", "−1, 0 or 1: the sign of x."),
    "floor": ("Floor", "floor({x})", "x rounded down."),
    "ceil": ("Ceil", "ceil({x})", "x rounded up."),
    "round": ("Round", "round({x})", "x rounded to the nearest whole number."),
    "fract": ("Fract", "fract({x})", "What is after the point: x − floor(x). Repeats every 1."),
    "trunc": ("Trunc", "trunc({x})", "x without what is after the point."),
    "sqrt": ("Sqrt", "sqrt({x})", "The square root of x."),
    "inverse_sqrt": ("Inverse sqrt", "inverseSqrt({x})", "1 / √x"),
    "square": ("Square", "({x} * {x})", "x × x"),
    "exp": ("Exp", "exp({x})", "e to the power of x."),
    "exp2": ("Exp2", "exp2({x})", "2 to the power of x."),
    "log": ("Log", "log({x})", "The natural logarithm of x."),
    "log2": ("Log2", "log2({x})", "The base 2 logarithm of x."),
    "sin": ("Sin", "sin({x})", "The sine of x (radians)."),
    "cos": ("Cos", "cos({x})", "The cosine of x (radians)."),
    "tan": ("Tan", "tan({x})", "The tangent of x (radians)."),
    "asin": ("Asin", "asin({x})", "The arc sine of x, in radians."),
    "acos": ("Acos", "acos({x})", "The arc cosine of x, in radians."),
    "atan": ("Atan", "atan({x})", "The arc tangent of x, in radians."),
    "sinh": ("Sinh", "sinh({x})", "The hyperbolic sine of x."),
    "cosh": ("Cosh", "cosh({x})", "The hyperbolic cosine of x."),
    "tanh": ("Tanh", "tanh({x})", "The hyperbolic tangent of x: an S curve from −1 to 1."),
    "one_minus": ("One minus", "(1.0 - {x})", "1 − x: turns 0..1 around."),
    "reciprocal": ("Reciprocal", "(1.0 / {x})", "1 / x"),
    "saturate": ("Saturate", "saturate({x})", "x kept between 0 and 1."),
    "degrees": ("Degrees", "degrees({x})", "Radians to degrees."),
    "radians": ("Radians", "radians({x})", "Degrees to radians."),
}


def _build_func(ctx: "Build") -> None:
    op = ctx.params.get("op", "sin")
    ctx.out("result", ctx.format(UNARY.get(op, UNARY["sin"])[1]))


_node("func", "Function", "Math", "A function of one value (vectors work per component).",
      [_in("x", GENERIC, 0.0)], [_out("result", GENERIC)], params=(_enum("op", list(UNARY), "sin"),),
      build=_build_func, min_type="float", label=lambda n, g: UNARY.get(n.params.get("op", "sin"), UNARY["sin"])[0],
      preset=False, icon="function-square")
for _op, (_title, _tpl, _help) in UNARY.items():
    preset("func", _title, _help, "function trigonometry", op=_op)

_node("mix", "Mix", "Math", "Blends from a (t = 0) to b (t = 1): a lerp.",
      [_in("a", GENERIC, 0.0), _in("b", GENERIC, 1.0), _in("t", GENERIC, 0.5, hint="range:0:1")],
      [_out("result", GENERIC)], exprs={"result": "mix({a}, {b}, {t})"}, min_type="float",
      keywords="lerp interpolate blend")
_node("clamp", "Clamp", "Math", "x kept between min and max.",
      [_in("x", GENERIC, 0.0), _in("min", GENERIC, 0.0), _in("max", GENERIC, 1.0)], [_out("result", GENERIC)],
      exprs={"result": "clamp({x}, {min}, {max})"}, min_type="float", keywords="limit range")
_node("smoothstep", "Smoothstep", "Math", "0 below edge0, 1 above edge1 and a smooth curve between them.",
      [_in("edge0", GENERIC, 0.0), _in("edge1", GENERIC, 1.0), _in("x", GENERIC, 0.5)], [_out("result", GENERIC)],
      exprs={"result": "smoothstep({edge0}, {edge1}, {x})"}, min_type="float", keywords="smooth threshold ease")
_node("remap", "Remap", "Math", "x moved from the range in_min..in_max to out_min..out_max.",
      [_in("x", GENERIC, 0.5), _in("in_min", GENERIC, 0.0), _in("in_max", GENERIC, 1.0),
       _in("out_min", GENERIC, -1.0), _in("out_max", GENERIC, 1.0)], [_out("result", GENERIC)],
      exprs={"result": "({out_min} + ({x} - {in_min}) * ({out_max} - {out_min}) / ({in_max} - {in_min}))"},
      min_type="float", keywords="map range scale fit")
_node("multiply_add", "Multiply add", "Math", "a × b + c",
      [_in("a", GENERIC, 1.0), _in("b", GENERIC, 1.0), _in("c", GENERIC, 0.0)], [_out("result", GENERIC)],
      exprs={"result": "({a} * {b} + {c})"}, min_type="float", keywords="fma mad")


# -- Vector --------------------------------------------------------------------------------


def _compose_ports(node: "Node", graph: "Graph") -> Ports:
    n = SIZE.get(node.params.get("type", "vec3"), 3)
    names = "xyzw"[:n]
    defaults = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
    return (tuple(_in(c, "float", defaults[c]) for c in names), (_out("vector", BY_SIZE[n]),))


def _build_compose(ctx: "Build") -> None:
    n = SIZE.get(ctx.params.get("type", "vec3"), 3)
    ctx.out("vector", f"{WGSL[BY_SIZE[n]]}({', '.join(ctx.inputs[c] for c in 'xyzw'[:n])})")


_node("compose", "Compose", "Vector", "Builds a vector from its components.",
      [_in("x", "float", 0.0), _in("y", "float", 0.0), _in("z", "float", 0.0)], [_out("vector", "vec3")],
      params=(_enum("type", ["vec2", "vec3", "vec4"], "vec3"),), build=_build_compose, ports=_compose_ports,
      label=lambda n, g: f"Compose {n.params.get('type', 'vec3')}", keywords="combine make vector join")
preset("compose", "Compose vec2", "Builds a vec2 from x and y.", "combine make", type="vec2")
preset("compose", "Compose vec4", "Builds a vec4 from x, y, z and w.", "combine make rgba", type="vec4")


def _build_decompose(ctx: "Build") -> None:
    t = ctx.types["vector"]
    n = SIZE.get(t, 1)
    v = ctx.inputs["vector"]
    for i, c in enumerate("xyzw"):
        if n == 1:
            ctx.out(c, v if i == 0 else "0.0")
        else:
            ctx.out(c, f"({v}).{c}" if i < n else ("1.0" if c == "w" else "0.0"))


_node("decompose", "Decompose", "Vector", "The components of a vector (x, y, z and w; r, g, b and a for colors).",
      [_in("vector", GENERIC, [0.0, 0.0, 0.0, 1.0])],
      [_out("x", "float"), _out("y", "float"), _out("z", "float"), _out("w", "float")],
      build=_build_decompose, min_type="float", keywords="split separate components rgba channels")


def _swizzle_mask(node: "Node") -> str:
    mask = str(node.params.get("mask", "xy")).lower().strip()
    mask = mask.translate(str.maketrans("rgba", "xyzw"))
    mask = "".join(c for c in mask if c in "xyzw")[:4]
    return mask or "x"


def _build_swizzle(ctx: "Build") -> None:
    mask = _swizzle_mask(ctx.node)
    v = convert(ctx.inputs["vector"], ctx.types["vector"], "vec4")
    ctx.out("result", f"({v}).{mask}")


_node("swizzle", "Swizzle", "Vector", "Picks and reorders components: “yx”, “zzz”, “rgb”, “x”…",
      [_in("vector", GENERIC, [0.0, 0.0, 0.0, 1.0])], [_out("result", "vec2")],
      params=(Param("mask", "text", "yx"),), build=_build_swizzle,
      resolve=lambda n, g, t: {"result": BY_SIZE[len(_swizzle_mask(n))]},
      label=lambda n, g: f"Swizzle .{_swizzle_mask(n)}", min_type="float", keywords="components reorder channels")


def _build_dot(ctx: "Build") -> None:
    a, b = ctx.inputs["a"], ctx.inputs["b"]
    ctx.out("result", f"({a} * {b})" if ctx.t == "float" else f"dot({a}, {b})")


_node("dot", "Dot", "Vector", "The dot product of a and b: how much they point the same way.",
      [_in("a", GENERIC, [1.0, 0.0]), _in("b", GENERIC, [1.0, 0.0])], [_out("result", "float")],
      build=_build_dot, min_type="float", keywords="product")
_node("cross", "Cross", "Vector", "The cross product of two vec3.",
      [_in("a", "vec3", [1.0, 0.0, 0.0]), _in("b", "vec3", [0.0, 1.0, 0.0])], [_out("result", "vec3")],
      exprs={"result": "cross({a}, {b})"}, keywords="product")
_node("length", "Length", "Vector", "How long a vector is.", [_in("vector", GENERIC, [1.0, 1.0])],
      [_out("length", "float")], exprs={"length": "length({vector})"}, min_type="float",
      keywords="magnitude norm size")
_node("distance", "Distance", "Vector", "How far apart a and b are.",
      [_in("a", GENERIC, "@uv"), _in("b", GENERIC, [0.5, 0.5])], [_out("distance", "float")],
      exprs={"distance": "distance({a}, {b})"}, min_type="float", keywords="length between")
_node("normalize", "Normalize", "Vector", "The vector made 1 long.", [_in("vector", GENERIC, [1.0, 1.0])],
      [_out("result", GENERIC)], exprs={"result": "normalize({vector})"}, min_type="vec2", keywords="unit direction")
_node("reflect", "Reflect", "Vector", "The direction i bounced off a surface facing n.",
      [_in("i", GENERIC, [1.0, -1.0]), _in("n", GENERIC, [0.0, 1.0])], [_out("result", GENERIC)],
      exprs={"result": "reflect({i}, {n})"}, min_type="vec2", keywords="bounce mirror")
_node("polar", "Polar", "Vector", "The distance and angle of the pixel around center (aspect kept): "
      "angle in radians (−π..π) and from 0 to 1.",
      [_in("uv", "vec2", "@uv"), _in("center", "vec2", [0.5, 0.5])],
      [_out("radius", "float"), _out("angle", "float"), _out("angle01", "float", "angle 0..1"),
       _out("polar", "vec2")],
      exprs={"radius": "length({self}_d)", "angle": "atan2({self}_d.y, {self}_d.x)",
             "angle01": "(atan2({self}_d.y, {self}_d.x) / 6.28318531 + 0.5)",
             "polar": "vec2<f32>(length({self}_d), atan2({self}_d.y, {self}_d.x) / 6.28318531 + 0.5)"},
      build=None, keywords="radial angle radius circular coordinates")


def _build_polar(ctx: "Build") -> None:
    ctx.line(f"let {ctx.var}_d = ({ctx.inputs['uv']} - {ctx.inputs['center']}) * "
             "vec2<f32>(size.x / max(size.y, 1.0), 1.0);")
    for name, tpl in TYPES["polar"].exprs.items():
        ctx.out(name, ctx.format(tpl))


TYPES["polar"] = NodeType(**{**TYPES["polar"].__dict__, "build": _build_polar})


# -- UV -----------------------------------------------------------------------------------------

_node("tiling_offset", "Tiling and offset", "UV", "uv × tiling + offset: repeats and moves what uses it.",
      [_in("uv", "vec2", "@uv"), _in("tiling", "vec2", [2.0, 2.0]), _in("offset", "vec2", [0.0, 0.0])],
      [_out("uv", "vec2")], exprs={"uv": "({uv} * {tiling} + {offset})"}, keywords="tile repeat scale move")
_node("scroll", "Scroll", "UV", "Moves uv over time: uv + speed × time.",
      [_in("uv", "vec2", "@uv"), _in("speed", "vec2", [0.1, 0.0]), _in("time", "float", "@time")],
      [_out("uv", "vec2")], exprs={"uv": "({uv} + {speed} * {time})"}, keywords="pan move animate scroll")
_node("rotate", "Rotate", "UV", "Turns uv around center by angle (radians).",
      [_in("uv", "vec2", "@uv"), _in("center", "vec2", [0.5, 0.5]), _in("angle", "float", 0.5, hint="angle")],
      [_out("uv", "vec2")], exprs={"uv": "pzs_rotate({uv}, {center}, {angle})"}, functions=("pzs_rotate",),
      keywords="spin turn angle")
_node("twirl", "Twirl", "UV", "Twists uv around center, more the farther away.",
      [_in("uv", "vec2", "@uv"), _in("center", "vec2", [0.5, 0.5]), _in("strength", "float", 6.0)],
      [_out("uv", "vec2")], exprs={"uv": "pzs_twirl({uv}, {center}, {strength})"}, functions=("pzs_twirl",),
      keywords="swirl twist vortex")
_node("pixelate", "Pixelate", "UV", "Snaps uv to a grid of cells, for a pixel-art look.",
      [_in("uv", "vec2", "@uv"), _in("cells", "vec2", [48.0, 32.0])], [_out("uv", "vec2")],
      exprs={"uv": "((floor({uv} * {cells}) + 0.5) / {cells})"}, keywords="mosaic pixel retro blocks")
_node("barrel", "Barrel", "UV", "Bends uv like a curved CRT screen; inside is 0 where the bent uv leaves the screen.",
      [_in("uv", "vec2", "@uv"), _in("amount", "float", 0.25)], [_out("uv", "vec2"), _out("inside", "float")],
      exprs={"uv": "pzs_barrel({uv}, {amount})",
             "inside": "(step(0.0, pzs_barrel({uv}, {amount}).x) * step(pzs_barrel({uv}, {amount}).x, 1.0) * "
                       "step(0.0, pzs_barrel({uv}, {amount}).y) * step(pzs_barrel({uv}, {amount}).y, 1.0))"},
      functions=("pzs_barrel",), keywords="crt curve fisheye distort lens")
_node("kaleidoscope", "Kaleidoscope", "UV", "Mirrors uv around center into segments.",
      [_in("uv", "vec2", "@uv"), _in("center", "vec2", [0.5, 0.5]), _in("segments", "float", 6.0)],
      [_out("uv", "vec2")], exprs={"uv": "pzs_kaleidoscope({uv}, {center}, {segments})"},
      functions=("pzs_kaleidoscope",), keywords="mirror symmetry")
_node("flip", "Flip", "UV", "Mirrors uv horizontally, vertically or both.", [_in("uv", "vec2", "@uv")],
      [_out("uv", "vec2")], params=(_enum("axis", ["x", "y", "both"]),),
      build=lambda ctx: ctx.out("uv", {"x": f"vec2<f32>(1.0 - ({ctx.inputs['uv']}).x, ({ctx.inputs['uv']}).y)",
                                       "y": f"vec2<f32>(({ctx.inputs['uv']}).x, 1.0 - ({ctx.inputs['uv']}).y)",
                                       "both": f"(1.0 - {ctx.inputs['uv']})"}[
          ctx.params.get("axis", "x") if ctx.params.get("axis", "x") in ("x", "y", "both") else "x"]),
      keywords="mirror invert")
_node("repeat", "Repeat", "UV", "Repeats space in cells around (0, 0): draw one shape, get a grid of them. "
      "Cell is which cell the pixel is in.",
      [_in("p", "vec2", "@centered"), _in("cell", "vec2", [0.25, 0.25])], [_out("p", "vec2"), _out("cell", "vec2")],
      exprs={"p": "({p} - {cell} * round({p} / {cell}))", "cell": "round({p} / {cell})"},
      keywords="tile domain repetition grid")


# -- Noise ------------------------------------------------------------------------------------------

NOISES = ("value", "perlin", "simplex")


def _build_noise(ctx: "Build") -> None:
    kind = ctx.params.get("kind", "perlin")
    kind = kind if kind in NOISES else "perlin"
    ctx.use(f"pzs_{kind}_noise")
    ctx.out("value", f"pzs_{kind}_noise({ctx.inputs['p']} * {ctx.inputs['scale']})")


_node("noise", "Noise", "Noise", "Smooth random values from 0 to 1 (value, Perlin or simplex noise).",
      [_in("p", "vec2", "@aspect"), _in("scale", "float", 8.0)], [_out("value", "float")],
      params=(_enum("kind", NOISES, "perlin"),), build=_build_noise,
      label=lambda n, g: f"{str(n.params.get('kind', 'perlin')).capitalize()} noise", keywords="random perlin simplex")
preset("noise", "Value noise", "Blocky smooth noise from 0 to 1.", "random", kind="value")
preset("noise", "Simplex noise", "Simplex noise from 0 to 1.", "random", kind="simplex")


def _build_fbm(ctx: "Build") -> None:
    kind = ctx.params.get("kind", "value")
    kind = kind if kind in NOISES else "value"
    ctx.use(f"pzs_fbm_{kind}")
    i = ctx.inputs
    ctx.out("value", f"pzs_fbm_{kind}({i['p']} * {i['scale']}, {i['octaves']}, {i['lacunarity']}, {i['gain']})")


_node("fbm", "Fractal noise", "Noise", "Layers of noise, each finer and fainter (fBm): clouds, smoke, fire, terrain.",
      [_in("p", "vec2", "@aspect"), _in("scale", "float", 4.0), _in("octaves", "int", 5),
       _in("lacunarity", "float", 2.0), _in("gain", "float", 0.5)], [_out("value", "float")],
      params=(_enum("kind", NOISES, "value"),), build=_build_fbm, keywords="fbm clouds smoke turbulence octaves")


def _build_voronoi(ctx: "Build") -> None:
    i = ctx.inputs
    ctx.use("pzs_voronoi")
    ctx.line(f"let {ctx.var}_v = pzs_voronoi({i['p']} * {i['scale']}, {i['jitter']}, {i['phase']});")
    v = f"{ctx.var}_v"
    ctx.out("distance", f"{v}.x")
    ctx.out("second", f"{v}.y")
    ctx.out("edge", f"{v}.w")
    ctx.out("cell", f"{v}.z")


_node("voronoi", "Voronoi", "Noise", "Cells around random points: the distance to the nearest point and the "
      "second nearest, to the nearest edge, and a random number per cell. Phase moves the points.",
      [_in("p", "vec2", "@aspect"), _in("scale", "float", 6.0), _in("jitter", "float", 1.0, hint="range:0:1"),
       _in("phase", "float", "@time")],
      [_out("distance", "float"), _out("second", "float"), _out("edge", "float"), _out("cell", "float")],
      build=_build_voronoi, keywords="cells worley cellular crystals")
_node("white_noise", "White noise", "Noise", "A different random number from 0 to 1 for every value of p.",
      [_in("p", "vec2", "@px")], [_out("value", "float"), _out("random2", "vec2")],
      exprs={"value": "pzs_hash21({p})", "random2": "pzs_hash22({p})"}, functions=("pzs_hash21", "pzs_hash22"),
      keywords="random hash static grain")
_node("random", "Random", "Noise", "A random number from 0 to 1 for a seed (the same seed, the same number).",
      [_in("seed", "float", 1.0)], [_out("value", "float")], exprs={"value": "pzs_hash11({seed})"},
      functions=("pzs_hash11",), keywords="hash seed")


# -- Patterns ----------------------------------------------------------------------------------------

_node("checker", "Checker", "Patterns", "A checkerboard of 0 and 1.",
      [_in("uv", "vec2", "@aspect"), _in("cells", "vec2", [8.0, 8.0])], [_out("value", "float")],
      exprs={"value": "(fract((floor(({uv}).x * ({cells}).x) + floor(({uv}).y * ({cells}).y)) * 0.5) * 2.0)"},
      keywords="checkerboard chess tiles")
_node("stripes", "Stripes", "Patterns", "Parallel stripes of 0 and 1 (angle in radians, width from 0 to 1).",
      [_in("uv", "vec2", "@uv"), _in("count", "float", 10.0), _in("angle", "float", 0.0, hint="angle"),
       _in("width", "float", 0.5, hint="range:0:1")], [_out("value", "float")],
      exprs={"value": "step(fract(dot({uv}, vec2<f32>(cos({angle}), sin({angle}))) * {count}), {width})"},
      keywords="lines bars")
_node("grid", "Grid", "Patterns", "Grid lines: 1 on the lines, 0 between them (thickness from 0 to 1 of a cell).",
      [_in("uv", "vec2", "@aspect"), _in("cells", "vec2", [8.0, 8.0]), _in("thickness", "float", 0.06)],
      [_out("value", "float")],
      exprs={"value": "(1.0 - step({thickness} * 0.5, min(min(fract(({uv}).x * ({cells}).x), 1.0 - fract(({uv}).x * "
                      "({cells}).x)), min(fract(({uv}).y * ({cells}).y), 1.0 - fract(({uv}).y * ({cells}).y)))))"},
      keywords="lines tiles graph")
_node("dots", "Dots", "Patterns", "A grid of round dots: 1 inside, 0 outside (radius from 0 to 0.5 of a cell).",
      [_in("uv", "vec2", "@aspect"), _in("cells", "vec2", [10.0, 10.0]), _in("radius", "float", 0.3)],
      [_out("value", "float")],
      exprs={"value": "(1.0 - step({radius}, length(fract({uv} * {cells}) - 0.5)))"}, keywords="polka circles")
_node("linear_gradient", "Linear gradient", "Patterns", "0 to 1 across the area in a direction (angle in radians).",
      [_in("uv", "vec2", "@uv"), _in("angle", "float", 0.0, hint="angle")], [_out("value", "float")],
      exprs={"value": "saturate(dot({uv} - 0.5, vec2<f32>(cos({angle}), sin({angle}))) + 0.5)"},
      keywords="ramp fade")
_node("radial_gradient", "Radial gradient", "Patterns", "1 at center, fading to 0 at radius (aspect kept).",
      [_in("uv", "vec2", "@uv"), _in("center", "vec2", [0.5, 0.5]), _in("radius", "float", 0.5)],
      [_out("value", "float")],
      exprs={"value": "saturate(1.0 - length(({uv} - {center}) * vec2<f32>(size.x / max(size.y, 1.0), 1.0)) / {radius})"},
      keywords="circle fade spot")

WAVES = ("sine", "triangle", "square", "sawtooth")


def _build_wave(ctx: "Build") -> None:
    shape = ctx.params.get("shape", "sine")
    ctx.use("pzs_wave")
    i = ctx.inputs
    ctx.out("value", f"pzs_wave({i['x']} * {i['frequency']} + {i['phase']}, {WAVES.index(shape) if shape in WAVES else 0})")


_node("wave", "Wave", "Patterns", "A repeating wave from 0 to 1 (sine, triangle, square or sawtooth): "
      "frequency waves per unit of x.",
      [_in("x", "float", "@time"), _in("frequency", "float", 1.0), _in("phase", "float", 0.0)],
      [_out("value", "float")], params=(_enum("shape", WAVES),), build=_build_wave,
      label=lambda n, g: f"{str(n.params.get('shape', 'sine')).capitalize()} wave",
      keywords="oscillator pulse sine triangle square saw")
preset("wave", "Square wave", "On and off: 0 or 1, repeating.", "pulse blink", shape="square")
preset("wave", "Sawtooth wave", "Ramps from 0 to 1 and starts again.", "ramp", shape="sawtooth")


# -- Shapes (signed distances, negative inside) --------------------------------------------------------

_P = _in("p", "vec2", "@centered")
_C = _in("center", "vec2", [0.0, 0.0])
_D = _out("distance", "float", hint="sdf")

_node("circle", "Circle", "Shapes", "The signed distance to a circle (negative inside). Use Fill or Stroke to draw it.",
      [_P, _C, _in("radius", "float", 0.3)], [_D], exprs={"distance": "(length({p} - {center}) - {radius})"},
      keywords="sdf disc round")
_node("box", "Box", "Shapes", "The signed distance to a rectangle of size (rounded by radius).",
      [_P, _C, _in("size", "vec2", [0.6, 0.4]), _in("radius", "float", 0.05)], [_D],
      exprs={"distance": "pzs_sd_box({p} - {center}, {size} * 0.5, {radius})"}, functions=("pzs_sd_box",),
      keywords="sdf rectangle square rounded")
_node("ring", "Ring", "Shapes", "The signed distance to a ring of radius and thickness.",
      [_P, _C, _in("radius", "float", 0.3), _in("thickness", "float", 0.05)], [_D],
      exprs={"distance": "(abs(length({p} - {center}) - {radius}) - {thickness} * 0.5)"}, keywords="sdf circle donut")
_node("segment", "Segment", "Shapes", "The signed distance to a line from a to b, thickness wide.",
      [_P, _in("a", "vec2", [-0.3, 0.0]), _in("b", "vec2", [0.3, 0.0]), _in("thickness", "float", 0.04)], [_D],
      exprs={"distance": "(pzs_sd_segment({p}, {a}, {b}) - {thickness} * 0.5)"}, functions=("pzs_sd_segment",),
      keywords="sdf line capsule")
_node("polygon", "Polygon", "Shapes", "The signed distance to a regular polygon (sides corners, radius to them).",
      [_P, _C, _in("radius", "float", 0.3), _in("sides", "float", 6.0), _in("rotation", "float", 0.0, hint="angle")],
      [_D], exprs={"distance": "pzs_sd_polygon(pzs_rotate({p} - {center}, vec2<f32>(0.0), {rotation}), {radius}, {sides})"},
      functions=("pzs_sd_polygon", "pzs_rotate"), keywords="sdf hexagon triangle pentagon")
_node("star", "Star", "Shapes", "The signed distance to a star (inner is how deep its valleys are, 0 to 1).",
      [_P, _C, _in("radius", "float", 0.35), _in("points", "float", 5.0), _in("inner", "float", 0.45),
       _in("rotation", "float", 0.0, hint="angle")],
      [_D], exprs={"distance": "pzs_sd_star(pzs_rotate({p} - {center}, vec2<f32>(0.0), {rotation}), {radius}, "
                               "{points}, {inner})"},
      functions=("pzs_sd_star", "pzs_rotate"), keywords="sdf")

SDF_OPS = ("union", "subtract", "intersect")


def _build_sdf_op(ctx: "Build") -> None:
    op = ctx.params.get("op", "union")
    a, b, k = ctx.inputs["a"], ctx.inputs["b"], ctx.inputs["smooth"]
    if op == "subtract":
        ctx.use("pzs_smax")
        ctx.out("distance", f"pzs_smax({a}, -({b}), {k})")
    elif op == "intersect":
        ctx.use("pzs_smax")
        ctx.out("distance", f"pzs_smax({a}, {b}, {k})")
    else:
        ctx.use("pzs_smin")
        ctx.out("distance", f"pzs_smin({a}, {b}, {k})")


_node("sdf_op", "Combine shapes", "Shapes", "Joins two shapes (union), cuts b out of a (subtract) or keeps where "
      "they overlap (intersect); smooth melts the seam.",
      [_in("a", "float", 1.0), _in("b", "float", 1.0), _in("smooth", "float", 0.0)], [_D],
      params=(_enum("op", SDF_OPS),), build=_build_sdf_op,
      label=lambda n, g: {"union": "Union", "subtract": "Subtract shape", "intersect": "Intersect"}.get(
          n.params.get("op", "union"), "Union"), preset=False, keywords="boolean csg")
preset("sdf_op", "Union", "Joins two shapes; smooth melts them together.", "sdf merge boolean smooth min", op="union")
preset("sdf_op", "Subtract shape", "Cuts shape b out of shape a.", "sdf boolean difference cut", op="subtract")
preset("sdf_op", "Intersect", "Keeps where two shapes overlap.", "sdf boolean", op="intersect")
_node("fill", "Fill", "Shapes", "Draws a shape: 1 inside, 0 outside, with an antialiased edge softness pixels wide.",
      [_in("distance", "float", 0.0), _in("softness", "float", 1.0)], [_out("mask", "float")],
      exprs={"mask": "(1.0 - smoothstep(-{softness} / max(size.y, 1.0), {softness} / max(size.y, 1.0), {distance}))"},
      keywords="sdf draw solid mask antialias")
_node("stroke", "Stroke", "Shapes", "Draws the outline of a shape, width wide (in the shape's units).",
      [_in("distance", "float", 0.0), _in("width", "float", 0.02), _in("softness", "float", 1.0)],
      [_out("mask", "float")],
      exprs={"mask": "(1.0 - smoothstep({width} * 0.5 - {softness} / max(size.y, 1.0), {width} * 0.5 + "
                     "{softness} / max(size.y, 1.0), abs({distance})))"},
      keywords="sdf outline border line")
_node("glow", "Glow", "Shapes", "A soft light around a shape that fades over radius.",
      [_in("distance", "float", 0.0), _in("radius", "float", 0.08), _in("intensity", "float", 1.0)],
      [_out("value", "float")], exprs={"value": "({intensity} * exp(-max({distance}, 0.0) / max({radius}, 0.0001)))"},
      keywords="sdf halo bloom light neon")


# -- Color --------------------------------------------------------------------------------------------

_node("hsv_to_rgb", "HSV to RGB", "Color", "A color from hue (0 to 1 around the wheel), saturation and value.",
      [_in("h", "float", 0.0, "hue"), _in("s", "float", 1.0, "saturation"), _in("v", "float", 1.0, "value")],
      [_out("rgb", "vec3")], exprs={"rgb": "pzs_hsv2rgb(vec3<f32>({h}, {s}, {v}))"}, functions=("pzs_hsv2rgb",),
      keywords="hue rainbow")
_node("rgb_to_hsv", "RGB to HSV", "Color", "The hue, saturation and value of a color.",
      [_in("rgb", "vec3", [1.0, 0.0, 0.0], hint="color")],
      [_out("hsv", "vec3"), _out("h", "float", "hue"), _out("s", "float", "saturation"), _out("v", "float", "value")],
      exprs={"hsv": "pzs_rgb2hsv({rgb})", "h": "pzs_rgb2hsv({rgb}).x", "s": "pzs_rgb2hsv({rgb}).y",
             "v": "pzs_rgb2hsv({rgb}).z"}, functions=("pzs_rgb2hsv",), keywords="hue")
_node("hue_shift", "Hue shift", "Color", "Turns the hue of a color (shift from 0 to 1 is a full turn).",
      [_in("rgb", "vec3", [1.0, 0.0, 0.0], hint="color"), _in("shift", "float", 0.25)], [_out("rgb", "vec3")],
      exprs={"rgb": "pzs_hue_shift({rgb}, {shift})"}, functions=("pzs_hue_shift",), keywords="hue rotate")
_node("saturation", "Saturation", "Color", "More (above 1) or less (below 1) colorful; 0 is gray.",
      [_in("rgb", "vec3", [1.0, 0.5, 0.0], hint="color"), _in("amount", "float", 1.5)], [_out("rgb", "vec3")],
      exprs={"rgb": "pzs_saturate_color({rgb}, {amount})"}, functions=("pzs_saturate_color",),
      keywords="desaturate vibrance")
_node("brightness_contrast", "Brightness and contrast", "Color", "Lighter or darker, and more or less contrast.",
      [_in("rgb", "vec3", [0.5, 0.5, 0.5], hint="color"), _in("brightness", "float", 0.0),
       _in("contrast", "float", 1.0)], [_out("rgb", "vec3")],
      exprs={"rgb": "(({rgb} - 0.5) * {contrast} + 0.5 + {brightness})"}, keywords="exposure levels")
_node("luminance", "Luminance", "Color", "How bright a color looks, from 0 to 1.",
      [_in("rgb", "vec3", [1.0, 1.0, 1.0], hint="color")], [_out("value", "float")],
      exprs={"value": "pzs_luminance({rgb})"}, functions=("pzs_luminance",), keywords="grayscale brightness luma")
_node("grayscale", "Grayscale", "Color", "The color in shades of gray.",
      [_in("rgb", "vec3", [1.0, 0.5, 0.0], hint="color")], [_out("rgb", "vec3")],
      exprs={"rgb": "vec3<f32>(pzs_luminance({rgb}))"}, functions=("pzs_luminance",), keywords="black white mono")


def _build_invert(ctx: "Build") -> None:
    c = ctx.inputs["color"]
    ctx.out("color", f"vec4<f32>(1.0 - ({c}).xyz, ({c}).w)" if ctx.t == "vec4" else f"(1.0 - {c})")


_node("invert", "Invert", "Color", "The opposite color: 1 − color (alpha is kept).",
      [_in("color", GENERIC, [1.0, 0.5, 0.0], hint="color")], [_out("color", GENERIC)], build=_build_invert,
      min_type="float", keywords="negative")
_node("gamma", "Gamma", "Color", "Brightens (above 1) or darkens (below 1) the midtones.",
      [_in("rgb", "vec3", [0.5, 0.5, 0.5], hint="color"), _in("gamma", "float", 2.2)], [_out("rgb", "vec3")],
      exprs={"rgb": "pow(max({rgb}, vec3<f32>(0.0)), vec3<f32>(1.0 / {gamma}))"}, keywords="midtones curve")
_node("posterize", "Posterize", "Color", "Keeps only a few steps of each component.",
      [_in("color", GENERIC, [0.3, 0.6, 0.9], hint="color"), _in("steps", "float", 4.0)], [_out("color", GENERIC)],
      exprs={"color": "(floor({color} * {steps}) / {steps})"}, min_type="float", keywords="quantize banding cel")


def _build_blend(ctx: "Build") -> None:
    mode = ctx.params.get("mode", "multiply")
    mode = mode if mode in library.BLEND_MODES else "normal"
    ctx.use(f"pzs_blend_{mode}")
    i = ctx.inputs
    ctx.out("rgb", f"pzs_blend_{mode}({i['base']}, {i['layer']}, {i['opacity']})")


_node("blend", "Blend", "Color", "Blends layer over base like an image editor's layer modes.",
      [_in("base", "vec3", [0.2, 0.4, 0.8], hint="color"), _in("layer", "vec3", [1.0, 0.6, 0.2], hint="color"),
       _in("opacity", "float", 1.0, hint="range:0:1")], [_out("rgb", "vec3")],
      params=(_enum("mode", library.BLEND_MODES, "multiply"),), build=_build_blend,
      label=lambda n, g: f"Blend · {str(n.params.get('mode', 'multiply')).replace('_', ' ')}",
      keywords="multiply screen overlay layer modes")
_node("palette", "Palette", "Color", "A smooth rainbow-like color for t, from Inigo Quilez's cosine palettes: "
      "a + b × cos(2π(c × t + d)).",
      [_in("t", "float", 0.0), _in("a", "vec3", [0.5, 0.5, 0.5]), _in("b", "vec3", [0.5, 0.5, 0.5]),
       _in("c", "vec3", [1.0, 1.0, 1.0]), _in("d", "vec3", [0.0, 0.33, 0.67])], [_out("rgb", "vec3")],
      exprs={"rgb": "pzs_palette({t}, {a}, {b}, {c}, {d})"}, functions=("pzs_palette",),
      keywords="cosine rainbow gradient colors iq")

#: The colors a new Gradient node starts with: ``[position, color]``.
DEFAULT_STOPS = [[0.0, "#1e1b4b"], [0.5, "#db2777"], [1.0, "#fde047"]]


def gradient_stops(value: Any) -> List[Tuple[float, str]]:
    """The stops of a Gradient node, sorted by position (two at least)."""
    out: List[Tuple[float, str]] = []
    for item in value or DEFAULT_STOPS:
        try:
            pos, color = item
            out.append((float(pos), str(color)))
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda s: s[0])
    if not out:
        out = [(0.0, "#000000"), (1.0, "#ffffff")]
    if len(out) == 1:
        out.append((1.0, out[0][1]))
    return out


def _build_gradient(ctx: "Build") -> None:
    stops = gradient_stops(ctx.params.get("stops"))
    t = ctx.inputs["t"]
    expr = literal(stops[0][1], "vec4")
    for (p0, _c0), (p1, c1) in zip(stops, stops[1:]):
        span = max(p1 - p0, 1e-5)
        expr = f"mix({expr}, {literal(c1, 'vec4')}, saturate(({t} - {literal(p0, 'float')}) / {literal(span, 'float')}))"
    ctx.line(f"let {ctx.var}_c = {expr};")
    ctx.out("color", f"{ctx.var}_c")
    ctx.out("rgb", f"{ctx.var}_c.xyz")
    ctx.out("alpha", f"{ctx.var}_c.w")


_node("gradient", "Gradient", "Color", "A color ramp: the color at t (0 to 1) between the stops you set.",
      [_in("t", "float", "@uv")], [_out("color", "vec4"), _out("rgb", "vec3"), _out("alpha", "float")],
      params=(Param("stops", "stops", DEFAULT_STOPS),), build=_build_gradient, keywords="ramp color map lut")
TYPES["gradient"] = NodeType(**{**TYPES["gradient"].__dict__,
                                "inputs": (_in("t", "float", 0.5, hint="range:0:1"),)})
_node("rgba", "RGBA", "Color", "A color with alpha from a vec3 color and an opacity.",
      [_in("rgb", "vec3", [1.0, 1.0, 1.0], hint="color"), _in("alpha", "float", 1.0, hint="range:0:1")],
      [_out("color", "vec4")], exprs={"color": "vec4<f32>({rgb}, {alpha})"}, keywords="alpha opacity combine")
_node("layer", "Layer", "Color", "Puts front over back using front's alpha.",
      [_in("back", "vec4", [0.0, 0.0, 0.0, 1.0], hint="color"), _in("front", "vec4", [1.0, 1.0, 1.0, 0.5], hint="color")],
      [_out("color", "vec4")],
      exprs={"color": "vec4<f32>(mix(({back}).xyz, ({front}).xyz, ({front}).w), "
                      "({front}).w + ({back}).w * (1.0 - ({front}).w))"},
      keywords="over composite alpha stack")


# -- Effects --------------------------------------------------------------------------------------------

_node("vignette", "Vignette", "Effects", "Darkens toward the corners: multiply a color by it.",
      [_in("uv", "vec2", "@uv"), _in("strength", "float", 0.8, hint="range:0:1")], [_out("value", "float")],
      exprs={"value": "saturate(1.0 - {strength} * 2.0 * dot({uv} - 0.5, {uv} - 0.5))"}, keywords="corners darken")
_node("scanlines", "Scanlines", "Effects", "The horizontal lines of a CRT screen: multiply a color by it.",
      [_in("px", "vec2", "@px", "pixel"), _in("spacing", "float", 3.0), _in("strength", "float", 0.25),
       _in("speed", "float", 0.0)], [_out("value", "float")],
      exprs={"value": "(1.0 - {strength} * (0.5 + 0.5 * cos(({px}).y * 6.2831853 / {spacing} - time * {speed})))"},
      keywords="crt retro tv lines")
_node("grain", "Film grain", "Effects", "Random speckles that change every frame: multiply a color by it.",
      [_in("px", "vec2", "@px", "pixel"), _in("strength", "float", 0.12)], [_out("value", "float")],
      exprs={"value": "(1.0 + (pzs_hash21({px} + fract(time) * 913.0) - 0.5) * 2.0 * {strength})"},
      functions=("pzs_hash21",), keywords="noise film static dither")


# -- Texture ----------------------------------------------------------------------------------------------


def _build_sample(ctx: "Build") -> None:
    tex = ctx.inputs["texture"]
    ctx.line(f"let {ctx.var}_c = {tex}({ctx.inputs['uv']});")
    ctx.out("color", f"{ctx.var}_c")
    ctx.out("rgb", f"{ctx.var}_c.xyz")
    ctx.out("alpha", f"{ctx.var}_c.w")


_node("sample_texture", "Sample texture", "Texture", "The color of a texture (an image variable) at uv.",
      [_in("texture", "texture", None), _in("uv", "vec2", "@uv")],
      [_out("color", "vec4"), _out("rgb", "vec3"), _out("alpha", "float")], build=_build_sample,
      keywords="image picture sprite sampler")


# -- Logic ---------------------------------------------------------------------------------------------------

COMPARISONS = {"<": "<", "<=": "<=", ">": ">", ">=": ">=", "==": "==", "!=": "!="}


def _build_compare(ctx: "Build") -> None:
    op = ctx.params.get("op", "<")
    op = op if op in COMPARISONS else "<"
    expr = f"({ctx.inputs['a']} {op} {ctx.inputs['b']})"
    ctx.out("result", f"all{expr}" if SIZE.get(ctx.t, 1) > 1 else expr)


_node("compare", "Compare", "Logic", "Whether a is less, greater or equal to b (for vectors: every component).",
      [_in("a", GENERIC, 0.0), _in("b", GENERIC, 0.5)], [_out("result", "bool")],
      params=(_enum("op", list(COMPARISONS)),), build=_build_compare, min_type="int",
      label=lambda n, g: f"Compare {n.params.get('op', '<')}", keywords="less greater equal if condition")
_node("select", "Select", "Logic", "if condition then a else b.",
      [_in("condition", "bool", True), _in("a", GENERIC, 1.0, "then"), _in("b", GENERIC, 0.0, "else")],
      [_out("result", GENERIC)], exprs={"result": "select({b}, {a}, {condition})"}, keywords="if branch switch ternary")

LOGIC = {"and": "({a} && {b})", "or": "({a} || {b})", "xor": "({a} != {b})", "not": "(!{a})"}


def _build_logic(ctx: "Build") -> None:
    op = ctx.params.get("op", "and")
    ctx.out("result", ctx.format(LOGIC.get(op, LOGIC["and"])))


_node("logic", "Logic", "Logic", "and, or, xor and not of true/false values.",
      [_in("a", "bool", True), _in("b", "bool", False)], [_out("result", "bool")],
      params=(_enum("op", list(LOGIC)),), build=_build_logic,
      label=lambda n, g: str(n.params.get("op", "and")).upper(), keywords="and or not boolean")


# -- Variables, utility, output: built by the compiler from the graph ----------------------------------------


def _parameter_ports(node: "Node", graph: "Graph") -> Ports:
    var = graph.variable(node.params.get("name", ""))
    if var is None:
        return ((), (_out("value", "float"),))
    t = var.port_type
    if var.type == "color":
        return ((), (_out("color", "vec4"), _out("rgb", "vec3"), _out("alpha", "float")))
    return ((), (_out("value", t),))


_node("parameter", "Parameter", "Parameters", "Reads a variable of the shader (see the Variables list): "
      "a mutable one changes without recompiling, a constant is built into the code.",
      outputs=[_out("value", "float")], params=(Param("name", "variable", ""),), ports=_parameter_ports,
      label=lambda n, g: str(n.params.get("name") or "Parameter"), icon="sliders-horizontal",
      keywords="uniform variable input property", preset=False)


def _set_ports(node: "Node", graph: "Graph") -> Ports:
    return ((_in("value", GENERIC, 0.0),), (_out("value", GENERIC),))


_node("set_var", "Set value", "Variables", "Gives a value a name, so Get value nodes can read it anywhere "
      "without a long wire.", [_in("value", GENERIC, 0.0)], [_out("value", GENERIC)],
      params=(Param("name", "text", "value1"),), label=lambda n, g: f"Set {n.params.get('name') or 'value'}",
      icon="arrow-down-to-line", keywords="variable local named reroute let", preset=True)


_node("get_var", "Get value", "Variables", "Reads a value named by a Set value node.",
      outputs=[_out("value", GENERIC)], params=(Param("name", "local", "value1"),),
      label=lambda n, g: f"Get {n.params.get('name') or 'value'}", icon="arrow-up-from-line",
      keywords="variable local named reroute")
_node("reroute", "Reroute", "Utility", "A point to bend a wire around other nodes.", [_in("in", GENERIC, 0.0)],
      [_out("out", GENERIC)], exprs={"out": "{in}"}, icon="dot", keywords="wire point redirect")

#: The output types an Expression node can return.
EXPRESSION_TYPES = ("float", "vec2", "vec3", "vec4", "int", "bool")


def _expression_resolve(node: "Node", graph: "Graph", t: str) -> Dict[str, str]:
    out = node.params.get("type", "float")
    return {"result": out if out in EXPRESSION_TYPES else "float"}


_node("expression", "Expression", "Utility", "Your own WGSL: an expression of a, b, c and d (and uv, px, size, "
      "time), or a function body with return. The types of a to d follow what is connected.",
      [_in("a", "any", 0.0), _in("b", "any", 0.0), _in("c", "any", 0.0), _in("d", "any", 0.0)],
      [_out("result", "float")],
      params=(Param("code", "code", "a + b"), _enum("type", EXPRESSION_TYPES)), resolve=_expression_resolve,
      icon="code", keywords="custom code wgsl function script")


def _subgraph_ports(node: "Node", graph: "Graph") -> Ports:
    sub = graph._subgraph(node.params.get("path", ""))
    inputs = [_in("uv", "vec2", "@uv")]
    if sub is not None:
        for var in sub.variables:
            if var.mutable:
                inputs.append(_in(var.name, var.port_type, var.value if var.type != "texture" else None,
                                  hint="color" if var.type == "color" else ""))
    return (tuple(inputs), (_out("color", "vec4"), _out("rgb", "vec3"), _out("alpha", "float")))


_node("subgraph", "Shader function", "Utility", "Another .pzshad used as a function: its mutable variables are "
      "inputs, its output is the color. Feed uv to move, tile or warp it.",
      [_in("uv", "vec2", "@uv")], [_out("color", "vec4"), _out("rgb", "vec3"), _out("alpha", "float")],
      params=(Param("path", "file", ""),), ports=_subgraph_ports,
      label=lambda n, g: (str(n.params.get("path") or "Shader function").replace("\\", "/").rsplit("/", 1)[-1]
                          .removesuffix(".pzshad")),
      icon="package", keywords="subgraph group reuse function call include")
_node("comment", "Comment", "Utility", "A note on the graph.", params=(Param("text", "text", "Note"),),
      icon="sticky-note", keywords="note frame text")
_node("output", "Output", "Output", "The color of every pixel. Alpha, when connected, replaces color's alpha.",
      [_in("color", "vec4", [0.0, 0.0, 0.0, 1.0], hint="color"), _in("alpha", "float", None)],
      icon="monitor", keywords="result final fragment")


def type_of(node: "Node") -> Optional[NodeType]:
    """The node type of ``node`` (``None`` if the catalog doesn't have it)."""
    return TYPES.get(node.type)


def category_of(type_: str) -> str:
    """The sidebar category of a node type."""
    nt = TYPES.get(type_)
    return nt.category if nt else "Utility"


def context_value(default: Any) -> Optional[Tuple[str, str, Tuple[str, ...]]]:
    """``(type, expression, functions)`` of a context default such as ``"@uv"``, or ``None``."""
    return CONTEXT.get(default) if isinstance(default, str) else None
