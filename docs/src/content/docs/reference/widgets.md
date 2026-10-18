---
title: "Widgets base"
description: "Los widgets nativos de pyzed: layout, texto, controles, editor, svg e iconos."
sidebar:
  order: 3
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs.py. -->

Los widgets base están implementados en Rust y se importan desde `pyzed`. Son los
ladrillos con los que están hechos los [componentes](/pyzed/components/overview/).
Ver la guía de [layout](/pyzed/guides/layout/) para los tamaños, el relleno y los colores.

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
svg(source, *, width=None, height=None, color=None)
```

Una imagen SVG.

| Parámetro | Descripción |
| --- | --- |
| `source` | Ruta a un `.svg`, el código SVG como texto (empieza por `<`) o `bytes`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `color` | Si se indica, tiñe todo el SVG de ese color (útil para iconos monocromos). |

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
| `text_size` | Tamaño del texto de la etiqueta. |
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
| `text_size` | Tamaño del texto de la etiqueta. |
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
    width=None,
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
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
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
)
```

Un editor de código con resaltado de sintaxis, números de línea y marcadores de git, basado en
`text_editor` de Iced. Es **no controlado**: `text` solo es el valor inicial para ese `id`; el
texto, el cursor y el historial viven en Rust. Usa `Command.set_editor_text` para reemplazarlo.
Para el estilo de Zed usa [`ui.editor`](/pyzed/components/code/).

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
