"""A node editor, like the shader graph: move nodes by their title and connect an output to an
input by dragging a wire between them. Only ports of the same type connect.

    python examples/dnd/node_editor.py

Walkthrough: https://albakore.github.io/pyzed/dnd/tutorials/node-editor/
"""

import pyzed as pz
from pyzed import draw, ui

WIDTH, HEADER, ROW = 170, 32, 26
TYPE_COLORS = {"float": "#e5c07b", "color": "#c678dd", "vec2": "#56b6c2"}

NODES = {
    "uv": {"title": "UV", "x": 30, "y": 60, "inputs": [], "outputs": [("uv", "vec2")]},
    "time": {"title": "Time", "x": 30, "y": 200, "inputs": [], "outputs": [("seconds", "float")]},
    "noise": {"title": "Noise", "x": 260, "y": 80, "inputs": [("uv", "vec2"), ("speed", "float")],
              "outputs": [("value", "float")]},
    "ramp": {"title": "Color ramp", "x": 500, "y": 140, "inputs": [("t", "float")], "outputs": [("color", "color")]},
    "out": {"title": "Output", "x": 720, "y": 220, "inputs": [("color", "color"), ("alpha", "float")], "outputs": []},
}


class NodeEditor(pz.App):
    title = "Node editor"
    size = (980, 560)

    def __init__(self):
        self.nodes = {k: dict(v) for k, v in NODES.items()}
        self.links = [("uv", "uv", "noise", "uv"), ("noise", "value", "ramp", "t")]

    # -- geometry: where the ports are, from the node positions -------------------------------
    def port_at(self, node, name, output):
        n = self.nodes[node]
        ports = n["outputs"] if output else n["inputs"]
        index = [p for p, _ in ports].index(name)
        if output:
            index += len(n["inputs"])
        return (n["x"] + (WIDTH - 6 if output else 6), n["y"] + HEADER + index * ROW + ROW / 2)

    # -- drops ---------------------------------------------------------------------------------
    def move_node(self, event):
        node = self.nodes[event.source]
        node["x"], node["y"] = event.item_x, event.item_y

    def connect(self, event):
        src_node, src_port = event.data
        dst_node, dst_port = event.target.split("/", 2)[1:]
        # An input takes one wire: the new one replaces the old.
        self.links = [link for link in self.links if (link[2], link[3]) != (dst_node, dst_port)]
        self.links.append((src_node, src_port, dst_node, dst_port))

    def disconnect(self, node, port):
        self.links = [link for link in self.links if (link[2], link[3]) != (node, port)]

    # -- view ----------------------------------------------------------------------------------
    def dot(self, kind):
        return pz.container(None, width=12, height=12).style(background=TYPE_COLORS[kind], radius=6,
                                                             border_color="#1e2127", border_width=2)

    def input_port(self, node, name, kind):
        target = pz.droppable(
            self.dot(kind), f"in/{node}/{name}", accepts=f"port:{kind}",
            can_drop=lambda e, n=node: e.data[0] != n,     # no wires from a node to itself
            over_style={"border_color": "#ffffff", "border_width": 2, "radius": 6}, on_drop=self.connect,
        ).on(right_click=lambda n=node, p=name: self.disconnect(n, p))
        return pz.row([target, ui.label(name, size="sm")], spacing=6, align="center", height=ROW)

    def output_port(self, node, name, kind):
        wire = pz.draggable(self.dot(kind), f"out/{node}/{name}", data=(node, name), type=f"port:{kind}",
                            preview="wire", wire_color=TYPE_COLORS[kind], wire_width=2.5)
        return pz.row([pz.space(width="fill"), ui.label(name, size="sm"), wire], spacing=6, align="center",
                      height=ROW)

    def node_view(self, key):
        t = pz.theme.current()
        n = self.nodes[key]
        title = pz.drag_handle(pz.container(ui.label(n["title"], weight="bold", size="sm"), padding=(6, 10),
                                            width="fill", height=HEADER).style(background=t.element, radius=(8, 8, 0, 0)))
        rows = [self.input_port(key, p, k) for p, k in n["inputs"]]
        rows += [self.output_port(key, p, k) for p, k in n["outputs"]]
        body = pz.column([title, *rows], width=WIDTH).style(
            background=t.elevated, radius=8, border_color=t.border, border_width=1)
        node = pz.draggable(body, key, type="node", handle=True, source="hide", lift=1.0, drop_animation=0)
        return pz.pin(node, x=n["x"], y=n["y"])

    def wires(self):
        shapes = []
        for a, ap, b, bp in self.links:
            (x1, y1), (x2, y2) = self.port_at(a, ap, True), self.port_at(b, bp, False)
            kind = dict(self.nodes[a]["outputs"])[ap]
            bend = max(abs(x2 - x1) / 2, 40)
            shapes.append(draw.path([("M", x1, y1), ("C", x1 + bend, y1, x2 - bend, y2, x2, y2)],
                                    stroke=TYPE_COLORS[kind], width=2.5))
        return pz.canvas(shapes, width="fill", height="fill")

    def view(self):
        t = pz.theme.current()
        graph = pz.droppable(
            pz.stack([self.wires(), *[self.node_view(k) for k in self.nodes]]),
            "graph", accepts="node", snap=10, over_style=False, on_drop=self.move_node,
        )
        hint = ui.muted("Drag from an output dot to an input of the same color · right-click an input to unplug it")
        return pz.column([hint, pz.container(graph, width="fill", height="fill").style(background=t.editor, radius=10,
                                                                                         clip=True)],
                         spacing=10, padding=12)


if __name__ == "__main__":
    NodeEditor().run()
