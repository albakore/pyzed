---
title: Create a project
description: Generate a complete app with the Pyzed CLI.
---

Pyzed installs the `pyzed` command, which creates a project ready to run:

```bash
pyzed new my-app
cd my-app
python main.py
```

This generates:

```
my-app/
├── main.py            # app with title bar, sidebar, status bar and command palette
└── requirements.txt   # pyzed
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
