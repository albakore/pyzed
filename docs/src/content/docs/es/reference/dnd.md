---
title: "Arrastrar y soltar (pyzed.dnd)"
description: "Referencia de la API de pyzed.dnd: widgets draggable, droppable y sortable, asas de arrastre, el DragEvent y las ayudas move y reorder para arrastrar y soltar en apps de escritorio con Python."
sidebar:
  order: 10.7
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Agarra cosas, muévelas y suéltalas en otro sitio: tableros Kanban, listas y cuadrículas
ordenables, creadores de formularios y de páginas, lienzos al estilo de Figma y cables de
nodos. El movimiento, las vistas previas, los huecos y las animaciones son nativos; Python se
entera de la suelta. Mira la [guía de arrastrar y soltar](/pyzed/es/dnd/).

```python
pz.sortable(items=self.tareas, item=self.fila, id="tareas",
            on_reorder=lambda e: pz.dnd.move(self.tareas, e))
```

## Widgets

### `sortable`

```python
sortable(
    children=None,
    id='list',
    *,
    items=None,
    item=None,
    key=None,
    keys=None,
    data=None,
    group=None,
    accepts=None,
    direction='vertical',
    spacing=8,
    line_spacing=None,
    width=None,
    height=None,
    padding=None,
    align=None,
    handle=False,
    lock_axis=False,
    sort=True,
    pull=True,
    put=True,
    max_items=None,
    combine=False,
    locked=None,
    disabled=False,
    draggable=True,
    can_drop=None,
    placeholder='shadow',
    placeholder_style=True,
    ghost_opacity=0.4,
    over_style=False,
    active_style=False,
    source='hide',
    preview=None,
    lift=1.03,
    shadow=True,
    opacity=1.0,
    radius=6,
    threshold=4,
    delay=0,
    drop_animation=180,
    animation=200,
    from_children=False,
    keyboard=False,
    on_reorder=None,
    on_drop=None,
    on_enter=None,
    on_leave=None,
    on_over=None,
    on_drag_start=None,
    on_drag_end=None,
    theme=None,
)
```

Una lista (o fila, o cuadrícula que salta de fila) cuyos elementos se reordenan arrastrando. Da los hijos con `keys` (ids estables), o `items` con `item(x)` para dibujar uno y `key(x)` para nombrarlo. `on_reorder(event)` dice adónde fue un elemento (`event.from_index` → `event.index`, contados en la lista final) y `pz.dnd.reorder`/`pz.dnd.move` lo aplican. Mientras tanto los demás se apartan, un `placeholder` (`"shadow"`, `"ghost"`, `"none"`) marca el destino y los elementos se deslizan a su sitio en `animation` ms. `direction` es `"vertical"`, `"horizontal"` o `"wrap"`, con `spacing`, `line_spacing`, `width`, `height`, `padding` y `align`. Entre listas: mismo `group`; `accepts` recibe otros grupos o tipos; `pull=False` / `"clone"`, `put=False`, `sort=False`, `max_items`, `can_drop(event)`, `locked`; `combine=True` deja soltar sobre otro elemento (`event.combine`). Elementos: `handle`, `lock_axis`, `source`, `preview`, `lift`, `shadow`, `opacity`, `radius`, `threshold`, `delay`, `drop_animation`; `keyboard=True` mueve el elemento con foco con Alt+flechas. Eventos: `on_reorder` (`on_drop`), `on_enter`, `on_over`, `on_leave`, `on_drag_start`, `on_drag_end`.

```python
pz.sortable(items=self.cards["todo"], item=self.card, id="todo", group="cards",
on_reorder=lambda e: pz.dnd.move(self.cards, e))
```

### `draggable`

```python
draggable(
    content,
    id,
    *,
    data=None,
    type='item',
    preview=None,
    handle=False,
    disabled=False,
    axis=None,
    bounds=None,
    grid=None,
    threshold=4,
    delay=0,
    source=None,
    source_opacity=0.35,
    lift=1.03,
    shadow=True,
    opacity=1.0,
    radius=6,
    wire_color=None,
    wire_width=2,
    drop_animation=180,
    from_children=False,
    cursor=True,
    on_drag_start=None,
    on_drag_move=None,
    on_drag_end=None,
    theme=None,
)
```

Deja que el puntero agarre `content` y lo suelte en un `droppable` o `sortable`. `id` lo nombra (único en la ventana), `data` es lo que reciben los destinos en `event.data` y `type` lo que comparan con `accepts`. Aspecto: `preview` (otro widget, `"wire"` o `"none"`), `lift`, `shadow`, `opacity`, `radius`, `source` (`"ghost"`, `"hide"`, `"keep"`, con `source_opacity`), `wire_color`, `wire_width` y `drop_animation`. Límites: `handle`, `axis`, `bounds` (`"parent"`, `"window"`), `grid`, `threshold`, `delay`, `from_children`, `disabled`, `cursor`. Eventos: `on_drag_start`, `on_drag_move`, `on_drag_end` (`event.dropped`).

```python
pz.draggable(ui.card(ui.label("Informe.pdf")), "archivo-7", data=archivo, type="archivo")
```

### `droppable`

```python
droppable(
    content,
    id,
    *,
    accepts=None,
    can_drop=None,
    disabled=False,
    snap=None,
    guides=False,
    snap_preview=None,
    placeholder='none',
    placeholder_style=True,
    ghost_opacity=0.4,
    over_style=True,
    active_style=False,
    guide_color=None,
    on_drop=None,
    on_enter=None,
    on_leave=None,
    on_over=None,
    theme=None,
)
```

Convierte `content` en un sitio donde soltar. `accepts` lista los tipos que acepta (`None` o `"*"`: todos), `can_drop(event)` añade tu regla y `disabled` rechaza todo. Lienzos: `event.item_x`/`item_y` es dónde cae la esquina del elemento; `snap` lo ajusta a una cuadrícula y `guides=True` lo alinea con los demás (en `guide_color`); `snap_preview` mueve la vista previa allí. Aspecto: `over_style`, `active_style`, `placeholder` (`"shadow"`, `"ghost"`), `placeholder_style`, `ghost_opacity`. Eventos: `on_drop`, `on_enter`, `on_over`, `on_leave`.

```python
pz.droppable(papelera, "papelera", accepts="archivo", on_drop=lambda e: self.borrar(e.data))
```

### `drag_handle`

```python
drag_handle(content, *, cursor=Ellipsis)
```

La parte de un elemento que empieza el arrastre cuando el draggable o el sortable tiene `handle=True` (el agarre de una fila, el título de un nodo). Muestra `cursor` (`"grab"` por defecto) al pasar por encima.

| Parámetro | Descripción |
| --- | --- |
| `content` | El aspecto del asa. |
| `cursor` | El cursor encima: `"grab"`, `"move"`, `"pointer"`... |

## Eventos y ayudas

### `DragEvent`

```python
class DragEvent
```

Lo que recibe una función de arrastrar y soltar. `type`: `"start"`, `"move"`, `"enter"`, `"over"`, `"leave"`, `"drop"`, `"end"`, `"cancel"` (`"check"` en `can_drop`). Del elemento: `source`, `data` (`item`), `types`, `from_list`, `from_index`, `width`, `height`, `copy`. Del destino: `target`, `index`, `combine`, `x`, `y` (`position`), `item_x`, `item_y` (`item_position`). Además `window_x`, `window_y`, `dx`, `dy`, `dropped`, `within` y los modificadores `shift`, `ctrl`, `alt`, `logo`.

### `move`

```python
move(lists, event, *, make=None)
```

Aplica una suelta a tus listas y devuelve el elemento que cayó. `lists` asocia el id de cada sortable con su lista (o es la única lista). El elemento sale de `lists[event.from_list]` (salvo copias) y entra en `lists[event.target]` en `event.index`; las copias y los draggables sueltos son `make(event.data)` o una copia profunda. Las sueltas con `event.combine` no se mueven (devuelve `None`).

```python
pz.dnd.move({"pendiente": self.pendiente, "hecho": self.hecho}, event)
```

### `reorder`

```python
reorder(items, from_index, to_index)
```

Mueve `items[from_index]` a `to_index` (en la misma lista) y devuelve `items`.

### `current`

```python
current()
```

El arrastre en curso como `DragEvent`, o `None`.

### `cancel`

```python
cancel()
```

Cancela el arrastre en curso, como Escape.
