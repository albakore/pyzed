---
title: "App y ejecución"
description: "Referencia de la API de pyzed.App: la clase de aplicación, run, screenshot, post, load_font y las opciones de ventana de una app de escritorio."
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
| `style` | `None` | El estilo global: un `pz.Style` para toda la ventana. Su color de texto, tamaño, fondo, color de borde y radio se vuelven tokens del tema. Ver [Estilos](/pyzed/es/theming/styles/#el-estilo-global). |
| `system_dark` | `True` | Si el sistema está en modo oscuro (lo actualiza el runtime). |
| `tab_focus` | `True` | Tab y Shift+Tab mueven el foco entre los campos de la ventana. Ver [Accesibilidad](/pyzed/es/guides/accessibility/). |
| `splash` | `None` | Una ventana [`Splash`](#splash) que se muestra antes de abrir la ventana principal. |
| `rendering` | `None` | Un [`Rendering`](#rendering): GPU o CPU, API gráfica, GPU y vsync. `None` lee `[tool.pyzed.rendering]` del `pyproject.toml` del proyecto. |

El resto de opciones de ventana (`min_size`, `resizable`, `decorations`, `icon`, `scale`…) están en `Window`.

| Método | Descripción |
| --- | --- |
| `view()` | Devuelve el árbol de widgets. Se llama después de cada mensaje. |
| `update(message)` | Recibe los mensajes. Puede devolver un `Command`, una lista de ellos, una corrutina, un generador (normal o async) u otro mensaje. |
| `on_start()` | Opcional. Se ejecuta una vez al arrancar; puede devolver un `Command` o una corrutina. |
| `on_key(combo)` | Opcional. Recibe cada tecla como `"ctrl-shift-p"`, `"escape"`, `"up"`… |
| `on_key_up(key)` | Opcional. Recibe las teclas al soltarlas, por nombre (`"left"`, `"space"`). |
| `subscriptions()` | Opcional. Devuelve las suscripciones activas (`pz.every`, `pz.listen`). Se reevalúa tras cada `update`. |
| `resolved_theme()` | El `Theme` concreto en uso (resuelve nombres y `themes.auto`). |
| `run()` | Abre la ventana y bloquea hasta que la app termina. |
| `screenshot(path, *, size=None, scale=2.0, wait=0.1)` | Renderiza el estado actual a un PNG sin ventana. |

Si `view()` lanza una excepción, la ventana muestra el traceback en lugar de cerrarse.

**Métodos y propiedades**

#### `App.subscriptions`

```python
App.subscriptions()
```

Temporizadores y streams que deben estar activos ahora mismo (se reevalúa tras cada update).

#### `App.run`

```python
App.run(*, reload=None, watch=())
```

Abre la ventana y bloquea hasta que la app termina.

#### `App.screenshot`

```python
App.screenshot(path, *, size=None, scale=2.0, wait=0.1)
```

Renderiza el estado actual fuera de pantalla (sin GPU ni display) en un PNG.

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

### `UNCHANGED`

```python
UNCHANGED(...)
```

Devuélvelo desde un callback que no cambió nada en pantalla (un movimiento del puntero que solo guardas, un cambio de foco): la ventana no se reconstruye. Cualquier otro valor redibuja como siempre. Ver la [guía de rendimiento](/pyzed/es/guides/performance/).

```python
def pointer_moved(self, x, y):
    self.pointer = (x, y)
    return pz.UNCHANGED  # no cambió nada visible: no se reconstruye
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
| `style` | `None` | Estilo global propio; `None` usa el de la app. |
| `icon` | `None` | El icono de la ventana (barra de título, barra de tareas): una ruta a una imagen o sus bytes. Fíjalo en `pz.Window` para dar el mismo a todas las ventanas. Ver [Iconos y metadatos](/pyzed/es/packaging/icons-metadata/#el-icono-de-la-ventana). |
| `app_id` | `None` | Linux: el id de la app que el escritorio empareja con un archivo `.desktop` (`com.acme.shop`). |
| `app` | — | La app dueña de la ventana (se asigna al abrirla). |
| `window_size` | — | Tamaño actual en píxeles lógicos (lo actualiza el runtime). |
| `window_position` | — | Dónde está la ventana en la pantalla, su esquina superior izquierda exterior (lo actualiza el runtime; `None` en Wayland). |

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
| `on_file_hover(path)`, `on_file_drop(path)`, `on_file_leave()` | Archivos arrastrados desde el sistema sobre la ventana, soltados en ella (una vez por archivo) o retirados. Por defecto van a la `ui.DropZone` donde caen. |

**Métodos y propiedades**

#### `Window.view`

```python
Window.view()
```

Devuelve el widget raíz de la ventana; las subclases deben sobrescribirlo.

#### `Window.update`

```python
Window.update(message)
```

Gestiona un mensaje producido en esta ventana (por defecto lo reenvía a la app).

#### `Window.on_close`

```python
Window.on_close()
```

Se llama cuando el usuario pide cerrar la ventana. Devuelve `False` para mantenerla abierta.

#### `Window.on_file_hover`

```python
Window.on_file_hover(path)
```

Un archivo arrastrado desde el sistema está sobre la ventana: ilumina la `ui.DropZone` donde caería.

#### `Window.on_file_drop`

```python
Window.on_file_drop(path)
```

Se soltó un archivo del sistema en la ventana (una vez por archivo): va a una `ui.DropZone`.

#### `Window.on_file_leave`

```python
Window.on_file_leave()
```

Los archivos arrastrados sobre la ventana salieron sin soltarse.

#### `Window.is_open`

```python
Window.is_open  # property
```

Si la ventana está abierta ahora.

#### `Window.open`

```python
Window.open()
```

Un comando que abre esta ventana: `return settings.open()`.

#### `Window.close`

```python
Window.close()
```

Un comando que cierra esta ventana: `on_press=self.close`.

#### `Window.drag`

```python
Window.drag()
```

Un comando que empieza a mover la ventana (para barras de título propias).

#### `Window.minimize`

```python
Window.minimize()
```

Un comando que minimiza la ventana.

#### `Window.toggle_maximize`

```python
Window.toggle_maximize()
```

Un comando que maximiza la ventana, o la restaura si está maximizada.

#### `Window.frame_menus`

```python
Window.frame_menus()
```

Los menús a la izquierda de la barra de título de un marco propio (`frame = "custom"`): una lista de `ui.Menu`.

#### `Window.resolved_theme`

```python
Window.resolved_theme()
```

El tema concreto que usa ahora esta ventana (con los colores y tamaños de su estilo global).

#### `Window.resolved_style`

```python
Window.resolved_style()
```

El estilo global de esta ventana: `pz.set_style` con su propio `style` (o el de la app) encima.

### `Splash`

```python
class Splash
```

Una pantalla de inicio: una ventana sin marco con una imagen, centrada en la pantalla, que se muestra mientras arranca la app. Dásela a `App.splash`; se queda al menos `duration` segundos, luego se abre la ventana principal y la pantalla se cierra. Ver [Pantalla de inicio](/pyzed/es/packaging/build/#pantalla-de-inicio).

| Parámetro | Descripción |
| --- | --- |
| `image` | Ruta a la imagen (PNG, JPEG...) o sus bytes. |
| `duration` | Segundos que se queda, como mínimo. |
| `size` | Tamaño de la ventana; por defecto, el de la imagen, reducido para caber en 900 × 600. |
| `text` | Texto escrito sobre la parte inferior de la imagen (por ejemplo `"Cargando…"`). |
| `color` | Color del texto. |
| `background` | Color detrás de la imagen (para imágenes con transparencia). |
| `title` | Título de la ventana (lo muestra la barra de tareas). |
| `icon` | Icono de la ventana. |

```python
class Shop(pz.App):
    splash = pz.Splash("assets/splash.png", duration=1.5, text="Cargando…")
```

### `Rendering`

```python
@dataclass
class Rendering(renderer='auto', gpu_api='auto', power='auto', vsync='auto')
```

Cómo dibuja la app sus ventanas: en la GPU o en la CPU, con qué API gráfica, qué GPU y vsync. Cada campo es `"auto"` por defecto (decide Pyzed). Dásela a `App.rendering`, o pon las mismas claves en `[tool.pyzed.rendering]` del `pyproject.toml` del proyecto, que leen `pz.run`, el diseñador y `pyzed build`. Ver [Renderizado](/pyzed/es/editor/settings/#renderizado).

| Parámetro | Descripción |
| --- | --- |
| `renderer` | `"auto"`, `"gpu"` (la necesitan los shaders) o `"cpu"` (tiny-skia: arranca antes, menos memoria, funciona en todas partes). |
| `gpu_api` | `"auto"`, `"vulkan"`, `"metal"`, `"dx12"` o `"gl"`. |
| `power` | `"auto"`, `"high"` (la GPU dedicada) o `"low"` (la integrada, ahorra batería). |
| `vsync` | `"auto"`, `"on"` (sin cortes) u `"off"` (dibuja lo más rápido posible). |

```python
class Game(pz.App):
    rendering = pz.Rendering(renderer="gpu", vsync="off")
```

**Métodos y propiedades**

#### `Rendering.from_table`

```python
@classmethod
Rendering.from_table(table)
```

Crea los ajustes a partir de una tabla `[tool.pyzed.rendering]`, ignorando claves y valores desconocidos.

#### `Rendering.to_table`

```python
Rendering.to_table()
```

Los ajustes que no son `"auto"`, tal como se escriben en `pyproject.toml`.

#### `Rendering.custom`

```python
Rendering.custom  # property
```

Si algún ajuste no es `"auto"`.

#### `Rendering.env`

```python
Rendering.env()
```

Las variables de entorno que llevan estos ajustes a Iced y wgpu.

#### `Rendering.apply`

```python
Rendering.apply(environ=None)
```

Define las variables de `env()` que aún no están definidas (las tuyas mandan); devuelve las que definió.

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

### `frames`

```python
frames(callback, *, key=None, max_fps=240.0)
```

Una suscripción que llama a `callback(dt)` una vez por fotograma (sincronizada con la pantalla, normalmente 60 veces por segundo), con `dt` los segundos desde el fotograma anterior (como mucho 0,25). Pensada para juegos y simulaciones: mueve las cosas `velocidad * dt`. Ver [Crear videojuegos](/pyzed/es/games/).

| Parámetro | Descripción |
| --- | --- |
| `callback` | Callable que recibe `dt` (un `float`). |
| `key` | Clave que identifica la suscripción (por defecto, el mensaje o la función). |
| `max_fps` | Tasa máxima donde la pantalla no espera a la sincronización vertical (renderizado por software). 240 por defecto. |

```python
def subscriptions(self):
    return [] if self.paused else [pz.frames(self.tick)]

def tick(self, dt):
    self.x += game.axis("left", "right") * 300 * dt
```

### `pressed`

```python
pressed()
```

Las teclas pulsadas ahora mismo, como un `frozenset` de nombres sin modificadores (`"left"`, `"space"`, `"a"`…). Vacío si no hay ventana abierta. Consúltalo en cada fotograma para movimiento continuo; `on_key` es para pulsaciones puntuales.

### `is_pressed`

```python
is_pressed(*keys, held=None)
```

Si alguna de `keys` está pulsada. `held` sustituye a `pressed()` (útil en tests).

| Parámetro | Descripción |
| --- | --- |
| `keys` | Nombres de teclas, como `"left"`, `"a"`. |
| `held` | Conjunto opcional de teclas en lugar de `pressed()`. |

```python
if pz.is_pressed("space") and self.cooldown <= 0:
    self.fire()
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

Lo que pasó, se le pasa a los handlers: `type`, `x`, `y` (relativos al widget), `dx`, `dy` (scroll o movimiento del arrastre), `width`, `height`, `button`, `key`, `shift`, `ctrl`, `alt`, `logo`, `window_x`, `window_y`, `screen_x`, `screen_y` (el puntero en la ventana y en la pantalla), y `value`/`source` en eventos propios.

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
| `window_x` | X del puntero en la ventana (fuera de ella si un arrastre se suelta fuera). |
| `window_y` | Y del puntero en la ventana. |
| `screen_x` | X del puntero en la pantalla, o `None` donde la plataforma no dice dónde están las ventanas (Wayland). `event.screen` da `(screen_x, screen_y)`. |
| `screen_y` | Y del puntero en la pantalla, o `None`. |

**Métodos y propiedades**

#### `Event.position`

```python
Event.position  # property
```

`(x, y)`.

#### `Event.size`

```python
Event.size  # property
```

`(width, height)`.

#### `Event.screen`

```python
Event.screen  # property
```

`(screen_x, screen_y)`, o `None` cuando la plataforma no informa de dónde están las ventanas.

### `Dock`

```python
class Dock
```

Un espacio de trabajo estilo editor: un `center` con `pz.DockPanel` acoplados a la izquierda, derecha, abajo o arriba. El usuario cambia el tamaño de un lado arrastrando su borde interior y mueve un panel arrastrando su pestaña a una zona de destino (o desde el menú del clic derecho de la pestaña). `on_layout` recibe la disposición como un dict para guardarla; pásala de vuelta en `layout=`. Ver [Layout](/pyzed/es/guides/layout/#paneles-acoplables-y-redimensionables).

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

**Métodos y propiedades**

#### `Dock.side_of`

```python
Dock.side_of(panel)
```

Devuelve el lado en que está acoplado un panel: su posición guardada si es válida, si no `panel.side`.

#### `Dock.groups`

```python
Dock.groups()
```

Devuelve los paneles agrupados por lado (están todos los lados, quizá con una lista vacía).

#### `Dock.snapshot`

```python
Dock.snapshot()
```

Devuelve la disposición como un dict simple (`positions`, `sizes`, `active`, `hidden`).

#### `Dock.changed`

```python
Dock.changed()
```

Emite `layout` con la instantánea actual.

#### `Dock.move`

```python
Dock.move(panel_id, side)
```

Acopla un panel en otro lado y lo hace la pestaña activa allí.

#### `Dock.select`

```python
Dock.select(side, panel_id)
```

Hace de `panel_id` la pestaña activa en `side` (un clic en la pestaña) y emite `layout`.

#### `Dock.toggle`

```python
Dock.toggle(side)
```

Muestra u oculta un lado entero.

#### `Dock.resized`

```python
Dock.resized(side, size)
```

Guarda el nuevo `size` (en píxeles) de `side` tras arrastrar su borde y emite `layout`.

#### `Dock.start_drag`

```python
Dock.start_drag(panel_id)
```

Empieza a arrastrar la pestaña de un panel: aparecen las zonas de soltar y se cierra el menú de la pestaña.

#### `Dock.end_drag`

```python
Dock.end_drag()
```

Termina el arrastre de una pestaña y oculta las zonas de soltar, recordando el panel para un `drop` tardío.

#### `Dock.drop`

```python
Dock.drop(side)
```

Mueve el panel arrastrado a `side` al soltarlo en esa zona; no hace nada si no hay ninguno.

#### `Dock.tab`

```python
Dock.tab(panel, side, active, t)
```

Construye la pestaña de un panel en la cabecera de un lado.

#### `Dock.move_menu`

```python
Dock.move_menu(panel, side, t)
```

Construye el menú contextual que mueve `panel` a cualquier lado distinto de `side`.

#### `Dock.side_view`

```python
Dock.side_view(side, panels, t)
```

Construye un lado: una cabecera con las pestañas de los paneles sobre el contenido del panel activo.

#### `Dock.drop_zones`

```python
Dock.drop_zones(t)
```

Construye las cuatro zonas de soltar (una por lado) que se muestran sobre el dock mientras se arrastra una pestaña.

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
| `args` | Props, en el orden en que se declaran (o los hijos, si la clase tiene una prop `children`). |
| `key` | Clave que identifica la suscripción (por defecto, el mensaje o la función). |
| `kwargs` | Props por nombre, handlers `on_<evento>=` (propios, de ciclo de vida o comunes), `key=` para conservar el estado cuando los elementos se mueven, y `style=`, `class_=`, `id=` y `animate=`. |

```python
class Rating(pz.Component):
    value: int = 0
    events = {"change": "Se eligió una estrella."}

    def render(self):
        return pz.row([pz.text("★").on(click=lambda i=i: self.emit("change", i)) for i in range(1, 6)])

Rating(value=3, on_change=lambda e: print(e.value))
```

**Métodos y propiedades**

#### `Component.refresh`

```python
Component.refresh()
```

Vuelve a dibujar el componente en el próximo `view()`, aunque sus props y su estado sean los mismos.

#### `Component.create`

```python
@classmethod
Component.create(*args, **kwargs)
```

Una instancia suelta (sin renderizar ni ciclo de vida), útil en tests: `c.render()`.

#### `Component.setup`

```python
Component.setup()
```

Se llama una vez antes del primer render (las props ya están puestas): inicializa aquí el estado.

#### `Component.render`

```python
Component.render()
```

Devuelve los widgets de este componente (se llama en cada render).

#### `Component.provide`

```python
Component.provide()
```

Valores que comparte con todos los componentes que dibuja (se leen con `pz.use_context`).

#### `Component.context`

```python
Component.context(name, default=None)
```

El valor compartido más cercano llamado `name` (ver `pz.provide`).

#### `Component.on_mount`

```python
Component.on_mount()
```

Se llama tras el primer render; puede devolver un `Command` o un mensaje.

#### `Component.on_unmount`

```python
Component.on_unmount()
```

Se llama cuando el componente deja de renderizarse.

#### `Component.emit`

```python
Component.emit(name, value=None)
```

Lanza el evento personalizado `name`: llama al handler que el padre pasó como `on_<name>`.

#### `Component.handles`

```python
Component.handles(name)
```

Si el padre pasó un handler para el evento personalizado `name`.

#### `Component.describe`

```python
@classmethod
Component.describe()
```

El primer párrafo del docstring (se muestra en el diseñador).

#### `Component.designer_spec`

```python
@classmethod
Component.designer_spec()
```

Este componente como entrada de la caja de herramientas del diseñador (`pyzed.designer.Component`).

### `Color`

```python
class Color
```

Anotación para un prop de componente que guarda un color (un token del tema o `"#rrggbb"`): el diseñador muestra un selector de color. En ejecución es un `str` normal.

```python
tint: pz.Color = "accent"
```

### `Icon`

```python
class Icon
```

Anotación para un prop de componente que guarda el nombre de un icono de Lucide: el diseñador muestra un selector de icono. En ejecución es un `str` normal.

```python
mark: pz.Icon = "star"
```

### `Multiline`

```python
class Multiline
```

Anotación para un prop de componente con texto largo: el diseñador muestra un área de texto. En ejecución es un `str` normal.

```python
notes: pz.Multiline = ""
```

### `FilePath`

```python
class FilePath
```

Anotación para un prop de componente con la ruta de un archivo: el diseñador muestra la ruta con un botón que abre el diálogo de archivos del sistema (una anotación `pathlib.Path` hace lo mismo). En ejecución es un `str` normal.

```python
logo: pz.FilePath = ""
```

### `FolderPath`

```python
class FolderPath
```

Anotación para un prop de componente con una carpeta: el diseñador muestra la ruta con un botón que abre el diálogo de carpetas del sistema. En ejecución es un `str` normal.

```python
output: pz.FolderPath = ""
```

### `Range`

```python
@dataclass
class Range(min, max, step=1)
```

Límites de un prop numérico, con `typing.Annotated`: el diseñador muestra un campo numérico limitado a ellos. Ver [Componentes propios](/pyzed/es/guides/components/#en-el-diseñador).

| Parámetro | Descripción |
| --- | --- |
| `min` | Valor mínimo. |
| `max` | Valor máximo. |
| `step` | Paso de los botones + y -. |

```python
level: Annotated[int, pz.Range(0, 10)] = 3
```

### `provide`

```python
provide(**values)
```

Un gestor de contexto que comparte valores con todos los componentes que se dibujan dentro, como el contexto de React. Se leen con `pz.use_context(nombre)` o `self.context(nombre)`. El método `provide()` de un componente hace lo mismo con lo que dibuja. Ver [Hijos, contexto y estilos](/pyzed/es/guides/components/#hijos-contexto-y-estilos).

| Parámetro | Descripción |
| --- | --- |
| `values` | Los valores, por nombre. |

```python
with pz.provide(user=self.user):
    page = Dashboard()
```

### `use_context`

```python
use_context(name, default=None)
```

El valor más cercano compartido como `name` con `pz.provide` o el `provide()` de un componente.

| Parámetro | Descripción |
| --- | --- |
| `name` | El nombre del valor. |
| `default` | Lo que devuelve si nadie lo comparte. |

### `state`

```python
state(default=None, *, doc='')
```

Declara una variable de estado privada en la clase de un componente: el padre no puede pasarla y cada instancia empieza con su propia copia del valor (listas y diccionarios son seguros). El diseñador la muestra junto a las props. Ver [Componentes propios](/pyzed/es/guides/components/).

| Parámetro | Descripción |
| --- | --- |
| `default` | Valor inicial, copiado para cada instancia. |
| `doc` | Descripción que muestra el diseñador. |

```python
class Counter(pz.Component):
    step: int = 1
    count: int = pz.state(0)
```

### `State`

```python
class State
```

El valor por defecto de una variable de estado declarada en la clase (ver `state`).

### `StateInfo`

```python
class StateInfo
```

Una variable de estado declarada con `pz.state`: su nombre, anotación, valor por defecto y descripción.

### `PropInfo`

```python
class PropInfo
```

Una prop: su nombre, anotación de tipo (puede ser un texto) y valor por defecto.

**Métodos y propiedades**

#### `PropInfo.required`

```python
PropInfo.required  # property
```

Si la prop no tiene valor por defecto y hay que pasarla.

### `find`

```python
find(type_name)
```

La clase de componente registrada como `type_name` (ver `Component.type_name`).

### `registered`

```python
registered()
```

Todas las subclases de `Component` definidas hasta ahora que deben aparecer en el diseñador.

### `render_pass`

```python
render_pass(owner)
```

Registra los componentes renderizados mientras `owner` (una ventana) ejecuta su `view()`.

Los componentes que no se vuelven a renderizar se desmontan al final. El runtime lo hace
en cada ventana; úsalo tú solo para renderizar componentes fuera de una ventana.

### `EventInfo`

```python
class EventInfo
```

La documentación de un evento: su grupo y qué informa.

### `accepts_argument`

```python
accepts_argument(handler)
```

Si `handler` recibe el evento: tiene un parámetro posicional obligatorio o `*args`.

Los parámetros con valor por defecto no cuentan, así que `lambda i=i: ...` se llama sin nada.
La respuesta se guarda en caché por función.

### `LIFECYCLE_EVENTS`

Los nombres de los eventos de ciclo de vida que lanza todo componente (`mount`, `unmount`...).

### `CATALOG`

Todos los nombres de evento que conoce Pyzed, con su `EventInfo` (qué lo lanza y qué contiene `event.value`).

### `COMMON`

Los eventos que acepta todo widget con `widget.on(...)` (clic, hover, foco, teclas...).

## Hot reload

### `enable`

```python
enable(app, paths=(), *, interval=0.25)
```

Inicia el hot reload para `app` (una instancia de `App` en marcha) y devuelve el reloader.

### `current`

```python
current()
```

El `Reloader` activo, o `None` cuando el hot reload está apagado.

### `is_reloading`

```python
is_reloading()
```

`True` mientras una recarga vuelve a ejecutar los módulos.

### `enabled_by_env`

```python
enabled_by_env()
```

Si `PYZED_RELOAD` pide hot reload (`1`, `true`, `yes` u `on`).

### `Reloader`

```python
class Reloader
```

Vigila los archivos del proyecto y recarga el código modificado en una app en marcha.

`app` es la instancia de `App` en marcha. `paths` son carpetas o archivos extra que
vigilar; por defecto se vigila la carpeta del módulo que define la clase de la app.
`interval` es cada cuántos segundos se comprueba si hay cambios.

La mayoría de los programas nunca crean uno a mano: lo hace `pz.run(app, reload=True)`.

**Métodos y propiedades**

#### `Reloader.watch`

```python
Reloader.watch(path, callback)
```

Llama a `callback(path)` en el hilo de la UI cada vez que cambia `path`.

#### `Reloader.project_modules`

```python
Reloader.project_modules()
```

Los módulos cargados cuyos archivos pertenecen al proyecto, por ruta de archivo.

#### `Reloader.scan`

```python
Reloader.scan()
```

Revisa una vez cada archivo vigilado y devuelve los que cambiaron.

#### `Reloader.start`

```python
Reloader.start()
```

Arranca el hilo vigilante y hace de este el reloader actual.

#### `Reloader.stop`

```python
Reloader.stop()
```

Deja de vigilar archivos.

#### `Reloader.reload`

```python
Reloader.reload(changed)
```

Recarga ahora el código de los archivos de `changed` (llámalo en el hilo de la UI).

### `ReloadError`

```python
class ReloadError
```

Lo lanza `view()` mientras la última recarga haya fallado; la ventana muestra su mensaje.

### `Change`

```python
@dataclass
class Change(name, changed=[], added=[], removed=[], new_state=[], updated_state=[])
```

Lo que una recarga cambió en una clase (ver `Reloader.changes`): `name`, los métodos
cambiados (`changed`), nuevos (`added`) y quitados (`removed`), los atributos que los objetos
vivos recibieron del nuevo `__init__` (`new_state`) y los que tomaron su nuevo valor inicial
(`updated_state`).

### `remember`

```python
remember(obj)
```

Guarda (una vez) los valores iniciales simples de `obj`, para que una recarga sepa qué cambió la app.

El runtime lo llama para la app, cada ventana y cada componente; llámalo para otros objetos
creados después de iniciar el hot reload solo si quieres que también se actualicen sus valores iniciales.

## Idiomas

### `t`

```python
t(key, *, language=None, default=None, **values)
```

El texto de `key` en el idioma actual, formateado con `values`. Si falta, prueba de `"es_AR"` a `"es"`, luego el idioma de respaldo y por último devuelve la clave. Ver [Idiomas](/pyzed/es/guides/i18n/).

| Parámetro | Descripción |
| --- | --- |
| `key` | Clave con puntos, como `"menu.open"`. |
| `language` | Busca en otro idioma. |
| `default` | Lo que devuelve si falta la clave (por defecto, la clave). |
| `values` | Valores para los `{nombre}`; `count=` además elige el plural. |

```python
i18n.add("es", {"greeting": "¡Hola, {name}!", "files": {"one": "{count} archivo", "other": "{count} archivos"}})
i18n.set_language("es")
pz.t("greeting", name="Kev"), pz.t("files", count=3)
```

### `add`

```python
add(language, catalog)
```

Añade o reemplaza textos de un idioma. Las tablas anidadas se vuelven claves con puntos; las tablas `{"one": ..., "other": ...}` son plurales.

| Parámetro | Descripción |
| --- | --- |
| `language` | Código de idioma, como `"es"` o `"pt_BR"`. |
| `catalog` | Dict de textos. |

### `load`

```python
load(folder)
```

Carga todos los `<idioma>.json` y `<idioma>.toml` de `folder`; devuelve los idiomas encontrados.

| Parámetro | Descripción |
| --- | --- |
| `folder` | Carpeta con los catálogos. |

### `set_language`

```python
set_language(language)
```

Cambia el idioma. La app lo muestra en el siguiente render, así que llámalo desde un handler.

| Parámetro | Descripción |
| --- | --- |
| `language` | Código de idioma, como `"es"`. |

### `language`

```python
language()
```

El idioma actual, normalizado (`"es_ar"`).

### `languages`

```python
languages()
```

Los idiomas con catálogo.

### `set_fallback`

```python
set_fallback(language)
```

El idioma que se usa cuando falta un texto (por defecto `"en"`).

| Parámetro | Descripción |
| --- | --- |
| `language` | Código de idioma. |

### `on_change`

```python
on_change(listener)
```

Llama a `listener(idioma)` tras cada cambio; devuelve una función que lo quita.

| Parámetro | Descripción |
| --- | --- |
| `listener` | Función que recibe el nuevo idioma. |

### `system_language`

```python
system_language(default='en')
```

El idioma del sistema operativo (`LANG`, `LC_ALL` o el locale).

| Parámetro | Descripción |
| --- | --- |
| `default` | Lo que devuelve si el sistema no informa ninguno. |

### `has`

```python
has(key, *, language=None)
```

Si `key` tiene texto en el idioma o sus respaldos.

| Parámetro | Descripción |
| --- | --- |
| `key` | Clave con puntos. |
| `language` | Idioma a consultar (por defecto, el actual). |

### `normalize`

```python
normalize(language)
```

`"es-AR"`, `"es_AR.UTF-8"` -> `"es_ar"`.

## Referencia integrada

### `Browser`

```python
class Browser
```

Lo que muestra un visor de la referencia: el texto buscado, la página abierta y el historial atrás/adelante.

`ui.reference_browser(browser)` lo dibuja; sus botones y enlaces llaman a los métodos de abajo.

**Métodos y propiedades**

#### `Browser.open`

```python
Browser.open(id)
```

Muestra la página `id` (devuelve `False` si no existe).

#### `Browser.open_symbol`

```python
Browser.open_symbol(symbol)
```

Muestra la página sobre un nombre escrito en código; devuelve si encontró una.

#### `Browser.back`

```python
Browser.back()
```

Vuelve a la página anterior.

#### `Browser.forward`

```python
Browser.forward()
```

Va a la página siguiente después de volver atrás.

#### `Browser.set_query`

```python
Browser.set_query(query)
```

Cambia el texto buscado.

#### `Browser.toggle`

```python
Browser.toggle(section)
```

Pliega o despliega una sección de la lista de clases.

#### `Browser.results`

```python
Browser.results()
```

Las entradas que coinciden con el texto buscado.

#### `Browser.page`

```python
Browser.page()
```

La página mostrada (`None` antes de abrir una).

#### `Browser.follow`

```python
Browser.follow(url)
```

Gestiona un enlace de una página: los internos abren su página; si no, devuelve la URL que hay que abrir.

### `Entry`

```python
@dataclass
class Entry(id, title, section, group='', summary='', icon='book-open', kind='function')
```

Una página de la referencia, tal como la muestran los resultados de búsqueda y la lista de clases.

### `Page`

```python
@dataclass
class Page(entry, body, url=None)
```

Una página completa: la entrada a la que pertenece y su cuerpo en Markdown.

**Métodos y propiedades**

#### `Page.id`

```python
Page.id  # property
```

El id de la entrada.

#### `Page.title`

```python
Page.title  # property
```

El título de la entrada.

### `Provider`

```python
@dataclass
class Provider(name, entries, page, lookup=None)
```

Una sección de la referencia que viene de otro sitio que no son las páginas de la API de la librería.

`entries(lang)` lista sus páginas, `page(id, lang)` construye una (`None` si el id no es suyo)
y `lookup(symbol)` convierte un nombre escrito en código en uno de sus ids.

### `register`

```python
register(provider)
```

Añade una sección a la referencia (reemplaza la que tenga el mismo `name`).

### `entries`

```python
entries(lang=None)
```

Todas las páginas de la referencia, en el orden de la lista de clases (primero los controles del diseñador, luego la librería).

### `sections`

```python
sections(lang=None)
```

La lista de clases: `[(sección, [(grupo, [entradas]), ...]), ...]` en orden.

### `search`

```python
search(query, lang=None, limit=60)
```

Las entradas que coinciden con `query`: primero los nombres exactos, luego los que empiezan por él y después el resto.

Cada palabra debe aparecer en el título, el grupo o el resumen (`"tab bar"` encuentra `ui.tab_bar`).

### `page`

```python
page(id, lang=None)
```

La página con `id` (`KeyError` si no existe).

### `lookup`

```python
lookup(symbol)
```

El id de la página sobre un nombre escrito en código (`"pz.text"`, `"ui.button"`, `"Theme"`...).

### `languages`

```python
languages()
```

Los idiomas en los que están las descripciones de la API.

### `tables_as_lists`

```python
tables_as_lists(markdown)
```

Tablas de Markdown convertidas en listas (`- primera celda: las otras celdas`).

Para visores cuyas tablas no parten las celdas largas, como `ui.reference_browser` en una pestaña estrecha.
Los bloques de código no se tocan.

### `display_name`

```python
display_name(name)
```

`"pyzed.text"` -> `"pz.text"`, `"pyzed.ui.button"` -> `"ui.button"`.

### `summary`

```python
summary(markdown)
```

La primera frase de un texto Markdown, sin formato (para listas y resultados de búsqueda).

## Formularios y validación

### `validation_errors`

```python
validation_errors(error)
```

Convierte un error de validación en `{campo: mensaje}`, listo para `ui.field(..., error=)`. Acepta un `ValidationError` de Pydantic o SQLModel, un `ValidationError` de Django, el JSON de una respuesta 422 de FastAPI (`{"detail": [...]}`) o su lista `detail`. Los campos anidados se unen con puntos y los errores que no son de ningún campo usan la clave `""`. Se guarda solo el primer mensaje de cada campo. Mira [Integraciones](/pyzed/es/integrations/overview/#errores-de-validación-en-cada-campo).

| Parámetro | Descripción |
| --- | --- |
| `error` | El error, o el JSON de la respuesta. |

```python
try:
    item = ItemIn.model_validate(self.draft)
except ValidationError as error:
    self.errors = pz.validation_errors(error)

ui.field("Precio", ui.input(self.draft["price"], self.set_price), error=self.errors.get("price"))
```
