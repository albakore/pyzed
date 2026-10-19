---
title: "Widgets base"
description: "Los widgets nativos de pyzed: layout, texto, controles, editor, svg e iconos."
sidebar:
  order: 3
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Los widgets base están implementados en Rust y se importan desde `pyzed`. Son los
ladrillos con los que están hechos los [componentes](/pyzed/es/components/overview/).
Ver la guía de [layout](/pyzed/es/guides/layout/) para los tamaños, el relleno y los colores.

## Widget

### `Widget`

Un nodo inmutable del árbol de la interfaz, implementado en Rust. Lo devuelven todas las funciones de widgets y componentes. Donde se espera un hijo también puedes pasar un texto o un número (se convierte en `text`) o `None` (se ignora).

## Layout

### `column`

```python
column(
    children=None,
    *,
    spacing=0.0,
    padding=None,
    width=None,
    height=None,
    align=None,
    max_width=None,
    clip=False,
)
```

Apila los hijos en vertical.

| Parámetro | Descripción |
| --- | --- |
| `children` | Lista de hijos. Se aplanan listas anidadas y se ignoran `None` y `False`, así que puedes escribir `cond and widget`. |
| `spacing` | Separación entre hijos, en píxeles. |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `align` | Alineación de los hijos en el eje cruzado: `"start"`, `"center"` o `"end"`. |
| `max_width` | Ancho máximo en píxeles. |
| `clip` | Recorta el contenido que se sale de los límites. |

```python
pz.column([pz.text("Uno"), pz.text("Dos")], spacing=8, padding=16)
```

### `row`

```python
row(
    children=None,
    *,
    spacing=0.0,
    padding=None,
    width=None,
    height=None,
    align=None,
    clip=False,
    wrap=False,
    line_spacing=None,
)
```

Coloca los hijos en horizontal.

| Parámetro | Descripción |
| --- | --- |
| `children` | Lista de hijos. Se aplanan listas anidadas y se ignoran `None` y `False`, así que puedes escribir `cond and widget`. |
| `spacing` | Separación entre hijos, en píxeles. |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `align` | Alineación de los hijos en el eje cruzado: `"start"`, `"center"` o `"end"`. |
| `clip` | Recorta el contenido que se sale de los límites. |
| `wrap` | Ajuste de línea / pasa los hijos a una nueva fila cuando no caben. |
| `line_spacing` | Separación entre filas cuando `wrap=True`. |

```python
pz.row([ui.label("Nombre"), pz.hspace(), ui.button("OK", "ok")], align="center")
```

### `container`

```python
container(
    content=None,
    *,
    padding=None,
    width=None,
    height=None,
    max_width=None,
    max_height=None,
    align_x=None,
    align_y=None,
    center=False,
    bg=None,
    color=None,
    border_color=None,
    border_width=0.0,
    radius=None,
    shadow=None,
    clip=False,
    gradient=None,
)
```

Envuelve un hijo para darle tamaño, alineación, fondo, borde, radio y sombra.

| Parámetro | Descripción |
| --- | --- |
| `content` | El hijo (o `None` para una caja vacía, útil como rectángulo de color). |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `max_width` | Ancho máximo en píxeles. |
| `max_height` | Alto máximo en píxeles. |
| `align_x` | Alineación horizontal: `"start"`/`"left"`, `"center"`, `"end"`/`"right"`. |
| `align_y` | Alineación vertical: `"start"`/`"top"`, `"center"`, `"end"`/`"bottom"`. |
| `center` | Centra el contenido en ambos ejes y ocupa todo el espacio. |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `color` | Color del texto o del icono. |
| `border_color` | Color del borde. |
| `border_width` | Grosor del borde en píxeles. |
| `radius` | Radio de las esquinas: un número o `(sup_izq, sup_der, inf_der, inf_izq)`. |
| `shadow` | Sombra: `(color, (dx, dy), desenfoque)`. |
| `clip` | Recorta el contenido que se sale de los límites. |
| `gradient` | Degradado lineal de fondo: `(ángulo, [colores])` o `(ángulo, [(posición, color), ...])`. |

### `center`

```python
center(content, **kwargs)
```

Centra `content` en todo el espacio disponible. Equivale a `container(content, center=True)`.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `kwargs` | Cualquier parámetro de `container`. |

### `scrollable`

```python
scrollable(
    content,
    *,
    direction='vertical',
    width=None,
    height=None,
    padding=None,
    id=None,
    anchor_bottom=False,
    rail=None,
    scroller=None,
    scroller_hover=None,
    scrollbar_width=8.0,
    scroller_width=None,
    margin=0.0,
    on_scroll=None,
)
```

Hace desplazable su contenido.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `direction` | `"vertical"`, `"horizontal"` o `"both"`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `anchor_bottom` | Mantiene el scroll pegado al final (logs, terminales, chats). |
| `rail` | Color del carril de la barra. |
| `scroller` | Color del tirador. |
| `scroller_hover` | Color del tirador al pasar el ratón. |
| `scrollbar_width` | Ancho de la barra. |
| `scroller_width` | Ancho del tirador (por defecto, el de la barra). |
| `margin` | Margen entre la barra y el contenido. |
| `on_scroll` | Callable que recibe un dict con `x`, `y`, `relative_x`, `relative_y`, `width`, `height`, `content_width` y `content_height`. |

### `stack`

```python
stack(children=None, *, width=None, height=None)
```

Superpone los hijos, el último encima. Base de capas, modales y notificaciones.

| Parámetro | Descripción |
| --- | --- |
| `children` | Lista de hijos. Se aplanan listas anidadas y se ignoran `None` y `False`, así que puedes escribir `cond and widget`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

### `space`

```python
space(width=None, height=None)
```

Espacio vacío de un tamaño dado.

| Parámetro | Descripción |
| --- | --- |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

### `hspace`

```python
hspace(width='fill')
```

Hueco horizontal flexible: empuja a los hermanos de una fila hacia los extremos.

| Parámetro | Descripción |
| --- | --- |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

### `vspace`

```python
vspace(height='fill')
```

Hueco vertical flexible: empuja a los hermanos de una columna hacia los extremos.

| Parámetro | Descripción |
| --- | --- |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

### `rule`

```python
rule(*, vertical=False, thickness=1.0, color=None)
```

Una línea divisoria horizontal (o vertical).

| Parámetro | Descripción |
| --- | --- |
| `vertical` | Línea vertical en lugar de horizontal. |
| `thickness` | Grosor en píxeles. |
| `color` | Color del texto o del icono. |

Una regla horizontal ocupa todo el ancho. Dentro de una columna que debe encoger, pon `width="shrink"` en la columna.

### `grid`

```python
grid(
    children=None,
    *,
    columns=None,
    max_width=None,
    spacing=0.0,
    height=None,
    aspect_ratio=None,
    width=None,
)
```

Coloca los hijos en una rejilla con un número fijo de `columns`, o tantas columnas de como mucho `max_width` como quepan.

| Parámetro | Descripción |
| --- | --- |
| `children` | Lista de hijos. Se aplanan listas anidadas y se ignoran `None` y `False`, así que puedes escribir `cond and widget`. |
| `columns` | Número de columnas. |
| `max_width` | Ancho máximo en píxeles. |
| `spacing` | Separación entre hijos, en píxeles. |
| `height` | Alto de cada fila. |
| `aspect_ratio` | Mantiene las celdas en esta proporción ancho/alto. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

```python
pz.grid([card(p) for p in photos], max_width=220, spacing=8, aspect_ratio=1)
```

### `split`

```python
split(
    first,
    second,
    *,
    ratio=0.5,
    on_resize=None,
    vertical=False,
    min_size=80.0,
    min_size_second=None,
    color=None,
    hover_color=None,
    thickness=1.0,
    handle=8.0,
    width=None,
    height=None,
)
```

Dos paneles con un divisor que se arrastra. Para el estilo del tema usa `ui.split`.

| Parámetro | Descripción |
| --- | --- |
| `first` | Primer panel. |
| `second` | Segundo panel. |
| `ratio` | Proporción del primer panel (0–1). |
| `on_resize` | Callable que recibe la nueva proporción mientras se arrastra. |
| `vertical` | Apila los paneles arriba/abajo. |
| `min_size` | Tamaño mínimo del primer panel. |
| `min_size_second` | Tamaño mínimo del segundo panel. |
| `color` | Color del divisor. |
| `hover_color` | Color del divisor al pasar el ratón o arrastrar. |
| `thickness` | Grosor de la línea. |
| `handle` | Ancho de la zona que se puede arrastrar. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

### `pin`

```python
pin(content, *, x=0.0, y=0.0, width=None, height=None)
```

Coloca `content` en `(x, y)` dentro de una caja. Úsalo en un `stack` para posicionar popovers y menús contextuales.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `x` | Posición horizontal. |
| `y` | Posición vertical. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

### `responsive`

```python
responsive(function)
```

Construye su contenido con `function(ancho, alto)` usando el espacio realmente disponible, para que el layout se adapte (por ejemplo, ocultar una barra lateral si la ventana es estrecha).

| Parámetro | Descripción |
| --- | --- |
| `function` | Función que recibe `(ancho, alto)` y devuelve un widget. |

## Texto e iconos

### `text`

```python
text(
    content,
    *,
    size=None,
    color=None,
    font=None,
    weight=None,
    italic=False,
    line_height=None,
    align_x=None,
    align_y=None,
    width=None,
    height=None,
    wrap=True,
)
```

Un texto.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `size` | Tamaño de la fuente. |
| `color` | Color del texto o del icono. |
| `font` | `"sans"` (IBM Plex Sans), `"mono"`, `"icons"`, `"serif"` o el nombre de una familia cargada con `load_font`. |
| `weight` | `"thin"`, `"light"`, `"normal"`, `"medium"`, `"semibold"`, `"bold"`, `"black"` o un número (100–900). |
| `italic` | Cursiva. |
| `line_height` | Alto de línea relativo al tamaño (1.0, 1.5…). |
| `align_x` | Alineación horizontal: `"start"`/`"left"`, `"center"`, `"end"`/`"right"`. |
| `align_y` | Alineación vertical: `"start"`/`"top"`, `"center"`, `"end"`/`"bottom"`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `wrap` | Ajuste de línea. Con `False` el texto no se parte. |

### `icon`

```python
icon(name, *, size=16, color=None)
```

Un icono de [Lucide](https://lucide.dev). `color` por defecto es el color del texto que lo rodea.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del icono (`pyzed icons` los lista). |
| `size` | Tamaño en píxeles. |
| `color` | Color. |

```python
pz.icon("folder", size=16, color="#74ade8")
```

### `svg`

```python
svg(
    source,
    *,
    width=None,
    height=None,
    color=None,
    content_fit=None,
    opacity=1.0,
    rotation=0.0,
)
```

Una imagen SVG.

| Parámetro | Descripción |
| --- | --- |
| `source` | Ruta a un `.svg`, el código SVG como texto (empieza por `<`) o `bytes`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `color` | Si se indica, tiñe todo el SVG de ese color (útil para iconos monocromos). |
| `content_fit` | `"contain"`, `"cover"`, `"fill"`, `"none"` o `"scale-down"`. |
| `opacity` | Opacidad de 0 a 1. |
| `rotation` | Rotación en grados. |

## Imágenes y contenido

### `image`

```python
image(
    source,
    *,
    width=None,
    height=None,
    content_fit=None,
    filter='linear',
    opacity=1.0,
    radius=0.0,
    rotation=0.0,
    scale=1.0,
    size=None,
)
```

Una imagen de mapa de bits (PNG, JPEG, GIF, BMP, WebP…) desde una ruta o `bytes`, o píxeles RGBA crudos.

| Parámetro | Descripción |
| --- | --- |
| `source` | Ruta del archivo, `bytes` del archivo codificado, o píxeles RGBA crudos con `size=(ancho, alto)`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `content_fit` | `"contain"`, `"cover"`, `"fill"`, `"none"` o `"scale-down"`. |
| `filter` | `"linear"` (suave) o `"nearest"` (píxeles nítidos, para pixel art). |
| `opacity` | Opacidad de 0 a 1. |
| `radius` | Radio de las esquinas. |
| `rotation` | Rotación en grados. |
| `scale` | Escala. |
| `size` | `(ancho, alto)` cuando `source` son píxeles RGBA crudos. |

```python
pz.image("foto.jpg", width=320, content_fit="cover", radius=8)
```

### `image_viewer`

```python
image_viewer(
    source,
    *,
    width=None,
    height=None,
    min_scale=0.25,
    max_scale=10.0,
    scale_step=0.1,
    filter='linear',
    size=None,
)
```

Una imagen que se puede desplazar (arrastrando) y ampliar (rueda del ratón), como el visor de Iced.

| Parámetro | Descripción |
| --- | --- |
| `source` | Ruta del archivo, `bytes` del archivo codificado, o píxeles RGBA crudos con `size=(ancho, alto)`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `min_scale` | Zoom mínimo. |
| `max_scale` | Zoom máximo. |
| `scale_step` | Cuánto cambia el zoom por paso de rueda. |
| `filter` | `"linear"` (suave) o `"nearest"` (píxeles nítidos, para pixel art). |
| `size` | `(ancho, alto)` para píxeles RGBA crudos. |

### `markdown`

```python
markdown(
    source,
    *,
    size=14.0,
    color=None,
    link_color=None,
    code_color=None,
    code_bg=None,
    on_link=None,
    width=None,
)
```

Renderiza Markdown (títulos, listas, bloques de código, citas, tablas, enlaces…). Para los colores del tema usa `ui.markdown`.

| Parámetro | Descripción |
| --- | --- |
| `source` | El texto Markdown. |
| `size` | Tamaño. |
| `color` | Color del texto o del icono. |
| `link_color` | Color de los enlaces. |
| `code_color` | Color del código. |
| `code_bg` | Fondo del código. |
| `on_link` | Callable que recibe la URL al pulsar un enlace. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

### `rich_text`

```python
rich_text(
    spans,
    *,
    size=None,
    color=None,
    font=None,
    line_height=None,
    width=None,
    align_x=None,
    wrap=True,
)
```

Texto hecho de fragmentos con estilos distintos. Los textos sueltos son fragmentos sin estilo.

| Parámetro | Descripción |
| --- | --- |
| `spans` | Lista de `span(...)` o textos. |
| `size` | Tamaño. |
| `color` | Color del texto o del icono. |
| `font` | Fuente del fragmento o del texto (nombre de familia, p. ej. `"IBM Plex Mono"`). |
| `line_height` | Alto de línea. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `align_x` | Alineación horizontal: `"start"`/`"left"`, `"center"`, `"end"`/`"right"`. |
| `wrap` | Ajuste de línea / pasa los hijos a una nueva fila cuando no caben. |

```python
pz.rich_text(["Pulsa ", pz.span("aquí", color="#74ade8", underline=True, link=self.abrir), " para abrir."])
```

### `span`

```python
span(
    text,
    *,
    color=None,
    size=None,
    font=None,
    weight=None,
    italic=False,
    bg=None,
    radius=0.0,
    padding=None,
    underline=False,
    strikethrough=False,
    link=None,
)
```

Un fragmento con estilo para `rich_text`. Con `link`, al pulsarlo se envía (o se llama) ese valor.

| Parámetro | Descripción |
| --- | --- |
| `text` | El texto. |
| `color` | Color del texto o del icono. |
| `size` | Tamaño. |
| `font` | Fuente del fragmento o del texto (nombre de familia, p. ej. `"IBM Plex Mono"`). |
| `weight` | Grosor de la fuente: `"normal"`, `"medium"`, `"semibold"` o `"bold"`. |
| `italic` | Si es `True`, el fragmento se dibuja en cursiva. |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `radius` | Radio del fondo. |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `underline` | Subrayado. |
| `strikethrough` | Tachado. |
| `link` | Mensaje o callable al pulsarlo. |

### `Span`

El tipo de los fragmentos que crea `pz.span`.

### `qr_code`

```python
qr_code(data, *, cell_size=4.0, color=None, bg=None)
```

Un código QR que codifica `data`.

| Parámetro | Descripción |
| --- | --- |
| `data` | El texto o URL a codificar. |
| `cell_size` | Tamaño de cada módulo en píxeles. |
| `color` | Color del texto o del icono. |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |

### `canvas`

```python
canvas(
    shapes=None,
    *,
    width=None,
    height=None,
    id=None,
    on_press=None,
    on_release=None,
    on_right_press=None,
    on_move=None,
    on_scroll=None,
    cursor=None,
)
```

Una superficie de dibujo 2D. `shapes` es una lista creada con [`pyzed.draw`](/pyzed/es/reference/draw/). Los callbacks del ratón reciben coordenadas relativas al canvas. Con un `id`, la geometría se cachea entre frames y solo se recalcula cuando cambian las formas. Ver la guía de [dibujo con canvas](/pyzed/es/guides/canvas/).

| Parámetro | Descripción |
| --- | --- |
| `shapes` | Lista de formas de `pyzed.draw` (se aceptan listas anidadas). |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `id` | Activa la caché de geometría. |
| `on_press` | Callable que recibe `(x, y)` al pulsar. |
| `on_release` | Callable que recibe `(x, y)` al soltar. |
| `on_right_press` | Callable que recibe `(x, y)` con clic derecho. |
| `on_move` | Se llama con `(x, y)` al mover el ratón. |
| `on_scroll` | Callable que recibe `(dx, dy)` en líneas al usar la rueda. |
| `cursor` | Cursor del ratón (`"crosshair"`, `"pointer"`…). |

## Interacción

### `button`

```python
button(
    content,
    on_press=None,
    *,
    padding=None,
    width=None,
    height=None,
    bg=None,
    color=None,
    border_color=None,
    border_width=0.0,
    radius=None,
    shadow=None,
    hover_bg=None,
    hover_color=None,
    hover_border_color=None,
    pressed_bg=None,
    disabled_color=None,
    clip=False,
)
```

Un botón sin estilo predefinido. Para el botón de Zed usa `ui.button`.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido del botón. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `color` | Color del texto o del icono. |
| `border_color` | Color del borde. |
| `border_width` | Grosor del borde en píxeles. |
| `radius` | Radio de las esquinas: un número o `(sup_izq, sup_der, inf_der, inf_izq)`. |
| `shadow` | Sombra: `(color, (dx, dy), desenfoque)`. |
| `hover_bg` | Fondo al pasar el ratón. |
| `hover_color` | Color del texto al pasar el ratón. |
| `hover_border_color` | Color del borde al pasar el ratón. |
| `pressed_bg` | Fondo mientras se pulsa. |
| `disabled_color` | Color del texto cuando está deshabilitado. |
| `clip` | Recorta el contenido que se sale de los límites. |

### `text_input`

```python
text_input(
    value,
    *,
    placeholder='',
    on_input=None,
    on_submit=None,
    id=None,
    size=None,
    font=None,
    padding=None,
    width=None,
    secure=False,
    icon=None,
    icon_size=None,
    bg=None,
    border_color=None,
    hover_border_color=None,
    focus_border_color=None,
    border_width=None,
    radius=None,
    color=None,
    placeholder_color=None,
    selection_color=None,
    icon_color=None,
)
```

Un campo de texto controlado: muestra `value` y te avisa de los cambios con `on_input`. Para el estilo de Zed usa `ui.input`.

| Parámetro | Descripción |
| --- | --- |
| `value` | Texto actual. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `on_input` | Callable que recibe el texto nuevo en cada pulsación. |
| `on_submit` | Mensaje o callable que se envía al pulsar Enter. |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `size` | Tamaño de la fuente. |
| `font` | Familia de la fuente. |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `secure` | Oculta el texto (contraseñas). |
| `icon` | Carácter del icono (usa `pyzed.icons.glyph(nombre)`). |
| `icon_size` | Tamaño del icono. |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `border_color` | Color del borde. |
| `hover_border_color` | Color del borde al pasar el ratón. |
| `focus_border_color` | Color del borde con el foco. |
| `border_width` | Grosor del borde en píxeles. |
| `radius` | Radio de las esquinas: un número o `(sup_izq, sup_der, inf_der, inf_izq)`. |
| `color` | Color del texto o del icono. |
| `placeholder_color` | Color del placeholder. |
| `selection_color` | Color de la selección. |
| `icon_color` | Color del icono. |

### `mouse_area`

```python
mouse_area(
    content,
    *,
    on_press=None,
    on_release=None,
    on_right_press=None,
    on_double_click=None,
    on_enter=None,
    on_exit=None,
    on_move=None,
    on_scroll=None,
    on_middle_press=None,
    cursor=None,
)
```

Detecta eventos del ratón sobre su contenido.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `on_press` | Clic izquierdo (al pulsar). |
| `on_release` | Al soltar el botón izquierdo. |
| `on_right_press` | Clic derecho (menús contextuales). |
| `on_double_click` | Doble clic. |
| `on_enter` | El ratón entra. |
| `on_exit` | El ratón sale. |
| `on_move` | Se llama con `(x, y)` al mover el ratón. |
| `on_scroll` | Callable que recibe `(dx, dy)` en líneas al usar la rueda. |
| `on_middle_press` | Clic con el botón central. |
| `cursor` | `"pointer"`, `"text"`, `"grab"`, `"grabbing"`, `"crosshair"`, `"not-allowed"`, `"resize-horizontal"`, `"resize-vertical"`, `"move"` o `"default"`. |

### `hover`

```python
hover(base, top)
```

Muestra `top` encima de `base` solo mientras el ratón está encima (por ejemplo, el botón de cerrar de una pestaña).

| Parámetro | Descripción |
| --- | --- |
| `base` | Widget de abajo. |
| `top` | Widget que aparece al pasar el ratón. |

### `opaque`

```python
opaque(content)
```

Hace que un widget bloquee el ratón para lo que está debajo en un `stack`.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |

### `tooltip`

```python
tooltip(
    content,
    tip,
    *,
    position='bottom',
    gap=4.0,
    bg=None,
    color=None,
    border_color=None,
    border_width=0.0,
    radius=None,
    shadow=None,
)
```

Muestra `tip` junto a `content` al pasar el ratón. `ui.tooltip` añade el estilo de Zed.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `tip` | Contenido del tooltip. |
| `position` | `"top"`, `"bottom"`, `"left"`, `"right"` o `"cursor"`. |
| `gap` | Distancia al contenido. |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `color` | Color del texto o del icono. |
| `border_color` | Color del borde. |
| `border_width` | Grosor del borde en píxeles. |
| `radius` | Radio de las esquinas: un número o `(sup_izq, sup_der, inf_der, inf_izq)`. |
| `shadow` | Sombra: `(color, (dx, dy), desenfoque)`. |

## Controles

### `checkbox`

```python
checkbox(
    checked,
    label=None,
    *,
    on_toggle=None,
    size=None,
    text_size=None,
    accent=None,
    bg=None,
    border_color=None,
    check_color=None,
    color=None,
)
```

Una casilla de verificación.

| Parámetro | Descripción |
| --- | --- |
| `checked` | Estado actual. |
| `label` | Texto de la etiqueta. |
| `on_toggle` | Callable que recibe el nuevo `bool` (o mensaje que se envía). |
| `size` | Tamaño de la casilla. |
| `text_size` | Tamaño del texto. |
| `accent` | Color de acento (parte activa). |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `border_color` | Color del borde. |
| `check_color` | Color de la marca. |
| `color` | Color del texto o del icono. |

### `toggler`

```python
toggler(
    checked,
    label=None,
    *,
    on_toggle=None,
    size=None,
    text_size=None,
    accent=None,
    bg=None,
    border_color=None,
    knob_color=None,
    color=None,
)
```

Un interruptor encendido/apagado.

| Parámetro | Descripción |
| --- | --- |
| `checked` | Estado actual. |
| `label` | Texto de la etiqueta. |
| `on_toggle` | Callable que recibe el nuevo `bool` (o mensaje que se envía). |
| `size` | Alto del interruptor. |
| `text_size` | Tamaño del texto. |
| `accent` | Color de acento (parte activa). |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `border_color` | Color del borde. |
| `knob_color` | Color del tirador. |
| `color` | Color del texto o del icono. |

### `slider`

```python
slider(
    min,
    max,
    value,
    *,
    step=1.0,
    on_change=None,
    on_release=None,
    width=None,
    height=None,
    vertical=False,
    accent=None,
    bg=None,
    knob_color=None,
    border_color=None,
)
```

Un deslizador entre `min` y `max`.

| Parámetro | Descripción |
| --- | --- |
| `min` | Mínimo. |
| `max` | Máximo. |
| `value` | Valor actual. |
| `step` | Paso. |
| `on_change` | Callable que recibe el nuevo valor. |
| `on_release` | Se envía al soltar el tirador. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `vertical` | Orientación vertical. |
| `accent` | Color de acento (parte activa). |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `knob_color` | Color del tirador. |
| `border_color` | Color del borde. |

### `progress_bar`

```python
progress_bar(
    value,
    *,
    min=0.0,
    max=1.0,
    width=None,
    height=None,
    accent=None,
    bg=None,
    radius=2.0,
)
```

Una barra de progreso.

| Parámetro | Descripción |
| --- | --- |
| `value` | Valor actual. |
| `min` | Mínimo. |
| `max` | Máximo. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `accent` | Color de acento (parte activa). |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `radius` | Radio de las esquinas. |

### `vertical_slider`

```python
vertical_slider(min, max, value, **kwargs)
```

Un deslizador vertical (`slider(..., vertical=True)`).

| Parámetro | Descripción |
| --- | --- |
| `min` | Mínimo. |
| `max` | Máximo. |
| `value` | Valor actual. |
| `kwargs` | Los de `slider`. |

### `pick_list`

```python
pick_list(
    options,
    selected=None,
    on_select=None,
    *,
    placeholder=None,
    width=None,
    padding=None,
    text_size=None,
    font=None,
    handle=None,
    handle_size=12.0,
    menu_height=None,
    bg=None,
    color=None,
    placeholder_color=None,
    handle_color=None,
    border_color=None,
    hover_border_color=None,
    radius=None,
    menu_bg=None,
    menu_color=None,
    menu_border_color=None,
    selected_bg=None,
    selected_color=None,
)
```

Un desplegable para elegir una de `options`. `on_select(opción)` recibe la elegida. Para el estilo de Zed usa `ui.select`.

| Parámetro | Descripción |
| --- | --- |
| `options` | Lista de opciones. |
| `selected` | Opción actual. |
| `on_select` | Callable que recibe el elemento elegido. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `text_size` | Tamaño del texto. |
| `font` | Familia de la fuente. |
| `handle` | Carácter del icono de la flecha. |
| `handle_size` | Tamaño de la flecha. |
| `menu_height` | Alto máximo del menú. |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `color` | Color del texto o del icono. |
| `placeholder_color` | Color del placeholder. |
| `handle_color` | Color de la flecha. |
| `border_color` | Color del borde. |
| `hover_border_color` | Color del borde al pasar el ratón. |
| `radius` | Radio de las esquinas: un número o `(sup_izq, sup_der, inf_der, inf_izq)`. |
| `menu_bg` | Fondo del menú. |
| `menu_color` | Texto del menú. |
| `menu_border_color` | Borde del menú. |
| `selected_bg` | Fondo de la opción resaltada. |
| `selected_color` | Texto de la opción resaltada. |

### `radio`

```python
radio(
    label,
    selected,
    on_select=None,
    *,
    size=None,
    text_size=None,
    spacing=None,
    accent=None,
    bg=None,
    border_color=None,
    color=None,
)
```

Un botón de radio. Agrupa varios tú mismo (o usa `ui.radio_group`); `on_select` se envía al pulsarlo.

| Parámetro | Descripción |
| --- | --- |
| `label` | Texto de la etiqueta. |
| `selected` | Si está marcado. |
| `on_select` | Mensaje o callable al pulsarlo. |
| `size` | Tamaño. |
| `text_size` | Tamaño del texto. |
| `spacing` | Separación entre el círculo y el texto. |
| `accent` | Color de acento (parte activa). |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `border_color` | Color del borde. |
| `color` | Color del texto o del icono. |

## Editor de código

### `code_editor`

```python
code_editor(
    id,
    text='',
    *,
    language='txt',
    size=14.0,
    line_height=None,
    font=None,
    width=None,
    height=None,
    padding=None,
    syntax=None,
    bg=None,
    color=None,
    selection_color=None,
    placeholder=None,
    placeholder_color=None,
    gutter=True,
    gutter_color=None,
    gutter_active_color=None,
    gutter_width=None,
    markers=None,
    wrap=False,
    on_change=None,
    on_cursor=None,
    active_line=None,
    scrollbar_color=None,
    annotations=None,
    whitespace=None,
    tab_size=None,
    capture_keys=None,
    on_scroll=None,
    auto_close=False,
    folding=False,
    minimap=None,
    minimap_thumb=None,
    cursor_shape='bar',
    cursor_width=2.0,
    cursor_blink=True,
    cursor_color=None,
    on_zoom=None,
)
```

Un editor de código con resaltado de sintaxis, números de línea y marcadores de git, basado en
`text_editor` de Iced. Es **no controlado**: `text` solo es el valor inicial para ese `id`; el
texto, el cursor y el historial viven en Rust. Usa `Command.set_editor_text` para reemplazarlo.
Para el estilo de Zed usa [`ui.editor`](/pyzed/es/components/code/).

| Parámetro | Descripción |
| --- | --- |
| `id` | Identifica el buffer. Reutilízalo para conservar el estado entre renders. |
| `text` | Texto inicial. |
| `language` | Extensión o nombre del lenguaje (`"py"`, `"rs"`, `"json"`…). |
| `size` | Tamaño de la fuente. |
| `line_height` | Alto de línea en píxeles. |
| `font` | Familia (por defecto, monoespaciada). |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `syntax` | Mapa de scopes TextMate a colores (lo da `Theme.syntax_scopes()`). |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `color` | Color del texto o del icono. |
| `selection_color` | Color de la selección. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `placeholder_color` | Color del placeholder. |
| `gutter` | Muestra los números de línea. |
| `gutter_color` | Color de los números de línea. |
| `gutter_active_color` | Color del número de la línea del cursor. |
| `gutter_width` | Ancho del margen (automático por defecto). |
| `markers` | `{línea: color}` para las marcas de git del margen (líneas desde 1). |
| `wrap` | Ajuste de línea. |
| `on_change` | Callable que recibe el texto completo tras cada edición. |
| `on_cursor` | Callable que recibe `(línea, columna)`, desde 1. |
| `active_line` | Color de fondo de la línea del cursor. |
| `scrollbar_color` | Color de la barra de desplazamiento. |
| `annotations` | `{línea: "texto"}` o `{línea: ("texto", color)}`: texto virtual al final de la línea (code lens, diagnósticos). |
| `whitespace` | Dibuja los espacios como `·` y los tabuladores como `→` en este color. |
| `tab_size` | Tab inserta espacios hasta el siguiente múltiplo; Enter mantiene la sangría; Backspace quita un nivel. |
| `capture_keys` | Teclas que el editor deja al `on_key` de la app (`"up"`, `"enter"`…), por ejemplo con una lista de autocompletado abierta. |
| `on_scroll` | Se llama al desplazar. |
| `auto_close` | Al escribir un paréntesis, corchete, llave o comilla también inserta el de cierre. |
| `folding` | Flechas de plegado en el margen y Ctrl+Shift+[ / ]. |
| `minimap` | Ancho del minimapa en píxeles (`None`: sin minimapa). |
| `minimap_thumb` | Color del resaltado del área visible en el minimapa. |
| `cursor_shape` | `"bar"`, `"block"`, `"underline"` o `"hollow"`. |
| `cursor_width` | Ancho del cursor de barra. |
| `cursor_blink` | Si el cursor parpadea. |
| `cursor_color` | Color del cursor. |
| `on_zoom` | Callable que recibe `1`, `-1` o `0` con Ctrl+= / Ctrl+- / Ctrl+0 y Ctrl+rueda. |
