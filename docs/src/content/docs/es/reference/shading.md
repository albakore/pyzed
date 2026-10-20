---
title: "Grafos de shaders (pyzed.shading)"
description: "Referencia de la API de pyzed.shading: carga grafos de shaders .pzshad, cambia sus variables y crea grafos de nodos en código que se compilan al WGSL de pz.shader."
sidebar:
  order: 11.5
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

`pyzed.shading` es el sistema de shaders por nodos que hay detrás de la
[vista de shaders](/pyzed/es/shading/shader-designer/) del diseñador: grafos `.pzshad` de nodos que se
compilan al WGSL de [`pz.shader`](/pyzed/es/reference/widgets/). Mira
[Grafos de shaders](/pyzed/es/shading/shader-graphs/) para un recorrido.

```python
from pyzed import shading

fuego = shading.load("shaders/fuego.pzshad")
fuego["speed"] = 2.0                       # una variable mutable: no recompila
pz.shader(fuego, width=320, height=200)    # o pz.shader("shaders/fuego.pzshad")
```

## Usar shaders

### `load`

```python
load(path, *, fresh=False)
```

El `Shader` de un archivo `.pzshad`, en caché por ruta (`fresh=True` lo vuelve a leer). Se recarga solo cuando el archivo cambia.

### `Shader`

```python
class Shader
```

Un grafo de shader listo para dibujar, con sus propios valores de las variables: `shader["speed"] = 2`, `shader.set(...)`, `shader.variables`, `shader.wgsl` y `shader.widget(...)`. `pz.shader` lo acepta directamente.

### `widget`

```python
widget(source, **options)
```

Un widget `pz.shader` para una ruta `.pzshad`, un `Graph` o un `Shader`.

## Crear grafos

### `Graph`

```python
class Graph
```

Un grafo de shader: variables, nodos y las conexiones entre ellos. Llama a un tipo de nodo sobre él para añadirlo (`g.noise(scale=4)`, `g.sin(x)`), elige salidas con `nodo["nombre"]` y combínalas con aritmética. `save`, `compile`, `arrange`, `connect` y los métodos de variables lo editan.

### `new`

```python
new(name='shader')
```

Un grafo nuevo con UV alimentando un degradado hacia el nodo Output: la plantilla Blank del diseñador.

### `load_graph`

```python
load_graph(path)
```

El `Graph` de un archivo `.pzshad`, para editarlo.

### `Variable`

```python
@dataclass
class Variable(name, type='float', value=None, mutable=True, min=None, max=None, step=None, description='')
```

Una variable de un shader: `name`, `type` (float, int, bool, vec2, vec3, vec4, color, texture), `value`, `mutable` (un uniform) o constante, `min`, `max`, `step` y `description`.

### `Node`

```python
@dataclass
class Node(id, type, x=0.0, y=0.0, inputs={}, params={}, title='', preview=True)
```

Un nodo de un grafo: su `type`, su posición, `inputs` (valores fijos de las entradas sin conectar), `params` (ajustes), `title` y si se muestra su `preview`.

### `NodeRef`

```python
class NodeRef
```

Lo que devuelve `Graph.add`: `ref["puerto"]` es una salida para conectar en otro sitio; la aritmética usa su primera salida.

### `GraphError`

```python
class GraphError
```

Se lanza con conexiones imposibles (tipos, ciclos), tipos de nodo desconocidos y nombres de variable no válidos.

## Compilar

### `compile`

```python
compile(graph, target=None, *, values=None)
```

Compila un grafo (o la salida de un nodo, para su vista previa) a WGSL: el código `Compiled`, uniforms, texturas y problemas por nodo.

### `Compiled`

```python
@dataclass
class Compiled(code, uniforms={}, textures={}, names={}, errors={}, lines={}, uses_time=False)
```

El resultado de `compile`: `code`, `uniforms`, `textures`, `names` (el uniform de cada variable), `errors` por id de nodo, `uses_time`, y `check()`, que ejecuta el compilador de la GPU y pone sus mensajes en el nodo que escribió la línea.

## El catálogo de nodos

### `register`

```python
register(node_type, *, preset=True)
```

Añade un tipo de nodo propio al catálogo (y a la barra Shading del diseñador).

### `NodeType`

```python
@dataclass
class NodeType(id, title, category, description, inputs=(), outputs=(), params=(), exprs={}, functions=(), min_type='bool', build=None, ports=None, resolve=None, label=None, icon='', keywords='')
```

Un tipo de nodo: id, título, categoría, entradas, salidas, ajustes y cómo escribe su WGSL.

### `Preset`

```python
@dataclass
class Preset(type, title, category, description, params={}, keywords='')
```

Una entrada de la barra Shading: un tipo de nodo con algunos ajustes (`func:sin` es el nodo Function con sin).
