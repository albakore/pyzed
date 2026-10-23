---
title: "Command"
description: "Referencia de la API de los comandos de Pyzed: los efectos que devuelven update y los callbacks, como enfocar campos, cerrar y tareas en segundo plano."
sidebar:
  order: 2
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Un `Command` es un efecto que el runtime ejecuta por ti. Devuélvelo desde `update`,
`on_start`, `on_key` o cualquier callback. También puedes devolver una lista o una
tupla de comandos. Ver la guía de [comandos y tareas](/pyzed/es/guides/commands/).

```python
from pyzed import Command

def on_key(self, combo):
    if combo == "ctrl-p":
        self.finder_open = True
        return Command.focus("finder")
```

## Métodos estáticos

### `Command`

La clase de los comandos. No se instancia directamente: usa sus métodos estáticos.

### `exit`

```python
exit()
```

Cierra la aplicación.

### `focus`

```python
focus(id)
```

Enfoca el `text_input` (o editor) con ese `id`.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` que pasaste al widget. |

### `focus_next`

```python
focus_next()
```

Mueve el foco del teclado al siguiente campo de la ventana, volviendo al primero tras el último (lo que hace Tab).

### `focus_previous`

```python
focus_previous()
```

Mueve el foco del teclado al campo anterior de la ventana (lo que hace Shift+Tab).

### `select_all`

```python
select_all(id)
```

Da el foco al `text_input` con ese `id` y selecciona todo su texto (lo que se escriba lo reemplaza).

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del campo. |

### `set_editor_text`

```python
set_editor_text(id, text)
```

Reemplaza el contenido del `code_editor` con ese `id`. Los editores no son controlados: `text` solo es el valor inicial.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del editor. |
| `text` | El texto nuevo. |

### `set_editor_cursor`

```python
set_editor_cursor(id, line, column)
```

Mueve el cursor del editor (línea y columna empiezan en 1). Funciona aunque el editor aún no se haya dibujado.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del editor. |
| `line` | Línea (desde 1). |
| `column` | Columna (desde 1). |

### `fold_all`

```python
fold_all(id, fold=True)
```

Pliega todos los bloques del editor (`fold=False` los despliega). Funciona aunque el editor aún no se haya dibujado.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del editor. |
| `fold` | `True` para plegar, `False` para desplegar. |

### `fold_line`

```python
fold_line(id, line, fold=True)
```

Pliega (o despliega) el bloque que empieza en `line`, según la sangría. Funciona aunque el editor aún no se haya dibujado.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del editor. |
| `line` | Línea (desde 1) donde empieza el bloque. |
| `fold` | `True` para plegar, `False` para desplegar. |

### `editor_action`

```python
editor_action(id, name)
```

Ejecuta una acción del editor con ese `id`, como si se pulsara su atajo: el nombre de la acción de Zed en snake case (`"undo"`, `"select_next"`, `"move_line_up"`, `"toggle_comments"`…). Lanza `ValueError` si el nombre no existe.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del editor. |
| `name` | El nombre de la acción (`Command.editor_actions()` las lista; también vale `"editor::SelectNext"`). |

### `editor_actions`

```python
editor_actions()
```

Los nombres que acepta `Command.editor_action`.

### `select_editor_ranges`

```python
select_editor_ranges(id, ranges)
```

Selecciona rangos del editor, un cursor por rango; el primero es el cursor principal. Despliega lo que los oculta y funciona aunque el editor aún no se haya dibujado.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del editor. |
| `ranges` | `[(línea, columna, línea_final, columna_final)]`, desde 1, con el final excluido (un rango vacío es un cursor sin selección). |

### `replace_editor_ranges`

```python
replace_editor_ranges(id, edits)
```

Reemplaza rangos del editor por textos en un solo paso de deshacer y llama al `on_change` del editor (buscar y reemplazar).

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del editor. |
| `edits` | `[((línea, columna, línea_final, columna_final), texto)]`, desde 1, con el final excluido. |

### `scroll_to_end`

```python
scroll_to_end(id)
```

Desplaza el `scrollable` con ese `id` hasta el final.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del scrollable. |

### `batch`

```python
batch(commands)
```

Ejecuta varios comandos.

| Parámetro | Descripción |
| --- | --- |
| `commands` | Lista de `Command`. |

### `message`

```python
message(message)
```

Vuelve a enviar `message` a `update` en el siguiente ciclo.

| Parámetro | Descripción |
| --- | --- |
| `message` | Cualquier valor de Python, o un callable. |

### `perform`

```python
perform(function, then=None)
```

Ejecuta `function()` en segundo plano y entrega el resultado a `then(resultado)` en el hilo de la interfaz. `function` puede ser normal (corre en un hilo) o `async def` (corre en el loop de asyncio de Pyzed). Si devuelve un generador (normal o async), `then` se llama con cada valor. También acepta una corrutina o un generador ya creados (`fetch(url)` en lugar de `fetch`). Sin `then`, los resultados van a `update`. Si `function` lanza, se imprime el error.

| Parámetro | Descripción |
| --- | --- |
| `function` | Función sin argumentos que hace el trabajo lento. |
| `then` | Callable que recibe el resultado (o `None` para enviarlo a `update`). |

```python
def cargar(self):
    self.cargando = True
    return Command.perform(lambda: requests.get(URL).json(), self.recibido)

def recibido(self, datos):
    self.cargando, self.datos = False, datos
```

### `scroll_to`

```python
scroll_to(id, x=0.0, y=0.0)
```

Desplaza el `scrollable` con ese `id` a una posición absoluta en píxeles.

| Parámetro | Descripción |
| --- | --- |
| `id` | El `id` del scrollable. |
| `x` | Desplazamiento horizontal. |
| `y` | Desplazamiento vertical. |

### `copy`

```python
copy(text)
```

Copia `text` al portapapeles del sistema.

| Parámetro | Descripción |
| --- | --- |
| `text` | El texto. |

### `paste`

```python
paste(then)
```

Lee el portapapeles y llama a `then(texto)` (cadena vacía si está vacío).

| Parámetro | Descripción |
| --- | --- |
| `then` | Callable que recibe el texto. |

### `paste_image`

```python
paste_image(then)
```

Lee una imagen del portapapeles (una captura, una imagen copiada) y llama a `then(png)` con sus bytes PNG, o a `then(None)` si el portapapeles no tiene una imagen.

| Parámetro | Descripción |
| --- | --- |
| `then` | Callable que recibe los bytes PNG o `None`. |

### `pick_files`

```python
pick_files(
    then,
    *,
    title=None,
    filters=None,
    directory=None,
    multiple=True,
    folder=False,
)
```

Abre el diálogo de archivos del sistema y llama a `then(rutas)` con las rutas elegidas (una lista vacía si se cancela).

| Parámetro | Descripción |
| --- | --- |
| `then` | Callable que recibe la lista de rutas. |
| `title` | El título del diálogo. |
| `filters` | Una lista de pares `(nombre, extensiones)`, como `[("Imágenes", ["png", "jpg"])]`. |
| `directory` | La carpeta en la que se abre. |
| `multiple` | `False` elige un solo archivo. |
| `folder` | `True` elige carpetas en vez de archivos. |

### `save_file`

```python
save_file(then, *, title=None, filters=None, directory=None, file_name=Ellipsis)
```

Abre el diálogo «Guardar como» del sistema y llama a `then(rutas)` con la ruta elegida en una lista (una lista vacía si se cancela).

| Parámetro | Descripción |
| --- | --- |
| `then` | Callable que recibe la lista con la ruta. |
| `title` | El título del diálogo. |
| `filters` | Una lista de pares `(nombre, extensiones)`, como `[("Imágenes", ["png", "jpg"])]`. |
| `directory` | La carpeta en la que se abre. |
| `file_name` | El nombre que sugiere. |

## Ventanas y portapapeles

### `open_window`

```python
open_window(window)
```

Abre una ventana nueva para esa instancia de `pz.Window`.

| Parámetro | Descripción |
| --- | --- |
| `window` | La ventana. |

### `close_window`

```python
close_window(window=None)
```

Cierra la ventana.

| Parámetro | Descripción |
| --- | --- |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `drag_window`

```python
drag_window(window=None)
```

Empieza a mover la ventana con el ratón (úsalo al pulsar una barra de título propia).

| Parámetro | Descripción |
| --- | --- |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `minimize_window`

```python
minimize_window(window=None)
```

Minimiza la ventana.

| Parámetro | Descripción |
| --- | --- |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `toggle_maximize_window`

```python
toggle_maximize_window(window=None)
```

Maximiza la ventana o la restaura si ya lo está.

| Parámetro | Descripción |
| --- | --- |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `maximize_window`

```python
maximize_window(maximized=True, window=None)
```

Maximiza la ventana, o la restaura con `maximized=False`.

| Parámetro | Descripción |
| --- | --- |
| `maximized` | `False` la restaura. |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `drag_resize_window`

```python
drag_resize_window(direction, window=None)
```

Empieza a cambiar el tamaño de la ventana con el ratón desde un borde o una esquina (para ventanas sin decoraciones del sistema; `ui.window_frame` y `pz.window_edges` ya lo hacen).

| Parámetro | Descripción |
| --- | --- |
| `direction` | `"n"`, `"s"`, `"e"`, `"w"`, `"ne"`, `"nw"`, `"se"` o `"sw"`. |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `show_window_menu`

```python
show_window_menu(window=None)
```

Muestra el menú de ventana del sistema (mover, tamaño, cerrar…) bajo el puntero. Solo Windows tiene uno.

| Parámetro | Descripción |
| --- | --- |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `set_fullscreen`

```python
set_fullscreen(fullscreen=True, window=None, monitor=None, exclusive=False)
```

Pone o quita la pantalla completa, en la pantalla que elijas y quizá exclusiva. Ver [Pantallas y quioscos](/pyzed/es/guides/windows/#pantallas-y-quioscos).

| Parámetro | Descripción |
| --- | --- |
| `fullscreen` | `True` para pantalla completa, `False` vuelve a ventana. |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |
| `monitor` | Un índice de `pz.monitors()`; `None` deja la pantalla actual. |
| `exclusive` | `True` toma la pantalla con su propio modo de vídeo (menos latencia en Windows y X11; Wayland se queda con una ventana sin bordes). |

### `set_window_level`

```python
set_window_level(level, window=None)
```

Mantiene la ventana sobre o bajo las demás.

| Parámetro | Descripción |
| --- | --- |
| `level` | `"top"`, `"bottom"` o `"normal"`. |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `hide_cursor`

```python
hide_cursor(hidden=True, window=None)
```

Oculta el puntero sobre la ventana pida lo que pida cada widget (paneles táctiles, quioscos).

| Parámetro | Descripción |
| --- | --- |
| `hidden` | `False` lo vuelve a mostrar. |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `list_monitors`

```python
list_monitors(then)
```

Pide al sistema sus pantallas y llama a `then(monitores)` con una lista de `pz.Monitor` (también la guarda para `pz.monitors()`).

| Parámetro | Descripción |
| --- | --- |
| `then` | Se llama con la lista. |

### `resize_window`

```python
resize_window(width, height, window=None)
```

Cambia el tamaño de la ventana (píxeles lógicos).

| Parámetro | Descripción |
| --- | --- |
| `width` | Ancho. |
| `height` | Alto. |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `move_window`

```python
move_window(x, y, window=None)
```

Mueve la ventana a una posición de la pantalla.

| Parámetro | Descripción |
| --- | --- |
| `x` | Posición horizontal. |
| `y` | Posición vertical. |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

### `focus_window`

```python
focus_window(window=None)
```

Trae la ventana al frente y le da el foco.

| Parámetro | Descripción |
| --- | --- |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |
