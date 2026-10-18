---
title: "Command"
description: "Efectos secundarios que devuelven update y los callbacks."
sidebar:
  order: 2
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs.py. -->

Un `Command` es un efecto que el runtime ejecuta por ti. Devuélvelo desde `update`,
`on_start`, `on_key` o cualquier callback. También puedes devolver una lista o una
tupla de comandos. Ver la guía de [comandos y tareas](/pyzed/guides/commands/).

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

Ejecuta `function()` en un hilo en segundo plano y entrega el resultado a `then(resultado)` en el hilo de la interfaz. Sin `then`, el resultado se envía a `update`. Si `function` lanza, se imprime el error.

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
