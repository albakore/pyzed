---
title: "Servicios (pyzed.services)"
description: "Referencia de la API de pyzed.services: temporizadores, atajos, vigilantes de archivos, procesos, tareas en segundo plano, peticiones web, portapapeles, ajustes, diálogos de archivos y notificaciones."
sidebar:
  order: 10.5
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

Los servicios lanzan eventos pero no dibujan nada: son los componentes no visuales de Pyzed
Design ([la bandeja bajo el formulario](/pyzed/es/editor/non-visual-components/)) y funcionan
igual en un `pz.App` o en un script. Los handlers van en `on_<evento>=`; los eventos que lanza un
hilo en segundo plano les llegan en el hilo de la app. Mira la [guía de servicios](/pyzed/es/guides/services/).

```python
watcher = pz.FileWatcher("inbox", pattern="*.csv", on_created=self.import_file)
watcher.start()
```

## Tiempo y teclas

### `Timer`

```python
class Timer
```

Lanza `tick` (con la cuenta) cada `interval` milisegundos mientras está en marcha; con `repeat=False` hace un solo tick. Devuelve `subscriptions()` desde el `subscriptions` de tu app.

### `Shortcut`

```python
class Shortcut
```

Lanza `activate` al pulsar una de sus `keys` (`"ctrl-s"`, `"Ctrl+S"`, varias separadas por comas; `mod-` es Cmd en macOS y Ctrl en el resto). Llama a `handle(combo)` desde `on_key`.

## Archivos y programas

### `FileWatcher`

```python
class FileWatcher
```

Vigila una carpeta o un archivo y lanza `created`, `modified` y `deleted` (una ruta) y `change` (las rutas cambiadas), revisando cada `interval` milisegundos. `start()`, `stop()`, `running`.

### `Process`

```python
class Process
```

Ejecuta un programa y lanza `output` y `error_output` por cada línea que imprime, `finished` con su código de salida, `started` y `failed`. `start()`, `write()`, `kill()`, `wait()`.

### `Worker`

```python
class Worker
```

Ejecuta `work(value)` en un hilo aparte con `run(value)`; `report()` lanza `progress`, el resultado llega en `done` y una excepción en `failed`. `cancel()` activa `cancelled`.

## Red

### `HttpRequest`

```python
class HttpRequest
```

Llama a una dirección web en segundo plano: `send()` lanza `response` con un `HttpResponse` (también con estados de error) o `failed` si no hubo respuesta. `json=` envía JSON.

### `HttpResponse`

```python
@dataclass
class HttpResponse(status, content=b'', headers={}, url='')
```

La respuesta de un servidor web: `status`, `ok`, `headers`, `content` (bytes), `text` y `json()`.

## Sistema

### `Clipboard`

```python
class Clipboard
```

El portapapeles del sistema: `copy(text)` y `paste()` devuelven comandos; con `watch=True` lanza `change` cuando se copia algo nuevo.

### `Settings`

```python
class Settings
```

Valores que se guardan entre ejecuciones: un diccionario guardado como JSON en la carpeta de ajustes del usuario en cada cambio, con `defaults`; lanza `change` con `(clave, valor)`.

### `FileDialog`

```python
class FileDialog
```

El diálogo de archivos del sistema: `show()` devuelve el comando que lo abre en el modo `"open"`, `"open_many"`, `"save"` o `"folder"`; lanza `chosen` o `cancelled`.

### `Notification`

```python
class Notification
```

Una notificación de escritorio: `show(text)` la muestra y devuelve si pudo; lanza `shown` o `failed`.
