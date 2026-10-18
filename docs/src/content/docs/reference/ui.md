---
title: "Componentes (pyzed.ui)"
description: "Referencia de todos los componentes al estilo de Zed."
sidebar:
  order: 4
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs.py. -->

Firmas y parámetros de todos los componentes. Para verlos con imágenes y ejemplos,
ve a la sección [Componentes](/pyzed/components/overview/).

Todos son funciones que devuelven un `Widget` y leen sus colores del tema actual.
Los parámetros de color aceptan un **token** del tema (`"accent"`, `"text_muted"`,
`"error"`…) o un color hex.

## Básicos

### `label`

```python
label(
    content,
    *,
    color='text',
    size='md',
    weight=None,
    mono=False,
    italic=False,
    wrap=True,
    theme=None,
    **kwargs,
)
```

Texto con un color del tema.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `color` | Token del tema o color hex. Por defecto `"text"`. |
| `size` | `"xs"` (11), `"sm"` (12), `"md"` (13.5), `"lg"` (16), `"xl"` (20), `"2xl"` (26) o un número. |
| `weight` | Peso: `"medium"`, `"semibold"`, `"bold"`… |
| `mono` | Usa la fuente monoespaciada (IBM Plex Mono). |
| `italic` | Cursiva. |
| `wrap` | Ajuste de línea. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |
| `kwargs` | Se pasan a `pyzed.text`. |

### `muted`

```python
muted(content, **kwargs)
```

Un `label` con color `"text_muted"`.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `kwargs` | Los de `label`. |

### `heading`

```python
heading(content, *, level=1, theme=None, **kwargs)
```

Un título en semibold.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `level` | 1 (26 px), 2 (20 px), 3 (16 px) o 4 (13.5 px). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |
| `kwargs` | Los de `label`. |

### `button`

```python
button(
    content=None,
    on_press=None,
    *,
    icon=None,
    icon_position='start',
    icon_color=None,
    variant='filled',
    tint=None,
    size='md',
    selected=False,
    disabled=False,
    full_width=False,
    keys=None,
    theme=None,
    **style,
)
```

El botón de Zed.

| Parámetro | Descripción |
| --- | --- |
| `content` | Texto o widget. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `icon_position` | `"start"` o `"end"`. |
| `icon_color` | Color del icono: un token del tema o un color hex. |
| `variant` | `"filled"`, `"ghost"`, `"subtle"`, `"outline"`, `"solid"`, `"tinted"`, o un color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"`. |
| `tint` | Color de las variantes `solid` y `tinted`. |
| `size` | `"xs"`, `"sm"`, `"md"` o `"lg"`. |
| `selected` | Lo marca como seleccionado. |
| `disabled` | Lo deshabilita (ignora los clics). |
| `full_width` | Ocupa todo el ancho. |
| `keys` | Atajo que se muestra al final, al estilo de Zed: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |
| `style` | Cualquier parámetro de estilo de `pyzed.button` (`bg`, `hover_bg`, `color`…). |

### `icon_button`

```python
icon_button(
    name,
    on_press=None,
    *,
    size='md',
    variant='ghost',
    color=None,
    selected=False,
    disabled=False,
    tooltip=None,
    theme=None,
)
```

Un botón cuadrado con solo un icono (el `IconButton` de Zed).

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del icono. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `size` | `"xs"`, `"sm"`, `"md"` o `"lg"`. |
| `variant` | Como en `ui.button`. Por defecto `"ghost"`. |
| `color` | Color del icono. |
| `selected` | Lo marca como seleccionado. |
| `disabled` | Lo deshabilita (ignora los clics). |
| `tooltip` | Texto del tooltip. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `badge`

```python
badge(content, *, tint='accent', variant='soft', icon=None, theme=None)
```

Una píldora pequeña para estados y contadores.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `variant` | `"soft"`, `"solid"` o `"outline"`. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `indicator`

```python
indicator(color='accent', *, size=6, theme=None)
```

Un punto de color (estado, cambios sin guardar, presencia).

| Parámetro | Descripción |
| --- | --- |
| `color` | Token o color. |
| `size` | Diámetro. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `kbd`

```python
kbd(keys, *, size='sm', theme=None)
```

Dibuja un atajo como teclas: `"ctrl-shift-p"`, `"cmd-k cmd-s"`. En macOS usa símbolos (⌘⇧P) y en el resto palabras.

| Parámetro | Descripción |
| --- | --- |
| `keys` | El atajo. |
| `size` | `"xs"` o `"sm"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `format_keys`

```python
format_keys(keys)
```

Separa un atajo en etiquetas por acorde: `format_keys("ctrl-shift-p") == [["Ctrl", "Shift", "P"]]`. El estilo se controla con `pyzed.ui.base.KEY_STYLE` (`"auto"`, `"symbols"` o `"words"`).

| Parámetro | Descripción |
| --- | --- |
| `keys` | El atajo. |

### `avatar`

```python
avatar(initials, *, color=None, size=22, index=0, theme=None)
```

Un avatar redondo con iniciales.

| Parámetro | Descripción |
| --- | --- |
| `initials` | Iniciales (se usan las dos primeras). |
| `color` | Color de fondo. |
| `size` | Diámetro. |
| `index` | Elige un color de colaborador del tema (`theme.players`). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `tooltip`

```python
tooltip(content, text, *, keys=None, position='bottom', theme=None)
```

Envuelve `content` con un tooltip al estilo de Zed, opcionalmente con su atajo.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `text` | Texto del tooltip. |
| `keys` | Atajo que se muestra al final, al estilo de Zed: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `position` | `"top"`, `"bottom"`, `"left"`, `"right"` o `"cursor"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `divider`

```python
divider(*, vertical=False, color=None, theme=None)
```

Una línea divisoria con el color del tema.

| Parámetro | Descripción |
| --- | --- |
| `vertical` | Vertical en lugar de horizontal. |
| `color` | Color del texto o del icono. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `card`

```python
card(content, *, title=None, actions=(), padding=16, width=None, theme=None)
```

Una superficie con borde para agrupar contenido, con título y acciones opcionales.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `title` | Título. |
| `actions` | Widgets extra (normalmente botones) que se muestran como acciones. |
| `padding` | Relleno interior. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

## Formularios

### `input`

```python
input(
    value,
    on_input=None,
    *,
    placeholder='',
    icon=None,
    on_submit=None,
    id=None,
    size='md',
    secure=False,
    width='fill',
    borderless=False,
    mono=False,
    theme=None,
)
```

Un campo de texto.

| Parámetro | Descripción |
| --- | --- |
| `value` | Texto actual. |
| `on_input` | Callable que recibe el texto nuevo en cada pulsación. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `on_submit` | Mensaje o callable que se envía al pulsar Enter. |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `secure` | Oculta el texto. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `borderless` | Sin borde ni fondo (como en la paleta de comandos). |
| `mono` | Usa la fuente monoespaciada (IBM Plex Mono). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `search_input`

```python
search_input(value, on_input=None, *, placeholder='Search…', **kwargs)
```

Un `input` con icono de lupa.

| Parámetro | Descripción |
| --- | --- |
| `value` | Texto actual. |
| `on_input` | Callable que recibe el texto nuevo en cada pulsación. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `kwargs` | Los de `input`. |

### `switch`

```python
switch(checked, on_toggle=None, *, label=None, theme=None)
```

Un interruptor encendido/apagado.

| Parámetro | Descripción |
| --- | --- |
| `checked` | Estado actual. |
| `on_toggle` | Callable que recibe el nuevo `bool` (o mensaje que se envía). |
| `label` | Texto de la etiqueta. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `checkbox`

```python
checkbox(checked, on_toggle=None, *, label=None, theme=None)
```

Una casilla de verificación.

| Parámetro | Descripción |
| --- | --- |
| `checked` | Estado actual. |
| `on_toggle` | Callable que recibe el nuevo `bool` (o mensaje que se envía). |
| `label` | Texto de la etiqueta. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `slider`

```python
slider(value, on_change=None, *, min=0.0, max=1.0, step=0.01, width='fill', theme=None)
```

Un deslizador.

| Parámetro | Descripción |
| --- | --- |
| `value` | Valor actual. |
| `on_change` | Callable que recibe el nuevo valor. |
| `min` | Mínimo. |
| `max` | Máximo. |
| `step` | Paso. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `progress`

```python
progress(value, *, max=1.0, tint='accent', height=4, width='fill', theme=None)
```

Una barra de progreso fina.

| Parámetro | Descripción |
| --- | --- |
| `value` | Valor actual. |
| `max` | Valor máximo. |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `height` | Grosor. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `segmented`

```python
segmented(options, selected, on_select=None, *, theme=None)
```

Un grupo de botones mutuamente excluyentes (el `ToggleButtonGroup` de Zed).

| Parámetro | Descripción |
| --- | --- |
| `options` | Lista de opciones (textos). |
| `selected` | La opción activa. |
| `on_select` | Callable que recibe el elemento elegido. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `field`

```python
field(title, control, *, description=None, theme=None)
```

Una fila de formulario: título y descripción a la izquierda, control a la derecha (como los ajustes de Zed).

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `control` | El control (switch, input…). |
| `description` | Texto de ayuda. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

## Controles

### `select`

```python
select(
    options,
    selected=None,
    on_select=None,
    *,
    placeholder='Select…',
    width=None,
    size='md',
    theme=None,
)
```

Un desplegable con el estilo del tema (el `DropdownMenu` de Zed). Las opciones se muestran con `str()`, así que sirven textos, enums o dataclasses.

| Parámetro | Descripción |
| --- | --- |
| `options` | Lista de opciones. |
| `selected` | Opción actual. |
| `on_select` | Callable que recibe el elemento elegido. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `radio_group`

```python
radio_group(
    options,
    selected,
    on_select=None,
    *,
    horizontal=False,
    spacing=8,
    theme=None,
)
```

Opciones mutuamente excluyentes como botones de radio.

| Parámetro | Descripción |
| --- | --- |
| `options` | Textos o pares `(valor, etiqueta)`. |
| `selected` | Valor actual. |
| `on_select` | Callable que recibe el valor elegido. |
| `horizontal` | En fila en lugar de columna. |
| `spacing` | Separación entre hijos, en píxeles. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `number_field`

```python
number_field(
    value,
    on_change=None,
    *,
    min=None,
    max=None,
    step=1,
    width=120,
    suffix=None,
    theme=None,
)
```

Un campo numérico con botones −/+ (el `NumericStepper` de Zed). `on_change(valor)` recibe el número ya limitado a `min`/`max`; lo que no se puede leer como número se ignora.

| Parámetro | Descripción |
| --- | --- |
| `value` | Valor actual. |
| `on_change` | Callable que recibe el nuevo valor. |
| `min` | Mínimo. |
| `max` | Máximo. |
| `step` | Paso de los botones. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `suffix` | Unidad que se muestra al final (`"px"`, `"%"`…). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `split_button`

```python
split_button(
    content,
    on_press=None,
    on_menu=None,
    *,
    icon=None,
    variant='filled',
    size='md',
    theme=None,
)
```

Un botón con una flecha aparte para más opciones (el `SplitButton` de Zed). `on_press` ejecuta la acción principal y `on_menu` normalmente abre un `ui.menu` en un `ui.popover`.

| Parámetro | Descripción |
| --- | --- |
| `content` | Texto del botón. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `on_menu` | Mensaje o callable del botón del menú. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `variant` | Como en `ui.button`. |
| `size` | `"xs"`, `"sm"`, `"md"` o `"lg"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `toggle_group`

```python
toggle_group(options, selected, on_select, *, theme=None)
```

Un control segmentado solo con iconos.

| Parámetro | Descripción |
| --- | --- |
| `options` | Pares `(valor, nombre_de_icono)`. |
| `selected` | Valor actual. |
| `on_select` | Callable que recibe el elemento elegido. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `chip`

```python
chip(content, *, on_press=None, on_remove=None, selected=False, icon=None, theme=None)
```

Una etiqueta compacta, opcionalmente pulsable (filtros) y con botón para quitarla.

| Parámetro | Descripción |
| --- | --- |
| `content` | Texto. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `on_remove` | Muestra una ✕ que envía esto al pulsarla. |
| `selected` | Lo marca como seleccionado. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `disclosure`

```python
disclosure(title, content, *, open, on_toggle=None, end=None, theme=None)
```

Una sección plegable: cabecera con flecha que muestra u oculta `content`. El estado abierto es tuyo: cámbialo en `on_toggle`.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título (texto o widget). |
| `content` | Contenido. |
| `open` | Si está abierta. |
| `on_toggle` | Mensaje o callable al pulsar la cabecera. |
| `end` | Widgets al final (derecha). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

## Datos y feedback

### `callout`

```python
callout(
    title,
    description=None,
    *,
    tint='info',
    icon=None,
    actions=(),
    on_dismiss=None,
    theme=None,
)
```

Un aviso en línea (el `Callout`/`Banner` de Zed).

| Parámetro | Descripción |
| --- | --- |
| `title` | Título (texto o widget). |
| `description` | Texto secundario. |
| `tint` | `"info"`, `"success"`, `"warning"`, `"error"` o `"hint"`: elige el color y el icono. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `actions` | Widgets extra (normalmente botones) que se muestran como acciones. |
| `on_dismiss` | Añade un botón de cerrar. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `empty_state`

```python
empty_state(title, description=None, *, icon='inbox', actions=(), theme=None)
```

Un marcador centrado para listas vacías, búsquedas sin resultados, etc.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `description` | Texto secundario. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `actions` | Widgets extra (normalmente botones) que se muestran como acciones. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `settings_group`

```python
settings_group(title, rows, *, description=None, theme=None)
```

Un bloque con título de filas `ui.field` separadas por líneas (la interfaz de ajustes de Zed).

| Parámetro | Descripción |
| --- | --- |
| `title` | Título del grupo. |
| `rows` | Las filas (normalmente `ui.field`). |
| `description` | Texto secundario. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `Column`

```python
@dataclass
class Column(title, key, width='fill', align='start', render=None, sortable=True)
```

Una columna de `ui.table`. `key` es una clave de dict, un nombre de atributo o una función de la fila; `render` (opcional) convierte el valor en un widget. `width` es `"fill"`, un número o `("fill", 2)`.

| Parámetro | Descripción |
| --- | --- |
| `title` | Encabezado (y nombre para ordenar). |
| `key` | Cómo obtener el valor de cada fila. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `align` | `"start"`, `"center"` o `"end"`. |
| `render` | Función valor → widget. |
| `sortable` | Si el encabezado se puede pulsar para ordenar. |

### `table`

```python
table(
    columns,
    rows,
    *,
    sort_by=None,
    descending=False,
    on_sort=None,
    on_row_press=None,
    selected=None,
    striped=False,
    row_height=30,
    height=None,
    theme=None,
)
```

Una tabla de datos con encabezado fijo, orden opcional y selección de filas. El orden se hace aquí cuando `sort_by` nombra una columna: pulsar un encabezado llama a `on_sort(título)` y tú cambias `sort_by`/`descending` en tu estado.

| Parámetro | Descripción |
| --- | --- |
| `columns` | `ui.Column` o claves simples. |
| `rows` | Dicts u objetos. |
| `sort_by` | Título de la columna por la que se ordena. |
| `descending` | Orden descendente. |
| `on_sort` | Callable que recibe el título pulsado. |
| `on_row_press` | Callable que recibe la fila pulsada. |
| `selected` | La fila resaltada. |
| `striped` | Filas alternas sombreadas. |
| `row_height` | Alto de cada fila. |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `stat`

```python
stat(title, value, *, delta=None, trend=None, width=None, theme=None)
```

Un número de panel: título, valor grande, variación opcional (`+4.2%`) y sparkline.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `value` | Valor actual. |
| `delta` | Variación en %; verde si es positiva, roja si no. |
| `trend` | Valores para la sparkline. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `sparkline`

```python
sparkline(values, *, width=120, height=32, tint='accent', fill=True, theme=None)
```

Un gráfico de línea diminuto para tendencias.

| Parámetro | Descripción |
| --- | --- |
| `values` | Valores. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `fill` | Rellena el área bajo la línea. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `bar_chart`

```python
bar_chart(values, *, labels=None, width=320, height=160, tint='accent', theme=None)
```

Un gráfico de barras vertical con etiquetas opcionales.

| Parámetro | Descripción |
| --- | --- |
| `values` | Valores. |
| `labels` | Etiquetas bajo cada barra. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `donut`

```python
donut(values, *, colors=None, size=96, thickness=14, label=None, theme=None)
```

Un gráfico de anillo; `label` se dibuja en el centro.

| Parámetro | Descripción |
| --- | --- |
| `values` | Valores. |
| `colors` | Colores (por defecto, los del tema). |
| `size` | Tamaño. |
| `thickness` | Grosor del anillo. |
| `label` | Texto central. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `spinner`

```python
spinner(*, size=16, tint='accent', speed=1.0, theme=None)
```

Un arco que gira para estados de carga. Su ángulo sale del reloj, así que mantén una suscripción `pz.every(1/30, ...)` activa mientras se muestra.

| Parámetro | Descripción |
| --- | --- |
| `size` | Tamaño. |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `speed` | Vueltas por segundo. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `count_badge`

```python
count_badge(count, *, tint='accent', max=99, theme=None)
```

Un contador redondo (notificaciones, problemas…). Muestra `99+` por encima de `max`.

| Parámetro | Descripción |
| --- | --- |
| `count` | El número. |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `max` | Máximo antes de mostrar `N+`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `facepile`

```python
facepile(people, *, size=22, overlap=6, max_shown=5, theme=None)
```

Avatares superpuestos de colaboradores, como en la barra de título de Zed. Los que pasan de `max_shown` se agrupan en `+N`.

| Parámetro | Descripción |
| --- | --- |
| `people` | Iniciales o nombres. |
| `size` | Tamaño. |
| `overlap` | Solapamiento en píxeles. |
| `max_shown` | Cuántos mostrar. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `diff_stat`

```python
diff_stat(added, removed, *, blocks=5, theme=None)
```

`+12 −3` con bloques de colores al estilo de GitHub.

| Parámetro | Descripción |
| --- | --- |
| `added` | Líneas añadidas. |
| `removed` | Líneas eliminadas. |
| `blocks` | Número de bloques. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `keybinding_hint`

```python
keybinding_hint(text, keys, *, theme=None)
```

Una pista atenuada como «Abrir archivo Ctrl P» para pies y estados vacíos.

| Parámetro | Descripción |
| --- | --- |
| `text` | Texto. |
| `keys` | Atajo que se muestra al final, al estilo de Zed: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `markdown`

```python
markdown(source, *, size=None, on_link=None, width=None, theme=None)
```

`pz.markdown` con los colores de texto, enlaces y código del tema.

| Parámetro | Descripción |
| --- | --- |
| `source` | El texto Markdown. |
| `size` | Tamaño. |
| `on_link` | Callable que recibe la URL al pulsar un enlace. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `split`

```python
split(
    first,
    second,
    *,
    ratio=0.5,
    on_resize=None,
    vertical=False,
    min_size=80,
    theme=None,
    **kwargs,
)
```

`pz.split` con el divisor del color de borde del tema (acento al arrastrarlo).

| Parámetro | Descripción |
| --- | --- |
| `first` | Primer panel. |
| `second` | Segundo panel. |
| `ratio` | Proporción del primero (0–1). |
| `on_resize` | Callable que recibe la nueva proporción. |
| `vertical` | Orientación vertical. |
| `min_size` | Tamaño mínimo de cada panel. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |
| `kwargs` | Los de `pz.split`. |

## Listas, árbol y menús

### `list_item`

```python
list_item(
    content,
    on_press=None,
    *,
    icon=None,
    icon_color=None,
    start=None,
    end=None,
    selected=False,
    focused=False,
    indent=0,
    height=26,
    color=None,
    inset=False,
    disabled=False,
    on_right_press=None,
    theme=None,
)
```

Una fila de lista (el `ListItem` de Zed): icono, texto y un hueco al final.

| Parámetro | Descripción |
| --- | --- |
| `content` | Texto o widget. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `icon_color` | Color del icono: un token del tema o un color hex. |
| `start` | Widgets al inicio (izquierda). |
| `end` | Widgets al final (derecha). |
| `selected` | Lo marca como seleccionado. |
| `focused` | Dibuja un borde de foco. |
| `indent` | Sangría a la izquierda, en píxeles. |
| `height` | Alto de la fila. |
| `color` | Color del texto. |
| `inset` | Con margen y esquinas redondeadas (menús, paletas). |
| `disabled` | Lo deshabilita (ignora los clics). |
| `on_right_press` | Clic derecho. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `list_header`

```python
list_header(title, *, end=None, theme=None)
```

Un encabezado de sección para listas.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `end` | Widgets al final (derecha). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `TreeNode`

```python
@dataclass
class TreeNode(name, children=None, id=None, status=None, icon=None, icon_color=None)
```

Un archivo o carpeta para `ui.tree`. Las carpetas tienen `children` (lista). `status` es `"modified"`, `"created"`, `"deleted"`, `"conflict"` o `"ignored"`. `TreeNode.from_paths(paths, status=None)` construye el árbol a partir de rutas como `"src/main.rs"`, con las carpetas primero y el estado de git propagado a las carpetas.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre visible. |
| `children` | Hijos (`None` si es un archivo). |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `status` | Estado de git. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `icon_color` | Color del icono: un token del tema o un color hex. |

### `tree`

```python
tree(
    nodes,
    *,
    expanded,
    selected=None,
    on_toggle=None,
    on_select=None,
    indent=14,
    item_height=24,
    theme=None,
)
```

Un árbol de archivos plegable (el panel de proyecto de Zed).

| Parámetro | Descripción |
| --- | --- |
| `nodes` | Lista de `TreeNode`. |
| `expanded` | Conjunto de ids de carpetas abiertas. |
| `selected` | Id del nodo seleccionado. |
| `on_toggle` | Se llama con el id de la carpeta pulsada. |
| `on_select` | Se llama con el id del archivo pulsado. |
| `indent` | Sangría a la izquierda, en píxeles. |
| `item_height` | Alto de cada fila. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `MenuItem`

```python
@dataclass
class MenuItem(label, on_press=None, icon=None, keys=None, disabled=False, danger=False, checked=None)
```

Una entrada de `ui.menu`.

| Parámetro | Descripción |
| --- | --- |
| `label` | Texto de la etiqueta. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `keys` | Atajo que se muestra al final, al estilo de Zed: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `disabled` | Lo deshabilita (ignora los clics). |
| `danger` | En rojo (acciones destructivas). |
| `checked` | Muestra una marca (`True`/`False`) o nada (`None`). |

### `menu`

```python
menu(items, *, width=240, theme=None)
```

Un menú contextual flotante. Usa `ui.SEPARATOR` entre grupos; un texto suelto es un encabezado.

| Parámetro | Descripción |
| --- | --- |
| `items` | Lista de `MenuItem`, `ui.SEPARATOR` o textos. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `SEPARATOR`

Separador para `ui.menu`.

## Navegación

### `Tab`

```python
@dataclass
class Tab(id, label, icon=None, icon_color=None, dirty=False, preview=False, status=None)
```

Una pestaña. `Tab.for_file(path, **kwargs)` la crea con el nombre y el icono del archivo.

| Parámetro | Descripción |
| --- | --- |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `label` | Texto de la etiqueta. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `icon_color` | Color del icono: un token del tema o un color hex. |
| `dirty` | Cambios sin guardar (muestra un punto). |
| `preview` | Pestaña de vista previa (en cursiva). |
| `status` | Estado de git (tiñe el nombre). |

### `tab`

```python
tab(item, *, active, on_select=None, on_close=None, height=32, theme=None)
```

Una sola pestaña. Normalmente se usa `tab_bar`.

| Parámetro | Descripción |
| --- | --- |
| `item` | El `Tab`. |
| `active` | Si es la activa. |
| `on_select` | Callable que recibe el elemento elegido. |
| `on_close` | Mensaje o callable que se envía al pulsar la X. |
| `height` | Alto. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `tab_bar`

```python
tab_bar(
    tabs,
    active,
    *,
    on_select=None,
    on_close=None,
    start=(),
    end=(),
    height=32,
    theme=None,
)
```

Una fila de pestañas con controles opcionales al principio y al final (navegación, dividir, +). El botón de cerrar aparece en la activa y al pasar el ratón.

| Parámetro | Descripción |
| --- | --- |
| `tabs` | Lista de `Tab`. |
| `active` | Id de la pestaña activa. |
| `on_select` | Callable que recibe el elemento elegido. |
| `on_close` | Mensaje o callable que se envía al pulsar la X. |
| `start` | Widgets al inicio (izquierda). |
| `end` | Widgets al final (derecha). |
| `height` | Alto. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `breadcrumbs`

```python
breadcrumbs(parts, *, separator='›', on_press=None, theme=None)
```

`src › main.rs › fn main`. Las partes pueden ser textos o tuplas `(icono, texto)`.

| Parámetro | Descripción |
| --- | --- |
| `parts` | Las partes. |
| `separator` | Separador. |
| `on_press` | Se llama con el índice de la parte pulsada. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `toolbar`

```python
toolbar(start=(), end=(), *, height=32, theme=None)
```

La barra bajo las pestañas: breadcrumbs a la izquierda y acciones del buffer a la derecha.

| Parámetro | Descripción |
| --- | --- |
| `start` | Widgets al inicio (izquierda). |
| `end` | Widgets al final (derecha). |
| `height` | Alto. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

## Workspace

### `workspace`

```python
workspace(
    center,
    *,
    title_bar=None,
    left=None,
    right=None,
    bottom=None,
    status_bar=None,
    left_width=240,
    right_width=320,
    bottom_height=220,
    theme=None,
)
```

El layout de una ventana de Zed: barra de título, docks izquierdo, derecho e inferior, centro y barra de estado. Pasa `None` para ocultar un dock.

| Parámetro | Descripción |
| --- | --- |
| `center` | Contenido central (normalmente pestañas + editor). |
| `title_bar` | Barra de título (`ui.title_bar`). |
| `left` | Dock izquierdo. |
| `right` | Dock derecho. |
| `bottom` | Dock inferior. |
| `status_bar` | Barra de estado (`ui.status_bar`). |
| `left_width` | Ancho del dock izquierdo. |
| `right_width` | Ancho del dock derecho. |
| `bottom_height` | Alto del dock inferior. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `title_bar`

```python
title_bar(start=(), end=(), *, center=None, height=34, theme=None)
```

La barra superior: selectores de proyecto y rama a la izquierda, cuenta y acciones a la derecha.

| Parámetro | Descripción |
| --- | --- |
| `start` | Widgets al inicio (izquierda). |
| `end` | Widgets al final (derecha). |
| `center` | Widget centrado. |
| `height` | Alto. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `title_button`

```python
title_button(
    content,
    on_press=None,
    *,
    icon=None,
    muted=False,
    chevron=False,
    theme=None,
)
```

Un botón compacto para la barra de título (`pyzed ▾`, `main`…).

| Parámetro | Descripción |
| --- | --- |
| `content` | Texto. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `muted` | Texto atenuado. |
| `chevron` | Añade un ▾. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `status_bar`

```python
status_bar(start=(), end=(), *, height=28, theme=None)
```

La barra de estado inferior.

| Parámetro | Descripción |
| --- | --- |
| `start` | Widgets al inicio (izquierda). |
| `end` | Widgets al final (derecha). |
| `height` | Alto. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `status_item`

```python
status_item(
    content=None,
    on_press=None,
    *,
    icon=None,
    color=None,
    icon_color=None,
    selected=False,
    tooltip=None,
    keys=None,
    theme=None,
)
```

Un icono y/o texto en la barra de estado (diagnósticos, posición del cursor, lenguaje…).

| Parámetro | Descripción |
| --- | --- |
| `content` | Texto. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `color` | Color del texto o del icono. |
| `icon_color` | Color del icono: un token del tema o un color hex. |
| `selected` | Lo marca como seleccionado. |
| `tooltip` | Texto del tooltip. |
| `keys` | Atajo que se muestra al final, al estilo de Zed: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `panel`

```python
panel(content, *, header=None, width=None, height=None, side='left', theme=None)
```

Un panel acoplable. `side` decide en qué borde va la línea.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `header` | Cabecera (`ui.panel_header`). |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `side` | `"left"`, `"right"` o `"bottom"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `panel_header`

```python
panel_header(title, actions=(), *, icon=None, height=32, theme=None)
```

La cabecera de un panel: icono, título y acciones.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `actions` | Widgets extra (normalmente botones) que se muestran como acciones. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `height` | Alto. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

## Overlays

### `layer`

```python
layer(
    base,
    overlay=None,
    *,
    on_dismiss=None,
    backdrop=None,
    align_x='center',
    align_y='start',
    offset=72,
)
```

Apila `overlay` sobre `base`. Hacer clic fuera envía `on_dismiss`. Con `overlay=None` devuelve `base` tal cual.

| Parámetro | Descripción |
| --- | --- |
| `base` | La interfaz de debajo. |
| `overlay` | Lo que flota encima (modal, paleta, menú). |
| `on_dismiss` | Mensaje o callable que se envía al cerrar. |
| `backdrop` | Color del fondo que oscurece la interfaz. |
| `align_x` | Alineación horizontal: `"start"`/`"left"`, `"center"`, `"end"`/`"right"`. |
| `align_y` | Alineación vertical: `"start"`/`"top"`, `"center"`, `"end"`/`"bottom"`. |
| `offset` | Distancia desde arriba cuando `align_y` es `"start"`. |

### `modal`

```python
modal(content, *, title=None, on_close=None, width=480, footer=(), theme=None)
```

Un diálogo. Úsalo como `overlay` de `ui.layer`.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `title` | Título. |
| `on_close` | Mensaje o callable que se envía al pulsar la X. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `footer` | Botones del pie, alineados a la derecha. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `PaletteItem`

```python
@dataclass
class PaletteItem(label, on_press=None, keys=None, icon=None, detail=None)
```

Una entrada de `command_palette` o `picker`.

| Parámetro | Descripción |
| --- | --- |
| `label` | Texto de la etiqueta. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `keys` | Atajo que se muestra al final, al estilo de Zed: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `detail` | Texto secundario (por ejemplo, la ruta de un archivo). |

### `command_palette`

```python
command_palette(
    query,
    on_query,
    commands,
    *,
    selected=0,
    on_submit=None,
    placeholder='Execute a command…',
    input_id='command-palette',
    theme=None,
    **kwargs,
)
```

La paleta de comandos de Zed: filtra `commands` por `query` con búsqueda difusa y muestra sus atajos.

| Parámetro | Descripción |
| --- | --- |
| `query` | Texto buscado. |
| `on_query` | Callable que recibe el texto nuevo. |
| `commands` | Lista de `PaletteItem`. |
| `selected` | Índice resaltado (para navegar con flechas). |
| `on_submit` | Mensaje o callable que se envía al pulsar Enter. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `input_id` | Id del campo (para `Command.focus`). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |
| `kwargs` | Los de `picker`. |

### `picker`

```python
picker(
    query,
    on_query,
    items,
    *,
    selected=0,
    placeholder='Search…',
    input_id='picker',
    on_submit=None,
    width=560,
    max_height=340,
    empty_text='No matches',
    theme=None,
)
```

Una lista con buscador en una superficie flotante. Es la base de la paleta y del buscador de archivos.

| Parámetro | Descripción |
| --- | --- |
| `query` | Texto buscado. |
| `on_query` | Callable que recibe el texto nuevo. |
| `items` | Pares `(PaletteItem, posiciones)`, por ejemplo de `fuzzy_filter`. |
| `selected` | Índice resaltado. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `input_id` | Id del campo. |
| `on_submit` | Mensaje o callable que se envía al pulsar Enter. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `max_height` | Alto máximo en píxeles. |
| `empty_text` | Texto cuando no hay resultados. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `fuzzy_match`

```python
fuzzy_match(query, candidate)
```

Devuelve `(puntuación, posiciones)` si todas las letras de `query` aparecen en orden en `candidate`; si no, `None`. Premia los inicios de palabra y las letras consecutivas.

| Parámetro | Descripción |
| --- | --- |
| `query` | Texto buscado. |
| `candidate` | Texto candidato. |

### `fuzzy_filter`

```python
fuzzy_filter(query, items, key=<class 'str'>)
```

Filtra y ordena `items` por puntuación difusa. Devuelve `[(item, posiciones), ...]`.

| Parámetro | Descripción |
| --- | --- |
| `query` | Texto buscado. |
| `items` | Elementos. |
| `key` | Función que da el texto de cada elemento. |

### `highlighted`

```python
highlighted(text, positions, *, color, match_color, size=13.5, weight=None)
```

Texto con los caracteres de `positions` resaltados (coincidencias de la búsqueda difusa).

| Parámetro | Descripción |
| --- | --- |
| `text` | Texto. |
| `positions` | Índices a resaltar. |
| `color` | Color del texto o del icono. |
| `match_color` | Color de las coincidencias. |
| `size` | Tamaño. |
| `weight` | Peso del texto. |

### `toast`

```python
toast(
    title,
    message=None,
    *,
    kind='info',
    icon=None,
    on_dismiss=None,
    actions=(),
    width=340,
    theme=None,
)
```

Una notificación.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `message` | Texto secundario. |
| `kind` | `"info"`, `"success"`, `"warning"` o `"error"`. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `on_dismiss` | Mensaje o callable que se envía al cerrar. |
| `actions` | Widgets extra (normalmente botones) que se muestran como acciones. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `toasts`

```python
toasts(base, items, *, spacing=8)
```

Muestra `items` (normalmente `toast(...)`) apilados en la esquina inferior derecha sobre `base`.

| Parámetro | Descripción |
| --- | --- |
| `base` | La interfaz de debajo. |
| `items` | Lista de toasts. |
| `spacing` | Separación entre hijos, en píxeles. |

### `popover`

```python
popover(base, content=None, *, x=0, y=0, on_dismiss=None)
```

Muestra `content` (un `ui.menu`, una tarjeta…) sobre `base` en `(x, y)`. Hacer clic en cualquier otro sitio llama a `on_dismiss`. Para un menú de clic derecho, guarda la posición del ratón con `mouse_area(on_move=...)` y abre el popover desde `on_right_press` (ver `examples/context_menu.py`).

| Parámetro | Descripción |
| --- | --- |
| `base` | La interfaz de debajo. |
| `content` | Lo que flota (o `None`). |
| `x` | Posición horizontal. |
| `y` | Posición vertical. |
| `on_dismiss` | Mensaje o callable que se envía al cerrar. |

## Código

### `editor`

```python
editor(
    id,
    text='',
    *,
    language=None,
    path=None,
    on_change=None,
    on_cursor=None,
    markers=None,
    font_size=None,
    line_height=None,
    gutter=True,
    wrap=False,
    active_line=True,
    height='fill',
    placeholder=None,
    theme=None,
)
```

El editor de código de Zed: resaltado con los colores del tema, números de línea y marcadores de git.

| Parámetro | Descripción |
| --- | --- |
| `id` | Identifica el buffer (usa la ruta del archivo). |
| `text` | Texto inicial. |
| `language` | Lenguaje. Si falta, se deduce de `path`. |
| `path` | Ruta del archivo. |
| `on_change` | Callable que recibe el nuevo valor. |
| `on_cursor` | Callable que recibe `(línea, columna)`. |
| `markers` | `{línea: "created" | "modified" | "deleted"}`. |
| `font_size` | Tamaño de la fuente (por defecto, el del tema). |
| `line_height` | Alto de línea. |
| `gutter` | Muestra los números de línea. |
| `wrap` | Ajuste de línea. |
| `active_line` | Color de fondo de la línea del cursor. |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `language_token`

```python
language_token(path)
```

Devuelve el token de lenguaje del resaltador para una ruta (`"main.rs"` → `"rs"`).

| Parámetro | Descripción |
| --- | --- |
| `path` | Ruta del archivo. |

### `terminal`

```python
terminal(lines, *, font_size=13, id=None, theme=None)
```

Una vista de terminal de solo lectura con colores ANSI. Se mantiene desplazada al final.

| Parámetro | Descripción |
| --- | --- |
| `lines` | Texto con escapes ANSI o lista de líneas de segmentos `(texto, color)`. |
| `font_size` | Tamaño de la fuente. |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `ansi`

```python
ansi(text)
```

Convierte texto con colores ANSI en líneas de segmentos `(texto, nombre_de_color)`.

| Parámetro | Descripción |
| --- | --- |
| `text` | Texto con escapes ANSI. |
