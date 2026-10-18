# Changelog

Todos los cambios relevantes de Pyzed se registran aquí. El formato sigue
[Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto usa
[versionado semántico](https://semver.org/lang/es/).

Cada versión es un encabezado `## [X.Y.Z] - AAAA-MM-DD` con las secciones que apliquen:
`### Breaking changes`, `### Añadido`, `### Cambiado`, `### Corregido`, `### Eliminado`.
Las versiones con sufijo (`1.0.0-rc.1`, `0.2.0b1`) se consideran preliminares.
La web de documentación lee este archivo en cada build y marca la última versión estable.

## [Sin publicar]

## [0.1.0] - 2026-10-18

Primera versión.

### Añadido

- Runtime al estilo Elm sobre Iced 0.14 (`App`, `update`, `view`, `on_start`, `on_key`).
- Mensajes como cualquier valor de Python o como callables que se llaman directamente.
- `Command`: `exit`, `focus`, `set_editor_text`, `set_editor_cursor`, `scroll_to_end`, `batch`, `message` y `perform` (trabajo en un hilo).
- `pz.post()` para enviar mensajes desde otros hilos.
- Widgets base: `text`, `column`, `row`, `container`, `center`, `button`, `text_input`, `scrollable`, `space`, `rule`, `mouse_area`, `stack`, `opaque`, `hover`, `tooltip`, `checkbox`, `toggler`, `slider`, `progress_bar`, `code_editor`, `svg` e `icon`.
- Unos 40 componentes al estilo Zed en `pyzed.ui`: botones, formularios, listas, árbol de archivos, pestañas, workspace con docks, paleta de comandos, toasts, editor de código y terminal.
- Temas One Dark, One Light y Gruvbox Dark con los tokens de color de Zed, y `Theme.derive()`.
- Fuentes IBM Plex e iconos Lucide incluidos.
- Capturas fuera de pantalla con `app.screenshot()` (sin GPU ni display).
- CLI: `pyzed new` y `pyzed icons`.
