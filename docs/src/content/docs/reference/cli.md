---
title: CLI
description: The pyzed new and pyzed icons commands.
sidebar:
  order: 9
---

Installing Pyzed adds the `pyzed` command (also available as `python -m pyzed`).

## `pyzed new <name>`

Creates a folder with a ready-to-run app from a template.

```bash
pyzed new my-app
cd my-app && python main.py
```

| File | Contents |
| --- | --- |
| `main.py` | App with `ui.workspace`, title bar, sidebar with pages, status bar, command palette (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>) and theme switching. |
| `requirements.txt` | `pyzed` |

The app title is derived from the folder name (`my-app` → `My App`). It fails if the folder
exists and is not empty.

## `pyzed icons [filter]`

Lists the names of the bundled Lucide icons that contain `filter`.

```bash
pyzed icons arrow
```
