---
title: Create a project
description: "Generate a Pyzed desktop app as a standard uv project with one command: the UI in its own folder, plus ruff, ty and git ready to go."
---

Pyzed installs the `pyzed` command. With [uv](https://docs.astral.sh/uv/) installed, it creates a complete
project:

```bash
pyzed new my-app
cd my-app
uv run pyzed design     # open the main form in the visual designer
uv run pyzed run        # run the app
```

This generates a standard uv project:

```
my-app/
├── pyproject.toml     # dependencies (pyzed-ui; ruff and ty for development) + [tool.pyzed]
├── uv.lock
├── .venv/
├── .git/
├── src/my_app/        # backend
└── ui/                # forms (.pzform) and their event handlers (.py)
```

The UI folder keeps the interface apart from the rest of the code, and its handlers can import the backend, any
module of the project and every dependency. Already have a project made with `uv init`? Run `pyzed init` inside
it. See [Projects with uv](/pyzed/guides/projects/) for the layout, dependency commands and the designer's
Project tab, and [Build and distribute](/pyzed/packaging/build/) to package the app for each platform.

## A single-file app

To start from code instead of the designer, `--script` creates one `main.py` without uv:

```bash
pyzed new my-app --script
cd my-app
python main.py
```

The template already includes:

- A `ui.workspace` with a title bar, left panel and status bar.
- Navigation between pages with `ui.list_item`.
- A command palette that opens with <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>
  and closes with <kbd>Esc</kbd>.
- A button to switch between light and dark themes.

## Find icons

Pyzed includes the ~2000 [Lucide](https://lucide.dev) icons. To search for names:

```bash
pyzed icons folder
# folder, folder-open, folder-git, folder-plus, ...
```

Use them with `pz.icon("folder")` or with the `icon=` parameter of components.

## Run as a module

`python -m pyzed` is equivalent to the `pyzed` command:

```bash
python -m pyzed new another-app
```
