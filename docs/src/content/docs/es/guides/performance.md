---
title: Muchos datos y rendimiento
description: Muestra cientos de miles de filas con listas y tablas virtuales, y evita reconstruir las partes de la vista que no cambiaron con @pz.memo.
sidebar:
  order: 18
---

Pyzed llama a `view()` después de cada mensaje y convierte el árbol de widgets que devuelve en
widgets de Iced. En la mayoría de apps eso tarda mucho menos de un milisegundo. Dos cosas lo
hacen lento: construir **muchas filas** que ni siquiera están en pantalla y reconstruir
**subárboles grandes** que no cambiaron. Pyzed tiene una herramienta para cada una.

## Listas y tablas virtuales

Una lista virtual solo construye las filas visibles. Las filas se construyen cuando entran en
la vista y se descartan cuando salen, así que una lista de un millón de elementos cuesta lo
mismo que una de cincuenta.

```python
import pyzed as pz
from pyzed import ui

class Logs(pz.App):
    def __init__(self):
        self.lines = [f"[{i:06}] petición atendida" for i in range(500_000)]

    def view(self):
        return ui.virtual_list(
            self.lines,
            lambda line: pz.text(line, font="mono", size=12),
            item_height=20,
            id="logs",
        )
```

- [`ui.virtual_list(items, render)`](/pyzed/es/library/virtual-list/) es una lista con scroll y
  con el tema: `render(elemento)` devuelve el widget de un elemento.
- [`ui.table`](/pyzed/es/library/table/) también está virtualizada: pásale todas tus filas.
- [`pz.virtual_column(count, item, item_height=...)`](/pyzed/es/reference/widgets/#virtual_column)
  es la pieza básica: `item(índice)` devuelve la fila `índice`. Ponla dentro de cualquier
  `pz.scrollable`.

Todas las filas tienen la misma altura (`item_height`), y por eso Pyzed sabe dónde va cada fila
sin construirla. Para ir a la fila `i`, desplaza el `id` de la lista hasta
`i * (item_height + spacing)`:

```python
pz.Command.scroll_to("logs", 0, 1_000 * 20)   # fila 1000
```

Medido con una tabla de 200 000 filas, construir la vista pasó de 3,7 s a 0,2 ms.

:::tip
`items` y `rows` deberían ser listas (u otras secuencias): otros iterables se copian a una lista
en cada `view()`. Ordenar una tabla enorme en cada `view()` es el coste que queda; guarda las
filas ya ordenadas en tu estado u ordénalas en una función `@pz.memo`.
:::

## Subárboles memoizados

`@pz.memo` guarda lo que devuelve una función según sus argumentos. Mientras los argumentos
sean iguales, el siguiente `view()` reutiliza el mismo árbol de widgets en vez de construirlo
otra vez:

```python
@pz.memo
def sidebar(files: tuple, selected: str):
    return pz.column([ui.list_item(f, icon="file", selected=f == selected) for f in files])

class Editor(pz.App):
    def view(self):
        return pz.row([sidebar(tuple(self.files), self.selected), self.editor()])
```

Cómo se comparan los argumentos:

| Argumento | Se compara por |
| --- | --- |
| Números, textos, tuplas, dataclasses congeladas... | Valor (su hash). |
| Listas, dicts y sets | Su contenido. |
| Cualquier otra cosa (tus objetos, `self`) | Identidad: modificarlo sin reemplazarlo no refresca la caché. |

El tema y el idioma actuales siempre forman parte de la clave, así que al cambiarlos se
reconstruyen todos los subárboles memoizados.

:::caution
Una función memoizada solo ve sus argumentos. Si lee `self.algo` o una variable global, el
subárbol guardado conserva el valor antiguo hasta que cambien los argumentos. Pasa todo lo que
usa, o un número de versión que incrementes cuando cambien los datos.
:::

- `@pz.memo(maxsize=256)` guarda más resultados (64 por defecto). Es útil en una función que se
  llama una vez por fila, como el `render` de una lista virtual.
- `funcion.cache_clear()` vacía la caché de una función y `pz.clear_memos()` la de todas.
- `pz.memo_stats()` devuelve `{"hits": ..., "misses": ...}` para comprobar que un subárbol se reutiliza.

## Otros consejos

- Deja `view()` sin trabajo lento: carga archivos, consulta bases de datos y ordena datos en los
  handlers o en [tareas async](/pyzed/es/guides/async/), y guarda los resultados en tu estado.
- Dibuja miles de formas con un solo [canvas](/pyzed/es/guides/canvas/) en vez de miles de widgets.
- Las suscripciones `pz.every` llaman a `view()` en cada tic: detenlas cuando nada se mueve.
