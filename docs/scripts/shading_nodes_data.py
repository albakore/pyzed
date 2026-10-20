"""What the node catalog pages say about each node beyond its ports: what it is for, in plain words, and a tiny
example in Python. Read by ``gen_shading_nodes.py``.

Every example runs after ``from pyzed import shading`` and ``g = shading.Graph("demo")`` and ends with
``g.output(...)``; ``gen_shading_nodes.py --check`` compiles each one, so they stay correct.

``PAGES`` groups the categories of ``pyzed.shading.nodes.CATEGORIES`` into pages of the catalog.
"""

from __future__ import annotations

#: The catalog's pages: slug, English title, Spanish title, English and Spanish descriptions, categories.
PAGES = [
    ("inputs", "Inputs, parameters and constants", "Entradas, parámetros y constantes",
     "The nodes every shader starts from: where the pixel is, the time, the mouse, your own variables and fixed values.",
     "Los nodos de los que parte todo shader: dónde está el píxel, el tiempo, el ratón, tus variables y valores fijos.",
     ("Input", "Parameters", "Constants")),
    ("math", "Math", "Matemáticas",
     "Arithmetic, one-value functions (sin, fract, abs...), mix, clamp, smoothstep and remap: the glue of every shader graph.",
     "Aritmética, funciones de un valor (sin, fract, abs...), mix, clamp, smoothstep y remap: el pegamento de todo grafo.",
     ("Math",)),
    ("vectors-uv", "Vectors and UV", "Vectores y UV",
     "Build and split vectors, measure distances and angles, and move, tile, rotate, twist or bend the coordinates.",
     "Crea y separa vectores, mide distancias y ángulos, y mueve, repite, gira, retuerce o curva las coordenadas.",
     ("Vector", "UV")),
    ("noise-patterns", "Noise and patterns", "Ruido y patrones",
     "Organic randomness (Perlin, simplex, fractal, Voronoi) and regular patterns (checker, stripes, grid, dots, gradients, waves).",
     "Aleatoriedad orgánica (Perlin, simplex, fractal, Voronoi) y patrones regulares (damero, rayas, cuadrícula, puntos, degradados, ondas).",
     ("Noise", "Patterns")),
    ("shapes", "Shapes", "Formas",
     "Circles, boxes, rings, lines, polygons and stars as signed distances, combined and drawn with fill, stroke and glow.",
     "Círculos, cajas, anillos, líneas, polígonos y estrellas como distancias con signo, combinadas y dibujadas con relleno, trazo y brillo.",
     ("Shapes",)),
    ("color-effects", "Color, effects and textures", "Color, efectos y texturas",
     "Gradients, palettes, hue, saturation, blend modes and layers, screen effects (vignette, scanlines, grain) and images.",
     "Degradados, paletas, tono, saturación, modos de fusión y capas, efectos de pantalla (viñeta, líneas de barrido, grano) e imágenes.",
     ("Color", "Effects", "Texture")),
    ("logic-utility", "Logic, variables and utility", "Lógica, variables y utilidades",
     "Comparisons and if/else, named values, reroutes, your own WGSL, other shaders as functions, comments and the Output node.",
     "Comparaciones y si/si no, valores con nombre, desvíos, tu propio WGSL, otros shaders como funciones, comentarios y el nodo Salida.",
     ("Logic", "Variables", "Utility", "Output")),
]

#: What each category is about, shown above its nodes.
CATEGORY_TEXT = {
    "Input": ("Where the pixel being painted is, how big the area is, the time and the mouse. Almost every graph "
              "starts with one of these.",
              "Dónde está el píxel que se pinta, el tamaño del área, el tiempo y el ratón. Casi todo grafo empieza "
              "con uno de estos."),
    "Parameters": ("A **Parameter** node reads one of the shader's variables: the values your Python code (or a "
                   "slider in the Preview tab) changes.",
                   "Un nodo **Parámetro** lee una de las variables del shader: los valores que cambia tu código "
                   "Python (o un deslizador en la pestaña Vista previa)."),
    "Constants": ("Fixed values written into the shader. When a value never changes, a constant is the simplest "
                  "choice; when you want to change it from code, use a variable instead.",
                  "Valores fijos escritos en el shader. Si un valor nunca cambia, una constante es lo más simple; si "
                  "quieres cambiarlo desde código, usa una variable."),
    "Math": ("Every math node works on numbers **and** vectors: with a `vec3` it works on each component (red, green "
             "and blue at once). Their inputs and outputs have the generic type `T`.",
             "Todos los nodos de matemáticas funcionan con números **y** con vectores: con un `vec3` trabajan en cada "
             "componente (rojo, verde y azul a la vez). Sus entradas y salidas tienen el tipo genérico `T`."),
    "Vector": ("Vectors are groups of 2, 3 or 4 numbers: a position (x, y), a color (r, g, b) or a color with alpha "
               "(r, g, b, a). These nodes build, split and measure them.",
               "Los vectores son grupos de 2, 3 o 4 números: una posición (x, y), un color (r, g, b) o un color con "
               "alfa (r, g, b, a). Estos nodos los crean, separan y miden."),
    "UV": ("UV nodes change **where** the next nodes look, not the color: feed their `uv` output into the `uv` (or "
           "`p`) input of a pattern, a noise or a shape to move, repeat, rotate or distort it.",
           "Los nodos UV cambian **dónde** miran los nodos siguientes, no el color: conecta su salida `uv` a la "
           "entrada `uv` (o `p`) de un patrón, un ruido o una forma para moverlo, repetirlo, girarlo o deformarlo."),
    "Noise": ("Noise gives values between 0 and 1 that look random but change smoothly: the base of clouds, fire, "
              "water, marble and terrain.",
              "El ruido da valores entre 0 y 1 que parecen aleatorios pero cambian suavemente: la base de nubes, "
              "fuego, agua, mármol y terrenos."),
    "Patterns": ("Regular patterns, mostly 0 or 1 (black or white). Multiply a color by them, or use them as the "
                 "`t` of a Mix or a Gradient.",
                 "Patrones regulares, casi siempre 0 o 1 (negro o blanco). Multiplica un color por ellos, o úsalos "
                 "como `t` de un Mezclar o un Degradado."),
    "Shapes": ("Shapes are **signed distances** (SDF): each pixel gets its distance to the edge of the shape, "
               "negative inside and positive outside. A distance is not a picture yet: **Fill**, **Stroke** and "
               "**Glow** turn it into a mask from 0 to 1. Distances can be combined (union, subtract, intersect) "
               "before drawing, even with a smooth seam.",
               "Las formas son **distancias con signo** (SDF): cada píxel recibe su distancia al borde de la forma, "
               "negativa dentro y positiva fuera. Una distancia todavía no es una imagen: **Relleno**, **Contorno** y "
               "**Resplandor** la convierten en una máscara de 0 a 1. Las distancias se pueden combinar (unión, resta, "
               "intersección) antes de dibujar, incluso con una unión suave."),
    "Color": ("Colors are `vec3` (r, g, b) or `vec4` (r, g, b, a) with values from 0 to 1, not from 0 to 255: "
              "`(1, 0.5, 0)` is orange.",
              "Los colores son `vec3` (r, g, b) o `vec4` (r, g, b, a) con valores de 0 a 1, no de 0 a 255: "
              "`(1, 0.5, 0)` es naranja."),
    "Effects": ("Screen effects that return a number around 1: multiply your final color by them.",
                "Efectos de pantalla que devuelven un número cercano a 1: multiplica tu color final por ellos."),
    "Texture": ("Images in a shader: add a `texture` variable (an image file) and read its colors.",
                "Imágenes en un shader: añade una variable `texture` (un archivo de imagen) y lee sus colores."),
    "Logic": ("True/false values and choosing between two values. Shaders run on every pixel at once, so prefer "
              "Mix and Smoothstep for soft transitions and keep Select for hard either/or choices.",
              "Valores verdadero/falso y elegir entre dos valores. Los shaders corren en todos los píxeles a la vez: "
              "prefiere Mezclar y Paso suave para transiciones suaves y deja Elegir para elecciones tajantes."),
    "Variables": ("Named values inside the graph: compute something once, name it, and read it anywhere without a "
                  "long wire across the canvas.",
                  "Valores con nombre dentro del grafo: calcula algo una vez, ponle nombre y léelo en cualquier "
                  "lugar sin un cable largo por el lienzo."),
    "Utility": ("Nodes that keep big graphs tidy and let you go beyond the catalog.",
                "Nodos que mantienen ordenados los grafos grandes y te dejan ir más allá del catálogo."),
    "Output": ("Every shader has one Output node: what reaches it is the color of the pixel.",
               "Todo shader tiene un nodo Salida: lo que llega a él es el color del píxel."),
}

#: Per node type: plain-language use (English, Spanish) and an example.
NODES = {
    # -- Input
    "uv": dict(
        en="The most used node. `x` goes from 0 at the left to 1 at the right and `y` from 0 at the top to 1 at "
           "the bottom, whatever the size of the widget. Wire `x` into a Gradient to get a horizontal ramp.",
        es="El nodo más usado. `x` va de 0 a la izquierda a 1 a la derecha e `y` de 0 arriba a 1 abajo, sea cual "
           "sea el tamaño del widget. Conecta `x` a un Degradado para obtener una rampa horizontal.",
        code='uv = g.uv()\ng.output(g.gradient(uv["x"]))'),
    "pixel": dict(
        en="The same as UV but in pixels: use it for things that must keep their size in pixels when the widget "
           "grows, such as scanlines every 3 pixels.",
        es="Como UV pero en píxeles: úsalo para lo que debe mantener su tamaño en píxeles cuando el widget crece, "
           "como líneas cada 3 píxeles.",
        code='px = g.pixel()\nlines = g.fract(px["y"] / 4.0)\ng.output(g.rgba(g.step(0.5, lines), 1.0))'),
    "size": dict(
        en="The width and height of the area in pixels. `aspect` (width ÷ height) keeps circles round on wide "
           "widgets; Centered UV already uses it for you.",
        es="El ancho y el alto del área en píxeles. `aspect` (ancho ÷ alto) mantiene redondos los círculos en "
           "widgets anchos; Centered UV ya lo usa por ti.",
        code='s = g.size()\ng.output(g.rgba(g.fract(s["aspect"]), 1.0))'),
    "time": dict(
        en="Seconds since the app started: anything wired to it moves. `sin` and `cos` swing smoothly between −1 "
           "and 1, perfect for pulses. `scale` speeds it up or slows it down.",
        es="Segundos desde que arrancó la app: todo lo que se conecta a él se mueve. `sin` y `cos` oscilan "
           "suavemente entre −1 y 1, perfectos para pulsos. `scale` lo acelera o lo frena.",
        code='t = g.time(scale=2.0)\npulse = t["sin"] * 0.5 + 0.5\ng.output(g.rgba(g.hsv_to_rgb(0.6, 0.8, pulse), 1.0))'),
    "mouse": dict(
        en="Where the pointer is, in UV (0 to 1). While it is outside the shader, `position` is the center and "
           "`inside` is false. Great for spotlights and hover effects.",
        es="Dónde está el puntero, en UV (0 a 1). Mientras está fuera del shader, `position` es el centro e "
           "`inside` es falso. Ideal para focos y efectos al pasar el ratón.",
        code='m = g.mouse()\nlight = g.radial_gradient(center=m["position"], radius=0.3)\ng.output(g.rgba(light, 1.0))'),
    "centered_uv": dict(
        en="The coordinates to draw shapes with: (0, 0) is the middle and one unit is the height, so a circle stays "
           "round on any widget. `aspect_uv` keeps noise and cells square.",
        es="Las coordenadas para dibujar formas: (0, 0) es el centro y una unidad es la altura, así un círculo "
           "sigue redondo en cualquier widget. `aspect_uv` mantiene cuadrados el ruido y las celdas.",
        code='c = g.centered_uv()\nd = g.length(c["centered"])\ng.output(g.rgba(g.smoothstep(0.4, 0.0, d), 1.0))'),
    # -- Parameters
    "parameter": dict(
        en="Your shader's knobs. `g.uniform(...)` adds a mutable variable and a Parameter node at once; in the "
           "designer, drag a variable from the Outline onto the graph. A `color` variable gives `color`, `rgb` "
           "and `alpha` outputs.",
        es="Los mandos de tu shader. `g.uniform(...)` añade una variable mutable y un nodo Parámetro a la vez; en "
           "el diseñador, arrastra una variable de la Estructura (Outline) al grafo. Una variable `color` da las salidas "
           "`color`, `rgb` y `alpha`.",
        code='tint = g.uniform("tint", "color", "#22d3ee")\nglow = g.radial_gradient(radius=0.6)\ng.output(g.rgba(tint["rgb"] * glow, 1.0))'),
    # -- Constants
    "float": dict(
        en="One fixed number. Most inputs already take a typed value directly, so you only need this node to feed "
           "the same number into several places.",
        es="Un número fijo. La mayoría de las entradas ya aceptan un valor escrito directamente, así que solo "
           "necesitas este nodo para llevar el mismo número a varios sitios.",
        code='half = g.float(0.5)\ng.output(g.rgba(g.compose(half, half, 1.0), 1.0))'),
    "int": dict(en="A fixed whole number, for inputs such as the octaves of Fractal noise.",
                es="Un número entero fijo, para entradas como las octavas de Ruido fractal.",
                code='octaves = g.int(3)\nn = g.fbm(octaves=octaves)\ng.output(g.rgba(n, 1.0))'),
    "bool": dict(en="A fixed true or false, for Select and Logic nodes.",
                 es="Un verdadero o falso fijo, para los nodos Elegir y Lógica.",
                 code='on = g.bool(True)\ng.output(g.rgba(g.select(on, 1.0, 0.2), 1.0))'),
    "vec2": dict(en="Two fixed numbers: a point or a size.", es="Dos números fijos: un punto o un tamaño.",
                 code='center = g.vec2([0.3, 0.5])\ng.output(g.rgba(g.radial_gradient(center=center, radius=0.3), 1.0))'),
    "vec3": dict(en="Three fixed numbers: often an RGB color written as numbers from 0 to 1.",
                 es="Tres números fijos: a menudo un color RGB escrito con números de 0 a 1.",
                 code='orange = g.vec3([1.0, 0.5, 0.0])\ng.output(g.rgba(orange, 1.0))'),
    "vec4": dict(en="Four fixed numbers: a color with alpha, as numbers.",
                 es="Cuatro números fijos: un color con alfa, en números.",
                 code='g.output(g.vec4([0.1, 0.2, 0.4, 1.0]))'),
    "color": dict(en="A fixed color picked with the color picker (or written as `#rrggbb`).",
                  es="Un color fijo elegido con el selector de color (o escrito como `#rrggbb`).",
                  code='g.output(g.color("#7c3aed"))'),
    "math_constants": dict(
        en="π, τ (2π), e and φ, so you don't have to type 3.14159. Multiply a 0..1 value by τ to get a full turn in "
           "radians.",
        es="π, τ (2π), e y φ, para no escribir 3.14159. Multiplica un valor 0..1 por τ para obtener una vuelta "
           "completa en radianes.",
        code='k = g.math_constants()\nwave = g.sin(g.uv()["x"] * k["tau"] * 3.0) * 0.5 + 0.5\ng.output(g.rgba(wave, 1.0))'),
    # -- Math
    "math": dict(
        en="Two values in, one out. In Python you rarely add it by hand: `a + b`, `a * 2` or `a ** 2` on ports add "
           "Math nodes for you. Each operation is its own entry in the sidebar (Add, Multiply, Step...).",
        es="Dos valores entran, uno sale. En Python casi nunca lo añades a mano: `a + b`, `a * 2` o `a ** 2` "
           "sobre puertos añaden nodos Matemáticas por ti. Cada operación es su propia entrada en la barra lateral "
           "(Sumar, Multiplicar, Escalón...).",
        code='uv = g.uv()\nstripes = g.step(0.5, g.fract(uv["x"] * 8.0))\ng.output(g.rgba(stripes * 0.8 + 0.1, 1.0))'),
    "func": dict(
        en="One value in, one out: rounding, roots, powers, trigonometry and more. Each function is its own entry "
           "in the sidebar (Sin, Fract, Abs...) and a method in Python (`g.sin(x)`, `g.fract(x)`).",
        es="Un valor entra, uno sale: redondeos, raíces, potencias, trigonometría y más. Cada función es su "
           "propia entrada en la barra lateral (Sin, Fract, Abs...) y un método en Python (`g.sin(x)`, "
           "`g.fract(x)`).",
        code='t = g.time()["time"]\nwave = g.abs(g.sin(g.uv()["x"] * 10.0 + t))\ng.output(g.rgba(wave, 1.0))'),
    "mix": dict(
        en="Blends two values: `t` = 0 gives `a`, 1 gives `b`, 0.5 half of each. The node you will use most to "
           "combine colors.",
        es="Mezcla dos valores: `t` = 0 da `a`, 1 da `b`, 0.5 mitad de cada uno. El nodo que más usarás para "
           "combinar colores.",
        code='uv = g.uv()\nsky = g.mix([0.1, 0.2, 0.5], [0.9, 0.6, 0.3], uv["y"])\ng.output(g.rgba(sky, 1.0))'),
    "clamp": dict(
        en="Keeps a value inside a range, so a bright spot never goes over 1 or a dark one under 0.",
        es="Mantiene un valor dentro de un rango, para que un punto brillante nunca pase de 1 ni uno oscuro baje "
           "de 0.",
        code='v = g.uv()["x"] * 2.0 - 0.5\ng.output(g.rgba(g.clamp(v, 0.0, 1.0), 1.0))'),
    "smoothstep": dict(
        en="A soft threshold: 0 below `edge0`, 1 above `edge1`, and a smooth curve between. Use it to turn a "
           "distance or a noise into a soft-edged mask.",
        es="Un umbral suave: 0 por debajo de `edge0`, 1 por encima de `edge1` y una curva suave entre ambos. "
           "Úsalo para convertir una distancia o un ruido en una máscara de borde suave.",
        code='n = g.noise(scale=6.0)\nmask = g.smoothstep(0.45, 0.55, n)\ng.output(g.rgba(mask, 1.0))'),
    "remap": dict(
        en="Moves a value from one range to another: −1..1 (a sine) to 0..1 (a color), or 0..1 to 0.2..0.8.",
        es="Pasa un valor de un rango a otro: de −1..1 (un seno) a 0..1 (un color), o de 0..1 a 0.2..0.8.",
        code='s = g.time()["sin"]\nv = g.remap(s, -1.0, 1.0, 0.2, 0.8)\ng.output(g.rgba(v, 1.0))'),
    "multiply_add": dict(
        en="`a × b + c` in one node: scale and shift a value, such as `sin × 0.5 + 0.5` to bring −1..1 into 0..1.",
        es="`a × b + c` en un solo nodo: escala y desplaza un valor, como `sin × 0.5 + 0.5` para llevar −1..1 a "
           "0..1.",
        code='s = g.time()["sin"]\ng.output(g.rgba(g.multiply_add(s, 0.5, 0.5), 1.0))'),
    # -- Vector
    "compose": dict(
        en="Builds a vector from separate numbers: three values into an RGB color, two into a point. The `type` "
           "setting picks vec2, vec3 or vec4 (the sidebar has *Compose vec2* and *Compose vec4* too).",
        es="Construye un vector a partir de números sueltos: tres valores en un color RGB, dos en un punto. El "
           "ajuste `type` elige vec2, vec3 o vec4 (la barra lateral también tiene *Componer vec2* y "
           "*Componer vec4*).",
        code='uv = g.uv()\nrgb = g.compose(uv["x"], uv["y"], 0.5)\ng.output(g.rgba(rgb, 1.0))'),
    "decompose": dict(
        en="Splits a vector into its components: `x`, `y`, `z`, `w` (the red, green, blue and alpha of a color).",
        es="Separa un vector en sus componentes: `x`, `y`, `z`, `w` (el rojo, verde, azul y alfa de un color).",
        code='c = g.color("#f97316")\nparts = g.decompose(c)\ng.output(g.rgba(parts["x"], 1.0))'),
    "swizzle": dict(
        en="Picks and reorders components with a mask: `yx` swaps x and y, `rgb` drops alpha, `xxx` repeats one. "
           "In Python, `port.yx` or `port.rgb` adds it for you.",
        es="Elige y reordena componentes con una máscara: `yx` intercambia x e y, `rgb` quita el alfa, `xxx` "
           "repite uno. En Python, `puerto.yx` o `puerto.rgb` lo añade por ti.",
        code='uv = g.uv()["uv"]\ng.output(g.rgba(g.compose(uv.y, uv.x, 0.0), 1.0))'),
    "dot": dict(
        en="The dot product: how much two directions point the same way (1 same, 0 square, −1 opposite). Also "
           "`p · p` is the squared length.",
        es="El producto escalar: cuánto apuntan dos direcciones hacia el mismo lado (1 igual, 0 en ángulo recto, "
           "−1 opuestas). `p · p` es la longitud al cuadrado.",
        code='p = g.uv()["uv"] - 0.5\nd = g.dot(p, p)\ng.output(g.rgba(1.0 - d * 4.0, 1.0))'),
    "cross": dict(
        en="The cross product of two 3D vectors: a direction perpendicular to both. Mostly for lighting tricks.",
        es="El producto vectorial de dos vectores 3D: una dirección perpendicular a ambos. Sobre todo para "
           "trucos de iluminación.",
        code='n = g.cross([1.0, 0.0, 0.0], [0.0, 1.0, 0.0])\ng.output(g.rgba(n, 1.0))'),
    "length": dict(
        en="How long a vector is. The length of Centered UV is the distance to the center: a circle in one node.",
        es="Lo largo que es un vector. La longitud de UV centrado es la distancia al centro: un círculo en un nodo.",
        code='d = g.length(g.centered_uv()["centered"])\ng.output(g.rgba(1.0 - d, 1.0))'),
    "distance": dict(
        en="How far apart two points are. By default `a` is the pixel's UV, so it measures from the pixel to `b`.",
        es="A qué distancia están dos puntos. Por defecto `a` es el UV del píxel, así que mide del píxel a `b`.",
        code='d = g.distance(b=[0.5, 0.5])\ng.output(g.rgba(g.smoothstep(0.3, 0.0, d), 1.0))'),
    "normalize": dict(
        en="The same direction with a length of 1: for directions, light vectors and reflections.",
        es="La misma dirección con longitud 1: para direcciones, vectores de luz y reflejos.",
        code='n = g.normalize(g.uv()["uv"] - 0.5)\ng.output(g.rgba(g.compose(n.x, n.y, 0.5) * 0.5 + 0.5, 1.0))'),
    "reflect": dict(
        en="Bounces direction `i` off a surface that faces `n`, like a ball off a wall.",
        es="Hace rebotar la dirección `i` en una superficie orientada hacia `n`, como una pelota en una pared.",
        code='r = g.reflect(g.uv()["uv"] - 0.5, [0.0, 1.0])\ng.output(g.rgba(g.compose(r.x, r.y, 0.5) + 0.5, 1.0))'),
    "polar": dict(
        en="Distance and angle around a center: the key to radial things such as radar sweeps, pie charts, sun "
           "rays and spirals. `angle01` goes 0..1 around the circle.",
        es="Distancia y ángulo alrededor de un centro: la clave de lo radial, como barridos de radar, gráficos "
           "de tarta, rayos de sol y espirales. `angle01` va de 0 a 1 alrededor del círculo.",
        code='p = g.polar()\nrays = g.step(0.5, g.fract(p["angle01"] * 12.0))\ng.output(g.rgba(rays, 1.0))'),
    # -- UV
    "tiling_offset": dict(
        en="Repeats and moves what comes next: `tiling` (2, 2) shows it twice in each direction, `offset` slides "
           "it.",
        es="Repite y mueve lo que viene después: `tiling` (2, 2) lo muestra dos veces en cada dirección, `offset` "
           "lo desplaza.",
        code='uv = g.tiling_offset(tiling=[4.0, 4.0])\ng.output(g.rgba(g.fract(uv["uv"]).x, 1.0))'),
    "scroll": dict(
        en="Moves the coordinates over time: wire it before a noise or a pattern to make it drift like clouds or "
           "a conveyor belt.",
        es="Mueve las coordenadas con el tiempo: ponlo antes de un ruido o un patrón para que se desplace como "
           "nubes o una cinta transportadora.",
        code='uv = g.scroll(speed=[0.1, 0.0])\nn = g.fbm(uv["uv"], scale=3.0)\ng.output(g.rgba(n, 1.0))'),
    "rotate": dict(
        en="Turns the coordinates around `center` by `angle` radians (wire Time into it to spin).",
        es="Gira las coordenadas alrededor de `center` `angle` radianes (conecta el Tiempo para que gire solo).",
        code='uv = g.rotate(angle=g.time()["time"])\ns = g.stripes(uv["uv"], count=8.0)\ng.output(g.rgba(s, 1.0))'),
    "twirl": dict(
        en="Twists the coordinates around a center, more the farther away: whirlpools and portals.",
        es="Retuerce las coordenadas alrededor de un centro, más cuanto más lejos: remolinos y portales.",
        code='uv = g.twirl(strength=8.0)\nc = g.checker(uv["uv"], cells=[8.0, 8.0])\ng.output(g.rgba(c, 1.0))'),
    "pixelate": dict(
        en="Snaps the coordinates to a grid of cells, so whatever comes next looks like pixel art.",
        es="Ajusta las coordenadas a una cuadrícula de celdas, así lo que viene después parece pixel art.",
        code='uv = g.pixelate(cells=[24.0, 16.0])\ng.output(g.gradient(g.noise(uv["uv"], scale=4.0)))'),
    "barrel": dict(
        en="Bends the coordinates like the curved glass of an old CRT. Multiply the color by `inside` to black out "
           "the corners that fall off the screen.",
        es="Curva las coordenadas como el cristal de un CRT antiguo. Multiplica el color por `inside` para "
           "oscurecer las esquinas que se salen de la pantalla.",
        code='b = g.barrel(amount=0.3)\nc = g.checker(b["uv"], cells=[10.0, 8.0])\ng.output(g.rgba(c * b["inside"], 1.0))'),
    "kaleidoscope": dict(
        en="Mirrors the coordinates into `segments` slices around a center, like a kaleidoscope.",
        es="Refleja las coordenadas en `segments` porciones alrededor de un centro, como un caleidoscopio.",
        code='uv = g.kaleidoscope(segments=8.0)\nn = g.noise(uv["uv"], scale=6.0)\ng.output(g.rgba(g.palette(n), 1.0))'),
    "flip": dict(
        en="Mirrors the coordinates horizontally (`x`), vertically (`y`) or both.",
        es="Refleja las coordenadas en horizontal (`x`), en vertical (`y`) o en ambas.",
        code='uv = g.flip(axis="y")\ng.output(g.gradient(uv["uv"].y))'),
    "repeat": dict(
        en="Repeats space in cells: draw one shape and get a whole grid of them. `cell` tells which cell a pixel "
           "is in, to give each copy its own color.",
        es="Repite el espacio en celdas: dibuja una forma y obtén una cuadrícula entera. `cell` dice en qué celda "
           "está el píxel, para dar a cada copia su color.",
        code='r = g.repeat(cell=[0.25, 0.25])\nd = g.circle(r["p"], radius=0.08)\ng.output(g.rgba(g.fill(d), 1.0))'),
    # -- Noise
    "noise": dict(
        en="Smooth randomness from 0 to 1. **Perlin** is the classic, **simplex** looks more natural, **value** is "
           "blockier and cheaper. `scale` is how many bumps fit across.",
        es="Aleatoriedad suave de 0 a 1. **Perlin** es la clásica, **simplex** se ve más natural, **value** es "
           "más cuadrada y más barata. `scale` es cuántas ondulaciones caben.",
        code='n = g.noise(scale=5.0, kind="simplex")\ng.output(g.rgba(n, 1.0))'),
    "fbm": dict(
        en="Several layers of noise, each finer and fainter: the look of clouds, smoke and mountains. More "
           "`octaves` add detail (and cost).",
        es="Varias capas de ruido, cada una más fina y más tenue: el aspecto de nubes, humo y montañas. Más "
           "`octaves` añaden detalle (y coste).",
        code='n = g.fbm(scale=3.0, octaves=6)\ng.output(g.gradient(n))'),
    "voronoi": dict(
        en="Cells around random points, like cracked mud, crystals or giraffe skin. `edge` is small near the "
           "borders, `cell` is a random number per cell (great for a color each). `phase` moves the points.",
        es="Celdas alrededor de puntos aleatorios, como barro agrietado, cristales o piel de jirafa. `edge` es "
           "pequeño cerca de los bordes y `cell` es un número aleatorio por celda (ideal para un color por "
           "celda). `phase` mueve los puntos.",
        code='v = g.voronoi(scale=6.0)\ncolor = g.palette(v["cell"])\ng.output(g.rgba(color * g.smoothstep(0.0, 0.05, v["edge"]), 1.0))'),
    "white_noise": dict(
        en="A different random number for each input value, with no smoothness: TV static, sparkles, dithering.",
        es="Un número aleatorio distinto para cada valor de entrada, sin suavidad: estática de TV, destellos, "
           "tramado.",
        code='n = g.white_noise()\ng.output(g.rgba(n, 1.0))'),
    "random": dict(
        en="A random number for a seed: the same seed always gives the same number. Feed it a cell number to give "
           "each cell its own value.",
        es="Un número aleatorio para una semilla: la misma semilla da siempre el mismo número. Pásale el número "
           "de una celda para dar a cada celda su propio valor.",
        code='r = g.repeat(cell=[0.2, 0.2])\nv = g.random(r["cell"].x * 7.0 + r["cell"].y)\ng.output(g.rgba(v, 1.0))'),
    # -- Patterns
    "checker": dict(en="A checkerboard: 0 and 1 in alternating squares.",
                    es="Un damero: 0 y 1 en cuadros alternos.",
                    code='c = g.checker(cells=[8.0, 8.0])\ng.output(g.rgba(g.mix(0.2, 0.9, c), 1.0))'),
    "stripes": dict(en="Parallel stripes at any angle; `width` is how much of each stripe is white.",
                    es="Rayas paralelas en cualquier ángulo; `width` es cuánto de cada raya es blanco.",
                    code='s = g.stripes(count=12.0, angle=0.785)\ng.output(g.rgba(s, 1.0))'),
    "grid": dict(en="Thin grid lines: graph paper, blueprints and synthwave floors.",
                 es="Líneas finas de cuadrícula: papel milimetrado, planos y suelos synthwave.",
                 code='l = g.grid(cells=[10.0, 10.0], thickness=0.05)\ng.output(g.rgba(g.mix([0.05, 0.05, 0.15], [0.2, 0.8, 1.0], l), 1.0))'),
    "dots": dict(en="A grid of round dots: polka dots and halftone looks.",
                 es="Una cuadrícula de puntos redondos: lunares y aspecto de trama de imprenta.",
                 code='d = g.dots(cells=[12.0, 12.0], radius=0.25)\ng.output(g.rgba(d, 1.0))'),
    "linear_gradient": dict(
        en="0 to 1 across the area in a direction (`angle` in radians, 0 is left to right).",
        es="De 0 a 1 a lo ancho del área en una dirección (`angle` en radianes, 0 es de izquierda a derecha).",
        code='t = g.linear_gradient(angle=1.57)\ng.output(g.gradient(t))'),
    "radial_gradient": dict(
        en="1 in the center fading to 0 at `radius`: spotlights, soft glows and vignettes.",
        es="1 en el centro que se desvanece a 0 en `radius`: focos, brillos suaves y viñetas.",
        code='r = g.radial_gradient(radius=0.5)\ng.output(g.rgba(g.compose(r, r * 0.6, 0.2), 1.0))'),
    "wave": dict(
        en="A repeating wave from 0 to 1 in four shapes: **sine** (smooth), **triangle**, **square** (on/off, "
           "blinking) and **sawtooth** (ramp). With the default `x` (time) it animates; wire a UV coordinate to "
           "get bands.",
        es="Una onda repetida de 0 a 1 en cuatro formas: **sine** (suave), **triangle**, **square** "
           "(encendido/apagado, parpadeo) y **sawtooth** (rampa). Con la `x` por defecto (el tiempo) se anima; "
           "conecta una coordenada UV para obtener bandas.",
        code='w = g.wave(g.uv()["x"], frequency=6.0, shape="triangle")\ng.output(g.rgba(w, 1.0))'),
    # -- Shapes
    "circle": dict(
        en="A circle around `center` with a `radius` (in units of the height). Draw it with Fill, Stroke or Glow.",
        es="Un círculo alrededor de `center` con un `radius` (en unidades de la altura). Dibújalo con Relleno, "
           "Contorno o Resplandor.",
        code='d = g.circle(radius=0.3)\ng.output(g.rgba(g.fill(d), 1.0))'),
    "box": dict(en="A rectangle of `size`, with corners rounded by `radius`: cards, buttons, panels.",
                es="Un rectángulo de tamaño `size`, con esquinas redondeadas por `radius`: tarjetas, botones, paneles.",
                code='d = g.box(size=[0.8, 0.5], radius=0.08)\ng.output(g.rgba(g.fill(d), 1.0))'),
    "ring": dict(en="A ring (a donut outline) of `radius` and `thickness`: loaders, targets, halos.",
                 es="Un anillo de `radius` y `thickness`: indicadores de carga, dianas, halos.",
                 code='d = g.ring(radius=0.3, thickness=0.04)\ng.output(g.rgba(g.fill(d), 1.0))'),
    "segment": dict(en="A line from `a` to `b` with round ends and a `thickness`.",
                    es="Una línea de `a` a `b` con extremos redondeados y un grosor `thickness`.",
                    code='d = g.segment(a=[-0.4, -0.2], b=[0.4, 0.2], thickness=0.05)\ng.output(g.rgba(g.fill(d), 1.0))'),
    "polygon": dict(en="A regular polygon with `sides` corners: triangles, hexagons, octagons.",
                    es="Un polígono regular de `sides` esquinas: triángulos, hexágonos, octógonos.",
                    code='d = g.polygon(radius=0.35, sides=6.0)\ng.output(g.rgba(g.fill(d), 1.0))'),
    "star": dict(en="A star with `points` tips; `inner` is how deep the valleys between tips are.",
                 es="Una estrella de `points` puntas; `inner` es la profundidad de los valles entre puntas.",
                 code='d = g.star(radius=0.4, points=5.0, inner=0.45)\ng.output(g.rgba(g.fill(d), 1.0))'),
    "sdf_op": dict(
        en="Combines two shapes before drawing them: **Union** joins them, **Subtract shape** cuts `b` out of `a`, "
           "**Intersect** keeps the overlap. `smooth` above 0 melts the seam, like two drops of water merging.",
        es="Combina dos formas antes de dibujarlas: **Unión** las une, **Restar forma** recorta `b` de `a` e "
           "**Intersecar** deja la parte común. `smooth` mayor que 0 funde la unión, como dos gotas de agua.",
        code='a = g.circle(center=[-0.15, 0.0], radius=0.25)\nb = g.circle(center=[0.15, 0.0], radius=0.25)\nd = g.union(a, b, smooth=0.1)\ng.output(g.rgba(g.fill(d), 1.0))'),
    "fill": dict(
        en="Draws a shape solid: 1 inside, 0 outside, with an antialiased edge `softness` pixels wide. Raise "
           "`softness` for a blurry edge.",
        es="Dibuja una forma rellena: 1 dentro, 0 fuera, con un borde suavizado de `softness` píxeles. Sube "
           "`softness` para un borde difuso.",
        code='d = g.box(size=[0.6, 0.6], radius=0.1)\ng.output(g.rgba(g.fill(d, softness=8.0), 1.0))'),
    "stroke": dict(en="Draws only the outline of a shape, `width` wide.",
                   es="Dibuja solo el contorno de una forma, de ancho `width`.",
                   code='d = g.star(radius=0.4)\ng.output(g.rgba(g.stroke(d, width=0.02), 1.0))'),
    "glow": dict(
        en="A soft light around a shape that fades over `radius`: neon signs and halos. Add it to a Fill for a "
           "solid shape with a glow.",
        es="Una luz suave alrededor de una forma que se desvanece en `radius`: letreros de neón y halos. Súmalo "
           "a un Relleno para una forma sólida con brillo.",
        code='d = g.ring(radius=0.3, thickness=0.01)\nlight = g.glow(d, radius=0.1)\ng.output(g.rgba(g.compose(0.1, 0.8, 1.0) * light, 1.0))'),
    # -- Color
    "hsv_to_rgb": dict(
        en="A color from hue (0..1 around the color wheel: red, yellow, green, cyan, blue, magenta, red), "
           "saturation and value. Wire Time into the hue for a rainbow that cycles.",
        es="Un color a partir del tono (0..1 alrededor de la rueda: rojo, amarillo, verde, cian, azul, magenta, "
           "rojo), la saturación y el valor. Conecta el Tiempo al tono para un arcoíris que gira.",
        code='uv = g.uv()\ng.output(g.rgba(g.hsv_to_rgb(uv["x"], 0.8, 1.0), 1.0))'),
    "rgb_to_hsv": dict(en="Splits a color into hue, saturation and value, to change one of them.",
                       es="Separa un color en tono, saturación y valor, para cambiar uno de ellos.",
                       code='hsv = g.rgb_to_hsv([1.0, 0.5, 0.0])\ng.output(g.rgba(g.hsv_to_rgb(hsv["h"], 0.3, hsv["v"]), 1.0))'),
    "hue_shift": dict(en="Turns the hue of a color around the wheel (`shift` 1 is a full turn).",
                      es="Gira el tono de un color por la rueda (`shift` 1 es una vuelta completa).",
                      code='g.output(g.rgba(g.hue_shift([1.0, 0.2, 0.2], g.time(scale=0.2)["time"]), 1.0))'),
    "saturation": dict(en="More (above 1) or less (below 1) colorful; 0 is gray.",
                       es="Más (por encima de 1) o menos (por debajo de 1) colorido; 0 es gris.",
                       code='c = g.palette(g.uv()["x"])\ng.output(g.rgba(g.saturation(c, 0.4), 1.0))'),
    "brightness_contrast": dict(en="Lighter or darker, and more or less contrast, like a photo editor.",
                                es="Más claro u oscuro, y más o menos contraste, como en un editor de fotos.",
                                code='c = g.palette(g.uv()["x"])\ng.output(g.rgba(g.brightness_contrast(c, 0.1, 1.4), 1.0))'),
    "luminance": dict(en="How bright a color looks to the eye, as one number from 0 to 1.",
                      es="Lo brillante que parece un color al ojo, como un número de 0 a 1.",
                      code='l = g.luminance([0.2, 0.7, 0.3])\ng.output(g.rgba(l, 1.0))'),
    "grayscale": dict(en="The color in shades of gray (black and white).",
                      es="El color en tonos de gris (blanco y negro).",
                      code='c = g.palette(g.uv()["x"])\ng.output(g.rgba(g.grayscale(c), 1.0))'),
    "invert": dict(en="The negative of a color (1 − color); alpha is kept.",
                   es="El negativo de un color (1 − color); el alfa se mantiene.",
                   code='c = g.gradient(g.uv()["x"])\ng.output(g.invert(c["color"]))'),
    "gamma": dict(en="Brightens (above 1) or darkens (below 1) the midtones without touching black and white.",
                  es="Aclara (por encima de 1) u oscurece (por debajo de 1) los medios tonos sin tocar el blanco y "
                     "el negro.",
                  code='v = g.uv()["x"]\ng.output(g.rgba(g.gamma(g.compose(v, v, v), 2.2), 1.0))'),
    "posterize": dict(en="Keeps only a few steps of each color: cel shading and retro looks.",
                      es="Deja solo unos pocos escalones de cada color: sombreado cel y aspecto retro.",
                      code='c = g.palette(g.uv()["x"])\ng.output(g.rgba(g.posterize(c, 4.0), 1.0))'),
    "blend": dict(
        en="Blends `layer` over `base` like the layer modes of an image editor: normal, multiply, screen, overlay, "
           "add, subtract, difference, darken, lighten, soft light, color dodge and color burn.",
        es="Mezcla `layer` sobre `base` como los modos de capa de un editor de imágenes: normal, multiply, "
           "screen, overlay, add, subtract, difference, darken, lighten, soft light, color dodge y color burn.",
        code='base = g.gradient(g.uv()["y"])\nclouds = g.fbm(scale=3.0)\nlayer = g.compose(clouds, clouds, clouds)\ng.output(g.rgba(g.blend(base["rgb"], layer, 0.8, mode="screen"), 1.0))'),
    "palette": dict(
        en="Turns a number from 0 to 1 into a smooth, rainbow-like color with a cosine formula. Change `d` to "
           "shift the colors; it is the quickest way to color noise.",
        es="Convierte un número de 0 a 1 en un color suave tipo arcoíris con una fórmula de cosenos. Cambia `d` "
           "para desplazar los colores; es la forma más rápida de colorear un ruido.",
        code='n = g.noise(scale=4.0)\ng.output(g.rgba(g.palette(n), 1.0))'),
    "gradient": dict(
        en="A color ramp you edit with stops: the color at `t` between the stops. In the designer you drag the "
           "stops; in Python pass `stops=[[position, color], ...]`.",
        es="Una rampa de color que editas con paradas: el color en `t` entre las paradas. En el diseñador "
           "arrastras las paradas; en Python pasa `stops=[[posición, color], ...]`.",
        code='ramp = g.gradient(g.uv()["x"], stops=[[0.0, "#0f172a"], [0.6, "#7c3aed"], [1.0, "#f472b6"]])\ng.output(ramp)'),
    "rgba": dict(en="Joins an RGB color and an opacity into the `vec4` the Output wants.",
                 es="Une un color RGB y una opacidad en el `vec4` que quiere la Salida.",
                 code='g.output(g.rgba([0.2, 0.6, 1.0], 0.5))'),
    "layer": dict(en="Puts `front` over `back` using front's alpha, like stacking two layers.",
                  es="Pone `front` sobre `back` usando el alfa de front, como apilar dos capas.",
                  code='back = g.gradient(g.uv()["y"])\nspot = g.rgba([1.0, 1.0, 1.0], g.fill(g.circle(radius=0.2)))\ng.output(g.layer(back["color"], spot))'),
    # -- Effects
    "vignette": dict(en="Darkens toward the corners, drawing the eye to the center.",
                     es="Oscurece hacia las esquinas y lleva la mirada al centro.",
                     code='c = g.gradient(g.uv()["x"])\ng.output(g.rgba(c["rgb"] * g.vignette(strength=0.9), 1.0))'),
    "scanlines": dict(en="The horizontal lines of an old TV; `speed` makes them roll.",
                      es="Las líneas horizontales de un televisor antiguo; `speed` las hace desplazarse.",
                      code='c = g.gradient(g.uv()["y"])\ng.output(g.rgba(c["rgb"] * g.scanlines(spacing=3.0, strength=0.3), 1.0))'),
    "grain": dict(en="Random speckles that change every frame, like film.",
                  es="Motas aleatorias que cambian en cada fotograma, como en una película.",
                  code='c = g.gradient(g.uv()["x"])\ng.output(g.rgba(c["rgb"] * g.grain(strength=0.15), 1.0))'),
    # -- Texture
    "sample_texture": dict(
        en="Reads the color of an image at a UV. Add a `texture` variable whose value is an image path (relative "
           "to the `.pzshad`), wire it into `texture`, and warp the UV first for ripples or pixelation.",
        es="Lee el color de una imagen en un UV. Añade una variable `texture` cuyo valor sea la ruta de una "
           "imagen (relativa al `.pzshad`), conéctala a `texture` y deforma antes el UV para ondas o pixelado.",
        code='photo = g.uniform("photo", "texture", "photo.png")\nuv = g.pixelate(cells=[40.0, 30.0])\ng.output(g.sample_texture(photo, uv["uv"]))'),
    # -- Logic
    "compare": dict(en="Compares `a` and `b` (`<`, `<=`, `>`, `>=`, `==`, `!=`) and gives true or false.",
                    es="Compara `a` y `b` (`<`, `<=`, `>`, `>=`, `==`, `!=`) y da verdadero o falso.",
                    code='left = g.compare(g.uv()["x"], 0.5, op="<")\ng.output(g.rgba(g.select(left, 1.0, 0.2), 1.0))'),
    "select": dict(en="If `condition` is true, `a` (then); otherwise `b` (else).",
                   es="Si `condition` es verdadero, `a` (entonces); si no, `b` (si no).",
                   code='inside = g.mouse()["inside"]\ng.output(g.rgba(g.select(inside, [0.2, 0.8, 0.4], [0.3, 0.3, 0.3]), 1.0))'),
    "logic": dict(en="`and`, `or`, `xor` and `not` of true/false values.",
                  es="`and`, `or`, `xor` y `not` de valores verdadero/falso.",
                  code='uv = g.uv()\nboth = g.logic(g.compare(uv["x"], 0.5, op=">"), g.compare(uv["y"], 0.5, op=">"), op="and")\ng.output(g.rgba(g.select(both, 1.0, 0.0), 1.0))'),
    # -- Variables
    "set_var": dict(
        en="Gives a value a name. Any **Get value** with the same name reads it, so you can reuse it far away "
           "without a wire crossing the whole canvas.",
        es="Da nombre a un valor. Cualquier **Leer valor** con el mismo nombre lo lee, así puedes reutilizarlo "
           "lejos sin un cable que cruce todo el lienzo.",
        code='g.set_var(g.noise(scale=4.0), name="n")\nn = g.get_var(name="n")\ng.output(g.rgba(g.palette(n), 1.0))'),
    "get_var": dict(en="Reads a value named by a **Set value** node.",
                    es="Lee un valor al que un nodo **Guardar valor** puso nombre.",
                    code='g.set_var(g.uv()["x"], name="x")\ng.output(g.gradient(g.get_var(name="x")))'),
    # -- Utility
    "reroute": dict(en="A dot that only bends a wire around other nodes: it changes nothing.",
                    es="Un punto que solo desvía un cable alrededor de otros nodos: no cambia nada.",
                    code='x = g.reroute(g.uv()["x"])\ng.output(g.gradient(x))'),
    "expression": dict(
        en="Your own line of WGSL when no node does what you need: an expression of `a`, `b`, `c` and `d` (plus "
           "`uv`, `px`, `size` and `time`), or a function body with `return`. Pick the result's `type`.",
        es="Tu propia línea de WGSL cuando ningún nodo hace lo que necesitas: una expresión de `a`, `b`, `c` y "
           "`d` (más `uv`, `px`, `size` y `time`), o el cuerpo de una función con `return`. Elige el `type` del "
           "resultado.",
        code='e = g.expression(g.uv()["x"], 8.0, code="abs(sin(a * b + time))", type="float")\ng.output(g.rgba(e, 1.0))'),
    "subgraph": dict(
        en="Uses another `.pzshad` as a function: its mutable variables become inputs and its color the output. "
           "Feed `uv` to move, tile or warp the whole shader.",
        es="Usa otro `.pzshad` como función: sus variables mutables se vuelven entradas y su color la salida. "
           "Pasa un `uv` para mover, repetir o deformar el shader entero.",
        code=None),
    "comment": dict(en="A note on the canvas to explain a part of the graph. It has no effect on the shader.",
                    es="Una nota en el lienzo para explicar una parte del grafo. No afecta al shader.",
                    code='g.comment(text="Sky: gradient from top to bottom")\ng.output(g.gradient(g.uv()["y"]))'),
    "output": dict(
        en="The end of the graph: the color it receives is the color of the pixel. If `alpha` is connected it "
           "replaces the color's alpha. `g.output(color)` adds or finds it in Python.",
        es="El final del grafo: el color que recibe es el color del píxel. Si `alpha` está conectado, reemplaza "
           "el alfa del color. En Python, `g.output(color)` lo añade o lo encuentra.",
        code='g.output([1.0, 0.4, 0.1, 1.0], alpha=g.radial_gradient(radius=0.5))'),
}

#: Shown under a node when it is drawn in Python as one of several sidebar entries.
EXAMPLE_NOTE = {
    "subgraph": ("A Shader function needs another `.pzshad` file: `g.subgraph(path=\"plasma.pzshad\", uv=...)`. "
                 "In the designer, double-click the node to open that file.",
                 "Un Shader function necesita otro archivo `.pzshad`: `g.subgraph(path=\"plasma.pzshad\", uv=...)`. "
                 "En el diseñador, haz doble clic en el nodo para abrir ese archivo."),
}
