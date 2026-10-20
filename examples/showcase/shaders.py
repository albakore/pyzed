"""A gallery of shader graphs: plasma, a ripple that follows the pointer, a tunnel, a CRT
screen, Voronoi cells and a fire. Each is a ``.pzshad`` file in ``shaders/`` made of nodes
(no WGSL to write): open one in Pyzed Design (``pyzed design shaders/fire.pzshad``) to see
and change its graph.

    python examples/showcase/shaders.py

``pz.shader`` compiles the graph and runs it on the GPU for every pixel, every frame::

    pz.shader("shaders/plasma.pzshad", uniforms={"speed": 2.0}, width=340, height=210)

``uniforms`` sets the shader's mutable variables by name; the slider below changes
``speed`` on every shader without recompiling.
"""

from pathlib import Path

import pyzed as pz
from pyzed import shading

HERE = Path(__file__).parent / "shaders"
NAMES = {"Plasma": "plasma", "Ripple": "ripple", "Tunnel": "tunnel", "CRT": "crt", "Voronoi": "voronoi",
         "Fire": "fire"}
SHADERS = {name: shading.load(HERE / f"{file}.pzshad") for name, file in NAMES.items()}
FALLBACKS = {
    "Plasma": pz.Gradient(["#7c3aed", "#ec4899", "#f59e0b"], angle=45),
    "Ripple": pz.Gradient(["#0c4a6e", "#0891b2"], angle=180),
    "Tunnel": pz.Gradient(["#1e1b4b", "#0e7490"], angle=135),
    "CRT": pz.Gradient(["#ef4444", "#22c55e", "#3b82f6"], angle=90),
    "Voronoi": pz.Gradient(["#111827", "#4c1d95"], angle=135),
    "Fire": pz.Gradient(["#000000", "#b91c1c", "#fbbf24"], angle=180),
}
TINTS = {"Ripple": "#7dd3fc", "Voronoi": "#a78bfa"}


class Shaders(pz.App):
    title = "Shaders"
    size = (1140, 720)
    theme = pz.themes.ONE_DARK

    def __init__(self):
        self.speed = 1.0

    def set_speed(self, value):
        self.speed = value

    def tile(self, name):
        shader = SHADERS[name]
        uniforms = {"speed": self.speed}
        if name in TINTS:
            uniforms["tint"] = TINTS[name]
        art = pz.shader(shader, uniforms=uniforms, width=340, height=210, fallback=FALLBACKS[name])
        label = pz.row([
            pz.text(name, size=14, weight="semibold", color="#ffffff"),
            pz.space(width="fill"),
            pz.text(f"{len(shader.graph.nodes)} nodes", size=11, color="#ffffff88", font="mono"),
        ], width=340, align="center")
        return pz.column([art, label],
                         spacing=8).animate("lift", on="hover")

    def view(self):
        names = list(SHADERS)
        grid = pz.column([pz.row([self.tile(n) for n in names[i:i + 3]], spacing=20) for i in (0, 3)],
                         spacing=22)
        header = pz.row([
            pz.column([
                pz.text("Shaders", size=28, weight="bold", color="#ffffff"),
                pz.text("Node graphs from Pyzed Design, running on the GPU", size=13, color="#ffffffaa"),
            ], spacing=2),
            pz.space(width="fill"),
            pz.text("Speed", size=13, color="#ffffffaa"),
            pz.slider(0.0, 3.0, self.speed, step=0.05, on_change=self.set_speed, width=200),
            pz.text(f"{self.speed:.2f}×", size=13, color="#ffffff", font="mono", width=48),
        ], spacing=12, align="center", width=1060)
        return pz.container(pz.column([header, pz.row(pz.stagger([grid], "fade_in_up"))], spacing=24),
                            width="fill", height="fill", align_x="center", align_y="center").style(
            background="#0b0d14")


if __name__ == "__main__":
    pz.run(Shaders)
