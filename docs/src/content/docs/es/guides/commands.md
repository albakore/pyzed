---
title: Comandos y tareas
description: Enfocar campos, cerrar la app, editar el editor, trabajo en segundo plano y mensajes desde hilos.
sidebar:
  order: 4
---

Un [`Command`](/pyzed/es/reference/command/) es un efecto que el runtime ejecuta por ti. Devuélvelo
desde `update`, `on_start`, `on_key` o cualquier callback.

```python
from pyzed import Command
```

| Comando | Efecto |
| --- | --- |
| `Command.focus(id)` | Enfoca el campo con ese `id`. |
| `Command.exit()` | Cierra la aplicación. |
| `Command.set_editor_text(id, texto)` | Reemplaza el texto de un editor. |
| `Command.set_editor_cursor(id, línea, col)` | Mueve el cursor de un editor (desde 1). |
| `Command.scroll_to_end(id)` | Desplaza un `scrollable` al final. |
| `Command.scroll_to(id, x, y)` | Desplaza un `scrollable` a una posición en píxeles. |
| `Command.copy(texto)` | Copia al portapapeles. |
| `Command.paste(then)` | Lee el portapapeles y llama a `then(texto)`. |
| `Command.paste_image(then)` | Lee una imagen del portapapeles y llama a `then(png)` con sus bytes PNG (`None` si no hay). |
| `Command.pick_files(then, ...)` | Abre el diálogo de archivos del sistema y llama a `then(rutas)`; `filters=[("Imágenes", ["png", "jpg"])]`, `multiple=False`, `folder=True`. |
| `Command.message(msg)` | Envía `msg` a `update` en el siguiente ciclo. |
| `Command.perform(fn, then)` | Ejecuta `fn()` en segundo plano (un hilo, o el loop de asyncio si es `async def`) y entrega el resultado a `then`. |
| `Command.batch([...])` | Varios a la vez (también vale devolver una lista). |
| `Command.open_window(w)`, `close_window`, `drag_window`… | Controlan ventanas. Ver [varias ventanas](/pyzed/es/guides/windows/#comandos-de-ventana). |

## Enfocar un campo

```python
def abrir_buscador(self):
    self.buscando = True
    return Command.focus("buscar")

def view(self):
    return ui.input(self.query, self.set_query, id="buscar") if self.buscando else ...
```

## Trabajo en segundo plano

`Command.perform` ejecuta una función lenta en segundo plano para no congelar la interfaz y, al
terminar, llama a `then(resultado)` en el hilo de la interfaz. Si la función es `async def`, corre
en el loop de asyncio de Pyzed; si devuelve un generador, `then` se llama con cada valor. Para
código async también puedes devolver la corrutina directamente: ver
[async y suscripciones](/pyzed/es/guides/async/).

```python
import json
import urllib.request


class Repos(pz.App):
    def __init__(self):
        self.repos, self.cargando = [], False

    def on_start(self):
        return self.cargar()

    def cargar(self):
        self.cargando = True
        return Command.perform(self.descargar, self.recibido)

    @staticmethod
    def descargar():
        with urllib.request.urlopen("https://api.github.com/users/albakore/repos") as r:
            return json.load(r)

    def recibido(self, repos):
        self.repos, self.cargando = repos, False

    def view(self):
        if self.cargando:
            return pz.center(ui.muted("Cargando…"))
        return pz.column([ui.list_item(r["name"], icon="book") for r in self.repos], padding=8)
```

Si `fn` lanza una excepción, se imprime y `then` no se llama. Captúrala dentro de `fn` y
devuelve un valor de error si quieres mostrarlo.

## Mensajes desde otros hilos

`pz.post(mensaje)` envía un mensaje a la app desde **cualquier hilo**. Sirve para progreso,
procesos largos, sockets o temporizadores:

```python
import subprocess
import threading


class Build(pz.App):
    def __init__(self):
        self.lineas = []

    def update(self, message):
        kind, value = message
        if kind == "linea":
            self.lineas.append(value)
            return Command.scroll_to_end("log")

    def compilar(self):
        def worker():
            proc = subprocess.Popen(["cargo", "build"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for linea in proc.stdout:
                pz.post(("linea", linea.rstrip()))
        threading.Thread(target=worker, daemon=True).start()

    def view(self):
        return pz.column([
            ui.button("Compilar", self.compilar, variant="solid"),
            ui.terminal(self.lineas, id="log"),
        ], spacing=8, padding=12)
```

`pz.post` lanza `RuntimeError` si no hay ninguna app ejecutándose. El GIL se libera mientras
corre el bucle de eventos, así que tus hilos avanzan con normalidad.

## Cerrar la app

```python
def on_key(self, combo):
    if combo == "ctrl-q":
        return Command.exit()
```
