"""A custom shader graph built in Python: an aurora with sliders for its variables.

    python examples/tutorial/aurora_graph.py            # show it
    python examples/tutorial/aurora_graph.py --save     # also write shaders/aurora.pzshad

- ``shading.Graph`` is the same graph the Shader view of Pyzed Design edits: calling a node type
  on it (``g.fbm(...)``, ``g.smoothstep(...)``) adds that node, ``node["output"]`` picks an output,
  and ``+``, ``-``, ``*`` and ``/`` on outputs add Math nodes.
- ``g.uniform(...)`` adds a *mutable* variable: the sliders change it every frame without
  recompiling anything.
- ``pz.shader(graph, uniforms=...)`` compiles the graph to WGSL and runs it on the GPU. Without a
  GPU it draws the ``fallback`` gradient.
- ``--save`` writes the graph as a ``.pzshad`` file you can open in Pyzed Design to keep editing.

Walkthrough: https://albakore.github.io/pyzed/tutorials/advanced/shader-graph/
"""

import sys
from pathlib import Path

import pyzed as pz
from pyzed import shading, ui

HERE = Path(__file__).resolve().parent
TINTS = {"Green": "#34d399", "Violet": "#a78bfa", "Blue": "#38bdf8"}


def build_aurora() -> shading.Graph:
    g = shading.Graph("aurora")
    g.description = "Curtains of light drifting over a night sky."

    # Variables: the knobs your Python code (and the sliders) can turn.
    speed = g.uniform("speed", "float", 0.3, min=0, max=2)
    height = g.uniform("height", "float", 0.55, min=0.2, max=0.9)
    tint = g.uniform("tint", "color", "#34d399")

    # 1. Where is this pixel, and what time is it?
    uv = g.uv()
    t = g.time()["time"] * speed

    # 2. Drifting fractal noise, stretched sideways: the curtains.
    p = g.compose(uv["x"] * 3.0 + t, uv["y"] * 0.6 - t * 0.3)["vector"]
    curtains = g.fbm(p, scale=2.5, octaves=5)

    # 3. Keep them in a band near the top, fading toward the ground.
    band = g.smoothstep(height - 0.35, height, 1.0 - uv["y"]) * g.smoothstep(1.0, height, 1.0 - uv["y"])
    light = g.smoothstep(0.35, 0.8, curtains["value"]) * band

    # 4. Colors: a night sky gradient, plus the tint where there is light.
    sky = g.gradient(uv["y"], stops=[[0.0, "#020617"], [1.0, "#0f172a"]])
    glow = g.mix(sky["rgb"], tint * 1.4, light)
    g.output(g.rgba(glow * g.vignette(strength=0.6), 1.0)["color"])

    g.arrange()  # lay the nodes out in columns, as the Arrange button of the Shader view does
    return g


AURORA = build_aurora()


class Aurora(pz.App):
    title = "Aurora"
    size = (760, 480)
    theme = "Pyzed Dark"

    def __init__(self):
        self.speed = 0.3
        self.height = 0.55
        self.tint = "Green"

    def knob(self, label, value, low, high, field):
        return ui.field(label, pz.container(ui.slider(value, lambda v: setattr(self, field, v), min=low, max=high),
                                            width=180))

    def view(self):
        sky = pz.shader(AURORA, uniforms={"speed": self.speed, "height": self.height, "tint": TINTS[self.tint]},
                        width="fill", height="fill", fallback=pz.Gradient(["#020617", "#064e3b"], angle=180))
        panel = pz.container(pz.column([
            ui.label("Aurora", weight="semibold"),
            self.knob("Speed", self.speed, 0, 2, "speed"),
            self.knob("Height", self.height, 0.2, 0.9, "height"),
            ui.field("Tint", ui.segmented(list(TINTS), self.tint,
                                          lambda c: setattr(self, "tint", c))),
        ], spacing=8), padding=14).style(glass=True, radius=12)
        return pz.stack([sky, pz.container(panel, padding=16, width="fill", height="fill",
                                           align_x="start", align_y="end")])


if __name__ == "__main__":
    if "--save" in sys.argv:
        print("wrote", AURORA.save(HERE / "shaders" / "aurora.pzshad"))
    pz.run(Aurora)
