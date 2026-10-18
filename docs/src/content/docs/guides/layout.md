---
title: Layout y estilo
description: Filas, columnas, contenedores, tamaños, relleno, alineación y colores.
sidebar:
  order: 2
---

## Filas y columnas

```python
pz.column([a, b, c], spacing=8, padding=16)            # vertical
pz.row([a, b, c], spacing=8, align="center")          # horizontal
```

- `children` acepta listas anidadas y omite `None` y `False`, así que puedes escribir
  `self.error and ui.label(self.error, color="error")`.
- Un texto o un número como hijo se convierte en `pz.text`.
- `align` alinea los hijos en el eje cruzado: `"start"`, `"center"`, `"end"`.

## Tamaños

`width` y `height` aceptan:

| Valor | Significado |
| --- | --- |
| `240` | Píxeles fijos. |
| `"shrink"` | Lo justo para el contenido. |
| `"fill"` | Todo el espacio disponible. |
| `"fill:2"` | Una proporción del espacio: dos `"fill:1"` y un `"fill:2"` reparten 25/25/50. |

```python
pz.row([
    pz.container(sidebar, width=240),
    pz.container(contenido, width="fill"),
])
```

Empuja elementos a los extremos con un hueco flexible:

```python
pz.row([ui.label("Título"), pz.hspace(), ui.button("Cerrar", self.cerrar)])
```

:::caution[Hijos que rellenan]
Un hijo con `"fill"` (por ejemplo, `pz.rule()` horizontal) hace que su columna también rellene.
Si quieres que la columna encoja, pon `width="shrink"` en la columna.
:::

## Relleno

`padding` acepta `8` (todos los lados), `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`.

## Contenedores

`pz.container` envuelve un hijo para darle tamaño, alineación y estilo:

```python
pz.container(
    contenido,
    padding=(12, 16),
    width="fill",
    max_width=720,
    align_x="center",
    bg="#2f343e",
    border_color="#464b57",
    border_width=1,
    radius=8,
    shadow=("#00000066", (0, 4), 16),   # (color, (dx, dy), desenfoque)
    clip=True,
)
```

`pz.center(contenido)` lo centra en todo el espacio. `pz.container(None, width=8, height=8, bg=...)`
es un rectángulo de color.

## Colores

Los colores aceptan `"#rgb"`, `"#rrggbb"`, `"#rrggbbaa"`, tuplas `(r, g, b)` / `(r, g, b, a)` o
`"transparent"`. En los componentes de `pyzed.ui` también puedes usar un token del tema
(`"accent"`, `"text_muted"`…). Para colores derivados:

```python
from pyzed.theme import alpha, mix

alpha(self.theme.accent, 0.2)            # 20 % de opacidad
mix(self.theme.editor, "#ffffff", 0.05)  # un 5 % más claro
```

## Texto

```python
pz.text("Hola", size=16, weight="semibold", color="#dce0e5")
pz.text("código", font="mono")
pz.text("una línea muy larga…", wrap=False)
```

Fuentes incluidas: IBM Plex Sans (`"sans"`, por defecto), IBM Plex Mono (`"mono"`) y Lucide
(`"icons"`). Ver [iconos y fuentes](/pyzed/guides/icons-fonts/).

## Superposiciones y scroll

- `pz.stack([abajo, arriba])` superpone widgets; `pz.opaque(w)` evita que los clics lo atraviesen.
- `pz.scrollable(contenido, direction="vertical" | "horizontal" | "both")` añade scroll.
  Con `anchor_bottom=True` se queda pegado al final.
- `pz.hover(base, encima)` muestra `encima` solo al pasar el ratón.
- `pz.mouse_area(w, on_right_press=..., on_double_click=..., cursor="pointer")` detecta eventos
  del ratón.
