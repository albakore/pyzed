---
title: Shader graphs
description: "Shaders made of nodes (.pzshad): draw them with pz.shader, change their variables from Python, and build or edit graphs in code with pyzed.shading."
sidebar:
  order: 3.7
---

A **shader graph** is a [shader](/pyzed/guides/shaders/) made of nodes instead of WGSL: inputs such as UV and
Time, math, noise, shapes and colors, wired into an Output node. You build it in the designer's
[Shader view](/pyzed/editor/shader-designer/) and save it as a `.pzshad` file; `pyzed.shading` compiles it to the
WGSL that `pz.shader` runs on the GPU, so it is exactly as fast as a hand-written shader.

```python
import pyzed as pz

pz.shader("shaders/fire.pzshad", uniforms={"speed": 2.0}, width=320, height=200)
```

## Drawing a `.pzshad`

`pz.shader` takes the path of a `.pzshad` (a `str` or a `Path`) where it takes WGSL code. `uniforms` sets the
shader's **mutable variables** by name, and the shader's own settings (its fallback color, whether it animates)
apply unless you pass them:

```python
from pathlib import Path

import pyzed as pz

SHADERS = Path(__file__).parent / "shaders"


class Menu(pz.App):
    speed = 1.0

    def view(self):
        return pz.stack([
            pz.shader(SHADERS / "synthwave.pzshad", width="fill", height="fill"),
            pz.slider(0, 3, self.speed, on_change=lambda v: setattr(self, "speed", v)),
        ])
```

Changing a mutable variable costs nothing: the code is compiled once and only the value changes, so a slider or
an animation can drive it at full frame rate.

## Loading and changing variables

`shading.load` returns a `Shader`: the graph plus its own values for the variables. It is cached by path, and it
reloads by itself when the file changes, so saving in the designer updates a running app.

```python
from pyzed import shading

# a shader with the variables speed and tint (mutable) and octaves (a constant)
fire = shading.load("shaders/fire.pzshad")
fire["speed"] = 2.0                  # a mutable variable: no recompiling
fire.set(speed=2.0, tint="#ff8800")  # several at once
fire.set(octaves=6)                  # a constant: the code is built again
fire.variables                       # {"speed": 2.0, "tint": "#ff8800", "octaves": 6}

pz.shader(fire, width=320, height=200)   # or fire.widget(width=320, height=200)
print(fire.wgsl)                          # the generated code
```

| Variable | In the graph | Changing it |
| --- | --- | --- |
| **Mutable** | A uniform, read by the GPU every frame. | Free: `fire["speed"] = 2`. |
| **Constant** | A literal written into the code. | Builds the code again (fine now and then, not every frame). |

Variables can be `float`, `int`, `bool`, `vec2`, `vec3`, `vec4`, `color` (a hex color or a theme token such as
`"accent"`) or `texture` (an image path). A shader takes up to 32 mutable variables and 8 textures.

## Building a graph in code

`shading.Graph` is the same graph the designer edits, with an API that reads like the nodes: call a node type
on the graph to add it, pass inputs as arguments, and pick an output with `node["name"]`. Arithmetic on outputs
adds math nodes for you.

```python
from pyzed import shading

g = shading.Graph("rings")
speed = g.uniform("speed", "float", 1.0, min=0, max=4)    # a mutable variable and a node that reads it

d = g.ring(g.centered_uv()["centered"], radius=0.3, thickness=0.02)
glow = g.glow(d["distance"], radius=0.1)
hue = g.time()["time"] * speed["value"] * 0.1             # Multiply nodes
color = g.hsv_to_rgb(hue, 0.8, 1.0)["rgb"] * glow["value"]
g.output(g.rgba(color, 1.0)["color"])

g.arrange()                     # columns, left to right, as the designer's Arrange
g.save("shaders/rings.pzshad")  # open it in Pyzed Design to keep editing
```

- `g.add("noise", kind="simplex", scale=4)` is the long form; `g.noise(...)`, `g.sin(x)`, `g.multiply(a, b)`
  and every entry of the sidebar work as methods. Keys such as `"func:sin"` or `"math:max"` work in `add`.
- Positional arguments go to the inputs in order; keywords go to inputs or settings by name. A value can be a
  number, a list (a vector), a color, another node's output or a context such as `"@uv"`.
- `node["x"]` is an output; vectors have swizzles (`uv["uv"].x`, `color.xyz`).
- `g.uniform(name, type, value)` and `g.constant(...)` add a variable and a node that reads it; `g.get(name)` adds
  another reader; `g.set_variable(name, value=..., mutable=False)` changes one.
- `g.connect(src, out, dst, inp)` and `g.disconnect(dst, inp)` wire by node id; types are checked and cycles
  refused (`GraphError`).
- `g.compile()` returns the WGSL (`.code`), the uniforms and textures for `pz.shader`, and the problems by node
  (`.errors`); `.check()` also runs the GPU compiler and puts what it finds on the node that wrote the line.

## Nodes that make graphs smaller

| Node | What it does |
| --- | --- |
| **Set value / Get value** | Names a value once and reads it anywhere, without a long wire. |
| **Expression** | Your own WGSL: an expression of `a`, `b`, `c` and `d` (and `uv`, `px`, `size`, `time`), or a function body with `return`. The types of `a`–`d` follow what is wired to them. |
| **Shader function** | Another `.pzshad` used as a function: its mutable variables are inputs, its `uv` input moves or warps it, its outputs are the color. |
| **Reroute** | A point to route a wire around other nodes. |

## In forms and from the command line

The designer's **Shader** control (toolbox → Display) draws a `.pzshad` on a form; its `variables` property
(`{"speed": 2}`) sets the variables, from the Properties panel or from a handler. `pyzed run fire.pzshad` shows a
shader filling a window, with sliders for its mutable variables (press **V**).

## The file format

A `.pzshad` is JSON: the shader's name and description, its variables, its nodes (type, position, inputs and
settings) and its links. It diffs well in git, and an AI agent can write one: the [MCP server](/pyzed/guides/mcp/)
has `list_shader_nodes`, `new_shader` and `check_shader`.

```json
{
 "format": "pyzed.shader/1",
 "name": "glow",
 "variables": [{"name": "speed", "type": "float", "value": 1.0, "mutable": true, "min": 0, "max": 4}],
 "nodes": [{"id": "1", "type": "time", "x": 0, "y": 0}, "..."],
 "links": [{"from": "1", "out": "time", "to": "3", "in": "a"}, "..."]
}
```
