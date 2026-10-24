<h1 align="center">
  <a href="https://albakore.github.io/pyzed/">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/albakore/pyzed/main/assets/brand/pyzed-wordmark-dark.svg">
      <img src="https://raw.githubusercontent.com/albakore/pyzed/main/assets/brand/pyzed-wordmark.svg" alt="Pyzed" width="300">
    </picture>
  </a>
</h1>

<p align="center"><b>English</b> · <a href="https://github.com/albakore/pyzed/blob/main/README.es.md">Español</a></p>

<p align="center">
  <b>Modern, fast desktop GUIs in Python, drawn natively by <a href="https://iced.rs">Iced</a> (Rust).</b><br>
  Components inspired by the <a href="https://zed.dev">Zed</a> editor, a visual designer in the spirit of Godot and Unreal,
  node-based shaders, animations, games and built-in AI agents. A modern alternative to tkinter, PyQt, Kivy and Flet.
</p>

<p align="center">
  <a href="https://pypi.org/project/pyzed-ui/"><img src="https://img.shields.io/pypi/v/pyzed-ui" alt="PyPI"></a>
  <a href="https://pypi.org/project/pyzed-ui/"><img src="https://img.shields.io/pypi/pyversions/pyzed-ui" alt="Python"></a>
  <a href="https://github.com/albakore/pyzed/actions/workflows/ci.yml"><img src="https://github.com/albakore/pyzed/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License: MIT"></a>
</p>

<p align="center">
  📖 <b><a href="https://albakore.github.io/pyzed/">Documentation</a></b> ·
  ⬇️ <b><a href="https://albakore.github.io/pyzed/download/">Download Pyzed Design</a></b> ·
  🧩 <b><a href="https://albakore.github.io/pyzed/library/">Component library</a></b> ·
  📰 <b><a href="CHANGELOG.md">Changelog</a></b>
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/designer-place-controls.webp" alt="Dragging a button, a text box and a check box from the toolbox onto a form in Pyzed Design" width="100%">
</p>

## What is Pyzed

- **Native performance.** Python describes the interface; layout, text and drawing are done by Iced 0.14 in
  Rust (wgpu on the GPU, tiny-skia on the CPU as a fallback). `import pyzed` takes about 35 ms.
- **Simple.** The Elm architecture: state, `update` and `view`. A button can call a method directly
  (`on_press=self.save`), and `update` accepts coroutines, generators and streams.
- **More than 90 components** ready to use: buttons, forms, virtual tables with hundreds of thousands of rows,
  file tree, tabs, command palette, code editor, terminal, custom window frame, charts… They all follow the
  current theme.
- **Pyzed Design**, a visual designer installed as an app: draw forms and components, write their code with
  completion and diagnostics, build node-based shaders and run it all with **F5**.
- **Effects and animations**: animate any property, transitions between windows, glow, bloom, blur, glass and
  WGSL shaders with `pz.shader`.
- **Games**: a game loop (`pz.frames`), held keys, sprites and particles with `pyzed.game`.
- **AI**: an agent panel inside Pyzed Design (Claude, OpenAI, Gemini, Copilot, local models…), `pyzed.agents`
  for your own apps and an MCP server so any agent can build apps with Pyzed.
- **Zed themes**: One, Ayu and Gruvbox included, any Zed theme, generated themes and the system's light/dark mode.
- **Cross-platform**: Linux, macOS and Windows (x86-64 and ARM). IBM Plex fonts and about 2000 Lucide icons
  included.
- **Headless screenshots**: `app.screenshot("ui.png")` renders without a GPU or a display, ideal for tests and
  docs.

<table>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/src/assets/showcase/hud.png" alt="A game HUD made with Pyzed" width="410"><br><sub><b>Showcase: game HUD</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/src/assets/showcase/glass-dashboard.png" alt="A control panel with a glass effect" width="410"><br><sub><b>Glass dashboard</b></sub></td>
</tr>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/src/assets/showcase/main-menu.png" alt="A synthwave main menu" width="410"><br><sub><b>Main menu with shaders</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/audio/ui/synth.webp" alt="A synthesizer made with Pyzed playing notes, with moving knobs, oscilloscope and spectrum" width="410"><br><sub><b>Audio: a synth with knobs, scope and spectrum</b></sub></td>
</tr>
</table>

## Installation

You need Python 3.10 or newer. There are wheels for Linux (glibc and musl), macOS and Windows, so Rust is not
needed.

```bash
uv add pyzed-ui                  # in a uv project
pip install pyzed-ui             # inside an activated virtual environment
python3 -m pip install pyzed-ui  # with the system Python (on Windows: py -m pip install pyzed-ui)
```

Optional extras: `pyzed-ui[mcp]` (MCP server) and `pyzed-ui[agents]` (AI agents in your apps).

The package is `pyzed-ui` on PyPI and is imported as `pyzed`. It is not related to the `pyzed` module of the
Stereolabs ZED camera SDK.

**Pyzed Design** is installed separately as an app, with installers for Windows and macOS and a script for Linux,
and it updates itself: see [Download Pyzed Design](https://albakore.github.io/pyzed/download/).

## Quick start

```python
import pyzed as pz
from pyzed import ui


class Counter(pz.App):
    title = "Counter"
    size = (360, 220)

    def __init__(self):
        self.count = 0

    def update(self, message):          # messages can be any Python value
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
                    # ...or a callable, which is called directly
                    ui.icon_button("rotate-ccw", lambda: setattr(self, "count", 0), tooltip="Reset"),
                ], spacing=8),
            ], spacing=16, align="center"),
            bg=self.theme.editor,
        )


pz.run(Counter)
```

<p align="center"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/counter.webp" alt="The counter: + 1 three times, − 1 once, then Reset" width="360"></p>

Continue with the [quick start](https://albakore.github.io/pyzed/getting-started/quickstart/) and the basic,
intermediate and advanced [tutorials](https://albakore.github.io/pyzed/tutorials/).

### A complete project

```bash
pyzed new my-app          # a uv project: UI in ui/, backend in src/, ruff, ty and git
cd my-app
uv run pyzed design       # opens Pyzed Design on the project
uv run pyzed dev main.py  # hot reload: the window updates on save and keeps its state
uv run pyzed build        # an executable for this platform
```

More in [Create a project](https://albakore.github.io/pyzed/getting-started/new-project/) and
[Distribute](https://albakore.github.io/pyzed/packaging/).

## Pyzed Design

A visual designer made with Pyzed, with Zed's interface: drag components onto a grid with anchors, edit their
properties and styles, double-click to write the code of each event and press **F5** to run it.

<table>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/src/assets/editor/welcome.png" alt="The Pyzed Design welcome window" width="410"><br><sub><b>Welcome screen with sample projects</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/media/shader-graph.webp" alt="Building a shader by connecting nodes in the Shader view, with a live preview" width="410"><br><sub><b>Node-based shaders, like in Godot</b></sub></td>
</tr>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/designer-tabs-anywhere.webp" alt="The Events panel and a form dragged to other docks, with the target lit up" width="410"><br><sub><b>Any tab goes anywhere</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/designer-timer-outline.webp" alt="A Timer dropped on a form lands in the tray and is listed under Non-visual in the Outline" width="410"><br><sub><b>Non-visual components go to the tray</b></sub></td>
</tr>
</table>

- **Form, component, shader and code views**, with tabs that can be torn off into their own window.
- **A Zed-grade code editor**: completion with ty, diagnostics with ruff, multiple cursors, find and replace,
  folding, minimap, configurable shortcuts and IME.
- **Project**: a file tree with Zed's menu, file search, dependencies with uv and a terminal.
- **Custom components** with typed properties, inheritance, data binding and validation.
- **A built-in AI agent** that reads the project, creates forms and complete apps and drives the editor through
  Pyzed's MCP.
- It updates itself, like Zed, with a what's-new tab.

Full manual in [Designer](https://albakore.github.io/pyzed/editor/) and
[Shading](https://albakore.github.io/pyzed/shading/).

## Components

![Component gallery](https://raw.githubusercontent.com/albakore/pyzed/main/docs/screenshots/components-dark.png)

See them in motion (click one to open its page):

<table>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/button/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/button.webp" alt="A Save button with its shortcut, hovered and pressed" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/button/">Button</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/input/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/input.webp" alt="Typing in text fields with icons" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/input/">Input</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/select/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/select.webp" alt="Opening a drop-down and picking an option" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/select/">Select</a></b></sub></td>
</tr>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/slider/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/slider.webp" alt="Dragging two sliders" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/slider/">Slider</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/switch/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/switch.webp" alt="Turning switches on and off" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/switch/">Switch</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/toast/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/toast.webp" alt="Notifications appearing, with an action button" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/toast/">Toast</a></b></sub></td>
</tr>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/command-palette/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/command-palette.webp" alt="Filtering commands as you type" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/command-palette/">Command palette</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/menu/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/menu.webp" alt="A context menu with shortcuts and a check mark" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/menu/">Menu</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/tree/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/tree.webp" alt="Expanding folders in a file tree" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/tree/">Tree</a></b></sub></td>
</tr>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/calendar/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/calendar.webp" alt="Picking a date range in a two-month calendar" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/calendar/">Calendar</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/accordion/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/accordion.webp" alt="Expanding and collapsing sections" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/accordion/">Accordion</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/library/editor/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/components/editor.webp" alt="Typing in the code editor with syntax highlighting" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/library/editor/">Code editor</a></b></sub></td>
</tr>
</table>

<table>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/media/hover.webp" alt="Buttons, a switch, a slider and tabs reacting to the pointer" width="410"><br><sub><b>Hover, press, focus and tooltips</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/media/form-validation.webp" alt="A sign-in form showing an error for an invalid email" width="410"><br><sub><b>Forms with validation</b></sub></td>
</tr>
</table>

Every component has its own page with all its variants, examples and API in the
[library](https://albakore.github.io/pyzed/library/). There are also ready-to-copy
[blocks](https://albakore.github.io/pyzed/blocks/): sign-in screens, settings, dashboards…

Any widget has the usual events of a GUI builder (`click`, `double_click`, `drag`, `key_down`, `resize`…), and
custom components are classes with annotated props, state and events:

```python
class Rating(pz.Component):
    value: int = 0
    events = {"change": "A star was picked"}

    def render(self):
        return pz.row([pz.text("★" if i <= self.value else "☆").on(click=lambda i=i: self.emit("change", i))
                       for i in range(1, 6)])
```

## Animations and effects

Animate any property with presets, keyframes and timelines, move between views with transitions and add
glow, particles or your own WGSL shaders. See [Animation](https://albakore.github.io/pyzed/animation/) and
[Shading](https://albakore.github.io/pyzed/shading/).

<table>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/animation/overview.webp" alt="A dashboard whose cards fade in one after another, with a recording badge and a spinner" width="410"><br><sub><b>Presets, hover and stagger</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/media/shaders.webp" alt="Plasma, tunnel, fire, Voronoi, synthwave and nebula shaders moving" width="410"><br><sub><b>Shaders with <code>pz.shader</code></b></sub></td>
</tr>
<tr>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/animation/transition.webp" alt="A sidebar that widens and narrows smoothly" width="410"><br><sub><b>Transitions</b></sub></td>
<td width="50%" align="center" valign="top"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/public/media/concept-particles.webp" alt="Particle bursts, a fountain, glowing particles and a trail" width="410"><br><sub><b>Particles</b></sub></td>
</tr>
</table>

## Games

Every game in [`examples/games`](examples/games) has a step-by-step tutorial in
[Games](https://albakore.github.io/pyzed/games/).

<table>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/games/snake/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/snake.webp" alt="The Snake game being played" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/games/snake/">Snake</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/games/breakout/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/breakout.webp" alt="The Breakout game: the ball breaks rows of bricks" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/games/breakout/">Breakout</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/games/neon-invaders/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/neon-invaders.webp" alt="Neon Invaders: a ship shooting at waves of aliens" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/games/neon-invaders/">Neon Invaders</a></b></sub></td>
</tr>
<tr>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/games/platformer/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/platformer.webp" alt="A platformer: a character runs, jumps and collects coins" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/games/platformer/">Platformer</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/games/asteroids/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/asteroids.webp" alt="Asteroids: a ship turns and shoots at rocks" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/games/asteroids/">Asteroids</a></b></sub></td>
<td width="33%" align="center" valign="top"><a href="https://albakore.github.io/pyzed/games/puzzle-2048/"><img src="https://raw.githubusercontent.com/albakore/pyzed/main/docs/readme/games/2048.webp" alt="The 2048 puzzle: tiles slide and merge" width="270"></a><br><sub><b><a href="https://albakore.github.io/pyzed/games/puzzle-2048/">2048</a></b></sub></td>
</tr>
</table>

## AI

- **Agent panel** in Pyzed Design: sign in to Claude in the browser or with your subscription, or use OpenAI,
  Gemini, GitHub Copilot, Vertex AI, OpenRouter, Ollama and more. Attach images, connect external MCP servers or
  ACP agents (Gemini CLI, Codex…).
- **MCP server** (`pyzed mcp`): Claude, Cursor, VS Code and other agents look up the exact API, generate and check
  apps and see a screenshot of the result.

  ```bash
  claude mcp add pyzed -- uvx --from "pyzed-ui[mcp]" pyzed mcp
  ```

- **`pyzed.agents`** to add an agent with tools to your own apps.

See [AI](https://albakore.github.io/pyzed/ai/). For language models, the whole documentation is also available as
[llms.txt](https://albakore.github.io/pyzed/llms.txt).

## Integrations

Tutorials and runnable demos with [FastAPI, SQLAlchemy, SQLModel, Django, httpx and Pydantic](https://albakore.github.io/pyzed/integrations/overview/):
where each thing runs (UI thread, asyncio loop, worker threads) and how to show validation errors in forms. The
code is in [`examples/integrations`](examples/integrations).

## Why Pyzed?

Comparisons with tkinter, Qt, Kivy, Flet, Dear PyGui and Toga, with
[measured, reproducible benchmarks](https://albakore.github.io/pyzed/why/benchmarks/) of startup, memory, updates
and installed size ([`benchmarks/`](benchmarks)).

## Examples

| Folder or file | What it shows |
| --- | --- |
| [`examples/counter.py`](examples/counter.py), [`todo.py`](examples/todo.py) | The basics: state, messages, forms and lists. |
| [`examples/gallery.py`](examples/gallery.py) | Every component, interactive, with a theme picker. |
| [`examples/zed_editor.py`](examples/zed_editor.py) | A complete code editor over a real folder. |
| [`examples/showcase/`](examples/showcase) | Game HUD, main menu, inventory, glass dashboard and shader gallery. |
| [`examples/games/`](examples/games) | Snake, Breakout and Neon Invaders. |
| [`examples/integrations/`](examples/integrations) | FastAPI, SQLAlchemy, SQLModel, Django, httpx, Pydantic and aiosqlite. |
| [`examples/effects.py`](examples/effects.py), [`animations.py`](examples/animations.py) | Visual effects and animations. |
| [`examples/window_frame.py`](examples/window_frame.py) | A custom window frame with each platform's menus and buttons. |
| [`examples/ai_chat.py`](examples/ai_chat.py) | A chat with an AI agent. |
| [`examples/designer/`](examples/designer) | A Pyzed Design form (`.pzform` + `.py`). |
| [`examples/tutorial/`](examples/tutorial), [`hot_reload/`](examples/hot_reload) | Step-by-step tutorial and hot reload. |

They all run with `python examples/<file>.py` (or `uv run`). More in
[Examples](https://albakore.github.io/pyzed/examples/).

## How it works

```
Python                         Rust (pyzed._core, PyO3)                 Iced 0.14
App.view() ──► Widget tree ──► render.rs: Widget → iced::Element ──► layout + wgpu/tiny-skia
App.update() ◄── messages ◄────── app.rs: Message, Command → Task ◄──── events (mouse, keyboard)
```

Widgets are immutable Rust objects, so building the view from Python is cheap. The internal state of each editor
lives in Rust and the GIL is released while the event loop runs. More in
[Architecture](https://albakore.github.io/pyzed/guides/architecture/).

## Developing Pyzed

```bash
git clone https://github.com/albakore/pyzed && cd pyzed
uv sync                     # builds the Rust core (1.88 or newer) and installs pyzed in editable mode
uv run pytest tests
uv run python examples/gallery.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Pyzed follows [semantic versioning](https://semver.org/) since 1.0; the
policy and known limitations are in [Stability](https://albakore.github.io/pyzed/guides/stability/).

## License

MIT. The bundled fonts are IBM Plex (SIL Open Font License) and Lucide (ISC); their licenses are in
[`assets/fonts`](assets/fonts). The One, Ayu and Gruvbox themes come from the Zed repository (MIT); see
[`python/pyzed/zed_themes/LICENSE`](python/pyzed/zed_themes/LICENSE).
