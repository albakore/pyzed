"""Turns a shader graph into the WGSL of ``pz.shader``.

``compile(graph)`` walks back from the Output node, gives every output it needs a typed
``let`` in one function, writes the library functions those nodes call once, and returns
a ``Compiled`` with the code, the uniforms (mutable variables) and the textures to pass
to ``pz.shader``. ``compile(graph, (node_id, port))`` compiles one output as a color
instead: that is how each node shows a preview of what it makes.

Mutable variables become uniforms (``u_speed()``) so changing them doesn't recompile;
constants are written into the code. Problems never raise: ``Compiled.errors`` says
which node has which problem, and the node's outputs fall back to zero.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

from . import library
from . import nodes as _nodes
from .types import GENERIC, SIZE, WGSL, convert, literal, parse_color, widest

if TYPE_CHECKING:  # pragma: no cover
    from .graph import Graph, Node, Variable

#: How many mutable variables (uniforms) one shader can have; ``pz.shader`` has this many slots.
MAX_UNIFORMS = 32
#: How many texture variables one shader can have.
MAX_TEXTURES = 8

ARGS = "uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32"


@dataclass
class Compiled:
    """The result of compiling a graph: WGSL code plus what to pass to ``pz.shader``."""

    #: The WGSL code, with ``fn shade(...)``.
    code: str
    #: ``{uniform name: value}`` for ``pz.shader(uniforms=...)``.
    uniforms: Dict[str, Any] = field(default_factory=dict)
    #: ``{texture name: image path}`` for ``pz.shader(textures=...)``.
    textures: Dict[str, str] = field(default_factory=dict)
    #: The uniform each mutable variable is passed as (``{"speed": "u_speed"}``).
    names: Dict[str, str] = field(default_factory=dict)
    #: Problems, by node id (``"graph"`` for the graph as a whole).
    errors: Dict[str, str] = field(default_factory=dict)
    #: Which node wrote each line of ``code`` (1-based), to point compiler errors at a node.
    lines: Dict[int, str] = field(default_factory=dict)
    #: Whether the shader changes with time (an animated shader redraws every frame).
    uses_time: bool = False

    @property
    def ok(self) -> bool:
        """Whether the graph compiled without problems."""
        return not self.errors

    def uniform_values(self, values: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """The uniforms with some variables changed: ``values`` is ``{variable name: value}``."""
        out = dict(self.uniforms)
        for name, value in (values or {}).items():
            key = self.names.get(name)
            if key is not None and key in out:
                out[key] = uniform_value(value)
        return out

    def check(self) -> Dict[str, str]:
        """Compiles the code with the GPU compiler (naga) and adds what it finds to ``errors``,
        on the node that wrote the line. Returns ``errors``."""
        from .. import _core

        try:
            _core.shader(self.code, uniforms=self.uniforms or None, textures=self.textures or None)
        except ValueError as err:
            message = str(err).replace("invalid shader:\n", "").strip()
            node = self._node_of(message)
            self.errors.setdefault(node or "graph", _first_line(message))
            self.errors.setdefault("wgsl", message)
        return self.errors

    def _node_of(self, message: str) -> Optional[str]:
        from .. import _core

        try:
            module = _core.shader_module(self.code, uniforms=self.uniforms or None, textures=self.textures or None)
        except (ValueError, TypeError, AttributeError):
            return None
        offset = module[:module.find(self.code)].count("\n") if self.code in module else 0
        for match in re.finditer(r"wgsl:(\d+):\d+", message):
            line = int(match.group(1)) - offset
            node = self.lines.get(line)
            if node is not None:
                return node
        return None


def _first_line(message: str) -> str:
    for line in message.splitlines():
        line = line.strip()
        if line.startswith("error:"):
            return line[6:].strip()
    return message.splitlines()[0] if message else "invalid shader"


def uniform_value(value: Any) -> Any:
    """A variable's value the way ``pz.shader`` takes a uniform (a number or 2 to 4 numbers)."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return parse_color(value)
    return tuple(float(v) for v in value)


# -- types ----------------------------------------------------------------------------------------


def value_type(value: Any, port_type: str = GENERIC) -> str:
    """The type of an unconnected input's value (``float`` for a number, ``vec3`` for 3 numbers)."""
    ctx = _nodes.context_value(value)
    if ctx is not None:
        return ctx[0]
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, str):
        return "vec4"  # a color
    if isinstance(value, (list, tuple)):
        return {1: "float", 2: "vec2", 3: "vec3"}.get(len(value), "vec4")
    return "float"


def resolve_types(graph: "Graph") -> Dict[str, Dict[str, str]]:
    """The type of every port of every node: ``{node id: {output: type, "in:<input>": type, "T": type}}``.

    Inputs and outputs typed ``T`` take the widest type among the node's ``T`` inputs, following
    the wires from the inputs of the graph to its output.
    """
    cached = graph._types_cache
    if cached is not None and cached[0] == graph.revision:
        return cached[1]
    types: Dict[str, Dict[str, str]] = {}
    order: List[str] = []
    state: Dict[str, int] = {}

    def visit(nid: str) -> None:
        if state.get(nid) or nid not in graph.nodes:
            return
        state[nid] = 1
        for dep in graph.dependencies(nid):
            visit(dep)
        state[nid] = 2
        order.append(nid)

    for nid in graph.nodes:
        visit(nid)
    links = {(l.dst, l.inp): l for l in graph.links}
    for nid in order:
        node = graph.nodes[nid]
        nt = _nodes.TYPES.get(node.type)
        inputs, outputs = graph.ports(node)
        mine: Dict[str, str] = {}
        generic: List[str] = []
        for p in inputs:
            link = links.get((nid, p.name))
            src_type = types.get(link.src, {}).get(link.out, "float") if link is not None else None
            value = node.inputs.get(p.name, p.default)
            if p.type == GENERIC:
                generic.append(src_type or value_type(value))
            elif p.type == "any":
                mine[f"in:{p.name}"] = src_type or value_type(value)
            else:
                mine[f"in:{p.name}"] = p.type
        t = widest(generic, nt.min_type if nt else "bool") if generic else "float"
        if t == "texture":
            t = "float"
        if node.type == "get_var":
            name = node.params.get("name")
            setter = next((n for n in graph.nodes.values() if n.type == "set_var" and n.params.get("name") == name), None)
            t = types.get(setter.id, {}).get("value", "float") if setter is not None else "float"
        mine["T"] = t
        for p in inputs:
            if p.type == GENERIC:
                mine[f"in:{p.name}"] = t
        for o in outputs:
            mine[o.name] = t if o.type == GENERIC else o.type
        if nt is not None and nt.resolve is not None:
            mine.update(nt.resolve(node, graph, t))
        types[nid] = mine
    graph._types_cache = (graph.revision, types)
    return types


# -- building one node ---------------------------------------------------------------------------------------


class Build:
    """What a node type's ``build`` function works with: the node's inputs as WGSL expressions
    (already converted to the input's type), its settings, and where to put its outputs."""

    def __init__(self, compiler: "Compiler", node: "Node", inputs: Dict[str, str], types: Dict[str, str],
                 t: str, connected: Set[str]) -> None:
        self.compiler = compiler
        self.node = node
        self.graph = compiler.graph
        #: The WGSL expression of each input.
        self.inputs = inputs
        #: The type of each input.
        self.types = types
        #: What ``T`` resolved to for this node.
        self.t = t
        #: The inputs that have a wire.
        self.connected = connected
        self.params = node.params
        #: The prefix of the node's own WGSL names (``n12``).
        self.var = f"n{_safe(node.id)}"
        self.outputs: Dict[str, str] = {}
        self.lines: List[str] = []

    def out(self, name: str, expr: str) -> None:
        """Sets the WGSL expression of the output ``name``."""
        self.outputs[name] = expr

    def line(self, statement: str) -> None:
        """Adds a statement before the outputs (``let n12_v = ...;``)."""
        self.lines.append(statement)

    def use(self, *functions: str) -> None:
        """Marks library functions as needed."""
        self.compiler.functions.update(functions)

    def format(self, template: str) -> str:
        """Fills a template: ``{input}``, ``{self}`` and ``{p_setting}``."""
        values = dict(self.inputs)
        values["self"] = self.var
        values.update({f"p_{k}": v for k, v in self.params.items()})
        return template.format(**values)


def _safe(node_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", node_id)


def _zero(type_: str) -> str:
    if type_ == "texture":
        return "pzs_white"
    if type_ == "vec4":
        return "vec4<f32>(0.0, 0.0, 0.0, 1.0)"
    return literal(0, type_) if type_ in WGSL else "0.0"


def to_color(expr: str, type_: str, hint: str = "") -> str:
    """``expr`` (of ``type_``) as an RGBA color, the way a node's preview shows it."""
    if hint == "sdf" and type_ == "float":
        return f"pzs_sdf_preview({expr}, size)"
    if type_ == "texture":
        return f"{expr}(uv)"
    if type_ == "bool":
        return f"select(vec4<f32>(0.0, 0.0, 0.0, 1.0), vec4<f32>(1.0), {expr})"
    if type_ == "int":
        return f"vec4<f32>(vec3<f32>(f32({expr})), 1.0)"
    if type_ == "float":
        return f"vec4<f32>(vec3<f32>({expr}), 1.0)"
    return convert(expr, type_, "vec4")


class Compiler:
    """Compiles one graph; a Shader function node compiles its graph with a child compiler."""

    def __init__(self, graph: "Graph", *, values: Optional[Dict[str, Any]] = None, function: Optional[str] = None,
                 parent: Optional["Compiler"] = None, textures: Optional[Dict[str, str]] = None) -> None:
        self.graph = graph
        self.values = values or {}
        #: The name of the function to write (a Shader function node), or ``None`` for the shader itself.
        self.function = function
        self.parent = parent
        root = parent.root if parent is not None else self
        self.root: Compiler = root
        if parent is None:
            self.functions: Set[str] = set()
            self.extra: List[Tuple[str, Optional[str]]] = []  # (code, node id of the parent graph)
            self.uniforms: Dict[str, Any] = {}
            self.names: Dict[str, str] = {}
            self.texture_paths: Dict[str, str] = {}
            self.subgraphs: Dict[Tuple[Any, ...], str] = {}
            self.stack: List[str] = [str(graph.path or id(graph))]
        else:
            self.functions = parent.functions
        #: Texture variables of this graph bound to texture functions of the shader (Shader functions).
        self.bound_textures = textures or {}
        self.errors: Dict[str, str] = {}
        self.body: List[Tuple[str, Optional[str]]] = []
        self.values_of: Dict[Tuple[str, str], str] = {}
        self.uses_time = False
        #: Names given by Set value nodes compiled so far.
        self.locals: Set[str] = set()
        self.types = resolve_types(graph)

    # -- variables --------------------------------------------------------------------------------
    def variable_value(self, var: "Variable") -> Any:
        return self.values.get(var.name, var.value)

    def variable_expr(self, var: "Variable", node_id: str) -> str:
        """How the shader reads a variable: a uniform, an argument (in a Shader function), or a literal."""
        t = var.port_type
        if var.type == "texture":
            if var.name in self.bound_textures:
                return self.bound_textures[var.name]
            if var.value and not self._resolve_path(var.value):
                self.errors[node_id] = f"can't find the image {var.value!r}"
            return self.texture(var.name, var.value, prefix="t_" if self.function is None else f"{self.function}_t_")
        if not var.mutable:
            value = self.variable_value(var)
            return literal(parse_color(value) if var.type == "color" else value, t)
        if self.function is not None:
            raw = f"a_{var.name}"
        else:
            root = self.root
            raw = f"u_{var.name}"
            if raw not in root.uniforms:
                if len(root.uniforms) >= MAX_UNIFORMS:
                    self.errors[node_id] = f"a shader takes at most {MAX_UNIFORMS} mutable variables"
                    return _zero(t)
                root.uniforms[raw] = uniform_value(self.variable_value(var))
                root.names[var.name] = raw
            raw = f"{raw}()"
        if var.type == "int":
            return f"i32({raw})"
        if var.type == "bool":
            return f"({raw} > 0.5)"
        return raw

    def texture(self, name: str, path: Any, prefix: str) -> str:
        """The function that samples the texture variable ``name`` (an image at ``path``)."""
        root = self.root
        key = f"{prefix}{name}"
        if key not in root.texture_paths:
            if len(root.texture_paths) >= MAX_TEXTURES:
                return "pzs_white"
            root.texture_paths[key] = self._resolve_path(path)
        return key

    def _resolve_path(self, path: Any) -> str:
        if not path:
            return ""
        p = Path(str(path))
        if not p.is_absolute() and self.graph.path is not None:
            p = self.graph.path.parent / p
        return str(p) if p.is_file() else ""

    # -- nodes -------------------------------------------------------------------------------------
    def input_exprs(self, node: "Node") -> Tuple[Dict[str, str], Dict[str, str], Set[str]]:
        types = self.types.get(node.id, {})
        exprs: Dict[str, str] = {}
        in_types: Dict[str, str] = {}
        connected: Set[str] = set()
        literals: List[str] = []
        live = False  # whether an input reads a wire or the pixel (then nothing is folded at compile time)
        for p in self.graph.ports(node)[0]:
            want = types.get(f"in:{p.name}", p.type if p.type not in (GENERIC, "any") else "float")
            in_types[p.name] = want
            link = self.graph.link_into(node.id, p.name)
            if link is not None and (link.src, link.out) in self.values_of:
                have = self.types.get(link.src, {}).get(link.out, "float")
                try:
                    exprs[p.name] = convert(self.values_of[(link.src, link.out)], have, want)
                    connected.add(p.name)
                    live = True
                    continue
                except TypeError as err:
                    self.errors[node.id] = str(err)
            value = node.inputs.get(p.name, p.default)
            ctx = _nodes.context_value(value)
            if ctx is not None:
                ctx_type, expr, functions = ctx
                self.functions.update(functions)
                live = True
                if expr == "time":
                    self.uses_time = True
                try:
                    exprs[p.name] = convert(expr, ctx_type, want)
                except TypeError:
                    exprs[p.name] = _zero(want)
            elif want == "texture":
                self.functions.add("pzs_white")
                exprs[p.name] = "pzs_white"
            else:
                if value is None:
                    exprs[p.name] = _zero(want)
                else:
                    try:
                        exprs[p.name] = literal(parse_color(value) if isinstance(value, str) else value, want)
                    except (TypeError, ValueError):
                        exprs[p.name] = _zero(want)
                if want in WGSL:
                    literals.append(p.name)
        if literals and not live and node.type not in ("output",):
            # Only constants: name them, or WGSL would compute the node at compile time (and reject 1 / 0).
            for name in literals:
                var = f"n{_safe(node.id)}_in_{name}"
                self.body.append((f"let {var}: {WGSL[in_types[name]]} = {exprs[name]};", node.id))
                exprs[name] = var
        return exprs, in_types, connected

    def emit(self, node: "Node", needed: Set[Tuple[str, str]]) -> None:
        nt = _nodes.TYPES.get(node.type)
        types = self.types.get(node.id, {})
        outputs = self.graph.ports(node)[1]
        if nt is None:
            self.errors[node.id] = f"unknown node type {node.type!r}"
            for o in outputs:
                self.values_of[(node.id, o.name)] = _zero(types.get(o.name, "float"))
            return
        inputs, in_types, connected = self.input_exprs(node)
        ctx = Build(self, node, inputs, in_types, types.get("T", "float"), connected)
        try:
            self.build(nt, ctx)
        except Exception as err:  # noqa: BLE001 - a bad setting must not stop the whole shader
            self.errors.setdefault(node.id, f"{type(err).__name__}: {err}")
            ctx.lines.clear()
            ctx.outputs.clear()
        for statement in ctx.lines:
            self.body.append((statement, node.id))
            if re.search(r"\btime\b", statement):
                self.uses_time = True
        for o in outputs:
            out_type = types.get(o.name, "float")
            expr = ctx.outputs.get(o.name)
            if expr is None:
                expr = _zero(out_type)
            if re.search(r"\btime\b", expr) and (node.id, o.name) in needed:
                self.uses_time = True
            if out_type == "texture":
                self.values_of[(node.id, o.name)] = expr
                continue
            if (node.id, o.name) not in needed:
                continue
            name = f"{ctx.var}_{o.name}"
            self.body.append((f"let {name}: {WGSL[out_type]} = {expr};", node.id))
            self.values_of[(node.id, o.name)] = name

    def build(self, nt: _nodes.NodeType, ctx: Build) -> None:
        node = ctx.node
        if node.type == "parameter":
            var = self.graph.variable(str(node.params.get("name", "")))
            if var is None:
                self.errors[node.id] = f"no variable {node.params.get('name')!r}" if node.params.get("name") \
                    else "pick a variable"
                return
            expr = self.variable_expr(var, node.id)
            if var.type == "color":
                ctx.out("color", expr)
                ctx.out("rgb", f"({expr}).xyz")
                ctx.out("alpha", f"({expr}).w")
            else:
                ctx.out("value", expr)
            return
        if node.type == "set_var":
            name = str(node.params.get("name", ""))
            from .graph import valid_name

            if not valid_name(name):
                self.errors[node.id] = f"{name!r} can't name a value"
                ctx.out("value", ctx.inputs["value"])
                return
            first = next(n for n in self.graph.nodes.values() if n.type == "set_var" and n.params.get("name") == name)
            if first.id != node.id:
                self.errors[node.id] = f"another Set value already names {name!r}"
                ctx.out("value", ctx.inputs["value"])
                return
            ctx.line(f"let l_{name}: {WGSL[ctx.t]} = {ctx.inputs['value']};")
            self.locals.add(name)
            ctx.out("value", f"l_{name}")
            return
        if node.type == "get_var":
            name = str(node.params.get("name", ""))
            if name not in self.locals:
                self.errors[node.id] = f"no Set value names {name!r}"
                return
            ctx.out("value", f"l_{name}")
            return
        if node.type == "expression":
            self.build_expression(ctx)
            return
        if node.type == "subgraph":
            self.build_subgraph(ctx)
            return
        if node.type in ("output", "comment"):
            return
        if nt.build is not None:
            nt.build(ctx)
        else:
            ctx.use(*nt.functions)
            for name, template in nt.exprs.items():
                ctx.out(name, ctx.format(template))
        ctx.use(*nt.functions)

    def build_expression(self, ctx: Build) -> None:
        node = ctx.node
        code = str(node.params.get("code", "")).strip() or "0.0"
        out_type = self.types.get(node.id, {}).get("result", "float")
        names = ("a", "b", "c", "d")
        args = ", ".join(f"{n}: {WGSL.get(ctx.types[n], 'f32')}" for n in names)
        body = code if re.search(r"\breturn\b", code) else f"return {code.rstrip(';')};"
        fn = f"pzs_expr_{_safe(node.id)}"
        if self.function is not None:
            fn = f"{self.function}_expr_{_safe(node.id)}"
        lines = [f"fn {fn}({args}, {ARGS}) -> {WGSL[out_type]} {{"]
        lines += [f"    {line}" for line in body.splitlines()]
        lines.append("}")
        self.root.extra.append(("\n".join(lines), node.id if self.parent is None else self._parent_node))
        if re.search(r"\btime\b", code):
            self.uses_time = True
        ctx.out("result", f"{fn}({', '.join(ctx.inputs[n] for n in names)}, uv, px, size, time)")

    _parent_node: Optional[str] = None

    def build_subgraph(self, ctx: Build) -> None:
        node = ctx.node
        path = node.params.get("path", "")
        sub = self.graph._subgraph(path)
        if sub is None:
            self.errors[node.id] = f"can't read {path!r}" if path else "pick a .pzshad file"
            return
        key_path = str(sub.path or path)
        root = self.root
        if key_path in root.stack:
            self.errors[node.id] = "a shader can't use itself"
            return
        textures: Dict[str, str] = {}
        args: List[str] = []
        for var in sub.variables:
            if not var.mutable:
                continue
            if var.type == "texture":
                link = self.graph.link_into(node.id, var.name)
                if link is not None and (link.src, link.out) in self.values_of:
                    textures[var.name] = self.values_of[(link.src, link.out)]
            else:
                args.append(ctx.inputs[var.name])
        key = (key_path, tuple(sorted(textures.items())), sub.revision)
        fn = root.subgraphs.get(key)
        if fn is None:
            fn = f"pzs_fn{len(root.subgraphs) + 1}"
            root.subgraphs[key] = fn
            child = Compiler(sub, function=fn, parent=self, textures=textures)
            child._parent_node = node.id if self.parent is None else self._parent_node
            root.stack.append(key_path)
            try:
                code = child.function_code()
            finally:
                root.stack.pop()
            for nid, message in child.errors.items():
                self.errors.setdefault(node.id, f"{Path(key_path).name}: {message}")
            root.extra.append((code, child._parent_node))
            if child.uses_time:
                root.subgraphs[("time",) + key] = fn
        if ("time",) + key in root.subgraphs:
            self.uses_time = True
        uv = ctx.inputs["uv"]
        extra = "".join(f", {a}" for a in args)
        ctx.line(f"let {ctx.var}_c = {fn}({uv}, {uv} * size, size, time{extra});")
        ctx.out("color", f"{ctx.var}_c")
        ctx.out("rgb", f"{ctx.var}_c.xyz")
        ctx.out("alpha", f"{ctx.var}_c.w")

    # -- whole graph ---------------------------------------------------------------------------------------
    def result(self, target: Optional[Tuple[str, str]]) -> str:
        """Emits the nodes ``target`` needs (the Output node's by default) and returns the color expression."""
        graph = self.graph
        out_node = graph.output_node
        if target is not None and target[0] in graph.nodes and graph.nodes[target[0]].type != "output":
            start = target[0]
        elif out_node is not None:
            start, target = out_node.id, None
        else:
            self.errors["graph"] = "the shader has no Output node"
            return "vec4<f32>(0.0, 0.0, 0.0, 1.0)"
        order = graph.upstream(start)
        members = set(order)
        needed: Set[Tuple[str, str]] = {(l.src, l.out) for l in graph.links if l.dst in members and l.src in members}
        if target is not None:
            needed.add(target)
        for nid in order:
            self.emit(graph.nodes[nid], needed)
        if target is not None:
            node = graph.nodes[target[0]]
            expr = self.values_of.get(target)
            port = graph.output_port(node, target[1])
            if expr is None or port is None:
                return "vec4<f32>(0.0, 0.0, 0.0, 1.0)"
            t = self.types.get(node.id, {}).get(target[1], "float")
            if port.hint == "sdf" and t == "float":
                self.functions.add("pzs_sdf_preview")
            return to_color(expr, t, port.hint)
        inputs, _types, connected = self.input_exprs(out_node)  # type: ignore[arg-type]
        color = inputs["color"]
        if "alpha" in connected:
            return f"vec4<f32>(({color}).xyz, {inputs['alpha']})"
        return color

    def function_code(self) -> str:
        """The graph as a WGSL function (for a Shader function node)."""
        result = self.result(None)
        args = "".join(f", a_{v.name}: {WGSL[v.port_type]}" for v in self.graph.variables
                       if v.mutable and v.type != "texture")
        lines = [f"// {self.graph.name}", f"fn {self.function}({ARGS}{args}) -> vec4<f32> {{"]
        lines += [f"    {s}" for s, _ in self.body]
        lines += [f"    return {result};", "}"]
        return "\n".join(lines)


def compile(graph: "Graph", target: Optional[Tuple[str, str]] = None, *, values: Optional[Dict[str, Any]] = None,
            ) -> Compiled:
    """Compiles ``graph`` to WGSL for ``pz.shader``.

    ``target=(node_id, port)`` compiles that output shown as a color instead of the Output node (a
    node's preview). ``values`` changes variables for this compile (``{"speed": 2.0}``); mutable
    ones only change the uniforms, constants change the code. Results are cached until the graph
    changes.
    """
    key = (graph.revision, target, tuple(sorted((k, repr(v)) for k, v in (values or {}).items())))
    cache = graph._compiled
    hit = cache.get(key)
    if hit is not None:
        return hit
    c = Compiler(graph, values=values)
    result = c.result(target)
    head = [f"// {graph.name}: made with pyzed.shading. Edit the .pzshad, not this code.", ""]
    code_lines: List[str] = list(head)
    lines: Dict[int, str] = {}
    library_code = library.code(sorted(c.functions))
    if library_code:
        code_lines += library_code.rstrip("\n").split("\n") + [""]
    for text, node_id in c.extra:
        start = len(code_lines) + 1
        code_lines += text.split("\n") + [""]
        if node_id is not None:
            for i in range(start, len(code_lines) + 1):
                lines[i] = node_id
    code_lines.append(f"fn pzs_main({ARGS}) -> vec4<f32> {{")
    for statement, node_id in c.body:
        code_lines.append(f"    {statement}")
        if node_id is not None:
            lines[len(code_lines)] = node_id
    code_lines += [f"    return {result};", "}", "",
                   f"fn shade({ARGS}) -> vec4<f32> {{", "    return pzs_main(uv, px, size, time);", "}", ""]
    compiled = Compiled("\n".join(code_lines), dict(c.uniforms), dict(c.texture_paths), dict(c.names), dict(c.errors),
                        lines, c.uses_time)
    if len(cache) > 256:
        cache.clear()
    for old in [k for k in cache if k[0] != graph.revision]:
        del cache[old]
    cache[key] = compiled
    return compiled
