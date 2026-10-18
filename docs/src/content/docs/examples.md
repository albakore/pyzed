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
