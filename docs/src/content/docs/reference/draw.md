---
title: "Dibujo (pyzed.draw)"
description: "Formas, texto y transformaciones para pz.canvas."
sidebar:
  order: 7
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs.py. -->

Las formas de `pyzed.draw` son diccionarios simples que se pasan a [`pz.canvas`](/pyzed/reference/widgets/#canvas).
Los ángulos van en grados y `y` crece hacia abajo. Ver la guía de [dibujo con canvas](/pyzed/guides/canvas/).

```python
from pyzed import draw

pz.canvas([
    draw.background("#1e2127"),
    draw.circle(100, 100, 40, fill="#74ade8"),
    draw.text(100, 180, "Hola", color="#dce0e5", align_x="center"),
], width=200, height=200)
```

## Formas

### `background`

```python
background(color)
```

Rellena todo el canvas.

| Parámetro | Descripción |
| --- | --- |
| `color` | Color. |

### `rect`

```python
rect(x, y, w, h, *, fill=None, stroke=None, width=1.0, radius=0.0, dash=None)
```

Un rectángulo, relleno y/o con trazo.

| Parámetro | Descripción |
| --- | --- |
| `x` | Izquierda. |
| `y` | Arriba. |
| `w` | Ancho. |
| `h` | Alto. |
| `fill` | Color de relleno. |
| `stroke` | Color del trazo. |
| `width` | Grosor del trazo. |
| `radius` | Radio de las esquinas. |
| `dash` | Patrón de guiones, p. ej. `[6, 4]`. |

### `rects`

```python
rects(items, *, fill)
```

Muchos rectángulos rellenos de un color en una sola forma (rápido para rejillas y barras).

| Parámetro | Descripción |
| --- | --- |
| `items` | Tuplas `(x, y, w, h)`. |
| `fill` | Color. |

### `circle`

```python
circle(x, y, r, *, fill=None, stroke=None, width=1.0, dash=None)
```

Un círculo centrado en `(x, y)`.

| Parámetro | Descripción |
| --- | --- |
| `x` | Centro x. |
| `y` | Centro y. |
| `r` | Radio. |
| `fill` | Color de relleno. |
| `stroke` | Color del trazo. |
| `width` | Grosor del trazo. |
| `dash` | Patrón de guiones, p. ej. `[6, 4]`. |

### `line`

```python
line(x1, y1, x2, y2, *, stroke='#ffffff', width=1.0, dash=None, cap=None)
```

Una línea recta.

| Parámetro | Descripción |
| --- | --- |
| `x1` | Inicio x. |
| `y1` | Inicio y. |
| `x2` | Fin x. |
| `y2` | Fin y. |
| `stroke` | Color del trazo. |
| `width` | Grosor del trazo. |
| `dash` | Patrón de guiones, p. ej. `[6, 4]`. |
| `cap` | `"round"`, `"square"` o `"butt"`: forma de los extremos. |

### `polyline`

```python
polyline(
    points,
    *,
    stroke='#ffffff',
    width=1.0,
    closed=False,
    fill=None,
    dash=None,
    cap='round',
)
```

Une `points` con líneas rectas (`closed=True` cierra la figura).

| Parámetro | Descripción |
| --- | --- |
| `points` | Lista de `(x, y)`. |
| `stroke` | Color del trazo. |
| `width` | Grosor del trazo. |
| `closed` | Cierra la figura. |
| `fill` | Color de relleno. |
| `dash` | Patrón de guiones, p. ej. `[6, 4]`. |
| `cap` | `"round"`, `"square"` o `"butt"`: forma de los extremos. |

### `polygon`

```python
polygon(points, *, fill=None, stroke=None, width=1.0)
```

Una figura cerrada que pasa por `points`.

| Parámetro | Descripción |
| --- | --- |
| `points` | Lista de `(x, y)`. |
| `fill` | Color de relleno. |
| `stroke` | Color del trazo. |
| `width` | Grosor del trazo. |

### `arc`

```python
arc(x, y, r, start, end, *, stroke=None, fill=None, width=1.0, pie=False, cap=None)
```

Un arco de circunferencia de `start` a `end` grados (0 = las 3 en punto, sentido horario). `pie=True` lo cierra por el centro (porción de tarta).

| Parámetro | Descripción |
| --- | --- |
| `x` | Centro x. |
| `y` | Centro y. |
| `r` | Radio. |
| `start` | Ángulo inicial. |
| `end` | Ángulo final. |
| `stroke` | Color del trazo. |
| `fill` | Color de relleno. |
| `width` | Grosor del trazo. |
| `pie` | Cierra por el centro. |
| `cap` | `"round"`, `"square"` o `"butt"`: forma de los extremos. |

### `path`

```python
path(ops, *, fill=None, stroke=None, width=1.0, dash=None, cap=None)
```

Un trazado libre con operaciones tipo SVG: `("M", x, y)` mover, `("L", x, y)` línea, `("Q", cx, cy, x, y)` curva cuadrática, `("C", c1x, c1y, c2x, c2y, x, y)` curva cúbica, `("A", cx, cy, r, inicio, fin)` arco, `("Z",)` cerrar.

| Parámetro | Descripción |
| --- | --- |
| `ops` | Lista de operaciones. |
| `fill` | Color de relleno. |
| `stroke` | Color del trazo. |
| `width` | Grosor del trazo. |
| `dash` | Patrón de guiones, p. ej. `[6, 4]`. |
| `cap` | `"round"`, `"square"` o `"butt"`: forma de los extremos. |

### `text`

```python
text(
    x,
    y,
    content,
    *,
    color='#ffffff',
    size=14,
    font='sans',
    weight=None,
    align_x='start',
    align_y='top',
)
```

Texto anclado en `(x, y)`; `align_x`/`align_y` eligen qué lado del texto queda en ese punto.

| Parámetro | Descripción |
| --- | --- |
| `x` | Posición x. |
| `y` | Posición y. |
| `content` | El texto. |
| `color` | Color. |
| `size` | Tamaño. |
| `font` | Familia. |
| `weight` | Peso. |
| `align_x` | `"start"`, `"center"` o `"end"`. |
| `align_y` | `"top"`, `"center"` o `"bottom"`. |

## Transformaciones

### `translate`

```python
translate(x, y)
```

Desplaza las formas que vienen después.

| Parámetro | Descripción |
| --- | --- |
| `x` | Horizontal. |
| `y` | Vertical. |

### `rotate`

```python
rotate(degrees)
```

Gira las formas que vienen después alrededor del origen actual.

| Parámetro | Descripción |
| --- | --- |
| `degrees` | Grados. |

### `scale`

```python
scale(x, y=None)
```

Escala las formas que vienen después.

| Parámetro | Descripción |
| --- | --- |
| `x` | Factor horizontal. |
| `y` | Factor vertical (por defecto, igual que `x`). |

### `save`

```python
save()
```

Guarda la transformación actual (úsalo con `restore`).

### `restore`

```python
restore()
```

Vuelve a la transformación guardada por el último `save`.

### `group`

```python
group(shapes, *, x=0.0, y=0.0, rotation=0.0, scale_by=None)
```

Dibuja `shapes` desplazadas, giradas y escaladas sin afectar a las formas siguientes. Devuelve una lista: expándela con `*`.

| Parámetro | Descripción |
| --- | --- |
| `shapes` | Las formas. |
| `x` | Desplazamiento x. |
| `y` | Desplazamiento y. |
| `rotation` | Grados. |
| `scale_by` | Escala. |
