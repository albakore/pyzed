---
title: CLI
description: Los comandos pyzed new y pyzed icons.
sidebar:
  order: 9
---

Al instalar Pyzed se añade el comando `pyzed` (también disponible como `python -m pyzed`).

## `pyzed new <nombre>`

Crea una carpeta con una app lista para ejecutar a partir de una plantilla.

```bash
pyzed new mi-app
cd mi-app && python main.py
```

| Archivo | Contenido |
| --- | --- |
| `main.py` | App con `ui.workspace`, barra de título, sidebar con páginas, barra de estado, paleta de comandos (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>) y cambio de tema. |
| `requirements.txt` | `pyzed` |

El título de la app se deriva del nombre de la carpeta (`mi-app` → `Mi App`). Falla si la carpeta
existe y no está vacía.

## `pyzed icons [filtro]`

Lista los nombres de los iconos de Lucide incluidos que contienen `filtro`.

```bash
pyzed icons arrow
```
