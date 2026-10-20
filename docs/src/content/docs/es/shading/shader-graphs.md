---
title: Grafos de shaders
description: "Shaders hechos de nodos (.pzshad): dibújalos con pz.shader, cambia sus variables desde Python y crea o edita grafos en código con pyzed.shading."
sidebar:
  order: 3.7
---

Un **grafo de shader** es un [shader](/pyzed/es/guides/shaders/) hecho de nodos en lugar de WGSL: entradas como UV
y Time, matemáticas, ruido, formas y colores, conectados a un nodo Output. Lo creas en la
[vista de shaders](/pyzed/es/editor/shader-designer/) del diseñador y lo guardas como archivo `.pzshad`;
`pyzed.shading` lo compila al WGSL que `pz.shader` ejecuta en la GPU, así que es exactamente igual de rápido que un
shader escrito a mano.

```python
import pyzed as pz

pz.shader("shaders/fuego.pzshad", uniforms={"speed": 2.0}, width=320, height=200)
```

## Dibujar un `.pzshad`

`pz.shader` acepta la ruta de un `.pzshad` (un `str` o un `Path`) donde acepta código WGSL. `uniforms` cambia las
**variables mutables** del shader por nombre, y los ajustes del propio shader (su color fallback, si se anima) se
aplican salvo que los pases tú:

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

Cambiar una variable mutable no cuesta nada: el código se compila una vez y solo cambia el valor, así que un
deslizador o una animación pueden moverla a la máxima velocidad de fotogramas.

## Cargar y cambiar variables

`shading.load` devuelve un `Shader`: el grafo más sus propios valores de las variables. Se guarda en caché por
ruta y se recarga solo cuando el archivo cambia, así que guardar en el diseñador actualiza una app en marcha.

```python
from pyzed import shading

# un shader con las variables speed y tint (mutables) y octaves (una constante)
fuego = shading.load("shaders/fuego.pzshad")
fuego["speed"] = 2.0                  # una variable mutable: no recompila
fuego.set(speed=2.0, tint="#ff8800")  # varias a la vez
fuego.set(octaves=6)                  # una constante: se vuelve a generar el código
fuego.variables                       # {"speed": 2.0, "tint": "#ff8800", "octaves": 6}

pz.shader(fuego, width=320, height=200)   # o fuego.widget(width=320, height=200)
print(fuego.wgsl)                          # el código generado
```

| Variable | En el grafo | Cambiarla |
| --- | --- | --- |
| **Mutable** | Un uniform que la GPU lee en cada frame. | Gratis: `fuego["speed"] = 2`. |
| **Constante** | Un literal escrito en el código. | Vuelve a generar el código (bien de vez en cuando, no en cada frame). |

Las variables pueden ser `float`, `int`, `bool`, `vec2`, `vec3`, `vec4`, `color` (un color hex o un token del
tema como `"accent"`) o `texture` (la ruta de una imagen). Un shader admite hasta 32 variables mutables y 8
texturas.

## Crear un grafo en código

`shading.Graph` es el mismo grafo que edita el diseñador, con una API que se lee como los nodos: llama a un tipo de
nodo sobre el grafo para añadirlo, pasa las entradas como argumentos y elige una salida con `nodo["nombre"]`. Las
operaciones aritméticas entre salidas añaden nodos matemáticos por ti.

```python
from pyzed import shading

g = shading.Graph("anillos")
speed = g.uniform("speed", "float", 1.0, min=0, max=4)    # una variable mutable y un nodo que la lee

d = g.ring(g.centered_uv()["centered"], radius=0.3, thickness=0.02)
brillo = g.glow(d["distance"], radius=0.1)
tono = g.time()["time"] * speed["value"] * 0.1             # nodos Multiply
color = g.hsv_to_rgb(tono, 0.8, 1.0)["rgb"] * brillo["value"]
g.output(g.rgba(color, 1.0)["color"])

g.arrange()                       # columnas, de izquierda a derecha, como Arrange del diseñador
g.save("shaders/anillos.pzshad")  # ábrelo en Pyzed Design para seguir editándolo
```

- `g.add("noise", kind="simplex", scale=4)` es la forma larga; `g.noise(...)`, `g.sin(x)`, `g.multiply(a, b)` y
  todas las entradas de la barra funcionan como métodos. Claves como `"func:sin"` o `"math:max"` funcionan en
  `add`.
- Los argumentos posicionales van a las entradas en orden; los de palabra clave van a entradas o ajustes por
  nombre. Un valor puede ser un número, una lista (un vector), un color, la salida de otro nodo o un contexto como
  `"@uv"`.
- `nodo["x"]` es una salida; los vectores tienen swizzles (`uv["uv"].x`, `color.xyz`).
- `g.uniform(nombre, tipo, valor)` y `g.constant(...)` añaden una variable y un nodo que la lee; `g.get(nombre)`
  añade otro lector; `g.set_variable(nombre, value=..., mutable=False)` la cambia.
- `g.connect(origen, salida, destino, entrada)` y `g.disconnect(destino, entrada)` conectan por id de nodo; se
  comprueban los tipos y se rechazan los ciclos (`GraphError`).
- `g.compile()` devuelve el WGSL (`.code`), los uniforms y texturas para `pz.shader` y los problemas por nodo
  (`.errors`); `.check()` también ejecuta el compilador de la GPU y pone lo que encuentra en el nodo que escribió
  la línea.

## Nodos que hacen grafos más pequeños

| Nodo | Qué hace |
| --- | --- |
| **Set value / Get value** | Nombra un valor una vez y lo lee en cualquier parte, sin una conexión larga. |
| **Expression** | Tu propio WGSL: una expresión con `a`, `b`, `c` y `d` (y `uv`, `px`, `size`, `time`), o el cuerpo de una función con `return`. Los tipos de `a`–`d` siguen lo que tengan conectado. |
| **Shader function** | Otro `.pzshad` usado como función: sus variables mutables son entradas, su entrada `uv` lo mueve o lo deforma, sus salidas son el color. |
| **Reroute** | Un punto para llevar una conexión alrededor de otros nodos. |

## En formularios y desde la línea de comandos

El control **Shader** del diseñador (caja de herramientas → Display) dibuja un `.pzshad` en un formulario; su
propiedad `variables` (`{"speed": 2}`) cambia las variables, desde el panel de propiedades o desde un manejador.
`pyzed run fuego.pzshad` muestra un shader ocupando una ventana, con deslizadores para sus variables mutables
(pulsa **V**).

## El formato de archivo

Un `.pzshad` es JSON: el nombre y la descripción del shader, sus variables, sus nodos (tipo, posición, entradas y
ajustes) y sus conexiones. Se compara bien en git, y un agente de IA puede escribir uno: el
[servidor MCP](/pyzed/es/guides/mcp/) tiene `list_shader_nodes`, `new_shader` y `check_shader`.

```json
{
 "format": "pyzed.shader/1",
 "name": "brillo",
 "variables": [{"name": "speed", "type": "float", "value": 1.0, "mutable": true, "min": 0, "max": 4}],
 "nodes": [{"id": "1", "type": "time", "x": 0, "y": 0}, "..."],
 "links": [{"from": "1", "out": "time", "to": "3", "in": "a"}, "..."]
}
```
