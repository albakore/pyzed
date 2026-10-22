# Pyzed

[English](README.md) · **Español**

**Interfaces de escritorio modernas y rápidas en Python, dibujadas por [Iced](https://iced.rs) (Rust).**
Componentes inspirados en el editor [Zed](https://zed.dev), un diseñador visual al estilo de Godot y Unreal,
shaders por nodos, animaciones, juegos y agentes de IA integrados.

[![PyPI](https://img.shields.io/pypi/v/pyzed-ui)](https://pypi.org/project/pyzed-ui/)
[![Python](https://img.shields.io/pypi/pyversions/pyzed-ui)](https://pypi.org/project/pyzed-ui/)
[![CI](https://github.com/albakore/pyzed/actions/workflows/ci.yml/badge.svg)](https://github.com/albakore/pyzed/actions/workflows/ci.yml)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)

📖 **[Documentación](https://albakore.github.io/pyzed/es/)** ·
⬇️ **[Descargar Pyzed Design](https://albakore.github.io/pyzed/es/download/)** ·
🧩 **[Biblioteca de componentes](https://albakore.github.io/pyzed/es/library/)** ·
📰 **[Novedades](CHANGELOG.md)**

![Pyzed Design con un formulario de inicio de sesión abierto](docs/src/assets/editor/form-view.png)

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

| Showcase: HUD de juego | Panel de cristal |
| --- | --- |
| ![HUD de un juego hecho con Pyzed](docs/src/assets/showcase/hud.png) | ![Panel de control con efecto cristal](docs/src/assets/showcase/glass-dashboard.png) |
| **Menú principal con shaders** | **Neon Invaders** |
| ![Menú principal synthwave](docs/src/assets/showcase/main-menu.png) | ![Juego Neon Invaders](docs/src/assets/games/neon-invaders.png) |

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

<img src="docs/screenshots/counter.png" width="360" alt="Contador">

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

| Pantalla de bienvenida con proyectos de ejemplo | Shaders por nodos, como en Godot |
| --- | --- |
| ![Ventana de bienvenida de Pyzed Design](docs/src/assets/editor/welcome.png) | ![Vista Shader con un grafo de nodos](docs/src/assets/shading/shader-view.png) |

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

![Galería de componentes](docs/screenshots/components-dark.png)

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
