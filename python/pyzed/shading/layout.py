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
    """Places nodes in columns, each right before the first node that reads it, with its wires level."""
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
    readers: Dict[str, List[str]] = {nid: [] for nid in graph.nodes}
    for nid in graph.nodes:
        for dep in graph.dependencies(nid):
            if dep in readers and dep != nid:
                readers[dep].append(nid)
    # a value read only further right moves up to the column before its first reader
    for nid in sorted(depth, key=lambda n: depth[n], reverse=True):
        later = [depth[r] for r in readers[nid] if depth[r] > depth[nid]]
        if later:
            depth[nid] = min(later) - 1
    columns: Dict[int, List[str]] = {}
    for nid, d in depth.items():
        if graph.nodes[nid].type == "comment":
            continue
        columns.setdefault(d, []).append(nid)
    dx, dy = spacing
    placed: Dict[str, float] = {}

    def anchor(nid: str) -> float:
        # level with the inputs it feeds, from right to left
        node = graph.nodes[nid]
        ys = []
        for link in graph.links_from(nid):
            if link.dst in placed:
                reader = graph.nodes[link.dst]
                into = port_position(graph, reader, link.inp, False)[1] - reader.y + placed[link.dst]
                ys.append(into - (port_position(graph, node, link.out, True)[1] - node.y))
        ys += [placed[r] for r in readers[nid] if r in placed and not graph.links_from(nid)]
        return sum(ys) / len(ys) if ys else node.y

    for col in sorted(columns, reverse=True):
        ids = sorted(columns[col], key=anchor)
        wants = [anchor(nid) for nid in ids]
        y = min(wants, default=0.0)
        for nid, want in zip(ids, wants):
            node = graph.nodes[nid]
            y = max(y, want)
            node.x = col * dx
            node.y = y
            placed[nid] = y
            y += size(graph, node)[1] + dy
    if placed:
        top = min(placed.values())
        for nid in placed:
            graph.nodes[nid].y = round(graph.nodes[nid].y - top, 1)
