---
title: Inicio rápido
description: Tu primera ventana con Pyzed en cinco minutos.
---

## 1. Una ventana

```python title="hola.py"
import pyzed as pz


class Hola(pz.App):
    title = "Hola"
    size = (400, 240)

    def view(self):
        return pz.center(pz.text("Hola, Pyzed", size=24))


pz.run(Hola)
```

```bash
python hola.py
```

Una app es una clase que hereda de `pz.App`. Su método `view()` devuelve los widgets que se ven.
`pz.run()` abre la ventana y bloquea hasta que se cierra.

## 2. Estado y mensajes

El estado vive en tu objeto. Los widgets interactivos reciben un **mensaje**: cualquier valor de
Python. Cuando el usuario pulsa el botón, Pyzed llama a `update(mensaje)` y vuelve a dibujar.

```python title="counter.py"
import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    title = "Counter"
    size = (360, 220)

    def __init__(self):
        self.count = 0

    def update(self, message):
        if message == "increment":
            self.count += 1
        elif message == "decrement":
            self.count -= 1

    def view(self):
        return pz.center(
            pz.column([
                ui.heading(str(self.count)),
                pz.row([
                    ui.button("1", "decrement", icon="minus"),
                    ui.button("1", "increment", icon="plus", variant="solid"),
                    ui.icon_button("rotate-ccw", lambda: setattr(self, "count", 0), tooltip="Reset"),
                ], spacing=8),
            ], spacing=16, align="center"),
            bg=self.resolved_theme().editor,
        )


pz.run(Counter)
```

![El contador](../../../../../screenshots/counter.png)

## 3. Callables en lugar de mensajes

Si el mensaje es un callable (una lambda o un método), Pyzed lo **llama directamente** y no pasa
por `update`. Para apps pequeñas suele ser lo más cómodo:

```python
ui.button("Guardar", self.guardar)            # llama a self.guardar()
ui.button("Borrar", lambda: self.borrar(id))  # con argumentos
```

Los controles que producen un valor (`on_input`, `on_toggle`, `on_change`…) llaman al callable
con ese valor:

```python
ui.input(self.nombre, lambda texto: setattr(self, "nombre", texto), placeholder="Tu nombre")
```

## 4. Componentes y temas

`pyzed.ui` trae componentes listos al estilo de Zed. Todos leen el tema actual:

```python
class MiApp(pz.App):
    theme = pz.themes.ONE_LIGHT

    def cambiar_tema(self):
        self.theme = "One Light" if self.resolved_theme().is_dark else "One Dark"
```

## Siguiente

- [Crear un proyecto con `pyzed new`](/pyzed/es/getting-started/new-project/)
- [Tutorial: lista de tareas](/pyzed/es/tutorials/todo-app/)
- [Guía de la arquitectura](/pyzed/es/guides/architecture/)
