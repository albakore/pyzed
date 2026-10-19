---
title: "App y ejecución"
description: "La clase App, run, screenshot, post y load_font."
sidebar:
  order: 1
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs_es.py. -->

            Todo lo que necesitas para arrancar una aplicación. Ver también la guía de
            [arquitectura](/pyzed/es/guides/architecture/).
        

Ver también [varias ventanas](/pyzed/es/guides/windows/) y [async y suscripciones](/pyzed/es/guides/async/).

## Aplicación

### `App`

Clase base de las aplicaciones (arquitectura Elm, como Iced). Es también la **ventana
principal**, así que hereda todo lo de [`Window`](#window). Sobrescribe `view()` y, si usas
mensajes, `update(message)`. El estado vive en atributos de la instancia.

| Atributo de clase | Por defecto | Descripción |
| --- | --- | --- |
| `title` | `"Pyzed"` | Título de la ventana. Puede ser un callable (o propiedad) que devuelva el texto. |
| `size` | `(1280, 800)` | Tamaño inicial de la ventana. |
| `font_size` | `14` | Tamaño de texto por defecto. |
| `theme` | `themes.ONE_DARK` | Un `Theme`, el nombre de un tema registrado o `themes.auto(claro, oscuro)`. Cámbialo en cualquier momento. |
| `system_dark` | `True` | Si el sistema está en modo oscuro (lo actualiza el runtime). |

El resto de opciones de ventana (`min_size`, `resizable`, `decorations`, `scale`…) están en `Window`.

| Método | Descripción |
| --- | --- |
| `view()` | Devuelve el árbol de widgets. Se llama después de cada mensaje. |
| `update(message)` | Recibe los mensajes. Puede devolver un `Command`, una lista de ellos, una corrutina, un generador (normal o async) u otro mensaje. |
| `on_start()` | Opcional. Se ejecuta una vez al arrancar; puede devolver un `Command` o una corrutina. |
| `on_key(combo)` | Opcional. Recibe cada tecla como `"ctrl-shift-p"`, `"escape"`, `"up"`… |
| `subscriptions()` | Opcional. Devuelve las suscripciones activas (`pz.every`, `pz.listen`). Se reevalúa tras cada `update`. |
| `resolved_theme()` | El `Theme` concreto en uso (resuelve nombres y `themes.auto`). |
| `run()` | Abre la ventana y bloquea hasta que la app termina. |
| `screenshot(path, *, size=None, scale=2.0, wait=0.1)` | Renderiza el estado actual a un PNG sin ventana. |

Si `view()` lanza una excepción, la ventana muestra el traceback en lugar de cerrarse.

### `run`

```python
run(app, *, reload=None, watch=())
```

Ejecuta una app: abre la ventana y bloquea hasta que se cierra. Acepta la clase o una instancia.

| Parámetro | Descripción |
| --- | --- |
| `app` | Una instancia de `App` (o la clase, que se instancia sin argumentos). |
| `reload` | Hot reload: al guardar un archivo del proyecto se actualiza la ventana sin perder el estado. `None` sigue a `PYZED_RELOAD` (lo define `pyzed dev`). |
| `watch` | Carpetas o archivos extra a vigilar para el hot reload. |

### `screenshot`

```python
screenshot(app, path, *, size=None, scale=2.0, wait=0.1)
```

Renderiza `app` fuera de pantalla (sin ventana ni GPU) y guarda un PNG. Útil para tests y documentación.

| Parámetro | Descripción |
| --- | --- |
| `app` | Una instancia de `App` (o la clase, que se instancia sin argumentos). |
| `path` | Ruta del PNG de salida. |
| `size` | Tamaño lógico `(ancho, alto)`. Por defecto, `app.size`. |
| `scale` | Factor de escala del PNG (2.0 = retina). |
| `wait` | Segundos que se esperan antes de capturar (para tareas de `on_start`). |

```python
pz.screenshot(MiApp, "docs/ui.png", size=(800, 600))
```

### `post`

```python
post(message)
```

Envía un mensaje a la app en ejecución desde **cualquier hilo**. Lanza `RuntimeError` si no hay ninguna app corriendo.

| Parámetro | Descripción |
| --- | --- |
| `message` | Cualquier valor de Python, o un callable. |

```python
def worker():
    for i in range(100):
        time.sleep(0.05)
        pz.post(("progress", i / 100))

threading.Thread(target=worker, daemon=True).start()
```

### `load_font`

```python
load_font(source)
```

Carga una fuente extra (ruta a un `.ttf`/`.otf` o sus bytes) para usarla por su nombre de familia: `text("hola", font="JetBrains Mono")`.

| Parámetro | Descripción |
| --- | --- |
| `source` | Ruta del archivo de fuente o `bytes`. |

## Ventanas

### `Window`

Una ventana extra con su propio `view()`, título, tamaño y tema. Se abre devolviendo
`ventana.open()` (o `Command.open_window(ventana)`). Dentro, `self.app` es la app, así que las
ventanas comparten estado; los mensajes que produce van a su `update()`, que por defecto los
reenvía a `app.update()`.

| Atributo | Por defecto | Descripción |
| --- | --- | --- |
| `title` | `"Pyzed"` | Texto o callable. |
| `size` | `(800, 600)` | Tamaño inicial. |
| `min_size`, `max_size` | `None` | Límites de tamaño. |
| `position` | `None` | `"center"` o `(x, y)`. |
| `resizable` | `True` | Si se puede redimensionar. |
| `decorations` | `True` | `False` quita el marco del sistema (barra de título propia con `drag()`). |
| `transparent`, `maximized`, `fullscreen` | `False` | Estado inicial. |
| `scale` | `1.0` | Escala de la interfaz. |
| `theme` | `None` | Tema propio; `None` usa el de la app. |
| `app` | — | La app dueña de la ventana (se asigna al abrirla). |
| `window_size` | — | Tamaño actual en píxeles lógicos (lo actualiza el runtime). |

| Método | Descripción |
| --- | --- |
| `view()` | Obligatorio. Devuelve el árbol de widgets de la ventana. |
| `update(message)` | Recibe los mensajes de la ventana (por defecto los reenvía a la app). |
| `open()` / `close()` / `drag()` | Comandos para abrirla, cerrarla o empezar a moverla. |
| `is_open` | Si está abierta. |
| `resolved_theme()` | El `Theme` concreto que usa. |
| `on_open()` | Al abrirse. |
| `on_close()` | Cuando el usuario pide cerrarla; devuelve `False` para impedirlo. |
| `on_resize(width, height)` | Al cambiar de tamaño. |
| `on_key(combo)`, `subscriptions()` | Como en `App`. |

## Async y suscripciones

### `every`

```python
every(seconds, message, *, key=None)
```

Una suscripción que envía `message` a `update` cada `seconds` segundos (como `time::every` de Iced). Si `message` es un callable, se llama. Devuélvela desde `subscriptions()`.

| Parámetro | Descripción |
| --- | --- |
| `seconds` | Intervalo en segundos (mayor que 0). |
| `message` | Cualquier valor de Python, o un callable. |
| `key` | Clave que identifica la suscripción (por defecto, el mensaje o la función). |

```python
def subscriptions(self):
    return [pz.every(1, "tick")] if self.running else []
```

### `listen`

```python
listen(function, *, key=None)
```

Una suscripción que ejecuta `function()` (un generador o generador async) mientras esté activa y envía cada valor que produce a `update`. Ideal para websockets y streams.

| Parámetro | Descripción |
| --- | --- |
| `function` | Función generadora (normal o `async def`). |
| `key` | Clave que identifica la suscripción (por defecto, el mensaje o la función). |

```python
async def feed():
    async for message in websocket:
        yield message

def subscriptions(self):
    return [pz.listen(feed)]
```

### `Subscription`

Lo que devuelven `every` y `listen`. Se identifica por su `key`: mientras `subscriptions()` siga devolviendo una con la misma clave, sigue en marcha; cuando desaparece, se detiene.

### `spawn`

```python
spawn(awaitable)
```

Programa una corrutina en el loop de asyncio de Pyzed sin esperar su resultado y devuelve un `concurrent.futures.Future`. Para recibir el resultado en la interfaz, devuelve la corrutina desde `update` o usa `Command.perform`.

| Parámetro | Descripción |
| --- | --- |
| `awaitable` | La corrutina. |

### `asyncio_loop`

```python
asyncio_loop()
```

El loop de asyncio (en un hilo en segundo plano) donde Pyzed ejecuta todas las corrutinas. Se arranca al usarlo por primera vez.

## Eventos y componentes

### `on`

```python
on(widget, *, cursor=None, **handlers)
```

Añade handlers de eventos comunes a un widget; igual que `widget.on(...)`. Eventos: `click`, `double_click`, `right_click`, `middle_click`, `mouse_down`, `mouse_up`, `mouse_enter`, `mouse_leave`, `mouse_move`, `scroll`, `drag_start`, `drag`, `drag_end`, `focus`, `blur`, `key_down`, `key_up`, `resize`. Ver [Eventos](/pyzed/es/guides/events/).

| Parámetro | Descripción |
| --- | --- |
| `widget` | El widget (un texto se envuelve en un container). |
| `cursor` | Cursor del ratón sobre el widget, como `"pointer"` o `"grab"`. |
| `handlers` | Pares `evento=handler`. Un handler con un argumento recibe un `pz.Event`; un valor no invocable es un mensaje para `update`; `None` lo quita. |

```python
pz.container(tarjeta, padding=12).on(click=self.seleccionar, drag=lambda e: self.mover(e.dx, e.dy))
```

### `Event`

```python
class Event
```

Lo que pasó, se le pasa a los handlers: `type`, `x`, `y` (relativos al widget), `dx`, `dy` (scroll o movimiento del arrastre), `width`, `height`, `button`, `key`, `shift`, `ctrl`, `alt`, `logo`, y `value`/`source` en eventos propios.

| Parámetro | Descripción |
| --- | --- |
| `type` | Nombre del evento. |
| `x` | X del puntero, relativa al widget. |
| `y` | Y del puntero, relativa al widget. |
| `dx` | Scroll horizontal (líneas) o movimiento del arrastre. |
| `dy` | Scroll vertical (líneas) o movimiento del arrastre. |
| `width` | Ancho del widget. |
| `height` | Alto del widget. |
| `button` | `"left"`, `"right"`, `"middle"`... |
| `key` | Combinación de teclas, como `"ctrl-s"`. |
| `shift` | Shift pulsado. |
| `ctrl` | Control pulsado. |
| `alt` | Alt pulsado. |
| `logo` | Tecla Cmd/Windows pulsada. |
| `value` | Valor de un evento propio. |
| `source` | Componente que lo emitió. |

### `Dock`

```python
class Dock
```

Un espacio de trabajo como el de Zed: un `center` con `pz.DockPanel` acoplados a la izquierda, derecha, abajo o arriba. El usuario cambia el tamaño de un lado arrastrando su borde interior y mueve un panel arrastrando su pestaña a una zona de destino (o desde el menú del clic derecho de la pestaña). `on_layout` recibe la disposición como un dict para guardarla; pásala de vuelta en `layout=`. Ver [Layout](/pyzed/es/guides/layout/#paneles-acoplables-y-redimensionables).

| Parámetro | Descripción |
| --- | --- |
| `args` | Props por posición: `center`, `panels`, `layout`. |
| `key` | Clave que identifica la suscripción (por defecto, el mensaje o la función). |
| `kwargs` | Props y handlers por nombre, además de `key=`. |

```python
pz.Dock(center=editor, panels=[
    pz.DockPanel("project", "Proyecto", arbol, icon="folder", side="left"),
    pz.DockPanel("terminal", "Terminal", terminal, icon="terminal", side="bottom"),
], layout=self.disposicion, on_layout=lambda e: setattr(self, "disposicion", e.value))
```

### `DockPanel`

```python
class DockPanel
```

Un panel para `pz.Dock`.

| Parámetro | Descripción |
| --- | --- |
| `id` | Id estable (se usa en la disposición guardada). |
| `title` | Título de la pestaña. |
| `content` | El widget del panel. |
| `icon` | Icono de Lucide para la pestaña. |
| `side` | Lado inicial: `"left"`, `"right"`, `"bottom"` o `"top"`. |

### `Component`

```python
class Component
```

Clase base de los componentes propios, como en React: los atributos de clase anotados son props, los demás atributos son estado que se conserva entre renders, `render()` devuelve widgets y `events` declara eventos propios que se lanzan con `self.emit(nombre, valor)`. Llamar a la clase devuelve un widget. Aparecen en la biblioteca del diseñador. Ver [Componentes propios](/pyzed/es/guides/components/).

| Parámetro | Descripción |
| --- | --- |
| `args` | Props, en el orden en que se declaran. |
| `key` | Clave que identifica la suscripción (por defecto, el mensaje o la función). |
| `kwargs` | Props por nombre, handlers `on_<evento>=` (propios, de ciclo de vida o comunes) y `key=` para conservar el estado cuando los elementos se mueven. |

```python
class Rating(pz.Component):
    value: int = 0
    events = {"change": "Se eligió una estrella."}

    def render(self):
        return pz.row([pz.text("★").on(click=lambda i=i: self.emit("change", i)) for i in range(1, 6)])

Rating(value=3, on_change=lambda e: print(e.value))
```
