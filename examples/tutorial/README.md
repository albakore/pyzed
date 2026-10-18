# Tutorial de Pyzed

Cinco pasos cortos, cada uno es un archivo que se ejecuta solo:

```bash
python examples/tutorial/step1_hello.py
```

## 1. Una ventana ([`step1_hello.py`](step1_hello.py))

Una app es una clase que hereda de `pz.App` y define `view()`. `view()` devuelve un árbol de
widgets (`pz.text`, `pz.column`, `pz.row`, `pz.container`…). Pyzed la vuelve a llamar después
de cada cambio, así que nunca modificas widgets: describes cómo se ve el estado actual.

Atributos de clase como `title` y `size` configuran la ventana.

## 2. Estado y mensajes ([`step2_state.py`](step2_state.py))

El estado son atributos normales de tu objeto. Los widgets reciben qué hacer de dos formas:

- **Un valor** (`ui.button("Greet", "greet")`): se envía a `update(message)`.
- **Un callable** (`ui.button("Reset", self.reset)`): se llama directamente.

Los callbacks que traen datos reciben el valor nuevo: `on_input=lambda text: ...`,
`on_toggle=lambda checked: ...`, `on_change=lambda value: ...`.

## 3. Layout, componentes y temas ([`step3_layout.py`](step3_layout.py))

`pyzed.ui` trae componentes al estilo de Zed: `button`, `input`, `select`, `switch`,
`number_field`, `settings_group`, `field`, `callout`, `table`, `editor`… Todos toman sus colores
del tema activo.

`theme` puede ser un `Theme`, el nombre de un tema incluido (`pz.themes.names()`: One, Ayu y
Gruvbox, importados de Zed) o `pz.themes.auto("One Light", "One Dark")` para seguir al sistema.
Cambiarlo en cualquier momento re-estiliza toda la ventana. `self.resolved_theme()` devuelve el
`Theme` en uso para leer colores (`t.background`, `t.accent`…).

Para crear tu propio tema: `pz.Theme.generate("Mío", background="#1b1d23", text="#e6e6e6",
accent="#ff8a65")`, `tema.with_accent("#...")`, o `pz.Theme.from_zed("mi-tema.json")` para usar
cualquier tema de Zed.

## 4. Async ([`step4_async.py`](step4_async.py))

El trabajo lento no debe bloquear la ventana. Opciones:

- `return pz.Command.perform(funcion, then)`: `funcion` corre en segundo plano (un hilo, o el loop
  de asyncio si es `async def`) y `then(resultado)` se llama en el hilo de la UI.
- Devolver una corrutina desde `update` o desde un callback: su resultado vuelve a `update`.
- Devolver un generador o un generador `async`: cada valor que produce va a `update`. Ideal para
  progreso (ver [`download_progress.py`](../download_progress.py)).
- `subscriptions()` devuelve fuentes continuas: `pz.every(segundos, mensaje)` (temporizador) y
  `pz.listen(generador)` (streams, websockets; ver [`websocket_stream.py`](../websocket_stream.py)).
  Se vuelve a evaluar tras cada cambio, así que una suscripción existe solo mientras la devuelves.

Todas las corrutinas comparten un único loop de asyncio (`pz.asyncio_loop()`), así que
librerías como `aiohttp` funcionan sin configuración.

## 5. Todo junto ([`step5_notes.py`](step5_notes.py))

Una app de notas con lista lateral, editor con vista previa de Markdown en un `ui.split`
redimensionable, un atajo (`on_key` recibe combinaciones como `"ctrl-n"`) y una segunda ventana.

Las ventanas extra son subclases de `pz.Window` con su propio `view()`, título, tamaño y tema.
Se abren con `return MiVentana().open()` y comparten el estado de la app (`self.app`).

## Siguientes pasos

Los demás archivos de [`examples/`](..) recrean las demos de Iced (todos, game of life, reloj,
cronómetro, descargas, multi-ventana, imágenes, QR, estilos, paneles) y la galería de componentes.
