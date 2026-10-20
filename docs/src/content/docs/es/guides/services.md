---
title: Servicios
description: "Temporizadores, atajos, vigilantes de archivos, procesos, tareas en segundo plano, peticiones web, portapapeles, ajustes, diálogos de archivos y notificaciones para apps de escritorio en Python con Pyzed, con eventos en el hilo de la interfaz."
sidebar:
  order: 5.5
---

Los **servicios** son las partes de una app que lanzan eventos pero no dibujan nada: `pz.Timer`, `pz.Shortcut`,
`pz.FileWatcher`, `pz.Process`, `pz.Worker`, `pz.HttpRequest`, `pz.Clipboard`, `pz.Settings`, `pz.FileDialog` y
`pz.Notification`. Son los mismos objetos que los [componentes no visuales](/pyzed/es/editor/non-visual-components/)
de Pyzed Design, y funcionan en un `pz.App`, en un formulario o en un script sin ninguna ventana.

```python
from pathlib import Path

import pyzed as pz
from pyzed import ui


class Inbox(pz.App):
    def __init__(self):
        self.files = sorted(p.name for p in Path("inbox").glob("*"))
        self.watcher = pz.FileWatcher("inbox", on_change=self.refresh)
        self.watcher.start()

    def refresh(self, changed):            # corre en el hilo de la interfaz
        self.files = sorted(p.name for p in Path("inbox").glob("*"))

    def view(self):
        return pz.column([ui.list_item(name, icon="file-text") for name in self.files], padding=16)


pz.run(Inbox)
```

![Un Vigilante de archivos listando los archivos que se crean y se borran en una carpeta](/pyzed/media/services/watcher.webp)

## Handlers e hilos

Pasa los handlers como `on_<evento>=`, o más tarde con `service.on("evento", handler)` (`None` lo quita). Un handler
con un parámetro recibe el valor del evento; uno sin parámetros simplemente se llama. Cada clase lista sus eventos en
`Service.events`.

Los vigilantes, los procesos, las tareas y las peticiones web trabajan en **hilos en segundo plano**, pero sus eventos
llegan a los handlers en **el hilo de la app** (con `pz.post`), así que un handler puede cambiar el estado de la app y
devolver comandos como cualquier callback. Sin una app en marcha, en un script o en un test, el handler se llama en
el momento, en el hilo que lanzó el evento.

`service.enabled = False` silencia todos sus eventos; `stop()` detiene lo que esté haciendo.

## Los servicios

| Clase | Lanza | Qué saber |
| --- | --- | --- |
| `pz.Timer(interval=1000, repeat=True)` | `tick` (la cuenta) | Milisegundos, como en Visual Basic y Qt. Devuelve `timer.subscriptions()` desde `App.subscriptions`. `start()`, `stop()`, `running`. |
| `pz.Shortcut("mod-s")` | `activate` (la combinación) | Llama a `shortcut.handle(combo)` desde `on_key`. Valen `"Ctrl+S"`, `"ctrl-s, cmd-s"` y `mod-` (Cmd en macOS, Ctrl en el resto). |
| `pz.FileWatcher(path, pattern="*", recursive=False, interval=500)` | `created`, `modified`, `deleted` (una ruta), `change` (la lista) | Compara fechas y tamaños cada `interval` ms, así que funciona igual en todas partes, también en unidades de red. |
| `pz.Process(command, directory=None, env=None, shell=False)` | `started`, `output`, `error_output` (una línea), `finished` (código de salida), `failed` | `start()`, `write(text)`, `kill()`, `wait()`, `running`, `exit_code`. Un comando en texto se separa como lo haría una shell. |
| `pz.Worker(work)` | `progress`, `done` (el resultado), `failed` (la excepción) | `run(value)` llama a `work(value)` en un hilo; puede usar `report(progress)` y mirar `cancelled`. |
| `pz.HttpRequest(url, method="GET", headers=None, body=None, timeout=30)` | `response` (un `HttpResponse`), `failed` | `send()`; `send(json={...})` envía JSON con POST. Los estados de error también son respuestas: mira `response.ok`. |
| `pz.Clipboard(watch=False, interval=500)` | `change`, `paste` (el texto) | `copy(text)` y `paste()` devuelven comandos. Con `watch`, devuelve `subscriptions()` desde tu app. |
| `pz.Settings(name, folder=None, defaults=None)` | `change` (`(clave, valor)`) | Un diccionario guardado como JSON al momento (`autosave`), por usuario, en la carpeta de ajustes de Pyzed. |
| `pz.FileDialog(mode="open", filters=..., directory=None, file_name="")` | `chosen` (ruta o lista), `cancelled` | `show()` devuelve el comando que lo abre; modos `open`, `open_many`, `save`, `folder`. |
| `pz.Notification(title, text)` | `shown`, `failed` | `show(text=None)` devuelve si se pudo mostrar. |

### Un temporizador y un atajo

```python
import time

import pyzed as pz


class Clock(pz.App):
    def __init__(self):
        self.now = ""
        self.clock = pz.Timer(1000, on_tick=self.tick)
        self.quit = pz.Shortcut("mod-q", on_activate=lambda: pz.Command.exit())

    def tick(self):
        self.now = time.strftime("%H:%M:%S")

    def subscriptions(self):
        return self.clock.subscriptions()

    def on_key(self, combo):
        return self.quit.handle(combo)

    def view(self):
        return pz.text(self.now, size=48)
```

### Un comando y su salida

```python
self.log = []
self.build = pz.Process("cargo build --release", directory="engine",
                        on_output=self.log.append, on_error_output=self.log.append,
                        on_finished=lambda code: self.done(code == 0))
self.build.start()
```

### Trabajo en segundo plano

```python
def resize_all(paths):
    for i, path in enumerate(paths):
        if worker.cancelled:
            return None
        shrink(path)
        worker.report((i + 1) * 100 // len(paths))
    return len(paths)

worker = pz.Worker(resize_all, on_progress=self.set_progress, on_done=self.finished)
worker.run(photos)
```

### Una API web

```python
api = pz.HttpRequest("https://api.github.com/repos/albakore/pyzed", on_response=self.show_stars)
api.send()

def show_stars(self, response):
    if response.ok:
        self.stars = response.json()["stargazers_count"]
```

### Ajustes y diálogos

```python
prefs = pz.Settings("my-app", defaults={"theme": "One Dark"})
prefs["theme"] = "One Light"          # se guarda al momento
prefs.get("theme")                    # "One Light", también la próxima vez

dialog = pz.FileDialog("open", filters="Imágenes: png, jpg", on_chosen=self.load_image)

def open_clicked(self):
    return dialog.show()              # un comando: devuélvelo
```

## Sin ventana

Nada de esto necesita una app en marcha. Los scripts y los tests pueden esperar el resultado:

```python
import pyzed as pz

process = pz.Process(["git", "status", "--short"], on_output=print)
process.start()
process.wait()                        # espera a que termine; devuelve el código de salida

request = pz.HttpRequest("https://example.com")
request.send()
print(request.wait(10).status)        # 200
```

`Process.wait()`, `Worker.wait()` y `HttpRequest.wait()` esperan a que termine el trabajo (con un `timeout`
opcional) y devuelven el código de salida, el resultado o la respuesta.
