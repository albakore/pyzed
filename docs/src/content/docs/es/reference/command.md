---
title: "Command"
description: "Efectos secundarios que devuelven update y los callbacks."
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

### `set_fullscreen`

```python
set_fullscreen(fullscreen=True, window=None)
```

Pone o quita la pantalla completa.

| Parámetro | Descripción |
| --- | --- |
| `fullscreen` | `True` para pantalla completa. |
| `window` | La ventana (`pz.Window`). Sin ella, la que produjo el mensaje. |

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
