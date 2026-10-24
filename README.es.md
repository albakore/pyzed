<h1 align="center">
  <a href="https://albakore.github.io/pyzed/es/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/albakore/pyzed/main/assets/brand/pyzed-wordmark-dark.svg">
      <img src="https://raw.githubusercontent.com/albakore/pyzed/main/assets/brand/pyzed-wordmark.svg" alt="Pyzed" width="300">
    </picture>
  </a>
</h1>

<p align="center"><a href="https://github.com/albakore/pyzed/blob/main/README.md">English</a> · <b>Español</b></p>

<p align="center">
  <b>Interfaces de escritorio modernas y rápidas en Python, dibujadas por <a href="https://iced.rs">Iced</a> (Rust).</b><br>
  Componentes inspirados en el editor <a href="https://zed.dev">Zed</a>, un diseñador visual al estilo de Godot y Unreal,
  shaders por nodos, animaciones, juegos y agentes de IA integrados.
</p>

<p align="center">
  <a href="https://pypi.org/project/pyzed-ui/"><img src="https://img.shields.io/pypi/v/pyzed-ui" alt="PyPI"></a>
  <a href="https://pypi.org/project/pyzed-ui/"><img src="https://img.shields.io/pypi/pyversions/pyzed-ui" alt="Python"></a>
  <a href="https://github.com/albakore/pyzed/actions/workflows/ci.yml"><img src="https://github.com/albakore/pyzed/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licencia-MIT-blue" alt="Licencia: MIT"></a>
</p>

<p align="center">
  📖 <b><a href="https://albakore.github.io/pyzed/es/">Documentación</a></b> ·
  ⬇️ <b><a href="https://albakore.github.io/pyzed/es/download/">Descargar Pyzed Design</a></b> ·
  🧩 <b><a href="https://albakore.github.io/pyzed/es/library/">Biblioteca de componentes</a></b> ·
  📰 <b><a href="CHANGELOG.md">Novedades</a></b>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/designer-place-controls.webp" alt="Un botón, un cuadro de texto y una casilla arrastrados desde la caja de herramientas a un formulario en Pyzed Design" width="100%">
</p>

## Qué es Pyzed

- **Rendimiento nativo.** Python describe la interfaz; el layout, el texto y el dibujado los hace Iced 0.14 en
  Rust (wgpu en la GPU, tiny-skia por CPU como respaldo). `import pyzed` tarda unos 35 ms.
- **Sencillo.** Arquitectura Elm: estado, `update` y `view`. Un botón puede llamar directamente a un método
  (`on_press=self.guardar`), y `update` acepta corrutinas, generadores y streams.
- **Más de 90 componentes** listos para usar: botones, formularios, tablas virtuales de cientos de miles de filas,
  árbol de archivos, pestañas, paleta de comandos, editor de código, terminal, marco de ventana propio, gráficos…
  Todos siguen el tema actual.
- **Pyzed Design**, un diseñador visual que se instala como una app: dibuja formularios y componentes, escribe su
  código con autocompletado y diagnósticos, crea shaders por nodos y ejecútalo todo con **F5**.
- **Efectos y animaciones**: anima cualquier propiedad, transiciones entre ventanas, glow, bloom, blur, cristal y
  shaders WGSL con `pz.shader`.
- **Juegos**: bucle de juego (`pz.frames`), teclas mantenidas, sprites y partículas con `pyzed.game`.
- **IA**: un panel de agentes dentro de Pyzed Design (Claude, OpenAI, Gemini, Copilot, modelos locales…),
  `pyzed.agents` para tus apps y un servidor MCP para que cualquier agente construya apps con Pyzed.
- **Temas de Zed**: One, Ayu y Gruvbox incluidos, cualquier tema de Zed, temas generados y modo claro/oscuro
  del sistema.
- **Multiplataforma**: Linux, macOS y Windows (x86-64 y ARM). Fuentes IBM Plex y unos 2000 iconos Lucide incluidos.
- **Capturas sin ventana**: `app.screenshot("ui.png")` renderiza sin GPU ni pantalla, ideal para tests y docs.

<table>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/src/assets/showcase/hud.png" alt="HUD de un juego hecho con Pyzed" width="410"><br><sub><b>Showcase: HUD de juego</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/src/assets/showcase/glass-dashboard.png" alt="Panel de control con efecto cristal" width="410"><br><sub><b>Panel de cristal</b></sub></td>
</tr>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/src/assets/showcase/main-menu.png" alt="Menú principal synthwave" width="410"><br><sub><b>Menú principal con shaders</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/audio/ui/synth.webp" alt="Un sintetizador hecho con Pyzed tocando notas, con perillas, osciloscopio y espectro en movimiento" width="410"><br><sub><b>Audio: un sintetizador con perillas, osciloscopio y espectro</b></sub></td>
</tr>
</table>

## Instalación

Necesitas Python 3.10 o superior. Hay wheels para Linux (glibc y musl), macOS y Windows, así que no hace falta Rust.

```bash
uv add pyzed-ui                  # en un proyecto de uv
pip install pyzed-ui             # dentro de un entorno virtual activado
python3 -m pip install pyzed-ui  # con el Python del sistema (en Windows: py -m pip install pyzed-ui)
```

Extras opcionales: `pyzed-ui[mcp]` (servidor MCP) y `pyzed-ui[agents]` (agentes de IA en tus apps).

**Pyzed Design** se instala aparte como app, con instaladores para Windows y macOS y un script para Linux, y se
actualiza solo: ver [Descargar Pyzed Design](https://albakore.github.io/pyzed/es/download/).

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
                    ui.button("1", "decrement", icon="minus"),
                    ui.button("1", "increment", icon="plus", variant="solid"),
                    # ...o un callable, que se llama directamente
                    ui.icon_button("rotate-ccw", lambda: setattr(self, "count", 0), tooltip="Reset"),
                ], spacing=8),
            ], spacing=16, align="center"),
            bg=self.theme.editor,
        )


pz.run(Counter)
```

<p align="center"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/counter.webp" alt="El contador: + 1 tres veces, − 1 una vez y luego Reset" width="360"></p>

Sigue con el [inicio rápido](https://albakore.github.io/pyzed/es/getting-started/quickstart/) y los
[tutoriales](https://albakore.github.io/pyzed/es/tutorials/) básicos, intermedios y avanzados.

### Un proyecto completo

```bash
pyzed new mi-app          # proyecto de uv: UI en ui/, backend en src/, ruff, ty y git
cd mi-app
uv run pyzed design       # abre Pyzed Design en el proyecto
uv run pyzed dev main.py  # hot reload: la ventana se actualiza al guardar y conserva el estado
uv run pyzed build        # ejecutable para esta plataforma
```

Más en [Crear un proyecto](https://albakore.github.io/pyzed/es/getting-started/new-project/) y
[Distribuir](https://albakore.github.io/pyzed/es/packaging/).

## Pyzed Design

Un diseñador visual hecho con Pyzed, con la interfaz de Zed: arrastra componentes a una grilla con anclajes, edita
sus propiedades y estilos, haz doble clic para escribir el código de cada evento y pulsa **F5** para ejecutarlo.

<table>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/src/assets/editor/welcome.png" alt="Ventana de bienvenida de Pyzed Design" width="410"><br><sub><b>Ventana de bienvenida con proyectos de ejemplo</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/media/shader-graph.webp" alt="Un shader creado conectando nodos en la vista Shader, con vista previa en vivo" width="410"><br><sub><b>Shaders por nodos, como en Godot</b></sub></td>
</tr>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/designer-tabs-anywhere.webp" alt="El panel Events y un formulario arrastrados a otros paneles, con el destino iluminado" width="410"><br><sub><b>Cualquier pestaña va a cualquier sitio</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/designer-timer-outline.webp" alt="Un Timer soltado en un formulario va a la bandeja y aparece bajo Non-visual en el Outline" width="410"><br><sub><b>Los componentes no visuales van a la bandeja</b></sub></td>
</tr>
</table>

- **Vistas** de formulario, componente, shader y código, con pestañas que se pueden sacar a su propia ventana.
- **Editor de código** de nivel Zed: autocompletado con ty, diagnósticos con ruff, varios cursores, buscar y
  reemplazar, plegado, minimapa, atajos configurables e IME.
- **Proyecto**: árbol de archivos con el menú de Zed, búsqueda de archivos, dependencias con uv y terminal.
- **Componentes propios** con propiedades tipadas, herencia, data binding y validación.
- **Agente de IA** integrado que lee el proyecto, crea formularios y apps completas y controla el editor a través
  del MCP de Pyzed.
- Se actualiza solo, como Zed, con una pestaña de novedades.

Manual completo en [Diseñador](https://albakore.github.io/pyzed/es/editor/) y
[Shading](https://albakore.github.io/pyzed/es/shading/).

## Componentes

![Galería de componentes](https://raw.githubusercontent.com/albakore/pyzed/main/docs/screenshots/components-dark.png)

Míralos en movimiento (haz clic en uno para abrir su página):

<table>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/button/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/button.webp" alt="Un botón Save con su atajo, al pasar el ratón y al pulsarlo" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/button/">Botón</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/input/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/input.webp" alt="Escribiendo en campos de texto con iconos" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/input/">Campo de texto</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/select/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/select.webp" alt="Abriendo un desplegable y eligiendo una opción" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/select/">Desplegable</a></b></sub></td>
</tr>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/slider/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/slider.webp" alt="Arrastrando dos deslizadores" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/slider/">Deslizador</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/switch/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/switch.webp" alt="Encendiendo y apagando interruptores" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/switch/">Interruptor</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/toast/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/toast.webp" alt="Notificaciones que aparecen, con un botón de acción" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/toast/">Notificación</a></b></sub></td>
</tr>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/command-palette/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/command-palette.webp" alt="Filtrando comandos mientras se escribe" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/command-palette/">Paleta de comandos</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/menu/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/menu.webp" alt="Un menú contextual con atajos y una marca" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/menu/">Menú</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/tree/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/tree.webp" alt="Abriendo carpetas en un árbol de archivos" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/tree/">Árbol</a></b></sub></td>
</tr>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/calendar/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/calendar.webp" alt="Eligiendo un rango de fechas en un calendario de dos meses" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/calendar/">Calendario</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/accordion/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/accordion.webp" alt="Abriendo y cerrando secciones" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/accordion/">Acordeón</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/library/editor/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/editor.webp" alt="Escribiendo en el editor de código con resaltado de sintaxis" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/library/editor/">Editor de código</a></b></sub></td>
</tr>
</table>

<table>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/media/hover.webp" alt="Botones, un interruptor, un deslizador y pestañas reaccionando al puntero" width="410"><br><sub><b>Hover, pulsación, foco y tooltips</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/media/form-validation.webp" alt="Un formulario de inicio de sesión que muestra un error por un email no válido" width="410"><br><sub><b>Formularios con validación</b></sub></td>
</tr>
</table>

Cada componente tiene su página con todas sus variantes, ejemplos y API en la
[biblioteca](https://albakore.github.io/pyzed/es/library/). También hay [bloques](https://albakore.github.io/pyzed/es/blocks/)
listos para copiar: pantallas de inicio de sesión, ajustes, paneles…

Cualquier widget tiene los eventos habituales de un editor gráfico (`click`, `double_click`, `drag`, `key_down`,
`resize`…), y los componentes propios son clases con props anotados, estado y eventos:

```python
class Rating(pz.Component):
    value: int = 0
    events = {"change": "Se eligió una estrella"}

    def render(self):
        return pz.row([pz.text("★" if i <= self.value else "☆").on(click=lambda i=i: self.emit("change", i))
                       for i in range(1, 6)])
```

## Animaciones y efectos

Anima cualquier propiedad con presets, keyframes y líneas de tiempo, pasa de una vista a otra con transiciones y
añade glow, partículas o tus propios shaders WGSL. Mira [Animación](https://albakore.github.io/pyzed/es/animation/) y
[Shading](https://albakore.github.io/pyzed/es/shading/).

<table>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/animation/overview.webp" alt="Un panel cuyas tarjetas aparecen una tras otra, con una insignia de grabación y un spinner" width="410"><br><sub><b>Presets, hover y escalonado</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/media/shaders.webp" alt="Shaders de plasma, túnel, fuego, Voronoi, synthwave y nebulosa en movimiento" width="410"><br><sub><b>Shaders con <code>pz.shader</code></b></sub></td>
</tr>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/animation/transition.webp" alt="Una barra lateral que se ensancha y se estrecha con suavidad" width="410"><br><sub><b>Transiciones</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/concept-particles.webp" alt="Explosiones de partículas, una fuente, partículas con brillo y una estela" width="410"><br><sub><b>Partículas</b></sub></td>
</tr>
</table>

## Juegos

Cada juego de [`examples/games`](examples/games) tiene un tutorial paso a paso en
[Juegos](https://albakore.github.io/pyzed/es/games/).

<table>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/games/snake/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/snake.webp" alt="Una partida de Snake" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/games/snake/">Snake</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/games/breakout/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/breakout.webp" alt="Breakout: la bola rompe filas de ladrillos" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/games/breakout/">Breakout</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/games/neon-invaders/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/neon-invaders.webp" alt="Neon Invaders: una nave dispara a oleadas de alienígenas" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/games/neon-invaders/">Neon Invaders</a></b></sub></td>
</tr>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/games/platformer/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/platformer.webp" alt="Un juego de plataformas: el personaje corre, salta y recoge monedas" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/games/platformer/">Plataformas</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/games/asteroids/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/asteroids.webp" alt="Asteroids: una nave gira y dispara a las rocas" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/games/asteroids/">Asteroids</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/es/games/puzzle-2048/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/2048.webp" alt="El puzle 2048: las fichas se deslizan y se suman" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/es/games/puzzle-2048/">2048</a></b></sub></td>
</tr>
</table>

## IA

- **Panel de agentes** en Pyzed Design: inicia sesión en Claude por navegador o con tu suscripción, o usa OpenAI,
  Gemini, GitHub Copilot, Vertex AI, OpenRouter, Ollama y más. Adjunta imágenes, conecta servidores MCP externos
  o agentes ACP (Gemini CLI, Codex…).
- **Servidor MCP** (`pyzed mcp`): Claude, Cursor, VS Code y otros agentes consultan la API exacta, generan y
  comprueban apps y ven una captura del resultado.

  ```bash
  claude mcp add pyzed -- uvx --from "pyzed-ui[mcp]" pyzed mcp
  ```

- **`pyzed.agents`** para añadir un agente con herramientas a tus propias apps.

Ver [IA](https://albakore.github.io/pyzed/es/ai/).

## Integraciones

Tutoriales y demos ejecutables con [FastAPI, SQLAlchemy, SQLModel, Django, httpx y Pydantic](https://albakore.github.io/pyzed/es/integrations/overview/):
dónde corre cada cosa (hilo de la UI, loop de asyncio, hilos de trabajo) y cómo mostrar errores de validación en
los formularios. El código está en [`examples/integrations`](examples/integrations).

## ¿Por qué Pyzed?

Comparativas con tkinter, Qt, Kivy, Flet, Dear PyGui y Toga, con
[benchmarks medidos y reproducibles](https://albakore.github.io/pyzed/es/why/benchmarks/) de arranque, memoria,
actualización y tamaño instalado ([`benchmarks/`](benchmarks)).

## Ejemplos

| Carpeta o archivo | Qué muestra |
| --- | --- |
| [`examples/counter.py`](examples/counter.py), [`todo.py`](examples/todo.py) | Lo mínimo: estado, mensajes, formularios y listas. |
| [`examples/gallery.py`](examples/gallery.py) | Todos los componentes, interactivos, con selector de tema. |
| [`examples/zed_editor.py`](examples/zed_editor.py) | Un editor de código completo sobre una carpeta real. |
| [`examples/showcase/`](examples/showcase) | HUD de juego, menú principal, inventario, panel de cristal y galería de shaders. |
| [`examples/games/`](examples/games) | Snake, Breakout y Neon Invaders. |
| [`examples/integrations/`](examples/integrations) | FastAPI, SQLAlchemy, SQLModel, Django, httpx, Pydantic y aiosqlite. |
| [`examples/effects.py`](examples/effects.py), [`animations.py`](examples/animations.py) | Efectos visuales y animaciones. |
| [`examples/window_frame.py`](examples/window_frame.py) | Marco de ventana propio con menús y botones de cada plataforma. |
| [`examples/ai_chat.py`](examples/ai_chat.py) | Un chat con un agente de IA. |
| [`examples/designer/`](examples/designer) | Un formulario de Pyzed Design (`.pzform` + `.py`). |
| [`examples/tutorial/`](examples/tutorial), [`hot_reload/`](examples/hot_reload) | Tutorial paso a paso y hot reload. |

Todos se ejecutan con `python examples/<archivo>.py` (o `uv run`). Más en
[Ejemplos](https://albakore.github.io/pyzed/es/examples/).

## Cómo funciona

```
Python                         Rust (pyzed._core, PyO3)                 Iced 0.14
App.view() ──► árbol de Widget ──► render.rs: Widget → iced::Element ──► layout + wgpu/tiny-skia
App.update() ◄── mensajes ◄────── app.rs: Message, Command → Task ◄──── eventos (ratón, teclado)
```

Los widgets son objetos inmutables de Rust, así que construir la vista desde Python es barato. El estado interno
de cada editor vive en Rust y el GIL se libera mientras corre el bucle de eventos. Más en
[Arquitectura](https://albakore.github.io/pyzed/es/guides/architecture/).

## Desarrollar Pyzed

```bash
git clone https://github.com/albakore/pyzed && cd pyzed
uv sync                     # compila el núcleo de Rust (1.88 o superior) e instala pyzed editable
uv run pytest tests
uv run python examples/gallery.py
```

Ver [CONTRIBUTING.md](CONTRIBUTING.md). Pyzed sigue [versionado semántico](https://semver.org/lang/es/) desde la
1.0; la política y las limitaciones conocidas están en
[Estabilidad](https://albakore.github.io/pyzed/es/guides/stability/).

## Licencia

MIT. Las fuentes incluidas son IBM Plex (SIL Open Font License) y Lucide (ISC); sus licencias están en
[`assets/fonts`](assets/fonts). Los temas One, Ayu y Gruvbox vienen del repositorio de Zed (MIT); ver
[`python/pyzed/zed_themes/LICENSE`](python/pyzed/zed_themes/LICENSE).
