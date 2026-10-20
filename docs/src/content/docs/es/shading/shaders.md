---
title: Shaders
description: Pinta widgets en la GPU con tus propios shaders WGSL (fondos, efectos y visuales de videojuego) con uniforms desde Python y la posición del ratón.
sidebar:
  order: 3.6
---

`pz.shader` es un widget que pinta la GPU con una función que escribes en
[WGSL](https://www.w3.org/TR/WGSL/), el lenguaje de shaders de WebGPU. La GPU la ejecuta para
cada píxel en cada frame, así que fondos animados, plasma, fuego o el barrido de un radar no le
cuestan nada a Python.

:::tip[¿Prefieres nodos?]
Puedes crear shaders sin escribir WGSL: conecta nodos en la
[vista de shaders](/pyzed/es/editor/shader-designer/) del diseñador y dibuja el archivo `.pzshad` con
`pz.shader("fuego.pzshad")`. Mira [Grafos de shaders](/pyzed/es/guides/shader-graphs/).
:::

![Seis shaders: plasma, ondas, túnel, CRT, Voronoi y fuego](../../../../assets/showcase/shaders.png)

```python
ONDAS = """
fn shade(uv: vec2<f32>, px: vec2<f32>, size: vec2<f32>, time: f32) -> vec4<f32> {
    let onda = 0.5 + 0.5 * sin(uv.x * 12.0 + time * speed());
    return vec4<f32>(mix(vec3<f32>(0.1, 0.1, 0.3), tint().rgb, onda), 1.0);
}
"""

pz.shader(ONDAS, uniforms={"speed": 2.0, "tint": "accent"}, height=200)
```

## La función `shade`

Tu código define `shade` y las funciones auxiliares que necesite. Recibe:

| Argumento | Significado |
| --- | --- |
| `uv` | Dónde está el píxel, de `(0, 0)` arriba a la izquierda a `(1, 1)` abajo a la derecha. |
| `px` | La misma posición en píxeles. |
| `size` | El tamaño del widget en píxeles. |
| `time` | Segundos desde que arrancó la app. |

Devuelve el color del píxel como `vec4<f32>(rojo, verde, azul, alfa)`, cada uno de 0 a 1, en el
mismo espacio de color que los colores CSS. `mouse()` devuelve la posición del puntero como un
`uv` (negativo cuando está fuera del widget); un shader que la usa se redibuja al mover el ratón.

## Uniforms

`uniforms` pasa hasta 32 valores desde Python. Cada uno se convierte en una función con su nombre:

| Valor | WGSL |
| --- | --- |
| Un número | `speed()` devuelve `f32` |
| 2, 3 o 4 números | `vec2<f32>`, `vec3<f32>` o `vec4<f32>` |
| Un color (hex o token del tema) | `vec4<f32>` con el rojo, verde, azul y alfa del color |

Cambia los valores en `view()` como cualquier otra propiedad: el shader se compila una vez y solo
cambian los valores, así que un slider puede moverlo a la frecuencia de la pantalla.

## Opciones

- `width`, `height`: el tamaño (`"fill"` por defecto).
- `animate=False` dibuja una imagen quieta que solo cambia cuando cambia la vista.
- `time=1.5` congela `time` en ese valor.
- `fallback` es un color o degradado que se dibuja donde no hay GPU (y detrás del shader donde es
  transparente).
- `textures={"foto": "assets/foto.png"}` pasa hasta 8 imágenes: cada una se convierte en una función,
  `foto(uv)`, que devuelve el color de la imagen en `uv` (se repite fuera de 0..1).

## Errores

El código se comprueba al crear el widget, así que un error lanza un `ValueError` en Python con
el mensaje del compilador y la línea:

```text
ValueError: invalid shader:
error: no definition in scope for identifier: `colr`
   ┌─ wgsl:24:12
```

## Combinarlo con otros efectos

Un shader es un widget, así que funciona con el resto de Pyzed: ponlo en un `pz.stack` detrás de
paneles de cristal (que lo desenfocan), recórtalo con un contenedor, gíralo o desvanécelo con
`style()` y `animate()`. Las [demos](/pyzed/es/showcase/) usan shaders para una nebulosa, un
horizonte synthwave, brasas y manchas de color en movimiento.

## Límites

- Los shaders necesitan el renderer de GPU. En el renderer por software (sin GPU, y en algunas
  máquinas de CI) el widget muestra `fallback`, y las capturas hechas ahí también. En Linux sin
  GPU, el driver Vulkan por software de Mesa (`mesa-vulkan-drivers`) los ejecuta.
- Las esquinas de un shader son rectas: `radius` en un contenedor alrededor no las redondea.
