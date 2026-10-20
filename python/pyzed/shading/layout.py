"""How big nodes are on the graph, where their ports sit, and placing nodes in tidy columns.

The editor draws nodes with these sizes, so ``port_position`` is where a wire meets a
port on screen (before panning and zooming).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from .graph import Graph, Node

#: Width of a node.
WIDTH = 200.0
#: Height of a node's title bar.
HEADER = 30.0
#: Height of each row of ports.
ROW = 24.0
#: Height of the preview under the ports.
PREVIEW = 92.0
#: Space under the last row.
PADDING = 8.0
#: The width and height of a Comment.
COMMENT = (220.0, 90.0)


def rows(graph: "Graph", node: "Node") -> int:
    """How many rows of ports a node has: inputs and outputs side by side, plus a row for its setting."""
    inputs, outputs = graph.ports(node)
    return max(len(inputs), len(outputs)) + (1 if has_body(graph, node) else 0)


def has_body(graph: "Graph", node: "Node") -> bool:
    """Whether the node shows a setting under its title (an operation, a value, a variable)."""
    from . import nodes

    nt = nodes.TYPES.get(node.type)
    return bool(nt and nt.params and node.type not in ("comment",))


def shows_preview(graph: "Graph", node: "Node") -> bool:
    """Whether the node has a preview (nodes that make a value, unless it is turned off)."""
    if not node.preview or node.type in ("output", "comment", "reroute"):
        return False
    outputs = graph.ports(node)[1]
    return bool(outputs)


def size(graph: "Graph", node: "Node") -> Tuple[float, float]:
    """The width and height of a node."""
    if node.type == "comment":
        w = float(node.params.get("width", COMMENT[0]) or COMMENT[0])
        h = float(node.params.get("height", COMMENT[1]) or COMMENT[1])
        return w, h
    if node.type == "reroute":
        return 28.0, 28.0
    h = HEADER + rows(graph, node) * ROW + PADDING
    if shows_preview(graph, node):
        h += PREVIEW + 4
    return WIDTH, h


def port_position(graph: "Graph", node: "Node", port: str, output: bool) -> Tuple[float, float]:
    """Where the port ``port`` of ``node`` is, in graph coordinates."""
    if node.type == "reroute":
        return (node.x + (28.0 if output else 0.0), node.y + 14.0)
    inputs, outputs = graph.ports(node)
    names = [p.name for p in (outputs if output else inputs)]
    index = names.index(port) if port in names else 0
    offset = 1 if has_body(graph, node) else 0
    y = node.y + HEADER + (index + offset) * ROW + ROW / 2
    return (node.x + (WIDTH if output else 0.0), y)


def arrange(graph: "Graph", spacing: Tuple[float, float] = (250.0, 30.0)) -> None:
    """Places nodes in columns by their distance from the graph's inputs, lined up with what they read."""
    depth: Dict[str, int] = {}

    def visit(nid: str, trail: Tuple[str, ...] = ()) -> int:
        if nid in depth:
            return depth[nid]
        if nid in trail:
            return 0
        deps = [d for d in graph.dependencies(nid) if d in graph.nodes]
        value = 1 + max((visit(d, trail + (nid,)) for d in deps), default=-1)
        depth[nid] = value
        return value

    for nid in graph.nodes:
        visit(nid)
    # nodes that only feed the next column sit right before it
    columns: Dict[int, List[str]] = {}
    for nid, d in depth.items():
        if graph.nodes[nid].type == "comment":
            continue
        columns.setdefault(d, []).append(nid)
    dx, dy = spacing
    placed_y: Dict[str, float] = {}
    for col in sorted(columns):
        ids = columns[col]

        def anchor(nid: str) -> float:
            ys = [placed_y[s] for s in graph.dependencies(nid) if s in placed_y]
            return sum(ys) / len(ys) if ys else graph.nodes[nid].y

        ids.sort(key=anchor)
        y = 0.0
        for nid in ids:
            node = graph.nodes[nid]
            want = anchor(nid) if col else y
            y = max(y, want)
            node.x = col * dx
            node.y = y
            placed_y[nid] = y
            y += size(graph, node)[1] + dy
