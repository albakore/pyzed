"""Shaders made of nodes, like Godot's visual shaders: ``.pzshad`` files you edit in Pyzed Design.

A shader graph is nodes (inputs such as UV and Time, math, noise, shapes, colors...)
wired from the inputs to an Output node. ``pyzed.shading`` compiles it to the WGSL of
``pz.shader``, so it runs on the GPU like a hand-written shader, with no WGSL to write::

    import pyzed as pz
    from pyzed import shading

    fire = shading.load("fire.pzshad")      # made in Pyzed Design (New → Shader)
    fire["speed"] = 2.0                     # a mutable variable: changes without recompiling
    pz.shader(fire, width=320, height=200)  # or fire.widget(...), or pz.shader("fire.pzshad")

Or build the graph in code (see ``Graph``)::

    g = shading.Graph("rings")
    d = g.circle(radius=0.3 + 0.05 * g.time()["sin"])
    g.output(g.rgba(g.palette(g.uv()["x"]) * g.fill(d), 1.0))
    g.save("rings.pzshad")

The modules: ``types`` (port types and conversions), ``nodes`` (the node catalog and the
sidebar's entries), ``graph`` (``Graph``, ``Node``, ``Variable``), ``compiler`` (graph to
WGSL), ``runtime`` (``Shader``: load, set variables, draw) and ``layout`` (node sizes).
"""

from __future__ import annotations

from . import library, nodes, types
from .compiler import Compiled, compile, resolve_types
from .graph import FORMAT, SUFFIX, VAR_TYPES, Graph, GraphError, Link, Node, NodeRef, Socket, Variable, valid_name
from .graph import load as load_graph
from .nodes import CATEGORIES, PRESETS, TYPES, NodeType, Preset, register
from .runtime import Shader, load, widget


def new(name: str = "shader") -> Graph:
    """A new shader graph with UV feeding a gradient into the Output node: a starting point."""
    g = Graph(name)
    uv = g.add("uv", x=0, y=0)
    grad = g.add("gradient", t=uv["x"], x=240, y=0)
    g.output(grad["color"])
    g.nodes[g.output_node.id].x, g.nodes[g.output_node.id].y = 500, 0  # type: ignore[union-attr]
    g.touch()
    return g


__all__ = [
    "CATEGORIES", "FORMAT", "PRESETS", "SUFFIX", "TYPES", "VAR_TYPES", "Compiled", "Graph", "GraphError", "Link",
    "Node", "NodeRef", "NodeType", "Preset", "Shader", "Socket", "Variable", "compile", "library", "load",
    "load_graph", "new", "nodes", "register", "resolve_types", "types", "valid_name", "widget",
]
