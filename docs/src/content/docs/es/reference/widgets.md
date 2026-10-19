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

Todo widget tiene `widget.on(...)` (ver [Eventos](/pyzed/es/guides/events/)) y `widget.style(*estilos, **props)`, que le da estilo como CSS: fondo, bordes, radio, sombra, padding, margen, tamaño y la tipografía de todos los textos de dentro. `widget.style_props()` devuelve lo que se fijó. Ver [Estilos](/pyzed/es/guides/styles/).

`widget.animate(*animaciones, **opciones)` reproduce presets o animaciones por keyframes (al aparecer, en hover, al pulsar, con foco, al hacer clic o mientras `active`) y `widget.transition(**props)` anima los cambios de propiedades como una transición CSS. Ver [Animación](/pyzed/es/guides/animation/).

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
    rows=None,
    max_width=None,
    spacing=0.0,
    row_spacing=None,
    height=None,
    aspect_ratio=None,
    width=None,
    padding=None,
    align_x=None,
    align_y=None,
)
```

Coloca los hijos en una rejilla. Con `columns=3` las columnas son iguales (o `max_width` mete tantas como quepan). Con listas de pistas (`columns=[200, "1fr", "auto"]`, `rows=...`) funciona como un grid de CSS: los números son píxeles, `"auto"` se ajusta al contenido y `"<n>fr"` reparte el espacio que sobra. Envuelve los hijos en `pz.cell` para colocarlos y hacer que ocupen varias celdas; el resto llena las celdas libres fila a fila. Ver [Layout](/pyzed/es/guides/layout/#rejillas).

| Parámetro | Descripción |
| --- | --- |
| `children` | Lista de hijos. Se aplanan listas anidadas y se ignoran `None` y `False`, así que puedes escribir `cond and widget`. |
| `columns` | Número de columnas iguales, o pistas: una lista (`[200, "1fr", "auto"]`) o un texto (`"200 1fr auto"`). |
| `rows` | Pistas de las filas, como `columns`. Las filas que no están en la lista son `"auto"`. |
| `max_width` | Mete tantas columnas de como mucho este ancho como quepan (solo con `columns=<int>`). |
| `spacing` | Espacio entre celdas. |
| `row_spacing` | Espacio entre filas, si es distinto. |
| `height` | Con `columns=<int>`: alto de cada fila. Con pistas: alto de la rejilla. |
| `aspect_ratio` | Mantiene las celdas en esta proporción ancho/alto (solo con `columns=<int>`). |
| `width` | Con `columns=<int>`: píxeles. Con pistas: ancho de la rejilla (por defecto `"fill"`). |
| `padding` | Espacio alrededor de las celdas. |
| `align_x` | Alineación horizontal de cada elemento en su celda: `"start"`, `"center"`, `"end"`. |
| `align_y` | Alineación vertical de cada elemento en su celda. |

```python
pz.grid([pz.cell(header, column=0, row=0, column_span=2), sidebar, content],
        columns=[200, "1fr"], rows=[48, "1fr"], spacing=8, height="fill")
```

### `cell`

```python
cell(
    content,
    *,
    column=None,
    row=None,
    column_span=1,
    row_span=1,
    align_x=None,
    align_y=None,
)
```

Coloca un hijo en una rejilla con pistas: su columna y fila (desde 0) y cuántas ocupa. Los hijos sin celda llenan las celdas libres fila a fila. Fuera de una rejilla es solo el hijo.

| Parámetro | Descripción |
| --- | --- |
| `content` | El widget. |
| `column` | Índice de columna (desde 0). |
| `row` | Índice de fila (desde 0). |
| `column_span` | Columnas que ocupa. |
| `row_span` | Filas que ocupa. |
| `align_x` | Alineación horizontal en la celda. |
| `align_y` | Alineación vertical en la celda. |

```python
pz.cell(ui.button("Guardar"), column=2, row=3, align_x="end")
```

### `flex`

```python
flex(
    children=(),
    *,
    direction='row',
    justify='start',
    align='start',
    gap=0,
    wrap=False,
    padding=None,
    width=None,
    height=None,
)
```

Coloca los hijos a lo largo de un eje, como flexbox de CSS, con `justify` en el eje principal y `align` en el transversal. Usa `pz.flex_item` para que un hijo crezca o tenga un tamaño fijo.

| Parámetro | Descripción |
| --- | --- |
| `children` | Los widgets, o `pz.flex_item(...)` para hijos con su propio tamaño. |
| `direction` | `"row"` o `"column"`. |
| `justify` | `"start"`, `"center"`, `"end"`, `"between"`, `"around"` o `"evenly"`. No tiene efecto si algún hijo crece. |
| `align` | Alineación transversal: `"start"`, `"center"` o `"end"`. |
| `gap` | Espacio entre hijos. |
| `wrap` | Pasa a nuevas líneas (solo filas con `justify="start"`). |
| `padding` | Espacio alrededor de los hijos. |
| `width` | Ancho. |
| `height` | Alto. |

```python
pz.flex([logo, titulo, pz.flex_item(buscador, grow=1), avatar], justify="between", align="center", gap=8)
```

### `flex_item`

```python
flex_item(content, *, grow=1, basis=None, align=None)
```

Da tamaño a un hijo de `pz.flex`.

| Parámetro | Descripción |
| --- | --- |
| `content` | El widget. |
| `grow` | Parte del espacio libre en el eje principal (`0` mantiene su tamaño natural). |
| `basis` | Un tamaño fijo en píxeles en el eje principal, en lugar de crecer. |
| `align` | Alineación transversal de este hijo. |

### `anchor`

```python
anchor(
    content,
    *,
    x=0,
    y=0,
    width=100,
    height=28,
    anchor='top_left',
    min_width=0,
    min_height=0,
    max_width=0,
    max_height=0,
    pivot=(0.5, 0.5),
    rotate=0,
)
```

Coloca un hijo de `pz.anchor_layout` en `x`, `y` con `width` y `height` (en el tamaño de diseño de la disposición) y dice cómo sigue a un cambio de tamaño.

| Parámetro | Descripción |
| --- | --- |
| `content` | El widget. |
| `x` | Borde izquierdo en el tamaño de diseño. |
| `y` | Borde superior en el tamaño de diseño. |
| `width` | Ancho en el tamaño de diseño. |
| `height` | Alto en el tamaño de diseño. |
| `anchor` | Un preset de `pyzed.anchors.PRESETS` (`"top_right"`, `"bottom_wide"`, `"center"`, `"full"`...), palabras (`"left right bottom"`) o una tupla de bordes. |
| `min_width` | Ancho mínimo al estirarse (`0`: sin límite). |
| `min_height` | Alto mínimo al estirarse. |
| `max_width` | Ancho máximo al estirarse (`0`: sin límite). |
| `max_height` | Alto máximo al estirarse. |
| `pivot` | `(x, y)` de `0` a `1`: el punto que queda fijo cuando un límite lo frena, y alrededor del que gira `rotate`. |
| `rotate` | Grados en sentido horario. |

```python
pz.anchor(ui.button("Cerrar", on_close), x=284, y=252, width=100, height=32, anchor="bottom_right")
```

### `anchor_layout`

```python
anchor_layout(children, *, design=None, width='fill', height='fill')
```

Coloca libremente hijos hechos con `pz.anchor`, como un formulario diseñado: al cambiar de tamaño, cada hijo mantiene su distancia a los bordes a los que está anclado, se estira entre bordes opuestos y se queda centrado en los demás casos. Los últimos hijos se dibujan encima. Ver [Disposiciones ancladas](/pyzed/es/guides/layout/#disposiciones-ancladas).

| Parámetro | Descripción |
| --- | --- |
| `children` | Hijos hechos con `pz.anchor(...)` (`None` se ignora). |
| `design` | `(ancho, alto)` en el que se colocaron los hijos; por defecto, el más pequeño que los contiene. |
| `width` | Ancho. |
| `height` | Alto. |

```python
pz.anchor_layout([
    pz.anchor(ui.heading("Informe"), x=16, y=12, width=368, height=28, anchor="top_wide"),
    pz.anchor(ui.button("Cerrar", on_close), x=284, y=252, width=100, height=32, anchor="bottom_right"),
], design=(400, 300))
```

### `place`

```python
place(
    rect,
    anchor,
    design,
    actual,
    *,
    min_size=(0, 0),
    max_size=(0, 0),
    pivot=(0.5, 0.5),
)
```

Dónde va una caja diseñada en un padre de tamaño `design` dentro de un padre de tamaño `actual`, siguiendo su anclaje, con límites de tamaño y un pivote. La cuenta detrás de `pz.anchor_layout` y de los formularios diseñados.

| Parámetro | Descripción |
| --- | --- |
| `rect` | `(x, y, ancho, alto)` en el tamaño de diseño. |
| `anchor` | Un preset, palabras o bordes. |
| `design` | El tamaño de diseño del padre. |
| `actual` | El tamaño actual del padre. |
| `min_size` | Límites inferiores `(ancho, alto)` (`0`: ninguno). |
| `max_size` | Límites superiores `(ancho, alto)` (`0`: ninguno). |
| `pivot` | El punto que queda fijo cuando un límite frena el estiramiento. |

```python
anchors.place((20, 20, 100, 30), "top_right", design=(400, 300), actual=(600, 300))  # (220, 20, 100, 30)
```

### `PRESETS`

Los 16 presets de anclaje por nombre (`top_left`, `top_center`, `top_right`, `top_wide`, `center_left`, `center`, `center_right`, `center_wide`, `bottom_left`, `bottom_center`, `bottom_right`, `bottom_wide`, `left_tall`, `center_tall`, `right_tall`, `full`), cada uno con la tupla de bordes a los que ancla.

### `edges`

```python
edges(anchor)
```

Los bordes de un anclaje dado como nombre de preset, palabras o bordes. Lanza `ValueError` con cualquier otra cosa.

| Parámetro | Descripción |
| --- | --- |
| `anchor` | Lo que se lee. |

### `preset_of`

```python
preset_of(edges)
```

El nombre del preset que corresponde a un conjunto de bordes (todo conjunto es uno de los 16).

| Parámetro | Descripción |
| --- | --- |
| `edges` | Bordes. |

### `preset`

```python
preset(horizontal, vertical)
```

El preset colocado `horizontal` (`left`, `center`, `right`, `wide`) y `vertical` (`top`, `center`, `bottom`, `tall`).

| Parámetro | Descripción |
| --- | --- |
| `horizontal` | Colocación en el eje x. |
| `vertical` | Colocación en el eje y. |

### `axes`

```python
axes(edges)
```

La colocación `(horizontal, vertical)` de un conjunto de bordes, como `("right", "top")`.

| Parámetro | Descripción |
| --- | --- |
| `edges` | Bordes. |

### `snap_to`

```python
snap_to(anchor, rect, parent, margin=0.0)
```

Una caja movida (y redimensionada en los ejes estirados) adonde apunta un anclaje: contra los bordes anclados, centrada o llenando el padre, a `margin` píxeles.

| Parámetro | Descripción |
| --- | --- |
| `anchor` | Un preset, palabras o bordes. |
| `rect` | La caja. |
| `parent` | El tamaño del padre. |
| `margin` | Distancia a los bordes. |

### `offsets`

```python
offsets(rect, parent)
```

Las distancias `(izquierda, arriba, derecha, abajo)` de cada lado del padre a una caja.

| Parámetro | Descripción |
| --- | --- |
| `rect` | La caja. |
| `parent` | El tamaño del padre. |

### `pivot_offset`

```python
pivot_offset(size, pivot, rotate=0.0, scale=1.0)
```

La traslación que hace que una rotación y una escala (que giran alrededor del centro de la caja) giren alrededor de `pivot`.

| Parámetro | Descripción |
| --- | --- |
| `size` | El tamaño de la caja. |
| `pivot` | `(x, y)` de `0` a `1`. |
| `rotate` | Grados en sentido horario. |
| `scale` | Factor de escala. |

### `resizable`

```python
resizable(
    content,
    *,
    edge='right',
    size=240.0,
    min_size=80.0,
    max_size=None,
    on_resize=None,
    color=None,
    hover_color=None,
    thickness=1.0,
    handle=8.0,
    width=None,
    height=None,
)
```

Un panel cuyo borde `edge` se arrastra para cambiar su tamaño. Conserva el tamaño al que lo arrastra el usuario; `on_resize(size)` se llama al terminar de arrastrar para que puedas guardarlo. Si `size` cambia después, vuelve a ese valor.

| Parámetro | Descripción |
| --- | --- |
| `content` | El contenido del panel. |
| `edge` | El borde con el asa: `"right"` (una barra lateral izquierda), `"left"`, `"top"` (un panel inferior) o `"bottom"`. |
| `size` | Ancho inicial (alto con los bordes top/bottom). |
| `min_size` | Tamaño mínimo. |
| `max_size` | Tamaño máximo. |
| `on_resize` | Se llama con el nuevo tamaño al terminar de arrastrar. |
| `color` | Color de la línea. |
| `hover_color` | Color de la línea al pasar el ratón o arrastrar. |
| `thickness` | Grosor de la línea. |
| `handle` | Ancho de la zona que se puede agarrar. |
| `width` | Ancho con los bordes top/bottom. |
| `height` | Alto con los bordes left/right. |

```python
pz.row([pz.resizable(barra, edge="right", size=240, on_resize=self.guardar_ancho), editor])
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
| `ratio` | Proporción del primer panel (0–1). El divisor conserva la proporción a la que lo arrastra el usuario hasta que esto cambia. |
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

### `FlexItem`

```python
class FlexItem
```

Un hijo de `pz.flex` con su propio tamaño; se crea con `pz.flex_item`.

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
    align_x=None,
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
| `align_x` | Alineación horizontal: `"start"`/`"left"`, `"center"`, `"end"`/`"right"`. |

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
    on_action=None,
    highlights=None,
    highlight_color=None,
    match_brackets=True,
    selection_highlight=True,
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
| `on_action` | Callable que recibe el nombre de cada acción del editor que se ejecuta (`"undo"`, `"select_next"`…). |
| `highlights` | Rangos pintados detrás del texto (resultados de búsqueda): `[(línea, columna, línea_final, columna_final)]`, desde 1, con el final excluido. |
| `highlight_color` | Color de `highlights`. |
| `match_brackets` | Remarca el corchete pareja del que está junto al cursor. |
| `selection_highlight` | Resalta las demás apariciones del texto seleccionado. |

## Estilos

### `Style`

```python
class Style
```

Un conjunto reutilizable de propiedades de estilo para `widget.style(...)`, el `style=` de un componente o `App.style`. Combina estilos con `|` (gana el de la derecha). Ver [Estilos](/pyzed/es/guides/styles/).

| Parámetro | Descripción |
| --- | --- |
| `styles` | Estilos, dicts o nombres de estilo de partida. |
| `props` | Propiedades: `background`, `color`, `font`, `weight`, `italic`, `size`, `line_height`, `border_color`, `border_width`, `border` (`(ancho, color)`), `radius`, `shadow`, `padding`, `margin`, `width`, `height`, `max_width`, `max_height`, `align_x`, `align_y`, `clip`. Efectos: `opacity`, `translate` (`(x, y)`, píxeles o `"50%"`), `scale`, `glow` (un color, un tamaño o `(color, tamaño)`), `bloom` (un color o `(color, intensidad)`) y `glass` (`True`, un tinte o `{"tint", "strength"}`). Los colores pueden ser tokens del tema. |

```python
tarjeta = pz.Style(background="panel", border=(1, "border"), radius=8, padding=12)
pz.column([...]).style(tarjeta | pz.Style(shadow=("#0006", (0, 4), 12)))
```

**Métodos y propiedades**

#### `Style.get`

```python
Style.get(key, default=None)
```

Devuelve el valor de una propiedad (se aceptan alias), o `default` si no está fijada.

#### `Style.merge`

```python
Style.merge(*styles, **props)
```

Un estilo nuevo con `styles` y `props` encima de este.

#### `Style.without`

```python
Style.without(*keys)
```

Un estilo nuevo sin estas propiedades.

#### `Style.text`

```python
Style.text()
```

Solo las propiedades de texto (lo que un estilo pasa a los textos de dentro).

#### `Style.to_dict`

```python
Style.to_dict()
```

Las propiedades en formato apto para JSON (los gradientes y pinturas pasan a ser dicts).

#### `Style.from_dict`

```python
@classmethod
Style.from_dict(data)
```

Crea un estilo a partir de datos hechos con `to_dict` (se aceptan alias).

### `define_style`

```python
define_style(name, *styles, **props)
```

Pone nombre a un estilo para usarlo así: `widget.style("card")`. Lo devuelve.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del estilo. |
| `styles` | Estilos a combinar. |
| `props` | Propiedades encima. |

### `set_style`

```python
set_style(*styles, **props)
```

Fija el estilo global de todas las ventanas, por debajo del `style` de cada una. Sin argumentos lo quita.

| Parámetro | Descripción |
| --- | --- |
| `styles` | Estilos a combinar. |
| `props` | Propiedades encima. |

### `Gradient`

```python
class Gradient
```

Un gradiente lineal para fondos. Los ángulos siguen CSS: 0 arriba, 90 derecha, 180 (por defecto) abajo. Hasta 8 paradas.

| Parámetro | Descripción |
| --- | --- |
| `stops` | Colores, repartidos por igual, o pares `(posición, color)` con posiciones de 0 a 1. |
| `angle` | Dirección en grados. |

```python
pz.container(None, height=80).style(background=pz.Gradient(["#f97316", "#7c3aed"], angle=90))
```

**Métodos y propiedades**

#### `Gradient.to_value`

```python
Gradient.to_value()
```

`(angle, [(offset, "#rrggbbaa"), ...])`, la forma que los widgets aceptan como `gradient=`.

#### `Gradient.to_dict`

```python
Gradient.to_dict()
```

Devuelve el gradiente como datos listos para JSON: `{"type": "linear", "angle", "stops"}`.

### `Mask`

```python
class Mask
```

Una máscara de opacidad para un `Paint`: cuánto se ve el relleno a lo largo de una dirección. Sobre un gradiente sigue su dirección.

| Parámetro | Descripción |
| --- | --- |
| `stops` | Opacidades (0 a 1), repartidas por igual, o pares `(posición, opacidad)`. |
| `angle` | Dirección cuando el relleno es un color liso. |

**Métodos y propiedades**

#### `Mask.at`

```python
Mask.at(offset)
```

Devuelve la opacidad (0 a 1) en `offset` (0 a 1), interpolando entre paradas.

#### `Mask.to_dict`

```python
Mask.to_dict()
```

Devuelve la máscara como datos listos para JSON: `{"angle", "stops"}`.

### `Paint`

```python
class Paint
```

Un relleno: un color o un `Gradient` con opacidad general y una `Mask` opcional. Sirve en cualquier fondo.

| Parámetro | Descripción |
| --- | --- |
| `fill` | Un color o un `Gradient`. |
| `opacity` | De 0 a 1; multiplica el alfa del relleno. |
| `mask` | Una `pz.Mask`. |

```python
pz.Paint("#3b82f6", opacity=0.8, mask=pz.Mask([1, 0]))  # se desvanece hacia abajo
```

**Métodos y propiedades**

#### `Paint.resolve`

```python
Paint.resolve()
```

`(color, gradient)`: lo que dibuja un contenedor (uno de los dos es `None`).

#### `Paint.to_dict`

```python
Paint.to_dict()
```

Devuelve la pintura como datos listos para JSON: `fill`, `opacity` y `mask` cuando la hay.

### `global_style`

```python
global_style()
```

El estilo fijado con `set_style` (`None` si no hay).

### `named_styles`

```python
named_styles()
```

Los estilos definidos con `define_style`, por nombre.

### `apply_global`

```python
apply_global(view, style=None)
```

`view` con el estilo global de una ventana: las propiedades de texto completan lo que los textos no fijan.

### `themed`

```python
themed(theme, style)
```

`theme` con el color de texto, el fondo, el color de borde, el tamaño y el radio de un estilo global.

### `to_hex`

```python
to_hex(color)
```

Cualquier color como `"#rrggbb"` o `"#rrggbbaa"` (con los tokens del tema resueltos).

### `paint_from_dict`

```python
paint_from_dict(data)
```

Reconstruye un `Gradient` o un `Paint` guardado con `to_dict()`.

## Animación

### `Animation`

```python
@dataclass
class Animation(keyframes=(), duration=300, delay=0, easing='ease', repeat=1, direction='normal', fill='both', on='mount', category='custom', description='', _frames=())
```

Una animación por keyframes, como una regla CSS `@keyframes` con su timing.

`keyframes` es una lista de frames `{propiedad: valor}` (repartidos por igual; un frame puede
fijar `offset` y `easing`) o un dict de offsets (`0` a `1`, `"50%"`, `"from"`, `"to"`) a
frames. Una propiedad que falte al principio o al final sale del valor propio del widget o
vuelve a él, y `None` nombra ese valor explícitamente:

```python
pz.Animation([{"opacity": 0, "y": 12}, {"opacity": 1, "y": 0}], duration=250)
pz.Animation({0: {"scale": 1}, "50%": {"scale": 1.1}, 1: {"scale": 1}}, repeat="infinite")
```

Los demás campos son los valores por defecto que sobrescriben las opciones de `animate()`.
`category` y `description` dicen a los editores dónde y cómo mostrar un preset.

**Métodos y propiedades**

#### `Animation.properties`

```python
Animation.properties  # property
```

Las propiedades que cambian los keyframes, en orden de aparición.

#### `Animation.total`

```python
Animation.total  # property
```

Milisegundos del principio al final (`inf` si se repite para siempre).

#### `Animation.with_options`

```python
Animation.with_options(**options)
```

Una copia con otro timing o disparador (`duration`, `easing`, `on`...).

#### `Animation.compile`

```python
Animation.compile(**options)
```

Los datos simples que reproduce la parte nativa (los usa `animate()`).

#### `Animation.to_dict`

```python
Animation.to_dict()
```

Datos listos para JSON (`Animation.from_dict` los vuelve a leer).

#### `Animation.from_dict`

```python
@classmethod
Animation.from_dict(data)
```

Reconstruye una animación guardada con `to_dict`.

### `define_animation`

```python
define_animation(name, animation=None, **options)
```

Da nombre a una animación para que `animate(nombre)` la reproduzca; la devuelve.

`define_animation("wiggle", [{"x": 0}, {"x": -4}, {"x": 4}, {"x": 0}], duration=300)`

### `presence`

```python
presence(
    content,
    key,
    *,
    enter='fade_in',
    exit='fade_out',
    id=None,
    duration=None,
    easing=None,
)
```

Muestra `content` y, cuando cambia `key`, anima la salida del contenido anterior (`exit`)
mientras entra el nuevo (`enter`), como transiciones entre páginas:

```python
pz.presence(self.vista_pagina(), key=self.pagina, enter="slide_in_right", exit="fade_out")
```

`id` distingue unas presences de otras (por defecto es el lugar desde donde se llama, así que
da uno cuando la misma línea crea varias). `duration` y `easing` sobrescriben los de ambas animaciones.

### `stagger`

```python
stagger(items, animation='fade_in_up', *, step=40, delay=0, **options)
```

`items` con la misma animación, cada uno empezando `step` milisegundos después del anterior
(una lista que entra en cascada):

```python
pz.column(pz.stagger([fila(i) for i in items], "fade_in_up", step=30))
```

### `set_reduced_motion`

```python
set_reduced_motion(on=True)
```

Apaga el movimiento (`True`) o lo vuelve a encender: las animaciones muestran al instante su estado de reposo.

Por defecto Pyzed sigue el ajuste de accesibilidad "reducir movimiento" del sistema (se lee al
arrancar la app, ver `pyzed.system_reduced_motion`). `True` o `False` lo reemplazan (por ejemplo
desde los ajustes de tu app, o en tests) y `None` vuelve a seguir al sistema. La variable de
entorno `PYZED_REDUCED_MOTION` (`1` o `0`) también lo reemplaza.

### `system_reduced_motion`

```python
system_reduced_motion()
```

Si el sistema pide a las apps reducir el movimiento (`None` si no se sabe).

### `reduced_motion`

```python
reduced_motion()
```

Si el movimiento reducido está encendido.

### `animation`

```python
animation(name)
```

La animación llamada `name` (un preset o una definida con `define_animation`).

### `presets`

```python
presets(category=None)
```

Las animaciones con nombre (todas, o una `category`: entrance, exit, attention, interaction, loop).

### `ease`

```python
ease(easing, t)
```

`easing` en `t` (0 a 1), la curva que usan las animaciones: `ease("ease_out", 0.5)`.

Útil para animar tus propios dibujos (`pz.canvas`) con las mismas curvas.

### `window_animations`

```python
window_animations(window, closing=False)
```

La animación que reproduce una ventana al abrirse (o cerrarse), según su `transition` y `exit_transition` (una lista vacía si no tiene).

### `PRESETS`

Todas las animaciones con nombre (los presets incluidos y los añadidos con `define_animation`), asociadas a su `Animation`. Ver [la lista de presets](/pyzed/es/guides/animation/#presets).

### `CATEGORIES`

Categorías de presets: `entrance` (entrada), `exit` (salida), `attention` (atención), `interaction` (interacción) y `loop` (bucle).

### `EASINGS`

Nombres de easing (`linear`, `ease`, `ease_out_cubic`, `ease_out_back`, `spring`...). `animate()` también acepta Béziers cúbicas `(x1, y1, x2, y2)` y `"steps(n)"`.

### `TRIGGERS`

Qué reproduce una animación: `mount`, `hover`, `press`, `focus`, `click` y `active`.

### `PROPERTIES`

Las propiedades que cambian las animaciones y transiciones: `opacity`, `x`, `y`, `scale`, `background`, `border_color`, `color`, `radius`, `border_width`, `glow` y `glow_color`.

### `WINDOW_TRANSITIONS`

Nombres para `Window.transition` (`fade`, `zoom`, `pop`, `slide_up`, `slide_down`, `slide_left`, `slide_right`) asociados a sus presets `(apertura, cierre)`.

## Muchos datos

### `virtual_column`

```python
virtual_column(count, item, *, item_height, spacing=0.0, overscan=4, width=None)
```

Una columna de `count` filas de la misma altura que solo construye las filas visibles: `item(índice)` se llama cuando la fila entra en la vista, y las que salen se descartan. Una columna de un millón de filas cuesta lo mismo que una de cincuenta. Ponla dentro de un `scrollable` (se virtualiza contra el área visible del más cercano, o de la ventana).

| Parámetro | Descripción |
| --- | --- |
| `count` | Número de filas. |
| `item` | Función que recibe el índice de una fila y devuelve su widget. |
| `item_height` | Altura de cada fila, en píxeles. |
| `spacing` | Espacio entre filas, en píxeles. |
| `overscan` | Filas extra construidas por encima y por debajo de las visibles, para que el scroll rápido no deje huecos. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |

```python
rows = load_logs()          # una lista con 500 000 entradas

pz.scrollable(
    pz.virtual_column(len(rows), lambda i: pz.text(rows[i]), item_height=20),
    id="logs", height="fill",
)
```

### `memo`

```python
memo(function=None, *, maxsize=64)
```

Decorador que guarda lo que devuelve una función de la vista según sus argumentos, para que el siguiente `view()` reutilice el mismo árbol de widgets mientras no cambien. Pasa como argumentos todo lo que usa el subárbol. Las listas, dicts y sets se comparan por contenido y otros objetos no hashables por identidad; el tema y el idioma actuales siempre forman parte de la clave. `funcion.cache_clear()` vacía su caché.

| Parámetro | Descripción |
| --- | --- |
| `function` | La función a memoizar (al usarlo como `@pz.memo`). |
| `maxsize` | Cuántos resultados guardar por función (se descartan los usados hace más tiempo). |

```python
@pz.memo
def sidebar(files: tuple, selected: str):
    return pz.column([ui.list_item(f, selected=f == selected) for f in files])
```

### `clear_memos`

```python
clear_memos()
```

Vacía la caché de todas las funciones `@pz.memo`.

### `memo_stats`

```python
memo_stats()
```

Devuelve `{"hits": n, "misses": m}`: cuántas llamadas a funciones memoizadas se respondieron desde la caché y cuántas construyeron su resultado.
