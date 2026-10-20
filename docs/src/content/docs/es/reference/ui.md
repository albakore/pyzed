---
title: "Componentes (pyzed.ui)"
description: "Referencia de la API de pyzed.ui: cada componente listo para usar con sus parámetros, valores por defecto y eventos, para apps de escritorio en Python."
sidebar:
  order: 4
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Firmas y parámetros de todos los componentes. Para verlos con imágenes y ejemplos,
ve a la sección [Componentes](/pyzed/es/components/overview/).

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
    loading=False,
    tooltip=None,
    theme=None,
    **style,
)
```

Un botón con tema, con variantes, tamaños, un icono y un atajo.

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
| `keys` | Atajo que se muestra al final, escrito como texto: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `loading` | Muestra un spinner en lugar del icono e ignora las pulsaciones (mantén una suscripción `pz.every(1/30, ...)` mientras gira). |
| `tooltip` | Texto que aparece al pasar el ratón. |
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
    keys=None,
    tint=None,
    loading=False,
    indicator=None,
    theme=None,
)
```

Un botón cuadrado con solo un icono.

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
| `keys` | Atajo que se muestra en el tooltip. |
| `tint` | Lo colorea (`"error"`, `"accent"`…). |
| `loading` | Cambia el icono por un spinner e ignora las pulsaciones. |
| `indicator` | Añade un punto de este color arriba a la derecha (sin leer, cambios…). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `badge`

```python
badge(
    content,
    *,
    tint='accent',
    variant='soft',
    icon=None,
    size='md',
    on_press=None,
    theme=None,
)
```

Una píldora pequeña para estados y contadores.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `variant` | `"soft"`, `"solid"` o `"outline"`. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `on_press` | La hace pulsable. |
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
avatar(
    initials,
    *,
    color=None,
    size=22,
    index=0,
    image=None,
    status=None,
    tooltip=None,
    theme=None,
)
```

Un avatar redondo con iniciales.

| Parámetro | Descripción |
| --- | --- |
| `initials` | Iniciales (se usan las dos primeras). |
| `color` | Color de fondo. |
| `size` | Diámetro. |
| `index` | Elige un color de colaborador del tema (`theme.players`). |
| `image` | Una imagen (ruta o bytes) en lugar de las iniciales. |
| `status` | Punto de presencia: `"online"`, `"away"`, `"busy"`, `"offline"` o un color. |
| `tooltip` | Texto al pasar el ratón (el nombre de la persona). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `tooltip`

```python
tooltip(content, text, *, keys=None, position='bottom', theme=None)
```

Envuelve `content` con un tooltip con el estilo del tema, opcionalmente con su atajo.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `text` | Texto del tooltip. |
| `keys` | Atajo que se muestra al final, escrito como texto: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `position` | `"top"`, `"bottom"`, `"left"`, `"right"` o `"cursor"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `divider`

```python
divider(*, vertical=False, color=None, label=None, spacing=0, theme=None)
```

Una línea divisoria con el color del tema.

| Parámetro | Descripción |
| --- | --- |
| `vertical` | Vertical en lugar de horizontal. |
| `color` | Color del texto o del icono. |
| `label` | Texto atenuado en el centro de una línea horizontal (`"o"`, una fecha…). |
| `spacing` | Espacio a ambos lados de la línea. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `card`

```python
card(
    content,
    *,
    title=None,
    actions=(),
    padding=16,
    width=None,
    footer=(),
    on_press=None,
    selected=False,
    elevated=False,
    theme=None,
)
```

Una superficie con borde para agrupar contenido, con título y acciones opcionales.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `title` | Título. |
| `actions` | Widgets extra (normalmente botones) que se muestran como acciones. |
| `padding` | Relleno interior. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `footer` | Widgets abajo a la derecha (botones). |
| `on_press` | Hace pulsable toda la tarjeta. |
| `selected` | La resalta con el color de acento. |
| `elevated` | Añade una sombra. |
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
    on_clear=None,
    id=None,
    size='md',
    secure=False,
    width='fill',
    borderless=False,
    mono=False,
    disabled=False,
    readonly=False,
    invalid=False,
    max_length=None,
    align='start',
    theme=None,
)
```

Un campo de texto. El foco, la pérdida de foco y las teclas vienen de los eventos comunes: `.on(focus=..., blur=..., key_down=...)`.

| Parámetro | Descripción |
| --- | --- |
| `value` | Texto actual. |
| `on_input` | Callable que recibe el texto nuevo en cada pulsación. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `on_submit` | Mensaje o callable que se envía al pulsar Enter. |
| `on_clear` | Muestra una ✕ mientras hay texto; se envía al pulsarla. |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `secure` | Oculta el texto. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `borderless` | Sin borde ni fondo (como en la paleta de comandos). |
| `mono` | Usa la fuente monoespaciada (IBM Plex Mono). |
| `disabled` | Lo atenúa e ignora lo que se escribe. |
| `readonly` | Se puede seleccionar y copiar, pero no cambiar. |
| `invalid` | Pinta el borde con el color de error. |
| `max_length` | Ignora los cambios más largos que esto. |
| `align` | Alineación del texto: `"start"`, `"center"` o `"end"`. |
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
switch(checked, on_toggle=None, *, label=None, size='md', disabled=False, theme=None)
```

Un interruptor encendido/apagado.

| Parámetro | Descripción |
| --- | --- |
| `checked` | Estado actual. |
| `on_toggle` | Callable que recibe el nuevo `bool` (o mensaje que se envía). |
| `label` | Texto de la etiqueta. |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `disabled` | Lo atenúa e ignora los clics. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `checkbox`

```python
checkbox(checked, on_toggle=None, *, label=None, size='md', disabled=False, theme=None)
```

Una casilla de verificación. `checked=None` muestra el estado mixto (parte de un grupo marcada); al pulsarla se marca.

| Parámetro | Descripción |
| --- | --- |
| `checked` | Estado actual. |
| `on_toggle` | Callable que recibe el nuevo `bool` (o mensaje que se envía). |
| `label` | Texto de la etiqueta. |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `disabled` | La atenúa e ignora los clics. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `slider`

```python
slider(
    value,
    on_change=None,
    *,
    min=0.0,
    max=1.0,
    step=0.01,
    on_release=None,
    vertical=False,
    width=None,
    height=None,
    disabled=False,
    show_value=False,
    theme=None,
)
```

Un deslizador.

| Parámetro | Descripción |
| --- | --- |
| `value` | Valor actual. |
| `on_change` | Callable que recibe el nuevo valor. |
| `min` | Mínimo. |
| `max` | Máximo. |
| `step` | Paso. |
| `on_release` | Se envía al terminar de arrastrar (guarda o aplica ahí). |
| `vertical` | Lo pone de pie. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `disabled` | Lo atenúa. |
| `show_value` | Muestra el número al lado: `True`, o un formato como `"{:.0%}"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `progress`

```python
progress(
    value,
    *,
    max=1.0,
    tint='accent',
    height=4,
    width='fill',
    label=None,
    show_value=False,
    theme=None,
)
```

Una barra de progreso fina.

| Parámetro | Descripción |
| --- | --- |
| `value` | Progreso, o `None` para una barra indeterminada (mantén una suscripción `pz.every(1/30, ...)` mientras se ve). |
| `max` | Valor máximo. |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `height` | Grosor. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `label` | Texto sobre la barra. |
| `show_value` | Añade el porcentaje a su derecha. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `segmented`

```python
segmented(
    options,
    selected,
    on_select=None,
    *,
    size='md',
    width=None,
    disabled=False,
    theme=None,
)
```

Un grupo de botones mutuamente excluyentes.

| Parámetro | Descripción |
| --- | --- |
| `options` | Textos, `(valor, etiqueta)` o `(valor, etiqueta, icono)`. |
| `selected` | El valor activo. |
| `on_select` | Callable que recibe el elemento elegido. |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `width` | `"fill"` reparte el ancho entre los botones. |
| `disabled` | `True`, o los valores a desactivar. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `field`

```python
field(
    title,
    control,
    *,
    description=None,
    error=None,
    required=False,
    vertical=False,
    theme=None,
)
```

Una fila de formulario: título y descripción a la izquierda, control a la derecha (como una pantalla de ajustes).

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `control` | El control (switch, input…). |
| `description` | Texto de ayuda. |
| `error` | Un mensaje de validación que se muestra bajo el título con el color de error (ver `pz.validation_errors`). |
| `required` | Añade un `*` rojo tras el título. |
| `vertical` | Pone el control bajo el título. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

## Diálogos

### `dialog_layer`

```python
dialog_layer(base, dialog=None, *, on_dismiss=None, theme=None)
```

Muestra un diálogo centrado sobre `base` con un fondo oscurecido. Con `dialog=None` devuelve `base` sin cambios, así que puede envolver siempre la vista. Ver [Diálogos](/pyzed/es/guides/i18n/#diálogos).

| Parámetro | Descripción |
| --- | --- |
| `base` | La interfaz de debajo. |
| `dialog` | Un diálogo de las funciones de abajo, o `ui.modal`. |
| `on_dismiss` | Se envía al hacer clic en el fondo. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

```python
ui.dialog_layer(self.vista_principal(), ui.confirm("¿Eliminar 3 archivos?", self.eliminar, self.cancelar,
                danger=True) if self.preguntando else None, on_dismiss=self.cancelar)
```

### `alert`

```python
alert(message, on_close, *, title=None, kind=None, ok_label=None, width=400, theme=None)
```

Un mensaje con un botón.

| Parámetro | Descripción |
| --- | --- |
| `message` | Texto o widget. |
| `on_close` | El botón y el icono de cerrar. |
| `title` | Título. |
| `kind` | `"info"`, `"success"`, `"warning"` o `"error"` añade un icono. |
| `ok_label` | Texto del botón (por defecto: Aceptar, traducido). |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `confirm`

```python
confirm(
    message,
    on_confirm,
    on_cancel,
    *,
    title=None,
    confirm_label=None,
    cancel_label=None,
    danger=False,
    kind=None,
    width=420,
    theme=None,
)
```

Hace una pregunta de sí o no.

| Parámetro | Descripción |
| --- | --- |
| `message` | Texto o widget. |
| `on_confirm` | El botón de confirmar. |
| `on_cancel` | Cancelar, el icono de cerrar. |
| `title` | Título. |
| `confirm_label` | Texto del botón de confirmar. |
| `cancel_label` | Texto del botón de cancelar. |
| `danger` | Pinta el botón de rojo y lo llama Eliminar. |
| `kind` | Añade un icono, como en `alert`. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `prompt`

```python
prompt(
    title,
    value,
    on_input,
    on_submit,
    on_cancel,
    *,
    message=None,
    placeholder='',
    submit_label=None,
    cancel_label=None,
    id=None,
    width=440,
    theme=None,
)
```

Pide una línea de texto.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `value` | Texto actual. |
| `on_input` | Recibe cada edición. |
| `on_submit` | Enter o el botón de aceptar. |
| `on_cancel` | Cancelar, el icono de cerrar. |
| `message` | Texto sobre el campo. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `submit_label` | Texto del botón de aceptar. |
| `cancel_label` | Texto del botón de cancelar. |
| `id` | Id del campo (para `Command.focus`). |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `choice`

```python
choice(message, options, on_cancel, *, title=None, width=440, theme=None)
```

Un mensaje con tus propios botones.

| Parámetro | Descripción |
| --- | --- |
| `message` | Cualquier valor de Python, o un callable. |
| `options` | Pares `(texto, on_press)`; el último es el botón principal. |
| `on_cancel` | El icono de cerrar. |
| `title` | Título. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `unsaved_changes`

```python
unsaved_changes(name, on_save, on_discard, on_cancel, *, width=440, theme=None)
```

«¿Guardar los cambios de *nombre* antes de cerrar?» con No guardar, Cancelar y Guardar.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre del archivo o documento. |
| `on_save` | Guardar. |
| `on_discard` | No guardar. |
| `on_cancel` | Cancelar. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
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
    disabled=False,
    invalid=False,
    on_open=None,
    on_close=None,
    theme=None,
)
```

Un desplegable con el estilo del tema. Las opciones se muestran con `str()`, así que sirven textos, enums, dataclasses o modelos de base de datos; `on_select` recibe el objeto elegido, no su texto.

| Parámetro | Descripción |
| --- | --- |
| `options` | Lista de opciones. |
| `selected` | Opción actual. |
| `on_select` | Callable que recibe el elemento elegido. |
| `placeholder` | Texto de ayuda cuando está vacío. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `disabled` | Lo atenúa. |
| `invalid` | Pinta el borde con el color de error. |
| `on_open` | Se envía al abrir el menú. |
| `on_close` | Se envía al cerrar el menú. |
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
    disabled=False,
    descriptions=None,
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
| `disabled` | `True`, o los valores a desactivar. |
| `descriptions` | Asocia valores a una línea atenuada bajo su etiqueta. |
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
    prefix=None,
    align='center',
    decimals=None,
    disabled=False,
    invalid=False,
    id=None,
    on_submit=None,
    theme=None,
)
```

Un campo numérico con botones −/+. `on_change(valor)` recibe el número ya limitado a `min`/`max`; lo que no se puede leer como número se ignora. Tras pulsarlo, ↑/↓ lo mueven un paso (con Shift, diez) e Inicio/Fin saltan a `min`/`max`.

| Parámetro | Descripción |
| --- | --- |
| `value` | Valor actual. |
| `on_change` | Callable que recibe el nuevo valor. |
| `min` | Mínimo. |
| `max` | Máximo. |
| `step` | Paso de los botones. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `suffix` | Unidad que se muestra al final (`"px"`, `"%"`…). |
| `prefix` | Texto antes del número (`"$"`…). |
| `align` | Dónde va el número entre los botones: `"center"` (por defecto), `"start"` o `"end"`. |
| `decimals` | Decimales que muestra (por defecto, los de `step`). |
| `disabled` | Lo atenúa. |
| `invalid` | Pinta el borde con el color de error. |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `on_submit` | Se envía con Enter. |
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
    tint=None,
    size='md',
    disabled=False,
    tooltip=None,
    theme=None,
)
```

Un botón con una flecha aparte para más opciones. `on_press` ejecuta la acción principal y `on_menu` normalmente abre un `ui.menu` en un `ui.popover`.

| Parámetro | Descripción |
| --- | --- |
| `content` | Texto del botón. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `on_menu` | Mensaje o callable del botón del menú. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `variant` | Como en `ui.button`. |
| `tint` | Como en `ui.button`. |
| `size` | `"xs"`, `"sm"`, `"md"` o `"lg"`. |
| `disabled` | Desactiva las dos mitades. |
| `tooltip` | Tooltip de la mitad principal. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `toggle_group`

```python
toggle_group(
    options,
    selected,
    on_select=None,
    *,
    disabled=False,
    multiple=False,
    theme=None,
)
```

Un control segmentado solo con iconos.

| Parámetro | Descripción |
| --- | --- |
| `options` | `(valor, nombre_de_icono)` o `(valor, nombre_de_icono, tooltip)`. |
| `selected` | Valor actual (una colección con `multiple`). |
| `on_select` | Callable que recibe el elemento elegido. |
| `disabled` | `True`, o los valores a desactivar. |
| `multiple` | Cada botón activa o desactiva su valor. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `chip`

```python
chip(
    content,
    *,
    on_press=None,
    on_remove=None,
    selected=False,
    icon=None,
    tint='accent',
    disabled=False,
    theme=None,
)
```

Una etiqueta compacta, opcionalmente pulsable (filtros) y con botón para quitarla.

| Parámetro | Descripción |
| --- | --- |
| `content` | Texto. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `on_remove` | Muestra una ✕ que envía esto al pulsarla. |
| `selected` | Lo marca como seleccionado. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `tint` | Color cuando está seleccionada (un token del tema). |
| `disabled` | La atenúa e ignora las pulsaciones. |
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

### `AccordionSection`

```python
class AccordionSection
```

Una sección de `ui.accordion`: `key`, `title`, `content` y, opcionales, `icon` y un widget `end` en la cabecera.

| Parámetro | Descripción |
| --- | --- |
| `key` | Clave que identifica la suscripción (por defecto, el mensaje o la función). |
| `title` | Título. |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `end` | Widgets al final (derecha). |

### `accordion`

```python
accordion(
    sections,
    *,
    open=(),
    on_toggle=None,
    icons=None,
    spacing=8,
    padding=(6, 12, 10, 12),
    theme=None,
)
```

Secciones plegables apiladas y separadas por divisores, como los paneles de una pantalla de ajustes. Cada cabecera ocupa todo el ancho, así que el contenido queda alineado con el resto del panel. El estado abierto es tuyo: cámbialo en `on_toggle`.

| Parámetro | Descripción |
| --- | --- |
| `sections` | Elementos `ui.AccordionSection(key, title, content, icon=None, end=None)` (o tuplas `(key, title, content)`). |
| `open` | El conjunto de ids abiertos, un dict `{id: bool}` o `True` para todos. |
| `on_toggle` | Se llama con la clave de la cabecera pulsada. |
| `icons` | `{id: icono}`: un icono de Lucide para cada cabecera. |
| `spacing` | Espacio alrededor de los divisores entre secciones. |
| `padding` | Relleno alrededor del contenido de una sección abierta. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

```python
ui.accordion([
    ui.AccordionSection("layout", "Layout", layout_rows, icon="ruler"),
    ui.AccordionSection("events", "Events", event_rows, icon="zap"),
], open=self.open_sections, on_toggle=lambda key: self.open_sections.symmetric_difference_update({key}))
```

## Consola y ayuda

### `Log`

```python
class Log
```

Las entradas de un `ui.console`: seguro entre hilos, limitado a `limit` y con las líneas repetidas agrupadas. `write(level, text)` añade una línea; `capture()` (o `with log:`) copia la salida de `print` y los tracebacks; `pipe(stream)` lee la salida de un subproceso en segundo plano; `text()` devuelve todo para copiarlo.

| Parámetro | Descripción |
| --- | --- |
| `limit` | Máximo de entradas guardadas. |
| `on_write` | Se llama tras cada escritura (desde cualquier hilo). |

```python
log = ui.Log()
with log:
    print("hola")           # sigue llegando a la terminal
ui.console(log.entries, on_clear=log.clear)
```

**Métodos y propiedades**

#### `Log.write`

```python
Log.write(level, text)
```

Añade una línea con nivel `level` y llama a `on_write`.

#### `Log.clear`

```python
Log.clear()
```

Quita todas las entradas.

#### `Log.counts`

```python
Log.counts()
```

Devuelve cuántas líneas hay por nivel, contando las repeticiones plegadas.

#### `Log.text`

```python
Log.text()
```

Todo como texto plano (para copiar).

#### `Log.capturing`

```python
Log.capturing  # property
```

Si `sys.stdout`/`sys.stderr` se están copiando al log.

#### `Log.capture`

```python
Log.capture()
```

Copia `sys.stdout`/`sys.stderr` al log (siguen llegando a la terminal).

#### `Log.release`

```python
Log.release()
```

Deja de capturar y restaura los streams originales.

#### `Log.pipe`

```python
Log.pipe(stream, level='stdout', on_end=None)
```

Lee una tubería de un subproceso (bytes o texto) línea a línea hacia el log, en un hilo en segundo plano.

### `LogEntry`

```python
@dataclass
class LogEntry(level, text, time=time.time(), count=1)
```

Una línea de un `ui.Log`: `level`, `text`, `time`, `count` (líneas idénticas seguidas) y `clock` (`HH:MM:SS`).

| Parámetro | Descripción |
| --- | --- |
| `level` | Nivel. |
| `text` | La línea. |
| `time` | Cuándo se escribió (`time.time()`). |
| `count` | Líneas idénticas seguidas. |

**Métodos y propiedades**

#### `LogEntry.clock`

```python
LogEntry.clock  # property
```

La hora local de la entrada como `HH:MM:SS`.

### `LOG_LEVELS`

```python
LOG_LEVELS(...)
```

Los niveles que colorea `ui.console`, en el orden de sus filtros: info, event, stdout, stderr, warning, error.

### `console`

```python
console(
    entries,
    *,
    query='',
    on_query=None,
    hidden=(),
    on_toggle_level=None,
    on_clear=None,
    on_copy=None,
    actions=(),
    font_size=12.5,
    id=None,
    theme=None,
)
```

Una vista de registro como la consola de las herramientas de desarrollo del navegador: filtro, un botón por nivel con su cuenta, copiar y limpiar, y las entradas en monoespaciada, siempre desplazada a la más nueva.

| Parámetro | Descripción |
| --- | --- |
| `entries` | Elementos `ui.LogEntry` (`log.entries`). |
| `query` | Texto del filtro. |
| `on_query` | Recibe cada edición del filtro. |
| `hidden` | Niveles ocultos. |
| `on_toggle_level` | Se llama con el nivel del botón pulsado. |
| `on_clear` | Añade el botón Limpiar. |
| `on_copy` | Añade el botón Copiar. |
| `actions` | Widgets extra al final de la barra. |
| `font_size` | Tamaño de las entradas. |
| `id` | Id del scrollable. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `shortcuts`

```python
shortcuts(groups, *, query='', on_query=None, height=380, theme=None)
```

Una lista de atajos de teclado agrupada y con búsqueda (para un diálogo de atajos).

| Parámetro | Descripción |
| --- | --- |
| `groups` | `[(título, [(etiqueta, teclas), ...]), ...]`, teclas como `"ctrl-s"`. |
| `query` | Texto del filtro. |
| `on_query` | Añade un buscador. |
| `height` | Alto de la lista. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `about`

```python
about(
    name,
    version='',
    description='',
    *,
    icon='app-window',
    details=(),
    links=(),
    theme=None,
)
```

Un cuadro Acerca de: icono, nombre, versión, una descripción, algunos detalles y botones de enlace.

| Parámetro | Descripción |
| --- | --- |
| `name` | Nombre de la app. |
| `version` | Versión. |
| `description` | Una o dos frases. |
| `icon` | Icono de Lucide. |
| `details` | Filas `(etiqueta, valor)`. |
| `links` | Botones `(etiqueta, on_press)`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `reference_browser`

```python
reference_browser(
    browser,
    *,
    on_open_url=None,
    sidebar_width=270,
    width='fill',
    height='fill',
    theme=None,
)
```

La referencia integrada, como la de Godot: una lista de clases con búsqueda junto a la página abierta.

`browser` es un `pyzed.reference.Browser` (guárdalo en el estado de tu app); al hacer clic en entradas,
enlaces y en los botones atrás/adelante cambia. `on_open_url(url)` recibe los enlaces que salen de la
referencia (la web, GitHub...):

```python
self.help = reference.Browser("pyzed.ui.button")
...
ui.reference_browser(self.help, on_open_url=abrir_en_navegador)
```

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

Un aviso en línea (un callout o banner).

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
empty_state(
    title,
    description=None,
    *,
    icon='inbox',
    actions=(),
    size='md',
    height='fill',
    theme=None,
)
```

Un marcador centrado para listas vacías, búsquedas sin resultados, etc.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `description` | Texto secundario. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `actions` | Widgets extra (normalmente botones) que se muestran como acciones. |
| `size` | `"sm"`, `"md"` o `"lg"`. |
| `height` | `"fill"` (por defecto), píxeles o `"shrink"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `settings_group`

```python
settings_group(title, rows, *, description=None, end=None, theme=None)
```

Un bloque con título de filas `ui.field` separadas por líneas, como una pantalla de ajustes.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título del grupo. |
| `rows` | Las filas (normalmente `ui.field`). |
| `description` | Texto secundario. |
| `end` | Widget a la derecha del título (un botón Restablecer…). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `Column`

```python
@dataclass
class Column(title, key, width='fill', align='start', render=None, sortable=True)
```

Una columna de `ui.table`. `key` es una clave de dict, un nombre de atributo o una función de la fila; `render` (opcional) convierte el valor en un widget. `width` es `"fill"`, un número o una porción como `"fill:2"`.

| Parámetro | Descripción |
| --- | --- |
| `title` | Encabezado (y nombre para ordenar). |
| `key` | Cómo obtener el valor de cada fila. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `align` | `"start"`, `"center"` o `"end"`. |
| `render` | Función valor → widget. |
| `sortable` | Si el encabezado se puede pulsar para ordenar. |

**Métodos y propiedades**

#### `Column.value`

```python
Column.value(row)
```

Devuelve el valor de esta columna para `row`: `key(row)`, un elemento de dict o un atributo.

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
    on_row_double_press=None,
    on_row_context=None,
    empty=None,
    theme=None,
)
```

Una tabla de datos con encabezado fijo, orden opcional y selección de filas. El orden se hace aquí cuando `sort_by` nombra una columna: pulsar un encabezado llama a `on_sort(título)` y tú cambias `sort_by`/`descending` en tu estado. Las filas están virtualizadas: solo se construyen las visibles, así que cientos de miles de filas se desplazan con fluidez.

| Parámetro | Descripción |
| --- | --- |
| `columns` | `ui.Column` o claves simples. |
| `rows` | Dicts u objetos. |
| `sort_by` | Título de la columna por la que se ordena. |
| `descending` | Orden descendente. |
| `on_sort` | Callable que recibe el título pulsado. |
| `on_row_press` | Callable que recibe la fila pulsada. |
| `selected` | La fila a resaltar, o una lista o conjunto de filas (selección múltiple). |
| `striped` | Filas alternas sombreadas. |
| `row_height` | Alto de cada fila. |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `on_row_double_press` | Recibe la fila con un doble clic (abrir, editar…). |
| `on_row_context` | Recibe la fila con un clic derecho (un menú contextual). |
| `empty` | Texto o widget que se muestra en lugar de las filas cuando no hay ninguna. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `stat`

```python
stat(
    title,
    value,
    *,
    delta=None,
    trend=None,
    width=None,
    icon=None,
    inverse=False,
    on_press=None,
    theme=None,
)
```

Un número de panel: título, valor grande, variación opcional (`+4.2%`) y sparkline.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título. |
| `value` | Valor actual. |
| `delta` | Variación en %; verde si es positiva, roja si no. |
| `trend` | Valores para la sparkline. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `icon` | Icono antes del título. |
| `inverse` | Pinta de verde una bajada y de rojo una subida (errores, latencia…). |
| `on_press` | Hace pulsable la tarjeta. |
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
count_badge(count, *, tint='accent', max=99, show_zero=True, theme=None)
```

Un contador redondo (notificaciones, problemas…). Muestra `99+` por encima de `max`.

| Parámetro | Descripción |
| --- | --- |
| `count` | El número. |
| `tint` | Color semántico: `"accent"`, `"error"`, `"warning"`, `"success"`, `"info"` o un token. |
| `max` | Máximo antes de mostrar `N+`. |
| `show_zero` | Con `False`, un 0 no dibuja nada. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `facepile`

```python
facepile(people, *, size=22, overlap=6, max_shown=5, theme=None)
```

Avatares superpuestos de colaboradores, como en la barra de título de un editor colaborativo. Los que pasan de `max_shown` se agrupan en `+N`.

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
| `keys` | Atajo que se muestra al final, escrito como texto: `"ctrl-s"`, `"cmd-k cmd-s"`. |
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
    on_double_press=None,
    description=None,
    tooltip=None,
    theme=None,
)
```

Una fila de lista: icono, texto y un hueco al final.

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
| `on_double_press` | Se envía con un doble clic (abrir, renombrar…). |
| `description` | Una segunda línea atenuada (la fila crece a 40 px salvo que fijes `height`). |
| `tooltip` | Texto al pasar el ratón. |
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

**Métodos y propiedades**

#### `TreeNode.is_folder`

```python
TreeNode.is_folder  # property
```

Si el nodo es una carpeta (tiene una lista `children`, aunque esté vacía).

#### `TreeNode.from_paths`

```python
@classmethod
TreeNode.from_paths(paths, status=None)
```

Crea un árbol a partir de rutas del estilo `"src/main.rs"`. Las carpetas van primero.

#### `TreeNode.sort`

```python
TreeNode.sort()
```

Ordena los hijos recursivamente: primero las carpetas, luego por nombre sin distinguir mayúsculas.

### `tree`

```python
tree(
    nodes,
    *,
    expanded,
    selected=None,
    on_toggle=None,
    on_select=None,
    on_open=None,
    on_context=None,
    focused=None,
    indent=14,
    item_height=24,
    theme=None,
)
```

Un árbol de archivos plegable, como el panel de proyecto de un editor de código.

| Parámetro | Descripción |
| --- | --- |
| `nodes` | Lista de `TreeNode`. |
| `expanded` | Conjunto de ids de carpetas abiertas. |
| `selected` | Un id o una colección de ids (selección múltiple). |
| `on_toggle` | Se llama con el id de la carpeta pulsada. |
| `on_select` | Se llama con el id del archivo pulsado. |
| `on_open` | Recibe el id del archivo al que se hace doble clic. |
| `on_context` | Recibe el id de la fila en la que se hace clic derecho (muestra un `ui.menu` ahí). |
| `focused` | Resalta el borde de la fila en la que está el teclado. |
| `indent` | Sangría a la izquierda, en píxeles. |
| `item_height` | Alto de cada fila. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `MenuItem`

```python
@dataclass
class MenuItem(label, on_press=None, icon=None, keys=None, disabled=False, danger=False, checked=None, description=None, submenu=False)
```

Una entrada de `ui.menu`.

| Parámetro | Descripción |
| --- | --- |
| `label` | Texto de la etiqueta. |
| `on_press` | Mensaje o callable que se envía al pulsar. `None` deshabilita el control. |
| `icon` | Nombre de un icono de Lucide (`pyzed icons` los lista). |
| `keys` | Atajo que se muestra al final, escrito como texto: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `disabled` | Lo deshabilita (ignora los clics). |
| `danger` | En rojo (acciones destructivas). |
| `checked` | Muestra una marca (`True`/`False`) o nada (`None`). |
| `description` | Una segunda línea atenuada. |
| `submenu` | Termina la fila con una flecha; abre el siguiente menú al lado en `on_press`. |

### `menu`

```python
menu(items, *, width=240, max_height=None, theme=None)
```

Un menú contextual flotante. Usa `ui.SEPARATOR` entre grupos; un texto suelto es un encabezado.

| Parámetro | Descripción |
| --- | --- |
| `items` | Lista de `MenuItem`, `ui.SEPARATOR` o textos. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `max_height` | Desplaza un menú más alto que esto. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `SEPARATOR`

Separador para `ui.menu`.

### `virtual_list`

```python
virtual_list(
    items,
    render,
    *,
    item_height=26,
    spacing=0,
    width='fill',
    height='fill',
    padding=None,
    overscan=4,
    id=None,
    on_scroll=None,
    theme=None,
)
```

Una lista con scroll que solo construye las filas visibles, para miles o millones de elementos. `render(elemento)` devuelve el widget de un elemento y se llama cuando entra en la vista. Todas las filas tienen la misma altura.

| Parámetro | Descripción |
| --- | --- |
| `items` | Los elementos: una lista o cualquier secuencia (otros iterables se convierten en lista). |
| `render` | Función que recibe un elemento y devuelve su widget. |
| `item_height` | Altura de cada fila, en píxeles. |
| `spacing` | Separación entre hijos, en píxeles. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `padding` | Relleno interior: `8`, `(vertical, horizontal)` o `(arriba, derecha, abajo, izquierda)`. |
| `overscan` | Filas extra construidas por encima y por debajo de las visibles. |
| `id` | Identificador estable para enfocarlo o desplazarlo con un `Command`. |
| `on_scroll` | Callable que recibe el viewport del scroll, como en `pz.scrollable`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

## Navegación

### `Tab`

```python
@dataclass
class Tab(id, label, icon=None, icon_color=None, dirty=False, preview=False, status=None, pinned=False, tooltip=None)
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
| `pinned` | Muestra solo el icono, no tiene botón de cerrar y va primera en `tab_bar`. |
| `tooltip` | Texto al pasar el ratón (la ruta completa…). |

**Métodos y propiedades**

#### `Tab.for_file`

```python
@classmethod
Tab.for_file(path, **kwargs)
```

Una pestaña para el archivo `path`: su nombre como etiqueta y el icono y color de archivo correspondientes.

### `tab`

```python
tab(item, *, active, on_select=None, on_close=None, height=32, dimmed=False, theme=None)
```

Una sola pestaña. Normalmente se usa `tab_bar`.

| Parámetro | Descripción |
| --- | --- |
| `item` | El `Tab`. |
| `active` | Si es la activa. |
| `on_select` | Callable que recibe el elemento elegido. |
| `on_close` | Mensaje o callable que se envía al pulsar la X. |
| `height` | Alto. |
| `dimmed` | Apaga la etiqueta (la pestaña que se arrastra). |
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
    on_drag=None,
    on_drop=None,
    on_drag_over=None,
    dragging=None,
    drop_index=None,
    on_context=None,
    on_new=None,
    theme=None,
)
```

Una fila de pestañas con controles opcionales al principio y al final (navegación, dividir, +). El botón de cerrar aparece en la activa y al pasar el ratón. Las pestañas se pueden arrastrar para reordenarlas o sacarlas de la ventana: ver [Pestañas arrastrables](/pyzed/es/guides/windows/#pestañas-arrastrables-y-ventanas-desprendibles).

| Parámetro | Descripción |
| --- | --- |
| `tabs` | Lista de `Tab`. |
| `active` | Id de la pestaña activa. |
| `on_select` | Callable que recibe el elemento elegido. |
| `on_close` | Mensaje o callable que se envía al pulsar la X. |
| `start` | Widgets al inicio (izquierda). |
| `end` | Widgets al final (derecha). |
| `height` | Alto. |
| `on_drag` | Se llama con el id de la pestaña cuando empieza a arrastrarse. |
| `on_drop` | Se llama con el id de la pestaña y el `Event` al soltar la pestaña arrastrada: `event.window_x`/`window_y` (fuera de la ventana si se soltó fuera) y `event.screen`. |
| `on_drag_over` | Mientras `dragging` tiene valor: se llama con el índice de inserción bajo el puntero, o `None` cuando sale de la barra. |
| `dragging` | Id de la pestaña que se arrastra (la apaga y activa `on_drag_over`). |
| `drop_index` | Dibuja la marca de inserción antes de la pestaña de este índice (`len(tabs)`: después de la última). |
| `on_context` | Recibe el id de la pestaña en la que se hace clic derecho. |
| `on_new` | Se envía con un doble clic en el espacio vacío tras las pestañas. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `breadcrumbs`

```python
breadcrumbs(
    parts,
    *,
    separator='›',
    on_press=None,
    max_items=None,
    on_more=None,
    theme=None,
)
```

`src › main.rs › fn main`. Las partes pueden ser textos o tuplas `(icono, texto)`.

| Parámetro | Descripción |
| --- | --- |
| `parts` | Las partes. |
| `separator` | Separador. |
| `on_press` | Se llama con el índice de la parte pulsada. |
| `max_items` | Conserva la primera parte y las últimas y muestra `…` en lugar del resto. |
| `on_more` | Hace pulsable el `…`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `toolbar`

```python
toolbar(start=(), end=(), *, center=None, height=32, theme=None)
```

La barra bajo las pestañas: breadcrumbs a la izquierda y acciones del buffer a la derecha.

| Parámetro | Descripción |
| --- | --- |
| `start` | Widgets al inicio (izquierda). |
| `end` | Widgets al final (derecha). |
| `center` | Se mantiene en el centro de la barra sean cuales sean los anchos de los lados. |
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
    on_resize=None,
    theme=None,
)
```

El layout de una ventana estilo editor: barra de título, docks izquierdo, derecho e inferior, centro y barra de estado. Pasa `None` para ocultar un dock.

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
| `on_resize` | Se llama con `(side, size)` cuando el usuario termina de cambiar el tamaño de un panel arrastrando su borde interior. |
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
| `keys` | Atajo que se muestra al final, escrito como texto: `"ctrl-s"`, `"cmd-k cmd-s"`. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `panel`

```python
panel(
    content,
    *,
    header=None,
    width=None,
    height=None,
    side='left',
    resizable=True,
    on_resize=None,
    min_size=120,
    theme=None,
)
```

Un panel acoplable. `side` decide en qué borde va la línea; con un `width` numérico (`height` para el inferior) ese borde se arrastra para cambiar su tamaño.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `header` | Cabecera (`ui.panel_header`). |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `side` | `"left"`, `"right"` o `"bottom"`. |
| `resizable` | `False` mantiene el tamaño fijo. |
| `on_resize` | Se llama con el nuevo tamaño al terminar de arrastrar. |
| `min_size` | Tamaño mínimo al redimensionar. |
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

## Marco de ventana

### `window_frame`

```python
window_frame(
    content,
    *,
    title=None,
    menus=None,
    menu_button=True,
    start=(),
    center=None,
    end=(),
    style=None,
    window=None,
    height=None,
    resize_border=6.0,
    resize_edges=True,
    bg=None,
    theme=None,
)
```

El marco entero de una ventana abierta con `frame="custom"`: una barra de título que mueve la ventana (doble clic maximiza, clic derecho abre el menú del sistema en Windows), los botones de minimizar, maximizar y cerrar con el estilo de una plataforma, menús a la izquierda y bordes que cambian el tamaño de la ventana.

| Parámetro | Descripción |
| --- | --- |
| `content` | El contenido de la ventana, bajo la barra de título. |
| `title` | Título de la barra. Por defecto el `title` de la ventana. |
| `menus` | Menús a la izquierda de la barra: una lista de `ui.Menu`. |
| `menu_button` | Muestra los menús tras un botón ☰ (`False` muestra siempre sus nombres). |
| `start` | Elementos después de los menús (proyecto, rama…). |
| `center` | Tu propio widget en el centro en lugar del título. |
| `end` | Elementos antes de los botones de ventana. |
| `style` | `"macos"`, `"windows"`, `"gnome"`, `"ubuntu"` o `"kde"`. Por defecto el `frame` de la ventana, o el del sistema. |
| `window` | La ventana sobre la que actúan los botones. Por defecto aquella cuyo `view()` se está ejecutando. |
| `height` | Alto de la barra. Por defecto el de la plataforma. |
| `resize_border` | Ancho en píxeles de los bordes que cambian el tamaño de la ventana. |
| `resize_edges` | `False` deja los bordes de redimensionar a tu cargo (`pz.window_edges`), para ponerlos encima de menús y diálogos. |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

```python
class Notes(pz.App):
frame = "custom"

def view(self):
    return ui.window_frame(self.editor(), menus=[ui.Menu("Archivo", [ui.MenuItem("Abrir", self.open)])],
                           end=[ui.icon_button("settings", self.settings)])
```

### `window_title_bar`

```python
window_title_bar(
    title=None,
    *,
    style=None,
    start=(),
    center=None,
    end=(),
    on_drag=None,
    on_minimize=None,
    on_maximize=None,
    on_close=None,
    on_menu=None,
    maximized=False,
    focused=True,
    width='fill',
    height=None,
    bg=None,
    border=True,
    theme=None,
)
```

La barra de título de una ventana, sola: botones de ventana con el estilo de `style` (a la izquierda en macOS), elementos `start`, el título y elementos `end`. Sin callbacks solo se muestra, que es como Pyzed Design previsualiza un formulario con el marco de cada plataforma.

| Parámetro | Descripción |
| --- | --- |
| `title` | Título (centrado, o a la izquierda en Windows). |
| `style` | `"macos"`, `"windows"`, `"gnome"`, `"ubuntu"` o `"kde"` (`None`: el del sistema). |
| `start` | Elementos al principio. |
| `center` | Widget en el centro en lugar del título. |
| `end` | Elementos al final. |
| `on_drag` | Se llama al arrastrar la parte vacía de la barra (devuelve `Command.drag_window()`). |
| `on_minimize` | Botón de minimizar. |
| `on_maximize` | Botón de maximizar y doble clic en la barra. |
| `on_close` | Botón de cerrar. |
| `on_menu` | Clic derecho en la barra. |
| `maximized` | Muestra el símbolo de restaurar. |
| `focused` | `False` la atenúa como una ventana en segundo plano. |
| `width` | Ancho: píxeles, `"fill"`, `"shrink"` o `"fill:N"` (proporción). |
| `height` | Alto. Por defecto el de la plataforma. |
| `bg` | Color de fondo (`"#rrggbb[aa]"`, `(r, g, b[, a])` o `"transparent"`). |
| `border` | Línea bajo la barra. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `window_controls`

```python
window_controls(
    style=None,
    *,
    on_minimize=None,
    on_maximize=None,
    on_close=None,
    maximized=False,
    focused=True,
    height=None,
    theme=None,
)
```

Los botones de minimizar, maximizar y cerrar con el estilo de una plataforma. Un botón sin callback se dibuja pero no hace nada.

| Parámetro | Descripción |
| --- | --- |
| `style` | `"macos"`, `"windows"`, `"gnome"`, `"ubuntu"` o `"kde"` (`None`: el del sistema). |
| `on_minimize` | Botón de minimizar. |
| `on_maximize` | Botón de maximizar. |
| `on_close` | Botón de cerrar. |
| `maximized` | Muestra el símbolo de restaurar. |
| `focused` | `False` los atenúa. |
| `height` | Alto. |
| `theme` | Tema a usar en lugar del actual (`pyzed.theme.current()`). |

### `Menu`

```python
@dataclass
class Menu(label, items=[])
```

Un menú de la barra de menús de un marco de ventana: un nombre y sus elementos (`ui.MenuItem`, `ui.SEPARATOR` o un texto de cabecera).

| Parámetro | Descripción |
| --- | --- |
| `label` | El nombre del menú. |
| `items` | Sus elementos: `ui.MenuItem`, `ui.SEPARATOR` o un texto de cabecera. |

```python
ui.Menu("Archivo", [ui.MenuItem("Abrir…", self.open, keys="ctrl-o"), ui.SEPARATOR, ui.MenuItem("Salir", self.close)])
```

### `system_platform`

```python
system_platform()
```

El estilo de los botones de ventana de este sistema: `"macos"`, `"windows"`, `"kde"`, `"ubuntu"` o `"gnome"` (otros escritorios Linux). En WSL es `"windows"`.

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
modal(
    content,
    *,
    title=None,
    on_close=None,
    width=480,
    footer=(),
    description=None,
    icon=None,
    max_height=None,
    theme=None,
)
```

Un diálogo. Úsalo como `overlay` de `ui.layer`.

| Parámetro | Descripción |
| --- | --- |
| `content` | Contenido: un `Widget`, un texto o un número (se convierte en texto). |
| `title` | Título. |
| `on_close` | El botón de cerrar; también lo envía Escape mientras el diálogo tiene el foco. |
| `width` | Píxeles o `"sm"` (360), `"md"` (480), `"lg"` (640) o `"xl"` (820). |
| `footer` | Botones del pie, alineados a la derecha. |
| `description` | Línea atenuada bajo el título. |
| `icon` | Icono antes del título. |
| `max_height` | Desplaza el contenido más alto que esto, sin ocultar la cabecera ni el pie. |
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
| `keys` | Atajo que se muestra al final, escrito como texto: `"ctrl-s"`, `"cmd-k cmd-s"`. |
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

Una paleta de comandos: filtra `commands` por `query` con búsqueda difusa y muestra sus atajos.

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
    progress=None,
    on_press=None,
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
| `progress` | De 0 a 1: una barra fina abajo (tiempo restante, una descarga). |
| `on_press` | Hace pulsable la tarjeta. |
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
popover(base, content=None, *, x=0, y=0, on_dismiss=None, align_x='start')
```

Muestra `content` (un `ui.menu`, una tarjeta…) sobre `base` en `(x, y)`. Hacer clic en cualquier otro sitio llama a `on_dismiss`. Para un menú de clic derecho, guarda la posición del ratón con `mouse_area(on_move=...)` y abre el popover desde `on_right_press` (ver `examples/context_menu.py`).

| Parámetro | Descripción |
| --- | --- |
| `base` | La interfaz de debajo. |
| `content` | Lo que flota (o `None`). |
| `x` | Posición horizontal. |
| `y` | Posición vertical. |
| `on_dismiss` | Mensaje o callable que se envía al cerrar. |
| `align_x` | Alineación horizontal: `"start"`/`"left"`, `"center"`, `"end"`/`"right"`. |

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
    annotations=None,
    show_whitespace=False,
    tab_size=None,
    capture_keys=(),
    on_scroll=None,
    auto_close=True,
    folding=True,
    minimap=False,
    cursor_shape='bar',
    cursor_blink=True,
    cursor_width=2.0,
    cursor_color=None,
    on_zoom=None,
    on_action=None,
    highlights=None,
    match_brackets=True,
    selection_highlight=True,
    font=None,
    keymap=None,
    scrollbar=True,
    theme=None,
)
```

Un editor de código: resaltado con los colores del tema, números de línea y marcadores de git.

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
| `annotations` | `{línea: "texto"}` o `{línea: ("texto", color)}`: texto virtual al final de la línea (code lens, diagnósticos). |
| `show_whitespace` | Dibuja los espacios como `·` y los tabuladores como `→`. |
| `tab_size` | Tab inserta espacios hasta el siguiente múltiplo; Enter mantiene la sangría (un nivel más tras `:`); Backspace quita un nivel. |
| `capture_keys` | Teclas que el editor deja al `on_key` de la app (`"up"`, `"enter"`…), por ejemplo con una lista de autocompletado abierta. |
| `on_scroll` | Se llama al desplazar. |
| `auto_close` | Cierra paréntesis, corchetes, llaves y comillas al escribir (y envuelve la selección). |
| `folding` | Flechas de plegado en el margen; Ctrl+Shift+[ pliega y Ctrl+Shift+] despliega. |
| `minimap` | `True` (o un ancho en píxeles) muestra un minimapa a la derecha. |
| `cursor_shape` | `"bar"`, `"block"`, `"underline"` o `"hollow"`. |
| `cursor_blink` | Si el cursor parpadea. |
| `cursor_width` | Ancho del cursor de barra. |
| `cursor_color` | Color del cursor (por defecto, el color de jugador del tema). |
| `on_zoom` | Callable que recibe `1`, `-1` o `0` con Ctrl+= / Ctrl+- / Ctrl+0 y Ctrl+rueda. |
| `on_action` | Callable que recibe el nombre de cada acción del editor que se ejecuta (`"undo"`, `"select_next"`…), por ejemplo para contarlas. |
| `highlights` | Rangos pintados detrás del texto con el color de búsqueda del tema: `[(línea, columna, línea_final, columna_final)]`, desde 1, con el final excluido. |
| `match_brackets` | Remarca el corchete pareja del que está junto al cursor (Ctrl+M salta a él). |
| `selection_highlight` | Resalta las demás apariciones del texto seleccionado (Ctrl+D añade la siguiente como cursor). |
| `font` | Tipografía: `"mono"` por defecto; `"sans"` hace un cuadro de texto de varias líneas, como el cuadro de mensaje de un chat. |
| `keymap` | Diccionario `{atajo: acción}` al estilo de Zed (`{"ctrl-shift-d": "duplicate_line_down"}`); `None` como acción quita una tecla por defecto. Créalo a partir de cambios por acción con `pyzed.ui.editor.keymap_for`. |
| `scrollbar` | `False` oculta las barras de desplazamiento. |
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

## Selector de color

### `ColorPicker`

```python
class ColorPicker
```

Un componente para elegir un color con alfa, un gradiente lineal (paradas que se añaden, arrastran y quitan, más un ángulo) o un relleno con máscara de opacidad. `on_change` recibe un texto `"#rrggbb[aa]"`, un `pz.Gradient` o un `pz.Paint`, todos válidos como `background`. Devuelve el valor elegido en `value`. Ver [Estilos](/pyzed/es/theming/styles/#selector-de-color).

| Parámetro | Descripción |
| --- | --- |
| `value` | Un color, token del tema, `pz.Gradient` o `pz.Paint`. |
| `alpha` | Muestra la barra y el campo de alfa. |
| `gradients` | Muestra el cambio Sólido/Gradiente. |
| `masks` | Muestra el editor de máscara. |
| `swatches` | Colores rápidos (por defecto: el acento y los colores de estado del tema). |
| `on_change` | Recibe `event.value`. |

```python
ui.ColorPicker(value=self.fill, on_change=lambda e: setattr(self, "fill", e.value))
```

**Métodos y propiedades**

#### `ColorPicker.parts`

```python
ColorPicker.parts()
```

`(stops, angle, mask, opacity)`: una sola parada y sin ángulo para un color liso.

#### `ColorPicker.build`

```python
ColorPicker.build(stops, angle, mask, opacity)
```

Convierte `(stops, angle, mask, opacity)` de nuevo en un color, un `Gradient` o un `Paint`.

#### `ColorPicker.publish`

```python
ColorPicker.publish(*parts)
```

Fija el valor a partir de las partes, descarta el texto hex a medio escribir y emite `change`.

#### `ColorPicker.current`

```python
ColorPicker.current()
```

Devuelve el color hex que se está editando (el de la parada seleccionada).

#### `ColorPicker.set_color`

```python
ColorPicker.set_color(color)
```

Cambia el color de la parada seleccionada por `color` y publica el resultado.

#### `ColorPicker.hsva`

```python
ColorPicker.hsva()
```

Devuelve el color editado como `(h, s, v, a)`, cada uno de 0 a 1.

#### `ColorPicker.pick_sv`

```python
ColorPicker.pick_sv(event)
```

Fija la saturación y el valor al pulsar o arrastrar en el área de saturación/valor.

#### `ColorPicker.pick_hue`

```python
ColorPicker.pick_hue(event)
```

Fija el tono al pulsar o arrastrar en la barra de tono.

#### `ColorPicker.pick_alpha`

```python
ColorPicker.pick_alpha(event)
```

Fija el alfa al pulsar o arrastrar en la barra de alfa.

#### `ColorPicker.type_hex`

```python
ColorPicker.type_hex(text)
```

Gestiona lo que se escribe en el campo hex: aplica el texto en cuanto es un color hex válido.

#### `ColorPicker.set_alpha_percent`

```python
ColorPicker.set_alpha_percent(value)
```

Fija el alfa desde el campo de porcentaje (0 a 100).

#### `ColorPicker.set_mode`

```python
ColorPicker.set_mode(mode)
```

Cambia entre `"Solid"` y `"Gradient"`.

#### `ColorPicker.set_angle`

```python
ColorPicker.set_angle(value)
```

Fija el ángulo del gradiente en grados (o el de la máscara, sobre un color liso).

#### `ColorPicker.select_stop`

```python
ColorPicker.select_stop(index)
```

Selecciona para editar la parada del gradiente en `index`.

#### `ColorPicker.move_stop`

```python
ColorPicker.move_stop(index, event)
```

Mueve una parada del gradiente adonde se pulsa la barra o según el `dx` de un arrastre.

#### `ColorPicker.add_stop`

```python
ColorPicker.add_stop(event)
```

Añade una parada del gradiente donde se hace clic en la barra, con el color que el gradiente tiene ahí.

#### `ColorPicker.remove_stop`

```python
ColorPicker.remove_stop()
```

Quita la parada del gradiente seleccionada (un gradiente conserva al menos dos).

#### `ColorPicker.toggle_mask`

```python
ColorPicker.toggle_mask(on)
```

Con `on` añade una máscara que va de opaco a transparente; si no, quita la máscara.

#### `ColorPicker.select_mask_stop`

```python
ColorPicker.select_mask_stop(index)
```

Selecciona para editar la parada de la máscara en `index`.

#### `ColorPicker.move_mask_stop`

```python
ColorPicker.move_mask_stop(index, event)
```

Mueve una parada de la máscara adonde se pulsa la barra o según el `dx` de un arrastre, manteniendo las paradas ordenadas.

#### `ColorPicker.add_mask_stop`

```python
ColorPicker.add_mask_stop(event)
```

Añade una parada de la máscara donde se hace clic en la barra, con la opacidad que la máscara tiene ahí (como mucho 8).

#### `ColorPicker.set_mask_opacity`

```python
ColorPicker.set_mask_opacity(value)
```

Fija la opacidad de la parada de la máscara seleccionada (0 a 1).

#### `ColorPicker.remove_mask_stop`

```python
ColorPicker.remove_mask_stop()
```

Quita la parada de la máscara seleccionada (una máscara conserva al menos dos).

#### `ColorPicker.marker`

```python
ColorPicker.marker(x, y, color, *, size=14, selected=True, **events)
```

Un tirador redondo de color `color` centrado en `(x, y)`.

#### `ColorPicker.area`

```python
ColorPicker.area(layers, height, markers, on_pick, *, width=248)
```

Una franja redondeada de capas apiladas que informa de dónde se pulsa y se arrastra.

#### `ColorPicker.sv_area`

```python
ColorPicker.sv_area()
```

El cuadrado de saturación/valor del tono actual, con un marcador en el color actual.

#### `ColorPicker.hue_bar`

```python
ColorPicker.hue_bar()
```

La barra de tono arcoíris con un marcador en el tono actual.

#### `ColorPicker.alpha_bar`

```python
ColorPicker.alpha_bar()
```

La barra de alfa (sobre un damero) con un marcador en el alfa actual.

#### `ColorPicker.stops_bar`

```python
ColorPicker.stops_bar(points, preview, selected, on_select, on_move, on_add, *, colors=True)
```

Una barra que previsualiza `preview` con un tirador arrastrable por cada punto `(offset, value)`.

### `color_swatch`

```python
color_swatch(value, *, size=20, on_press=None)
```

Un cuadrito que muestra un color, gradiente o pintura sobre un damero.

| Parámetro | Descripción |
| --- | --- |
| `value` | Qué mostrar. |
| `size` | Lado en píxeles. |
| `on_press` | Lo hace pulsable. |

### `checkerboard`

```python
checkerboard(width, height, size=6)
```

Un damero claro/oscuro para dibujar bajo colores translúcidos.

| Parámetro | Descripción |
| --- | --- |
| `width` | Ancho. |
| `height` | Alto. |
| `size` | Tamaño de celda. |

## Selector de iconos

### `IconPicker`

```python
class IconPicker
```

Un componente para elegir un icono de Lucide: un buscador (nombres y etiquetas), un desplegable de categorías y una cuadrícula que solo construye las filas visibles. Enter elige la primera coincidencia. `on_change` recibe el nombre del icono (`""` si se quita); devuélvelo en `value`. Ver la página [Selector de iconos](/pyzed/es/library/icon-picker/).

| Parámetro | Descripción |
| --- | --- |
| `value` | El nombre del icono elegido. |
| `columns` | Iconos por fila. |
| `height` | Alto de la cuadrícula. |
| `clearable` | Muestra un botón que quita el icono. |
| `autofocus` | Da el foco al buscador al aparecer. |
| `on_change` | Recibe `event.value`. |

```python
ui.IconPicker(value=self.icon, on_change=lambda e: setattr(self, "icon", e.value))
```

**Métodos y propiedades**

#### `IconPicker.set_query`

```python
IconPicker.set_query(text)
```

Filtra la cuadrícula por `text` (nombres y etiquetas).

#### `IconPicker.set_group`

```python
IconPicker.set_group(key)
```

Muestra solo los iconos de la categoría `key` (`""` para todos).

#### `IconPicker.matches`

```python
IconPicker.matches()
```

Los iconos que se muestran: los de la categoría elegida que coinciden con la búsqueda, los mejores primero.

#### `IconPicker.pick`

```python
IconPicker.pick(name)
```

Selecciona `name` y emite `change`.

### `icon_picker_dialog`

```python
icon_picker_dialog(
    value,
    on_pick,
    *,
    on_close=None,
    title=None,
    columns=10,
    clearable=True,
    key='icon-picker',
    theme=None,
)
```

Un diálogo con un `IconPicker` que elige con un clic; úsalo como diálogo de `ui.dialog_layer`. El buscador recibe el foco.

| Parámetro | Descripción |
| --- | --- |
| `value` | El icono actual. |
| `on_pick` | Se llama con el nombre del icono pulsado (`""` si se quita). |
| `on_close` | El botón de cerrar. |
| `title` | Por defecto: "Elegir un icono", traducido. |
| `columns` | Iconos por fila. |
| `clearable` | Muestra el botón "Sin icono". |
| `key` | Clave del componente, para varios selectores en una vista. |
| `theme` | Tema. |

```python
ui.dialog_layer(page, ui.icon_picker_dialog(self.icon, self.pick, on_close=self.close) if self.picking else None,
                on_dismiss=self.close)
```

### `icon_grid`

```python
icon_grid(
    names,
    on_pick,
    *,
    selected=None,
    columns=8,
    cell=34,
    height=288,
    id=None,
    theme=None,
)
```

La cuadrícula de iconos sola, virtualizada: solo se construyen las filas visibles, así que miles de iconos cuestan lo mismo que unos pocos.

| Parámetro | Descripción |
| --- | --- |
| `names` | Nombres de iconos, en orden. |
| `on_pick` | Se llama con el nombre pulsado. |
| `selected` | El nombre resaltado. |
| `columns` | Iconos por fila. |
| `cell` | Lado de cada celda en píxeles. |
| `height` | Alto de la cuadrícula. |
| `id` | Id del desplazable, para `Command.scroll_to`. |
| `theme` | Tema. |
