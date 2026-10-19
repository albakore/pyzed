---
title: Projects
description: "Create and open uv projects in Pyzed Design, browse and search files, manage dependencies, run ruff and ty, and create the git repository."
sidebar:
  order: 1
---

A Pyzed app is a normal [uv](https://docs.astral.sh/uv/) project: the interface lives in `ui/`, the backend in
`src/` and uv manages the dependencies. The **Project** panel (left dock, next to **Design**) shows the project's
files, like the project panel of Zed or the explorer of VS Code, and the **Dependencies** panel next to it manages
packages, tools and checks, all without leaving the editor. The background, the layout of a project and the matching `pyzed` commands are in
[Projects with uv](/pyzed/guides/projects/).

![The Project panel: the project's files and folders](../../../../screenshots/designer-project.png)

## How the editor finds your project

When the editor starts, it looks for a Pyzed project (a `pyproject.toml` with a `[tool.pyzed]` table) at the file
you opened or above it, or above the current folder. If it finds one it:

- **opens it** in the Project panel, makes its folder the working folder and remembers it among the recent
  projects;
- **activates** it, so forms and handlers can import `ui/` helpers, the `src/` package and every dependency of
  its `.venv`;
- **discovers its components**: every `.pzcomp` of the project joins the toolbox;
- **checks its tools** in the background (uv, git, ruff and ty, with their versions).

The title bar then shows the project's name before the file name: click it to bring the Project panel to the
front.

## No project open

With no project, the panel offers **New project** and **Open…**, and lists your recent projects (click one to
open it).

![The New project dialog](../../../../screenshots/editor-new-project.png)

### New project

| Field | What it does |
| --- | --- |
| **Name** | The project's name and folder name. |
| **Location** | The folder it is created in; the dialog shows the full path it will create. **Browse…** opens the folder browser: walk to a folder and press **Choose this folder**. |
| **Backend in src/** | `uv init --package`: a `src/<name>/` package importable from the UI and from tests. Off gives a flat layout (`uv init --app`). |
| **Git repository** | Runs `git init` and writes a `.gitignore`. |

**Create** runs uv in the background and then opens the new project and its main form. The target folder must be
empty, or already be a project.

### Open project

**Open…** shows a folder browser instead of a text field:

![The Open project dialog: places, recent projects and the folders of the current one](../../../../screenshots/editor-open-project.png)

- The bar at the top goes to the **parent folder** (up arrow) or **home**, and every part of the path is
  clickable. The eye shows or hides hidden folders.
- The path field below it takes a folder typed or pasted; <kbd>Enter</kbd> goes there.
- On the left, the usual **places** (home, desktop, documents, downloads, the disks) and your **recent**
  projects (click one to open it).
- On the right, the folders of the current one; click a folder to go into it. Folders that are uv projects (they
  have a `pyproject.toml`) carry a **project** badge and their own **Open** button.

**Open** at the bottom opens the folder you are in when it is a project. If the project has a main form, it
opens in a tab.

## The project panel

### Header

The project's name, version and folder. On the right, the current **git branch**, or **Create repository** when
the folder is not a repository yet (it runs `git init` and writes a `.gitignore`, like Zed), and a folder button
that opens another project.

While a command runs, a bar with a spinner says what is going on (`Adding httpx`, `Syncing the environment`...).
Commands run on a worker thread, so you can keep designing while uv downloads packages.

### Files

Under the header, the project's files and folders as a tree, like Zed's project panel. Folders open and close with
a click (the `ui/` and `src/` folders start open); files are colored by their git status (modified, new, deleted,
conflict) and folders take the color of what changed inside them. Virtual environments, caches and build output
(`.venv`, `__pycache__`, `build`, `dist`...) are left out; hidden files such as `.gitignore` stay.

Clicking a file opens it where it belongs:

| File | Opens |
| --- | --- |
| `.pzform`, `.pzcomp` | In a designer tab. |
| The `.py` of a form or component | Its form, with the whole code file in the [code panel](/pyzed/editor/code-editor/). |
| Anything else | In the system's app for that file type. |

The toolbar above the tree has a **search field** for files and folders (it matches letters in order, like Zed's
file finder, and file names count more than folders: `crt` finds `ui/cart.pzform`), **New file**, **New
folder** (in the selected folder), **Collapse all** and **Refresh**. The tree reloads by itself when you save and
after uv commands.

**Right-click** a file or folder (or the empty space below the tree, for the project folder) for its menu:

| Item | What it does |
| --- | --- |
| **Open** / **Open with the system app** | Opens the file in the editor or with its default app. |
| **Reveal in file manager** | Shows it in Files, Finder or Explorer. |
| **New file…** / **New folder…** | Creates one in that folder (a new file opens right away). |
| **Copy path** / **Copy relative path** | Copies the full path or the path from the project folder. |
| **Rename…** | Renames it in place. |
| **Delete…** | Deletes it after asking (a folder with everything in it); it cannot be undone. |

### Go to file

<kbd>Ctrl</kbd>+<kbd>P</kbd> (or **File → Go to file…**) opens a search over every file and folder of the
project. Type part of a name and press <kbd>Enter</kbd> for the best match, or click a result; a folder is revealed
in the Project panel.

## The Dependencies panel

With a project open, the left dock gets a **Dependencies** panel next to **Project** (when the three titles do not
fit, the panels not shown keep only their icon).

![The Dependencies panel: packages, tools and the output of ruff](../../../../screenshots/designer-dependencies.png)

### Dependencies

| Control | Runs |
| --- | --- |
| **Add package** field + **+** (or <kbd>Enter</kbd>) | `uv add <packages>`. Type several separated by spaces, or a constraint such as `httpx>=0.28`. Tick **dev** for the dev group. |
| **Pencil** on a row | Opens **Change**: type a new requirement (`httpx==0.27.2`, `httpx>=0.28,<1`) and apply it. |
| **Up arrow** on a row | Upgrades that package within its constraint. |
| **Trash** on a row | `uv remove` from the group it is in. |
| **Refresh** in the section header | `uv sync`: makes `.venv` match `uv.lock`. |
| **Search** in the section header | **Check for updates**: looks up newer versions; rows with one show `↑version` in green (hover it for the change). |
| **Up arrow** in the section header | Upgrades every package. |

Dependencies of other groups show their group as a badge.

### Tools

uv, git, ruff and ty with the version found, or a red **missing** badge. Under them:

- **Lint** runs `ruff check` on the project.
- **Format** runs `ruff format`.
- **Types** runs `ty check`.

The **Output** section at the bottom shows the command that ran (`$ ruff check`) and the last lines of its output,
in red when it failed. A failed command also shows a notification with its last line.

:::tip
Ruff reads its rules from `[tool.ruff]` in `pyproject.toml`, so **Lint** and the code editor's inline warnings
follow the same configuration.
:::

## Running forms of a project

When the editor runs inside the project's own environment (you started it with `uv run pyzed design`), **Run**
(<kbd>F5</kbd>) runs the form in the editor's process. When it does not (the standalone app, or `pyzed design`
installed with `uv tool`), **Run** saves the form and starts it with `uv run pyzed run --reload` in the project,
so it has every dependency of `.venv` and updates on every save. Its output is piped into the
[console](/pyzed/editor/console-and-running/) either way.

## Building the app

The Project panel does not package apps; use the command line in the project folder:

```bash
uv run pyzed build            # a folder with the executable for this platform
uv run pyzed build --onefile  # a single file
uv run pyzed build --workflow # a GitHub Actions workflow for Linux, Windows and macOS
```

See [Build and distribute](/pyzed/guides/packaging/).

## The standalone app

**Pyzed Design** is also published as a standalone app for Linux, Windows and macOS: the editor compiled with its
own Python and the `uv` binary, so nothing else needs to be installed. Projects created from it are normal uv
projects with their own `.venv`, and their forms always run through `uv run`.

:::tip
If completion does not know a package you just added, press **Restart servers** in the
[editor settings](/pyzed/editor/code-editor/#editor-settings) after the sync finishes: the language servers read
the project's `.venv` when they start.
:::
