# Pyzed

**Interfaces modernas y rápidas en Python, renderizadas por [Iced](https://iced.rs) (Rust).**
Incluye componentes listos para usar inspirados en el editor [Zed](https://zed.dev).

![Recreación del editor Zed hecha con Pyzed](docs/screenshots/zed-one-dark.png)

> Esta captura es una app de Python ([`examples/zed_editor.py`](examples/zed_editor.py)):
> panel de proyecto, pestañas, editor con resaltado de sintaxis, marcadores de git,
> barra de estado, paleta de comandos y temas. Todo se dibuja con Iced.

## Por qué Pyzed

- **Rendimiento nativo.** Python solo describe la interfaz. El layout, el texto y el dibujado
  (wgpu, con tiny-skia como respaldo por software) los hace Iced 0.14 en Rust, mediante PyO3.
- **Sencillo.** Sigue la arquitectura Elm de Iced (estado, `update` y `view`). Un botón puede
  llamar directamente a un método: `on_press=self.guardar`.
- **Componentes listos.** Unos 40 componentes al estilo Zed (botones, pestañas, árbol de archivos,
  paleta de comandos, editor de código, terminal, menús, notificaciones…), todos personalizables.
- **Temas.** Incluye las familias One, Ayu y Gruvbox importadas de Zed, puede leer cualquier
  tema de Zed, generar uno a partir de tres colores y seguir el modo claro/oscuro del sistema.
- **Async y varias ventanas.** `async def`, generadores y streams en `update`, temporizadores con
  `pz.every` y tantas ventanas como quieras con `pz.Window`.
- **Multiplataforma.** Linux, macOS y Windows. Las fuentes (IBM Plex) y los iconos
  (Lucide, ~2000) van incluidos.
- **Capturas sin ventana.** `app.screenshot("ui.png")` renderiza fuera de pantalla, sin GPU ni
  display. Sirve para tests y documentación (así se generaron todas estas imágenes).

## Instalación

Por ahora se instala desde el código fuente. Necesitas Rust estable y Python 3.9 o superior.

```bash
pip install git+https://github.com/albakore/pyzed
```

Para desarrollar:

```bash
git clone https://github.com/albakore/pyzed && cd pyzed
python -m venv .venv && source .venv/bin/activate
pip install maturin
maturin develop --release   # usa --release: la build debug es mucho más lenta
```

## Inicio rápido

```python
import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    title = "Counter"
    size = (360, 220)

    def __init__(self):
        self.count = 0

    def update(self, message):          # los mensajes pueden ser cualquier valor de Python
        if message == "increment":
            self.count += 1
        elif message == "decrement":
            self.count -= 1

    def view(self):
        return pz.center(
            pz.column([
                ui.heading(str(self.count)),
                pz.row([
                    ui.button("-1", "decrement", icon="minus"),
                    ui.button("+1", "increment", icon="plus", variant="solid"),
                    # ...o un callable, que se llama directamente
                    ui.icon_button("rotate-ccw", lambda: setattr(self, "count", 0), tooltip="Reset"),
                ], spacing=8),
            ], spacing=16, align="center"),
            bg=self.theme.editor,
        )


pz.run(Counter)
```

<img src="docs/screenshots/counter.png" width="360" alt="Contador">

### Crear un proyecto nuevo

```bash
pyzed new mi-app      # crea mi-app/main.py con barra de título, sidebar, estado y paleta de comandos
cd mi-app && python main.py
pyzed icons folder    # busca nombres de iconos
```

## Conceptos

| Concepto | Cómo funciona |
| --- | --- |
| `App` | Tu estado vive en el objeto. `view()` devuelve widgets y `update(msg)` cambia el estado. |
| Mensajes | `on_press=valor` envía `valor` a `update`. Si es un callable (lambda, método), se llama directamente. Lo que devuelva, si no es `None`, se envía a `update`. |
| Callbacks con datos | `on_input`, `on_toggle`, `on_change`… reciben el valor nuevo: `on_input=lambda t: setattr(self, "query", t)`. |
| `Command` | Efectos que devuelve `update` o un callback: `Command.focus("id")`, `Command.exit()`, `Command.set_editor_text(id, txt)`, `Command.set_editor_cursor(id, línea, col)`, `Command.scroll_to(id, x, y)`, `Command.copy(txt)`, `Command.batch([...])` y `Command.perform(fn, then)`, que ejecuta `fn` (normal o `async def`) en segundo plano y entrega el resultado a `then`. |
| Async | `update` y los callbacks pueden devolver una corrutina, un generador o un generador `async`: cada resultado vuelve a `update`. Todo corre en un único loop de asyncio. |
| Suscripciones | `subscriptions()` devuelve `pz.every(segundos, msg)` (temporizador) y `pz.listen(gen)` (streams). Solo existen mientras las devuelves. |
| Ventanas | `class Ajustes(pz.Window)` con su propio `view()`, título, tamaño y tema; se abre con `return Ajustes().open()`. Ganchos: `on_open`, `on_close`, `on_resize`. |
| Atajos | `on_key(self, combo)` recibe cada tecla al estilo Zed: `"ctrl-shift-p"`, `"escape"`, `"up"`… |
| Hilos | `pz.post(mensaje)` envía un mensaje a la app desde cualquier hilo. |
| Inicio | `on_start()` se ejecuta una vez y puede devolver un `Command` o una corrutina. |
| Errores | Si `view()` lanza una excepción, la ventana muestra el traceback en vez de cerrarse. |

### Widgets base (`pyzed`)

`text`, `column`, `row`, `container`, `center`, `button`, `text_input`, `scrollable`, `space`,
`hspace`, `vspace`, `rule`, `mouse_area`, `stack`, `opaque`, `hover`, `tooltip`, `checkbox`,
`toggler`, `slider`, `vertical_slider`, `progress_bar`, `code_editor`, `svg`, `icon`,
`image` e `image_viewer` (PNG, JPEG… o píxeles RGBA), `canvas` (dibujo 2D con `pyzed.draw`),
`markdown`, `rich_text` + `span`, `qr_code`, `pick_list`, `radio`, `split`, `grid`, `pin` y
`responsive`. Los contenedores aceptan `gradient=(ángulo, [colores])`.

Los tamaños aceptan píxeles, `"fill"`, `"shrink"` o `"fill:2"` (proporción). El padding acepta
`8`, `(v, h)` o `(arriba, derecha, abajo, izquierda)`. Los colores aceptan `"#rrggbb[aa]"` o
tuplas `(r, g, b[, a])`.

## Componentes (`pyzed.ui`)

![Galería de componentes](docs/screenshots/components-dark.png)

| Grupo | Componentes |
| --- | --- |
| Básicos | `label`, `muted`, `heading`, `button` (filled, ghost, outline, solid, error/warning/success; tamaños xs a lg; atajo opcional), `icon_button`, `badge`, `indicator`, `kbd`, `avatar`, `tooltip`, `divider`, `card` |
| Formularios | `input`, `search_input`, `switch`, `checkbox`, `slider`, `progress`, `segmented`, `field`, `select`, `radio_group`, `number_field`, `split_button`, `toggle_group`, `chip`, `disclosure` |
| Datos y feedback | `table` + `Column` (orden y selección), `callout`, `count_badge`, `facepile`, `diff_stat`, `keybinding_hint`, `empty_state`, `settings_group`, `stat`, `sparkline`, `bar_chart`, `donut`, `spinner`, `markdown`, `split` |
| Listas | `list_item`, `list_header`, `tree` + `TreeNode.from_paths(...)` (panel de proyecto con estados de git), `menu` + `MenuItem` |
| Navegación | `tab_bar` + `Tab.for_file(...)` (sucia, vista previa, estado git, cierre al pasar el ratón), `breadcrumbs`, `toolbar` |
| Workspace | `workspace` (layout con docks izquierdo, derecho e inferior), `title_bar`, `title_button`, `status_bar`, `status_item`, `panel`, `panel_header` |
| Overlays | `layer` (capa con fondo y cierre al hacer clic fuera), `modal`, `popover` (menús contextuales), `picker`, `command_palette` + `PaletteItem`, `fuzzy_filter`, `toast`, `toasts` |
| Código | `editor` (resaltado de sintaxis, números de línea, marcadores de git, scroll horizontal con números fijos, ajuste de línea, `on_change` y `on_cursor`), `terminal` (con colores ANSI), `ansi` |

Todos leen sus colores del tema actual y aceptan `theme=` u otros parámetros para cambiarlos.

## Temas

```python
class MiApp(pz.App):
    theme = "Ayu Dark"                     # cualquier nombre de pz.themes.names()
    # theme = pz.themes.auto("One Light", "One Dark")   # sigue al sistema

oceano = pz.themes.ONE_DARK.derive(name="Océano", syntax={"keyword": "#ff79c6"}).with_accent("#4fb3ff")
propio = pz.Theme.generate("Propio", background="#1b1d23", text="#e6e6e6", accent="#ff8a65")
de_zed = pz.Theme.from_zed("catppuccin.json", name="Catppuccin Mocha")   # temas de Zed
```

Cambiar `self.theme` en `update` cambia el estilo de toda la interfaz al momento.

| One Light + terminal + outline | Paleta de comandos |
| --- | --- |
| ![One Light](docs/screenshots/zed-one-light.png) | ![Paleta](docs/screenshots/zed-command-palette.png) |
| **Buscador de archivos (Gruvbox)** | **Componentes (One Light)** |
| ![Buscador](docs/screenshots/zed-file-finder.png) | ![Componentes claros](docs/screenshots/components-light.png) |

## Ejemplos

| Archivo | Qué muestra |
| --- | --- |
| [`examples/counter.py`](examples/counter.py) | Lo mínimo: estado, mensajes y callables. |
| [`examples/gallery.py`](examples/gallery.py) | Todos los componentes, interactivos, con selector de tema. |
| [`examples/zed_editor.py`](examples/zed_editor.py) | Un editor tipo Zed sobre una carpeta real: abrir, editar y guardar (`ctrl-s`), paleta (`ctrl-shift-p`), buscador (`ctrl-p`), docks (`ctrl-b`, `ctrl-j`, `ctrl-alt-b`) y temas. El panel de terminal muestra una salida de ejemplo; no ejecuta una shell. |
| [`examples/tutorial/`](examples/tutorial) | Tutorial en cinco pasos, de una ventana vacía a una app de notas. |
| [`examples/todos.py`](examples/todos.py) | Lista de tareas con edición, filtros y guardado (demo `todos` de Iced). |
| [`examples/game_of_life.py`](examples/game_of_life.py) | Juego de la vida en un `canvas` con `pz.every`. |
| [`examples/clock.py`](examples/clock.py), [`stopwatch.py`](examples/stopwatch.py) | Reloj analógico y cronómetro con vueltas. |
| [`examples/download_progress.py`](examples/download_progress.py) | Descargas concurrentes con generadores `async`. |
| [`examples/websocket_stream.py`](examples/websocket_stream.py) | Datos en vivo con `pz.listen`. |
| [`examples/multi_window.py`](examples/multi_window.py) | Varias ventanas con estado compartido y temas distintos. |
| [`examples/image_viewer.py`](examples/image_viewer.py) | `image` e `image_viewer` con zoom y desplazamiento. |
| [`examples/markdown_viewer.py`](examples/markdown_viewer.py) | Editor de Markdown con vista previa en un `split`. |
| [`examples/styling.py`](examples/styling.py) | Selector de temas, tema del sistema y temas generados. |
| [`examples/context_menu.py`](examples/context_menu.py), [`panes.py`](examples/panes.py), [`qr_code.py`](examples/qr_code.py) | Menú contextual, paneles redimensionables y códigos QR. |
| [`examples/screenshots.py`](examples/screenshots.py) | Regenera las imágenes de `docs/screenshots`. |

## Cómo funciona

```
Python                         Rust (pyzed._core, PyO3)                 Iced 0.14
App.view() ──► árbol de Widget ──► render.rs: Widget → iced::Element ──► layout + wgpu/tiny-skia
App.update() ◄── mensajes ◄────── app.rs: Message, Command → Task ◄──── eventos (ratón, teclado)
```

- Los nodos `Widget` son objetos inmutables de Rust, así que construir la vista desde Python es barato.
- El estado interno de cada editor (texto, cursor, deshacer) vive en Rust y se identifica por `id`.
- El resaltado usa syntect (gramáticas de `two-face`) con los colores del tema de Pyzed.
- El GIL se libera mientras corre el bucle de eventos, así que otros hilos de Python siguen funcionando.

## Estado y limitaciones

Es la versión 0.2. Limitaciones conocidas:

- `pz.run()` solo puede llamarse una vez por proceso (limitación de winit); usa `pz.Window`
  para más ventanas.
- Con `wrap=True`, el editor numera la primera fila de cada línea ajustada, como Zed.

## Licencia

MIT. Las fuentes incluidas son IBM Plex (SIL Open Font License) y Lucide (ISC); sus
licencias están en [`assets/fonts`](assets/fonts). Los temas One, Ayu y Gruvbox vienen del
repositorio de Zed (MIT); ver [`python/pyzed/zed_themes/LICENSE`](python/pyzed/zed_themes/LICENSE).
