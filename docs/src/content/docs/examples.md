---
title: Ejemplos
description: Apps de ejemplo incluidas en el repositorio, listas para ejecutar.
---

Todos los ejemplos están en [`examples/`](https://github.com/albakore/pyzed/tree/main/examples).
Ejecútalos desde la raíz del repositorio:

```bash
python examples/<nombre>.py
```

| Ejemplo | Qué muestra | Tutorial |
| --- | --- | --- |
| [`counter.py`](https://github.com/albakore/pyzed/blob/main/examples/counter.py) | Lo mínimo: estado, mensajes y callables. | [Inicio rápido](/pyzed/getting-started/quickstart/) |
| [`todo.py`](https://github.com/albakore/pyzed/blob/main/examples/todo.py) | Formularios, listas, filtros, foco y atajos. | [Lista de tareas](/pyzed/tutorials/todo-app/) |
| [`downloads.py`](https://github.com/albakore/pyzed/blob/main/examples/downloads.py) | `Command.perform`, `pz.post` desde hilos, progreso y notificaciones. | [Tareas en segundo plano](/pyzed/tutorials/background-tasks/) |
| [`mini_editor.py`](https://github.com/albakore/pyzed/blob/main/examples/mini_editor.py) | Un editor tipo Zed en ~150 líneas. | [Mini editor](/pyzed/tutorials/zed-like-editor/) |
| [`gallery.py`](https://github.com/albakore/pyzed/blob/main/examples/gallery.py) | Todos los componentes, interactivos, con selector de tema. | [Componentes](/pyzed/components/overview/) |
| [`zed_editor.py`](https://github.com/albakore/pyzed/blob/main/examples/zed_editor.py) | Editor completo: buscador de archivos, paleta, docks, terminal, temas y marcadores de git. | |
| [`tutorial/`](https://github.com/albakore/pyzed/tree/main/examples/tutorial/) | Cinco pasos: ventana, estado, layout y temas, async, app de notas. | [Tutorial en 5 pasos](/pyzed/tutorials/step-by-step/) |
| [`todos.py`](https://github.com/albakore/pyzed/blob/main/examples/todos.py) | Las *todos* de Iced: añadir, editar, completar, filtrar y guardar. |  |
| [`game_of_life.py`](https://github.com/albakore/pyzed/blob/main/examples/game_of_life.py) | `pz.canvas` con miles de celdas y `pz.every` como motor. | [Canvas](/pyzed/guides/canvas/) |
| [`clock.py`](https://github.com/albakore/pyzed/blob/main/examples/clock.py) | Reloj analógico dibujado en un canvas. | [Canvas](/pyzed/guides/canvas/) |
| [`stopwatch.py`](https://github.com/albakore/pyzed/blob/main/examples/stopwatch.py) | Cronómetro con vueltas y atajos. | [Async](/pyzed/guides/async/) |
| [`download_progress.py`](https://github.com/albakore/pyzed/blob/main/examples/download_progress.py) | Descargas concurrentes con generadores `async` y progreso. | [Async](/pyzed/guides/async/) |
| [`websocket_stream.py`](https://github.com/albakore/pyzed/blob/main/examples/websocket_stream.py) | Datos en vivo con `pz.listen` y un generador `async`. | [Async](/pyzed/guides/async/) |
| [`multi_window.py`](https://github.com/albakore/pyzed/blob/main/examples/multi_window.py) | Varias `pz.Window` con estado compartido y temas distintos. | [Varias ventanas](/pyzed/guides/windows/) |
| [`styling.py`](https://github.com/albakore/pyzed/blob/main/examples/styling.py) | Selector de temas, modo del sistema, `Theme.generate` y acentos. | [Temas](/pyzed/guides/theming/) |
| [`image_viewer.py`](https://github.com/albakore/pyzed/blob/main/examples/image_viewer.py) | `pz.image` y el visor con zoom `pz.image_viewer`. | [Contenido](/pyzed/components/content/#imágenes) |
| [`markdown_viewer.py`](https://github.com/albakore/pyzed/blob/main/examples/markdown_viewer.py) | Editor de Markdown con vista previa en vivo. | [Contenido](/pyzed/components/content/) |
| [`qr_code.py`](https://github.com/albakore/pyzed/blob/main/examples/qr_code.py) | Genera un código QR mientras escribes. | [Contenido](/pyzed/components/content/) |
| [`panes.py`](https://github.com/albakore/pyzed/blob/main/examples/panes.py) | Paneles redimensionables con `ui.split` anidados. | [Contenido](/pyzed/components/content/#paneles-redimensionables) |
| [`context_menu.py`](https://github.com/albakore/pyzed/blob/main/examples/context_menu.py) | Menú contextual con `ui.popover` y `ui.menu`. | [Contenido](/pyzed/components/content/#popover) |
| [`screenshots.py`](https://github.com/albakore/pyzed/blob/main/examples/screenshots.py) | Regenera las capturas de la documentación. | [Tests y capturas](/pyzed/guides/testing/) |

## Editor tipo Zed

```bash
python examples/zed_editor.py .
```

Atajos: <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> paleta, <kbd>Ctrl</kbd>+<kbd>P</kbd>
buscador de archivos, <kbd>Ctrl</kbd>+<kbd>S</kbd> guardar, <kbd>Ctrl</kbd>+<kbd>B</kbd>,
<kbd>Ctrl</kbd>+<kbd>J</kbd> y <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>B</kbd> docks.

![Editor tipo Zed en One Dark](../../../screenshots/zed-one-dark.png)

| Paleta de comandos | Buscador de archivos (Gruvbox) |
| --- | --- |
| ![Paleta](../../../screenshots/zed-command-palette.png) | ![Buscador](../../../screenshots/zed-file-finder.png) |

## Galería de componentes

```bash
python examples/gallery.py
```

![Galería en One Light](../../../screenshots/components-light.png)

## Descargas

![Descargas](../../assets/tutorials/downloads.png)

## Demos de Iced

Recreaciones en Python de las [demos de Iced](https://github.com/iced-rs/iced/tree/master/examples).

| Game of Life | Estilos |
| --- | --- |
| ![Game of Life](../../assets/tutorials/game-of-life.png) | ![Estilos](../../assets/tutorials/styling.png) |

| Reloj | Cronómetro |
| --- | --- |
| ![Reloj](../../assets/examples/clock.png) | ![Cronómetro](../../assets/examples/stopwatch.png) |

| Todos | Código QR |
| --- | --- |
| ![Todos](../../assets/examples/todos.png) | ![Código QR](../../assets/examples/qr_code.png) |

| Visor de imágenes | Markdown |
| --- | --- |
| ![Visor de imágenes](../../assets/examples/image_viewer.png) | ![Markdown](../../assets/examples/markdown_viewer.png) |

### Varias ventanas

![Varias ventanas](../../assets/tutorials/multi-window.png)

Las capturas de esta página se generan con `python docs/scripts/example_shots.py`.
